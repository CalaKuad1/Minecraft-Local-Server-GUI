import asyncio
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import sys
import json
import logging
from queue import Queue

# --- CRITICAL: DEBUG LOGGING FOR PROD ---
# Log to AppData so we can see why it crashes in .exe
try:
    if sys.platform == "win32":
        log_dir = os.path.join(os.getenv("APPDATA"), "MinecraftServerGUI")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), ".minecraft_server_gui")
        
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logging.basicConfig(
        filename=os.path.join(log_dir, "backend_debug.log"),
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info("Backend starting up...")
    logging.info(f"CWD: {os.getcwd()}")
    logging.info(f"Python executable: {sys.executable}")
except Exception as e:
    # Fallback to print if logging fails
    print(f"Logging setup failed: {e}")

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.server_handler import ServerHandler
from server.config_manager import ConfigManager
from utils.java_manager import JavaManager
from utils.server_detector import ServerDetector
from utils.api_client import get_server_versions, get_forge_versions, download_server_jar

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global State ---
class AppState:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # PROD FIX: Use APPDATA for mutable data
        if sys.platform == "win32":
            self.app_data_dir = os.path.join(os.getenv("APPDATA"), "MinecraftServerGUI")
        else:
            self.app_data_dir = os.path.join(os.path.expanduser("~"), ".minecraft_server_gui")
            
        if not os.path.exists(self.app_data_dir):
            os.makedirs(self.app_data_dir)
            
        # Config Path
        self.config_path = os.path.join(self.app_data_dir, "gui_config.json")
        default_config = os.path.join(self.script_dir, "gui_config.json")
        
        # Check if config exists in AppData, if not copy from default (if exists) or create empty
        if not os.path.exists(self.config_path):
            if os.path.exists(default_config):
                try:
                    with open(default_config, 'r') as f:
                        data = f.read()
                    with open(self.config_path, 'w') as f:
                        f.write(data)
                except Exception as e:
                    print(f"Failed to copy default config: {e}")
            else:
                # Create empty default config
                 with open(self.config_path, 'w') as f:
                    f.write(json.dumps({"servers": []}))

        self.config_manager = ConfigManager(self.config_path)
        
        # Java Runtimes in AppData
        self.java_runtimes_dir = os.path.join(self.app_data_dir, "java_runtimes")
        self.java_manager = JavaManager(self.java_runtimes_dir)
        
        self.server_handler: Optional[ServerHandler] = None
        self.active_websockets: List[WebSocket] = []
        self.log_history: List[dict] = []
        self.loop = asyncio.get_running_loop()
        self.selected_server_id = None
        
        # Tunnel management
        self.tunnel_process = None
        self.tunnel_address = None
        
        # Do not initialize handler automatically on startup anymore
        # self.initialize_handler() 

    def load_server(self, server_id):
        server_config = self.config_manager.get_server(server_id)
        if not server_config:
            raise ValueError("Server not found")
            
        server_path = server_config.get("path")
        if not server_path or not os.path.exists(server_path):
            raise ValueError(f"Server path invalid: {server_path}")
            
        self.selected_server_id = server_id
        
        # Clear log history when switching servers
        self.log_history.clear()
        self.broadcast_log_sync(f"Switched to server: {server_config.get('name', server_id)}", "info")
        
        # If a handler is already running, we might want to stop it? 
        # For now, we assume user stops server before switching.
        # TODO: Enforce stop before switch?
        
        self.server_handler = ServerHandler(
            server_path=server_path,
            server_type=server_config.get("type") or server_config.get("server_type") or "vanilla",
            ram_min=server_config.get("ram_min", "2"),
            ram_max=server_config.get("ram_max", "4"),
            ram_unit=server_config.get("ram_unit", "G"),
            output_callback=self.broadcast_log_sync,
            minecraft_version=server_config.get("version") or server_config.get("minecraft_version")
        )
        self.config_manager.config["last_selected_id"] = server_id
        self.config_manager.save()
        return server_config

    def broadcast_log_sync(self, message, level="normal"):
        """Thread-safe wrapper to broadcast logs from synchronous code."""
        try:
            if isinstance(message, dict):
                 msg_obj = message
            else:
                 msg_obj = {"message": message, "level": level}
            asyncio.run_coroutine_threadsafe(self.broadcast_log(msg_obj), self.loop)
        except Exception as e:
            print(f"Error logging: {e}")

    async def broadcast_log(self, message: dict):
        # Debug print to verify python is receiving logs
        print(f"DEBUG: Broadcasting log: {message.get('message', '')[:50]}...", flush=True)
        
        # Store in history (keep last 500 lines)
        self.log_history.append(message)
        if len(self.log_history) > 500:
            self.log_history.pop(0)

        for websocket in self.active_websockets[:]:
            try:
                await websocket.send_json(message)
            except:
                if websocket in self.active_websockets:
                    self.active_websockets.remove(websocket)

state: Optional[AppState] = None

@app.on_event("startup")
async def startup_event():
    global state
    state = AppState()

# --- Models ---
class ServerConfig(BaseModel):
    name: str # New field
    path: str
    type: str
    version: Optional[str] = None
    ram_min: str
    ram_max: str
    ram_unit: str

class CommandRequest(BaseModel):
    command: str

class InstallRequest(BaseModel):
    server_type: str
    version: str
    parent_path: str
    folder_name: str
    forge_version: Optional[str] = None

class ValidatePathRequest(BaseModel):
    path: str

class SelectServerRequest(BaseModel):
    server_id: str

# --- Core Endpoints ---

@app.get("/servers")
async def list_servers():
    return state.config_manager.get_all_servers()

@app.post("/servers")
async def add_server(config: ServerConfig):
    # This endpoint creates a new profile
    data = config.dict()
    # Ensure validation
    if not os.path.exists(data['path']):
         # If path doesn't exist, we might be creating a new one soon, 
         # but for "import" it should exist. 
         # For "create", the wizard creates folder first.
         pass 
         
    new_server = state.config_manager.add_server(data)
    return new_server

@app.post("/servers/select")
async def select_server(req: SelectServerRequest):
    try:
        config = state.load_server(req.server_id)
        return {"status": "success", "server": config}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/servers/{server_id}")
async def delete_server(server_id: str):
    state.config_manager.delete_server(server_id)
    if state.selected_server_id == server_id:
        state.server_handler = None
        state.selected_server_id = None
    return {"status": "deleted"}

@app.get("/status")
def get_status():
    if not state or not state.server_handler:
        return {"status": "not_configured"}
    
    stats = state.server_handler.get_stats()
    return {
        "status": "online" if state.server_handler.is_running() else "starting" if state.server_handler.is_starting() else "offline",
        "pid": state.server_handler.get_pid(),
        "server_type": state.server_handler.server_type,
        "minecraft_version": state.server_handler.minecraft_version,
        "cpu": stats["cpu"],
        "ram": stats["ram"],
        "uptime": stats["uptime"],
        "recent_logs": state.log_history[-15:] # Return last 15 lines for the mini console
    }

@app.post("/start")
def start_server():
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.start()
    return {"message": "Start command issued"}

@app.post("/stop")
def stop_server():
    if not state or not state.server_handler:
         raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.stop()
    return {"message": "Stop command issued"}

@app.post("/command")
def send_console_command(cmd: CommandRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.send_command(cmd.command)
    return {"message": "Command sent"}

@app.post("/configure")
def configure_server(config: ServerConfig):
    if not state: raise HTTPException(status_code=500, detail="App state not initialized")
    state.config_manager.set("server_path", config.server_path)
    state.config_manager.set("server_type", config.server_type)
    state.config_manager.set("ram_min", config.ram_min)
    state.config_manager.set("ram_max", config.ram_max)
    state.config_manager.set("ram_unit", config.ram_unit)
    if config.minecraft_version:
        state.config_manager.set("minecraft_version", config.minecraft_version)
    state.config_manager.save()
    state.initialize_handler()
    return {"message": "Configuration saved"}

# --- Setup Endpoints ---

@app.get("/setup/versions/{server_type}")
def getting_versions(server_type: str):
    if server_type.lower() == "forge":
        # Return a simplified list or the structured dict
        versions = get_forge_versions()
        return {"versions": list(versions.keys()), "all_data": versions}
    else:
        # returns list of dicts {version: "1.20.1", ...}
        data = get_server_versions(server_type) 
        # Extract just version strings for easier frontend consumption
        versions = [v['version'] for v in data] if data else []
        return {"versions": versions}

@app.get("/setup/java/check/{minecraft_version}")
def check_java_status(minecraft_version: str):
    if not state: raise HTTPException(status_code=500, detail="App state not initialized")
    return state.java_manager.get_java_status(minecraft_version)

class InstallJavaRequest(BaseModel):
    minecraft_version: str

class DetectRequest(BaseModel):
    path: str

@app.post("/setup/detect")
def detect_server_info(req: DetectRequest):
    detector = ServerDetector()
    return detector.detect(req.path)

    threading.Thread(target=run_java_install, daemon=True).start()
    return {"message": "Java installation started"}

@app.post("/setup/java/install")
def install_java_endpoint(req: InstallJavaRequest):
    if not state: raise HTTPException(status_code=500, detail="App state not initialized")
    
    logging.info(f"Received Java install request for MC {req.minecraft_version}")

    def run_java_install():
        try:
            logging.info("Starting run_java_install thread")
            # Log the java manager base dir
            logging.info(f"JavaManager base dir: {state.java_manager.base_dir}")
            
            required_version = state.java_manager.get_required_java_version(req.minecraft_version)
            logging.info(f"Required Java version: {required_version}")
            
            def send_progress(pct):
                logging.debug(f"Java Progress: {pct}%")
                state.broadcast_log_sync({
                    "type": "java_progress", 
                    "value": pct, 
                    "message": f"Downloading Java {required_version}..."
                })

            send_progress(0)
            state.broadcast_log_sync(f"Starting Java {required_version} download...", "info")
            
            logging.info("Calling download_java...")
            java_path = state.java_manager.download_java(required_version, progress_callback=send_progress)
            logging.info(f"download_java returned: {java_path}")
            
            if java_path:
                send_progress(100)
                state.broadcast_log_sync(f"Java installed at {java_path}", "success")
                logging.info("Java install success broadcasted")
            else:
                logging.error("Java download execution returned None")
                state.broadcast_log_sync("Java download failed", "error")
                state.broadcast_log_sync({"type": "java_progress", "value": 0, "error": "Download failed"})

        except Exception as e:
            logging.exception("Exception in run_java_install:")
            state.broadcast_log_sync(f"Java install error: {e}", "error")
            state.broadcast_log_sync({"type": "java_progress", "value": 0, "error": str(e)})

    threading.Thread(target=run_java_install, daemon=True).start()
    return {"message": "Java installation started"}

@app.post("/setup/validate-path")
def validate_path(req: ValidatePathRequest):
    if os.path.isdir(req.path):
        # Check if valid server
        has_jar = any(f.endswith('.jar') for f in os.listdir(req.path))
        return {"valid": True, "has_jar": has_jar}
    return {"valid": False, "error": "Directory does not exist"}

@app.post("/setup/install")
def install_server(req: InstallRequest):
    if not state: raise HTTPException(status_code=500, detail="App state not initialized")
    
    install_path = os.path.join(req.parent_path, req.folder_name)
    os.makedirs(install_path, exist_ok=True)
    
    def run_install():
        try:
            # Helper to send structured progress
            def send_progress(pct, msg):
                state.broadcast_log_sync({
                    "type": "progress", 
                    "value": pct, 
                    "message": msg
                })

            send_progress(0, f"Starting installation of {req.server_type} {req.version}...")
            state.broadcast_log_sync(f"Install location: {install_path}", "info")

            # Progress wrapper for download functions
            def progress_callback(p):
                send_progress(p, "Downloading server files...")

            if req.server_type.lower() == "forge":
                # Need to use ServerHandler's logic or extract it
                # For now, we instantiate a temp handler just for installation
                temp_handler = ServerHandler(install_path, "forge", "1", "2", "G", output_callback=lambda m, l: state.broadcast_log_sync(m, l), minecraft_version=req.version)
                
                # Wrap the progress to match our format
                def forge_progress(p):
                    send_progress(p, "Installing Forge...")
                    
                temp_handler.install_forge_server(req.forge_version, req.version, forge_progress)
            else:
                jar_path = os.path.join(install_path, "server.jar")
                success = download_server_jar(req.server_type, req.version, jar_path, progress_callback)
                if success:
                    send_progress(100, "Download complete.")
                else:
                    send_progress(0, "Download failed.")
                    state.broadcast_log_sync("Failed to download Server JAR.", "error")
                    return

            send_progress(100, "Configuring server...")
            
            send_progress(100, "Configuring server...")
            
            # Create new server profile
            new_server_data = {
                "name": req.folder_name,
                "path": install_path,
                "type": req.server_type,
                "version": req.version,
                "ram_min": "2",
                "ram_max": "4",
                "ram_unit": "G"
            }
            
            saved_server = state.config_manager.add_server(new_server_data)
            state.load_server(saved_server["id"]) # Auto-select so dashboard is ready
            
            send_progress(100, "Installation complete!")
            state.broadcast_log_sync("Installation complete! You can now start the server.", "success")
            
        except Exception as e:
            state.broadcast_log_sync(f"Installation failed: {e}", "error")
            # Send error event so frontend stops spinning
            state.broadcast_log_sync({"type": "progress", "value": 0, "error": str(e)})

    threading.Thread(target=run_install, daemon=True).start()
    return {"message": "Installation started running in background"}

@app.websocket("/ws/console")
async def websocket_console(websocket: WebSocket):
    await websocket.accept()
    if state:
        state.active_websockets.append(websocket)
        # Replay history
        for msg in state.log_history:
            await websocket.send_json(msg)
    try:
        while True:
            data = await websocket.receive_text()
            if state and state.server_handler:
                state.server_handler.send_command(data)
    except WebSocketDisconnect:
        if state and websocket in state.active_websockets:
            state.active_websockets.remove(websocket)

# --- Player Management Endpoints ---

class PlayerActionRequest(BaseModel):
    name: str
    reason: Optional[str] = None

import platform
import subprocess
from mcstatus import JavaServer

# --- Helper to open folder ---
def open_file_explorer(path):
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

@app.post("/system/open-folder")
def open_server_folder():
    if state.server_handler and state.server_handler.server_path:
        path = state.server_handler.server_path
        if os.path.exists(path):
            open_file_explorer(path)
            return {"message": "Folder opened"}
    raise HTTPException(status_code=404, detail="Server path not found")

@app.get("/players/lists")
def get_player_lists():
    if not state or not state.server_handler:
        return {"online": [], "ops": [], "banned": [], "whitelist": []}
    
    server_path = state.server_handler.server_path
    
    # helper
    def load_json(name):
        try:
            with open(os.path.join(server_path, name), 'r') as f:
                return json.load(f)
        except: return []

    ops = load_json("ops.json")
    banned = load_json("banned-players.json")
    whitelist = load_json("whitelist.json")
    
    # Get Online Players via mcstatus
    online_players = []
    try:
        # Read port from server.properties
        props = state.server_handler.get_server_properties()
        port = int(props.get('server-port', 25565))
        
        server = JavaServer.lookup(f"127.0.0.1:{port}")
        query = server.status()
        
        if query.players.sample:
            for p in query.players.sample:
                online_players.append({"name": p.name, "uuid": p.id})
    except Exception as e:
        print(f"Failed to query server status: {e}")
        # online_players remains empty if offline or query fails

    return {
        "online": online_players,
        "ops": ops,
        "banned": banned,
        "whitelist": whitelist
    }

@app.post("/players/op")
def op_player(req: PlayerActionRequest):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")
    
    if state.server_handler.is_running():
        state.server_handler.send_command(f"op {req.name}")
        return {"message": f"Opped {req.name} (Online)"}
    else:
        # Offline: Add to ops.json
        # Note: ops.json requires UUID and level. For offline adding without UUID, it's tricky as MC needs UUID.
        # We will try to add a minimal entry and hope server resolves it or user accepts it might need UUID.
        # Ideally we'd fetch UUID from Mojang API here.
        # VALIDATION: ops.json structure: [{ "uuid": "...", "name": "...", "level": 4 }]
        
        # For simplicity and robustness, we will fetch UUID if possible or fallback to a placeholder
        # In a real production app we SHOULD call Mojang API. For now, we'll warn or try to fetch.
        import requests
        uuid = ""
        try:
            r = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{req.name}")
            if r.status_code == 200:
                uuid = r.json().get("id")
                # Format UUID with dashes
                if len(uuid) == 32:
                    uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        except:
            pass
            
        if not uuid:
             return {"message": "Could not fetch UUID. Cannot OP offline without UUID."}

        path = os.path.join(state.server_handler.server_path, "ops.json")
        entry = {"uuid": uuid, "name": req.name, "level": 4, "bypassesPlayerLimit": False}
        
        updated = update_json_list(path, entry, "uuid")
        return {"message": f"Opped {req.name} (Offline)"}

@app.post("/players/deop")
def deop_player(req: PlayerActionRequest):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")
    
    if state.server_handler.is_running():
        state.server_handler.send_command(f"deop {req.name}")
        return {"message": f"Deopped {req.name}"}
    else:
        path = os.path.join(state.server_handler.server_path, "ops.json")
        remove_from_json_list(path, "name", req.name)
        return {"message": f"Deopped {req.name} (Offline)"}

@app.post("/players/whitelist/add")
def whitelist_add(req: PlayerActionRequest):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")
    
    if state.server_handler.is_running():
        state.server_handler.send_command(f"whitelist add {req.name}")
        return {"message": f"Added {req.name} to whitelist"}
    else:
        # Fetch UUID as required for whitelist usually
        import requests
        uuid = ""
        try:
            r = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{req.name}")
            if r.status_code == 200:
                uuid = r.json().get("id")
                if len(uuid) == 32:
                    uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        except:
            pass
            
        if not uuid:
             return {"message": "Could not fetch UUID. Cannot Whitelist offline without UUID."}

        path = os.path.join(state.server_handler.server_path, "whitelist.json")
        entry = {"uuid": uuid, "name": req.name}
        update_json_list(path, entry, "uuid")
        return {"message": f"Added {req.name} to whitelist (Offline)"}

@app.post("/players/whitelist/remove")
def whitelist_remove(req: PlayerActionRequest):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")

    if state.server_handler.is_running():
        state.server_handler.send_command(f"whitelist remove {req.name}")
        return {"message": f"Removed {req.name} from whitelist"}
    else:
        path = os.path.join(state.server_handler.server_path, "whitelist.json")
        remove_from_json_list(path, "name", req.name)
        return {"message": f"Removed {req.name} from whitelist (Offline)"}

@app.post("/players/ban")
def ban_player(req: PlayerActionRequest):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")
    reason = f" {req.reason}" if req.reason else ""
    
    if state.server_handler.is_running():
        state.server_handler.send_command(f"ban {req.name}{reason}")
        return {"message": f"Banned {req.name}"}
    else:
        # For ban, we ideally need UUID too for banned-players.json
        import requests
        uuid = ""
        try:
            r = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{req.name}")
            if r.status_code == 200:
                uuid = r.json().get("id")
                if len(uuid) == 32:
                    uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        except:
            pass
        
        # banned-players.json usually wants UUID, but older versions might accept name? 
        # Standard format: [ { "uuid": "...", "name": "...", "created": "...", "source": "Console", "expires": "forever", "reason": "..." } ]
        if not uuid:
            return {"message": "Could not fetch UUID. Cannot Ban offline without UUID."}

        path = os.path.join(state.server_handler.server_path, "banned-players.json")
        from datetime import datetime
        entry = {
            "uuid": uuid, 
            "name": req.name, 
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S %z"),
            "source": "Console", 
            "expires": "forever", 
            "reason": req.reason or "Banned by operator"
        }
        update_json_list(path, entry, "uuid")
        return {"message": f"Banned {req.name} (Offline)"}

@app.post("/players/pardon")
def pardon_player(req: PlayerActionRequest):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")
    
    if state.server_handler.is_running():
        state.server_handler.send_command(f"pardon {req.name}")
        return {"message": f"Unbanned {req.name}"}
    else:
        path = os.path.join(state.server_handler.server_path, "banned-players.json")
        remove_from_json_list(path, "name", req.name)
        return {"message": f"Unbanned {req.name} (Offline)"}

@app.post("/players/kick")
def kick_player(req: PlayerActionRequest):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")
    # Kick only makes sense online
    if not state.server_handler.is_running():
        return {"message": "Cannot kick player while server is offline"}
        
    reason = f" {req.reason}" if req.reason else ""
    state.server_handler.send_command(f"kick {req.name}{reason}")
    return {"message": f"Kicked {req.name}"}

# --- Helpers ---
def update_json_list(path, entry, key_id="uuid"):
    """Adds or updates an entry in a JSON list file."""
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except: data = []
    
    # Check if exists
    exists = False
    for i, item in enumerate(data):
        if item.get(key_id) == entry.get(key_id):
            data[i] = entry
            exists = True
            break
    if not exists:
        data.append(entry)
        
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def remove_from_json_list(path, key, value):
    """Removes an entry from a JSON list file."""
    if not os.path.exists(path): return
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Filter out
        data = [item for item in data if item.get(key) != value]
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except: pass

# --- Settings Endpoints ---

@app.get("/settings/properties")
def get_server_properties():
    if not state or not state.server_handler: return {}
    path = os.path.join(state.server_handler.server_path, "server.properties")
    props = {}
    if os.path.exists(path):
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    props[key.strip()] = value.strip()
    return props

@app.post("/settings/properties")
async def update_server_properties(request: Request):
    if not state or not state.server_handler: raise HTTPException(status_code=400, detail="Server not configured")
    data = await request.json()
    path = os.path.join(state.server_handler.server_path, "server.properties")
    
    # Read existing lines to preserve comments/order
    lines = []
    if os.path.exists(path):
        with open(path, 'r') as f:
            lines = f.readlines()
            
    new_lines = []
    processed_keys = set()
    
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key, val = stripped.split('=', 1)
            key = key.strip()
            if key in data:
                new_lines.append(f"{key}={data[key]}\n")
                processed_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    # Append new keys that weren't in the file
    for key, val in data.items():
        if key not in processed_keys:
            new_lines.append(f"{key}={val}\n")
            
    with open(path, 'w') as f:
        f.writelines(new_lines)
        
    return {"message": "Properties updated"}

@app.get("/settings/app")
def get_app_settings():
    if not state: return {}
    conf = state.config_manager.config
    return {
        "ram_min": conf.get("ram_min", "2"),
        "ram_max": conf.get("ram_max", "4"),
        "ram_unit": conf.get("ram_unit", "G"),
        "java_path": conf.get("java_path", "java")
    }

@app.post("/settings/app")
async def update_app_settings(request: Request):
    if not state: raise HTTPException(status_code=500, detail="App state invalid")
    data = await request.json()
    
    # Update config manager
    state.config_manager.config.update(data)
    state.config_manager.save()
    
    # Update active handler if it exists
    if state.server_handler:
        state.server_handler.java_path = data.get("java_path", state.server_handler.java_path)
        # Update RAM (handler method updates its internal state)
        if "ram_max" in data or "ram_min" in data:
            state.server_handler.update_ram(
                data.get("ram_max", state.server_handler.ram_max),
                data.get("ram_min", state.server_handler.ram_min),
                data.get("ram_unit", state.server_handler.ram_unit)
            )
            
    return {"message": "App settings updated"}


# --- World Management Endpoints ---

@app.get("/worlds")
def get_worlds():
    if not state or not state.server_handler: return []
    
    server_path = state.server_handler.server_path
    worlds = []
    
    if os.path.exists(server_path):
        for item in os.listdir(server_path):
            item_path = os.path.join(server_path, item)
            if os.path.isdir(item_path):
                # Check for level.dat to confirm it's a world
                if os.path.exists(os.path.join(item_path, "level.dat")):
                    # Get size
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(item_path):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            total_size += os.path.getsize(fp)
                    
                    size_mb = round(total_size / (1024 * 1024), 2)
                    
                    worlds.append({
                        "name": item,
                        "size": f"{size_mb} MB",
                        "last_modified": os.path.getmtime(os.path.join(item_path, "level.dat"))
                    })
    
    return worlds

@app.post("/worlds/create")
def create_world(request: Request):
    # Basic stub. Minecraft creates world automatically if level-name changes to non-existent folder.
    pass

# --- Tunnel Management Endpoints (Pinggy) ---

@app.get("/tunnel/status")
def get_tunnel_status():
    if not state:
        return {"active": False, "address": None}
    
    return {
        "active": state.tunnel_process is not None and state.tunnel_process.poll() is None,
        "address": state.tunnel_address
    }

@app.post("/tunnel/start")
def start_tunnel(request: Request, region: str = "eu"):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    
    # If tunnel already running, return existing address
    if state.tunnel_process and state.tunnel_process.poll() is None:
        return {"message": "Tunnel already running", "address": state.tunnel_address}
    
    # Get server port (default 25565)
    port = "25565"
    if state.server_handler:
        try:
            props_path = os.path.join(state.server_handler.server_path, "server.properties")
            if os.path.exists(props_path):
                with open(props_path, 'r') as f:
                    for line in f:
                        if line.startswith("server-port="):
                            port = line.split("=")[1].strip()
                            break
        except:
            pass
    
    def _ensure_ssh_key():
        """Ensures a dedicated SSH key exists for the app to authenticate with Pinggy."""
        try:
            ssh_dir = os.path.join(state.app_data_dir, "ssh")
            if not os.path.exists(ssh_dir):
                os.makedirs(ssh_dir)
            
            key_path = os.path.join(ssh_dir, "id_rsa")
            pub_path = f"{key_path}.pub"
            
            # If key doesn't exist, generate it
            if not os.path.exists(key_path) or not os.path.exists(pub_path):
                logging.info("Generating new SSH key for Pinggy...")
                subprocess.run(
                    ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", key_path, "-N", ""],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
            return key_path
        except Exception as e:
            logging.error(f"Failed to generate SSH key: {e}")
            return None

    def run_tunnel():
        import subprocess
        import re
        try:
            # Construct host based on region
            # regions: eu, us, ap, sa
            host = f"{region}.free.pinggy.io"
            
            logging.info(f"Starting Pinggy tunnel ({region.upper()}) for port {port}...")
            state.broadcast_log_sync(f"🌐 Iniciando túnel público ({region.upper()}) para puerto {port}...", "info")
            
            # Ensure we have a key
            key_path = _ensure_ssh_key()
            
            # Pinggy SSH command - optimized with identity
            cmd = [
                "ssh",
                "-p", "443",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=30",
                "-o", "BatchMode=yes",
                "-T", # Disable pseudo-terminal
            ]
            
            if key_path and os.path.exists(key_path):
                cmd.extend(["-i", key_path, "-o", "IdentitiesOnly=yes"])
            
            cmd.extend([
                "-R", f"0:127.0.0.1:{port}",
                f"tcp@{host}"
            ])
            
            # Using bufsize=1 for line buffering
            state.tunnel_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            # Read output to find the tunnel URL
            for line in state.tunnel_process.stdout:
                line = line.strip()
                if not line: continue
                
                logging.debug(f"Pinggy output: {line}")
                
                # Pinggy outputs something like: "tcp://xyz.a.pinggy.io:12345"
                # Match tcp:// format
                tcp_match = re.search(r'tcp://([a-zA-Z0-9\.\-]+:\d+)', line)
                if tcp_match:
                    state.tunnel_address = tcp_match.group(1)
                    
                # Match raw address format (free.pinggy.io:12345)
                # Broader match: something.pinggy.io:digits
                if not state.tunnel_address:
                    addr_match = re.search(r'([a-zA-Z0-9\.\-]+\.pinggy\.io:\d+)', line)
                    if addr_match:
                        state.tunnel_address = addr_match.group(1)
                
                if state.tunnel_address:
                    logging.info(f"Tunnel established: {state.tunnel_address}")
                    state.broadcast_log_sync(f"✅ ¡Servidor público activo! Dirección: {state.tunnel_address}", "success")
                    state.broadcast_log_sync({"type": "tunnel_connected", "address": state.tunnel_address})
            
            # If we exit the loop, tunnel has closed
            state.broadcast_log_sync("🔴 Túnel cerrado", "warning")
            state.broadcast_log_sync({"type": "tunnel_disconnected"})
            state.tunnel_address = None
            
        except Exception as e:
            logging.exception(f"Tunnel error: {e}")
            state.broadcast_log_sync(f"❌ Error en túnel: {e}", "error")
            state.tunnel_address = None
    
    threading.Thread(target=run_tunnel, daemon=True).start()
    return {"message": "Tunnel starting...", "status": "connecting"}

@app.post("/tunnel/stop")
def stop_tunnel():
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    
    if state.tunnel_process:
        try:
            state.tunnel_process.terminate()
            state.tunnel_process.wait(timeout=5)
        except:
            state.tunnel_process.kill()
        
        state.tunnel_process = None
        state.tunnel_address = None
        state.broadcast_log_sync("🔴 Túnel detenido", "info")
        state.broadcast_log_sync({"type": "tunnel_disconnected"})
    
    return {"message": "Tunnel stopped"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

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
import zipfile
from datetime import datetime
import psutil
import time

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
from utils.mods_manager import ModsManager

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
        self.mods_manager = ModsManager()
        
        self.active_websockets: List[WebSocket] = []
        self.loop = asyncio.get_running_loop()
        self.selected_server_id = None

        # Log broadcasting control (prevents WS flood from starving the API)
        self._log_queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._log_broadcaster_task: Optional[asyncio.Task] = None
        
        # Tunnel management
        self.tunnel_process = None
        self.tunnel_address = None

        self.world_size_cache = {}
        self.world_size_inflight = set()
        self.world_size_lock = threading.Lock()
        
        # Multi-server management
        self.active_handlers = {} # server_id -> ServerHandler
        
        # App-level log history for Dashboard mini-console
        self.app_log_history = []

    def start_background_tasks(self):
        if self._log_broadcaster_task is None:
            self._log_broadcaster_task = asyncio.create_task(self._log_broadcaster())

    def _enqueue_log_from_loop(self, msg_obj: dict):
        """Must be called from the asyncio loop thread."""
        try:
            if self._log_queue.full() and msg_obj.get("level") in ("normal", "info"):
                return
            self._log_queue.put_nowait(msg_obj)
        except asyncio.QueueFull:
            try:
                _ = self._log_queue.get_nowait()
            except Exception:
                return
            try:
                self._log_queue.put_nowait(msg_obj)
            except Exception:
                return

    async def _log_broadcaster(self):
        """Batches log messages and streams them to WebSocket clients.

        This avoids scheduling thousands of per-line tasks during server startup.
        """
        while True:
            msg = await self._log_queue.get()

            batch = [msg]
            start = self.loop.time()
            # Drain up to 200 messages or 50ms worth of logs
            while len(batch) < 200:
                remaining = 0.05 - (self.loop.time() - start)
                if remaining <= 0:
                    break
                try:
                    nxt = await asyncio.wait_for(self._log_queue.get(), timeout=remaining)
                    batch.append(nxt)
                except asyncio.TimeoutError:
                    break

            if not self.active_websockets:
                continue

            filtered_batch = []
            for item in batch:
                msg_server_id = item.get("server_id")
                if msg_server_id and msg_server_id != self.selected_server_id:
                    continue
                filtered_batch.append(item)

            if not filtered_batch:
                continue

            payload = {"type": "batch", "items": filtered_batch}
            dead = []
            for ws in list(self.active_websockets):
                try:
                    await asyncio.wait_for(ws.send_json(payload), timeout=0.5)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                if ws in self.active_websockets:
                    self.active_websockets.remove(ws)

    @property
    def server_handler(self):
        """Returns the handler for the currently selected server, or None."""
        if self.selected_server_id:
            return self.active_handlers.get(self.selected_server_id)
        return None
    
    @server_handler.setter
    def server_handler(self, handler):
        """Sets the handler for the current server."""
        if self.selected_server_id:
            if handler is None:
                if self.selected_server_id in self.active_handlers:
                    del self.active_handlers[self.selected_server_id]
            else:
                self.active_handlers[self.selected_server_id] = handler

    @property
    def log_history(self):
        """Returns log history of current handler or app-level history."""
        if self.server_handler and self.server_handler.log_history:
            return self.server_handler.log_history
        return self.app_log_history

    def load_server(self, server_id):
        server_config = self.config_manager.get_server(server_id)
        if not server_config:
            raise ValueError("Server not found")

        self.selected_server_id = server_id

        # If we already have a handler for this server, use it
        if server_id in self.active_handlers:
            self.broadcast_log_sync(f"Reconnected to server: {server_config.get('name', server_id)}", "info")
            return server_config
            
        server_path = server_config.get("path")
        if not server_path or not os.path.exists(server_path):
            raise ValueError(f"Server path invalid: {server_path}")
            
        self.broadcast_log_sync(f"Switched to server: {server_config.get('name', server_id)}", "info")
        
        # Create new handler
        new_handler = ServerHandler(
            server_id=server_id,
            server_path=server_path,
            server_type=server_config.get("type") or server_config.get("server_type") or "vanilla",
            ram_min=server_config.get("ram_min", "2"),
            ram_max=server_config.get("ram_max", "4"),
            ram_unit=server_config.get("ram_unit", "G"),
            output_callback=self.broadcast_log_sync,
            minecraft_version=server_config.get("version") or server_config.get("minecraft_version"),
            java_path=server_config.get("java_path") # Pass saved Java path
        )
        self.active_handlers[server_id] = new_handler
        
        self.config_manager.config["last_selected_id"] = server_id
        self.config_manager.save()
        return server_config

    def broadcast_log_sync(self, message, level="normal", server_id=None):
        """Thread-safe wrapper to broadcast logs from synchronous code."""
        try:
            if isinstance(message, dict):
                 msg_obj = message
                 if server_id and "server_id" not in msg_obj:
                     msg_obj["server_id"] = server_id
            else:
                 if isinstance(message, str):
                     message = message.replace("\r", "")
                 msg_obj = {"message": message, "level": level, "server_id": server_id}
            
            # Store in app-level history for Dashboard polling
            # Skip verbose installer logs (recipe files, etc.) to avoid spam
            msg_text = msg_obj.get("message", "") if isinstance(msg_obj, dict) else str(msg_obj)
            
            # Robust filter for Forge/other installer verbose output
            # Patterns: "[Installer]   " (extra spaces), ".json", ".jar", "data/minecraft/", etc.
            is_verbose_installer = False
            if "[Installer]" in msg_text:
                lower_msg = msg_text.lower()
                is_verbose_installer = (
                    "   " in msg_text or  # File listings usually have extra indentation
                    ".json" in lower_msg or 
                    ".class" in lower_msg or
                    "data/minecraft/" in lower_msg or
                    "extracting " in lower_msg or
                    "unpacking " in lower_msg
                )
            
            if not is_verbose_installer:
                self.app_log_history.append(msg_obj)
                if len(self.app_log_history) > 500:
                    self.app_log_history.pop(0)

                # Thread-safe enqueue into the asyncio queue (only non-verbose logs)
                try:
                    self.loop.call_soon_threadsafe(self._enqueue_log_from_loop, msg_obj)
                except Exception:
                    return
        except Exception as e:
            print(f"Error logging: {e}")

    async def broadcast_log(self, message: dict):
        # Filter logs: Only send to WS if they belong to the CURRENT server or are global (no server_id)
        msg_server_id = message.get("server_id")
        
        # If message belongs to a specific server, and it's NOT the selected one, don't stream it to console
        if msg_server_id and msg_server_id != self.selected_server_id:
            return 
            
        for ws in self.active_websockets:
            try:
                await ws.send_json(message)
            except Exception:
                pass

state: Optional[AppState] = None

@app.on_event("startup")
async def startup_event():
    global state
    state = AppState()
    state.start_background_tasks()

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

class ModInstallRequest(BaseModel):
    version_id: str

class ModDeleteRequest(BaseModel):
    filename: str

# --- Core Endpoints ---

@app.get("/servers")
async def list_servers():
    if not state: return []
    servers = state.config_manager.get_all_servers()
    
    # Enrich with runtime status
    for s in servers:
        s_id = s.get("id")
        if s_id in state.active_handlers:
            s["status"] = state.active_handlers[s_id].get_status()
        else:
            s["status"] = "offline"
            
    return servers

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
        # Si cambiamos de servidor, limpiamos el historial de logs globales de la UI
        if state.selected_server_id != req.server_id:
            state.app_log_history = [] 
            
        config = state.load_server(req.server_id)
        
        # Devolver estado inmediato para evitar lag visual
        status_response = get_status() 
        return {"status": "success", "server": config, "server_status": status_response}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/servers/{server_id}")
async def delete_server(server_id: str, delete_files: bool = False):
    # Get server info before deleting profile
    server_info = state.config_manager.get_server(server_id)
    server_path = server_info.get("path") if server_info else None
    
    # Delete the profile
    state.config_manager.delete_server(server_id)
    if state.selected_server_id == server_id:
        state.server_handler = None
        state.selected_server_id = None
    
    # Optionally delete files
    if delete_files and server_path and os.path.exists(server_path):
        import shutil
        try:
            shutil.rmtree(server_path)
        except Exception as e:
            return {"status": "deleted", "files_deleted": False, "error": str(e)}
        return {"status": "deleted", "files_deleted": True}
    
    return {"status": "deleted", "files_deleted": False}

@app.get("/status")
def get_status():
    if not state or not state.server_handler:
        return {"status": "not_configured"}
    
    stats = state.server_handler.get_stats()

    online_players = state.server_handler.get_active_players_list(trigger_refresh=False)
    players_count = len(online_players) if online_players is not None else 0
    return {
        "status": state.server_handler.get_status(),
        "pid": state.server_handler.get_pid(),
        "server_type": state.server_handler.server_type,
        "minecraft_version": state.server_handler.minecraft_version,
        "cpu": stats["cpu"],
        "ram": stats["ram"],
        "players": players_count,
        "max_players": state.server_handler.get_max_players(),
        "online_players": online_players,
        "uptime": stats["uptime"],
        "recent_logs": state.log_history[-15:] # Return last 15 lines for the mini console
    }

@app.post("/server/open-folder")
def open_server_folder():
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not initialized")
    
    success = state.server_handler.open_folder()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to open folder")
    return {"status": "success"}

@app.post("/start")
def start_server():
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.start()
    return {"message": "Start command issued"}

@app.post("/stop")
def stop_server(force: bool = False):
    if not state or not state.server_handler:
         raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.stop(force=force)
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
    
    def run_install():
        try:
            # Helper to send structured progress
            def send_progress(pct, msg, **kwargs):
                data = {
                    "type": "progress", 
                    "value": pct, 
                    "message": msg
                }
                data.update(kwargs)
                state.broadcast_log_sync(data)

            # 1. Preparación del Directorio
            send_progress(5, f"Preparing directory for {req.server_type} {req.version}...")
            os.makedirs(install_path, exist_ok=True)
            state.broadcast_log_sync(f"Install location: {install_path}", "info")

            # 2. GESTIÓN AUTOMÁTICA DE JAVA (Paso Crítico para Forge)
            # Forge requiere ejecutar su instalador con la versión correcta de Java.
            send_progress(10, "Checking Java compatibility...")
            
            # Esto descarga Java si es necesario y devuelve la ruta al ejecutable
            java_path = state.java_manager.get_java_for_server(
                install_path, 
                req.version, 
                force_download=False # Ya intenta descargar si falta
            )
            
            if not java_path:
                raise Exception(f"Could not setup a valid Java runtime for Minecraft {req.version}")
                
            state.broadcast_log_sync(f"Using Java: {java_path}", "success")

            # Progress wrapper for download functions
            def progress_callback(p):
                # Map download 0-100 to overall 20-50 range
                scaled = 20 + (p * 0.3)
                send_progress(scaled, "Downloading server files...")

            # 3. Instalación del Servidor
            if req.server_type.lower() == "forge":
                # Crear un handler temporal con la ruta de Java CORRECTA explícita
                temp_handler = ServerHandler(
                    install_path, 
                    "forge", 
                    "1", "2", "G", 
                    output_callback=lambda m, l: state.broadcast_log_sync(m, l), 
                    minecraft_version=req.version,
                    java_path=java_path # IMPORTANTE: Usar el Java recién obtenido
                )
                
                # Wrap progress for forge installer (50-90 range)
                def forge_progress(p):
                    scaled = 50 + (p * 0.4)
                    send_progress(scaled, "Running Forge Installer (this may take a while)...")
                
                forge_ver = req.forge_version
                if not forge_ver:
                    send_progress(15, f"Fetching latest Forge version for {req.version}...")
                    from utils.api_client import get_forge_versions
                    versions = get_forge_versions()
                    if req.version in versions and versions[req.version]:
                        forge_ver = versions[req.version][0]
                        state.broadcast_log_sync(f"Auto-selected Forge version: {forge_ver}", "info")
                    else:
                        raise Exception(f"No Forge version found for Minecraft {req.version}")

                # Ejecutar instalador
                temp_handler.install_forge_server(forge_ver, req.version, forge_progress)
                
            else:
                # Vanilla / Paper / Fabric logic
                jar_path = os.path.join(install_path, "server.jar")
                success = download_server_jar(req.server_type, req.version, jar_path, progress_callback)
                if not success:
                    raise Exception("Failed to download Server JAR.")

            # 4. Configuración Final
            send_progress(95, "Finalizing configuration...")
            
            # Create new server profile
            new_server_data = {
                "name": req.folder_name,
                "path": install_path,
                "type": req.server_type,
                "version": req.version,
                "ram_min": "2",
                "ram_max": "4",
                "ram_unit": "G",
                "java_path": java_path # Guardar la ruta de Java detectada en la config
            }
            
            saved_server = state.config_manager.add_server(new_server_data)
            
            try:
                state.load_server(saved_server["id"]) 
                if state.server_handler:
                    state.server_handler._accept_eula()
                    state.server_handler._create_default_server_properties()
                    # Asegurar que el handler cargado tenga la ruta de Java correcta
                    state.server_handler.java_path = java_path 
            except Exception as e:
                state.broadcast_log_sync(f"Warning during final setup: {e}", "warning")
            
            send_progress(100, "Installation complete!", server_id=saved_server["id"])
            state.broadcast_log_sync("Installation complete! Server is ready to start.", "success")
            
        except Exception as e:
            state.broadcast_log_sync(f"Installation failed: {e}", "error")
            state.broadcast_log_sync({"type": "progress", "value": 0, "error": str(e)})

    threading.Thread(target=run_install, daemon=True).start()
    return {"message": "Installation started running in background"}

@app.websocket("/ws/console")
async def websocket_console(websocket: WebSocket):
    await websocket.accept()
    # logging.info("WebSocket connected")
    if state:
        state.active_websockets.append(websocket)
        # Replay history
        try:
            history = state.log_history[-200:]
            if history:
                await websocket.send_json({"type": "batch", "items": history})
        except Exception as e:
            # Client disconnected during replay
            if websocket in state.active_websockets:
                state.active_websockets.remove(websocket)
            return
    else:
        logging.error("WebSocket rejected: App State is None")
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_text()
            if state and state.server_handler:
                state.server_handler.send_command(data)
    except WebSocketDisconnect:
        # logging.info("WebSocket disconnected")
        if state and websocket in state.active_websockets:
            state.active_websockets.remove(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
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
    
    # Get Online Players via ServerHandler (uses status_query)
    online_players = []
    if state.server_handler:
        raw_sample = state.server_handler.get_active_players_list()
        # Convert SLP format {name, id} to frontend expected {name, uuid}
        for player in raw_sample:
            online_players.append({
                "name": player.get("name", "Unknown"),
                "uuid": player.get("id", "")
            })

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
                    level_dat = os.path.join(item_path, "level.dat")
                    level_mtime = os.path.getmtime(level_dat)
                    folder_mtime = os.path.getmtime(item_path)

                    cached = state.world_size_cache.get(item_path)
                    size_str = None
                    if cached and cached.get("folder_mtime") == folder_mtime:
                        size_str = cached.get("size")
                    else:
                        size_str = cached.get("size") if cached and cached.get("size") else "..."

                        with state.world_size_lock:
                            if item_path not in state.world_size_inflight:
                                state.world_size_inflight.add(item_path)

                                def _compute_world_size(path_to_size: str, expected_folder_mtime: float):
                                    try:
                                        total_size = 0
                                        for dirpath, dirnames, filenames in os.walk(path_to_size):
                                            for f in filenames:
                                                fp = os.path.join(dirpath, f)
                                                try:
                                                    total_size += os.path.getsize(fp)
                                                except Exception:
                                                    pass
                                        size_mb = round(total_size / (1024 * 1024), 2)
                                        if state:
                                            state.world_size_cache[path_to_size] = {
                                                "size": f"{size_mb} MB",
                                                "folder_mtime": expected_folder_mtime,
                                            }
                                    finally:
                                        if state:
                                            with state.world_size_lock:
                                                state.world_size_inflight.discard(path_to_size)

                                threading.Thread(target=_compute_world_size, args=(item_path, folder_mtime), daemon=True).start()
                    
                    worlds.append({
                        "name": item,
                        "size": size_str or "...",
                        "last_modified": level_mtime
                    })
    
    return worlds

@app.post("/worlds/create")
def create_world(request: Request):
    # Basic stub. Minecraft creates world automatically if level-name changes to non-existent folder.
    pass


class WorldBackupRequest(BaseModel):
    world: Optional[str] = None


@app.get("/worlds/backups")
def list_world_backups(world: Optional[str] = None):
    if not state or not state.server_handler:
        return []

    server_path = state.server_handler.server_path
    backups_dir = os.path.join(server_path, "world_backups")
    if not os.path.exists(backups_dir):
        return []

    items = []
    try:
        for name in sorted(os.listdir(backups_dir), reverse=True):
            if not name.lower().endswith(".zip"):
                continue
            if world and not name.startswith(f"{world}-"):
                continue
            fp = os.path.join(backups_dir, name)
            if not os.path.isfile(fp):
                continue

            size_mb = round(os.path.getsize(fp) / (1024 * 1024), 2)
            items.append({
                "name": name,
                "size": f"{size_mb} MB",
                "created": os.path.getmtime(fp)
            })
    except Exception:
        return items

    return items


@app.post("/worlds/backups/create")
def create_world_backup(req: WorldBackupRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    server_path = state.server_handler.server_path

    world_name = (req.world or "").strip() or None
    if not world_name:
        props_path = os.path.join(server_path, "server.properties")
        try:
            if os.path.exists(props_path):
                with open(props_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if line.startswith("level-name="):
                            world_name = line.split("=", 1)[1].strip() or None
                            break
        except Exception:
            world_name = None

    if not world_name:
        world_name = "world"

    world_path = os.path.join(server_path, world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail=f"World not found: {world_name}")

    backups_dir = os.path.join(server_path, "world_backups")
    os.makedirs(backups_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{world_name}-{ts}.zip"
    backup_path = os.path.join(backups_dir, backup_name)

    def run_backup():
        try:
            if state:
                state.broadcast_log_sync(f"📦 Creating backup: {backup_name}", "info")

            with zipfile.ZipFile(backup_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for dirpath, dirnames, filenames in os.walk(world_path):
                    for filename in filenames:
                        full_path = os.path.join(dirpath, filename)
                        try:
                            arcname = os.path.relpath(full_path, server_path)
                            zf.write(full_path, arcname=arcname)
                        except Exception:
                            pass

            if state:
                state.broadcast_log_sync(f"✅ Backup created: {backup_name}", "success")
        except Exception as e:
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
            except Exception:
                pass
            if state:
                state.broadcast_log_sync(f"❌ Error creating backup: {e}", "error")

    threading.Thread(target=run_backup, daemon=True).start()
    return {"status": "started", "name": backup_name}

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
    
    # Stop any existing tunnel before starting a new one
    if state.tunnel_process and state.tunnel_process.poll() is None:
        logging.info("Stopping existing tunnel before starting a new one...")
        state.broadcast_log_sync("🔄 Closing previous tunnel...", "info")
        try:
            state.tunnel_process.terminate()
            state.tunnel_process.wait(timeout=3)
        except:
            try:
                state.tunnel_process.kill()
            except:
                pass
        state.tunnel_process = None
        state.tunnel_address = None
    
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
        connected_emitted = False
        try:
            # Construct host based on region
            # regions: eu, us, ap, sa
            host = f"{region}.free.pinggy.io"
            
            logging.info(f"Starting Pinggy tunnel ({region.upper()}) for port {port}...")
            state.broadcast_log_sync(f"🌐 Starting public tunnel ({region.upper()}) for port {port}...", "info")
            
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
                    new_addr = tcp_match.group(1)
                    if new_addr and new_addr != state.tunnel_address:
                        state.tunnel_address = new_addr
                    
                # Match raw address format (free.pinggy.io:12345)
                # Broader match: something.pinggy.io:digits
                if not state.tunnel_address:
                    addr_match = re.search(r'([a-zA-Z0-9\.\-]+\.pinggy\.io:\d+)', line)
                    if addr_match:
                        new_addr = addr_match.group(1)
                        if new_addr and new_addr != state.tunnel_address:
                            state.tunnel_address = new_addr
                
                if state.tunnel_address and not connected_emitted:
                    logging.info(f"Tunnel established: {state.tunnel_address}")
                    state.broadcast_log_sync(f"✅ Public server active! Address: {state.tunnel_address}", "success")
                    state.broadcast_log_sync({"type": "tunnel_connected", "address": state.tunnel_address})
                    connected_emitted = True
            
            # If we exit the loop, tunnel has closed
            state.broadcast_log_sync("🔴 Tunnel closed", "warning")
            state.broadcast_log_sync({"type": "tunnel_disconnected"})
            state.tunnel_address = None
            
        except Exception as e:
            logging.exception(f"Tunnel error: {e}")
            state.broadcast_log_sync(f"❌ Tunnel error: {e}", "error")
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
        state.broadcast_log_sync("🔴 Tunnel stopped", "info")
        state.broadcast_log_sync({"type": "tunnel_disconnected"})
    
    return {"message": "Tunnel stopped"}

# --- Mods Endpoints ---
@app.get("/mods/search")
def search_mods(q: str, loader: str = "fabric", version: str = None, project_type: str = "mod", sort: str = "downloads", category: str = None):
    if not state: raise HTTPException(status_code=500, detail="State not initialized")
    
    # If version not provided, try to use server's version
    if not version and state.server_handler:
        version = state.server_handler.minecraft_version
        
    return state.mods_manager.search_mods(q, loader, version, project_type, sort, category)

@app.get("/mods/versions/{slug}")
def get_mod_versions(slug: str, loader: str = "fabric", version: str = None):
    if not state: raise HTTPException(status_code=500, detail="State not initialized")
    
    # If version not provided, use server's version
    if not version and state.server_handler:
        version = state.server_handler.minecraft_version
        
    return state.mods_manager.get_mod_versions(slug, loader, version)

@app.get("/mods/installed")
def get_installed_mods():
    if not state or not state.server_handler: return []
    return state.mods_manager.get_installed_mods(state.server_handler.server_path)

@app.post("/mods/install")
def install_mod(req: ModInstallRequest):
    if not state or not state.server_handler: 
        raise HTTPException(status_code=400, detail="Server not configured")
        
    def run_mod_install():
        try:
            def progress(pct, msg):
                state.broadcast_log_sync({
                    "type": "progress",
                    "value": pct,
                    "message": msg
                })
            
            result = state.mods_manager.install_mod(req.version_id, state.server_handler.server_path, progress_callback=progress)
            
            if result.get("success"):
                state.broadcast_log_sync(f"Installation success: {result.get('filename') or 'Modpack'}", "success")
                state.broadcast_log_sync({"type": "mod_install_complete", "success": True})
            else:
                state.broadcast_log_sync(f"Installation failed: {result.get('error')}", "error")
                state.broadcast_log_sync({"type": "mod_install_complete", "success": False})

        except Exception as e:
            state.broadcast_log_sync(f"Installation crashed: {e}", "error")
            state.broadcast_log_sync({"type": "mod_install_complete", "success": False})

    # Start in background
    threading.Thread(target=run_mod_install, daemon=True).start()
    
    return {"status": "started", "message": "Installation started in background"}

@app.post("/mods/delete")
def delete_mod(req: ModDeleteRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
        
    success = state.mods_manager.delete_mod(req.filename, state.server_handler.server_path)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete mod")
        
    return {"status": "success"}

@app.post("/mods/open-folder")
def open_mods_folder():
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
        
    mods_path = os.path.join(state.server_handler.server_path, "mods")
    if not os.path.exists(mods_path):
        os.makedirs(mods_path)
        
    open_file_explorer(mods_path)
    return {"message": "Folder opened"}

@app.post("/system/shutdown")
def shutdown_app():
    logging.info("Shutdown request received")
    
    def perform_full_shutdown():
        # Stop any running tunnel
        if state and state.tunnel_process and state.tunnel_process.poll() is None:
            logging.info("Stopping tunnel process...")
            try:
                state.tunnel_process.terminate()
                state.tunnel_process.wait(timeout=3)
            except:
                try:
                    state.tunnel_process.kill()
                except:
                    pass
            state.tunnel_process = None
            state.tunnel_address = None
        
        # Stop servers
        if state and state.active_handlers:
            handlers_to_wait = []
            for server_id, handler in state.active_handlers.items():
                if handler.is_running() or handler.is_starting():
                    logging.info(f"Stopping server {server_id}...")
                    handler.stop(silent=True)
                    handlers_to_wait.append((server_id, handler))
            
            # Wait for each server to stop
            for server_id, handler in handlers_to_wait:
                logging.info(f"Waiting for server {server_id} to stop...")
                handler.wait_for_stop(timeout=25) # Slightly less than backend timeout
        
        logging.info("All servers stopped. Backend exiting.")
        # Final exit
        os._exit(0)

    # Start shutdown in a separate thread so we can return the response immediately
    threading.Thread(target=perform_full_shutdown, daemon=True).start()
    return {"message": "Shutdown sequence started"}

def start_parent_watchdog():
    """Vigila si el proceso padre (Electron) sigue vivo. Si muere, cerramos todo."""
    parent_pid = os.getppid()
    if parent_pid <= 1: # No parent or init
        return

    def watch():
        logging.info(f"Parent watchdog started for PID {parent_pid}")
        while True:
            try:
                # Comprobar si el padre sigue existiendo
                parent = psutil.Process(parent_pid)
                if not parent.is_running() or parent.status() == psutil.STATUS_ZOMBIE:
                    raise psutil.NoSuchProcess(parent_pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logging.warning("Parent process lost. Shutting down backend and servers...")
                # Intentar cerrar servidores limpiamente si es posible
                if state and state.server_handler:
                    try:
                        state.server_handler.stop(force=True, silent=True)
                    except:
                        pass
                os._exit(0)
            time.sleep(2)

    threading.Thread(target=watch, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    # Iniciar el watchdog antes de arrancar el servidor
    start_parent_watchdog()
    uvicorn.run(app, host="127.0.0.1", port=8000)

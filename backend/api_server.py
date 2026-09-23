import os
import sys
import multiprocessing

# --- CRITICAL: REDIRECT STREAMS IN FROZEN EXE ---
# If running as a PyInstaller --noconsole EXE, stdout/stderr are None, which crashes many libraries.
if getattr(sys, "frozen", False) and sys.platform == "win32":
    log_dir = os.path.join(os.getenv("APPDATA", ""), "MinecraftServerGUI")
    os.makedirs(log_dir, exist_ok=True)
    log_file = open(os.path.join(log_dir, "backend_crash.log"), "w", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file
    multiprocessing.freeze_support()

import asyncio
import collections
import secrets
import threading
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Request,
    Query,
    UploadFile,
    File,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
import json
import logging
from queue import Queue
import zipfile
from datetime import datetime
import psutil
import time
import shutil
import requests

# --- CRITICAL: DEBUG LOGGING FOR PROD ---
# Log to AppData so we can see why it crashes in .exe
try:
    if sys.platform == "win32":
        log_dir = os.path.join(os.getenv("APPDATA"), "MinecraftServerGUI")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), ".minecraft_server_gui")

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    from logging.handlers import RotatingFileHandler

    _log_handler = RotatingFileHandler(
        os.path.join(log_dir, "backend_debug.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _log_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    _root_logger = logging.getLogger()
    _root_logger.setLevel(logging.INFO)
    # Guard against duplicate handlers if this module gets imported twice
    if not any(isinstance(h, RotatingFileHandler) for h in _root_logger.handlers):
        _root_logger.addHandler(_log_handler)
    logging.info("Backend starting up...")
    logging.info(f"CWD: {os.getcwd()}")
    logging.info(f"Python executable: {sys.executable}")
except Exception as e:
    # Fallback to print if logging fails
    print(f"Logging setup failed: {e}")

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.server_handler import ServerHandler, _malloc_trim
from server.config_manager import ConfigManager
from utils.java_manager import JavaManager
from utils.server_detector import ServerDetector
from utils.api_client import (
    get_server_versions,
    get_forge_versions,
    get_neoforge_versions,
    download_server_jar,
    download_file_from_url,
)
from utils.mods_manager import ModsManager


# Maximum length of a single log line retained in memory (deques / async queue).
# Matches server_handler.MAX_LOG_LINE_LEN — kept duplicated here to avoid a
# circular import. Bounds retained memory when server output has no newlines.
MAX_LOG_LINE_LEN = 8000


# --- Security: shared token + restricted CORS ---
# The backend listens on 127.0.0.1 with full control over the Minecraft server
# (start/stop, console commands, file writes, arbitrary jar install). Without
# auth, any web page open in the user's browser could call it. Electron
# generates a random token, passes it to the backend via the MLSG_TOKEN env var
# and to the renderer via argv; every HTTP request must send it in
# X-MLSG-Token and the WebSocket must pass it as ?token=.
# If MLSG_TOKEN is not set (e.g. running the script standalone for debugging),
# auth is disabled and a warning is logged.
API_TOKEN = os.environ.get("MLSG_TOKEN", "").strip()
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "null",  # file:// renderer in the packaged app sends Origin: null
    "file://",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global state
    logging.info("Lifespan starting...")

    # Ensure loop is set
    try:
        loop = asyncio.get_running_loop()
        if state:
            state.loop = loop
            # Set exception handler
            if sys.platform == "win32":

                def custom_exception_handler(loop, context):
                    if "WinError 10054" in str(context.get("exception", "")):
                        return
                    loop.default_exception_handler(context)

                loop.set_exception_handler(custom_exception_handler)

            state.start_background_tasks()
            logging.info("Background tasks started in lifespan")

            # Best-effort: remove SRV records this install created but no longer
            # uses (safe for shared Workers: only touches our own subdomains).
            if state.config_manager.get_all_servers():
                threading.Thread(
                    target=_cleanup_own_dns_records, args=(state, "startup"), daemon=True
                ).start()
    except Exception as e:
        logging.error(f"Error in lifespan startup: {e}")

    yield
    logging.info("Lifespan shutting down...")


app = FastAPI(lifespan=lifespan)

# Enable CORS (restricted to the app's own origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def token_auth_middleware(request: Request, call_next):
    """Require the shared token on every request when configured.

    Exempts CORS preflight (OPTIONS), which the browser sends without custom
    headers; the actual request carries the token.
    """
    if API_TOKEN and request.method != "OPTIONS":
        # The server icon is rendered via <img src>, which cannot send custom
        # headers. It only ever serves the fixed server-icon.png, so it is safe
        # to leave unauthenticated.
        if request.url.path != "/server/icon/image":
            provided = request.headers.get("x-mlsg-token", "")
            if not secrets.compare_digest(provided, API_TOKEN):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# --- Global State ---
class AppState:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # PROD FIX: Use APPDATA for mutable data
        if sys.platform == "win32":
            self.app_data_dir = os.path.join(os.getenv("APPDATA"), "MinecraftServerGUI")
        else:
            self.app_data_dir = os.path.join(
                os.path.expanduser("~"), ".minecraft_server_gui"
            )

        if not os.path.exists(self.app_data_dir):
            os.makedirs(self.app_data_dir)

        # Config Path
        self.config_path = os.path.join(self.app_data_dir, "gui_config.json")

        # MIGRATION: Check for legacy config in local folder (next to exe or script)
        # If running from EXE, sys.executable is the EXE. If script, __file__ is the script.
        current_dir = os.path.dirname(
            os.path.abspath(
                sys.executable if getattr(sys, "frozen", False) else __file__
            )
        )
        legacy_config = os.path.join(current_dir, "gui_config.json")

        # Alternative legacy location: one level up from backend (Resources folder)
        resources_dir = os.path.dirname(current_dir)
        legacy_config_alt = os.path.join(resources_dir, "gui_config.json")

        # Check if config exists in AppData, if not try to migrate or create empty
        if not os.path.exists(self.config_path):
            found_legacy = None
            if os.path.exists(legacy_config):
                found_legacy = legacy_config
            elif os.path.exists(legacy_config_alt):
                found_legacy = legacy_config_alt

            if found_legacy:
                try:
                    logging.info(
                        f"Migrating legacy config from {found_legacy} to {self.config_path}"
                    )
                    shutil.copy2(found_legacy, self.config_path)
                except Exception as e:
                    logging.error(f"Failed to migrate legacy config: {e}")
            else:
                default_config = os.path.join(self.script_dir, "gui_config.json")
                if os.path.exists(default_config):
                    try:
                        shutil.copy2(default_config, self.config_path)
                    except Exception as e:
                        logging.error(f"Failed to copy default config: {e}")
                else:
                    # Create empty default config
                    with open(self.config_path, "w") as f:
                        json.dump({"servers": []}, f)
                    logging.info("Created new empty config in AppData")

        self.config_manager = ConfigManager(self.config_path)

        # Java Runtimes in AppData
        self.java_runtimes_dir = os.path.join(self.app_data_dir, "java_runtimes")
        self.java_manager = JavaManager(self.java_runtimes_dir)
        self.mods_manager = ModsManager()

        self.active_websockets: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.selected_server_id: Optional[str] = None

        # Log broadcasting control (prevents WS flood from starving the API)
        self._log_queue: Optional[asyncio.Queue] = None
        self._log_broadcaster_task: Optional[asyncio.Task] = None

        # Tunnel management
        self.tunnel_process: Optional[subprocess.Popen] = None
        self.tunnel_address: Optional[str] = None
        self.dns_address: Optional[str] = None
        # Last DNS verification result (None=unknown, True=ok, False=failed)
        self._dns_ok: Optional[bool] = None
        # Serializes tunnel starts so two rapid clicks can't spawn two ssh
        # processes (which happened: two tunnels for the same port).
        self._tunnel_lock = threading.Lock()
        self._tunnel_starting = False
        # Subdomain whose SRV record is currently published, so it can be removed
        # exactly (tunnel stop / server change) instead of leaking records.
        self._dns_active_slug: Optional[str] = None
        self._dns_refresh_task: Optional[asyncio.Task] = None

        # Bedrock Tunnel (Geyser UDP)
        self.bedrock_tunnel_process: Optional[subprocess.Popen] = None
        self.bedrock_tunnel_address: Optional[str] = None
        self._bedrock_tunnel_lock = threading.Lock()
        self._bedrock_tunnel_starting = False
        # Incremented on every start/stop. A background start compares its
        # captured generation and aborts when superseded, so stopping while
        # the CLI is still downloading can never leave an orphan tunnel.
        self._bedrock_tunnel_gen = 0

        # Install Progress Tracking
        self.install_progress: int = 0
        self.install_status_msg: str = ""
        self.install_error: Optional[str] = None
        self.installed_server_id: Optional[str] = None

        self.world_size_cache = {}
        self.world_size_inflight = set()
        self.world_size_lock = threading.Lock()
        self.world_size_cache_max = 100

        # Multi-server management
        self.active_handlers = {}  # server_id -> ServerHandler

        # App-level log history for Dashboard mini-console
        self.app_log_history = collections.deque(maxlen=500)

        # --- Memory diagnostics ---
        # The memory watchdog logs RSS + sizes of every in-memory structure once
        # a minute so a leak can be pinpointed in production (backend_debug.log).
        # Deep allocation tracing is opt-in (MLSG_MEMDEBUG=1 or GET /system/memory?trace=true)
        # because tracemalloc adds overhead.
        self._mem_watchdog_task: Optional[asyncio.Task] = None
        self._tracemalloc_enabled = os.environ.get("MLSG_MEMDEBUG", "0") == "1"
        self._last_mem_rss: Optional[float] = None

        # Automatic world backups (per selected server)
        self._auto_backup_task: Optional[asyncio.Task] = None
        self._last_auto_backup = {}  # server_id -> epoch seconds

    def start_background_tasks(self):
        if self._log_queue is None:
            self._log_queue = asyncio.Queue(maxsize=2000)
        if self._log_broadcaster_task is None:
            self._log_broadcaster_task = asyncio.create_task(self._log_broadcaster())
        if self._mem_watchdog_task is None:
            self._mem_watchdog_task = asyncio.create_task(self._memory_watchdog())
        if self._auto_backup_task is None:
            self._auto_backup_task = asyncio.create_task(self._auto_backup_watchdog())
        if self._dns_refresh_task is None:
            self._dns_refresh_task = asyncio.create_task(self._dns_refresh_watchdog())

    def _enqueue_log_from_loop(self, msg_obj: dict):
        """Must be called from the asyncio loop thread."""
        if self._log_queue is None:
            return
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
        if self._log_queue is None:
            return
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
                    nxt = await asyncio.wait_for(
                        self._log_queue.get(), timeout=remaining
                    )
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

    def memory_snapshot(self, include_traces: bool = False) -> dict:
        """Return a breakdown of everything the backend holds in memory.

        Used by GET /system/memory and by the periodic watchdog log line so a
        growth can be attributed to a concrete structure (log deques, event-loop
        backlog, websockets, handlers, world-size cache ...).
        """
        try:
            proc = psutil.Process()
            rss_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
        except Exception:
            rss_mb = None

        # asyncio exposes the pending-callback deque as `_ready`, but uvloop
        # (Linux) does not, so read it defensively.
        try:
            loop_ready = len(self.loop._ready) if self.loop else None
        except Exception:
            loop_ready = None

        snap = {
            "rss_mb": rss_mb,
            "threads": threading.active_count(),
            "active_websockets": len(self.active_websockets),
            "active_handlers": len(self.active_handlers),
            "app_log_history": len(self.app_log_history),
            "log_queue": self._log_queue.qsize() if self._log_queue else None,
            "log_queue_max": self._log_queue.maxsize if self._log_queue else None,
            "loop_ready_backlog": loop_ready,
            "world_size_cache": len(self.world_size_cache),
            "world_size_inflight": len(self.world_size_inflight),
        }

        handler = self.server_handler
        if handler is not None:
            snap["handler"] = {
                "server_id": handler.server_id,
                "log_history": len(handler.log_history),
                "tracked_players": len(handler.tracked_players),
            }

        if include_traces or self._tracemalloc_enabled:
            try:
                import tracemalloc

                if not tracemalloc.is_tracing():
                    tracemalloc.start(10)
                current, peak = tracemalloc.get_traced_memory()
                top = []
                for stat in tracemalloc.take_snapshot().statistics("lineno")[:10]:
                    top.append(
                        {
                            "location": str(stat.traceback),
                            "size_kb": round(stat.size / 1024, 1),
                        }
                    )
                snap["tracemalloc"] = {
                    "current_mb": round(current / (1024 * 1024), 2),
                    "peak_mb": round(peak / (1024 * 1024), 2),
                    "top": top,
                }
                tracemalloc.stop()
            except Exception as e:
                snap["tracemalloc"] = {"error": str(e)}

        return snap

    async def _memory_watchdog(self):
        """Logs the memory breakdown once a minute and trims the heap on Linux."""
        while True:
            try:
                await asyncio.sleep(60)
                snap = self.memory_snapshot()
                rss = snap.get("rss_mb")
                delta = ""
                if isinstance(rss, (int, float)) and self._last_mem_rss is not None:
                    delta = f" (Δ{rss - self._last_mem_rss:+.1f}MB)"
                if isinstance(rss, (int, float)):
                    self._last_mem_rss = rss
                logging.info(
                    f"[mem] RSS={rss}MB{delta} threads={snap['threads']} "
                    f"ws={snap['active_websockets']} handlers={snap['active_handlers']} "
                    f"app_logs={snap['app_log_history']} q={snap['log_queue']} "
                    f"loop_ready={snap['loop_ready_backlog']} "
                    f"world_cache={snap['world_size_cache']} "
                    f"handler={snap.get('handler')}"
                )
                # Give freed heap back to the OS on Linux (no-op on Windows).
                _malloc_trim()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.debug(f"[mem] watchdog error: {e}")

    async def _auto_backup_watchdog(self):
        """Create scheduled world backups for the selected server.

        Runs the (blocking) zip creation in a worker thread so the event loop
        keeps serving requests.
        """
        while True:
            try:
                await asyncio.sleep(60)
                if not self.selected_server_id or not self.server_handler:
                    continue

                cfg = self.config_manager.get_server(self.selected_server_id) or {}
                settings = cfg.get("auto_backup") or {}
                if not settings.get("enabled"):
                    continue

                interval_min = max(5, int(settings.get("interval_minutes", 60)))
                keep = max(1, int(settings.get("keep", 5)))
                now = time.time()
                last = self._last_auto_backup.get(self.selected_server_id, 0)
                if now - last < interval_min * 60:
                    continue

                server_path = self.server_handler.server_path
                world_name = _resolve_world_name(server_path)
                name = await asyncio.to_thread(
                    _create_world_backup_sync, server_path, world_name
                )
                self._last_auto_backup[self.selected_server_id] = time.time()
                removed = _prune_backups(server_path, world_name, keep)
                self.broadcast_log_sync(
                    f"🗄️ Auto-backup created: {name}"
                    + (f" (removed {removed} old)" if removed else ""),
                    "info",
                )
                self.broadcast_log_sync(
                    {"type": "backup_created", "name": name, "world": world_name}
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.debug(f"[auto-backup] error: {e}")

    async def _dns_refresh_watchdog(self):
        """Re-publish the SRV every 6h so the Worker's age-based cleanup never
        removes the record of a long-running tunnel."""
        while True:
            try:
                await asyncio.sleep(6 * 3600)
                if (
                    self.tunnel_address
                    and self._dns_active_slug
                    and self.tunnel_process
                    and self.tunnel_process.poll() is None
                ):
                    await asyncio.to_thread(
                        _call_dns_proxy,
                        self,
                        "create",
                        self._dns_active_slug,
                        self.tunnel_address,
                    )
                    logging.info("[dns] refreshed SRV record")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.debug(f"[dns] refresh error: {e}")

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
        # Fallback to app log history if server logs are empty (e.g. startup/install logs)
        return self.app_log_history

    def load_server(self, server_id):
        server_config = self.config_manager.get_server(server_id)
        if not server_config:
            raise ValueError("Server not found")

        self.selected_server_id = server_id

        # If we already have a handler for this server, use it
        if server_id in self.active_handlers:
            self.broadcast_log_sync(
                f"Reconnected to server: {server_config.get('name', server_id)}", "info"
            )
            return server_config

        server_path = server_config.get("path")
        if not server_path or not os.path.exists(server_path):
            raise ValueError(f"Server path invalid: {server_path}")

        self.broadcast_log_sync(
            f"Switched to server: {server_config.get('name', server_id)}", "info"
        )

        # Create new handler
        new_handler = ServerHandler(
            server_id=server_id,
            server_path=server_path,
            server_type=server_config.get("type")
            or server_config.get("server_type")
            or "vanilla",
            ram_min=server_config.get("ram_min", "2"),
            ram_max=server_config.get("ram_max", "4"),
            ram_unit=server_config.get("ram_unit", "G"),
            output_callback=self.broadcast_log_sync,
            minecraft_version=server_config.get("version")
            or server_config.get("minecraft_version"),
            java_path=server_config.get("java_path"),  # Pass saved Java path
        )
        self.active_handlers[server_id] = new_handler

        # Cargar subdominio DNS personalizado si existe
        dns_sub = server_config.get("dns_subdomain", "")
        if dns_sub:
            new_handler.dns_subdomain = dns_sub

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

            # Bound memory: truncate huge messages (e.g. a 1MB force-flushed log
            # chunk) before they enter app_log_history (deque 500) or the async
            # log queue (maxsize 2000). Without this, a chatty/idle server with
            # newline-less output could retain gigabytes in these structures.
            msg_text_check = msg_obj.get("message") if isinstance(msg_obj, dict) else None
            if isinstance(msg_text_check, str) and len(msg_text_check) > MAX_LOG_LINE_LEN:
                msg_obj = dict(msg_obj)
                msg_obj["message"] = msg_text_check[:MAX_LOG_LINE_LEN] + " …[truncated]"

            # Store in app-level history for Dashboard polling
            # Skip verbose installer logs (recipe files, etc.) to avoid spam
            msg_text = (
                msg_obj.get("message", "")
                if isinstance(msg_obj, dict)
                else str(msg_obj)
            )

            # Robust filter for Forge/other installer verbose output
            # Patterns: "[Installer]   " (extra spaces), ".json", ".jar", "data/minecraft/", etc.
            is_verbose_installer = False
            if "[Installer]" in msg_text:
                lower_msg = msg_text.lower()
                is_verbose_installer = (
                    "   " in msg_text  # File listings usually have extra indentation
                    or ".json" in lower_msg
                    or ".class" in lower_msg
                    or "data/minecraft/" in lower_msg
                    or "extracting " in lower_msg
                    or "unpacking " in lower_msg
                )

            if not is_verbose_installer:
                self.app_log_history.append(msg_obj)
                # deque auto-evicts oldest when full — no manual pop needed

                # Thread-safe enqueue into the asyncio queue (only non-verbose logs)
                if self.loop:
                    # Safety valve: if the event loop is badly backed up (e.g. a
                    # wedged websocket send), `call_soon_threadsafe` would queue
                    # an unbounded number of callbacks, each pinning a log dict.
                    # Drop the line instead of growing the backlog without bound.
                    try:
                        if len(self.loop._ready) > 5000:
                            return
                    except Exception:
                        pass
                    try:
                        self.loop.call_soon_threadsafe(
                            self._enqueue_log_from_loop, msg_obj
                        )
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


state: AppState = AppState()
logging.info(f"Global state initialized. Config path: {state.config_path}")


# --- Models ---
class ServerConfig(BaseModel):
    name: str  # New field
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
    neoforge_version: Optional[str] = None
    ram_min: str = "2"
    ram_max: str = "4"
    ram_unit: str = "G"


class ValidatePathRequest(BaseModel):
    path: str


class SelectServerRequest(BaseModel):
    server_id: str


class ModInstallRequest(BaseModel):
    version_id: str


class ModDeleteRequest(BaseModel):
    filename: str


class ScheduleStopRequest(BaseModel):
    minutes: int


# --- Core Endpoints ---


@app.get("/servers")
async def list_servers():
    if not state:
        return []
    servers = state.config_manager.get_all_servers()

    # Enrich with runtime status
    for s in servers:
        s_id = s.get("id")
        if s_id in state.active_handlers:
            s["status"] = state.active_handlers[s_id].get_status()
        else:
            s["status"] = "offline"

        # Ensure version compatibility
        if "version" not in s and "minecraft_version" in s:
            s["version"] = s["minecraft_version"]
        elif "minecraft_version" not in s and "version" in s:
            s["minecraft_version"] = s["version"]

    return servers


@app.get("/app-settings")
async def get_app_settings():
    if not state:
        return {}
    settings = dict(state.config_manager.config.get("app_settings", {}))
    # If a server is selected, merge that server's specific hardware config
    # so Settings.jsx initializes with the current server's actual values
    if state.selected_server_id:
        server = state.config_manager.get_server(state.selected_server_id)
        if server:
            for field in ["ram_min", "ram_max", "ram_unit", "java_path"]:
                if field in server and server[field] is not None:
                    settings[field] = server[field]
    return settings


@app.put("/app-settings")
async def update_app_settings(request: Request):
    if not state:
        raise HTTPException(status_code=500, detail="Backend not initialized")
    body = await request.json()
    if "app_settings" not in state.config_manager.config:
        state.config_manager.config["app_settings"] = {}
    state.config_manager.config["app_settings"].update(body)
    state.config_manager.save()

    # Also update active handlers' java_path
    if "java_path" in body:
        for handler in state.active_handlers.values():
            handler.java_path = body["java_path"]
        if state.server_handler:
            state.server_handler.java_path = body["java_path"]

    # Synchronize selected server profile and handler with RAM and Java settings
    if state.selected_server_id:
        server_updates = {}
        for field in ["ram_min", "ram_max", "ram_unit", "java_path"]:
            if field in body and body[field] is not None:
                server_updates[field] = str(body[field])
        if server_updates:
            state.config_manager.update_server(state.selected_server_id, server_updates)

    if state.server_handler and ("ram_max" in body or "ram_min" in body or "ram_unit" in body):
        ram_max = str(body.get("ram_max", state.server_handler.ram_max))
        ram_min = str(body.get("ram_min", state.server_handler.ram_min))
        ram_unit = str(body.get("ram_unit", state.server_handler.ram_unit))
        state.server_handler.update_ram(ram_max, ram_min, ram_unit)

    return state.config_manager.config["app_settings"]


@app.post("/servers")
async def add_server(config: ServerConfig):
    # This endpoint creates a new profile
    data = config.dict()
    # Ensure validation
    if not os.path.exists(data["path"]):
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
            state.app_log_history.clear()

        config = state.load_server(req.server_id)

        # Guardar marca de tiempo de apertura para la sección "Recently Opened"
        from datetime import datetime

        state.config_manager.update_server(
            req.server_id, {"last_opened": datetime.now().isoformat()}
        )

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
    dns_slug = (server_info.get("dns_subdomain") or "").strip() if server_info else ""

    # Delete the profile
    state.config_manager.delete_server(server_id)
    # Clean up handler from active_handlers to prevent memory leaks
    if server_id in state.active_handlers:
        handler = state.active_handlers.pop(server_id)
        try:
            handler.stop()
        except:
            pass
    if state.selected_server_id == server_id:
        state.selected_server_id = None

    # Free the DNS record so deleted servers don't keep leaking DNS entries
    # (this is what filled the zone's record quota).
    if dns_slug:
        try:
            _delete_dns_for_subdomain(state, dns_slug)
        except Exception:
            pass

    # Optionally delete files
    if delete_files and server_path and os.path.exists(server_path):
        import shutil

        try:
            shutil.rmtree(server_path)
        except Exception as e:
            return {"status": "deleted", "files_deleted": False, "error": str(e)}
        return {"status": "deleted", "files_deleted": True}

    return {"status": "deleted", "files_deleted": False}


def _detect_geyser(state):
    """Detect if GeyserMC and Floodgate are installed, and read the Bedrock port."""
    info = {
        "installed": False,
        "bedrock_port": 19132,
        "floodgate_installed": False,
        "config_path": None,
        "type": None,
    }
    if not state or not state.server_handler:
        return info

    server_path = state.server_handler.server_path
    if not server_path or not os.path.exists(server_path):
        return info

    # Check plugins folder
    plugins_dir = os.path.join(server_path, "plugins")
    if os.path.exists(plugins_dir):
        try:
            for f in os.listdir(plugins_dir):
                fl = f.lower()
                if fl.endswith(".jar"):
                    if "geyser" in fl:
                        info["installed"] = True
                        info["type"] = "plugin"
                    if "floodgate" in fl:
                        info["floodgate_installed"] = True
        except Exception:
            pass

    # Check mods folder
    mods_dir = os.path.join(server_path, "mods")
    if os.path.exists(mods_dir):
        try:
            for f in os.listdir(mods_dir):
                fl = f.lower()
                if fl.endswith(".jar"):
                    if "geyser" in fl:
                        info["installed"] = True
                        info["type"] = "mod"
                    if "floodgate" in fl:
                        info["floodgate_installed"] = True
        except Exception:
            pass

    # Candidate config paths
    config_candidates = [
        os.path.join(server_path, "plugins", "Geyser-Spigot", "config.yml"),
        os.path.join(server_path, "plugins", "Geyser-Paper", "config.yml"),
        os.path.join(server_path, "plugins", "Geyser", "config.yml"),
        os.path.join(server_path, "config", "Geyser-Fabric", "config.yml"),
        os.path.join(server_path, "config", "Geyser-NeoForge", "config.yml"),
        os.path.join(server_path, "config", "Geyser", "config.yml"),
    ]

    for cpath in config_candidates:
        if os.path.exists(cpath):
            info["config_path"] = cpath
            info["installed"] = True
            try:
                with open(cpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                import re

                match = re.search(
                    r"bedrock:\s*(?:\n\s*#[^\n]*)*\n(?:\s+[^\n]+\n)*?\s+port:\s*(\d+)",
                    content,
                )
                if match:
                    info["bedrock_port"] = int(match.group(1))
                    break
                m2 = re.search(r"^\s*port:\s*(\d+)", content, re.MULTILINE)
                if m2:
                    info["bedrock_port"] = int(m2.group(1))
                    break
            except Exception as e:
                logging.warning(f"Failed to read Geyser config {cpath}: {e}")

    return info


@app.get("/status")
def get_status():
    if not state:
        return {"status": "offline", "cpu": 0, "ram": 0, "players": 0}

    # If we are installing, return 'starting' so the UI knows we are busy
    installing = (
        getattr(state, "install_progress", 0) > 0
        and getattr(state, "install_progress", 0) < 100
    )

    if not state.server_handler:
        ram_str = "0/0 GB"
        if state.selected_server_id:
            server = state.config_manager.get_server(state.selected_server_id)
            if server and server.get("ram_max"):
                try:
                    val = float(server["ram_max"])
                    if server.get("ram_unit") == "M":
                        val /= 1024.0
                    ram_str = f"0.0/{val:.1f} GB"
                except (ValueError, TypeError):
                    pass
        return {
            "status": "starting" if installing else "not_configured",
            "server_id": state.selected_server_id,
            "cpu": 0,
            "ram": ram_str,
            "players": 0,
            "recent_logs": list(state.log_history)[-50:],
        }

    stats = state.server_handler.get_stats()

    online_players = state.server_handler.get_active_players_list(trigger_refresh=False)
    players_count = len(online_players) if online_players is not None else 0
    return {
        "status": state.server_handler.get_status(),
        "pid": state.server_handler.get_pid(),
        "server_id": state.server_handler.server_id,
        "server_type": state.server_handler.server_type,
        "minecraft_version": state.server_handler.minecraft_version,
        "version": state.server_handler.minecraft_version,
        "cpu": stats["cpu"],
        "ram": stats["ram"],
        "ram_min": getattr(state.server_handler, "ram_min", "2"),
        "ram_max": getattr(state.server_handler, "ram_max", "4"),
        "ram_unit": getattr(state.server_handler, "ram_unit", "G"),
        "players": players_count,
        "max_players": state.server_handler.get_max_players(),
        "online_players": online_players,
        "uptime": stats["uptime"],
        "recent_logs": list(state.log_history)[-50:],
        "shutdown_info": state.server_handler.get_shutdown_info(),
        "tunnel": {
            "active": state.tunnel_process is not None
            and state.tunnel_process.poll() is None,
            "address": state.tunnel_address,
            "dns_address": state.dns_address,
        },
        "bedrock_tunnel": {
            "active": state.bedrock_tunnel_process is not None
            and state.bedrock_tunnel_process.poll() is None,
            "starting": state._bedrock_tunnel_starting,
            "address": state.bedrock_tunnel_address,
        },
        "geyser": _detect_geyser(state),
        "auto_restart": {
            "enabled": state.server_handler.auto_restart,
            "attempt": state.server_handler._restart_count,
            "max_attempts": state.server_handler._max_restarts,
        },
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
    logging.info("API: /start request received")
    if not state or not state.server_handler:
        logging.error("API: /start failed - Server not configured")
        raise HTTPException(status_code=400, detail="Server not configured")

    try:
        logging.info("API: Triggering server_handler.start()...")
        state.server_handler.start()
        return {"message": "Start command issued"}
    except Exception as e:
        logging.exception("API: Critical error in /start endpoint")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stop")
def stop_server(force: bool = False):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.stop(force=force)
    return {"message": "Stop command issued"}


@app.post("/server/schedule-stop")
def schedule_stop_server(req: ScheduleStopRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    success, message = state.server_handler.schedule_shutdown(req.minutes)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@app.post("/server/cancel-stop")
def cancel_stop_server():
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    success, message = state.server_handler.cancel_shutdown()
    return {"message": message}


@app.post("/server/auto-restart")
def set_auto_restart(enabled: bool = True):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.auto_restart = enabled
    state.server_handler._restart_count = 0
    return {"message": f"Auto-restart {'enabled' if enabled else 'disabled'}"}


@app.get("/server/auto-restart")
def get_auto_restart():
    if not state or not state.server_handler:
        return {"enabled": False, "attempt": 0, "max_attempts": 3}
    return {
        "enabled": state.server_handler.auto_restart,
        "attempt": state.server_handler._restart_count,
        "max_attempts": state.server_handler._max_restarts,
    }


@app.post("/command")
def send_console_command(cmd: CommandRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    state.server_handler.send_command(cmd.command)
    return {"message": "Command sent"}


@app.post("/configure")
def configure_server(config: ServerConfig):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    if not state.selected_server_id:
        raise HTTPException(status_code=400, detail="No server selected")
    # NOTE: this endpoint used attributes that don't exist on ServerConfig
    # (server_path/server_type/minecraft_version) and called a non-existent
    # initialize_handler(), so it always raised. Update the selected profile.
    updates = {
        "path": config.path,
        "type": config.type,
        "ram_min": config.ram_min,
        "ram_max": config.ram_max,
        "ram_unit": config.ram_unit,
    }
    if config.version:
        updates["version"] = config.version
    state.config_manager.update_server(state.selected_server_id, updates)
    if state.server_handler:
        state.server_handler.update_ram(config.ram_max, config.ram_min, config.ram_unit)
    return {"message": "Configuration saved"}


# --- Setup Endpoints ---


@app.get("/setup/versions/{server_type}")
def getting_versions(server_type: str):
    if server_type.lower() == "forge":
        # Return a simplified list or the structured dict
        versions = get_forge_versions()
        return {"versions": list(versions.keys()), "all_data": versions}
    elif server_type.lower() == "neoforge":
        versions = get_neoforge_versions()
        return {"versions": list(versions.keys()), "all_data": versions}
    else:
        # returns list of dicts {version: "1.20.1", ...}
        data = get_server_versions(server_type)
        # Extract just version strings for easier frontend consumption
        versions = [v["version"] for v in data] if data else []
        return {"versions": versions}


@app.get("/setup/java/check/{minecraft_version}")
def check_java_status(minecraft_version: str):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    return state.java_manager.get_java_status(minecraft_version)


class InstallJavaRequest(BaseModel):
    minecraft_version: str


class DetectRequest(BaseModel):
    path: str


@app.post("/setup/detect")
def detect_server_info(req: DetectRequest):
    detector = ServerDetector()
    return detector.detect(req.path)


@app.post("/setup/java/install")
def install_java_endpoint(req: InstallJavaRequest):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")

    logging.info(f"Received Java install request for MC {req.minecraft_version}")

    def run_java_install():
        try:
            logging.info("Starting run_java_install thread")
            # Log the java manager base dir
            logging.info(f"JavaManager base dir: {state.java_manager.base_dir}")

            required_version = state.java_manager.get_required_java_version(
                req.minecraft_version
            )
            logging.info(f"Required Java version: {required_version}")

            def send_progress(pct):
                logging.debug(f"Java Progress: {pct}%")
                state.broadcast_log_sync(
                    {
                        "type": "java_progress",
                        "value": pct,
                        "message": f"Downloading Java {required_version}...",
                    }
                )

            send_progress(0)
            state.broadcast_log_sync(
                f"Starting Java {required_version} download...", "info"
            )

            logging.info("Calling download_java...")
            java_path = state.java_manager.download_java(
                required_version, progress_callback=send_progress
            )
            logging.info(f"download_java returned: {java_path}")

            if java_path:
                send_progress(100)
                state.broadcast_log_sync(f"Java installed at {java_path}", "success")
                logging.info("Java install success broadcasted")
            else:
                logging.error("Java download execution returned None")
                state.broadcast_log_sync("Java download failed", "error")
                state.broadcast_log_sync(
                    {"type": "java_progress", "value": 0, "error": "Download failed"}
                )

        except Exception as e:
            logging.exception("Exception in run_java_install:")
            state.broadcast_log_sync(f"Java install error: {e}", "error")
            state.broadcast_log_sync(
                {"type": "java_progress", "value": 0, "error": str(e)}
            )

    threading.Thread(target=run_java_install, daemon=True).start()
    return {"message": "Java installation started"}


@app.post("/setup/validate-path")
def validate_path(req: ValidatePathRequest):
    if os.path.isdir(req.path):
        # Check if valid server
        has_jar = any(f.endswith(".jar") for f in os.listdir(req.path))
        return {"valid": True, "has_jar": has_jar}
    return {"valid": False, "error": "Directory does not exist"}


@app.get("/setup/install/progress")
def get_install_progress():
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    return {
        "value": state.install_progress,
        "message": state.install_status_msg,
        "error": state.install_error,
        "server_id": state.installed_server_id,
    }


@app.post("/setup/install")
def install_server(req: InstallRequest):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")

    install_path = os.path.join(req.parent_path, req.folder_name)

    def run_install():
        logging.info("Installation thread started")
        try:
            # Normalize server type to lowercase so the mcutils download URL and
            # the dispatch below behave consistently regardless of the casing the
            # frontend sends (e.g. "Paper" vs "paper"). mcutils returns HTTP 500
            # for capitalized types, which previously broke Paper installs.
            server_type = (req.server_type or "").lower()

            # Helper to send structured progress
            def send_progress(pct, msg, **kwargs):
                state.install_progress = pct
                state.install_status_msg = msg
                if "server_id" in kwargs:
                    state.installed_server_id = kwargs["server_id"]

                data = {"type": "progress", "value": pct, "message": msg}
                data.update(kwargs)
                state.broadcast_log_sync(data)

            # Reset progress state at start
            state.install_progress = 0
            state.install_status_msg = "Preparing directory..."
            state.install_error = None
            state.installed_server_id = None

            # 1. Preparación del Directorio
            send_progress(
                5, f"Preparing directory for {req.server_type} {req.version}..."
            )
            os.makedirs(install_path, exist_ok=True)
            state.broadcast_log_sync(f"Install location: {install_path}", "info")

            # 2. GESTIÓN AUTOMÁTICA DE JAVA (Paso Crítico para Forge)
            # Forge requiere ejecutar su instalador con la versión correcta de Java.
            send_progress(10, "Checking Java compatibility...")

            last_java_p = -1

            def java_progress_callback(p):
                nonlocal last_java_p
                int_p = int(p)
                if int_p > last_java_p:
                    last_java_p = int_p
                    # Map Java download (0-100) to 10-20% of overall installation
                    scaled = 10 + (p * 0.1)
                    send_progress(scaled, f"Setting up Java Runtime ({int(p)}%)...")

            # Esto descarga Java si es necesario y devuelve la ruta al ejecutable
            java_path = state.java_manager.get_java_for_server(
                install_path,
                req.version,
                force_download=False,
                progress_callback=java_progress_callback,
            )

            if not java_path:
                raise Exception(
                    f"Could not setup a valid Java runtime for Minecraft {req.version}"
                )

            state.broadcast_log_sync(f"Using Java: {java_path}", "success")

            # Progress wrapper for download functions
            # Throttle updates to avoid flooding the WebSocket and freezing the UI
            last_progress = -1

            def progress_callback(p):
                nonlocal last_progress
                int_p = int(p)
                if int_p > last_progress:
                    last_progress = int_p
                    # Map download 0-100 to overall 20-50 range
                    scaled = 20 + (p * 0.3)
                    send_progress(scaled, "Downloading server files...")

            # 3. Instalación del Servidor
            if server_type == "forge":
                # Crear un handler temporal con la ruta de Java CORRECTA explícita
                temp_handler = ServerHandler(
                    install_path,
                    "forge",
                    "1",
                    "2",
                    "G",
                    output_callback=lambda m, l: state.broadcast_log_sync(m, l),
                    minecraft_version=req.version,
                    java_path=java_path,  # IMPORTANTE: Usar el Java recién obtenido
                )

                # Wrap progress for forge installer (50-90 range)
                def forge_progress(p):
                    scaled = 50 + (p * 0.4)
                    send_progress(
                        scaled, "Running Forge Installer (this may take a while)..."
                    )

                forge_ver = req.forge_version
                if not forge_ver:
                    send_progress(
                        15, f"Fetching latest Forge version for {req.version}..."
                    )
                    from utils.api_client import get_forge_versions

                    versions = get_forge_versions()
                    if req.version in versions and versions[req.version]:
                        forge_ver = versions[req.version][0]
                        state.broadcast_log_sync(
                            f"Auto-selected Forge version: {forge_ver}", "info"
                        )
                    else:
                        raise Exception(
                            f"No Forge version found for Minecraft {req.version}"
                        )

                # Ejecutar instalador
                temp_handler.install_forge_server(
                    forge_ver, req.version, forge_progress
                )

            elif server_type == "neoforge":
                # NeoForge logic
                temp_handler = ServerHandler(
                    install_path,
                    "neoforge",
                    "1",
                    "2",
                    "G",
                    output_callback=lambda m, l: state.broadcast_log_sync(m, l),
                    minecraft_version=req.version,
                    java_path=java_path,
                )

                def neoforge_progress(p):
                    scaled = 50 + (p * 0.4)
                    send_progress(
                        scaled, "Running NeoForge Installer (this may take a while)..."
                    )

                neoforge_ver = req.neoforge_version
                if not neoforge_ver:
                    send_progress(
                        15, f"Fetching latest NeoForge version for {req.version}..."
                    )
                    from utils.api_client import get_neoforge_versions

                    versions = get_neoforge_versions()
                    if req.version in versions and versions[req.version]:
                        neoforge_ver = versions[req.version][0]
                        state.broadcast_log_sync(
                            f"Auto-selected NeoForge version: {neoforge_ver}", "info"
                        )
                    else:
                        raise Exception(
                            f"No NeoForge version found for Minecraft {req.version}"
                        )

                # Ejecutar instalador
                temp_handler.install_neoforge_server(neoforge_ver, neoforge_progress)

            else:
                # Vanilla / Paper / Spigot / Fabric logic
                jar_path = os.path.join(install_path, "server.jar")
                success = download_server_jar(
                    server_type, req.version, jar_path, progress_callback
                )
                if not success:
                    # Surface the real failure reason (URL/status/exception) instead
                    # of a generic message so users can diagnose Paper/Spigot issues.
                    reason = getattr(
                        download_file_from_url, "last_error", None
                    ) or "Unknown error"
                    raise Exception(f"Failed to download Server JAR: {reason}")

            # 4. Configuración Final
            send_progress(95, "Finalizing configuration...")

            # Create new server profile
            new_server_data = {
                "name": req.folder_name,
                "path": install_path,
                "type": server_type,
                "version": req.version,
                "ram_min": req.ram_min,
                "ram_max": req.ram_max,
                "ram_unit": req.ram_unit,
                "java_path": java_path,  # Guardar la ruta de Java detectada en la config
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
            state.broadcast_log_sync(
                "Installation complete! Server is ready to start.", "success"
            )

        except Exception as e:
            logging.exception(f"Installation failed: {e}")
            state.install_error = str(e)
            state.broadcast_log_sync(f"Installation failed: {e}", "error")
            state.broadcast_log_sync({"type": "progress", "value": 0, "error": str(e)})

    threading.Thread(target=run_install, daemon=True).start()
    return {"message": "Installation started running in background"}


@app.websocket("/ws/console")
async def websocket_console(websocket: WebSocket):
    # WebSocket handshakes bypass CORS, so the shared token is the gate here.
    if API_TOKEN:
        provided = websocket.query_params.get("token", "")
        if not secrets.compare_digest(provided, API_TOKEN):
            await websocket.close(code=1008)
            return
    await websocket.accept()
    # logging.info("WebSocket connected")
    if state:
        state.active_websockets.append(websocket)
        # Replay history
        try:
            history = list(state.log_history)[-200:]
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
    except ConnectionResetError:
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
            with open(os.path.join(server_path, name), "r") as f:
                return json.load(f)
        except:
            return []

    ops = load_json("ops.json")
    banned = load_json("banned-players.json")
    whitelist = load_json("whitelist.json")

    # Get Online Players via ServerHandler (uses status_query)
    online_players = []
    if state.server_handler:
        try:
            raw_sample = state.server_handler.get_active_players_list()
            # Convert SLP format {name, id} to frontend expected {name, uuid}
            if raw_sample and isinstance(raw_sample, list):
                for player in raw_sample:
                    if isinstance(player, dict):
                        online_players.append(
                            {
                                "name": player.get("name", "Unknown"),
                                "uuid": player.get("id") or player.get("uuid", ""),
                            }
                        )
                    else:
                        # Fallback for non-dict objects (some libraries return objects)
                        online_players.append(
                            {
                                "name": getattr(player, "name", str(player)),
                                "uuid": getattr(
                                    player, "id", getattr(player, "uuid", "")
                                ),
                            }
                        )
        except Exception as e:
            logging.error(f"Error processing online players list: {e}")

    return {
        "online": online_players,
        "ops": ops,
        "banned": banned,
        "whitelist": whitelist,
    }


@app.post("/players/op")
def op_player(req: PlayerActionRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

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
            r = requests.get(
                f"https://api.mojang.com/users/profiles/minecraft/{req.name}",
                timeout=10,
            )
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
        entry = {
            "uuid": uuid,
            "name": req.name,
            "level": 4,
            "bypassesPlayerLimit": False,
        }

        updated = update_json_list(path, entry, "uuid")
        return {"message": f"Opped {req.name} (Offline)"}


@app.post("/players/deop")
def deop_player(req: PlayerActionRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    if state.server_handler.is_running():
        state.server_handler.send_command(f"deop {req.name}")
        return {"message": f"Deopped {req.name}"}
    else:
        path = os.path.join(state.server_handler.server_path, "ops.json")
        remove_from_json_list(path, "name", req.name)
        return {"message": f"Deopped {req.name} (Offline)"}


@app.post("/players/whitelist/add")
def whitelist_add(req: PlayerActionRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    if state.server_handler.is_running():
        state.server_handler.send_command(f"whitelist add {req.name}")
        return {"message": f"Added {req.name} to whitelist"}
    else:
        # Fetch UUID as required for whitelist usually
        import requests

        uuid = ""
        try:
            r = requests.get(
                f"https://api.mojang.com/users/profiles/minecraft/{req.name}",
                timeout=10,
            )
            if r.status_code == 200:
                uuid = r.json().get("id")
                if len(uuid) == 32:
                    uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        except:
            pass

        if not uuid:
            return {
                "message": "Could not fetch UUID. Cannot Whitelist offline without UUID."
            }

        path = os.path.join(state.server_handler.server_path, "whitelist.json")
        entry = {"uuid": uuid, "name": req.name}
        update_json_list(path, entry, "uuid")
        return {"message": f"Added {req.name} to whitelist (Offline)"}


@app.post("/players/whitelist/remove")
def whitelist_remove(req: PlayerActionRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    if state.server_handler.is_running():
        state.server_handler.send_command(f"whitelist remove {req.name}")
        return {"message": f"Removed {req.name} from whitelist"}
    else:
        path = os.path.join(state.server_handler.server_path, "whitelist.json")
        remove_from_json_list(path, "name", req.name)
        return {"message": f"Removed {req.name} from whitelist (Offline)"}


@app.post("/players/ban")
def ban_player(req: PlayerActionRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    reason = f" {req.reason}" if req.reason else ""

    if state.server_handler.is_running():
        state.server_handler.send_command(f"ban {req.name}{reason}")
        return {"message": f"Banned {req.name}"}
    else:
        # For ban, we ideally need UUID too for banned-players.json
        import requests

        uuid = ""
        try:
            r = requests.get(
                f"https://api.mojang.com/users/profiles/minecraft/{req.name}",
                timeout=10,
            )
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
            "reason": req.reason or "Banned by operator",
        }
        update_json_list(path, entry, "uuid")
        return {"message": f"Banned {req.name} (Offline)"}


@app.post("/players/pardon")
def pardon_player(req: PlayerActionRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    if state.server_handler.is_running():
        state.server_handler.send_command(f"pardon {req.name}")
        return {"message": f"Unbanned {req.name}"}
    else:
        path = os.path.join(state.server_handler.server_path, "banned-players.json")
        remove_from_json_list(path, "name", req.name)
        return {"message": f"Unbanned {req.name} (Offline)"}


@app.post("/players/kick")
def kick_player(req: PlayerActionRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
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
            with open(path, "r") as f:
                data = json.load(f)
        except:
            data = []

    # Check if exists
    exists = False
    for i, item in enumerate(data):
        if item.get(key_id) == entry.get(key_id):
            data[i] = entry
            exists = True
            break
    if not exists:
        data.append(entry)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def remove_from_json_list(path, key, value):
    """Removes an entry from a JSON list file."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)

        # Filter out
        data = [item for item in data if item.get(key) != value]

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass


# --- Settings Endpoints ---


@app.get("/settings/properties")
def get_server_properties():
    if not state or not state.server_handler:
        return {}
    path = os.path.join(state.server_handler.server_path, "server.properties")
    props = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    props[key.strip()] = value.strip()
    return props


@app.post("/settings/properties")
async def update_server_properties(request: Request):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    data = await request.json()
    path = os.path.join(state.server_handler.server_path, "server.properties")

    # Read existing lines to preserve comments/order
    lines = []
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.readlines()

    new_lines = []
    processed_keys = set()

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, val = stripped.split("=", 1)
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

    with open(path, "w") as f:
        f.writelines(new_lines)

    return {"message": "Properties updated"}


@app.get("/settings/app")
def get_app_settings():
    if not state:
        return {}
    conf = state.config_manager.config
    return {
        "ram_min": conf.get("ram_min", "2"),
        "ram_max": conf.get("ram_max", "4"),
        "ram_unit": conf.get("ram_unit", "G"),
        "java_path": conf.get("java_path", "java"),
    }


@app.post("/settings/app")
async def update_app_settings(request: Request):
    if not state:
        raise HTTPException(status_code=500, detail="App state invalid")
    data = await request.json()

    # Update config manager
    state.config_manager.config.update(data)
    state.config_manager.save()

    # Update active handler if it exists
    if state.server_handler:
        state.server_handler.java_path = data.get(
            "java_path", state.server_handler.java_path
        )
        # Update RAM (handler method updates its internal state)
        if "ram_max" in data or "ram_min" in data:
            state.server_handler.update_ram(
                data.get("ram_max", state.server_handler.ram_max),
                data.get("ram_min", state.server_handler.ram_min),
                data.get("ram_unit", state.server_handler.ram_unit),
            )

    return {"message": "App settings updated"}


# --- World Management Endpoints ---


@app.get("/worlds")
def get_worlds():
    if not state or not state.server_handler:
        return []

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
                        size_str = (
                            cached.get("size")
                            if cached and cached.get("size")
                            else "..."
                        )

                        with state.world_size_lock:
                            if item_path not in state.world_size_inflight:
                                state.world_size_inflight.add(item_path)

                                def _compute_world_size(
                                    path_to_size: str, expected_folder_mtime: float
                                ):
                                    try:
                                        total_size = 0
                                        for dirpath, dirnames, filenames in os.walk(
                                            path_to_size
                                        ):
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
                                            # Evict oldest entries if cache exceeds limit
                                            if len(state.world_size_cache) > state.world_size_cache_max:
                                                excess = sorted(state.world_size_cache.keys())[:-state.world_size_cache_max]
                                                for k in excess:
                                                    del state.world_size_cache[k]
                                    finally:
                                        if state:
                                            with state.world_size_lock:
                                                state.world_size_inflight.discard(
                                                    path_to_size
                                                )

                                threading.Thread(
                                    target=_compute_world_size,
                                    args=(item_path, folder_mtime),
                                    daemon=True,
                                ).start()

                    worlds.append(
                        {
                            "name": item,
                            "size": size_str or "...",
                            "last_modified": level_mtime,
                        }
                    )

    return worlds


@app.post("/worlds/create")
def create_world(request: Request):
    # Basic stub. Minecraft creates world automatically if level-name changes to non-existent folder.
    pass


# --- World backup helpers ---


def _resolve_world_name(server_path, world_name=None):
    """Return the world name to operate on, falling back to server.properties."""
    world_name = (world_name or "").strip() or None
    if not world_name:
        props_path = os.path.join(server_path, "server.properties")
        try:
            if os.path.exists(props_path):
                with open(props_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if line.startswith("level-name="):
                            world_name = line.split("=", 1)[1].strip() or None
                            break
        except Exception:
            world_name = None
    return world_name or "world"


def _backups_dir(server_path):
    d = os.path.join(server_path, "world_backups")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_backup_path(server_path, name):
    """Resolve a backup filename inside world_backups, rejecting traversal."""
    if not name or name != os.path.basename(name) or not name.lower().endswith(".zip"):
        return None
    backups_dir = os.path.abspath(_backups_dir(server_path))
    candidate = os.path.abspath(os.path.join(backups_dir, name))
    if os.path.dirname(candidate) != backups_dir:
        return None
    return candidate


def _create_world_backup_sync(server_path, world_name):
    """Create a zip backup of `world_name` and return its filename. Blocking."""
    world_path = os.path.join(server_path, world_name)
    if not os.path.isdir(world_path):
        raise FileNotFoundError(f"World not found: {world_name}")

    backups_dir = _backups_dir(server_path)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{world_name}-{ts}.zip"
    backup_path = os.path.join(backups_dir, backup_name)
    counter = 1
    while os.path.exists(backup_path):
        backup_name = f"{world_name}-{ts}-{counter}.zip"
        backup_path = os.path.join(backups_dir, backup_name)
        counter += 1
    try:
        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for dirpath, dirnames, filenames in os.walk(world_path):
                for filename in filenames:
                    full_path = os.path.join(dirpath, filename)
                    try:
                        arcname = os.path.relpath(full_path, server_path)
                        zf.write(full_path, arcname=arcname)
                    except Exception:
                        pass
    except Exception:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass
        raise
    return backup_name


def _prune_backups(server_path, world_name, keep):
    """Delete oldest backups for a world, keeping the newest `keep`."""
    if not keep or keep <= 0:
        return 0
    backups_dir = _backups_dir(server_path)
    try:
        files = [
            f
            for f in os.listdir(backups_dir)
            if f.lower().endswith(".zip") and f.startswith(f"{world_name}-")
        ]
    except Exception:
        return 0
    # Order by real mtime so same-second backups (name suffix -1, -2 ...) are
    # pruned correctly; name sorting does not order those reliably.
    files.sort(
        key=lambda f: os.path.getmtime(os.path.join(backups_dir, f)), reverse=True
    )
    removed = 0
    for f in files[keep:]:
        try:
            os.remove(os.path.join(backups_dir, f))
            removed += 1
        except Exception:
            pass
    return removed


def _safe_extract_zip(zip_path, dest_dir):
    """Extract a zip, rejecting entries that would escape dest_dir (zip-slip)."""
    dest_abs = os.path.abspath(dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            target = os.path.abspath(os.path.join(dest_abs, member.filename))
            if target != dest_abs and not target.startswith(dest_abs + os.sep):
                raise ValueError(f"Unsafe path in archive: {member.filename}")
        zf.extractall(dest_abs)


class WorldBackupRequest(BaseModel):
    world: Optional[str] = None


class BackupRestoreRequest(BaseModel):
    name: str
    world: Optional[str] = None


class BackupSettings(BaseModel):
    enabled: bool = False
    interval_minutes: int = 60
    keep: int = 5


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
            items.append(
                {"name": name, "size": f"{size_mb} MB", "created": os.path.getmtime(fp)}
            )
    except Exception:
        return items

    return items


@app.post("/worlds/backups/create")
def create_world_backup(req: WorldBackupRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    server_path = state.server_handler.server_path
    world_name = _resolve_world_name(server_path, req.world)
    world_path = os.path.join(server_path, world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail=f"World not found: {world_name}")

    def run_backup():
        try:
            if state:
                state.broadcast_log_sync(f"📦 Creating backup of '{world_name}'...", "info")
            name = _create_world_backup_sync(server_path, world_name)
            if state:
                state.broadcast_log_sync(f"✅ Backup created: {name}", "success")
                state.broadcast_log_sync(
                    {"type": "backup_created", "name": name, "world": world_name}
                )
        except Exception as e:
            if state:
                state.broadcast_log_sync(f"❌ Error creating backup: {e}", "error")

    threading.Thread(target=run_backup, daemon=True).start()
    return {"status": "started"}


@app.delete("/worlds/backups/{name}")
def delete_world_backup(name: str):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    path = _safe_backup_path(state.server_handler.server_path, name)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Backup not found")
    try:
        os.remove(path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete backup: {e}")
    return {"status": "deleted", "name": name}


@app.get("/worlds/backups/download/{name}")
def download_world_backup(name: str):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    path = _safe_backup_path(state.server_handler.server_path, name)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Backup not found")
    from fastapi.responses import FileResponse

    return FileResponse(path, filename=name, media_type="application/zip")


@app.post("/worlds/backups/restore")
def restore_world_backup(req: BackupRestoreRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    if state.server_handler.is_running():
        raise HTTPException(
            status_code=400, detail="Stop the server before restoring a backup"
        )

    server_path = state.server_handler.server_path
    backup_path = _safe_backup_path(server_path, req.name)
    if not backup_path or not os.path.isfile(backup_path):
        raise HTTPException(status_code=404, detail="Backup not found")

    tmp_dir = os.path.join(server_path, ".__restore_tmp")
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        _safe_extract_zip(backup_path, tmp_dir)

        # The archive stores paths relative to the server folder, so the world
        # lives at tmp/<folder>/level.dat. Fall back to a root-level world.
        source = None
        if os.path.exists(os.path.join(tmp_dir, "level.dat")):
            source = tmp_dir
        else:
            for entry in os.listdir(tmp_dir):
                candidate = os.path.join(tmp_dir, entry)
                if os.path.isdir(candidate) and os.path.exists(
                    os.path.join(candidate, "level.dat")
                ):
                    source = candidate
                    break
        if not source:
            raise HTTPException(
                status_code=400, detail="Backup does not contain a valid world"
            )

        target_name = (req.world or "").strip()
        if target_name and (
            target_name != os.path.basename(target_name) or not target_name
        ):
            raise HTTPException(status_code=400, detail="Invalid world name")
        if not target_name:
            target_name = os.path.basename(source) if source != tmp_dir else "world"

        target_path = os.path.join(server_path, target_name)
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        shutil.move(source, target_path)
        state.broadcast_log_sync(
            f"♻️ World '{target_name}' restored from {req.name}", "success"
        )
        return {"status": "restored", "world": target_name}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/worlds/backups/upload")
async def upload_world_backup(file: UploadFile = File(...)):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    filename = os.path.basename(file.filename or "")
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip backups are allowed")
    dest = os.path.join(_backups_dir(state.server_handler.server_path), filename)
    with open(dest, "wb") as f:
        f.write(await file.read())
    state.broadcast_log_sync(f"⬆️ Backup imported: {filename}", "info")
    return {"status": "imported", "name": filename}


@app.get("/server/backup-settings")
def get_backup_settings():
    default = {"enabled": False, "interval_minutes": 60, "keep": 5}
    if not state or not state.selected_server_id:
        return default
    cfg = state.config_manager.get_server(state.selected_server_id) or {}
    ab = cfg.get("auto_backup") or {}
    return {
        "enabled": bool(ab.get("enabled", False)),
        "interval_minutes": int(ab.get("interval_minutes", 60)),
        "keep": int(ab.get("keep", 5)),
    }


@app.post("/server/backup-settings")
def set_backup_settings(req: BackupSettings):
    if not state or not state.selected_server_id:
        raise HTTPException(status_code=400, detail="Server not configured")
    settings = {
        "enabled": bool(req.enabled),
        "interval_minutes": max(5, int(req.interval_minutes)),
        "keep": max(1, int(req.keep)),
    }
    state.config_manager.update_server(
        state.selected_server_id, {"auto_backup": settings}
    )
    return settings


# --- DNS Proxy Helper ---
def _get_server_slug(state):
    """Devuelve el subdominio personalizado del servidor, o None si no se ha configurado."""
    if not state or not state.server_handler:
        return None
    handler = state.server_handler
    if hasattr(handler, "dns_subdomain") and handler.dns_subdomain:
        slug = handler.dns_subdomain.strip().lower()
        slug = "".join(c if c.isalnum() or c in "-" else "-" for c in slug).strip("-")
        if slug:
            return slug
    return None


def _get_dns_settings(state):
    """Lee los settings del proxy DNS desde la config de la app."""
    try:
        app = state.config_manager.config.get("app_settings", {})
        enabled = app.get("dns_proxy_enabled", True)
        url = app.get("dns_proxy_url", "")
        # Siempre usar la URL por defecto
        if not url:
            url = "https://dns.ariser.app"
        return {
            "enabled": enabled,
            "url": url,
        }
    except Exception:
        return {"enabled": False, "url": ""}


def _install_id(state):
    """Stable random id for this installation (used to reserve subdomains)."""
    conf = state.config_manager.config
    iid = conf.get("install_id")
    if not iid:
        import uuid

        iid = str(uuid.uuid4())
        conf["install_id"] = iid
        state.config_manager.save()
    return iid


def _call_dns_proxy(state, action, subdomain="", target="", extra=None):
    """Call the DNS proxy Worker. Returns (ok, payload). Never raises.

    The Worker returns the real Cloudflare error (e.g. 81045 quota exceeded,
    9060 invalid target) which we surface to the UI instead of failing silently.
    """
    settings = _get_dns_settings(state)
    if not settings["enabled"] or not settings["url"]:
        return False, {"error": "DNS proxy disabled"}
    if action not in ("prune", "list") and not subdomain:
        return False, {"error": "no subdomain"}
    try:
        import requests as req

        payload = {"subdomain": subdomain, "target": target, "action": action}
        if action in ("create", "delete", "check", "release", "reserve"):
            payload["owner"] = _install_id(state)
        if extra:
            payload.update(extra)
        r = req.post(settings["url"], json=payload, timeout=30)
        try:
            data = r.json()
        except Exception:
            data = {}
        if not r.ok:
            return False, {"error": data.get("error") or f"HTTP {r.status_code}"}
        if isinstance(data, dict) and data.get("error"):
            return False, {"error": data["error"]}
        return True, data
    except Exception as e:
        return False, {"error": str(e)}


def _configured_subdomains(state):
    """Subdomains of all configured servers (the ones we must keep)."""
    subs = set()
    for s in state.config_manager.get_all_servers():
        slug = (s.get("dns_subdomain") or "").strip().lower()
        if slug:
            subs.add(slug)
    return sorted(subs)


def _track_dns_subdomain(state, slug):
    """Remember the subdomains this installation created (for safe cleanup).

    Used so cleanup only ever deletes records WE created, never those of other
    users sharing the same DNS Worker/domain.
    """
    if not state or not slug:
        return
    conf = state.config_manager.config
    known = conf.setdefault("dns_known_subdomains", [])
    slug = slug.strip().lower()
    if slug and slug not in known:
        known.append(slug)
        state.config_manager.save()


def _cleanup_own_dns_records(state, reason="startup"):
    """Delete SRV records this installation created but no longer needs.

    SAFE for a shared Worker: it only removes subdomains this app tracked in
    its own config, so it can never delete another user's records.
    """
    if not state:
        return 0
    conf = state.config_manager.config
    configured = set(_configured_subdomains(state))
    known = [s.strip().lower() for s in conf.get("dns_known_subdomains", []) if s]
    stale = [s for s in known if s not in configured]
    deleted = 0
    for s in stale:
        ok, _ = _call_dns_proxy(state, "delete", s)
        if ok:
            deleted += 1
    # Keep only what's currently configured.
    conf["dns_known_subdomains"] = sorted(configured)
    state.config_manager.save()
    if deleted:
        logging.info(f"[dns] cleanup ({reason}): deleted {deleted} own stale record(s)")
        state.broadcast_log_sync(
            f"🧹 DNS cleanup: removed {deleted} stale record(s)", "info"
        )
    return deleted


def _delete_dns_for_subdomain(state, subdomain):
    """Best-effort delete of a subdomain's SRV record (used on change/delete)."""
    if not subdomain:
        return False
    ok, _ = _call_dns_proxy(state, "delete", subdomain)
    return ok


def _dns_srv_lookup(fqdn):
    """Resolve an SRV record via DNS-over-HTTPS. Returns (results, error)."""
    try:
        import requests

        r = requests.get(
            "https://cloudflare-dns.com/dns-query",
            params={"name": fqdn, "type": "SRV"},
            headers={"accept": "application/dns-json"},
            timeout=6,
        )
        data = r.json()
    except Exception as e:
        return None, str(e)

    results = []
    for a in data.get("Answer") or []:
        if a.get("type") == 33 and a.get("data"):
            parts = a["data"].split()
            if len(parts) >= 4:
                try:
                    results.append(
                        {"port": int(parts[2]), "target": parts[3].rstrip(".")}
                    )
                except ValueError:
                    pass
    return results, None


def _verify_dns_record(state, slug, tunnel_address, attempts=6, delay=3.0):
    """Check that the SRV record exists and points to the current tunnel.

    Asks the Worker (Cloudflare API) instead of a public resolver: propagation /
    negative-caching on resolvers (1.1.1.1) made the old DoH check report false
    "no SRV record yet" errors even when the record was fine.
    """
    if not slug or not tunnel_address or ":" not in tunnel_address:
        return False, {"error": "no tunnel address"}
    host, port = tunnel_address.rsplit(":", 1)
    try:
        port_i = int(port)
    except ValueError:
        return False, {"error": "invalid tunnel address"}

    last = None
    for i in range(attempts):
        ok, data = _call_dns_proxy(state, "get", slug)
        if not ok:
            last = data.get("error")
        elif data.get("exists"):
            if (
                (data.get("target") or "").lower() == host.lower()
                and data.get("port") == port_i
            ):
                return True, {"fqdn": data.get("fqdn"), "target": f"{host}:{port_i}"}
            last = f"record points to {data.get('target')}:{data.get('port')}"
        else:
            last = "record not found yet"
        if i < attempts - 1:
            time.sleep(delay)
    return False, {"error": last or "not verified"}


def _verify_and_notify_dns(state, slug, address):
    """Verify the DNS record and notify the UI (success or failure)."""
    ok, data = _verify_dns_record(state, slug, address)
    state._dns_ok = ok
    if ok:
        state.broadcast_log_sync(
            f"✅ DNS verified: {slug}.play.ariser.app → {address}", "success"
        )
        state.broadcast_log_sync(
            {
                "type": "dns_verified",
                "address": f"{slug}.play.ariser.app",
                "target": address,
            }
        )
    else:
        state.broadcast_log_sync(
            f"⚠️ DNS verification failed for {slug}.play.ariser.app: {data.get('error')}",
            "warning",
        )
        state.broadcast_log_sync(
            {
                "type": "dns_error",
                "subdomain": slug,
                "error": f"Verification failed: {data.get('error')}",
                "direct": address,
            }
        )


def _update_dns_record_proxy(state):
    """Creates/updates the SRV record for the selected server, reporting errors."""
    settings = _get_dns_settings(state)
    if not settings["enabled"] or not settings["url"] or not state.tunnel_address:
        return
    slug = _get_server_slug(state)
    if not slug:
        # Auto-generar un slug único
        if not state.server_handler:
            return
        folder = os.path.basename(state.server_handler.server_path.rstrip("/\\"))
        folder_slug = "".join(c if c.isalnum() else "-" for c in folder.lower()).strip("-") or "mc"
        uid = (state.server_handler.server_id or "x")[:5]
        slug = f"{folder_slug}-{uid}"
        state.server_handler.dns_subdomain = slug
        state.config_manager.update_server(state.selected_server_id, {"dns_subdomain": slug})
        state.broadcast_log_sync(f"🌐 Auto-generated subdomain: {slug}", "info")

    ok, data = _call_dns_proxy(state, "create", slug, state.tunnel_address)
    if not ok:
        state.dns_address = None
        state._dns_ok = False
        err = data.get("error")
        state.broadcast_log_sync(
            f"⚠️ DNS update failed for {slug}.play.ariser.app: {err}", "warning"
        )
        state.broadcast_log_sync(
            {
                "type": "dns_error",
                "subdomain": slug,
                "error": err,
                "direct": state.tunnel_address,
            }
        )
        return

    state.dns_address = f"{slug}.play.ariser.app"
    state._dns_active_slug = slug
    state._dns_ok = None  # pending verification
    _track_dns_subdomain(state, slug)
    state.broadcast_log_sync(
        f"🌐 DNS updated: {state.dns_address} → {state.tunnel_address}", "info"
    )
    state.broadcast_log_sync({
        "type": "dns_updated",
        "address": state.dns_address,
        "target": state.tunnel_address,
    })
    # Verify the record actually resolves and tell the UI (async, with retries).
    threading.Thread(
        target=_verify_and_notify_dns,
        args=(state, slug, state.tunnel_address),
        daemon=True,
    ).start()


def _delete_dns_record_proxy(state):
    """Remove the published SRV record (tunnel stop / app exit).

    Deletes exactly the subdomain that was published so the zone doesn't fill
    up with records for tunnels that are no longer running.
    """
    slug = state._dns_active_slug or _get_server_slug(state)
    if slug:
        _delete_dns_for_subdomain(state, slug)
    state._dns_active_slug = None
    state.dns_address = None


# --- Tunnel Management Endpoints (Pinggy) ---


@app.get("/tunnel/status")
def get_tunnel_status():
    if not state:
        return {"active": False, "address": None, "dns_address": None}

    return {
        "active": state.tunnel_process is not None
        and state.tunnel_process.poll() is None,
        "address": state.tunnel_address,
        "dns_address": state.dns_address,
    }


@app.post("/tunnel/start")
def start_tunnel(
    request: Request, region: str = Query("eu"), provider: str = Query("pinggy")
):
    try:
        if not state:
            raise HTTPException(status_code=500, detail="App state not initialized")

        # Prevent concurrent starts: two rapid calls used to spawn two ssh.exe
        # processes for the same port (the second overwrote state.tunnel_process,
        # orphaning the first).
        with state._tunnel_lock:
            if state._tunnel_starting:
                return {"message": "Tunnel is already starting...", "status": "connecting"}
            state._tunnel_starting = True

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

        # Verify SSH is available BEFORE starting the thread
        ssh_executable = shutil.which("ssh")
        if not ssh_executable and sys.platform == "win32":
            # Fallback for Windows if not in PATH
            common_paths = [
                os.path.join(
                    os.environ.get("SystemRoot", "C:\\Windows"),
                    "System32\\OpenSSH\\ssh.exe",
                ),
                os.path.join(
                    os.environ.get("ProgramFiles", "C:\\Program Files"),
                    "OpenSSH\\ssh.exe",
                ),
                os.path.join(
                    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                    "OpenSSH\\ssh.exe",
                ),
            ]
            for p in common_paths:
                if os.path.exists(p):
                    ssh_executable = p
                    logging.info(f"Found SSH at fallback path: {p}")
                    break

        if not ssh_executable:
            logging.error("SSH not found in PATH or common locations")
            raise HTTPException(
                status_code=400,
                detail="SSH no encontrado. Por favor, instala 'OpenSSH Client' en las características opcionales de Windows para usar 'Make Public'.",
            )

        # Discover ssh-keygen as well
        ssh_keygen_executable = shutil.which("ssh-keygen")
        if not ssh_keygen_executable and ssh_executable:
            # If we found ssh.exe in a folder, its likely ssh-keygen is there too
            potential_keygen = os.path.join(
                os.path.dirname(ssh_executable), "ssh-keygen.exe"
            )
            if os.path.exists(potential_keygen):
                ssh_keygen_executable = potential_keygen

        if not ssh_keygen_executable:
            ssh_keygen_executable = "ssh-keygen"  # Fallback to PATH and hope for the best if we couldn't find it explicitly

        # Get server port (default 25565)
        port = "25565"
        if state.server_handler:
            try:
                props_path = os.path.join(
                    state.server_handler.server_path, "server.properties"
                )
                if os.path.exists(props_path):
                    with open(props_path, "r", encoding="utf-8", errors="replace") as f:
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
                        [
                            ssh_keygen_executable,
                            "-t",
                            "rsa",
                            "-b",
                            "2048",
                            "-f",
                            key_path,
                            "-N",
                            "",
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                        if sys.platform == "win32"
                        else 0,
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

                logging.info(
                    f"Starting Pinggy tunnel ({region.upper()}) for port {port}..."
                )
                state.broadcast_log_sync(
                    f"🌐 Starting public tunnel ({region.upper()}) for port {port}...",
                    "info",
                )

                # Ensure we have a key
                key_path = _ensure_ssh_key()

                # Pinggy SSH command - optimized with identity
                cmd = [
                    ssh_executable,
                    "-p",
                    "443",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "ServerAliveInterval=30",
                    "-o",
                    "BatchMode=yes",
                    "-T",  # Disable pseudo-terminal
                ]

                if key_path and os.path.exists(key_path):
                    cmd.extend(["-i", key_path, "-o", "IdentitiesOnly=yes"])

                cmd.extend(["-R", f"0:127.0.0.1:{port}", f"tcp@{host}"])

                # Using bufsize=1 for line buffering
                state.tunnel_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32"
                    else 0,
                )

                # Read output to find the tunnel URL
                # Use iter to read line by line until process exits
                for line in iter(state.tunnel_process.stdout.readline, ""):
                    if not line:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    # logging.debug(f"Pinggy output: {line}") # Too noisy

                    # Pinggy outputs something like: "tcp://xyz.a.pinggy.io:12345"
                    # Match tcp:// format
                    tcp_match = re.search(r"tcp://([a-zA-Z0-9\.\-]+:\d+)", line)
                    if tcp_match:
                        new_addr = tcp_match.group(1)
                        if new_addr and new_addr != state.tunnel_address:
                            state.tunnel_address = new_addr

                    # Match raw address format (free.pinggy.io:12345)
                    # Broader match: something.pinggy.io:digits
                    if not state.tunnel_address:
                        addr_match = re.search(
                            r"([a-zA-Z0-9\.\-]+\.pinggy\.io:\d+)", line
                        )
                        if addr_match:
                            new_addr = addr_match.group(1)
                            if new_addr and new_addr != state.tunnel_address:
                                state.tunnel_address = new_addr

                    # Check for "Permission denied" or other errors
                    if "Permission denied" in line or "Error" in line:
                        state.broadcast_log_sync(f"Tunnel Error: {line}", "error")

                    if state.tunnel_address and not connected_emitted:
                        logging.info(f"Tunnel established: {state.tunnel_address}")
                        state.broadcast_log_sync(
                            f"✅ Public server active! Address: {state.tunnel_address}",
                            "success",
                        )
                        state.broadcast_log_sync(
                            {
                                "type": "tunnel_connected",
                                "address": state.tunnel_address,
                            }
                        )
                        connected_emitted = True
                        # Update DNS record via proxy
                        _update_dns_record_proxy(state)

                # Additional check if process exited with error
                if (
                    state.tunnel_process.poll() is not None
                    and state.tunnel_process.returncode != 0
                ):
                    err_out = (
                        state.tunnel_process.stderr.read()
                        if state.tunnel_process.stderr
                        else ""
                    )
                    if err_out:
                        logging.error(f"Tunnel process error: {err_out}")
                        state.broadcast_log_sync(f"Tunnel crashed: {err_out}", "error")

                # If we exit the loop, tunnel has closed
                state.broadcast_log_sync("🔴 Tunnel closed", "warning")
                state.broadcast_log_sync({"type": "tunnel_disconnected"})
                state.tunnel_address = None

            except Exception as e:
                logging.exception(f"Tunnel error: {e}")
                state.broadcast_log_sync(f"❌ Tunnel error: {e}", "error")
                state.tunnel_address = None
            finally:
                state._tunnel_starting = False
                # Remove the SRV: the tunnel is down, so the record is useless
                # and keeping it would fill Cloudflare's record quota over time.
                _delete_dns_record_proxy(state)

        threading.Thread(target=run_tunnel, daemon=True).start()
        return {"message": "Tunnel starting...", "status": "connecting"}
    except Exception as e:
        state._tunnel_starting = False
        logging.exception(f"Error in start_tunnel endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

    # Remove the DNS record (server is going offline).
    _delete_dns_record_proxy(state)

    return {"message": "Tunnel stopped"}


class SetTunnelAddressRequest(BaseModel):
    address: str


@app.post("/tunnel/set-address")
def set_tunnel_address(req: SetTunnelAddressRequest):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")

    state.tunnel_address = req.address

    # Save to cache
    playit_cache_file = os.path.join(state.app_data_dir, "playit_cache.json")
    try:
        import json

        with open(playit_cache_file, "w") as f:
            json.dump({"domain": req.address}, f)
    except Exception as e:
        logging.error(f"Failed to cache playit domain manually: {e}")

    state.broadcast_log_sync(f"✅ Custom IP set: {req.address}", "success")
    state.broadcast_log_sync({"type": "tunnel_connected", "address": req.address})
    return {"status": "success"}


# --- Bedrock / GeyserMC Tunnel Endpoints (Pinggy UDP) ---

PINGGY_CLI_VERSION = "v0.5.8"
# Official SHA-256 digests published by the GitHub Releases API for
# Pinggy-io/cli-js v0.5.8. A downloaded binary is only ever executed when it
# matches its pinned size and hash, so a tampered/truncated download is
# discarded instead of run.
PINGGY_CLI_ASSETS = {
    "pinggy-win-x64.exe": (
        77937645,
        "81d6446edaf9bc14dc68a767df7fe7357810c6aa6a5a037c877e693cad3ce3ea",
    ),
    "pinggy-win-arm64.exe": (
        77188103,
        "04b3a9e779f31de49f7c3deba144f45819740f22a1d64b009dfd6a86527d7652",
    ),
    "pinggy-macos-x64": (
        100772576,
        "1cf156b94d6b910f64e4d977d2e1509a2b513f40f2793692f24b17d04f3d6cba",
    ),
    "pinggy-macos-arm64": (
        97443856,
        "d77f5bf83986372b8d1f2cdd413d231acbf13ee68a971caf6d9a1bb1e68467e9",
    ),
    "pinggy-linux-x64": (
        83097576,
        "fc7fdb6a9454929b3df40f0a4476f84a3121a2bab3b8735296a29b394fb5ba1d",
    ),
    "pinggy-linux-arm64": (
        79017970,
        "d889c36a821895a6af9c4a8e11b92205fc931f7030c26116cb45e3ca76ee80f7",
    ),
}


def _pick_pinggy_asset():
    import platform

    machine = platform.machine().lower()
    is_arm = "arm" in machine or "aarch64" in machine
    if sys.platform == "win32":
        return "pinggy-win-arm64.exe" if is_arm else "pinggy-win-x64.exe"
    if sys.platform == "darwin":
        return "pinggy-macos-arm64" if is_arm else "pinggy-macos-x64"
    return "pinggy-linux-arm64" if is_arm else "pinggy-linux-x64"


def _verify_pinggy_binary(path, expected_size, expected_sha256):
    """True when the file on disk matches the pinned size and SHA-256."""
    import hashlib

    try:
        if not os.path.isfile(path) or os.path.getsize(path) != expected_size:
            return False
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == expected_sha256
    except OSError:
        return False


def _get_pinggy_cli_path(state, should_cancel=None):
    """Returns the path to the verified pinggy CLI, downloading it if needed.

    Runs inside the tunnel thread (never in the HTTP handler): the binary is
    ~75-100 MB. Downloads go to a .part file and are renamed into place only
    after size + SHA-256 verification.
    """
    sys_pinggy = shutil.which("pinggy")
    if sys_pinggy:
        return sys_pinggy

    bin_dir = os.path.join(state.app_data_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    exe_name = "pinggy.exe" if sys.platform == "win32" else "pinggy"
    target_path = os.path.join(bin_dir, exe_name)

    filename = _pick_pinggy_asset()
    expected_size, expected_sha256 = PINGGY_CLI_ASSETS[filename]
    url = (
        f"https://github.com/Pinggy-io/cli-js/releases/download/"
        f"{PINGGY_CLI_VERSION}/{filename}"
    )

    if _verify_pinggy_binary(target_path, expected_size, expected_sha256):
        return target_path

    if os.path.exists(target_path):
        logging.warning("Existing Pinggy CLI failed verification; re-downloading.")
        try:
            os.remove(target_path)
        except OSError:
            pass

    part_path = target_path + ".part"
    logging.info(f"Downloading Pinggy CLI from {url} to {target_path}...")
    state.broadcast_log_sync(
        "📥 Downloading Pinggy CLI for Bedrock UDP tunnel (~75 MB)...", "info"
    )

    def _cancelled():
        return should_cancel is not None and should_cancel()

    try:
        if _cancelled():
            return None
        import requests

        res = requests.get(url, stream=True, timeout=(10, 120))
        res.raise_for_status()
        downloaded = 0
        with open(part_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=256 * 1024):
                if _cancelled():
                    raise RuntimeError("cancelled")
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        if downloaded != expected_size:
            raise RuntimeError(
                f"size mismatch (got {downloaded} bytes, expected {expected_size})"
            )
        if not _verify_pinggy_binary(part_path, expected_size, expected_sha256):
            raise RuntimeError("SHA-256 checksum mismatch")

        os.replace(part_path, target_path)
        if sys.platform != "win32":
            os.chmod(target_path, 0o755)
        logging.info(f"Pinggy CLI successfully saved to {target_path}")
        state.broadcast_log_sync("✅ Pinggy CLI installed and verified.", "success")
        return target_path
    except Exception as e:
        logging.error(f"Failed to download Pinggy CLI: {e}")
        if str(e) != "cancelled":
            state.broadcast_log_sync(f"❌ Failed to download Pinggy CLI: {e}", "error")
        for p in (part_path,):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        return None


@app.get("/server/geyser")
def get_geyser_status():
    if not state:
        return {"installed": False, "bedrock_port": 19132, "floodgate_installed": False}
    return _detect_geyser(state)


@app.get("/tunnel/bedrock/status")
def get_bedrock_tunnel_status():
    if not state:
        return {"active": False, "address": None, "host": None, "port": None}
    active = (
        state.bedrock_tunnel_process is not None
        and state.bedrock_tunnel_process.poll() is None
    )
    b_host, b_port = (None, None)
    if state.bedrock_tunnel_address and ":" in state.bedrock_tunnel_address:
        b_host, b_port = state.bedrock_tunnel_address.rsplit(":", 1)
    return {
        "active": active,
        "starting": state._bedrock_tunnel_starting,
        "address": state.bedrock_tunnel_address,
        "host": b_host,
        "port": b_port,
    }


@app.post("/tunnel/bedrock/start")
def start_bedrock_tunnel(region: str = Query("eu")):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")

    with state._bedrock_tunnel_lock:
        if state._bedrock_tunnel_starting:
            return {
                "message": "Bedrock tunnel is already starting...",
                "status": "connecting",
            }
        state._bedrock_tunnel_starting = True
        state._bedrock_tunnel_gen += 1
        my_gen = state._bedrock_tunnel_gen

    # Stop existing tunnel before starting a new one
    if state.bedrock_tunnel_process and state.bedrock_tunnel_process.poll() is None:
        logging.info("Stopping existing Bedrock tunnel...")
        try:
            state.bedrock_tunnel_process.terminate()
            state.bedrock_tunnel_process.wait(timeout=3)
        except Exception:
            try:
                state.bedrock_tunnel_process.kill()
            except Exception:
                pass
        state.bedrock_tunnel_process = None
        state.bedrock_tunnel_address = None

    def _superseded():
        return state._bedrock_tunnel_gen != my_gen

    def run_bedrock_tunnel():
        import re
        import subprocess

        connected_emitted = False
        process = None
        try:
            # Download + verification happen here, never in the HTTP handler:
            # the CLI is ~75-100 MB and must not block the response.
            cli_path = _get_pinggy_cli_path(state, _superseded)
            if _superseded():
                return
            if not cli_path or not os.path.exists(cli_path):
                state.broadcast_log_sync(
                    "❌ Could not find or download the Pinggy CLI binary.", "error"
                )
                state.broadcast_log_sync({"type": "tunnel_bedrock_disconnected"})
                return

            geyser_info = _detect_geyser(state)
            bedrock_port = geyser_info.get("bedrock_port") or 19132

            host = f"{region}.free.pinggy.io"
            logging.info(
                f"Starting Pinggy UDP tunnel ({region.upper()}) for Bedrock port {bedrock_port}..."
            )
            state.broadcast_log_sync(
                f"🎮 Starting Bedrock UDP tunnel ({region.upper()}) on port {bedrock_port}...",
                "info",
            )

            cmd = [
                cli_path,
                "-p",
                "443",
                f"-R0:localhost:{bedrock_port}",
                f"udp@{host}",
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0,
            )
            with state._bedrock_tunnel_lock:
                if _superseded():
                    # Stop was requested while we were still starting up.
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    return
                state.bedrock_tunnel_process = process

            for line in iter(process.stdout.readline, ""):
                if not line:
                    break
                line_str = line.strip()
                if not line_str:
                    continue

                udp_match = re.search(r"udp://([a-zA-Z0-9\.\-]+:\d+)", line_str)
                if udp_match:
                    new_addr = udp_match.group(1)
                    if new_addr and new_addr != state.bedrock_tunnel_address:
                        state.bedrock_tunnel_address = new_addr

                if not state.bedrock_tunnel_address:
                    addr_match = re.search(
                        r"([a-zA-Z0-9\.\-]+\.(?:pinggy|pinggy-free)\.link:\d+)",
                        line_str,
                    )
                    if addr_match:
                        new_addr = addr_match.group(1)
                        if new_addr and new_addr != state.bedrock_tunnel_address:
                            state.bedrock_tunnel_address = new_addr

                if state.bedrock_tunnel_address and not connected_emitted:
                    logging.info(
                        f"Bedrock tunnel established: {state.bedrock_tunnel_address}"
                    )
                    b_host, b_port = (
                        state.bedrock_tunnel_address.rsplit(":", 1)
                        if ":" in state.bedrock_tunnel_address
                        else (state.bedrock_tunnel_address, "19132")
                    )
                    state.broadcast_log_sync(
                        f"✅ Bedrock Public tunnel active! Address: {b_host} Port: {b_port}",
                        "success",
                    )
                    state.broadcast_log_sync(
                        {
                            "type": "tunnel_bedrock_connected",
                            "address": state.bedrock_tunnel_address,
                            "host": b_host,
                            "port": b_port,
                        }
                    )
                    connected_emitted = True
                    # Now it is running (not starting): allow a restart click to
                    # replace it without waiting for the process to exit.
                    if not _superseded():
                        state._bedrock_tunnel_starting = False

            if not _superseded():
                state.broadcast_log_sync("🔴 Bedrock tunnel closed", "warning")
                state.broadcast_log_sync({"type": "tunnel_bedrock_disconnected"})
        except Exception as e:
            logging.exception(f"Bedrock tunnel error: {e}")
            if not _superseded():
                state.broadcast_log_sync(f"❌ Bedrock tunnel error: {e}", "error")
                state.broadcast_log_sync({"type": "tunnel_bedrock_disconnected"})
        finally:
            if not _superseded():
                state._bedrock_tunnel_starting = False
                state.bedrock_tunnel_address = None
                if state.bedrock_tunnel_process is process:
                    state.bedrock_tunnel_process = None

    threading.Thread(target=run_bedrock_tunnel, daemon=True).start()
    return {"message": "Bedrock tunnel starting...", "status": "connecting"}


@app.post("/tunnel/bedrock/stop")
def stop_bedrock_tunnel():
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")

    # Invalidate any in-flight start (including an ongoing CLI download) so a
    # late background thread can never bring the tunnel back up after this stop.
    with state._bedrock_tunnel_lock:
        was_active = state._bedrock_tunnel_starting or (
            state.bedrock_tunnel_process is not None
        )
        state._bedrock_tunnel_gen += 1
        state._bedrock_tunnel_starting = False

    if state.bedrock_tunnel_process:
        try:
            state.bedrock_tunnel_process.terminate()
            state.bedrock_tunnel_process.wait(timeout=3)
        except Exception:
            try:
                state.bedrock_tunnel_process.kill()
            except Exception:
                pass
        state.bedrock_tunnel_process = None

    if was_active:
        state.bedrock_tunnel_address = None
        state.broadcast_log_sync("🔴 Bedrock tunnel stopped", "info")
        state.broadcast_log_sync({"type": "tunnel_bedrock_disconnected"})

    return {"message": "Bedrock tunnel stopped"}


# --- DNS Subdomain Endpoints ---


@app.get("/server/dns-subdomain")
def get_dns_subdomain():
    if not state or not state.server_handler:
        return {"subdomain": "", "address": ""}
    slug = _get_server_slug(state)
    settings = _get_dns_settings(state)
    domain = ""

    # Si no hay subdominio personalizado, generar uno único
    if not slug:
        folder = os.path.basename(state.server_handler.server_path.rstrip("/\\"))
        folder_slug = "".join(c if c.isalnum() else "-" for c in folder.lower()).strip("-") or "mc"
        uid = (state.server_handler.server_id or "x")[:5]
        slug = f"{folder_slug}-{uid}"

    if settings["enabled"]:
        domain = f"{slug}.play.ariser.app"

    return {
        "subdomain": slug,
        "address": domain if settings["enabled"] else "",
        "enabled": settings["enabled"],
    }


@app.post("/server/dns-subdomain")
async def set_dns_subdomain(request: Request):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    body = await request.json()
    subdomain = (body.get("subdomain") or "").strip().lower()
    subdomain = "".join(c if c.isalnum() or c in "-" else "-" for c in subdomain).strip("-")

    if not subdomain:
        raise HTTPException(status_code=400, detail="Invalid subdomain")

    # Guardar en la config del servidor
    server_id = state.selected_server_id
    old_subdomain = _get_server_slug(state)  # capture BEFORE changing

    # Reserve the name for this installation (fails if another user has it).
    ok, data = _call_dns_proxy(state, "reserve", subdomain)
    if not ok:
        raise HTTPException(
            status_code=409, detail=data.get("error") or "Subdomain not available"
        )

    state.config_manager.update_server(server_id, {"dns_subdomain": subdomain})
    state.server_handler.dns_subdomain = subdomain

    address = f"{subdomain}.play.ariser.app"

    # Free the previous name (record + reservation) when renaming.
    if old_subdomain and old_subdomain != subdomain:
        _call_dns_proxy(state, "release", old_subdomain)

    if state.tunnel_address and state.tunnel_process and state.tunnel_process.poll() is None:
        ok, data = _call_dns_proxy(state, "create", subdomain, state.tunnel_address)
        if ok:
            state.dns_address = address
            _track_dns_subdomain(state, subdomain)
            state.broadcast_log_sync({
                "type": "dns_updated",
                "address": address,
                "target": state.tunnel_address,
            })
            state.broadcast_log_sync(f"🌐 DNS updated: {address} → {state.tunnel_address}", "info")
        else:
            state.dns_address = None
            err = data.get("error")
            state.broadcast_log_sync(f"⚠️ DNS update failed for {address}: {err}", "warning")
            state.broadcast_log_sync({"type": "dns_error", "subdomain": subdomain, "error": err})

    return {"subdomain": subdomain, "address": address}


@app.post("/server/dns-check")
async def check_dns_subdomain(request: Request):
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    body = await request.json()
    subdomain = (body.get("subdomain") or "").strip().lower()
    subdomain = "".join(c if c.isalnum() or c in "-" else "-" for c in subdomain).strip("-")

    if not subdomain:
        return {"available": False, "error": "Invalid subdomain"}

    settings = _get_dns_settings(state)
    if not settings["url"]:
        return {"available": True, "note": "No proxy configured"}

    try:
        import requests as req
        r = req.post(
            settings["url"],
            json={"subdomain": subdomain, "target": "", "action": "check"},
            timeout=5,
        )
        data = r.json()
        return data
    except Exception as e:
        return {"available": True, "note": f"Could not verify: {e}"}


@app.post("/server/dns-cleanup")
def cleanup_dns_records():
    """Remove SRV records this install created but no longer uses.

    Safe on a shared Worker: it only deletes subdomains tracked in our own
    config, never other users' records.
    """
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    deleted = _cleanup_own_dns_records(state, reason="manual")
    return {"status": "ok", "deleted": deleted}


@app.post("/server/dns-verify")
def verify_dns_record():
    """Verify that the current server's custom address actually resolves."""
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    slug = _get_server_slug(state)
    if not slug:
        return {"verified": False, "error": "No subdomain configured"}

    if state.tunnel_address:
        ok, data = _verify_dns_record(state, slug, state.tunnel_address, attempts=3, delay=2.0)
        return {
            "verified": ok,
            "address": f"{slug}.play.ariser.app",
            "target": state.tunnel_address,
            "detail": data,
        }

    # No active tunnel: only check whether a record exists (it would be stale).
    ok, data = _call_dns_proxy(state, "get", slug)
    if ok and data.get("exists"):
        return {
            "verified": True,
            "address": f"{slug}.play.ariser.app",
            "detail": data,
            "note": "No active tunnel; the record exists but may be stale",
        }
    return {
        "verified": False,
        "address": f"{slug}.play.ariser.app",
        "error": data.get("error") or "No SRV record found",
    }


# Cloudflare Free plan DNS record limit (used for the usage indicator).
DNS_ZONE_CAPACITY = 200


@app.get("/server/dns-usage")
def get_dns_usage():
    """Usage/availability of the DNS zone for the UI indicator."""
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    try:
        capacity = int(
            state.config_manager.config.get("app_settings", {})
            .get("dns_capacity", DNS_ZONE_CAPACITY)
            or DNS_ZONE_CAPACITY
        )
    except Exception:
        capacity = DNS_ZONE_CAPACITY

    ok, data = _call_dns_proxy(state, "list")
    used = srv = None
    error = None
    if ok:
        used = data.get("total")
        srv = data.get("srv")
        if used is None:
            used = data.get("count")
        if srv is None:
            srv = data.get("count")
    else:
        error = data.get("error")

    available = None
    if isinstance(used, int):
        available = max(0, capacity - used)

    return {
        "used": used,
        "capacity": capacity,
        "available": available,
        "srv": srv,
        "healthy": state._dns_ok,
        "address": state.dns_address,
        "direct": state.tunnel_address,
        "error": error,
    }


@app.get("/server/online-mode")
def get_online_mode():
    if not state or not state.server_handler:
        return {"online_mode": True}
    props = get_server_properties()
    return {"online_mode": props.get("online-mode", "true") == "true"}


@app.post("/server/online-mode")
async def toggle_online_mode(request: Request):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    body = await request.json()
    val = "true" if body.get("online_mode", True) else "false"
    _write_server_property("online-mode", val)
    state.broadcast_log_sync(f"Online-mode set to {val}", "info")
    return {"online_mode": val == "true"}


def _write_server_property(key, value):
    """Escribir una propiedad individual en server.properties."""
    if not state or not state.server_handler:
        return
    props_path = os.path.join(state.server_handler.server_path, "server.properties")
    lines = []
    found = False
    if os.path.exists(props_path):
        with open(props_path, "r") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(props_path, "w") as f:
        f.writelines(lines)


# --- Mods Endpoints ---
@app.get("/mods/search")
def search_mods(
    q: str,
    loader: str = "fabric",
    version: str = None,
    project_type: str = "mod",
    sort: str = "downloads",
    category: str = None,
):
    if not state:
        raise HTTPException(status_code=500, detail="State not initialized")

    # If version not provided, try to use server's version
    if not version and state.server_handler:
        version = state.server_handler.minecraft_version

    return state.mods_manager.search_mods(
        q, loader, version, project_type, sort, category
    )


@app.get("/mods/versions/{slug}")
def get_mod_versions(slug: str, loader: str = "fabric", version: str = None):
    if not state:
        raise HTTPException(status_code=500, detail="State not initialized")

    # If version not provided, use server's version
    if not version and state.server_handler:
        version = state.server_handler.minecraft_version

    return state.mods_manager.get_mod_versions(slug, loader, version)


@app.get("/mods/installed")
def get_installed_mods():
    if not state or not state.server_handler:
        return []
    return state.mods_manager.get_installed_mods(state.server_handler.server_path)


@app.post("/mods/install")
def install_mod(req: ModInstallRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    def run_mod_install():
        try:

            def progress(pct, msg):
                state.broadcast_log_sync(
                    {"type": "progress", "value": pct, "message": msg}
                )

            result = state.mods_manager.install_mod(
                req.version_id,
                state.server_handler.server_path,
                progress_callback=progress,
            )

            if result.get("success"):
                state.broadcast_log_sync(
                    f"Installation success: {result.get('filename') or 'Modpack'}",
                    "success",
                )
                state.broadcast_log_sync(
                    {"type": "mod_install_complete", "success": True}
                )
            else:
                state.broadcast_log_sync(
                    f"Installation failed: {result.get('error')}", "error"
                )
                state.broadcast_log_sync(
                    {"type": "mod_install_complete", "success": False}
                )

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

    success = state.mods_manager.delete_mod(
        req.filename, state.server_handler.server_path
    )
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


@app.post("/mods/import")
async def import_mod(file: UploadFile = File(...)):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")
    mods_path = os.path.join(state.server_handler.server_path, "mods")
    if not os.path.exists(mods_path):
        os.makedirs(mods_path)
    dest = os.path.join(mods_path, file.filename)
    with open(dest, "wb") as f:
        f.write(await file.read())
    state.broadcast_log_sync(f"📦 Mod imported: {file.filename}", "info")
    return {"status": "imported", "filename": file.filename}


@app.post("/system/shutdown")
def shutdown_app():
    logging.info("Shutdown request received")

    def perform_full_shutdown():
        # Stop any running tunnel
        if state and state.tunnel_process and state.tunnel_process.poll() is None:
            logging.info("Stopping tunnel process...")
            # Remove the SRV before tearing the tunnel down.
            try:
                _delete_dns_record_proxy(state)
            except Exception:
                pass
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

        # Stop Bedrock tunnel
        if state and state.bedrock_tunnel_process and state.bedrock_tunnel_process.poll() is None:
            logging.info("Stopping Bedrock tunnel process...")
            try:
                state.bedrock_tunnel_process.terminate()
                state.bedrock_tunnel_process.wait(timeout=3)
            except:
                try:
                    state.bedrock_tunnel_process.kill()
                except:
                    pass
            state.bedrock_tunnel_process = None
            state.bedrock_tunnel_address = None


        # Stop servers
        if state and state.active_handlers:
            handlers_to_wait = []
            for server_id, handler in state.active_handlers.items():
                if handler.server_process and handler.server_process.poll() is None:
                    logging.info(f"Stopping server {server_id}...")
                    handler.stop(silent=True)
                    handlers_to_wait.append((server_id, handler))

            # Wait for each server to stop
            for server_id, handler in handlers_to_wait:
                logging.info(f"Waiting for server {server_id} to stop...")
                handler.wait_for_stop(timeout=25)  # Slightly less than backend timeout

        logging.info("All servers stopped. Backend exiting.")
        # Final exit
        os._exit(0)

    # Start shutdown in a separate thread so we can return the response immediately
    threading.Thread(target=perform_full_shutdown, daemon=True).start()
    return {"message": "Shutdown sequence started"}


def start_parent_watchdog(forced_parent_pid=None):
    """Vigila si el proceso padre (Electron) sigue vivo. Si muere, cerramos todo."""
    parent_pid = forced_parent_pid or os.getppid()
    if parent_pid <= 1:  # No parent or init
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
                logging.warning(
                    "Parent process lost. Shutting down backend and servers..."
                )
                # Remove the published DNS record before dying so it doesn't leak.
                try:
                    _delete_dns_record_proxy(state)
                except Exception:
                    pass
                # Stop ALL active server handlers, not just the selected one
                if state and state.active_handlers:
                    for server_id, handler in state.active_handlers.items():
                        try:
                            if (
                                handler.server_process
                                and handler.server_process.poll() is None
                            ):
                                handler.stop(force=True, silent=True)
                        except:
                            pass
                os._exit(0)
            time.sleep(2)

    threading.Thread(target=watch, daemon=True).start()


# --- Server Appearance ---


@app.post("/server/icon")
async def upload_server_icon(file: UploadFile = File(...)):
    if not state.server_handler:
        raise HTTPException(status_code=400, detail="No server selected")

    try:
        # Check if valid image extension
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            raise HTTPException(
                status_code=400, detail="Only PNG or JPG images are allowed"
            )

        server_path = state.server_handler.server_path
        icon_path = os.path.join(server_path, "server-icon.png")

        # Try to use Pillow for resizing
        try:
            from PIL import Image
            import io

            contents = await file.read()
            img = Image.open(io.BytesIO(contents))

            # Resize to 64x64
            img = img.resize((64, 64), Image.Resampling.LANCZOS)

            # Save as PNG
            img.save(icon_path, format="PNG")

        except ImportError:
            # Fallback: Just save the file (user must ensure it's 64x64)
            # Or log warning.
            logging.warning(
                "Pillow not installed, saving icon directly. It might not work if not 64x64."
            )
            contents = await file.read()
            with open(icon_path, "wb") as f:
                f.write(contents)
        except Exception as e:
            logging.error(f"Error processing image: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to process image: {str(e)}"
            )

        return {"status": "success", "message": "Server icon updated"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/server/icon")
async def get_server_icon():
    if not state.server_handler:
        return {"exists": False}

    icon_path = os.path.join(state.server_handler.server_path, "server-icon.png")
    if os.path.exists(icon_path):
        return {"exists": True, "ts": os.path.getmtime(icon_path)}
    return {"exists": False}


@app.get("/server/icon/image")
async def get_server_icon_image():
    if not state.server_handler:
        raise HTTPException(status_code=404, detail="No server")

    icon_path = os.path.join(state.server_handler.server_path, "server-icon.png")
    if os.path.exists(icon_path):
        from fastapi.responses import FileResponse

        return FileResponse(icon_path)

    raise HTTPException(status_code=404, detail="No icon")


# --- Plugin Management (Paper/Spigot) ---


@app.get("/server/plugins")
def get_plugins():
    if not state.server_handler:
        raise HTTPException(status_code=400, detail="No server selected")

    plugins_dir = os.path.join(state.server_handler.server_path, "plugins")
    if not os.path.exists(plugins_dir):
        return []

    plugins = []
    try:
        for f in os.listdir(plugins_dir):
            if f.endswith(".jar"):
                path = os.path.join(plugins_dir, f)
                size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)
                plugins.append({"filename": f, "size": f"{size_mb} MB"})
    except Exception as e:
        logging.error(f"Error listing plugins: {e}")
        return []

    return plugins


@app.post("/server/plugins")
async def upload_plugin(file: UploadFile = File(...)):
    if not state.server_handler:
        raise HTTPException(status_code=400, detail="No server selected")

    plugins_dir = os.path.join(state.server_handler.server_path, "plugins")
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir)

    file_path = os.path.join(plugins_dir, file.filename)

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/server/plugins/{filename}")
def delete_plugin(filename: str):
    if not state.server_handler:
        raise HTTPException(status_code=400, detail="No server selected")

    plugins_dir = os.path.join(state.server_handler.server_path, "plugins")
    file_path = os.path.join(plugins_dir, filename)

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail="Plugin not found")


# --- Plugin Browsing (Modrinth) ---


@app.get("/plugins/search")
def search_plugins(
    q: str = "", version: str = None, sort: str = "downloads", category: str = None
):
    if not state:
        raise HTTPException(status_code=500, detail="State not initialized")

    # Use server version if not provided
    if not version and state.server_handler:
        version = state.server_handler.minecraft_version

    # Search with project_type="plugin" and loaders for bukkit/spigot/paper
    return state.mods_manager.search_mods(
        q,
        loader="paper",
        version=version,
        project_type="plugin",
        sort=sort,
        category=category,
    )


@app.get("/plugins/versions/{slug}")
def get_plugin_versions(slug: str, version: str = None):
    if not state:
        raise HTTPException(status_code=500, detail="State not initialized")

    if not version and state.server_handler:
        version = state.server_handler.minecraft_version

    return state.mods_manager.get_mod_versions(slug, loader="paper", version=version)


class PluginInstallRequest(BaseModel):
    version_id: str


@app.post("/plugins/install")
def install_plugin(req: PluginInstallRequest):
    if not state or not state.server_handler:
        raise HTTPException(status_code=400, detail="Server not configured")

    def run_plugin_install():
        try:

            def progress(pct, msg):
                state.broadcast_log_sync(
                    {"type": "progress", "value": pct, "message": msg}
                )

            # Get version info
            response = requests.get(
                f"https://api.modrinth.com/v2/version/{req.version_id}",
                headers={"User-Agent": "MinecraftLocalServerGUI/1.0"},
                timeout=10,
            )
            response.raise_for_status()
            version_data = response.json()

            files = version_data.get("files", [])
            if not files:
                state.broadcast_log_sync("No files found for plugin", "error")
                return

            primary_file = next((f for f in files if f.get("primary")), files[0])
            url = primary_file["url"]
            filename = primary_file["filename"]

            plugins_dir = os.path.join(state.server_handler.server_path, "plugins")
            if not os.path.exists(plugins_dir):
                os.makedirs(plugins_dir)

            file_path = os.path.join(plugins_dir, filename)

            progress(10, f"Downloading {filename}...")

            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            progress(100, "Installed!")
            state.broadcast_log_sync(f"Plugin installed: {filename}", "success")
            state.broadcast_log_sync(
                {
                    "type": "plugin_install_complete",
                    "success": True,
                    "filename": filename,
                }
            )

        except Exception as e:
            state.broadcast_log_sync(f"Plugin install error: {e}", "error")
            state.broadcast_log_sync(
                {"type": "plugin_install_complete", "success": False}
            )

    threading.Thread(target=run_plugin_install, daemon=True).start()
    return {"status": "started", "message": "Plugin installation started"}


# --- System Info (RAM validation) ---


@app.get("/system/info")
def get_system_info():
    """Returns system information for frontend validation (e.g. RAM limits)."""
    try:
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 1)
        available_gb = round(mem.available / (1024**3), 1)
        return {
            "total_ram_gb": total_gb,
            "available_ram_gb": available_gb,
            "cpu_count": psutil.cpu_count(logical=True),
            # Recommended max: 80% of total RAM
            "max_recommended_ram_gb": round(total_gb * 0.8, 1),
        }
    except Exception as e:
        logging.error(f"Error getting system info: {e}")
        return {
            "total_ram_gb": 16,
            "available_ram_gb": 8,
            "cpu_count": 4,
            "max_recommended_ram_gb": 12,
        }


@app.get("/servers/running")
def get_running_servers():
    """Returns whether any server is currently running. Used by Electron close handler."""
    if not state:
        return {"any_running": False}
    for handler in state.active_handlers.values():
        if handler.is_running() or handler.is_starting():
            return {"any_running": True}
    return {"any_running": False}


@app.get("/system/memory")
def get_memory_info(trace: bool = False):
    """Memory breakdown of the backend process.

    Poll this from the UI/console while the server runs to see which structure
    grows. Pass ?trace=true to enable tracemalloc and get the top allocation
    sites (heavier; leave it off unless diagnosing).
    """
    if not state:
        raise HTTPException(status_code=500, detail="App state not initialized")
    if trace:
        state._tracemalloc_enabled = True
    return state.memory_snapshot(include_traces=trace)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", type=int)
    args, _ = parser.parse_known_args()

    # Iniciar el watchdog antes de arrancar el servidor
    start_parent_watchdog(args.parent_pid)
    uvicorn.run(app, host="127.0.0.1", port=8000)

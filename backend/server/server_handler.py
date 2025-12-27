import subprocess
import threading
import os
import glob
import sys
import logging
import re

from utils.api_client import download_file_from_url, download_and_extract_zip
from utils.java_manager import JavaManager
from utils.status_query import get_server_status
import psutil
import time

class ServerHandler:
    def __init__(self, server_path, server_type, ram_min, ram_max, ram_unit, output_callback, java_path="java", minecraft_version=None, server_id=None):
        self.server_id = server_id
        self.server_path = server_path
        self.server_type = server_type
        self.ram_min = ram_min
        self.ram_max = ram_max
        self.ram_unit = ram_unit
        self.output_callback = output_callback
        self.java_path = java_path
        self.minecraft_version = minecraft_version
        
        # Inicializar el gestor de Java
        self.java_manager = JavaManager()
        
        self.server_process = None
        self.tunnel_process = None
        self.public_url = None
        self.tunnel_thread = None
        self.stop_tunnel_event = threading.Event()
        self.server_fully_started = False
        self.server_stopping = False
        self.server_running = False
        
        # Si tenemos la versión de Minecraft, configurar Java automáticamente
        # OPTIMIZATION: Do NOT run this in __init__ to avoid blocking the UI during server selection.
        # It will run lazily in start() -> _get_start_command()
        # if minecraft_version:
        #     self._setup_java_for_minecraft(minecraft_version)
        
        self.log_history = [] 
        
        # Track players from log messages
        self.tracked_players = set() 
        self._expecting_player_list_next_line = False
        self._last_list_request_time = 0.0
        self._list_request_cooldown = 4.0
        
        # Status Cache
        self.cached_status = None
        self.last_status_time = 0
        self.cache_duration = 4.0 # seconds 
        self._status_lock = threading.Lock()
        self._status_in_flight = False
        
        # Scheduled Shutdown
        self._shutdown_timer = None
        self._shutdown_time_target = None # Epoch time when shutdown will occur

    def _log(self, message, level="normal"):
        """Internal log method that stores history and calls callback."""
        # Clean message if string
        if isinstance(message, str):
            message = message.rstrip()
            if not message: return
            msg_obj = {"message": message, "level": level, "server_id": self.server_id}
        else:
            msg_obj = message
            if self.server_id and "server_id" not in msg_obj:
                msg_obj["server_id"] = self.server_id
            
        # Store in local history
        self.log_history.append(msg_obj)
        if len(self.log_history) > 1000:
            self.log_history.pop(0)
            
        # Broadcast via callback
        if self.output_callback:
            self.output_callback(msg_obj)

    def _setup_java_for_minecraft(self, minecraft_version):
        """Configura automáticamente la versión correcta de Java para Minecraft."""
        try:
            self._log(f"Configuring Java for Minecraft {minecraft_version}...\n", "info")
            
            # Obtener el Java apropiado - NO descargar durante el start, solo usar lo que ya existe
            java_path = self.java_manager.get_java_for_server(self.server_path, minecraft_version, skip_download=True)
            
            if java_path:
                self.java_path = java_path
                self._log(f"Java configured: {java_path}\n", "info")
            else:
                self._log("Java not found. Please install Java from the Setup Wizard before starting.\n", "warning")
                
        except Exception as e:
            self._log(f"Error configuring Java: {e}\n", "error")
    
    def set_minecraft_version(self, minecraft_version):
        """Establece la versión de Minecraft y reconfigura Java si es necesario."""
        self.minecraft_version = minecraft_version
        self._setup_java_for_minecraft(minecraft_version)
    
    def get_java_status(self):
        """Obtiene el estado actual de Java para este servidor."""
        if not self.minecraft_version:
            return {"status_message": "Minecraft version not specified", "status_color": "orange"}
        
        return self.java_manager.get_java_status(self.minecraft_version)
    
    def _verify_java_installation(self, java_path):
        """Verifica que la instalación de Java funciona correctamente."""
        try:
            result = subprocess.run(
                [java_path, "-version"], 
                capture_output=True, 
                text=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.returncode != 0:
                print(f"[DEBUG] Java Check Failed. Path: {java_path}, RC: {result.returncode}, Stderr: {result.stderr}")
            return result.returncode == 0
        except Exception as e:
            return False
        except Exception as e:
            print(f"[DEBUG] Java Check Exception. Path: {java_path}, Error: {e}")
            return False

    def open_folder(self):
        """Abre la carpeta del servidor en el explorador de archivos."""
        try:
            if sys.platform == "win32":
                os.startfile(self.server_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.server_path])
            else:
                subprocess.Popen(["xdg-open", self.server_path])
            return True
        except Exception as e:
            self.output_callback(f"Error opening folder: {e}\n", "error")
            return False


    def install_forge_server(self, forge_version, minecraft_version, progress_callback):
        """Downloads and installs a Forge server."""
        # This is an example URL structure. You'll need to get the correct URLs.
        # Example: https://maven.minecraftforge.net/net/minecraftforge/forge/1.20.1-47.2.0/forge-1.20.1-47.2.0-installer.jar
        forge_full_version = f"{minecraft_version}-{forge_version}"
        file_name = f"forge-{forge_full_version}-installer.jar"
        download_url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{forge_full_version}/{file_name}"
        installer_path = os.path.join(self.server_path, file_name)

        self.output_callback(f"Downloading Forge installer from {download_url}\n", "info")
        if not download_file_from_url(download_url, installer_path, progress_callback):
            self.output_callback("Failed to download Forge installer.\n", "error")
            return

        self.output_callback("Download complete. Running installer...\n", "info")
        
        # Run the installer
        try:
            install_command = [self.java_path, "-jar", installer_path, "--installServer"]
            process = subprocess.Popen(install_command, cwd=self.server_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            
            # Log stdout and stderr from the installer
            stdout, stderr = process.communicate()
            for line in stdout.splitlines():
                self.output_callback(f"[Installer] {line}\n", "normal")
            for line in stderr.splitlines():
                self.output_callback(f"[Installer] {line}\n", "error")

            if process.returncode != 0:
                self.output_callback("Forge installer failed with a non-zero exit code.\n", "error")
            else:
                self.output_callback("Forge installation successful.\n", "info")
                # On Windows, a run.bat is created. On Linux/macOS, a run.sh.
                # The server can now be started with the standard start() method.
                
                # Auto-configure so server is ready to run immediately
                self._accept_eula()
                self._create_default_server_properties()

        except Exception as e:
            self.output_callback(f"An error occurred during Forge installation: {e}\n", "error")
        finally:
            # Clean up the installer and its log
            self.output_callback("Cleaning up installer files...\n", "info")
            try:
                os.remove(installer_path)
                installer_log = f"{installer_path}.log"
                if os.path.exists(installer_log):
                    os.remove(installer_log)
            except OSError as e:
                self.output_callback(f"Error during cleanup: {e}\n", "warning")

    def get_status(self):
        """
        Unified status check. Prioritizes the actual process state.
        Returns: 'offline', 'starting', 'online', or 'stopping'.
        """
        if self.server_process is None or self.server_process.poll() is not None:
            return 'offline'
        
        if self.server_stopping:
            return 'stopping'
            
        if self.server_fully_started:
            return 'online'
            
        return 'starting'

    def schedule_shutdown(self, minutes):
        """Schedules a server shutdown in X minutes."""
        if not self.is_running():
            return False, "Server must be online to schedule a shutdown."
            
        self.cancel_shutdown() # Cancel any existing timer
        
        seconds = minutes * 60
        self._shutdown_time_target = time.time() + seconds
        
        def _perform_shutdown():
            self._log(f"Scheduled shutdown triggered after {minutes} minute(s).\n", "warning")
            self.stop()
            self._shutdown_timer = None
            self._shutdown_time_target = None

        self._shutdown_timer = threading.Timer(seconds, _perform_shutdown)
        self._shutdown_timer.daemon = True
        self._shutdown_timer.start()
        
        self._log(f"Server shutdown scheduled in {minutes} minute(s).\n", "info")
        return True, f"Shutdown scheduled in {minutes} minutes."

    def cancel_shutdown(self):
        """Cancels any active shutdown timer."""
        if self._shutdown_timer:
            self._shutdown_timer.cancel()
            self._shutdown_timer = None
            self._shutdown_time_target = None
            self._log("Scheduled shutdown cancelled.\n", "info")
            return True, "Shutdown cancelled."
        return False, "No shutdown scheduled."

    def get_shutdown_info(self):
        """Returns the remaining time for the scheduled shutdown."""
        if self._shutdown_time_target:
            remaining = int(max(0, self._shutdown_time_target - time.time()))
            return {
                "scheduled": True,
                "remaining_seconds": remaining,
                "target_time": self._shutdown_time_target
            }
        return {"scheduled": False}

    def is_starting(self):
        return self.get_status() == 'starting'

    def is_running(self):
        return self.get_status() == 'online'

    def _accept_eula(self):
        """Checks for eula.txt and sets eula=true if found or creates it."""
        eula_path = os.path.join(self.server_path, 'eula.txt')
        try:
            if os.path.exists(eula_path):
                with open(eula_path, 'r') as f:
                    content = f.read()
                if 'eula=true' not in content:
                    with open(eula_path, 'w') as f:
                        f.write('eula=true\n')
                    self.output_callback("Accepted EULA automatically.\n", "info")
            else:
                with open(eula_path, 'w') as f:
                    f.write('eula=true\n')
                self.output_callback("Created eula.txt and accepted EULA.\n", "info")
        except Exception as e:
            self.output_callback(f"Warning: Could not accept EULA automatically: {e}\n", "warning")

    def _create_default_server_properties(self):
        """Creates a default server.properties file if it doesn't exist."""
        props_path = os.path.join(self.server_path, 'server.properties')
        try:
            if not os.path.exists(props_path):
                default_props = """#Minecraft server properties
motd=A Minecraft Server
max-players=20
online-mode=true
enable-command-block=false
spawn-protection=16
view-distance=10
simulation-distance=10
difficulty=easy
gamemode=survival
pvp=true
allow-flight=false
"""
                with open(props_path, 'w') as f:
                    f.write(default_props)
                self.output_callback("Created default server.properties.\n", "info")
        except Exception as e:
            self.output_callback(f"Warning: Could not create server.properties: {e}\n", "warning")

    def start(self):
        if self.is_running() or self.is_starting():
            self.output_callback("Server is already running or starting.\n", "warning")
            return

        if not self.server_path:
            self.output_callback("Server path is not set up.\n", "error")
            return

        # Auto-accept EULA before starting
        self._accept_eula()

        command, env = self._get_start_command()
        if not command:
            return

        self.server_fully_started = False
        self.server_stopping = False
        self.server_running = True
        self.output_callback(f"Starting server with command: {' '.join(command)}\n", "info")
        self.output_callback(f"Working Directory: {self.server_path}\n", "info")
        threading.Thread(target=self._run_server, args=(command, env), daemon=True).start()

    def _get_start_command(self):
        # Verificar que tenemos una ruta de Java válida
        java_path = self.java_path
        
        # Si tenemos versión de Minecraft y no hemos configurado Java específico, intentar configurarlo
        if self.minecraft_version and java_path == "java":
            self._setup_java_for_minecraft(self.minecraft_version)
            java_path = self.java_path
        
        # Verificar que Java existe y funciona
        if not self._verify_java_installation(java_path):
            self.output_callback(f"Error: Java is not working at: {java_path}. Attempting to repair...\n", "warning")
            
            # Intentar reparar buscando de nuevo
            new_path = self.ensure_java_compatibility(self.minecraft_version)
            if new_path and new_path != java_path and self._verify_java_installation(new_path):
                self.output_callback(f"Fixed: Using new Java path: {new_path}\n", "success")
                java_path = new_path
                self.java_path = new_path
            else:
                # Último intento: usar simplemente "java" del sistema
                if self._verify_java_installation("java"):
                     self.output_callback("Fixed: Using system 'java' (PATH).\n", "success")
                     java_path = "java"
                     self.java_path = "java"
                else:
                    self.output_callback("Critical error: No working Java installation was found. Please install Java.\n", "error")
                    return None, None
        
        run_script = None
        
        # Universal check for startup scripts
        if sys.platform == "win32":
            script_path = os.path.join(self.server_path, 'run.bat')
            if os.path.exists(script_path):
                run_script = script_path
        else: # For macOS and Linux
            script_path = os.path.join(self.server_path, 'run.sh')
            if os.path.exists(script_path):
                run_script = script_path

        # If a run script is found, prioritize it
        if run_script:
            self.output_callback(f"Detected startup script: {os.path.basename(run_script)}. Using it to launch.\n", "info")
            # For Forge, we might need to set JVM_ARGS, but for now, a direct run is more universal.
            # A more advanced implementation could parse the script to inject RAM settings.
            return [run_script, '--nogui'], None

        # Fallback to JAR-based startup if no script is found
        self.output_callback("No startup script found. Using generic JAR startup method.\n", "info")
        all_jars = glob.glob(os.path.join(self.server_path, '*.jar'))
        server_jar_path = None
        
        non_installer_jars = [j for j in all_jars if 'installer' not in os.path.basename(j).lower()]
        
        if non_installer_jars:
            # Look for common server jar names first
            preferred_names = ['server.jar', 'minecraft_server.jar', 'paper.jar', 'spigot.jar', 'fabric-server-launch.jar']
            for name in preferred_names:
                for jar in non_installer_jars:
                    if os.path.basename(jar).lower() == name:
                        server_jar_path = jar
                        break
                if server_jar_path:
                    break
            
            # If no preferred name is found, take the first non-installer jar
            if not server_jar_path:
                server_jar_path = non_installer_jars[0]
        
        elif all_jars: # Fallback if only installer jars are present for some reason
            server_jar_path = all_jars[0]

        if not server_jar_path:
            self.output_callback("Error: No server .jar file or run script found in the directory.\n", "error")
            return None, None

        min_ram_str = f"-Xms{self.ram_min}{self.ram_unit}"
        max_ram_str = f"-Xmx{self.ram_max}{self.ram_unit}"
        
        # Base command with suppression flags
        command = [
            java_path, 
            max_ram_str, 
            min_ram_str,
            "--add-modules=jdk.incubator.vector", 
            "--enable-native-access=ALL-UNNAMED",
            "-XX:+UnlockExperimentalVMOptions",
            # Forge/ModLauncher Java 16+ compatibility args
            "--add-exports=java.base/sun.security.util=ALL-UNNAMED",
            "--add-opens=java.base/java.util.jar=ALL-UNNAMED",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            "--add-opens=java.base/java.util=ALL-UNNAMED",
            "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED",
            "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
            "--add-opens=java.base/java.text=ALL-UNNAMED",
            "--add-opens=java.desktop/java.awt.font=ALL-UNNAMED",
            "--add-opens=java.base/java.nio=ALL-UNNAMED",
            "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
            "--add-opens=java.management/sun.management=ALL-UNNAMED",
            "--add-opens=jdk.management/com.sun.management.internal=ALL-UNNAMED"
        ]
        
        # Add any server-type specific arguments before the -jar flag
        # Example for future use:
        # if self.server_type == 'some_type':
        #     command.extend(['-Dsome.flag=true'])

        command.extend(['-jar', os.path.basename(server_jar_path), '--nogui'])
        
        return command, None

    def _run_server(self, command, env):
        try:
            self.server_process = subprocess.Popen(command, cwd=self.server_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0, env=env)
            
            stdout_thread = threading.Thread(target=self._read_output, args=(self.server_process.stdout, "normal"), daemon=True)
            stderr_thread = threading.Thread(target=self._read_output, args=(self.server_process.stderr, "error"), daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            self.server_process.wait()
        except FileNotFoundError:
            self._log("Error: 'java' command not found. Is Java installed and in your PATH?\n", "error")
        except Exception as e:
            self._log(f"Server start failed: {e}\n", "error")
        finally:
            # Esperar a que los hilos de salida terminen de procesar los últimos logs
            # Esto evita que el estado se quede en 'stopping' si el log llega justo al final.
            try:
                if stdout_thread: stdout_thread.join(timeout=2)
                if stderr_thread: stderr_thread.join(timeout=2)
            except: pass

            # --- CRITICAL FIX: ACTUALIZAR ESTADO INTERNO PRIMERO ---
            # Guardamos el estado previo para el log
            was_stopping = self.server_stopping
            
            # 1. Marcar inmediatamente como detenido para que cualquier consulta a /status
            # devuelva "offline" y no "stopping" o "online".
            self.server_fully_started = False
            self.server_process = None
            self.server_running = False
            self.server_stopping = False

            # 2. Enviar mensaje de log final
            if not was_stopping:
                self._log("Server stopped unexpectedly.\n", "error")
            else:
                self._log("Server stopped.\n", "info")

            # 3. NOTIFICAR AL FRONTEND VIA WEBSOCKET (Explicit event)
            # Esto asegura que el frontend limpie cualquier estado 'stopping' residual.
            if self.output_callback:
                self.output_callback({
                    "type": "status_change",
                    "status": "offline",
                    "server_id": self.server_id
                })

    def _read_output(self, pipe, level):
        import re
        join_pattern = re.compile(r'\b([A-Za-z0-9_]{1,16})\b\s+joined the game', re.IGNORECASE)
        leave_pattern = re.compile(r'\b([A-Za-z0-9_]{1,16})\b\s+left the game', re.IGNORECASE)
        # Allow any prefix (timestamp/logger) before the message
        list_inline_pattern = re.compile(r".*There are\s+\d+\s+of\s+a\s+max\s+of\s+\d+\s+players\s+online:\s*(.*)", re.IGNORECASE)
        list_header_pattern = re.compile(r".*There are\s+\d+\s+of\s+a\s+max\s+of\s+\d+\s+players\s+online:\s*$", re.IGNORECASE)

        try:
            for line in iter(pipe.readline, ''):
                line_no_ansi = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
                if 'Done' in line_no_ansi and 'For help' in line_no_ansi:
                    self.server_fully_started = True
                    self.server_stopping = False
                    # Broadcast explicit status change to online
                    if self.output_callback:
                        self.output_callback({
                            "type": "status_change",
                            "status": "online",
                            "server_id": self.server_id
                        })
                elif 'Stopping the server' in line_no_ansi or 'Stopping server' in line_no_ansi:
                    self.server_stopping = True
                elif 'All dimensions are saved' in line_no_ansi or 'All chunks are saved' in line_no_ansi:
                    self.server_stopping = True
                    # Detect that the server HAS saved everything.
                    # If it doesn't close in 7 seconds, we force it.
                    def delayed_kill():
                        time.sleep(7)
                        if self.get_status() == 'stopping':
                            self._log("Server finished saving but hung. Forcing termination.\n", "warning")
                            self._kill_process_tree()
                    
                    threading.Thread(target=delayed_kill, daemon=True).start()
                
                # Detect player join/leave
                join_match = join_pattern.search(line_no_ansi)
                if join_match:
                    player_name = join_match.group(1)
                    self.tracked_players.add(player_name)
                    
                leave_match = leave_pattern.search(line_no_ansi)
                if leave_match:
                    player_name = leave_match.group(1)
                    self.tracked_players.discard(player_name)

                clean_line = line_no_ansi.strip()
                suppress_from_console = False
                if clean_line:
                    if self._expecting_player_list_next_line:
                        # Only accept the expected next line if it actually contains a players list.
                        # Some servers output only the header line when there are 0 players.
                        if "players online:" not in clean_line.lower():
                            self._expecting_player_list_next_line = False
                        else:
                            # Parse the content after 'players online:' (avoid issues with timestamp prefixes)
                            names_line = clean_line.split("players online:", 1)[1].strip()
                            if names_line:
                                self.tracked_players = {p.strip() for p in names_line.split(",") if p.strip()}
                            else:
                                self.tracked_players = set()
                            self._expecting_player_list_next_line = False

                            # Hide list output from console, but keep parsed data
                            suppress_from_console = True

                    elif "there are no players online" in clean_line.lower():
                        self.tracked_players = set()
                        self._expecting_player_list_next_line = False

                        # Hide list output from console
                        suppress_from_console = True

                    else:
                        inline_match = list_inline_pattern.search(clean_line)
                        if inline_match is not None:
                            names_part = (inline_match.group(1) or "").strip()
                            if names_part:
                                self.tracked_players = {p.strip() for p in names_part.split(",") if p.strip()}
                            else:
                                self._expecting_player_list_next_line = True

                            # Hide list output from console
                            suppress_from_console = True
                        elif list_header_pattern.search(clean_line) is not None:
                            self._expecting_player_list_next_line = True

                            # Hide list output from console
                            suppress_from_console = True
                
                if not suppress_from_console:
                    self._log(line_no_ansi, level)
        finally:
            pipe.close()

    def request_player_list_refresh(self, force: bool = False):
        if not self.is_running():
            return
        now = time.time()
        if force or (now - self._last_list_request_time) >= self._list_request_cooldown:
            self._last_list_request_time = now
            self.send_command("list", silent=True)

    def stop(self, silent=False, force=False):
        """Detiene el servidor. Si force=True, mata el proceso inmediatamente."""
        # Cancel any scheduled shutdown if manual stop is called
        if self._shutdown_timer:
            self._shutdown_timer.cancel()
            self._shutdown_timer = None
            self._shutdown_time_target = None

        if not self.is_running() and not self.is_starting():
            return

        self.server_stopping = True
        
        if force:
            if not silent:
                self._log("Force killing server process tree...\n", "warning")
            self._kill_process_tree()
            return

        self.tracked_players.clear()  # Clear player list on stop
        
        if self.server_process:
            if not silent:
                self._log("Attempting graceful stop...\n", "info")
            self.send_command("stop")
            
            # Cerrar stdin para señalar EOF (Fin de Archivo). 
            # Esto ayuda a que Java sepa que la consola se ha cerrado y termine antes.
            try:
                if self.server_process and self.server_process.stdin:
                    self.server_process.stdin.close()
            except Exception as e:
                self._log(f"Warning closing stdin: {e}\n", "warning")
            
            # Lanzar un hilo para vigilar si se cuelga
            threading.Thread(target=self._watchdog_stop, daemon=True).start()

    def _watchdog_stop(self):
        """Vigila si el servidor tarda demasiado en cerrarse y avisa."""
        time.sleep(30)
        if self.is_running():
            self._log("Server is taking a long time to stop. You can force stop it now.\n", "warning")

    def _kill_process_tree(self):
        """Mata el proceso del servidor y todos sus hijos."""
        if not self.server_process:
            return
            
        pid = self.server_process.pid
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try: 
                    child.kill()
                except: 
                    pass
            parent.kill()
        except psutil.NoSuchProcess:
            pass
        finally:
            self.force_stop_state()
            self._log("Server process killed.\n", "error")
            if self.output_callback:
                self.output_callback({
                    "type": "status_change",
                    "status": "offline",
                    "server_id": self.server_id
                })

    def wait_for_stop(self, timeout=30):
        """Blocks until the server process has exited or the timeout is reached."""
        if not self.server_process:
            return True
            
        try:
            # Wait for the process to exit
            self.server_process.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            self._log(f"Warning: Server did not stop within {timeout}s. Forcing termination.\n", "warning")
            try:
                self.server_process.kill()
            except:
                pass
            return False
        except Exception as e:
            self._log(f"Error while waiting for server to stop: {e}\n", "error")
            return False

    def send_command(self, command, silent: bool = False):
        if self.server_process and self.server_process.poll() is None and self.server_process.stdin:
            try:
                # Echo command to log history so Dashboard can see it
                if not silent:
                    self._log(f"> {command}", "input")
                self.server_process.stdin.write(f"{command}\n")
                self.server_process.stdin.flush()
            except (IOError, ValueError) as e:
                self.output_callback(f"Error sending command: {e}\n", "error")
        else:
            self.output_callback("Cannot send command: server is not running or stdin is not available.\n", "warning")

    def update_ram(self, ram_max, ram_min, ram_unit):
        self.ram_max = ram_max
        self.ram_min = ram_min
        self.ram_unit = ram_unit
        self.output_callback(f"RAM settings updated to {ram_min}-{ram_max}{ram_unit}. Changes will apply on next restart.\n", "info")
    
    def ensure_java_compatibility(self, minecraft_version):
        """
        Asegura que Java sea compatible con la versión de Minecraft especificada.
        Descarga automáticamente si es necesario.
        """
        if not self.java_manager:
            return self.java_path
        
        try:
            # Intentar obtener Java compatible para este servidor
            # Si la ruta actual es sospechosa (Oracle javapath) forzamos descarga?
            force = False
            if self.java_path and "javapath" in self.java_path.lower():
                 force = True
                 
            compatible_java = self.java_manager.get_java_for_server(self.server_path, minecraft_version, force_download=force)
            
            if compatible_java:
                old_java = self.java_path
                self.java_path = compatible_java
                if old_java != compatible_java:
                    self.output_callback(f"Java updated automatically: {compatible_java}\n", "info")
                return compatible_java
            else:
                self.output_callback(f"Warning: Could not obtain compatible Java for Minecraft {minecraft_version}\n", "warning")
                return self.java_path
                
        except Exception as e:
            self.output_callback(f"Error checking Java compatibility: {e}\n", "error")
            return self.java_path

    def get_pid(self):
        if self.server_process:
            return self.server_process.pid
# ... (rest of the code remains the same)
        return None

    def get_server_properties(self):
        """Parses server.properties into a dict."""
        props = {}
        props_file = os.path.join(self.server_path, 'server.properties')
        if os.path.exists(props_file):
            try:
                with open(props_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            props[key.strip()] = value.strip()
            except Exception as e:
                self.output_callback(f"Error reading server.properties: {e}\n", "error")
        return props

    def get_stats(self):
        if not self.server_process:
            self._cached_process = None
            return {"cpu": 0, "ram": "0/0 GB", "uptime": "0h 0m"}
        
        try:
            # Logic to find the actual Java process if we haven't already or if it died
            if not hasattr(self, '_cached_process') or self._cached_process is None or not self._cached_process.is_running():
                parent = psutil.Process(self.server_process.pid)
                
                # Get all descendants
                try:
                    children = parent.children(recursive=True)
                except psutil.NoSuchProcess:
                    children = []

                # Include parent in candidates? Usually parent is cmd.exe, we want the heavy child.
                candidates = children + [parent]
                
                best_proc = None
                max_mem = -1

                for p in candidates:
                    try:
                        # Get memory info
                        mem_info = p.memory_info()
                        rss = mem_info.rss
                        
                        # Prioritize if name contains java
                        name = p.name().lower()
                        score = rss
                        if 'java' in name or 'openjdk' in name:
                            # Give a massive bonus to java processes so they win even if they just started and have low ram
                            score += 1024 * 1024 * 1024 * 100 # +100GB bonus
                        
                        if score > max_mem:
                            max_mem = score
                            best_proc = p
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                if best_proc:
                    self._cached_process = best_proc
                    # Debug log to verify we hooked the right one
                    # self.output_callback(f"[Debug] Monitoring Process: {best_proc.name()} (PID: {best_proc.pid})\n", "normal")
                else:
                    self._cached_process = parent

            proc = self._cached_process
            
            with proc.oneshot():
                cpu_percent = proc.cpu_percent(interval=None) / psutil.cpu_count()
                mem = proc.memory_info()
                create_time = proc.create_time()

            # RAM
            ram_used_gb = mem.rss / (1024 * 1024 * 1024)
            ram_max_gb = float(self.ram_max) # simple assumption
            
            # Uptime
            uptime_seconds = time.time() - create_time
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            return {
                "cpu": round(cpu_percent, 1),
                "ram": f"{ram_used_gb:.1f}/{ram_max_gb:.1f} GB",
                "uptime": f"{hours}h {minutes}m"
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            # If process dies or we can't read it, reset cache
            self._cached_process = None
            return {"cpu": 0, "ram": "0/0 GB", "uptime": "0h 0m"}

    def force_stop_state(self):
        """Forcefully resets the server's state variables, e.g., after a crash or EULA stop."""
        self.server_fully_started = False
        self.server_process = None
        self.server_running = False
        self.server_stopping = False

    def get_bore_path(self):
        """Returns the expected path to the bore executable."""
        return os.path.join(os.getcwd(), "bore.exe")

    def is_bore_downloaded(self):
        """Checks if bore.exe exists."""
        return os.path.exists(self.get_bore_path())

    def _download_bore(self):
        """Downloads and extracts bore.exe."""
        # URL for bore v0.5.0 for Windows
        bore_url = "https://github.com/ekzhang/bore/releases/download/v0.5.0/bore-v0.5.0-x86_64-pc-windows-msvc.zip"
        extract_dir = os.getcwd()
        
        self.output_callback("Downloading bore executable (this will only happen once)...\n", "info")

        # Simple progress display via output_callback. A real progress bar would require more GUI integration.
        def progress_callback(p):
            self.output_callback(f"\rDownload progress: {p}%", "info")

        if download_and_extract_zip(bore_url, extract_dir, progress_callback):
            self.output_callback("\nBore downloaded successfully.\n", "info")
            return True
        else:
            self.output_callback("\nFailed to download bore.\n", "error")
            return False

    def start_tunnel(self, port):
        """Starts the tunnel using bore."""
        if self.is_tunnel_running():
            self.output_callback("Tunnel is already running.\n", "warning")
            return

        if not self.is_bore_downloaded():
            self.output_callback("Bore executable not found. Attempting to download...\n", "info")
            if not self._download_bore():
                self.output_callback("Could not start tunnel due to download failure.\n", "error")
                return
        
        bore_path = self.get_bore_path()
        command = [bore_path, "local", str(port), "--to", "bore.pub"]

        self.output_callback("Starting tunnel...\n", "info")

        self.stop_tunnel_event.clear()
        self.tunnel_thread = threading.Thread(target=self._run_tunnel, args=(command,), daemon=True)
        self.tunnel_thread.start()

    def _run_tunnel(self, command):
        """Runs the bore process and captures its output."""
        try:
            self.tunnel_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            self.output_callback("Tunnel process started. Waiting for public URL...\n", "info")

            # Read output line-by-line to find the URL
            for line in iter(self.tunnel_process.stdout.readline, ''):
                if self.stop_tunnel_event.is_set():
                    break
                
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                self.output_callback(f"[Tunnel] {line_stripped}\n", "normal")
                
                # Clean the line of ANSI escape codes for reliable parsing
                clean_line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line_stripped)

                if "listening at" in clean_line and not self.public_url:
                    try:
                        url_part = clean_line.split("listening at")[1].strip()
                        self.public_url = url_part
                        self.output_callback(f"PUBLIC_URL:{self.public_url}\n", "success")
                        # URL found, break the reading loop and move to waiting
                        break
                    except IndexError:
                        self.output_callback("Could not parse public URL from tunnel output.\n", "warning")
            
            # If we are here, we either found the URL, the process died, or we are stopping
            if self.stop_tunnel_event.is_set():
                # We were asked to stop while searching for URL, which is handled in stop_tunnel
                pass
            elif self.public_url:
                # URL was found, now just wait for the process to end for any reason.
                # This will block the thread until stop_tunnel() is called or the process dies.
                self.tunnel_process.wait()
            else:
                # Loop finished but we have no URL, means process died before giving one
                self.output_callback("Tunnel process exited before providing a public URL.\n", "warning")

        except FileNotFoundError:
            self.output_callback(f"Error: bore.exe not found at {command[0]}\n", "error")
        except Exception as e:
            self.output_callback(f"An error occurred while running the tunnel: {e}\n", "error")
        finally:
            # This block now runs only when the process has truly terminated
            self.tunnel_process = None
            self.public_url = None
            if not self.stop_tunnel_event.is_set():
                 self.output_callback("Tunnel stopped unexpectedly.\n", "error")
            
            # Always notify GUI to reset state
            self.output_callback("PUBLIC_URL_STOPPED\n", "info")

    def stop_tunnel(self):
        """Stops the tunnel process."""
        if not self.is_tunnel_running():
            return
            
        self.output_callback("Stopping tunnel...\n", "info")
        self.stop_tunnel_event.set()
        if self.tunnel_process:
            self.tunnel_process.terminate()
            try:
                self.tunnel_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tunnel_process.kill()
        
        if self.tunnel_thread:
            self.tunnel_thread.join(timeout=2)

        self.tunnel_process = None
        self.tunnel_thread = None
        self.public_url = None
        self.output_callback("Tunnel stopped.\n", "info")
        self.output_callback("PUBLIC_URL_STOPPED\n", "info")

    def is_tunnel_running(self):
        """Checks if the tunnel process is running."""
        return self.tunnel_thread and self.tunnel_thread.is_alive()

    def _update_status_cache(self):
        """Updates the status cache if enough time has passed."""
        if not self.is_running():
            self.cached_status = None
            return

        current_time = time.time()
        if current_time - self.last_status_time <= self.cache_duration:
            return

        # Prevent overlapping status queries (can stall the API during startup)
        with self._status_lock:
            if self._status_in_flight:
                return
            self._status_in_flight = True

        try:
            props = self.get_server_properties()
            port = int(props.get("server-port", 25565))
            try:
                self.cached_status = get_server_status(port=port, timeout=0.6)
            except Exception:
                self.cached_status = None
            self.last_status_time = time.time()
        finally:
            with self._status_lock:
                self._status_in_flight = False

    def get_player_count(self):
        """Returns the current number of online players."""
        self._update_status_cache()
        if self.cached_status and self.cached_status.get("online"):
            return self.cached_status["players"]["online"]
        return 0

    def get_max_players(self):
        """Returns the maximum number of players allowed."""
        self._update_status_cache()
        if self.cached_status and self.cached_status.get("online"):
            return self.cached_status["players"]["max"]
        
        # Fallback to properties if server is offline or query fails
        props = self.get_server_properties()
        return int(props.get("max-players", 20))

    def get_active_players_list(self, trigger_refresh: bool = True):
        """Returns a list of active players from log tracking or SLP sample."""
        # Don't spam the server with 'list' while it is still starting.
        if trigger_refresh and self.server_fully_started:
            self.request_player_list_refresh()

        # Primary: Use tracked_players from log parsing (more reliable)
        if self.tracked_players:
            return [{"name": name, "id": ""} for name in self.tracked_players]
        
        # Fallback: Use SLP sample (may be empty)
        self._update_status_cache()
        if self.cached_status and self.cached_status.get("online"):
            return self.cached_status["players"]["sample"] or []
        return []

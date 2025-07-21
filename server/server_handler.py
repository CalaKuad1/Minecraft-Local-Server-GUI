import subprocess
import threading
import os
import glob
import sys
import logging
import re

from utils.api_client import download_file_from_url, download_and_extract_zip

class ServerHandler:
    def __init__(self, server_path, server_type, ram_min, ram_max, ram_unit, output_callback, java_path="java"):
        self.server_path = server_path
        self.server_type = server_type
        self.ram_min = ram_min
        self.ram_max = ram_max
        self.ram_unit = ram_unit
        self.output_callback = output_callback
        self.java_path = java_path
        self.server_process = None
        self.tunnel_process = None
        self.public_url = None
        self.tunnel_thread = None
        self.stop_tunnel_event = threading.Event()
        self.server_fully_started = False
        self.server_stopping = False
        self.server_running = False


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

    def is_starting(self):
        return self.server_process is not None and self.server_process.poll() is None and not self.server_fully_started

    def is_running(self):
        return self.server_process is not None and self.server_process.poll() is None and self.server_fully_started

    def start(self):
        if self.is_running() or self.is_starting():
            self.output_callback("Server is already running or starting.\n", "warning")
            return

        if not self.server_path:
            self.output_callback("Server path is not set up.\n", "error")
            return

        command, env = self._get_start_command()
        if not command:
            return

        self.server_fully_started = False
        self.server_stopping = False
        self.server_running = True
        self.output_callback(f"Starting server with command: {' '.join(command)}\n", "info")
        threading.Thread(target=self._run_server, args=(command, env), daemon=True).start()

    def _get_start_command(self):
        java_path = self.java_path
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
        
        # Base command
        command = [java_path, max_ram_str, min_ram_str]
        
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
            self.output_callback("Error: 'java' command not found. Is Java installed and in your PATH?\n", "error")
        except Exception as e:
            self.output_callback(f"Server start failed: {e}\n", "error")
        finally:
            self.server_fully_started = False
            self.server_process = None
            self.server_running = False
            if not self.server_stopping:
                self.output_callback("Server stopped unexpectedly.\n", "error")

    def _read_output(self, pipe, level):
        try:
            for line in iter(pipe.readline, ''):
                if 'Done' in line and 'For help, type "help"' in line:
                    self.server_fully_started = True
                self.output_callback(line, level)
        finally:
            pipe.close()

    def stop(self, silent=False):
        if not self.is_running() and not self.is_starting():
            return

        self.server_stopping = True
        self.server_running = False
        if self.server_process:
            if not silent:
                self.output_callback("Attempting graceful stop...\n", "info")
            self.send_command("stop")
        
        # The process will terminate on its own, and the _run_server finally block will clean up.

    def send_command(self, command):
        if self.is_running() and self.server_process and self.server_process.stdin:
            try:
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

    def get_pid(self):
        if self.server_process:
            return self.server_process.pid
        return None

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

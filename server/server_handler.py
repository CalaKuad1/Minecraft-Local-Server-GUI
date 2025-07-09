import subprocess
import threading
import os
import glob
import sys

class ServerHandler:
    def __init__(self, server_path, server_type, ram_min, ram_max, ram_unit, output_callback):
        self.server_path = server_path
        self.server_type = server_type
        self.ram_min = ram_min
        self.ram_max = ram_max
        self.ram_unit = ram_unit
        self.output_callback = output_callback
        self.server_process = None
        self.server_fully_started = False
        self.server_stopping = False
        self.server_running = False

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
        java_path = "java"
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
                self.output_callback(f"> {command}\n", "info")
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

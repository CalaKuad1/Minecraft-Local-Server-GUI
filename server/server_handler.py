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
        self.server_running = False

    def start(self):
        if self.server_running:
            self.output_callback("Server is already running.\n", "warning")
            return

        if not self.server_path:
            self.output_callback("Server path is not set up.\n", "error")
            return

        command, env = self._get_start_command()
        if not command:
            return

        self.server_running = True
        self.output_callback(f"Starting server with command: {' '.join(command)}\n", "info")
        threading.Thread(target=self._run_server, args=(command, env), daemon=True).start()

    def _get_start_command(self):
        java_path = "java"  # Using a simple default

        # --- Modern Forge Startup Logic (using @user_jvm_args.txt and @libraries/net/minecraftforge/.../win_args.txt) ---
        if self.server_type == 'forge':
            # Path to the user-configurable JVM arguments
            user_args_file = os.path.join(self.server_path, 'user_jvm_args.txt')
            # Find the main Forge arguments file, which is version-specific
            win_args_path_pattern = os.path.join(self.server_path, 'libraries', 'net', 'minecraftforge', 'forge', '*', 'win_args.txt')
            win_args_files = glob.glob(win_args_path_pattern)

            if os.path.exists(user_args_file) and win_args_files:
                self.output_callback("Detected modern Forge server. Using run.bat for startup.\n", "info")
                # For modern Forge on Windows, the run.bat is the most reliable way to handle the complex classpath and arguments.
                # We will call it directly but add --nogui to prevent it from opening its own window.
                run_script = os.path.join(self.server_path, 'run.bat')
                if os.path.exists(run_script):
                    # The batch script handles memory arguments via environment variables.
                    # We set them temporarily for the subprocess.
                    env = os.environ.copy()
                    env["JVM_ARGS"] = f"-Xms{self.ram_min}{self.ram_unit} -Xmx{self.ram_max}{self.ram_unit}"
                    return [run_script, '--nogui'], env

        # --- Generic startup for non-Forge or older Forge servers (fallback) ---
        self.output_callback("Using generic JAR startup method.\n", "info")
        all_jars = glob.glob(os.path.join(self.server_path, '*.jar'))
        server_jar_path = None
        
        non_installer_jars = [j for j in all_jars if 'installer' not in os.path.basename(j).lower()]
        
        if non_installer_jars:
            preferred_names = ['server.jar', 'minecraft_server.jar', 'paper.jar']
            for name in preferred_names:
                for jar in non_installer_jars:
                    if os.path.basename(jar).lower() == name:
                        server_jar_path = jar
                        break
                if server_jar_path:
                    break
            
            if not server_jar_path:
                server_jar_path = non_installer_jars[0]
        
        elif all_jars:
            server_jar_path = all_jars[0]

        if not server_jar_path:
            self.output_callback("No server .jar file found in the directory.\n", "error")
            return None, None

        min_ram_str = f"-Xms{self.ram_min}{self.ram_unit}"
        max_ram_str = f"-Xmx{self.ram_max}{self.ram_unit}"
        return [java_path, max_ram_str, min_ram_str, '-jar', os.path.basename(server_jar_path), '--nogui'], None

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
            if self.server_running:
                self.stop(silent=True)

    def _read_output(self, pipe, level):
        try:
            for line in iter(pipe.readline, ''):
                self.output_callback(line, level)
        finally:
            pipe.close()

    def stop(self, silent=False):
        if not self.server_running:
            return

        if self.server_process:
            self.output_callback("Attempting graceful stop...\n", "info")
            self.send_command("stop")
        
        self.server_running = False
        self.server_process = None
        if not silent:
            self.output_callback("Server has stopped.\n", "info")

    def send_command(self, cmd):
        if self.server_process and self.server_running:
            try:
                if self.server_process.stdin:
                    self.server_process.stdin.write(cmd + '\n')
                    self.server_process.stdin.flush()
                    self.output_callback(f"> {cmd}\n", "info")
                else:
                    self.output_callback("Cannot send command: server stdin is not available.\n", "error")
            except (IOError, ValueError) as e:
                self.output_callback(f"Failed to send command: {e}\n", "error")
        else:
            self.output_callback("Cannot send command: server is not running.\n", "warning")

    def is_running(self):
        return self.server_running and self.server_process and self.server_process.poll() is None

    def get_pid(self):
        if self.server_process:
            return self.server_process.pid
        return None
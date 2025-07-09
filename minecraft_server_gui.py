import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import psutil
import json
import shutil
import glob
import sys
import re
import uuid
import time
import threading
import subprocess
import webbrowser
from PIL import Image, ImageTk

from gui.widgets import CollapsiblePane
from utils.constants import *
from utils.helpers import format_size, get_folder_size, get_local_ip
from utils.api_client import fetch_player_avatar_image, fetch_player_uuid, download_server_jar, get_server_versions, fetch_username_from_uuid
from server.server_handler import ServerHandler
from server.config_manager import ConfigManager


# Attempt to hide the Python interpreter console window on Windows
if sys.platform == "win32":
    try:
        import ctypes
        console_window_handle = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window_handle != 0:
            ctypes.windll.user32.ShowWindow(console_window_handle, 0)
    except (ImportError, Exception):
        pass

# Matplotlib for resource graphs
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    matplotlib_available = True
except ImportError:
    matplotlib_available = False

class ServerControlGUI:
    def __init__(self, master):
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_dir = os.path.abspath(self.script_dir)

        self.config_manager = ConfigManager(os.path.join(self.script_dir, "gui_config.json"))
        self.changelog_path = os.path.join(self.script_dir, "changelog.txt")

        # --- TK Variables ---
        self.master = master
        self.ram_min_val_var = tk.StringVar(value=self.config_manager.get("ram_min", "1"))
        self.ram_max_val_var = tk.StringVar(value=self.config_manager.get("ram_max", "2"))
        self.ram_unit_var = tk.StringVar(value=self.config_manager.get("ram_unit", "G"))
        self.java_path_var = tk.StringVar(value=self.config_manager.get("java_path", "java"))

        master.title("Minecraft Server Control")
        try:
            logo_path = os.path.join(self.script_dir, "assets", "logo.png")
            pil_img = Image.open(logo_path)
            self.logo_image = ImageTk.PhotoImage(pil_img)
            master.iconphoto(True, self.logo_image)
        except Exception as e:
            print(f"Error setting window icon: {e}")
            pass
        
        self._load_config_or_run_setup()

    def on_close(self):
        if hasattr(self, 'server_handler') and (self.server_handler.is_running() or self.server_handler.is_starting()):
            dialog = ctk.CTkInputDialog(text="The server is running. Stop it and quit?", title="Confirm Quit")
            response = dialog.get_input()
            
            if response is not None:
                self.log_to_console("Stopping server before exiting...\n", "info")
                self.server_handler.stop()
                self._wait_for_server_to_stop_and_destroy()
        else:
            self.master.destroy()

    def _wait_for_server_to_stop_and_destroy(self):
        if hasattr(self, 'server_handler') and self.server_handler.server_process and self.server_handler.server_process.poll() is None:
            self.master.after(100, self._wait_for_server_to_stop_and_destroy)
        else:
            self.master.destroy()

    def _load_config_or_run_setup(self):
        server_path = self.config_manager.get("server_path")
        if server_path and os.path.isdir(server_path):
            self.server_path = server_path
            self.server_type = self.config_manager.get("server_type", "vanilla")
            self._initialize_main_gui()
        else:
            self._create_setup_wizard()

    def _initialize_paths(self):
        if not self.server_path: return
        self.server_properties_path = os.path.join(self.server_path, "server.properties")
        self.mods_dir_path = os.path.join(self.server_path, "mods")
        self.config_dir_path = os.path.join(self.server_path, "config")

    def _initialize_main_gui(self):
        try:
            self._initialize_paths()
            for widget in self.master.winfo_children():
                widget.destroy()

            self.server_handler = ServerHandler(
                self.server_path, 
                self.server_type, 
                self.ram_min_val_var.get(), 
                self.ram_max_val_var.get(), 
                self.ram_unit_var.get(), 
                self.log_to_console
            )

            # --- Initialize attributes ---
            self.players_connected = []
            self.selected_player_name = None
            self.ops_list = []
            self.expecting_player_list_next_line = False
            self.player_count_line_prefix = "There are "
            self.player_count_line_suffix = " players online:"
            self.property_widgets = {}
            self.active_view_id = None
            self.placeholder_avatar = self._create_placeholder_avatar(size=(24,24))
            self.avatar_cache = {}
            self.mod_data = []
            self.player_uuids = {}
            self.stats_files = {}
            self.current_mod_config_path = None
            self.selected_stats_player_uuid = None
            self.stats_player_widgets = {}
            self.current_player_stats = None
            self.stats_widgets_cache = {}
            self.uuid_to_name_cache = {}
            self._update_uuid_cache()

            # --- Build UI ---
            self._create_main_layout(self.master)
            self._show_view('control')
            self._update_server_status_display()
            self._update_dashboard_info()
            self.master.after(2000, self._update_resource_usage)

        except Exception as e:
            import traceback
            error_info = traceback.format_exc()
            messagebox.showerror("Fatal GUI Error", f"A critical error occurred while building the main interface:\n\n{e}\n\nDetails:\n{error_info}")

    def _update_uuid_cache(self):
        """Builds and updates a cache mapping UUIDs to usernames from all available local files."""
        
        # 1. usercache.json (Primary source)
        cache_file = os.path.join(self.server_path, 'usercache.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    user_cache_data = json.load(f)
                    for entry in user_cache_data:
                        if 'uuid' in entry and 'name' in entry:
                            self.uuid_to_name_cache[entry['uuid'].replace('-', '').lower()] = entry['name']
            except (json.JSONDecodeError, KeyError, TypeError):
                self.log_to_console("Warning: Could not parse usercache.json.\n", "warning")

        # 2. ops.json
        ops_file = os.path.join(self.server_path, 'ops.json')
        if os.path.exists(ops_file):
            try:
                with open(ops_file, 'r') as f:
                    ops_data = json.load(f)
                    for entry in ops_data:
                        if 'uuid' in entry and 'name' in entry:
                            uuid_clean = entry['uuid'].replace('-', '').lower()
                            if uuid_clean not in self.uuid_to_name_cache:
                                self.uuid_to_name_cache[uuid_clean] = entry['name']
            except (json.JSONDecodeError, KeyError, TypeError):
                self.log_to_console("Warning: Could not parse ops.json.\n", "warning")

        # 3. banned-players.json
        banned_file = os.path.join(self.server_path, 'banned-players.json')
        if os.path.exists(banned_file):
            try:
                with open(banned_file, 'r') as f:
                    banned_data = json.load(f)
                    for entry in banned_data:
                        if 'uuid' in entry and 'name' in entry:
                            uuid_clean = entry['uuid'].replace('-', '').lower()
                            if uuid_clean not in self.uuid_to_name_cache:
                                self.uuid_to_name_cache[uuid_clean] = entry['name']
            except (json.JSONDecodeError, KeyError, TypeError):
                self.log_to_console("Warning: Could not parse banned-players.json.\n", "warning")

    def _create_main_layout(self, parent_frame):
        parent_frame.grid_columnconfigure(1, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(parent_frame, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsw")
        self.sidebar_frame.grid_propagate(False)
        
        logo_font = ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        sidebar_title_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        sidebar_title_frame.pack(pady=20, padx=20)
        
        try:
            logo_path = os.path.join(self.script_dir, "assets", "logo.png")
            logo_img = ctk.CTkImage(Image.open(logo_path), size=(32, 32))
            ctk.CTkLabel(sidebar_title_frame, image=logo_img, text="").pack(side=tk.LEFT, padx=(0, 10))
        except Exception as e:
            print(f"Error loading sidebar logo: {e}")

        ctk.CTkLabel(sidebar_title_frame, text="MC Server GUI", font=logo_font, anchor="w").pack(side=tk.LEFT)

        # --- Top Bar ---
        self.top_bar_frame = ctk.CTkFrame(parent_frame, height=70, corner_radius=0, fg_color="transparent")
        self.top_bar_frame.grid(row=0, column=1, sticky="new")
        self.top_bar_frame.grid_columnconfigure(0, weight=1)

        self.server_title_label = ctk.CTkLabel(self.top_bar_frame, text="Minecraft Server Dashboard", font=ctk.CTkFont(size=24, weight="bold"))
        self.server_title_label.grid(row=0, column=0, sticky='w', padx=20, pady=10)

        top_bar_actions_frame = ctk.CTkFrame(self.top_bar_frame, fg_color="transparent")
        top_bar_actions_frame.grid(row=0, column=1, sticky='e', padx=20)

        self.server_status_label = ctk.CTkLabel(top_bar_actions_frame, text="Status: Offline", font=ctk.CTkFont(weight="bold"))
        self.server_status_label.pack(side=tk.LEFT, padx=(0,15))
        
        self.restart_button = ctk.CTkButton(top_bar_actions_frame, text="Restart Server", command=self.restart_server, state=tk.DISABLED)
        self.restart_button.pack(side=tk.LEFT)

        # --- Content Area ---
        self.content_area_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        self.content_area_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        self.view_frames = {}
        self.views_config = [
            {'id': 'control', 'text': '🖥️  Dashboard', 'create_method': self._create_control_view_widgets},
            {'id': 'console', 'text': '⌨️  Console', 'create_method': self._create_console_view_widgets},
            {'id': 'properties', 'text': '⚙️  Properties', 'create_method': self._create_properties_view_widgets},
            {'id': 'resources', 'text': '📈 Resources', 'create_method': self._create_resources_view_widgets},
            {'id': 'players', 'text': '👥 Players', 'create_method': self._create_players_view_widgets},
            {'id': 'ops', 'text': '⭐ Operators', 'create_method': self._create_ops_view_widgets},
            {'id': 'worlds', 'text': '🌍 Worlds', 'create_method': self._create_worlds_view_widgets},
            {'id': 'stats', 'text': '📊 Statistics', 'create_method': self._create_stats_view_widgets},
            {'id': 'bans', 'text': '🚫 Bans', 'create_method': self._create_bans_view_widgets},
            {'id': 'mods', 'text': '🧩 Mods', 'create_method': self._create_mods_view_widgets},
            {'id': 'app_settings', 'text': '🛠️ Settings', 'create_method': self._create_app_settings_view_widgets},
        ]

        self.sidebar_buttons = {}
        for view_info in self.views_config:
            frame = ctk.CTkFrame(self.content_area_frame, fg_color="transparent")
            self.view_frames[view_info['id']] = frame
            view_info['create_method'](frame)
            btn = ctk.CTkButton(self.sidebar_frame, text=view_info['text'], 
                                command=lambda v_id=view_info['id']: self._show_view(v_id),
                                anchor="w", corner_radius=0, fg_color="transparent",
                                font=ctk.CTkFont(size=14))
            btn.pack(fill=tk.X, padx=10, pady=5, ipady=5)
            self.sidebar_buttons[view_info['id']] = btn

    def _create_setup_wizard(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        
        setup_frame = ctk.CTkFrame(self.master, fg_color="transparent")
        setup_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        ctk.CTkLabel(setup_frame, text="Minecraft Server Setup", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(10, 20))

        self.setup_mode = tk.StringVar(value="install")
        
        mode_frame = ctk.CTkFrame(setup_frame, fg_color="transparent")
        mode_frame.pack(pady=10, fill=tk.X)
        ctk.CTkRadioButton(mode_frame, text="Install New Server", variable=self.setup_mode, value="install", command=self._toggle_setup_view).pack(side=tk.LEFT, padx=10)
        ctk.CTkRadioButton(mode_frame, text="Use Existing Server", variable=self.setup_mode, value="existing", command=self._toggle_setup_view).pack(side=tk.LEFT, padx=10)

        self.install_frame = ctk.CTkFrame(setup_frame, fg_color="transparent")
        self.install_frame.pack(fill=tk.X, expand=True, pady=5)
        self.existing_frame = ctk.CTkFrame(setup_frame, fg_color="transparent")

        # --- Widgets for "Install New Server" ---
        ctk.CTkLabel(self.install_frame, text="1. Select Server Type", font=ctk.CTkFont(weight="bold")).pack(anchor='w', pady=(10,5))
        server_types = ["Vanilla", "Paper", "Spigot", "Forge", "Fabric"]
        self.server_type_var = tk.StringVar(value=server_types[0])
        ctk.CTkComboBox(self.install_frame, variable=self.server_type_var, values=server_types, command=self._update_server_versions).pack(fill=tk.X, pady=5)
        
        ctk.CTkLabel(self.install_frame, text="2. Select Minecraft Version", font=ctk.CTkFont(weight="bold")).pack(anchor='w', pady=(10,5))
        self.server_version_var = tk.StringVar()
        self.version_menu = ctk.CTkComboBox(self.install_frame, variable=self.server_version_var, values=["Loading..."], state="disabled")
        self.version_menu.pack(fill=tk.X, pady=5)
        
        ctk.CTkLabel(self.install_frame, text="3. Choose Parent Directory", font=ctk.CTkFont(weight="bold")).pack(anchor='w', pady=(10,5))
        install_location_frame = ctk.CTkFrame(self.install_frame, fg_color="transparent")
        install_location_frame.pack(fill=tk.X, pady=5)
        self.install_location_var = tk.StringVar()
        ctk.CTkEntry(install_location_frame, textvariable=self.install_location_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(install_location_frame, text="Browse...", command=self._browse_install_location, width=80).pack(side=tk.LEFT, padx=(5,0))
        
        ctk.CTkLabel(self.install_frame, text="4. Name Server Folder", font=ctk.CTkFont(weight="bold")).pack(anchor='w', pady=(10,5))
        self.server_name_var = tk.StringVar()
        self.server_name_entry = ctk.CTkEntry(self.install_frame, textvariable=self.server_name_var)
        self.server_name_entry.pack(fill=tk.X, pady=5)
        
        self.eula_accepted_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.install_frame, text="I agree to the Minecraft EULA (minecraft.net/eula)", variable=self.eula_accepted_var).pack(fill=tk.X, pady=10)
        
        self.server_version_var.trace_add('write', self._update_default_folder_name)
        
        # --- Widgets for "Use Existing Server" ---
        ctk.CTkLabel(self.existing_frame, text="1. Choose Existing Server Location", font=ctk.CTkFont(weight="bold")).pack(anchor='w', pady=(10,5))
        existing_location_frame = ctk.CTkFrame(self.existing_frame, fg_color="transparent")
        existing_location_frame.pack(fill=tk.X, pady=5)
        self.existing_location_var = tk.StringVar()
        ctk.CTkEntry(existing_location_frame, textvariable=self.existing_location_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(existing_location_frame, text="Browse...", command=self._browse_existing_location, width=80).pack(side=tk.LEFT, padx=(5,0))

        # --- Action Button & Progress ---
        self.action_button = ctk.CTkButton(setup_frame, text="Download and Install Server", command=self._start_setup_action)
        self.action_button.pack(pady=(30, 10), ipady=10, fill=tk.X)
        self.progress_bar = ctk.CTkProgressBar(setup_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.status_label = ctk.CTkLabel(setup_frame, text="Ready to begin.")
        self.status_label.pack(pady=10)

        self._toggle_setup_view()
        self._update_server_versions()

    def _update_server_versions(self, *args):
        server_type = self.server_type_var.get()
        self.server_version_var.set("Loading...")
        self.version_menu.configure(state=tk.DISABLED)
        threading.Thread(target=self._fetch_and_update_versions, args=(server_type,), daemon=True).start()

    def _fetch_and_update_versions(self, server_type):
        versions_data = get_server_versions(server_type)
        versions = [v['version'] for v in versions_data] if versions_data else []
        
        def update_ui():
            if versions:
                self.version_menu.configure(values=versions, state="normal")
                self.server_version_var.set(versions[0])
            else:
                self.server_version_var.set("Error fetching versions")
        
        if hasattr(self, 'master'):
            self.master.after(0, update_ui)

    def _toggle_setup_view(self):
        mode = self.setup_mode.get()
        if mode == "install":
            self.existing_frame.pack_forget()
            self.install_frame.pack(fill=tk.X, expand=True, pady=5)
            self.action_button.configure(text="Download and Install Server")
            self.status_label.configure(text="Ready to begin installation.")
        else:
            self.install_frame.pack_forget()
            self.existing_frame.pack(fill=tk.X, expand=True, pady=5)
            self.action_button.configure(text="Use This Folder")
            self.status_label.configure(text="Select an existing server folder.")
            
    def _update_default_folder_name(self, *args):
        try:
            if hasattr(self, 'server_name_entry') and self.server_name_entry.winfo_exists():
                server_type = self.server_type_var.get()
                version = self.server_version_var.get()
                if version != "Loading...":
                    self.server_name_var.set(f"{server_type.lower()}-server-{version}")
        except tk.TclError:
            pass

    def _browse_install_location(self):
        directory = filedialog.askdirectory(initialdir=os.path.expanduser("~/Documents"), title="Select a parent folder for the new server")
        if directory:
            self.install_location_var.set(directory)

    def _browse_existing_location(self):
        directory = filedialog.askdirectory(initialdir=os.path.expanduser("~/Documents"), title="Select an existing server folder")
        if directory:
            self.existing_location_var.set(directory)

    def _start_setup_action(self):
        self.action_button.configure(state=tk.DISABLED)
        mode = self.setup_mode.get()
        if mode == "install":
            if not self.install_location_var.get() or not self.server_name_var.get():
                messagebox.showerror("Error", "Please select a parent directory and provide a folder name.")
                self.action_button.configure(state=tk.NORMAL)
                return
            if not self.eula_accepted_var.get():
                messagebox.showerror("EULA Required", "You must agree to the Minecraft EULA to install a new server.")
                self.action_button.configure(state=tk.NORMAL)
                return
            threading.Thread(target=self._perform_server_installation, daemon=True).start()
        else:
            threading.Thread(target=self._use_existing_server, daemon=True).start()

    def _use_existing_server(self):
        try:
            server_path = self.existing_location_var.get()
            if not server_path:
                messagebox.showerror("Error", "Please select an existing server directory.")
                return

            jar_files = glob.glob(os.path.join(server_path, '*.jar'))
            properties_file = os.path.join(server_path, 'server.properties')
            run_script = os.path.join(server_path, 'run.bat') if sys.platform == "win32" else os.path.join(server_path, 'run.sh')

            # A valid server must have server.properties and either a .jar file or a run script.
            if not os.path.exists(properties_file) or (not jar_files and not os.path.exists(run_script)):
                messagebox.showerror("Invalid Folder", "The selected folder does not appear to be a valid Minecraft server. (Missing server.properties and a .jar file or run script)")
                return

            self.master.after(0, self.status_label.configure, {'text': "Configuration saved! Launching..."})
            self.server_path = server_path
            self.server_type = self._detect_server_type(server_path)
            
            # Detect and store the server version
            detected_version = self._detect_server_version(server_path)
            self.server_version_var = tk.StringVar(value=detected_version)
            
            self._save_config()
            time.sleep(1)
            self.master.after(0, self._initialize_main_gui)

        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        finally:
            if hasattr(self, 'action_button') and self.action_button.winfo_exists():
                self.master.after(0, self.action_button.configure, {'state': tk.NORMAL})

    def _detect_server_type(self, server_path):
        try:
            jars = os.listdir(server_path)
            for jar in jars:
                jar_lower = jar.lower()
                if "forge" in jar_lower: return "forge"
                if "fabric" in jar_lower: return "fabric"
                if "spigot" in jar_lower: return "spigot"
                if "paper" in jar_lower: return "paper"
        except FileNotFoundError:
            return "vanilla"
        return "vanilla"

    def _detect_server_version(self, server_path):
        try:
            jars = glob.glob(os.path.join(server_path, '*.jar'))
            if not jars:
                return "Unknown"
            
            # Prioritize server.jar if it exists, otherwise take the first jar found.
            server_jar = next((j for j in jars if os.path.basename(j).lower() == 'server.jar'), jars[0])
            jar_name = os.path.basename(server_jar)
            
            # Regex to find version numbers like 1.19.2, 1.18, etc.
            match = re.search(r'(\d+\.\d+(\.\d+)?)', jar_name)
            if match:
                return match.group(1)
            
            return "Unknown"
        except Exception:
            return "Unknown"

    def _perform_server_installation(self):
        try:
            server_type = self.server_type_var.get().lower()
            server_version = self.server_version_var.get()
            parent_dir = self.install_location_var.get()
            server_folder_name = self.server_name_var.get()
            
            install_path = os.path.join(parent_dir, server_folder_name)
            jar_name = "server.jar"
            jar_path = os.path.join(install_path, jar_name)

            if os.path.exists(install_path) and os.listdir(install_path):
                dialog = ctk.CTkInputDialog(text="Destination folder is not empty. Overwrite?", title="Warning")
                if dialog.get_input() is None:
                    raise Exception("Installation cancelled by user.")

            self.master.after(0, self.status_label.configure, {'text': f"Creating directory: {os.path.basename(install_path)}"})
            os.makedirs(install_path, exist_ok=True)
            
            self.master.after(0, self.status_label.configure, {'text': f"Downloading {server_type} {server_version}..."})
            download_server_jar(server_type, server_version, jar_path, lambda p: self.master.after(0, self.progress_bar.set, p / 100))
            
            self.master.after(0, self.status_label.configure, {'text': "Generating server files..."})
            self.master.after(0, self.progress_bar.set, 0)
            
            initial_run_command = ['java', '-jar', jar_name]
            if server_type == 'forge':
                initial_run_command.append('--installServer')
            else:
                initial_run_command.append('--nogui')

            process = subprocess.Popen(initial_run_command, cwd=install_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            try:
                stdout, stderr = process.communicate(timeout=600)
                if server_type == 'forge':
                    run_script_path = os.path.join(install_path, 'run.bat') if sys.platform == "win32" else os.path.join(install_path, 'run.sh')
                    if not os.path.exists(run_script_path):
                         if process.returncode != 0:
                             raise RuntimeError(f"Forge installer failed with exit code {process.returncode}.\n\nLOG:\n{stdout}\n{stderr}")
                         else:
                             raise RuntimeError(f"Forge installer finished but the run script was not created.\n\nLOG:\n{stdout}\n{stderr}")
                else:
                    if process.returncode != 0 and 'eula' not in (stdout + stderr).lower():
                        raise RuntimeError(f"Server process failed. Log:\n{stderr or stdout}")

            except subprocess.TimeoutExpired:
                process.kill()
                run_script_path = os.path.join(install_path, 'run.bat') if sys.platform == "win32" else os.path.join(install_path, 'run.sh')
                if server_type == 'forge' and os.path.exists(run_script_path):
                    self.log_to_console("Forge installer timed out but seems to have succeeded. Continuing...\n", "warning")
                else:
                    raise RuntimeError("Server setup timed out (10+ min).")

            if server_type != 'forge':
                eula_path = os.path.join(install_path, "eula.txt")
                self.master.after(0, self.status_label.configure, {'text': "Accepting EULA..."})
                time.sleep(1)
                if not os.path.exists(eula_path):
                    self.log_to_console("eula.txt was not created. It will need to be accepted on the first server launch.\n", "warning")
                else:
                    with open(eula_path, 'r+') as f:
                        content = f.read().replace("eula=false", "eula=true")
                        f.seek(0); f.write(content); f.truncate()
            
            self.master.after(0, self.status_label.configure, {'text': "Setup complete! Launching..."})
            self.server_path = install_path
            self.server_type = server_type
            self._save_config()
            time.sleep(1)
            self.master.after(0, self._initialize_main_gui)

        except Exception as e:
            messagebox.showerror("Installation Failed", str(e))
            self.master.after(0, self.status_label.configure, {'text': "Error during installation."})
        finally:
            self.master.after(0, self.action_button.configure, {'state': tk.NORMAL})
            
    def _save_config(self):
        self.config_manager.set("server_path", self.server_path)
        self.config_manager.set("server_type", self.server_type)
        # Ensure server_version_var exists and has a value to save
        if hasattr(self, 'server_version_var') and self.server_version_var.get():
            self.config_manager.set("server_version", self.server_version_var.get())
        self.config_manager.set("ram_min", self.ram_min_val_var.get())
        self.config_manager.set("ram_max", self.ram_max_val_var.get())
        self.config_manager.set("ram_unit", self.ram_unit_var.get())
        self.config_manager.set("java_path", self.java_path_var.get())
        self.config_manager.save()

    def _load_data_for_view(self, view_id):
        if view_id == 'properties': self.load_server_properties()
        elif view_id == 'players': self.update_players_list()
        elif view_id == 'ops': self.update_ops_list()
        elif view_id == 'bans': self._load_bans()
        elif view_id == 'worlds': self._refresh_worlds_visual()
        elif view_id == 'stats': self.update_stats_list()
        elif view_id == 'mods': self._load_mods_list()
        elif view_id == 'app_settings': self._load_changelog()

    def _show_view(self, view_id_to_show):
        if self.active_view_id == view_id_to_show:
            return

        # Update button styles
        if self.active_view_id:
            self.sidebar_buttons[self.active_view_id].configure(fg_color="transparent")
        self.sidebar_buttons[view_id_to_show].configure(fg_color="gray20")

        # Hide old frame, show new one
        if self.active_view_id:
            self.view_frames[self.active_view_id].pack_forget()
        
        self.active_view_id = view_id_to_show
        new_frame = self.view_frames[view_id_to_show]
        new_frame.pack(fill=tk.BOTH, expand=True)
        
        self._load_data_for_view(view_id_to_show)

    def _create_control_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)

        top_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 10))
        top_frame.grid_columnconfigure((0, 1), weight=1)

        # --- Left Panel for Server Actions & Memory ---
        left_panel = ctk.CTkFrame(top_frame)
        left_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        left_panel.grid_columnconfigure(0, weight=1)

        actions_frame = ctk.CTkFrame(left_panel)
        actions_frame.grid(row=0, column=0, sticky='ew', padx=15, pady=(0, 10))
        ctk.CTkLabel(actions_frame, text="Server Actions", font=ctk.CTkFont(weight="bold")).pack(anchor='w', pady=(10,5))
        self.start_button = ctk.CTkButton(actions_frame, text="Start Server", command=self.start_server_thread)
        self.start_button.pack(fill=tk.X, pady=5, ipady=8)
        self.stop_button = ctk.CTkButton(actions_frame, text="Stop Server", command=self.stop_server, state=tk.DISABLED)
        self.stop_button.pack(fill=tk.X, pady=5, ipady=8)

        memory_frame = ctk.CTkFrame(left_panel)
        memory_frame.grid(row=1, column=0, sticky='ew', padx=15, pady=10)
        memory_frame.grid_columnconfigure(0, weight=1)
        
        mem_title_frame = ctk.CTkFrame(memory_frame, fg_color="transparent")
        mem_title_frame.grid(row=0, column=0, sticky='ew', pady=(0,5))
        ctk.CTkLabel(mem_title_frame, text="Memory Allocation", font=ctk.CTkFont(weight="bold")).pack(side=tk.LEFT)
        self.ram_slider_label = ctk.CTkLabel(mem_title_frame, text=f"{self.ram_max_val_var.get()} GB")
        self.ram_slider_label.pack(side=tk.RIGHT)

        self.ram_slider = ctk.CTkSlider(memory_frame, from_=1, to=16, number_of_steps=15, command=self._on_ram_slider_change)
        self.ram_slider.set(float(self.ram_max_val_var.get()))
        self.ram_slider.grid(row=1, column=0, sticky='ew')

        # --- Right Panel for Server Info ---
        right_panel = ctk.CTkFrame(top_frame)
        right_panel.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        ctk.CTkLabel(right_panel, text="Server Info", font=ctk.CTkFont(weight="bold")).pack(anchor='w', pady=10, padx=15)
        
        info_grid = ctk.CTkFrame(right_panel, fg_color="transparent")
        info_grid.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0,15))
        info_grid.grid_columnconfigure(1, weight=1)

        def add_info_row(label_text, var_text):
            row_idx = info_grid.grid_size()[1]
            ctk.CTkLabel(info_grid, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, sticky='w', padx=(0,10))
            label = ctk.CTkLabel(info_grid, text=var_text, anchor='w')
            label.grid(row=row_idx, column=1, sticky='ew')
            return label

        self.motd_label = add_info_row("MOTD:", "N/A")
        self.version_label = add_info_row("Version:", "N/A")
        self.players_label = add_info_row("Players:", "N/A")
        
        row_idx = info_grid.grid_size()[1]
        ctk.CTkLabel(info_grid, text="Server IP:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, sticky='w', padx=(0,10), pady=(5,0))
        ip_frame = ctk.CTkFrame(info_grid, fg_color="transparent")
        ip_frame.grid(row=row_idx, column=1, sticky='ew', pady=(5,0))
        self.ip_label = ctk.CTkLabel(ip_frame, text="N/A")
        self.ip_label.pack(side=tk.LEFT, anchor='w')
        self.copy_ip_button = ctk.CTkButton(ip_frame, text="Copy", width=60, command=self._copy_ip_to_clipboard)
        self.copy_ip_button.pack(side=tk.LEFT, padx=5)

        # --- Bottom Panel for Console ---
        console_card = ctk.CTkFrame(parent_frame)
        console_card.grid(row=1, column=0, sticky='nsew')
        console_card.grid_rowconfigure(1, weight=1)
        console_card.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(console_card, text="Live Console", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=15, pady=(10,5))
        self.dashboard_console_output_area = ctk.CTkTextbox(console_card, wrap=tk.WORD, font=ctk.CTkFont(family="monospace"))
        self.dashboard_console_output_area.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0,10))
        self.dashboard_console_output_area.tag_config("error", foreground="red")
        self.dashboard_console_output_area.tag_config("warning", foreground="yellow")
        self.dashboard_console_output_area.tag_config("info", foreground="gray")
        self.dashboard_console_output_area.tag_config("success", foreground="green")

        command_frame = ctk.CTkFrame(console_card, fg_color="transparent")
        command_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(0,10))
        command_frame.grid_columnconfigure(0, weight=1)
        self.console_command_entry = ctk.CTkEntry(command_frame)
        self.console_command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.console_command_entry.bind("<Return>", self.send_command_from_console_entry)
        self.console_send_btn = ctk.CTkButton(command_frame, text="Send", width=70, command=self.send_command_from_console_button)
        self.console_send_btn.grid(row=0, column=1)

    def _on_ram_slider_change(self, value):
        # Update the label as the slider moves
        max_ram = int(value)
        self.ram_slider_label.configure(text=f"{max_ram} GB")
        
        # Set the tk variables
        self.ram_max_val_var.set(str(max_ram))
        self.ram_min_val_var.set("1") # Keep min RAM at 1GB for simplicity
        self.ram_unit_var.set("G")
        
        # Save the configuration automatically
        self._save_config()
        # Also update the server handler instance if it exists
        if hasattr(self, 'server_handler'):
            self.server_handler.update_ram(str(max_ram), "1", "G")

    def _copy_ip_to_clipboard(self):
        ip = self.ip_label.cget("text")
        if ip and ip != "N/A":
            self.master.clipboard_clear()
            self.master.clipboard_append(ip)
            self.log_to_console(f"Copied '{ip}' to clipboard.\n", "success")

    def _update_dashboard_info(self):
        if not self.server_path: return
        properties = {}
        if os.path.exists(self.server_properties_path):
            with open(self.server_properties_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        properties[key.strip()] = value.strip()

        motd = properties.get("motd", "A Minecraft Server")
        max_players = properties.get("max-players", "20")
        
        server_type_str = self.config_manager.get('server_type', 'N/A').capitalize()
        server_version_str = self.config_manager.get('server_version', 'N/A')
        
        self.motd_label.configure(text=motd)
        self.version_label.configure(text=f"{server_type_str} {server_version_str}")
        self.players_label.configure(text=f"{len(self.players_connected)}/{max_players}")
        self.ip_label.configure(text=get_local_ip())

    def _create_console_view_widgets(self, parent_frame):
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        
        console_card = ctk.CTkFrame(parent_frame)
        console_card.grid(row=0, column=0, sticky='nsew')
        console_card.grid_rowconfigure(1, weight=1)
        console_card.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(console_card, text="Full Server Console", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=15, pady=(10,5))
        self.full_console_output_area = ctk.CTkTextbox(console_card, wrap=tk.WORD, font=ctk.CTkFont(family="monospace"))
        self.full_console_output_area.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0,10))
        self.full_console_output_area.tag_config("error", foreground="red")
        self.full_console_output_area.tag_config("warning", foreground="yellow")
        self.full_console_output_area.tag_config("info", foreground="gray")
        self.full_console_output_area.tag_config("success", foreground="green")

        command_frame = ctk.CTkFrame(console_card, fg_color="transparent")
        command_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(0,10))
        command_frame.grid_columnconfigure(0, weight=1)
        self.command_entry = ctk.CTkEntry(command_frame)
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.command_entry.bind("<Return>", self.send_command_from_entry)
        self.send_btn = ctk.CTkButton(command_frame, text="Send", width=70, command=self.send_command_from_button)
        self.send_btn.grid(row=0, column=1)

    def _create_properties_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)

        top_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(top_frame, text="Server Properties", font=ctk.CTkFont(size=18, weight="bold")).pack(side=tk.LEFT)
        self.save_properties_button = ctk.CTkButton(top_frame, text="Save Changes", command=self.save_server_properties, state=tk.DISABLED)
        self.save_properties_button.pack(side=tk.RIGHT)
        
        self.properties_scrollable_frame = ctk.CTkScrollableFrame(parent_frame)
        self.properties_scrollable_frame.grid(row=1, column=0, sticky="nsew")
        
        self._define_all_properties()

        self.property_widgets = {}
        for category, properties in self.properties_definitions.items():
            pane = CollapsiblePane(self.properties_scrollable_frame, text=category)
            pane.pack(fill='x', pady=5, padx=2)
            
            for prop_def in properties:
                self._add_property_control(pane.body, prop_def)

    def _add_property_control(self, parent, prop_def):
        key = prop_def['key']
        var = None
        
        prop_frame = ctk.CTkFrame(parent, fg_color="transparent")
        prop_frame.pack(fill=tk.X, pady=8)
        prop_frame.grid_columnconfigure(0, weight=1, minsize=200)
        prop_frame.grid_columnconfigure(1, weight=2)
        
        info_frame = ctk.CTkFrame(prop_frame, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky='w', padx=(0, 10))
        ctk.CTkLabel(info_frame, text=key, font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        ctk.CTkLabel(info_frame, text=prop_def.get('desc', ''), wraplength=250, justify=tk.LEFT, text_color="gray").pack(anchor='w')

        widget_frame = ctk.CTkFrame(prop_frame, fg_color="transparent")
        widget_frame.grid(row=0, column=1, sticky='e')

        prop_type = prop_def.get('type', 'string')

        if prop_type == 'boolean':
            var = tk.BooleanVar(value=prop_def.get('default'))
            widget = ctk.CTkSwitch(widget_frame, text="", variable=var)
            widget.pack(anchor='w')
        elif prop_type == 'enum':
            var = tk.StringVar(value=str(prop_def.get('default')))
            widget = ctk.CTkComboBox(widget_frame, variable=var, values=prop_def.get('values', []))
            widget.pack(fill=tk.X, expand=True)
        else:
            var = tk.StringVar(value=str(prop_def.get('default')))
            widget = ctk.CTkEntry(widget_frame, textvariable=var)
            widget.pack(fill=tk.X, expand=True)

        var.trace_add("write", self._on_property_change)
        self.property_widgets[key] = var
            
    def load_server_properties(self):
        current_properties = {}
        if os.path.exists(self.server_properties_path):
            try:
                with open(self.server_properties_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            current_properties[key.strip()] = value.strip()
            except Exception as e:
                self.log_to_console(f"Error reading server.properties: {e}\n", "error")
        
        for category, properties in self.properties_definitions.items():
            for prop_def in properties:
                key = prop_def['key']
                var = self.property_widgets.get(key)
                if var:
                    file_value = current_properties.get(key)
                    if file_value is not None:
                        if isinstance(var, tk.BooleanVar):
                            var.set(file_value.lower() == 'true')
                        else:
                            var.set(file_value)
                    else:
                        if isinstance(var, tk.BooleanVar):
                            var.set(prop_def.get('default', False))
                        else:
                            var.set(prop_def.get('default', ''))
        
        self.master.after(100, lambda: self.save_properties_button.configure(state='disabled'))

    def _on_property_change(self, *args):
        if hasattr(self, 'save_properties_button'):
            self.save_properties_button.configure(state='normal')

    def save_server_properties(self):
        try:
            content_lines = [
                f"# Minecraft server properties, managed by ServerControlGUI",
                f"# Last saved: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                ""
            ]
            for category, properties in self.properties_definitions.items():
                content_lines.append(f"# ---- {category} ----")
                for prop_def in properties:
                    key = prop_def['key']
                    var = self.property_widgets.get(key)
                    if var:
                        value = var.get()
                        if isinstance(value, bool): value = str(value).lower()
                        content_lines.append(f"{key}={value}")
                content_lines.append("")

            with open(self.server_properties_path, 'w') as f:
                f.write("\n".join(content_lines))

            messagebox.showinfo("Success", "server.properties saved successfully.")
            self.save_properties_button.configure(state='disabled')
            self.log_to_console("server.properties saved. A server restart is required for changes to take effect.\n", "warning")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save server.properties: {e}")

    def _define_all_properties(self):
        self.properties_definitions = {
            "General": [
                {"key": "motd", "type": "string", "default": "A Minecraft Server", "desc": "The message displayed in the server list."},
                {"key": "gamemode", "type": "enum", "values": ["survival", "creative", "adventure", "spectator"], "default": "survival", "desc": "Default game mode for new players."},
                {"key": "difficulty", "type": "enum", "values": ["peaceful", "easy", "normal", "hard"], "default": "easy", "desc": "Game difficulty."},
                {"key": "hardcore", "type": "boolean", "default": False, "desc": "If true, players are banned on death."},
                {"key": "pvp", "type": "boolean", "default": True, "desc": "Enable Player vs Player combat."},
                {"key": "force-gamemode", "type": "boolean", "default": False, "desc": "Force players to join in the default gamemode."}
            ],
            "World": [
                {"key": "level-name", "type": "string", "default": "world", "desc": "Name of the world folder."},
                {"key": "level-seed", "type": "string", "default": "", "desc": "Seed for generating a new world."},
                {"key": "level-type", "type": "enum", "values": ["minecraft:normal", "minecraft:flat", "minecraft:large_biomes", "minecraft:amplified", "minecraft:single_biome_surface"], "default": "minecraft:normal", "desc": "Type of world to generate."},
                {"key": "generate-structures", "type": "boolean", "default": True, "desc": "Enable generation of structures like villages."},
                {"key": "allow-nether", "type": "boolean", "default": True, "desc": "Allow players to travel to the Nether."},
                {"key": "max-world-size", "type": "integer", "default": 29999984, "desc": "Maximum radius of the world border."}
            ],
            "Spawning": [
                {"key": "spawn-animals", "type": "boolean", "default": True, "desc": "Allow friendly animal spawning."},
                {"key": "spawn-monsters", "type": "boolean", "default": True, "desc": "Allow hostile monster spawning."},
                {"key": "spawn-npcs", "type": "boolean", "default": True, "desc": "Allow villager spawning in villages."},
                {"key": "spawn-protection", "type": "integer", "default": 16, "desc": "Radius of spawn protection for non-ops."}
            ],
            "Players & Network": [
                {"key": "max-players", "type": "integer", "default": 20, "desc": "Maximum number of players allowed."},
                {"key": "online-mode", "type": "boolean", "default": True, "desc": "Verify players with Mojang servers. Set to false for offline/cracked servers."},
                {"key": "white-list", "type": "boolean", "default": False, "desc": "Enable the server whitelist."},
                {"key": "view-distance", "type": "integer", "default": 10, "desc": "Server-side render distance in chunks."},
                {"key": "network-compression-threshold", "type": "integer", "default": 256, "desc": "Packet compression level. -1 to disable."}
            ],
            "Advanced": [
                {"key": "allow-flight", "type": "boolean", "default": False, "desc": "Allow flight, e.g., in Survival with mods."},
                {"key": "enable-command-block", "type": "boolean", "default": False, "desc": "Enable command blocks."},
                {"key": "function-permission-level", "type": "integer", "default": 2, "desc": "Permission level for functions (1-4)."},
                {"key": "op-permission-level", "type": "integer", "default": 4, "desc": "Default permission level for ops (1-4)."},
                {"key": "sync-chunk-writes", "type": "boolean", "default": True, "desc": "Enables synchronous chunk writes."}
            ]
        }

    def _create_resources_view_widgets(self, parent_frame):
        if not matplotlib_available:
            ctk.CTkLabel(parent_frame, text="Matplotlib is not installed.\nResource graphs are unavailable.").pack(pady=20)
            return
            
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(0, weight=1)
        
        fig = Figure(figsize=(5, 2), dpi=100, facecolor="#2b2b2b")
        self.ax_cpu = fig.add_subplot(121)
        self.ax_ram = fig.add_subplot(122)

        for ax, title in [(self.ax_cpu, 'CPU Usage (%)'), (self.ax_ram, 'RAM Usage (%)')]:
            ax.set_facecolor("#2b2b2b")
            ax.set_title(title, color="white")
            ax.tick_params(axis='y', colors="gray")
            ax.tick_params(axis='x', colors="#2b2b2b") 
            for spine in ax.spines.values(): spine.set_color("gray")
            ax.set_ylim(0, 100)

        self.cpu_history = [0.0] * 50
        self.ram_history = [0.0] * 50
        self.line_cpu, = self.ax_cpu.plot(self.cpu_history, color="#1f6aa5", lw=2)
        self.line_ram, = self.ax_ram.plot(self.ram_history, color="#2fa572", lw=2)

        fig.tight_layout(pad=2.0)
        self.resource_canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        self.resource_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.resource_canvas.draw()
        
        info_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        self.ram_label = ctk.CTkLabel(info_frame, text="RAM: N/A")
        self.ram_label.pack(side=tk.LEFT, expand=True)
        self.cpu_percent_label = ctk.CTkLabel(info_frame, text="CPU: N/A")
        self.cpu_percent_label.pack(side=tk.LEFT, expand=True)

    def _update_resource_usage(self):
        if not hasattr(self, 'server_handler') or not self.server_handler.is_running():
            if matplotlib_available and hasattr(self, 'line_cpu'):
                self.cpu_history = [0.0] * 50
                self.ram_history = [0.0] * 50
                self.line_cpu.set_ydata(self.cpu_history)
                self.line_ram.set_ydata(self.ram_history)
                if self.resource_canvas.get_tk_widget().winfo_exists(): self.resource_canvas.draw()
                if self.cpu_percent_label.winfo_exists(): self.cpu_percent_label.configure(text="CPU: 0.0%")
                if self.ram_label.winfo_exists(): self.ram_label.configure(text="RAM: 0MB (0.0%)")
            self.master.after(2000, self._update_resource_usage)
            return

        try:
            pid = self.server_handler.get_pid()
            if pid is None: return
            proc = psutil.Process(pid)
            cpu_percent = proc.cpu_percent(interval=None) / (psutil.cpu_count() or 1)
            self.cpu_history.pop(0)
            self.cpu_history.append(float(cpu_percent))
            
            mem_info = proc.memory_info()
            ram_percent = (mem_info.rss / psutil.virtual_memory().total) * 100
            self.ram_history.pop(0)
            self.ram_history.append(ram_percent)

            if matplotlib_available and self.resource_canvas.get_tk_widget().winfo_exists():
                self.line_cpu.set_ydata(self.cpu_history)
                self.line_ram.set_ydata(self.ram_history)
                self.resource_canvas.draw()
                self.cpu_percent_label.configure(text=f"CPU: {cpu_percent:.1f}%")
                self.ram_label.configure(text=f"RAM: {mem_info.rss / (1024**2):.0f}MB ({ram_percent:.1f}%)")

        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        finally:
            self.master.after(2000, self._update_resource_usage)

    def log_to_console(self, msg, level="info"):
        text_boxes = []
        if hasattr(self, 'full_console_output_area') and self.full_console_output_area.winfo_exists():
            text_boxes.append(self.full_console_output_area)
        if hasattr(self, 'dashboard_console_output_area') and self.dashboard_console_output_area.winfo_exists():
            text_boxes.append(self.dashboard_console_output_area)

        for text_box in text_boxes:
            text_box.insert(tk.END, msg, level)
            text_box.see(tk.END)

        self.process_server_output(msg, level)
        
    def start_server_thread(self):
        self.server_handler.start()
        self._update_server_status_display()

    def stop_server(self):
        self.server_handler.stop()
        self.stop_button.configure(state=tk.DISABLED)
        self._update_server_status_display()

    def on_server_stop(self, silent=False):
        self._update_server_status_display()
        if not silent:
            self.log_to_console("Server has stopped.\n", "info")

    def process_server_output(self, line, level):
        clean_line = line.strip()
        if not clean_line: return

        if self.expecting_player_list_next_line:
            self.players_connected = [p.strip() for p in clean_line.split(',') if p.strip()]
            self._refresh_players_display()
            self.expecting_player_list_next_line = False
        
        elif self.player_count_line_prefix in clean_line and self.player_count_line_suffix in clean_line:
            try:
                start = clean_line.find(self.player_count_line_suffix) + len(self.player_count_line_suffix)
                player_names_part = clean_line[start:].strip()
                if player_names_part:
                    self.players_connected = [p.strip() for p in player_names_part.split(',') if p.strip()]
                    self._refresh_players_display()
                else:
                    self.expecting_player_list_next_line = True
            except Exception:
                self.expecting_player_list_next_line = False
        
        elif "opped players:" in clean_line or "operators:" in clean_line.lower():
            try:
                ops_str = clean_line.split(":", 1)[1].strip()
                self.ops_list = [op.strip() for op in ops_str.split(',') if op.strip()]
            except IndexError: self.ops_list = []
            self._refresh_ops_display()
        elif "There are no opped players" in clean_line:
            self.ops_list = []
            self._refresh_ops_display()
        elif ("Made" in clean_line and "a server operator" in clean_line) or "De-opped" in clean_line:
            self.master.after(200, self.update_ops_list)
        elif "You need to agree to the EULA" in clean_line:
            self.log_to_console("EULA needs to be accepted. Attempting to accept automatically...\n", "warning")
            self.master.after(500, self._handle_eula_shutdown)

        if 'Done' in clean_line and 'For help, type "help"' in clean_line:
            self.master.after(0, self._update_server_status_display)

        self._detect_version_from_log(clean_line)
        self._detect_type_from_log(clean_line)

    def _detect_version_from_log(self, line):
        # Don't try to detect if a version is already properly set
        current_version = self.config_manager.get('server_version', 'N/A')
        if current_version != 'N/A' and current_version != 'Unknown':
            return

        # Regex patterns for different server types
        patterns = [
            r"Starting minecraft server version\s+([0-9\.]+)",  # Vanilla, Spigot, Paper
            r"mcVersion,?\s+([0-9\.]+)",                         # Forge (from user feedback)
            r"Loading Minecraft\s+([0-9\.]+)\s+with Fabric",     # Fabric
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                version = match.group(1)
                # Update if the new version is different from what's stored
                if version != self.config_manager.get('server_version'):
                    self.log_to_console(f"Detected server version: {version}\n", "success")
                    
                    # Update variable, config, and UI
                    if not hasattr(self, 'server_version_var'):
                        self.server_version_var = tk.StringVar()
                    self.server_version_var.set(version)
                    self._save_config()
                    self._update_dashboard_info()
                return # Stop after first match

    def _detect_type_from_log(self, line):
        # Don't re-detect if the type is already something other than vanilla/unknown
        current_type = self.config_manager.get('server_type', 'vanilla').lower()
        if current_type not in ['vanilla', 'unknown']:
            return

        type_patterns = {
            'forge': r'ModLauncher running|forgeserver|fml.forgeVersion',
            'fabric': r'FabricLoader|Loading Minecraft .* with Fabric',
            'paper': r'This server is running Paper',
            'spigot': r'This server is running Spigot',
        }

        for server_type, pattern in type_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                if server_type != current_type:
                    self.log_to_console(f"Detected server type: {server_type.capitalize()}\n", "success")
                    self.server_type = server_type
                    self._save_config()
                    self._update_dashboard_info()
                return

    def _handle_eula_shutdown(self):
        self._accept_eula_file()
        if self.server_handler.is_starting():
            self.on_server_stop(silent=True)

    def _accept_eula_file(self):
        if not self.server_path: return
        eula_path = os.path.join(self.server_path, "eula.txt")
        if not os.path.exists(eula_path):
            self.log_to_console("Tried to accept EULA, but eula.txt was not found.\n", "warning")
            return
        try:
            with open(eula_path, 'r+') as f:
                content = f.read().replace("eula=false", "eula=true")
                f.seek(0); f.write(content); f.truncate()
            self.log_to_console("EULA has been automatically accepted. The server has stopped. Please start it again.\n", "success")
        except Exception as e:
            self.log_to_console(f"Failed to automatically accept EULA: {e}\n", "error")

    def send_command_from_entry(self, event=None): self.send_command_from_button()
    def send_command_from_button(self):
        cmd = self.command_entry.get().strip()
        if cmd:
            self.server_handler.send_command(cmd)
            self.command_entry.delete(0, tk.END)

    def send_command_from_console_entry(self, event=None): self.send_command_from_console_button()
    def send_command_from_console_button(self):
        cmd = self.console_command_entry.get().strip()
        if cmd:
            self.server_handler.send_command(cmd)
            self.console_command_entry.delete(0, tk.END)

    def restart_server(self):
        if self.server_handler.is_running():
            self.stop_server()
            self.master.after(2000, self._check_if_stopped_then_start)
            self.restart_button.configure(state=tk.DISABLED)

    def _check_if_stopped_then_start(self):
        if not self.server_handler.is_running() and not self.server_handler.is_starting():
            self.log_to_console("Server stopped, restarting...\n", "info")
            self.start_server_thread()
        else:
            self.log_to_console("Waiting for server to stop...\n", "info")
            self.master.after(2000, self._check_if_stopped_then_start)

    def _update_server_status_display(self):
        is_starting = self.server_handler.is_starting()
        is_running = self.server_handler.is_running()

        if is_running:
            status_text, status_color = ("Status: Online", "green")
            start_state, stop_state, restart_state = (tk.DISABLED, tk.NORMAL, tk.NORMAL)
        elif is_starting:
            status_text, status_color = ("Status: Starting...", "orange")
            start_state, stop_state, restart_state = (tk.DISABLED, tk.DISABLED, tk.DISABLED)
        else:
            status_text, status_color = ("Status: Offline", "red")
            start_state, stop_state, restart_state = (tk.NORMAL, tk.DISABLED, tk.DISABLED)
        
        if hasattr(self, 'server_status_label') and self.server_status_label.winfo_exists(): self.server_status_label.configure(text=status_text, text_color=status_color)
        if hasattr(self, 'restart_button') and self.restart_button.winfo_exists(): self.restart_button.configure(state=restart_state)
        if hasattr(self, 'stop_button') and self.stop_button.winfo_exists(): self.stop_button.configure(state=stop_state)
        if hasattr(self, 'start_button') and self.start_button.winfo_exists(): self.start_button.configure(state=start_state)
        
        console_state = tk.NORMAL if is_running else tk.DISABLED
        if hasattr(self, 'console_send_btn') and self.console_send_btn.winfo_exists(): self.console_send_btn.configure(state=console_state)
        if hasattr(self, 'console_command_entry') and self.console_command_entry.winfo_exists(): self.console_command_entry.configure(state=console_state)
        if hasattr(self, 'send_btn') and self.send_btn.winfo_exists(): self.send_btn.configure(state=console_state)
        if hasattr(self, 'command_entry') and self.command_entry.winfo_exists(): self.command_entry.configure(state=console_state)

    def _create_placeholder_avatar(self, size=(24, 24)):
        return ctk.CTkImage(Image.new('RGBA', size, (0,0,0,0)), size=size)

    def _update_avatar_label(self, label, photo_image):
        if label.winfo_exists():
            label.configure(image=photo_image)

    def _fetch_player_avatar(self, player_identifier, avatar_label, size=(24, 24)):
        if not player_identifier or player_identifier == 'N/A': return
        if player_identifier in self.avatar_cache:
            self.master.after(0, self._update_avatar_label, avatar_label, self.avatar_cache[player_identifier])
            return
        if self.placeholder_avatar:
             self.master.after(0, self._update_avatar_label, avatar_label, self.placeholder_avatar)
        threading.Thread(target=self._fetch_player_avatar_thread, args=(player_identifier, avatar_label, size), daemon=True).start()

    def _fetch_player_avatar_thread(self, player_identifier, avatar_label, size):
        try:
            image = fetch_player_avatar_image(player_identifier, size)
            if image:
                # Create CTkImage in the main thread via master.after
                def update_image():
                    if avatar_label.winfo_exists():
                        photo_img = ctk.CTkImage(light_image=image, dark_image=image, size=size)
                        self.avatar_cache[player_identifier] = photo_img
                        self._update_avatar_label(avatar_label, photo_img)
                self.master.after(0, update_image)
        except Exception as e:
            # It's useful to log the exception to see what's going wrong.
            print(f"Error fetching avatar for {player_identifier}: {e}")
            pass
            
    def _create_players_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        
        title_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Connected Players", font=ctk.CTkFont(size=18, weight="bold")).pack(side=tk.LEFT)
        ctk.CTkButton(title_frame, text='Refresh List', command=self.update_players_list).pack(side=tk.RIGHT)
        
        self.scrollable_players_list_frame = ctk.CTkScrollableFrame(parent_frame)
        self.scrollable_players_list_frame.grid(row=1, column=0, sticky="nsew")
        
    def update_players_list(self):
        if self.server_handler.is_running(): self.server_handler.send_command("list")
        else:
            self.players_connected = []
            self._refresh_players_display()

    def _refresh_players_display(self):
        if not hasattr(self, 'scrollable_players_list_frame'): return
        for widget in self.scrollable_players_list_frame.winfo_children(): widget.destroy()
        
        if not self.players_connected:
            ctk.CTkLabel(self.scrollable_players_list_frame, text="No players currently online.").pack(pady=10)
        else:
            for player_name in self.players_connected:
                row = ctk.CTkFrame(self.scrollable_players_list_frame, fg_color="gray20")
                row.pack(fill=tk.X, expand=True, pady=2)
                avatar_label = ctk.CTkLabel(row, text="")
                avatar_label.pack(side=tk.LEFT, padx=(10, 8), pady=10)
                self._fetch_player_avatar(player_name, avatar_label)
                ctk.CTkLabel(row, text=player_name, anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                ctk.CTkButton(row, text="Ban", width=50, command=lambda p=player_name: self._context_ban_player(p)).pack(side=tk.RIGHT, padx=5, pady=5)
                ctk.CTkButton(row, text="Kick", width=50, command=lambda p=player_name: self._context_kick_player(p)).pack(side=tk.RIGHT, padx=5, pady=5)
                op_button = ctk.CTkButton(row, text="Op", width=50, command=lambda p=player_name: self._context_op_player(p, True))
                deop_button = ctk.CTkButton(row, text="De-Op", width=50, command=lambda p=player_name: self._context_op_player(p, False))
                
                if player_name in self.ops_list:
                    deop_button.pack(side=tk.RIGHT, padx=5, pady=5)
                else:
                    op_button.pack(side=tk.RIGHT, padx=5, pady=5)

        self._update_dashboard_info()
        
    def _context_op_player(self, player_name, make_op: bool):
        cmd = "op" if make_op else "deop"
        self.server_handler.send_command(f"{cmd} {player_name}")
        self.master.after(500, self.update_ops_list)
    
    def _context_kick_player(self, player_name):
        self.server_handler.send_command(f"kick {player_name}")
        self.master.after(200, self.update_players_list)

    def _context_ban_player(self, player_name):
        self.server_handler.send_command(f"ban {player_name}")
        self.master.after(200, self.update_players_list)

    def _create_ops_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        
        title_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Operators (Ops)", font=ctk.CTkFont(size=18, weight="bold")).pack(side=tk.LEFT)
        ctk.CTkButton(title_frame, text='Refresh List', command=self.update_ops_list).pack(side=tk.RIGHT)
        
        self.scrollable_ops_list_frame = ctk.CTkScrollableFrame(parent_frame)
        self.scrollable_ops_list_frame.grid(row=1, column=0, sticky="nsew")
        
        add_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        add_frame.grid(row=2, column=0, sticky="ew", pady=(10,0))
        add_frame.grid_columnconfigure(0, weight=1)
        self.op_entry = ctk.CTkEntry(add_frame, placeholder_text="Enter player name to op...")
        self.op_entry.grid(row=0, column=0, sticky="ew", padx=(0,10))
        self.add_op_button = ctk.CTkButton(add_frame, text="Add", width=70, command=self._add_op)
        self.add_op_button.grid(row=0, column=1)

    def update_ops_list(self):
        if self.server_handler.is_running():
            self.server_handler.send_command("op list")
        else:
            ops_path = os.path.join(self.server_path, 'ops.json')
            if os.path.exists(ops_path):
                try:
                    with open(ops_path, 'r') as f: 
                        ops_data = json.load(f)
                        # Ensure ops_data is a list of dicts and extract names
                        if isinstance(ops_data, list):
                            self.ops_list = [op.get('name') for op in ops_data if op.get('name')]
                        else:
                            self.ops_list = []
                except (json.JSONDecodeError, KeyError): 
                    self.ops_list = []
            else:
                self.ops_list = []
            self._refresh_ops_display()

    def _refresh_ops_display(self):
        if not hasattr(self, 'scrollable_ops_list_frame'): return
        for widget in self.scrollable_ops_list_frame.winfo_children(): widget.destroy()

        if not self.ops_list:
            ctk.CTkLabel(self.scrollable_ops_list_frame, text="No operators defined.").pack(pady=10)
        else:
            for op_name in self.ops_list:
                row = ctk.CTkFrame(self.scrollable_ops_list_frame, fg_color="gray20")
                row.pack(fill=tk.X, expand=True, pady=2)
                avatar_label = ctk.CTkLabel(row, text="")
                avatar_label.pack(side=tk.LEFT, padx=(10, 8), pady=10)
                self._fetch_player_avatar(op_name, avatar_label)
                ctk.CTkLabel(row, text=op_name, anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
                ctk.CTkButton(row, text="De-Op", width=70, command=lambda p=op_name: self._deop_player(p)).pack(side=tk.RIGHT, padx=10, pady=5)

    def _add_op(self):
        player_name = self.op_entry.get().strip()
        if not player_name: return

        if self.server_handler.is_running():
            self.server_handler.send_command(f"op {player_name}")
            self.op_entry.delete(0, tk.END)
        else:
            self.add_op_button.configure(state=tk.DISABLED, text="Adding...")
            threading.Thread(target=self._add_op_offline, args=(player_name,), daemon=True).start()

    def _add_op_offline(self, player_name):
        try:
            self.master.after(0, self.log_to_console, f"Fetching UUID for {player_name}...\n", "info")
            player_data = fetch_player_uuid(player_name)
            if not player_data:
                messagebox.showerror("Error", f"Could not find player '{player_name}'. Please check the name.")
                return

            formatted_uuid = str(uuid.UUID(player_data['id']))
            ops_path = os.path.join(self.server_path, 'ops.json')
            ops_list = []
            if os.path.exists(ops_path):
                try:
                    with open(ops_path, 'r') as f: ops_list = json.load(f)
                except (json.JSONDecodeError, IOError): pass

            if any(op.get('name', '').lower() == player_name.lower() for op in ops_list):
                messagebox.showwarning("Already Op", f"'{player_name}' is already an operator.")
                return

            ops_list.append({"uuid": formatted_uuid, "name": player_name, "level": 4, "bypassesPlayerLimit": False})
            with open(ops_path, 'w') as f: json.dump(ops_list, f, indent=4)

            self.master.after(0, self.op_entry.delete, 0, tk.END)
            self.master.after(0, self.log_to_console, f"Successfully added '{player_name}' to operators (offline).\n", "success")
            self.master.after(100, self.update_ops_list)

        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred while adding operator:\n{e}")
        finally:
            if hasattr(self, 'add_op_button') and self.add_op_button.winfo_exists():
                self.master.after(0, self.add_op_button.configure, {'state': tk.NORMAL, 'text': 'Add'})

    def _deop_player(self, player_name):
        if not player_name: return

        if self.server_handler.is_running():
            self.server_handler.send_command(f"deop {player_name}")
        else:
            ops_path = os.path.join(self.server_path, 'ops.json')
            if not os.path.exists(ops_path): return
            try:
                with open(ops_path, 'r') as f: ops_list = json.load(f)
                original_count = len(ops_list)
                ops_list = [op for op in ops_list if op.get('name', '').lower() != player_name.lower()]
                if len(ops_list) < original_count:
                    with open(ops_path, 'w') as f: json.dump(ops_list, f, indent=4)
                    self.log_to_console(f"Successfully de-opped '{player_name}' (offline).\n", "success")
                self.master.after(100, self.update_ops_list)
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while modifying ops.json:\n{e}")
            
    def _create_worlds_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        
        title_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))
        ctk.CTkLabel(title_frame, text="Server Worlds", font=ctk.CTkFont(size=18, weight="bold")).pack(side=tk.LEFT)
        ctk.CTkButton(title_frame, text="Refresh", command=self._refresh_worlds_visual).pack(side=tk.RIGHT)
        
        self.scrollable_worlds_frame = ctk.CTkScrollableFrame(parent_frame)
        self.scrollable_worlds_frame.grid(row=1, column=0, sticky="nsew")
        
    def _refresh_worlds_visual(self):
        if not hasattr(self, 'scrollable_worlds_frame'): return
        for widget in self.scrollable_worlds_frame.winfo_children(): widget.destroy()

        if not self.server_path or not os.path.isdir(self.server_path):
            ctk.CTkLabel(self.scrollable_worlds_frame, text="Server path is not configured or not found.").pack(pady=20)
            return

        world_folders = set()
        try:
            with open(self.server_properties_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('level-name='):
                        world_name = line.split('=', 1)[1].strip()
                        if os.path.isdir(os.path.join(self.server_path, world_name)):
                            world_folders.add(world_name)
                        break
        except (IOError, IndexError): pass

        try:
            for item in os.listdir(self.server_path):
                item_path = os.path.join(self.server_path, item)
                if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'level.dat')):
                    world_folders.add(item)
        except OSError as e:
            ctk.CTkLabel(self.scrollable_worlds_frame, text=f"Error scanning for worlds:\n{e}", wraplength=300).pack(pady=20)
            return

        if not world_folders:
            ctk.CTkLabel(self.scrollable_worlds_frame, text="No worlds found. Check 'level-name' in server.properties.").pack(pady=20)
            return

        for world_name in sorted(list(world_folders)):
            world_path = os.path.join(self.server_path, world_name)
            
            pane = CollapsiblePane(self.scrollable_worlds_frame, text=f"🌍 {world_name}")
            pane.pack(fill=tk.X, expand=True, pady=4, padx=2)

            # --- Add size label and backup button to the header ---
            pane.header_frame.columnconfigure(2, weight=0) # Column for size
            pane.header_frame.columnconfigure(3, weight=0) # Column for button

            total_size_label = ctk.CTkLabel(pane.header_frame, text="Calculating size...", text_color="gray")
            total_size_label.grid(row=0, column=2, sticky='e', padx=10)
            threading.Thread(target=self._update_world_size_label, args=(world_path, total_size_label, "Total Size: "), daemon=True).start()
            
            ctk.CTkButton(pane.header_frame, text="Backup", width=80, command=lambda w=world_name: self.backup_world(w)).grid(row=0, column=3, sticky='e', padx=(0, 10))

            # --- Populate dimensions inside the collapsible body ---
            self._populate_world_dimensions(pane.body, world_path)

    def _populate_world_dimensions(self, parent_frame, world_path):
        dim_map = {
            ".": "Overworld",
            "DIM-1": "The Nether",
            "DIM1": "The End"
        }
        
        dimensions_found = []
        # The Overworld is the root world folder itself
        if os.path.exists(os.path.join(world_path, 'region')):
            dimensions_found.append(".")

        # Find other dimension folders
        for item in os.listdir(world_path):
            item_path = os.path.join(world_path, item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'region')):
                dimensions_found.append(item)
        
        if not dimensions_found:
            ctk.CTkLabel(parent_frame, text="No dimensions found in this world.").pack(padx=10, pady=10)
            return

        for dim_folder in sorted(dimensions_found):
            dim_name = dim_map.get(dim_folder, dim_folder)
            dim_path = os.path.join(world_path, dim_folder)

            row = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row.pack(fill=tk.X, expand=True, pady=1, padx=10)
            
            ctk.CTkLabel(row, text=f"  • {dim_name}", anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
            size_label = ctk.CTkLabel(row, text="Calculating...", text_color="gray", anchor='e')
            size_label.pack(side=tk.RIGHT)
            
            threading.Thread(target=self._update_world_size_label, args=(dim_path, size_label), daemon=True).start()

    def _update_world_size_label(self, world_path, size_label, prefix="Size: "):
        try:
            size_bytes = get_folder_size(world_path)
            if size_label.winfo_exists():
                self.master.after(0, size_label.configure, {'text': f"{prefix}{format_size(size_bytes)}"})
        except Exception:
            if size_label.winfo_exists():
                self.master.after(0, size_label.configure, {'text': f"{prefix}Error"})

    def backup_world(self, world_name):
        world_path = os.path.join(self.server_path, world_name)
        backup_dir = os.path.join(self.server_path, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup_path_base = os.path.join(backup_dir, f"{world_name}_{time.strftime('%Y-%m-%d_%H-%M-%S')}")
        
        self.log_to_console(f"Starting backup of '{world_name}'...", "info")
        try:
            shutil.make_archive(backup_path_base, 'zip', world_path)
            self.log_to_console(f"Backup successful: {os.path.basename(backup_path_base)}.zip\n", "success")
            messagebox.showinfo("Backup Complete", f"World '{world_name}' backed up successfully.")
        except Exception as e:
            self.log_to_console(f"Backup failed for '{world_name}': {e}\n", "error")
            messagebox.showerror("Backup Failed", f"Could not back up world '{world_name}'.\nError: {e}")

    def _format_stat_value(self, stat_key, value):
        # Existing time and distance formatting
        if 'time' in stat_key or 'since' in stat_key:
            try:
                seconds = int(value) / 20  # Ticks to seconds
                if seconds < 60:
                    return f"{seconds:.1f}s"
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                d, h = divmod(h, 24)
                if d > 0:
                    return f"{int(d)}d {int(h)}h"
                elif h > 0:
                    return f"{int(h)}h {int(m)}m"
                else:
                    return f"{int(m)}m {int(s)}s"
            except (ValueError, TypeError):
                return str(value)
        if 'cm' in stat_key:
            try:
                cm = int(value)
                if cm >= 100000:  # Over 1km
                    return f"{cm / 100000:.2f} km"
                elif cm >= 100:  # Over 1m
                    return f"{cm / 100:.2f} m"
                else:
                    return f"{cm} cm"
            except (ValueError, TypeError):
                return str(value)
        if 'damage' in stat_key:
            try:
                # Damage is in 1/10ths of a heart
                return f"{int(value) / 10:.1f} hearts"
            except (ValueError, TypeError):
                return str(value)
        
        # Default formatting for other numbers
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return str(value)

    def _create_stats_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(1, weight=3)
        parent_frame.grid_rowconfigure(0, weight=1)
        
        # --- Left panel for player list ---
        players_frame = ctk.CTkFrame(parent_frame, width=250)
        players_frame.grid(row=0, column=0, sticky="nsw", padx=(0,10), pady=0)
        players_frame.grid_rowconfigure(1, weight=1)
        players_frame.grid_columnconfigure(0, weight=1)
        players_frame.grid_propagate(False)
        
        ctk.CTkLabel(players_frame, text="Select Player", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10)
        self.stats_player_list_frame = ctk.CTkScrollableFrame(players_frame, fg_color="transparent")
        self.stats_player_list_frame.grid(row=1, column=0, sticky="nsew", padx=5)

        # --- Right panel for stats display ---
        self.stats_display_frame = ctk.CTkFrame(parent_frame)
        self.stats_display_frame.grid(row=0, column=1, sticky="nsew")
        self.stats_display_frame.grid_columnconfigure(0, weight=1)
        self.stats_display_frame.grid_rowconfigure(1, weight=1)
        
        self.stats_search_var = tk.StringVar()
        self.stats_search_var.trace_add("write", lambda *_: self._refresh_stats_display())
        ctk.CTkEntry(self.stats_display_frame, textvariable=self.stats_search_var, placeholder_text="Search stats...").grid(row=0, column=0, sticky="ew", padx=15, pady=(10,5))

        self.stats_scrollable_frame = ctk.CTkScrollableFrame(self.stats_display_frame, fg_color="transparent")
        self.stats_scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0,10))
        self.stats_scrollable_frame.grid_columnconfigure(0, weight=1)
        self.stats_scrollable_frame.grid_columnconfigure(1, weight=1)
        
        self.no_player_selected_label = ctk.CTkLabel(self.stats_display_frame, text="Select a player from the list to view their stats.", font=ctk.CTkFont(size=16))
        self.no_player_selected_label.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0,10))
        self.stats_scrollable_frame.grid_remove() # Hide until player is selected
        
    def update_stats_list(self):
        self._update_uuid_cache()
        for widget in self.stats_player_list_frame.winfo_children():
            widget.destroy()
        self.stats_files.clear()

        if not self.server_path:
            ctk.CTkLabel(self.stats_player_list_frame, text="Server path not set.").pack(pady=10)
            return

        stats_dir = None
        world_dirs = ['world'] + [d for d in os.listdir(self.server_path) if os.path.isdir(os.path.join(self.server_path, d)) and os.path.exists(os.path.join(self.server_path, d, 'level.dat'))]
        for world_dir in world_dirs:
            potential_stats_dir = os.path.join(self.server_path, world_dir, 'stats')
            if os.path.isdir(potential_stats_dir):
                stats_dir = potential_stats_dir
                break
        
        if not stats_dir:
            ctk.CTkLabel(self.stats_player_list_frame, text="Stats folder not found.").pack(pady=10)
            return

        # --- Processing ---
        stat_file_uuids = [f[:-5] for f in os.listdir(stats_dir) if f.endswith('.json')]

        if not stat_file_uuids:
            ctk.CTkLabel(self.stats_player_list_frame, text="No stats files found.").pack(pady=10)
            return

        for uuid_str in sorted(stat_file_uuids):
            self.stats_files[uuid_str] = os.path.join(stats_dir, f"{uuid_str}.json")
            
            player_frame = ctk.CTkFrame(self.stats_player_list_frame, fg_color="transparent", corner_radius=6)
            player_frame.pack(fill="x", pady=2, padx=2)
            
            avatar_label = ctk.CTkLabel(player_frame, text="")
            avatar_label.pack(side="left", padx=5, pady=5)
            name_label = ctk.CTkLabel(player_frame, text=f"Loading {uuid_str[:8]}...", anchor="w")
            name_label.pack(side="left", expand=True, fill="x")
            
            self.stats_player_widgets[uuid_str] = (player_frame, name_label, avatar_label)
            
            # Bind clicks
            player_frame.bind("<Button-1>", lambda e, u=uuid_str: self._on_stats_player_selected(u))
            for child in player_frame.winfo_children():
                child.bind("<Button-1>", lambda e, u=uuid_str: self._on_stats_player_selected(u))

            # --- Fetch Name and Avatar ---
            uuid_clean_lower = uuid_str.replace('-', '').lower()
            if uuid_clean_lower in self.uuid_to_name_cache:
                # Name is in local cache, use it
                name = self.uuid_to_name_cache[uuid_clean_lower]
                self.player_uuids[name] = uuid_str
                name_label.configure(text=name)
                self._fetch_player_avatar(name, avatar_label, size=(32,32))
            else:
                # Name not in local cache, display UUID as fallback
                name_label.configure(text=f"UUID: ...{uuid_str[-12:]}")
                self._fetch_player_avatar(uuid_str, avatar_label, size=(32,32))

        if not self.selected_stats_player_uuid and stat_file_uuids:
            self._on_stats_player_selected(stat_file_uuids[0])

    

    def _on_stats_player_selected(self, uuid):
        if self.selected_stats_player_uuid and self.selected_stats_player_uuid in self.stats_player_widgets:
            self.stats_player_widgets[self.selected_stats_player_uuid][0].configure(fg_color="transparent")
        
        self.selected_stats_player_uuid = uuid
        if uuid in self.stats_player_widgets:
            self.stats_player_widgets[uuid][0].configure(fg_color="gray20")

        stats_file = self.stats_files.get(self.selected_stats_player_uuid)
        if not stats_file:
            self.current_player_stats = None
        else:
            try:
                with open(stats_file, 'r') as f:
                    self.current_player_stats = json.load(f).get("stats", {})
            except (IOError, json.JSONDecodeError) as e:
                print(f"Error reading stats file for {uuid}: {e}")
                self.current_player_stats = None
        
        self._create_stat_widgets()
        self._refresh_stats_display()

    def _create_stat_widgets(self):
        """Create and cache the widgets for the main stats."""
        self.stats_widgets_cache.clear()
        if not self.current_player_stats:
            return

        custom_stats = self.current_player_stats.get("minecraft:custom", {})

        # Define the most important stats to show
        key_stats_map = {
            "General": [
                ("Time Played", "minecraft:play_time"),
                ("Player Kills", "minecraft:player_kills"),
                ("Deaths", "minecraft:deaths"),
                ("Mob Kills", "minecraft:mob_kills"),
                ("Damage Dealt", "minecraft:damage_dealt"),
                ("Damage Taken", "minecraft:damage_taken"),
                ("Jumps", "minecraft:jump"),
            ],
            "Movement": [
                ("Walked", "minecraft:walk_one_cm"),
                ("Sprinted", "minecraft:sprint_one_cm"),
                ("Crouched", "minecraft:crouch_one_cm"),
                ("Swam", "minecraft:swim_one_cm"),
                ("Fallen", "minecraft:fall_one_cm"),
                ("Flown", "minecraft:fly_one_cm"),
                ("Climbed", "minecraft:climb_one_cm"),
                ("Dove", "minecraft:dive_one_cm"),
            ]
        }

        for category, keys in key_stats_map.items():
            # Add category header
            header = ctk.CTkLabel(self.stats_scrollable_frame, text=category, font=ctk.CTkFont(weight="bold"))
            self.stats_widgets_cache[category] = [("header", header, None)]
            
            for display_name, stat_key in keys:
                value = custom_stats.get(stat_key, 0)
                formatted_value = self._format_stat_value(stat_key, value)
                
                name_label = ctk.CTkLabel(self.stats_scrollable_frame, text=display_name, anchor="w")
                value_label = ctk.CTkLabel(self.stats_scrollable_frame, text=formatted_value, anchor="e")
                
                self.stats_widgets_cache[category].append((display_name, name_label, value_label))

    def _refresh_stats_display(self):
        if not self.current_player_stats:
            self.no_player_selected_label.grid()
            self.stats_scrollable_frame.grid_remove()
            return
        
        self.no_player_selected_label.grid_remove()
        self.stats_scrollable_frame.grid()

        search_term = self.stats_search_var.get().lower()
        
        # Clear the frame before redrawing
        for widget in self.stats_scrollable_frame.winfo_children():
            widget.grid_remove()

        row = 0
        for category, widgets in self.stats_widgets_cache.items():
            # Check if any item in the category matches the search
            category_matches = any(search_term in name.lower() for name, _, _ in widgets if name != "header")
            
            if not search_term or category_matches:
                # Display header
                header_widget = widgets[0][1]
                header_widget.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
                row += 1

                # Display stats in this category
                for name, name_label, value_label in widgets:
                    if name == "header": continue
                    if not search_term or search_term in name.lower():
                        name_label.grid(row=row, column=0, sticky="ew", padx=10, pady=1)
                        value_label.grid(row=row, column=1, sticky="ew", padx=10, pady=1)
                        row += 1
                
                # Add a separator
                sep = ctk.CTkFrame(self.stats_scrollable_frame, height=1, fg_color="gray25")
                sep.grid(row=row, column=0, columnspan=2, sticky='ew', pady=5, padx=5)
                row += 1

    def _create_bans_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        
        title_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))
        ctk.CTkLabel(title_frame, text="Ban Management", font=ctk.CTkFont(size=18, weight="bold")).pack(side=tk.LEFT)
        ctk.CTkButton(title_frame, text="Refresh Lists", command=self._load_bans).pack(side=tk.RIGHT)
        
        paned_window = ctk.CTkFrame(parent_frame, fg_color="transparent")
        paned_window.grid(row=1, column=0, sticky="nsew")
        paned_window.grid_columnconfigure((0,1), weight=1)
        paned_window.grid_rowconfigure(0, weight=1)

        players_frame = ctk.CTkFrame(paned_window)
        players_frame.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        players_frame.grid_rowconfigure(1, weight=1)
        players_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(players_frame, text="Banned Players", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10)
        self.banned_players_list_frame = ctk.CTkScrollableFrame(players_frame)
        self.banned_players_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        
        ips_frame = ctk.CTkFrame(paned_window)
        ips_frame.grid(row=0, column=1, sticky="nsew", padx=(5,0))
        ips_frame.grid_rowconfigure(1, weight=1)
        ips_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ips_frame, text="Banned IPs", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10)
        self.banned_ips_list_frame = ctk.CTkScrollableFrame(ips_frame)
        self.banned_ips_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))

        # --- Add Ban Frame ---
        add_ban_frame = ctk.CTkFrame(parent_frame)
        add_ban_frame.grid(row=2, column=0, sticky="ew", pady=(10,0))
        add_ban_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(add_ban_frame, text="Add New Ban", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=(5,0), sticky="w")
        
        self.ban_target_entry = ctk.CTkEntry(add_ban_frame, placeholder_text="Player Name or IP Address")
        self.ban_target_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.ban_reason_entry = ctk.CTkEntry(add_ban_frame, placeholder_text="Reason (optional)")
        self.ban_reason_entry.grid(row=1, column=1, sticky="ew", padx=(0,10), pady=5)

        ban_buttons_frame = ctk.CTkFrame(add_ban_frame, fg_color="transparent")
        ban_buttons_frame.grid(row=1, column=2, padx=(0,10), pady=5)
        ctk.CTkButton(ban_buttons_frame, text="Ban Player", command=self._ban_player_from_input).pack(side=tk.LEFT)
        ctk.CTkButton(ban_buttons_frame, text="Ban IP", command=self._ban_ip_from_input).pack(side=tk.LEFT, padx=5)

    def _ban_player_from_input(self):
        target = self.ban_target_entry.get().strip()
        reason = self.ban_reason_entry.get().strip()
        if not target:
            messagebox.showwarning("Input Required", "Please enter a player name to ban.")
            return

        if self.server_handler.is_running():
            command = f"ban {target} {reason}"
            self.server_handler.send_command(command.strip())
            self.log_to_console(f"Attempted to ban player: {target}\n", "info")
        else:
            self.log_to_console(f"Server is offline. Attempting to ban {target} by editing files...\n", "info")
            threading.Thread(target=self._ban_player_offline, args=(target, reason), daemon=True).start()

        self.ban_target_entry.delete(0, tk.END)
        self.ban_reason_entry.delete(0, tk.END)
        self.master.after(1000, self._load_bans)

    def _ban_player_offline(self, player_name, reason):
        try:
            self.master.after(0, self.log_to_console, f"Fetching UUID for {player_name}...\n", "info")
            player_data = fetch_player_uuid(player_name)
            if not player_data:
                self.master.after(0, messagebox.showerror, "Error", f"Could not find player '{player_name}'. Please check the name.")
                return

            uuid_str = player_data['id']
            
            ban_entry = {
                "uuid": str(uuid.UUID(uuid_str)), # Format with dashes
                "name": player_name,
                "created": time.strftime("%Y-%m-%d %H:%M:%S %z"),
                "source": "ServerControlGUI",
                "expires": "forever",
                "reason": reason or "Banned by an operator."
            }

            file_path = os.path.join(self.server_path, 'banned-players.json')
            ban_list = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        ban_list = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass # Overwrite if file is corrupt

            # Avoid duplicate bans
            if any(entry.get('name', '').lower() == player_name.lower() for entry in ban_list):
                self.master.after(0, messagebox.showwarning, "Already Banned", f"'{player_name}' is already on the ban list.")
                return

            ban_list.append(ban_entry)
            with open(file_path, 'w') as f:
                json.dump(ban_list, f, indent=4)
            
            self.master.after(0, self.log_to_console, f"Successfully banned '{player_name}' (offline).\n", "success")
            self.master.after(100, self._load_bans)

        except Exception as e:
            self.master.after(0, messagebox.showerror, "Error", f"An unexpected error occurred while banning offline:\n{e}")

    def _ban_ip_from_input(self):
        target = self.ban_target_entry.get().strip()
        reason = self.ban_reason_entry.get().strip()
        if not target:
            messagebox.showwarning("Input Required", "Please enter an IP address to ban.")
            return

        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", target):
             messagebox.showwarning("Invalid Format", "Please enter a valid IP address (e.g., 127.0.0.1).")
             return

        if self.server_handler.is_running():
            command = f"ban-ip {target} {reason}"
            self.server_handler.send_command(command.strip())
            self.log_to_console(f"Attempted to ban IP: {target}\n", "info")
        else:
            self.log_to_console(f"Server is offline. Attempting to ban IP {target} by editing files...\n", "info")
            self._ban_ip_offline(target, reason)

        self.ban_target_entry.delete(0, tk.END)
        self.ban_reason_entry.delete(0, tk.END)
        self.master.after(500, self._load_bans)

    def _ban_ip_offline(self, ip_address, reason):
        try:
            ban_entry = {
                "ip": ip_address,
                "created": time.strftime("%Y-%m-%d %H:%M:%S %z"),
                "source": "ServerControlGUI",
                "expires": "forever",
                "reason": reason or "Banned by an operator."
            }
            file_path = os.path.join(self.server_path, 'banned-ips.json')
            ban_list = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        ban_list = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
            
            if any(entry.get('ip') == ip_address for entry in ban_list):
                self.master.after(0, messagebox.showwarning, "Already Banned", f"The IP '{ip_address}' is already on the ban list.")
                return

            ban_list.append(ban_entry)
            with open(file_path, 'w') as f:
                json.dump(ban_list, f, indent=4)

            self.master.after(0, self.log_to_console, f"Successfully banned IP '{ip_address}' (offline).\n", "success")
            self.master.after(100, self._load_bans)
        except Exception as e:
            self.master.after(0, messagebox.showerror, "Error", f"An unexpected error occurred while banning IP offline:\n{e}")

    def _load_bans(self):
        self._load_banned_players()
        self._load_banned_ips()
        
    def _load_banned_players(self):
        if not hasattr(self, 'banned_players_list_frame'): return
        for w in self.banned_players_list_frame.winfo_children(): w.destroy()
        
        file_path = os.path.join(self.server_path, 'banned-players.json')
        if not os.path.exists(file_path): return

        try:
            with open(file_path, 'r') as f: banned_players = json.load(f)
            if not banned_players:
                ctk.CTkLabel(self.banned_players_list_frame, text="No players are banned.").pack()
                return
            for ban_entry in banned_players:
                player_name = ban_entry.get('name', 'N/A')
                row = ctk.CTkFrame(self.banned_players_list_frame, fg_color="gray20")
                row.pack(fill=tk.X, pady=2)
                avatar_label = ctk.CTkLabel(row, text="")
                avatar_label.pack(side=tk.LEFT, padx=(10,5))
                self._fetch_player_avatar(ban_entry.get('uuid', player_name), avatar_label)
                info_text = f"{player_name}\nReason: {ban_entry.get('reason', 'None')}"
                ctk.CTkLabel(row, text=info_text, justify=tk.LEFT).pack(side=tk.LEFT, expand=True, anchor='w', pady=5)
                ctk.CTkButton(row, text="Pardon", width=70, command=lambda p=player_name: self._pardon_player(p)).pack(side=tk.RIGHT, padx=10)
        except Exception as e:
            ctk.CTkLabel(self.banned_players_list_frame, text=f"Error reading bans:\n{e}", wraplength=300).pack()

    def _load_banned_ips(self):
        if not hasattr(self, 'banned_ips_list_frame'): return
        for w in self.banned_ips_list_frame.winfo_children(): w.destroy()

        file_path = os.path.join(self.server_path, 'banned-ips.json')
        if not os.path.exists(file_path): return
            
        try:
            with open(file_path, 'r') as f: banned_ips = json.load(f)
            if not banned_ips:
                ctk.CTkLabel(self.banned_ips_list_frame, text="No IPs are banned.").pack()
                return
            for ban_entry in banned_ips:
                ip = ban_entry.get('ip', 'N/A')
                row = ctk.CTkFrame(self.banned_ips_list_frame, fg_color="gray20")
                row.pack(fill=tk.X, pady=2)
                info_text = f"IP: {ip}\nReason: {ban_entry.get('reason', 'None')}"
                ctk.CTkLabel(row, text=info_text, justify=tk.LEFT).pack(side=tk.LEFT, expand=True, anchor='w', padx=10, pady=5)
                ctk.CTkButton(row, text="Pardon", width=70, command=lambda i=ip: self._pardon_ip(i)).pack(side=tk.RIGHT, padx=10)
        except Exception as e:
             ctk.CTkLabel(self.banned_ips_list_frame, text=f"Error reading IP bans:\n{e}", wraplength=300).pack()

    def _pardon_player(self, player_name):
        if self.server_handler.is_running():
            self.server_handler.send_command(f"pardon {player_name}")
            self.log_to_console(f"Attempted to pardon player: {player_name}\n", "info")
        else:
            self.log_to_console(f"Server is offline. Attempting to pardon {player_name} by editing files...\n", "info")
            self._pardon_player_offline(player_name)
        self.master.after(500, self._load_bans)

    def _pardon_player_offline(self, player_name):
        file_path = os.path.join(self.server_path, 'banned-players.json')
        if not os.path.exists(file_path):
            self.log_to_console("banned-players.json not found.\n", "warning")
            return
        
        try:
            with open(file_path, 'r') as f:
                ban_list = json.load(f)
            
            original_count = len(ban_list)
            ban_list = [entry for entry in ban_list if entry.get('name', '').lower() != player_name.lower()]

            if len(ban_list) < original_count:
                with open(file_path, 'w') as f:
                    json.dump(ban_list, f, indent=4)
                self.log_to_console(f"Successfully pardoned '{player_name}' (offline).\n", "success")
            else:
                self.log_to_console(f"Player '{player_name}' not found in the offline ban list.\n", "info")

        except (json.JSONDecodeError, IOError) as e:
            messagebox.showerror("Error", f"Failed to process banned-players.json: {e}")

    def _pardon_ip(self, ip_address):
        if self.server_handler.is_running():
            self.server_handler.send_command(f"pardon-ip {ip_address}")
            self.log_to_console(f"Attempted to pardon IP: {ip_address}\n", "info")
        else:
            self.log_to_console(f"Server is offline. Attempting to pardon IP {ip_address} by editing files...\n", "info")
            self._pardon_ip_offline(ip_address)
        self.master.after(500, self._load_bans)

    def _pardon_ip_offline(self, ip_address):
        file_path = os.path.join(self.server_path, 'banned-ips.json')
        if not os.path.exists(file_path):
            self.log_to_console("banned-ips.json not found.\n", "warning")
            return

        try:
            with open(file_path, 'r') as f:
                ban_list = json.load(f)

            original_count = len(ban_list)
            ban_list = [entry for entry in ban_list if entry.get('ip') != ip_address]

            if len(ban_list) < original_count:
                with open(file_path, 'w') as f:
                    json.dump(ban_list, f, indent=4)
                self.log_to_console(f"Successfully pardoned IP '{ip_address}' (offline).\n", "success")
            else:
                self.log_to_console(f"IP '{ip_address}' not found in the offline ban list.\n", "info")

        except (json.JSONDecodeError, IOError) as e:
            messagebox.showerror("Error", f"Failed to process banned-ips.json: {e}")

    def _create_mods_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)

        top_actions_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        top_actions_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))
        ctk.CTkButton(top_actions_frame, text="Open Mods Folder", command=self._open_mods_folder).pack(side=tk.LEFT, padx=(0,5))
        ctk.CTkButton(top_actions_frame, text="Open Config Folder", command=self._open_config_folder).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(top_actions_frame, text="Refresh Mod List", command=self._load_mods_list).pack(side=tk.RIGHT)
        
        paned_window = ctk.CTkFrame(parent_frame, fg_color="transparent")
        paned_window.grid(row=1, column=0, sticky="nsew")
        paned_window.grid_columnconfigure(0, weight=1)
        paned_window.grid_columnconfigure(1, weight=2)
        paned_window.grid_rowconfigure(0, weight=1)

        mod_list_outer_frame = ctk.CTkFrame(paned_window)
        mod_list_outer_frame.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        mod_list_outer_frame.grid_rowconfigure(1, weight=1)
        mod_list_outer_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(mod_list_outer_frame, text="Installed Mods", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10)
        self.scrollable_mod_list_frame = ctk.CTkScrollableFrame(mod_list_outer_frame)
        self.scrollable_mod_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))

        config_editor_frame = ctk.CTkFrame(paned_window)
        config_editor_frame.grid(row=0, column=1, sticky="nsew")
        config_editor_frame.grid_rowconfigure(1, weight=1)
        config_editor_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(config_editor_frame, text="Configuration File Editor", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10)
        self.mod_config_text_area = ctk.CTkTextbox(config_editor_frame, wrap=tk.WORD, font=ctk.CTkFont(family="monospace"), state='disabled')
        self.mod_config_text_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        self.save_mod_config_button = ctk.CTkButton(config_editor_frame, text="Save Config Changes", command=self._save_mod_config, state=tk.DISABLED)
        self.save_mod_config_button.grid(row=2, column=0, sticky="se", padx=10, pady=(0,10))

    def _load_mods_list(self):
        if not hasattr(self, 'scrollable_mod_list_frame'): return
        for widget in self.scrollable_mod_list_frame.winfo_children(): widget.destroy()
        self.mod_data.clear()

        if not os.path.isdir(self.mods_dir_path):
            ctk.CTkLabel(self.scrollable_mod_list_frame, text="Mods folder not found.").pack(pady=20)
            return

        jar_files = [f for f in os.listdir(self.mods_dir_path) if f.lower().endswith(('.jar', '.jar.disabled'))]
        if not jar_files:
            ctk.CTkLabel(self.scrollable_mod_list_frame, text="No mods found.").pack(pady=20)
            return

        for jar_file in sorted(jar_files, key=str.lower):
            mod_id = self._extract_mod_id(jar_file)
            config_file_path = self._find_mod_config_file(mod_id)
            is_enabled = not jar_file.lower().endswith('.disabled')
            mod_info = {'jar': jar_file, 'id': mod_id, 'config_path': config_file_path, 'is_enabled': is_enabled}
            self.mod_data.append(mod_info)

            row = ctk.CTkFrame(self.scrollable_mod_list_frame, fg_color="gray20")
            row.pack(fill=tk.X, pady=2)
            status_indicator = "🟢" if is_enabled else "⚪"
            ctk.CTkLabel(row, text=f"{status_indicator} {jar_file}", anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=5)
            
            actions_frame = ctk.CTkFrame(row, fg_color="transparent")
            actions_frame.pack(side=tk.RIGHT, padx=5, pady=5)
            if config_file_path:
                ctk.CTkButton(actions_frame, text="⚙️", width=30, command=lambda m=mod_info: self._load_mod_config_for_editing(m)).pack(side=tk.LEFT)
            toggle_text = "Off" if is_enabled else "On"
            ctk.CTkButton(actions_frame, text=toggle_text, width=40, command=lambda m=mod_info: self._toggle_mod_status(m)).pack(side=tk.LEFT, padx=2)
            ctk.CTkButton(actions_frame, text="🗑️", width=30, command=lambda m=mod_info: self._delete_specific_mod(m)).pack(side=tk.LEFT)

    def _extract_mod_id(self, jar_filename):
        match = re.match(r"([a-zA-Z0-9_\-\[\]]+?)(?:[-_]?(?:forge|fabric|mc)?[.\d]+.*?)?\.jar", jar_filename, re.IGNORECASE)
        return match.group(1).lower().replace('[','').replace(']','') if match else os.path.splitext(jar_filename)[0].lower()

    def _find_mod_config_file(self, mod_id):
        if not self.config_dir_path or not os.path.isdir(self.config_dir_path): return None
        patterns = [f"{mod_id}.toml", f"{mod_id}.cfg", f"{mod_id}.json", f"{mod_id}-common.toml"]
        for p in patterns:
            path = os.path.join(self.config_dir_path, p)
            if os.path.isfile(path): return path
        try:
            for item in os.listdir(self.config_dir_path):
                if mod_id in item.lower() and os.path.isdir(os.path.join(self.config_dir_path, item)):
                    for sub_item in os.listdir(os.path.join(self.config_dir_path, item)):
                        if any(sub_item.lower().endswith(ext) for ext in ['.cfg', '.toml', '.json']):
                            return os.path.join(self.config_dir_path, item, sub_item)
        except OSError: pass
        return None

    def _load_mod_config_for_editing(self, mod_info):
        self.current_mod_config_path = mod_info.get('config_path')
        if not self.current_mod_config_path: return
        self.mod_config_text_area.configure(state='normal')
        self.mod_config_text_area.delete('1.0', tk.END)
        try:
            with open(self.current_mod_config_path, 'r', encoding='utf-8') as f:
                self.mod_config_text_area.insert('1.0', f.read())
            self.save_mod_config_button.configure(state='normal')
        except Exception as e:
            self.mod_config_text_area.insert('1.0', f"Error loading config: {e}")
            self.save_mod_config_button.configure(state='disabled')

    def _save_mod_config(self):
        if not self.current_mod_config_path: return
        try:
            content = self.mod_config_text_area.get('1.0', tk.END)
            with open(self.current_mod_config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log_to_console(f"Saved config: {os.path.basename(self.current_mod_config_path)}\n", "success")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save config file: {e}")

    def _toggle_mod_status(self, mod_info):
        old_name = mod_info['jar']
        new_name = old_name.replace('.disabled', '') if not mod_info['is_enabled'] else old_name + '.disabled'
        try:
            os.rename(os.path.join(self.mods_dir_path, old_name), os.path.join(self.mods_dir_path, new_name))
            self._load_mods_list()
        except Exception as e:
            messagebox.showerror("Error", f"Could not change mod status: {e}")
            
    def _delete_specific_mod(self, mod_info):
        dialog = ctk.CTkInputDialog(text=f"Are you sure you want to delete {mod_info['jar']}?", title="Confirm Delete")
        if dialog.get_input() is not None:
            try:
                os.remove(os.path.join(self.mods_dir_path, mod_info['jar']))
                self._load_mods_list()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete mod: {e}")
                
    def _open_mods_folder(self): os.startfile(self.mods_dir_path)
    def _open_config_folder(self): os.startfile(self.config_dir_path)

    def _create_app_settings_view_widgets(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        
        settings_frame = ctk.CTkScrollableFrame(parent_frame)
        settings_frame.grid(row=0, column=0, sticky="nsew", rowspan=2)
        
        ctk.CTkLabel(settings_frame, text="Application Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor='w', pady=(0, 15), padx=15)
        
        server_path_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        server_path_frame.pack(fill=tk.X, pady=(5, 10), padx=15)
        ctk.CTkLabel(server_path_frame, text="Server Path:", font=ctk.CTkFont(weight="bold")).pack(side=tk.LEFT)
        ctk.CTkLabel(server_path_frame, text=self.server_path or "Not Set", wraplength=500).pack(side=tk.LEFT, padx=5)
        
        # --- About Section ---
        ctk.CTkLabel(settings_frame, text="About", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor='w', pady=(20, 5), padx=15)
        about_frame = ctk.CTkFrame(settings_frame)
        about_frame.pack(fill=tk.X, pady=10, padx=15)

        ctk.CTkLabel(about_frame, text="Author: CalaKuad1").pack(anchor='w', padx=15, pady=(5, 0))
        
        repo_link = "https://github.com/CalaKuad1/Minecraft-Local-Server-GUI"
        repo_label = ctk.CTkLabel(about_frame, text=f"Repository: {repo_link}", text_color="#6AABD2", cursor="hand2")
        repo_label.pack(anchor='w', padx=15, pady=(0, 5))
        repo_label.bind("<Button-1>", lambda e: webbrowser.open_new_tab(repo_link))

        ctk.CTkLabel(settings_frame, text="Changelog", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor='w', pady=(20, 5), padx=15)
        changelog_frame = ctk.CTkFrame(settings_frame)
        changelog_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=15)
        changelog_frame.grid_rowconfigure(0, weight=1)
        changelog_frame.grid_columnconfigure(0, weight=1)
        self.changelog_text = ctk.CTkTextbox(changelog_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.changelog_text.grid(row=0, column=0, sticky="nsew")

    def _load_changelog(self):
        self.changelog_text.configure(state='normal')
        self.changelog_text.delete('1.0', tk.END)
        try:
            with open(self.changelog_path, 'r', encoding='utf-8') as f:
                self.changelog_text.insert('1.0', f.read())
        except FileNotFoundError:
            self.changelog_text.insert('1.0', "Changelog not found.")
        except Exception as e:
            self.changelog_text.insert('1.0', f"Error reading changelog: {e}")
        finally:
            self.changelog_text.configure(state=tk.DISABLED)

    def _save_and_confirm_ram(self):
        try:
            int(self.ram_max_val_var.get())
            int(self.ram_min_val_var.get())
            self._save_config()
            messagebox.showinfo("Saved", "Memory settings saved. They will be applied on the next server start.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Memory values must be whole numbers.")

    def _browse_java_path(self):
        filepath = filedialog.askopenfilename(title="Select Java Executable", filetypes=(("Executable files", "*.exe"), ("All files", "*.* ")))
        if filepath:
            self.java_path_var.set(filepath)
            self._save_config()
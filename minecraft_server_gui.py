import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
import os
import psutil
import json
import shutil
import glob
import sys
import re
import uuid
import time
import math
import threading
import subprocess
from PIL import Image, ImageTk

from gui.widgets import CollapsiblePane, ToolTip, CustomDropdownMenu
from utils.constants import *
from utils.helpers import format_size, get_folder_size, get_local_ip
from utils.api_client import fetch_player_avatar_image, fetch_player_uuid, download_server_jar, get_server_versions
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
        master.configure(bg=PRIMARY_BG)
        
        self.style = ttk.Style()
        self.style.theme_use('default')

        self._load_config_or_run_setup()

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
            self.transition_in_progress = False
            self.placeholder_avatar = self._create_placeholder_avatar(size=(24,24))
            self.avatar_cache = {}
            self.mod_data = []
            self.player_uuids = {}
            self.stats_files = {}
            self.current_mod_config_path = None

            # --- Build UI ---
            main_app_frame = ttk.Frame(self.master, style='TFrame')
            main_app_frame.pack(fill=tk.BOTH, expand=True)
            self._configure_styles()
            self._create_main_layout(main_app_frame)

            self._show_view('control')
            self._update_server_status_display()
            self._update_dashboard_info()
            self.master.after(2000, self._update_resource_usage) # Start resource monitor loop

        except Exception as e:
            import traceback
            error_info = traceback.format_exc()
            messagebox.showerror("Fatal GUI Error", f"A critical error occurred while building the main interface:\n\n{e}\n\nDetails:\n{error_info}")

    def _create_main_layout(self, parent_frame):
        self.sidebar_frame = ttk.Frame(parent_frame, width=200, style='Card.TFrame')
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10,0), pady=10)
        self.sidebar_frame.pack_propagate(False)

        self.top_bar_frame = ttk.Frame(parent_frame, height=70, style='Header.TFrame')
        self.top_bar_frame.pack(side=tk.TOP, fill=tk.X, padx=(5,10), pady=(10,5))
        self.top_bar_frame.pack_propagate(False)
        self.top_bar_frame.columnconfigure(0, weight=1)
        self.top_bar_frame.columnconfigure(1, weight=0)
        
        self.server_title_label = ttk.Label(self.top_bar_frame, text="Minecraft Server Dashboard", font=FONT_UI_TITLE, style='Title.TLabel')
        self.server_title_label.grid(row=0, column=0, sticky='ew', padx=(15, 5), pady=5)

        top_bar_actions_frame = ttk.Frame(self.top_bar_frame, style='Header.TFrame')
        top_bar_actions_frame.grid(row=0, column=1, sticky='e', padx=(0, 15), pady=5)

        self.server_status_label = ttk.Label(top_bar_actions_frame, text="Status: Offline", style='StatusOffline.TLabel')
        self.server_status_label.pack(side=tk.LEFT, padx=(0,15))
        
        self.restart_button = ttk.Button(top_bar_actions_frame, text="Restart Server", command=self.restart_server, style="Accent2.TButton", state=tk.DISABLED)
        self.restart_button.pack(side=tk.LEFT)

        self.content_area_frame = ttk.Frame(parent_frame, style='TFrame')
        self.content_area_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,10), pady=(5,10))
        self.transition_overlay = ttk.Frame(self.content_area_frame, style='TransitionOverlay.TFrame')

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
            frame = ttk.Frame(self.content_area_frame, style='TFrame', padding=0)
            self.view_frames[view_info['id']] = frame
            view_info['create_method'](frame)
            btn = ttk.Button(self.sidebar_frame, text=view_info['text'], 
                             command=lambda v_id=view_info['id']: self._show_view(v_id),
                             style='Sidebar.TButton')
            btn.pack(fill=tk.X, padx=10, pady=5, ipady=5)
            self.sidebar_buttons[view_info['id']] = btn

    def _create_setup_wizard(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        
        self._configure_styles()
        setup_frame = ttk.Frame(self.master, style='TFrame', padding=(40, 20))
        setup_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(setup_frame, text="Minecraft Server Setup", font=FONT_UI_TITLE, style='Title.TLabel', background=PRIMARY_BG).pack(pady=(10, 20))

        # --- Setup Mode Selection ---
        mode_frame = ttk.Frame(setup_frame, style='TFrame')
        mode_frame.pack(pady=10, fill=tk.X, padx=20)
        self.setup_mode = tk.StringVar(value="install")
        
        install_radio = ttk.Radiobutton(mode_frame, text="Install New Server", variable=self.setup_mode, value="install", command=self._toggle_setup_view, style='Switch.TCheckbutton')
        install_radio.pack(side=tk.LEFT, padx=10)
        existing_radio = ttk.Radiobutton(mode_frame, text="Use Existing Server", variable=self.setup_mode, value="existing", command=self._toggle_setup_view, style='Switch.TCheckbutton')
        existing_radio.pack(side=tk.LEFT, padx=10)

        # --- Frames for each mode ---
        self.install_frame = ttk.Frame(setup_frame, style='TFrame')
        self.install_frame.pack(fill=tk.X, expand=True, pady=5)
        self.existing_frame = ttk.Frame(setup_frame, style='TFrame')

        # --- Widgets for "Install New Server" ---
        ttk.Label(self.install_frame, text="1. Select Server Type", font=FONT_UI_HEADER, background=PRIMARY_BG).pack(anchor='w', pady=(10,5), padx=20)
        server_types = ["Vanilla", "Paper", "Spigot", "Forge", "Fabric"]
        self.server_type_var = tk.StringVar(value=server_types[0])
        type_menu = CustomDropdownMenu(self.install_frame, self.server_type_var, server_types, style_prefix="Dropdown")
        type_menu.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(self.install_frame, text="2. Select Minecraft Version", font=FONT_UI_HEADER, background=PRIMARY_BG).pack(anchor='w', pady=(10,5), padx=20)
        self.server_version_var = tk.StringVar()
        self.version_menu = CustomDropdownMenu(self.install_frame, self.server_version_var, ["Loading..."], style_prefix="Dropdown")
        self.version_menu.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(self.install_frame, text="3. Choose Parent Directory", font=FONT_UI_HEADER, background=PRIMARY_BG).pack(anchor='w', pady=(10,5), padx=20)
        install_location_frame = ttk.Frame(self.install_frame, style='TFrame')
        install_location_frame.pack(fill=tk.X, padx=20, pady=5)
        self.install_location_var = tk.StringVar()
        ttk.Entry(install_location_frame, textvariable=self.install_location_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(install_location_frame, text="Browse...", command=self._browse_install_location, style="Accent.TButton").pack(side=tk.LEFT, padx=(5,0))
        
        ttk.Label(self.install_frame, text="4. Name Server Folder", font=FONT_UI_HEADER, background=PRIMARY_BG).pack(anchor='w', pady=(10,5), padx=20)
        self.server_name_var = tk.StringVar()
        self.server_name_entry = ttk.Entry(self.install_frame, textvariable=self.server_name_var)
        self.server_name_entry.pack(fill=tk.X, padx=20, pady=5)
        
        self.server_version_var.trace_add('write', self._update_default_folder_name)
        self.server_type_var.trace_add('write', self._update_server_versions)
        
        # --- Widgets for "Use Existing Server" ---
        ttk.Label(self.existing_frame, text="1. Choose Existing Server Location", font=FONT_UI_HEADER, background=PRIMARY_BG).pack(anchor='w', pady=(10,5), padx=20)
        existing_location_frame = ttk.Frame(self.existing_frame, style='TFrame')
        existing_location_frame.pack(fill=tk.X, padx=20, pady=5)
        self.existing_location_var = tk.StringVar()
        ttk.Entry(existing_location_frame, textvariable=self.existing_location_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(existing_location_frame, text="Browse...", command=self._browse_existing_location, style="Accent.TButton").pack(side=tk.LEFT, padx=(5,0))

        # --- Action Button & Progress ---
        self.action_button = ttk.Button(setup_frame, text="Download and Install Server", command=self._start_setup_action, style="Accent.TButton")
        self.action_button.pack(pady=(30, 10), ipady=10, fill=tk.X, padx=20)
        self.progress_bar = ttk.Progressbar(setup_frame, orient='horizontal', mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=20, pady=5)
        self.status_label = ttk.Label(setup_frame, text="Ready to begin.", font=FONT_UI_NORMAL, background=PRIMARY_BG, foreground=TEXT_SECONDARY)
        self.status_label.pack(pady=10)

        self._toggle_setup_view() # Set initial view
        self._update_server_versions() # Initial version load

    def _update_server_versions(self, *args):
        server_type = self.server_type_var.get()
        self.server_version_var.set("Loading...")
        self.version_menu.button.config(state=tk.DISABLED)
        threading.Thread(target=self._fetch_and_update_versions, args=(server_type,), daemon=True).start()

    def _fetch_and_update_versions(self, server_type):
        versions_data = get_server_versions(server_type)
        versions = [v['version'] for v in versions_data] if versions_data else []
        
        def update_ui():
            if versions:
                self.version_menu.update_options(versions)
                self.server_version_var.set(versions[0])
                self.version_menu.button.config(state=tk.NORMAL)
            else:
                self.server_version_var.set("Error fetching versions")
        
        if hasattr(self, 'master'):
            self.master.after(0, update_ui)

    def _toggle_setup_view(self):
        mode = self.setup_mode.get()
        if mode == "install":
            self.existing_frame.pack_forget()
            self.install_frame.pack(fill=tk.X, expand=True, pady=5)
            self.action_button.config(text="Download and Install Server")
            self.status_label.config(text="Ready to begin installation.")
        else: # existing
            self.install_frame.pack_forget()
            self.existing_frame.pack(fill=tk.X, expand=True, pady=5)
            self.action_button.config(text="Use This Folder")
            self.status_label.config(text="Select an existing server folder.")
            
    def _update_default_folder_name(self, *args):
        try:
            # Check if the widget exists before trying to set its variable.
            if hasattr(self, 'server_name_entry') and self.server_name_entry.winfo_exists():
                server_type = self.server_type_var.get()
                version = self.server_version_var.get()
                self.server_name_var.set(f"{server_type.lower()}-server-{version}")
        except tk.TclError:
            # This can still happen if the window is being destroyed.
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
        self.action_button.config(state=tk.DISABLED)
        mode = self.setup_mode.get()
        if mode == "install":
            if not self.install_location_var.get() or not self.server_name_var.get():
                messagebox.showerror("Error", "Please select a parent directory and provide a folder name.")
                self.action_button.config(state=tk.NORMAL)
                return
            threading.Thread(target=self._perform_server_installation, daemon=True).start()
        else: # existing
            threading.Thread(target=self._use_existing_server, daemon=True).start()

    def _use_existing_server(self):
        try:
            server_path = self.existing_location_var.get()
            if not server_path:
                messagebox.showerror("Error", "Please select an existing server directory.")
                return

            # Validate it's a server folder
            jar_files = glob.glob(os.path.join(server_path, '*.jar'))
            properties_file = os.path.join(server_path, 'server.properties')

            if not jar_files or not os.path.exists(properties_file):
                messagebox.showerror("Invalid Folder", "The selected folder does not appear to be a valid Minecraft server. (Missing .jar or server.properties)")
                return

            self.master.after(0, self.status_label.config, {'text': "Configuration saved! Launching..."})
            self.server_path = server_path
            self.server_type = self._detect_server_type(server_path)
            self._save_config()
            time.sleep(1)
            self.master.after(0, self._initialize_main_gui)

        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        finally:
            if hasattr(self, 'action_button') and self.action_button.winfo_exists():
                self.master.after(0, self.action_button.config, {'state': tk.NORMAL})

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
                if not messagebox.askyesno("Warning", "The destination folder is not empty. Files may be overwritten. Continue?"):
                    raise Exception("Installation cancelled by user.")

            self.master.after(0, self.status_label.config, {'text': f"Creating directory: {os.path.basename(install_path)}"})
            os.makedirs(install_path, exist_ok=True)
            
            self.master.after(0, self.status_label.config, {'text': f"Downloading {server_type} {server_version}..."})
            download_server_jar(server_type, server_version, jar_path, lambda p: self.master.after(0, self.progress_bar.config, {'value': p}))
            
            self.master.after(0, self.status_label.config, {'text': "Generating server files..."})
            self.master.after(0, self.progress_bar.config, {'value': 0})
            
            # Different server types have different installer arguments
            initial_run_command = ['java', '-jar', jar_name]
            if server_type == 'forge':
                initial_run_command.append('--installServer')
            else:
                initial_run_command.append('--nogui')

            process = subprocess.Popen(initial_run_command, cwd=install_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            try:
                stdout, stderr = process.communicate(timeout=600) # Increased timeout to 10 mins
                
                # For Forge, success is the installer finishing and creating the run script.
                if server_type == 'forge':
                    run_script_path = os.path.join(install_path, 'run.bat') if sys.platform == "win32" else os.path.join(install_path, 'run.sh')
                    if not os.path.exists(run_script_path):
                         # Check the exit code as a fallback
                         if process.returncode != 0:
                             raise RuntimeError(f"Forge installer failed with exit code {process.returncode} and did not create a run script.\n\nLOG:\n{stdout}\n{stderr}")
                         else:
                             # If exit code is 0 but script is missing, it's still an error.
                             raise RuntimeError(f"Forge installer finished but the required run script was not created.\n\nLOG:\n{stdout}\n{stderr}")
                else: # For other server types, check for EULA generation
                    if process.returncode != 0 and 'eula' not in (stdout + stderr).lower():
                        raise RuntimeError(f"Server process failed. Log:\n{stderr or stdout}")

            except subprocess.TimeoutExpired:
                process.kill()
                # If it times out, check one last time if Forge succeeded anyway
                run_script_path = os.path.join(install_path, 'run.bat') if sys.platform == "win32" else os.path.join(install_path, 'run.sh')
                if server_type == 'forge' and os.path.exists(run_script_path):
                    self.log_to_console("Forge installer timed out but seems to have succeeded. Continuing...\n", "warning")
                else:
                    raise RuntimeError("Server setup timed out (10+ min). Please check logs or try again.")

            # The eula.txt part only applies to non-Forge servers on first run.
            # Forge installation doesn't create eula.txt; the first server launch does.
            if server_type != 'forge':
                eula_path = os.path.join(install_path, "eula.txt")
                self.master.after(0, self.status_label.config, {'text': "Accepting EULA..."})
                time.sleep(1) # Give a moment for eula.txt to appear
                if not os.path.exists(eula_path):
                    self.log_to_console("eula.txt was not created. It will need to be accepted on the first server launch.\n", "warning")
                else:
                    with open(eula_path, 'r+') as f:
                        content = f.read().replace("eula=false", "eula=true")
                        f.seek(0); f.write(content); f.truncate()
            
            self.master.after(0, self.status_label.config, {'text': "Setup complete! Launching..."})
            self.server_path = install_path
            self.server_type = server_type
            self._save_config()
            time.sleep(1)
            self.master.after(0, self._initialize_main_gui)

        except Exception as e:
            messagebox.showerror("Installation Failed", str(e))
            self.master.after(0, self.status_label.config, {'text': "Error during installation."})
        finally:
            self.master.after(0, self.action_button.config, {'state': tk.NORMAL})
            
    def _save_config(self):
        self.config_manager.set("server_path", self.server_path)
        self.config_manager.set("server_type", self.server_type)
        self.config_manager.set("ram_min", self.ram_min_val_var.get())
        self.config_manager.set("ram_max", self.ram_max_val_var.get())
        self.config_manager.set("ram_unit", self.ram_unit_var.get())
        self.config_manager.set("java_path", self.java_path_var.get())
        self.config_manager.save()

    def _configure_styles(self):
        self.style.configure('.', background=PRIMARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL, borderwidth=0, focusthickness=0, highlightthickness=0)
        self.style.configure('TFrame', background=PRIMARY_BG)
        self.style.configure('Card.TFrame', background=SECONDARY_BG)
        self.style.configure('Header.TFrame', background=TERTIARY_BG)
        self.style.configure('CardInner.TFrame', background=SECONDARY_BG)
        self.style.configure('TransitionOverlay.TFrame', background=PRIMARY_BG)
        
        self.style.configure('TLabel', background=SECONDARY_BG, foreground=TEXT_PRIMARY, padding=2)
        self.style.configure('Title.TLabel', background=TERTIARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_TITLE, padding=(5,15,5,10))
        self.style.configure('Header.TLabel', background=SECONDARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_HEADER)
        
        self.style.configure('StatusOnline.TLabel', background=TERTIARY_BG, foreground=SUCCESS_COLOR, font=FONT_UI_BOLD)
        self.style.configure('StatusOffline.TLabel', background=TERTIARY_BG, foreground=ERROR_FG_CUSTOM, font=FONT_UI_BOLD)
        self.style.configure('StatusStarting.TLabel', background=TERTIARY_BG, foreground=WARNING_FG_CUSTOM, font=FONT_UI_BOLD)

        btn_padding = [14, 10]
        self.style.configure('Accent.TButton', font=FONT_UI_BOLD, padding=btn_padding, relief='flat', borderwidth=0)
        self.style.map('Accent.TButton', background=[('pressed', ACCENT_HOVER), ('active', ACCENT_HOVER), ('', ACCENT_COLOR)], foreground=[('', PRIMARY_BG)])
        
        self.style.configure('Accent2.TButton', font=FONT_UI_BOLD, padding=btn_padding, relief='flat', borderwidth=0)
        self.style.map('Accent2.TButton', background=[('pressed', ACCENT_COLOR), ('active', ACCENT_COLOR), ('', TERTIARY_BG)], foreground=[('', TEXT_PRIMARY)])
        
        self.style.configure('Sidebar.TButton', font=FONT_UI_BOLD, padding=[20, 10], relief='flat', anchor='w')
        self.style.map('Sidebar.TButton', background=[('pressed', ACCENT_HOVER), ('active', ACCENT_HOVER), ('selected', ACCENT_COLOR), ('', SECONDARY_BG)], foreground=[('', TEXT_PRIMARY)])
        
        self.style.configure('ActionRow.TButton', font=('Segoe UI', 10), padding=4, relief='flat')
        self.style.map('ActionRow.TButton', background=[('pressed', ACCENT_HOVER), ('active', ACCENT_HOVER), ('', TERTIARY_BG)], foreground=[('', TEXT_PRIMARY)])

        self.style.configure("Vertical.TScrollbar", background=SECONDARY_BG, troughcolor=PRIMARY_BG, bordercolor=TERTIARY_BG, arrowcolor=TEXT_SECONDARY)
        self.style.map("Vertical.TScrollbar", background=[("active", ACCENT_HOVER)], arrowcolor=[("pressed", ACCENT_COLOR)])
        
        self.style.configure('TEntry', fieldbackground=TERTIARY_BG, foreground=TEXT_PRIMARY, insertcolor=TEXT_PRIMARY, borderwidth=1, relief='solid', padding=8)
        self.style.map('TEntry', bordercolor=[('focus', ACCENT_COLOR), ('!focus', TERTIARY_BG)])
        
        self.style.map('TCombobox', fieldbackground=[('readonly', TERTIARY_BG)], foreground=[('readonly', TEXT_PRIMARY)], selectbackground=[('readonly', TERTIARY_BG)], selectforeground=[('readonly', TEXT_PRIMARY)])
        self.master.option_add("*TCombobox*Listbox*Background", SECONDARY_BG)
        self.master.option_add("*TCombobox*Listbox*Foreground", TEXT_PRIMARY)
        self.master.option_add("*TCombobox*Listbox*selectBackground", ACCENT_COLOR)
        self.master.option_add("*TCombobox*Listbox*selectForeground", TEXT_PRIMARY)
        self.style.configure('TMenubutton', background=SECONDARY_BG, foreground=TEXT_PRIMARY, padding=8, relief='flat', borderwidth=0)
        self.style.map('TMenubutton', background=[('active', TERTIARY_BG)])

        self.style.configure("Dropdown.TButton", font=FONT_UI_NORMAL, padding=8, relief='flat', borderwidth=0)
        self.style.map("Dropdown.TButton", background=[('active', TERTIARY_BG)])
        self.style.configure("Dropdown.TFrame", background=SECONDARY_BG)
        self.style.configure("Dropdown.Item.TButton", font=FONT_UI_NORMAL, padding=8, relief='flat', borderwidth=0)
        self.style.map("Dropdown.Item.TButton", background=[('active', ACCENT_HOVER)], foreground=[('active', TEXT_PRIMARY)])
        
        self.style.configure('Switch.TCheckbutton', font=FONT_UI_NORMAL, padding=5)
        self.style.map('Switch.TCheckbutton',
            indicatorcolor=[('selected', SUCCESS_COLOR), ('!selected', TEXT_SECONDARY)],
            background=[('active', SECONDARY_BG), ('', SECONDARY_BG)]
        )

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
        if self.transition_in_progress or self.active_view_id == view_id_to_show:
            return

        old_view_frame = self.view_frames.get(self.active_view_id)
        new_view_frame = self.view_frames.get(view_id_to_show)

        if new_view_frame:
            self.transition_in_progress = True

            if self.active_view_id:
                self.sidebar_buttons[self.active_view_id].state(['!selected'])
            self.sidebar_buttons[view_id_to_show].state(['selected'])

            self.transition_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.transition_overlay.lift()
            
            self.master.after(100, lambda: self._load_data_for_view(view_id_to_show))
            
            def switch_views():
                if old_view_frame:
                    old_view_frame.place_forget()
                new_view_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
                self.transition_overlay.place_forget()
                self.active_view_id = view_id_to_show 
                self.transition_in_progress = False
        
            self.master.after(250, switch_views)

    def _create_control_view_widgets(self, parent_frame):
        control_main_frame = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        control_main_frame.pack(fill=tk.BOTH, expand=True)
        control_main_frame.rowconfigure(1, weight=1)
        control_main_frame.columnconfigure(0, weight=1)

        # Top panels for actions and info
        top_frame = ttk.Frame(control_main_frame, style='Card.TFrame')
        top_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 5))
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)

        left_panel = ttk.Frame(top_frame, style='CardInner.TFrame', padding=(20, 15))
        left_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        ttk.Label(left_panel, text="Server Actions", font=FONT_UI_HEADER, style='Header.TLabel').pack(anchor='w', pady=(0, 15))
        self.start_button = ttk.Button(left_panel, text="Start Server", command=self.start_server_thread, style="Accent.TButton")
        self.start_button.pack(fill=tk.X, pady=5, ipady=8)
        self.stop_button = ttk.Button(left_panel, text="Stop Server", command=self.stop_server, style="Accent.TButton", state=tk.DISABLED)
        self.stop_button.pack(fill=tk.X, pady=5, ipady=8)

        right_panel = ttk.Frame(top_frame, style='CardInner.TFrame', padding=(20, 15))
        right_panel.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        ttk.Label(right_panel, text="Server Info", font=FONT_UI_HEADER, style='Header.TLabel').pack(anchor='w', pady=(0, 15))
        
        info_grid = ttk.Frame(right_panel, style='CardInner.TFrame')
        info_grid.pack(fill=tk.X)
        info_grid.columnconfigure(1, weight=1)

        def add_info_row(label_text, var_text):
            row_idx = info_grid.grid_size()[1]
            ttk.Label(info_grid, text=label_text, style='TLabel', background=SECONDARY_BG, font=FONT_UI_BOLD).grid(row=row_idx, column=0, sticky='w', padx=(0,10))
            label = ttk.Label(info_grid, text=var_text, style='TLabel', background=SECONDARY_BG, anchor='w')
            label.grid(row=row_idx, column=1, sticky='ew')
            return label

        self.motd_label = add_info_row("MOTD:", "N/A")
        self.version_label = add_info_row("Version:", "N/A")
        self.players_label = add_info_row("Players:", "N/A")
        
        # IP Address with Copy Button
        row_idx = info_grid.grid_size()[1]
        ttk.Label(info_grid, text="Server IP:", style='TLabel', background=SECONDARY_BG, font=FONT_UI_BOLD).grid(row=row_idx, column=0, sticky='w', padx=(0,10), pady=(5,0))
        ip_frame = ttk.Frame(info_grid, style='CardInner.TFrame')
        ip_frame.grid(row=row_idx, column=1, sticky='ew', pady=(5,0))
        self.ip_label = ttk.Label(ip_frame, text="N/A", style='TLabel', background=SECONDARY_BG)
        self.ip_label.pack(side=tk.LEFT, anchor='w')
        self.copy_ip_button = ttk.Button(ip_frame, text="Copy", command=self._copy_ip_to_clipboard, style="ActionRow.TButton")
        self.copy_ip_button.pack(side=tk.LEFT, padx=5)

        # Dashboard Console
        console_card = ttk.Frame(control_main_frame, style='Card.TFrame', padding=(15,10))
        console_card.grid(row=1, column=0, columnspan=1, sticky='nsew', pady=(5,0))
        ttk.Label(console_card, text="Live Console", font=FONT_UI_HEADER, style='Header.TLabel').pack(anchor='w', pady=(0, 5))
        self.dashboard_console_output_area = scrolledtext.ScrolledText(console_card, wrap=tk.WORD, height=10, bg=TERTIARY_BG, fg=TEXT_PRIMARY, relief='flat', borderwidth=0, font=FONT_CONSOLE_CUSTOM)
        self.dashboard_console_output_area.pack(fill=tk.BOTH, expand=True)
        self.dashboard_console_output_area.tag_config("error", foreground=ERROR_FG_CUSTOM)
        self.dashboard_console_output_area.tag_config("warning", foreground=WARNING_FG_CUSTOM)
        self.dashboard_console_output_area.tag_config("info", foreground=TEXT_SECONDARY)
        self.dashboard_console_output_area.tag_config("success", foreground=SUCCESS_COLOR)

        command_frame = ttk.Frame(console_card, style='Card.TFrame')
        command_frame.pack(fill=tk.X, pady=(10,0))
        self.console_command_entry = ttk.Entry(command_frame, font=FONT_UI_NORMAL)
        self.console_command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.console_command_entry.bind("<Return>", self.send_command_from_console_entry)
        self.console_send_btn = ttk.Button(command_frame, text="Send Command", command=self.send_command_from_console_button, style="Accent.TButton")
        self.console_send_btn.pack(side=tk.LEFT)

    def _copy_ip_to_clipboard(self):
        ip = self.ip_label.cget("text")
        if ip and ip != "N/A":
            self.master.clipboard_clear()
            self.master.clipboard_append(ip)
            self.log_to_console(f"Copied '{ip}' to clipboard.\n", "success")

    def _update_dashboard_info(self):
        if not self.server_path:
            return

        properties = {}
        if os.path.exists(self.server_properties_path):
            with open(self.server_properties_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        properties[key.strip()] = value.strip()

        motd = properties.get("motd", "A Minecraft Server")
        max_players = properties.get("max-players", "20")
        
        self.motd_label.config(text=motd)
        self.version_label.config(text=self.config_manager.get('server_version', 'N/A'))
        self.players_label.config(text=f"{len(self.players_connected)}/{max_players}")
        self.ip_label.config(text=get_local_ip())

    def _create_console_view_widgets(self, parent_frame):
        console_card = ttk.Frame(parent_frame, style='Card.TFrame', padding=(15,10))
        console_card.pack(fill=tk.BOTH, expand=True)
        ttk.Label(console_card, text="Full Server Console", font=FONT_UI_HEADER, style='Header.TLabel').pack(anchor='w', pady=(0, 5))
        self.full_console_output_area = scrolledtext.ScrolledText(console_card, wrap=tk.WORD, height=10, bg=TERTIARY_BG, fg=TEXT_PRIMARY, relief='flat', borderwidth=0, font=FONT_CONSOLE_CUSTOM)
        self.full_console_output_area.pack(fill=tk.BOTH, expand=True)
        self.full_console_output_area.tag_config("error", foreground=ERROR_FG_CUSTOM)
        self.full_console_output_area.tag_config("warning", foreground=WARNING_FG_CUSTOM)
        self.full_console_output_area.tag_config("info", foreground=TEXT_SECONDARY)
        self.full_console_output_area.tag_config("success", foreground=SUCCESS_COLOR)

        command_frame = ttk.Frame(console_card, style='Card.TFrame')
        command_frame.pack(fill=tk.X, pady=(10,0))
        self.command_entry = ttk.Entry(command_frame, font=FONT_UI_NORMAL)
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.command_entry.bind("<Return>", self.send_command_from_entry)
        self.send_btn = ttk.Button(command_frame, text="Send Command", command=self.send_command_from_button, style="Accent.TButton")
        self.send_btn.pack(side=tk.LEFT)

    def _create_properties_view_widgets(self, parent_frame):
        main_frame = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        top_frame = ttk.Frame(main_frame, style='CardInner.TFrame')
        top_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(top_frame, text="Server Properties", font=FONT_UI_HEADER, style='Header.TLabel').pack(side=tk.LEFT)
        self.save_properties_button = ttk.Button(top_frame, text="Save Changes", command=self.save_server_properties, style="Accent.TButton", state=tk.DISABLED)
        self.save_properties_button.pack(side=tk.RIGHT)
        
        # --- Canvas and Scrollbar for all properties ---
        canvas = tk.Canvas(main_frame, bg=SECONDARY_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.properties_scrollable_frame = ttk.Frame(canvas, style='CardInner.TFrame', padding=5)

        canvas_window = canvas.create_window((0, 0), window=self.properties_scrollable_frame, anchor="nw")

        def on_inner_frame_configure(event):
            # Update scrollregion whenever the inner frame's size changes.
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            # Update the inner frame's width to match the canvas's width.
            canvas.itemconfig(canvas_window, width=event.width)

        self.properties_scrollable_frame.bind("<Configure>", on_inner_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # --- Define all properties ---
        self._define_all_properties()

        # --- Create widgets from definitions ---
        self.property_widgets = {}
        for category, properties in self.properties_definitions.items():
            pane = CollapsiblePane(self.properties_scrollable_frame, text=category)
            pane.pack(fill='x', pady=5, padx=2)
            
            for prop_def in properties:
                self._add_property_control(pane.body, prop_def)

    def _add_property_control(self, parent, prop_def):
        key = prop_def['key']
        var = None
        
        prop_frame = ttk.Frame(parent, style='CardInner.TFrame', padding=(5, 8))
        prop_frame.pack(fill=tk.X)
        prop_frame.columnconfigure(0, weight=1, minsize=200)
        prop_frame.columnconfigure(1, weight=2)
        
        # Left side: Label and Description
        info_frame = ttk.Frame(prop_frame, style='CardInner.TFrame')
        info_frame.grid(row=0, column=0, sticky='w', padx=(0, 10))
        label = ttk.Label(info_frame, text=key, font=FONT_UI_BOLD, style='TLabel')
        label.pack(anchor='w')
        desc = ttk.Label(info_frame, text=prop_def.get('desc', ''), foreground=TEXT_SECONDARY, wraplength=250, justify=tk.LEFT)
        desc.pack(anchor='w')

        # Right side: Widget
        widget_frame = ttk.Frame(prop_frame, style='CardInner.TFrame')
        widget_frame.grid(row=0, column=1, sticky='e')

        prop_type = prop_def.get('type', 'string')

        if prop_type == 'boolean':
            var = tk.BooleanVar(value=prop_def.get('default'))
            widget = ttk.Checkbutton(widget_frame, variable=var, style='Switch.TCheckbutton')
            widget.pack(anchor='w')
        elif prop_type == 'enum':
            var = tk.StringVar(value=str(prop_def.get('default')))
            widget = ttk.Combobox(widget_frame, textvariable=var, values=prop_def.get('values', []), state='readonly', font=FONT_UI_NORMAL)
            widget.pack(fill=tk.X, expand=True)
        elif prop_type == 'integer':
            var = tk.StringVar(value=str(prop_def.get('default')))
            widget = ttk.Entry(widget_frame, textvariable=var, font=FONT_UI_NORMAL)
            widget.pack(fill=tk.X, expand=True)
        else: # String
            var = tk.StringVar(value=str(prop_def.get('default')))
            widget = ttk.Entry(widget_frame, textvariable=var, font=FONT_UI_NORMAL)
            widget.pack(fill=tk.X, expand=True)

        var.trace_add("write", self._on_property_change)
        self.property_widgets[key] = var
            
    def load_server_properties(self):
        # Read the existing properties file into a dictionary
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
        
        # Set widget values based on the file or defaults
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
                    else: # Not in file, use definition's default
                        if isinstance(var, tk.BooleanVar):
                            var.set(prop_def.get('default', False))
                        else:
                            var.set(prop_def.get('default', ''))
        
        self.master.after(100, lambda: self.save_properties_button.config(state='disabled'))

    def _on_property_change(self, *args):
        if hasattr(self, 'save_properties_button'):
            self.save_properties_button.config(state='normal')

    def save_server_properties(self):
        try:
            # Re-generate the entire properties file from our definitions
            # This ensures consistency and includes all properties.
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
                        content_lines.append(f"{key}={var.get()}")
                content_lines.append("")

            with open(self.server_properties_path, 'w') as f:
                f.write("\n".join(content_lines))

            messagebox.showinfo("Success", "server.properties saved successfully.")
            self.save_properties_button.config(state='disabled')
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
            ttk.Label(parent_frame, text="Matplotlib is not installed.\nResource graphs are unavailable.", justify=tk.CENTER).pack(pady=20)
            return
            
        resources_frame = ttk.Frame(parent_frame, style='TFrame')
        resources_frame.pack(fill=tk.BOTH, expand=True)
        
        fig = Figure(figsize=(5, 2), dpi=100, facecolor=SECONDARY_BG)
        self.ax_cpu = fig.add_subplot(121)
        self.ax_ram = fig.add_subplot(122)

        for ax, title in [(self.ax_cpu, 'CPU Usage (%)'), (self.ax_ram, 'RAM Usage (%)')]:
            ax.set_facecolor(SECONDARY_BG)
            ax.set_title(title, color=TEXT_PRIMARY, fontdict={'family': FONT_UI_NORMAL[0], 'size': FONT_UI_BOLD[1]})
            ax.tick_params(axis='y', colors=TEXT_SECONDARY, labelsize=8)
            ax.tick_params(axis='x', colors=SECONDARY_BG) 
            for spine in ['bottom', 'top', 'right']: ax.spines[spine].set_color(SECONDARY_BG)
            ax.spines['left'].set_color(TEXT_SECONDARY)
            ax.set_ylim(0, 100)

        self.cpu_history = [0.0] * 50
        self.ram_history = [0.0] * 50
        self.line_cpu, = self.ax_cpu.plot(self.cpu_history, color=ACCENT_COLOR, lw=2)
        self.line_ram, = self.ax_ram.plot(self.ram_history, color=SUCCESS_COLOR, lw=2)

        fig.tight_layout(pad=2.0)
        self.resource_canvas = FigureCanvasTkAgg(fig, master=resources_frame)
        self.resource_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.resource_canvas.draw()
        
        info_frame = ttk.Frame(resources_frame, style='TFrame')
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.ram_label = ttk.Label(info_frame, text="RAM: N/A", font=FONT_UI_NORMAL, style='TLabel', background=PRIMARY_BG)
        self.ram_label.pack(side=tk.LEFT, expand=True)
        self.cpu_percent_label = ttk.Label(info_frame, text="CPU: N/A", font=FONT_UI_NORMAL, style='TLabel', background=PRIMARY_BG)
        self.cpu_percent_label.pack(side=tk.LEFT, expand=True)

    def _update_resource_usage(self):
        if not self.server_handler.is_running():
            if matplotlib_available:
                self.cpu_history = [0.0] * 50
                self.ram_history = [0.0] * 50
                if hasattr(self, 'line_cpu'): self.line_cpu.set_ydata(self.cpu_history)
                if hasattr(self, 'line_ram'): self.line_ram.set_ydata(self.ram_history)
                if hasattr(self, 'resource_canvas') and self.resource_canvas.get_tk_widget().winfo_exists():
                    self.resource_canvas.draw()
                if hasattr(self, 'cpu_percent_label') and self.cpu_percent_label.winfo_exists():
                    self.cpu_percent_label.config(text="CPU: 0.0%")
                if hasattr(self, 'ram_label') and self.ram_label.winfo_exists():
                    self.ram_label.config(text="RAM: 0MB (0.0%)")
            self.master.after(2000, self._update_resource_usage)
            return

        try:
            pid = self.server_handler.get_pid()
            if pid is None:
                return
            proc = psutil.Process(pid)
            cpu_count = psutil.cpu_count() or 1
            cpu_percent = proc.cpu_percent(interval=None) / cpu_count
            self.cpu_history.pop(0)
            self.cpu_history.append(float(cpu_percent))
            
            mem_info = proc.memory_info()
            ram_percent = (mem_info.rss / psutil.virtual_memory().total) * 100
            self.ram_history.pop(0)
            self.ram_history.append(ram_percent)

            if matplotlib_available and hasattr(self, 'resource_canvas') and self.resource_canvas.get_tk_widget().winfo_exists():
                self.line_cpu.set_ydata(self.cpu_history)
                self.line_ram.set_ydata(self.ram_history)
                
                self.ax_cpu.draw_artist(self.ax_cpu.patch)
                self.ax_cpu.draw_artist(self.line_cpu)
                self.ax_ram.draw_artist(self.ax_ram.patch)
                self.ax_ram.draw_artist(self.line_ram)
                self.resource_canvas.blit(self.ax_cpu.bbox)
                self.resource_canvas.blit(self.ax_ram.bbox)

                self.cpu_percent_label.config(text=f"CPU: {cpu_percent:.1f}%")
                used_mem_mb = mem_info.rss / (1024**2)
                self.ram_label.config(text=f"RAM: {used_mem_mb:.0f}MB ({ram_percent:.1f}%)")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            self.log_to_console(f"Resource monitor error: {e}\n", "error")
        finally:
            self.master.after(2000, self._update_resource_usage)

    def log_to_console(self, msg, level="info"):
        if hasattr(self, 'full_console_output_area') and self.full_console_output_area.winfo_exists():
            self.full_console_output_area.insert(tk.END, msg, level)
            self.full_console_output_area.see(tk.END)

        if hasattr(self, 'dashboard_console_output_area') and self.dashboard_console_output_area.winfo_exists():
            self.dashboard_console_output_area.insert(tk.END, msg, level)
            self.dashboard_console_output_area.see(tk.END)

        self.process_server_output(msg, level)
        
    def start_server_thread(self):
        self.server_handler.start()
        self._update_server_status_display()

    def stop_server(self):
        self.server_handler.stop()
        self.stop_button.config(state=tk.DISABLED)
        self.server_status_label.config(text="Status: Stopping...", style='StatusStarting.TLabel')
        self._update_server_status_display()

    def on_server_stop(self, silent=False):
        self._update_server_status_display()
        if not silent:
            self.log_to_console("Server has stopped.\n", "info")

    def process_server_output(self, line, level):
        clean_line = line.strip()
        if not clean_line: return

        if self.expecting_player_list_next_line:
            current_players = [p.strip() for p in clean_line.split(',') if p.strip()]
            self.players_connected = current_players
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
            except IndexError:
                self.ops_list = []
            self._refresh_ops_display()
        elif "There are no opped players" in clean_line:
            self.ops_list = []
            self._refresh_ops_display()
        elif ("Made" in clean_line and "a server operator" in clean_line) or "De-opped" in clean_line:
            self.master.after(200, self.update_ops_list)
        elif "You need to agree to the EULA" in clean_line:
            # This is a key message that appears when the EULA needs to be accepted.
            self.log_to_console("EULA needs to be accepted. Attempting to accept automatically...\n", "warning")
            self.master.after(500, self._handle_eula_shutdown) # Use master.after to avoid thread issues

        if 'Done' in clean_line and 'For help, type "help"' in clean_line:
            self.master.after(0, self._update_server_status_display)

    def _handle_eula_shutdown(self):
        """Handles the full sequence of accepting the EULA and resetting server state."""
        self._accept_eula_file()
        # Now, forcefully update the GUI state to reflect that the server has stopped.
        # We call with silent=True because we've already logged a more specific message.
        if self.server_handler.server_running:
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
                f.seek(0)
                f.write(content)
                f.truncate()
            self.log_to_console("EULA has been automatically accepted. The server has stopped. Please start it again.\n", "success")
        except Exception as e:
            self.log_to_console(f"Failed to automatically accept EULA: {e}\n", "error")

    def send_command_from_entry(self, event=None):
        self.send_command_from_button()

    def send_command_from_button(self):
        cmd = self.command_entry.get().strip()
        if cmd:
            self.server_handler.send_command(cmd)
            self.command_entry.delete(0, tk.END)

    def send_command_from_console_entry(self, event=None):
        self.send_command_from_console_button()

    def send_command_from_console_button(self):
        cmd = self.console_command_entry.get().strip()
        if cmd:
            self.server_handler.send_command(cmd)
            self.console_command_entry.delete(0, tk.END)

    def restart_server(self):
        if self.server_handler.server_running:
            self.stop_server()
            self.master.after(2000, self._check_if_stopped_then_start)
            self.server_status_label.config(text="Status: Restarting...", style='StatusStarting.TLabel')
            self.restart_button.config(state=tk.DISABLED)

    def _check_if_stopped_then_start(self):
        if not self.server_handler.server_running:
            self.log_to_console("Server stopped, restarting...\n", "info")
            self.start_server_thread()
        else:
            self.log_to_console("Waiting for server to stop...\n", "info")
            self.master.after(2000, self._check_if_stopped_then_start)

    def _update_server_status_display(self):
        is_online = self.server_handler.server_running and self.server_handler.server_process and self.server_handler.server_process.poll() is None
        
        status_text, status_style = ("Status: Online", 'StatusOnline.TLabel') if is_online else ("Status: Offline", 'StatusOffline.TLabel')
        if self.server_handler.server_running and not is_online:
             status_text, status_style = ("Status: Starting...", 'StatusStarting.TLabel')

        start_state, stop_state, restart_state = (tk.DISABLED, tk.NORMAL, tk.NORMAL) if is_online else (tk.NORMAL, tk.DISABLED, tk.DISABLED)
        
        if hasattr(self, 'server_status_label'): self.server_status_label.config(text=status_text, style=status_style)
        if hasattr(self, 'restart_button'): self.restart_button.config(state=restart_state)
        if hasattr(self, 'stop_button'): self.stop_button.config(state=stop_state)
        if hasattr(self, 'start_button'): self.start_button.config(state=start_state)
        if hasattr(self, 'console_send_btn'): self.console_send_btn.config(state=tk.NORMAL if is_online else tk.DISABLED)
        if hasattr(self, 'console_command_entry'): self.console_command_entry.config(state=tk.NORMAL if is_online else tk.DISABLED)

    def _create_placeholder_avatar(self, size=(24, 24)):
        return ImageTk.PhotoImage(Image.new('RGBA', size, (0,0,0,0)))

    def _update_avatar_label(self, label, photo_image):
        if label.winfo_exists():
            label.configure(image=photo_image)
            label.image = photo_image

    def _fetch_player_avatar(self, player_identifier, avatar_label, size=(24, 24)):
        if not player_identifier or player_identifier == 'N/A': return
        if player_identifier in self.avatar_cache:
            self.master.after(0, self._update_avatar_label, avatar_label, self.avatar_cache[player_identifier])
            return
        if self.placeholder_avatar:
             self.master.after(0, self._update_avatar_label, avatar_label, self.placeholder_avatar)
        threading.Thread(target=self._fetch_player_avatar_thread, args=(player_identifier, avatar_label, size), daemon=True).start()

    def _fetch_player_avatar_thread(self, player_identifier, avatar_label, size):
        photo_img = fetch_player_avatar_image(player_identifier, size)
        if photo_img:
            self.avatar_cache[player_identifier] = photo_img
            self.master.after(0, self._update_avatar_label, avatar_label, photo_img)
            
    def _create_scrollable_list(self, parent_frame):
        outer_frame = ttk.Frame(parent_frame, style='CardInner.TFrame')
        outer_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer_frame, bg=SECONDARY_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
        scrollable_frame = ttk.Frame(canvas, style='CardInner.TFrame')
        scrollable_frame.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        return scrollable_frame
        
    def _create_players_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        card.pack(fill=tk.BOTH, expand=True)
        title_frame = ttk.Frame(card, style='CardInner.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(title_frame, text="Connected Players", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(title_frame, text='Refresh List', command=self.update_players_list, style='Accent.TButton').pack(side=tk.RIGHT)
        self.scrollable_players_list_frame = self._create_scrollable_list(card)
        
        self.player_context_menu = tk.Menu(self.master, tearoff=0, background=SECONDARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL)
        self.player_context_menu.add_command(label="⭐ Op", command=lambda: self._context_op_player(True))
        self.player_context_menu.add_command(label="⚡ De-Op", command=lambda: self._context_op_player(False))
        self.player_context_menu.add_separator()
        self.player_context_menu.add_command(label="👢 Kick", command=self._context_kick_player)
        self.player_context_menu.add_command(label="🚫 Ban", command=self._context_ban_player)

    def update_players_list(self):
        if self.server_handler.server_running: self.server_handler.send_command("list")
        else:
            self.players_connected = []
            self._refresh_players_display()

    def _refresh_players_display(self):
        if not hasattr(self, 'scrollable_players_list_frame'): return
        for widget in self.scrollable_players_list_frame.winfo_children(): widget.destroy()
        if not self.players_connected:
            ttk.Label(self.scrollable_players_list_frame, text="No players currently online.").pack(pady=10)
        else:
            for player_name in self.players_connected:
                row = ttk.Frame(self.scrollable_players_list_frame, style='CardInner.TFrame', padding=(10,8))
                row.pack(fill=tk.X, expand=True, pady=2, padx=2)
                avatar_label = ttk.Label(row)
                avatar_label.pack(side=tk.LEFT, padx=(0,8))
                self._fetch_player_avatar(player_name, avatar_label)
                name_label = ttk.Label(row, text=player_name, anchor='w')
                name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                for widget in [row, avatar_label, name_label]:
                    widget.bind("<Button-3>", lambda e, p=player_name: self._show_player_context_menu(e, p))
        self._update_dashboard_info()

    def _show_player_context_menu(self, event, player_name):
        self.selected_player_name = player_name
        is_op = player_name in self.ops_list
        self.player_context_menu.entryconfigure("⭐ Op", state=tk.DISABLED if is_op else tk.NORMAL)
        self.player_context_menu.entryconfigure("⚡ De-Op", state=tk.NORMAL if is_op else tk.DISABLED)
        self.player_context_menu.post(event.x_root, event.y_root)
        
    def _context_op_player(self, make_op: bool):
        if self.selected_player_name:
            cmd = "op" if make_op else "deop"
            self.server_handler.send_command(f"{cmd} {self.selected_player_name}")
            self.master.after(500, self.update_ops_list)
    
    def _context_kick_player(self):
        if self.selected_player_name:
            self.server_handler.send_command(f"kick {self.selected_player_name}")
            self.master.after(200, self.update_players_list)

    def _context_ban_player(self):
        if self.selected_player_name:
            self.server_handler.send_command(f"ban {self.selected_player_name}")
            self.master.after(200, self.update_players_list)

    def _create_ops_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        card.pack(fill=tk.BOTH, expand=True)
        
        title_frame = ttk.Frame(card, style='CardInner.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(title_frame, text="Operators (Ops)", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(title_frame, text='Refresh List', command=self.update_ops_list, style='Accent.TButton').pack(side=tk.RIGHT)
        
        self.scrollable_ops_list_frame = self._create_scrollable_list(card)
        
        add_frame = ttk.Frame(card, style='CardInner.TFrame', padding=(0,10,0,0))
        add_frame.pack(fill=tk.X)
        self.op_entry = ttk.Entry(add_frame, font=FONT_UI_NORMAL)
        self.op_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.add_op_button = ttk.Button(add_frame, text="Add", command=self._add_op, style="Accent.TButton")
        self.add_op_button.pack(side=tk.LEFT)

    def update_ops_list(self):
        if self.server_handler.server_running:
            self.server_handler.send_command("op list")
        else: # Read from file if offline
            if not self.server_path:
                self.ops_list = []
                self._refresh_ops_display()
                return
            ops_path = os.path.join(self.server_path, 'ops.json')
            if os.path.exists(ops_path):
                try:
                    with open(ops_path, 'r') as f:
                        self.ops_list = [op['name'] for op in json.load(f) if 'name' in op]
                except (json.JSONDecodeError, KeyError):
                    self.ops_list = []
            else:
                self.ops_list = []
            self._refresh_ops_display()

    def _refresh_ops_display(self):
        if not hasattr(self, 'scrollable_ops_list_frame'): return
        for widget in self.scrollable_ops_list_frame.winfo_children(): widget.destroy()

        if not self.ops_list:
            ttk.Label(self.scrollable_ops_list_frame, text="No operators defined.").pack(pady=10)
        else:
            for op_name in self.ops_list:
                row = ttk.Frame(self.scrollable_ops_list_frame, style='CardInner.TFrame', padding=(10,8))
                row.pack(fill=tk.X, expand=True, pady=2, padx=2)
                avatar_label = ttk.Label(row)
                avatar_label.pack(side=tk.LEFT, padx=(0,8))
                self._fetch_player_avatar(op_name, avatar_label)
                ttk.Label(row, text=op_name, anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)
                ttk.Button(row, text="⚡ De-Op", command=lambda p=op_name: self._deop_player(p), style="ActionRow.TButton").pack(side=tk.RIGHT)

    def _add_op(self):
        player_name = self.op_entry.get().strip()
        if not player_name:
            return

        if self.server_handler.server_running:
            self.server_handler.send_command(f"op {player_name}")
            self.op_entry.delete(0, tk.END)
        else:
            if not self.server_path:
                messagebox.showerror("Error", "Server path is not configured.")
                return
            self.add_op_button.config(state=tk.DISABLED, text="Adding...")
            threading.Thread(target=self._add_op_offline, args=(player_name,), daemon=True).start()

    def _add_op_offline(self, player_name):
        if not self.server_path:
            # This is a safeguard; the check is usually done before calling this method.
            self.master.after(0, messagebox.showerror, "Error", "Server path is not configured.")
            if hasattr(self, 'add_op_button') and self.add_op_button.winfo_exists():
                self.master.after(0, self.add_op_button.config, {'state': tk.NORMAL, 'text': 'Add'})
            return

        try:
            self.master.after(0, self.log_to_console, f"Fetching UUID for {player_name}...\n", "info")
            player_data = fetch_player_uuid(player_name)
            if not player_data:
                self.master.after(0, self.log_to_console, f"Error: Player '{player_name}' not found.\n", "error")
                messagebox.showerror("Error", f"Could not find player '{player_name}'. Please check the name.")
                return

            player_uuid_str = player_data['id']
            formatted_uuid = str(uuid.UUID(player_uuid_str))

            ops_path = os.path.join(self.server_path, 'ops.json')
            ops_list = []
            if os.path.exists(ops_path):
                try:
                    with open(ops_path, 'r') as f:
                        ops_list = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            if any(op.get('name', '').lower() == player_name.lower() for op in ops_list):
                self.master.after(0, self.log_to_console, f"Player '{player_name}' is already an operator.\n", "warning")
                messagebox.showwarning("Already Op", f"'{player_name}' is already an operator.")
                return

            new_op_entry = {"uuid": formatted_uuid, "name": player_name, "level": 4, "bypassesPlayerLimit": False}
            ops_list.append(new_op_entry)

            with open(ops_path, 'w') as f:
                json.dump(ops_list, f, indent=4)

            self.master.after(0, self.op_entry.delete, 0, tk.END)
            self.master.after(0, self.log_to_console, f"Successfully added '{player_name}' to operators (offline).\n", "success")
            self.master.after(100, self.update_ops_list)

        except requests.RequestException as e:
            self.master.after(0, self.log_to_console, f"API Error: Could not fetch UUID for '{player_name}'.\n", "error")
            messagebox.showerror("API Error", f"Could not contact Mojang's API to get player details.\nPlease check your internet connection.\n\n{e}")
        except Exception as e:
            self.master.after(0, self.log_to_console, f"Error adding op offline: {e}\n", "error")
            messagebox.showerror("Error", f"An unexpected error occurred while adding operator:\n{e}")
        finally:
            if hasattr(self, 'add_op_button') and self.add_op_button.winfo_exists():
                self.master.after(0, self.add_op_button.config, {'state': tk.NORMAL, 'text': 'Add'})

    def _deop_player(self, player_name):
        if not player_name:
            return

        if self.server_handler.server_running:
            self.server_handler.send_command(f"deop {player_name}")
        else:
            if not self.server_path:
                messagebox.showerror("Error", "Server path is not configured.")
                return
            
            ops_path = os.path.join(self.server_path, 'ops.json')
            if not os.path.exists(ops_path):
                self.log_to_console("ops.json not found. Cannot de-op offline.\n", "warning")
                return

            try:
                with open(ops_path, 'r') as f:
                    ops_list = json.load(f)

                original_count = len(ops_list)
                ops_list = [op for op in ops_list if op.get('name', '').lower() != player_name.lower()]

                if len(ops_list) < original_count:
                    with open(ops_path, 'w') as f:
                        json.dump(ops_list, f, indent=4)
                    self.log_to_console(f"Successfully de-opped '{player_name}' (offline).\n", "success")
                else:
                    self.log_to_console(f"Player '{player_name}' not found in ops.json.\n", "info")
                
                self.master.after(100, self.update_ops_list)

            except (json.JSONDecodeError, IOError, Exception) as e:
                self.log_to_console(f"Error modifying ops.json: {e}\n", "error")
                messagebox.showerror("Error", f"An error occurred while modifying ops.json:\n{e}")
            
    def _create_worlds_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        card.pack(fill=tk.BOTH, expand=True)
        
        title_frame = ttk.Frame(card, style='CardInner.TFrame')
        title_frame.pack(fill=tk.X, pady=(0,10))
        ttk.Label(title_frame, text="Server Worlds", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(title_frame, text="Refresh", command=self._refresh_worlds_visual, style="Accent.TButton").pack(side=tk.RIGHT)
        
        self.scrollable_worlds_frame = self._create_scrollable_list(card)
        
    def _refresh_worlds_visual(self):
        if not hasattr(self, 'scrollable_worlds_frame'): return
        for widget in self.scrollable_worlds_frame.winfo_children(): widget.destroy()

        if not self.server_path:
            ttk.Label(self.scrollable_worlds_frame, text="Server path is not configured.").pack(pady=20)
            return

        try:
            world_folders = [item for item in os.listdir(self.server_path) if os.path.isdir(os.path.join(self.server_path, item)) and os.path.exists(os.path.join(self.server_path, item, 'level.dat'))]
            if not world_folders:
                ttk.Label(self.scrollable_worlds_frame, text="No worlds found.").pack(pady=20)
                return

            for world_name in sorted(world_folders):
                row = ttk.Frame(self.scrollable_worlds_frame, style='CardInner.TFrame', padding=(10,8))
                row.pack(fill=tk.X, expand=True, pady=2, padx=2)

                info_frame = ttk.Frame(row, style='CardInner.TFrame')
                info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
                ttk.Label(info_frame, text=f"🌍 {world_name}", font=FONT_UI_BOLD).pack(anchor='w')
                size_label = ttk.Label(info_frame, text="Calculating size...", foreground=TEXT_SECONDARY)
                size_label.pack(anchor='w')
                threading.Thread(target=self._update_world_size_label, args=(os.path.join(self.server_path, world_name), size_label), daemon=True).start()
                
                actions_frame = ttk.Frame(row, style='CardInner.TFrame')
                actions_frame.pack(side=tk.RIGHT, padx=5)
                ttk.Button(actions_frame, text="Backup", command=lambda w=world_name: self.backup_world(w), style="Accent2.TButton").pack()
        except Exception as e:
            ttk.Label(self.scrollable_worlds_frame, text=f"An error occurred: {e}").pack()
            
    def _update_world_size_label(self, world_path, size_label):
        try:
            size_bytes = get_folder_size(world_path)
            if size_label.winfo_exists():
                self.master.after(0, size_label.config, {'text': f"Size: {format_size(size_bytes)}"})
        except Exception:
            if size_label.winfo_exists():
                self.master.after(0, size_label.config, {'text': "Size: Error"})

    def backup_world(self, world_name):
        if not self.server_path:
            messagebox.showerror("Backup Failed", "Server path not configured.")
            return
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
        # Time in ticks (20 ticks/sec) -> HH:MM:SS
        if 'time' in stat_key or 'since' in stat_key:
            try:
                seconds = int(value) / 20
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
            except (ValueError, TypeError):
                return str(value)
        
        # Distance in cm -> km or m
        if 'cm' in stat_key:
            try:
                val_int = int(value)
                if val_int > 100000: # over 1 km
                    return f"{val_int / 100000:.2f} km"
                else: # meters
                    return f"{val_int / 100:.2f} m"
            except (ValueError, TypeError):
                return str(value)

        # Damage in 1/10ths of a heart -> hearts
        if 'damage' in stat_key:
            try:
                return f"{int(value) / 10:.1f} hearts"
            except (ValueError, TypeError):
                return str(value)

        try:
            return f"{int(value):,}" # Add comma separators for large numbers
        except (ValueError, TypeError):
            return str(value)

    def _create_stats_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        card.pack(fill=tk.BOTH, expand=True)
        
        paned_window = ttk.PanedWindow(card, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        players_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=10, width=250)
        players_frame.pack_propagate(False)
        paned_window.add(players_frame, weight=1)
        
        ttk.Label(players_frame, text="Select Player:", style='Header.TLabel').pack(fill=tk.X)
        self.stats_player_var = tk.StringVar()
        self.stats_player_dropdown = ttk.Combobox(players_frame, textvariable=self.stats_player_var, state='readonly', font=FONT_UI_NORMAL)
        self.stats_player_dropdown.pack(fill=tk.X, pady=5)
        self.stats_player_dropdown.bind('<<ComboboxSelected>>', self._refresh_stats_display)
        
        stats_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=10)
        paned_window.add(stats_frame, weight=3)
        
        search_frame = ttk.Frame(stats_frame, style='CardInner.TFrame')
        search_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_frame, text="Search Stats:").pack(side=tk.LEFT, padx=(0,5))
        self.stats_search_var = tk.StringVar()
        self.stats_search_var.trace_add("write", self._refresh_stats_display)
        search_entry = ttk.Entry(search_frame, textvariable=self.stats_search_var)
        search_entry.pack(fill=tk.X, expand=True)

        self.stats_display_frame = self._create_scrollable_list(stats_frame)
        
    def update_stats_list(self):
        self.stats_files.clear(); self.player_uuids.clear()
        if not self.server_path:
            return
        stats_dir = os.path.join(self.server_path, 'world', 'stats')
        if not os.path.isdir(stats_dir):
            if hasattr(self, 'stats_player_dropdown'): self.stats_player_dropdown['values'] = []
            return

        for f in os.listdir(stats_dir):
            if f.endswith('.json'):
                self.stats_files[f[:-5]] = os.path.join(stats_dir, f)
        
        cache_file = os.path.join(self.server_path, 'usercache.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    for entry in json.load(f):
                        if entry.get('uuid') in self.stats_files:
                            self.player_uuids[entry['name']] = entry['uuid']
            except (json.JSONDecodeError, KeyError):
                pass # Ignore if usercache.json is malformed or being written to
        
        player_names = sorted(list(self.player_uuids.keys()))
        if hasattr(self, 'stats_player_dropdown'):
            self.stats_player_dropdown['values'] = player_names
            if player_names:
                self.stats_player_var.set(player_names[0])
            else:
                self.stats_player_var.set("") # Clear selection if no players
        self._refresh_stats_display()

    def _refresh_stats_display(self, *args):
        if not hasattr(self, 'stats_display_frame'): return
        for widget in self.stats_display_frame.winfo_children(): widget.destroy()

        player_name = self.stats_player_var.get()
        if not player_name:
            ttk.Label(self.stats_display_frame, text="Select a player to view their stats.").pack()
            return

        uuid = self.player_uuids.get(player_name)
        stats_file = self.stats_files.get(uuid)
        if not stats_file:
            ttk.Label(self.stats_display_frame, text=f"Stats file for {player_name} not found.").pack()
            return

        search_term = self.stats_search_var.get().lower() if hasattr(self, 'stats_search_var') else ""
            
        try:
            with open(stats_file, 'r') as f:
                stats_data = json.load(f).get("stats", {})
            if not stats_data:
                ttk.Label(self.stats_display_frame, text="No stats available.").pack()
                return

            any_stats_shown = False
            for category, values in sorted(stats_data.items()):
                cat_name = category.replace('minecraft:', '').replace('_', ' ').title()
                
                # Filter stats based on search term
                filtered_values = {
                    stat: value for stat, value in values.items() 
                    if search_term in stat.lower().replace('_', ' ') or search_term in cat_name.lower()
                }

                if not filtered_values:
                    continue
                
                any_stats_shown = True
                pane = CollapsiblePane(self.stats_display_frame, text=cat_name)
                pane.pack(fill='x', pady=2, padx=2)
                
                for stat, value in sorted(filtered_values.items()):
                    stat_name = stat.replace('minecraft:', '').replace('_', ' ').title()
                    display_value = self._format_stat_value(stat, value)
                    ttk.Label(pane.body, text=f"• {stat_name}: {display_value}").pack(anchor='w', padx=15, pady=1)

            if not any_stats_shown:
                ttk.Label(self.stats_display_frame, text=f"No stats found matching '{search_term}'.").pack(pady=10)

        except Exception as e:
            ttk.Label(self.stats_display_frame, text=f"Error reading stats file: {e}").pack()

    def _create_bans_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        card.pack(fill=tk.BOTH, expand=True)
        
        title_frame = ttk.Frame(card, style='CardInner.TFrame')
        title_frame.pack(fill=tk.X, pady=(0,10))
        ttk.Label(title_frame, text="Ban Management", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(title_frame, text="Refresh Lists", command=self._load_bans, style="Accent.TButton").pack(side=tk.RIGHT)
        
        paned_window = ttk.PanedWindow(card, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=10)

        players_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=10)
        paned_window.add(players_frame, weight=1)
        ttk.Label(players_frame, text="Banned Players", font=FONT_UI_BOLD).pack(anchor='w', pady=(0,5))
        self.banned_players_list_frame = self._create_scrollable_list(players_frame)
        
        ips_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=10)
        paned_window.add(ips_frame, weight=1)
        ttk.Label(ips_frame, text="Banned IPs", font=FONT_UI_BOLD).pack(anchor='w', pady=(0,5))
        self.banned_ips_list_frame = self._create_scrollable_list(ips_frame)

    def _load_bans(self):
        self._load_banned_players()
        self._load_banned_ips()
        
    def _load_banned_players(self):
        if not hasattr(self, 'banned_players_list_frame'): return
        for w in self.banned_players_list_frame.winfo_children(): w.destroy()
        
        if not self.server_path:
            return
        file_path = os.path.join(self.server_path, 'banned-players.json')
        if not os.path.exists(file_path): return

        try:
            with open(file_path, 'r') as f:
                banned_players = json.load(f)
            if not banned_players:
                ttk.Label(self.banned_players_list_frame, text="No players are banned.").pack()
                return
            for ban_entry in banned_players:
                player_name = ban_entry.get('name', 'N/A')
                row = ttk.Frame(self.banned_players_list_frame, style='CardInner.TFrame', padding=5)
                row.pack(fill=tk.X, pady=2, padx=2)
                avatar_label = ttk.Label(row)
                avatar_label.pack(side=tk.LEFT, padx=(0,5))
                self._fetch_player_avatar(ban_entry.get('uuid', player_name), avatar_label)
                info_text = f"{player_name}\nReason: {ban_entry.get('reason', 'None')}"
                ttk.Label(row, text=info_text, justify=tk.LEFT).pack(side=tk.LEFT, expand=True, anchor='w')
                ttk.Button(row, text="Pardon", command=lambda p=player_name: self._pardon_player(p), style="ActionRow.TButton").pack(side=tk.RIGHT)
        except Exception as e:
            ttk.Label(self.banned_players_list_frame, text=f"Error reading bans:\n{e}", wraplength=300).pack()

    def _load_banned_ips(self):
        if not hasattr(self, 'banned_ips_list_frame'): return
        for w in self.banned_ips_list_frame.winfo_children(): w.destroy()

        if not self.server_path:
            return
        file_path = os.path.join(self.server_path, 'banned-ips.json')
        if not os.path.exists(file_path): return
            
        try:
            with open(file_path, 'r') as f:
                banned_ips = json.load(f)
            if not banned_ips:
                ttk.Label(self.banned_ips_list_frame, text="No IPs are banned.").pack()
                return
            for ban_entry in banned_ips:
                ip = ban_entry.get('ip', 'N/A')
                row = ttk.Frame(self.banned_ips_list_frame, style='CardInner.TFrame', padding=5)
                row.pack(fill=tk.X, pady=2, padx=2)
                info_text = f"IP: {ip}\nReason: {ban_entry.get('reason', 'None')}"
                ttk.Label(row, text=info_text, justify=tk.LEFT).pack(side=tk.LEFT, expand=True, anchor='w')
                ttk.Button(row, text="Pardon", command=lambda i=ip: self._pardon_ip(i), style="ActionRow.TButton").pack(side=tk.RIGHT)
        except Exception as e:
             ttk.Label(self.banned_ips_list_frame, text=f"Error reading IP bans:\n{e}", wraplength=300).pack()

    def _pardon_player(self, player_name):
        self.server_handler.send_command(f"pardon {player_name}")
        self.master.after(500, self._load_bans)

    def _pardon_ip(self, ip_address):
        self.server_handler.send_command(f"pardon-ip {ip_address}")
        self.master.after(500, self._load_bans)

    def _create_whitelist_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        card.pack(fill=tk.BOTH, expand=True)
        
        title_frame = ttk.Frame(card, style='CardInner.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(title_frame, text="Whitelist Management", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(title_frame, text='Refresh List', command=self._load_whitelist, style='Accent.TButton').pack(side=tk.RIGHT)
        
        self.scrollable_whitelist_frame = self._create_scrollable_list(card)
        
        add_frame = ttk.Frame(card, style='CardInner.TFrame', padding=(0,10,0,0))
        add_frame.pack(fill=tk.X)
        self.whitelist_entry = ttk.Entry(add_frame, font=FONT_UI_NORMAL)
        self.whitelist_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.add_whitelist_button = ttk.Button(add_frame, text="Add", command=self._add_to_whitelist, style="Accent.TButton")
        self.add_whitelist_button.pack(side=tk.LEFT)

    def _load_whitelist(self):
        if not hasattr(self, 'scrollable_whitelist_frame'): return
        for w in self.scrollable_whitelist_frame.winfo_children(): w.destroy()
        
        if not self.server_path:
            return
        file_path = os.path.join(self.server_path, 'whitelist.json')
        if not os.path.exists(file_path): return

        try:
            with open(file_path, 'r') as f:
                whitelist = json.load(f)
            if not whitelist:
                ttk.Label(self.scrollable_whitelist_frame, text="The whitelist is empty.").pack()
                return
            for player in whitelist:
                player_name = player.get('name', 'N/A')
                row = ttk.Frame(self.scrollable_whitelist_frame, style='CardInner.TFrame', padding=5)
                row.pack(fill=tk.X, pady=2, padx=2)
                avatar_label = ttk.Label(row)
                avatar_label.pack(side=tk.LEFT, padx=(0,5))
                self._fetch_player_avatar(player.get('uuid', player_name), avatar_label)
                ttk.Label(row, text=player_name, justify=tk.LEFT).pack(side=tk.LEFT, expand=True, anchor='w')
                ttk.Button(row, text="Remove", command=lambda p=player_name: self._remove_from_whitelist(p), style="ActionRow.TButton").pack(side=tk.RIGHT)
        except Exception as e:
            ttk.Label(self.scrollable_whitelist_frame, text=f"Error reading whitelist:\n{e}", wraplength=300).pack()

    def _add_to_whitelist(self):
        player_name = self.whitelist_entry.get().strip()
        if player_name:
            self.server_handler.send_command(f"whitelist add {player_name}")
            self.whitelist_entry.delete(0, tk.END)
            self.master.after(500, self._load_whitelist)

    def _remove_from_whitelist(self, player_name):
        self.server_handler.send_command(f"whitelist remove {player_name}")
        self.master.after(500, self._load_whitelist)

    def _create_mods_view_widgets(self, parent_frame):
        main_card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        main_card.pack(fill=tk.BOTH, expand=True)

        top_actions_frame = ttk.Frame(main_card, style='CardInner.TFrame')
        top_actions_frame.pack(fill=tk.X, pady=(0,10))
        ttk.Button(top_actions_frame, text="Open Mods Folder", command=self._open_mods_folder, style="Accent2.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(top_actions_frame, text="Open Config Folder", command=self._open_config_folder, style="Accent2.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(top_actions_frame, text="Refresh Mod List", command=self._load_mods_list, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        
        paned_window = ttk.PanedWindow(main_card, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=10)

        mod_list_outer_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=10)
        paned_window.add(mod_list_outer_frame, weight=1)
        ttk.Label(mod_list_outer_frame, text="Installed Mods", style='Header.TLabel').pack(anchor='w', pady=(0,5))
        self.scrollable_mod_list_frame = self._create_scrollable_list(mod_list_outer_frame)

        config_editor_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=10)
        paned_window.add(config_editor_frame, weight=2)
        ttk.Label(config_editor_frame, text="Configuration File Editor", style='Header.TLabel').pack(anchor='w', pady=(0,5))
        self.mod_config_text_area = scrolledtext.ScrolledText(config_editor_frame, wrap=tk.WORD, bg=TERTIARY_BG, fg=TEXT_PRIMARY, font=FONT_CONSOLE_CUSTOM, relief='flat', borderwidth=1, state='disabled')
        self.mod_config_text_area.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        self.save_mod_config_button = ttk.Button(config_editor_frame, text="Save Config Changes", command=self._save_mod_config, style="Accent.TButton", state=tk.DISABLED)
        self.save_mod_config_button.pack(anchor='se')

    def _load_mods_list(self):
        if not hasattr(self, 'scrollable_mod_list_frame'): return
        for widget in self.scrollable_mod_list_frame.winfo_children(): widget.destroy()
        self.mod_data.clear()

        if not os.path.isdir(self.mods_dir_path):
            ttk.Label(self.scrollable_mod_list_frame, text="Mods folder not found.").pack(pady=20)
            return

        jar_files = [f for f in os.listdir(self.mods_dir_path) if f.lower().endswith(('.jar', '.jar.disabled'))]
        if not jar_files:
            ttk.Label(self.scrollable_mod_list_frame, text="No mods found.").pack(pady=20)
            return

        for jar_file in sorted(jar_files, key=str.lower):
            mod_id = self._extract_mod_id(jar_file)
            config_file_path = self._find_mod_config_file(mod_id)
            is_enabled = not jar_file.lower().endswith('.disabled')
            mod_info = {'jar': jar_file, 'id': mod_id, 'config_path': config_file_path, 'is_enabled': is_enabled}
            self.mod_data.append(mod_info)

            row = ttk.Frame(self.scrollable_mod_list_frame, style='CardInner.TFrame', padding=(10,8))
            row.pack(fill=tk.X, pady=2, padx=2)

            status_indicator = "🟢" if is_enabled else "⚪"
            ttk.Label(row, text=f"{status_indicator} {jar_file}", anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)

            actions_frame = ttk.Frame(row, style='CardInner.TFrame')
            actions_frame.pack(side=tk.RIGHT)
            if config_file_path:
                ttk.Button(actions_frame, text="⚙️", command=lambda m=mod_info: self._load_mod_config_for_editing(m), style="ActionRow.TButton").pack(side=tk.LEFT, padx=2)
            toggle_text = "Off" if is_enabled else "On"
            ttk.Button(actions_frame, text=toggle_text, command=lambda m=mod_info: self._toggle_mod_status(m), style="ActionRow.TButton").pack(side=tk.LEFT, padx=2)
            ttk.Button(actions_frame, text="🗑️", command=lambda m=mod_info: self._delete_specific_mod(m), style="ActionRow.TButton").pack(side=tk.LEFT)

    def _extract_mod_id(self, jar_filename):
        match = re.match(r"([a-zA-Z0-9_\-\[\]]+?)(?:[-_]?(?:forge|fabric|mc)?[.\d]+.*?)?\.jar", jar_filename, re.IGNORECASE)
        return match.group(1).lower().replace('[','').replace(']','') if match else os.path.splitext(jar_filename)[0].lower()

    def _find_mod_config_file(self, mod_id):
        if not self.config_dir_path or not os.path.isdir(self.config_dir_path): return None
        patterns = [f"{mod_id}.toml", f"{mod_id}.cfg", f"{mod_id}.json", f"{mod_id}-common.toml"]
        for pattern in patterns:
            path = os.path.join(self.config_dir_path, pattern)
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
        self.mod_config_text_area.config(state='normal')
        self.mod_config_text_area.delete('1.0', tk.END)
        try:
            with open(self.current_mod_config_path, 'r', encoding='utf-8') as f:
                self.mod_config_text_area.insert('1.0', f.read())
            self.save_mod_config_button.config(state='normal')
        except Exception as e:
            self.mod_config_text_area.insert('1.0', f"Error loading config: {e}")
            self.save_mod_config_button.config(state='disabled')

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
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {mod_info['jar']}?"):
            try:
                os.remove(os.path.join(self.mods_dir_path, mod_info['jar']))
                self._load_mods_list()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete mod: {e}")
                
    def _open_mods_folder(self):
        os.startfile(self.mods_dir_path)

    def _open_config_folder(self):
        os.startfile(self.config_dir_path)

    def _create_app_settings_view_widgets(self, parent_frame):
        settings_frame = ttk.Frame(parent_frame, style='Card.TFrame', padding=20)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(settings_frame, text="Application Settings", font=FONT_UI_HEADER, style='Header.TLabel').pack(anchor='w', pady=(0, 15))
        
        server_path_frame = ttk.Frame(settings_frame, style='CardInner.TFrame')
        server_path_frame.pack(fill=tk.X, pady=(5, 10))
        ttk.Label(server_path_frame, text="Server Path:", font=FONT_UI_BOLD).pack(side=tk.LEFT)
        path_label = ttk.Label(server_path_frame, text=self.server_path or "Not Set", wraplength=500)
        path_label.pack(side=tk.LEFT, padx=5)
        ToolTip(path_label, self.server_path or "Not Set")
        
        # --- Memory Allocation Settings ---
        mem_frame = ttk.Frame(settings_frame, style='CardInner.TFrame', padding=(10,15))
        mem_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(mem_frame, text="Java Memory Allocation", font=FONT_UI_BOLD).pack(anchor='w', pady=(0, 10))
        
        max_mem_frame = ttk.Frame(mem_frame, style='CardInner.TFrame')
        max_mem_frame.pack(fill=tk.X, pady=2)
        ttk.Label(max_mem_frame, text="Maximum (Xmx):", width=15).pack(side=tk.LEFT)
        ttk.Entry(max_mem_frame, textvariable=self.ram_max_val_var, width=6).pack(side=tk.LEFT, padx=5)

        min_mem_frame = ttk.Frame(mem_frame, style='CardInner.TFrame')
        min_mem_frame.pack(fill=tk.X, pady=2)
        ttk.Label(min_mem_frame, text="Minimum (Xms):", width=15).pack(side=tk.LEFT)
        ttk.Entry(min_mem_frame, textvariable=self.ram_min_val_var, width=6).pack(side=tk.LEFT, padx=5)

        unit_frame = ttk.Frame(mem_frame, style='CardInner.TFrame')
        unit_frame.pack(fill=tk.X, pady=2)
        ttk.Label(unit_frame, text="Unit:", width=15).pack(side=tk.LEFT)
        ttk.Combobox(unit_frame, textvariable=self.ram_unit_var, values=["G", "M"], width=4, state='readonly').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(mem_frame, text="Save Memory Settings", command=self._save_and_confirm_ram, style="Accent2.TButton").pack(anchor='e', pady=(15,0))

        ttk.Label(settings_frame, text="Changelog", font=FONT_UI_HEADER, style='Header.TLabel').pack(anchor='w', pady=(20, 5))
        changelog_frame = ttk.Frame(settings_frame, style='CardInner.TFrame')
        changelog_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.changelog_text = scrolledtext.ScrolledText(changelog_frame, wrap=tk.WORD, bg=TERTIARY_BG, fg=TEXT_PRIMARY, font=FONT_CONSOLE_CUSTOM, relief='flat', borderwidth=0)
        self.changelog_text.pack(fill=tk.BOTH, expand=True)
        self.changelog_text.config(state=tk.DISABLED)

    def _load_changelog(self):
        self.changelog_text.config(state='normal')
        self.changelog_text.delete('1.0', tk.END)
        try:
            with open(self.changelog_path, 'r', encoding='utf-8') as f:
                self.changelog_text.insert('1.0', f.read())
        except FileNotFoundError:
            self.changelog_text.insert('1.0', "Changelog not found.")
        except Exception as e:
            self.changelog_text.insert('1.0', f"Error reading changelog: {e}")
        finally:
            self.changelog_text.config(state=tk.DISABLED)

    def _accept_eula(self):
        if not self.server_path: return
        eula_path = os.path.join(self.server_path, "eula.txt")
        
        if not os.path.exists(eula_path):
            self.log_to_console("Tried to accept EULA, but eula.txt was not found.\n", "warning")
            return

        try:
            with open(eula_path, 'r+') as f:
                content = f.read().replace("eula=false", "eula=true")
                f.seek(0)
                f.write(content)
                f.truncate()
            self.log_to_console("EULA has been automatically accepted. The server has stopped. Please start it again.\n", "success")
        except Exception as e:
            self.log_to_console(f"Failed to automatically accept EULA: {e}\n", "error")

    def _save_and_confirm_ram(self):
        try:
            # Validate that inputs are numbers
            int(self.ram_max_val_var.get())
            int(self.ram_min_val_var.get())
            self._save_config()
            messagebox.showinfo("Saved", "Memory settings saved. They will be applied on the next server start.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Memory values must be whole numbers.")

    def _browse_java_path(self):
        filepath = filedialog.askopenfilename(
            title="Select Java Executable",
            filetypes=(("Executable files", "*.exe"), ("All files", "*.*"))
        )
        if filepath:
            self.java_path_var.set(filepath)
            self._save_config()

if __name__ == '__main__':
    root = tk.Tk()
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = 1000, 750
    x, y = (ws/2) - (w/2), (hs/2) - (h/2)
    root.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
    root.minsize(900, 650)
    app = ServerControlGUI(root)
    root.mainloop()

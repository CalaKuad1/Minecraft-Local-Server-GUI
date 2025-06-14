import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import subprocess
import threading
import os
import psutil
import matplotlib
import json
import shutil
import glob
import sys
import random # Added for particle animation
import re # Added for mod name extraction
import uuid # Added for offline OP UUID generation
import hashlib # Added for offline OP UUID generation
from PIL import Image, ImageTk, UnidentifiedImageError # For avatars
import requests # For avatars
import io # For avatars

# Attempt to hide the Python interpreter console window on Windows
if sys.platform == "win32":
    try:
        import ctypes
        # SW_HIDE = 0. This is the value for hiding the window.
        # Get a handle to the console window associated with the current process.
        # If the script is run with pythonw.exe, GetConsoleWindow() will return 0 (NULL),
        # and ShowWindow(0, ...) will do nothing, which is the desired behavior.
        console_window_handle = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window_handle != 0:
            ctypes.windll.user32.ShowWindow(console_window_handle, 0) # 0 corresponds to SW_HIDE
    except ImportError:
        # ctypes might not be available in some minimal Python installations (though unlikely for a GUI app)
        pass # Silently ignore if ctypes cannot be imported
    except Exception:
        # Catch any other unexpected errors during the ctypes calls to prevent crashing
        pass # Silently ignore other errors

matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Paleta de colores Moderna Oscura
PRIMARY_BG = '#1E1F22'  # Darker, slightly desaturated
SECONDARY_BG = '#2B2D30' # Panel/Card background, a bit lighter than primary
TERTIARY_BG = '#202124'  # For distinct areas like top bar or sidebar sections (if not card-styled)
ACCENT_COLOR = '#00BFFF' # Deep Sky Blue - vibrant and modern
ACCENT_HOVER = '#009ACD' # Slightly darker/desaturated for hover
SUCCESS_COLOR = '#32CD32' # Lime Green - vibrant success
TEXT_PRIMARY = '#F0F0F0'   # Lighter text for better contrast on dark BG
TEXT_SECONDARY = '#A0A0A0' # Softer grey for secondary text
CONSOLE_FG_CUSTOM = '#40E0D0' # Turquoise for console text
ERROR_FG_CUSTOM = '#FF6347'   # Tomato red for errors
WARNING_FG_CUSTOM = '#FFD700' # Gold for warnings

# Tipografía Moderna (Adjusted sizes and weights)
FONT_UI_NORMAL = ('Segoe UI', 12) # Base size increased
FONT_UI_BOLD = ('Segoe UI Semibold', 13) # Increased size for bold elements
FONT_UI_HEADER = ('Segoe UI Semibold', 14) # Specific for major headers within cards
FONT_UI_TITLE = ('Segoe UI Bold', 26)    # Changed to Bold for thicker appearance
FONT_CONSOLE_CUSTOM = ('Consolas', 12) # Slightly larger console font

class ServerControlGUI:
    def __init__(self, master):
        # Determine the base path for bundled or script execution
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running in a PyInstaller bundle
            # sys.executable is the path to the executable
            self.script_dir = os.path.dirname(sys.executable)
        else:
            # Running in a normal Python environment
            # __file__ is the path to the script file
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        # Ensure self.script_dir is an absolute path and normalized, useful for consistency
        self.script_dir = os.path.abspath(self.script_dir)

        self.run_bat_path = os.path.join(self.script_dir, "run.bat")
        self.server_properties_path = os.path.join(self.script_dir, "server.properties")
        self.banned_ips_path = os.path.join(self.script_dir, "banned-ips.json")
        self.banned_players_path = os.path.join(self.script_dir, "banned-players.json")
        self.mods_dir_path = os.path.join(self.script_dir, "mods")
        self.config_dir_path = os.path.join(self.script_dir, "config")
        self.changelog_path = os.path.join(self.script_dir, "changelog.txt")

        self.master = master
        master.title("Minecraft Server Control")
        master.geometry("950x720")
        master.configure(bg=PRIMARY_BG)
        master.bind("<Button-1>", self._handle_global_click) # Global click binding

        # --- Main Application Structure ---
        main_app_frame = ttk.Frame(master, style='TFrame') # This will use PRIMARY_BG by default
        main_app_frame.pack(fill=tk.BOTH, expand=True)

        # Particle Animation Canvas - Initialize with main_app_frame as parent
        # This will create the canvas, place it to fill main_app_frame, and lower it.
        self._init_particle_animation(main_app_frame)

        # Click Effect Overlay Toplevel and Canvas
        self.click_effect_toplevel = tk.Toplevel(master)
        self.click_effect_toplevel.overrideredirect(True) # Frameless
        self.click_effect_toplevel.attributes("-topmost", True) # Keep on top
        # Attempt to make the Toplevel background transparent (Windows specific for 'white')
        # A common color unlikely to be used for particles directly, e.g., a specific off-white or light grey
        self.transparent_color_key = "#FEFEFE" # Using a near-white color
        self.click_effect_toplevel.attributes("-transparentcolor", self.transparent_color_key)
        self.click_effect_toplevel.configure(bg=self.transparent_color_key)
        self.click_effect_toplevel.withdraw() # Start hidden

        self.click_effect_drawing_canvas = tk.Canvas(self.click_effect_toplevel, bg=self.transparent_color_key, highlightthickness=0)
        self.click_effect_drawing_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.click_effect_particles = []
        self.click_effect_toplevel_after_id = None 

        # Inicializar atributos de estado del servidor ANTES de crear widgets que puedan usarlos
        self.server_process = None
        self.server_running = False

        # Selection states for various lists
        self.selected_player_name = None # For kick/ban actions
        self.selected_banned_ip = None
        self.selected_banned_player_name = None # Store name for pardon command
        self.current_selected_mod_info = None # For mod config loading and deletion

        # Flag for multi-line player list parsing - Initialize these BEFORE any logging can occur
        self.expecting_player_list_next_line = False
        self.player_count_line_prefix = "There are "
        self.player_count_line_suffix = " players online:"

        self.property_row_frames = [] # Initialize here
        self.server_config_properties = {} # Initialize dictionary for server properties
        self.active_view_id = None # ID of the currently displayed view
        self.transition_in_progress = False # Flag to prevent overlapping transitions
        self.placeholder_avatar = self._create_placeholder_avatar(size=(24,24)) # Create placeholder
        self.particles_initialized = False # Flag for particle distribution
        self.canvas_width = 0 # Initial canvas width before actual measurement
        self.canvas_height = 0 # Initial canvas height before actual measurement
        self.avatar_cache = {} # Cache for fetched avatars

        self.style = ttk.Style()
        self.style.theme_use('default')

        # --- Custom Styles (Consolidated) ---
        self._configure_styles()

        # Sidebar Frame - child of main_app_frame
        self.sidebar_frame = ttk.Frame(main_app_frame, width=200, style='Card.TFrame') # Use Card style (SECONDARY_BG)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10,0), pady=10)
        self.sidebar_frame.pack_propagate(False) # Prevent frame from shrinking to fit content

        # Top Bar (Enhanced) - child of main_app_frame
        self.top_bar_frame = ttk.Frame(main_app_frame, height=70, style='Header.TFrame') # Uses TERTIARY_BG
        self.top_bar_frame.pack(side=tk.TOP, fill=tk.X, padx=(5,10), pady=(10,5)) # Packed after sidebar
        self.top_bar_frame.pack_propagate(False)

        # Configure grid layout for top_bar_frame
        self.top_bar_frame.columnconfigure(0, weight=1) # Title column expands
        self.top_bar_frame.columnconfigure(1, weight=0) # Actions column does not expand

        self.server_title_label = ttk.Label(self.top_bar_frame, text="Minecraft Server Dashboard", font=FONT_UI_TITLE, style='Title.TLabel', background=TERTIARY_BG)
        self.server_title_label.grid(row=0, column=0, sticky='ew', padx=(15, 5), pady=5)

        top_bar_actions_frame = ttk.Frame(self.top_bar_frame, style='Header.TFrame') # Uses TERTIARY_BG
        top_bar_actions_frame.grid(row=0, column=1, sticky='e', padx=(0, 15), pady=5)

        self.server_status_label = ttk.Label(top_bar_actions_frame, text="Status: Offline", font=FONT_UI_BOLD, style='StatusOffline.TLabel', background=TERTIARY_BG)
        self.server_status_label.pack(side=tk.LEFT, padx=(0,15))

        
        self.restart_button = ttk.Button(top_bar_actions_frame, text="Restart Server", command=self.restart_server, style="Accent2.TButton", state=tk.DISABLED)
        self.restart_button.pack(side=tk.LEFT)

        # Content Area Frame (where tab content will now go) - child of main_app_frame
        self.content_area_frame = ttk.Frame(main_app_frame, style='TFrame') # Base background for content area (PRIMARY_BG)
        self.content_area_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,10), pady=(5,10)) # Packed after sidebar & top bar

        # Initialize the transition overlay frame AFTER content_area_frame is created
        self.transition_overlay = ttk.Frame(self.content_area_frame, style='TransitionOverlay.TFrame') # Uses PRIMARY_BG for dip effect

        # --- Dictionary to store content frames for each view ---
        self.view_frames = {}

        # --- Create Sidebar Buttons and Content Frames ---
        # Order matters for display in sidebar
        self.views_config = [
            {'id': 'control', 'text': '🖥️  Dashboard', 'create_method': self._create_control_view_widgets},
            {'id': 'console', 'text': '⌨️  Console', 'create_method': self._create_console_view_widgets}, # New method for dedicated console view
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

        for view_info in self.views_config:
            # Create the frame for this view, parent is content_area_frame
            frame = ttk.Frame(self.content_area_frame, style='TFrame', padding=0) # View frames will have PRIMARY_BG
            self.view_frames[view_info['id']] = frame
            # Call the method to populate this frame (e.g., self._create_control_tab_widgets(frame))
            view_info['create_method'](frame) # Pass the frame as the parent
            # Initially, all frames are hidden; we'll show one later

            btn = ttk.Button(self.sidebar_frame, text=view_info['text'], 
                             command=lambda v_id=view_info['id']: self._show_view(v_id),
                             style='Sidebar.TButton') # Removed anchor='w'
            btn.pack(fill=tk.X, padx=10, pady=5, ipady=5)

        # Load initial data and show the first view (e.g., control/dashboard)
        self.load_server_properties()
        self._show_view('control') # Show the control/dashboard view by default
        self._update_server_status_display() # Initialize server status display

    

    def _configure_styles(self):
        self.style.configure('.', background=PRIMARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL, borderwidth=0, focusthickness=0, highlightthickness=0)
        self.style.configure('TFrame', background=PRIMARY_BG)
        self.style.configure('Card.TFrame', background=SECONDARY_BG, relief='solid', borderwidth=1, bordercolor=TERTIARY_BG)
        self.style.configure('Header.TFrame', background=TERTIARY_BG)
        self.style.configure('CardInner.TFrame', background=SECONDARY_BG)
        self.style.configure('TransitionOverlay.TFrame', background=PRIMARY_BG)
        
        self.style.configure('TLabel', background=SECONDARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL, padding=5)
        self.style.configure('Title.TLabel', background=TERTIARY_BG, foreground=ACCENT_COLOR, font=FONT_UI_TITLE, padding=(5,15,5,10))
        self.style.configure('Header.TLabel', background=SECONDARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_HEADER, padding=(8, 8, 8, 4))
        
        self.style.configure('StatusOnline.TLabel', background=TERTIARY_BG, foreground=SUCCESS_COLOR, font=FONT_UI_BOLD)
        self.style.configure('StatusOffline.TLabel', background=TERTIARY_BG, foreground=ERROR_FG_CUSTOM, font=FONT_UI_BOLD)
        self.style.configure('StatusStarting.TLabel', background=TERTIARY_BG, foreground=WARNING_FG_CUSTOM, font=FONT_UI_BOLD)

        self.style.configure('TNotebook', background=PRIMARY_BG, borderwidth=0)
        self.style.configure('TNotebook.Tab', font=FONT_UI_BOLD, padding=[18, 8], relief='flat')
        self.style.map('TNotebook.Tab',
                       background=[('selected', SECONDARY_BG), ('!selected', PRIMARY_BG)],
                       foreground=[('selected', ACCENT_COLOR), ('!selected', TEXT_SECONDARY)],
                       expand=[('selected', [1, 1, 1, 0])])

        button_padding = [14, 10, 14, 10]
        self.style.configure('Accent.TButton', font=FONT_UI_BOLD, padding=button_padding, relief='flat', borderwidth=0)
        self.style.map('Accent.TButton', 
                       background=[('pressed', ACCENT_HOVER), ('active', ACCENT_HOVER), ('', ACCENT_COLOR)], 
                       foreground=[('', PRIMARY_BG)])
        
        self.style.configure('Accent2.TButton', font=FONT_UI_BOLD, padding=button_padding, relief='flat', borderwidth=0)
        self.style.map('Accent2.TButton',
                       background=[('pressed', ACCENT_COLOR), ('active', ACCENT_COLOR), ('', TERTIARY_BG)],
                       foreground=[('', TEXT_PRIMARY)])
        
        self.style.configure('TSeparator', background=TERTIARY_BG)
        
        self.style.configure('TEntry',
                             fieldbackground=PRIMARY_BG,
                             foreground=TEXT_PRIMARY,
                             insertcolor=ACCENT_COLOR,
                             font=FONT_UI_NORMAL,
                             padding=(8,8),
                             relief='flat',
                             borderwidth=1)
        self.style.map('TEntry',
                       bordercolor=[('focus', ACCENT_COLOR), ('hover', ACCENT_HOVER), ('', TERTIARY_BG)],
                       fieldbackground=[('focus', SECONDARY_BG), ('hover', SECONDARY_BG), ('disabled', TERTIARY_BG)],
                       foreground=[('focus', ACCENT_COLOR), ('disabled', TEXT_SECONDARY)],
                       borderwidth=[('focus', 2), ('hover', 2), ('', 1)])

        self.style.configure('TCombobox',
                             fieldbackground=PRIMARY_BG,
                             foreground=TEXT_PRIMARY,
                             selectbackground=SECONDARY_BG,
                             selectforeground=ACCENT_COLOR, 
                             insertcolor=ACCENT_COLOR, 
                             arrowcolor=TEXT_PRIMARY,
                             font=FONT_UI_NORMAL,
                             padding=(8,8),
                             relief='flat',
                             borderwidth=1)
        self.style.map('TCombobox',
                       bordercolor=[('focus', ACCENT_COLOR), ('hover', ACCENT_HOVER), ('readonly', TERTIARY_BG), ('', TERTIARY_BG)],
                       fieldbackground=[
                           ('readonly', PRIMARY_BG),      
                           ('focus', SECONDARY_BG),       
                           ('hover', SECONDARY_BG),      
                           ('active', SECONDARY_BG),
                           ('disabled', TERTIARY_BG)
                       ],
                       foreground=[
                           ('readonly', TEXT_PRIMARY),    
                           ('focus', ACCENT_COLOR),       
                           ('disabled', TEXT_SECONDARY)
                       ],
                       arrowcolor=[('hover', ACCENT_COLOR), ('pressed', ACCENT_COLOR), ('readonly', TEXT_PRIMARY), ('disabled', TEXT_SECONDARY)],
                       background=[ 
                           ('readonly', PRIMARY_BG),
                           ('active', SECONDARY_BG),
                           ('hover', SECONDARY_BG),
                           ('disabled', PRIMARY_BG)
                       ],
                       borderwidth=[('focus', 2), ('hover', 2), ('readonly', 1), ('', 1)])
        
        self.master.option_add('*TCombobox*Listbox.background', SECONDARY_BG)
        self.master.option_add('*TCombobox*Listbox.foreground', TEXT_PRIMARY)
        self.master.option_add('*TCombobox*Listbox.selectBackground', ACCENT_COLOR)
        self.master.option_add('*TCombobox*Listbox.selectForeground', PRIMARY_BG)
        self.master.option_add('*TCombobox*Listbox.font', FONT_UI_NORMAL)
        self.master.option_add('*TCombobox*Listbox.borderWidth', 0)
        self.master.option_add('*TCombobox*Listbox.relief', 'flat')

        self.style.configure("Vertical.TScrollbar", 
                             background=ACCENT_HOVER,
                             troughcolor=PRIMARY_BG,      
                             bordercolor=TERTIARY_BG,   
                             arrowcolor=TEXT_PRIMARY,     
                             relief='flat', 
                             gripcount=0)
        self.style.map("Vertical.TScrollbar", 
                       background=[('active', ACCENT_COLOR), ('pressed', ACCENT_HOVER)], 
                       arrowcolor=[('active', ACCENT_COLOR)]
                       )

        self.style.configure('CardView.Treeview',
                             background=SECONDARY_BG,
                             fieldbackground=SECONDARY_BG, 
                             foreground=TEXT_PRIMARY,
                             rowheight=30,
                             font=FONT_UI_NORMAL,
                             relief='flat',
                             borderwidth=0)
        self.style.map('CardView.Treeview',
                       background=[('selected', ACCENT_COLOR)],
                       foreground=[('selected', PRIMARY_BG)])

        self.style.configure('CardView.Treeview.Heading',
                             background=TERTIARY_BG,
                             foreground=TEXT_PRIMARY,
                             font=FONT_UI_BOLD,
                             relief='flat',
                             padding=(10, 10))
        self.style.map('CardView.Treeview.Heading',
                       background=[('active', ACCENT_HOVER), ('hover', ACCENT_HOVER)],
                       relief=[('active', 'groove'), ('hover', 'ridge')])

        self.style.configure('Switch.TCheckbutton', 
                             font=FONT_UI_NORMAL, 
                             padding=(10, 8, 10, 8),
                             relief='flat', 
                             indicatordiameter=18)
        self.style.map('Switch.TCheckbutton',
                       indicatorcolor=[('selected', SUCCESS_COLOR), ('pressed', SUCCESS_COLOR),
                                       ('!selected', TEXT_SECONDARY), ('disabled', TERTIARY_BG)],
                       background=[('active', SECONDARY_BG), ('', SECONDARY_BG)],
                       foreground=[('', TEXT_PRIMARY)])

        FONT_ACTION_ROW = (FONT_UI_NORMAL[0], FONT_UI_NORMAL[1] - 2)
        action_row_button_padding = [10, 6, 10, 6]
        self.style.configure('ActionRow.TButton', font=FONT_ACTION_ROW, padding=action_row_button_padding, relief='flat', borderwidth=0)
        self.style.map('ActionRow.TButton',
                       background=[('pressed', ACCENT_COLOR), ('active', ACCENT_COLOR), ('', TERTIARY_BG)],
                       foreground=[('pressed', TEXT_PRIMARY), ('active', TEXT_PRIMARY), ('', TEXT_PRIMARY)])

        self.style.configure('Sidebar.TButton', font=FONT_UI_BOLD, padding=(18, 12, 18, 12), relief='flat', borderwidth=0, anchor=tk.W)
        self.style.map('Sidebar.TButton',
                       background=[('pressed', ACCENT_HOVER), ('active', ACCENT_HOVER), ('selected', ACCENT_COLOR), ('', SECONDARY_BG)],
                       foreground=[('pressed', PRIMARY_BG), ('active', PRIMARY_BG), ('selected', TEXT_PRIMARY), ('', TEXT_PRIMARY)])

    def _init_particle_animation(self, parent_widget):
        self.particle_canvas = tk.Canvas(parent_widget, bg=PRIMARY_BG, highlightthickness=0)
        self.particle_canvas.place(x=0, y=0, relwidth=1, relheight=1) 
        tk.Misc.lower(self.particle_canvas) 
        # self.particle_canvas.bind("<Button-1>", self._on_canvas_click) # REMOVED Bind left mouse click

        self.particles = []
        self.num_particles = 400 # Reducido de 1200 a 400 para optimización
        self.particle_colors = [TERTIARY_BG, SECONDARY_BG, '#35373A', ACCENT_COLOR]
        
        for _ in range(self.num_particles):
            size = random.uniform(2, 5) # Aumentado el rango de tamaño de (1,3) a (2,5)
            dx = random.uniform(-0.3, 0.3)
            dy = random.uniform(-0.3, 0.3)
            while abs(dx) < 0.05 and abs(dy) < 0.05:
                dx = random.uniform(-0.3, 0.3)
                dy = random.uniform(-0.3, 0.3)
            color = random.choice(self.particle_colors)
            particle_id = self.particle_canvas.create_oval(0, 0, size, size, fill=color, outline="") # Temp position
            self.particles.append({'id': particle_id, 'x': 0, 'y': 0, 'dx': dx, 'dy': dy, 'size': size, 'color': color})
        
        # Schedule the first call to _animate_particles to allow GUI to settle
        self.master.after(10, self._animate_particles) 

    def _animate_particles(self):
        if not self.master.winfo_exists(): # Stop animation if window is destroyed
            return

        # --- Animate Background Particles (on self.particle_canvas) ---
        current_bg_canvas_width = self.particle_canvas.winfo_width()
        current_bg_canvas_height = self.particle_canvas.winfo_height()

        if current_bg_canvas_width <= 1 or current_bg_canvas_height <= 1: # Background canvas not ready
            # We don't want to reschedule the entire animation loop if only the background is not ready
            # but the click effect might be. However, this early return is for the main particle init.
            # If background particles are not initialized, it's okay to wait.
            self.master.after(50, self._animate_particles) 
            return
        
        if not self.particles_initialized or \
           self.canvas_width != current_bg_canvas_width or \
           self.canvas_height != current_bg_canvas_height:
            
            self.canvas_width = current_bg_canvas_width
            self.canvas_height = current_bg_canvas_height
            
            for p in self.particles: # Background particles
                p['x'] = random.uniform(0, self.canvas_width - p['size'])
                p['y'] = random.uniform(0, self.canvas_height - p['size'])
                self.particle_canvas.coords(p['id'], p['x'], p['y'], p['x'] + p['size'], p['y'] + p['size'])
            self.particles_initialized = True
        
        if self.particles_initialized: # Only animate background particles if initialized
            for p in self.particles:
                current_coords = self.particle_canvas.coords(p['id'])
                if not current_coords: 
                    continue
                p['x'] += p['dx']
                p['y'] += p['dy']
                if p['x'] < 0 or (p['x'] + p['size']) > self.canvas_width:
                    p['dx'] *= -1
                    p['x'] = max(0, min(p['x'], self.canvas_width - p['size'])) 
                if p['y'] < 0 or (p['y'] + p['size']) > self.canvas_height:
                    p['dy'] *= -1
                    p['y'] = max(0, min(p['y'], self.canvas_height - p['size'])) 
                self.particle_canvas.coords(p['id'], p['x'], p['y'], p['x'] + p['size'], p['y'] + p['size'])
        
        # --- Animate Click Effect Particles (on self.click_effect_drawing_canvas) ---
        if self.click_effect_drawing_canvas.winfo_ismapped() and self.click_effect_particles:
            # Use a copy for iteration if modifying the list (e.g., removing particles)
            particles_to_remove = []
            click_canvas_width = self.click_effect_drawing_canvas.winfo_width()
            click_canvas_height = self.click_effect_drawing_canvas.winfo_height()

            for p_click in self.click_effect_particles:
                p_click['lifetime'] -= 1
                if p_click['lifetime'] <= 0:
                    particles_to_remove.append(p_click)
                    if self.click_effect_drawing_canvas.winfo_exists():
                        try:
                            self.click_effect_drawing_canvas.delete(p_click['id'])
                        except tk.TclError:
                            pass # Item might already be gone
                    continue

                p_click['x'] += p_click['dx']
                p_click['y'] += p_click['dy']

                # Boundary collision for click particles (within the full click_effect_canvas)
                if p_click['x'] < 0 or (p_click['x'] + p_click['size']) > click_canvas_width:
                    p_click['dx'] *= -1
                    p_click['x'] = max(0, min(p_click['x'], click_canvas_width - p_click['size']))
                if p_click['y'] < 0 or (p_click['y'] + p_click['size']) > click_canvas_height:
                    p_click['dy'] *= -1
                    p_click['y'] = max(0, min(p_click['y'], click_canvas_height - p_click['size']))
                
                if self.click_effect_drawing_canvas.winfo_exists():
                    try:
                        self.click_effect_drawing_canvas.coords(p_click['id'], p_click['x'], p_click['y'], p_click['x'] + p_click['size'], p_click['y'] + p_click['size'])
                    except tk.TclError:
                        pass # Item might have been deleted by hide_canvas
            
            for p_remove in particles_to_remove:
                if p_remove in self.click_effect_particles:
                    self.click_effect_particles.remove(p_remove)

        self.master.after(50, self._animate_particles) # Reschedule the main animation loop

    def _update_sidebar_buttons(self, view_id_to_show):
        """Updates the visual state of sidebar buttons to reflect the active view."""
        for child in self.sidebar_frame.winfo_children():
            if isinstance(child, ttk.Button):
                button_view_id = None
                try: 
                    cmd_str = str(child.cget('command'))
                    if "_show_view(" in cmd_str:
                        button_view_id = cmd_str.split("('")[-1].split("')")[0] # Corrected this line
                except:
                    pass

                if button_view_id == view_id_to_show:
                    child.state(['selected'])
                else:
                    child.state(['!selected'])

    def _load_data_for_view(self, view_id_to_show):
        """Loads or refreshes data specific to the view being shown."""
        if view_id_to_show == 'players' and self.server_running:
            self.update_players_list()
        elif view_id_to_show == 'bans':
            self._load_bans()
        elif view_id_to_show == 'mods':
            self._load_mods_list()
        elif view_id_to_show == 'app_settings':
            self._load_changelog()
        elif view_id_to_show == 'ops':
            self.update_ops_list() 
        elif view_id_to_show == 'stats':
            self.update_stats_list()
        elif view_id_to_show == 'worlds':
            self._refresh_worlds_visual()
        # Add other view-specific load/refresh calls here

    def _complete_transition_show(self, new_view_frame, view_id_to_show, skip_overlay_hide=False):
        """Completes the view transition: hides overlay, shows new frame, loads data."""
        if not skip_overlay_hide:
            if self.transition_overlay.winfo_ismapped():
                self.transition_overlay.place_forget()

        # Ensure any other potentially visible frames are hidden
        for vid, frame in self.view_frames.items():
            if frame != new_view_frame and frame.winfo_ismapped():
                frame.pack_forget()
            
        if new_view_frame.winfo_exists():
            new_view_frame.pack(fill=tk.BOTH, expand=True)
            new_view_frame.lift()

        self._load_data_for_view(view_id_to_show)
        self.transition_in_progress = False

    def _show_view(self, view_id_to_show):
        """Manages hiding old views and showing the new one, with a transition effect."""
        if self.transition_in_progress:
            return # Don't start a new transition if one is ongoing

        current_frame_is_target = False
        if self.active_view_id == view_id_to_show:
            active_frame = self.view_frames.get(self.active_view_id)
            if active_frame and active_frame.winfo_ismapped():
                current_frame_is_target = True

        if current_frame_is_target:
            if self.view_frames[view_id_to_show].winfo_exists():
                 self.view_frames[view_id_to_show].lift()
            self._load_data_for_view(view_id_to_show) # Reload data for the current view
            return

        self.transition_in_progress = True
        new_view_frame = self.view_frames[view_id_to_show]

        old_view_frame = None
        if self.active_view_id is not None and self.active_view_id != view_id_to_show:
            old_view_frame = self.view_frames.get(self.active_view_id)
            if old_view_frame and old_view_frame.winfo_ismapped():
                old_view_frame.pack_forget()
            else:
                old_view_frame = None 

        self._update_sidebar_buttons(view_id_to_show) # Update sidebar button states

        if old_view_frame: # Transition needed
            self.transition_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.transition_overlay.lift()
            
            self.active_view_id = view_id_to_show 
            self.master.after(75, lambda: self._complete_transition_show(new_view_frame, view_id_to_show))
        else: # No transition (first view or no effectively visible old view)
            self.active_view_id = view_id_to_show
            self._complete_transition_show(new_view_frame, view_id_to_show, skip_overlay_hide=True)
        
    def _bind_hover(self, widget, normal_bg, hover_bg):
        # Necesita acceder a widget.cget("style") y parsearlo o tener estilos dedicados para hover
        pass

    def _create_control_view_widgets(self, parent_frame):
        # Main frame for the control view, allowing for better spacing of cards
        control_view_content_frame = ttk.Frame(parent_frame, style='TFrame', padding=0)
        control_view_content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # --- Server Controls Card ---
        controls_card = ttk.Frame(control_view_content_frame, style='Card.TFrame', padding=25)
        controls_card.pack(fill=tk.X, pady=(10, 10), padx=10) # Consistent padding

        title_controls = ttk.Label(controls_card, text="Server Controls", style='Title.TLabel')
        title_controls.pack(anchor='w', pady=(0, 20))

        # Frame within the card for the buttons themselves
        buttons_frame = ttk.Frame(controls_card, style='CardInner.TFrame')
        buttons_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(buttons_frame, text="Start Server", command=self.start_server_thread, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=10)
        # Hover managed by style.map

        self.stop_button = ttk.Button(buttons_frame, text="Stop Server", command=self.stop_server, state=tk.DISABLED, style="Accent2.TButton")
        self.stop_button.pack(side=tk.LEFT, padx=10)
        # Hover managed by style.map
        
        # --- Server Console Card ---
        console_card = ttk.Frame(control_view_content_frame, style='Card.TFrame', padding=25)
        console_card.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0,10)) # pady top 0 as it's below controls card

        console_label = ttk.Label(console_card, text="Server Console", style='Header.TLabel')
        console_label.pack(anchor='w', pady=(0, 10))

        self.console_output_area = scrolledtext.ScrolledText(console_card, wrap=tk.WORD, height=15, 
                                                            bg=PRIMARY_BG, fg=CONSOLE_FG_CUSTOM, 
                                                            insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM, 
                                                            relief='flat', borderwidth=1, # Changed to flat
                                                            highlightthickness=0, bd=1, # bd should match borderwidth
                                                            padx=10, pady=10)
        self.console_output_area.pack(expand=True, fill=tk.BOTH)
        self.console_output_area.configure(state='disabled')
        self.console_output_area.tag_configure("error", foreground=ERROR_FG_CUSTOM)
        self.console_output_area.tag_configure("info", foreground=ACCENT_COLOR)
        self.console_output_area.tag_configure("warning", foreground=WARNING_FG_CUSTOM)
        self.console_output_area.tag_configure("usercmd", foreground=CONSOLE_FG_CUSTOM, font=(FONT_CONSOLE_CUSTOM[0], FONT_CONSOLE_CUSTOM[1], 'bold'))
        self.console_output_area.tag_configure("normal", foreground=TEXT_SECONDARY)

        entry_frame = ttk.Frame(console_card, style='CardInner.TFrame') # Use CardInner for thematic consistency if desired, or TFrame
        entry_frame.pack(fill=tk.X, pady=(15, 0)) # pady top to separate from console text area

        self.command_entry = ttk.Entry(entry_frame, font=FONT_CONSOLE_CUSTOM, style='TEntry')
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5, ipadx=5)
        self.command_entry.bind('<Return>', self.send_command_from_entry)
        self.command_entry.config(state='disabled')
        self.command_entry.insert(0, 'Type a command here...')
        self.command_entry.config(foreground='#888888') # Placeholder color

        def on_focus_in(event):
            if self.command_entry.get() == 'Type a command here...':
                self.command_entry.delete(0, tk.END)
                self.command_entry.config(foreground=TEXT_PRIMARY)
        def on_focus_out(event):
            if not self.command_entry.get():
                self.command_entry.insert(0, 'Type a command here...')
                self.command_entry.config(foreground='#888888')
        self.command_entry.bind('<FocusIn>', on_focus_in)
        self.command_entry.bind('<FocusOut>', on_focus_out)

        send_btn = ttk.Button(entry_frame, text='Send', command=self.send_command_from_button, style='Accent.TButton')
        send_btn.pack(side=tk.RIGHT) # Removed ipadx=16, ipady=6
        # Hover managed by style.map
        self.send_btn = send_btn
        self.send_btn.config(state='disabled')

    def _create_console_view_widgets(self, parent_frame):
        console_card = ttk.Frame(parent_frame, style='Card.TFrame', padding=25)
        console_card.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        console_label = ttk.Label(console_card, text="Full Server Console", style='Header.TLabel') # Changed style and text
        console_label.pack(anchor='w', pady=(0, 10)) # Adjusted pady
        
        # Re-use existing console_output_area if already created, or create it here.
        # For simplicity, let's assume it's always created by _create_control_view_widgets
        # and we just re-parent or make it accessible. 
        # A better approach is to make console_output_area a shared component if needed in multiple views,
        # or ensure it's only created once and its parent is set dynamically.
        # For now, we assume the console from the Dashboard is the primary one. This view could offer a larger view of it.
        # Let's just create a new one for this dedicated view for modularity.
        dedicated_console_output_area = scrolledtext.ScrolledText(console_card, wrap=tk.WORD, height=15, 
                                                            bg=PRIMARY_BG, fg=CONSOLE_FG_CUSTOM, 
                                                            insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM, 
                                                            relief='flat', borderwidth=1, # Changed to flat
                                                            highlightthickness=0, bd=1, # bd should match borderwidth
                                                            padx=10, pady=10)
        dedicated_console_output_area.pack(expand=True, fill=tk.BOTH)
        dedicated_console_output_area.configure(state='normal') # Enable to insert/configure
        # Link tags from the main console area or redefine them
        dedicated_console_output_area.tag_configure("error", foreground=ERROR_FG_CUSTOM)
        dedicated_console_output_area.tag_configure("info", foreground=ACCENT_COLOR)
        dedicated_console_output_area.tag_configure("warning", foreground=WARNING_FG_CUSTOM)
        dedicated_console_output_area.tag_configure("usercmd", foreground=CONSOLE_FG_CUSTOM, font=(FONT_CONSOLE_CUSTOM[0], FONT_CONSOLE_CUSTOM[1], 'bold'))
        dedicated_console_output_area.tag_configure("normal", foreground=TEXT_SECONDARY)
        
        # Improved placeholder message styling
        dedicated_console_output_area.delete('1.0', tk.END) 
        message_font = (FONT_CONSOLE_CUSTOM[0], FONT_CONSOLE_CUSTOM[1] + 1, 'italic')
        dedicated_console_output_area.tag_configure("placeholder_info", foreground=TEXT_SECONDARY, font=message_font, justify='center', lmargin1=20, lmargin2=20, rmargin=20)
        dedicated_console_output_area.insert(tk.END, "\\n\\nThis is a dedicated console view.\\n\\nLive server output is primarily shown on the Dashboard.\\nFuture enhancements may include full interactivity here.\\n", "placeholder_info")
        dedicated_console_output_area.configure(state='disabled')

        # Command Entry (similar to dashboard, but maybe separate state)
        entry_frame = ttk.Frame(console_card, style='CardInner.TFrame')
        entry_frame.pack(fill=tk.X, pady=(15, 0))
        dedicated_command_entry = ttk.Entry(entry_frame, font=FONT_CONSOLE_CUSTOM, style='TEntry')
        dedicated_command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5, ipadx=5) # Reduced ipady/ipadx
        # dedicated_command_entry.bind('<Return>', self.send_command_from_dedicated_entry) # Needs new method
        dedicated_command_entry.config(state='disabled') # Or link to server_running state
        dedicated_command_entry.insert(0, 'Type a command here...')

    def _create_properties_view_widgets(self, parent_frame):
        # Frame principal para la pestaña de propiedades, con scroll
        container = ttk.Frame(parent_frame, style='Card.TFrame') # Use Card.TFrame as the main container
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container, bg=SECONDARY_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
        self.properties_scrollable_frame = ttk.Frame(canvas, style='CardInner.TFrame') # Frame que contendrá los widgets

        self.properties_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        canvas.create_window((0, 0), window=self.properties_scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(15,0), pady=15) # Reduced from 20
        scrollbar.pack(side="right", fill="y", padx=(0,15), pady=15) # Reduced from 20

        title = ttk.Label(self.properties_scrollable_frame, text="Server Properties", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10), padx=10)

        # Frame para los botones de acción
        properties_controls_frame = ttk.Frame(self.properties_scrollable_frame, style='CardInner.TFrame')
        properties_controls_frame.pack(fill=tk.X, pady=(5,15), padx=10)
        
        self.load_props_button = ttk.Button(properties_controls_frame, text="Reload Properties", command=self.load_server_properties, style="Accent.TButton")
        self.load_props_button.pack(side=tk.LEFT, padx=(0,10))
        
        self.save_props_button = ttk.Button(properties_controls_frame, text="Save Properties", command=self.save_server_properties, style="Accent2.TButton")
        self.save_props_button.pack(side=tk.LEFT)

        # Diccionario para almacenar los widgets de propiedades y sus valores originales
        self.property_widgets = {}
        self.property_original_values = {}

        # Área para propiedades no manejadas explícitamente (opcional, o para más tarde)
        ttk.Label(self.properties_scrollable_frame, text="Additional Properties (Advanced):", style='Header.TLabel').pack(anchor='w', pady=(20,5), padx=10)
        self.additional_properties_text_area = scrolledtext.ScrolledText(self.properties_scrollable_frame, wrap=tk.WORD, height=10, width=70, 
                                                              bg=PRIMARY_BG, fg=TEXT_PRIMARY, 
                                                              insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM, 
                                                              relief='flat', borderwidth=1, highlightthickness=0, bd=1, padx=5, pady=5)
        self.additional_properties_text_area.pack(fill=tk.X, expand=True, padx=10, pady=(0,10))

    def _add_property_control(self, key_name, label_text, widget_type, default_value="", options=None, description="", target_frame=None, insert_before_widget=None):
        # Usar target_frame si se especifica, sino el por defecto.
        parent_frame = target_frame if target_frame else self.properties_scrollable_frame

        prop_frame = ttk.Frame(parent_frame, style='CardInner.TFrame')
        # Insertar el nuevo frame de propiedad ANTES del widget especificado (ej. el área de adicionales)
        if insert_before_widget:
            prop_frame.pack(fill=tk.X, pady=4, padx=10, before=insert_before_widget)
        else:
            prop_frame.pack(fill=tk.X, pady=4, padx=10)

        label = ttk.Label(prop_frame, text=label_text, style='TLabel', width=30, anchor='w') # Ancho aumentado para nombres largos
        label.pack(side=tk.LEFT, padx=(0,10))

        if description:
            self._add_tooltip(label, description)

        widget = None
        var = None # Inicializar var

        if widget_type == "entry":
            var = tk.StringVar(value=str(default_value)) # Asegurar que sea string
            widget = ttk.Entry(prop_frame, textvariable=var, width=35, font=FONT_UI_NORMAL)
            widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif widget_type == "switch": 
            var = tk.BooleanVar(value=(str(default_value).lower() == 'true'))
            # Añadimos un pequeño texto para que el checkbutton tenga tamaño, el estilo lo hará parecer un switch
            widget = ttk.Checkbutton(prop_frame, variable=var, style='Switch.TCheckbutton', text=" ") 
            widget.pack(side=tk.LEFT, padx=(5,10)) # Added padx around switch
        elif widget_type == "combobox":
            var = tk.StringVar(value=str(default_value))
            current_values = options or []
            widget = ttk.Combobox(prop_frame, textvariable=var, values=current_values, state='readonly', width=33, font=FONT_UI_NORMAL)
            widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
            if default_value and current_values and default_value in current_values:
                var.set(default_value)
            elif current_values: # Si el valor por defecto no está en las opciones, seleccionar la primera opción
                var.set(current_values[0])
        
        if widget and var is not None: # Chequeo de var también
            self.property_widgets[key_name] = (widget, var, widget_type)
            self.property_original_values[key_name] = default_value 
        elif widget_type not in ["entry", "switch", "combobox"]:
            # Solo para depuración, si se intenta usar un tipo no definido.
            print(f"Advertencia: Tipo de widget desconocido '{widget_type}' para la propiedad '{key_name}'. No se creó control.")

    def _create_resources_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=20) 
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        title = ttk.Label(card, text="Server Resource Usage", style='Header.TLabel') 
        title.pack(anchor='w', pady=(0, 15))

        self.debug_label = ttk.Label(card, text="", style='TLabel', font=("Consolas", 9))
        self.debug_label.pack(anchor='w', pady=(0, 10))

        cpu_frame = ttk.Frame(card, style='CardInner.TFrame')
        cpu_frame.pack(fill=tk.X, pady=10)
        cpu_icon = ttk.Label(cpu_frame, text='🖥️', font=('Segoe UI Emoji', 24), background=SECONDARY_BG)
        cpu_icon.pack(side=tk.LEFT, padx=(0, 10))
        cpu_label = ttk.Label(cpu_frame, text="CPU:", style='TLabel')
        cpu_label.pack(side=tk.LEFT)
        self.cpu_percent_label = ttk.Label(cpu_frame, text="0%", style='TLabel')
        self.cpu_percent_label.pack(side=tk.LEFT, padx=(10, 0))
        self.cpu_bar = ttk.Progressbar(cpu_frame, orient='horizontal', length=300, mode='determinate', maximum=100)
        self.cpu_bar.pack(side=tk.LEFT, padx=20, fill=tk.X, expand=True)

        ram_frame = ttk.Frame(card, style='CardInner.TFrame')
        ram_frame.pack(fill=tk.X, pady=10)
        ram_icon = ttk.Label(ram_frame, text='💾', font=('Segoe UI Emoji', 24), background=SECONDARY_BG)
        ram_icon.pack(side=tk.LEFT, padx=(0, 10))
        ram_label = ttk.Label(ram_frame, text="RAM:", style='TLabel')
        ram_label.pack(side=tk.LEFT)
        self.ram_label = ttk.Label(ram_frame, text="0 MB / 0 MB", style='TLabel')
        self.ram_label.pack(side=tk.LEFT, padx=(10, 0))
        self.ram_bar = ttk.Progressbar(ram_frame, orient='horizontal', length=300, mode='determinate', maximum=100)
        self.ram_bar.pack(side=tk.LEFT, padx=20, fill=tk.X, expand=True)

        self.cpu_history = [0]*60
        self.ram_history = [0]*60
        self.time_history = list(range(-59, 1))
        graph_frame = ttk.Frame(card, style='TFrame') 
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=(15,0))
        fig = Figure(figsize=(7,2.5), dpi=100, facecolor=SECONDARY_BG)
        self.ax_cpu = fig.add_subplot(211)
        self.ax_ram = fig.add_subplot(212)

        for ax, color, title_text in [
            (self.ax_cpu, ACCENT_COLOR, 'CPU (%)'),
            (self.ax_ram, ACCENT_COLOR, 'RAM (%)')]:
            ax.set_facecolor(SECONDARY_BG)
            ax.set_title(title_text, color=TEXT_PRIMARY, fontsize=FONT_UI_HEADER[1], fontweight='bold', pad=10)
            ax.tick_params(axis='x', colors=TEXT_SECONDARY, labelsize=FONT_UI_NORMAL[1]-2)
            ax.tick_params(axis='y', colors=TEXT_PRIMARY, labelsize=FONT_UI_NORMAL[1]-1)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color(TERTIARY_BG)
            ax.spines['left'].set_color(TEXT_SECONDARY)
            ax.grid(True, color=TERTIARY_BG, linestyle='--', linewidth=0.7, alpha=0.7)
        
        self.line_cpu, = self.ax_cpu.plot(self.time_history, self.cpu_history, color=ACCENT_COLOR, linewidth=2.5, alpha=0.9)
        self.line_ram, = self.ax_ram.plot(self.time_history, self.ram_history, color=ACCENT_COLOR, linewidth=2.5, alpha=0.9)
        self.ax_cpu.set_ylim(0, 100)
        self.ax_ram.set_ylim(0, 100)
        self.ax_cpu.set_xlim(-59, 0)
        self.ax_ram.set_xlim(-59, 0)
        self.ax_cpu.set_ylabel('%', color=TEXT_PRIMARY, fontsize=FONT_UI_NORMAL[1], fontweight='bold')
        self.ax_ram.set_ylabel('%', color=TEXT_PRIMARY, fontsize=FONT_UI_NORMAL[1], fontweight='bold')
        self.ax_cpu.set_xticks([])
        self.ax_ram.set_xticks([])
        fig.tight_layout(pad=2.0)
        self.canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        self.canvas.get_tk_widget().configure(bg=SECONDARY_BG)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=(10,0))
        self.fig = fig

        self._update_resource_usage()

    def _update_resource_usage(self):
        # Solo actualiza si el servidor está corriendo
        java_proc = None
        debug_info = ""
        cpu_per_core = 0
        ram_percent = 0
        if self.server_running:
            try:
                # Buscar todos los procesos java.exe
                candidates = []
                for proc in psutil.process_iter(['name', 'cmdline', 'memory_info']):
                    try:
                        if proc.info['name'] and 'java' in proc.info['name'].lower():
                            cmdline = ' '.join(proc.info.get('cmdline', []))
                            # Busca pistas típicas de Minecraft Forge/Server
                            if ('forge' in cmdline.lower() or 'minecraft' in cmdline.lower() or self.script_dir.lower() in cmdline.lower()):
                                candidates.append(proc)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                debug_info += f"Procesos java detectados (con pistas): {len(candidates)}\n"
                if not candidates:
                    # Si no hay pistas, toma el java.exe con más RAM
                    for proc in psutil.process_iter(['name', 'memory_info', 'cmdline']):
                        try:
                            if proc.info['name'] and 'java' in proc.info['name'].lower():
                                candidates.append(proc)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    debug_info += f"Procesos java detectados (total): {len(candidates)}\n"
                if candidates:
                    # Elige el de mayor RAM
                    java_proc = max(candidates, key=lambda p: getattr(p.info.get('memory_info', None), 'rss', 0))
                    debug_info += f"Usando PID: {java_proc.pid}\n"
                    debug_info += f"Cmdline: {' '.join(java_proc.cmdline())}\n"
                if java_proc:
                    cpu_total = java_proc.cpu_percent(interval=0.1)  # Porcentaje de CPU total
                    num_cores = psutil.cpu_count(logical=True) or 1
                    cpu_per_core = cpu_total / num_cores
                    mem_info = java_proc.memory_info()
                    ram_used = mem_info.rss / (1024 * 1024)  # MB
                    ram_total = psutil.virtual_memory().total / (1024 * 1024)  # MB
                    ram_percent = (ram_used / ram_total) * 100 if ram_total > 0 else 0
                    self.cpu_percent_label.config(text=f"{cpu_per_core:.1f}% per core ({num_cores} cores)")
                    self.cpu_bar['value'] = min(cpu_per_core, 100)
                    self.ram_label.config(text=f"{ram_used:.0f} MB / {ram_total:.0f} MB")
                    self.ram_bar['value'] = ram_percent
                else:
                    self.cpu_percent_label.config(text="-")
                    self.cpu_bar['value'] = 0
                    self.ram_label.config(text="-")
                    self.ram_bar['value'] = 0
            except Exception as e:
                debug_info += f"Error: {e}\n"
                self.cpu_percent_label.config(text="-")
                self.cpu_bar['value'] = 0
                self.ram_label.config(text="-")
                self.ram_bar['value'] = 0
        else:
            self.cpu_percent_label.config(text="-")
            self.cpu_bar['value'] = 0
            self.ram_label.config(text="-")
            self.ram_bar['value'] = 0
        self.debug_label.config(text=debug_info)
        # --- Actualiza gráficos ---
        self.cpu_history.append(min(cpu_per_core, 100))
        self.cpu_history.pop(0)
        self.ram_history.append(min(ram_percent, 100))
        self.ram_history.pop(0)
        self.line_cpu.set_ydata(self.cpu_history)
        self.line_ram.set_ydata(self.ram_history)
        self.canvas.draw()
        self.master.after(1500, self._update_resource_usage)

    def load_server_properties(self):
        # Limpiar widgets de propiedades anteriores y datos almacenados
        for widget_tuple in self.property_widgets.values():
            if widget_tuple[0] and widget_tuple[0].winfo_exists():
                widget_tuple[0].master.destroy() # Destruir el prop_frame contenedor
        self.property_widgets.clear()
        self.property_original_values.clear()

        # Limpiar frames de filas de propiedades anteriores
        for row_frame_widget in self.property_row_frames:
            if row_frame_widget.winfo_exists():
                row_frame_widget.destroy()
        self.property_row_frames.clear()

        # Limpiar el área de texto de propiedades adicionales también
        self.additional_properties_text_area.configure(state='normal')
        self.additional_properties_text_area.delete('1.0', tk.END)
        self.additional_properties_text_area.insert('1.0', "# Unparsed properties or long comments might appear here in the future.")
        self.additional_properties_text_area.configure(state='disabled')

        self.server_properties_lines = [] # Para guardar el orden y comentarios
        self.property_row_frames = [] # To keep track of dynamically created row frames for properties

        # Definiciones para propiedades especiales
        special_properties = {
            "gamemode": {"type": "combobox", "options": ["survival", "creative", "adventure", "spectator"]},
            "difficulty": {"type": "combobox", "options": ["peaceful", "easy", "normal", "hard"]}
            # Puedes añadir más propiedades especiales aquí, por ejemplo, para rangos numéricos o colores.
        }
        # Nombres más amigables para las etiquetas
        friendly_names = {
            "max-players": "Max Players:",
            "server-port": "Server Port:",
            "level-name": "World Name:",
            "online-mode": "Online Mode:",
            "pvp": "Allow PvP:",
            "spawn-animals": "Spawn Animals:",
            "spawn-monsters": "Spawn Monsters:",
            "spawn-npcs": "Spawn NPCs:",
            "allow-flight": "Allow Flight:",
            "enable-command-block": "Enable Command Block:",
            "motd": "Message of the Day (MOTD):"
        }

        properties_to_display = []
        try:
            with open(self.server_properties_path, 'r') as f:
                for line in f:
                    self.server_properties_lines.append(line.rstrip('\r\n'))
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith('#') or '=' not in line_stripped:
                        continue
                    key, value = line_stripped.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    properties_to_display.append((key, value))
                    self.server_config_properties[key] = value # Populate the server config properties

            current_row_frame = None
            controls_in_current_row = 0
            max_controls_per_row = 2 # Adjust as needed (2 or 3 typically)

            for key, value in properties_to_display:
                if current_row_frame is None or controls_in_current_row >= max_controls_per_row:
                    current_row_frame = ttk.Frame(self.properties_scrollable_frame, style='CardInner.TFrame')
                    current_row_frame.pack(fill=tk.X, pady=4, padx=5) # Increased pady, added padx for row frame
                    self.property_row_frames.append(current_row_frame)
                    controls_in_current_row = 0
                
                widget_type = "entry"
                options = None
                label_text = friendly_names.get(key, f"{key.replace('-', ' ').title()}:")
                description = f"Original property: {key}\nCurrent value: {value}"

                if key in special_properties:
                    widget_type = special_properties[key]["type"]
                    options = special_properties[key].get("options")
                elif value.lower() in ['true', 'false']:
                    widget_type = "switch"
                
                # Pass current_row_frame as the target_frame for _add_property_control
                self._add_property_control(key, label_text, widget_type, 
                                         default_value=value, options=options, description=description, 
                                         target_frame=current_row_frame) # Pass the row frame
                controls_in_current_row += 1
            
            # Move the "Additional Properties" section to be packed AFTER all dynamic property rows
            # This requires repacking or ensuring it was packed after the loop that creates rows.
            # For simplicity, if it was already created, we can try to lift it above other things not part of rows.
            # The easiest is to ensure its parent (properties_scrollable_frame) orders it last after rows.
            # The add_property_control no longer uses insert_before_widget for rows.

            # Ensure the label and text area for additional properties are at the bottom
            # Accessing them through their parent: self.properties_scrollable_frame
            # Find the label for "Additional Properties" and its Text area
            # This is a bit fragile, assumes they are direct children or specific structure.
            # A more robust way would be to store references to these widgets if complex manipulation is needed.
            # For now, we rely on pack order: rows are packed, then this section should be packed.
            # If they were packed before the loop, we might need to re-pack them.
            
            # Let's assume they are already created and parented to self.properties_scrollable_frame.
            # We just need to ensure they are packed *after* the dynamic rows.
            # One way: find them and re-pack if they exist.
            children = self.properties_scrollable_frame.winfo_children()
            additional_props_label_widget = None
            additional_props_text_area_widget = self.additional_properties_text_area
            
            for child in children:
                if isinstance(child, ttk.Label) and "Additional Properties" in child.cget("text"):
                    additional_props_label_widget = child
                    break # Found the label
            
            # Re-pack them at the end if they exist (they should)
            if additional_props_label_widget:
                additional_props_label_widget.pack_forget()
                additional_props_label_widget.pack(anchor='w', pady=(20,5), padx=10) 
            if additional_props_text_area_widget.winfo_exists(): # ScrolledText is complex, check its main frame
                additional_props_text_area_widget.master.pack_forget() # Assuming it's in a simple frame
                additional_props_text_area_widget.master.pack(fill=tk.X, expand=True, padx=10, pady=(0,10))


            self.log_to_console("Server properties loaded and UI dynamically generated.\n", "info")

            # Ensure the canvas scrollregion is updated after all widgets are added
            self.properties_scrollable_frame.update_idletasks()
            canvas = self.properties_scrollable_frame.master # This should be the canvas
            canvas.configure(scrollregion=canvas.bbox("all"))

        except FileNotFoundError:
            self.additional_properties_text_area.configure(state='normal')
            self.additional_properties_text_area.delete('1.0', tk.END)
            self.additional_properties_text_area.insert('1.0', f"# Error: {self.server_properties_path} not found.")
            self.additional_properties_text_area.configure(state='disabled')
            messagebox.showerror("Error", f"server.properties not found at {self.server_properties_path}")
            self.log_to_console(f"Error: {self.server_properties_path} not found.\\n", "error")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load server.properties: {e}")
            self.log_to_console(f"Failed to load server.properties: {e}\\n", "error")

    def save_server_properties(self):
        try:
            new_content_lines = []
            # Iterar sobre las líneas originales para mantener comentarios y orden
            for line in self.server_properties_lines:
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith('#'):
                    new_content_lines.append(line.rstrip('\r\n')) # Mantener comentarios y líneas vacías
                    continue
                
                if '=' in line_stripped:
                    key, original_value_from_file = line_stripped.split('=', 1)
                    key = key.strip()

                    if key in self.property_widgets:
                        widget, var, widget_type = self.property_widgets[key]
                        current_value = var.get()
                        if widget_type == 'switch':
                            current_value = str(current_value).lower() # Convertir BooleanVar (True/False) a 'true'/'false'
                        elif isinstance(current_value, str):
                            current_value = current_value.strip() # Limpiar espacios en strings de Entries
                        
                        new_content_lines.append(f"{key}={current_value}")
                    else:
                        # Esta propiedad estaba en el archivo original pero no se creó un widget para ella.
                        # Esto no debería suceder si todas las líneas key=value son procesadas por load_server_properties.
                        # Se añade la línea original para no perderla.
                        new_content_lines.append(line.rstrip('\r\n')) 
                else:
                    # Líneas que no son comentarios ni key-value (raro en server.properties, pero se preservan)
                     new_content_lines.append(line.rstrip('\r\n'))

            # El contenido del área de "propiedades adicionales" no se está utilizando activamente 
            # para añadir nuevas propiedades en esta lógica, así que no es necesario leerlo aquí
            # si el objetivo es solo modificar las existentes.

            with open(self.server_properties_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_content_lines) + '\n') # Escribir líneas y asegurar una nueva línea al final
            
            messagebox.showinfo("Success", "server.properties saved successfully!")
            self.log_to_console("server.properties saved successfully.\\n", "info")
            
            # Opcional: Recargar las propiedades para reflejar cualquier normalización (ej. true/false)
            # y actualizar los original_values si es necesario, o simplemente asumir que la UI ya está al día.
            self.load_server_properties() # Recargar para que la UI y los datos internos estén sincronizados

        except Exception as e:
            messagebox.showerror("Error", f"Error saving server.properties: {e}")
            self.log_to_console(f"Error saving server.properties: {e}\\n", "error")

    def log_to_console(self, message, level="normal", animate=False):
        self.console_output_area.configure(state='normal')
        tag = level if level in ("error", "info", "warning", "usercmd") else "normal"
        
        original_message_for_console = message # Keep the original message for display

        # Player list parsing logic
        message_stripped = message.strip()

        if self.expecting_player_list_next_line:
            # This line should contain the player names
            current_players = [p.strip() for p in message_stripped.split(',') if p.strip()]
            self.players_connected = current_players
            print(f"DEBUG: Players on next line: {self.players_connected}") # DEBUG
            self._refresh_players_display() # MODIFIED
            self.expecting_player_list_next_line = False # Reset flag
        
        elif self.player_count_line_prefix in message_stripped and self.player_count_line_suffix in message_stripped:
            try:
                # Extract the relevant part of the message that starts with player_count_line_prefix
                # This handles cases where there might be timestamps or other info before "There are..."
                start_index = message_stripped.find(self.player_count_line_prefix)
                relevant_message_part = message_stripped[start_index:]

                parts = relevant_message_part.split(self.player_count_line_suffix, 1)
                player_names_part = parts[1].strip()
                
                if player_names_part: # Players are on the same line
                    current_players = [p.strip() for p in player_names_part.split(',') if p.strip()]
                    self.players_connected = current_players
                    print(f"DEBUG: Players on same line: {self.players_connected}") # DEBUG
                    self._refresh_players_display() # MODIFIED
                    self.expecting_player_list_next_line = False
                else:
                    # Player names might be on the next line, or there are no players
                    count_part_text = parts[0][len(self.player_count_line_prefix):].strip() # Should be like "X of a max Y"
                    if count_part_text.startswith("0"): # "0 of a max..."
                        self.players_connected = [] # No players
                        print("DEBUG: Zero players detected from count line.") # DEBUG
                        self._refresh_players_display() # MODIFIED
                        self.expecting_player_list_next_line = False
                    else:
                        # Non-zero players, but names not on this line, so expect them on the next
                        print(f"DEBUG: Expecting player list on next line. Count part: {count_part_text}") # DEBUG
                        self.expecting_player_list_next_line = True
                        # Player list will be updated when the next line is processed
            except Exception as e: # pylint: disable=broad-except
                print(f"DEBUG: Error parsing player count line: {e}") # DEBUG
                self.expecting_player_list_next_line = False # Reset on any parsing error
                # Original message will still be logged below
                pass # Avoid crashing GUI on unexpected format

        # Insert the original, unmodified message into the console GUI
        if animate:
            for char in original_message_for_console:
                self.console_output_area.insert(tk.END, char, tag)
                self.console_output_area.see(tk.END)
                self.console_output_area.update_idletasks()
                self.master.after(1)
        else:
            self.console_output_area.insert(tk.END, original_message_for_console, tag)
            self.console_output_area.see(tk.END)
        
        self.console_output_area.configure(state='disabled')

    def start_server_thread(self):
        if not os.path.exists(self.run_bat_path):
            messagebox.showerror("Error", f"run.bat not found at {self.run_bat_path}")
            return
        if self.server_running:
            messagebox.showinfo("Info", "Server is already running.")
            return
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.command_entry.config(state='normal')
        self.send_btn.config(state='normal')
        self.server_running = True # Set to true, _update_server_status_display will show "Starting..."
        self._update_server_status_display() # Show "Starting..." immediately
        self.log_to_console("Starting server with nogui option...\n", "info")
        thread = threading.Thread(target=self.execute_server_command)
        thread.daemon = True
        thread.start()
        # self._update_server_status_display() # Moved to execute_server_command

    def execute_server_command(self):
        try:
            # Add 'nogui' argument. shell=False is generally safer with a list of args.
            command_to_run = [self.run_bat_path, "nogui"]
            self.server_process = subprocess.Popen(
                command_to_run,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW, # This flag might be Windows-specific for hiding console
                cwd=self.script_dir,
                shell=False # Set to False when command_to_run is a list
            )
            if self.master.winfo_exists(): # Ensure GUI is still there
                self._update_server_status_display() # Update status to Online/Starting after Popen

            for line in iter(self.server_process.stdout.readline, ''):
                self.log_to_console(line)
            self.server_process.stdout.close()
            return_code = self.server_process.wait()
            self.log_to_console(f"Server process exited with code {return_code}.\n")
        except FileNotFoundError:
            self.log_to_console(f"Error: The batch file '{self.run_bat_path}' was not found.\n", "error")
            self.server_running = False # Ensure this is set if Popen fails
            if self.master.winfo_exists(): self._update_server_status_display()
        except Exception as e:
            self.log_to_console(f"An error occurred while trying to start the server: {e}\n", "error")
            self.server_running = False # Ensure this is set on other exceptions
            if self.master.winfo_exists(): self._update_server_status_display()
        finally:
            self.server_running = False
            self.server_process = None
            if self.master.winfo_exists():
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.command_entry.config(state='disabled')
                self.send_btn.config(state='disabled')
                self._update_server_status_display() # Final status update to Offline

    def send_command_from_entry(self, event=None):
        cmd = self.command_entry.get().strip()
        if cmd and cmd != 'Type a command here...':
            self.send_command_to_server(cmd)
            self.command_entry.delete(0, tk.END)
            self.command_entry.insert(0, 'Type a command here...')
            self.command_entry.config(foreground='#888888')

    def send_command_from_button(self):
        self.send_command_from_entry()

    def send_command_to_server(self, cmd):
        if self.server_process and self.server_process.stdin:
            try:
                self.server_process.stdin.write(cmd + '\n')
                self.server_process.stdin.flush()
                self.log_to_console(f"> {cmd}\n", "usercmd", animate=True)
            except Exception as e:
                self.log_to_console(f"Error sending command: {e}\n", "error")
        else:
            self.log_to_console("Server is not running or cannot send command.\n", "error")

    def stop_server(self):
        if not self.server_running or not self.server_process:
            # If server_running is true but no process, it might be in a weird state. Allow trying to stop.
            if not self.server_running:
                 messagebox.showinfo("Info", "Server is not running.")
                 return
            else: # server_running true, but no process (e.g. failed to start but flag not reset)
                 self.log_to_console("Server process not found, attempting to reset state...\n", "warning")
                 # Reset state as if it stopped, as there's no process to send 'stop' to
                 self.server_running = False
                 self.server_process = None # Ensure it's None
                 if self.master.winfo_exists():
                    self.start_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.DISABLED)
                    self.command_entry.config(state='disabled')
                    self.send_btn.config(state='disabled')
                    self._update_server_status_display()
                 return

        self.log_to_console("Stopping server (sending 'stop')...\n", "info") # Log before changing status text
        # Update status to 'Stopping...' before sending command
        # Keep server_running True for now, execute_server_command's finally block will set it to False
        if self.master.winfo_exists():
            # Temporarily set a 'Stopping' status. 
            # The actual 'Offline' status will be set when the process truly exits.
            original_text = self.server_status_label.cget("text")
            self.server_status_label.config(text="Status: Stopping...", style='StatusStarting.TLabel') # Reuse 'Starting' style for 'Stopping'
            self.master.update_idletasks() # Force GUI update

        self.send_command_to_server('stop')
        self.stop_button.config(state=tk.DISABLED) # Disable stop button as stop is in progress
        # Command entry and send button are disabled here, which is fine.
        # self.command_entry.config(state='disabled')
        # self.send_btn.config(state='disabled')
        
        # Note: The server_running flag and final status update to 'Offline' 
        # will happen in the 'finally' block of execute_server_command 
        # once the server process actually terminates.
        # Status will be updated when server process actually exits in execute_server_command's finally block
        # Or we can optimistically set it here, but the finally block is more robust.
        # For now, let the finally block handle the definitive "Offline" state.
        # We can set it to "Stopping..." if desired.
        self.server_status_label.config(text="Status: Stopping...", style='StatusStarting.TLabel') # Using "Starting" style for yellow
        self.restart_button.config(state=tk.DISABLED)

    def _create_players_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        title = ttk.Label(card, text="Connected Players", style='Header.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Frame for the scrollable list of players
        players_list_outer_frame = ttk.Frame(card, style='CardInner.TFrame')
        players_list_outer_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        players_canvas = tk.Canvas(players_list_outer_frame, bg=SECONDARY_BG, highlightthickness=0)
        players_scrollbar = ttk.Scrollbar(players_list_outer_frame, orient="vertical", command=players_canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_players_list_frame = ttk.Frame(players_canvas, style='CardInner.TFrame')

        self.scrollable_players_list_frame.bind(
            "<Configure>",
            lambda e, canvas=players_canvas: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        players_canvas.create_window((0, 0), window=self.scrollable_players_list_frame, anchor="nw")
        players_canvas.configure(yscrollcommand=players_scrollbar.set)

        players_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        players_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Old Treeview and its related widgets are removed.
        # self.players_tree = ttk.Treeview(...)
        # self.players_tree.bind("<<TreeviewSelect>>", self._on_player_select)

        # Frame for action buttons (Kick, Ban, Refresh) - Refresh button remains for now
        actions_frame = ttk.Frame(card, style='CardInner.TFrame')
        actions_frame.pack(fill=tk.X, pady=(10,0))

        # Kick and Ban buttons are removed from here, will be per-row
        # self.kick_button = ttk.Button(...)
        # self.ban_button = ttk.Button(...)
        
        # Botón para refrescar manualmente - moved to the right of action buttons
        refresh_btn = ttk.Button(actions_frame, text='Refresh List', command=self.update_players_list, style='Accent.TButton')
        refresh_btn.pack(side=tk.RIGHT, padx=5) # Use side=tk.RIGHT to push it to the far right
        # self._bind_hover(refresh_btn, ACCENT_COLOR, ACCENT_HOVER) # Hover managed by style map
        
        self.players_connected = [] # Still used to store player names from 'list' command

    def update_players_list(self):
        # Envía el comando 'list' al servidor y espera la respuesta para actualizar la lista de jugadores
        if not self.server_running or not self.server_process:
            # Clear the list if server is not running
            if hasattr(self, 'scrollable_players_list_frame') and self.scrollable_players_list_frame.winfo_exists():
                for widget in self.scrollable_players_list_frame.winfo_children():
                    widget.destroy()
                ttk.Label(self.scrollable_players_list_frame, text="Server offline. No players to display.").pack(pady=10)
                self.scrollable_players_list_frame.update_idletasks()
                canvas = self.scrollable_players_list_frame.master
                canvas.configure(scrollregion=canvas.bbox("all"))
            return
        self.send_command_to_server('list')
        # La respuesta se parsea en log_to_console y llama a _refresh_players_display

    def _refresh_players_display(self): # Renamed from _refresh_players_tree
        if not hasattr(self, 'scrollable_players_list_frame') or not self.scrollable_players_list_frame.winfo_exists():
            return # Frame not created or already destroyed

        for widget in self.scrollable_players_list_frame.winfo_children():
            widget.destroy()

        print(f"DEBUG: _refresh_players_display called. self.players_connected = {self.players_connected}") 

        if not self.players_connected:
            ttk.Label(self.scrollable_players_list_frame, text="No players currently online.").pack(pady=10)
        else:
            for player_name in self.players_connected:
                player_row_frame = ttk.Frame(self.scrollable_players_list_frame, style='CardInner.TFrame', padding=(10,8))
                player_row_frame.pack(fill=tk.X, expand=True, pady=(4,0), padx=5)

                avatar_label_player = ttk.Label(player_row_frame, image=self.placeholder_avatar, style='TLabel')
                avatar_label_player.image = self.placeholder_avatar # Keep reference
                avatar_label_player.pack(side=tk.LEFT, padx=(0,8))
                self._fetch_player_avatar(player_name, avatar_label_player) # Fetch by name for connected players

                ttk.Label(player_row_frame, text=player_name, style='TLabel', anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10)) # Removed emoji

                actions_frame_player = ttk.Frame(player_row_frame, style='CardInner.TFrame')
                actions_frame_player.pack(side=tk.RIGHT, fill=tk.NONE)

                kick_btn = ttk.Button(actions_frame_player, text="👢 Kick", 
                                        command=lambda p=player_name: self._kick_player(p), 
                                        style="ActionRow.TButton") # Use new style, remove width
                kick_btn.pack(side=tk.LEFT, padx=(0,5), ipady=0) # Rely on style padding

                ban_btn = ttk.Button(actions_frame_player, text="🚫 Ban", 
                                       command=lambda p=player_name: self._ban_player(p), 
                                       style="ActionRow.TButton") # Use new style, remove width
                ban_btn.pack(side=tk.LEFT, ipady=0) # Rely on style padding
        
        self.scrollable_players_list_frame.update_idletasks()
        canvas = self.scrollable_players_list_frame.master
        if canvas.winfo_exists():
            canvas.configure(scrollregion=canvas.bbox("all"))

    def _create_ops_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        title = ttk.Label(card, text="Operators (Ops)", style='Header.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # --- Scrollable frame for Ops List ---
        ops_list_outer_frame = ttk.Frame(card, style='CardInner.TFrame') # Main container for the list part
        ops_list_outer_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ops_canvas = tk.Canvas(ops_list_outer_frame, bg=SECONDARY_BG, highlightthickness=0)
        ops_scrollbar = ttk.Scrollbar(ops_list_outer_frame, orient="vertical", command=ops_canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_ops_list_frame = ttk.Frame(ops_canvas, style='CardInner.TFrame')

        self.scrollable_ops_list_frame.bind(
            "<Configure>",
            lambda e, canvas=ops_canvas: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        ops_canvas.create_window((0, 0), window=self.scrollable_ops_list_frame, anchor="nw")
        ops_canvas.configure(yscrollcommand=ops_scrollbar.set)

        ops_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ops_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Old Treeview for ops removed
        # self.ops_tree = ttk.Treeview(...)

        # Botón para añadir operador - This section remains below the list area
        add_frame = ttk.Frame(card, style='CardInner.TFrame')
        add_frame.pack(fill=tk.X, pady=(10,0))
        self.new_op_entry = tk.Entry(add_frame, font=FONT_CONSOLE_CUSTOM, bg=PRIMARY_BG, fg=TEXT_PRIMARY, insertbackground=ACCENT_COLOR, relief='flat', borderwidth=2, highlightthickness=1, highlightbackground=ACCENT_COLOR, highlightcolor=ACCENT_COLOR)
        self.new_op_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=6)
        self.new_op_entry.insert(0, 'Username')
        self.new_op_entry.config(fg='#888888')
        def on_focus_in(event):
            if self.new_op_entry.get() == 'Username':
                self.new_op_entry.delete(0, tk.END)
                self.new_op_entry.config(fg=TEXT_PRIMARY)
        def on_focus_out(event):
            if not self.new_op_entry.get():
                self.new_op_entry.insert(0, 'Username')
                self.new_op_entry.config(fg='#888888')
        self.new_op_entry.bind('<FocusIn>', on_focus_in)
        self.new_op_entry.bind('<FocusOut>', on_focus_out)
        add_btn = ttk.Button(add_frame, text='Add OP', command=self.add_op, style='Accent.TButton')
        add_btn.pack(side=tk.RIGHT)
        # Hover for Accent.TButton is managed by style.map
        # Cargar ops
        self.ops_list = []
        self.update_ops_list()

    def update_ops_list(self):
        ops_path = os.path.join(self.script_dir, 'ops.json')
        new_ops_data = [] # Default to empty if file not found or error
        
        if os.path.exists(ops_path):
            try:
                with open(ops_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip(): # Check if file content is empty or only whitespace
                        self.log_to_console("ops.json is empty. Operator list will be empty.", "info")
                        # new_ops_data remains []
                    else:
                        loaded_json = json.loads(content)
                        if isinstance(loaded_json, list):
                            new_ops_data = loaded_json
                        else:
                            self.log_to_console(f"ops.json does not contain a valid JSON list. Found type: {type(loaded_json)}. Operator list will be empty.", "error")
                            messagebox.showwarning("Ops Load Warning", "ops.json content is not a list. Operator list may be incorrect or empty.")
                            # new_ops_data remains []
            except json.JSONDecodeError as jde:
                self.log_to_console(f"Error decoding ops.json: {jde}. Operator list will be treated as empty.", "error")
                messagebox.showerror("Ops Load Error", f"Failed to decode ops.json: {jde}. Please check the file contents.")
                # new_ops_data remains []
            except IOError as ioe:
                self.log_to_console(f"IOError reading ops.json: {ioe}. Operator list will be treated as empty.", "error")
                messagebox.showerror("Ops Load Error", f"Could not read ops.json: {ioe}")
                # new_ops_data remains []
            except Exception as e:
                self.log_to_console(f"Unexpected error loading ops.json: {e}. Operator list will be treated as empty.", "error")
                messagebox.showerror("Ops Load Error", f"An unexpected error occurred while loading ops list: {e}")
                # new_ops_data remains []
        else:
            self.log_to_console("ops.json not found. Operator list is empty.", "info")
            # new_ops_data remains []

        self.ops_list = new_ops_data
        self._refresh_ops_display()

    def _refresh_ops_display(self): # Renamed from _refresh_ops_tree
        if not hasattr(self, 'scrollable_ops_list_frame') or not self.scrollable_ops_list_frame.winfo_exists():
            return

        for widget in self.scrollable_ops_list_frame.winfo_children():
            widget.destroy()

        if not self.ops_list:
            ttk.Label(self.scrollable_ops_list_frame, text="No operators (ops) defined.").pack(pady=10)
        else:
            for op_entry in self.ops_list:
                name = op_entry.get('name', 'N/A')
                uuid = op_entry.get('uuid', 'N/A')
                level = op_entry.get('level', 'N/A')

                op_row_frame = ttk.Frame(self.scrollable_ops_list_frame, style='CardInner.TFrame', padding=(10,8))
                op_row_frame.pack(fill=tk.X, expand=True, pady=(4,0), padx=5)

                avatar_label_op = ttk.Label(op_row_frame, image=self.placeholder_avatar, style='TLabel')
                avatar_label_op.image = self.placeholder_avatar
                avatar_label_op.pack(side=tk.LEFT, padx=(0,8))
                
                # Use UUID if available for avatar, otherwise name
                identifier_for_avatar = name # Always use name
                self._fetch_player_avatar(identifier_for_avatar, avatar_label_op)

                info_text = f"Name: {name} (Level: {level})" # Removed UUID
                ttk.Label(op_row_frame, text=info_text, style='TLabel', anchor='w', justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10))

                actions_frame_op = ttk.Frame(op_row_frame, style='CardInner.TFrame')
                actions_frame_op.pack(side=tk.RIGHT, fill=tk.NONE)

                deop_btn = ttk.Button(actions_frame_op, text="⚡ DeOp", 
                                        command=lambda p=name: self._deop_player(p), 
                                        style="ActionRow.TButton") # Use new style, remove width
                deop_btn.pack(side=tk.LEFT, ipady=0, padx=5) # Rely on style padding
        
        self.scrollable_ops_list_frame.update_idletasks()
        ops_canvas = self.scrollable_ops_list_frame.master
        if ops_canvas.winfo_exists():
            ops_canvas.configure(scrollregion=ops_canvas.bbox("all"))

    def add_op(self):
        username = self.new_op_entry.get().strip()
        if not username or username == 'Username':
            messagebox.showwarning('Add OP', 'Please enter a valid username.')
            return
        # Enviar comando op al servidor
        if self.server_running:
            # Server is running, send command
            self.send_command_to_server(f'op {username}')
            self.log_to_console(f"Sent command to add {username} as an operator. Refreshing Ops list soon.", "info")
            # Clear input field
            self.new_op_entry.delete(0, tk.END)
            self.new_op_entry.insert(0, 'Username') # Placeholder text
            self.new_op_entry.config(fg='#888888') # Placeholder color
            self.master.focus_set() # Remove focus from entry
            # Refresh list after a delay to allow server to process
            self.master.after(1500, self.update_ops_list)
        else:
            # Server is not running, modify ops.json directly
            ops_path = os.path.join(self.script_dir, 'ops.json')
            current_ops = []

            # Load existing ops.json
            if os.path.exists(ops_path):
                try:
                    with open(ops_path, 'r', encoding='utf-8') as f:
                        loaded_data = json.load(f)
                    if isinstance(loaded_data, list):
                        current_ops = loaded_data
                    else:
                        self.log_to_console("Warning: ops.json content is not a list. Initializing as empty.", "warning")
                        messagebox.showwarning("Add OP Warning", "ops.json content was not a list. It will be treated as empty for this operation.")
                        current_ops = [] # Treat as empty if not a list
                except json.JSONDecodeError:
                    self.log_to_console("Warning: ops.json is corrupted. Initializing as empty for OP addition.", "warning")
                    messagebox.showwarning("Add OP Warning", "ops.json is corrupted. It will be treated as empty for this operation.")
                    current_ops = [] # Treat as empty if corrupted
                except Exception as e:
                    self.log_to_console(f"Error reading ops.json: {e}. Cannot add OP offline.", "error")
                    messagebox.showerror("Add OP Error", f"Could not read ops.json: {e}")
                    return

            # Check if player (by name, case-insensitive) is already in the list
            player_already_op = False
            for op_entry_item in current_ops:
                if op_entry_item.get('name', '').lower() == username.lower():
                    player_already_op = True
                    break
            
            if player_already_op:
                self.log_to_console(f"{username} is already listed in ops.json. No changes made to the file.", "info")
            else:
                # Player not found, add them
                effective_uuid = f"PLACEHOLDER_UUID_FOR_{username}" # Default placeholder
                
                # Ensure self.server_config_properties is available; it's loaded in __init__
                is_online_mode = self.server_config_properties.get('online-mode', 'true').lower() == 'true'

                if not is_online_mode:
                    try:
                        effective_uuid = ServerControlGUI._generate_offline_uuid(username)
                        self.log_to_console(f"Generated offline UUID for {username}: {effective_uuid}", "info")
                    except Exception as e:
                        self.log_to_console(f"Could not generate offline UUID for {username}: {e}. Using placeholder.", "warning")
                        # effective_uuid remains the placeholder
                else: # online-mode is true
                    self.log_to_console(f"Server is in online-mode. Cannot determine official UUID for {username} while server is offline. Using placeholder.", "warning")
                    messagebox.showwarning("Add OP (Offline - Online Mode)", 
                                           f"Server is in online-mode. Adding {username} to ops.json with a placeholder UUID. "
                                           f"The server may need to correct this when it's online and the player joins, or if 'op {username}' is run via console.")

                new_op_entry_data = {
                    "uuid": effective_uuid,
                    "name": username,
                    "level": 4,  # Default OP level for Minecraft
                    "bypassesPlayerLimit": False
                }
                current_ops.append(new_op_entry_data)
                
                try:
                    with open(ops_path, 'w', encoding='utf-8') as f:
                        json.dump(current_ops, f, indent=2)
                    self.log_to_console(f"Added {username} to ops.json (server offline).", "info")
                except Exception as e:
                    self.log_to_console(f"Error writing to ops.json: {e}", "error")
                    messagebox.showerror("Add OP Error", f"Could not write to ops.json: {e}")
                    return # Don't proceed if write failed
            
            # Clear input field and refresh list (common for both player_already_op and new_player_added scenarios if successful till here)
            self.new_op_entry.delete(0, tk.END)
            self.new_op_entry.insert(0, 'Username') # Placeholder text
            self.new_op_entry.config(fg='#888888') # Placeholder color
            self.master.focus_set() # Remove focus from entry
            # Refresh list (shorter delay as it's a local file change or no change)
            self.master.after(100, self.update_ops_list)

    def _deop_player(self, player_name):
        if player_name and player_name != 'N/A':
            if self.server_running:
                command = f"deop {player_name}"
                self.send_command_to_server(command)
                self.log_to_console(f"Sent command to deop {player_name}. Refreshing Ops list soon.", "info")
                self.master.after(1500, self.update_ops_list) # Refresh list after a delay for server processing
            else:
                # Server is not running, modify ops.json directly
                self.log_to_console(f"Attempting to deop {player_name} (server offline).", "info") # Added log
                ops_path = os.path.join(self.script_dir, 'ops.json')
                current_ops = []
                player_found_for_deop = False

                if os.path.exists(ops_path):
                    try:
                        with open(ops_path, 'r', encoding='utf-8') as f:
                            loaded_data = json.load(f)
                        if isinstance(loaded_data, list):
                            current_ops = loaded_data
                            self.log_to_console(f"Offline deop: Loaded ops.json content: {current_ops}", "info") # Added log
                        else:
                            self.log_to_console("Warning: ops.json content is not a list. Cannot deop offline.", "warning")
                            messagebox.showwarning("DeOp Warning", "ops.json content was not a list. DeOp operation aborted.")
                            return
                    except json.JSONDecodeError:
                        self.log_to_console("Warning: ops.json is corrupted. Cannot deop offline.", "warning")
                        messagebox.showwarning("DeOp Warning", "ops.json is corrupted. DeOp operation aborted.")
                        return
                    except Exception as e:
                        self.log_to_console(f"Error reading ops.json: {e}. Cannot deop offline.", "error")
                        messagebox.showerror("DeOp Error", f"Could not read ops.json: {e}")
                        return
                else:
                    self.log_to_console("ops.json not found. Cannot deop offline.", "warning")
                    messagebox.showwarning("DeOp Warning", "ops.json not found. DeOp operation aborted.")
                    return

                # Find and remove the player (case-insensitive)
                updated_ops = []
                for op_entry in current_ops:
                    op_name_in_file = op_entry.get('name', '')
                    # Added detailed log for checking each entry
                    self.log_to_console(f"Offline deop: Checking entry: {op_entry}. Name in file: '{op_name_in_file}' (lower: '{op_name_in_file.lower()}'). Target: '{player_name}' (lower: '{player_name.lower()}').", "info")
                    if op_name_in_file.lower() == player_name.lower():
                        player_found_for_deop = True
                        self.log_to_console(f"Offline deop: Match found for {player_name}. Player will be removed.", "info") # Added log
                        # Don't add this entry to updated_ops, effectively removing them
                    else:
                        updated_ops.append(op_entry)
                
                self.log_to_console(f"Offline deop: player_found_for_deop = {player_found_for_deop}", "info") # Added log
                self.log_to_console(f"Offline deop: Ops list that will be written (updated_ops): {updated_ops}", "info") # Added log

                if player_found_for_deop:
                    try:
                        with open(ops_path, 'w', encoding='utf-8') as f:
                            json.dump(updated_ops, f, indent=2)
                        self.log_to_console(f"Removed {player_name} from ops.json (server offline). File written successfully.", "info") # Updated log
                        # Verification re-read
                        try:
                            with open(ops_path, 'r', encoding='utf-8') as f_verify:
                                verify_data = json.load(f_verify)
                            self.log_to_console(f"Offline deop: Verification read of ops.json after write: {verify_data}", "info") # Added log
                        except Exception as e_verify:
                            self.log_to_console(f"Offline deop: Error during verification re-read of ops.json: {e_verify}", "error") # Added log
                    except Exception as e:
                        self.log_to_console(f"Error writing to ops.json during deop: {e}", "error")
                        messagebox.showerror("DeOp Error", f"Could not write to ops.json: {e}")
                        return # Don't refresh if write failed
                else:
                    self.log_to_console(f"{player_name} not found in ops.json. No changes made to the file.", "info") # Updated log
                
                # Refresh list (shorter delay as it's a local file change or no change)
                self.master.after(100, self.update_ops_list)
        else:
            self.log_to_console("Invalid player name to deop.", "warning")

    def _create_worlds_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        title = ttk.Label(card, text="🌍 Server Worlds", style='Header.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        # Tabla de mundos visual con botones
        self.worlds_list_frame = ttk.Frame(card, style='CardInner.TFrame')
        self.worlds_list_frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_worlds_visual()
        # Botón para refrescar
        refresh_btn = ttk.Button(card, text='Refresh', command=self._refresh_worlds_visual, style='Accent.TButton')
        refresh_btn.pack(anchor='e', pady=(10,0))
        # Hover managed by style map

    def _refresh_worlds_visual(self):
        for widget in self.worlds_list_frame.winfo_children():
            widget.destroy()
        # Header
        header = ttk.Frame(self.worlds_list_frame, style='CardInner.TFrame')
        header.pack(fill=tk.X, pady=(0,5))
        ttk.Label(header, text='🌍 World', style='TLabel', width=20, anchor='center').pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text='Size', style='TLabel', width=15, anchor='center').pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text='Backup', style='TLabel', width=10, anchor='center').pack(side=tk.LEFT, padx=5)
        # Lista de mundos
        world_names = [d for d in os.listdir(self.script_dir) if os.path.isdir(os.path.join(self.script_dir, d)) and d.startswith('world')]
        if not world_names:
            ttk.Label(self.worlds_list_frame, text='No worlds found.', style='TLabel').pack(pady=20)
            return
        for name in world_names:
            path = os.path.join(self.script_dir, name)
            size = self._format_size(self._get_folder_size(path))
            row = ttk.Frame(self.worlds_list_frame, style='CardInner.TFrame')
            row.pack(fill=tk.X, pady=4)

            # Left frame for world name and size
            left_content_frame = ttk.Frame(row, style='CardInner.TFrame')
            left_content_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            ttk.Label(left_content_frame, text=f'🌎 {name}', style='TLabel', anchor='w').pack(side=tk.LEFT, padx=(0,10))
            ttk.Label(left_content_frame, text=size, style='TLabel', anchor='w').pack(side=tk.LEFT)

            # Right frame for action buttons
            actions_frame = ttk.Frame(row, style='CardInner.TFrame')
            actions_frame.pack(side=tk.RIGHT, fill=tk.NONE, padx=5)

            backup_btn = ttk.Button(actions_frame, text='💾 Backup', command=lambda n=name: self.backup_world(n), style='ActionRow.TButton')
            backup_btn.pack(side=tk.LEFT, ipady=0) # Rely on style padding
            # Hover managed by style map

    def backup_world(self, world_name):
        world_path = os.path.join(self.script_dir, world_name)
        backup_name = f"{world_name}_backup.zip"
        backup_path = os.path.join(self.script_dir, backup_name)
        try:
            shutil.make_archive(world_path + '_backup', 'zip', world_path)
            messagebox.showinfo('Backup', f'Backup created: {backup_name}')
        except Exception as e:
            messagebox.showerror('Backup', f'Error creating backup: {e}')

    def _get_folder_size(self, folder):
        total = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except Exception:
                    pass
        return total

    def _format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/1024**2:.1f} MB"
        else:
            return f"{size_bytes/1024**3:.2f} GB"

    def _create_stats_view_widgets(self, parent_frame):
        card = ttk.Frame(parent_frame, style='Card.TFrame', padding=20) # Reduced padding from 30 to 20
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        title = ttk.Label(card, text="📊 Player Statistics", style='Header.TLabel') # Standardized to Header.TLabel
        title.pack(anchor='w', pady=(0, 15)) # Adjusted pady, consistent with Resources view title
        # Encabezados coloridos
        header_frame = ttk.Frame(card, style='CardInner.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 8))
        # Adjusted widths for better alignment
        ttk.Label(header_frame, text='👤 Name', style='TLabel', width=22, anchor='w', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⎈ UUID', style='TLabel', width=36, anchor='w', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⏱️ Time', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='💀 Deaths', style='TLabel', width=10, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ERROR_FG_CUSTOM).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⛏️ Mined', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='🚶 Walk (km)', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='🤸 Jumps', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⚔️ Dmg', style='TLabel', width=10, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='🎯 Kills', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)

        # Frame para filas
        self.stats_rows_frame = ttk.Frame(card, style='CardInner.TFrame')
        self.stats_rows_frame.pack(fill=tk.BOTH, expand=True)
        # Botón para refrescar
        refresh_btn = ttk.Button(card, text='Refresh', command=self.update_stats_list, style='Accent.TButton')
        refresh_btn.pack(anchor='e', pady=(10,0))
        # Hover managed by style map
        self.update_stats_list()

    def update_stats_list(self):
        stats_dir = os.path.join(self.script_dir, 'world', 'stats')
        stats_files = glob.glob(os.path.join(stats_dir, '*.json'))
        # Cargar cache de nombres
        name_cache = self._load_username_cache()
        stats_data = []
        for stat_file in stats_files:
            try:
                with open(stat_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                uuid = os.path.splitext(os.path.basename(stat_file))[0]
                name = name_cache.get(uuid, uuid)
                
                custom_stats = data.get('stats', {}).get('minecraft:custom', {})
                killed_stats = data.get('stats', {}).get('minecraft:killed', {})

                # Tiempo jugado (en ticks, 1 tick = 1/20 seg)
                played_ticks = custom_stats.get('minecraft:play_time', 0)
                played_hours = played_ticks / 20 / 3600
                # Muertes
                deaths = custom_stats.get('minecraft:deaths', 0)
                # Bloques minados (suma de todos los bloques)
                mined_blocks_dict = data.get('stats', {}).get('minecraft:mined', {})
                blocks_mined = sum(mined_blocks_dict.values())

                # New Stats
                walked_cm = custom_stats.get('minecraft:walk_one_cm', 0)
                walked_km = walked_cm / 100 / 1000 # cm to m, then m to km
                jumps = custom_stats.get('minecraft:jump', 0)
                damage_dealt = custom_stats.get('minecraft:damage_dealt', 0)
                mobs_killed = sum(killed_stats.values()) if killed_stats else 0
                
                stats_data.append((name, uuid, f"{played_hours:.1f} h", deaths, blocks_mined, f"{walked_km:.2f}", jumps, damage_dealt, mobs_killed))
            except Exception:
                continue
        self._refresh_stats_tree(stats_data)

    def _load_username_cache(self):
        # Intenta cargar usernamecache.json o usercache.json
        cache_files = ['usernamecache.json', 'usercache.json']
        for fname in cache_files:
            path = os.path.join(self.script_dir, fname)
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # usernamecache.json: {"uuid": "name", ...}
                    # usercache.json: [{"name": ..., "uuid": ...}, ...]
                    if isinstance(data, dict):
                        return data
                    elif isinstance(data, list):
                        return {entry['uuid']: entry['name'] for entry in data if 'uuid' in entry and 'name' in entry}
                except Exception:
                    continue
        return {}

    def _refresh_stats_tree(self, stats_data):
        for widget in self.stats_rows_frame.winfo_children():
            widget.destroy()
        for i, row in enumerate(stats_data):
            name, uuid_val, played, deaths, mined, walked_km, jumps, dmg_dealt, mobs_killed = row
            bg_color = SECONDARY_BG # All rows on SECONDARY_BG for consistency within the card
            fila = tk.Frame(self.stats_rows_frame, bg=bg_color)

            avatar_label_stats = ttk.Label(fila, image=self.placeholder_avatar, background=bg_color, style='TLabel') # Ensure TLabel style is applied if needed for bg
            avatar_label_stats.image = self.placeholder_avatar 
            avatar_label_stats.pack(side=tk.LEFT, padx=(5,5), pady=2) 

            identifier_for_avatar_stats = name 
            self._fetch_player_avatar(identifier_for_avatar_stats, avatar_label_stats)

            name_lbl = tk.Label(fila, text=name, font=FONT_UI_BOLD, bg=bg_color, fg=TEXT_PRIMARY, width=18, anchor='w', cursor='hand2')
            name_lbl.pack(side=tk.LEFT, padx=5)
            self._add_tooltip(name_lbl, uuid_val)
            
            tk.Label(fila, text=uuid_val, font=FONT_CONSOLE_CUSTOM, bg=bg_color, fg=TEXT_SECONDARY, width=36, anchor='w').pack(side=tk.LEFT, padx=5)
            tk.Label(fila, text=played, font=FONT_UI_NORMAL, bg=bg_color, fg=TEXT_PRIMARY, width=12, anchor='center').pack(side=tk.LEFT, padx=5)
            tk.Label(fila, text=f'{deaths}', font=FONT_UI_NORMAL, bg=bg_color, fg=ERROR_FG_CUSTOM, width=10, anchor='center').pack(side=tk.LEFT, padx=5)
            tk.Label(fila, text=f'{mined}', font=FONT_UI_NORMAL, bg=bg_color, fg=TEXT_PRIMARY, width=12, anchor='center').pack(side=tk.LEFT, padx=5)
            tk.Label(fila, text=f'{walked_km}', font=FONT_UI_NORMAL, bg=bg_color, fg=TEXT_PRIMARY, width=12, anchor='center').pack(side=tk.LEFT, padx=5)
            tk.Label(fila, text=f'{jumps}', font=FONT_UI_NORMAL, bg=bg_color, fg=TEXT_PRIMARY, width=12, anchor='center').pack(side=tk.LEFT, padx=5)
            tk.Label(fila, text=f'{dmg_dealt}', font=FONT_UI_NORMAL, bg=bg_color, fg=TEXT_PRIMARY, width=10, anchor='center').pack(side=tk.LEFT, padx=5)
            tk.Label(fila, text=f'{mobs_killed}', font=FONT_UI_NORMAL, bg=bg_color, fg=TEXT_PRIMARY, width=12, anchor='center').pack(side=tk.LEFT, padx=5)

            fila.pack(fill=tk.X, pady=2)

    def _add_tooltip(self, widget, text):
        # Tooltip simple para mostrar el UUID al pasar el ratón
        tooltip = tk.Toplevel(widget)
        tooltip.withdraw()
        tooltip.overrideredirect(True)
        tooltip.config(bg='#222222')
        label = tk.Label(tooltip, text=text, bg='#222222', fg=ACCENT_COLOR, font=("Consolas", 9), padx=6, pady=2)
        label.pack()
        def enter(event):
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            tooltip.geometry(f'+{x}+{y}')
            tooltip.deiconify()
        def leave(event):
            tooltip.withdraw()
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    # --- Methods for Player Actions (Kick/Ban) ---
    def _kick_player(self, player_name): # Renamed and takes player_name
        if player_name:
            command = f"kick {player_name}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            # self.scrollable_players_list_frame.selection_remove(self.scrollable_players_list_frame.selection()) # No selection anymore
            self.master.after(200, self.update_players_list) # Refresh list after a short delay
        else:
            self.log_to_console("No player specified to kick.\n", "warning")

    def _ban_player(self, player_name): # Renamed and takes player_name
        if player_name:
            command = f"ban {player_name}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            # self.scrollable_players_list_frame.selection_remove(self.scrollable_players_list_frame.selection()) # No selection anymore
            self.master.after(200, self.update_players_list) # Refresh list after a short delay
        else:
            self.log_to_console("No player specified to ban.\n", "warning")

    # --- BAN MANAGEMENT --- 
    def _create_bans_view_widgets(self, parent_frame):
        main_card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        main_card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Refresh button at the top
        refresh_bans_button = ttk.Button(main_card, text="Refresh Bans", command=self._load_bans, style="Accent.TButton")
        refresh_bans_button.pack(anchor='ne', pady=(0,10), padx=5)
        # Hover managed by style map

        # --- Banned IPs Section ---
        ips_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        ips_card.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        ttk.Label(ips_card, text="Banned IPs", style='Header.TLabel', font=FONT_UI_BOLD).pack(anchor='w', pady=(0,10))

        # --- Scrollable frame for Banned IPs ---
        banned_ips_canvas = tk.Canvas(ips_card, bg=SECONDARY_BG, highlightthickness=0)
        banned_ips_scrollbar = ttk.Scrollbar(ips_card, orient="vertical", command=banned_ips_canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_banned_ips_frame = ttk.Frame(banned_ips_canvas, style='CardInner.TFrame')

        self.scrollable_banned_ips_frame.bind(
            "<Configure>",
            lambda e, canvas=banned_ips_canvas: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        banned_ips_canvas.create_window((0, 0), window=self.scrollable_banned_ips_frame, anchor="nw")
        banned_ips_canvas.configure(yscrollcommand=banned_ips_scrollbar.set)

        banned_ips_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        banned_ips_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Old Treeview for IPs removed
        # self.banned_ips_tree = ttk.Treeview(...)
        # self.unban_ip_button = ttk.Button(...) -> Will be per-row

        # --- Banned Players Section --- (Mirroring IPs section)
        players_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        players_card.pack(fill=tk.BOTH, expand=True, pady=(10,0))
        ttk.Label(players_card, text="Banned Players", style='Header.TLabel', font=FONT_UI_BOLD).pack(anchor='w', pady=(0,10))

        # --- Scrollable frame for Banned Players ---
        banned_players_canvas = tk.Canvas(players_card, bg=SECONDARY_BG, highlightthickness=0)
        banned_players_scrollbar = ttk.Scrollbar(players_card, orient="vertical", command=banned_players_canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_banned_players_frame = ttk.Frame(banned_players_canvas, style='CardInner.TFrame')

        self.scrollable_banned_players_frame.bind(
            "<Configure>",
            lambda e, canvas=banned_players_canvas: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        banned_players_canvas.create_window((0, 0), window=self.scrollable_banned_players_frame, anchor="nw")
        banned_players_canvas.configure(yscrollcommand=banned_players_scrollbar.set)

        banned_players_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        banned_players_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Old Treeview for Players removed
        # self.banned_players_tree = ttk.Treeview(...)
        # self.unban_player_button = ttk.Button(...) -> Will be per-row
        
        self.selected_banned_ip = None # May not be needed if actions are direct
        self.selected_banned_player_name = None # May not be needed

        self._load_bans() # Initial load

    def _load_bans(self):
        self._load_banned_ips()
        self._load_banned_players()

    def _load_banned_ips(self):
        for widget in self.scrollable_banned_ips_frame.winfo_children():
            widget.destroy()
        try:
            if os.path.exists(self.banned_ips_path):
                with open(self.banned_ips_path, 'r', encoding='utf-8') as f:
                    banned_ips_data = json.load(f)
                if not banned_ips_data:
                    ttk.Label(self.scrollable_banned_ips_frame, text="No IPs are currently banned.").pack(pady=10)
                
                for ban_entry in banned_ips_data:
                    ip_row_frame = ttk.Frame(self.scrollable_banned_ips_frame, style='CardInner.TFrame', padding=(10,8))
                    ip_row_frame.pack(fill=tk.X, expand=True, pady=(4,0), padx=5)

                    info_text = f"🚫 IP: {ban_entry.get('ip', 'N/A')}\n"
                    info_text += f"   Reason: {ban_entry.get('reason', 'N/A')} (Source: {ban_entry.get('source', 'N/A')})\n"
                    info_text += f"   Created: {ban_entry.get('created', 'N/A')} | Expires: {ban_entry.get('expires', 'N/A')}"
                    
                    ttk.Label(ip_row_frame, text=info_text, style='TLabel', anchor='w', justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10))
                    
                    pardon_ip_btn = ttk.Button(ip_row_frame, text="⚖️ Pardon", 
                                               command=lambda ip=ban_entry.get('ip'): self._pardon_ip(ip), 
                                               style="ActionRow.TButton") # Use new style, remove width
                    pardon_ip_btn.pack(side=tk.RIGHT, ipady=0, padx=5) # Rely on style padding
            else:
                self.log_to_console(f"Ban file not found: {self.banned_ips_path}\n", "warning")
                ttk.Label(self.scrollable_banned_ips_frame, text=f"Ban file not found: {self.banned_ips_path}").pack(pady=10)
        except Exception as e:
            self.log_to_console(f"Error loading banned IPs: {e}\n", "error")
            messagebox.showerror("Error Loading Bans", f"Failed to load {self.banned_ips_path}:\n{e}")
            ttk.Label(self.scrollable_banned_ips_frame, text=f"Error loading: {os.path.basename(self.banned_ips_path)}").pack(pady=10)
        finally:
            if self.scrollable_banned_ips_frame.winfo_exists(): # Check if frame exists before calling methods on it
                self.scrollable_banned_ips_frame.update_idletasks()
                banned_ips_canvas = self.scrollable_banned_ips_frame.master
                if banned_ips_canvas.winfo_exists():
                    banned_ips_canvas.configure(scrollregion=banned_ips_canvas.bbox("all"))

    def _load_banned_players(self):
        for widget in self.scrollable_banned_players_frame.winfo_children():
            widget.destroy()
        try:
            if os.path.exists(self.banned_players_path):
                with open(self.banned_players_path, 'r', encoding='utf-8') as f:
                    banned_players_data = json.load(f)
                if not banned_players_data:
                    ttk.Label(self.scrollable_banned_players_frame, text="No players are currently banned.").pack(pady=10)

                for ban_entry in banned_players_data:
                    player_row_frame = ttk.Frame(self.scrollable_banned_players_frame, style='CardInner.TFrame', padding=(10,8))
                    player_row_frame.pack(fill=tk.X, expand=True, pady=(4,0), padx=5)

                    info_text = f"🚫 Player: {ban_entry.get('name', 'N/A')} (UUID: {ban_entry.get('uuid', 'N/A')})\n"
                    info_text += f"   Reason: {ban_entry.get('reason', 'N/A')} (Source: {ban_entry.get('source', 'N/A')})\n"
                    info_text += f"   Created: {ban_entry.get('created', 'N/A')} | Expires: {ban_entry.get('expires', 'N/A')}"

                    ttk.Label(player_row_frame, text=info_text, style='TLabel', anchor='w', justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10))

                    pardon_player_btn = ttk.Button(player_row_frame, text="⚖️ Pardon", 
                                                   command=lambda name=ban_entry.get('name'): self._pardon_player(name), 
                                                   style="ActionRow.TButton") # Use new style, remove width
                    pardon_player_btn.pack(side=tk.RIGHT, ipady=0, padx=5) # Rely on style padding
            else:
                self.log_to_console(f"Ban file not found: {self.banned_players_path}\n", "warning")
                ttk.Label(self.scrollable_banned_players_frame, text=f"Ban file not found: {self.banned_players_path}").pack(pady=10)
        except Exception as e:
            self.log_to_console(f"Error loading banned players: {e}\n", "error")
            messagebox.showerror("Error Loading Bans", f"Failed to load {self.banned_players_path}:\n{e}")
            ttk.Label(self.scrollable_banned_players_frame, text=f"Error loading: {os.path.basename(self.banned_players_path)}").pack(pady=10)
        finally:
            if self.scrollable_banned_players_frame.winfo_exists(): # Check if frame exists
                self.scrollable_banned_players_frame.update_idletasks()
                banned_players_canvas = self.scrollable_banned_players_frame.master
                if banned_players_canvas.winfo_exists():
                    banned_players_canvas.configure(scrollregion=banned_players_canvas.bbox("all"))

    def _pardon_ip(self, ip_address):
        if ip_address and ip_address != 'N/A':
            command = f"pardon-ip {ip_address}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            self.master.after(500, self._load_bans) # Refresh lists after a short delay
        else:
            self.log_to_console("Invalid IP address to pardon.\n", "warning")

    def _pardon_player(self, player_name):
        if player_name and player_name != 'N/A':
            command = f"pardon {player_name}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            self.master.after(500, self._load_bans) # Refresh lists after a short delay
        else:
            self.log_to_console("Invalid player name to pardon.\n", "warning")

    # --- MOD MANAGEMENT ---   
    def _create_mods_view_widgets(self, parent_frame):
        main_card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        main_card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top action buttons frame
        top_actions_frame = ttk.Frame(main_card, style='CardInner.TFrame')
        top_actions_frame.pack(fill=tk.X, pady=(0,10))

        open_mods_folder_btn = ttk.Button(top_actions_frame, text="Open Mods Folder", command=self._open_mods_folder, style="Accent2.TButton")
        open_mods_folder_btn.pack(side=tk.LEFT, padx=5)
        # Hover managed by style map

        open_config_folder_btn = ttk.Button(top_actions_frame, text="Open Config Folder", command=self._open_config_folder, style="Accent2.TButton")
        open_config_folder_btn.pack(side=tk.LEFT, padx=5)
        # Hover managed by style map

        refresh_mods_btn = ttk.Button(top_actions_frame, text="Refresh Mod List", command=self._load_mods_list, style="Accent.TButton")
        refresh_mods_btn.pack(side=tk.RIGHT, padx=5) # Refresh on the right
        # Hover managed by style map
        
        # PanedWindow for resizable sections: Mod List | Config Editor
        paned_window = ttk.PanedWindow(main_card, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=10)

        # Left Pane: Mod List (Now a scrollable frame of custom mod entries)
        mod_list_outer_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=(10,5))
        paned_window.add(mod_list_outer_frame, weight=1)

        ttk.Label(mod_list_outer_frame, text="Installed Mods (.jar files)", style='Header.TLabel').pack(anchor='w', pady=(0,5))
        
        # Canvas and Scrollbar for a scrollable mod list
        mod_list_canvas = tk.Canvas(mod_list_outer_frame, bg=SECONDARY_BG, highlightthickness=0)
        mod_list_scrollbar = ttk.Scrollbar(mod_list_outer_frame, orient="vertical", command=mod_list_canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_mod_list_frame = ttk.Frame(mod_list_canvas, style='CardInner.TFrame') # Frame that will hold the mod rows

        self.scrollable_mod_list_frame.bind(
            "<Configure>",
            lambda e: mod_list_canvas.configure(
                scrollregion=mod_list_canvas.bbox("all")
            )
        )
        mod_list_canvas.create_window((0, 0), window=self.scrollable_mod_list_frame, anchor="nw")
        mod_list_canvas.configure(yscrollcommand=mod_list_scrollbar.set)

        mod_list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mod_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # The old Treeview and its related widgets are removed here.
        # self.mods_tree = ttk.Treeview(...)
        # self.mods_tree.pack(...)
        # mod_scrollbar = ttk.Scrollbar(...)
        # self.mods_tree.bind("<<TreeviewSelect>>", self._on_mod_select)

        # Delete Mod Button - REMOVED (will be per-mod now)
        # self.delete_mod_button = ttk.Button(...)

        # Right Pane: Config Editor (remains mostly the same structure)
        config_editor_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=(10,5))
        paned_window.add(config_editor_frame, weight=2) # Give more weight to editor

        ttk.Label(config_editor_frame, text="Configuration File Editor", style='Header.TLabel').pack(anchor='w', pady=(0,5))
        self.mod_config_text_area = scrolledtext.ScrolledText(config_editor_frame, wrap=tk.WORD, height=15, 
                                                            bg=PRIMARY_BG, fg=TEXT_PRIMARY, 
                                                            insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM, 
                                                            relief='flat', borderwidth=1, highlightthickness=0, bd=1, padx=5, pady=5)
        self.mod_config_text_area.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        self.mod_config_text_area.configure(state='disabled') # Disabled initially

        self.save_mod_config_button = ttk.Button(config_editor_frame, text="Save Config Changes", command=self._save_mod_config, style="Accent.TButton", state=tk.DISABLED)
        self.save_mod_config_button.pack(anchor='se')
        # Hover managed by style map

        self.current_mod_config_path = None
        self.mod_data = [] # To store tuples of (jar_file, display_name, config_path_or_None)

        self._load_mods_list() # Initial load

    def _extract_mod_id(self, jar_filename):
        # Try to remove common versioning patterns and file extension
        # e.g., "jei-1.16.5-7.7.1.139.jar" -> "jei"
        # e.g., "OptiFine_1.16.5_HD_U_G8.jar" -> "OptiFine"
        # This is a heuristic and might need refinement for complex names
        match = re.match(r"([a-zA-Z0-9_]+)([-_ ]+[0-9].*)?(\.jar)", jar_filename, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        # Fallback: remove .jar and take the part before first digit/special char if common pattern fails
        name_part = jar_filename.replace(".jar", "")
        fallback_match = re.match(r"([a-zA-Z_]+)", name_part)
        return fallback_match.group(1).lower() if fallback_match else name_part.lower()

    def _find_mod_config_file(self, mod_id):
        if not os.path.isdir(self.config_dir_path):
            return None
        
        # Common config file extensions/patterns
        # Order matters: more specific (like -common) before generic
        config_patterns = [
            f"{mod_id}-common.toml", f"{mod_id}-client.toml", f"{mod_id}-server.toml",
            f"{mod_id}.toml", f"{mod_id}.cfg", f"{mod_id}.json", f"{mod_id}.properties",
            # Mod specific subfolders (e.g., /config/mod_id/mod_id.cfg or /config/mod_id/main.cfg)
            os.path.join(mod_id, f"{mod_id}.cfg"), os.path.join(mod_id, f"{mod_id}.toml"),
            os.path.join(mod_id, "main.cfg"), os.path.join(mod_id, "config.cfg"),
            # Add uppercase variants for direct files as well
            f"{mod_id}.TOML", f"{mod_id}.CFG", f"{mod_id}.JSON", f"{mod_id}.PROPERTIES", 
        ]
 
        for pattern in config_patterns:
            potential_path = os.path.join(self.config_dir_path, pattern)
            if os.path.isfile(potential_path):
                return potential_path
        
        # NEW: Search in all first-level subdirectories of config_dir_path
        try:
            for entry_name in os.listdir(self.config_dir_path):
                subfolder_path = os.path.join(self.config_dir_path, entry_name)
                if os.path.isdir(subfolder_path): # If this entry is a subdirectory
                    # Heuristic: If subfolder name shares a keyword with mod_id, search within it
                    # Make simple versions for comparison (lowercase, no spaces)
                    simple_subfolder_name = entry_name.lower().replace(" ", "").replace("-", "").replace("_", "")
                    simple_mod_id = mod_id.lower() # mod_id should already be somewhat clean

                    # Check if mod_id is related to subfolder_name (e.g., "l2library" and "L2 Config")
                    # Or if subfolder name is generic like "config" and mod_id indicates it, less likely useful here.
                    # Let's be a bit broad: if a significant part of mod_id is in subfolder name or vice versa.
                    # This is very heuristic. For "L2 Config" and "l2library", "l2" might be common.
                    # We can check for mod_id in simple_subfolder_name or simple_subfolder_name in mod_id for a loose match.
                    # A more robust way might involve a predefined mapping for known group folders if this is too broad/incorrect.
                    
                    # Updated Heuristic: If mod_id contains a part of the subfolder name (min 3 chars) or vice-versa
                    # Or if the subfolder name contains keywords like the mod_id itself.
                    keywords_from_mod_id = [simple_mod_id] # Can add more sophisticated keyword extraction from mod_id if needed
                    # Extract potential keywords from subfolder name (e.g., "L2 Config" -> "l2", "config")
                    subfolder_keywords = [kw for kw in re.split(r'[ _-]', entry_name.lower()) if len(kw) >= 2] 

                    match_found = False
                    for mod_kw in keywords_from_mod_id:
                        for sub_kw in subfolder_keywords:
                            if mod_kw.startswith(sub_kw) or sub_kw.startswith(mod_kw) or mod_kw.endswith(sub_kw) or sub_kw.endswith(mod_kw):
                                match_found = True
                                break
                        if match_found:
                            break
                    
                    if not match_found and len(simple_mod_id) > 3: # last resort, check if mod_id is in subfolder name
                        if simple_mod_id in simple_subfolder_name:
                            match_found = True

                    if match_found:
                        # If subfolder seems related, list its files and pick the first common config type
                        try:
                            for item_in_subfolder in os.listdir(subfolder_path):
                                full_item_path = os.path.join(subfolder_path, item_in_subfolder)
                                if os.path.isfile(full_item_path):
                                    if item_in_subfolder.lower().endswith(('.cfg', '.toml', '.json', '.properties')):
                                        # Heuristic: assume this config is for the mod if we are in a related subfolder.
                                        # If there are multiple configs, this picks the first one, which might not always be correct.
                                        # Check if filename *also* relates to mod_id for better precision
                                        simple_item_name = item_in_subfolder.lower().replace(".cfg", "").replace(".toml","").replace(".json","").replace(".properties","")
                                        if simple_mod_id in simple_item_name or simple_item_name in simple_mod_id: 
                                            return full_item_path # Higher confidence match
                                        # If not, but we are in a matched subfolder, maybe it is a general config for the group
                                        # For now, to be less greedy, let's only return if filename also matches
                                        # To be more greedy, we could return full_item_path here directly if a subfolder match was found.
                            # If no filename match within the subfolder, but subfolder was a keyword match, try to return the first config found.
                            # This is the L2 Config / mod.cfg type scenario we want to catch
                            for item_in_subfolder in os.listdir(subfolder_path):
                                full_item_path = os.path.join(subfolder_path, item_in_subfolder)
                                if os.path.isfile(full_item_path):
                                    if item_in_subfolder.lower().endswith(('.cfg', '.toml', '.json', '.properties')):
                                        return full_item_path # Return first config found in a matched subfolder
                        except OSError:
                            pass # Error listing subfolder contents

        except OSError: # Handle cases like permission errors when listing directory
            pass # Silently ignore for now, or log it
        
        return None

    def _load_mods_list(self):
        # Clear existing mod rows from the scrollable frame
        for widget in self.scrollable_mod_list_frame.winfo_children():
            widget.destroy()
        
        self.mod_data.clear()
        self.mod_config_text_area.configure(state='disabled')
        self.save_mod_config_button.config(state=tk.DISABLED)
        self.current_mod_config_path = None
        # self.delete_mod_button.config(state=tk.DISABLED) # Button removed
        self.current_selected_mod_info = None 
        self.mod_config_text_area.delete('1.0', tk.END)

        if not os.path.isdir(self.mods_dir_path):
            self.log_to_console(f"Mods directory not found: {self.mods_dir_path}\n", "warning")
            ttk.Label(self.scrollable_mod_list_frame, text=f"Mods folder not found: {self.mods_dir_path}").pack(pady=20)
            return

        try:
            jar_files = [f for f in os.listdir(self.mods_dir_path) if f.lower().endswith('.jar')]
            if not jar_files:
                 ttk.Label(self.scrollable_mod_list_frame, text="No .jar files found in the mods folder.").pack(pady=20)
                 # Ensure scrollregion is updated even if empty
                 self.scrollable_mod_list_frame.update_idletasks()
                 mod_list_canvas = self.scrollable_mod_list_frame.master
                 mod_list_canvas.configure(scrollregion=mod_list_canvas.bbox("all"))
                 return

            for jar_file in sorted(jar_files, key=str.lower):
                mod_id = self._extract_mod_id(jar_file)
                config_file_path = self._find_mod_config_file(mod_id)
                mod_info_dict = {'jar': jar_file, 'id': mod_id, 'config_path': config_file_path}
                self.mod_data.append(mod_info_dict) # Store for other methods

                # Create a row for each mod
                mod_row_frame = ttk.Frame(self.scrollable_mod_list_frame, style='CardInner.TFrame', padding=(10,8)) # Increased padding
                mod_row_frame.pack(fill=tk.X, expand=True, pady=(4,0), padx=5) # Increased pady and padx

                left_info_frame = ttk.Frame(mod_row_frame, style='CardInner.TFrame')
                left_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5)) # Added padx

                ttk.Label(left_info_frame, text=f"🧩 {jar_file}", style='TLabel', anchor='w', wraplength=250).pack(fill=tk.X, pady=(0,2)) # Added pady
                if config_file_path:
                    ttk.Label(left_info_frame, text=f"  └─ Config: {os.path.basename(config_file_path)}", style='TLabel', font=(FONT_UI_NORMAL[0], FONT_UI_NORMAL[1]-1), foreground=TEXT_SECONDARY, anchor='w', wraplength=230).pack(fill=tk.X)
                else:
                    ttk.Label(left_info_frame, text="  └─ Config: N/A", style='TLabel', font=(FONT_UI_NORMAL[0], FONT_UI_NORMAL[1]-1), foreground=TEXT_SECONDARY, anchor='w').pack(fill=tk.X)

                actions_frame_mod = ttk.Frame(mod_row_frame, style='CardInner.TFrame')
                actions_frame_mod.pack(side=tk.RIGHT, fill=tk.NONE, padx=(5,0)) # Added padx

                if config_file_path:
                    view_config_btn = ttk.Button(actions_frame_mod, text="⚙️ View", 
                                                 command=lambda m=mod_info_dict: self._load_mod_config_for_editing(m), 
                                                 style="ActionRow.TButton") # Use new style, remove width
                    view_config_btn.pack(side=tk.LEFT, padx=(0,5), ipady=0) # Rely on style padding
                
                delete_btn_mod = ttk.Button(actions_frame_mod, text="🗑️ Del", 
                                            command=lambda m=mod_info_dict: self._delete_specific_mod(m), 
                                            style="ActionRow.TButton") # Use new style, remove width
                delete_btn_mod.pack(side=tk.LEFT, ipady=0) # Rely on style padding
            
            # Update scrollregion after all mod rows are added
            self.scrollable_mod_list_frame.update_idletasks()
            mod_list_canvas = self.scrollable_mod_list_frame.master
            mod_list_canvas.configure(scrollregion=mod_list_canvas.bbox("all"))
            
        except Exception as e:
            self.log_to_console(f"Error loading mods list: {e}\n", "error")
            messagebox.showerror("Error Loading Mods", f"Failed to list mods: {e}")

    def _load_mod_config_for_editing(self, mod_info):
        """Loads the config file for the given mod_info into the text editor."""
        self.mod_config_text_area.configure(state='disabled')
        self.save_mod_config_button.config(state=tk.DISABLED)
        self.current_mod_config_path = None
        self.current_selected_mod_info = mod_info # Store for saving and context
        self.mod_config_text_area.delete('1.0', tk.END)

        config_path = mod_info.get('config_path')
        jar_name = mod_info.get('jar', 'Unknown Mod')

        if config_path:
            self.current_mod_config_path = config_path
            try:
                with open(self.current_mod_config_path, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                self.mod_config_text_area.configure(state='normal')
                self.mod_config_text_area.insert('1.0', config_content)
                self.save_mod_config_button.config(state=tk.NORMAL)
                self.log_to_console(f"Loaded config for {jar_name}: {os.path.basename(self.current_mod_config_path)}\n", "info")
            except Exception as e:
                self.log_to_console(f"Error loading mod config {self.current_mod_config_path}: {e}\n", "error")
                messagebox.showerror("Error Loading Config", f"Could not read {os.path.basename(self.current_mod_config_path)}:\n{e}")
                self.mod_config_text_area.insert('1.0', f"# Could not load: {os.path.basename(self.current_mod_config_path)}\n# Error: {e}")
        else:
            self.log_to_console(f"No associated config file found or loaded for {jar_name}.\n", "info")
            self.mod_config_text_area.insert('1.0', f"# No configuration file automatically detected for {jar_name}.")

    def _save_mod_config(self):
        if not self.current_mod_config_path: # Relies on current_mod_config_path being set by _load_mod_config_for_editing
            messagebox.showwarning("Save Error", "No configuration file is currently loaded for saving.")
            return
        if not self.mod_config_text_area.get("1.0", tk.END).strip(): # Check if empty
            messagebox.showwarning("Save Error", "Cannot save empty configuration.")
            return

        try:
            content_to_save = self.mod_config_text_area.get("1.0", tk.END).strip() # Get all content, strip trailing newline if any from ScrolledText
            # Ensure a newline at the end of the file as many configs expect it
            if not content_to_save.endswith('\n'):
                 content_to_save += '\n'

            with open(self.current_mod_config_path, 'w', encoding='utf-8') as f:
                f.write(content_to_save)
            self.log_to_console(f"Saved config: {os.path.basename(self.current_mod_config_path)}\n", "info")
            messagebox.showinfo("Save Successful", f"{os.path.basename(self.current_mod_config_path)} saved successfully.")
            # Optionally, reload the mod list or config to confirm changes visually or clear dirty state
        except Exception as e:
            self.log_to_console(f"Error saving mod config {self.current_mod_config_path}: {e}\n", "error")
            messagebox.showerror("Save Error", f"Could not save {os.path.basename(self.current_mod_config_path)}:\n{e}")

    def _open_mods_folder(self):
        if os.path.isdir(self.mods_dir_path):
            try:
                if sys.platform == "win32":
                    os.startfile(self.mods_dir_path)
                elif sys.platform == "darwin": # macOS
                    subprocess.run(["open", self.mods_dir_path], check=True)
                else: # Linux and other POSIX
                    subprocess.run(["xdg-open", self.mods_dir_path], check=True)
            except Exception as e:
                messagebox.showerror("Open Folder Error", f"Could not open mods folder: {e}")
        else:
            messagebox.showwarning("Open Folder Error", f"Mods folder not found: {self.mods_dir_path}")

    def _open_config_folder(self):
        if os.path.isdir(self.config_dir_path):
            try:
                if sys.platform == "win32":
                    os.startfile(self.config_dir_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", self.config_dir_path], check=True)
                else:
                    subprocess.run(["xdg-open", self.config_dir_path], check=True)
            except Exception as e:
                messagebox.showerror("Open Folder Error", f"Could not open config folder: {e}")
        else:
            messagebox.showwarning("Open Folder Error", f"Config folder not found: {self.config_dir_path}")

    def _delete_specific_mod(self, mod_info_to_delete):
        """Deletes the specified mod and its associated config file."""
        if not mod_info_to_delete or not mod_info_to_delete.get('jar'):
            messagebox.showwarning("Delete Error", "Mod information is incomplete.")
            return

        mod_jar_name = mod_info_to_delete['jar']
        mod_jar_path = os.path.join(self.mods_dir_path, mod_jar_name)
        
        config_path_to_delete = mod_info_to_delete.get('config_path')
        config_name_display = os.path.basename(config_path_to_delete) if config_path_to_delete else "no associated config file"

        confirm_message = f"Are you sure you want to delete the mod '{mod_jar_name}' and {config_name_display}? This action cannot be undone."
        if config_path_to_delete and not os.path.exists(config_path_to_delete):
            confirm_message = f"Are you sure you want to delete the mod '{mod_jar_name}'? (Associated config file {config_name_display} not found or already deleted). This action cannot be undone."
        elif not config_path_to_delete:
             confirm_message = f"Are you sure you want to delete the mod '{mod_jar_name}'? (No associated config file was detected). This action cannot be undone."

        if messagebox.askyesno("Confirm Delete Mod", confirm_message):
            deleted_jar = False
            deleted_config = False
            errors = []

            # Delete JAR file
            try:
                if os.path.exists(mod_jar_path):
                    os.remove(mod_jar_path)
                    self.log_to_console(f"Deleted mod JAR: {mod_jar_name}\n", "info")
                    deleted_jar = True
                else:
                    self.log_to_console(f"Mod JAR not found for deletion: {mod_jar_name}\n", "warning")
                    errors.append(f"JAR file '{mod_jar_name}' not found.")
            except Exception as e:
                self.log_to_console(f"Error deleting mod JAR {mod_jar_name}: {e}\n", "error")
                errors.append(f"Could not delete '{mod_jar_name}': {e}")

            # Delete associated config file
            if config_path_to_delete and os.path.exists(config_path_to_delete):
                try:
                    os.remove(config_path_to_delete)
                    self.log_to_console(f"Deleted associated config: {os.path.basename(config_path_to_delete)}\n", "info")
                    deleted_config = True
                except Exception as e:
                    self.log_to_console(f"Error deleting mod config {os.path.basename(config_path_to_delete)}: {e}\n", "error")
                    errors.append(f"Could not delete config '{os.path.basename(config_path_to_delete)}': {e}")
            
            if not errors:
                messagebox.showinfo("Delete Successful", f"Successfully deleted '{mod_jar_name}' and its associated configuration.")
            else:
                summary_message = "Deletion process completed with issues:\n"
                if deleted_jar: summary_message += f"- Mod '{mod_jar_name}' was deleted.\n"
                if deleted_config: summary_message += f"- Config '{config_name_display}' was deleted.\n"
                summary_message += "\nErrors encountered:\n" + "\n".join(errors)
                messagebox.showwarning("Delete Partially Successful", summary_message)

            self._load_mods_list() # Refresh the list
            
            # Clear editor if the deleted mod's config was being viewed
            if self.current_selected_mod_info and self.current_selected_mod_info.get('jar') == mod_jar_name:
                self.current_selected_mod_info = None
                self.current_mod_config_path = None
                self.mod_config_text_area.configure(state='normal') # Enable to clear
                self.mod_config_text_area.delete('1.0', tk.END)
                self.mod_config_text_area.configure(state='disabled')
                self.save_mod_config_button.config(state=tk.DISABLED)

    # --- APP SETTINGS & CHANGELOG ---
    def _create_app_settings_view_widgets(self, parent_frame):
        main_card = ttk.Frame(parent_frame, style='Card.TFrame', padding=15)
        main_card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Application Information Section ---
        info_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        info_card.pack(fill=tk.X, pady=(0,10)) # Fill X, place at top
        ttk.Label(info_card, text="Application Information", style='Header.TLabel').pack(anchor='w', pady=(0,10))
        
        app_name_text = "Minecraft Server Control GUI"
        app_version_text = "1.2.2" # Updated version
        app_author_text = "CalaKuad1"
        app_description_text = "A comprehensive tool to manage your Minecraft server with ease, view stats, manage players, mods, and more."

        ttk.Label(info_card, text=f"Name: {app_name_text}", style='TLabel').pack(anchor='w')
        ttk.Label(info_card, text=f"Version: {app_version_text}", style='TLabel').pack(anchor='w')
        ttk.Label(info_card, text=f"Author(s): {app_author_text}", style='TLabel').pack(anchor='w')
        # Update wraplength dynamically or set a reasonable fixed one
        # For dynamic, it needs to be done after the window is drawn or on configure events.
        # Simple approach: use a large enough fixed value based on typical window width.
        description_label = ttk.Label(info_card, text=f"Description: {app_description_text}", style='TLabel', wraplength=650) # Adjust wraplength as needed
        description_label.pack(anchor='w', pady=(5,0), fill=tk.X)

        # --- Changelog Section (Read-Only) ---
        changelog_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        changelog_card.pack(fill=tk.BOTH, expand=True, pady=(10,10))
        ttk.Label(changelog_card, text="Application Changelog", style='Header.TLabel').pack(anchor='w', pady=(0,10))

        self.changelog_text_area = scrolledtext.ScrolledText(changelog_card, wrap=tk.WORD, height=10,
                                                             bg=PRIMARY_BG, fg=TEXT_SECONDARY, 
                                                             insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM,
                                                             relief='flat', borderwidth=1, highlightthickness=0, bd=1, padx=5, pady=5)
        self.changelog_text_area.pack(fill=tk.BOTH, expand=True, pady=(0,0))
        # No Save Changelog button - it's read-only now

        # --- Placeholder for App Configuration Section ---
        app_config_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        app_config_card.pack(fill=tk.X, pady=(10,0))
        ttk.Label(app_config_card, text="Other Application Settings", style='Header.TLabel').pack(anchor='w', pady=(0,5))
        ttk.Label(app_config_card, text="(Future application-specific settings will appear here)", style='TLabel').pack(anchor='w', pady=(0,10))

        self._load_changelog() # Initial load

    def _load_changelog(self):
        self.changelog_text_area.configure(state='normal') # Enable to insert text
        self.changelog_text_area.delete('1.0', tk.END)
        try:
            if os.path.exists(self.changelog_path):
                with open(self.changelog_path, 'r', encoding='utf-8') as f:
                    changelog_content = f.read()
                self.changelog_text_area.insert('1.0', changelog_content)
            else:
                default_text = "# Application Changelog\n\n(Changelog file not found. This file should be created and maintained by the application developer.)\n"
                self.changelog_text_area.insert('1.0', default_text)
        except Exception as e:
            messagebox.showerror("Error Loading Changelog", f"Failed to load {self.changelog_path}:\n{e}")
            self.changelog_text_area.insert('1.0', f"# Error loading changelog: {e}")
        finally:
            self.changelog_text_area.configure(state='disabled') # Make read-only

    def _update_server_status_display(self):
        if self.server_running:
            if self.server_process: # Process started, considered "Online" or "Starting"
                 # More nuanced status could be added if server output indicates full startup
                self.server_status_label.config(text="Status: Online", style='StatusOnline.TLabel')
                self.restart_button.config(state=tk.NORMAL)
            else: # server_running is true, but process not yet up (e.g. during startup attempt)
                self.server_status_label.config(text="Status: Starting...", style='StatusStarting.TLabel')
                self.restart_button.config(state=tk.DISABLED) # Can't restart if not fully started or stopped
        else:
            self.server_status_label.config(text="Status: Offline", style='StatusOffline.TLabel')
            self.restart_button.config(state=tk.DISABLED) # Can't restart if offline (use Start)
        
        # Ensure top_bar_frame background is applied to labels if they don't fill it
        self.server_status_label.configure(background=TERTIARY_BG)

    def restart_server(self):
        if self.server_running and self.server_process:
            self.log_to_console("Restarting server...\n", "info")
            self.stop_server()
            # Need to wait for server to fully stop before starting again.
            # This can be tricky. A simple approach is a timed delay,
            # or better, check periodically if self.server_process is None.
            self.master.after(5000, self._check_if_stopped_then_start) # Wait 5s then check
            self.server_status_label.config(text="Status: Restarting...", style='StatusStarting.TLabel')
            self.restart_button.config(state=tk.DISABLED)
        elif not self.server_running:
            self.log_to_console("Server is not running. Starting it...\n", "info")
            self.start_server_thread()
        else: # Server might be in a stopping state or starting state without a full process
            messagebox.showwarning("Restart Server", "Server is currently in a transition state. Please wait.")

    def _check_if_stopped_then_start(self):
        if not self.server_running and self.server_process is None:
            self.log_to_console("Server stopped. Starting again for restart...\n", "info")
            self.start_server_thread()
        elif self.master.winfo_exists(): # If not stopped yet, check again shortly
            # Add a counter to prevent infinite loop if server fails to stop
            if not hasattr(self, '_restart_check_counter'):
                self._restart_check_counter = 0
            self._restart_check_counter += 1
            if self._restart_check_counter < 10: # Max 10 * 1s = 10 seconds of checks
                self.master.after(1000, self._check_if_stopped_then_start)
            else:
                self.log_to_console("Failed to stop server for restart. Please check server status and try starting manually.\n", "error")
                messagebox.showerror("Restart Error", "Server did not stop cleanly. Cannot complete restart.")
                self._update_server_status_display() # Reset status display
                self._restart_check_counter = 0 # Reset counter
        if hasattr(self, '_restart_check_counter') and self._restart_check_counter != 0 and (self.server_running or self.server_process is not None):
             # If successfully restarted, reset counter outside the <10 check
            pass # Will be reset when starting or if it fails
        if self.server_running and self.server_process is not None : # Successfully restarted
             self._restart_check_counter = 0

    @staticmethod
    def _generate_offline_uuid(username):
        # Minecraft offline UUID generation (version 3 based on MD5)
        # This method generates a UUID version 3, which is what Minecraft uses for offline players.
        # The input string "OfflinePlayer:" + username is hashed using MD5.
        # Specific bytes of the hash are then manipulated to set the UUID version and variant.
        hash_bytes = hashlib.md5(("OfflinePlayer:" + username).encode('utf-8')).digest()
        
        b = list(hash_bytes) # Convert bytes to list of ints for manipulation
        
        # Set version to 3 (xxxxxxxx-xxxx-3xxx-xxxx-xxxxxxxxxxxx)
        # This affects the 7th byte (index 6 of 0-indexed 16-byte array)
        b[6] = (b[6] & 0x0F) | 0x30
        
        # Set variant to Leach-Salz (RFC 4122: xxxxxxxx-xxxx-xxxx-Vxxx-xxxxxxxxxxxx where V is 8,9,A,or B)
        # This affects the 9th byte (index 8 of 0-indexed 16-byte array)
        b[8] = (b[8] & 0x3F) | 0x80
            
        return str(uuid.UUID(bytes=bytes(b)))

    def _create_placeholder_avatar(self, size=(24, 24)):
        try:
            img = Image.new('RGB', size, color = (120, 120, 120)) # Medium grey
            # Optionally, draw a character if you want more than a colored square
            # from PIL import ImageDraw
            # draw = ImageDraw.Draw(img)
            # try:
            #     font = ImageFont.truetype("arial", int(size[1]*0.7))
            # except IOError:
            #     font = ImageFont.load_default()
            # text = "?"
            # text_bbox = draw.textbbox((0,0), text, font=font)
            # text_width = text_bbox[2] - text_bbox[0]
            # text_height = text_bbox[3] - text_bbox[1]
            # position = ((size[0] - text_width) / 2, (size[1] - text_height) / 2 - int(size[1]*0.1)) # Adjust for better centering
            # draw.text(position, text, fill=(200,200,200), font=font)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            self.log_to_console(f"Error creating placeholder avatar: {e}", "error")
            return None

    def _update_avatar_label(self, label, photo_image):
        try:
            if label.winfo_exists():
                label.configure(image=photo_image)
                label.image = photo_image  # Keep a reference!
        except tk.TclError: # Widget might be destroyed
            pass
        except Exception as e:
            self.log_to_console(f"Error updating avatar label: {e}", "error")


    def _fetch_player_avatar_thread(self, player_identifier, avatar_label, size=(24, 24)):
        try:
            # Use a small, fixed size for the avatar request, e.g., 24px or 32px
            # The API endpoint is https://mineskin.eu/avatar/IDENTIFIER/SIZE
            api_size = size[0] # Assuming square avatars, use width for API size parameter
            url = f"https://mineskin.eu/avatar/{player_identifier}/{api_size}"
            # self.log_to_console(f"Fetching avatar for '{player_identifier}' from {url}", "info") # Commented out for cleaner console
            
            response = requests.get(url, timeout=10) # Increased timeout slightly
            response.raise_for_status()  # Raise HTTPError for bad responses (4XX or 5XX)

            image_data = response.content
            if not image_data:
                self.log_to_console(f"Avatar fetch for '{player_identifier}': No image data received.", "warning")
                return

            img = Image.open(io.BytesIO(image_data))
            img = img.convert("RGBA") # Ensure consistent format, handling transparency
            img = img.resize(size, Image.Resampling.LANCZOS) # Resize to desired display size
            photo_img = ImageTk.PhotoImage(img)

            self.avatar_cache[player_identifier] = photo_img # Store in cache
            self.master.after(0, self._update_avatar_label, avatar_label, photo_img)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # self.log_to_console(f"Avatar not found for '{player_identifier}' (404).", "info") # Commented out for cleaner console
                pass # Still handle the 404 gracefully, just don't log to console by default
            else:
                self.log_to_console(f"Avatar fetch HTTP error for '{player_identifier}': {e}", "warning")
        except requests.exceptions.RequestException as e:
            self.log_to_console(f"Avatar fetch network error for '{player_identifier}': {e}", "warning")
        except UnidentifiedImageError:
            self.log_to_console(f"Avatar fetch for '{player_identifier}': Content is not a valid image.", "warning")
        except Exception as e:
            self.log_to_console(f"Generic avatar fetch error for '{player_identifier}': {e}", "error")


    def _fetch_player_avatar(self, player_identifier, avatar_label, size=(24, 24)):
        if not player_identifier or player_identifier == 'N/A':
            # Don't attempt to fetch for invalid identifiers
            if self.placeholder_avatar and avatar_label.winfo_exists():
                 self.master.after(0, self._update_avatar_label, avatar_label, self.placeholder_avatar)
            return

        # Check cache first
        if player_identifier in self.avatar_cache:
            cached_avatar = self.avatar_cache[player_identifier]
            if avatar_label.winfo_exists():
                self.master.after(0, self._update_avatar_label, avatar_label, cached_avatar)
            return

        # Set placeholder initially
        if self.placeholder_avatar and avatar_label.winfo_exists():
            # Configure might fail if label is already destroyed, guard it
            try:
                avatar_label.configure(image=self.placeholder_avatar)
                avatar_label.image = self.placeholder_avatar
            except tk.TclError:
                 pass


        thread = threading.Thread(target=self._fetch_player_avatar_thread, args=(player_identifier, avatar_label, size))
        thread.daemon = True
        thread.start()

    def _handle_global_click(self, event):
        # This will call _spawn_click_effect
        # Check if the click is on the click_effect_canvas itself to prevent re-triggering
        if event.widget == self.click_effect_drawing_canvas:
            return
        
        # Add more sophisticated checks here if needed to prevent effects on certain UI areas.
        # For example, you might want to check if event.widget is a child of self.sidebar_frame
        # or other specific frames where you don't want the click effect.
        # For now, we proceed if it's not the click_effect_canvas itself.

        self._spawn_click_effect(event.x, event.y)

    def _spawn_click_effect(self, x, y):
        # Cancel any pending hide operation for the click canvas
        if self.click_effect_toplevel_after_id:
            self.master.after_cancel(self.click_effect_toplevel_after_id)
            self.click_effect_toplevel_after_id = None

        # Clear any previous click particles from the canvas and our list
        for p_old in self.click_effect_particles:
            if p_old.get('id') and self.click_effect_drawing_canvas.winfo_exists():
                try:
                    self.click_effect_drawing_canvas.delete(p_old['id'])
                except tk.TclError: # Item might already be gone
                    pass
        self.click_effect_particles.clear()

        # Make the click effect canvas visible and on top
        self.click_effect_drawing_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        # self.click_effect_canvas.lift() # Incorrect for lifting the widget
        tk.Misc.lift(self.click_effect_drawing_canvas) # Correct way to lift the canvas widget

        num_burst_particles = 30  # Number of particles in a burst
        particle_lifetime = 25    # Animation frames (approx 0.5 - 0.8s at ~30-50fps)

        for _ in range(num_burst_particles):
            size = random.uniform(2, 6) # Slightly larger and more variable for effect
            # Faster, more outward velocity
            dx = random.uniform(-2.0, 2.0) 
            dy = random.uniform(-2.0, 2.0)
            while abs(dx) < 0.2 and abs(dy) < 0.2: # Ensure noticeable movement
                dx = random.uniform(-2.0, 2.0)
                dy = random.uniform(-2.0, 2.0)

            color = ACCENT_COLOR # Use accent color for visibility
            # Create particle on the click_effect_canvas
            particle_id = self.click_effect_drawing_canvas.create_oval(x, y, x + size, y + size, fill=color, outline="")
            
            self.click_effect_particles.append({
                'id': particle_id,
                'x': x,
                'y': y,
                'dx': dx,
                'dy': dy,
                'size': size,
                'color': color,
                'lifetime': particle_lifetime
            })
        
        # Schedule the canvas to hide after a short duration
        self.click_effect_toplevel_after_id = self.master.after(700, self._hide_click_effect_canvas) # Hide after 700ms

    def _hide_click_effect_canvas(self):
        if self.click_effect_drawing_canvas.winfo_exists():
            self.click_effect_drawing_canvas.place_forget()
        
        # Also clear any remaining particle items from the canvas if any (should be handled by animation, but good practice)
        for p_old in self.click_effect_particles:
            if p_old.get('id') and self.click_effect_drawing_canvas.winfo_exists():
                try:
                    self.click_effect_drawing_canvas.delete(p_old['id'])
                except tk.TclError:
                    pass # Item might already be gone or canvas destroyed
        self.click_effect_particles.clear()
        self.click_effect_toplevel_after_id = None

    def _animate_particles(self):
        if not self.master.winfo_exists(): # Stop animation if window is destroyed
            return

        # --- Animate Background Particles (on self.particle_canvas) ---
        current_bg_canvas_width = self.particle_canvas.winfo_width()
        current_bg_canvas_height = self.particle_canvas.winfo_height()

        if current_bg_canvas_width <= 1 or current_bg_canvas_height <= 1: # Background canvas not ready
            # We don't want to reschedule the entire animation loop if only the background is not ready
            # but the click effect might be. However, this early return is for the main particle init.
            # If background particles are not initialized, it's okay to wait.
            self.master.after(50, self._animate_particles) 
            return
        
        if not self.particles_initialized or \
           self.canvas_width != current_bg_canvas_width or \
           self.canvas_height != current_bg_canvas_height:
            
            self.canvas_width = current_bg_canvas_width
            self.canvas_height = current_bg_canvas_height
            
            for p in self.particles: # Background particles
                p['x'] = random.uniform(0, self.canvas_width - p['size'])
                p['y'] = random.uniform(0, self.canvas_height - p['size'])
                self.particle_canvas.coords(p['id'], p['x'], p['y'], p['x'] + p['size'], p['y'] + p['size'])
            self.particles_initialized = True
        
        if self.particles_initialized: # Only animate background particles if initialized
            for p in self.particles:
                current_coords = self.particle_canvas.coords(p['id'])
                if not current_coords: 
                    continue
                p['x'] += p['dx']
                p['y'] += p['dy']
                if p['x'] < 0 or (p['x'] + p['size']) > self.canvas_width:
                    p['dx'] *= -1
                    p['x'] = max(0, min(p['x'], self.canvas_width - p['size'])) 
                if p['y'] < 0 or (p['y'] + p['size']) > self.canvas_height:
                    p['dy'] *= -1
                    p['y'] = max(0, min(p['y'], self.canvas_height - p['size'])) 
                self.particle_canvas.coords(p['id'], p['x'], p['y'], p['x'] + p['size'], p['y'] + p['size'])
        
        # --- Animate Click Effect Particles (on self.click_effect_drawing_canvas) ---
        if self.click_effect_drawing_canvas.winfo_ismapped() and self.click_effect_particles:
            # Use a copy for iteration if modifying the list (e.g., removing particles)
            particles_to_remove = []
            click_canvas_width = self.click_effect_drawing_canvas.winfo_width()
            click_canvas_height = self.click_effect_drawing_canvas.winfo_height()

            for p_click in self.click_effect_particles:
                p_click['lifetime'] -= 1
                if p_click['lifetime'] <= 0:
                    particles_to_remove.append(p_click)
                    if self.click_effect_drawing_canvas.winfo_exists():
                        try:
                            self.click_effect_drawing_canvas.delete(p_click['id'])
                        except tk.TclError:
                            pass # Item might already be gone
                    continue

                p_click['x'] += p_click['dx']
                p_click['y'] += p_click['dy']

                # Boundary collision for click particles (within the full click_effect_canvas)
                if p_click['x'] < 0 or (p_click['x'] + p_click['size']) > click_canvas_width:
                    p_click['dx'] *= -1
                    p_click['x'] = max(0, min(p_click['x'], click_canvas_width - p_click['size']))
                if p_click['y'] < 0 or (p_click['y'] + p_click['size']) > click_canvas_height:
                    p_click['dy'] *= -1
                    p_click['y'] = max(0, min(p_click['y'], click_canvas_height - p_click['size']))
                
                if self.click_effect_drawing_canvas.winfo_exists():
                    try:
                        self.click_effect_drawing_canvas.coords(p_click['id'], p_click['x'], p_click['y'], p_click['x'] + p_click['size'], p_click['y'] + p_click['size'])
                    except tk.TclError:
                        pass # Item might have been deleted by hide_canvas
            
            for p_remove in particles_to_remove:
                if p_remove in self.click_effect_particles:
                    self.click_effect_particles.remove(p_remove)

        self.master.after(50, self._animate_particles) # Reschedule the main animation loop


if __name__ == "__main__":
    root = tk.Tk() # Ya no es ThemedTk
    # Los estilos globales se definen dentro de ServerControlGUI
    gui = ServerControlGUI(root)
    root.mainloop()

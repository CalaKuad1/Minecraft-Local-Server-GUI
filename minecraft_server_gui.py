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
PRIMARY_BG = '#18191A'
SECONDARY_BG = '#242526'
TERTIARY_BG = '#3A3B3C'
ACCENT_COLOR = '#00A2FF'
ACCENT_HOVER = '#007ACC'
TEXT_PRIMARY = '#E4E6EB'
TEXT_SECONDARY = '#B0B3B8'
CONSOLE_FG_CUSTOM = '#33FF57'
ERROR_FG_CUSTOM = '#FF4D4D'
WARNING_FG_CUSTOM = '#FFBB33'
# Tipografía Moderna
FONT_UI_NORMAL = ('Segoe UI', 11)
FONT_UI_BOLD = ('Segoe UI Semibold', 12)
FONT_UI_TITLE = ('Segoe UI Light', 22)
FONT_CONSOLE_CUSTOM = ('Consolas', 11)

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

        # Particle Animation Canvas - Placed early to be in the background
        self._init_particle_animation() # Call before other widgets if it fills the whole window

        # Inicializar atributos de estado del servidor ANTES de crear widgets que puedan usarlos
        self.server_process = None
        self.server_running = False

        # Selection states for various lists
        self.selected_player_name = None # For kick/ban actions
        self.selected_banned_ip = None
        self.selected_banned_player_name = None # Store name for pardon command
        self.current_selected_mod_info = None # For mod config loading and deletion

        self.style = ttk.Style()
        self.style.theme_use('default') # Empezar con un tema base simple de Tk

        # --- Definición de Estilos Personalizados --- 
        self.style.configure('.', background=PRIMARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL, borderwidth=0, focusthickness=0, highlightthickness=0)
        self.style.configure('TFrame', background=PRIMARY_BG)
        # Card.TFrame: For main cards, now with a border
        self.style.configure('Card.TFrame', background=SECONDARY_BG, relief='solid', borderwidth=1, bordercolor=TERTIARY_BG)
        # CardInner.TFrame: For frames within a Card, sharing Card's BG but no extra border
        self.style.configure('CardInner.TFrame', background=SECONDARY_BG)

        self.style.configure('TLabel', background=SECONDARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL, padding=5)
        self.style.configure('Title.TLabel', background=SECONDARY_BG, foreground=ACCENT_COLOR, font=FONT_UI_TITLE, padding=(10,15,10,10))
        self.style.configure('Header.TLabel', background=SECONDARY_BG, foreground=TEXT_SECONDARY, font=FONT_UI_BOLD, padding=6)
        
        # Pestañas (Notebook)
        self.style.configure('TNotebook', background=PRIMARY_BG, borderwidth=0)
        self.style.configure('TNotebook.Tab', font=FONT_UI_BOLD, padding=[18, 8], relief='flat')
        self.style.map('TNotebook.Tab',
                       background=[('selected', SECONDARY_BG), ('!selected', PRIMARY_BG)],
                       foreground=[('selected', ACCENT_COLOR), ('!selected', TEXT_SECONDARY)],
                       expand=[('selected', [1, 1, 1, 0])]) # Ligero relieve en la pestaña activa

        # Botones
        button_padding = [12, 8, 12, 8]
        self.style.configure('Accent.TButton', font=FONT_UI_BOLD, padding=button_padding, relief='flat', borderwidth=0)
        self.style.map('Accent.TButton', 
                       background=[('pressed', ACCENT_HOVER), ('active', ACCENT_HOVER), ('', ACCENT_COLOR)], 
                       foreground=[('', PRIMARY_BG)])
        self.style.configure('Accent2.TButton', font=FONT_UI_BOLD, padding=button_padding, relief='flat', borderwidth=0)
        self.style.map('Accent2.TButton',
                       background=[('pressed', ACCENT_COLOR), ('active', ACCENT_COLOR), ('', TERTIARY_BG)],
                       foreground=[('', TEXT_PRIMARY)])
        
        self.style.configure('TSeparator', background=TERTIARY_BG)
        
        # Estilos para TEntry (cajas de texto)
        self.style.configure('TEntry',
                             fieldbackground=PRIMARY_BG,
                             foreground=TEXT_PRIMARY,
                             insertcolor=ACCENT_COLOR, # Color del cursor
                             font=FONT_UI_NORMAL,
                             padding=(6,6),
                             relief='flat',
                             borderwidth=1)
        self.style.map('TEntry',
                       bordercolor=[('focus', ACCENT_COLOR), ('', TERTIARY_BG)],
                       fieldbackground=[('focus', SECONDARY_BG), ('disabled', SECONDARY_BG)],
                       foreground=[('focus', ACCENT_COLOR), ('disabled', TEXT_SECONDARY)])

        # Estilos para TCombobox (listas desplegables)
        self.style.configure('TCombobox',
                             fieldbackground=PRIMARY_BG,
                             foreground=TEXT_PRIMARY,
                             selectbackground=SECONDARY_BG, # Fondo del item seleccionado en el dropdown
                             selectforeground=ACCENT_COLOR, # Texto del item seleccionado en el dropdown
                             insertcolor=ACCENT_COLOR, # Cursor
                             arrowcolor=TEXT_PRIMARY,
                             font=FONT_UI_NORMAL,
                             padding=(6,6), # Padding igual que TEntry
                             relief='flat')
        self.style.map('TCombobox',
                       bordercolor=[('focus', ACCENT_COLOR), ('readonly', TERTIARY_BG), ('', TERTIARY_BG)],
                       fieldbackground=[
                           ('readonly', PRIMARY_BG),      # Estado por defecto para props (son readonly)
                           ('focus', SECONDARY_BG),       # Al enfocar (si no es readonly)
                           ('active', SECONDARY_BG),      # Cuando el dropdown está activo
                           ('disabled', SECONDARY_BG)
                       ],
                       foreground=[
                           ('readonly', TEXT_PRIMARY),    # Texto por defecto para props
                           ('focus', ACCENT_COLOR),       # Texto al enfocar
                           ('disabled', TEXT_SECONDARY)
                       ],
                       arrowcolor=[('hover', ACCENT_COLOR), ('pressed', ACCENT_COLOR), ('readonly', TEXT_PRIMARY), ('disabled', TEXT_SECONDARY)],
                       background=[ # Color de fondo del widget combobox (área de la flecha)
                           ('readonly', PRIMARY_BG),
                           ('active', SECONDARY_BG),
                           ('hover', SECONDARY_BG),
                           ('disabled', PRIMARY_BG)
                       ])
        # Para el Listbox DENTRO del Combobox (necesario para algunos temas/plataformas)
        self.master.option_add('*TCombobox*Listbox.background', SECONDARY_BG)
        self.master.option_add('*TCombobox*Listbox.foreground', TEXT_PRIMARY)
        self.master.option_add('*TCombobox*Listbox.selectBackground', ACCENT_COLOR)
        self.master.option_add('*TCombobox*Listbox.selectForeground', PRIMARY_BG)
        self.master.option_add('*TCombobox*Listbox.font', FONT_UI_NORMAL)
        self.master.option_add('*TCombobox*Listbox.borderWidth', 0)
        self.master.option_add('*TCombobox*Listbox.relief', 'flat')

        # Scrollbars (requiere más trabajo para un look 100% custom)
        self.style.configure("Vertical.TScrollbar", background=TERTIARY_BG, troughcolor=SECONDARY_BG, bordercolor=TERTIARY_BG, arrowcolor=TEXT_PRIMARY, gripcount=0)
        self.style.map("Vertical.TScrollbar", background=[('active', ACCENT_COLOR)])

        # Custom Treeview style for use on cards
        self.style.configure('CardView.Treeview',
                             background=SECONDARY_BG,
                             fieldbackground=SECONDARY_BG, # Background of the item area
                             foreground=TEXT_PRIMARY,
                             rowheight=28, # Increased row height for better spacing
                             font=FONT_UI_NORMAL,
                             relief='flat',
                             borderwidth=0)
        self.style.map('CardView.Treeview',
                       background=[('selected', ACCENT_HOVER)],
                       foreground=[('selected', TEXT_PRIMARY)]) # Ensure selected text is readable

        self.style.configure('CardView.Treeview.Heading',
                             background=TERTIARY_BG, # A slightly different background for headers
                             foreground=TEXT_PRIMARY,
                             font=FONT_UI_BOLD,
                             relief='flat', # Flat look for headings
                             padding=(8, 8)) # Generous padding for headings
        self.style.map('CardView.Treeview.Heading',
                       background=[('active', ACCENT_COLOR), ('hover', ACCENT_COLOR)], # Highlight on hover/active
                       relief=[('active', 'groove'), ('hover', 'ridge')])

        # Estilo para Checkbutton (usado como Switch)
        self.style.configure('Switch.TCheckbutton', font=FONT_UI_NORMAL, padding=5)
        self.style.map('Switch.TCheckbutton',
                       indicatorcolor=[('selected', ACCENT_COLOR), ('!selected', TERTIARY_BG)],
                       background=[('active', SECONDARY_BG)], foreground=[('', TEXT_PRIMARY)]) # Fondo del texto

        # Eliminar selector de tema (ya no se usa ttkthemes)
        # --- Fin de Estilos --- 

        # Flag for multi-line player list parsing - Initialize these BEFORE load_server_properties
        self.expecting_player_list_next_line = False
        self.player_count_line_prefix = "There are " 
        self.player_count_line_suffix = " players online:"

        self._init_particle_animation()

        # Pestañas con iconos (los iconos se mantienen)
        self.notebook = ttk.Notebook(master, style='TNotebook')
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=15, pady=15)
        
        # Los frames de las pestañas usan el estilo base TFrame (PRIMARY_BG)
        # Las tarjetas internas usarán 'Card.TFrame' (SECONDARY_BG)
        self.control_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.control_tab, text='🖥️  Server Control')
        self._create_control_tab_widgets()
        self.properties_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.properties_tab, text='⚙️  Server Properties')
        self._create_properties_tab_widgets()
        self.resources_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.resources_tab, text='📈 System Resources')
        self._create_resources_tab_widgets()
        self.players_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.players_tab, text='👥 Players')
        self._create_players_tab_widgets()
        self.ops_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.ops_tab, text='⭐ Operators')
        self._create_ops_tab_widgets()
        self.worlds_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.worlds_tab, text='🌍 Worlds')
        self._create_worlds_tab_widgets()
        self.stats_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.stats_tab, text='📊 Statistics')
        self._create_stats_tab_widgets()
        self.bans_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.bans_tab, text='🚫 Bans')
        self._create_bans_tab_widgets()
        self.mods_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.mods_tab, text='🧩 Mods')
        self._create_mods_tab_widgets()
        self.app_settings_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.app_settings_tab, text='⚙️ App Settings')
        self._create_app_settings_tab_widgets()

        self.load_server_properties()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _init_particle_animation(self):
        self.particle_canvas = tk.Canvas(self.master, bg=PRIMARY_BG, highlightthickness=0)
        self.particle_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.master.lower(self.particle_canvas) # Ensure canvas is behind other widgets

        self.particles = []
        self.num_particles = 70 # Increased number of particles
        self.particle_colors = [TEXT_SECONDARY, TERTIARY_BG, '#555555', '#6C6C6C', '#7F7F7F'] # Adjusted for more visibility
        
        # Get current window dimensions; may need to update if window resizes significantly
        # For simplicity, we'll use initial geometry. For responsive particles, a resize handler is needed.
        self.master.update_idletasks() # Ensure geometry is up-to-date
        self.canvas_width = self.master.winfo_width()
        self.canvas_height = self.master.winfo_height()

        for _ in range(self.num_particles):
            x = random.uniform(0, self.canvas_width)
            y = random.uniform(0, self.canvas_height)
            size = random.uniform(2, 4) # Increased size
            # Slightly faster speeds
            dx = random.uniform(-0.5, 0.5) 
            dy = random.uniform(-0.5, 0.5)
            # Ensure particles have some movement
            while abs(dx) < 0.1 and abs(dy) < 0.1: # Ensure some minimum movement
                dx = random.uniform(-0.5, 0.5)
                dy = random.uniform(-0.5, 0.5)

            color = random.choice(self.particle_colors)
            # Create the particle on the canvas and store its ID and properties
            particle_id = self.particle_canvas.create_oval(x, y, x + size, y + size, fill=color, outline="")
            self.particles.append({'id': particle_id, 'x': x, 'y': y, 'dx': dx, 'dy': dy, 'size': size, 'color': color})
        
        self._animate_particles()

    def _animate_particles(self):
        if not self.master.winfo_exists(): # Stop animation if window is destroyed
            return

        # Update canvas dimensions in case of resize (simple approach)
        # A more robust way involves binding to <Configure> event on the canvas or master
        current_width = self.master.winfo_width()
        current_height = self.master.winfo_height()
        if self.canvas_width != current_width or self.canvas_height != current_height:
            self.canvas_width = current_width
            self.canvas_height = current_height
            # Could optionally re-initialize particles or adjust their positions here

        for p in self.particles:
            current_coords = self.particle_canvas.coords(p['id'])
            if not current_coords: # Particle might have been deleted or canvas cleared
                continue

            # Update internal position based on dx, dy
            p['x'] += p['dx']
            p['y'] += p['dy']

            # Boundary checks (bounce)
            if p['x'] < 0 or (p['x'] + p['size']) > self.canvas_width:
                p['dx'] *= -1
                p['x'] = max(0, min(p['x'], self.canvas_width - p['size'])) # Clamp position
            if p['y'] < 0 or (p['y'] + p['size']) > self.canvas_height:
                p['dy'] *= -1
                p['y'] = max(0, min(p['y'], self.canvas_height - p['size'])) # Clamp position
            
            # Move the particle on canvas
            self.particle_canvas.coords(p['id'], p['x'], p['y'], p['x'] + p['size'], p['y'] + p['size'])
        
        self.master.after(30, self._animate_particles) # Approx 33 FPS

    def _on_tab_changed(self, event):
        selected_tab_index = self.notebook.index(self.notebook.select())
        # Players tab is index 3 (0-indexed)
        # Worlds tab is index 5
        # Stats tab is index 6
        # Bans tab is index 7 (newly added)
        # Mods tab is index 8 (newly added)
        # App Settings tab is index 9 (newly added)
        if selected_tab_index == 3: # Players tab
            if self.server_running: # Only update if server is supposed to be running
                self.update_players_list()
        elif selected_tab_index == 7: # Bans tab
            self._load_bans()
        elif selected_tab_index == 8: # Mods tab
            self._load_mods_list()
        elif selected_tab_index == 9: # App Settings tab
            self._load_changelog()

    def _bind_hover(self, widget, normal_bg, hover_bg):
        # Necesita acceder a widget.cget("style") y parsearlo o tener estilos dedicados para hover
        # Por simplicidad, vamos a reconfigurar el background directamente
        # Esto puede no funcionar bien con todos los temas/widgets ttk si tienen layouts complejos.
        original_style = widget.cget("style")
        def on_enter(e):
            widget.configure(style=original_style) # Reset por si acaso
            widget.master.configure(bg=hover_bg) # Esto es un hack, idealmente se usa un estilo de hover
            widget.configure(background=hover_bg)
        def on_leave(e):
            widget.configure(style=original_style)
            widget.master.configure(bg=normal_bg)
            widget.configure(background=normal_bg)
        # Los estilos map de ttk son mejores para esto, el bind manual de bg puede ser problemático.
        # Mantendré los map para TButton y este bind_hover lo quitaremos o refactorizaremos.
        pass # Se usará ttk.Style().map para hover de botones

    def _create_control_tab_widgets(self):
        # Tarjeta visual para controles
        card = ttk.Frame(self.control_tab, style='Card.TFrame', padding=25)
        card.pack(fill=tk.X, pady=(0, 20), padx=10)

        title = ttk.Label(card, text="Server Controls", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        controls_frame = ttk.Frame(card, style='CardInner.TFrame') # Fondo de tarjeta
        controls_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(controls_frame, text="Start Server", command=self.start_server_thread, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=10, ipadx=15, ipady=8)
        self._bind_hover(self.start_button, ACCENT_COLOR, ACCENT_HOVER)

        self.stop_button = ttk.Button(controls_frame, text="Stop Server", command=self.stop_server, state=tk.DISABLED, style="Accent2.TButton")
        self.stop_button.pack(side=tk.LEFT, padx=10, ipadx=15, ipady=8)
        self._bind_hover(self.stop_button, TERTIARY_BG, ACCENT_COLOR)

        sep = ttk.Separator(self.control_tab, orient='horizontal')
        sep.pack(fill=tk.X, pady=20, padx=10)

        console_card = ttk.Frame(self.control_tab, style='Card.TFrame', padding=25)
        console_card.pack(expand=True, fill=tk.BOTH, padx=10)
        console_label = ttk.Label(console_card, text="Server Console", style='Title.TLabel')
        console_label.pack(anchor='w', pady=(0, 15))
        self.console_output_area = scrolledtext.ScrolledText(console_card, wrap=tk.WORD, height=15, 
                                                            bg=PRIMARY_BG, fg=CONSOLE_FG_CUSTOM, 
                                                            insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM, 
                                                            relief='flat', borderwidth=0, highlightthickness=0, bd=0, padx=10, pady=10)
        self.console_output_area.pack(expand=True, fill=tk.BOTH)
        self.console_output_area.configure(state='disabled')
        self.console_output_area.tag_configure("error", foreground=ERROR_FG_CUSTOM)
        self.console_output_area.tag_configure("info", foreground=ACCENT_COLOR)
        self.console_output_area.tag_configure("warning", foreground=WARNING_FG_CUSTOM)
        self.console_output_area.tag_configure("usercmd", foreground=CONSOLE_FG_CUSTOM, font=(FONT_CONSOLE_CUSTOM[0], FONT_CONSOLE_CUSTOM[1], 'bold'))
        self.console_output_area.tag_configure("normal", foreground=TEXT_SECONDARY)

        entry_frame = ttk.Frame(console_card, style='CardInner.TFrame')
        entry_frame.pack(fill=tk.X, pady=(15, 0))
        self.command_entry = ttk.Entry(entry_frame, font=FONT_CONSOLE_CUSTOM, style='TEntry')
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=10, ipadx=10)
        self.command_entry.bind('<Return>', self.send_command_from_entry)
        self.command_entry.config(state='disabled')
        # Placeholder
        self.command_entry.insert(0, 'Type a command here...')
        self.command_entry.config(foreground='#888888') # Placeholder color

        def on_focus_in(event):
            if self.command_entry.get() == 'Type a command here...':
                self.command_entry.delete(0, tk.END)
                self.command_entry.config(foreground=TEXT_PRIMARY) # Use styled foreground for normal text
        def on_focus_out(event):
            if not self.command_entry.get():
                self.command_entry.insert(0, 'Type a command here...')
                self.command_entry.config(foreground='#888888') # Placeholder color
        self.command_entry.bind('<FocusIn>', on_focus_in)
        self.command_entry.bind('<FocusOut>', on_focus_out)
        # Botón Send grande y alineado a la derecha
        send_btn = ttk.Button(entry_frame, text='Send', command=self.send_command_from_button, style='Accent.TButton')
        send_btn.pack(side=tk.RIGHT, ipadx=16, ipady=6)
        self._bind_hover(send_btn, ACCENT_COLOR, ACCENT_HOVER)
        self.send_btn = send_btn
        self.send_btn.config(state='disabled')

    def _create_properties_tab_widgets(self):
        # Frame principal para la pestaña de propiedades, con scroll
        container = ttk.Frame(self.properties_tab, style='Card.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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

        canvas.pack(side="left", fill="both", expand=True, padx=(20,0), pady=20)
        scrollbar.pack(side="right", fill="y", padx=(0,20), pady=20)

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
                                                              relief='flat', borderwidth=0, highlightthickness=0, bd=0, padx=5, pady=5)
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
            widget.pack(side=tk.LEFT)
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

    def _create_resources_tab_widgets(self):
        card = ttk.Frame(self.resources_tab, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True)
        title = ttk.Label(card, text="Server Resource Usage", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Info de depuración
        self.debug_label = ttk.Label(card, text="", style='TLabel', font=("Consolas", 9))
        self.debug_label.pack(anchor='w', pady=(0, 10))

        # CPU
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

        # RAM
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

        # --- Gráficos en tiempo real ---
        self.cpu_history = [0]*60
        self.ram_history = [0]*60
        self.time_history = list(range(-59, 1))
        graph_frame = ttk.Frame(card, style='TFrame') # Usar TFrame base oscuro
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=(30,0))
        fig = Figure(figsize=(7,2.5), dpi=100, facecolor=PRIMARY_BG)
        self.ax_cpu = fig.add_subplot(211)
        self.ax_ram = fig.add_subplot(212)
        # --- Estética moderna ---
        for ax, color, title in [
            (self.ax_cpu, ACCENT_COLOR, 'CPU (%)'),
            (self.ax_ram, ACCENT_COLOR, 'RAM (%)')]:
            ax.set_facecolor(PRIMARY_BG)
            ax.set_title(title, color=color, fontsize=12, fontweight='bold', pad=10)
            ax.tick_params(axis='x', colors='#888888', labelsize=8)
            ax.tick_params(axis='y', colors=color, labelsize=10)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#444444')
            ax.spines['left'].set_color(color)
            ax.grid(True, color='#222222', linestyle='--', linewidth=0.7, alpha=0.7)
        self.line_cpu, = self.ax_cpu.plot(self.time_history, self.cpu_history, color=ACCENT_COLOR, linewidth=2.5, alpha=0.9)
        self.line_ram, = self.ax_ram.plot(self.time_history, self.ram_history, color=ACCENT_COLOR, linewidth=2.5, alpha=0.9)
        self.ax_cpu.set_ylim(0, 100)
        self.ax_ram.set_ylim(0, 100)
        self.ax_cpu.set_xlim(-59, 0)
        self.ax_ram.set_xlim(-59, 0)
        self.ax_cpu.set_ylabel('%', color=ACCENT_COLOR, fontsize=10, fontweight='bold')
        self.ax_ram.set_ylabel('%', color=ACCENT_COLOR, fontsize=10, fontweight='bold')
        self.ax_cpu.set_xticks([])
        self.ax_ram.set_xticks([])
        fig.tight_layout(pad=2.0)
        self.canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        self.canvas.get_tk_widget().configure(bg=PRIMARY_BG) # Fondo del widget canvas
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=(10,0))
        self.fig = fig

        # Inicia actualización periódica
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
        self.master.after(1000, self._update_resource_usage)

    def load_server_properties(self):
        # Limpiar widgets de propiedades anteriores y datos almacenados
        for widget_tuple in self.property_widgets.values():
            # El widget principal es el prop_frame que se añadió al parent_frame
            # widget_tuple[0] es el Entry, Checkbutton o Combobox. Su master es prop_frame.
            if widget_tuple[0] and widget_tuple[0].winfo_exists():
                widget_tuple[0].master.destroy() # Destruir el prop_frame contenedor
        self.property_widgets.clear()
        self.property_original_values.clear()

        # Limpiar el área de texto de propiedades adicionales también
        self.additional_properties_text_area.configure(state='normal')
        self.additional_properties_text_area.delete('1.0', tk.END)
        self.additional_properties_text_area.insert('1.0', "# Unparsed properties or long comments might appear here in the future.")
        self.additional_properties_text_area.configure(state='disabled')

        self.server_properties_lines = [] # Para guardar el orden y comentarios

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

        try:
            with open(self.server_properties_path, 'r') as f:
                for line in f:
                    self.server_properties_lines.append(line.rstrip('\r\n')) # Guardar la línea original sin saltos finales
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith('#'):
                        # Podríamos añadir comentarios como Labels si son cortos, o al área de adicionales.
                        # Por ahora, se reconstruirán al guardar.
                        continue
                    
                    if '=' in line_stripped:
                        key, value = line_stripped.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        widget_type = "entry"
                        options = None
                        # Usar nombre amigable o generar uno
                        label_text = friendly_names.get(key, f"{key.replace('-', ' ').title()}:")
                        description = f"Original property: {key}\\nCurrent value: {value}" 

                        if key in special_properties:
                            widget_type = special_properties[key]["type"]
                            options = special_properties[key].get("options")
                        elif value.lower() in ['true', 'false']:
                            widget_type = "switch"
                        
                        self._add_property_control(key, label_text, widget_type, 
                                                 default_value=value, options=options, description=description, 
                                                 target_frame=self.properties_scrollable_frame, 
                                                 insert_before_widget=self.additional_properties_text_area.master.master.winfo_children()[-2]) # Intentar insertar antes del label de "Adicionales"
                                                 # El ScrolledText está dentro de un frame, por eso el .master.master y el índice -2 (label + scrolledtext)
                                                 # Esto puede ser frágil. Sería mejor nombrar el frame del label de adicionales.
            
            self.log_to_console("Server properties loaded and UI dynamically generated.\n", "info")

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
            self._refresh_players_tree()
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
                    self._refresh_players_tree()
                    self.expecting_player_list_next_line = False
                else:
                    # Player names might be on the next line, or there are no players
                    count_part_text = parts[0][len(self.player_count_line_prefix):].strip() # Should be like "X of a max Y"
                    if count_part_text.startswith("0"): # "0 of a max..."
                        self.players_connected = [] # No players
                        print("DEBUG: Zero players detected from count line.") # DEBUG
                        self._refresh_players_tree()
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
        self.server_running = True
        self.log_to_console("Starting server...\n", "info")
        thread = threading.Thread(target=self.execute_server_command)
        thread.daemon = True
        thread.start()

    def execute_server_command(self):
        try:
            self.server_process = subprocess.Popen(
                self.run_bat_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=self.script_dir,
                shell=True
            )
            for line in iter(self.server_process.stdout.readline, ''):
                self.log_to_console(line)
            self.server_process.stdout.close()
            return_code = self.server_process.wait()
            self.log_to_console(f"Server process exited with code {return_code}.\n")
        except FileNotFoundError:
            self.log_to_console(f"Error: The batch file '{self.run_bat_path}' was not found.\n", "error")
        except Exception as e:
            self.log_to_console(f"An error occurred while trying to start the server: {e}\n", "error")
        finally:
            self.server_running = False
            self.server_process = None
            if self.master.winfo_exists():
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.command_entry.config(state='disabled')
                self.send_btn.config(state='disabled')

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
            messagebox.showinfo("Info", "Server is not running.")
            return
        self.log_to_console("Stopping server (sending 'stop')...\n", "info")
        self.send_command_to_server('stop')
        self.stop_button.config(state=tk.DISABLED)
        self.command_entry.config(state='disabled')
        self.send_btn.config(state='disabled')

    def _create_players_tab_widgets(self):
        card = ttk.Frame(self.players_tab, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True)
        title = ttk.Label(card, text="Connected Players", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Frame for Treeview and its scrollbar (if needed, though height is fixed here)
        tree_frame = ttk.Frame(card, style='CardInner.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Tabla de jugadores - Only Player Name column now
        columns = ("Player",)
        self.players_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', style='CardView.Treeview', height=10)
        self.players_tree.heading("Player", text="Player")
        self.players_tree.column("Player", width=300, anchor='w') # Anchor w for left alignment
        self.players_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Pack to left to allow buttons on right or bottom

        # Scrollbar for Treeview (optional, good practice)
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.players_tree.yview, style="Vertical.TScrollbar")
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.players_tree.configure(yscrollcommand=tree_scrollbar.set)

        self.players_tree.bind("<<TreeviewSelect>>", self._on_player_select)

        # Frame for action buttons (Kick, Ban, Refresh)
        actions_frame = ttk.Frame(card, style='CardInner.TFrame')
        actions_frame.pack(fill=tk.X, pady=(10,0))

        self.kick_button = ttk.Button(actions_frame, text="Kick Selected", command=self._kick_selected_player, style="Accent2.TButton", state=tk.DISABLED)
        self.kick_button.pack(side=tk.LEFT, padx=5)
        self._bind_hover(self.kick_button, TERTIARY_BG, ACCENT_COLOR)

        self.ban_button = ttk.Button(actions_frame, text="Ban Selected", command=self._ban_selected_player, style="Accent2.TButton", state=tk.DISABLED)
        self.ban_button.pack(side=tk.LEFT, padx=5)
        self._bind_hover(self.ban_button, TERTIARY_BG, ACCENT_COLOR)
        
        # Botón para refrescar manualmente - moved to the right of action buttons
        refresh_btn = ttk.Button(actions_frame, text='Refresh', command=self.update_players_list, style='Accent.TButton')
        refresh_btn.pack(side=tk.RIGHT, padx=5) # Use side=tk.RIGHT to push it to the far right
        self._bind_hover(refresh_btn, ACCENT_COLOR, ACCENT_HOVER)
        
        self.players_connected = []

    def _on_player_select(self, event=None): # event is passed by the binding
        selected_items = self.players_tree.selection()
        if selected_items: # If something is selected
            item = selected_items[0] # Get the first selected item
            player_name_tuple = self.players_tree.item(item, 'values')
            if player_name_tuple: # Ensure 'values' is not empty
                self.selected_player_name = player_name_tuple[0]
                self.kick_button.config(state=tk.NORMAL)
                self.ban_button.config(state=tk.NORMAL)
                print(f"DEBUG: Player selected: {self.selected_player_name}") # DEBUG
                return
        
        # If no selection or error in getting name, disable buttons
        self.selected_player_name = None
        self.kick_button.config(state=tk.DISABLED)
        self.ban_button.config(state=tk.DISABLED)
        print("DEBUG: Player selection cleared or invalid.") # DEBUG

    def update_players_list(self):
        # Envía el comando 'list' al servidor y espera la respuesta para actualizar la lista de jugadores
        if not self.server_running or not self.server_process:
            self.players_tree.delete(*self.players_tree.get_children())
            return
        self.send_command_to_server('list')
        # La respuesta se parsea en handle_server_output  <- This comment is key. It's parsed in log_to_console
        # self.master.after(2000, self.update_players_list) # REMOVE THIS RECURSIVE CALL

    def _refresh_players_tree(self):
        print(f"DEBUG: _refresh_players_tree called. self.players_connected = {self.players_connected}") # DEBUG
        self.players_tree.delete(*self.players_tree.get_children())
        for player in self.players_connected:
            self.players_tree.insert('', 'end', values=(player,)) # Only player name in values

    def _create_ops_tab_widgets(self):
        card = ttk.Frame(self.ops_tab, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True)
        title = ttk.Label(card, text="Operators (Ops)", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        # Tabla de ops
        columns = ("Name", "UUID", "Level", "Actions")
        self.ops_tree = ttk.Treeview(card, columns=columns, show='headings', style='CardView.Treeview', height=10)
        for col in columns:
            self.ops_tree.heading(col, text=col)
            self.ops_tree.column(col, width=120 if col!="Acciones" else 140, anchor='center')
        self.ops_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # Botón para añadir operador
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
        add_btn.pack(side=tk.RIGHT, ipadx=10, ipady=3)
        self._bind_hover(add_btn, ACCENT_COLOR, ACCENT_HOVER)
        # Cargar ops
        self.ops_list = []
        self.update_ops_list()

    def update_ops_list(self):
        ops_path = os.path.join(self.script_dir, 'ops.json')
        try:
            with open(ops_path, 'r', encoding='utf-8') as f:
                self.ops_list = json.load(f)
        except Exception:
            self.ops_list = []
        self._refresh_ops_tree()

    def _refresh_ops_tree(self):
        self.ops_tree.delete(*self.ops_tree.get_children())
        for op in self.ops_list:
            name = op.get('name', '-')
            uuid = op.get('uuid', '-')
            level = op.get('level', '-')
            self.ops_tree.insert('', 'end', values=(name, uuid, level, 'Remove'))

    def add_op(self):
        username = self.new_op_entry.get().strip()
        if not username or username == 'Username':
            messagebox.showwarning('Add OP', 'Please enter a valid username.')
            return
        # Enviar comando op al servidor
        self.send_command_to_server(f'op {username}')
        messagebox.showinfo('Add OP', f'Command sent to add {username} as an operator. If the user exists, they will appear in the list after a refresh.')
        self.new_op_entry.delete(0, tk.END)
        self.new_op_entry.insert(0, 'Username')
        self.new_op_entry.config(fg='#888888')
        self.master.after(2000, self.update_ops_list)

    def _create_worlds_tab_widgets(self):
        card = ttk.Frame(self.worlds_tab, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True)
        title = ttk.Label(card, text="🌍 Server Worlds", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        # Tabla de mundos visual con botones
        self.worlds_list_frame = ttk.Frame(card, style='CardInner.TFrame')
        self.worlds_list_frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_worlds_visual()
        # Botón para refrescar
        refresh_btn = ttk.Button(card, text='Refresh', command=self._refresh_worlds_visual, style='Accent.TButton')
        refresh_btn.pack(anchor='e', pady=(10,0))
        self._bind_hover(refresh_btn, ACCENT_COLOR, ACCENT_HOVER)

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
            ttk.Label(row, text=f'🌎 {name}', style='TLabel', width=20, anchor='center').pack(side=tk.LEFT, padx=5)
            ttk.Label(row, text=size, style='TLabel', width=15, anchor='center').pack(side=tk.LEFT, padx=5)
            backup_btn = ttk.Button(row, text='💾 Backup', command=lambda n=name: self.backup_world(n), style='Accent2.TButton')
            backup_btn.pack(side=tk.LEFT, padx=5, ipadx=8, ipady=2)
            self._bind_hover(backup_btn, ACCENT_COLOR, ACCENT_HOVER)

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

    def _create_stats_tab_widgets(self):
        card = ttk.Frame(self.stats_tab, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True)
        title = ttk.Label(card, text="📊 Player Statistics", style='Title.TLabel', font=("Segoe UI Semibold", 18))
        title.pack(anchor='w', pady=(0, 20))
        # Encabezados coloridos
        header_frame = ttk.Frame(card, style='CardInner.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header_frame, text='👤 Name', style='TLabel', width=18, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⎈ UUID', style='TLabel', width=28, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⏱️ Time Played', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='💀 Deaths', style='TLabel', width=10, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ERROR_FG_CUSTOM).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⛏️ Blocks Mined', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        # Frame para filas
        self.stats_rows_frame = ttk.Frame(card, style='CardInner.TFrame')
        self.stats_rows_frame.pack(fill=tk.BOTH, expand=True)
        # Botón para refrescar
        refresh_btn = ttk.Button(card, text='Refresh', command=self.update_stats_list, style='Accent.TButton')
        refresh_btn.pack(anchor='e', pady=(10,0))
        self._bind_hover(refresh_btn, ACCENT_COLOR, ACCENT_HOVER)
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
                stats = data.get('stats', {})
                # Tiempo jugado (en ticks, 1 tick = 1/20 seg)
                played_ticks = stats.get('minecraft:custom', {}).get('minecraft:play_time', 0)
                played_hours = played_ticks / 20 / 3600
                # Muertes
                deaths = stats.get('minecraft:custom', {}).get('minecraft:deaths', 0)
                # Bloques minados (suma de todos los bloques)
                blocks = stats.get('minecraft:mined', {})
                blocks_mined = sum(blocks.values())
                stats_data.append((name, uuid, f"{played_hours:.1f} h", deaths, blocks_mined))
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
            name, uuid, played, deaths, mined = row
            # Determinar el color de fondo para la fila basado en el tema actual
            # Esto es un poco más complejo, necesitaríamos saber si el tema es claro u oscuro.
            # Por ahora, mantenemos la alternancia simple, pero el PRIMARY_BG y SECONDARY_BG deben estar bien definidos.
            bg_color = SECONDARY_BG if i % 2 == 0 else PRIMARY_BG 
            fila = tk.Frame(self.stats_rows_frame, bg=bg_color) # Aplicar color de fondo directamente
            # Avatar/emoji
            avatar = name[0].upper() if name and name != uuid else '👤'
            tk.Label(fila, text=avatar, font=("Segoe UI Emoji", 16), bg=bg_color, fg=ACCENT_COLOR, width=2).pack(side=tk.LEFT, padx=(5,0))
            # Nombre con tooltip UUID
            name_lbl = tk.Label(fila, text=name, font=("Segoe UI", 12, "bold"), bg=bg_color, fg=ACCENT_COLOR, width=15, anchor='w', cursor='hand2')
            name_lbl.pack(side=tk.LEFT, padx=5)
            self._add_tooltip(name_lbl, uuid)
            # UUID
            tk.Label(fila, text=uuid, font=("Consolas", 10), bg=bg_color, fg=ACCENT_COLOR, width=28, anchor='center').pack(side=tk.LEFT, padx=5)
            # Tiempo jugado
            tk.Label(fila, text=played, font=("Segoe UI", 12), bg=bg_color, fg=ACCENT_COLOR, width=12, anchor='center').pack(side=tk.LEFT, padx=5)
            # Muertes
            tk.Label(fila, text=f'💀 {deaths}', font=("Segoe UI", 12), bg=bg_color, fg=ERROR_FG_CUSTOM, width=10, anchor='center').pack(side=tk.LEFT, padx=5)
            # Minados
            tk.Label(fila, text=f'⛏️ {mined}', font=("Segoe UI", 12), bg=bg_color, fg=ACCENT_COLOR, width=12, anchor='center').pack(side=tk.LEFT, padx=5)
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
    def _kick_selected_player(self):
        if self.selected_player_name:
            command = f"kick {self.selected_player_name}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            # Optionally, deselect or refresh list after action
            self.players_tree.selection_remove(self.players_tree.selection()) # Deselect
            self.update_players_list() # Refresh list
        else:
            self.log_to_console("No player selected to kick.\n", "warning")

    def _ban_selected_player(self):
        if self.selected_player_name:
            command = f"ban {self.selected_player_name}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            # Optionally, deselect or refresh list after action
            self.players_tree.selection_remove(self.players_tree.selection()) # Deselect
            self.update_players_list() # Refresh list
        else:
            self.log_to_console("No player selected to ban.\n", "warning")

    # --- BAN MANAGEMENT --- 
    def _create_bans_tab_widgets(self):
        main_card = ttk.Frame(self.bans_tab, style='Card.TFrame', padding=15)
        main_card.pack(fill=tk.BOTH, expand=True)

        # Refresh button at the top
        refresh_bans_button = ttk.Button(main_card, text="Refresh Bans", command=self._load_bans, style="Accent.TButton")
        refresh_bans_button.pack(anchor='ne', pady=(0,10), padx=5)
        self._bind_hover(refresh_bans_button, ACCENT_COLOR, ACCENT_HOVER)

        # --- Banned IPs Section ---
        ips_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        ips_card.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        ttk.Label(ips_card, text="Banned IPs", style='Title.TLabel', font=FONT_UI_BOLD).pack(anchor='w', pady=(0,10))

        ip_tree_frame = ttk.Frame(ips_card, style='CardInner.TFrame')
        ip_tree_frame.pack(fill=tk.BOTH, expand=True)
        ip_columns = ("IP Address", "Created", "Source", "Expires", "Reason")
        self.banned_ips_tree = ttk.Treeview(ip_tree_frame, columns=ip_columns, show='headings', style='CardView.Treeview', height=6)
        for col in ip_columns:
            self.banned_ips_tree.heading(col, text=col)
            self.banned_ips_tree.column(col, width=120, anchor='w')
        self.banned_ips_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ip_scrollbar = ttk.Scrollbar(ip_tree_frame, orient="vertical", command=self.banned_ips_tree.yview, style="Vertical.TScrollbar")
        ip_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.banned_ips_tree.configure(yscrollcommand=ip_scrollbar.set)
        self.banned_ips_tree.bind("<<TreeviewSelect>>", self._on_banned_ip_select)

        self.unban_ip_button = ttk.Button(ips_card, text="Pardon Selected IP", command=self._unban_selected_ip, style="Accent2.TButton", state=tk.DISABLED)
        self.unban_ip_button.pack(pady=(10,0), anchor='w')
        self._bind_hover(self.unban_ip_button, TERTIARY_BG, ACCENT_COLOR)

        # --- Banned Players Section ---
        players_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        players_card.pack(fill=tk.BOTH, expand=True, pady=(10,0))
        ttk.Label(players_card, text="Banned Players", style='Title.TLabel', font=FONT_UI_BOLD).pack(anchor='w', pady=(0,10))

        player_tree_frame = ttk.Frame(players_card, style='CardInner.TFrame')
        player_tree_frame.pack(fill=tk.BOTH, expand=True)
        player_columns = ("Username", "UUID", "Created", "Source", "Expires", "Reason")
        self.banned_players_tree = ttk.Treeview(player_tree_frame, columns=player_columns, show='headings', style='CardView.Treeview', height=6)
        for col in player_columns:
            self.banned_players_tree.heading(col, text=col)
            self.banned_players_tree.column(col, width=100, anchor='w')
        self.banned_players_tree.column("UUID", width=180)
        self.banned_players_tree.column("Reason", width=150)
        self.banned_players_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        player_scrollbar = ttk.Scrollbar(player_tree_frame, orient="vertical", command=self.banned_players_tree.yview, style="Vertical.TScrollbar")
        player_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.banned_players_tree.configure(yscrollcommand=player_scrollbar.set)
        self.banned_players_tree.bind("<<TreeviewSelect>>", self._on_banned_player_select)

        self.unban_player_button = ttk.Button(players_card, text="Pardon Selected Player", command=self._unban_selected_player, style="Accent2.TButton", state=tk.DISABLED)
        self.unban_player_button.pack(pady=(10,0), anchor='w')
        self._bind_hover(self.unban_player_button, TERTIARY_BG, ACCENT_COLOR)
        
        self.selected_banned_ip = None
        self.selected_banned_player_name = None # Store name for pardon command

        self._load_bans() # Initial load

    def _on_banned_ip_select(self, event=None):
        selected_items = self.banned_ips_tree.selection()
        if selected_items:
            item_values = self.banned_ips_tree.item(selected_items[0], 'values')
            if item_values:
                self.selected_banned_ip = item_values[0] # IP is the first column
                self.unban_ip_button.config(state=tk.NORMAL)
                print(f"DEBUG: Banned IP selected: {self.selected_banned_ip}")
                return
        self.selected_banned_ip = None
        self.unban_ip_button.config(state=tk.DISABLED)

    def _on_banned_player_select(self, event=None):
        selected_items = self.banned_players_tree.selection()
        if selected_items:
            item_values = self.banned_players_tree.item(selected_items[0], 'values')
            if item_values:
                self.selected_banned_player_name = item_values[0] # Username is the first column
                self.unban_player_button.config(state=tk.NORMAL)
                print(f"DEBUG: Banned Player selected: {self.selected_banned_player_name}")
                return
        self.selected_banned_player_name = None
        self.unban_player_button.config(state=tk.DISABLED)

    def _load_bans(self):
        self._load_banned_ips()
        self._load_banned_players()

    def _load_banned_ips(self):
        self.banned_ips_tree.delete(*self.banned_ips_tree.get_children())
        try:
            if os.path.exists(self.banned_ips_path):
                with open(self.banned_ips_path, 'r', encoding='utf-8') as f:
                    banned_ips_data = json.load(f)
                for ban_entry in banned_ips_data:
                    self.banned_ips_tree.insert('', 'end', values=(
                        ban_entry.get('ip', 'N/A'),
                        ban_entry.get('created', 'N/A'),
                        ban_entry.get('source', 'N/A'),
                        ban_entry.get('expires', 'N/A'),
                        ban_entry.get('reason', 'N/A')
                    ))
            else:
                self.log_to_console(f"Ban file not found: {self.banned_ips_path}\n", "warning")
        except Exception as e:
            self.log_to_console(f"Error loading banned IPs: {e}\n", "error")
            messagebox.showerror("Error Loading Bans", f"Failed to load {self.banned_ips_path}:\n{e}")

    def _load_banned_players(self):
        self.banned_players_tree.delete(*self.banned_players_tree.get_children())
        try:
            if os.path.exists(self.banned_players_path):
                with open(self.banned_players_path, 'r', encoding='utf-8') as f:
                    banned_players_data = json.load(f)
                for ban_entry in banned_players_data:
                    self.banned_players_tree.insert('', 'end', values=(
                        ban_entry.get('name', 'N/A'),
                        ban_entry.get('uuid', 'N/A'),
                        ban_entry.get('created', 'N/A'),
                        ban_entry.get('source', 'N/A'),
                        ban_entry.get('expires', 'N/A'),
                        ban_entry.get('reason', 'N/A')
                    ))
            else:
                self.log_to_console(f"Ban file not found: {self.banned_players_path}\n", "warning")
        except Exception as e:
            self.log_to_console(f"Error loading banned players: {e}\n", "error")
            messagebox.showerror("Error Loading Bans", f"Failed to load {self.banned_players_path}:\n{e}")

    def _unban_selected_ip(self):
        if self.selected_banned_ip:
            command = f"pardon-ip {self.selected_banned_ip}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            self.selected_banned_ip = None # Deselect
            self.unban_ip_button.config(state=tk.DISABLED)
            self._load_bans() # Refresh lists
        else:
            self.log_to_console("No IP selected to pardon.\n", "warning")

    def _unban_selected_player(self):
        if self.selected_banned_player_name:
            command = f"pardon {self.selected_banned_player_name}"
            self.send_command_to_server(command)
            self.log_to_console(f"Sent command: {command}\n", "info")
            self.selected_banned_player_name = None # Deselect
            self.unban_player_button.config(state=tk.DISABLED)
            self._load_bans() # Refresh lists
        else:
            self.log_to_console("No player selected to pardon.\n", "warning")

    # --- MOD MANAGEMENT ---   
    def _create_mods_tab_widgets(self):
        main_card = ttk.Frame(self.mods_tab, style='Card.TFrame', padding=15)
        main_card.pack(fill=tk.BOTH, expand=True)

        # Top action buttons frame
        top_actions_frame = ttk.Frame(main_card, style='CardInner.TFrame')
        top_actions_frame.pack(fill=tk.X, pady=(0,10))

        open_mods_folder_btn = ttk.Button(top_actions_frame, text="Open Mods Folder", command=self._open_mods_folder, style="Accent2.TButton")
        open_mods_folder_btn.pack(side=tk.LEFT, padx=5)
        self._bind_hover(open_mods_folder_btn, TERTIARY_BG, ACCENT_COLOR)

        open_config_folder_btn = ttk.Button(top_actions_frame, text="Open Config Folder", command=self._open_config_folder, style="Accent2.TButton")
        open_config_folder_btn.pack(side=tk.LEFT, padx=5)
        self._bind_hover(open_config_folder_btn, TERTIARY_BG, ACCENT_COLOR)

        refresh_mods_btn = ttk.Button(top_actions_frame, text="Refresh Mod List", command=self._load_mods_list, style="Accent.TButton")
        refresh_mods_btn.pack(side=tk.RIGHT, padx=5) # Refresh on the right
        self._bind_hover(refresh_mods_btn, ACCENT_COLOR, ACCENT_HOVER)
        
        # PanedWindow for resizable sections: Mod List | Config Editor
        paned_window = ttk.PanedWindow(main_card, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=10)

        # Left Pane: Mod List
        mod_list_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=(10,5))
        paned_window.add(mod_list_frame, weight=1) # Add with weight for resizing

        ttk.Label(mod_list_frame, text="Installed Mods (.jar files)", style='Header.TLabel').pack(anchor='w', pady=(0,5))
        mod_tree_frame = ttk.Frame(mod_list_frame, style='CardInner.TFrame')
        mod_tree_frame.pack(fill=tk.BOTH, expand=True)
        mod_columns = ("Mod File", "Detected Config")
        self.mods_tree = ttk.Treeview(mod_tree_frame, columns=mod_columns, show='headings', style='CardView.Treeview', height=15)
        self.mods_tree.heading("Mod File", text="Mod File")
        self.mods_tree.heading("Detected Config", text="Detected Config File")
        self.mods_tree.column("Mod File", width=200, anchor='w')
        self.mods_tree.column("Detected Config", width=200, anchor='w')
        self.mods_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mod_scrollbar = ttk.Scrollbar(mod_tree_frame, orient="vertical", command=self.mods_tree.yview, style="Vertical.TScrollbar")
        mod_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.mods_tree.configure(yscrollcommand=mod_scrollbar.set)
        self.mods_tree.bind("<<TreeviewSelect>>", self._on_mod_select)

        # Delete Mod Button - below the mod list tree
        self.delete_mod_button = ttk.Button(mod_list_frame, text="Delete Selected Mod", command=self._delete_selected_mod, style="Accent2.TButton", state=tk.DISABLED)
        self.delete_mod_button.pack(pady=(10,0), anchor='sw') # Anchor to south-west
        self._bind_hover(self.delete_mod_button, TERTIARY_BG, ACCENT_COLOR)

        # Right Pane: Config Editor
        config_editor_frame = ttk.Frame(paned_window, style='CardInner.TFrame', padding=(10,5))
        paned_window.add(config_editor_frame, weight=2) # Give more weight to editor

        ttk.Label(config_editor_frame, text="Configuration File Editor", style='Header.TLabel').pack(anchor='w', pady=(0,5))
        self.mod_config_text_area = scrolledtext.ScrolledText(config_editor_frame, wrap=tk.WORD, height=15, 
                                                            bg=PRIMARY_BG, fg=TEXT_PRIMARY, 
                                                            insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM, 
                                                            relief='solid', borderwidth=1, highlightthickness=0, bd=0, padx=5, pady=5)
        self.mod_config_text_area.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        self.mod_config_text_area.configure(state='disabled') # Disabled initially

        self.save_mod_config_button = ttk.Button(config_editor_frame, text="Save Config Changes", command=self._save_mod_config, style="Accent.TButton", state=tk.DISABLED)
        self.save_mod_config_button.pack(anchor='se')
        self._bind_hover(self.save_mod_config_button, ACCENT_COLOR, ACCENT_HOVER)

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
            # Mod specific subfolders
            os.path.join(mod_id, f"{mod_id}.cfg"), os.path.join(mod_id, f"{mod_id}.toml"),
            os.path.join(mod_id, "main.cfg"), os.path.join(mod_id, "config.cfg"),
        ]
        # Some mods use mixed case or exact jar name for config
        config_patterns.extend([f"{mod_id}.CFG", f"{mod_id}.PROPERTIES"]) 

        for pattern in config_patterns:
            potential_path = os.path.join(self.config_dir_path, pattern)
            if os.path.isfile(potential_path):
                return potential_path
        
        # Check for a folder named after the mod_id itself (e.g., /config/jei/ for JEI settings)
        # If such a folder exists, we might not pick a single file, but indicate the folder exists.
        # For simplicity, let's return the folder path if it exists and no specific file was found yet.
        # Or, we can just not return anything if a single file isn't obvious.
        # For now, let's keep it simple: only return if a specific file is found.
        return None

    def _load_mods_list(self):
        self.mods_tree.delete(*self.mods_tree.get_children())
        self.mod_data.clear()
        self.mod_config_text_area.configure(state='disabled')
        self.save_mod_config_button.config(state=tk.DISABLED)
        self.current_mod_config_path = None
        self.delete_mod_button.config(state=tk.DISABLED) # Disable delete button too
        self.current_selected_mod_info = None # Clear selected mod info
        self.mod_config_text_area.delete('1.0', tk.END)

        if not os.path.isdir(self.mods_dir_path):
            self.log_to_console(f"Mods directory not found: {self.mods_dir_path}\n", "warning")
            # Display a message in the Treeview area if possible or a label
            # For now, just log and leave the tree empty.
            ttk.Label(self.mods_tree, text=f"Mods folder not found: {self.mods_dir_path}").pack(pady=20)
            return

        try:
            jar_files = [f for f in os.listdir(self.mods_dir_path) if f.lower().endswith('.jar')]
            if not jar_files:
                 ttk.Label(self.mods_tree, text="No .jar files found in the mods folder.").pack(pady=20)

            for jar_file in sorted(jar_files, key=str.lower):
                mod_id = self._extract_mod_id(jar_file)
                config_file_path = self._find_mod_config_file(mod_id)
                config_display_name = os.path.basename(config_file_path) if config_file_path else "N/A"
                
                self.mods_tree.insert('', 'end', values=(jar_file, config_display_name))
                self.mod_data.append({'jar': jar_file, 'id': mod_id, 'config_path': config_file_path})
            
        except Exception as e:
            self.log_to_console(f"Error loading mods list: {e}\n", "error")
            messagebox.showerror("Error Loading Mods", f"Failed to list mods: {e}")

    def _on_mod_select(self, event=None):
        selected_items = self.mods_tree.selection()
        self.mod_config_text_area.configure(state='disabled')
        self.save_mod_config_button.config(state=tk.DISABLED)
        self.delete_mod_button.config(state=tk.DISABLED) # Disable delete button too
        self.current_mod_config_path = None
        self.current_selected_mod_info = None # Clear selected mod info
        self.mod_config_text_area.delete('1.0', tk.END)

        if not selected_items:
            return
        
        selected_tree_item = selected_items[0]
        # Find the corresponding mod_data entry based on the selected Treeview item
        # This assumes the Treeview is populated in the same order as mod_data, 
        # or we need a more robust way to link Treeview items to mod_data indices.
        # For simplicity, let's iterate: (Can be optimized if many mods)
        selected_jar_name = self.mods_tree.item(selected_tree_item, 'values')[0]
        
        selected_mod_info = None
        for mod_info_iter in self.mod_data:
            if mod_info_iter['jar'] == selected_jar_name:
                selected_mod_info = mod_info_iter
                break
        
        self.current_selected_mod_info = selected_mod_info # Store for potential deletion

        if selected_mod_info and selected_mod_info['config_path']:
            self.current_mod_config_path = selected_mod_info['config_path']
            try:
                with open(self.current_mod_config_path, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                self.mod_config_text_area.configure(state='normal')
                self.mod_config_text_area.insert('1.0', config_content)
                self.save_mod_config_button.config(state=tk.NORMAL)
                self.delete_mod_button.config(state=tk.NORMAL) # Enable delete button
                self.log_to_console(f"Loaded config for {selected_jar_name}: {os.path.basename(self.current_mod_config_path)}\n", "info")
            except Exception as e:
                self.log_to_console(f"Error loading mod config {self.current_mod_config_path}: {e}\n", "error")
                messagebox.showerror("Error Loading Config", f"Could not read {os.path.basename(self.current_mod_config_path)}:\n{e}")
                self.mod_config_text_area.insert('1.0', f"# Could not load: {os.path.basename(self.current_mod_config_path)}\n# Error: {e}")
        elif selected_mod_info: # Mod selected, but no config file found/loaded
            self.delete_mod_button.config(state=tk.NORMAL) # Still allow deleting the JAR
            self.log_to_console(f"No associated config file found or loaded for {selected_jar_name}.\n", "info")
            self.mod_config_text_area.insert('1.0', f"# No configuration file automatically detected for {selected_jar_name}.")
        else:
             self.log_to_console(f"Could not find mod data for selected item: {selected_jar_name}.\n", "warning") # Should not happen

    def _save_mod_config(self):
        if not self.current_mod_config_path:
            messagebox.showwarning("Save Error", "No configuration file is currently loaded.")
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

    def _delete_selected_mod(self):
        if not self.current_selected_mod_info or not self.current_selected_mod_info.get('jar'):
            messagebox.showwarning("Delete Error", "No mod selected or mod information is incomplete.")
            return

        mod_jar_name = self.current_selected_mod_info['jar']
        mod_jar_path = os.path.join(self.mods_dir_path, mod_jar_name)
        
        config_path_to_delete = self.current_selected_mod_info.get('config_path')
        config_name_display = os.path.basename(config_path_to_delete) if config_path_to_delete else "no associated config file"

        confirm_message = f"Are you sure you want to delete the mod '{mod_jar_name}' and {config_name_display}?This action cannot be undone."
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
            # Clear selection states as the item is gone
            self.current_selected_mod_info = None
            self.current_mod_config_path = None
            self.mod_config_text_area.configure(state='disabled')
            self.mod_config_text_area.delete('1.0', tk.END)
            self.save_mod_config_button.config(state=tk.DISABLED)
            self.delete_mod_button.config(state=tk.DISABLED)

    # --- APP SETTINGS & CHANGELOG ---
    def _create_app_settings_tab_widgets(self):
        main_card = ttk.Frame(self.app_settings_tab, style='Card.TFrame', padding=15)
        main_card.pack(fill=tk.BOTH, expand=True)

        # --- Application Information Section ---
        info_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        info_card.pack(fill=tk.X, pady=(0,10)) # Fill X, place at top
        ttk.Label(info_card, text="Application Information", style='Title.TLabel', font=FONT_UI_BOLD).pack(anchor='w', pady=(0,10))
        
        app_name_text = "Minecraft Server Control GUI"
        app_version_text = "1.2.1" # Example version, update as needed
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
        ttk.Label(changelog_card, text="Application Changelog", style='Title.TLabel', font=FONT_UI_BOLD).pack(anchor='w', pady=(0,10))

        self.changelog_text_area = scrolledtext.ScrolledText(changelog_card, wrap=tk.WORD, height=10,
                                                             bg=PRIMARY_BG, fg=TEXT_SECONDARY, # Adjusted fg for read-only text
                                                             insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM,
                                                             relief='solid', borderwidth=1, highlightthickness=0, bd=0, padx=5, pady=5)
        self.changelog_text_area.pack(fill=tk.BOTH, expand=True, pady=(0,0))
        # No Save Changelog button - it's read-only now

        # --- Placeholder for App Configuration Section ---
        app_config_card = ttk.Frame(main_card, style='CardInner.TFrame', padding=15)
        app_config_card.pack(fill=tk.X, pady=(10,0))
        ttk.Label(app_config_card, text="Other Application Settings", style='Title.TLabel', font=FONT_UI_BOLD).pack(anchor='w', pady=(0,5))
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

    # Removed _save_changelog method as it's no longer needed

    def _delete_selected_mod(self):
        if not self.current_selected_mod_info or not self.current_selected_mod_info.get('jar'):
            messagebox.showwarning("Delete Error", "No mod selected or mod information is incomplete.")
            return

        mod_jar_name = self.current_selected_mod_info['jar']
        mod_jar_path = os.path.join(self.mods_dir_path, mod_jar_name)
        
        config_path_to_delete = self.current_selected_mod_info.get('config_path')
        config_name_display = os.path.basename(config_path_to_delete) if config_path_to_delete else "no associated config file"

        confirm_message = f"Are you sure you want to delete the mod '{mod_jar_name}' and {config_name_display}?This action cannot be undone."
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
            # Clear selection states as the item is gone
            self.current_selected_mod_info = None
            self.current_mod_config_path = None
            self.mod_config_text_area.configure(state='disabled')
            self.mod_config_text_area.delete('1.0', tk.END)
            self.save_mod_config_button.config(state=tk.DISABLED)
            self.delete_mod_button.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk() # Ya no es ThemedTk
    # Los estilos globales se definen dentro de ServerControlGUI
    gui = ServerControlGUI(root)
    root.mainloop() 

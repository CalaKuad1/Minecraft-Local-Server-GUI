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
        self.master = master
        master.title("Minecraft Server Control")
        master.geometry("950x720")
        master.configure(bg=PRIMARY_BG)

        # Inicializar atributos de estado del servidor ANTES de crear widgets que puedan usarlos
        self.server_process = None
        self.server_running = False

        self.style = ttk.Style()
        self.style.theme_use('default') # Empezar con un tema base simple de Tk

        # --- Definición de Estilos Personalizados --- 
        self.style.configure('.', background=PRIMARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL, borderwidth=0, focusthickness=0, highlightthickness=0)
        self.style.configure('TFrame', background=PRIMARY_BG)
        self.style.configure('Card.TFrame', background=SECONDARY_BG, relief='flat') # Para tarjetas
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
        
        # Scrollbars (requiere más trabajo para un look 100% custom)
        self.style.configure("Vertical.TScrollbar", background=TERTIARY_BG, troughcolor=SECONDARY_BG, bordercolor=TERTIARY_BG, arrowcolor=TEXT_PRIMARY, gripcount=0)
        self.style.map("Vertical.TScrollbar", background=[('active', ACCENT_COLOR)])

        # Estilo para Checkbutton (usado como Switch)
        self.style.configure('Switch.TCheckbutton', font=FONT_UI_NORMAL, padding=5)
        self.style.map('Switch.TCheckbutton',
                       indicatorcolor=[('selected', ACCENT_COLOR), ('!selected', TERTIARY_BG)],
                       background=[('active', SECONDARY_BG)], foreground=[('', TEXT_PRIMARY)]) # Fondo del texto

        # Eliminar selector de tema (ya no se usa ttkthemes)
        # --- Fin de Estilos --- 

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
        self.notebook.add(self.resources_tab, text='📈 Recursos')
        self._create_resources_tab_widgets()
        self.players_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.players_tab, text='👥 Jugadores')
        self._create_players_tab_widgets()
        self.ops_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.ops_tab, text='⭐ Ops')
        self._create_ops_tab_widgets()
        self.worlds_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.worlds_tab, text='🌍 Mundos')
        self._create_worlds_tab_widgets()
        self.stats_tab = ttk.Frame(self.notebook, style='TFrame', padding=10)
        self.notebook.add(self.stats_tab, text='📊 Estadísticas')
        self._create_stats_tab_widgets()

        self.load_server_properties()

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

        controls_frame = ttk.Frame(card, style='Card.TFrame') # Fondo de tarjeta
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

        entry_frame = ttk.Frame(console_card, style='Card.TFrame')
        entry_frame.pack(fill=tk.X, pady=(15, 0))
        self.command_entry = tk.Entry(entry_frame, font=FONT_CONSOLE_CUSTOM, 
                                      bg=PRIMARY_BG, fg=TEXT_PRIMARY, insertbackground=ACCENT_COLOR, 
                                      relief='flat', borderwidth=0, highlightthickness=0, bd=0)
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=10, ipadx=10)
        self.command_entry.bind('<Return>', self.send_command_from_entry)
        self.command_entry.config(state='disabled')
        # Placeholder
        self.command_entry.insert(0, 'Escribe un comando aquí...')
        self.command_entry.config(fg='#888888')
        def on_focus_in(event):
            if self.command_entry.get() == 'Escribe un comando aquí...':
                self.command_entry.delete(0, tk.END)
                self.command_entry.config(fg=ACCENT_COLOR)
        def on_focus_out(event):
            if not self.command_entry.get():
                self.command_entry.insert(0, 'Escribe un comando aquí...')
                self.command_entry.config(fg='#888888')
        self.command_entry.bind('<FocusIn>', on_focus_in)
        self.command_entry.bind('<FocusOut>', on_focus_out)
        # Botón Send grande y alineado a la derecha
        send_btn = ttk.Button(entry_frame, text='Enviar', command=self.send_command_from_button, style='Accent.TButton')
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
        self.properties_scrollable_frame = ttk.Frame(canvas, style='Card.TFrame') # Frame que contendrá los widgets

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
        properties_controls_frame = ttk.Frame(self.properties_scrollable_frame, style='Card.TFrame')
        properties_controls_frame.pack(fill=tk.X, pady=(5,15), padx=10)
        
        self.load_props_button = ttk.Button(properties_controls_frame, text="Recargar Propiedades", command=self.load_server_properties, style="Accent.TButton")
        self.load_props_button.pack(side=tk.LEFT, padx=(0,10))
        
        self.save_props_button = ttk.Button(properties_controls_frame, text="Guardar Propiedades", command=self.save_server_properties, style="Accent2.TButton")
        self.save_props_button.pack(side=tk.LEFT)

        # Diccionario para almacenar los widgets de propiedades y sus valores originales
        self.property_widgets = {}
        self.property_original_values = {}

        # Área para propiedades no manejadas explícitamente (opcional, o para más tarde)
        ttk.Label(self.properties_scrollable_frame, text="Propiedades Adicionales (avanzado):", style='Header.TLabel').pack(anchor='w', pady=(20,5), padx=10)
        self.additional_properties_text_area = scrolledtext.ScrolledText(self.properties_scrollable_frame, wrap=tk.WORD, height=10, width=70, 
                                                              bg=PRIMARY_BG, fg=TEXT_PRIMARY, 
                                                              insertbackground=ACCENT_COLOR, font=FONT_CONSOLE_CUSTOM, 
                                                              relief='flat', borderwidth=0, highlightthickness=0, bd=0, padx=5, pady=5)
        self.additional_properties_text_area.pack(fill=tk.X, expand=True, padx=10, pady=(0,10))

    def _add_property_control(self, key_name, label_text, widget_type, default_value="", options=None, description="", target_frame=None, insert_before_widget=None):
        # Usar target_frame si se especifica, sino el por defecto.
        parent_frame = target_frame if target_frame else self.properties_scrollable_frame

        prop_frame = ttk.Frame(parent_frame, style='Card.TFrame')
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
        title = ttk.Label(card, text="Uso de Recursos del Servidor", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Info de depuración
        self.debug_label = ttk.Label(card, text="", style='TLabel', font=("Consolas", 9))
        self.debug_label.pack(anchor='w', pady=(0, 10))

        # CPU
        cpu_frame = ttk.Frame(card, style='Card.TFrame')
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
        ram_frame = ttk.Frame(card, style='Card.TFrame')
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
                    self.cpu_percent_label.config(text=f"{cpu_per_core:.1f}% por núcleo ({num_cores} núcleos)")
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
        self.additional_properties_text_area.insert('1.0', "# Las propiedades no parseadas o comentarios largos podrían aparecer aquí en el futuro.")
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
            "max-players": "Max. Jugadores:",
            "server-port": "Puerto del Servidor:",
            "level-name": "Nombre del Mundo:",
            "online-mode": "Modo Online:",
            "pvp": "Permitir PvP:",
            "spawn-animals": "Generar Animales:",
            "spawn-monsters": "Generar Monstruos:",
            "spawn-npcs": "Generar NPCs:",
            "allow-flight": "Permitir Volar:",
            "enable-command-block": "Habilitar Bloque de Comandos:",
            "motd": "Mensaje del Día (MOTD):"
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
                        description = f"Propiedad original: {key}\nValor actual: {value}" 

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
            self.log_to_console(f"Error: {self.server_properties_path} not found.\n", "error")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load server.properties: {e}")
            self.log_to_console(f"Failed to load server.properties: {e}\n", "error")

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
            
            messagebox.showinfo("Success", "server.properties guardado exitosamente!")
            self.log_to_console("server.properties guardado exitosamente.\n", "info")
            
            # Opcional: Recargar las propiedades para reflejar cualquier normalización (ej. true/false)
            # y actualizar los original_values si es necesario, o simplemente asumir que la UI ya está al día.
            self.load_server_properties() # Recargar para que la UI y los datos internos estén sincronizados

        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar server.properties: {e}")
            self.log_to_console(f"Error al guardar server.properties: {e}\n", "error")

    def log_to_console(self, message, level="normal", animate=False):
        self.console_output_area.configure(state='normal')
        tag = level if level in ("error", "info", "warning", "usercmd") else "normal"
        if animate:
            for char in message:
                self.console_output_area.insert(tk.END, char, tag)
                self.console_output_area.see(tk.END)
                self.console_output_area.update_idletasks()
                self.master.after(1)
        else:
            self.console_output_area.insert(tk.END, message, tag)
            self.console_output_area.see(tk.END)
        self.console_output_area.configure(state='disabled')
        # Parseo de jugadores conectados
        if message.startswith('There are') and 'players online:' in message:
            try:
                # Ejemplo: 'There are 2 of a max of 20 players online: Steve, Alex'
                parts = message.split(':', 1)
                if len(parts) == 2:
                    players = [p.strip() for p in parts[1].split(',') if p.strip()]
                    self.players_connected = players
                    self._refresh_players_tree()
            except Exception:
                pass

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
                creationflags=subprocess.CREATE_NEW_CONSOLE,
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
        if cmd and cmd != 'Escribe un comando aquí...':
            self.send_command_to_server(cmd)
            self.command_entry.delete(0, tk.END)
            self.command_entry.insert(0, 'Escribe un comando aquí...')
            self.command_entry.config(fg='#888888')

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
        title = ttk.Label(card, text="Jugadores conectados", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        # Tabla de jugadores
        columns = ("Jugador", "Acciones")
        self.players_tree = ttk.Treeview(card, columns=columns, show='headings', style='Card.TFrame', height=10)
        self.players_tree.heading("Jugador", text="Jugador")
        self.players_tree.heading("Acciones", text="Acciones")
        self.players_tree.column("Jugador", width=200, anchor='center')
        self.players_tree.column("Acciones", width=200, anchor='center')
        self.players_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # Botón para refrescar manualmente
        refresh_btn = ttk.Button(card, text='Refrescar', command=self.update_players_list, style='Accent.TButton')
        refresh_btn.pack(anchor='e', pady=(10,0))
        self._bind_hover(refresh_btn, ACCENT_COLOR, ACCENT_HOVER)
        # Actualización periódica
        self.players_connected = []
        self.update_players_list()

    def update_players_list(self):
        # Envía el comando 'list' al servidor y espera la respuesta para actualizar la lista de jugadores
        if not self.server_running or not self.server_process:
            self.players_tree.delete(*self.players_tree.get_children())
            return
        self.send_command_to_server('list')
        # La respuesta se parsea en handle_server_output
        self.master.after(2000, self.update_players_list)

    def _refresh_players_tree(self):
        self.players_tree.delete(*self.players_tree.get_children())
        for player in self.players_connected:
            self.players_tree.insert('', 'end', values=(player, 'Expulsar | Banear'))

    def _create_ops_tab_widgets(self):
        card = ttk.Frame(self.ops_tab, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True)
        title = ttk.Label(card, text="Operadores (Ops)", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        # Tabla de ops
        columns = ("Nombre", "UUID", "Nivel", "Acciones")
        self.ops_tree = ttk.Treeview(card, columns=columns, show='headings', style='Card.TFrame', height=10)
        for col in columns:
            self.ops_tree.heading(col, text=col)
            self.ops_tree.column(col, width=120 if col!="Acciones" else 140, anchor='center')
        self.ops_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # Botón para añadir operador
        add_frame = ttk.Frame(card, style='Card.TFrame')
        add_frame.pack(fill=tk.X, pady=(10,0))
        self.new_op_entry = tk.Entry(add_frame, font=FONT_CONSOLE_CUSTOM, bg=PRIMARY_BG, fg=TEXT_PRIMARY, insertbackground=ACCENT_COLOR, relief='flat', borderwidth=2, highlightthickness=1, highlightbackground=ACCENT_COLOR, highlightcolor=ACCENT_COLOR)
        self.new_op_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=6)
        self.new_op_entry.insert(0, 'Nombre de usuario')
        self.new_op_entry.config(fg='#888888')
        def on_focus_in(event):
            if self.new_op_entry.get() == 'Nombre de usuario':
                self.new_op_entry.delete(0, tk.END)
                self.new_op_entry.config(fg=TEXT_PRIMARY)
        def on_focus_out(event):
            if not self.new_op_entry.get():
                self.new_op_entry.insert(0, 'Nombre de usuario')
                self.new_op_entry.config(fg='#888888')
        self.new_op_entry.bind('<FocusIn>', on_focus_in)
        self.new_op_entry.bind('<FocusOut>', on_focus_out)
        add_btn = ttk.Button(add_frame, text='Añadir OP', command=self.add_op, style='Accent.TButton')
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
            self.ops_tree.insert('', 'end', values=(name, uuid, level, 'Quitar'))

    def add_op(self):
        username = self.new_op_entry.get().strip()
        if not username or username == 'Nombre de usuario':
            messagebox.showwarning('Añadir OP', 'Introduce un nombre de usuario válido.')
            return
        # Enviar comando op al servidor
        self.send_command_to_server(f'op {username}')
        messagebox.showinfo('Añadir OP', f'Se ha enviado el comando para añadir a {username} como operador. Si el usuario existe, aparecerá en la lista tras refrescar.')
        self.new_op_entry.delete(0, tk.END)
        self.new_op_entry.insert(0, 'Nombre de usuario')
        self.new_op_entry.config(fg='#888888')
        self.master.after(2000, self.update_ops_list)

    def _create_worlds_tab_widgets(self):
        card = ttk.Frame(self.worlds_tab, style='Card.TFrame', padding=30)
        card.pack(fill=tk.BOTH, expand=True)
        title = ttk.Label(card, text="🌍 Mundos del Servidor", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        # Tabla de mundos visual con botones
        self.worlds_list_frame = ttk.Frame(card, style='Card.TFrame')
        self.worlds_list_frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_worlds_visual()
        # Botón para refrescar
        refresh_btn = ttk.Button(card, text='Refrescar', command=self._refresh_worlds_visual, style='Accent.TButton')
        refresh_btn.pack(anchor='e', pady=(10,0))
        self._bind_hover(refresh_btn, ACCENT_COLOR, ACCENT_HOVER)

    def _refresh_worlds_visual(self):
        for widget in self.worlds_list_frame.winfo_children():
            widget.destroy()
        # Header
        header = ttk.Frame(self.worlds_list_frame, style='Card.TFrame')
        header.pack(fill=tk.X, pady=(0,5))
        ttk.Label(header, text='🌍 Mundo', style='TLabel', width=20, anchor='center').pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text='Tamaño', style='TLabel', width=15, anchor='center').pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text='Backup', style='TLabel', width=10, anchor='center').pack(side=tk.LEFT, padx=5)
        # Lista de mundos
        world_names = [d for d in os.listdir(self.script_dir) if os.path.isdir(os.path.join(self.script_dir, d)) and d.startswith('world')]
        if not world_names:
            ttk.Label(self.worlds_list_frame, text='No se encontraron mundos.', style='TLabel').pack(pady=20)
            return
        for name in world_names:
            path = os.path.join(self.script_dir, name)
            size = self._format_size(self._get_folder_size(path))
            row = ttk.Frame(self.worlds_list_frame, style='Card.TFrame')
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
            messagebox.showinfo('Backup', f'Backup creado: {backup_name}')
        except Exception as e:
            messagebox.showerror('Backup', f'Error al crear backup: {e}')

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
        title = ttk.Label(card, text="📊 Estadísticas de Jugadores", style='Title.TLabel', font=("Segoe UI Semibold", 18))
        title.pack(anchor='w', pady=(0, 20))
        # Encabezados coloridos
        header_frame = ttk.Frame(card, style='Card.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header_frame, text='👤 Nombre', style='TLabel', width=18, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⎈ UUID', style='TLabel', width=28, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⏱️ Tiempo', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='💀 Muertes', style='TLabel', width=10, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ERROR_FG_CUSTOM).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text='⛏️ Minados', style='TLabel', width=12, anchor='center', font=("Segoe UI", 12, "bold"), foreground=ACCENT_COLOR).pack(side=tk.LEFT, padx=5)
        # Frame para filas
        self.stats_rows_frame = ttk.Frame(card, style='Card.TFrame')
        self.stats_rows_frame.pack(fill=tk.BOTH, expand=True)
        # Botón para refrescar
        refresh_btn = ttk.Button(card, text='Refrescar', command=self.update_stats_list, style='Accent.TButton')
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

if __name__ == "__main__":
    root = tk.Tk() # Ya no es ThemedTk
    # Los estilos globales se definen dentro de ServerControlGUI
    gui = ServerControlGUI(root)
    root.mainloop() 
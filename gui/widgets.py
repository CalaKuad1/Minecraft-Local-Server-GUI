import tkinter as tk
from tkinter import ttk
from utils.constants import FONT_UI_HEADER, FONT_UI_NORMAL, SECONDARY_BG, TERTIARY_BG, TEXT_PRIMARY

class CollapsiblePane(ttk.Frame):
    """A collapsible pane widget that can hide or show its content."""
    def __init__(self, parent, text="", body_background=SECONDARY_BG):
        super().__init__(parent, style='CardInner.TFrame')

        self.columnconfigure(0, weight=1)
        self.body_background = body_background
        
        # Header
        self.header_frame = ttk.Frame(self, style='CardInner.TFrame')
        self.header_frame.grid(row=0, column=0, sticky='ew')
        self.header_frame.columnconfigure(1, weight=1)

        self.toggle_button = ttk.Label(self.header_frame, text="▼", font=('Segoe UI', 10), style='TLabel')
        self.toggle_button.grid(row=0, column=0, padx=5, sticky='w')
        
        self.title_label = ttk.Label(self.header_frame, text=text, font=FONT_UI_HEADER, style='Header.TLabel')
        self.title_label.grid(row=0, column=1, sticky='w')

        # Body
        self.body = ttk.Frame(self, style='CardInner.TFrame', padding=(15, 10))

        self.toggle_button.bind("<Button-1>", self._toggle)
        self.title_label.bind("<Button-1>", self._toggle)
        self._is_collapsed = False
        self.body.grid(row=1, column=0, sticky='nsew', padx=5, pady=5) # Start expanded

    def _toggle(self, event):
        if self._is_collapsed:
            self.body.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
            self.toggle_button.configure(text="▼")
        else:
            self.body.grid_remove()
            self.toggle_button.configure(text="▶")
        self._is_collapsed = not self._is_collapsed

class ToolTip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tooltip_window = widget, text, None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)
    def show(self, event=None):
        if self.tooltip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        ttk.Label(tw, text=self.text, background=TERTIARY_BG, foreground=TEXT_PRIMARY, font=FONT_UI_NORMAL, relief='solid', borderwidth=1, padding=5).pack()
    def hide(self, event=None):
        if self.tooltip_window: self.tooltip_window.destroy()
        self.tooltip_window = None

class CustomDropdownMenu(ttk.Frame):
    def __init__(self, parent, textvariable, options, style_prefix, **kwargs):
        super().__init__(parent, **kwargs)
        self.textvariable = textvariable
        self.options = options
        self.style_prefix = style_prefix
        self.is_open = False

        self.button = ttk.Button(self, textvariable=self.textvariable, command=self.toggle, style=f"{self.style_prefix}.TButton")
        self.button.pack(fill=tk.BOTH, expand=True)

        self.window = tk.Toplevel(self.master)
        self.window.withdraw()
        self.window.wm_overrideredirect(True)

        self.frame = ttk.Frame(self.window, style=f"{self.style_prefix}.TFrame")
        self.frame.pack()

        self.canvas = tk.Canvas(self.frame, background=SECONDARY_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_frame = ttk.Frame(self.canvas, style=f"{self.style_prefix}.TFrame")

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.master.bind("<Configure>", self.hide)
        self.button.bind("<Destroy>", self.hide)

    def toggle(self, event=None):
        if self.is_open:
            self.hide()
        else:
            self.show()

    def show(self):
        self.is_open = True
        self.update_options(self.options)
        x = self.button.winfo_rootx()
        y = self.button.winfo_rooty() + self.button.winfo_height()
        self.window.wm_geometry(f"+{x}+{y}")
        self.window.deiconify()
        self.window.lift()
        self.window.focus_set()
        self.master.bind_all("<Button-1>", self._on_click_elsewhere, add=True)

    def hide(self, event=None):
        self.is_open = False
        self.window.withdraw()
        self.master.unbind_all("<Button-1>")

    def _on_click_elsewhere(self, event):
        if self.window.winfo_containing(event.x_root, event.y_root) is None:
            if self.button.winfo_containing(event.x_root, event.y_root) is None:
                self.hide()

    def update_options(self, options):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.options = options
        for option in self.options:
            btn = ttk.Button(self.scrollable_frame, text=option, 
                             command=lambda o=option: self.select(o), 
                             style=f"{self.style_prefix}.Item.TButton")
            btn.pack(fill=tk.X, expand=True)

    def select(self, option):
        self.textvariable.set(option)
        self.hide()

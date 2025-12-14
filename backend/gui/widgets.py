import customtkinter as ctk

class CollapsiblePane(ctk.CTkFrame):
    """A collapsible pane widget for customtkinter."""
    def __init__(self, parent, text="", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.columnconfigure(0, weight=1)
        
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        self.header_frame.grid(row=0, column=0, sticky='ew')
        self.header_frame.columnconfigure(1, weight=1)

        self.toggle_button = ctk.CTkLabel(self.header_frame, text="▼", font=('Segoe UI', 14, 'bold'))
        self.toggle_button.grid(row=0, column=0, padx=(5, 10), sticky='w')
        
        self.title_label = ctk.CTkLabel(self.header_frame, text=text, font=('Segoe UI', 16, 'bold'))
        self.title_label.grid(row=0, column=1, sticky='w')

        # Body
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)

        self.header_frame.bind("<Button-1>", self._toggle)
        self.toggle_button.bind("<Button-1>", self._toggle)
        self.title_label.bind("<Button-1>", self._toggle)
        
        self._is_collapsed = False

    def _toggle(self, event=None):
        if self._is_collapsed:
            self.body.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)
            self.toggle_button.configure(text="▼")
        else:
            self.body.grid_remove()
            self.toggle_button.configure(text="▶")
        self._is_collapsed = not self._is_collapsed

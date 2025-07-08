import customtkinter as ctk
from minecraft_server_gui import ServerControlGUI

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

if __name__ == '__main__':
    root = ctk.CTk()
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = 1000, 750
    x, y = (ws/2) - (w/2), (hs/2) - (h/2)
    root.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
    root.minsize(900, 650)
    app = ServerControlGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

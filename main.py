import tkinter as tk
from minecraft_server_gui import ServerControlGUI

if __name__ == '__main__':
    root = tk.Tk()
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = 1000, 750
    x, y = (ws/2) - (w/2), (hs/2) - (h/2)
    root.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
    root.minsize(900, 650)
    app = ServerControlGUI(root)
    root.mainloop()

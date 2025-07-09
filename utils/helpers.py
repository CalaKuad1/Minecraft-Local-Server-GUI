import math
import os
import socket
from PIL import Image, ImageDraw, ImageTk

def create_rounded_rectangle(width, height, radius, color):
    """Create a rounded rectangle image."""
    img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width, height), radius, fill=color)
    return img

def format_size(size_bytes):
    if size_bytes == 0: return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024))) if size_bytes > 0 else 0
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def get_folder_size(path):
    """Iteratively calculates the size of a folder."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        # Skip files that can't be accessed
                        pass
    except OSError:
        # Return 0 if the root path is inaccessible
        return 0
    return total

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP
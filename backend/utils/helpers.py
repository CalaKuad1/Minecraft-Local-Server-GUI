import math
import os
import socket
import subprocess
import re
import sys
from PIL import Image, ImageDraw, ImageTk

def create_rounded_rectangle(width, height, radius, color):
    """Create a rounded rectangle image."""
    img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width, height), radius, fill=color)
    return img

# Las funciones de Java han sido movidas a utils/java_manager.py
# Mantenemos estas funciones por compatibilidad, pero redirigen al nuevo sistema

def get_java_version(java_path="java"):
    """Checks the version of the specified Java executable. (Legacy function)"""
    from .java_manager import JavaManager
    manager = JavaManager()
    result = manager.detect_system_java(java_path)
    return result[0] if result else None

def get_required_java_version(minecraft_version_str):
    """Determines the required major Java version for a given Minecraft version string. (Legacy function)"""
    from .java_manager import JavaManager
    manager = JavaManager()
    return manager.get_required_java_version(minecraft_version_str)

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

def get_server_port(server_properties_path):
    """Reads the server.properties file and returns the server port."""
    try:
        with open(server_properties_path, 'r') as f:
            for line in f:
                if line.strip().startswith('server-port='):
                    return int(line.split('=')[1].strip())
    except (IOError, IndexError, ValueError):
        return 25565 # Default Minecraft port
    return 25565 # Default if not found

def is_valid_minecraft_username(username):
    """Checks if a username is valid according to Minecraft's rules."""
    if not 3 <= len(username) <= 16:
        return False
    if not all(c.isalnum() or c == '_' for c in username):
        return False
    return True

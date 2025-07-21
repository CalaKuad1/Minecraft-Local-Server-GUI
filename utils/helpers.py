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

def get_java_version(java_path="java"):
    """Checks the version of the specified Java executable."""
    try:
        # The 'java -version' command outputs to stderr
        process = subprocess.run([java_path, "-version"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        output = process.stderr
        # Regex to find the version number (e.g., "1.8.0_291", "17.0.1", "21")
        match = re.search(r'version "(\d+)(?:\.\d+)*.*"', output)
        if match:
            major_version = int(match.group(1))
            # Java 8 reports as "1.8", so we need to handle that
            if major_version == 1:
                match_java_8 = re.search(r'version "1\.(\d+)', output)
                if match_java_8:
                    return int(match_java_8.group(1))
            return major_version
        return None
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        # Return None if java is not found, the command fails, or parsing fails
        return None

def get_required_java_version(minecraft_version_str):
    """Determines the required major Java version for a given Minecraft version string."""
    if not minecraft_version_str:
        return 8 # Default to 8 if version is unknown
    
    try:
        # Extract the minor version number (e.g., 16, 17, 20)
        parts = minecraft_version_str.split('.')
        if len(parts) >= 2:
            minor_version = int(parts[1])
            
            # Minecraft 1.21+ requires Java 21
            if minor_version >= 21:
                return 21
            
            # Minecraft 1.20.5+ requires Java 21
            if minor_version == 20:
                if len(parts) > 2 and int(parts[2]) >= 5:
                    return 21
                # MC 1.20 to 1.20.4 use Java 17
                return 17
            
            # Minecraft 1.17 to 1.19.4 use Java 17
            if minor_version >= 17:
                return 17
                
    except (ValueError, IndexError):
        pass # Fallback to default if parsing fails
        
    return 8 # Default for 1.16.5 and below

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

# Minecraft Server Control GUI

A Python-based graphical user interface for managing a Minecraft server.

## Prerequisites

*   Python 3.x installed (if running from script).
*   A pre-existing Minecraft server setup, including a `run.bat` (or equivalent for other OS) script to start the server. **The GUI application (script or executable) expects this file to be in the same directory as itself (the server's root directory).**
*   The Minecraft server's `server.properties`, `ops.json`, `usernamecache.json` (or `usercache.json`), and world data should be in the standard locations relative to the server's root directory.

## Installation (Running from Python Script)

1.  **Download the files:**
    Download `minecraft_server_gui.py` and `requirements.txt`.
2.  **Place files in server directory:**
    **Crucially, place both `minecraft_server_gui.py` and `requirements.txt` directly into your Minecraft server's root directory.** This is the same directory that contains your `run.bat` (or equivalent) and server data folders like `world`.

3.  **Install dependencies:**
    Open a terminal or command prompt **in the server's root directory** and run:
    ```bash
    pip install -r requirements.txt
    ```

## Usage (Running from Python Script)

1.  Navigate to the server's root directory in your terminal or command prompt.
2.  Run the GUI application:
    ```bash
    python minecraft_server_gui.py
    ```

## Using the Executable (Recommended for ease of use)

If an executable version (e.g., `MinecraftServerGUI.exe` on Windows) is provided:

1.  **Download the executable.**
2.  **Place the executable in your server directory:**
    **Crucially, place the `MinecraftServerGUI.exe` (or equivalent for your OS) directly into your Minecraft server's root directory.** This is the same directory that contains your `run.bat` (or equivalent) and server data folders like `world`.
3.  **Run the executable:**
    Double-click the `MinecraftServerGUI.exe` (or run it from the terminal if preferred).
    No Python installation or `pip install` steps are needed for the executable version.

## Application Features

The application will open, allowing you to:
*   Start and stop your Minecraft server.
*   View the server console and send commands.
*   Manage server properties (`server.properties`).
*   Monitor server resource usage (CPU, RAM).
*   View connected players.
*   Manage server operators (`ops.json`).
*   View and backup server worlds.
*   View basic player statistics.

## Notes

*   The application identifies the server process by looking for Java processes associated with "forge" or "minecraft" in their command line, or by proximity to the script's/executable's directory. Resource monitoring accuracy depends on correctly identifying the server process.
*   **The `run.bat` (or equivalent) file must be in the same directory as `minecraft_server_gui.py` or `MinecraftServerGUI.exe` (i.e., the server's root directory).**
*   The server properties, ops list, and world information are loaded from files expected to be in the server directory (e.g., `server.properties`, `ops.json`, `world/` folder). 

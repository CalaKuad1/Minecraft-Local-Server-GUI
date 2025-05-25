# Minecraft Server Control GUI

A Python-based graphical user interface for managing a Minecraft server.

## Prerequisites

*   Python 3.x installed.
*   A pre-existing Minecraft server setup, including a `run.bat` (or equivalent for other OS) script to start the server. The GUI application expects this file to be in the same directory as the script.
*   The Minecraft server's `server.properties`, `ops.json`, `usernamecache.json` (or `usercache.json`), and world data should be in the standard locations relative to the server's root directory (where `run.bat` is located).

## Installation

1.  **Clone or download the repository/files.**
    Place `minecraft_server_gui.py` and `requirements.txt` in your Minecraft server's root directory.

2.  **Install dependencies:**
    Open a terminal or command prompt in the server's root directory and run:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Navigate to the server's root directory in your terminal or command prompt.
2.  Run the GUI application:
    ```bash
    python minecraft_server_gui.py
    ```
3.  The application will open, allowing you to:
    *   Start and stop your Minecraft server.
    *   View the server console and send commands.
    *   Manage server properties (`server.properties`).
    *   Monitor server resource usage (CPU, RAM).
    *   View connected players.
    *   Manage server operators (`ops.json`).
    *   View and backup server worlds.
    *   View basic player statistics.

## Notes

*   The application identifies the server process by looking for Java processes associated with "forge" or "minecraft" in their command line, or by proximity to the script's directory. Resource monitoring accuracy depends on correctly identifying the server process.
*   The `run.bat` file must be in the same directory as `minecraft_server_gui.py`.
*   The server properties, ops list, and world information are loaded from files expected to be in the server directory (e.g., `server.properties`, `ops.json`, `world/` folder). 
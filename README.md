# Minecraft Local Server GUI

A user-friendly desktop application for installing, managing, and running local Minecraft servers. Built with Python and Tkinter, this tool provides a complete graphical interface for server administration, from initial setup to daily management.

## Features

- **Easy Setup Wizard**:
  - **Install New Servers**: Download and install a new server with just a few clicks. Supports **Vanilla, Paper, Spigot, Forge, and Fabric**.
  - **Use Existing Servers**: Easily import and manage a pre-existing server folder.
- **Complete Server Control**:
  - **One-Click Actions**: Start, Stop, and Restart the server directly from the GUI.
  - **Live Console**: View the live server console, with color-coded messages for errors and warnings.
  - **Command Input**: Send commands directly to the server through the interface.
- **Management Panels**:
  - **Properties Editor**: A graphical editor for `server.properties` with categorized, collapsible sections and helpful descriptions.
  - **Player Management**: View connected players with their avatars, op/de-op, kick, or ban them with a right-click.
  - **Operators & Bans**: Manage server operators and banned players/IPs, with support for offline modifications.
  - **World Management**: View all world folders and create backups with a single click.
  - **Mod Management**: For Forge/Fabric, view installed mods, enable/disable them, view/edit their config files, and delete them.
- **Resource Monitoring**:
  - Live graphs showing the server's CPU and RAM usage over time.
- **Smart & Automated**:
  - **Automatic EULA Handling**: Automatically detects and accepts the EULA on the first run of a new server.
  - **Smart Startup**: Automatically uses the correct startup script (`run.bat`/`run.sh`) for Forge servers.
- **Customization & Settings**:
  - **Custom RAM Allocation**: Easily set the minimum and maximum RAM for your server.
  - **Configuration Saving**: Remembers your server path and settings between sessions.

## Requirements

- **Python 3.x**
- **Java**: You must have Java installed on your system for the application to run the Minecraft server JAR file.
- The required Python packages are listed in `requirements.txt`:
  ```
  requests
  psutil
  Pillow
  matplotlib
  ```

## Installation & Usage

1.  **Clone the Repository**:
    ```sh
    git clone https://github.com/your-username/Minecraft-Local-Server-GUI.git
    cd Minecraft-Local-Server-GUI
    ```
2.  **Install Dependencies**:
    ```sh
    pip install -r requirements.txt
    ```
3.  **Run the Application**:
    ```sh
    python main.py
    ```
4.  **First-Time Setup**:
    - The first time you run the app, a setup wizard will appear.
    - Choose to **install a new server** (the app will download all necessary files) or **use an existing server folder**.
    - Once configured, the main GUI will launch, and your settings will be saved for the next session.

## Project Structure

```
Minecraft-Local-Server-GUI/
├── gui/
│   ├── widgets.py         # Custom Tkinter widgets (CollapsiblePane, etc.)
├── server/
│   ├── config_manager.py  # Handles saving/loading of GUI and server settings.
│   └── server_handler.py  # Manages the Minecraft server process.
├── utils/
│   ├── api_client.py      # Handles API calls to fetch server versions, player data, etc.
│   ├── constants.py       # Stores UI constants like colors and fonts.
│   └── helpers.py         # Utility functions.
├── main.py                # Main entry point of the application.
├── minecraft_server_gui.py # The core class for the main GUI window and all its logic.
├── requirements.txt       # Python package dependencies.
└── README.md              # This file.
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
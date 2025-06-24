# Minecraft Local Server GUI

A user-friendly desktop application for installing, managing, and running local Minecraft servers on your PC. Built with Python and Tkinter.

## Features

- **Easy Setup Wizard**:
  - Install a new server with just a few clicks. Supports **Vanilla, Paper, Spigot, Forge, and Fabric**.
  - Or, use a pre-existing server folder.
- **Complete Server Control**:
  - One-click **Start, Stop, and Restart** buttons.
  - **Live server console** integrated into the GUI to see logs in real-time.
  - Send commands directly to the server through the interface.
- **User-Friendly Management Panels**:
  - **Properties Editor**: A graphical editor for `server.properties` with categorized, collapsible sections and helpful descriptions for each option.
  - **Player Management**: View connected players, op/deop, kick, or ban them with a right-click. Player avatars are displayed next to their names.
  - **Operators**: Manage the server's operator list, with support for offline adding/removing.
  - **Worlds**: View and create backups of your world folders.
  - **Resource Monitoring**: Live graphs showing the server's CPU and RAM usage.
- **Forge & Mod Support**:
  - **Mod Management**: View installed mods, enable/disable them, view their config files, and delete them.
  - **Smart Startup**: Automatically uses the correct startup script (`run.bat`) for Forge servers.
  - **Automatic EULA Handling**: Automatically detects and accepts the EULA when a new server is started for the first time.
- **Customization & Settings**:
  - **Custom RAM Allocation**: Easily set the minimum and maximum RAM for your server.
  - Remembers your server path and settings between sessions.

## Prerequisites

- **Java**: You must have Java installed on your system and available in your system's PATH for the application to be able to run the Minecraft server.

## How to Use

1.  **Clone or Download**: Get the source code from this repository.
    ```sh
    git clone <repository_url>
    ```
2.  **Install Dependencies**: Navigate to the project folder and install the required Python packages.
    ```sh
    pip install -r requirements.txt
    ```
3.  **Run the Application**:
    ```sh
    python minecraft_server_gui.py
    ```
4.  **First-Time Setup**:
    - The first time you run the app, a setup wizard will appear.
    - Choose to **install a new server** (the app will download all necessary files) or **use an existing server folder**.
    - Once configured, the main GUI will launch, and your settings will be saved for the next session.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

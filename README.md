<div align="center">
  <img src="assets/logo.png" alt="Logo" width="150">
  <h1>Minecraft Local Server GUI</h1>
  
  <p><strong>🎮 The definitive tool for managing local Minecraft servers</strong></p>
  
  <p>An intuitive desktop application that completely automates the installation, configuration, and management of Minecraft servers. Featuring automatic Java management, a modern graphical interface, and full support for all server types.</p>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.7+-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Java-Auto--Managed-green.svg" alt="Java Auto-Managed">
    <img src="https://img.shields.io/badge/Minecraft-All%20Versions-orange.svg" alt="Minecraft Support">
    <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg" alt="Platform Support">
  </p>
</div>

---

### 🚀 Key Features

**NEW: Automatic Java Management**
*   **Smart Detection**: Automatically detects the required Java version for each Minecraft version.
*   **Automatic Download**: Downloads and installs Java 8, 17, or 21 as required.
*   **Per-Server Configuration**: Each server is automatically configured to use its correct Java version.
*   **Error Elimination**: Completely eliminates "UnsupportedClassVersionError" issues.

**Effortless Installation and Setup**
*   **Installation Wizard**: Download and configure servers with just a few clicks.
*   **Universal Support**: Compatible with Vanilla, Paper, Spigot, Forge, and Fabric.
*   **Easy Import**: Automatically import and manage existing server installations.
*   **Smart Configuration**: Automatically detects server versions and configures the appropriate Java environment.

---

### ⚙️ Full Feature List

**Complete Server Control**
*   **One-Click Actions**: Start, stop, and restart servers directly from the interface.
*   **Live Console**: View server logs in real-time with color-coded errors and warnings.
*   **Command Input**: Send commands directly to the server from the application interface.
*   **Resource Monitoring**: View real-time graphs of CPU and RAM usage.

**Advanced Player Management**
*   **Visual Player List**: See currently connected players with their Minecraft avatars.
*   **Operator Management**: Grant or revoke administrator permissions with ease.
*   **Ban System**: Ban players or IPs, with support for offline-mode servers.
*   **Player Statistics**: View detailed statistics for each player.

**Intuitive Configuration**
*   **Properties Editor**: A graphical editor for `server.properties` with organized, easy-to-navigate sections.
*   **World Management**: View all world folders and create backups with a single click.
*   **Mod Management**: For Forge and Fabric, you can enable/disable mods and edit their configurations.
*   **Persistent Settings**: All configurations and server paths are saved between sessions.

**Advanced Functions**
*   **Make Public (Experimental)**: Exposes your local server to the internet with one click. For better performance and stability, we recommend using a dedicated external service like `playit.gg`.
*   **Automatic EULA Handling**: Automatically accepts the Minecraft EULA on the first launch of a new server.
*   **Smart Start**: Automatically uses the correct startup scripts for modded servers like Forge.
*   **Custom RAM Allocation**: Easily configure the minimum and maximum RAM for each server.

**Security and Stability**
*   **Automatic Validation**: Verifies server configurations before applying any changes.
*   **Error Recovery**: Features intelligent error handling and automatic recovery mechanisms.
*   **Detailed Logs**: A complete logging system is integrated for diagnosing application issues.

---

### 📋 System Requirements
*   **Python 3.7+**: Must be installed and added to the system's PATH.
*   **Java**: No longer required. The application automatically downloads and manages all necessary Java versions.
*   **Internet Connection**: Required for the initial download of server files and Java runtimes.
*   **Disk Space**: Approximately 500MB for Java installations, plus additional space for each server.

---

### 🚀 Installation and Use

**Quick Start (Recommended)**

**For Windows:**
1.  Download the project from GitHub (Code button → Download ZIP).
2.  Extract the ZIP file to your preferred folder.
3.  Execute `run.bat`.
4.  The application will install dependencies and launch automatically.

**For macOS/Linux:**
1.  Clone or download the repository:
    ```bash
    git clone https://github.com/your-username/Minecraft-Local-Server-GUI.git
    cd Minecraft-Local-Server-GUI
    ```
2.  Install dependencies and run:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python main.py
    ```

**Manual Installation (Advanced)**

If you prefer to install manually or encounter issues with the automated scripts:
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/CalaKuad1/Minecraft-Local-Server-GUI.git
    cd Minecraft-Local-Server-GUI
    ```
2.  **Create and activate a virtual environment:**
    *   **Windows:**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the application:**
    ```bash
    python main.py
    ```

---

### 🎮 First Use

**Setup Wizard**
*   On its first run, the application will launch an intuitive setup wizard.
*   **Choose an option**:
    *   **Install New Server**: The application will download and configure everything automatically.
    *   **Use Existing Server**: Import a pre-existing server folder.
*   **Automated Java Handling**: The application detects the Minecraft version and downloads the correct Java runtime automatically.
*   Once completed, the main interface will open, and your settings will be saved for future sessions.

---

### ☕ Java Management System

**The Problem It Solves**
*   **Previously**: Users would encounter `UnsupportedClassVersionError` when running new Minecraft versions with outdated Java.
*   **Currently**: The system functions automatically without these errors.

**How It Works**
*   **Automatic Detection**: Identifies the server's Minecraft version from its core files.
*   **Smart Download**: Fetches the correct Java version from trusted sources like Eclipse Adoptium.
*   **Automatic Linking**: Ensures each server instance uses the appropriate Java runtime.
*   **Efficient Management**: Reuses existing Java installations for other compatible servers.

**Version Compatibility**
| Minecraft Version   | Required Java | Status                 |
|:--------------------|:--------------|:-----------------------|
| 1.21+               | Java 21       | ✅ Automatic Download |
| 1.20.5 - 1.20.6     | Java 21       | ✅ Automatic Download |
| 1.17 - 1.20.4       | Java 17       | ✅ System or Download   |
| 1.16.5 and earlier  | Java 8        | ✅ System or Download   |


**Benefits**
*   **Zero compatibility errors**: Each server runs on its correct Java version.
*   **Automated installation**: No need to install or manage Java manually.
*   **Multi-version support**: Maintains separate installations of Java 8, 17, and 21 simultaneously.
*   **Intelligent detection**: Automatically recognizes Minecraft versions.

---

### ❓ Frequently Asked Questions

**Installation Issues**
*   **Q: What should I do if Python is not installed?**
    A: Download Python from python.org. During installation, ensure the "Add Python to PATH" option is checked.
*   **Q: The automatic installer is not working. What can I do?**
    A: Follow the manual installation instructions. Ensure you have the necessary administrative permissions if required.

**Java Issues**
*   **Q: I already have Java installed. Why is the application downloading another version?**
    A: The application downloads specific, sandboxed versions of Java to guarantee compatibility and prevent conflicts with system-wide installations. This is intended behavior.
*   **Q: Can I use my existing system Java installation?**
    A: Yes. If a compatible system-wide Java version is detected, the application may use it. However, its internal manager is designed to prevent version conflicts.

**Server Issues**
*   **Q: My server fails to start. How can I diagnose the issue?**
    A: Check the server logs in the console tab. The application will display specific errors and may provide suggestions.
*   **Q: How can I import an existing server?**
    A: In the initial setup wizard, select "Use Existing Server" and navigate to your server's root folder.

**"Make Public" Functionality**
*   **Q: Is it safe to make my server public?**
    A: This feature uses a public tunneling service. It should only be used with trusted individuals. We strongly recommend configuring a whitelist for your server.
*   **Q: Why does the public address change with each session?**
    A: This is standard for free tunneling services, which generate dynamic addresses upon connection.

---

### 🛠️ Troubleshooting

**Quick Diagnostics**
*   **Verify Python**: Open a terminal and run `python --version`. It should return version 3.7 or higher.
*   **Check Permissions**: If you encounter file access errors, try running the application as an administrator.
*   **Review Logs**: The application's console provides detailed error messages for diagnostics.
*   **Restart the Application**: A simple restart can resolve many temporary issues.

**Getting Help**
*   **GitHub Issues**: Report bugs or request new features on the project's GitHub page.
*   **Provide Detailed Logs**: When reporting an issue, always include the relevant logs from the console.
*   **Include System Information**: Mention your operating system, Python version, and Java version.

---

### 📄 License
This project is licensed under the MIT License. See the LICENSE file for more details.

---

### ⭐ Support the Project
If this project has been useful to you, please consider giving it a star on GitHub! This helps other users discover the tool and motivates continued development.

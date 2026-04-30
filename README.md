<div align="center">
  <img src="electron-app/public/images/logo2.png" alt="Logo" width="200">
  
  <h1>Minecraft Local Server GUI</h1>
  
  <p><strong>The ultimate tool for installing and managing Minecraft servers — beautiful, modern, and effortless.</strong></p>
  
  <p>
    <a href="https://github.com/CalaKuad1/Minecraft-Local-Server-GUI/releases/latest">
      <img src="https://img.shields.io/badge/⬇️_Download-Windows-00d26a?style=for-the-badge&logo=windows" alt="Download Windows">
    </a>
    <a href="https://github.com/CalaKuad1/Minecraft-Local-Server-GUI/releases/latest">
      <img src="https://img.shields.io/badge/⬇️_Download-Linux-fcc624?style=for-the-badge&logo=linux&logoColor=black" alt="Download Linux">
    </a>
  </p>
  
  <p>
    <img src="https://img.shields.io/badge/Electron-28.3.3-47848F?logo=electron" alt="Electron">
    <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react" alt="React">
    <img src="https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi" alt="FastAPI">
    <img src="https://img.shields.io/badge/Java-Auto--Managed-ED8B00?logo=openjdk" alt="Java">
  </p>

  <br>
  
  <img src="images/dashboard-screenshot.png" alt="Dashboard Screenshot" width="800">
</div>

---

## What's New in v1.2.0

### Complete UI Redesign
- **Pixel art icon system** — Custom 16x16 pixel icons throughout the entire UI for a cohesive Minecraft-inspired aesthetic
- **Visual effects** — Mouse spotlight tracking, noise grain overlay, magnetic button hover effects, and animated abstract backgrounds
- **Server Library** — Completely redesigned server selector with grid view, search, recently opened section, and engine type icons
- **Refined dark theme** — Deeper blacks, improved contrast, and smoother glassmorphism panels

### NeoForge Support
- Full support for **NeoForge** as a server engine alongside Vanilla, Paper, Spigot, Forge, and Fabric
- NeoForge appears in the Setup Wizard, Mods browser, and server cards with its own icon

### Modpacks
- New **Modpacks** tab in the Mods section — browse and install modpacks directly from Modrinth

### Multi-Language (i18n)
- Interface available in **English, Spanish, French, and Russian**
- Language selector in the new App Settings panel

### App Settings
- New dedicated **Settings panel** with language, theme, notifications, and more options

### Other Improvements
- **Error Boundary** — Graceful error handling across the UI
- **WebSocket Context** — Centralized real-time communication layer
- **Engine icons** — Each server type (Vanilla, Paper, Spigot, Forge, NeoForge, Fabric) now has its own visual icon in cards and selectors
- **Improved Mods browser** — Filter by loader (Fabric, Forge, NeoForge, Quilt), version, category, and sort order

---

## Download & Install

**One-click installation** — No Python or Java required!

| Platform | Download |
|:--------:|:---------|
| **Windows** | [Download Installer (.exe)](https://github.com/CalaKuad1/Minecraft-Local-Server-GUI/releases/latest) |
| **Linux** | [Download AppImage (.AppImage)](https://github.com/CalaKuad1/Minecraft-Local-Server-GUI/releases/latest) |

> **Note:** The app automatically downloads and manages Java for you. Just install and play!

---

## Features

<table>
<tr>
<td width="50%">

### Server Management
- **One-click server creation** — Vanilla, Paper, Spigot, Forge, **NeoForge**, Fabric
- **Multiple server profiles** — Switch between servers instantly
- **Live console** with real-time logs and command input
- **Start/Stop controls** with visual status indicators
- **Server Conflict Guard** — Prevents running multiple servers simultaneously

</td>
<td width="50%">

### Automatic Java
- **Zero configuration** — Java 8/17/21 downloaded automatically
- **Smart detection** — Matches Java version to Minecraft version
- **No more errors** — Eliminates `UnsupportedClassVersionError`
- **Isolated installations** — Won't affect your system Java

</td>
</tr>
<tr>
<td width="50%">

### Dashboard
- **Real-time stats** — CPU, RAM, and uptime monitoring with sparkline graphs
- **Public Server** — Share your server globally via SSH tunnel (Pinggy)
- **Region Selection** — EU, US, and Asia for best latency
- **Local IP display** — Easy LAN connection for friends
- **Quick command input** — Send commands from dashboard

### Mods & Modpacks
- **Mod search & install** — Browse and install mods from Modrinth
- **Modpacks** — Browse and install complete modpacks
- **Advanced filters** — Filter by loader, version, category, sort order
- **Smart warning** — Vanilla/Paper show a hint to install a mod loader

</td>
<td width="50%">

### Configuration
- **Visual settings editor** — No file editing required
- **server.properties GUI** — All options organized by category
- **RAM allocation** — Customize min/max memory with smart system limits
- **Player management** — Op, ban, whitelist with one click

### Multi-Language
- **4 languages** — English, Spanish, French, Russian
- **One-click switch** — Change language from App Settings

### Worlds & Backups
- **World list** with last modified time
- **Fast loading** — Sizes computed in background and cached
- **One-click backups** — ZIP backups inside your server folder

</td>
</tr>
</table>

---

## Modern UI

Built with **React** and **Tailwind CSS**, featuring:
- **Dark theme** — Deep, high-contrast dark design
- **Glassmorphism** — Blurred, translucent panels
- **Pixel art icons** — Custom Minecraft-inspired icon set
- **Smooth animations** — Powered by Framer Motion
- **Interactive effects** — Mouse spotlight, noise grain, magnetic buttons

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Electron + React + Vite |
| **Styling** | Tailwind CSS + Framer Motion |
| **Backend** | Python + FastAPI + Uvicorn |
| **i18n** | Custom React Context (en/es/fr/ru) |
| **Packaging** | electron-builder (GitHub Actions CI/CD) |

---

## Development Setup

```bash
# Clone the repository
git clone https://github.com/CalaKuad1/Minecraft-Local-Server-GUI.git
cd Minecraft-Local-Server-GUI

# Backend setup
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Frontend setup
cd ../electron-app
npm install

# Run in development mode
npm run dev
```

### Building the Installer (Production)

```bash
cd electron-app
npm run electron:build
```

**Automated Multi-platform Release**:
1. Bump version in `package.json`
2. Push a tag: `git tag v1.x.x && git push origin v1.x.x`
3. GitHub will build and publish everything automatically!

---

## Requirements

### For Users
- **Windows 10/11** (64-bit) or **Linux** (AppImage / .deb)
- **Internet connection** (for initial Java download)
- ~500MB disk space

### For Developers
- Node.js 18+
- Python 3.8+
- npm or yarn

---

## FAQ

<details>
<summary><strong>Why is it downloading Java?</strong></summary>

The app automatically downloads the correct Java version for your Minecraft server. This is sandboxed and won't affect your system Java installation.
</details>

<details>
<summary><strong>Can my friends connect to my server?</strong></summary>

For **LAN**: Share the Local IP shown in the dashboard.  
For **Internet**: Use a tunneling service like [playit.gg](https://playit.gg) (recommended) or configure port forwarding on your router.
</details>

<details>
<summary><strong>Is the UI available in other languages?</strong></summary>

Yes — the app UI is available in **English, Spanish, French, and Russian**. You can switch languages from App Settings.
</details>

<details>
<summary><strong>Where are my servers stored?</strong></summary>

Server files are stored in the location you choose during setup. App configuration is saved in `%APPDATA%/MinecraftServerGUI`.
</details>

<details>
<summary><strong>How do I import an existing server?</strong></summary>

Click "Add Server" in the Library, then select your server folder. The app will auto-detect the server type and version.
</details>

<details>
<summary><strong>Where is app data stored on Linux?</strong></summary>

On Linux, all app data is stored in `~/.minecraft_server_gui/`. On Windows, it's in `%APPDATA%/MinecraftServerGUI`.
</details>

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Support

If this project helped you, please **star the repository**  
It helps others discover the tool and motivates development!

<div align="center">
  <br>
  <p>Made with love by <a href="https://github.com/CalaKuad1">CalaKuad1</a></p>
</div>

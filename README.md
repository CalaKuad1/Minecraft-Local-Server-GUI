<div align="center">
  <img src="electron-app/public/images/icon.ico" alt="Logo" width="200">
  
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

## What's New in v1.3.2

### Fixed Server Addresses (DNS)
- **Permanent domain** — Your server gets a permanent address like `survival.play.ariser.app` that never changes
- **Auto-update** — DNS updates automatically every time the tunnel starts or the subdomain changes
- **Inline editing** — Click the pencil icon to change your server's subdomain
- **Duplicate protection** — Checks availability before assigning a subdomain

### Console Improvements
- **Search & filter** — Search bar and level badges (CMD/INF/WRN/ERR) for quick log navigation
- **Export logs** — Download button saves console history as `.txt`
- **Polling fallback** — Console fetches logs via REST API when WebSocket is disconnected

### Auto-Restart
- Toggle in Dashboard header — server restarts automatically on crash (max 3 attempts)

<details>
<summary><strong>Earlier versions</strong></summary>

### Auto-Restart on Crash
- Server automatically restarts after unexpected shutdowns — toggle it on/off from the Dashboard header
- Up to 3 restart attempts with a 3-second delay between retries

### Console Improvements
- **Export logs** — Download button saves the full console history as a `.txt` file
- **Search & filter** — Search bar and level filter (All/CMD/INF/WRN/ERR) for quick log navigation
- **Always usable input** — Console input stays enabled even when WebSocket is disconnected (REST API fallback)

### Stability Fixes
- **Logs persist across tab switches** — No more losing console logs when navigating between panels
- **Dashboard mini-console** — REST API fallback for sending commands when WebSocket is down
- **Connection status** — Clear "Disconnected" indicator instead of misleading "Loading..." state

---

<details>
<summary><strong>Earlier: v1.2.0 — UI Redesign & NeoForge</strong></summary>

### Complete UI Redesign
- **Pixel art icon system** — Custom 16x16 pixel icons throughout the entire UI
- **Visual effects** — Mouse spotlight, noise grain, magnetic buttons, abstract backgrounds
- **Server Library** — Redesigned grid view with search, recently opened, engine type icons

### NeoForge Support & Modpacks
- **NeoForge** as a new server engine + **Modpacks** tab for browsing and installing from Modrinth
- **Multi-Language (i18n)** — English, Spanish, French, and Russian with language selector in App Settings

</details>

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
- **Live console** with real-time logs, search/filter, export, and command input
- **Auto-restart on crash** — Detects and restarts server automatically after unexpected shutdowns
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
- **Auto-restart** — Toggle to automatically restart server on crash (max 3 attempts)
- **Public Server** — Share your server globally via SSH tunnel (Pinggy/Playit)
- **Fixed Address (DNS)** — Permanent domain via Cloudflare proxy (e.g. `survival.play.yourdomain.com`)
- **Region Selection** — EU, US, and Asia for best latency
- **Local IP display** — Easy LAN connection for friends
- **Quick command input** — Send commands from dashboard with WebSocket/REST fallback

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

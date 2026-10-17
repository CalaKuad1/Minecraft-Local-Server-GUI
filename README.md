<div align="center">
  <img src="images/cubi-logo.png" alt="Cubi logo" width="140">

  <h1>Cubi — Minecraft Local Server GUI</h1>

  <p><strong>Host a Minecraft server on your own PC and play with your friends in a minute.<br>Free, no limits, no port forwarding.</strong></p>

  <p>
    <a href="https://github.com/CalaKuad1/Minecraft-Local-Server-GUI/releases/latest">
      <img src="https://img.shields.io/badge/Download-Windows-10b981?style=for-the-badge&logo=windows" alt="Download for Windows">
    </a>
    <a href="https://github.com/CalaKuad1/Minecraft-Local-Server-GUI/releases/latest">
      <img src="https://img.shields.io/badge/Download-Linux-10b981?style=for-the-badge&logo=linux&logoColor=white" alt="Download for Linux">
    </a>
  </p>

  <p>
    <img src="https://img.shields.io/github/downloads/CalaKuad1/Minecraft-Local-Server-GUI/total?color=6ee7b7&label=downloads" alt="Downloads">
    <img src="https://img.shields.io/github/stars/CalaKuad1/Minecraft-Local-Server-GUI?color=6ee7b7" alt="Stars">
    <img src="https://img.shields.io/badge/license-MIT-6ee7b7" alt="MIT license">
    <img src="https://img.shields.io/badge/languages-EN%20%C2%B7%20ES%20%C2%B7%20FR%20%C2%B7%20RU-6ee7b7" alt="Languages">
  </p>

  <br>
  <img src="images/screenshots/dashboard-online.png" alt="Cubi dashboard with the address to share with friends" width="860">
</div>

---

## How it works

1. **Create** — pick how you want to play (Vanilla, Paper plugins, Fabric/Forge/NeoForge mods). Cubi downloads the server and the right Java for you.
2. **Start** — the server starts by itself and gets a public address. No router setup.
3. **Share** — copy the address and send it to your friends. They paste it in *Multiplayer → Add Server*.

## Features

| | |
|---|---|
| **Play with friends from anywhere** | Public address in one click, a **free permanent address** with playit.gg, or a fixed `name.play.ariser.app` address. No port forwarding. |
| **Players** | Everyone who joined, with a **3D skin wearing their armor**, stats, inventory and ender chest with real item icons (vanilla *and* modded). Op, whitelist, kick and ban in one click. |
| **Mods & plugins** | Search and install from Modrinth, modpacks included. Installed list with readable names. |
| **Worlds & backups** | Automatic backups on a schedule, restore, download or import in one click. |
| **Simple settings** | Every option explained in plain words, RAM presets, live MOTD preview. |
| **Automatic Java** | The correct Java for each Minecraft version is downloaded and kept separate from your system. |
| **Bedrock crossplay** | With GeyserMC, phone and console players can join your Java server. |
| **4 languages** | English, Spanish, French and Russian. |

<details>
<summary><strong>More screenshots</strong></summary>
<br>

| | |
|:--:|:--:|
| <img src="images/screenshots/players.png" alt="Player card with 3D skin and inventory" width="400"><br><sub>Players</sub> | <img src="images/screenshots/mods.png" alt="Mods browser" width="400"><br><sub>Mods</sub> |
| <img src="images/screenshots/worlds.png" alt="Worlds and backups" width="400"><br><sub>Worlds & backups</sub> | <img src="images/screenshots/settings.png" alt="Server settings" width="400"><br><sub>Settings</sub> |
| <img src="images/screenshots/wizard-type.png" alt="Setup wizard" width="400"><br><sub>Setup wizard</sub> | <img src="images/screenshots/library.png" alt="Your servers" width="400"><br><sub>Your servers</sub> |

</details>

## Download

| Platform | |
|:--|:--|
| **Windows 10/11** (64-bit) | `.exe` installer |
| **Linux** | `.AppImage` or `.deb` |

[Download the latest version](https://github.com/CalaKuad1/Minecraft-Local-Server-GUI/releases/latest). Already using MLSG 1.x? The app will update to Cubi and keep your servers and settings.

No Python or Java needed. See the [changelog](CHANGELOG.md) for what's new.

## FAQ

<details>
<summary><strong>Do my friends need to install anything?</strong></summary>

Only Minecraft Java Edition (the same version as your server). With mods, they need the same mods too. Bedrock players can join if you install GeyserMC.
</details>

<details>
<summary><strong>Do I need to open ports on my router?</strong></summary>

No. Cubi creates a public tunnel automatically. Link a free playit.gg account once to get a permanent address with no time limit; otherwise a temporary Pinggy tunnel (60-minute sessions) is used.
</details>

<details>
<summary><strong>Why does it download Java and game graphics?</strong></summary>

Each Minecraft version needs a specific Java; Cubi downloads it into its own folder without touching your system. Item icons and skins are generated on your PC from the official game files downloaded from Mojang, once per version — Cubi doesn't ship any Mojang artwork.
</details>

<details>
<summary><strong>Where are my servers and settings stored?</strong></summary>

Servers live in the folder you choose (default `~/MinecraftServers`). App data is in `%APPDATA%/MinecraftServerGUI` on Windows and `~/.minecraft_server_gui/` on Linux.
</details>

<details>
<summary><strong>Can I import a server I already have?</strong></summary>

Yes: *New server → I already have a server*, then choose its folder. The type and version are detected automatically.
</details>

## Development

```bash
git clone https://github.com/CalaKuad1/Minecraft-Local-Server-GUI.git
cd Minecraft-Local-Server-GUI

# Backend (Python 3.11+)
cd backend
python -m venv venv
venv\Scripts\activate          # Windows  (Linux: source venv/bin/activate)
pip install -r requirements.txt

# Frontend (Node 18+)
cd ../electron-app
npm install
npm run dev
```

**Releases** are built by GitHub Actions: bump `electron-app/package.json`, then push a tag (`git tag v2.0.0 && git push origin v2.0.0`). Tags with a suffix such as `-beta.1` are published as pre-releases.

| Layer | Technology |
|---|---|
| App | Electron + React + Vite + Tailwind |
| Backend | Python + FastAPI |
| Packaging | electron-builder + PyInstaller (GitHub Actions) |

## License

[MIT](LICENSE). Made by [CalaKuad1](https://github.com/CalaKuad1). If Cubi helps you, starring the repo helps others find it.

<sub>Cubi is not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.</sub>

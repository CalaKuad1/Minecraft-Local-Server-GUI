# Changelog

## v2.0.0 — Cubi

MLSG is now **Cubi**: a redesigned app focused on one goal — get a Minecraft server running and your friends in, in a minute.

### Look & feel
- New name, logo and a mascot (Cubi reacts to your server: asleep when it's off, cheering when it's online — and when you click it).
- New visual style: clean green-tinted dark UI, readable fonts, line icons, real server-type logos.
- Startup splash, no layout "shaking", dashboard that fits without scrolling.

### Play with friends, faster
- Plain-language setup wizard (EN/ES/FR/RU); the new server starts by itself.
- A big **"Share this address with your friends"** card with a Copy button and how-to.
- **Free permanent address with playit.gg** (one-click link), Pinggy as fallback. Clear error and automatic fallback when a free playit account is over its agent limit.
- The fixed `*.play.ariser.app` address no longer gets deleted when a tunnel restarts.

### Players
- One player list (online, operators, whitelist, banned, everyone who joined) with a player card: **3D skin with the armor they wear**, stats, actions and their **inventory and ender chest with real item icons** — vanilla and modded items. Supports the Minecraft 26.x player-data layout.
- Item graphics are generated on your PC from the official game files (downloaded from Mojang after the EULA is accepted). Cubi ships no Mojang artwork.
- Player names in the console and dashboard are clickable.

### Mods, plugins, worlds, settings
- Redesigned Mods/Plugins browser (Modrinth): richer cards, install progress, readable installed list.
- Server settings with plain explanations, sliders, RAM presets and an unsaved-changes bar.
- Worlds & backups redesigned.

### Fixes
- Backend falls back to a free port when 8000 is in use.
- Blocking endpoints no longer freeze the UI; slow requests are logged.

## v1.3.3

### Linux
- **AppImage fixed on older distros** — the bundled Python backend crashed on startup with `GLIBC_2.38 not found`. Linux builds now target Ubuntu 22.04 (glibc 2.35), so the AppImage runs on all supported Ubuntu LTS releases and equivalents.

---

## v1.3.1

### Mods & Plugins
- **Accurate "Installed" badges** — projects whose jar name differs from their slug (e.g. Simple Voice Chat → `voicechat-*.jar`) are now detected correctly on the Mods and Plugins pages.
- **Per-card download progress** — each card shows its own progress bar while installing, plus a success flash when it finishes.

### Updates & App Settings
- **Auto-update policy** — choose **Automatic**, **Ask me first** (checks automatically, downloads only when you press Download) or **Off**.
- **Themed in-app dialogs** — browser popups are gone; deleting a server offers "Delete Profile Only" or "Delete Profile & Files" in one dialog.
- **Save states & real version** — Settings and Worlds show unsaved changes and a brief "Saved" confirmation; App Settings shows the actual app version.

### Reliability
- **Hardened downloads** — server jars, Java, mods, plugins and modpacks now fail fast on permanent errors, retry only transient ones, verify the file size and never leave partial files behind.
- **Transactional modpacks** — path-traversal entries are rejected, a failed install rolls the server folder back, and pre-existing files that were overwritten are restored.
- **Cleaner server switching** — the app waits for the previous server to stop before switching, and the library shows a retryable error instead of failing silently.
- **Setup Wizard** — defaults to `~/MinecraftServers` (fixes a literal `C:` folder being created on Linux/macOS).

<sub>Thanks to [@awtawsif](https://github.com/awtawsif) for PRs #19 and #20.</sub>

---

## v1.3.0

### Bedrock & Console Crossplay (GeyserMC)
- **Play with any device** — If GeyserMC is installed, the Dashboard detects it and shows a one-click **Bedrock Crossplay** panel. iOS, Android, Windows Bedrock, PlayStation, Xbox and Switch players can join your Java server.
- **No port forwarding** — A public UDP tunnel (Pinggy) is created automatically, and the address + port are shown with copy buttons.
- **Floodgate & port detection** — Floodgate is detected (badge) and the Bedrock port is read from Geyser's `config.yml`.
- **Safe & cancellable download** — The Pinggy CLI is downloaded on first use (Windows/macOS/Linux, x64/arm64) and verified against the official size + SHA-256 before running.
- **60-minute free tunnels** — Free Pinggy tunnels expire after ~60 minutes; restart from the Dashboard to renew.

### Stability & Fixes (PRs #17 & #18)
- **RAM fixed** — MB values now display correctly (512M → 0.5 GB) and RAM/Java settings are saved **per server** and applied without restarting.
- **Windows tunnel crash fixed** — The CLI output is now decoded as UTF-8 (`charmap` error).
- **Reliable internal API calls** — Status polling, tray and graceful shutdown now send the required token.
- **Safer window handling** — Minimize/maximize/close can't crash during teardown; auto-restart no longer swallows errors; preload listener leak fixed.
- **Better UX** — Force-stop confirmation localized (EN/ES/FR/RU), version dropdowns accept plain lists, and the lint/build pipeline is fixed.

<sub>Thanks to [@awtawsif](https://github.com/awtawsif) for PRs #17 and #18.</sub>

---

## v1.2.8

### Fixed a Massive Memory Leak
- **Backend no longer eats RAM** — an infinite loop in the Server List Ping code made the backend grow ~25-45 MB/s while a server was online (reaching 18 GB). It now stays around 70 MB.

### Security
- **Local API locked down** — every request now requires a per-launch token, and CORS is restricted to the app, so a malicious website can no longer control your server through localhost.

### Worlds & Backups
- **Full backup control** — restore, delete, download and upload backups.
- **Automatic backups** — schedule them by interval and choose how many to keep.

### Custom Address (DNS)
- **No more DNS quota errors** — the SRV record is created when the tunnel starts and removed when it stops/closes/is deleted, and the real error is shown if the DNS Worker fails.

### Console
- **Command history & autocomplete** — Up/Down history and Tab suggestions, plus logs that survive navigating back to the library.

### Fixes & UI
- Fixed the Schedule Shutdown crash, duplicate tunnels, the dead "Import World" button, icon 404s and log rotation.
- Redesigned the Server Library and translated Players/Worlds/Mods/Plugins into English, Spanish, French and Russian.
- **Auto-update** support, and builds now always ship the current backend.

## v1.2.7

### Fixed Server Installation (Paper/Spigot/Fabric)
- **Paper install fixed** — Installing Paper (and Spigot/Fabric) no longer fails with "Failed to download Server JAR." The server type is now lowercased before hitting the mcutils API, which returned HTTP 500 for capitalized types.
- **Reliable downloads** — Server JAR downloads now retry on transient CDN/Cloudflare errors with backoff, and the real failure reason (URL + status) is shown in the UI instead of a generic message.

### Fixed "Link to folder"
- **Import existing server works again** — The "Link Project" button in the Setup Wizard was silently broken (missing API method). It now detects the engine/version from your folder and registers the server, with loading and error feedback.

### Linux Memory Leak Fix
- **Massive RAM leak resolved** — On Linux, `api_server` could hold gigabytes after a server stopped. Log lines are now truncated before being stored in memory, the read buffer is reused, freed heap is returned to the OS via `malloc_trim`, and the backend no longer generates huge volumes of per-chunk debug log garbage.
- **Real log file now works** — `backend_debug.log` is now actually written (a logging setup bug previously sent everything to stderr).

## Earlier versions

### What's New in v1.2.5

### Fixed Server Addresses (DNS)
- **Permanent domain** — Your server gets a permanent address like `survival.play.tudominio.app` that never changes
- **Auto-generated** — A unique subdomain is created automatically when the tunnel starts
- **Duplicate protection** — Subdomains are permanently reserved for your server, never released
- **Inline editing** — Edit your subdomain directly in the Dashboard with availability checking
- **Cloudflare DNS Proxy** — Open-source Worker manages SRV records (repo: `MLSG-DNS-Worker`)

### Console
- **Search & filter** — Search bar and level badges (CMD/INF/WRN/ERR)
- **Export logs** — Download console history as `.txt`
- **Always works** — REST API fallback when WebSocket is disconnected

### Dashboard
- **Premium/No Premium** — Quick online-mode toggle in the Dashboard header
- **Auto-restart on crash** — Toggle to auto-restart server on unexpected shutdown
- **Auto-Tunnel** — Tunnel starts automatically with the server (toggle in Advanced)
- **Boot from library** — "Boot" button on server cards in the library

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

## Earlier: v1.2.0 — UI Redesign & NeoForge

### Complete UI Redesign
- **Pixel art icon system** — Custom 16x16 pixel icons throughout the entire UI
- **Visual effects** — Mouse spotlight, noise grain, magnetic buttons, abstract backgrounds
- **Server Library** — Redesigned grid view with search, recently opened, engine type icons

### NeoForge Support & Modpacks
- **NeoForge** as a new server engine + **Modpacks** tab for browsing and installing from Modrinth
- **Multi-Language (i18n)** — English, Spanish, French, and Russian with language selector in App Settings


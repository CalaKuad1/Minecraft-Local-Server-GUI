const API_URL = "http://127.0.0.1:8000";

// Shared secret injected by Electron (see electron/preload.cjs). Required by the
// backend on every request; absent when running the backend standalone in dev.
export const API_TOKEN = (typeof window !== 'undefined' && window.electron && window.electron.apiToken) || '';

const fetchJson = async (url, options, timeoutMs = 8000) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const mergedOptions = {
        ...(options || {}),
        signal: controller.signal,
        headers: {
            ...(options && options.headers ? options.headers : {}),
            ...(API_TOKEN ? { 'X-MLSG-Token': API_TOKEN } : {})
        }
    };

    try {
        const res = await fetch(url, mergedOptions);
        const text = await res.text();
        let data = null;
        try {
            data = text ? JSON.parse(text) : null;
        } catch {
            data = text;
        }

        if (!res.ok) {
            const detail = (data && typeof data === 'object' && data.detail) ? data.detail : (typeof data === 'string' ? data : 'Request failed');
            throw new Error(`${res.status} ${res.statusText}: ${detail}`);
        }
        return data;
    } catch (e) {
        if (e && (e.name === 'AbortError' || String(e).includes('AbortError'))) {
            throw new Error('Request timed out');
        }
        throw e;
    } finally {
        clearTimeout(timeoutId);
    }
};

export const api = {
    // --- System ---
    // ... existing ... 
    getStatus: async () => {
        try {
            return await fetchJson(`${API_URL}/status`, {}, 15000);
        } catch (e) { 
            console.error("Status check failed:", e);
            return { status: 'offline', cpu: 0, ram: 0, players: 0 };
        }
    },
    start: async () => {
        await fetchJson(`${API_URL}/start`, { method: 'POST' }, 30000);
    },
    stop: async (force = false) => {
        await fetchJson(`${API_URL}/stop?force=${force}`, { method: 'POST' }, 15000);
    },
    getOnlineMode: async () => {
        return await fetchJson(`${API_URL}/server/online-mode`);
    },
    setOnlineMode: async (onlineMode) => {
        return await fetchJson(`${API_URL}/server/online-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ online_mode: onlineMode })
        });
    },
    sendCommand: async (command) => {
        await fetchJson(`${API_URL}/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
    },
    setAutoRestart: async (enabled) => {
        await fetchJson(`${API_URL}/server/auto-restart?enabled=${enabled}`, { method: 'POST' });
    },
    getAutoRestart: async () => {
        return await fetchJson(`${API_URL}/server/auto-restart`);
    },
    scheduleStop: async (minutes) => {
        return await fetchJson(`${API_URL}/server/schedule-stop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ minutes })
        });
    },
    cancelStop: async () => {
        return await fetchJson(`${API_URL}/server/cancel-stop`, { method: 'POST' });
    },
    setup: async (_serverType, _version, _path) => {
        // ... (placeholder if needed or remove if used differently)
    },
    getVersions: async (type) => {
        return await fetchJson(`${API_URL}/setup/versions/${type}`);
    },
    validatePath: async (path) => {
        return await fetchJson(`${API_URL}/setup/validate-path`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
    },
    detectServer: async (path) => {
        return await fetchJson(`${API_URL}/setup/detect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
    },
    installServer: async (data) => {
        await fetchJson(`${API_URL}/setup/install`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }, 60000);
    },
    getInstallProgress: async () => {
        return await fetchJson(`${API_URL}/setup/install/progress`);
    },
    // --- Java Management ---
    checkJava: async (minecraftVersion) => {
        return await fetchJson(`${API_URL}/setup/java/check/${minecraftVersion}`);
    },
    installJava: async (minecraftVersion) => {
        await fetchJson(`${API_URL}/setup/java/install`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ minecraft_version: minecraftVersion })
        }, 60000);
    },
    configure: async (config) => {
        await fetchJson(`${API_URL}/configure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
    },

    // --- Player Management ---
    getPlayers: async () => {
        return await fetchJson(`${API_URL}/players/lists`);
    },
    opPlayer: async (name) => {
        await fetchJson(`${API_URL}/players/op`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    deopPlayer: async (name) => {
        await fetchJson(`${API_URL}/players/deop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    whitelistAdd: async (name) => {
        await fetchJson(`${API_URL}/players/whitelist/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    whitelistRemove: async (name) => {
        await fetchJson(`${API_URL}/players/whitelist/remove`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    kickPlayer: async (name, reason = "Kicked") => {
        await fetchJson(`${API_URL}/players/kick`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, reason })
        });
    },
    banPlayer: async (name, reason = "Banned") => {
        await fetchJson(`${API_URL}/players/ban`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, reason })
        });
    },
    unbanPlayer: async (name) => {
        await fetchJson(`${API_URL}/players/pardon`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },

    // --- Settings ---
    getServerProperties: async () => {
        return await fetchJson(`${API_URL}/settings/properties`);
    },
    updateServerProperties: async (props) => {
        await fetchJson(`${API_URL}/settings/properties`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(props)
        });
    },
    // App Settings point to the global state
    getAppSettings: async () => {
        return await fetchJson(`${API_URL}/app-settings`);
    },
    updateAppSettings: async (settings) => {
        return await fetchJson(`${API_URL}/app-settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    },

    // --- Worlds ---
    getWorlds: async () => {
        return await fetchJson(`${API_URL}/worlds`);
    },

    getWorldBackups: async (world = null) => {
        const url = world ? `${API_URL}/worlds/backups?world=${encodeURIComponent(world)}` : `${API_URL}/worlds/backups`;
        return await fetchJson(url);
    },

    createWorldBackup: async (world = null) => {
        return await fetchJson(`${API_URL}/worlds/backups/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ world })
        });
    },
    deleteWorldBackup: async (name) => {
        return await fetchJson(`${API_URL}/worlds/backups/${encodeURIComponent(name)}`, {
            method: 'DELETE'
        });
    },
    restoreWorldBackup: async (name, world = null) => {
        return await fetchJson(`${API_URL}/worlds/backups/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, world })
        }, 180000);
    },
    uploadWorldBackup: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return await fetchJson(`${API_URL}/worlds/backups/upload`, {
            method: 'POST',
            body: formData
        }, 180000);
    },
    downloadWorldBackup: async (name) => {
        // <a download> can't send the auth header, so fetch the blob and save it.
        const res = await fetch(`${API_URL}/worlds/backups/download/${encodeURIComponent(name)}`, {
            headers: API_TOKEN ? { 'X-MLSG-Token': API_TOKEN } : {}
        });
        if (!res.ok) throw new Error(`Download failed (${res.status})`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    },
    getBackupSettings: async () => {
        return await fetchJson(`${API_URL}/server/backup-settings`);
    },
    updateBackupSettings: async (settings) => {
        return await fetchJson(`${API_URL}/server/backup-settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    },

    // --- Multi-Server Management ---
    getServers: async () => {
        return await fetchJson(`${API_URL}/servers`);
    },
    addServer: async (serverConfig) => {
        return await fetchJson(`${API_URL}/servers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(serverConfig)
        });
    },
    // Link an existing server folder: detect engine/version, then register it.
    // (Previously this method was missing and the "Link Project" button in the
    // Setup Wizard silently did nothing — api.importServer was undefined.)
    importServer: async (path) => {
        if (!path) throw new Error('A server path is required');

        // Derive a friendly name from the folder name
        const name = path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || 'imported-server';

        // Detect engine + version from the folder contents
        let detected = { type: 'vanilla', version: null };
        try {
            detected = await fetchJson(`${API_URL}/setup/detect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
        } catch (e) {
            // Detection is best-effort; fall back to a generic vanilla profile
            console.warn('Server detection failed, using defaults:', e);
        }

        const serverType = (detected && detected.type && detected.type !== 'unknown')
            ? detected.type
            : 'vanilla';
        const version = (detected && detected.version) ? detected.version : null;

        return await fetchJson(`${API_URL}/servers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                path,
                type: serverType,
                version,
                ram_min: '2',
                ram_max: '4',
                ram_unit: 'G'
            })
        });
    },
    selectServer: async (serverId) => {
        return await fetchJson(`${API_URL}/servers/select`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server_id: serverId })
        });
    },
    deleteServer: async (serverId, deleteFiles = false) => {
        const url = `${API_URL}/servers/${serverId}${deleteFiles ? '?delete_files=true' : ''}`;
        await fetchJson(url, { method: 'DELETE' });
    },

    // (Consolidated above)

    // --- System ---
    openDirectoryPicker: async () => {
        if (window.electron && window.electron.openDirectory) {
            return await window.electron.openDirectory();
        }
        return null;
    },
    openFilePicker: async () => {
        if (window.electron && window.electron.openFile) {
            return await window.electron.openFile();
        }
        return null;
    },
    openServerFolder: async () => {
        return await fetchJson(`${API_URL}/server/open-folder`, { method: 'POST' });
    },

    // --- Tunnel (Public Server) ---
    getTunnelStatus: async () => {
        return await fetchJson(`${API_URL}/tunnel/status`);
    },
    startTunnel: async (region = "eu", provider = "pinggy") => {
        return await fetchJson(`${API_URL}/tunnel/start?region=${region}&provider=${provider}`, { method: 'POST' }, 30000);
    },
    stopTunnel: async () => {
        return await fetchJson(`${API_URL}/tunnel/stop`, { method: 'POST' }, 15000);
    },
    setTunnelAddress: async (address) => {
        return await fetchJson(`${API_URL}/tunnel/set-address`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address })
        });
    },

    // --- Bedrock Tunnel (GeyserMC Crossplay) ---
    getBedrockTunnelStatus: async () => {
        return await fetchJson(`${API_URL}/tunnel/bedrock/status`);
    },
    startBedrockTunnel: async (region = "eu") => {
        return await fetchJson(`${API_URL}/tunnel/bedrock/start?region=${region}`, { method: 'POST' }, 60000);
    },
    stopBedrockTunnel: async () => {
        return await fetchJson(`${API_URL}/tunnel/bedrock/stop`, { method: 'POST' }, 15000);
    },
    getGeyserStatus: async () => {
        return await fetchJson(`${API_URL}/server/geyser`);
    },

    getDnsSubdomain: async () => {
        return await fetchJson(`${API_URL}/server/dns-subdomain`);
    },
    setDnsSubdomain: async (subdomain) => {
        return await fetchJson(`${API_URL}/server/dns-subdomain`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subdomain })
        });
    },
    checkDnsSubdomain: async (subdomain) => {
        return await fetchJson(`${API_URL}/server/dns-check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subdomain })
        });
    },
    cleanupDns: async () => {
        return await fetchJson(`${API_URL}/server/dns-cleanup`, { method: 'POST' }, 60000);
    },
    verifyDns: async () => {
        return await fetchJson(`${API_URL}/server/dns-verify`, { method: 'POST' }, 60000);
    },
    getDnsUsage: async () => {
        return await fetchJson(`${API_URL}/server/dns-usage`, {}, 30000);
    },

    // --- Mods ---
    searchMods: async (query, loader = 'fabric', version = null, projectType = 'mod', sort = 'downloads', category = null) => {
        let url = `${API_URL}/mods/search?q=${encodeURIComponent(query)}&loader=${loader}&project_type=${projectType}&sort=${sort}`;
        if (version) url += `&version=${version}`;
        if (category && category !== 'all') url += `&category=${category}`;
        return await fetchJson(url);
    },
    getModVersions: async (slug, loader = 'fabric', version = null) => {
        let url = `${API_URL}/mods/versions/${slug}?loader=${loader}`;
        if (version) url += `&version=${version}`;
        return await fetchJson(url);
    },
    getInstalledMods: async () => {
        return await fetchJson(`${API_URL}/mods/installed`);
    },
    installMod: async (versionId) => {
        return await fetchJson(`${API_URL}/mods/install`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ version_id: versionId })
        });
    },
    deleteMod: async (filename) => {
        return await fetchJson(`${API_URL}/mods/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
    },
    openModsFolder: async () => {
        return await fetchJson(`${API_URL}/mods/open-folder`, { method: 'POST' });
    },
    importMod: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return await fetchJson(`${API_URL}/mods/import`, {
            method: 'POST',
            body: formData
        }, 30000);
    },

    // --- Server Appearance ---
    uploadServerIcon: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return await fetchJson(`${API_URL}/server/icon`, {
            method: 'POST',
            body: formData
        }, 30000);
    },
    getServerIconStatus: async () => {
        // Just checking if it exists
        return await fetchJson(`${API_URL}/server/icon`);
    },

    // --- Plugins ---
    getPlugins: async () => {
        return await fetchJson(`${API_URL}/server/plugins`);
    },
    uploadPlugin: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return await fetchJson(`${API_URL}/server/plugins`, {
            method: 'POST',
            body: formData
        }, 30000);
    },
    deletePlugin: async (filename) => {
        return await fetchJson(`${API_URL}/server/plugins/${filename}`, { method: 'DELETE' });
    },

    // --- Plugin Browsing (Modrinth) ---
    searchPlugins: async (query, version = null, sort = 'downloads', category = null) => {
        let url = `${API_URL}/plugins/search?q=${encodeURIComponent(query)}&sort=${sort}`;
        if (version) url += `&version=${version}`;
        if (category && category !== 'all') url += `&category=${category}`;
        return await fetchJson(url);
    },
    getPluginVersions: async (slug, version = null) => {
        let url = `${API_URL}/plugins/versions/${slug}`;
        if (version) url += `?version=${version}`;
        return await fetchJson(url);
    },
    installPlugin: async (versionId) => {
        return await fetchJson(`${API_URL}/plugins/install`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ version_id: versionId })
        });
    }
};

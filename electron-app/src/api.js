const API_URL = "http://127.0.0.1:8000";

const fetchJson = async (url, options, timeoutMs = 8000) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const mergedOptions = {
        ...(options || {}),
        signal: controller.signal
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
            return await fetchJson(`${API_URL}/status`);
        } catch (e) { return { status: 'offline' }; }
    },
    start: async () => {
        await fetchJson(`${API_URL}/start`, { method: 'POST' });
    },
    stop: async (force = false) => {
        await fetchJson(`${API_URL}/stop?force=${force}`, { method: 'POST' });
    },
    sendCommand: async (command) => {
        await fetchJson(`${API_URL}/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
    },
    setup: async (serverType, version, path) => {
        // ... (placeholder if needed or remove if used differently)
    },
    getVersions: async (type) => {
        const res = await fetch(`http://127.0.0.1:8000/setup/versions/${type}`);
        return await res.json();
    },
    validatePath: async (path) => {
        const res = await fetch('http://127.0.0.1:8000/setup/validate-path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        return await res.json();
    },
    installServer: async (data) => {
        await fetch('http://127.0.0.1:8000/setup/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    detectServer: async (path) => {
        const res = await fetch('http://127.0.0.1:8000/setup/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        return await res.json();
    },
    // --- Java Management ---
    checkJava: async (minecraftVersion) => {
        const res = await fetch(`http://127.0.0.1:8000/setup/java/check/${minecraftVersion}`);
        return await res.json();
    },
    installJava: async (minecraftVersion) => {
        await fetch('http://127.0.0.1:8000/setup/java/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ minecraft_version: minecraftVersion })
        });
    },
    configure: async (config) => {
        await fetch('http://127.0.0.1:8000/configure', {
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
    getAppSettings: async () => {
        return await fetchJson(`${API_URL}/settings/app`);
    },
    updateAppSettings: async (settings) => {
        await fetchJson(`${API_URL}/settings/app`, {
            method: 'POST',
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

    // --- System ---
    openDirectoryPicker: async () => {
        if (window.electron && window.electron.openDirectory) {
            return await window.electron.openDirectory();
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
    startTunnel: async (region = "eu") => {
        return await fetchJson(`${API_URL}/tunnel/start?region=${region}`, { method: 'POST' });
    },
    stopTunnel: async () => {
        return await fetchJson(`${API_URL}/tunnel/stop`, { method: 'POST' });
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
    }
};

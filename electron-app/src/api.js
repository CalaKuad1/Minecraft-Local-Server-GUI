export const api = {
    // ... existing ... 
    getStatus: async () => {
        try {
            const res = await fetch('http://127.0.0.1:8000/status');
            return await res.json();
        } catch (e) { return { status: 'offline' }; }
    },
    start: async () => {
        await fetch('http://127.0.0.1:8000/start', { method: 'POST' });
    },
    stop: async () => {
        await fetch('http://127.0.0.1:8000/stop', { method: 'POST' });
    },
    sendCommand: async (command) => {
        await fetch('http://127.0.0.1:8000/command', {
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
        const res = await fetch('http://127.0.0.1:8000/players/lists');
        return await res.json();
    },
    opPlayer: async (name) => {
        await fetch('http://127.0.0.1:8000/players/op', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    deopPlayer: async (name) => {
        await fetch('http://127.0.0.1:8000/players/deop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    whitelistAdd: async (name) => {
        await fetch('http://127.0.0.1:8000/players/whitelist/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    whitelistRemove: async (name) => {
        await fetch('http://127.0.0.1:8000/players/whitelist/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },
    kickPlayer: async (name, reason = "Kicked") => {
        await fetch('http://127.0.0.1:8000/players/kick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, reason })
        });
    },
    banPlayer: async (name, reason = "Banned") => {
        await fetch('http://127.0.0.1:8000/players/ban', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, reason })
        });
    },
    unbanPlayer: async (name) => {
        await fetch('http://127.0.0.1:8000/players/pardon', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
    },

    // --- Settings ---
    getServerProperties: async () => {
        const res = await fetch('http://127.0.0.1:8000/settings/properties');
        return await res.json();
    },
    updateServerProperties: async (props) => {
        await fetch('http://127.0.0.1:8000/settings/properties', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(props)
        });
    },
    getAppSettings: async () => {
        const res = await fetch('http://127.0.0.1:8000/settings/app');
        return await res.json();
    },
    openServerFolder: async () => {
        await fetch('http://127.0.0.1:8000/system/open-folder', { method: 'POST' });
    },
    updateAppSettings: async (settings) => {
        await fetch('http://127.0.0.1:8000/settings/app', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    },

    // --- Worlds ---
    getWorlds: async () => {
        const res = await fetch('http://127.0.0.1:8000/worlds');
        return await res.json();
    },

    // --- Multi-Server Management ---
    getServers: async () => {
        const res = await fetch('http://127.0.0.1:8000/servers');
        return await res.json();
    },
    addServer: async (serverConfig) => {
        const res = await fetch('http://127.0.0.1:8000/servers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(serverConfig)
        });
        return await res.json();
    },
    selectServer: async (serverId) => {
        const res = await fetch('http://127.0.0.1:8000/servers/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server_id: serverId })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to select server');
        }
        return await res.json();
    },
    deleteServer: async (serverId) => {
        await fetch(`http://127.0.0.1:8000/servers/${serverId}`, {
            method: 'DELETE'
        });
    },

    // --- System ---
    openDirectoryPicker: async () => {
        if (window.electron && window.electron.openDirectory) {
            return await window.electron.openDirectory();
        }
        return null;
    },

    // --- Tunnel (Public Server) ---
    getTunnelStatus: async () => {
        const res = await fetch('http://127.0.0.1:8000/tunnel/status');
        return await res.json();
    },
    startTunnel: async (region = "eu") => {
        const res = await fetch(`http://127.0.0.1:8000/tunnel/start?region=${region}`, { method: 'POST' });
        return await res.json();
    },
    stopTunnel: async () => {
        const res = await fetch('http://127.0.0.1:8000/tunnel/stop', { method: 'POST' });
        return await res.json();
    }
};

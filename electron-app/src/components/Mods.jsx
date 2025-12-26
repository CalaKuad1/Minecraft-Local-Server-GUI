import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Search, Download, Trash2, Package, RefreshCw, ExternalLink, HardDrive } from 'lucide-react';
import { useDialog } from './ui/DialogContext';

export default function Mods({ status, onOpenWizard }) {
    const dialog = useDialog();
    const [activeTab, setActiveTab] = useState('browse'); // 'browse' | 'installed'
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [installedMods, setInstalledMods] = useState([]);
    const [loading, setLoading] = useState(false);
    const [activeLoader, setActiveLoader] = useState('fabric');
    const [activeVersion, setActiveVersion] = useState('');
    const [installing, setInstalling] = useState({}); // { versionId: boolean }
    const [error, setError] = useState(null);

    // Filters
    const [sortBy, setSortBy] = useState('downloads'); // relevance, downloads, newest, updated
    const [category, setCategory] = useState('all'); // all, technology, magic, adventure, decoration, optimization

    // Initial load
    useEffect(() => {
        loadInstalledMods();
    }, []);

    const loadInstalledMods = async () => {
        try {
            const mods = await api.getInstalledMods();
            setInstalledMods(mods);
        } catch (e) {
            console.error("Failed to load installed mods:", e);
            setError(e?.message || 'Failed to load installed mods');
        }
    };

    // Sync state only on mount or when server type/version actually change
    const serverType = status?.type || status?.server_type || '';
    const serverVersion = status?.version || status?.minecraft_version || '';

    const lowerType = (serverType || '').toString().toLowerCase();
    const isNonModdedServer = lowerType.includes('vanilla') || lowerType.includes('paper');

    useEffect(() => {
        if (serverType) {
            const predictedLoader = serverType.toLowerCase().includes('forge') ? 'forge' : 'fabric';
            setActiveLoader(predictedLoader);
        }
        if (serverVersion) {
            setActiveVersion(serverVersion);
        }
    }, [serverType, serverVersion]);

    // Initial load & Debounced Search
    // Initial load & Debounced Search
    useEffect(() => {
        if (activeTab === 'browse' || activeTab === 'modpacks') {
            const timer = setTimeout(() => {
                performSearch(searchQuery);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery, activeTab, activeLoader, activeVersion, sortBy, category]);

    const performSearch = async (query) => {
        setLoading(true);
        setError(null);
        try {
            const projectType = activeTab === 'modpacks' ? 'modpack' : 'mod';
            const results = await api.searchMods(query, activeLoader, activeVersion, projectType, sortBy, category);
            setSearchResults(results);
        } catch (err) {
            setError(err?.message || "Failed to search mods. Please try again.");
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = (e) => {
        e.preventDefault();
        // Manual enter just triggers re-search instantly (clearing debounce technically handled by effect dependency)
        // But effect will handle it. We can just force it if needed, or do nothing.
    };

    const handleInstall = async (mod) => {
        // Find best version if we can, or just install what we have? 
        // NOTE: 'mod' here is a search result. It has 'project_id' or 'slug'.
        // We actually need a SPECIFIC FILE VERSION ID. 
        // The search result usually contains `latest_version` string or we should hit `getModVersions`.
        //
        // FOR NOW: Let's assume we fetch versions first to be safe, OR if the search result allows direct install (unlikely).
        // Modrinth Search Result -> slug.

        // 1. Fetch versions
        // 2. Install latest compatible

        try {
            setInstalling(prev => ({ ...prev, [mod.slug]: true })); // Use slug as key

            // Fetch versions
            const versions = await api.getModVersions(mod.slug, activeLoader, activeVersion);
            if (!versions || versions.length === 0) {
                // Try fetching "any" version just in case filters were too strict
                // Or just error
                throw new Error("No compatible versions found for this server.");
            }

            const targetVersion = versions[0]; // First one is usually latest

            // Trigger install
            // The backend now runs async and sends WS progress
            await api.installMod(targetVersion.id);

            // We don't await completion here anymore, we watch WS.
            // But we can keep state 'installing' until we get a completion event?
            // For now, let's rely on standard WS logs or optimistically say "Started".

        } catch (err) {
            console.error(err);
            setError(err.message);
            setInstalling(prev => ({ ...prev, [mod.slug]: false }));
        }
    };

    // Listen for install completion events
    useEffect(() => {
        const handleMessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'mod_install_complete') {
                    // Refresh installed list
                    loadInstalledMods();
                    // We can't easily know WHICH mod finished without more data from backend,
                    // but we can just clear all installing spinners or be smarter.
                    // For MVP simplicity:
                    setInstalling({});
                }
            } catch (e) { }
        };

        // We need access to the WebSocket. Ideally this component should receive the WS instance 
        // or we attach a global listener. 
        // Given 'status' prop might come from parent who holds WS.
        // Assuming there is a global WS or we reuse one?
        // 'SetupWizard' used a specific WS connection. The main Dashboard usually has one too.
        // If we don't have direct access here, we can rely on `loadInstalledMods` poll or just user manual refresh.
        // BUT, we want better UX.

        // Let's create a temp listener if we can't access global.
        const ws = new WebSocket('ws://127.0.0.1:8000/ws/console');
        ws.onmessage = handleMessage;

        return () => ws.close();
    }, []);

    const handleDelete = async (filename) => {
        if (!await dialog.confirm(`Delete ${filename}?`, "Delete Mod", "destructive")) return;
        try {
            await api.deleteMod(filename);
            loadInstalledMods();
        } catch (e) {
            console.error(e);
            dialog.alert("Failed to delete mod: " + e.message, "Error", "destructive");
            setError(e?.message || 'Delete failed');
        }
    };

    return (
        <div className="h-full flex flex-col animate-in fade-in zoom-in duration-500">
            {isNonModdedServer && (
                <div className="mb-4 p-4 rounded-2xl border border-yellow-500/20 bg-yellow-500/10 text-yellow-100/90 text-sm">
                    <div className="font-bold text-yellow-200 mb-1">Mods are not supported by your current server type</div>
                    <div className="text-yellow-100/80">
                        You are using <span className="font-mono">{serverType || 'Vanilla/Paper'}</span>. To install mods you need a modded server (Fabric / Forge / NeoForge).
                    </div>
                    <div className="mt-3">
                        <button
                            onClick={() => onOpenWizard && onOpenWizard()}
                            className="px-4 py-2 rounded-lg font-medium bg-white/10 hover:bg-white/15 border border-white/10 hover:border-white/20 transition-colors"
                        >
                            Open Setup Wizard
                        </button>
                    </div>
                </div>
            )}
            {error && (
                <div className="mb-4 p-3 rounded-xl border border-red-500/20 bg-red-500/10 text-red-200 text-sm">
                    {error}
                </div>
            )}
            {/* Header / Tabs */}
            <div className="flex items-center gap-4 mb-6">
                <button
                    onClick={() => setActiveTab('browse')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'browse' ? 'bg-primary text-white shadow-lg shadow-primary/25' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                >
                    Browse Mods
                </button>
                <button
                    onClick={() => setActiveTab('modpacks')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'modpacks' ? 'bg-primary text-white shadow-lg shadow-primary/25' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                >
                    Modpacks
                </button>
                <button
                    onClick={() => { setActiveTab('installed'); loadInstalledMods(); }}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'installed' ? 'bg-primary text-white shadow-lg shadow-primary/25' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                >
                    Installed ({installedMods.length})
                </button>
                <button
                    onClick={() => api.openModsFolder()}
                    className="px-4 py-2 rounded-lg font-medium bg-zinc-800 text-zinc-400 hover:text-white hover:bg-primary/20 transition-all flex items-center gap-2 ml-auto"
                    title="Open Mods Folder"
                >
                    <HardDrive size={18} />
                    Folder
                </button>
            </div>

            {(activeTab === 'browse' || activeTab === 'modpacks') && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex gap-2 mb-4">
                        <select
                            value={activeLoader}
                            onChange={(e) => setActiveLoader(e.target.value)}
                            className="bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white/80 focus:outline-none focus:border-primary/50"
                        >
                            <option value="any">Any Loader</option>
                            <option value="fabric">Fabric</option>
                            <option value="forge">Forge</option>
                            <option value="neoforge">NeoForge</option>
                            <option value="quilt">Quilt</option>
                        </select>
                        <input
                            type="text"
                            placeholder="Version"
                            value={activeVersion}
                            onChange={(e) => setActiveVersion(e.target.value)}
                            className="w-24 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white/80 focus:outline-none focus:border-primary/50 text-sm"
                        />

                        {/* Sort Dropdown */}
                        <select
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value)}
                            className="bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white/80 focus:outline-none focus:border-primary/50 text-sm"
                        >
                            <option value="relevance">Relevance</option>
                            <option value="downloads">Downloads</option>
                            <option value="newest">Newest</option>
                            <option value="updated">Updated</option>
                        </select>

                        {/* Category Dropdown */}
                        <select
                            value={category}
                            onChange={(e) => setCategory(e.target.value)}
                            className="bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white/80 focus:outline-none focus:border-primary/50 text-sm"
                        >
                            <option value="all">All Categories</option>
                            <option value="technology">Tech</option>
                            <option value="magic">Magic</option>
                            <option value="adventure">Adventure</option>
                            <option value="decoration">Decor</option>
                            <option value="optimization">Optimization</option>
                            <option value="library">Library</option>
                        </select>

                        <input
                            type="text"
                            placeholder={activeTab === 'modpacks' ? "Search..." : "Search..."}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="flex-1 bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary/50 transition-colors"
                        />
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {searchResults.map((mod) => (
                            <div key={mod.slug} className="bg-surface/40 border border-white/5 p-4 rounded-xl flex gap-4 hover:bg-surface/60 transition-colors">
                                <img
                                    src={mod.icon_url || 'https://cdn.modrinth.com/assets/logo.svg'}
                                    alt={mod.title}
                                    className="w-16 h-16 rounded-xl object-contain bg-black/20 p-2"
                                />
                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-bold text-lg text-white">{mod.title}</h3>
                                        <button
                                            onClick={() => handleInstall(mod)}
                                            disabled={installing[mod.slug]}
                                            className="p-2 hover:bg-white/10 rounded-lg transition-colors group"
                                            title="Install Latest"
                                        >
                                            <Download className={`w-5 h-5 ${installing[mod.slug] ? 'text-yellow-500 animate-pulse' : 'text-gray-400 group-hover:text-white'}`} />
                                        </button>
                                    </div>
                                    <p className="text-gray-400 text-sm line-clamp-2 mt-1">{mod.description}</p>
                                    <div className="flex gap-2 mt-2">
                                        <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-gray-500">{mod.author}</span>
                                        <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-gray-500 flex items-center gap-1"><Download size={10} /> {mod.downloads}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                        {searchResults.length === 0 && !loading && (
                            <div className="text-center text-gray-500 mt-10">
                                <Package size={48} className="mx-auto mb-4 opacity-20" />
                                <p>Search for mods via Modrinth</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {activeTab === 'installed' && (
                <div className="flex-1 overflow-y-auto pr-2 space-y-2 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                    {installedMods.length === 0 ? (
                        <div className="text-center text-gray-500 mt-10">
                            <HardDrive size={48} className="mx-auto mb-4 opacity-20" />
                            <p>No mods installed yet.</p>
                        </div>
                    ) : (
                        installedMods.map((file) => (
                            <div key={file.filename} className="bg-surface/40 border border-white/5 p-3 rounded-xl flex items-center justify-between group hover:bg-surface/60 transition-colors">
                                <div className="flex items-center gap-3">
                                    <Package size={20} className="text-primary" />
                                    <div>
                                        <div className="text-white font-medium">{file.filename}</div>
                                        <div className="text-xs text-gray-500">{file.size}</div>
                                    </div>
                                </div>
                                <button
                                    onClick={() => handleDelete(file.filename)}
                                    className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}

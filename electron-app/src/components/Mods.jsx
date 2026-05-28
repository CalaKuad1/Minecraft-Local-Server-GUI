import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api';
import { Search, Download, Trash2, Package, RefreshCw, ExternalLink, HardDrive } from './ui/PixelIcons';
import { useDialog } from './ui/DialogContext';
import { Select } from './ui/Select';
import { useWebSocket } from '../contexts/WebSocketContext';

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

    const { subscribe } = useWebSocket();

    useEffect(() => {
        return subscribe('mods', (item) => {
            if (item.type === 'mod_install_complete') {
                loadInstalledMods();
                setInstalling({});
            }
        });
    }, [subscribe]);

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
                <div className="mb-4 p-4 rounded-md border border-yellow-500/20 bg-yellow-500/10 text-yellow-100/90 text-sm">
                    <div className="font-bold text-yellow-200 mb-1 font-minecraft tracking-wider uppercase">Mods Unsupported</div>
                    <div className="text-yellow-100/80">
                        You are using <span className="font-mono text-emerald-400">{serverType || 'Vanilla/Paper'}</span>. To install mods you need a modded server (Fabric / Forge / NeoForge).
                    </div>
                    <div className="mt-3">
                        <button
                            onClick={() => onOpenWizard && onOpenWizard()}
                            className="px-4 py-2 rounded-md font-minecraft tracking-wider text-xs uppercase bg-white/10 hover:bg-white/15 border border-white/10 hover:border-white/20 transition-colors"
                        >
                            Open Setup Wizard
                        </button>
                    </div>
                </div>
            )}
            {error && (
                <div className="mb-4 p-3 rounded-md border border-red-500/20 bg-red-500/10 text-red-200 text-sm">
                    {error}
                </div>
            )}
            {/* Header / Tabs */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center bg-[#0a0a0a] border border-white/5 p-1 rounded-md max-w-fit shadow-inner">
                    <button
                        onClick={() => setActiveTab('browse')}
                        className={`px-6 py-2.5 rounded-sm font-minecraft tracking-wider text-sm transition-colors relative flex items-center justify-center gap-2 z-10 uppercase ${activeTab === 'browse' ? 'text-white' : 'text-zinc-500 hover:text-white'}`}
                    >
                        {activeTab === 'browse' && (
                            <motion.div layoutId="modsTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                        )}
                        <span className={`relative z-10 ${activeTab === 'browse' ? 'font-bold' : ''}`}>Browse</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('modpacks')}
                        className={`px-6 py-2.5 rounded-sm font-minecraft tracking-wider text-sm transition-colors relative flex items-center justify-center gap-2 z-10 uppercase ${activeTab === 'modpacks' ? 'text-white' : 'text-zinc-500 hover:text-white'}`}
                    >
                        {activeTab === 'modpacks' && (
                            <motion.div layoutId="modsTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                        )}
                        <span className={`relative z-10 ${activeTab === 'modpacks' ? 'font-bold' : ''}`}>Modpacks</span>
                    </button>
                    <button
                        onClick={() => { setActiveTab('installed'); loadInstalledMods(); }}
                        className={`px-6 py-2.5 rounded-sm font-minecraft tracking-wider text-sm transition-colors relative flex items-center justify-center gap-2 z-10 uppercase ${activeTab === 'installed' ? 'text-white' : 'text-zinc-500 hover:text-white'}`}
                    >
                        {activeTab === 'installed' && (
                            <motion.div layoutId="modsTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                        )}
                        <span className={`relative z-10 ${activeTab === 'installed' ? 'font-bold' : ''}`}>Installed ({installedMods.length})</span>
                    </button>
                </div>
                <button
                    onClick={() => api.openModsFolder()}
                    className="px-4 py-2 border border-transparent hover:border-white/10 rounded-md font-minecraft tracking-wider text-xs uppercase bg-transparent text-zinc-500 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2"
                    title="Open Mods Folder"
                >
                    <HardDrive size={18} />
                    Folder
                </button>
                <label className="px-4 py-2 border border-transparent hover:border-white/10 rounded-md font-minecraft tracking-wider text-xs uppercase bg-transparent text-zinc-500 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2 cursor-pointer ml-1">
                    <Plus size={18} />
                    Import
                    <input type="file" accept=".jar" className="hidden" onChange={async (e) => {
                        const file = e.target.files[0];
                        if (!file) return;
                        try {
                            await api.importMod(file);
                            loadInstalledMods();
                            e.target.value = '';
                        } catch (err) {
                            console.error('Import failed', err);
                        }
                    }} />
                </label>
            </div>

            {(activeTab === 'browse' || activeTab === 'modpacks') && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex gap-2 mb-4 h-10">
                        <div className="w-36">
                            <Select
                                value={activeLoader}
                                onChange={setActiveLoader}
                                options={[
                                    { value: 'any', label: 'Any Loader' },
                                    { value: 'fabric', label: 'Fabric' },
                                    { value: 'forge', label: 'Forge' },
                                    { value: 'neoforge', label: 'NeoForge' },
                                    { value: 'quilt', label: 'Quilt' }
                                ]}
                                className="h-full bg-black/40 border-white/5 rounded-sm text-[10px] font-minecraft tracking-widest"
                            />
                        </div>

                        <input
                            type="text"
                            placeholder="Version"
                            value={activeVersion}
                            onChange={(e) => setActiveVersion(e.target.value)}
                            className="w-24 bg-black/40 border border-white/5 rounded-sm px-3 py-2 text-white focus:outline-none focus:border-emerald-500/50 text-[10px] font-minecraft tracking-widest uppercase"
                        />

                        <div className="w-36">
                            <Select
                                value={sortBy}
                                onChange={setSortBy}
                                options={[
                                    { value: 'relevance', label: 'Relevance' },
                                    { value: 'downloads', label: 'Downloads' },
                                    { value: 'newest', label: 'Newest' },
                                    { value: 'updated', label: 'Updated' }
                                ]}
                                className="h-full bg-black/40 border-white/5 rounded-sm text-[10px] font-minecraft tracking-widest"
                            />
                        </div>

                        <div className="w-40">
                            <Select
                                value={category}
                                onChange={setCategory}
                                options={[
                                    { value: 'all', label: 'All' },
                                    { value: 'technology', label: 'Tech' },
                                    { value: 'magic', label: 'Magic' },
                                    { value: 'adventure', label: 'Adventure' },
                                    { value: 'decoration', label: 'Decor' },
                                    { value: 'optimization', label: 'Optim' },
                                    { value: 'library', label: 'Lib' }
                                ]}
                                className="h-full bg-black/40 border-white/5 rounded-sm text-[10px] font-minecraft tracking-widest"
                            />
                        </div>

                        <input
                            type="text"
                            placeholder={activeTab === 'modpacks' ? "Search..." : "Search..."}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="flex-1 bg-black/40 border border-white/10 rounded-sm px-4 py-2 text-white focus:outline-none focus:border-emerald-500/50 transition-colors font-minecraft text-[10px] tracking-widest uppercase"
                        />
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {searchResults.map((mod) => (
                            <div key={mod.slug} className="bg-black/20 border border-white/5 p-4 rounded-md flex gap-4 hover:bg-white/5 hover:border-white/10 transition-colors">
                                <img
                                    src={mod.icon_url || 'https://cdn.modrinth.com/assets/logo.svg'}
                                    alt={mod.title}
                                    className="w-16 h-16 rounded-md object-contain bg-black/40 p-2"
                                />
                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-bold text-lg text-emerald-400 font-minecraft">{mod.title}</h3>
                                        <button
                                            onClick={() => handleInstall(mod)}
                                            disabled={installing[mod.slug]}
                                            className="p-2 border border-transparent hover:border-white/10 rounded-md transition-colors group"
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
                            <div key={file.filename} className="bg-black/20 border border-white/5 p-3 rounded-md flex items-center justify-between group hover:bg-white/5 transition-colors hover:border-white/10">
                                <div className="flex items-center gap-4">
                                    <Package size={20} className="text-emerald-500" />
                                    <div>
                                        <div className="text-white font-mono text-sm">{file.filename}</div>
                                        <div className="text-xs text-gray-500">{file.size}</div>
                                    </div>
                                </div>
                                <button
                                    onClick={() => handleDelete(file.filename)}
                                    className="p-2 text-zinc-500 border border-transparent hover:border-red-500/30 hover:text-red-400 hover:bg-red-500/10 rounded-md opacity-0 group-hover:opacity-100 transition-all"
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

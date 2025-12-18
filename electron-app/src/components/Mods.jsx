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
    useEffect(() => {
        if (activeTab === 'browse' || activeTab === 'modpacks') {
            const timer = setTimeout(() => {
                performSearch(searchQuery);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery, activeTab, activeLoader, activeVersion]);

    const performSearch = async (query) => {
        setLoading(true);
        setError(null);
        try {
            const projectType = activeTab === 'modpacks' ? 'modpack' : 'mod';
            const results = await api.searchMods(query, activeLoader, activeVersion, projectType);
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
        // We typically install the latest compatible version
        // To do this right, we should query mod versions first.
        // For simplicity/MVP, we'll try to find the version ID from search result if available,
        // OR we might need a separate API call "getModVersions" in backend. 
        // 
        // CORRECT APPROACH: Modrinth search result doesn't give the file download URL directly.
        // We implemented 'get_mod_versions' in backend but didn't expose it yet directly for UI selection.
        // Ideally we pick the first compatible version.

        // Let's assume we want to open a "Versions" modal in a robust app.
        // For this MVP, let's auto-select the best version.
        // BUT wait, search result item has 'slug'. We need to call another endpoint.
        // Actually, let's just use the logic: "Install latest compatible".
        // I will implement a quick 'auto-install' helper on backend or just pick here. 
        // Oops, I didn't verify if search result has version_id. It usually has `project_id`.
        // I should have checked Modrinth API response structure!
        // 
        // Search Hit: { "slug": "...", "title": "...", "icon_url": "...", "project_id": "..." }
        // 
        // Plan: We need a way to install. 
        // I will update the install logic to:
        // 1. Fetch versions for this project (using backend API if exposed, or add one).
        // 2. Pick top one.
        // 3. Install it.
        // 
        // Since I haven't exposed `get_mod_versions` in `api_server` explicitly as a route,
        // I should probably add it or do a "smart install" endpoint.
        // Let's try to add `GET /mods/versions` to `api_server.py` quickly? 
        // OR client-side fetching? No, CORS using direct Modrinth API might be fine 
        // but backend is safer.
        // 
        // Pivot: I'll assume I can add `getModVersions` to `api.js` if I add the endpoint.
        // Wait, I missed adding `get_mod_versions` route in `api_server.py`.
        // I will add it in the next step. For now, I'll code this component to use it.

        try {
            setInstalling(prev => ({ ...prev, [mod.slug]: true }));

            const versions = await api.getModVersions(mod.slug, activeLoader, activeVersion);

            if (versions && versions.length > 0) {
                // Pick first
                const targetVersion = versions[0];
                await api.installMod(targetVersion.id);
                loadInstalledMods(); // Refresh installed
                loadInstalledMods(); // Refresh installed
            } else {
                dialog.alert(`No compatible version found for ${activeLoader} ${activeVersion}.`, "Version Error", "warning");
            }
        } catch (e) {
            dialog.alert("Install failed: " + e.message, "Error", "destructive");
            setError(e?.message || 'Install failed');
        } finally {
            setInstalling(prev => ({ ...prev, [mod.slug]: false }));
        }
    };

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
                            className="w-32 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white/80 focus:outline-none focus:border-primary/50"
                        />
                        <input
                            type="text"
                            placeholder={activeTab === 'modpacks' ? "Search modpacks..." : "Search mods..."}
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
                                            className="px-3 py-1.5 bg-white/5 hover:bg-primary hover:text-white text-gray-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                                        >
                                            {installing[mod.slug] ? <RefreshCw className="animate-spin" size={14} /> : <Download size={14} />}
                                            Install
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

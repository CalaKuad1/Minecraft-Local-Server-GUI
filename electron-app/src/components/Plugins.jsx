import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Trash2, Package, Search, Upload, HardDrive, RefreshCw, Download } from 'lucide-react';
import { useDialog } from './ui/DialogContext';

export default function Plugins({ status }) {
    const dialog = useDialog();
    const [activeTab, setActiveTab] = useState('browse');
    const [plugins, setPlugins] = useState([]);
    const [searchResults, setSearchResults] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [installing, setInstalling] = useState({});
    const [error, setError] = useState(null);

    // Filters
    const [sortBy, setSortBy] = useState('downloads');
    const [category, setCategory] = useState('all');

    const serverVersion = status?.minecraft_version || status?.version || '';
    const serverType = status?.type || status?.server_type || '';
    const isPaper = serverType.toLowerCase().includes('paper') || serverType.toLowerCase().includes('spigot') || serverType.toLowerCase().includes('bukkit');

    useEffect(() => {
        if (activeTab === 'installed') {
            loadPlugins();
        }
    }, [activeTab]);

    // Debounced search
    useEffect(() => {
        if (activeTab === 'browse') {
            const timer = setTimeout(() => {
                performSearch(searchQuery);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery, activeTab, sortBy, category]);

    const loadPlugins = async () => {
        setLoading(true);
        setError(null);
        try {
            const list = await api.getPlugins();
            setPlugins(list);
        } catch (e) {
            console.error(e);
            setError("Failed to load plugins.");
        } finally {
            setLoading(false);
        }
    };

    const performSearch = async (query) => {
        setLoading(true);
        setError(null);
        try {
            const results = await api.searchPlugins(query, serverVersion, sortBy, category);
            setSearchResults(results);
        } catch (err) {
            setError(err?.message || "Failed to search plugins.");
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleInstall = async (plugin) => {
        try {
            setInstalling(prev => ({ ...prev, [plugin.slug]: true }));

            // Fetch versions
            const versions = await api.getPluginVersions(plugin.slug, serverVersion);
            if (!versions || versions.length === 0) {
                throw new Error("No compatible versions found.");
            }

            const targetVersion = versions[0];
            await api.installPlugin(targetVersion.id);

            // Wait a bit then refresh installed list
            setTimeout(() => {
                loadPlugins();
                setInstalling(prev => ({ ...prev, [plugin.slug]: false }));
            }, 1500);

        } catch (err) {
            console.error(err);
            setError(err.message);
            setInstalling(prev => ({ ...prev, [plugin.slug]: false }));
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setUploading(true);
        try {
            await api.uploadPlugin(file);
            await loadPlugins();
            dialog.alert(`Successfully uploaded ${file.name}`, "Success");
        } catch (e) {
            console.error(e);
            dialog.alert("Failed to upload plugin: " + e.message, "Error", "destructive");
        } finally {
            setUploading(false);
        }
    };

    const handleDelete = async (filename) => {
        if (!await dialog.confirm(`Delete ${filename}?`, "Delete Plugin", "destructive")) return;
        try {
            await api.deletePlugin(filename);
            loadPlugins();
        } catch (e) {
            console.error(e);
            dialog.alert("Failed to delete plugin: " + e.message, "Error", "destructive");
        }
    };

    const filteredPlugins = plugins.filter(p => p.filename.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!isPaper) {
        return (
            <div className="h-full flex flex-col justify-center items-center text-center p-8 animate-in fade-in zoom-in duration-500">
                <div className="p-6 rounded-2xl bg-white/5 border border-white/10 max-w-md">
                    <h2 className="text-xl font-bold text-white mb-2">Paper/Spigot Required</h2>
                    <p className="text-gray-400 mb-4">
                        Plugins are only available for Paper, Spigot, or Bukkit servers.<br />
                        Your current server type is: <span className="text-primary font-mono">{serverType || 'Unknown'}</span>
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col animate-in fade-in zoom-in duration-500">
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
                    Browse Plugins
                </button>
                <button
                    onClick={() => { setActiveTab('installed'); loadPlugins(); }}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'installed' ? 'bg-primary text-white shadow-lg shadow-primary/25' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                >
                    Installed ({plugins.length})
                </button>
                <button
                    onClick={() => api.openServerFolder()}
                    className="px-4 py-2 rounded-lg font-medium bg-zinc-800 text-zinc-400 hover:text-white hover:bg-primary/20 transition-all flex items-center gap-2 ml-auto"
                    title="Open Plugins Folder"
                >
                    <HardDrive size={18} />
                    Folder
                </button>
            </div>

            {activeTab === 'browse' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex gap-2 mb-4">
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

                        <select
                            value={category}
                            onChange={(e) => setCategory(e.target.value)}
                            className="bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-white/80 focus:outline-none focus:border-primary/50 text-sm"
                        >
                            <option value="all">All Categories</option>
                            <option value="economy">Economy</option>
                            <option value="game-mechanics">Game Mechanics</option>
                            <option value="utility">Utility</option>
                            <option value="management">Management</option>
                            <option value="social">Social</option>
                        </select>

                        <input
                            type="text"
                            placeholder="Search plugins..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="flex-1 bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary/50 transition-colors"
                        />
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {loading && searchResults.length === 0 && (
                            <div className="text-center text-gray-500 mt-10">
                                <RefreshCw size={32} className="mx-auto mb-4 animate-spin opacity-50" />
                                <p>Searching...</p>
                            </div>
                        )}
                        {searchResults.map((plugin) => (
                            <div key={plugin.slug} className="bg-surface/40 border border-white/5 p-4 rounded-xl flex gap-4 hover:bg-surface/60 transition-colors">
                                <img
                                    src={plugin.icon_url || 'https://cdn.modrinth.com/assets/logo.svg'}
                                    alt={plugin.title}
                                    className="w-16 h-16 rounded-xl object-contain bg-black/20 p-2"
                                />
                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-bold text-lg text-white">{plugin.title}</h3>
                                        <button
                                            onClick={() => handleInstall(plugin)}
                                            disabled={installing[plugin.slug]}
                                            className="p-2 hover:bg-white/10 rounded-lg transition-colors group"
                                            title="Install Latest"
                                        >
                                            <Download className={`w-5 h-5 ${installing[plugin.slug] ? 'text-yellow-500 animate-pulse' : 'text-gray-400 group-hover:text-white'}`} />
                                        </button>
                                    </div>
                                    <p className="text-gray-400 text-sm line-clamp-2 mt-1">{plugin.description}</p>
                                    <div className="flex gap-2 mt-2">
                                        <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-gray-500">{plugin.author}</span>
                                        <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-gray-500 flex items-center gap-1"><Download size={10} /> {plugin.downloads}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                        {searchResults.length === 0 && !loading && (
                            <div className="text-center text-gray-500 mt-10">
                                <Package size={48} className="mx-auto mb-4 opacity-20" />
                                <p>Search for plugins on Modrinth</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {activeTab === 'installed' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    {/* Toolbar */}
                    <div className="flex gap-4 mb-6">
                        <div className="flex-1 relative">
                            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                            <input
                                type="text"
                                placeholder="Search installed plugins..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full bg-black/20 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-white focus:outline-none focus:border-primary/50 transition-colors"
                            />
                        </div>
                        <label className={`bg-primary hover:bg-primary-hover text-white px-6 py-2 rounded-xl flex items-center gap-2 font-medium transition-all shadow-lg shadow-primary/25 cursor-pointer ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
                            <Upload size={18} />
                            <span>{uploading ? 'Uploading...' : 'Upload'}</span>
                            <input type="file" className="hidden" accept=".jar" onChange={handleUpload} disabled={uploading} />
                        </label>
                        <button
                            onClick={loadPlugins}
                            className="p-3 bg-white/5 hover:bg-white/10 rounded-xl text-gray-400 hover:text-white transition-colors"
                            title="Refresh List"
                        >
                            <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>

                    {/* List */}
                    <div className="flex-1 overflow-y-auto pr-2 space-y-2 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {filteredPlugins.length === 0 ? (
                            <div className="text-center text-gray-500 mt-20">
                                <Package size={48} className="mx-auto mb-4 opacity-20" />
                                <p>{searchQuery ? 'No plugins found matching search.' : 'No plugins installed.'}</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {filteredPlugins.map((plugin) => (
                                    <div key={plugin.filename} className="bg-surface/40 border border-white/5 p-4 rounded-xl flex items-center justify-between group hover:bg-surface/60 transition-colors">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center text-green-400">
                                                <Package size={20} />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-white font-medium truncate max-w-[200px] md:max-w-[300px]" title={plugin.filename}>
                                                    {plugin.filename}
                                                </div>
                                                <div className="text-xs text-gray-500">{plugin.size}</div>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleDelete(plugin.filename)}
                                            className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                                            title="Delete"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

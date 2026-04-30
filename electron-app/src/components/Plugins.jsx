import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api';
import { Trash2, Package, Search, Upload, HardDrive, RefreshCw, Download } from './ui/PixelIcons';
import { useDialog } from './ui/DialogContext';
import { Select } from './ui/Select';

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
                <div className="p-6 rounded-md bg-white/5 border border-white/10 max-w-md">
                    <h2 className="text-xl font-minecraft text-emerald-400 uppercase tracking-widest mb-2">Paper/Spigot Required</h2>
                    <p className="text-zinc-400 mb-4 text-sm">
                        Plugins are only available for Paper, Spigot, or Bukkit servers.<br />
                        Your current server type is: <span className="text-emerald-400 font-mono text-xs uppercase tracking-wider">{serverType || 'Unknown'}</span>
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col animate-in fade-in zoom-in duration-500">
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
                            <motion.div layoutId="pluginsTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                        )}
                        <span className={`relative z-10 ${activeTab === 'browse' ? 'font-bold' : ''}`}>Browse</span>
                    </button>
                    <button
                        onClick={() => { setActiveTab('installed'); loadPlugins(); }}
                        className={`px-6 py-2.5 rounded-sm font-minecraft tracking-wider text-sm transition-colors relative flex items-center justify-center gap-2 z-10 uppercase ${activeTab === 'installed' ? 'text-white' : 'text-zinc-500 hover:text-white'}`}
                    >
                        {activeTab === 'installed' && (
                            <motion.div layoutId="pluginsTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                        )}
                        <span className={`relative z-10 ${activeTab === 'installed' ? 'font-bold' : ''}`}>Installed ({plugins.length})</span>
                    </button>
                </div>
                <button
                    onClick={() => api.openServerFolder()}
                    className="px-4 py-2 border border-transparent hover:border-white/10 rounded-md font-minecraft tracking-wider text-xs uppercase bg-transparent text-zinc-500 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2 ml-auto"
                    title="Open Plugins Folder"
                >
                    <HardDrive size={18} />
                    Folder
                </button>
            </div>

            {activeTab === 'browse' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex gap-2 mb-4 h-10">
                        <div className="w-40">
                            <Select
                                value={sortBy}
                                onChange={setSortBy}
                                options={[
                                    { value: 'relevance', label: 'Relevance' },
                                    { value: 'downloads', label: 'Downloads' },
                                    { value: 'newest', label: 'Newest' },
                                    { value: 'updated', label: 'Updated' }
                                ]}
                                className="h-full bg-black/40 border-white/5 rounded-sm text-[11px] font-minecraft tracking-widest"
                            />
                        </div>

                        <div className="w-48">
                            <Select
                                value={category}
                                onChange={setCategory}
                                options={[
                                    { value: 'all', label: 'All Categories' },
                                    { value: 'economy', label: 'Economy' },
                                    { value: 'game-mechanics', label: 'Game Mechanics' },
                                    { value: 'utility', label: 'Utility' },
                                    { value: 'management', label: 'Management' },
                                    { value: 'social', label: 'Social' }
                                ]}
                                className="h-full bg-black/40 border-white/5 rounded-sm text-[11px] font-minecraft tracking-widest"
                            />
                        </div>

                        <input
                            type="text"
                            placeholder="Search plugins..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="flex-1 bg-black/40 border border-white/10 rounded-sm px-4 py-2 text-white focus:outline-none focus:border-emerald-500/50 transition-colors font-minecraft text-xs tracking-widest uppercase"
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
                            <div key={plugin.slug} className="bg-black/20 border border-white/5 p-4 rounded-md flex gap-4 hover:bg-white/5 hover:border-white/10 transition-colors">
                                <img
                                    src={plugin.icon_url || 'https://cdn.modrinth.com/assets/logo.svg'}
                                    alt={plugin.title}
                                    className="w-16 h-16 rounded-md object-contain bg-black/40 p-2"
                                />
                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-bold text-lg text-emerald-400 font-minecraft">{plugin.title}</h3>
                                        <button
                                            onClick={() => handleInstall(plugin)}
                                            disabled={installing[plugin.slug]}
                                            className="p-2 border border-transparent hover:border-white/10 rounded-md transition-colors group"
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
                                className="w-full bg-black/40 border border-white/10 rounded-md pl-10 pr-4 py-3 text-white focus:outline-none focus:border-emerald-500/50 transition-colors font-mono"
                            />
                        </div>
                        <label className={`bg-transparent hover:bg-white/5 border border-white/10 text-emerald-400 font-minecraft tracking-wider uppercase text-xs px-6 py-2 rounded-md flex items-center justify-center gap-2 transition-all cursor-pointer ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
                            <Upload size={16} />
                            <span>{uploading ? 'Uploading...' : 'Upload'}</span>
                            <input type="file" className="hidden" accept=".jar" onChange={handleUpload} disabled={uploading} />
                        </label>
                        <button
                            onClick={loadPlugins}
                            className="p-3 bg-transparent hover:bg-white/5 border border-white/10 rounded-md text-zinc-500 hover:text-white transition-colors"
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
                                    <div key={plugin.filename} className="bg-black/20 border border-white/5 p-4 rounded-md flex items-center justify-between group hover:bg-white/5 transition-colors hover:border-white/10">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-md bg-white/5 border border-white/5 flex items-center justify-center text-emerald-500 drop-shadow-md">
                                                <Package size={20} />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-white font-mono text-sm truncate max-w-[200px] md:max-w-[300px]" title={plugin.filename}>
                                                    {plugin.filename}
                                                </div>
                                                <div className="text-xs text-gray-500">{plugin.size}</div>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleDelete(plugin.filename)}
                                            className="p-2 text-zinc-500 border border-transparent hover:border-red-500/30 hover:text-red-400 hover:bg-red-500/10 rounded-md opacity-0 group-hover:opacity-100 transition-all"
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

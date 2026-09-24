import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api';
import { Trash2, Package, Search, Upload, HardDrive, RefreshCw, Download, Check } from './ui/PixelIcons';
import { useDialog } from './ui/DialogContext';
import { Select } from './ui/Select';
import { useTranslation } from '../contexts/LanguageContext';

export default function Plugins({ status }) {
    const { t } = useTranslation();
    const dialog = useDialog();
    const [activeTab, setActiveTab] = useState('browse');
    const [plugins, setPlugins] = useState([]);
    const [searchResults, setSearchResults] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [installing, setInstalling] = useState({});
    const [justInstalled, setJustInstalled] = useState({});
    const [error, setError] = useState(null);

    const [sortBy, setSortBy] = useState('downloads');
    const [category, setCategory] = useState('all');

    const serverVersion = status?.minecraft_version || status?.version || '';
    const serverType = status?.type || status?.server_type || '';
    const isPaper = serverType.toLowerCase().includes('paper') || serverType.toLowerCase().includes('spigot') || serverType.toLowerCase().includes('bukkit');

    useEffect(() => {
        if (activeTab === 'installed') loadPlugins();
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'browse') {
            const timer = setTimeout(() => performSearch(searchQuery), 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery, activeTab, sortBy, category]);

    const loadPlugins = async () => {
        setLoading(true);
        setError(null);
        try {
            setPlugins(await api.getPlugins());
        } catch (e) {
            console.error(e);
            setError(t('common.error'));
        } finally {
            setLoading(false);
        }
    };

    const performSearch = async (query) => {
        setLoading(true);
        setError(null);
        try {
            setSearchResults(await api.searchPlugins(query, serverVersion, sortBy, category));
        } catch (err) {
            setError(err?.message || t('common.error'));
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleInstall = async (plugin) => {
        try {
            setInstalling(prev => ({ ...prev, [plugin.slug]: true }));
            const versions = await api.getPluginVersions(plugin.slug, serverVersion);
            if (!versions || versions.length === 0) throw new Error(t('mods.no_versions'));
            await api.installPlugin(versions[0].id);
            setTimeout(() => {
                loadPlugins();
                setInstalling(prev => ({ ...prev, [plugin.slug]: false }));
                setJustInstalled(prev => ({ ...prev, [plugin.slug]: true }));
                setTimeout(() => setJustInstalled(prev => (plugin.slug in prev ? { ...prev, [plugin.slug]: false } : prev)), 2000);
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
            dialog.alert(t('plugins.upload_success').replace('{name}', file.name), t('common.confirm'));
        } catch (e) {
            console.error(e);
            dialog.alert(`${t('plugins.upload_error')}: ${e.message}`, t('common.error'), "destructive");
        } finally {
            setUploading(false);
        }
    };

    const handleDelete = async (filename) => {
        if (!await dialog.confirm(t('mods.delete_confirm').replace('{name}', filename), t('plugins.delete_title'), "destructive")) return;
        try {
            await api.deletePlugin(filename);
            loadPlugins();
        } catch (e) {
            console.error(e);
            dialog.alert(`${t('plugins.delete_error')}: ${e.message}`, t('common.error'), "destructive");
        }
    };

    const filteredPlugins = plugins.filter(p => p.filename.toLowerCase().includes(searchQuery.toLowerCase()));
    const sorts = ['relevance', 'downloads', 'newest', 'updated'].map(v => ({ value: v, label: t(`plugins.sort.${v}`) }));
    const cats = ['all', 'economy', 'game-mechanics', 'utility', 'management', 'social'].map(v => ({ value: v, label: t(`plugins.categories.${v}`) }));

    if (!isPaper) {
        return (
            <div className="h-full flex flex-col justify-center items-center text-center p-8 animate-in fade-in zoom-in duration-500">
                <div className="p-6 rounded-sm bg-[#18181b]/60 border border-white/10 max-w-md">
                    <h2 className="text-xl font-minecraft text-emerald-400 uppercase tracking-widest mb-2">{t('plugins.unsupported_title')}</h2>
                    <p className="text-zinc-400 mb-4 text-sm">
                        {t('plugins.unsupported_desc')}<br />
                        {t('plugins.current_type').replace('{type}', serverType || 'Unknown')}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col animate-in fade-in zoom-in duration-500 w-full">
            {error && <div className="mb-4 p-3 rounded-sm border border-red-500/20 bg-red-500/10 text-red-200 text-sm">{error}</div>}

            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center bg-[#0a0a0a] border border-white/5 p-1 rounded-sm max-w-fit shadow-inner">
                    {[
                        { id: 'browse', label: t('plugins.browse') },
                        { id: 'installed', label: t('plugins.installed_tab').replace('{count}', plugins.length) }
                    ].map(tabItem => (
                        <button
                            key={tabItem.id}
                            onClick={() => { setActiveTab(tabItem.id); if (tabItem.id === 'installed') loadPlugins(); }}
                            className={`px-6 py-2.5 rounded-sm font-minecraft tracking-wider text-sm transition-colors relative flex items-center justify-center gap-2 z-10 uppercase ${activeTab === tabItem.id ? 'text-white' : 'text-zinc-500 hover:text-white'}`}
                        >
                            {activeTab === tabItem.id && (
                                <motion.div layoutId="pluginsTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                            )}
                            <span className={`relative z-10 ${activeTab === tabItem.id ? 'font-bold' : ''}`}>{tabItem.label}</span>
                        </button>
                    ))}
                </div>
                <button
                    onClick={() => api.openServerFolder()}
                    className="px-4 py-2 border border-transparent hover:border-white/10 rounded-sm font-minecraft tracking-wider text-xs uppercase bg-transparent text-zinc-500 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2 ml-auto"
                >
                    <HardDrive size={18} /> {t('common.folder')}
                </button>
            </div>

            {activeTab === 'browse' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex flex-wrap gap-2 mb-4">
                        <div className="w-40 h-10"><Select value={sortBy} onChange={setSortBy} options={sorts} className="h-full bg-black/40 border-white/5 rounded-sm text-[11px] font-minecraft tracking-widest" /></div>
                        <div className="w-48 h-10"><Select value={category} onChange={setCategory} options={cats} className="h-full bg-black/40 border-white/5 rounded-sm text-[11px] font-minecraft tracking-widest" /></div>
                        <input type="text" placeholder={t('plugins.search')} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                            className="flex-1 min-w-[160px] h-10 bg-black/40 border border-white/10 rounded-sm px-4 text-white focus:outline-none focus:border-emerald-500/50 transition-colors font-minecraft text-xs tracking-widest uppercase" />
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {loading && searchResults.length === 0 && (
                            <div className="text-center text-zinc-500 mt-10">
                                <RefreshCw size={32} className="mx-auto mb-4 animate-spin opacity-50" />
                                <p>{t('common.loading')}</p>
                            </div>
                        )}
                        {searchResults.map((plugin) => (
                            <div key={plugin.slug} className="bg-black/20 border border-white/5 p-4 rounded-sm flex gap-4 hover:bg-white/5 hover:border-white/10 transition-colors">
                                <img src={plugin.icon_url || 'https://cdn.modrinth.com/assets/logo.svg'} alt={plugin.title} className="w-16 h-16 rounded-sm object-contain bg-black/40 p-2" />
                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-bold text-lg text-emerald-400 font-minecraft">{plugin.title}</h3>
                                        <button onClick={() => handleInstall(plugin)} disabled={installing[plugin.slug]} className="p-2 border border-transparent hover:border-white/10 rounded-sm transition-colors group" title={t('plugins.install_latest')}>
                                            {justInstalled[plugin.slug] ? (
                                                <Check className="w-5 h-5 text-emerald-400" />
                                            ) : (
                                                <Download className={`w-5 h-5 ${installing[plugin.slug] ? 'text-yellow-500 animate-pulse' : 'text-zinc-400 group-hover:text-white'}`} />
                                            )}
                                        </button>
                                    </div>
                                    <p className="text-zinc-400 text-sm line-clamp-2 mt-1">{plugin.description}</p>
                                    <div className="flex gap-2 mt-2">
                                        <span className="text-xs px-2 py-0.5 rounded-sm bg-white/5 text-zinc-500">{plugin.author}</span>
                                        <span className="text-xs px-2 py-0.5 rounded-sm bg-white/5 text-zinc-500 flex items-center gap-1"><Download size={10} /> {plugin.downloads}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                        {searchResults.length === 0 && !loading && (
                            <div className="text-center text-zinc-500 mt-10">
                                <Package size={48} className="mx-auto mb-4 opacity-20" />
                                <p>{t('plugins.search_hint')}</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {activeTab === 'installed' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex gap-4 mb-6">
                        <div className="flex-1 relative">
                            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                            <input
                                type="text"
                                placeholder={t('plugins.search_installed')}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full bg-black/40 border border-white/10 rounded-sm pl-10 pr-4 py-3 text-white focus:outline-none focus:border-emerald-500/50 transition-colors font-mono"
                            />
                        </div>
                        <label className={`bg-transparent hover:bg-white/5 border border-white/10 text-emerald-400 font-minecraft tracking-wider uppercase text-xs px-6 py-2 rounded-sm flex items-center justify-center gap-2 transition-all cursor-pointer ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
                            <Upload size={16} />
                            <span>{uploading ? t('common.uploading') : t('common.upload')}</span>
                            <input type="file" className="hidden" accept=".jar" onChange={handleUpload} disabled={uploading} />
                        </label>
                        <button onClick={loadPlugins} className="p-3 bg-transparent hover:bg-white/5 border border-white/10 rounded-sm text-zinc-500 hover:text-white transition-colors" title={t('common.refresh')}>
                            <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 space-y-2 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {filteredPlugins.length === 0 ? (
                            <div className="text-center text-zinc-500 mt-20">
                                <Package size={48} className="mx-auto mb-4 opacity-20" />
                                <p>{searchQuery ? t('plugins.no_matching') : t('plugins.no_installed')}</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {filteredPlugins.map((plugin) => (
                                    <div key={plugin.filename} className="bg-black/20 border border-white/5 p-4 rounded-sm flex items-center justify-between group hover:bg-white/5 transition-colors hover:border-white/10">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-sm bg-white/5 border border-white/5 flex items-center justify-center text-emerald-500">
                                                <Package size={20} />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-white font-mono text-sm truncate max-w-[200px] md:max-w-[300px]" title={plugin.filename}>{plugin.filename}</div>
                                                <div className="text-xs text-zinc-500">{plugin.size}</div>
                                            </div>
                                        </div>
                                        <button onClick={() => handleDelete(plugin.filename)} className="p-2 text-zinc-500 border border-transparent hover:border-red-500/30 hover:text-red-400 hover:bg-red-500/10 rounded-sm opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-all" title={t('common.delete')}>
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

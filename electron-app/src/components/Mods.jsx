import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api';
import { Search, Download, Trash2, Package, RefreshCw, ExternalLink, HardDrive, Plus, Check } from './ui/PixelIcons';
import { useDialog } from './ui/DialogContext';
import { Select } from './ui/Select';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useTranslation } from '../contexts/LanguageContext';
import { isSlugInstalled } from '../utils/installedMatch';
import { resolveInstalledSlugs } from '../utils/installedResolve';

export default function Mods({ status, onOpenWizard }) {
    const { t } = useTranslation();
    const dialog = useDialog();
    const [activeTab, setActiveTab] = useState('browse'); // 'browse' | 'modpacks' | 'installed'
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [installedMods, setInstalledMods] = useState([]);
    const [loading, setLoading] = useState(false);
    const [activeLoader, setActiveLoader] = useState('fabric');
    const [activeVersion, setActiveVersion] = useState('');
    const [installing, setInstalling] = useState({});
    const [justInstalled, setJustInstalled] = useState({});
    const [downloadProgress, setDownloadProgress] = useState({});
    const [resolvedInstalled, setResolvedInstalled] = useState(new Set());
    const lastInstalledSlug = useRef(null);
    const [error, setError] = useState(null);

    const [sortBy, setSortBy] = useState('downloads');
    const [category, setCategory] = useState('all');

    useEffect(() => { loadInstalledMods(); }, []);

    const loadInstalledMods = async () => {
        try {
            setInstalledMods(await api.getInstalledMods());
        } catch (e) {
            console.error("Failed to load installed mods:", e);
            setError(e?.message || t('mods.load_error'));
        }
    };

    const serverType = status?.type || status?.server_type || '';
    const serverVersion = status?.version || status?.minecraft_version || '';
    const lowerType = (serverType || '').toString().toLowerCase();
    const isNonModdedServer = lowerType.includes('vanilla') || lowerType.includes('paper');

    useEffect(() => {
        if (serverType) setActiveLoader(serverType.toLowerCase().includes('forge') ? 'forge' : 'fabric');
        if (serverVersion) setActiveVersion(serverVersion);
    }, [serverType, serverVersion]);

    useEffect(() => {
        if (activeTab === 'browse' || activeTab === 'modpacks') {
            const timer = setTimeout(() => performSearch(searchQuery), 500);
            return () => clearTimeout(timer);
        }
    }, [searchQuery, activeTab, activeLoader, activeVersion, sortBy, category]);

    const performSearch = async (query) => {
        setLoading(true);
        setError(null);
        try {
            const projectType = activeTab === 'modpacks' ? 'modpack' : 'mod';
            setSearchResults(await api.searchMods(query, activeLoader, activeVersion, projectType, sortBy, category));
        } catch (err) {
            setError(err?.message || t('mods.search_error'));
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleInstall = async (mod) => {
        try {
            setInstalling(prev => ({ ...prev, [mod.slug]: true }));
            const versions = await api.getModVersions(mod.slug, activeLoader, activeVersion);
            if (!versions || versions.length === 0) throw new Error(t('mods.no_versions'));
            const targetVersion = versions[0];

            const reqDeps = targetVersion.dependencies?.filter(d => d.dependency_type === 'required') || [];
            if (reqDeps.length > 0) {
                const proceed = await dialog.confirm(
                    t('mods.deps_confirm').replace('{name}', mod.title || mod.slug).replace('{count}', reqDeps.length),
                    t('mods.deps_title'),
                    { variant: "warning", confirmLabel: t('mods.install_anyway'), cancelLabel: t('common.cancel') }
                );
                if (!proceed) { setInstalling(prev => ({ ...prev, [mod.slug]: false })); return; }
            }
            // Set before installMod's background thread can emit progress events.
            lastInstalledSlug.current = mod.slug;
            await api.installMod(targetVersion.id, mod.slug);
        } catch (err) {
            console.error(err);
            setError(err.message);
            setInstalling(prev => ({ ...prev, [mod.slug]: false }));
        }
    };

    const { subscribe } = useWebSocket();
    useEffect(() => {
        return subscribe('mods', (item) => {
            if (item.type === 'progress') {
                // Only trust progress tagged with the project slug; unrelated
                // server-setup progress events must not paint a mod card.
                if (item.slug && typeof item.value === 'number') {
                    setDownloadProgress(prev => ({ ...prev, [item.slug]: { value: item.value, message: item.message } }));
                }
                return;
            }
            if (item.type === 'mod_install_complete') {
                const slug = item.slug || lastInstalledSlug.current;
                lastInstalledSlug.current = null;
                if (slug) {
                    setDownloadProgress(prev => { const next = { ...prev }; delete next[slug]; return next; });
                    setInstalling(prev => ({ ...prev, [slug]: false }));
                }
                loadInstalledMods();
                if (item.success !== false && slug) {
                    setJustInstalled(prev => ({ ...prev, [slug]: true }));
                    setTimeout(() => setJustInstalled(prev => (slug in prev ? { ...prev, [slug]: false } : prev)), 2000);
                } else if (item.success === false) {
                    setError(t('mods.install_error'));
                }
            }
        });
    }, [subscribe, t]);

    // Exact-match resolution for projects whose jar filenames differ from their
    // slug (e.g. simple-voice-chat -> voicechat-fabric-*.jar). All published
    // filenames are checked (unfiltered) so past installs are still matched.
    useEffect(() => {
        if ((activeTab !== 'browse' && activeTab !== 'modpacks') || searchResults.length === 0) {
            setResolvedInstalled(new Set());
            return;
        }
        let cancelled = false;
        resolveInstalledSlugs({
            slugs: searchResults.map(r => r.slug),
            installed: installedMods,
        }).then(matched => { if (!cancelled) setResolvedInstalled(matched); });
        return () => { cancelled = true; };
    }, [activeTab, searchResults, installedMods]);

    const handleDelete = async (filename) => {
        if (!await dialog.confirm(t('mods.delete_confirm').replace('{name}', filename), t('mods.delete_title'), "destructive")) return;
        try {
            await api.deleteMod(filename);
            loadInstalledMods();
        } catch (e) {
            console.error(e);
            dialog.alert(e.message, t('common.error'), "destructive");
        }
    };

    const loaders = ['any', 'fabric', 'forge', 'neoforge', 'quilt'].map(v => ({ value: v, label: t(`mods.loaders.${v}`) }));
    const sorts = ['relevance', 'downloads', 'newest', 'updated'].map(v => ({ value: v, label: t(`mods.sort.${v}`) }));
    const cats = ['all', 'technology', 'magic', 'adventure', 'decoration', 'optimization', 'library'].map(v => ({ value: v, label: t(`mods.categories.${v}`) }));

    return (
        <div className="h-full flex flex-col animate-in fade-in zoom-in duration-500 w-full">
            {isNonModdedServer && (
                <div className="mb-4 p-4 rounded-sm border border-yellow-500/20 bg-yellow-500/10 text-yellow-100/90 text-sm">
                    <div className="font-bold text-yellow-200 mb-1 font-minecraft tracking-wider uppercase">{t('mods.unsupported_title')}</div>
                    <div className="text-yellow-100/80">
                        {t('mods.unsupported_desc').replace('{type}', serverType || 'Vanilla/Paper')}
                    </div>
                    <div className="mt-3">
                        <button
                            onClick={() => onOpenWizard && onOpenWizard()}
                            className="px-4 py-2 rounded-sm font-minecraft tracking-wider text-xs uppercase bg-white/10 hover:bg-white/15 border border-white/10 transition-colors"
                        >
                            {t('mods.open_wizard')}
                        </button>
                    </div>
                </div>
            )}
            {error && (
                <div className="mb-4 p-3 rounded-sm border border-red-500/20 bg-red-500/10 text-red-200 text-sm">{error}</div>
            )}

            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center bg-[#0a0a0a] border border-white/5 p-1 rounded-sm max-w-fit shadow-inner">
                    {[
                        { id: 'browse', label: t('mods.browse') },
                        { id: 'modpacks', label: t('mods.modpacks') },
                        { id: 'installed', label: t('mods.installed_tab').replace('{count}', installedMods.length) }
                    ].map(tabItem => (
                        <button
                            key={tabItem.id}
                            onClick={() => { setActiveTab(tabItem.id); if (tabItem.id === 'installed') loadInstalledMods(); }}
                            className={`px-6 py-2.5 rounded-sm font-minecraft tracking-wider text-sm transition-colors relative flex items-center justify-center gap-2 z-10 uppercase ${activeTab === tabItem.id ? 'text-white' : 'text-zinc-500 hover:text-white'}`}
                        >
                            {activeTab === tabItem.id && (
                                <motion.div layoutId="modsTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                            )}
                            <span className={`relative z-10 ${activeTab === tabItem.id ? 'font-bold' : ''}`}>{tabItem.label}</span>
                        </button>
                    ))}
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => api.openModsFolder()}
                        className="px-4 py-2 border border-transparent hover:border-white/10 rounded-sm font-minecraft tracking-wider text-xs uppercase bg-transparent text-zinc-500 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2"
                    >
                        <HardDrive size={18} /> {t('common.folder')}
                    </button>
                    <label className="px-4 py-2 border border-transparent hover:border-white/10 rounded-sm font-minecraft tracking-wider text-xs uppercase bg-transparent text-zinc-500 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2 cursor-pointer">
                        <Plus size={18} /> {t('common.import')}
                        <input type="file" accept=".jar" className="hidden" onChange={async (e) => {
                            const file = e.target.files[0];
                            if (!file) return;
                            try { await api.importMod(file); loadInstalledMods(); e.target.value = ''; } catch (err) { console.error('Import failed', err); }
                        }} />
                    </label>
                </div>
            </div>

            {(activeTab === 'browse' || activeTab === 'modpacks') && (
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex flex-wrap gap-2 mb-4">
                        <div className="w-36 h-10"><Select value={activeLoader} onChange={setActiveLoader} options={loaders} className="h-full bg-black/40 border-white/5 rounded-sm text-[10px] font-minecraft tracking-widest" /></div>
                        <input type="text" placeholder={t('mods.version')} value={activeVersion} onChange={(e) => setActiveVersion(e.target.value)}
                            className="w-24 h-10 bg-black/40 border border-white/5 rounded-sm px-3 text-white focus:outline-none focus:border-emerald-500/50 text-[10px] font-minecraft tracking-widest uppercase" />
                        <div className="w-36 h-10"><Select value={sortBy} onChange={setSortBy} options={sorts} className="h-full bg-black/40 border-white/5 rounded-sm text-[10px] font-minecraft tracking-widest" /></div>
                        <div className="w-40 h-10"><Select value={category} onChange={setCategory} options={cats} className="h-full bg-black/40 border-white/5 rounded-sm text-[10px] font-minecraft tracking-widest" /></div>
                        <input type="text" placeholder={t('mods.search')} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                            className="flex-1 min-w-[140px] h-10 bg-black/40 border border-white/10 rounded-sm px-4 text-white focus:outline-none focus:border-emerald-500/50 transition-colors font-minecraft text-[10px] tracking-widest uppercase" />
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {searchResults.map((mod) => (
                            <div key={mod.slug} className="bg-black/20 border border-white/5 p-4 rounded-sm flex gap-4 hover:bg-white/5 hover:border-white/10 transition-colors">
                                <img src={mod.icon_url || 'https://cdn.modrinth.com/assets/logo.svg'} alt={mod.title} className="w-16 h-16 rounded-sm object-contain bg-black/40 p-2" />
                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-bold text-lg text-emerald-400 font-minecraft">{mod.title}</h3>
                                        {isSlugInstalled(mod.slug, installedMods) || resolvedInstalled.has(mod.slug) ? (
                                            <span className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-minecraft tracking-widest uppercase">
                                                <Check size={12} /> {t('common.installed')}
                                            </span>
                                        ) : (
                                            <button onClick={() => handleInstall(mod)} disabled={installing[mod.slug]} className="p-2 border border-transparent hover:border-white/10 rounded-sm transition-colors group" title={t('mods.install_latest')}>
                                                {justInstalled[mod.slug] ? (
                                                    <Check className="w-5 h-5 text-emerald-400" />
                                                ) : (
                                                    <Download className={`w-5 h-5 ${installing[mod.slug] ? 'text-yellow-500 animate-pulse' : 'text-zinc-400 group-hover:text-white'}`} />
                                                )}
                                            </button>
                                        )}
                                    </div>
                                    <p className="text-zinc-400 text-sm line-clamp-2 mt-1">{mod.description}</p>
                                    <div className="flex gap-2 mt-2">
                                        <span className="text-xs px-2 py-0.5 rounded-sm bg-white/5 text-zinc-500">{mod.author}</span>
                                        <span className="text-xs px-2 py-0.5 rounded-sm bg-white/5 text-zinc-500 flex items-center gap-1"><Download size={10} /> {mod.downloads}</span>
                                    </div>
                                    {installing[mod.slug] && (
                                        <div className="mt-3">
                                            <div className="h-1.5 rounded-sm bg-white/5 overflow-hidden">
                                                <div className="h-full bg-emerald-500 transition-all duration-300" style={{ width: `${Math.min(100, downloadProgress[mod.slug]?.value ?? 0)}%` }} />
                                            </div>
                                            <div className="flex justify-between items-center mt-1">
                                                <span className="text-[10px] font-minecraft tracking-widest uppercase text-zinc-500">{t('common.downloading')}</span>
                                                <span className="text-[10px] font-minecraft tracking-widest text-emerald-400">{Math.round(downloadProgress[mod.slug]?.value ?? 0)}%</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        {searchResults.length === 0 && !loading && (
                            <div className="text-center text-zinc-500 mt-10">
                                <Package size={48} className="mx-auto mb-4 opacity-20" />
                                <p>{t('mods.search_hint')}</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {activeTab === 'installed' && (
                <div className="flex-1 overflow-y-auto pr-2 space-y-2 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                    {installedMods.length === 0 ? (
                        <div className="text-center text-zinc-500 mt-10">
                            <HardDrive size={48} className="mx-auto mb-4 opacity-20" />
                            <p>{t('mods.installed_empty')}</p>
                        </div>
                    ) : (
                        installedMods.map((file) => (
                            <div key={file.filename} className="bg-black/20 border border-white/5 p-3 rounded-sm flex items-center justify-between group hover:bg-white/5 transition-colors hover:border-white/10">
                                <div className="flex items-center gap-4">
                                    <Package size={20} className="text-emerald-500" />
                                    <div>
                                        <div className="text-white font-mono text-sm">{file.filename}</div>
                                        <div className="text-xs text-zinc-500">{file.size}</div>
                                    </div>
                                </div>
                                <button onClick={() => handleDelete(file.filename)} className="p-2 text-zinc-500 border border-transparent hover:border-red-500/30 hover:text-red-400 hover:bg-red-500/10 rounded-sm opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-all">
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

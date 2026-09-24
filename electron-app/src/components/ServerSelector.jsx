import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../api';
import { Plus, Server, Trash2, Play, Settings, Activity, Clock, FolderOpen, Search, Terminal, LayoutDashboard } from './ui/PixelIcons';
import fabricLogo from '../assets/engines/fabric.png';
import forgeLogo from '../assets/engines/forge.png';
import neoforgeLogo from '../assets/engines/neoforge.png';
import paperLogo from '../assets/engines/Paper_JE2_BE2.webp';
import spigotLogo from '../assets/engines/spigot.png';
import vanillaLogo from '../assets/engines/vanilla.webp';
import { useDialog } from './ui/DialogContext';
import { motion } from 'framer-motion';
import AppSettings from './AppSettings';
import { useTranslation } from '../contexts/LanguageContext';

function engineInfo(type) {
    const t = (type || '').toLowerCase();
    if (t.includes('paper')) return { src: paperLogo, color: 'text-sky-400', border: 'border-sky-500/30', bg: 'bg-sky-500/10' };
    if (t.includes('neoforge')) return { src: neoforgeLogo, color: 'text-orange-400', border: 'border-orange-500/30', bg: 'bg-orange-500/10' };
    if (t.includes('forge')) return { src: forgeLogo, color: 'text-red-400', border: 'border-red-500/30', bg: 'bg-red-500/10' };
    if (t.includes('fabric')) return { src: fabricLogo, color: 'text-amber-200', border: 'border-amber-500/30', bg: 'bg-amber-500/10' };
    if (t.includes('spigot')) return { src: spigotLogo, color: 'text-yellow-400', border: 'border-yellow-500/30', bg: 'bg-yellow-500/10' };
    if (t.includes('vanilla')) return { src: vanillaLogo, color: 'text-emerald-400', border: 'border-emerald-500/30', bg: 'bg-emerald-500/10' };
    return { src: null, color: 'text-zinc-400', border: 'border-white/10', bg: 'bg-white/5' };
}

function EngineIcon({ type, size = 16, className = '' }) {
    const { src } = engineInfo(type);
    if (src) {
        return (
            <div className={`flex items-center justify-center overflow-hidden ${className}`} style={{ width: size, height: size }}>
                <img src={src} className="w-full h-full object-contain brightness-0 invert" alt={type} />
            </div>
        );
    }
    return <Server size={size} className={className} />;
}

function StatusPill({ status }) {
    const { t } = useTranslation();
    const isOnline = status === 'online';
    const isBusy = status && status !== 'offline' && !isOnline;
    return (
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[9px] font-minecraft uppercase tracking-wider
            ${isOnline ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : isBusy ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                    : 'bg-white/5 border-white/10 text-zinc-500'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-400' : isBusy ? 'bg-yellow-400 animate-pulse' : 'bg-zinc-600'}`} />
            {t(`status.${status || 'offline'}`)}
        </span>
    );
}

function formatRelative(iso) {
    if (!iso) return null;
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

// Poll the backend until the given server reports offline (or nothing is
// running anymore). Returns false if it didn't settle within the timeout.
const waitForServerOffline = async (serverId, timeoutMs = 10000) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
        try {
            const list = await api.getServers();
            const target = list.find((s) => s.id === serverId);
            if (!target || !target.status || target.status === 'offline') return true;
            if (!list.some((s) => s.status && s.status !== 'offline')) return true;
        } catch (e) { /* transient backend hiccup — keep polling */ }
        await new Promise((r) => setTimeout(r, 1500));
    }
    return false;
};

export default function ServerSelector({ onSelect, onAdd }) {
    const { t } = useTranslation();
    const [servers, setServers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [booting, setBooting] = useState(null);
    const [viewMode, setViewMode] = useState('grid');
    const dialog = useDialog();

    useEffect(() => {
        let cancelled = false;
        let timer;
        let attempts = 0;

        const load = async () => {
            try {
                const list = await api.getServers();
                if (cancelled) return;
                setServers(list);
                setLoadError(null);
                attempts = 0;
                // Backend is up: relax to a slow keep-alive poll.
                timer = setTimeout(load, 5000);
            } catch (err) {
                if (cancelled) return;
                console.error("Failed to load servers", err);
                attempts += 1;
                // Don't slap the user with an error while the backend is still
                // starting (Electron boots it alongside the UI) — keep retrying
                // silently and fast until it settles, then back off.
                timer = setTimeout(load, Math.min(1000 + attempts * 700, 5000));
                if (attempts > 8) {
                    setLoadError(err?.message || 'Failed to load servers');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        load();
        return () => {
            cancelled = true;
            if (timer) clearTimeout(timer);
        };
    }, []);

    // Explicit refresh used by actions (boot/delete/add) and the manual Retry
    // button. The boot-time polling above runs independently.
    const loadServers = async () => {
        try {
            setServers(await api.getServers());
            setLoadError(null);
        } catch (err) {
            console.error("Failed to load servers", err);
            setLoadError(err?.message || 'Failed to load servers');
        } finally {
            setLoading(false);
        }
    };

    const checkConflict = async (targetId) => {
        const activeServer = servers.find(s => s.status && s.status !== 'offline');
        if (!activeServer || (targetId && activeServer.id === targetId)) return false;
        const confirmed = await dialog.confirm(
            `${activeServer.name} is ${activeServer.status}.\n\nYou must stop it before switching to a different server.`,
            "Server Conflict",
            { variant: "warning", confirmLabel: "Stop Server", cancelLabel: "Go Back" }
        );
        if (!confirmed) return true;
        try {
            await api.selectServer(activeServer.id);
            await api.stop();
            // Auto-continue: wait until the old server is actually offline, then
            // let the caller's original action (boot / select / add) proceed.
            const ready = await waitForServerOffline(activeServer.id);
            loadServers();
            if (!ready) {
                await dialog.alert("The running server is still stopping. Try again in a few seconds.", { title: "Server Conflict", variant: "warning" });
                return true;
            }
            return false;
        } catch (e) {
            console.error("Stop error", e);
            return true;
        }
    };

    const handleBoot = async (serverId, e) => {
        e?.stopPropagation();
        if (await checkConflict(serverId)) return;
        setBooting(serverId);
        try {
            await api.selectServer(serverId);
            await api.start();
            loadServers();
            setTimeout(() => onSelect(serverId), 1500);
        } catch (err) {
            console.error("Boot failed", err);
            setBooting(null);
        }
    };

    const handleSelect = async (id) => {
        if (await checkConflict(id)) return;
        try {
            setLoading(true);
            await api.selectServer(id);
            onSelect(id);
        } catch (err) {
            console.error("Failed to select server", err);
            dialog.alert(`Failed to load: ${err.message}`, "Error", "destructive");
            setLoading(false);
        }
    };

    const handleDelete = async (id, e) => {
        e?.stopPropagation();
        const server = servers.find((s) => s.id === id);
        // Single three-way dialog replaces two sequential confirms:
        // Cancel | Delete Profile & Files (danger) | Delete Profile Only
        const action = await dialog.confirm(
            `Delete "${server?.name || 'this profile'}"?\n\nYou can remove only the profile, or also delete every server file on disk.`,
            { title: t('library.delete_title'), variant: 'destructive', cancelLabel: t('common.cancel'), confirmLabel: t('library.delete_profile'), dangerLabel: t('library.delete_files') }
        );
        if (!action) return;
        try {
            await api.deleteServer(id, action === 'danger');
            loadServers();
        } catch (err) {
            console.error("Failed to delete", err);
            dialog.alert(`Failed to delete: ${err.message}`, { title: 'Error', variant: 'destructive' });
        }
    };

    const filteredServers = useMemo(() => servers.filter(s => {
        const q = searchQuery.toLowerCase();
        const matchesQuery = (s.name || '').toLowerCase().includes(q) || (s.server_type || s.type || '').toLowerCase().includes(q);
        const matchesStatus = statusFilter === 'all'
            || (statusFilter === 'online' && s.status === 'online')
            || (statusFilter === 'offline' && (!s.status || s.status === 'offline'));
        return matchesQuery && matchesStatus;
    }), [servers, searchQuery, statusFilter]);

    const recentlyOpened = useMemo(() => [...servers]
        .filter(s => s.last_opened)
        .sort((a, b) => new Date(b.last_opened) - new Date(a.last_opened))
        .slice(0, 3), [servers]);

    const onlineCount = servers.filter(s => s.status === 'online').length;
    const totalCount = servers.length;

    return (
        <div className="flex-1 w-full h-full bg-transparent text-white flex flex-col font-sans relative">
            <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}
                className="w-full flex-1 flex overflow-hidden"
            >
                {/* Sidebar */}
                <div className="w-64 bg-[#0a0a0a]/80 backdrop-blur-xl border-r border-white/10 flex flex-col shadow-2xl z-10 flex-shrink-0">
                    <div className="p-6">
                        <div className="flex items-center gap-3 text-white mb-8">
                            <Terminal size={22} className="text-emerald-400" />
                            <span className="font-minecraft text-xl tracking-wide">{t('library.title')}</span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 mb-8">
                            <div className="bg-black/30 border border-white/5 rounded-sm p-3">
                                <div className="text-2xl font-minecraft text-white">{totalCount}</div>
                                <div className="text-[9px] uppercase tracking-widest text-zinc-500 mt-0.5">{t('library.stats.total')}</div>
                            </div>
                            <div className="bg-emerald-500/5 border border-emerald-500/15 rounded-sm p-3">
                                <div className="text-2xl font-minecraft text-emerald-400">{onlineCount}</div>
                                <div className="text-[9px] uppercase tracking-widest text-emerald-400/70 mt-0.5">{t('library.stats.active')}</div>
                            </div>
                        </div>

                        <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.2em] mb-3">{t('library.quick_filters')}</h3>
                        <div className="space-y-1">
                            {[
                                { id: 'all', label: t('library.all_servers'), icon: <Server size={14} /> },
                                { id: 'online', label: t('status.online'), icon: <Activity size={14} /> },
                                { id: 'offline', label: t('status.offline'), icon: <FolderOpen size={14} /> },
                            ].map(f => (
                                <button
                                    key={f.id}
                                    onClick={() => setStatusFilter(f.id)}
                                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-sm text-xs tracking-wide transition-colors ${statusFilter === f.id ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <span className={statusFilter === f.id ? 'text-emerald-400' : 'text-zinc-500'}>{f.icon}</span>
                                    {f.label}
                                </button>
                            ))}
                        </div>

                        <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.2em] mt-8 mb-3">{t('library.view_mode')}</h3>
                        <div className="space-y-1">
                            <button onClick={() => setViewMode('grid')} className={`w-full flex items-center gap-3 px-3 py-2 rounded-sm text-xs tracking-wide transition-colors ${viewMode === 'grid' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white hover:bg-white/5'}`}>
                                <span className={viewMode === 'grid' ? 'text-emerald-400' : 'text-zinc-500'}><LayoutDashboard size={14} /></span>
                                {t('library.grid_view')}
                            </button>
                            <button onClick={() => setViewMode('detailed')} className={`w-full flex items-center gap-3 px-3 py-2 rounded-sm text-xs tracking-wide transition-colors ${viewMode === 'detailed' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white hover:bg-white/5'}`}>
                                <span className={viewMode === 'detailed' ? 'text-emerald-400' : 'text-zinc-500'}><Server size={14} /></span>
                                {t('library.detailed_view')}
                            </button>
                        </div>
                    </div>

                    <div className="mt-auto p-4 border-t border-white/5">
                        <button
                            onClick={() => setIsSettingsOpen(true)}
                            className="w-full flex items-center gap-3 px-4 py-3 rounded-sm text-xs font-semibold uppercase tracking-wider text-zinc-400 hover:text-white hover:bg-white/5 transition-all"
                        >
                            <Settings size={16} />
                            {t('nav.settings')}
                        </button>
                    </div>
                </div>

                {/* Main */}
                <div className="flex-1 flex flex-col relative overflow-hidden bg-[#050505]/70 backdrop-blur-md w-full">
                    <div className="px-8 pt-8 pb-6 border-b border-white/5 flex items-center gap-4">
                        <div className="flex-1">
                            <h2 className="text-3xl font-minecraft tracking-tight text-white">{t('library.title')}</h2>
                            <p className="text-zinc-500 text-sm mt-0.5">{totalCount} {t('library.stats.total').toLowerCase()}</p>
                        </div>
                        <div className="relative group w-72 max-w-full">
                            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-emerald-400 transition-colors" />
                            <input
                                type="text"
                                placeholder={t('library.search')}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Escape') { setSearchQuery(''); e.target.blur(); } }}
                                className="w-full bg-black/40 border border-white/5 rounded-sm pl-10 pr-9 py-2.5 text-sm text-white focus:outline-none focus:border-white/20 transition-colors font-minecraft tracking-wider"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => { setSearchQuery(''); }}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded-sm text-zinc-500 hover:text-white hover:bg-white/10 transition-colors"
                                    title="Clear search"
                                >
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                                </button>
                            )}
                        </div>
                        <button
                            onClick={async () => { if (await checkConflict(null)) return; onAdd(); }}
                            className="px-5 py-2.5 bg-white text-black rounded-sm text-sm font-medium transition-colors hover:bg-zinc-200 flex items-center gap-2 font-minecraft uppercase tracking-wider shrink-0"
                        >
                            <Plus size={16} /> {t('library.new_server')}
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        {loadError && (
                            <div className="mb-4 flex items-center justify-between gap-3 rounded-sm border border-red-500/20 bg-red-500/5 px-4 py-3 animate-in fade-in duration-200">
                                <div className="flex items-center gap-3 min-w-0">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-400 shrink-0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                                    <span className="text-[11px] text-red-300 truncate">{t('library.load_error')}</span>
                                </div>
                                <button
                                    onClick={() => { setLoading(true); loadServers(); }}
                                    className="px-3 py-1.5 rounded-sm border border-red-500/30 text-[10px] font-minecraft uppercase tracking-widest text-red-300 hover:bg-red-500/10 transition-colors shrink-0"
                                >
                                    {t('common.retry')}
                                </button>
                            </div>
                        )}

                        {loading && totalCount === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-center py-24">
                                <div className="w-8 h-8 border-2 border-white/10 border-t-emerald-400 rounded-full animate-spin mb-4" />
                                <p className="text-zinc-500 text-sm font-minecraft uppercase tracking-widest">{t('common.loading')}</p>
                            </div>
                        ) : totalCount === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-center py-24">
                                <div className="p-5 rounded-sm bg-emerald-500/5 border border-emerald-500/15 mb-6">
                                    <Server size={48} className="text-emerald-400/60" />
                                </div>
                                <h3 className="text-2xl font-minecraft text-white tracking-wide mb-2">{t('library.empty_infrastructure')}</h3>
                                <p className="text-zinc-500 text-sm mb-6 max-w-sm">Create your first Minecraft server to get started.</p>
                                <button
                                    onClick={onAdd}
                                    className="px-6 py-3 bg-white text-black rounded-sm font-minecraft uppercase tracking-wider text-sm hover:bg-zinc-200 transition-colors flex items-center gap-2"
                                >
                                    <Plus size={16} /> {t('library.new_server')}
                                </button>
                            </div>
                        ) : (
                            <>
                                {recentlyOpened.length > 0 && !searchQuery && statusFilter === 'all' && (
                                    <div className="mb-10">
                                        <div className="flex items-center gap-2 mb-4">
                                            <Clock size={16} className="text-emerald-400" />
                                            <h3 className="text-xs font-bold tracking-[0.2em] text-white uppercase font-minecraft">{t('library.recently_opened')}</h3>
                                        </div>
                                        <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-white/10">
                                            {recentlyOpened.map((server) => (
                                                <button
                                                    key={server.id}
                                                    onClick={() => handleSelect(server.id)}
                                                    className="shrink-0 w-56 text-left p-4 bg-[#0a0a0a]/60 backdrop-blur-md border border-white/5 hover:border-white/15 rounded-sm transition-colors group"
                                                >
                                                    <div className="flex items-center justify-between mb-3">
                                                        <div className={`p-2 rounded-sm border ${engineInfo(server.server_type || server.type).bg} ${engineInfo(server.server_type || server.type).border} ${engineInfo(server.server_type || server.type).color}`}>
                                                            <EngineIcon type={server.server_type || server.type} size={14} />
                                                        </div>
                                                        <StatusPill status={server.status} />
                                                    </div>
                                                    <div className="text-sm font-minecraft tracking-wider text-zinc-200 truncate uppercase">{server.name}</div>
                                                    <div className="text-[10px] text-zinc-500 font-mono mt-1">{server.version || 'Latest'} • {formatRelative(server.last_opened)}</div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                <div className="flex items-center gap-2 mb-4">
                                    <FolderOpen size={16} className="text-emerald-400" />
                                    <h3 className="text-xs font-bold tracking-[0.2em] text-white uppercase font-minecraft">
                                        {searchQuery ? t('library.search_results') : t('library.all_servers')}
                                    </h3>
                                    <span className="text-xs text-zinc-600 ml-1">{filteredServers.length}</span>
                                </div>

                                {filteredServers.length === 0 ? (
                                    <div className="py-20 flex flex-col items-center justify-center text-zinc-500">
                                        <Search size={40} className="mb-4 opacity-20" />
                                        <p className="font-minecraft tracking-widest uppercase text-sm opacity-60">{t('library.no_matches')}</p>
                                    </div>
                                ) : viewMode === 'grid' ? (
                                    <div className="grid gap-5 grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                                        {filteredServers.map((server) => (
                                            <ServerCard key={server.id} server={server} t={t}
                                                onClick={() => handleSelect(server.id)}
                                                onBoot={(e) => handleBoot(server.id, e)}
                                                onDelete={(e) => handleDelete(server.id, e)}
                                                booting={booting === server.id} />
                                        ))}
                                    </div>
                                ) : (
                                    <div className="flex flex-col gap-3 max-w-4xl">
                                        {filteredServers.map((server) => (
                                            <ServerRow key={server.id} server={server} t={t}
                                                onClick={() => handleSelect(server.id)}
                                                onBoot={(e) => handleBoot(server.id, e)}
                                                onDelete={(e) => handleDelete(server.id, e)}
                                                booting={booting === server.id} />
                                        ))}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>
            </motion.div>

            <AppSettings isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
        </div>
    );
}

function ServerCard({ server, onClick, onBoot, onDelete, booting, t }) {
    const isOnline = server.status === 'online';
    const isStarting = server.status && server.status !== 'offline' && !isOnline;
    const engineType = (server.server_type || server.type || 'vanilla').toLowerCase();
    const info = engineInfo(engineType);

    return (
        <div
            onClick={onClick}
            className="group relative flex flex-col p-5 bg-[#0a0a0a]/60 backdrop-blur-md border border-white/5 hover:border-white/15 rounded-sm transition-all duration-200 cursor-pointer overflow-hidden"
        >
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3 min-w-0">
                    <div className={`p-3 rounded-sm border shrink-0 ${isOnline ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : `${info.bg} ${info.border} ${info.color}`}`}>
                        <EngineIcon type={engineType} size={22} />
                    </div>
                    <div className="min-w-0">
                        <h3 className="text-base font-minecraft tracking-wider uppercase text-white truncate">{server.name}</h3>
                        <div className="mt-1"><StatusPill status={server.status} /></div>
                    </div>
                </div>
                <button
                    onClick={onDelete}
                    className="p-1.5 text-zinc-600 hover:text-red-400 rounded-sm hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 shrink-0"
                    title={t('library.delete')}
                >
                    <Trash2 size={14} />
                </button>
            </div>

            <div className="flex items-center gap-3 text-[10px] font-minecraft uppercase tracking-wider mb-4">
                <span className={info.color}>{engineType}</span>
                <span className="text-zinc-700">•</span>
                <span className="text-zinc-500">{server.version || 'Latest'}</span>
                {server.last_opened && <><span className="text-zinc-700">•</span><span className="text-zinc-600">{formatRelative(server.last_opened)}</span></>}
            </div>

            <div className="mt-auto">
                {!isOnline && !isStarting ? (
                    <button
                        onClick={onBoot}
                        className="w-full py-2 rounded-sm bg-white/5 hover:bg-white text-zinc-300 hover:text-black border border-white/10 text-[10px] font-minecraft uppercase tracking-wider flex items-center justify-center gap-2 transition-colors"
                    >
                        {booting
                            ? <><span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" /> {t('library.boot')}</>
                            : <><Play size={12} /> {t('library.boot')}</>}
                    </button>
                ) : (
                    <div className="w-full py-2 rounded-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-minecraft uppercase tracking-wider text-center">
                        {t('library.manage')}
                    </div>
                )}
            </div>
        </div>
    );
}

function ServerRow({ server, onClick, onBoot, onDelete, booting, t }) {
    const isOnline = server.status === 'online';
    const isStarting = server.status && server.status !== 'offline' && !isOnline;
    const engineType = (server.server_type || server.type || 'vanilla').toLowerCase();
    const info = engineInfo(engineType);

    return (
        <div
            onClick={onClick}
            className="group flex items-center gap-4 p-4 bg-[#0a0a0a]/60 backdrop-blur-md border border-white/5 hover:border-white/15 rounded-sm transition-colors cursor-pointer"
        >
            <div className={`p-3 rounded-sm border shrink-0 ${isOnline ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : `${info.bg} ${info.border} ${info.color}`}`}>
                <EngineIcon type={engineType} size={20} />
            </div>
            <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3">
                    <h3 className="text-sm font-minecraft tracking-wider uppercase text-white truncate">{server.name}</h3>
                    <StatusPill status={server.status} />
                </div>
                <div className="flex items-center gap-3 text-[10px] font-minecraft uppercase tracking-wider mt-1">
                    <span className={info.color}>{engineType}</span>
                    <span className="text-zinc-700">•</span>
                    <span className="text-zinc-500">{server.version || 'Latest'}</span>
                    {server.last_opened && <><span className="text-zinc-700">•</span><span className="text-zinc-600">{formatRelative(server.last_opened)}</span></>}
                </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                {!isOnline && !isStarting && (
                    <button onClick={onBoot} className="px-3 py-1.5 rounded-sm bg-white/5 hover:bg-white text-zinc-300 hover:text-black border border-white/10 text-[10px] font-minecraft uppercase tracking-wider flex items-center gap-1.5 transition-colors">
                        {booting ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <Play size={11} />}
                        {t('library.boot')}
                    </button>
                )}
                <button onClick={onDelete} className="p-2 text-zinc-600 hover:text-red-400 rounded-sm hover:bg-red-500/10 transition-colors" title={t('library.delete')}>
                    <Trash2 size={15} />
                </button>
            </div>
        </div>
    );
}

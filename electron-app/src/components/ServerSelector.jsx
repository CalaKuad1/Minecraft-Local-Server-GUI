import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Plus, Server, Trash2, Play, Settings, Globe, Activity, Clock, FolderOpen, Search, Terminal, LayoutDashboard } from './ui/PixelIcons';
import logo from '../assets/logo-minimal.png';
import fabricLogo from '../assets/engines/fabric.png';
import forgeLogo from '../assets/engines/forge.png';
import neoforgeLogo from '../assets/engines/neoforge.png';
import paperLogo from '../assets/engines/Paper_JE2_BE2.webp';
import spigotLogo from '../assets/engines/spigot.png';
import vanillaLogo from '../assets/engines/vanilla.webp';
import { useDialog } from './ui/DialogContext';
import { motion, AnimatePresence } from 'framer-motion';
import AppSettings from './AppSettings';
import { useTranslation } from '../contexts/LanguageContext';

export default function ServerSelector({ onSelect, onAdd }) {
    const { t } = useTranslation();
    const [servers, setServers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const dialog = useDialog();

    useEffect(() => {
        loadServers();
        const interval = setInterval(loadServers, 5000);
        return () => clearInterval(interval);
    }, []);

    const loadServers = async () => {
        try {
            const list = await api.getServers();
            setServers(list);
        } catch (err) {
            console.error("Failed to load servers", err);
        } finally {
            setLoading(false);
        }
    };

    const checkConflict = async (targetId) => {
        const activeServer = servers.find(s => s.status && s.status !== 'offline');
        if (activeServer && activeServer.id === targetId) return false;
        if (activeServer) {
            const result = await dialog.confirm(
                `${activeServer.name} is ${activeServer.status}.\n\nYou must stop it before switching to a different server.`,
                "Server Conflict",
                { variant: "warning", confirmLabel: "Stop Server", cancelLabel: "Go Back" }
            );
            if (result) {
                try {
                    await api.selectServer(activeServer.id);
                    await api.stop();
                    dialog.alert(`Stopping ${activeServer.name}...`, "Info", "info");
                } catch (e) { console.error("Stop error", e); }
            }
            return true;
        }
        return false;
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
        e.stopPropagation();
        if (!await dialog.confirm("Are you sure you want to delete this profile?", "Delete Server?", "destructive")) return;
        const deleteFiles = await dialog.confirm("Do you also want to delete all server files?", "Delete Files?", "destructive");
        try {
            await api.deleteServer(id, deleteFiles);
            loadServers();
        } catch (err) {
            console.error("Failed to delete", err);
        }
    };

    const filteredServers = servers.filter(s =>
        (s.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (s.server_type || s.type || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Sort by last_opened for "Recently Opened"
    const recentlyOpened = [...servers]
        .filter(s => s.last_opened)
        .sort((a, b) => new Date(b.last_opened) - new Date(a.last_opened))
        .slice(0, 3);

    const onlineCount = servers.filter(s => s.status === 'online').length;
    const totalCount = servers.length;

    return (
        <div className="flex-1 w-full h-full bg-transparent text-white flex flex-col font-sans relative">
            {/* Split-pane Container (SetupWizard Style) */}
            <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="w-full flex-1 flex overflow-hidden relative"
                style={{ display: 'flex', width: '100%', height: '100%' }}
            >
                {/* Left Sidebar (Wizard Theme) */}
                <div className="w-64 bg-[#0a0a0a]/80 backdrop-blur-xl border-r border-white/10 flex flex-col shadow-2xl z-10 flex-shrink-0">
                    <div className="p-8 pb-4">
                        <div className="flex items-center gap-3 text-white mb-10">
                            <Terminal size={24} className="text-primary" />
                            <span className="font-minecraft text-xl tracking-wide">Library</span>
                        </div>
                        
                        <div className="space-y-8">
                            {/* Stats Group */}
                            <div>
                                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4 font-minecraft">{t('library.all_servers')}</h3>
                                <div className="space-y-4">
                                    <StatItem icon={<Server size={14}/>} label={t('library.stats.total')} value={totalCount} />
                                    <StatItem icon={<Activity size={14}/>} label={t('library.stats.active')} value={onlineCount} active />
                                </div>
                            </div>

                            {/* Filters Group */}
                            <div>
                                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4 font-minecraft">{t('library.quick_filters')}</h3>
                                <div className="space-y-2">
                                    <FilterButton icon={<LayoutDashboard size={14}/>} label={t('library.grid_view')} active />
                                    <FilterButton icon={<Server size={14}/>} label={t('library.detailed_view')} />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="mt-auto p-6 border-t border-white/5">
                        <button 
                            onClick={() => setIsSettingsOpen(true)}
                            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-xs font-semibold uppercase tracking-wider text-gray-400 hover:text-white hover:bg-white/5 transition-all border border-transparent hover:border-white/10 font-minecraft"
                        >
                            <Settings size={16} />
                            {t('nav.settings')}
                        </button>
                    </div>
                </div>

                {/* Main Content Area */}
                <div className="flex-1 flex flex-col relative overflow-hidden bg-[#050505]/70 backdrop-blur-md w-full">
                    {/* Toolbar */}
                    <div className="px-8 pt-8 pb-6 border-b border-white/5 flex items-center justify-between">
                        <div className="relative group flex-1 max-w-md">
                            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 group-focus-within:text-emerald-400 transition-colors" />
                            <input
                                type="text"
                                placeholder={t('library.search')}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full bg-black/40 border border-white/5 rounded-md pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-white/20 transition-colors font-minecraft tracking-wider"
                            />
                        </div>

                        <button
                            onClick={async () => {
                                if (await checkConflict(null)) return;
                                onAdd();
                            }}
                            className="px-5 py-2 bg-white text-black rounded-md text-sm font-medium transition-colors hover:bg-gray-200 flex items-center gap-2 font-minecraft uppercase tracking-wider ml-4"
                        >
                            <Plus size={16} /> {t('library.new_server')}
                        </button>
                    </div>

                    {/* Scrollable Content */}
                    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                        
                        {/* Recently Opened Section */}
                        {recentlyOpened.length > 0 && !searchQuery && (
                            <div className="mb-12">
                                <div className="flex items-center gap-3 mb-6">
                                    <Clock size={18} className="text-emerald-400" />
                                    <h3 className="text-xs font-bold tracking-[0.2em] text-white uppercase font-minecraft">{t('library.recently_opened')}</h3>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {recentlyOpened.map((server) => (
                                        <RecentCard key={server.id} server={server} onClick={() => handleSelect(server.id)} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Main Grid */}
                        <div className="pb-10">
                            <div className="flex items-center gap-3 mb-6">
                                <FolderOpen size={18} className="text-emerald-400" />
                                <h3 className="text-xs font-bold tracking-[0.2em] text-white uppercase font-minecraft">
                                    {searchQuery ? t('library.search_results') : t('library.all_servers')}
                                </h3>
                            </div>

                            {filteredServers.length === 0 ? (
                                <div className="py-24 flex flex-col items-center justify-center text-gray-500">
                                    <Server size={48} className="mb-6 opacity-20" />
                                    <p className="font-bold tracking-widest uppercase text-sm opacity-50 font-minecraft">{searchQuery ? t('library.no_matches') : t('library.empty_infrastructure')}</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                                    {filteredServers.map((server) => (
                                        <ServerCard 
                                            key={server.id} 
                                            server={server} 
                                            onClick={() => handleSelect(server.id)}
                                            onDelete={(e) => handleDelete(server.id, e)}
                                            t={t}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </motion.div>

            <AppSettings isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
        </div>
    );
}

// Sub-components for cleaner structure
function StatItem({ icon, label, value, active }) {
    return (
        <div className="flex items-center justify-between group">
            <div className="flex items-center gap-3">
                <div className={`p-2 rounded-md border transition-colors ${active ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-black/20 border-white/5 text-gray-400 group-hover:text-gray-400'}`}>
                    {icon}
                </div>
                <span className="text-xs font-medium tracking-wide text-gray-400 group-hover:text-gray-400 transition-colors">{label}</span>
            </div>
            <span className={`text-sm font-semibold ${active ? 'text-emerald-400' : 'text-gray-300'}`}>{value}</span>
        </div>
    );
}

function FilterButton({ icon, label, active }) {
    return (
        <button className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium tracking-wide transition-colors ${active ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
            <span className={`${active ? 'text-white' : 'text-gray-400'}`}>{icon}</span>
            {label}
        </button>
    );
}

function EngineIcon({ type, size = 16, className = "" }) {
    const t = (type || '').toLowerCase();
    
    let src = null;
    if (t.includes('paper')) src = paperLogo;
    else if (t.includes('neoforge')) src = neoforgeLogo;
    else if (t.includes('forge')) src = forgeLogo;
    else if (t.includes('fabric')) src = fabricLogo;
    else if (t.includes('spigot')) src = spigotLogo;
    else if (t.includes('vanilla')) src = vanillaLogo;

    if (src) {
        return (
            <div className={`flex items-center justify-center overflow-hidden ${className}`} style={{ width: size, height: size }}>
                <img src={src} className="w-full h-full object-contain brightness-0 invert" alt={type} />
            </div>
        );
    }
    
    // Default Server Icon
    return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
            <line x1="12" y1="22.08" x2="12" y2="12"></line>
        </svg>
    );
}

function RecentCard({ server, onClick }) {
    const isOnline = server.status === 'online';
    
    const engineType = (server.server_type || server.type || 'vanilla').toLowerCase();
    let engineColor = 'text-gray-400';
    if (engineType.includes('paper')) engineColor = 'text-blue-400';
    else if (engineType.includes('neoforge')) engineColor = 'text-red-400';
    else if (engineType.includes('forge')) engineColor = 'text-orange-400';
    else if (engineType.includes('fabric')) engineColor = 'text-amber-200';
    else if (engineType.includes('vanilla')) engineColor = 'text-emerald-400';

    return (
        <button 
            onClick={onClick}
            className="flex flex-col items-start p-4 bg-[#0a0a0a]/60 backdrop-blur-md border border-white/5 rounded-sm hover:bg-white/[0.02] hover:border-white/10 transition-all duration-200 group text-left"
        >
            <div className="flex items-center gap-3 w-full mb-3">
                <div className={`p-1.5 rounded-sm border ${isOnline ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/5 text-gray-500'}`}>
                    <Play size={12} className={isOnline ? "ml-0.5" : ""} />
                </div>
                <div className="text-xs font-minecraft tracking-wider text-gray-200 truncate flex-1 uppercase">{server.name}</div>
            </div>
            
            <div className="flex items-center justify-between w-full mt-auto">
                <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-minecraft uppercase tracking-wider ${engineColor} flex items-center gap-1.5`}>
                        <EngineIcon type={engineType} size={10} />
                        {engineType}
                    </span>
                    <span className="text-[10px] font-mono text-gray-500">
                        {server.version || 'Latest'}
                    </span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-500' : 'bg-gray-600'}`} />
                </div>
            </div>
        </button>
    );
}

function ServerCard({ server, onClick, onDelete, t }) {
    const isOnline = server.status === 'online';
    const isStarting = server.status && server.status !== 'offline' && !isOnline;

    const engineType = (server.server_type || server.type || 'vanilla').toLowerCase();
    let engineColor = 'text-gray-400';
    if (engineType.includes('paper')) engineColor = 'text-blue-400';
    else if (engineType.includes('neoforge')) engineColor = 'text-red-400';
    else if (engineType.includes('forge')) engineColor = 'text-orange-400';
    else if (engineType.includes('fabric')) engineColor = 'text-amber-200';
    else if (engineType.includes('vanilla')) engineColor = 'text-emerald-400';

    return (
        <div 
            onClick={onClick}
            className="group flex flex-col p-4 bg-[#0a0a0a]/60 backdrop-blur-md border border-white/5 hover:bg-white/[0.02] hover:border-white/10 rounded-sm transition-all duration-200 cursor-pointer relative"
        >
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="relative flex items-center justify-center">
                        <div className={`p-2 rounded-sm border transition-colors duration-200 ${isOnline ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/5 text-gray-500 group-hover:text-gray-300'}`}>
                            <EngineIcon type={engineType} size={16} />
                        </div>
                    </div>
                    <div className="flex flex-col">
                        <h3 className="text-sm font-minecraft tracking-widest uppercase text-gray-200 group-hover:text-white transition-colors">{server.name}</h3>
                        <div className="flex items-center gap-1.5 mt-0.5">
                            <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.5)]' : isStarting ? 'bg-yellow-400 animate-pulse' : 'bg-gray-600'}`}></span>
                            <span className={`text-[9px] uppercase font-minecraft tracking-wider ${isOnline ? 'text-emerald-400' : isStarting ? 'text-yellow-400' : 'text-gray-500'}`}>
                                {server.status || 'Offline'}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button 
                        onClick={onDelete}
                        className="p-1.5 text-gray-600 hover:text-red-400 rounded-sm hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                        title="Delete Server"
                    >
                        <Trash2 size={14} />
                    </button>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <div className="bg-white/10 hover:bg-white/20 border border-white/10 text-white w-7 h-7 rounded-sm flex items-center justify-center transition-colors">
                            <Play size={12} className="ml-0.5" />
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-4 mt-auto pt-4 border-t border-white/5">
                <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-gray-600 uppercase tracking-widest font-minecraft">Engine:</span>
                    <span className={`text-[10px] font-minecraft uppercase tracking-wider ${engineColor}`}>
                        {engineType}
                    </span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-gray-600 uppercase tracking-widest font-minecraft">Version:</span>
                    <span className="text-[10px] font-mono text-gray-400">
                        {server.version || 'Latest'}
                    </span>
                </div>
            </div>
        </div>
    );
}

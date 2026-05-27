import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { Play, Square, Activity, Cpu, HardDrive, X, ExternalLink, FolderOpen, Users, Terminal, Clock, Globe } from './ui/PixelIcons';
import { motion, AnimatePresence } from 'framer-motion';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { api } from '../api';
import { Select } from './ui/Select';
import { useTranslation } from '../contexts/LanguageContext';
import { useWebSocket } from '../contexts/WebSocketContext';

const StatCard = ({ icon: Icon, label, value, sublabel, data = [] }) => {
    return (
        <div className="bg-[#050505]/40 border border-white/5 rounded-sm p-5 flex flex-col transition-all group cursor-default hover:border-white/10 hover:bg-[#070707]/60 relative overflow-hidden h-[120px] min-w-0">
            <div className="flex items-center gap-2 mb-3 relative z-10">
                <Icon size={14} className="text-gray-500 group-hover:text-gray-300 transition-colors" />
                <h3 className="text-gray-500 text-xs font-bold uppercase tracking-widest">{label}</h3>
            </div>
            <div className="text-3xl font-minecraft text-white tracking-tight leading-none mb-1 mt-auto relative z-10">{value}</div>
            <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest relative z-10">{sublabel}</div>

            {data.length > 0 && (
                <div className="absolute inset-0 z-0 opacity-10 group-hover:opacity-20 transition-opacity flex items-end">
                    <ResponsiveContainer width="100%" height="60%">
                        <AreaChart data={data}>
                            <defs>
                                <linearGradient id={`grad-${label.replace(/\s+/g, '')}`} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ffffff" stopOpacity={0.8} />
                                    <stop offset="95%" stopColor="#ffffff" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <Area type="monotone" dataKey="value" stroke="#ffffff" strokeWidth={1} fillOpacity={1} fill={`url(#grad-${label.replace(/\s+/g, '')})`} isAnimationActive={false} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
};

const LogBadge = ({ level }) => {
    if (level === 'input') return <span className="px-1.5 py-0.5 bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 rounded mr-2 text-[10px] font-bold">CMD</span>;
    if (level === 'error') return <span className="px-1.5 py-0.5 bg-red-500/10 text-red-500 border border-red-500/20 rounded mr-2 text-[10px] font-bold">ERR</span>;
    if (level === 'warning') return <span className="px-1.5 py-0.5 bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 rounded mr-2 text-[10px] font-bold">WRN</span>;
    return <span className="px-1.5 py-0.5 bg-white/5 text-white/40 border border-white/10 rounded mr-2 text-[10px] font-bold">INF</span>;
};

// Custom Modal Component (Public Server)
const PublicServerModal = ({ onClose, t }) => {
    const services = [
        {
            name: 'pinggy.io',
            description: 'Experimental. Quick tunnel with no installation or configuration. Uses SSH.',
            color: 'bg-primary/20 text-primary border-primary/30',
            url: 'https://pinggy.io',
            recommended: true,
            badge: 'BETA'
        }
    ];

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center">
            <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                onClick={onClose}
            />
            <motion.div
                initial={{ opacity: 0, scale: 0.98, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, y: 10 }}
                transition={{ duration: 0.2 }}
                className="bg-[#0f0f0f] border border-white/10 rounded-sm w-full max-w-lg shadow-2xl overflow-hidden relative z-10 mx-4"
                onClick={e => e.stopPropagation()}
            >
                <div className="bg-[#121212] p-6 border-b border-white/5 relative overflow-hidden">
                    <div className="relative flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="p-3 bg-primary/10 rounded-sm border border-primary/20 text-primary">
                                <Globe size={24} />
                            </div>
                            <div>
                                <h2 className="text-xl font-minecraft tracking-widest text-white uppercase">{t('dashboard.public_server.title')}</h2>
                                <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">{t('dashboard.public_server.desc')}</p>
                            </div>
                        </div>
                        <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-sm transition-colors text-gray-500 hover:text-white">
                            <X size={20} />
                        </button>
                    </div>
                </div>
                <div className="p-8 space-y-6">
                    <p className="text-gray-400 text-xs leading-relaxed font-medium uppercase tracking-wider opacity-80">
                        {t('dashboard.public_server.info_desc')}
                        {t('dashboard.public_server.experimental_warn')}
                    </p>
                    {services.map((service, i) => (
                        <a key={i} href={service.url} target="_blank" rel="noreferrer" className="block p-5 bg-black/40 hover:bg-white/[0.02] border border-white/5 hover:border-white/20 rounded-sm transition-all group">
                            <div className="flex items-start justify-between">
                                <div className="flex items-center gap-4">
                                    <div className={`w-12 h-12 rounded-sm ${service.color} border flex items-center justify-center text-xl font-bold font-minecraft`}>
                                        {service.name[0].toUpperCase()}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-3">
                                            <span className="font-minecraft text-white tracking-widest uppercase">{service.name}</span>
                                            {service.recommended && <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[9px] rounded-sm border border-emerald-500/20 font-bold uppercase tracking-widest">{service.badge || 'BETA'}</span>}
                                        </div>
                                        <p className="text-[11px] text-gray-500 mt-1 font-medium tracking-wide leading-tight">{service.description}</p>
                                    </div>
                                </div>
                                <ExternalLink size={14} className="text-gray-600 group-hover:text-emerald-400 transition-colors" />
                            </div>
                        </a>
                    ))}
                </div>
                <div className="p-6 bg-[#121212] border-t border-white/5 flex justify-end">
                    <button onClick={onClose} className="px-8 py-2.5 bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white rounded-sm text-[10px] font-minecraft tracking-widest uppercase transition-all border border-white/5">{t('common.cancel')}</button>
                </div>
            </motion.div>
        </div>
    );
};

// Custom Modal Component (Playit Claim)
const PlayitClaimModal = ({ link, onClose, t }) => {
    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center">
            <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                onClick={onClose}
            />
            <motion.div
                initial={{ opacity: 0, scale: 0.98, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, y: 10 }}
                transition={{ duration: 0.2 }}
                className="bg-[#0f0f0f] border border-white/10 rounded-sm w-full max-w-md shadow-2xl overflow-hidden relative z-10 mx-4"
                onClick={e => e.stopPropagation()}
            >
                <div className="bg-[#121212] p-6 border-b border-white/5 relative overflow-hidden">
                    <div className="relative flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="p-3 bg-blue-500/10 rounded-sm border border-blue-500/20 text-blue-400 font-minecraft text-xl font-bold">
                                P
                            </div>
                            <div>
                                    <h2 className="text-xl font-minecraft tracking-widest text-white uppercase">{t('dashboard.playit.claim_title', 'Playit.gg Setup')}</h2>
                                <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">{t('dashboard.playit.claim_desc', 'Authorization Required')}</p>
                            </div>
                        </div>
                        <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-sm transition-colors text-gray-500 hover:text-white">
                            <X size={20} />
                        </button>
                    </div>
                </div>
                <div className="p-8 space-y-6 flex flex-col items-center text-center">
                    <p className="text-gray-400 text-xs leading-relaxed font-medium uppercase tracking-wider opacity-80 mb-2">
                        {link.includes('manage/tunnels') 
                            ? "Tu agente de Playit ya está conectado. Sin embargo, no tienes ningún túnel configurado para Minecraft. Por favor, abre el panel de Playit, crea un túnel para Minecraft Java y copia tu nueva IP."
                            : t('dashboard.playit.click_link', 'Click the link below to link this server to your Playit.gg account. Once authorized, the tunnel will connect automatically.')}
                    </p>
                    <a href={link} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center w-full px-5 py-4 bg-blue-500 hover:bg-blue-400 text-black font-minecraft tracking-widest text-sm uppercase transition-all rounded-sm shadow-[0_0_15px_rgba(59,130,246,0.5)] outline outline-offset-2 outline-transparent hover:outline-blue-500/50">
                        <ExternalLink size={16} className="mr-2" />
                        {link.includes('manage/tunnels') ? "Abrir Panel de Control" : t('dashboard.playit.open_browser', 'Open in Browser')}
                    </a>
                </div>
                <div className="p-6 bg-[#121212] border-t border-white/5 flex justify-center">
                    {!link.includes('manage/tunnels') && (
                        <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
                            <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest animate-pulse">{t('dashboard.playit.waiting', 'Waiting for authorization...')}</span>
                        </div>
                    )}
                </div>
            </motion.div>
        </div>
    );
};

// Custom Modal Component (Shutdown Timer)
const ShutdownTimerModal = ({ onClose, onSchedule, onCancel, activeTimer, t }) => {
    const [minutes, setMinutes] = useState(60);
    const presets = [10, 30, 60, 120, 240];

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center">
            <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                onClick={onClose}
            />
            <motion.div
                initial={{ opacity: 0, scale: 0.98, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, y: 10 }}
                transition={{ duration: 0.2 }}
                className="bg-[#0f0f0f] border border-white/10 rounded-sm w-full max-w-md shadow-2xl overflow-hidden relative z-10 mx-4"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="bg-[#121212] p-6 border-b border-white/5 relative overflow-hidden">
                    <div className="flex items-center justify-between relative z-10">
                        <div className="flex items-center gap-4">
                            <div className="p-3 bg-orange-500/10 rounded-sm border border-orange-500/20 text-orange-400 shadow-inner">
                                <Clock size={24} />
                            </div>
                            <div>
                                <h2 className="text-xl font-minecraft tracking-widest text-white uppercase">{t('dashboard.shutdown_timer.title')}</h2>
                                <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">{t('dashboard.shutdown_timer.desc')}</p>
                            </div>
                        </div>
                        <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-sm transition-colors text-gray-500 hover:text-white">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div className="p-8 space-y-8">
                    <div>
                        <label className="text-[10px] font-minecraft text-gray-600 uppercase tracking-widest mb-4 block">{t('dashboard.shutdown_timer.set_duration')}</label>
                        <div className="flex items-center gap-4">
                            <div className="flex-1 relative group">
                                <input
                                    type="number"
                                    value={minutes}
                                    onChange={(e) => setMinutes(Math.max(1, parseInt(e.target.value) || 1))}
                                    className="relative w-full bg-black/40 border border-white/10 rounded-sm px-4 py-4 text-white focus:outline-none focus:border-orange-500/40 transition-colors text-2xl font-bold font-minecraft text-center tracking-widest"
                                />
                            </div>
                            <span className="text-gray-500 font-minecraft uppercase tracking-widest text-xs select-none">{t('dashboard.shutdown_timer.minutes')}</span>
                        </div>
                    </div>

                    <div>
                        <label className="text-[10px] font-minecraft text-gray-600 uppercase tracking-widest mb-4 block">{t('dashboard.shutdown_timer.presets')}</label>
                        <div className="grid grid-cols-5 gap-2">
                            {presets.map(p => (
                                <button
                                    key={p}
                                    onClick={() => setMinutes(p)}
                                    className={`py-2 rounded-sm text-[10px] font-minecraft uppercase tracking-widest transition-all border ${minutes === p
                                        ? 'bg-orange-500/10 text-orange-400 border-orange-500/40'
                                        : 'bg-white/5 border-white/5 text-gray-500 hover:bg-white/10 hover:text-white'
                                        }`}
                                >
                                    {p}m
                                </button>
                            ))}
                        </div>
                    </div>

                    {activeTimer && activeTimer.scheduled && (
                        <div className="p-4 bg-orange-500/5 border border-orange-500/20 rounded-sm flex items-center gap-3 animate-in fade-in zoom-in duration-300">
                            <div className="h-1.5 w-1.5 rounded-full bg-orange-500 animate-pulse shadow-[0_0_8px_#f97316]"></div>
                            <p className="text-[10px] font-minecraft uppercase tracking-widest text-orange-400/80">
                                {t('dashboard.shutdown_timer.starts_in').replace('{min}', Math.ceil(activeTimer.remaining_seconds / 60))}
                            </p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 bg-[#121212] border-t border-white/5 flex gap-4">
                    <button
                        onClick={onClose}
                        className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-gray-500 hover:text-white rounded-sm text-[10px] font-minecraft tracking-widest uppercase transition-all border border-white/5"
                    >
                        {t('common.cancel')}
                    </button>
                    {(activeTimer?.scheduled) ? (
                        <button
                            onClick={() => { onCancel(); onClose(); }}
                            className="flex-1 py-3 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 rounded-sm text-[10px] font-minecraft tracking-widest uppercase transition-all"
                        >
                            {t('dashboard.shutdown_timer.cancel')}
                        </button>
                    ) : (
                        <button
                            onClick={() => onSchedule(minutes)}
                            className="flex-1 py-3 bg-orange-500 text-black rounded-sm text-[10px] font-minecraft tracking-widest uppercase transition-all hover:bg-orange-400"
                        >
                            {t('dashboard.shutdown_timer.start')}
                        </button>
                    )}
                </div>
            </motion.div>
        </div>
    );
};

export default function Dashboard({ status: serverStatus, onRefresh }) {
    const { t } = useTranslation();
    // Local state for immediate UI feedback
    const [localStatus, setLocalStatus] = useState(serverStatus?.status || 'offline');
    const [localLogs, setLocalLogs] = useState([]);

    const isStoppingRef = useRef(serverStatus?.status === 'stopping');
    const lastIdRef = useRef(serverStatus?.server_id);
    const lastWsStatusTime = useRef(0);
    const STATUS_PRIORITY = { offline: 0, starting: 1, stopping: 2, online: 3 };

    // Derived values
    const status = serverStatus || { status: 'offline' };

    // Sync with polling props
    useEffect(() => {
        // Solo sincronizar si NO estamos en medio de un proceso de detención controlado localmente
        if (serverStatus?.status) {
            // Recharts Historical Tracing (Hardware)
            setHistory(prev => {
                const newCpu = [...prev.cpu, { value: parseFloat(serverStatus.cpu || 0) }];
                const newRam = [...prev.ram, { value: parseFloat(serverStatus.ram || 0) }];
                if (newCpu.length > 30) newCpu.shift();
                if (newRam.length > 30) newRam.shift();
                return { cpu: newCpu, ram: newRam };
            });
            if (isStoppingRef.current && serverStatus.status !== 'offline') {
                return;
            }
            setLocalStatus(prev => {
                const pollStatus = serverStatus.status;
                const wsAge = Date.now() - lastWsStatusTime.current;
                if (wsAge < 4000) {
                    if (STATUS_PRIORITY[pollStatus] <= STATUS_PRIORITY[prev]) {
                        return prev;
                    }
                }
                if (prev === 'online' && pollStatus === 'offline' && wsAge < 6000) {
                    return prev;
                }
                return pollStatus;
            });
            if (serverStatus.status === 'offline' || serverStatus.status === 'online') {
                setLoading(false);
                if (serverStatus.status === 'offline') {
                    isStoppingRef.current = false;
                }
            }

            // Sync shutdown info
            if (serverStatus.shutdown_info) {
                setShutdownInfo(serverStatus.shutdown_info);
            } else {
                setShutdownInfo({ scheduled: false });
            }

            // Polling Fallback for Logs (If WS is dead/unstable)
            if (!isConnected && serverStatus.recent_logs && Array.isArray(serverStatus.recent_logs) && serverStatus.recent_logs.length > 0) {
                setLocalLogs(prev => {
                    if (prev.length === 0) return serverStatus.recent_logs.slice(-50);
                    const lastPoll = serverStatus.recent_logs[serverStatus.recent_logs.length - 1];
                    const lastLocal = prev[prev.length - 1];

                    if (lastPoll && (!lastLocal || lastPoll.message !== lastLocal.message)) {
                        return serverStatus.recent_logs.slice(-50);
                    }
                    return prev;
                });
            }
            // Sync auto-restart state
            if (serverStatus?.auto_restart) {
                setAutoRestart(serverStatus.auto_restart.enabled);
            }

            // Sync tunnel info from polling too
            if (serverStatus?.tunnel) {
                if (serverStatus.tunnel.active && serverStatus.tunnel.address) {
                    setTunnelAddress(serverStatus.tunnel.address);
                    setTunnelConnecting(false);
                } else if (!tunnelConnecting && tunnelAddress) {
                    setTunnelAddress(null);
                }
            }
        }
    }, [serverStatus]);

    // Reset logs ONLY when the server ID changes to a DIFFERENT, VALID ID
    useEffect(() => {
        if (serverStatus?.server_id && serverStatus.server_id !== lastIdRef.current) {
            console.log('[Dashboard] Server ID changed, clearing logs');
            setLocalLogs([]);
            setLocalStatus(serverStatus?.status || 'offline');
            lastIdRef.current = serverStatus.server_id;
        }
    }, [serverStatus?.server_id]);


    const onlinePlayersLen = Array.isArray(status.online_players) ? status.online_players.length : 0;
    const playersValue = (status.players !== undefined && status.players !== null) ? Number(status.players) : null;
    const onlineCount = (Number.isFinite(playersValue) && playersValue > 0) ? playersValue : onlinePlayersLen;

    const [loading, setLoading] = useState(false);
    const [showPublicModal, setShowPublicModal] = useState(false);
    const [showShutdownModal, setShowShutdownModal] = useState(false);
    const [shutdownInfo, setShutdownInfo] = useState({ scheduled: false });
    const [tunnelAddress, setTunnelAddress] = useState(null);
    const [tunnelConnecting, setTunnelConnecting] = useState(false);
    const [tunnelRegion, setTunnelRegion] = useState('eu');
    
    // Load preferred provider from localStorage if available, default to pinggy
    const defaultProvider = localStorage.getItem('preferredTunnelProvider') || 'pinggy';
    const [tunnelProvider, setTunnelProvider] = useState(defaultProvider);
    const [playitClaimLink, setPlayitClaimLink] = useState(null);
    const [history, setHistory] = useState({ cpu: [], ram: [] });
    const [autoRestart, setAutoRestart] = useState(false);

    const { isConnected, subscribe, send } = useWebSocket();
    const logsEndRef = useRef(null);
    const scrollContainerRef = useRef(null);
    const userScrolledUpRef = useRef(false);

    const handleWsMessage = useCallback((item) => {
        if (item.type === 'status_change') {
            lastWsStatusTime.current = Date.now();
            setLocalStatus(item.status);
            setLoading(false);
            if (item.status === 'offline') {
                isStoppingRef.current = false;
                if (onRefresh) onRefresh();
            } else if (item.status === 'online') {
                if (onRefresh) onRefresh();
            }
            return;
        }

        if (item.type === 'playit_claim') {
            setPlayitClaimLink(item.link);
            return;
        }

        if (item.type === 'tunnel_connected') {
            setTunnelAddress(item.address);
            setTunnelConnecting(false);
            setPlayitClaimLink(null);
            return;
        }
        if (item.type === 'tunnel_disconnected') {
            setTunnelAddress(null);
            setTunnelConnecting(false);
            setPlayitClaimLink(null);
            return;
        }

        if (item.type === 'auto_restart') {
            setLocalLogs(prev => [...prev, {
                message: `🔄 Auto-restarting (attempt ${item.attempt}/${item.max_attempts})...`,
                level: 'warning',
                time: new Date().toLocaleTimeString([], { hour12: false })
            }]);
            return;
        }

        if (item.message !== undefined || item.level) {
            const msgText = typeof item.message === 'string' ? item.message : JSON.stringify(item.message || '');

            setLocalLogs(prev => {
                const newLogs = [...prev, { ...item, message: msgText }];
                return newLogs.length > 50 ? newLogs.slice(newLogs.length - 50) : newLogs;
            });

            const msg = msgText.toString();
            if (msg.includes("Done") && msg.includes("For help")) {
                lastWsStatusTime.current = Date.now();
                setLocalStatus('online');
                setLoading(false);
                isStoppingRef.current = false;
                if (onRefresh) onRefresh();
            } else if (msg.includes("Stopping server") || msg.includes("Stopping the server")) {
                setLocalStatus('stopping');
                isStoppingRef.current = true;
            }
        }
    }, [onRefresh]);

    useEffect(() => {
        return subscribe('dashboard', handleWsMessage);
    }, [subscribe, handleWsMessage]);

    // Robust Auto-scroll logs
    useEffect(() => {
        if (logsEndRef.current && !userScrolledUpRef.current) {
            const container = logsEndRef.current.parentElement;
            if (container) {
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'auto'
                });
            }
        }
    }, [localLogs]);

    const handleLogScroll = useCallback((e) => {
        const el = e.target;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        userScrolledUpRef.current = !atBottom;
    }, []);

    // Tunnel Polling
    useEffect(() => {
        const checkTunnel = async () => {
            try {
                const status = await api.getTunnelStatus();
                if (status.active && status.address) {
                    setTunnelAddress(status.address);
                    setTunnelConnecting(false);
                } else if (!tunnelConnecting) {
                    setTunnelAddress(null);
                    setTunnelConnecting(false);
                }
            } catch (e) { }
        };
        checkTunnel();
        const interval = setInterval(checkTunnel, 5000);
        return () => clearInterval(interval);
    }, [tunnelConnecting]); // Add dep to prevent clearing while connecting

    const handleStart = async () => {
        setLoading(true);
        setLocalStatus('starting'); // Immediate visual feedback
        try {
            await api.start();
            if (onRefresh) onRefresh();
        } catch (e) {
            setLocalStatus('offline');
            setLoading(false);
        }
    };

    const handleStop = async () => {
        // Si ya se está deteniendo, la segunda pulsación es un Force Kill
        if (isStopping) {
            if (confirm("¿El servidor no responde? ¿Quieres forzar el cierre inmediatemente? (Podría perderse el progreso no guardado)")) {
                setLoading(true);
                try {
                    await api.stop(true); // force = true
                } catch (e) { }
                setLoading(false);
            }
            return;
        }

        setLoading(true);
        setLocalStatus('stopping');
        isStoppingRef.current = true;
        try {
            await api.stop(false); // Normal stop
        } catch (e) {
            setLoading(false);
            isStoppingRef.current = false;
        }
    };

    const handleOpenFolder = async () => {
        try { await api.openServerFolder(); } catch (error) { }
    };

    const handleScheduleShutdown = async (minutes) => {
        try {
            await api.scheduleStop(minutes);
            setShowShutdownModal(false);
            if (onRefresh) onRefresh();
        } catch (error) {
            alert("Failed to schedule shutdown: " + error.message);
        }
    };

    const handleCancelShutdown = async () => {
        try {
            await api.cancelStop();
            if (onRefresh) onRefresh();
        } catch (error) {
            alert("Failed to cancel shutdown: " + error.message);
        }
    };

    const isOnline = localStatus === 'online';
    const isStarting = localStatus === 'starting';
    const isStopping = localStatus === 'stopping';

    return (
        <div className="flex flex-col h-full animate-in fade-in zoom-in duration-500">
            <div className="space-y-4 flex-none">
                {/* Header & Controls */}
                <div className="flex items-center justify-between px-6 py-5 bg-[#18181b]/60 border border-white/5 shadow-sm relative overflow-hidden backdrop-blur-2xl rounded-sm">
                    <div className="relative z-10 flex items-center gap-4">
                        <div className={`w-2 h-2 rounded-sm ${isOnline ? 'bg-primary shadow-[0_0_10px_rgba(16,185,129,0.4)]' : (isStarting || isStopping) ? 'bg-yellow-500 animate-pulse' : 'bg-zinc-600'}`}></div>
                        <div>
                            <div className="flex items-center gap-2 mb-0.5">
                                <span className={`text-[10px] font-bold tracking-widest uppercase ${isOnline ? 'text-primary' : (isStarting || isStopping) ? 'text-yellow-500' : 'text-zinc-500'}`}>
                                    {isStopping ? t('status.stopping') : t(`status.${localStatus}`)}
                                </span>
                            </div>
                            <h2 className="text-2xl font-minecraft text-white tracking-wide">
                                Minecraft Server
                            </h2>
                            <p className="text-[10px] text-gray-400 mt-0.5 uppercase font-bold tracking-widest">
                                {status.server_type ? `${status.server_type} | ${status.version || status.minecraft_version || ''}` : t('status.not_configured')}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3 relative z-10">
                        {!isOnline && !isStarting && !isStopping && (
                            <button
                                onClick={handleStart}
                                disabled={loading}
                                className="px-5 py-2.5 bg-white text-black hover:bg-zinc-200 border border-transparent rounded-sm font-minecraft tracking-wider text-sm flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed group uppercase font-bold"
                            >
                                <Play size={16} fill="currentColor" /> {t('dashboard.start')}
                            </button>
                        )}

                        {(isOnline || isStarting || isStopping) && (
                            <button
                                onClick={handleStop}
                                disabled={loading || (!isOnline && !isStarting && !isStopping)}
                                className={`px-5 py-2.5 rounded-sm font-minecraft tracking-wider text-sm flex items-center justify-center gap-2 transition-all disabled:opacity-50 border uppercase
                                    ${isStopping
                                        ? 'bg-red-500/10 border-red-500/50 text-red-500 animate-pulse'
                                        : 'bg-transparent border-white/10 text-zinc-400 hover:bg-white/5 hover:text-white hover:border-white/30'
                                    }`}
                            >
                                <Square size={16} fill="currentColor" /> {isStopping ? 'Force Kill' : t('dashboard.stop')}
                            </button>
                        )}
                        
                        {/* Scheduled Shutdown Button/Badge */}
                        {isOnline && (
                            <div className="relative">
                                <button
                                    onClick={() => setShowShutdownModal(true)}
                                    className={`h-10 w-10 flex items-center justify-center rounded-sm bg-transparent border hover:bg-white/10 transition-colors ${shutdownInfo.scheduled ? 'border-orange-500/50 text-orange-400' : 'border-white/10 text-zinc-600 hover:text-white'}`}
                                    title="Schedule Shutdown"
                                >
                                    <Clock size={16} className={shutdownInfo.scheduled ? 'animate-pulse' : ''} />
                                </button>
                                {shutdownInfo.scheduled && (
                                    <div className="absolute -top-2 -right-2 bg-orange-500 text-black text-[10px] font-bold px-1.5 py-0.5 rounded-sm border border-black shadow-sm pointer-events-none">
                                        {Math.ceil(shutdownInfo.remaining_seconds / 60)}m
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Auto-restart Toggle */}
                        <button
                            onClick={async () => {
                                const newState = !autoRestart;
                                try {
                                    await api.setAutoRestart(newState);
                                    setAutoRestart(newState);
                                } catch (err) {
                                    console.error("Failed to toggle auto-restart", err);
                                }
                            }}
                            className={`h-10 px-3 flex items-center gap-2 rounded-sm border text-[10px] font-bold uppercase tracking-widest transition-all ${
                                autoRestart
                                    ? 'bg-green-500/10 border-green-500/40 text-green-400 hover:bg-green-500/20'
                                    : 'border-white/10 text-zinc-600 hover:text-white hover:bg-white/5'
                            }`}
                            title={autoRestart ? 'Auto-restart on crash: ON' : 'Auto-restart on crash: OFF'}
                        >
                            <div className={`w-2 h-2 rounded-full ${autoRestart ? 'bg-green-500 animate-pulse' : 'bg-zinc-600'}`} />
                            Auto
                        </button>
                    </div>
                </div>

            {/* Local IP Info + Make Public */}
            <div className="flex items-center gap-4 p-4 bg-[#18181b]/60 border border-white/5 rounded-sm relative z-50 backdrop-blur-2xl">
                <div className="flex items-center gap-3 flex-1">
                    <div className="p-2 rounded-sm border border-white/10 bg-white/5 text-zinc-300">
                        <Terminal size={16} />
                    </div>
                    <div>
                        <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest leading-none mb-1">
                            {tunnelAddress ? 'Public Gateway' : 'Local Host'}
                        </div>
                        <div className="text-sm font-mono text-white font-bold leading-none">
                            {tunnelAddress === "Check Playit.gg Dashboard" ? (
                                <div className="flex items-center gap-2">
                                    <span className="text-orange-400">Panel Playit.gg</span>
                                    <button 
                                        onClick={async () => {
                                            const ip = prompt("Por favor, introduce la IP de tu servidor de Minecraft Java que te da Playit (ej. nombre.auto.playit.gg):");
                                            if (ip) {
                                                try {
                                                    await api.setTunnelAddress(ip);
                                                } catch (err) {
                                                    console.error("Failed to set IP", err);
                                                }
                                            }
                                        }}
                                        className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded-sm transition-colors text-white uppercase tracking-wider cursor-pointer"
                                    >
                                        Escribir IP
                                    </button>
                                </div>
                            ) : (
                                <span className={tunnelAddress ? "text-orange-400 select-all" : "select-all"}>
                                    {tunnelAddress || `${status.local_ip || '127.0.0.1'}:${status.port || '25565'}`}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <button onClick={handleOpenFolder} className="p-2 border border-transparent bg-transparent hover:bg-white/5 text-zinc-500 hover:text-white rounded-sm transition-colors hover:border-white/10" title="Open Server Directory">
                    <FolderOpen size={16} />
                </button>

                <div className="flex gap-2 h-full items-stretch">
                    <div className="w-28 relative z-50 rounded-sm border border-white/10 hover:border-white/20 transition-colors bg-white/5">
                        <Select value={tunnelProvider} onChange={(val) => {
                            setTunnelProvider(val);
                            localStorage.setItem('preferredTunnelProvider', val);
                        }} disabled={!!tunnelAddress || tunnelConnecting} options={[{ value: 'pinggy', label: 'Pinggy (Recomendado)' }, { value: 'playit', label: 'Playit.gg' }]} />
                    </div>
                    {tunnelProvider === 'pinggy' && (
                        <div className="w-24 relative z-50 rounded-sm border border-white/10 hover:border-white/20 transition-colors bg-white/5 animate-in fade-in slide-in-from-left-2 duration-300">
                            <Select value={tunnelRegion} onChange={setTunnelRegion} disabled={!!tunnelAddress || tunnelConnecting} options={[{ value: 'eu', label: 'EU 🇪🇺' }, { value: 'us', label: 'US 🇺🇸' }, { value: 'ap', label: 'Asia 🌏' }]} />
                        </div>
                    )}
                </div>

                <button
                    onClick={async () => {
                        try {
                            if (tunnelAddress) {
                                await api.stopTunnel();
                                setTunnelAddress(null);
                                setTunnelConnecting(false);
                                setPlayitClaimLink(null);
                            } else {
                                setTunnelConnecting(true);
                                setPlayitClaimLink(null);
                                console.log('[Dashboard] Starting tunnel with region:', tunnelRegion, 'provider:', tunnelProvider);
                                const result = await api.startTunnel(tunnelRegion, tunnelProvider);
                                console.log('[Dashboard] Tunnel start result:', result);
                                
                                // Automatically save Pinggy provider selection since it's the most reliable option now
                                if (tunnelProvider === 'pinggy') {
                                    localStorage.setItem('preferredTunnelProvider', 'pinggy');
                                }
                                // Note: tunnelConnecting will be set to false by polling or WS event
                            }
                        } catch (err) {
                            console.error('[Dashboard] Tunnel error:', err);
                            setTunnelConnecting(false);
                            // Get the error message from the response if possible
                            const errorMsg = err.response?.data?.detail || err.message || "Unknown error";
                            // Show error in logs
                            setLocalLogs(prev => [...prev, {
                                message: `❌ Tunnel error: ${errorMsg}`,
                                level: 'error',
                                time: new Date().toISOString()
                            }]);
                            alert(`Error de túnel: ${errorMsg}`);
                        }
                    }}
                    disabled={tunnelConnecting && !tunnelAddress}
                    className={`px-4 py-2 border rounded-sm text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all group ${tunnelAddress ? 'bg-transparent border-red-500/20 text-red-400 hover:bg-red-500/10' : tunnelConnecting ? 'bg-transparent border-yellow-500/20 text-yellow-400' : 'bg-transparent border-white/10 text-zinc-400 hover:text-white hover:border-white/30'}`}
                >
                    {tunnelAddress ? (<><Square size={14} className="group-hover:fill-current" /> Stop Public</>) : tunnelConnecting ? (<><div className="w-3.5 h-3.5 border-2 border-yellow-400/30 border-t-yellow-400 rounded-full animate-spin" /> Connecting...</>) : (<><Globe size={14} /> Make Public</>)}
                </button>

                <div className="relative group">
                    <button onClick={() => setShowPublicModal(true)} className="p-2 rounded-sm bg-[#27272a] hover:bg-[#3f3f46] text-gray-400 hover:text-white transition-all">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><path d="M12 17h.01" /></svg>
                    </button>

                    {/* Tooltip on hover */}
                    <div className="absolute bottom-full right-0 mb-2 w-64 p-3 bg-black/90 rounded-sm border border-white/10 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity shadow-xl z-50">
                        <div className="text-sm text-white font-medium mb-1 uppercase font-minecraft tracking-widest">Public Server</div>
                        <div className="text-xs text-gray-400 uppercase tracking-wider">
                            Click to make your server accessible from the Internet.
                        </div>
                        <div className="absolute bottom-[-6px] right-4 w-3 h-3 bg-black/90 rotate-45 border-r border-b border-white/10"></div>
                    </div>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-5 relative z-10">
                <StatCard icon={Users} label={t('dashboard.players_online')} value={onlineCount !== undefined ? `${onlineCount}` : '-'} sublabel={`/ ${status.max_players || 20} ${t('status.online')}`} />
                <StatCard icon={Cpu} label={t('dashboard.cpu_usage')} value={status.cpu !== undefined ? `${status.cpu}%` : '--'} sublabel={t('dashboard.cpu_sub')} data={history.cpu} />
                <StatCard icon={HardDrive} label={t('dashboard.ram_usage')} value={status.ram || '--'} sublabel={t('dashboard.ram_sub')} data={history.ram} />
                <StatCard icon={Activity} label={t('dashboard.uptime')} value={status.uptime || '--'} sublabel={t('dashboard.uptime_sub')} />
            </div>
            </div>

            {/* Mini Console (Real-time via WS) */}
            <div className="mt-8 h-80 flex-none bg-black/40 backdrop-blur-2xl border border-white/5 rounded-sm overflow-hidden flex flex-col shadow-xl">
                <div className="bg-black/40 px-4 py-2 border-b border-white/5 flex items-center justify-between">
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-2 font-minecraft">
                        {t('dashboard.sys_event_log')}
                    </span>
                </div>
                <div className="p-4 font-mono text-xs flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10" ref={scrollContainerRef} onScroll={handleLogScroll}>
                    {localLogs.length > 0 ? (
                        localLogs.map((log, i) => {
                            const timeStr = log.time
                                ? (log.time.includes(':') ? log.time : new Date(log.time).toLocaleTimeString([], { hour12: false }))
                                : '';
                            return (
                            <div key={`${i}-${log.message?.slice(0, 20)}`} className="flex items-start font-mono text-[11.5px] leading-relaxed hover:bg-white/5 px-2 py-0.5 rounded transition-colors group">
                                <div className="w-12 flex-shrink-0 text-white/10 select-none group-hover:text-white/30 transition-colors">
                                    {String(i + 1).padStart(4, '0')}
                                </div>
                                {log.level !== 'input' && (
                                    <div className="text-white/20 mr-3 select-none w-16">
                                        {timeStr}
                                    </div>
                                )}
                                <div className="mt-0.5"><LogBadge level={log.level} /></div>
                                <div className={`flex-1 whitespace-pre-wrap break-words ${log.level === 'error' ? 'text-red-400' :
                                    log.level === 'warning' ? 'text-yellow-400' :
                                        log.level === 'input' ? 'text-white font-bold tracking-tight' :
                                            'text-zinc-300'
                                    }`}>
                                    {log.message}
                                </div>
                            </div>
                            );
                        })
                    ) : (
                        <div className="h-full flex items-center justify-center text-gray-700 italic flex-col gap-2">
                            <Activity size={24} className="opacity-20 animate-pulse" />
                            <span>{t('dashboard.waiting_logs')}</span>
                        </div>
                    )}
                    <div ref={logsEndRef} className="h-1 shadow-sm" />
                </div>
                {/* Mini Console Input */}
                <form
                    onSubmit={async (e) => {
                        e.preventDefault();
                        const input = e.target.elements.cmd.value;
                        if (!input.trim()) return;

                        setLocalLogs(prev => [...prev, { message: `> ${input}`, level: 'input' }]);

                        try {
                            if (isConnected) {
                                send(input);
                            } else {
                                await api.sendCommand(input);
                            }
                            e.target.elements.cmd.value = '';
                        } catch (err) {
                            setLocalLogs(prev => [...prev, { message: `Error: ${err.message}`, level: 'error', time: new Date().toLocaleTimeString([], { hour12: false }) }]);
                        }
                    }}
                    className="border-t border-white/5 bg-black/30 p-2 flex"
                >
                    <span className="text-zinc-500 px-2 font-mono font-bold pt-1">$</span>
                    <input
                        name="cmd"
                        type="text"
                        autoComplete="off"
                        placeholder={t('nav.console') + "..."}
                        className="bg-transparent border-none outline-none text-zinc-300 font-mono text-sm flex-1"
                    />
                </form>
            </div>

            {/* Public Server Modal */}
            <AnimatePresence>
                {showPublicModal && (
                    <PublicServerModal
                        onClose={() => setShowPublicModal(false)}
                        t={t}
                    />
                )}
                {playitClaimLink && (
                    <PlayitClaimModal 
                        link={playitClaimLink} 
                        onClose={() => api.stopTunnel()} 
                        t={t} 
                    />
                )}
                {showShutdownModal && (
                    <ShutdownTimerModal
                        onClose={() => setShowShutdownModal(false)}
                        onSchedule={handleScheduleShutdown}
                        onCancel={handleCancelShutdown}
                        activeTimer={shutdownInfo}
                        t={t}
                    />
                )}
            </AnimatePresence>
        </div >
    );
}

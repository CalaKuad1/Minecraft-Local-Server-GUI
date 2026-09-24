import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Play, Square, Activity, Cpu, HardDrive, X, ExternalLink, FolderOpen, Users, Terminal, Clock, Globe, Zap } from './ui/PixelIcons';
import { motion, AnimatePresence } from 'framer-motion';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { api } from '../api';
import { Select } from './ui/Select';
import { useTranslation } from '../contexts/LanguageContext';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useDialog } from './ui/DialogContext';

const StatCard = ({ icon: Icon, label, value, sublabel, data = [], active = true }) => {
    return (
        <div className="bg-[#050505]/40 border border-white/5 rounded-sm p-5 flex flex-col transition-all group cursor-default hover:border-white/10 hover:bg-[#070707]/60 relative overflow-hidden h-[120px] min-w-0">
            <div className="flex items-center gap-2 mb-3 relative z-10">
                <Icon size={14} className="text-gray-500 group-hover:text-gray-300 transition-colors" />
                <h3 className="text-gray-500 text-xs font-bold uppercase tracking-widest">{label}</h3>
            </div>
            <div className="text-3xl font-minecraft text-white tracking-tight leading-none mb-1 mt-auto relative z-10">{value}</div>
            <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest relative z-10">{sublabel}</div>

            {data.length > 0 && active && (
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

// Schedule-shutdown modal. Previously referenced but never defined, which threw
// "ShutdownTimerModal is not defined" and crashed the Dashboard.
const ShutdownTimerModal = ({ onClose, onSchedule, onCancel, activeTimer, t }) => {
    const [minutes, setMinutes] = useState(15);
    const isActive = activeTimer?.scheduled;
    const remaining = isActive ? Math.max(0, Math.ceil((activeTimer.remaining_seconds || 0) / 60)) : 0;
    const presets = [5, 15, 30, 60];

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
                <div className="bg-[#121212] p-6 border-b border-white/5 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-orange-500/10 rounded-sm border border-orange-500/20 text-orange-400">
                            <Clock size={20} />
                        </div>
                        <div>
                            <h2 className="text-lg font-minecraft tracking-widest text-white uppercase">{t('dashboard.shutdown_timer.title')}</h2>
                            <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest">{t('dashboard.shutdown_timer.desc')}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-sm text-zinc-500 hover:text-white transition-colors">
                        <X size={18} />
                    </button>
                </div>

                <div className="p-6 space-y-5">
                    {isActive ? (
                        <div className="text-center py-4">
                            <div className="text-[10px] uppercase tracking-widest text-orange-400 mb-1">{t('dashboard.shutdown_timer.timer_active')}</div>
                            <div className="text-4xl font-minecraft text-white">
                                {remaining} <span className="text-lg text-zinc-500">{t('dashboard.shutdown_timer.minutes')}</span>
                            </div>
                        </div>
                    ) : (
                        <>
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">{t('dashboard.shutdown_timer.presets')}</div>
                                <div className="grid grid-cols-4 gap-2">
                                    {presets.map(p => (
                                        <button
                                            key={p}
                                            onClick={() => setMinutes(p)}
                                            className={`py-2 rounded-sm border text-sm font-mono transition-colors ${minutes === p ? 'bg-orange-500/15 border-orange-500/40 text-orange-400' : 'bg-white/5 border-white/10 text-zinc-400 hover:text-white'}`}
                                        >
                                            {p}m
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">{t('dashboard.shutdown_timer.set_duration')}</div>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="number" min="1" value={minutes}
                                        onChange={(e) => setMinutes(Math.max(1, parseInt(e.target.value || '1', 10) || 1))}
                                        className="flex-1 bg-black/40 border border-white/10 rounded-sm px-4 py-2 text-white font-mono focus:border-orange-500 outline-none"
                                    />
                                    <span className="text-zinc-500 text-sm">{t('dashboard.shutdown_timer.minutes')}</span>
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <div className="p-6 border-t border-white/5 flex justify-end gap-3">
                    {isActive ? (
                        <button
                            onClick={() => { onCancel(); onClose(); }}
                            className="px-6 py-2.5 rounded-sm border border-red-500/40 text-red-400 hover:bg-red-500/10 text-[10px] font-minecraft tracking-widest uppercase transition-all"
                        >
                            {t('dashboard.shutdown_timer.cancel')}
                        </button>
                    ) : (
                        <>
                            <button onClick={onClose} className="px-6 py-2.5 rounded-sm border border-white/5 text-zinc-500 hover:text-white hover:bg-white/5 text-[10px] font-minecraft tracking-widest uppercase transition-all">
                                {t('common.cancel')}
                            </button>
                            <button
                                onClick={() => { onSchedule(minutes); onClose(); }}
                                className="px-6 py-2.5 rounded-sm bg-orange-500 text-black hover:bg-orange-400 text-[10px] font-minecraft tracking-widest uppercase transition-all"
                            >
                                {t('dashboard.shutdown_timer.start')}
                            </button>
                        </>
                    )}
                </div>
            </motion.div>
        </div>
    );
};

const STATUS_PRIORITY = { offline: 0, starting: 1, stopping: 2, online: 3 };

export default function Dashboard({ status: serverStatus, onRefresh, active = true, onNavigate }) {
    const { t } = useTranslation();
    const { isConnected, subscribe, send } = useWebSocket();
    const dialog = useDialog();

    // Local state for immediate UI feedback
    const [localStatus, setLocalStatus] = useState(serverStatus?.status || 'offline');
    const [localLogs, setLocalLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [showPublicModal, setShowPublicModal] = useState(false);
    const [showShutdownModal, setShowShutdownModal] = useState(false);
    const [shutdownInfo, setShutdownInfo] = useState({ scheduled: false });
    const [tunnelAddress, setTunnelAddress] = useState(null);
    const [tunnelConnecting, setTunnelConnecting] = useState(false);
    const [tunnelRegion, setTunnelRegion] = useState('eu');
    const [tunnelProvider] = useState('pinggy');
    const [bedrockAddress, setBedrockAddress] = useState(null);
    const [bedrockConnecting, setBedrockConnecting] = useState(false);
    const [geyserInfo, setGeyserInfo] = useState({ installed: false, bedrock_port: 19132, floodgate_installed: false });
    const [history, setHistory] = useState({ cpu: [], ram: [] });

    const [autoRestart, setAutoRestart] = useState(false);
    const [dnsAddress, setDnsAddress] = useState(null);
    const [dnsStatus, setDnsStatus] = useState('unknown'); // unknown | checking | ok | error
    const [dnsUsage, setDnsUsage] = useState(null); // { used, capacity, srv, healthy }
    const [autoTunnel, setAutoTunnel] = useState(localStorage.getItem('autoTunnel') !== 'false');
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [dnsEditing, setDnsEditing] = useState(false);
    const [dnsAvailable, setDnsAvailable] = useState(null);
    const [dnsSubdomain, setDnsSubdomain] = useState('');
    const [onlineMode, setOnlineMode] = useState(true);
    const [togglingMode, setTogglingMode] = useState(false);
    const [serverError, setServerError] = useState(null);
    const [addressCopied, setAddressCopied] = useState(false);

    const isStoppingRef = useRef(serverStatus?.status === 'stopping');
    const lastIdRef = useRef(serverStatus?.server_id);
    const lastWsStatusTime = useRef(0);
    const logsEndRef = useRef(null);
    const scrollContainerRef = useRef(null);
    const userScrolledUpRef = useRef(false);

    // Derived status
    const isOnline = localStatus === 'online';
    const isStarting = localStatus === 'starting';
    const isStopping = localStatus === 'stopping';

    // Derived values
    const status = serverStatus || { status: 'offline' };
    const onlinePlayersLen = Array.isArray(status.online_players) ? status.online_players.length : 0;
    const playersValue = (status.players !== undefined && status.players !== null) ? Number(status.players) : null;
    const onlineCount = (Number.isFinite(playersValue) && playersValue > 0) ? playersValue : onlinePlayersLen;

    // Sync with polling props
    useEffect(() => {
        // Solo sincronizar si NO estamos en medio de un proceso de detenci├│n controlado localmente
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
                if (serverStatus.tunnel.dns_address) {
                    setDnsAddress(serverStatus.tunnel.dns_address);
                }
            }
            if (serverStatus?.bedrock_tunnel) {
                if (serverStatus.bedrock_tunnel.active && serverStatus.bedrock_tunnel.address) {
                    setBedrockAddress(serverStatus.bedrock_tunnel.address);
                    setBedrockConnecting(false);
                } else if (!bedrockConnecting && bedrockAddress) {
                    setBedrockAddress(null);
                }
            }
            if (serverStatus?.geyser) {
                setGeyserInfo(serverStatus.geyser);
            }
            if (serverStatus?.auto_restart) {
                setAutoRestart(serverStatus.auto_restart.enabled);
            }

        }
    }, [serverStatus]);

    // Load DNS subdomain
    useEffect(() => {
        if (!serverStatus?.server_id) return;
        api.getDnsSubdomain().then(data => {
            if (data?.subdomain && !data?.address) {
                setDnsSubdomain(data.subdomain);
                setDnsEditing(true);
            } else if (data?.address) {
                setDnsAddress(data.address);
                setDnsSubdomain(data.subdomain);
            }
        }).catch(() => {});
        api.getOnlineMode().then(data => {
            if (data) setOnlineMode(data.online_mode);
        }).catch(() => {});
    }, [serverStatus?.server_id]);

    // DNS usage/availability indicator (polls the Worker)
    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const u = await api.getDnsUsage();
                if (!cancelled) setDnsUsage(u);
            } catch (e) { /* ignore */ }
        };
        load();
        const interval = setInterval(load, 30000);
        return () => { cancelled = true; clearInterval(interval); };
    }, [serverStatus?.server_id]);

    // Reset logs ONLY when the server ID changes to a DIFFERENT, VALID ID
    useEffect(() => {
        if (serverStatus?.server_id && serverStatus.server_id !== lastIdRef.current) {
            console.log('[Dashboard] Server ID changed, clearing logs');
            setLocalLogs([]);
            setLocalStatus(serverStatus?.status || 'offline');
            lastIdRef.current = serverStatus.server_id;
        }
    }, [serverStatus?.server_id]);

    const MAX_MINI_LOGS = 50;
    const appendLocalLog = useCallback((entry) => {
        setLocalLogs(prev => {
            const next = [...prev, entry];
            return next.length > MAX_MINI_LOGS ? next.slice(next.length - MAX_MINI_LOGS) : next;
        });
    }, []);

    const handleWsMessage = useCallback((item) => {
        if (item.type === 'status_change') {
            lastWsStatusTime.current = Date.now();
            setLocalStatus(item.status);
            setLoading(false);
            if (item.status === 'offline') {
                isStoppingRef.current = false;
                if (onRefresh) onRefresh();
            } else if (item.status === 'online') {
                setServerError(null);
                if (onRefresh) onRefresh();
            }
            return;
        }

        if (item.type === 'tunnel_connected') {
            setTunnelAddress(item.address);
            setTunnelConnecting(false);
            return;
        }
        if (item.type === 'tunnel_disconnected') {
            setTunnelAddress(null);
            setTunnelConnecting(false);
            return;
        }
        if (item.type === 'tunnel_bedrock_connected') {
            setBedrockAddress(item.address);
            setBedrockConnecting(false);
            return;
        }
        if (item.type === 'tunnel_bedrock_disconnected') {
            setBedrockAddress(null);
            setBedrockConnecting(false);
            return;
        }


        if (item.type === 'auto_restart') {
            appendLocalLog({
                message: `🔄 Auto-restarting (attempt ${item.attempt}/${item.max_attempts})...`,
                level: 'warning',
                time: new Date().toLocaleTimeString([], { hour12: false })
            });
            return;
        }

        if (item.type === 'dns_updated') {
            setDnsAddress(item.address);
            setDnsStatus('checking');
            return;
        }

        if (item.type === 'dns_verified') {
            setDnsAddress(item.address);
            setDnsStatus('ok');
            setServerError(prev => (prev && prev.error === 'dns_error' ? null : prev));
            return;
        }

        if (item.type === 'dns_error') {
            setDnsStatus('error');
            setServerError({
                error: 'dns_error',
                fix: `Custom address problem: ${item.error}${item.direct ? ` — you can still connect directly via ${item.direct}` : ''}`,
                detail: item.subdomain ? `${item.subdomain}.play.ariser.app` : ''
            });
            return;
        }

        if (item.type === 'server_error') {
            setServerError(item);
            return;
        }

        if (item.message !== undefined || item.level) {
            const msgText = typeof item.message === 'string' ? item.message : JSON.stringify(item.message || '');

            appendLocalLog({ ...item, message: msgText });

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
    }, [onRefresh, appendLocalLog]);

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

            try {
                const bStatus = await api.getBedrockTunnelStatus();
                if (bStatus.active && bStatus.address) {
                    setBedrockAddress(bStatus.address);
                    setBedrockConnecting(false);
                } else if (!bStatus.starting) {
                    // Backend is neither connected nor starting: clear any stuck spinner.
                    setBedrockAddress(null);
                    setBedrockConnecting(false);
                }
            } catch (e) { }

            try {
                const gInfo = await api.getGeyserStatus();
                if (gInfo) setGeyserInfo(gInfo);
            } catch (e) { }
        };
        checkTunnel();
        const interval = setInterval(checkTunnel, 5000);
        return () => clearInterval(interval);
    }, [tunnelConnecting, bedrockConnecting]); // Add deps to prevent clearing while connecting


    const handleStart = async () => {
        setLoading(true);
        setLocalStatus('starting');
        try {
            await api.start();
            if (autoTunnel) {
                setTimeout(async () => {
                    try {
                        setTunnelConnecting(true);
                        await api.startTunnel(tunnelRegion, tunnelProvider);
                    } catch (e) { setTunnelConnecting(false); }
                }, 5000);
            }
            if (onRefresh) onRefresh();
        } catch (e) {
            setLocalStatus('offline');
            setLoading(false);
        }
    };

    const handleStop = async () => {
        // If already stopping, second click is a Force Kill
        if (isStopping) {
            const ok = await dialog.confirm(
                t('dashboard.force_stop_confirm', 'Server is not responding. Force close immediately? (Unsaved progress may be lost)'),
                { title: 'Force Kill?', variant: 'destructive', confirmLabel: 'Force Kill', cancelLabel: 'Cancel' }
            );
            if (ok) {
                setLoading(true);
                try {
                    await api.stop(true); // force = true
                } catch (e) {
                    console.error('[Dashboard] Force stop failed:', e);
                }
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
            dialog.alert("Failed to schedule shutdown: " + error.message, { title: 'Error', variant: 'destructive' });
        }
    };

    const handleCancelShutdown = async () => {
        try {
            await api.cancelStop();
            if (onRefresh) onRefresh();
        } catch (error) {
            dialog.alert("Failed to cancel shutdown: " + error.message, { title: 'Error', variant: 'destructive' });
        }
    };

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
                                <button
                                    onClick={async () => {
                                        if (isOnline) return;
                                        setTogglingMode(true);
                                        try {
                                            const r = await api.setOnlineMode(!onlineMode);
                                            setOnlineMode(r.online_mode);
                                        } catch (e) {
                                            console.error(e);
                                        }
                                        setTogglingMode(false);
                                    }}
                                    disabled={isOnline || togglingMode}
                                    title={onlineMode ? 'Requires premium Minecraft account' : 'Allows cracked/non-premium accounts'}
                                    className={`text-[9px] px-2 py-0.5 rounded-sm border uppercase tracking-wider transition-all font-medium ${
                                        onlineMode ? 'bg-white/5 border-white/10 text-zinc-400 hover:bg-white/[0.07]' : 'bg-white/[0.03] border-white/5 text-zinc-500 hover:bg-white/[0.06] hover:border-white/10'
                                    } ${isOnline ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
                                >
                                    {togglingMode ? '...' : onlineMode ? 'Premium' : 'No Premium'}
                                </button>
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

            {/* Error Banner */}
            {serverError && (
                <div className="rounded-sm border border-red-500/20 bg-red-500/5 p-4 relative overflow-hidden">
                    <div className="flex items-start gap-3">
                        <div className="p-1.5 rounded-sm bg-red-500/10 text-red-400 shrink-0 mt-0.5">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="text-xs font-minecraft tracking-wider uppercase text-red-400 mb-0.5">
                                {serverError.error === 'mod_dependency' ? 'Missing Mod Dependency' :
                                 serverError.error === 'java_version' ? 'Java Version Error' :
                                 serverError.error === 'port_conflict' ? 'Port Conflict' :
                                 serverError.error === 'out_of_memory' ? 'Out of Memory' :
                                 serverError.error === 'mod_loading' ? 'Mod Loading Error' :
                                 serverError.error === 'dns_error' ? 'DNS Error' :
                                 serverError.error === 'bedrock_tunnel' ? 'Bedrock Tunnel Error' :
                                 'Server Error'}
                            </div>
                            <div className="text-[11px] text-zinc-400 leading-relaxed">
                                {serverError.fix || 'Unknown error. Check the console for details.'}
                                {serverError.mod && <span className="text-zinc-500 ml-1">— {serverError.mod}</span>}
                            </div>
                            <div className="text-[9px] text-zinc-600 font-mono mt-1 truncate">{serverError.detail}</div>
                        </div>
                        <button onClick={() => setServerError(null)} className="p-1 rounded-sm text-zinc-500 hover:text-white hover:bg-white/5 transition-colors shrink-0">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                    </div>
                    {/* Dismiss hint */}
                    <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-red-500/[0.02] to-transparent pointer-events-none"></div>
                </div>
            )}

            {/* Tunnel Section */}
            <div className="p-4 bg-[#18181b]/60 border border-white/5 rounded-sm relative z-50 backdrop-blur-2xl">
                <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-sm border ${tunnelAddress ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/10 text-zinc-300'}`}>
                        <Terminal size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                            <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                                {tunnelAddress ? 'Public Server' : (dnsAddress ? 'Fixed Address' : 'Local Host')}
                            </div>
                            {tunnelAddress && dnsAddress && <span className="text-[8px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-sm border border-emerald-500/20 font-bold uppercase tracking-wider">ONLINE</span>}
                            {!tunnelAddress && dnsAddress && <span className="text-[8px] px-1.5 py-0.5 bg-zinc-500/10 text-zinc-500 rounded-sm border border-zinc-500/20 font-bold uppercase tracking-wider">OFFLINE</span>}
                        </div>
                        {dnsEditing ? (
                            <form onSubmit={async (e) => {
                                e.preventDefault();
                                const v = e.target.elements.sd.value.trim();
                                if (!v) { setDnsEditing(false); setDnsAvailable(null); return; }
                                let isTaken = false;
                                try {
                                    const c = await api.checkDnsSubdomain(v);
                                    if (c && !c.available && v !== dnsSubdomain) {
                                        setDnsAvailable(v);
                                        isTaken = true;
                                    }
                                } catch { /* network error, allow save */ }
                                if (!isTaken) {
                                    try {
                                        const r = await api.setDnsSubdomain(v);
                                        setDnsSubdomain(r.subdomain);
                                        setDnsAddress(r.address);
                                        setDnsEditing(false);
                                        setDnsAvailable(null);
                                    } catch(err) { console.error('Failed to set subdomain', err); }
                                }
                            }} className="mb-1">
                                <div className="flex items-center gap-1.5">
                                    <span className="text-sm font-mono text-emerald-400 font-bold select-none">🟢</span>
                                    <input name="sd" defaultValue={dnsSubdomain} placeholder="your-server-name" className="w-44 bg-[#050505] border border-emerald-500/40 rounded-sm px-2.5 py-1.5 text-sm font-mono font-bold text-emerald-400 placeholder-zinc-700 outline-none focus:border-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.15)]" autoFocus />
                                    <span className="text-xs font-mono text-zinc-600">.play.ariser.app</span>
                                    <button type="submit" className="p-1.5 rounded-sm bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/25 transition-colors">✓</button>
                                    <button type="button" onClick={() => { setDnsEditing(false); setDnsAvailable(null); }} className="p-1.5 rounded-sm text-zinc-500 hover:text-white hover:bg-white/5 transition-colors">✕</button>
                                </div>
                                {dnsAvailable && <div className="flex items-center gap-1.5 mt-1.5">
                                    <span className="text-[10px] text-red-400">&quot;{dnsAvailable}&quot; taken — try:</span>
                                    {[dnsAvailable+'-mc', dnsAvailable+'-sv', 'my-'+dnsAvailable].map(s => (
                                        <button key={s} type="button" onClick={() => { setDnsSubdomain(s); setDnsAvailable(null); }} className="text-[10px] px-1.5 py-0.5 rounded-sm bg-white/5 border border-white/10 text-zinc-400 hover:text-white hover:border-white/20 transition-colors font-mono">{s}</button>
                                    ))}
                                </div>}
                            </form>
                        ) : dnsAddress ? (
                            <div className="flex items-center gap-1.5 mb-1 group">
                                <span className="text-sm font-mono font-bold text-emerald-400 select-all cursor-default">{dnsAddress}</span>
                                <span className={`text-[9px] px-1.5 py-0.5 rounded-sm border font-bold uppercase tracking-wider ${
                                    dnsStatus === 'ok' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                                        : dnsStatus === 'error' ? 'bg-red-500/10 border-red-500/30 text-red-400'
                                            : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                                }`} title="DNS verification status">
                                    {dnsStatus === 'ok' ? 'DNS ✓' : dnsStatus === 'error' ? 'DNS ✗' : 'DNS …'}
                                </span>
                                <button onClick={() => navigator.clipboard.writeText(dnsAddress)} className="p-1 rounded-sm text-zinc-500 hover:text-white hover:bg-white/5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity" title="Copy">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                </button>
                                <button onClick={() => setDnsEditing(true)} className="p-1 rounded-sm text-zinc-600 hover:text-white hover:bg-white/5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity" title="Edit subdomain">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                                </button>
                            </div>
                        ) : null}
                        {dnsAvailable && !dnsEditing && <div className="text-[10px] text-red-400 mb-1">&quot;{dnsAvailable}&quot; is already taken — pick another name</div>}
                        {dnsStatus === 'error' && tunnelAddress && (
                            <div className="flex flex-wrap items-center gap-2 mb-1 text-[10px] text-orange-400">
                                <span>DNS failed — connect directly:</span>
                                <span className="font-mono select-all text-orange-300">{tunnelAddress}</span>
                                <button onClick={() => navigator.clipboard.writeText(tunnelAddress)} className="underline hover:text-white">copy</button>
                            </div>
                        )}
                        <div className="flex items-center gap-1.5 group">
                            {!dnsAddress ? <>
                                <span className={`text-sm font-mono font-bold leading-none select-all ${tunnelAddress ? 'text-orange-400' : 'text-white'}`}>{tunnelAddress || `${status.local_ip||'127.0.0.1'}:${status.port||'25565'}`}</span>
                                <button
                                    onClick={async () => {
                                        try {
                                            await navigator.clipboard.writeText(tunnelAddress || `${status.local_ip||'127.0.0.1'}:${status.port||'25565'}`);
                                            setAddressCopied(true);
                                            setTimeout(() => setAddressCopied(false), 1500);
                                        } catch (e) { console.error('Copy failed', e); }
                                    }}
                                    className="p-1 rounded-sm text-zinc-600 hover:text-white hover:bg-white/5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity"
                                    title="Copy address"
                                >
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                </button>
                                {addressCopied && <span className="text-[9px] font-bold uppercase tracking-widest text-emerald-400 animate-in fade-in duration-200">Copied</span>}
                            </> : null}
                        </div>
                        {(tunnelAddress||dnsAddress) && <div className="text-[9px] text-zinc-600 font-mono mt-0.5">Local {status.local_ip||'127.0.0.1'}:{status.port||'25565'}{tunnelAddress ? <span className="ml-2">via {tunnelAddress}</span> : null}</div>}
                    </div>

                    <button onClick={handleOpenFolder} className="p-2 border border-transparent bg-transparent hover:bg-white/5 text-zinc-500 hover:text-white rounded-sm transition-colors" title="Open Server Directory"><FolderOpen size={16} /></button>

                    <button onClick={async () => {
                        try {
                            if (tunnelAddress) {
                                await api.stopTunnel();
                                setTunnelAddress(null);
                                setTunnelConnecting(false);
                            } else {
                                setTunnelConnecting(true);
                                if (tunnelProvider === 'pinggy') localStorage.setItem('preferredTunnelProvider', 'pinggy');
                                await api.startTunnel(tunnelRegion, tunnelProvider);
                            }
                        } catch (err) {
                            setTunnelConnecting(false);
                            dialog.alert('Tunnel error: ' + (err.response?.data?.detail || err.message), { title: 'Tunnel Error', variant: 'destructive' });
                        }
                    }} disabled={tunnelConnecting && !tunnelAddress}
                    className={`px-5 py-2.5 rounded-sm text-xs font-minecraft font-bold uppercase tracking-widest flex items-center gap-2 transition-all ${tunnelAddress ? 'bg-transparent border border-red-500/30 text-red-400 hover:bg-red-500/10' : tunnelConnecting ? 'bg-transparent border border-yellow-500/30 text-yellow-400' : 'bg-white text-black hover:bg-zinc-200'}`}
                    >
                        {tunnelAddress ? <><Square size={14}/> Stop</> : tunnelConnecting ? <><div className="w-3.5 h-3.5 border-2 border-yellow-400/30 border-t-yellow-400 rounded-full animate-spin"/> Connecting</> : <><Globe size={14}/> Make Public</>}
                    </button>

                    <div className="relative group">
                        <button onClick={() => setShowAdvanced(!showAdvanced)} className={`p-2 rounded-sm transition-all relative ${showAdvanced ? 'bg-white/10 text-white' : 'text-zinc-600 hover:text-white hover:bg-white/5'}`}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                            {autoTunnel && <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_4px_rgba(16,185,129,0.6)]"></div>}
                        </button>
                        <div className="absolute bottom-full right-0 mb-2 w-72 p-4 bg-black/95 rounded-sm border border-white/10 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 pointer-events-none transition-opacity shadow-2xl z-50">
                            <div className="text-xs text-white font-minecraft tracking-widest uppercase mb-1">Make Public</div>
                            <div className="text-[11px] text-zinc-400 leading-relaxed">
                                Share your server worldwide. It gets a fixed address like <span className="text-emerald-400">survival.play.ariser.app</span> that never changes even when the tunnel IP rotates. DNS updates automatically.
                            </div>
                            <div className="absolute bottom-[-6px] right-4 w-3 h-3 bg-black/95 rotate-45 border-r border-b border-white/10"></div>
                        </div>
                    </div>
                </div>

                {showAdvanced && <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-white/5">
                    <span className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Provider</span>
                        <div className="w-24 rounded-sm border border-white/10 bg-white/5">
                            <Select value={tunnelProvider} onChange={() => {}} options={[{ value: 'pinggy', label: 'Pinggy' }]} />
                        </div>
                    {tunnelProvider === 'pinggy' && <><span className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Region</span><div className="w-20 rounded-sm border border-white/10 bg-white/5"><Select value={tunnelRegion} onChange={setTunnelRegion} options={[{ value: 'eu', label: 'EU' }, { value: 'us', label: 'US' }, { value: 'ap', label: 'Asia' }]} /></div></>}
                    <div className="w-px h-6 bg-white/5"></div>
                    <button onClick={() => { const v = !autoTunnel; setAutoTunnel(v); localStorage.setItem('autoTunnel', v.toString()); }} className={`flex items-center gap-1.5 px-2 py-1 rounded-sm border text-[10px] font-bold uppercase tracking-wider transition-all ${autoTunnel ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'border-white/10 text-zinc-600 hover:text-white'}`}><div className={`w-1.5 h-1.5 rounded-full ${autoTunnel ? 'bg-emerald-400' : 'bg-zinc-600'}`}/> Auto-Tunnel</button>
                    <span className="text-[10px] text-zinc-600 font-bold" title="DNS records used / zone limit (Cloudflare Free = 200)">
                        DNS: {dnsUsage && dnsUsage.used != null ? (
                            <span className={
                                dnsUsage.used / (dnsUsage.capacity || 1) > 0.9 ? 'text-red-400'
                                    : dnsUsage.used / (dnsUsage.capacity || 1) > 0.7 ? 'text-yellow-400'
                                        : 'text-emerald-400'
                            }>{dnsUsage.used}/{dnsUsage.capacity}</span>
                        ) : <span className="text-emerald-400">ON</span>}
                    </span>
                    {tunnelAddress && <span className="text-[10px] text-zinc-500 italic w-full">Region changes apply the next time you start the tunnel.</span>}
                    <button
                        onClick={async () => {
                            setDnsStatus('checking');
                            try {
                                const r = await api.verifyDns();
                                if (r.verified) {
                                    setDnsStatus('ok');
                                    dialog.alert(`DNS OK: ${r.address}${r.note ? ` (${r.note})` : ''}`, { title: 'DNS Verified', variant: 'success' });
                                } else {
                                    setDnsStatus('error');
                                    dialog.alert('DNS verification failed: ' + (r.error || r.detail?.error || 'unknown'), { title: 'DNS Error', variant: 'destructive' });
                                }
                            } catch (e) {
                                setDnsStatus('error');
                                dialog.alert('DNS verification error: ' + (e.message || e), { title: 'DNS Error', variant: 'destructive' });
                            }
                        }}
                        className="px-2 py-1 rounded-sm border border-white/10 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-white hover:bg-white/5 transition-all"
                        title="Check that the custom address actually resolves"
                    >
                        Verify DNS
                    </button>
                    <button
                        onClick={async () => {
                            try {
                                const r = await api.cleanupDns();
                                dialog.alert(`DNS cleanup: removed ${r.deleted ?? 0} stale record(s).`, { title: 'DNS Cleanup', variant: 'success' });
                            } catch (e) {
                                dialog.alert('DNS cleanup failed: ' + (e.message || e), { title: 'DNS Cleanup', variant: 'destructive' });
                            }
                        }}
                        className="px-2 py-1 rounded-sm border border-white/10 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-white hover:bg-white/5 transition-all"
                        title="Remove SRV records this app created but no longer uses"
                    >
                        Clean DNS
                    </button>
                </div>}
            </div>

            {/* Bedrock / GeyserMC Crossplay Section */}
            {geyserInfo.installed ? (
                <div className="p-4 bg-[#18181b]/60 border border-white/5 rounded-sm relative z-40 backdrop-blur-2xl">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-4 min-w-0">
                            <div className={`p-2 rounded-sm border ${bedrockAddress ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400' : 'bg-white/5 border-white/10 text-zinc-300'}`}>
                                <Zap size={16} />
                            </div>
                            <div className="min-w-0">
                                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                                    <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest font-minecraft">
                                        Bedrock Crossplay
                                    </span>
                                    <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-bold uppercase tracking-wider">
                                        GeyserMC
                                    </span>
                                    {geyserInfo.floodgate_installed && (
                                        <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-purple-500/10 border border-purple-500/20 text-purple-300 font-bold uppercase tracking-wider" title="Floodgate allows Bedrock players to join without needing a Java account">
                                            Floodgate Active
                                        </span>
                                    )}
                                    {bedrockAddress ? (
                                        <span className="text-[8px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-sm border border-emerald-500/20 font-bold uppercase tracking-wider">
                                            ONLINE (UDP)
                                        </span>
                                    ) : (
                                        <span className="text-[8px] px-1.5 py-0.5 bg-zinc-500/10 text-zinc-500 rounded-sm border border-zinc-500/20 font-bold uppercase tracking-wider">
                                            OFFLINE
                                        </span>
                                    )}
                                </div>

                                {bedrockAddress ? (
                                    <div className="space-y-1 mt-1">
                                        <div className="flex flex-wrap items-center gap-3">
                                            <div className="flex items-center gap-1.5 bg-black/40 border border-white/10 px-2.5 py-1 rounded-sm">
                                                <span className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold">Address:</span>
                                                <span className="text-xs font-mono font-bold text-cyan-300 select-all">
                                                    {bedrockAddress.includes(':') ? bedrockAddress.split(':')[0] : bedrockAddress}
                                                </span>
                                                <button
                                                    onClick={() => navigator.clipboard.writeText(bedrockAddress.includes(':') ? bedrockAddress.split(':')[0] : bedrockAddress)}
                                                    className="p-1 hover:text-white text-zinc-500 transition-colors"
                                                    title="Copy Server Address"
                                                >
                                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                                </button>
                                            </div>
                                            <div className="flex items-center gap-1.5 bg-black/40 border border-white/10 px-2.5 py-1 rounded-sm">
                                                <span className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold">Port:</span>
                                                <span className="text-xs font-mono font-bold text-emerald-400 select-all">
                                                    {bedrockAddress.includes(':') ? bedrockAddress.split(':')[1] : '19132'}
                                                </span>
                                                <button
                                                    onClick={() => navigator.clipboard.writeText(bedrockAddress.includes(':') ? bedrockAddress.split(':')[1] : '19132')}
                                                    className="p-1 hover:text-white text-zinc-500 transition-colors"
                                                    title="Copy Port"
                                                >
                                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                                </button>
                                            </div>
                                        </div>
                                        <div className="text-[10px] text-zinc-500">
                                            Bedrock players enter Address &amp; Port into <span className="text-zinc-400">Play &gt; Servers &gt; Add Server</span>
                                        </div>
                                        <div className="text-[10px] text-amber-500/80">
                                            Free Pinggy tunnels expire after ~60 min — restart the tunnel to renew it.
                                        </div>
                                    </div>
                                ) : (
                                    <div className="text-[11px] text-zinc-400 mt-0.5">
                                        Local UDP Port: <span className="font-mono text-zinc-300">{geyserInfo.bedrock_port || 19132}</span>. Share server with iOS, Android, Windows Bedrock &amp; Consoles.
                                    </div>
                                )}
                            </div>
                        </div>

                        <button
                            onClick={async () => {
                                try {
                                    if (bedrockAddress) {
                                        await api.stopBedrockTunnel();
                                        setBedrockAddress(null);
                                        setBedrockConnecting(false);
                                    } else {
                                        setBedrockConnecting(true);
                                        await api.startBedrockTunnel(tunnelRegion);
                                    }
                                } catch (err) {
                                    setBedrockConnecting(false);
                                    setServerError({
                                        error: 'bedrock_tunnel',
                                        fix: 'Could not start the Bedrock tunnel. Check the console for details.',
                                        detail: err.response?.data?.detail || err.message,
                                    });
                                }
                            }}
                            disabled={bedrockConnecting && !bedrockAddress}
                            className={`px-4 py-2 rounded-sm text-xs font-minecraft font-bold uppercase tracking-widest flex items-center gap-2 transition-all flex-shrink-0 ${
                                bedrockAddress
                                    ? 'bg-transparent border border-red-500/30 text-red-400 hover:bg-red-500/10'
                                    : bedrockConnecting
                                        ? 'bg-transparent border border-yellow-500/30 text-yellow-400'
                                        : 'bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/30'
                            }`}
                        >
                            {bedrockAddress ? (
                                <><Square size={12} /> Stop Bedrock</>
                            ) : bedrockConnecting ? (
                                <><div className="w-3 h-3 border-2 border-yellow-400/30 border-t-yellow-400 rounded-full animate-spin" /> Connecting</>
                            ) : (
                                <><Zap size={12} /> Enable Bedrock</>
                            )}
                        </button>
                    </div>
                </div>
            ) : (
                <div className="p-3 bg-white/[0.02] border border-white/5 rounded-sm flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="p-1.5 rounded-sm bg-white/5 border border-white/10 text-zinc-400">
                            <Zap size={14} />
                        </div>
                        <div>
                            <div className="text-xs font-bold text-zinc-300 font-minecraft">
                                Bedrock &amp; Console Crossplay
                            </div>
                            <div className="text-[10px] text-zinc-500">
                                Want iOS, Android, PlayStation, Xbox, Switch &amp; Windows Bedrock players to join? Install GeyserMC in Plugins.
                            </div>
                        </div>
                    </div>
                    {onNavigate && (
                        <button
                            onClick={() => onNavigate('plugins')}
                            className="px-3 py-1.5 rounded-sm border border-white/10 bg-white/5 hover:bg-white/10 text-[10px] font-minecraft text-white tracking-widest uppercase transition-all flex-shrink-0"
                        >
                            Get GeyserMC
                        </button>
                    )}
                </div>
            )}

            {/* Stats Grid */}

            <div className="grid grid-cols-1 md:grid-cols-4 gap-5 relative z-10">
                <StatCard icon={Users} label={t('dashboard.players_online')} value={onlineCount !== undefined ? `${onlineCount}` : '-'} sublabel={`/ ${status.max_players || 20} ${t('status.online')}`} />
                <StatCard icon={Cpu} label={t('dashboard.cpu_usage')} value={status.cpu !== undefined ? `${status.cpu}%` : '--'} sublabel={t('dashboard.cpu_sub')} data={history.cpu} active={active} />
                <StatCard icon={HardDrive} label={t('dashboard.ram_usage')} value={status.ram || '--'} sublabel={t('dashboard.ram_sub')} data={history.ram} active={active} />
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
                            const timeStr = log.time ? (log.time.includes(':') ? log.time : new Date(log.time).toTimeString().slice(0, 5)) : '';
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

                        setLocalLogs(prev => {
                            const next = [...prev, { message: `> ${input}`, level: 'input' }];
                            return next.length > MAX_MINI_LOGS ? next.slice(next.length - MAX_MINI_LOGS) : next;
                        });

                        try {
                            if (isConnected) {
                                send(input);
                            } else {
                                await api.sendCommand(input);
                            }
                            e.target.elements.cmd.value = '';
                        } catch (err) {
                            setLocalLogs(prev => {
                                const next = [...prev, { message: `Error: ${err.message}`, level: 'error', time: new Date().toLocaleTimeString([], { hour12: false }) }];
                                return next.length > MAX_MINI_LOGS ? next.slice(next.length - MAX_MINI_LOGS) : next;
                            });
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
        </div>
    );
}

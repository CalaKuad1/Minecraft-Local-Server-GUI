import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Play, Square, Activity, Cpu, HardDrive, X, ExternalLink, FolderOpen, Users, Terminal, Clock, Globe, Zap, Copy, Pencil, Check, Settings as SettingsIcon } from './ui/PixelIcons';
import { AnimatePresence } from 'framer-motion';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { api } from '../api';
import { Select } from './ui/Select';
import { Modal } from './ui/Modal';
import { Button, IconButton } from './ui/Button';
import { Badge } from './ui/Badge';
import Cubi from './ui/Cubi';
import { useToast } from './ui/toastContext';
import { useTranslation } from '../contexts/LanguageContext';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useDialog } from './ui/DialogContext';

const StatCard = ({ icon: Icon, label, value, sublabel, data = [], active = true }) => {
    return (
        <div className="bg-panel/60 border border-white/5 rounded-sm p-4 flex flex-col transition-colors group cursor-default hover:border-white/10 relative overflow-hidden h-[92px] min-w-0">
            <div className="flex items-center gap-2 mb-3 relative z-10">
                <Icon size={14} className="text-ink-faint group-hover:text-gray-300 transition-colors" />
                <h3 className="text-ink-faint text-xs font-bold uppercase tracking-widest">{label}</h3>
            </div>
            <div className="text-2xl font-minecraft text-white tracking-tight leading-none mb-1 mt-auto relative z-10 tabular-nums">{value}</div>
            <div className="text-[10px] text-ink-faint font-bold uppercase tracking-widest relative z-10">{sublabel}</div>

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

// Schedule-shutdown modal.
const ShutdownTimerModal = ({ onClose, onSchedule, onCancel, activeTimer, t }) => {
    const [minutes, setMinutes] = useState(15);
    const isActive = activeTimer?.scheduled;
    const remaining = isActive ? Math.max(0, Math.ceil((activeTimer.remaining_seconds || 0) / 60)) : 0;
    const presets = [5, 15, 30, 60];

    return (
        <Modal
            size="md"
            icon={Clock}
            iconClassName="text-gold"
            title={t('dashboard.shutdown_timer.title')}
            description={t('dashboard.shutdown_timer.desc')}
            onClose={onClose}
            footer={isActive ? (
                <Button variant="danger" data-autofocus onClick={() => { onCancel(); onClose(); }}>
                    {t('dashboard.shutdown_timer.cancel')}
                </Button>
            ) : (
                <>
                    <Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
                    <Button variant="primary" onClick={() => { onSchedule(minutes); onClose(); }}>
                        {t('dashboard.shutdown_timer.start')}
                    </Button>
                </>
            )}
        >
            {isActive ? (
                <div className="py-4 text-center" role="timer">
                    <div className="mb-1 text-sm text-gold">{t('dashboard.shutdown_timer.timer_active')}</div>
                    <div className="font-minecraft text-4xl text-ink">
                        {remaining} <span className="text-lg text-ink-faint">{t('dashboard.shutdown_timer.minutes')}</span>
                    </div>
                </div>
            ) : (
                <div className="space-y-5">
                    <div role="group" aria-labelledby="shutdown-presets">
                        <div id="shutdown-presets" className="mb-2 text-sm text-ink-dim">{t('dashboard.shutdown_timer.presets')}</div>
                        <div className="grid grid-cols-4 gap-2">
                            {presets.map(p => (
                                <Button
                                    key={p}
                                    size="sm"
                                    variant={minutes === p ? 'primary' : 'secondary'}
                                    aria-pressed={minutes === p}
                                    onClick={() => setMinutes(p)}
                                >
                                    {p}m
                                </Button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <label htmlFor="shutdown-minutes" className="mb-2 block text-sm text-ink-dim">{t('dashboard.shutdown_timer.set_duration')}</label>
                        <div className="flex items-center gap-3">
                            <input
                                id="shutdown-minutes"
                                data-autofocus
                                type="number" min="1" value={minutes}
                                onChange={(e) => setMinutes(Math.max(1, parseInt(e.target.value || '1', 10) || 1))}
                                className="h-10 flex-1 rounded-sm border border-white/10 bg-ground px-4 font-mono text-ink outline-none transition-colors focus:border-diamond"
                            />
                            <span className="text-sm text-ink-faint">{t('dashboard.shutdown_timer.minutes')}</span>
                        </div>
                    </div>
                </div>
            )}
        </Modal>
    );
};

const STATUS_PRIORITY = { offline: 0, starting: 1, stopping: 2, online: 3 };

export default function Dashboard({ status: serverStatus, onRefresh, active = true, onNavigate, autoStart = false, onAutoStartHandled }) {
    const { t } = useTranslation();
    const { isConnected, subscribe, send } = useWebSocket();
    const dialog = useDialog();
    const toast = useToast();

    // Local state for immediate UI feedback
    const [localStatus, setLocalStatus] = useState(serverStatus?.status || 'offline');
    const [localLogs, setLocalLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [showShutdownModal, setShowShutdownModal] = useState(false);
    const [shutdownInfo, setShutdownInfo] = useState({ scheduled: false });
    const [tunnelAddress, setTunnelAddress] = useState(null);
    const [runningProvider, setRunningProvider] = useState(null);
    const [tunnelConnecting, setTunnelConnecting] = useState(false);
    const [tunnelRegion, setTunnelRegion] = useState('eu');
    // playit.gg = permanent address once linked; Pinggy = temporary fallback.
    const [tunnelProvider, setTunnelProvider] = useState(localStorage.getItem('preferredTunnelProvider') || 'playit');
    const [playit, setPlayit] = useState({ supported: false, linked: false, linking: false, claim_url: null });
    const activeProvider = tunnelProvider === 'playit' && playit.linked ? 'playit' : 'pinggy';
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
    const [shareCopied, setShareCopied] = useState(false);
    const [switchingToPlayit, setSwitchingToPlayit] = useState(false);
    const tunnelActiveRef = useRef(false);
    const tunnelRegionRef = useRef(tunnelRegion);
    const autoStartedRef = useRef(false);

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
                    setRunningProvider(serverStatus.tunnel.provider || null);
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

    useEffect(() => { tunnelActiveRef.current = !!tunnelAddress; }, [tunnelAddress]);
    useEffect(() => { tunnelRegionRef.current = tunnelRegion; }, [tunnelRegion]);
    const activeProviderRef = useRef(activeProvider);
    useEffect(() => { activeProviderRef.current = activeProvider; }, [activeProvider]);

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
            try { if (lastIdRef.current) localStorage.setItem(`lastTunnelAddress:${lastIdRef.current}`, item.address); } catch { /* optional */ }
            setTunnelConnecting(false);
            setSwitchingToPlayit(false);
            return;
        }
        if (item.type === 'tunnel_disconnected') {
            setTunnelAddress(null);
            setTunnelConnecting(false);
            return;
        }
        if (item.type === 'playit_linked') {
            setPlayit(p => ({ ...p, linked: true, linking: false, claim_url: null }));
            setTunnelProvider('playit');
            localStorage.setItem('preferredTunnelProvider', 'playit');
            toast.success(t('dashboard.tunnel.playit_linked'));
            // A temporary Pinggy tunnel is running: swap it for the permanent
            // address right away instead of waiting for the next start.
            if (tunnelActiveRef.current) {
                setSwitchingToPlayit(true);
                setTunnelConnecting(true);
                api.startTunnel(tunnelRegionRef.current, 'playit').catch((err) => {
                    setSwitchingToPlayit(false);
                    setTunnelConnecting(false);
                    toast.error(err.response?.data?.detail || err.message, { title: t('dashboard.tunnel.error_title') });
                });
            }
            return;
        }
        if (item.type === 'playit_error') {
            // e.g. the free playit account is over its agent limit: explain it
            // and fall back to a temporary Pinggy address so friends can still join.
            toast.error(t('dashboard.tunnel.playit_over_limit').replace('{url}', item.url || 'playit.gg/account/agents'), {
                title: t('dashboard.tunnel.playit_unavailable'),
                duration: 15000,
            });
            setSwitchingToPlayit(false);
            setTunnelConnecting(true);
            api.startTunnel(tunnelRegionRef.current, 'pinggy').catch(() => setTunnelConnecting(false));
            return;
        }
        if (item.type === 'playit_link_failed') {
            setPlayit(p => ({ ...p, linking: false, claim_url: null }));
            toast.error(item.error, { title: t('dashboard.tunnel.playit_link_failed') });
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
    }, [onRefresh, appendLocalLog, t, toast]);

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

    // playit.gg link state (polled faster while waiting for browser approval)
    useEffect(() => {
        let cancelled = false;
        const refresh = async () => {
            try {
                const s = await api.getPlayitStatus();
                if (!cancelled && s) setPlayit(s);
            } catch (e) { }
        };
        refresh();
        const interval = setInterval(refresh, playit.linking ? 3000 : 30000);
        return () => { cancelled = true; clearInterval(interval); };
    }, [playit.linking]);

    const handleLinkPlayit = async () => {
        try {
            const r = await api.linkPlayit();
            setPlayit(p => ({ ...p, linking: true, claim_url: r?.claim_url || null }));
        } catch (err) {
            toast.error(err.response?.data?.detail || err.message, { title: t('dashboard.tunnel.playit_link_failed') });
        }
    };

    const handleCancelPlayitLink = async () => {
        try { await api.cancelPlayitLink(); } catch (e) { }
        setPlayit(p => ({ ...p, linking: false, claim_url: null }));
    };

    const handleUnlinkPlayit = async () => {
        const ok = await dialog.confirm(t('dashboard.tunnel.playit_unlink_confirm'), {
            title: t('dashboard.tunnel.playit_unlink'),
            variant: 'destructive',
            confirmLabel: t('dashboard.tunnel.playit_unlink'),
            cancelLabel: t('common.cancel'),
        });
        if (!ok) return;
        try {
            await api.unlinkPlayit();
            setPlayit(p => ({ ...p, linked: false }));
        } catch (err) {
            toast.error(err.response?.data?.detail || err.message, { title: t('dashboard.tunnel.error_title') });
        }
    };

    // Tunnel Polling
    useEffect(() => {
        const checkTunnel = async () => {
            try {
                const status = await api.getTunnelStatus();
                if (status.active && status.address) {
                    setTunnelAddress(status.address);
                    setRunningProvider(status.provider || null);
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
                // Open the tunnel together with the server: it only forwards a
                // local port, so it doesn't need to wait for the world to load.
                setTunnelConnecting(true);
                (async () => {
                    let provider = activeProviderRef.current;
                    try {
                        // playit's link status may not have loaded yet (e.g. right after the wizard).
                        const ps = await api.getPlayitStatus();
                        const preferred = localStorage.getItem('preferredTunnelProvider') || 'playit';
                        provider = preferred === 'playit' && ps?.linked ? 'playit' : 'pinggy';
                    } catch { /* keep the known provider */ }
                    try {
                        await api.startTunnel(tunnelRegionRef.current, provider);
                    } catch (e) { setTunnelConnecting(false); }
                })();
            }
            if (onRefresh) onRefresh();
        } catch (e) {
            setLocalStatus('offline');
            setLoading(false);
        }
    };

    // Right after the setup wizard: start the new server (and, through
    // autoTunnel, its public address) without making the user hunt for buttons.
    useEffect(() => {
        if (!autoStart) { autoStartedRef.current = false; return; }
        if (autoStartedRef.current) return;
        if (!serverStatus?.server_id || localStatus !== 'offline') return;
        autoStartedRef.current = true;
        if (onAutoStartHandled) onAutoStartHandled();
        handleStart();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoStart, serverStatus?.server_id, localStatus]);

    const startPublicTunnel = async () => {
        try {
            setTunnelConnecting(true);
            await api.startTunnel(tunnelRegion, activeProvider);
        } catch (err) {
            setTunnelConnecting(false);
            toast.error(err.response?.data?.detail || err.message, { title: t('dashboard.tunnel.error_title') });
        }
    };

    const shareAddress = tunnelAddress ? ((dnsAddress && dnsStatus !== 'error') ? dnsAddress : tunnelAddress) : null;
    const shareVisible = isOnline || isStarting;
    // While the tunnel connects, show the address we already know will be used:
    // the fixed subdomain, or the last permanent playit address of this server.
    const expectedAddress = (() => {
        if (dnsAddress && dnsStatus !== 'error') return dnsAddress;
        if (activeProvider !== 'playit') return null; // Pinggy addresses change every time
        try { return localStorage.getItem(`lastTunnelAddress:${status.server_id}`); } catch { return null; }
    })();
    const shownAddress = shareAddress || ((tunnelConnecting || switchingToPlayit) ? expectedAddress : null);
    const addressPending = !shareAddress && !!shownAddress;

    const stopPublicTunnel = async () => {
        try {
            await api.stopTunnel();
            setTunnelAddress(null);
            setTunnelConnecting(false);
        } catch (err) {
            toast.error(err.response?.data?.detail || err.message, { title: t('dashboard.tunnel.error_title') });
        }
    };

    // Tunnel controls shown inside the share card while the server runs.
    const tunnelToolbar = (
        <div className="flex shrink-0 items-center gap-1">
            <IconButton
                label={t('dashboard.tunnel.options')}
                icon={SettingsIcon}
                size={16}
                tone={showAdvanced ? 'active' : 'default'}
                aria-expanded={showAdvanced}
                onClick={() => setShowAdvanced(v => !v)}
                className="h-9 w-9"
            />
            {tunnelAddress && (
                <IconButton label={t('dashboard.tunnel.stop')} icon={Square} size={16} onClick={stopPublicTunnel} className="h-9 w-9" />
            )}
        </div>
    );
    const serverVersion = status.version || status.minecraft_version || '';

    const copyShareAddress = async () => {
        try {
            await navigator.clipboard.writeText(shownAddress);
            setShareCopied(true);
            setTimeout(() => setShareCopied(false), 2000);
        } catch (e) { console.error('Copy failed', e); }
    };

    const handleStop = async () => {
        // If already stopping, second click is a Force Kill
        if (isStopping) {
            const ok = await dialog.confirm(
                t('dashboard.force_stop_confirm', 'Server is not responding. Force close immediately? (Unsaved progress may be lost)'),
                { title: t('dashboard.force_kill_title'), variant: 'destructive', confirmLabel: t('dashboard.force_kill'), cancelLabel: t('common.cancel') }
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
            toast.error(error.message, { title: t('dashboard.tunnel.shutdown_fail') });
        }
    };

    const handleCancelShutdown = async () => {
        try {
            await api.cancelStop();
            if (onRefresh) onRefresh();
        } catch (error) {
            toast.error(error.message, { title: t('dashboard.tunnel.shutdown_cancel_fail') });
        }
    };

    return (
        <div className="flex flex-col h-full min-h-0 animate-in fade-in duration-200">
            <div className="space-y-3 flex-none">
                {/* Header & Controls */}
                <div className="flex items-center justify-between px-5 py-4 bg-panel/60 border border-white/5 shadow-sm relative overflow-hidden backdrop-blur-2xl rounded-sm">
                    <div className="relative z-10 flex items-center gap-4">
                        <div className={`w-3 h-3 rounded-sm ${isOnline ? 'bg-grass' : (isStarting || isStopping) ? 'bg-gold animate-pulse' : 'bg-ink-faint'}`} aria-hidden="true"></div>
                        <div>
                            <div className="flex items-center gap-2 mb-0.5">
                                <span className={`text-sm font-semibold ${isOnline ? 'text-grass-lit' : (isStarting || isStopping) ? 'text-gold' : 'text-ink-dim'}`}>
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
                                    title={onlineMode ? t('dashboard.premium_hint') : t('dashboard.no_premium_hint')}
                                    className={`text-xs px-2 py-0.5 rounded-sm border font-semibold transition-colors ${
                                        onlineMode ? 'bg-white/5 border-white/10 text-ink-dim hover:bg-white/10' : 'bg-gold/10 border-gold/30 text-gold hover:bg-gold/15'
                                    } ${isOnline ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                                >
                                    {togglingMode ? '…' : onlineMode ? t('dashboard.premium') : t('dashboard.no_premium')}
                                </button>
                            </div>
                            <h2 className="text-2xl font-minecraft text-white tracking-wide truncate max-w-md" title={status.name || undefined}>
                                {status.name || 'Minecraft Server'}
                            </h2>
                            <p className="mt-0.5 text-sm capitalize text-ink-dim">
                                {status.server_type ? `${status.server_type} ${status.version || status.minecraft_version || ''}` : t('status.not_configured')}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3 relative z-10">
                        {!isOnline && !isStarting && !isStopping && (
                            <Button variant="primary" size="lg" icon={Play} onClick={handleStart} loading={loading}>
                                {t('dashboard.start')}
                            </Button>
                        )}

                        {(isOnline || isStarting || isStopping) && (
                            <Button
                                variant={isStopping ? 'danger' : 'secondary'}
                                size="lg"
                                icon={Square}
                                onClick={handleStop}
                                disabled={loading || (!isOnline && !isStarting && !isStopping)}
                                className={isStopping ? 'animate-pulse' : undefined}
                            >
                                {isStopping ? t('dashboard.force_kill') : t('dashboard.stop')}
                            </Button>
                        )}
                        
                        {/* Scheduled Shutdown Button/Badge */}
                        {isOnline && (
                            <div className="relative">
                                <IconButton
                                    label={t('dashboard.shutdown_timer.title')}
                                    icon={Clock}
                                    tone={shutdownInfo.scheduled ? 'active' : 'default'}
                                    onClick={() => setShowShutdownModal(true)}
                                    className={`h-10 w-10 border ${shutdownInfo.scheduled ? 'border-gold/50 text-gold' : 'border-white/10'}`}
                                />
                                {shutdownInfo.scheduled && (
                                    <div className="absolute -top-2 -right-2 bg-gold text-black text-xs font-bold px-1.5 py-0.5 rounded-sm border border-black shadow-sm pointer-events-none">
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
                            role="switch"
                            aria-checked={autoRestart}
                            title={t('dashboard.auto_restart')}
                            className={`h-10 px-3 flex items-center gap-2 rounded-sm border text-sm font-semibold transition-colors ${
                                autoRestart
                                    ? 'bg-grass/10 border-grass/40 text-grass-lit hover:bg-grass/20'
                                    : 'border-white/10 text-ink-dim hover:text-white hover:bg-white/5'
                            }`}
                        >
                            <div className={`h-2 w-2 rounded-sm ${autoRestart ? 'bg-grass' : 'bg-ink-faint'}`} aria-hidden="true" />
                            {t('dashboard.auto')}
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
                                {['mod_dependency', 'java_version', 'port_conflict', 'out_of_memory', 'mod_loading', 'dns_error', 'bedrock_tunnel'].includes(serverError.error)
                                    ? t(`dashboard.errors.${serverError.error}`)
                                    : t('dashboard.errors.generic')}
                            </div>
                            <div className="text-[11px] text-zinc-400 leading-relaxed">
                                {serverError.fix || t('dashboard.errors.unknown_fix')}
                                {serverError.mod && <span className="text-ink-faint ml-1">— {serverError.mod}</span>}
                            </div>
                            <div className="text-[9px] text-ink-faint font-mono mt-1 truncate">{serverError.detail}</div>
                        </div>
                        <button onClick={() => setServerError(null)} aria-label={t('dashboard.errors.dismiss')} className="p-1 rounded-sm text-ink-faint hover:text-white hover:bg-white/5 transition-colors shrink-0">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                    </div>
                    {/* Dismiss hint */}
                    <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-red-500/[0.02] to-transparent pointer-events-none"></div>
                </div>
            )}

            {/* Share card: the one thing a new user needs once the server runs */}
            {(isOnline || isStarting) && (
                <div className={`p-5 rounded-sm border backdrop-blur-2xl ${shownAddress ? 'bg-emerald-500/[0.06] border-emerald-500/30' : 'bg-panel/60 border-white/5'}`}>
                    {shownAddress ? (
                        <>
                            <div className="flex items-start gap-4">
                                <Cubi mood={addressPending ? 'busy' : 'happy'} size={44} className="shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <h3 className="text-base font-display font-semibold text-white">{t('dashboard.share.ready_title')}</h3>
                                    <div className="mt-1 flex flex-wrap items-center gap-3">
                                        <span className={`text-2xl font-mono font-bold select-all break-all ${addressPending ? 'text-emerald-300/60' : 'text-emerald-300'}`}>{shownAddress}</span>
                                        <Button variant="primary" size="sm" icon={shareCopied ? Check : Copy} onClick={copyShareAddress} aria-live="polite">
                                            {shareCopied ? t('dashboard.share.copied') : t('dashboard.share.copy')}
                                        </Button>
                                        {addressPending && (
                                            <span className="inline-flex items-center gap-1.5 rounded-full bg-gold/10 px-2.5 py-0.5 text-xs font-medium text-gold">
                                                <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
                                                {t('dashboard.share.connecting_pill')}
                                            </span>
                                        )}
                                    </div>
                                    <p className="mt-2 text-sm text-ink-dim">
                                        {t('dashboard.share.how_to')}
                                        {serverVersion && <span className="text-ink-faint"> {t('dashboard.share.version_note').replace('{version}', serverVersion)}</span>}
                                    </p>
                                </div>
                                {tunnelToolbar}
                            </div>
                            {switchingToPlayit ? (
                                <p className="mt-3 text-xs text-gold">{t('dashboard.share.switching')}</p>
                            ) : (runningProvider || activeProvider) === 'playit' ? (
                                <p className="mt-3 text-xs text-emerald-400/80">{t('dashboard.share.permanent')}</p>
                            ) : (
                                <div className="mt-3 pt-3 border-t border-white/5 flex flex-wrap items-center gap-3">
                                    <Clock size={14} className="shrink-0 text-gold" aria-hidden="true" />
                                    <span className="text-xs text-gold flex-1 min-w-[12rem]">{shareAddress === dnsAddress ? t('dashboard.share.time_limit') : t('dashboard.share.temporary')}</span>
                                    {playit.supported && !playit.linked && (playit.linking ? <>
                                        <span className="text-xs text-ink-dim">{t('dashboard.share.upgrade_waiting')}</span>
                                        <Button size="sm" variant="secondary" onClick={handleLinkPlayit}>{t('dashboard.tunnel.playit_reopen')}</Button>
                                        <Button size="sm" variant="ghost" onClick={handleCancelPlayitLink}>{t('common.cancel')}</Button>
                                    </> : (
                                        <Button size="sm" variant="primary" icon={Zap} onClick={handleLinkPlayit}>{t('dashboard.share.upgrade')}</Button>
                                    ))}
                                </div>
                            )}
                        </>
                    ) : (tunnelConnecting || switchingToPlayit) ? (
                        <div className="flex items-center gap-3">
                            <Globe size={18} className="text-emerald-400 animate-pulse shrink-0" />
                            <div>
                                <h3 className="text-base font-semibold text-white">{t('dashboard.share.connecting_title')}</h3>
                                <p className="text-sm text-ink-dim">{t('dashboard.share.connecting_desc')}</p>
                            </div>
                        </div>
                    ) : isStarting ? (
                        <div className="flex items-center gap-3">
                            <Activity size={18} className="text-gold animate-pulse shrink-0" />
                            <div>
                                <h3 className="text-base font-semibold text-white">{t('dashboard.share.starting_title')}</h3>
                                <p className="text-sm text-ink-dim">{t('dashboard.share.starting_desc')}</p>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-wrap items-center gap-3">
                            <Globe size={18} className="text-ink-dim shrink-0" />
                            <div className="flex-1 min-w-[14rem]">
                                <h3 className="text-base font-semibold text-white">{t('dashboard.share.private_title')}</h3>
                                <p className="text-sm text-ink-dim">{t('dashboard.share.private_desc')}</p>
                            </div>
                            <Button variant="primary" icon={Globe} onClick={startPublicTunnel}>{t('dashboard.tunnel.make_public')}</Button>
                            {tunnelToolbar}
                        </div>
                    )}
                </div>
            )}

            {/* Tunnel Section: the address card while the server is off; once it
                runs, the share card above takes over and only the options panel
                (opened from its gear) shows here. */}
            {(!shareVisible || showAdvanced) && (
            <div className="p-4 bg-panel/60 border border-white/5 rounded-sm relative z-50 backdrop-blur-2xl">
                {!shareVisible && (
                <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-sm border ${tunnelAddress ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/10 text-zinc-300'}`}>
                        <Terminal size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                            <div className="text-sm text-ink-dim">
                                {tunnelAddress ? t('dashboard.tunnel.public_server') : (dnsAddress ? t('dashboard.tunnel.fixed_address') : t('dashboard.tunnel.local_address'))}
                            </div>
                            {tunnelAddress && dnsAddress && <Badge tone="grass" dot>{t('status.online')}</Badge>}
                            {!tunnelAddress && dnsAddress && <Badge>{t('status.offline')}</Badge>}
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
                                    <input name="sd" aria-label={t('dashboard.tunnel.edit_subdomain')} defaultValue={dnsSubdomain} placeholder="your-server-name" className="w-44 bg-ground border border-grass/40 rounded-sm px-2.5 py-1.5 text-sm font-mono font-bold text-grass-lit placeholder-ink-faint outline-none focus:border-grass" autoFocus />
                                    <span className="text-xs font-mono text-ink-faint">.play.ariser.app</span>
                                    <IconButton type="submit" label={t('common.save')} icon={Check} tone="active" />
                                    <IconButton label={t('common.cancel')} icon={X} onClick={() => { setDnsEditing(false); setDnsAvailable(null); }} />
                                </div>
                                {dnsAvailable && <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                                    <span className="text-xs text-redstone">&quot;{dnsAvailable}&quot; {t('dashboard.tunnel.taken_try')}</span>
                                    {[dnsAvailable+'-mc', dnsAvailable+'-sv', 'my-'+dnsAvailable].map(s => (
                                        <button key={s} type="button" onClick={() => { setDnsSubdomain(s); setDnsAvailable(null); }} className="text-xs px-1.5 py-0.5 rounded-sm bg-white/5 border border-white/10 text-ink-dim hover:text-white hover:border-white/20 transition-colors font-mono">{s}</button>
                                    ))}
                                </div>}
                            </form>
                        ) : dnsAddress ? (
                            <div className="flex items-center gap-1.5 mb-1 group">
                                <span className="text-sm font-mono font-bold text-grass-lit select-all cursor-default">{dnsAddress}</span>
                                <Badge tone={dnsStatus === 'ok' ? 'grass' : dnsStatus === 'error' ? 'redstone' : 'gold'} title={t('dashboard.tunnel.dns_status')}>
                                    {dnsStatus === 'ok' ? 'DNS ✓' : dnsStatus === 'error' ? 'DNS ✗' : 'DNS …'}
                                </Badge>
                                <IconButton
                                    label={t('dashboard.tunnel.copy')}
                                    icon={Copy}
                                    size={14}
                                    onClick={() => navigator.clipboard.writeText(dnsAddress).then(() => toast.success(t('dashboard.tunnel.copied'))).catch(() => {})}
                                />
                                <IconButton label={t('dashboard.tunnel.edit_subdomain')} icon={Pencil} size={14} onClick={() => setDnsEditing(true)} />
                            </div>
                        ) : null}
                        {dnsAvailable && !dnsEditing && <div className="text-xs text-redstone mb-1">&quot;{dnsAvailable}&quot; {t('dashboard.tunnel.taken_pick')}</div>}
                        {dnsStatus === 'error' && tunnelAddress && (
                            <div className="flex flex-wrap items-center gap-2 mb-1 text-xs text-gold">
                                <span>{t('dashboard.tunnel.dns_failed_direct')}</span>
                                <span className="font-mono select-all text-gold">{tunnelAddress}</span>
                                <button onClick={() => navigator.clipboard.writeText(tunnelAddress).then(() => toast.success(t('dashboard.tunnel.copied'))).catch(() => {})} className="underline hover:text-white">{t('dashboard.tunnel.copy')}</button>
                            </div>
                        )}
                        <div className="flex items-center gap-1.5 group">
                            {!dnsAddress ? <>
                                <span className={`text-sm font-mono font-bold leading-none select-all ${tunnelAddress ? 'text-gold' : 'text-white'}`}>{tunnelAddress || `${status.local_ip||'127.0.0.1'}:${status.port||'25565'}`}</span>
                                <IconButton
                                    label={t('dashboard.tunnel.copy_address')}
                                    icon={Copy}
                                    size={14}
                                    onClick={async () => {
                                        try {
                                            await navigator.clipboard.writeText(tunnelAddress || `${status.local_ip||'127.0.0.1'}:${status.port||'25565'}`);
                                            setAddressCopied(true);
                                            setTimeout(() => setAddressCopied(false), 1500);
                                        } catch (e) { console.error('Copy failed', e); }
                                    }}
                                />
                                <span role="status" className="text-xs font-semibold text-grass-lit">{addressCopied ? t('dashboard.tunnel.copied') : ''}</span>
                            </> : null}
                        </div>
                        {(tunnelAddress||dnsAddress) && <div className="text-xs text-ink-faint font-mono mt-0.5">{t('dashboard.tunnel.local')} {status.local_ip||'127.0.0.1'}:{status.port||'25565'}{tunnelAddress ? <span className="ml-2">{t('dashboard.tunnel.via')} {tunnelAddress}</span> : null}</div>}
                    </div>

                    <IconButton label={t('dashboard.open_folder')} icon={FolderOpen} size={18} onClick={handleOpenFolder} className="h-10 w-10" />

                    <Button
                        variant={tunnelAddress ? 'danger' : 'secondary'}
                        icon={tunnelAddress ? Square : Globe}
                        loading={tunnelConnecting && !tunnelAddress}
                        onClick={async () => {
                            try {
                                if (tunnelAddress) {
                                    await api.stopTunnel();
                                    setTunnelAddress(null);
                                    setTunnelConnecting(false);
                                } else {
                                    await startPublicTunnel();
                                }
                            } catch (err) {
                                setTunnelConnecting(false);
                                toast.error(err.response?.data?.detail || err.message, { title: t('dashboard.tunnel.error_title') });
                            }
                        }}
                    >
                        {tunnelAddress ? t('dashboard.tunnel.stop') : tunnelConnecting ? t('dashboard.tunnel.connecting') : t('dashboard.tunnel.make_public')}
                    </Button>

                    <div className="relative group">
                        <div className="relative">
                            <IconButton
                                label={t('dashboard.tunnel.options')}
                                title={undefined}
                                icon={SettingsIcon}
                                size={18}
                                tone={showAdvanced ? 'active' : 'default'}
                                aria-expanded={showAdvanced}
                                onClick={() => setShowAdvanced(!showAdvanced)}
                                className="h-10 w-10"
                            />
                            {autoTunnel && <div className="pointer-events-none absolute -top-0.5 -right-0.5 h-2 w-2 rounded-sm bg-grass" aria-hidden="true"></div>}
                        </div>
                        {/* Hover, or keyboard focus only: after a mouse click the button keeps focus and the tip would stay open over the header. */}
                        <div role="tooltip" className="absolute bottom-full right-0 mb-2 w-72 p-4 bg-panel rounded-sm shadow-bevel-panel opacity-0 group-hover:opacity-100 group-has-[:focus-visible]:opacity-100 pointer-events-none transition-opacity z-50">
                            <div className="mb-1 text-base font-semibold text-ink">{t('dashboard.tunnel.make_public')}</div>
                            <div className="text-sm leading-relaxed text-ink-dim">{t('dashboard.tunnel.about')}</div>
                        </div>
                    </div>
                </div>

                )}

                {playit.supported && !playit.linked && !shareVisible && (
                    <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-white/5">
                        <Zap size={16} className="shrink-0 text-gold" aria-hidden="true" />
                        <div className="flex-1 min-w-[12rem]">
                            <div className="text-sm font-semibold text-ink">{t('dashboard.tunnel.playit_cta_title')}</div>
                            <div className="text-xs text-ink-dim">
                                {playit.linking ? t('dashboard.tunnel.playit_waiting') : t('dashboard.tunnel.playit_cta_desc')}
                            </div>
                        </div>
                        {playit.linking ? <>
                            <Button size="sm" variant="secondary" onClick={handleLinkPlayit}>{t('dashboard.tunnel.playit_reopen')}</Button>
                            <Button size="sm" variant="ghost" onClick={handleCancelPlayitLink}>{t('common.cancel')}</Button>
                        </> : (
                            <Button size="sm" variant="primary" onClick={handleLinkPlayit}>{t('dashboard.tunnel.playit_activate')}</Button>
                        )}
                    </div>
                )}

                {showAdvanced && <div className={`flex flex-wrap items-center gap-3 ${shareVisible ? '' : 'mt-3 pt-3 border-t border-white/5'}`}>
                    <span className="text-sm text-ink-dim">{t('dashboard.tunnel.provider')}</span>
                        <div className="w-32 rounded-sm border border-white/10 bg-white/5">
                            <Select
                                value={activeProvider}
                                onChange={(v) => { setTunnelProvider(v); localStorage.setItem('preferredTunnelProvider', v); }}
                                options={[
                                    ...(playit.linked ? [{ value: 'playit', label: 'playit.gg' }] : []),
                                    { value: 'pinggy', label: 'Pinggy' },
                                ]}
                            />
                        </div>
                    {playit.linked && <Button size="sm" variant="ghost" onClick={handleUnlinkPlayit}>{t('dashboard.tunnel.playit_unlink')}</Button>}
                    {activeProvider === 'pinggy' && <><span className="text-sm text-ink-dim">{t('dashboard.tunnel.region')}</span><div className="w-20 rounded-sm border border-white/10 bg-white/5"><Select value={tunnelRegion} onChange={setTunnelRegion} options={[{ value: 'eu', label: 'EU' }, { value: 'us', label: 'US' }, { value: 'ap', label: t('dashboard.tunnel.region_asia') }]} /></div></>}
                    <div className="w-px h-6 bg-white/5"></div>
                    <button
                        role="switch"
                        aria-checked={autoTunnel}
                        onClick={() => { const v = !autoTunnel; setAutoTunnel(v); localStorage.setItem('autoTunnel', v.toString()); }}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded-sm border text-sm font-semibold transition-colors ${autoTunnel ? 'bg-grass/10 border-grass/30 text-grass-lit' : 'border-white/10 text-ink-dim hover:text-white'}`}
                    >
                        <div className={`h-2 w-2 rounded-sm ${autoTunnel ? 'bg-grass' : 'bg-ink-faint'}`} aria-hidden="true" />
                        {t('dashboard.tunnel.auto_tunnel')}
                    </button>
                    <span className="text-sm text-ink-faint" title={t('dashboard.tunnel.dns_hint')}>
                        DNS: {dnsUsage && dnsUsage.used != null ? (
                            <span className={
                                dnsUsage.used / (dnsUsage.capacity || 1) > 0.9 ? 'text-redstone'
                                    : dnsUsage.used / (dnsUsage.capacity || 1) > 0.7 ? 'text-gold'
                                        : 'text-grass-lit'
                            }>{dnsUsage.used}/{dnsUsage.capacity}</span>
                        ) : <span className="text-grass-lit">ON</span>}
                    </span>
                    {tunnelAddress && <span className="w-full text-xs text-ink-faint">{t('dashboard.tunnel.region_note')}</span>}
                    <Button
                        size="sm"
                        title={t('dashboard.tunnel.verify_hint')}
                        onClick={async () => {
                            setDnsStatus('checking');
                            try {
                                const r = await api.verifyDns();
                                if (r.verified) {
                                    setDnsStatus('ok');
                                    toast.success(`${r.address}${r.note ? ` (${r.note})` : ''}`, { title: t('dashboard.tunnel.dns_ok_title') });
                                } else {
                                    setDnsStatus('error');
                                    toast.error(r.error || r.detail?.error || 'unknown', { title: t('dashboard.tunnel.dns_failed') });
                                }
                            } catch (e) {
                                setDnsStatus('error');
                                toast.error(e.message || String(e), { title: t('dashboard.tunnel.dns_error_title') });
                            }
                        }}
                    >
                        {t('dashboard.tunnel.verify_dns')}
                    </Button>
                    <Button
                        size="sm"
                        title={t('dashboard.tunnel.clean_hint')}
                        onClick={async () => {
                            try {
                                const r = await api.cleanupDns();
                                toast.success(`${t('dashboard.tunnel.dns_cleanup_done')} ${r.deleted ?? 0}`, { title: t('dashboard.tunnel.dns_cleanup_title') });
                            } catch (e) {
                                toast.error(e.message || String(e), { title: t('dashboard.tunnel.dns_cleanup_failed') });
                            }
                        }}
                    >
                        {t('dashboard.tunnel.clean_dns')}
                    </Button>
                </div>}
            </div>

            )}

            {/* Bedrock / GeyserMC Crossplay Section */}
            {geyserInfo.installed ? (
                <div className="p-4 bg-panel/60 border border-white/5 rounded-sm relative z-40 backdrop-blur-2xl">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-4 min-w-0">
                            <div className={`p-2 rounded-sm border ${bedrockAddress ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400' : 'bg-white/5 border-white/10 text-zinc-300'}`}>
                                <Zap size={16} />
                            </div>
                            <div className="min-w-0">
                                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                                    <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest font-minecraft">
                                        {t('dashboard.bedrock.title')}
                                    </span>
                                    <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-bold uppercase tracking-wider">
                                        GeyserMC
                                    </span>
                                    {geyserInfo.floodgate_installed && (
                                        <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-purple-500/10 border border-purple-500/20 text-purple-300 font-bold uppercase tracking-wider" title={t('dashboard.bedrock.floodgate_hint')}>
                                            {t('dashboard.bedrock.floodgate_active')}
                                        </span>
                                    )}
                                    {bedrockAddress ? (
                                        <span className="text-[8px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-sm border border-emerald-500/20 font-bold uppercase tracking-wider">
                                            {t('status.online')} (UDP)
                                        </span>
                                    ) : (
                                        <span className="text-[8px] px-1.5 py-0.5 bg-zinc-500/10 text-ink-faint rounded-sm border border-zinc-500/20 font-bold uppercase tracking-wider">
                                            {t('status.offline')}
                                        </span>
                                    )}
                                </div>

                                {bedrockAddress ? (
                                    <div className="space-y-1 mt-1">
                                        <div className="flex flex-wrap items-center gap-3">
                                            <div className="flex items-center gap-1.5 bg-black/40 border border-white/10 px-2.5 py-1 rounded-sm">
                                                <span className="text-[9px] uppercase tracking-wider text-ink-faint font-bold">{t('dashboard.bedrock.address')}:</span>
                                                <span className="text-xs font-mono font-bold text-cyan-300 select-all">
                                                    {bedrockAddress.includes(':') ? bedrockAddress.split(':')[0] : bedrockAddress}
                                                </span>
                                                <button
                                                    onClick={() => navigator.clipboard.writeText(bedrockAddress.includes(':') ? bedrockAddress.split(':')[0] : bedrockAddress)}
                                                    className="p-1 hover:text-white text-ink-faint transition-colors"
                                                    title={t('dashboard.bedrock.copy_address')}
                                                >
                                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                                </button>
                                            </div>
                                            <div className="flex items-center gap-1.5 bg-black/40 border border-white/10 px-2.5 py-1 rounded-sm">
                                                <span className="text-[9px] uppercase tracking-wider text-ink-faint font-bold">{t('dashboard.bedrock.port')}:</span>
                                                <span className="text-xs font-mono font-bold text-emerald-400 select-all">
                                                    {bedrockAddress.includes(':') ? bedrockAddress.split(':')[1] : '19132'}
                                                </span>
                                                <button
                                                    onClick={() => navigator.clipboard.writeText(bedrockAddress.includes(':') ? bedrockAddress.split(':')[1] : '19132')}
                                                    className="p-1 hover:text-white text-ink-faint transition-colors"
                                                    title={t('dashboard.bedrock.copy_port')}
                                                >
                                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                                </button>
                                            </div>
                                        </div>
                                        <div className="text-[10px] text-ink-faint">
                                            {t('dashboard.bedrock.how_to')}
                                        </div>
                                        <div className="text-[10px] text-amber-500/80">
                                            {t('dashboard.bedrock.pinggy_note')}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="text-[11px] text-zinc-400 mt-0.5">
                                        {t('dashboard.bedrock.local_port').replace('{port}', geyserInfo.bedrock_port || 19132)}
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
                                        fix: t('dashboard.errors.bedrock_fix'),
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
                                <><Square size={12} /> {t('dashboard.bedrock.stop')}</>
                            ) : bedrockConnecting ? (
                                <><div className="w-3 h-3 border-2 border-yellow-400/30 border-t-yellow-400 rounded-full animate-spin" /> {t('dashboard.bedrock.connecting')}</>
                            ) : (
                                <><Zap size={12} /> {t('dashboard.bedrock.enable')}</>
                            )}
                        </button>
                    </div>
                </div>
            ) : !(isOnline || isStarting) ? (
                <div className="p-3 bg-white/[0.02] border border-white/5 rounded-sm flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="p-1.5 rounded-sm bg-white/5 border border-white/10 text-zinc-400">
                            <Zap size={14} />
                        </div>
                        <div>
                            <div className="text-sm font-semibold text-zinc-200">
                                {t('dashboard.bedrock.cta_title')}
                            </div>
                            <div className="text-xs text-ink-faint">
                                {t('dashboard.bedrock.cta_desc')}
                            </div>
                        </div>
                    </div>
                    {onNavigate && (
                        <button
                            onClick={() => onNavigate('plugins')}
                            className="px-3 py-1.5 rounded-sm border border-white/10 bg-white/5 hover:bg-white/10 text-[10px] font-minecraft text-white tracking-widest uppercase transition-all flex-shrink-0"
                        >
                            {t('dashboard.bedrock.cta_button')}
                        </button>
                    )}
                </div>
            ) : null}

            {/* Stats Grid */}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 relative z-10">
                <StatCard icon={Users} label={t('dashboard.players_online')} value={onlineCount !== undefined ? `${onlineCount}` : '-'} sublabel={`/ ${status.max_players || 20} ${t('status.online')}`} />
                <StatCard icon={Cpu} label={t('dashboard.cpu_usage')} value={status.cpu !== undefined ? `${status.cpu}%` : '--'} sublabel={t('dashboard.cpu_sub')} data={history.cpu} active={active} />
                <StatCard icon={HardDrive} label={t('dashboard.ram_usage')} value={status.ram || '--'} sublabel={t('dashboard.ram_sub')} data={history.ram} active={active} />
                <StatCard icon={Activity} label={t('dashboard.uptime')} value={status.uptime || '--'} sublabel={t('dashboard.uptime_sub')} />
            </div>
            </div>

            {/* Mini Console (Real-time via WS) */}
            <div className="mt-3 flex-1 min-h-[140px] basis-0 bg-black/40 backdrop-blur-2xl border border-white/5 rounded-sm overflow-hidden flex flex-col shadow-xl">
                <div className="bg-black/40 px-4 py-2 border-b border-white/5 flex items-center justify-between">
                    <span className="text-[10px] font-bold text-ink-faint uppercase tracking-widest flex items-center gap-2 font-minecraft">
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
                    <span className="text-ink-faint px-2 font-mono font-bold pt-1">$</span>
                    <input
                        name="cmd"
                        type="text"
                        autoComplete="off"
                        placeholder={t('nav.console') + "..."}
                        className="bg-transparent border-none outline-none text-zinc-300 font-mono text-sm flex-1"
                    />
                </form>
            </div>

            <AnimatePresence>
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

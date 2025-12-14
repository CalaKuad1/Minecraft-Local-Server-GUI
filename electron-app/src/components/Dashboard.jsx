import React, { useEffect, useState } from 'react';
import { Play, Square, Activity, Cpu, HardDrive, X, ExternalLink } from 'lucide-react';
import { api } from '../api';

const StatCard = ({ icon: Icon, label, value, sublabel, color }) => {
    const colors = {
        primary: 'text-primary bg-primary/10 border-primary/20',
        secondary: 'text-secondary bg-secondary/10 border-secondary/20',
        accent: 'text-accent bg-accent/10 border-accent/20',
    };

    return (
        <div className="bg-surface/50 backdrop-blur-md border border-white/5 rounded-2xl p-6 flex items-start justify-between hover:border-white/10 transition-colors shadow-lg">
            <div className={`p-3 rounded-xl ${colors[color]} group-hover:scale-110 transition-transform duration-300`}>
                <Icon size={24} />
            </div>
            <div>
                <h3 className="text-gray-400 text-sm font-medium">{label}</h3>
                <div className="text-2xl font-bold mt-1 text-white tracking-tight">{value}</div>
                <div className="text-xs text-gray-500 mt-1">{sublabel}</div>
            </div>
        </div>
    );
};

// Custom Modal Component
const PublicServerModal = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    const services = [
        {
            name: 'playit.gg',
            description: 'La forma más fácil. Descarga, ejecuta y listo. Sin configuración.',
            color: 'from-green-500 to-emerald-600',
            url: 'https://playit.gg',
            recommended: true
        },
        {
            name: 'ngrok',
            description: 'Túneles seguros para desarrolladores. Requiere cuenta gratuita.',
            color: 'from-blue-500 to-indigo-600',
            url: 'https://ngrok.com'
        },
        {
            name: 'Port Forwarding',
            description: 'Configura tu router manualmente. Opción más avanzada pero permanente.',
            color: 'from-orange-500 to-amber-600',
            url: 'https://www.youtube.com/results?search_query=port+forwarding+minecraft+server'
        }
    ];

    return (
        <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
            onClick={onClose}
        >
            <div
                className="bg-[#0a0a0a] border border-white/10 rounded-2xl max-w-lg w-full shadow-2xl animate-in zoom-in-95 duration-300"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="bg-gradient-to-r from-primary/20 to-accent/20 p-6 rounded-t-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-primary/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
                    <div className="relative flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-white/10 rounded-xl">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
                                    <circle cx="12" cy="12" r="10" />
                                    <line x1="2" x2="22" y1="12" y2="12" />
                                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                                </svg>
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-white">Hacer Servidor Público</h2>
                                <p className="text-sm text-gray-400">Comparte tu servidor con amigos</p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-white"
                        >
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 space-y-4">
                    <p className="text-gray-400 text-sm">
                        Para que tus amigos puedan conectarse desde fuera de tu red local, usa uno de estos servicios:
                    </p>

                    {services.map((service, i) => (
                        <a
                            key={i}
                            href={service.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block p-4 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl transition-all group"
                        >
                            <div className="flex items-start justify-between">
                                <div className="flex items-center gap-3">
                                    <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${service.color} flex items-center justify-center text-white font-bold text-lg`}>
                                        {service.name[0]}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-white">{service.name}</span>
                                            {service.recommended && (
                                                <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full font-medium">
                                                    Recomendado
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm text-gray-500 mt-0.5">{service.description}</p>
                                    </div>
                                </div>
                                <ExternalLink size={16} className="text-gray-500 group-hover:text-white transition-colors mt-1" />
                            </div>
                        </a>
                    ))}
                </div>

                {/* Footer */}
                <div className="px-6 pb-6">
                    <button
                        onClick={onClose}
                        className="w-full py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-gray-300 font-medium transition-colors"
                    >
                        Cerrar
                    </button>
                </div>
            </div>
        </div>
    );
};

export default function Dashboard() {
    const [status, setStatus] = useState({ status: 'offline' });
    const [loading, setLoading] = useState(false);
    const [showPublicModal, setShowPublicModal] = useState(false);

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 2000);
        return () => clearInterval(interval);
    }, []);

    const fetchStatus = async () => {
        const data = await api.getStatus();
        setStatus(data);
    };

    const pollFast = () => {
        let count = 0;
        const fInterval = setInterval(async () => {
            await fetchStatus();
            count++;
            if (count > 10) clearInterval(fInterval);
        }, 500);
    };

    const handleStart = async () => {
        setLoading(true);
        await api.start();
        pollFast();
        setTimeout(() => setLoading(false), 1000);
    };

    const handleStop = async () => {
        setLoading(true);
        await api.stop();
        pollFast();
        setTimeout(() => setLoading(false), 1000);
    };

    const isOnline = status.status === 'online';
    const isStarting = status.status === 'starting';

    return (
        <div className="space-y-8 animate-in fade-in zoom-in duration-500">
            {/* Header & Controls */}
            <div className="flex items-center justify-between p-8 bg-surface/50 backdrop-blur-md border border-white/5 rounded-3xl shadow-xl relative overflow-hidden">

                {/* Abstract Background Gradient */}
                <div className={`absolute top-0 right-0 w-96 h-96 bg-primary/20 blur-[100px] rounded-full translate-x-1/2 -translate-y-1/2 pointer-events-none transition-opacity duration-1000 ${isOnline ? 'opacity-100' : 'opacity-0'}`} />

                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-2">
                        <div className={`w-3 h-3 rounded-full ${isOnline ? 'bg-green-500 shadow-[0_0_10px_#22c55e]' : isStarting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`}></div>
                        <span className={`text-sm font-bold tracking-wider uppercase ${isOnline ? 'text-green-500' : isStarting ? 'text-yellow-500' : 'text-gray-400'}`}>{status.status}</span>
                    </div>
                    <h2 className="text-4xl font-bold text-white mb-2">Minecraft Server</h2>
                    <p className="text-gray-400 max-w-md">
                        {status.server_type ? `${status.server_type} ${status.minecraft_version || ''}` : 'Not configured'}
                    </p>
                </div>

                <div className="flex gap-4 relative z-10">
                    {!isOnline && !isStarting && (
                        <button
                            onClick={handleStart}
                            disabled={loading}
                            className="px-8 py-4 bg-primary hover:bg-primary-hover text-white rounded-xl font-bold flex items-center gap-2 shadow-lg hover:shadow-primary/50 hover:-translate-y-1 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Play size={20} fill="currentColor" />
                            START SERVER
                        </button>
                    )}

                    {(isOnline || isStarting) && (
                        <button
                            onClick={handleStop}
                            disabled={loading}
                            className="px-8 py-4 bg-surface hover:bg-red-500/20 text-red-400 border border-red-500/30 hover:border-red-500 rounded-xl font-bold flex items-center gap-2 transition-all duration-200 active:scale-95 disabled:opacity-50"
                        >
                            <Square size={20} fill="currentColor" />
                            STOP SERVER
                        </button>
                    )}
                </div>
            </div>

            {/* Local IP Info */}
            <div className="flex items-center gap-4 p-4 bg-surface/40 backdrop-blur-md border border-white/5 rounded-xl">
                <div className="flex items-center gap-3 flex-1">
                    <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect width="20" height="8" x="2" y="2" rx="2" ry="2" />
                            <rect width="20" height="8" x="2" y="14" rx="2" ry="2" />
                            <line x1="6" x2="6.01" y1="6" y2="6" />
                            <line x1="6" x2="6.01" y1="18" y2="18" />
                        </svg>
                    </div>
                    <div>
                        <div className="text-xs text-gray-500 uppercase tracking-wider">Local IP Address</div>
                        <div className="text-lg font-mono text-white font-bold">
                            {status.local_ip || '127.0.0.1'}:{status.port || '25565'}
                        </div>
                    </div>
                </div>

                {/* Help Button with Tooltip */}
                <div className="relative group">
                    <button
                        onClick={() => setShowPublicModal(true)}
                        className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" />
                            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                            <path d="M12 17h.01" />
                        </svg>
                    </button>

                    {/* Tooltip on hover */}
                    <div className="absolute bottom-full right-0 mb-2 w-64 p-3 bg-black/90 rounded-lg border border-white/10 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity shadow-xl z-50">
                        <div className="text-sm text-white font-medium mb-1">¿Cómo hago mi servidor público?</div>
                        <div className="text-xs text-gray-400">
                            Haz clic para ver opciones como playit.gg que te permiten compartir tu servidor con amigos fuera de tu red local.
                        </div>
                        <div className="absolute bottom-[-6px] right-4 w-3 h-3 bg-black/90 rotate-45 border-r border-b border-white/10"></div>
                    </div>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                    icon={Cpu}
                    label="CPU Usage"
                    value={status.cpu !== undefined ? `${status.cpu}%` : '--'}
                    sublabel="System Total"
                    color="primary"
                />
                <StatCard
                    icon={HardDrive}
                    label="RAM Usage"
                    value={status.ram || '--'}
                    sublabel="Usage / Allocated"
                    color="secondary"
                />
                <StatCard
                    icon={Activity}
                    label="Uptime"
                    value={status.uptime || '--'}
                    sublabel="Since last restart"
                    color="accent"
                />
            </div>

            {/* Mini Console */}
            <div className="bg-[#0f0f0f]/80 backdrop-blur-md border border-white/10 rounded-2xl overflow-hidden flex flex-col shadow-xl">
                <div className="bg-[#1a1a1a]/90 px-4 py-3 border-b border-white/5 flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-primary/50"></div>
                        Server Activity
                    </span>
                </div>
                <div className="p-4 font-mono text-xs h-48 overflow-y-auto space-y-1 text-gray-300 scrollbar-thin scrollbar-thumb-gray-700">
                    {status.recent_logs && status.recent_logs.length > 0 ? (
                        status.recent_logs.map((log, i) => (
                            <div key={i} className={`whitespace-pre-wrap break-all ${log.level === 'error' ? 'text-red-400' :
                                log.level === 'warning' ? 'text-yellow-400' :
                                    'text-gray-400'
                                }`}>
                                <span className="opacity-30 mr-2">[{new Date().toLocaleTimeString()}]</span>
                                {log.message}
                            </div>
                        ))
                    ) : (
                        <div className="h-full flex items-center justify-center text-gray-700 italic">
                            Waiting for logs...
                        </div>
                    )}
                </div>
                {/* Mini Console Input */}
                <form
                    onSubmit={async (e) => {
                        e.preventDefault();
                        const input = e.target.elements.cmd.value;
                        if (!input.trim()) return;
                        try {
                            await api.sendCommand(input);
                            e.target.elements.cmd.value = '';
                        } catch (err) {
                            console.error("Failed to send command", err);
                        }
                    }}
                    className="border-t border-white/5 bg-[#141414] p-2 flex"
                >
                    <span className="text-primary px-2 font-mono font-bold pt-1">$</span>
                    <input
                        name="cmd"
                        type="text"
                        autoComplete="off"
                        placeholder="Type a command..."
                        className="bg-transparent border-none outline-none text-gray-300 font-mono text-sm flex-1"
                    />
                </form>
            </div>

            {/* Public Server Modal */}
            <PublicServerModal
                isOpen={showPublicModal}
                onClose={() => setShowPublicModal(false)}
            />
        </div>
    );
}

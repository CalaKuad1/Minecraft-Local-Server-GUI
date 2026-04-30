import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api';
import { User, Shield, Ban, CheckCircle, Search, Plus, Trash2, ShieldOff, MoreVertical } from './ui/PixelIcons';

const PlayerCard = ({ player, type, onAction }) => {
    // Determine image (use minotar by name as it is reliable without UUIDs)
    const [imgSrc, setImgSrc] = useState(`https://minotar.net/helm/${player.name}/64`);

    return (
        <div className="bg-[#18181b]/60 backdrop-blur-xl border border-white/5 p-4 rounded-md flex items-center justify-between group hover:border-white/10 transition-all shadow-sm">
            <div className="flex items-center gap-4">
                <img
                    src={imgSrc}
                    alt={player.name}
                    className="w-10 h-10 rounded-lg shadow-sm"
                    onError={() => setImgSrc(`https://ui-avatars.com/api/?name=${player.name}&background=random`)}
                />
                <div>
                    <h3 className="text-white font-medium">{player.name}</h3>
                    {player.uuid && <p className="text-xs text-gray-500 font-mono opacity-0 group-hover:opacity-100 transition-opacity">{player.uuid}</p>}
                </div>
            </div>

            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                {type === 'ops' && (
                    <button onClick={() => onAction('deop', player.name)} className="p-2 hover:bg-red-500/10 text-red-400 rounded-lg transition-colors" title="Deop">
                        <ShieldOff size={18} />
                    </button>
                )}
                {type === 'whitelist' && (
                    <button onClick={() => onAction('unwhitelist', player.name)} className="p-2 hover:bg-red-500/10 text-red-400 rounded-lg transition-colors" title="Remove from Whitelist">
                        <Trash2 size={18} />
                    </button>
                )}
                {type === 'banned' && (
                    <button onClick={() => onAction('pardon', player.name)} className="p-2 hover:bg-green-500/10 text-green-400 rounded-lg transition-colors" title="Unban">
                        <CheckCircle size={18} />
                    </button>
                )}
                {type === 'online' && (
                    <>
                        <button onClick={() => onAction('op', player.name)} className="p-2 hover:bg-yellow-500/10 text-yellow-400 rounded-lg transition-colors" title="Op">
                            <Shield size={18} />
                        </button>
                        <button onClick={() => onAction('kick', player.name)} className="p-2 hover:bg-orange-500/10 text-orange-400 rounded-lg transition-colors" title="Kick">
                            <User size={18} />
                        </button>
                        <button onClick={() => onAction('ban', player.name)} className="p-2 hover:bg-red-500/10 text-red-400 rounded-lg transition-colors" title="Ban">
                            <Ban size={18} />
                        </button>
                    </>
                )}
            </div>
        </div>
    );
};

const StatCard = ({ icon: Icon, label, value }) => (
    <div className="bg-[#18181b]/60 backdrop-blur-xl border border-white/5 rounded-md p-5 flex flex-col justify-between hover:border-white/10 transition-all shadow-sm">
        <div className="flex items-center gap-2 mb-2 text-gray-500">
            <Icon size={14} className="opacity-70" />
            <h3 className="text-xs font-bold uppercase tracking-widest">{label}</h3>
        </div>
        <div className="text-3xl font-minecraft text-white tracking-wide">{value}</div>
    </div>
);

export default function Players() {
    const [activeTab, setActiveTab] = useState('online');
    const [data, setData] = useState({ ops: [], whitelist: [], banned: [] });
    const [onlinePlayers, setOnlinePlayers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const inFlightRef = useRef(false);
    const hasLoadedRef = useRef(false);
    const [showAddModal, setShowAddModal] = useState(false);
    const [newPlayerName, setNewPlayerName] = useState('');

    const fetchData = async ({ background = false } = {}) => {
        if (inFlightRef.current) return;
        inFlightRef.current = true;
        if (!background) {
            setLoading(true);
            setError(null);
        }
        try {
            const lists = await api.getPlayers();
            setData(lists);
            setOnlinePlayers(lists.online || []);
            hasLoadedRef.current = true;
        } catch (e) {
            console.error("Failed to load players", e);
            setError(e?.message || 'Failed to load players');
            if (!hasLoadedRef.current) {
                setData({ ops: [], whitelist: [], banned: [] });
                setOnlinePlayers([]);
            }
        } finally {
            if (!background) setLoading(false);
            inFlightRef.current = false;
        }
    };

    useEffect(() => {
        fetchData({ background: false });
        const interval = setInterval(() => fetchData({ background: true }), 5000);
        return () => clearInterval(interval);
    }, []);

    const handleAction = async (action, name) => {
        if (!name) return;
        setError(null);
        try {
            switch (action) {
                case 'op': await api.opPlayer(name); break;
                case 'deop': await api.deopPlayer(name); break;
                case 'ban': await api.banPlayer(name); break;
                case 'pardon': await api.unbanPlayer(name); break;
                case 'kick': await api.kickPlayer(name); break;
                case 'unwhitelist': await api.whitelistRemove(name); break;
                default:
                    throw new Error(`Unknown action: ${action}`);
            }
            setTimeout(fetchData, 500);
        } catch (e) {
            console.error("Player action failed", e);
            setError(e?.message || 'Action failed');
        }
    };

    const getList = () => {
        switch (activeTab) {
            case 'online': return onlinePlayers;
            case 'ops': return data.ops;
            case 'whitelist': return data.whitelist;
            case 'banned': return data.banned;
            default: return [];
        }
    };

    const currentList = getList();

    if (loading && !hasLoadedRef.current) {
        return <div className="p-8 text-center text-gray-500">Loading players...</div>;
    }

    if (error) {
        return (
            <div className="p-8 text-center">
                <div className="text-red-400 font-medium mb-2">Error loading Players</div>
                <div className="text-gray-500 text-sm mb-4">{error}</div>
                <button
                    onClick={fetchData}
                    className="bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-lg transition-colors border border-white/10"
                >
                    Retry
                </button>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in zoom-in duration-500">
            {/* Header & Stats */}
            <div>
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h2 className="text-4xl font-minecraft tracking-tight text-emerald-400 mb-2">Players</h2>
                        <p className="text-gray-400">Manage server operators, access, and bans.</p>
                    </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <StatCard
                        icon={User}
                        label="Online"
                        value={onlinePlayers.length || 0}
                    />
                    <StatCard
                        icon={Shield}
                        label="Operators"
                        value={data.ops?.length || 0}
                    />
                    <StatCard
                        icon={CheckCircle}
                        label="Whitelisted"
                        value={data.whitelist?.length || 0}
                    />
                    <StatCard
                        icon={Ban}
                        label="Banned"
                        value={data.banned?.length || 0}
                    />
                </div>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between">
                <div className="flex bg-[#030303]/60 backdrop-blur-xl border border-white/5 p-1 rounded-md mb-4 relative max-w-fit shadow-md">
                    {['online', 'ops', 'whitelist', 'banned'].map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-6 py-2.5 rounded-sm font-medium transition-colors relative flex items-center justify-center gap-2 z-10 text-sm ${activeTab === tab
                                ? 'text-white'
                                : 'text-zinc-500 hover:text-white'
                                }`}
                        >
                            {activeTab === tab && (
                                <motion.div layoutId="playersTab" className="absolute inset-0 bg-white/10 rounded-sm -z-10 shadow-sm" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                            )}
                            <span className={`relative z-10`}>{tab.charAt(0).toUpperCase() + tab.slice(1)}</span>
                        </button>
                    ))}
                </div>

                {/* Add Button */}
                {activeTab !== 'online' && (
                    <button
                        onClick={() => setShowAddModal(true)}
                        className="bg-primary hover:bg-primary-hover text-black px-5 py-2.5 rounded-md flex items-center gap-2 font-bold transition-all shadow-[0_0_15px_rgba(16,185,129,0.2)] shrink-0 ml-4 text-sm"
                    >
                        <Plus size={18} />
                        Add to {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
                    </button>
                )}
            </div>

            {/* List */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {currentList.length > 0 ? (
                    currentList.map((player, i) => (
                        <PlayerCard
                            key={player.uuid || i}
                            player={player}
                            type={activeTab}
                            onAction={handleAction}
                        />
                    ))
                ) : (
                    <div className="col-span-2 text-center py-20 bg-surface rounded-md border border-white/5 border-dashed">
                        <User size={48} className="mx-auto text-gray-600 mb-4 opacity-50" />
                        <p className="text-gray-500">No players found in this list.</p>
                        {activeTab === 'online' && <p className="text-gray-600 text-sm mt-1">Make sure the server is running.</p>}
                    </div>
                )}
            </div>

            {/* Simple Add Modal (Prompt style for MVP) */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200">
                    <div className="bg-[#1a1a1a] p-6 rounded-2xl border border-white/10 w-96 shadow-2xl scale-100 animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold text-white mb-4">Add to {activeTab}</h3>
                        <input
                            autoFocus
                            type="text"
                            className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-primary transition-colors mb-4"
                            placeholder="Player Name"
                            value={newPlayerName}
                            onChange={(e) => setNewPlayerName(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    // Handle add
                                    if (activeTab === 'ops') handleAction('op', newPlayerName);
                                    if (activeTab === 'whitelist') api.whitelistAdd(newPlayerName).then(fetchData);
                                    if (activeTab === 'banned') handleAction('ban', newPlayerName);
                                    setNewPlayerName('');
                                    setShowAddModal(false);
                                }
                            }}
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setShowAddModal(false)}
                                className="px-4 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => {
                                    if (activeTab === 'ops') handleAction('op', newPlayerName);
                                    // White list not in standard handleAction yet? fix handleAction to use api.whitelistAdd specific
                                    if (activeTab === 'whitelist') api.whitelistAdd(newPlayerName).then(fetchData);
                                    if (activeTab === 'banned') handleAction('ban', newPlayerName);
                                    setNewPlayerName('');
                                    setShowAddModal(false);
                                }}
                                className="px-4 py-2 rounded-lg bg-primary hover:bg-primary-hover text-white font-medium transition-colors"
                            >
                                Add
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

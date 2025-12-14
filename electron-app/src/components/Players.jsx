import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, Shield, Ban, CheckCircle, Search, Plus, Trash2, ShieldOff, MoreVertical } from 'lucide-react';

const PlayerCard = ({ player, type, onAction }) => {
    // Determine image (use minotar by name as it is reliable without UUIDs)
    const [imgSrc, setImgSrc] = useState(`https://minotar.net/helm/${player.name}/64`);

    return (
        <div className="bg-surface border border-white/5 p-4 rounded-xl flex items-center justify-between group hover:bg-surface-hover transition-colors">
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

export default function Players() {
    const [activeTab, setActiveTab] = useState('online');
    const [data, setData] = useState({ ops: [], whitelist: [], banned: [] });
    const [onlinePlayers, setOnlinePlayers] = useState([]); // Placeholder for now, ideally fetched from query
    const [loading, setLoading] = useState(false);
    const [showAddModal, setShowAddModal] = useState(false);
    const [newPlayerName, setNewPlayerName] = useState('');

    const fetchData = async () => {
        setLoading(true);
        const lists = await api.getPlayers();
        setData(lists);
        // TODO: In a real scenario, we'd also query the server for online players separately
        // For now, we'll fake online players or if available from a future status endpoint
        setLoading(false);
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const handleAction = async (action, name) => {
        if (!name) return;

        switch (action) {
            case 'op': await api.opPlayer(name); break;
            case 'deop': await api.deopPlayer(name); break;
            case 'ban': await api.banPlayer(name); break;
            case 'pardon': await api.unbanPlayer(name); break;
            case 'kick': await api.kickPlayer(name); break;
            // case 'whitelist': await api.whitelistAdd(name); break; 
            // case 'unwhitelist': await api.whitelistRemove(name); break; 
        }
        setTimeout(fetchData, 500); // quick refresh
    };

    // Filter displayed list based on tab
    const getList = () => {
        switch (activeTab) {
            case 'online': return onlinePlayers; // Currently empty until we verify query
            case 'ops': return data.ops;
            case 'whitelist': return data.whitelist;
            case 'banned': return data.banned;
            default: return [];
        }
    };

    const currentList = getList();

    return (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold text-white mb-2">Players</h2>
                    <p className="text-gray-400">Manage server operators, access, and bans.</p>
                </div>
                {activeTab !== 'online' && (
                    <button
                        onClick={() => setShowAddModal(true)}
                        className="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded-xl flex items-center gap-2 font-medium transition-colors"
                    >
                        <Plus size={18} />
                        Add to {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
                    </button>
                )}
            </div>

            {/* Tabs */}
            <div className="flex gap-2 border-b border-white/5 pb-1">
                {['online', 'ops', 'whitelist', 'banned'].map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-6 py-3 rounded-t-xl font-medium transition-colors relative ${activeTab === tab
                            ? 'text-white bg-white/5'
                            : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                            }`}
                    >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        {/* Active line */}
                        {activeTab === tab && (
                            <div className="absolute bottom-0 left-0 w-full h-0.5 bg-primary"></div>
                        )}
                    </button>
                ))}
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
                    <div className="col-span-2 text-center py-20 bg-surface rounded-2xl border border-white/5 border-dashed">
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

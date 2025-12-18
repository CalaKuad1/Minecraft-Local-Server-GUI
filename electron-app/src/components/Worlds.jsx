import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Globe, HardDrive, Check, FolderPlus, Clock, Archive, RefreshCw } from 'lucide-react';

export default function Worlds() {
    const [worlds, setWorlds] = useState([]);
    const [activeWorld, setActiveWorld] = useState('');
    const [loading, setLoading] = useState(false);
    const [switching, setSwitching] = useState(false);
    const [error, setError] = useState(null);

    const [backups, setBackups] = useState([]);
    const [backupsLoading, setBackupsLoading] = useState(false);
    const [creatingBackup, setCreatingBackup] = useState(false);

    useEffect(() => {
        loadData();
    }, []);

    useEffect(() => {
        if (activeWorld) {
            loadBackups(activeWorld);
        }
    }, [activeWorld]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [wList, props] = await Promise.all([
                api.getWorlds(),
                api.getServerProperties()
            ]);
            setWorlds(wList);
            setActiveWorld(props['level-name'] || 'world');
        } catch (e) {
            console.error("Failed to load worlds", e);
            setError(e?.message || 'Failed to load worlds');
            setWorlds([]);
            setActiveWorld('');
        }
        setLoading(false);
    };

    const loadBackups = async (worldName) => {
        setBackupsLoading(true);
        try {
            const list = await api.getWorldBackups(worldName);
            setBackups(Array.isArray(list) ? list : []);
        } catch (e) {
            // Keep Worlds usable even if backups fail
            console.error('Failed to load backups', e);
            setBackups([]);
        } finally {
            setBackupsLoading(false);
        }
    };

    const handleCreateBackup = async () => {
        if (!activeWorld) return;
        setCreatingBackup(true);
        try {
            await api.createWorldBackup(activeWorld);
            // Backend runs it async, give it a moment then refresh list
            setTimeout(() => loadBackups(activeWorld), 1200);
        } catch (e) {
            console.error('Failed to create backup', e);
            setError(e?.message || 'Failed to create backup');
        } finally {
            setCreatingBackup(false);
        }
    };

    const handleSwitchWorld = async (worldName) => {
        if (worldName === activeWorld) return;
        setSwitching(true);
        try {
            // Update server.properties
            await api.updateServerProperties({ 'level-name': worldName });
            setActiveWorld(worldName);
            // Optionally notify user they need to restart server
        } catch (e) {
            console.error("Failed to switch world", e);
            setError(e?.message || 'Failed to switch world');
        }
        setSwitching(false);
    };

    const formatDate = (timestamp) => {
        return new Date(timestamp * 1000).toLocaleString();
    };

    if (loading) {
        return <div className="p-8 text-center text-gray-500">Loading worlds...</div>;
    }

    if (error) {
        return (
            <div className="p-8 text-center">
                <div className="text-red-400 font-medium mb-2">Error loading Worlds</div>
                <div className="text-gray-500 text-sm mb-4">{error}</div>
                <button
                    onClick={loadData}
                    className="bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-lg transition-colors border border-white/10"
                >
                    Retry
                </button>
            </div>
        );
    }

    return (
        <div className="animate-in fade-in zoom-in duration-500 max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h2 className="text-3xl font-bold text-white mb-2">Worlds</h2>
                    <p className="text-gray-400">Manage your Minecraft worlds and saves.</p>
                </div>
                <button className="bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors border border-white/10">
                    <FolderPlus size={18} />
                    <span>Import World</span>
                </button>
            </div>

            {/* Backups */}
            <div className="mb-8 bg-surface/40 border border-white/5 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <Archive size={18} className="text-primary" />
                        <div>
                            <div className="text-lg font-bold text-white">Backups</div>
                            <div className="text-xs text-gray-500">World: <span className="font-mono">{activeWorld || '-'}</span></div>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => activeWorld && loadBackups(activeWorld)}
                            disabled={backupsLoading || !activeWorld}
                            className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-gray-200 text-sm flex items-center gap-2 disabled:opacity-50"
                            title="Refresh"
                        >
                            <RefreshCw size={14} className={backupsLoading ? 'animate-spin' : ''} />
                            Refresh
                        </button>
                        <button
                            onClick={handleCreateBackup}
                            disabled={creatingBackup || !activeWorld}
                            className="px-3 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 border border-primary/20 text-primary text-sm font-medium disabled:opacity-50"
                        >
                            {creatingBackup ? 'Creating...' : 'Create backup'}
                        </button>
                    </div>
                </div>

                {backupsLoading ? (
                    <div className="text-sm text-gray-500">Loading backups...</div>
                ) : backups.length === 0 ? (
                    <div className="text-sm text-gray-500">No backups yet.</div>
                ) : (
                    <div className="space-y-2">
                        {backups.slice(0, 8).map((b) => (
                            <div key={b.name} className="flex items-center justify-between px-3 py-2 rounded-xl bg-black/20 border border-white/5">
                                <div className="min-w-0">
                                    <div className="text-sm text-white font-medium truncate">{b.name}</div>
                                    <div className="text-xs text-gray-500">{b.size} • {formatDate(b.created)}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {worlds.map((world) => (
                    <div
                        key={world.name}
                        className={`group relative bg-surface border rounded-2xl p-5 transition-all duration-300 ${activeWorld === world.name
                                ? 'border-primary/50 bg-primary/5 shadow-[0_0_20px_rgba(99,102,241,0.1)]'
                                : 'border-white/5 hover:border-white/20 hover:bg-surface-hover'
                            }`}
                    >
                        <div className="flex items-start justify-between mb-4">
                            <div className={`p-3 rounded-xl ${activeWorld === world.name ? 'bg-primary/20 text-primary' : 'bg-black/40 text-gray-400 group-hover:text-white'}`}>
                                <Globe size={24} />
                            </div>
                            {activeWorld === world.name && (
                                <span className="flex items-center gap-1 text-xs font-bold text-primary bg-primary/10 px-2 py-1 rounded-full border border-primary/20">
                                    <Check size={12} />
                                    ACTIVE
                                </span>
                            )}
                        </div>

                        <h3 className="text-lg font-bold text-white mb-1">{world.name}</h3>

                        <div className="space-y-2 mt-4">
                            <div className="flex items-center text-sm text-gray-500 gap-2">
                                <HardDrive size={14} />
                                <span>{world.size}</span>
                            </div>
                            <div className="flex items-center text-sm text-gray-500 gap-2">
                                <Clock size={14} />
                                <span>{formatDate(world.last_modified)}</span>
                            </div>
                        </div>

                        <div className="mt-6 pt-4 border-t border-white/5 flex gap-2">
                            <button
                                onClick={() => handleSwitchWorld(world.name)}
                                disabled={switching || activeWorld === world.name}
                                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${activeWorld === world.name
                                        ? 'bg-transparent text-gray-500 cursor-default'
                                        : 'bg-white/5 hover:bg-white/10 text-white'
                                    }`}
                            >
                                {activeWorld === world.name ? 'Selected' : 'Load This World'}
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            <div className="mt-8 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl flex gap-3 text-yellow-200/80 text-sm">
                <div className="shrink-0 mt-0.5">⚠️</div>
                <p>Changing the active world requires a server restart to take effect.</p>
            </div>
        </div>
    );
}

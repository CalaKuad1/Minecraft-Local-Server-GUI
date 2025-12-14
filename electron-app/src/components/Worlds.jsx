import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Globe, HardDrive, Check, FolderPlus, Clock } from 'lucide-react';

export default function Worlds() {
    const [worlds, setWorlds] = useState([]);
    const [activeWorld, setActiveWorld] = useState('');
    const [loading, setLoading] = useState(false);
    const [switching, setSwitching] = useState(false);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [wList, props] = await Promise.all([
                api.getWorlds(),
                api.getServerProperties()
            ]);
            setWorlds(wList);
            setActiveWorld(props['level-name'] || 'world');
        } catch (e) {
            console.error("Failed to load worlds", e);
        }
        setLoading(false);
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
        }
        setSwitching(false);
    };

    const formatDate = (timestamp) => {
        return new Date(timestamp * 1000).toLocaleString();
    };

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

import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Save, Server, Monitor, Shield, Zap, Globe, FolderOpen, CircuitBoard, Cpu, HardDrive } from 'lucide-react';
import { Select } from './ui/Select';

export default function Settings() {
    const [activeTab, setActiveTab] = useState('server');
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);

    // State for Server Properties
    const [serverProps, setServerProps] = useState({});

    // State for App Settings
    const [appSettings, setAppSettings] = useState({
        ram_min: "2",
        ram_max: "4",
        ram_unit: "G",
        java_path: "java"
    });

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        setLoading(true);
        try {
            const props = await api.getServerProperties();
            const app = await api.getAppSettings();
            setServerProps(props);
            setAppSettings(app);
        } catch (e) {
            console.error("Failed to load settings", e);
        }
        setLoading(false);
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            if (activeTab === 'server') {
                await api.updateServerProperties(serverProps);
            } else {
                await api.updateAppSettings(appSettings);
            }
        } catch (e) {
            console.error("Failed to save", e);
        }
        setSaving(false);
        // Reload to ensure consistency
        setTimeout(loadSettings, 500);
    };

    const handlePropChange = (key, value) => {
        setServerProps(prev => ({ ...prev, [key]: value }));
    };

    const handleAppChange = (key, value) => {
        setAppSettings(prev => ({ ...prev, [key]: value }));
    };

    if (loading) return <div className="p-8 text-center text-gray-500">Loading settings...</div>;

    return (
        <div className="animate-in fade-in zoom-in duration-500 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h2 className="text-3xl font-bold text-white mb-2">Settings</h2>
                    <p className="text-gray-400">Manage server properties and application configuration.</p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => api.openServerFolder()}
                        className="bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors border border-white/10"
                    >
                        <FolderOpen size={18} />
                        <span>Open Server Folder</span>
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="bg-primary hover:bg-primary-hover text-white px-6 py-2 rounded-xl flex items-center gap-2 font-medium transition-all shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:shadow-[0_0_30px_rgba(99,102,241,0.5)]"
                    >
                        <Save size={18} />
                        <span>{saving ? 'Saving...' : 'Save Changes'}</span>
                    </button>
                </div>
            </div>

            <div className="flex gap-2 border-b border-white/5 mb-8">
                {['server', 'system'].map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-6 py-3 rounded-t-xl font-medium transition-colors relative flex items-center gap-2 ${activeTab === tab
                            ? 'text-white bg-white/5'
                            : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                            }`}
                    >
                        {tab === 'server' && <CircuitBoard size={18} />}
                        {tab === 'system' && <Cpu size={18} />}
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        {activeTab === tab && (
                            <div className="absolute bottom-0 left-0 w-full h-0.5 bg-primary"></div>
                        )}
                    </button>
                ))}
            </div>

            {activeTab === 'server' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in slide-in-from-left-4 duration-300 pb-10">

                    {/* General Settings */}
                    <div className="bg-surface border border-white/5 p-6 rounded-2xl h-fit">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <FolderOpen size={20} className="text-primary" />
                            General & World
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Server Port</label>
                                <input
                                    type="number"
                                    value={serverProps['server-port'] || '25565'}
                                    onChange={(e) => handlePropChange('server-port', e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary outline-none transition-colors"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">MOTD (Server Name)</label>
                                <textarea
                                    value={serverProps['motd'] || 'A Minecraft Server'}
                                    onChange={(e) => handlePropChange('motd', e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary outline-none transition-colors h-20 resize-none"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">World Seed</label>
                                <input
                                    type="text"
                                    placeholder="Leave empty for random"
                                    value={serverProps['level-seed'] || ''}
                                    onChange={(e) => handlePropChange('level-seed', e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary outline-none transition-colors"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Level Type</label>
                                <Select
                                    value={serverProps['level-type'] || 'default'}
                                    onChange={(val) => handlePropChange('level-type', val)}
                                    options={[
                                        { value: 'default', label: 'Default' },
                                        { value: 'flat', label: 'Flat' },
                                        { value: 'large_biomes', label: 'Large Biomes' },
                                        { value: 'amplified', label: 'Amplified' }
                                    ]}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Gameplay Settings */}
                    <div className="bg-surface border border-white/5 p-6 rounded-2xl h-fit">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <CircuitBoard size={20} className="text-accent" />
                            Gameplay
                        </h3>
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Difficulty</label>
                                    <Select
                                        value={serverProps['difficulty'] || 'easy'}
                                        onChange={(val) => handlePropChange('difficulty', val)}
                                        options={[
                                            { value: 'peaceful', label: 'Peaceful' },
                                            { value: 'easy', label: 'Easy' },
                                            { value: 'normal', label: 'Normal' },
                                            { value: 'hard', label: 'Hard' }
                                        ]}
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Gamemode</label>
                                    <Select
                                        value={serverProps['gamemode'] || 'survival'}
                                        onChange={(val) => handlePropChange('gamemode', val)}
                                        options={[
                                            { value: 'survival', label: 'Survival' },
                                            { value: 'creative', label: 'Creative' },
                                            { value: 'adventure', label: 'Adventure' },
                                            { value: 'spectator', label: 'Spectator' }
                                        ]}
                                    />
                                </div>
                            </div>

                            <div className="space-y-2 pt-2">
                                <LabelToggle
                                    label="PvP Allowed"
                                    desc="Players can hurt each other"
                                    checked={serverProps['pvp'] === 'true'}
                                    onChange={(v) => handlePropChange('pvp', v.toString())}
                                />
                                <LabelToggle
                                    label="Hardcore Mode"
                                    desc="Banned upon death"
                                    color="text-red-400"
                                    checked={serverProps['hardcore'] === 'true'}
                                    onChange={(v) => handlePropChange('hardcore', v.toString())}
                                />
                                <LabelToggle
                                    label="Allow Nether"
                                    desc="Enable nether dimension"
                                    checked={serverProps['allow-nether'] !== 'false'}
                                    onChange={(v) => handlePropChange('allow-nether', v.toString())}
                                />
                                <LabelToggle
                                    label="Allow Flight"
                                    desc="Allow flying in survival"
                                    checked={serverProps['allow-flight'] === 'true'}
                                    onChange={(v) => handlePropChange('allow-flight', v.toString())}
                                />
                                <LabelToggle
                                    label="Command Blocks"
                                    desc="Enable command blocks"
                                    checked={serverProps['enable-command-block'] === 'true'}
                                    onChange={(v) => handlePropChange('enable-command-block', v.toString())}
                                />
                                <LabelToggle
                                    label="Spawn Animals"
                                    desc="Natural animal spawning"
                                    checked={serverProps['spawn-animals'] !== 'false'}
                                    onChange={(v) => handlePropChange('spawn-animals', v.toString())}
                                />
                                <LabelToggle
                                    label="Spawn Monsters"
                                    desc="Natural monster spawning"
                                    checked={serverProps['spawn-monsters'] !== 'false'}
                                    onChange={(v) => handlePropChange('spawn-monsters', v.toString())}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Performance & Network */}
                    <div className="bg-surface border border-white/5 p-6 rounded-2xl h-fit">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Cpu size={20} className="text-blue-400" />
                            Performance & Network
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Max Players</label>
                                <input
                                    type="number"
                                    value={serverProps['max-players'] || '20'}
                                    onChange={(e) => handlePropChange('max-players', e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary outline-none transition-colors"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">View Distance (Chunks)</label>
                                <input
                                    type="number"
                                    min="2" max="32"
                                    value={serverProps['view-distance'] || '10'}
                                    onChange={(e) => handlePropChange('view-distance', e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary outline-none transition-colors"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Simulation Distance (Chunks)</label>
                                <input
                                    type="number"
                                    min="2" max="32"
                                    value={serverProps['simulation-distance'] || '10'}
                                    onChange={(e) => handlePropChange('simulation-distance', e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary outline-none transition-colors"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Security & Advanced */}
                    <div className="bg-surface border border-white/5 p-6 rounded-2xl h-fit">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <HardDrive size={20} className="text-orange-400" />
                            Security & Advanced
                        </h3>
                        <div className="space-y-2">
                            <LabelToggle
                                label="Online Mode"
                                desc="Verify users with Mojang"
                                checked={serverProps['online-mode'] === 'true'}
                                onChange={(v) => handlePropChange('online-mode', v.toString())}
                            />
                            <LabelToggle
                                label="Whitelist"
                                desc="Only listed players can join"
                                checked={serverProps['white-list'] === 'true'}
                                onChange={(v) => handlePropChange('white-list', v.toString())}
                            />
                            <LabelToggle
                                label="Enforce Whitelist"
                                desc="Kick unlisted even if already on"
                                checked={serverProps['enforce-whitelist'] === 'true'}
                                onChange={(v) => handlePropChange('enforce-whitelist', v.toString())}
                            />
                            <LabelToggle
                                label="Force Gamemode"
                                desc="Force default gamemode on join"
                                checked={serverProps['force-gamemode'] === 'true'}
                                onChange={(v) => handlePropChange('force-gamemode', v.toString())}
                            />
                        </div>
                    </div>

                </div>
            )}

            {activeTab === 'system' && (
                <div className="space-y-6 animate-in slide-in-from-right-4 duration-300">
                    <div className="bg-surface border border-white/5 p-6 rounded-2xl">
                        <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                            <HardDrive size={20} className="text-purple-400" />
                            Resources
                        </h3>

                        <div className="mb-8">
                            <div className="flex justify-between items-end mb-4">
                                <label className="text-sm font-medium text-gray-300">RAM Allocation (Max)</label>
                                <span className="text-2xl font-bold text-primary font-mono">{appSettings.ram_max} GB</span>
                            </div>
                            <input
                                type="range"
                                min="2"
                                max="16"
                                step="1"
                                value={appSettings.ram_max}
                                onChange={(e) => handleAppChange('ram_max', e.target.value)}
                                className="w-full h-2 bg-black/40 rounded-lg appearance-none cursor-pointer accent-primary"
                            />
                            <div className="flex justify-between text-xs text-gray-500 mt-2">
                                <span>2 GB</span>
                                <span>8 GB</span>
                                <span>16 GB</span>
                            </div>
                        </div>

                        <div className="mb-4">
                            <div className="flex justify-between items-end mb-4">
                                <label className="text-sm font-medium text-gray-300">RAM Allocation (Min)</label>
                                <span className="text-xl font-bold text-gray-400 font-mono">{appSettings.ram_min} GB</span>
                            </div>
                            <input
                                type="range"
                                min="1"
                                max={appSettings.ram_max}
                                step="1"
                                value={appSettings.ram_min}
                                onChange={(e) => handleAppChange('ram_min', e.target.value)}
                                className="w-full h-2 bg-black/40 rounded-lg appearance-none cursor-pointer accent-gray-500"
                            />
                            <p className="text-xs text-gray-500 mt-2">Initial memory allocation. Should be lower than Max.</p>
                        </div>
                    </div>

                    <div className="bg-surface border border-white/5 p-6 rounded-2xl">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Cpu size={20} className="text-orange-400" />
                            Java Configuration
                        </h3>
                        <div>
                            <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Java Executable Path</label>
                            <input
                                type="text"
                                value={appSettings.java_path}
                                onChange={(e) => handleAppChange('java_path', e.target.value)}
                                className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary outline-none transition-colors font-mono text-sm"
                                placeholder="java"
                            />
                            <p className="text-xs text-gray-500 mt-2">Path to your Java installation. Leave as 'java' to use system default.</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function LabelToggle({ label, desc, checked, onChange, color = "text-gray-300" }) {
    return (
        <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5 hover:border-white/10 transition-colors">
            <div className="flex flex-col">
                <span className={`font-medium ${color}`}>{label}</span>
                {desc && <span className="text-xs text-gray-500">{desc}</span>}
            </div>
            <input
                type="checkbox"
                checked={checked}
                onChange={(e) => onChange(e.target.checked)}
                className="w-5 h-5 accent-primary bg-black/40 border-white/10 rounded cursor-pointer"
            />
        </div>
    );
}

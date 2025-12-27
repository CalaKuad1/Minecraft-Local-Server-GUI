import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Save, Server, Monitor, Shield, Zap, Globe, FolderOpen, CircuitBoard, Cpu, HardDrive, Settings as SettingsIcon } from 'lucide-react';
import { Select } from './ui/Select';
import AdvancedSettingsModal from './AdvancedSettingsModal';
import MotdPreview from './MotdPreview';
import { Palette, Upload } from 'lucide-react';

export default function Settings() {
    const [activeTab, setActiveTab] = useState('server');
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [showAdvanced, setShowAdvanced] = useState(false);

    // State for Server Properties
    const [serverProps, setServerProps] = useState({});

    // State for App Settings
    const [appSettings, setAppSettings] = useState({
        ram_min: "2",
        ram_max: "4",
        ram_unit: "G",
        java_path: "java"
    });

    const [iconTs, setIconTs] = useState(Date.now());
    const API_BASE = "http://127.0.0.1:8000"; // Should be imported or context

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        setLoading(true);
        setError(null);
        try {
            const props = await api.getServerProperties();
            const app = await api.getAppSettings();
            setServerProps(props);
            setAppSettings(app);
        } catch (e) {
            console.error("Failed to load settings", e);
            setError(e?.message || 'Failed to load settings');
        }
        setLoading(false);
    };

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        try {
            if (activeTab === 'server') {
                await api.updateServerProperties(serverProps);
            } else {
                await api.updateAppSettings(appSettings);
            }
        } catch (e) {
            console.error("Failed to save", e);
            setError(e?.message || 'Failed to save');
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

    const handleIconUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        try {
            await api.uploadServerIcon(file);
            setIconTs(Date.now()); // Refresh image
        } catch (err) {
            setError("Failed to upload icon: " + err.message);
        }
    };

    const insertColorCode = (code) => {
        const textarea = document.getElementById('motd-input');
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const text = serverProps['motd'] || '';
        const newText = text.substring(0, start) + '&' + code + text.substring(end);

        handlePropChange('motd', newText);

        // Restore focus and position (rough)
        setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(start + 2, start + 2);
        }, 0);
    };

    if (loading) return <div className="p-8 text-center text-gray-500">Loading settings...</div>;

    if (error) {
        return (
            <div className="p-8 text-center">
                <div className="text-red-400 font-medium mb-2">Error loading Settings</div>
                <div className="text-gray-500 text-sm mb-4">{error}</div>
                <button
                    onClick={loadSettings}
                    className="bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-lg transition-colors border border-white/10"
                >
                    Retry
                </button>
            </div>
        );
    }

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
                {['server', 'appearance', 'system'].map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-6 py-3 rounded-t-xl font-medium transition-colors relative flex items-center gap-2 ${activeTab === tab
                            ? 'text-white bg-white/5'
                            : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                            }`}
                    >
                        {tab === 'server' && <CircuitBoard size={18} />}
                        {tab === 'appearance' && <Palette size={18} />}
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
                        <div className="space-y-4">
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

                            <div className="pt-4 border-t border-white/5">
                                <button
                                    onClick={() => setShowAdvanced(true)}
                                    className="w-full py-3 bg-white/5 hover:bg-white/10 text-white rounded-xl font-bold transition-all border border-white/5 hover:border-white/10 flex items-center justify-center gap-2 group"
                                >
                                    <SettingsIcon size={18} className="group-hover:rotate-45 transition-transform duration-500" />
                                    Open Advanced Configuration
                                </button>
                                <p className="text-center text-xs text-gray-500 mt-2">Access all server.properties</p>
                            </div>
                        </div>
                    </div>

                </div>
            )}

            {activeTab === 'appearance' && (
                <div className="animate-in slide-in-from-left-4 duration-300 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Icon Editor */}
                        <div className="bg-surface border border-white/5 p-6 rounded-2xl">
                            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                <Monitor size={20} className="text-blue-400" />
                                Server Icon
                            </h3>
                            <div className="flex flex-col items-center justify-center p-6 bg-black/20 rounded-xl border border-white/5 border-dashed hover:border-primary/50 transition-colors group">
                                <div className="w-[64px] h-[64px] mb-4 relative drop-shadow-2xl">
                                    <img
                                        src={`${API_BASE}/server/icon/image?t=${iconTs}`}
                                        onError={(e) => e.target.src = "https://static.wikia.nocookie.net/minecraft_gamepedia/images/4/44/Grass_Block_Revision_6.png"}
                                        className="w-full h-full object-contain pixelated rounded-sm"
                                    />
                                </div>
                                <p className="text-sm text-gray-400 mb-4 text-center">
                                    Upload a 64x64 PNG image.<br />It will be resized automatically.
                                </p>
                                <label className="cursor-pointer bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors">
                                    <Upload size={16} />
                                    <span>Choose File</span>
                                    <input type="file" className="hidden" accept="image/png,image/jpeg" onChange={handleIconUpload} />
                                </label>
                            </div>
                        </div>

                        {/* Visual Preview */}
                        <div className="bg-surface border border-white/5 p-6 rounded-2xl">
                            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                <Globe size={20} className="text-green-400" />
                                LIVE Preview
                            </h3>
                            <div className="bg-[url('https://assets.mcmaster.net/bg-dirt-dark.png')] p-4 rounded-xl flex items-center justify-center min-h-[160px]">
                                <MotdPreview
                                    motd={serverProps['motd']}
                                    iconUrl={`${API_BASE}/server/icon/image?t=${iconTs}`}
                                />
                            </div>
                            <p className="text-xs text-gray-500 mt-2 text-center">This is how your server appears in the multiplayer list.</p>
                        </div>
                    </div>

                    {/* MOTD Editor */}
                    <div className="bg-surface border border-white/5 p-6 rounded-2xl">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Zap size={20} className="text-yellow-400" />
                            Message of the Day (MOTD)
                        </h3>

                        {/* Color Palette */}
                        <div className="flex flex-wrap gap-2 mb-4 p-3 bg-black/20 rounded-lg">
                            {[
                                { c: '0', bg: '#000000', n: 'Black' }, { c: '1', bg: '#0000AA', n: 'Dark Blue' },
                                { c: '2', bg: '#00AA00', n: 'Dark Green' }, { c: '3', bg: '#00AAAA', n: 'Dark Aqua' },
                                { c: '4', bg: '#AA0000', n: 'Dark Red' }, { c: '5', bg: '#AA00AA', n: 'Dark Purple' },
                                { c: '6', bg: '#FFAA00', n: 'Gold' }, { c: '7', bg: '#AAAAAA', n: 'Gray' },
                                { c: '8', bg: '#555555', n: 'Dark Gray' }, { c: '9', bg: '#5555FF', n: 'Blue' },
                                { c: 'a', bg: '#55FF55', n: 'Green' }, { c: 'b', bg: '#55FFFF', n: 'Aqua' },
                                { c: 'c', bg: '#FF5555', n: 'Red' }, { c: 'd', bg: '#FF55FF', n: 'Light Purple' },
                                { c: 'e', bg: '#FFFF55', n: 'Yellow' }, { c: 'f', bg: '#FFFFFF', n: 'White' }
                            ].map(col => (
                                <button
                                    key={col.c}
                                    onClick={() => insertColorCode(col.c)}
                                    className="w-6 h-6 rounded hover:scale-110 transition-transform shadow-sm border border-white/10"
                                    style={{ backgroundColor: col.bg }}
                                    title={`&${col.c} - ${col.n}`}
                                />
                            ))}
                            <div className="w-px h-6 bg-white/10 mx-1"></div>
                            {[
                                { c: 'l', l: 'B', s: 'font-bold' }, { c: 'o', l: 'I', s: 'italic' },
                                { c: 'n', l: 'U', s: 'underline' }, { c: 'm', l: 'S', s: 'line-through' }
                            ].map(style => (
                                <button
                                    key={style.c}
                                    onClick={() => insertColorCode(style.c)}
                                    className={`w-6 h-6 rounded bg-zinc-800 text-gray-300 hover:bg-zinc-700 hover:text-white transition-colors text-xs font-serif ${style.s} border border-white/5`}
                                    title={`&${style.c}`}
                                >
                                    {style.l}
                                </button>
                            ))}
                        </div>

                        <textarea
                            id="motd-input"
                            value={serverProps['motd'] || ''}
                            onChange={(e) => handlePropChange('motd', e.target.value)}
                            className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-primary outline-none transition-colors font-mono text-lg h-32"
                            placeholder="A Minecraft Server"
                        />
                        <p className="text-sm text-gray-500 mt-2">Use the color buttons above or type <code>&code</code> to add colors.</p>
                    </div>
                </div>
            )}

            {showAdvanced && (
                <AdvancedSettingsModal
                    onClose={() => setShowAdvanced(false)}
                    properties={serverProps}
                    onSave={(newProps) => {
                        setServerProps(newProps);
                        // Optional: Trigger auto-save or just rely on the main Save button
                    }}
                />
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

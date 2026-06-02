import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api';
import { Save, Server, Monitor, Shield, Zap, Globe, FolderOpen, CircuitBoard, Cpu, HardDrive, Settings as SettingsIcon } from './ui/PixelIcons';
import { Select } from './ui/Select';
import AdvancedSettingsModal from './AdvancedSettingsModal';
import MotdPreview from './MotdPreview';
import { Palette, Upload } from './ui/PixelIcons';
import { useTranslation } from '../contexts/LanguageContext';

export default function Settings() {
    const { t } = useTranslation();
    const [activeTab, setActiveTab] = useState('general');
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [systemInfo, setSystemInfo] = useState(null);

    const [serverProps, setServerProps] = useState({});
    const [appSettings, setAppSettings] = useState({
        ram_min: "2",
        ram_max: "4",
        ram_unit: "G",
        java_path: "java"
    });

    const [iconTs, setIconTs] = useState(Date.now());
    const API_BASE = "http://127.0.0.1:8000";

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
            try {
                const res = await fetch('http://127.0.0.1:8000/system/info');
                if (res.ok) setSystemInfo(await res.json());
            } catch (_) {}
        } catch (e) {
            setError(e?.message || t('server_settings.error_loading'));
        }
        setLoading(false);
    };

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        try {
            await api.updateServerProperties(serverProps);
            await api.updateAppSettings(appSettings);
        } catch (e) {
            setError(e?.message || t('server_settings.error_saving'));
        }
        setSaving(false);
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
            setIconTs(Date.now());
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
        setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(start + 2, start + 2);
        }, 0);
    };

    if (loading) return <div className="p-8 text-center text-zinc-500 font-minecraft tracking-widest uppercase">{t('server_settings.loading')}</div>;

    if (error) {
        return (
            <div className="p-8 text-center">
                <div className="text-red-400 font-minecraft uppercase tracking-wider mb-2">{t('server_settings.error_title')}</div>
                <div className="text-gray-500 text-sm mb-4">{error}</div>
                <button onClick={loadSettings} className="bg-transparent border border-white/10 hover:bg-white/5 text-white px-4 py-2 rounded-md transition-colors font-minecraft uppercase text-xs">{t('common.retry')}</button>
            </div>
        );
    }

    return (
        <div className="animate-in fade-in zoom-in duration-500 w-full h-full">
            <div className="flex flex-col md:flex-row gap-8 max-w-6xl mx-auto items-start h-full pb-10">
                
                {/* Left Navigation Rails */}
                <div className="w-full md:w-64 shrink-0 flex flex-col gap-2 sticky top-0">
                    <div className="mb-6">
                        <h2 className="text-4xl font-minecraft tracking-tight text-emerald-400 mb-1">{t('server_settings.title')}</h2>
                        <p className="text-zinc-500 text-sm font-medium">{t('server_settings.subtitle')}</p>
                    </div>

                    <div className="flex flex-col gap-1">
                        {[
                            { id: 'general', label: t('server_settings.sections.general') },
                            { id: 'gameplay', label: t('server_settings.sections.gameplay') },
                            { id: 'network', label: t('server_settings.sections.network') },
                            { id: 'security', label: t('server_settings.sections.security') },
                            { id: 'appearance', label: t('server_settings.sections.appearance') },
                            { id: 'system', label: t('server_settings.sections.system') },
                        ].map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`w-full text-left px-4 py-3 rounded-md font-minecraft tracking-wider uppercase text-sm transition-all duration-200 border-l-2 ${
                                    activeTab === tab.id
                                        ? 'bg-white/10 text-emerald-400 border-emerald-400 shadow-sm'
                                        : 'border-transparent text-zinc-500 hover:text-white hover:bg-white/5'
                                }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    <div className="mt-8 pt-6 border-t border-white/5 space-y-3">
                        <button
                            onClick={() => api.openServerFolder()}
                            className="w-full bg-transparent hover:bg-white/5 text-zinc-400 hover:text-white px-4 py-3 rounded-md flex items-center justify-center gap-3 transition-colors border border-white/10 font-minecraft uppercase tracking-wider text-xs"
                        >
                            <FolderOpen size={16} /> {t('server_settings.open_directory')}
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="w-full bg-emerald-500/10 hover:bg-emerald-500 text-emerald-400 hover:text-black px-4 py-3 rounded-md flex items-center justify-center gap-3 transition-all border border-emerald-500/30 font-minecraft uppercase tracking-wider text-xs group shadow-[0_0_15px_max(0px,rgba(16,185,129,0.1))] hover:shadow-[0_0_20px_max(0px,rgba(16,185,129,0.4))]"
                        >
                            <Save size={16} className="group-hover:animate-bounce" /> {saving ? t('server_settings.saving') : t('server_settings.save_config')}
                        </button>
                    </div>
                </div>

                {/* Right Content Pane */}
                <div className="flex-1 w-full min-w-0">
                    <div className="bg-[#18181b]/60 backdrop-blur-xl border border-white/5 p-8 rounded-md min-h-[600px] shadow-2xl relative overflow-hidden">
                        
                        {/* Removed background glow per user feedback */}

                        {activeTab === 'general' && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 duration-300 relative z-10">
                                <h3 className="text-xl font-minecraft text-white uppercase tracking-wider mb-6 border-b border-white/5 pb-4">{t('server_settings.sections.general')}</h3>
                                
                                <div className="grid grid-cols-1 gap-6">
                                    <div className="grid grid-cols-2 gap-6">
                                        <SettingInput label={t('server_settings.props.server_port')} value={serverProps['server-port'] || '25565'} onChange={(v) => handlePropChange('server-port', v)} type="number" />
                                        <div className="flex flex-col">
                                            <label className="text-xs font-medium text-zinc-500 mb-1 uppercase tracking-wider">{t('server_settings.props.level_type')}</label>
                                            <Select
                                                value={serverProps['level-type'] || 'default'}
                                                onChange={(val) => handlePropChange('level-type', val)}
                                                options={[
                                                    { value: 'default', label: t('server_settings.props.level_types.default') },
                                                    { value: 'flat', label: t('server_settings.props.level_types.flat') },
                                                    { value: 'large_biomes', label: t('server_settings.props.level_types.large_biomes') },
                                                    { value: 'amplified', label: t('server_settings.props.level_types.amplified') }
                                                ]}
                                            />
                                        </div>
                                    </div>
                                    <SettingInput label={t('server_settings.props.world_seed')} placeholder={t('server_settings.props.world_seed_placeholder')} value={serverProps['level-seed'] || ''} onChange={(v) => handlePropChange('level-seed', v)} />
                                </div>
                            </div>
                        )}

                        {activeTab === 'gameplay' && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 duration-300 relative z-10">
                                <h3 className="text-xl font-minecraft text-white uppercase tracking-wider mb-6 border-b border-white/5 pb-4">{t('server_settings.sections.gameplay')}</h3>
                                
                                <div className="grid grid-cols-2 gap-6 mb-6">
                                    <div className="flex flex-col">
                                        <label className="text-xs font-medium text-zinc-500 mb-1 uppercase tracking-wider">{t('server_settings.props.difficulty')}</label>
                                        <Select
                                            value={serverProps['difficulty'] || 'easy'}
                                            onChange={(val) => handlePropChange('difficulty', val)}
                                            options={[
                                                { value: 'peaceful', label: t('server_settings.props.difficulties.peaceful') },
                                                { value: 'easy', label: t('server_settings.props.difficulties.easy') },
                                                { value: 'normal', label: t('server_settings.props.difficulties.normal') },
                                                { value: 'hard', label: t('server_settings.props.difficulties.hard') }
                                            ]}
                                        />
                                    </div>
                                    <div className="flex flex-col">
                                        <label className="text-xs font-medium text-zinc-500 mb-1 uppercase tracking-wider">{t('server_settings.props.gamemode')}</label>
                                        <Select
                                            value={serverProps['gamemode'] || 'survival'}
                                            onChange={(val) => handlePropChange('gamemode', val)}
                                            options={[
                                                { value: 'survival', label: t('server_settings.props.gamemodes.survival') },
                                                { value: 'creative', label: t('server_settings.props.gamemodes.creative') },
                                                { value: 'adventure', label: t('server_settings.props.gamemodes.adventure') },
                                                { value: 'spectator', label: t('server_settings.props.gamemodes.spectator') }
                                            ]}
                                        />
                                    </div>
                                </div>

                                <div className="space-y-2 grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <LabelToggle label={t('server_settings.props.pvp')} desc={t('server_settings.props_desc.pvp')} checked={serverProps['pvp'] === 'true'} onChange={(v) => handlePropChange('pvp', v.toString())} />
                                    <LabelToggle label={t('server_settings.props.hardcore')} desc={t('server_settings.props_desc.hardcore')} color="text-red-400" checked={serverProps['hardcore'] === 'true'} onChange={(v) => handlePropChange('hardcore', v.toString())} />
                                    <LabelToggle label={t('server_settings.props.allow_nether')} desc={t('server_settings.props_desc.allow_nether')} checked={serverProps['allow-nether'] !== 'false'} onChange={(v) => handlePropChange('allow-nether', v.toString())} />
                                    <LabelToggle label={t('server_settings.props.allow_flight')} desc={t('server_settings.props_desc.allow_flight')} checked={serverProps['allow-flight'] === 'true'} onChange={(v) => handlePropChange('allow-flight', v.toString())} />
                                    <LabelToggle label={t('server_settings.props.enable_command_block')} desc={t('server_settings.props_desc.enable_command_block')} checked={serverProps['enable-command-block'] === 'true'} onChange={(v) => handlePropChange('enable-command-block', v.toString())} />
                                    <LabelToggle label={t('server_settings.props.spawn_animals')} desc={t('server_settings.props_desc.spawn_animals')} checked={serverProps['spawn-animals'] !== 'false'} onChange={(v) => handlePropChange('spawn-animals', v.toString())} />
                                    <LabelToggle label={t('server_settings.props.spawn_monsters')} desc={t('server_settings.props_desc.spawn_monsters')} checked={serverProps['spawn-monsters'] !== 'false'} onChange={(v) => handlePropChange('spawn-monsters', v.toString())} />
                                </div>
                            </div>
                        )}

                        {activeTab === 'network' && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 duration-300 relative z-10">
                                <h3 className="text-xl font-minecraft text-white uppercase tracking-wider mb-6 border-b border-white/5 pb-4">{t('server_settings.sections.network')}</h3>
                                <div className="space-y-6 max-w-lg">
                                    <SettingInput label={t('server_settings.props.max_players')} value={serverProps['max-players'] || '20'} onChange={(v) => handlePropChange('max-players', v)} type="number" />
                                    <SettingInput label={t('server_settings.props.view_distance')} value={serverProps['view-distance'] || '10'} onChange={(v) => handlePropChange('view-distance', v)} type="number" min="2" max="32" />
                                    <SettingInput label={t('server_settings.props.simulation_distance')} value={serverProps['simulation-distance'] || '10'} onChange={(v) => handlePropChange('simulation-distance', v)} type="number" min="2" max="32" />
                                </div>
                            </div>
                        )}

                        {activeTab === 'security' && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 duration-300 relative z-10">
                                <h3 className="text-xl font-minecraft text-white uppercase tracking-wider mb-6 border-b border-white/5 pb-4">{t('server_settings.sections.security')}</h3>
                                <div className="space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                                        <LabelToggle label={t('server_settings.props.online_mode')} desc={t('server_settings.props_desc.online_mode')} checked={serverProps['online-mode'] === 'true'} onChange={(v) => handlePropChange('online-mode', v.toString())} />
                                        <LabelToggle label={t('server_settings.props.whitelist')} desc={t('server_settings.props_desc.whitelist')} checked={serverProps['white-list'] === 'true'} onChange={(v) => handlePropChange('white-list', v.toString())} />
                                        <LabelToggle label={t('server_settings.props.enforce_whitelist')} desc={t('server_settings.props_desc.enforce_whitelist')} checked={serverProps['enforce-whitelist'] === 'true'} onChange={(v) => handlePropChange('enforce-whitelist', v.toString())} />
                                        <LabelToggle label={t('server_settings.props.force_gamemode')} desc={t('server_settings.props_desc.force_gamemode')} checked={serverProps['force-gamemode'] === 'true'} onChange={(v) => handlePropChange('force-gamemode', v.toString())} />
                                    </div>

                                    <div className="p-6 border border-white/5 bg-black/20 rounded-md">
                                        <div className="mb-4">
                                            <h4 className="text-white font-minecraft uppercase tracking-wider mb-1">{t('server_settings.raw_config.title')}</h4>
                                            <p className="text-xs text-zinc-500">{t('server_settings.raw_config.desc')}</p>
                                        </div>
                                        <button
                                            onClick={() => setShowAdvanced(true)}
                                            className="w-full md:w-auto px-6 py-3 bg-transparent border border-white/20 hover:border-white/40 text-white rounded-md font-minecraft uppercase tracking-wider text-xs transition-all flex items-center justify-center gap-2 group"
                                        >
                                            <SettingsIcon size={16} className="group-hover:rotate-90 transition-transform duration-500" />
                                            {t('server_settings.raw_config.button')}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'appearance' && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 duration-300 relative z-10">
                                <h3 className="text-xl font-minecraft text-white uppercase tracking-wider mb-6 border-b border-white/5 pb-4">Appearance & Icon</h3>
                                
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                    <div className="space-y-4">
                                        <div className="flex flex-col items-center justify-center p-6 bg-black/30 rounded-md border border-white/5 border-dashed hover:border-emerald-500/50 transition-colors group">
                                            <div className="w-[64px] h-[64px] mb-6 relative drop-shadow-2xl">
                                                <img
                                                    src={`${API_BASE}/server/icon/image?t=${iconTs}`}
                                                    onError={(e) => e.target.src = "https://static.wikia.nocookie.net/minecraft_gamepedia/images/4/44/Grass_Block_Revision_6.png"}
                                                    className="w-full h-full object-contain pixelated rounded-sm"
                                                    alt="Server Icon"
                                                />
                                            </div>
                                            <label className="cursor-pointer bg-transparent border border-white/10 hover:bg-white/5 text-zinc-300 hover:text-white px-4 py-2 rounded-md flex items-center gap-2 transition-colors font-minecraft uppercase tracking-wider text-xs">
                                                <Upload size={14} />
                                                <span>{t('server_settings.appearance.upload_icon')}</span>
                                                <input type="file" className="hidden" accept="image/png,image/jpeg" onChange={handleIconUpload} />
                                            </label>
                                        </div>
                                        
                                        <div className="bg-black/80 p-4 rounded-sm flex items-center justify-center min-h-[140px] border border-white/5 relative overflow-hidden">
                                            <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "url('/images/Dirt_background_BE1.webp')", backgroundSize: '64px' }} />
                                            <div className="relative z-10 w-full flex justify-center">
                                                <MotdPreview motd={serverProps['motd']} iconUrl={`${API_BASE}/server/icon/image?t=${iconTs}`} />
                                            </div>
                                        </div>
                                    </div>

                                    <div className="space-y-4">
                                        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{t('server_settings.appearance.motd_label')}</label>
                                        
                        <div className="flex flex-wrap gap-1.5 p-2 bg-black/40 rounded-sm border border-white/5">
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
                                    key={col.c} onClick={() => insertColorCode(col.c)}
                                    className="w-5 h-5 rounded-sm hover:scale-110 transition-transform shadow-sm border border-white/20"
                                    style={{ backgroundColor: col.bg }} title={`&${col.c} - ${col.n}`}
                                />
                            ))}
                            <div className="w-px h-5 bg-white/10 mx-2"></div>
                            {[
                                { c: 'l', l: 'B', s: 'font-bold' }, { c: 'o', l: 'I', s: 'italic' },
                                { c: 'n', l: 'U', s: 'underline' }, { c: 'm', l: 'S', s: 'line-through' }
                            ].map(style => (
                                <button
                                    key={style.c} onClick={() => insertColorCode(style.c)}
                                    className={`w-5 h-5 rounded-sm bg-transparent text-gray-400 hover:text-white hover:bg-white/10 transition-colors text-xs font-serif ${style.s} border border-transparent`}
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
                                            className="w-full bg-black/50 border border-white/10 rounded-md px-4 py-3 text-emerald-400 focus:border-emerald-500 outline-none transition-colors font-minecraft text-lg h-32 resize-none"
                                            placeholder="A Minecraft Server"
                                        />
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'system' && (
                            <div className="space-y-8 animate-in slide-in-from-right-4 duration-300 relative z-10 w-full max-w-xl">
                                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                                    <h3 className="text-xl font-minecraft text-white uppercase tracking-wider">{t('server_settings.sections.system')}</h3>
                                    {systemInfo && (
                                        <span className="text-xs font-minecraft text-zinc-500 uppercase tracking-widest">
                                            {t('server_settings.system.host_ram').replace('{ram}', systemInfo.total_ram_gb)}
                                        </span>
                                    )}
                                </div>

                                <div>
                                    <div className="flex justify-between items-end mb-4">
                                        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{t('server_settings.system.max_ram')}</label>
                                        <span className="text-3xl font-minecraft text-emerald-400 tracking-wider shadow-emerald-500 drop-shadow-md">{appSettings.ram_max} GB</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="1"
                                        max={systemInfo ? Math.floor(systemInfo.max_recommended_ram_gb) : 32}
                                        step="1"
                                        value={appSettings.ram_max || 4}
                                        onChange={(e) => handleAppChange('ram_max', e.target.value)}
                                        className="w-full h-2 bg-black/60 rounded-sm appearance-none cursor-pointer ram-slider border border-white/10"
                                    />
                                    
                                    {systemInfo && Number(appSettings.ram_max) > systemInfo.total_ram_gb * 0.5 && (
                                        <div className={`mt-4 px-4 py-3 rounded-md text-sm font-medium flex items-center gap-3 border ${
                                            Number(appSettings.ram_max) > systemInfo.total_ram_gb * 0.75
                                                ? 'bg-red-500/10 border-red-500/30 text-red-400'
                                                : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                                        }`}>
                                            <span>{Number(appSettings.ram_max) > systemInfo.total_ram_gb * 0.75 ? '⚠️' : '⚡'}</span>
                                            <span className="font-mono text-xs">
                                                {Number(appSettings.ram_max) > systemInfo.total_ram_gb * 0.75
                                                    ? `CRITICAL OVERALLOCATION: Leaves insufficient RAM for host OS.`
                                                    : `Warning: Using ${Math.round(Number(appSettings.ram_max) / systemInfo.total_ram_gb * 100)}% memory.`
                                                }
                                            </span>
                                        </div>
                                    )}
                                </div>

                                <div>
                                    <div className="flex justify-between items-end mb-4">
                                        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{t('server_settings.system.min_ram')}</label>
                                        <span className="text-xl font-minecraft text-zinc-300 tracking-wider">{appSettings.ram_min} GB</span>
                                    </div>
                                    <input
                                        type="range" min="1" max={appSettings.ram_max || 16} step="1"
                                        value={appSettings.ram_min || 2}
                                        onChange={(e) => handleAppChange('ram_min', e.target.value)}
                                        className="w-full h-2 bg-black/60 rounded-sm appearance-none cursor-pointer ram-slider border border-white/10"
                                    />
                                </div>

                                <div className="pt-6 border-t border-white/5">
                                    <label className="text-xs font-medium text-zinc-500 mb-1 uppercase tracking-wider">{t('server_settings.system.java_path')}</label>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={appSettings.java_path}
                                            placeholder="java"
                                            onChange={(e) => handleAppChange('java_path', e.target.value)}
                                            className="flex-1 bg-black/40 border border-white/10 rounded-md px-4 py-2 text-white focus:border-emerald-500 focus:bg-black/60 outline-none transition-all font-mono text-sm"
                                        />
                                        <button
                                            onClick={async () => {
                                                const p = await api.openFilePicker();
                                                if (p) handleAppChange('java_path', p);
                                            }}
                                            className="px-4 py-2 bg-white/5 border border-white/10 rounded-md text-xs text-gray-400 hover:text-white hover:bg-white/10 transition-all font-minecraft"
                                        >
                                            {t('server_settings.system.browse')}
                                        </button>
                                    </div>
                                    <p className="text-[10px] text-zinc-600 uppercase tracking-widest mt-2">{t('server_settings.system.java_path_desc')}</p>
                                </div>
                            </div>
                        )}
                        
                    </div>
                </div>

            </div>

            {showAdvanced && (
                <AdvancedSettingsModal
                    onClose={() => setShowAdvanced(false)}
                    properties={serverProps}
                    onSave={(newProps) => setServerProps(newProps)}
                />
            )}
        </div>
    );
}

// Utility Components
function SettingInput({ label, value, onChange, type = "text", placeholder, min, max }) {
    return (
        <div className="flex flex-col">
            <label className="text-xs font-medium text-zinc-500 mb-1 uppercase tracking-wider">{label}</label>
            <input
                type={type}
                min={min} max={max}
                value={value}
                placeholder={placeholder}
                onChange={(e) => onChange(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-md px-4 py-2 text-white focus:border-emerald-500 focus:bg-black/60 outline-none transition-all font-mono text-sm"
            />
        </div>
    );
}

function LabelToggle({ label, desc, checked, onChange, color = "text-zinc-200" }) {
    return (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-black/20 rounded-md border border-white/5 hover:border-white/10 transition-colors gap-4">
            <div className="flex flex-col">
                <span className={`font-minecraft uppercase tracking-wider text-sm ${color}`}>{label}</span>
                {desc && <span className="text-xs text-zinc-500 font-medium">{desc}</span>}
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input type="checkbox" className="sr-only peer" checked={checked} onChange={(e) => onChange(e.target.checked)} />
                <div className="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-sm peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-sm after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500 drop-shadow-sm"></div>
            </label>
        </div>
    );
}

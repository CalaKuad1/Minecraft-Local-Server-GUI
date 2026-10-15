import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { api, API_TOKEN, API_URL } from '../api';
import { Save, Server, Shield, Zap, Globe, FolderOpen, Cpu, Palette, Upload, Settings as SettingsIcon, AlertTriangle } from './ui/PixelIcons';
import { Select } from './ui/Select';
import { Toggle } from './ui/Toggle';
import AdvancedSettingsModal from './AdvancedSettingsModal';
import MotdPreview from './MotdPreview';
import { useTranslation } from '../contexts/LanguageContext';
import { PageHeader, Segmented, SettingGroup, SettingRow, EmptyState } from './ui/Page';
import { inputClass } from '../utils/format';
import Cubi from './ui/Cubi';

// Newer servers write `level-type=minecraft\:normal` (namespaced, escaped);
// older ones use `default`. Show both as the same option and write back in
// whichever format the server already uses.
const LEVEL_NS = /^minecraft\\?:/;
const levelTypeKey = (raw) => {
    const key = (raw || 'default').replace(LEVEL_NS, '');
    return key === 'normal' ? 'default' : key;
};
const levelTypeValue = (key, previousRaw) => {
    if (!LEVEL_NS.test(previousRaw || '')) return key;
    return `minecraft\\:${key === 'default' ? 'normal' : key}`;
};

const MOTD_COLORS = [
    ['0', '#000000'], ['1', '#0000AA'], ['2', '#00AA00'], ['3', '#00AAAA'], ['4', '#AA0000'], ['5', '#AA00AA'],
    ['6', '#FFAA00'], ['7', '#AAAAAA'], ['8', '#555555'], ['9', '#5555FF'], ['a', '#55FF55'], ['b', '#55FFFF'],
    ['c', '#FF5555'], ['d', '#FF55FF'], ['e', '#FFFF55'], ['f', '#FFFFFF'],
];
const MOTD_STYLES = [['l', 'B', 'font-bold'], ['o', 'I', 'italic'], ['n', 'U', 'underline'], ['m', 'S', 'line-through']];

export default function Settings() {
    const { t } = useTranslation();
    const [tab, setTab] = useState('general');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [error, setError] = useState(null);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [systemInfo, setSystemInfo] = useState(null);
    const [props, setProps] = useState({});
    const [app, setApp] = useState({ ram_min: '2', ram_max: '4', ram_unit: 'G', java_path: 'java' });
    const [iconTs, setIconTs] = useState(Date.now());
    const [iconExists, setIconExists] = useState(false);

    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const [p, a] = await Promise.all([api.getServerProperties(), api.getAppSettings()]);
            setProps(p);
            setApp(a);
            setDirty(false);
            try {
                const res = await fetch(`${API_URL}/system/info`, { headers: API_TOKEN ? { 'X-MLSG-Token': API_TOKEN } : {} });
                if (res.ok) setSystemInfo(await res.json());
            } catch { /* optional */ }
            try {
                const s = await api.getServerIconStatus();
                setIconExists(!!s?.exists);
            } catch { /* optional */ }
        } catch (e) {
            setError(e?.message || t('server_settings.error_loading'));
        }
        setLoading(false);
    };

    useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const save = async () => {
        setSaving(true);
        setError(null);
        try {
            await api.updateServerProperties(props);
            await api.updateAppSettings(app);
            setDirty(false);
            setSaved(true);
            setTimeout(() => setSaved(false), 2200);
        } catch (e) {
            setError(e?.message || t('server_settings.error_saving'));
        }
        setSaving(false);
    };

    const setProp = (key, value) => { setDirty(true); setProps((p) => ({ ...p, [key]: value })); };
    const setAppKey = (key, value) => { setDirty(true); setApp((a) => ({ ...a, [key]: value })); };
    const bool = (key, dflt = false) => (props[key] === undefined ? dflt : props[key] === 'true');
    const toggle = (key, dflt = false) => (
        <Toggle checked={bool(key, dflt)} onChange={(v) => setProp(key, v.toString())} label={key} />
    );
    const num = (key, dflt, w = 'w-24', extra = {}) => (
        <input type="number" value={props[key] ?? dflt} onChange={(e) => setProp(key, e.target.value)} className={`${inputClass} ${w} text-right tabular-nums`} {...extra} />
    );

    const handleIconUpload = async (e) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file) return;
        try {
            await api.uploadServerIcon(file);
            setIconExists(true);
            setIconTs(Date.now());
        } catch (err) {
            setError(`${t('server_settings.appearance.upload_failed')} ${err.message}`);
        }
    };

    const insertMotdCode = (code) => {
        const ta = document.getElementById('motd-input');
        if (!ta) return;
        const { selectionStart: a, selectionEnd: b } = ta;
        const text = props.motd || '';
        setProp('motd', `${text.slice(0, a)}&${code}${text.slice(b)}`);
        setTimeout(() => { ta.focus(); ta.setSelectionRange(a + 2, a + 2); }, 0);
    };

    if (loading) return <div className="p-8 text-center text-ink-faint">{t('server_settings.loading')}</div>;
    if (error && !Object.keys(props).length) {
        return (
            <EmptyState icon={<Cubi mood="sad" size={64} />} title={t('server_settings.error_title')}>
                <p>{error}</p>
                <button onClick={load} className="mt-3 rounded-md border border-white/10 px-4 py-2 text-sm text-ink hover:bg-white/5">{t('common.retry')}</button>
            </EmptyState>
        );
    }

    const iconUrl = iconExists ? `${API_URL}/server/icon/image?t=${iconTs}` : undefined;
    const ramMax = Number(app.ram_max) || 4;
    const totalRam = systemInfo?.total_ram_gb;
    const ramShare = totalRam ? ramMax / totalRam : 0;
    const unit = app.ram_unit === 'M' ? 'MB' : 'GB';

    const tabs = [
        { value: 'general', label: t('server_settings.tabs.general'), icon: Server },
        { value: 'gameplay', label: t('server_settings.tabs.gameplay'), icon: Zap },
        { value: 'network', label: t('server_settings.tabs.network'), icon: Globe },
        { value: 'security', label: t('server_settings.tabs.security'), icon: Shield },
        { value: 'appearance', label: t('server_settings.tabs.appearance'), icon: Palette },
        { value: 'system', label: t('server_settings.tabs.system'), icon: Cpu },
    ];

    return (
        <div className="relative flex min-h-full flex-col gap-4 pb-20 animate-in fade-in duration-200">
            <PageHeader
                title={t('server_settings.title')}
                subtitle={t('server_settings.subtitle_new')}
                actions={(
                    <>
                        <button onClick={() => api.openServerFolder()} className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">
                            <FolderOpen size={15} /> {t('server_settings.open_directory')}
                        </button>
                        <button onClick={() => setShowAdvanced(true)} className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">
                            <SettingsIcon size={15} /> {t('server_settings.raw_config.button')}
                        </button>
                    </>
                )}
            />

            <div className="overflow-x-auto"><Segmented value={tab} onChange={setTab} options={tabs} layoutId="settings-tabs" /></div>
            {error && <div className="rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-300">{error}</div>}

            <div className="max-w-3xl space-y-5">
                {tab === 'general' && (
                    <SettingGroup>
                        <SettingRow label={t('server_settings.props.server_port')} description={t('server_settings.props_desc.server_port')}>
                            {num('server-port', '25565', 'w-28')}
                        </SettingRow>
                        <SettingRow label={t('server_settings.props.max_players')} description={t('server_settings.props_desc.max_players')}>
                            {num('max-players', '20')}
                        </SettingRow>
                        <SettingRow label={t('server_settings.props.level_type')} description={t('server_settings.props_desc.level_type')}>
                            <div className="w-48">
                                <Select
                                    value={levelTypeKey(props['level-type'])}
                                    onChange={(v) => setProp('level-type', levelTypeValue(v, props['level-type']))}
                                    options={['default', 'flat', 'large_biomes', 'amplified'].map((v) => ({ value: v, label: t(`server_settings.props.level_types.${v}`) }))}
                                />
                            </div>
                        </SettingRow>
                        <SettingRow label={t('server_settings.props.world_seed')} description={t('server_settings.props_desc.world_seed')}>
                            <input value={props['level-seed'] || ''} onChange={(e) => setProp('level-seed', e.target.value)} placeholder={t('server_settings.props.world_seed_placeholder')} className={`${inputClass} w-56`} />
                        </SettingRow>
                    </SettingGroup>
                )}

                {tab === 'gameplay' && (
                    <>
                        <SettingGroup>
                            <SettingRow label={t('server_settings.props.difficulty')}>
                                <div className="w-44">
                                    <Select value={props.difficulty || 'easy'} onChange={(v) => setProp('difficulty', v)} options={['peaceful', 'easy', 'normal', 'hard'].map((v) => ({ value: v, label: t(`server_settings.props.difficulties.${v}`) }))} />
                                </div>
                            </SettingRow>
                            <SettingRow label={t('server_settings.props.gamemode')}>
                                <div className="w-44">
                                    <Select value={props.gamemode || 'survival'} onChange={(v) => setProp('gamemode', v)} options={['survival', 'creative', 'adventure', 'spectator'].map((v) => ({ value: v, label: t(`server_settings.props.gamemodes.${v}`) }))} />
                                </div>
                            </SettingRow>
                            <SettingRow label={t('server_settings.props.hardcore')} description={t('server_settings.props_desc.hardcore')} tone="text-red-300">{toggle('hardcore')}</SettingRow>
                        </SettingGroup>
                        <SettingGroup title={t('server_settings.groups.world_rules')}>
                            <SettingRow label={t('server_settings.props.pvp')} description={t('server_settings.props_desc.pvp')}>{toggle('pvp', true)}</SettingRow>
                            <SettingRow label={t('server_settings.props.allow_nether')} description={t('server_settings.props_desc.allow_nether')}>{toggle('allow-nether', true)}</SettingRow>
                            <SettingRow label={t('server_settings.props.allow_flight')} description={t('server_settings.props_desc.allow_flight')}>{toggle('allow-flight')}</SettingRow>
                            <SettingRow label={t('server_settings.props.spawn_animals')} description={t('server_settings.props_desc.spawn_animals')}>{toggle('spawn-animals', true)}</SettingRow>
                            <SettingRow label={t('server_settings.props.spawn_monsters')} description={t('server_settings.props_desc.spawn_monsters')}>{toggle('spawn-monsters', true)}</SettingRow>
                            <SettingRow label={t('server_settings.props.enable_command_block')} description={t('server_settings.props_desc.enable_command_block')}>{toggle('enable-command-block')}</SettingRow>
                        </SettingGroup>
                    </>
                )}

                {tab === 'network' && (
                    <SettingGroup>
                        {[['view-distance', 'view_distance'], ['simulation-distance', 'simulation_distance']].map(([key, label]) => {
                            const v = Number(props[key] || 10);
                            return (
                                <SettingRow key={key} label={t(`server_settings.props.${label}`)} description={t(`server_settings.props_desc.${label}`)}>
                                    <input type="range" min="2" max="32" value={v} onChange={(e) => setProp(key, e.target.value)} className="w-40 accent-emerald-500" />
                                    <span className="w-16 text-right text-sm tabular-nums text-ink">{v} {t('server_settings.chunks')}</span>
                                </SettingRow>
                            );
                        })}
                    </SettingGroup>
                )}

                {tab === 'security' && (
                    <SettingGroup>
                        <SettingRow label={t('server_settings.props.online_mode')} description={t('server_settings.props_desc.online_mode')}>{toggle('online-mode', true)}</SettingRow>
                        <SettingRow label={t('server_settings.props.whitelist')} description={t('server_settings.props_desc.whitelist')}>{toggle('white-list')}</SettingRow>
                        <SettingRow label={t('server_settings.props.enforce_whitelist')} description={t('server_settings.props_desc.enforce_whitelist')}>{toggle('enforce-whitelist')}</SettingRow>
                        <SettingRow label={t('server_settings.props.force_gamemode')} description={t('server_settings.props_desc.force_gamemode')}>{toggle('force-gamemode')}</SettingRow>
                    </SettingGroup>
                )}

                {tab === 'appearance' && (
                    <div className="space-y-5">
                        <div className="rounded-lg border border-white/[0.06] bg-black/60 p-4">
                            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">{t('server_settings.appearance.preview')}</div>
                            <MotdPreview motd={props.motd} iconUrl={iconUrl} />
                        </div>
                        <SettingGroup>
                            <SettingRow label={t('server_settings.appearance.icon')} description={t('server_settings.appearance.icon_desc')}>
                                {iconUrl && <img src={iconUrl} alt="" className="h-10 w-10 rounded" style={{ imageRendering: 'pixelated' }} onError={() => setIconExists(false)} />}
                                <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-white/10 px-3 py-1.5 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">
                                    <Upload size={14} /> {t('server_settings.appearance.upload_icon')}
                                    <input type="file" className="hidden" accept="image/png,image/jpeg" onChange={handleIconUpload} />
                                </label>
                            </SettingRow>
                            <div className="space-y-2 px-4 py-3.5">
                                <div className="text-sm font-semibold text-ink">{t('server_settings.appearance.motd_label')}</div>
                                <div className="flex flex-wrap items-center gap-1">
                                    {MOTD_COLORS.map(([c, bg]) => (
                                        <button key={c} onClick={() => insertMotdCode(c)} className="h-5 w-5 rounded border border-white/20 transition-transform hover:scale-110" style={{ backgroundColor: bg }} title={`&${c}`} aria-label={`&${c}`} />
                                    ))}
                                    <span className="mx-1.5 h-5 w-px bg-white/10" />
                                    {MOTD_STYLES.map(([c, l, cls]) => (
                                        <button key={c} onClick={() => insertMotdCode(c)} className={`h-6 w-6 rounded text-xs text-ink-dim hover:bg-white/10 hover:text-ink ${cls}`} title={`&${c}`}>{l}</button>
                                    ))}
                                </div>
                                <textarea
                                    id="motd-input"
                                    value={props.motd || ''}
                                    onChange={(e) => setProp('motd', e.target.value)}
                                    rows={2}
                                    className="w-full resize-none rounded-md border border-white/10 bg-ground/70 px-3 py-2 font-mono text-sm text-ink outline-none focus:border-grass/60"
                                    placeholder="A Minecraft Server"
                                />
                            </div>
                        </SettingGroup>
                    </div>
                )}

                {tab === 'system' && (
                    <SettingGroup>
                        <div className="space-y-3 px-4 py-4">
                            <div className="flex items-end justify-between gap-4">
                                <div>
                                    <div className="text-sm font-semibold text-ink">{t('server_settings.system.max_ram')}</div>
                                    <div className="text-xs text-ink-faint">
                                        {totalRam ? t('server_settings.system.host_ram').replace('{ram}', totalRam) : t('server_settings.system.max_ram_desc')}
                                    </div>
                                </div>
                                <div className="font-display text-2xl font-semibold tabular-nums text-mint">{ramMax} {unit}</div>
                            </div>
                            <input
                                type="range" min="1" step="1"
                                max={systemInfo ? Math.max(2, Math.floor(systemInfo.max_recommended_ram_gb)) : 32}
                                value={ramMax}
                                onChange={(e) => setAppKey('ram_max', e.target.value)}
                                className="w-full accent-emerald-500"
                            />
                            <div className="flex flex-wrap gap-1.5">
                                {[2, 4, 6, 8, 12].filter((g) => !totalRam || g <= totalRam * 0.75).map((g) => (
                                    <button key={g} onClick={() => setAppKey('ram_max', String(g))} className={`rounded-full px-2.5 py-1 text-xs font-medium ${ramMax === g ? 'bg-grass/15 text-mint' : 'bg-white/5 text-ink-faint hover:text-ink'}`}>
                                        {g} GB
                                    </button>
                                ))}
                            </div>
                            {ramShare > 0.5 && (
                                <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs ${ramShare > 0.75 ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-amber-400/30 bg-amber-400/10 text-amber-200'}`}>
                                    <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                                    {ramShare > 0.75 ? t('server_settings.system.ram_critical') : t('server_settings.system.ram_warn').replace('{pct}', Math.round(ramShare * 100))}
                                </div>
                            )}
                        </div>
                        <SettingRow label={t('server_settings.system.min_ram')} description={t('server_settings.system.min_ram_desc')}>
                            <input type="number" min="1" max={ramMax} value={app.ram_min || 2} onChange={(e) => setAppKey('ram_min', e.target.value)} className={`${inputClass} w-20 text-right tabular-nums`} />
                            <span className="text-sm text-ink-faint">{unit}</span>
                        </SettingRow>
                        <div className="space-y-2 px-4 py-3.5">
                            <div className="text-sm font-semibold text-ink">{t('server_settings.system.java_path')}</div>
                            <div className="text-xs text-ink-faint">{t('server_settings.system.java_path_desc')}</div>
                            <div className="flex gap-2">
                                <input value={app.java_path || ''} placeholder="java" onChange={(e) => setAppKey('java_path', e.target.value)} className={`${inputClass} flex-1 font-mono`} />
                                <button onClick={async () => { const p = await api.openFilePicker(); if (p) setAppKey('java_path', p); }} className="rounded-md border border-white/10 px-3 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">
                                    {t('server_settings.system.browse')}
                                </button>
                            </div>
                        </div>
                    </SettingGroup>
                )}
            </div>

            {/* Appears only with unsaved changes; server.properties applies on restart. */}
            <AnimatePresence>
                {(dirty || saved) && (
                    <motion.div
                        initial={{ y: 24, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: 24, opacity: 0 }}
                        className="sticky bottom-0 z-20 mt-auto flex max-w-3xl flex-wrap items-center gap-3 rounded-lg border border-white/10 bg-raised/95 px-4 py-3 shadow-2xl backdrop-blur"
                    >
                        <div className="min-w-[12rem] flex-1">
                            <div className="text-sm font-semibold text-ink">{saved ? t('settings.saved') : t('server_settings.unsaved_title')}</div>
                            <div className="text-xs text-ink-faint">{t('server_settings.restart_hint')}</div>
                        </div>
                        {!saved && (
                            <>
                                <button onClick={load} className="rounded-md px-3 py-2 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">{t('server_settings.discard')}</button>
                                <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-md bg-grass px-4 py-2 text-sm font-semibold text-ground hover:bg-mint disabled:opacity-60">
                                    <Save size={15} /> {saving ? t('server_settings.saving') : t('server_settings.save_config')}
                                </button>
                            </>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>

            <AnimatePresence>
                {showAdvanced && (
                    <AdvancedSettingsModal
                        onClose={() => setShowAdvanced(false)}
                        properties={props}
                        onSave={(newProps) => { setProps(newProps); setDirty(true); }}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}

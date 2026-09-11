import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Globe, HardDrive, Check, Clock, Archive, RefreshCw, Download, Trash2, Upload, Save } from './ui/PixelIcons';
import { api } from '../api';
import { useDialog } from './ui/DialogContext';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useTranslation } from '../contexts/LanguageContext';

const parseWorldFromBackup = (name) =>
    name.replace(/-\d{8}-\d{6}(-\d+)?\.zip$/i, '') || name.replace(/\.zip$/i, '');

export default function Worlds() {
    const { t } = useTranslation();
    const dialog = useDialog();
    const { subscribe } = useWebSocket();

    const [worlds, setWorlds] = useState([]);
    const [activeWorld, setActiveWorld] = useState('');
    const [loading, setLoading] = useState(false);
    const [switching, setSwitching] = useState(false);
    const [error, setError] = useState(null);

    const [backups, setBackups] = useState([]);
    const [backupsLoading, setBackupsLoading] = useState(false);
    const [creatingBackup, setCreatingBackup] = useState(false);
    const [busyBackup, setBusyBackup] = useState(null);
    const uploadInputRef = useRef(null);

    const [backupSettings, setBackupSettings] = useState({ enabled: false, interval_minutes: 60, keep: 5 });
    const [savingSettings, setSavingSettings] = useState(false);

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [wList, props, bSettings] = await Promise.all([
                api.getWorlds(),
                api.getServerProperties(),
                api.getBackupSettings().catch(() => null)
            ]);
            setWorlds(wList);
            setActiveWorld(props['level-name'] || 'world');
            if (bSettings) setBackupSettings(bSettings);
        } catch (e) {
            console.error("Failed to load worlds", e);
            setError(e?.message || t('worlds.error'));
            setWorlds([]);
        }
        setLoading(false);
    }, [t]);

    const loadBackups = useCallback(async () => {
        setBackupsLoading(true);
        try {
            const list = await api.getWorldBackups();
            setBackups(Array.isArray(list) ? list : []);
        } catch (e) {
            console.error('Failed to load backups', e);
            setBackups([]);
        } finally {
            setBackupsLoading(false);
        }
    }, []);

    useEffect(() => { loadData(); }, [loadData]);
    useEffect(() => { loadBackups(); }, [loadBackups]);

    useEffect(() => {
        return subscribe('worlds', (item) => {
            if (item?.type === 'backup_created') loadBackups();
        });
    }, [subscribe, loadBackups]);

    const handleCreateBackup = async () => {
        setCreatingBackup(true);
        try {
            await api.createWorldBackup(null);
        } catch (e) {
            dialog.alert(e?.message || t('worlds.backup_error'), t('worlds.backup_error'), 'destructive');
        } finally {
            setCreatingBackup(false);
        }
    };

    const handleRestore = async (name) => {
        const ok = await dialog.confirm(
            t('worlds.restore_confirm').replace('{name}', name),
            t('worlds.restore_title'),
            { variant: 'destructive', confirmLabel: t('worlds.restore') }
        );
        if (!ok) return;
        setBusyBackup(name);
        try {
            await api.restoreWorldBackup(name, null);
            dialog.alert(t('worlds.restored').replace('{name}', name), t('common.confirm'), 'success');
            loadData();
        } catch (e) {
            dialog.alert(e?.message || t('worlds.restore_error'), t('worlds.restore_error'), 'destructive');
        } finally {
            setBusyBackup(null);
        }
    };

    const handleDelete = async (name) => {
        const ok = await dialog.confirm(
            t('worlds.delete_confirm').replace('{name}', name),
            t('worlds.delete_title'),
            { variant: 'destructive', confirmLabel: t('common.delete') }
        );
        if (!ok) return;
        setBusyBackup(name);
        try {
            await api.deleteWorldBackup(name);
            setBackups(prev => prev.filter(b => b.name !== name));
        } catch (e) {
            dialog.alert(e?.message || t('common.error'), t('common.error'), 'destructive');
        } finally {
            setBusyBackup(null);
        }
    };

    const handleDownload = async (name) => {
        setBusyBackup(name);
        try {
            await api.downloadWorldBackup(name);
        } catch (e) {
            dialog.alert(e?.message || t('common.error'), t('common.error'), 'destructive');
        } finally {
            setBusyBackup(null);
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file) return;
        try {
            await api.uploadWorldBackup(file);
            loadBackups();
        } catch (err) {
            dialog.alert(err?.message || t('common.error'), t('common.error'), 'destructive');
        }
    };

    const handleSaveSettings = async () => {
        setSavingSettings(true);
        try {
            setBackupSettings(await api.updateBackupSettings(backupSettings));
        } catch (e) {
            dialog.alert(e?.message || t('common.error'), t('common.error'), 'destructive');
        } finally {
            setSavingSettings(false);
        }
    };

    const handleSwitchWorld = async (worldName) => {
        if (worldName === activeWorld) return;
        const ok = await dialog.confirm(
            t('worlds.switch_confirm').replace('{world}', worldName),
            t('worlds.switch_title'),
            { variant: 'warning', confirmLabel: t('common.confirm') }
        );
        if (!ok) return;
        setSwitching(true);
        try {
            await api.updateServerProperties({ 'level-name': worldName });
            setActiveWorld(worldName);
        } catch (e) {
            dialog.alert(e?.message || t('worlds.switch_error'), t('common.error'), 'destructive');
        }
        setSwitching(false);
    };

    const formatDate = (timestamp) => new Date(timestamp * 1000).toLocaleString();

    if (loading) {
        return <div className="p-8 text-center text-zinc-500 font-minecraft tracking-widest uppercase">{t('worlds.loading')}</div>;
    }

    if (error) {
        return (
            <div className="p-8 text-center">
                <div className="text-red-400 font-minecraft uppercase tracking-wider mb-2">{t('worlds.error')}</div>
                <div className="text-zinc-500 text-sm mb-4">{error}</div>
                <button onClick={loadData} className="bg-transparent border border-white/10 hover:bg-white/5 text-white px-4 py-2 rounded-sm transition-colors font-minecraft uppercase text-xs">{t('common.retry')}</button>
            </div>
        );
    }

    return (
        <div className="animate-in fade-in zoom-in duration-500 max-w-5xl mx-auto w-full">
            <div className="mb-8">
                <h2 className="text-4xl font-minecraft tracking-tight text-emerald-400 mb-1">{t('worlds.title')}</h2>
                <p className="text-zinc-500 text-sm">{t('worlds.subtitle')}</p>
            </div>

            <div className="mb-8 bg-[#18181b]/60 backdrop-blur-xl border border-white/5 rounded-sm p-6">
                <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
                    <div className="flex items-center gap-3">
                        <Archive size={18} className="text-emerald-400" />
                        <div>
                            <div className="text-lg font-minecraft text-white tracking-wider uppercase">{t('worlds.backups')}</div>
                            <div className="text-xs text-zinc-500">{backups.length}</div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button onClick={loadBackups} disabled={backupsLoading}
                            className="px-3 py-2 rounded-sm bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-minecraft uppercase tracking-wider flex items-center gap-2 disabled:opacity-50">
                            <RefreshCw size={14} className={backupsLoading ? 'animate-spin' : ''} /> {t('common.refresh')}
                        </button>
                        <button onClick={() => uploadInputRef.current?.click()}
                            className="px-3 py-2 rounded-sm bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-minecraft uppercase tracking-wider flex items-center gap-2">
                            <Upload size={14} /> {t('common.import')}
                        </button>
                        <input ref={uploadInputRef} type="file" accept=".zip" className="hidden" onChange={handleUpload} />
                        <button onClick={handleCreateBackup} disabled={creatingBackup}
                            className="px-4 py-2 rounded-sm bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/25 text-xs font-minecraft uppercase tracking-wider disabled:opacity-50">
                            {creatingBackup ? t('worlds.creating') : t('worlds.create_backup')}
                        </button>
                    </div>
                </div>

                {backupsLoading ? (
                    <div className="text-sm text-zinc-500">{t('common.loading')}</div>
                ) : backups.length === 0 ? (
                    <div className="text-sm text-zinc-500">{t('worlds.no_backups')}</div>
                ) : (
                    <div className="space-y-2 max-h-72 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                        {backups.map((b) => (
                            <div key={b.name} className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-sm bg-black/20 border border-white/5">
                                <div className="min-w-0">
                                    <div className="text-sm text-white font-mono truncate">{b.name}</div>
                                    <div className="text-xs text-zinc-500">
                                        <span className="text-emerald-400/80">{parseWorldFromBackup(b.name)}</span> • {b.size} • {formatDate(b.created)}
                                    </div>
                                </div>
                                <div className="flex items-center gap-1 shrink-0">
                                    <button onClick={() => handleRestore(b.name)} disabled={busyBackup === b.name}
                                        title={t('worlds.restore')} className="p-2 rounded-sm text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors disabled:opacity-40">
                                        <RefreshCw size={15} />
                                    </button>
                                    <button onClick={() => handleDownload(b.name)} disabled={busyBackup === b.name}
                                        title={t('worlds.download')} className="p-2 rounded-sm text-zinc-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-40">
                                        <Download size={15} />
                                    </button>
                                    <button onClick={() => handleDelete(b.name)} disabled={busyBackup === b.name}
                                        title={t('common.delete')} className="p-2 rounded-sm text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40">
                                        <Trash2 size={15} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                <div className="mt-5 pt-5 border-t border-white/5">
                    <div className="flex flex-wrap items-end gap-4">
                        <label className="flex items-center gap-3 cursor-pointer select-none">
                            <input type="checkbox" className="sr-only peer"
                                checked={backupSettings.enabled}
                                onChange={(e) => setBackupSettings(s => ({ ...s, enabled: e.target.checked }))} />
                            <div className="w-11 h-6 bg-white/10 rounded-sm relative peer-checked:bg-emerald-500 transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-sm after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"></div>
                            <span className="text-xs font-minecraft uppercase tracking-wider text-zinc-300">{t('worlds.auto_backup')}</span>
                        </label>
                        <div className="flex flex-col">
                            <label className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">{t('worlds.every_minutes')}</label>
                            <input type="number" min="5" value={backupSettings.interval_minutes}
                                onChange={(e) => setBackupSettings(s => ({ ...s, interval_minutes: e.target.value }))}
                                className="w-28 bg-black/40 border border-white/10 rounded-sm px-3 py-1.5 text-white text-sm font-mono focus:border-emerald-500 outline-none" />
                        </div>
                        <div className="flex flex-col">
                            <label className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">{t('worlds.keep')}</label>
                            <input type="number" min="1" value={backupSettings.keep}
                                onChange={(e) => setBackupSettings(s => ({ ...s, keep: e.target.value }))}
                                className="w-20 bg-black/40 border border-white/10 rounded-sm px-3 py-1.5 text-white text-sm font-mono focus:border-emerald-500 outline-none" />
                        </div>
                        <button onClick={handleSaveSettings} disabled={savingSettings}
                            className="px-4 py-2 rounded-sm bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-minecraft uppercase tracking-wider flex items-center gap-2 disabled:opacity-50">
                            <Save size={14} /> {savingSettings ? t('common.saving') : t('common.save')}
                        </button>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {worlds.map((world) => (
                    <div key={world.name}
                        className={`bg-[#18181b]/60 backdrop-blur-xl border rounded-sm p-5 transition-colors ${activeWorld === world.name ? 'border-emerald-500/30' : 'border-white/5 hover:border-white/10'}`}>
                        <div className="flex items-start justify-between mb-4">
                            <div className={`p-3 rounded-sm border ${activeWorld === world.name ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-black/30 border-white/5 text-zinc-400'}`}>
                                <Globe size={22} />
                            </div>
                            {activeWorld === world.name && (
                                <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-sm border border-emerald-500/20 font-minecraft uppercase tracking-wider">
                                    <Check size={12} /> {t('worlds.active')}
                                </span>
                            )}
                        </div>
                        <h3 className="text-lg font-minecraft text-white tracking-wider mb-3">{world.name}</h3>
                        <div className="space-y-1.5 mb-4">
                            <div className="flex items-center text-xs text-zinc-500 gap-2"><HardDrive size={13} /> {world.size}</div>
                            <div className="flex items-center text-xs text-zinc-500 gap-2"><Clock size={13} /> {formatDate(world.last_modified)}</div>
                        </div>
                        <button onClick={() => handleSwitchWorld(world.name)} disabled={switching || activeWorld === world.name}
                            className={`w-full py-2 rounded-sm text-xs font-minecraft uppercase tracking-wider transition-colors ${activeWorld === world.name ? 'bg-transparent text-zinc-600 cursor-default' : 'bg-white/5 hover:bg-white/10 text-white'}`}>
                            {activeWorld === world.name ? t('worlds.selected') : t('worlds.load_world')}
                        </button>
                    </div>
                ))}
            </div>

            <div className="mt-6 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-sm flex gap-3 text-yellow-200/80 text-xs">
                <div className="shrink-0">⚠️</div>
                <p>{t('worlds.restart_note')}</p>
            </div>
        </div>
    );
}

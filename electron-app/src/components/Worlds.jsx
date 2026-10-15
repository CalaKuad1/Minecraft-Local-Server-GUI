import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Globe, Check, Archive, RefreshCw, Download, Trash2, Upload, Plus, AlertTriangle } from './ui/PixelIcons';
import { Card, EmptyState, PageHeader, SettingRow } from './ui/Page';
import { Toggle } from './ui/Toggle';
import { inputClass, relativeTime } from '../utils/format';
import Cubi from './ui/Cubi';
import { api } from '../api';
import { useDialog } from './ui/DialogContext';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useTranslation } from '../contexts/LanguageContext';

const parseWorldFromBackup = (name) =>
    name.replace(/-\d{8}-\d{6}(-\d+)?\.zip$/i, '') || name.replace(/\.zip$/i, '');

export default function Worlds() {
    const { t, locale } = useTranslation();
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
    const [settingsSaved, setSettingsSaved] = useState(false);

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
            setSettingsSaved(true);
            setTimeout(() => setSettingsSaved(false), 2000);
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

    const formatDate = (timestamp) => new Date(timestamp * 1000).toLocaleString(locale);

    if (loading) {
        return <div className="p-8 text-center text-ink-faint">{t('worlds.loading')}</div>;
    }

    if (error) {
        return (
            <EmptyState icon={<Cubi mood="sad" size={64} />} title={t('worlds.error')}>
                <p>{error}</p>
                <button onClick={loadData} className="mt-3 rounded-md border border-white/10 px-4 py-2 text-sm text-ink hover:bg-white/5">{t('common.retry')}</button>
            </EmptyState>
        );
    }

    return (
        <div className="flex flex-col gap-5 animate-in fade-in duration-200">
            <PageHeader
                title={t('worlds.title')}
                subtitle={t('worlds.subtitle')}
                actions={(
                    <>
                        <button onClick={() => uploadInputRef.current?.click()} className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">
                            <Upload size={15} /> {t('worlds.import_backup')}
                        </button>
                        <input ref={uploadInputRef} type="file" accept=".zip" className="hidden" onChange={handleUpload} />
                        <button onClick={handleCreateBackup} disabled={creatingBackup} className="inline-flex items-center gap-2 rounded-md bg-grass px-4 py-2 text-sm font-semibold text-ground hover:bg-mint disabled:opacity-60">
                            {creatingBackup ? <RefreshCw size={15} className="animate-spin" /> : <Plus size={15} />}
                            {creatingBackup ? t('worlds.creating') : t('worlds.create_backup')}
                        </button>
                    </>
                )}
            />

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
                <section className="min-w-0 space-y-2">
                    <div className="flex items-center justify-between px-1">
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">{t('worlds.backups')} · {backups.length}</h3>
                        <button onClick={loadBackups} disabled={backupsLoading} className="rounded-md p-1.5 text-ink-faint hover:bg-white/5 hover:text-ink" title={t('common.refresh')} aria-label={t('common.refresh')}>
                            <RefreshCw size={14} className={backupsLoading ? 'animate-spin' : ''} />
                        </button>
                    </div>
                    {backups.length === 0 && !backupsLoading ? (
                        <EmptyState icon={<Archive size={36} className="text-ink-faint" />} title={t('worlds.no_backups_title')}>{t('worlds.no_backups')}</EmptyState>
                    ) : (
                        <Card className="divide-y divide-white/[0.06]">
                            {backups.map((b) => (
                                <div key={b.name} className="group flex items-center gap-3 px-4 py-3">
                                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-white/5 text-mint"><Archive size={17} /></div>
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className="truncate text-sm font-semibold text-ink" title={formatDate(b.created)}>{relativeTime(b.created, locale)}</span>
                                            <span className="rounded-full bg-grass/10 px-2 py-0.5 text-[11px] font-medium text-mint">{parseWorldFromBackup(b.name)}</span>
                                        </div>
                                        <div className="truncate text-xs text-ink-faint">{formatDate(b.created)} · {b.size}</div>
                                    </div>
                                    <div className="flex shrink-0 items-center gap-1">
                                        <button onClick={() => handleRestore(b.name)} disabled={busyBackup === b.name} className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs font-medium text-ink-dim hover:bg-white/5 hover:text-ink disabled:opacity-40">
                                            {t('worlds.restore')}
                                        </button>
                                        <button onClick={() => handleDownload(b.name)} disabled={busyBackup === b.name} title={t('worlds.download')} aria-label={t('worlds.download')} className="rounded-md p-2 text-ink-faint hover:bg-white/5 hover:text-ink disabled:opacity-40">
                                            <Download size={15} />
                                        </button>
                                        <button onClick={() => handleDelete(b.name)} disabled={busyBackup === b.name} title={t('common.delete')} aria-label={t('common.delete')} className="rounded-md p-2 text-ink-faint hover:bg-red-500/10 hover:text-red-400 disabled:opacity-40">
                                            <Trash2 size={15} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </Card>
                    )}
                </section>

                <aside className="space-y-5">
                    <section className="space-y-2">
                        <h3 className="px-1 text-xs font-semibold uppercase tracking-wider text-ink-faint">{t('worlds.auto_backup')}</h3>
                        <Card className="divide-y divide-white/[0.06]">
                            <SettingRow label={t('worlds.auto_backup')} description={t('worlds.auto_backup_desc')}>
                                <Toggle checked={!!backupSettings.enabled} onChange={(v) => setBackupSettings((s) => ({ ...s, enabled: v }))} label={t('worlds.auto_backup')} />
                            </SettingRow>
                            <SettingRow label={t('worlds.every_minutes')}>
                                <input type="number" min="5" value={backupSettings.interval_minutes} onChange={(e) => setBackupSettings((s) => ({ ...s, interval_minutes: e.target.value }))} className={`${inputClass} w-20 text-right tabular-nums`} />
                            </SettingRow>
                            <SettingRow label={t('worlds.keep')} description={t('worlds.keep_desc')}>
                                <input type="number" min="1" value={backupSettings.keep} onChange={(e) => setBackupSettings((s) => ({ ...s, keep: e.target.value }))} className={`${inputClass} w-20 text-right tabular-nums`} />
                            </SettingRow>
                            <div className="flex justify-end px-4 py-3">
                                <button onClick={handleSaveSettings} disabled={savingSettings} className={`inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 text-sm font-semibold transition-colors ${settingsSaved ? 'bg-grass/15 text-mint' : 'bg-white/10 text-ink hover:bg-white/15'}`}>
                                    {settingsSaved && <Check size={14} />}
                                    {savingSettings ? t('common.saving') : settingsSaved ? t('settings.saved') : t('common.save')}
                                </button>
                            </div>
                        </Card>
                    </section>

                    <section className="space-y-2">
                        <h3 className="px-1 text-xs font-semibold uppercase tracking-wider text-ink-faint">{t('worlds.worlds_list')}</h3>
                        <Card className="divide-y divide-white/[0.06]">
                            {worlds.map((world) => {
                                const active = activeWorld === world.name;
                                return (
                                    <div key={world.name} className="flex items-center gap-3 px-4 py-3">
                                        <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-md ${active ? 'bg-grass/15 text-mint' : 'bg-white/5 text-ink-faint'}`}><Globe size={17} /></div>
                                        <div className="min-w-0 flex-1">
                                            <div className="truncate text-sm font-semibold text-ink">{world.name}</div>
                                            <div className="truncate text-xs text-ink-faint">{world.size} · {relativeTime(world.last_modified, locale)}</div>
                                        </div>
                                        {active ? (
                                            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-grass/15 px-2 py-0.5 text-[11px] font-medium text-mint"><Check size={11} /> {t('worlds.active')}</span>
                                        ) : (
                                            <button onClick={() => handleSwitchWorld(world.name)} disabled={switching} className="shrink-0 rounded-md border border-white/10 px-2.5 py-1 text-xs font-medium text-ink-dim hover:bg-white/5 hover:text-ink">
                                                {t('worlds.use_world')}
                                            </button>
                                        )}
                                    </div>
                                );
                            })}
                        </Card>
                        <p className="flex gap-2 px-1 text-xs text-ink-faint"><AlertTriangle size={13} className="mt-0.5 shrink-0 text-gold" />{t('worlds.restart_note')}</p>
                    </section>
                </aside>
            </div>
        </div>
    );
}

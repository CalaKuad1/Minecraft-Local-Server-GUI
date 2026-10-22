import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Search, Download, Trash2, Package, RefreshCw, FolderOpen, Upload, Check, Plug } from './ui/PixelIcons';
import { useDialog } from './ui/DialogContext';
import { Select } from './ui/Select';
import { Toggle } from './ui/Toggle';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useTranslation } from '../contexts/LanguageContext';
import { isSlugInstalled } from '../utils/installedMatch';
import { resolveInstalledSlugs } from '../utils/installedResolve';
import { compactNumber, inputClass, relativeTime } from '../utils/format';
import { Card, EmptyState, PageHeader, Segmented } from './ui/Page';
import Cubi from './ui/Cubi';

// Modrinth browser + installed list, shared by Mods and Plugins (they used to
// be two near-identical 300-line components). `kind` selects the API calls,
// texts and the extra mod filters (loader, version, modpacks).
const KINDS = {
    mod: {
        ns: 'mods',
        installEvent: 'mod_install_complete',
        tabs: ['browse', 'modpacks', 'installed'],
        list: () => api.getInstalledMods(),
        search: (q, f, tab) => api.searchMods(q, f.loader, f.version, tab === 'modpacks' ? 'modpack' : 'mod', f.sort, f.category, f.side),
        versions: (slug, f) => api.getModVersions(slug, f.loader, f.version),
        install: (id, slug) => api.installMod(id, slug),
        remove: (filename) => api.deleteMod(filename),
        upload: (file) => api.importMod(file),
        openFolder: () => api.openModsFolder(),
        categories: ['all', 'technology', 'magic', 'adventure', 'decoration', 'optimization', 'library'],
        // Modrinth environment filter: 'server' hides client-only mods (they
        // can't run on a server), 'server_only' also hides mods players need.
        sides: ['server', 'server_only', 'all'],
        updatable: true,
        Icon: Package,
    },
    plugin: {
        ns: 'plugins',
        installEvent: 'plugin_install_complete',
        tabs: ['browse', 'installed'],
        list: () => api.getPlugins(),
        search: (q, f) => api.searchPlugins(q, f.version, f.sort, f.category),
        versions: (slug, f) => api.getPluginVersions(slug, f.version),
        install: (id, slug) => api.installPlugin(id, slug),
        remove: (filename) => api.deletePlugin(filename),
        upload: (file) => api.uploadPlugin(file),
        openFolder: () => api.openServerFolder(),
        categories: ['all', 'economy', 'game-mechanics', 'utility', 'management', 'social'],
        Icon: Plug,
    },
};

// Modrinth mixes loaders/platforms into categories; show only real topics.
const PLATFORM_TAGS = new Set(['fabric', 'forge', 'neoforge', 'quilt', 'paper', 'spigot', 'bukkit', 'purpur', 'folia', 'sponge', 'bungeecord', 'velocity', 'waterfall', 'datapack', 'minecraft', 'liteloader', 'modloader', 'rift']);

// "voicechat-fabric-1.21.1-2.5.0.jar" -> "voicechat fabric"
// Drops versions and loader names: "appleskin-neoforge-mc1.21-3.0.9" -> "appleskin".
const LOADER_WORD = /^(neo)?forge$|^fabric$|^quilt$|^paper$|^spigot$|^bukkit$|^mc[\d.]+$|^v?\d[\w.+]*$/i;
const prettyName = (filename) => filename
    .replace(/\.jar(\.disabled)?$/i, '')
    .replace(/[[\]()]/g, ' ')
    .split(/[-_\s+]+/)
    .filter((w) => w && !LOADER_WORD.test(w))
    .join(' ')
    .trim() || filename;

function ProjectCard({ project, installed, installing, justInstalled, progress, onInstall, showSide, t, locale }) {
    const cats = (project.display_categories || project.categories || []).filter((c) => !PLATFORM_TAGS.has(c)).slice(0, 3);
    const serverOnly = showSide && project.server_side && project.server_side !== 'unsupported' && ['optional', 'unsupported'].includes(project.client_side);
    const url = project.slug ? `https://modrinth.com/${project.project_type || 'mod'}/${project.slug}` : null;
    return (
        <Card className="flex gap-3.5 p-3.5 transition-colors hover:border-white/15">
            <img
                src={project.icon_url || 'https://cdn.modrinth.com/assets/logo.svg'}
                alt=""
                className="h-14 w-14 shrink-0 rounded-md bg-ground/60 object-contain p-1"
                loading="lazy"
            />
            <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        {url ? (
                            <a href={url} target="_blank" rel="noreferrer" className="block truncate font-display text-[15px] font-semibold text-ink hover:text-mint">{project.title}</a>
                        ) : (
                            <div className="truncate font-display text-[15px] font-semibold text-ink">{project.title}</div>
                        )}
                        <div className="truncate text-xs text-ink-faint">{t('content.by')} {project.author}</div>
                    </div>
                    {installed ? (
                        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-grass/15 px-2.5 py-1 text-xs font-medium text-mint">
                            <Check size={12} /> {t('common.installed')}
                        </span>
                    ) : (
                        <button
                            onClick={onInstall}
                            disabled={installing}
                            className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${justInstalled ? 'bg-grass/15 text-mint' : 'bg-grass text-ground hover:bg-mint disabled:opacity-60'}`}
                        >
                            {justInstalled ? <Check size={13} /> : installing ? <RefreshCw size={13} className="animate-spin" /> : <Download size={13} />}
                            {justInstalled ? t('common.installed') : installing ? t('content.installing') : t('common.install')}
                        </button>
                    )}
                </div>
                <p className="mt-1.5 line-clamp-2 text-sm text-ink-dim">{project.description}</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-faint">
                    <span className="inline-flex items-center gap-1"><Download size={12} /> {compactNumber(project.downloads, locale)}</span>
                    {project.date_modified && <span>{t('content.updated')} {relativeTime(project.date_modified, locale)}</span>}
                    {serverOnly && <span className="rounded-full bg-grass/10 px-2 py-0.5 text-mint" title={t('mods.server_only_hint')}>{t('mods.server_only_badge')}</span>}
                    {cats.map((c) => <span key={c} className="rounded-full bg-white/5 px-2 py-0.5 capitalize">{c.replace(/-/g, ' ')}</span>)}
                </div>
                {installing && (
                    <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/5">
                        <div className="h-full rounded-full bg-grass transition-all duration-300" style={{ width: `${Math.max(4, Math.min(100, progress ?? 0))}%` }} />
                    </div>
                )}
            </div>
        </Card>
    );
}

export default function ContentBrowser({ kind, status, unsupported = null }) {
    const cfg = KINDS[kind];
    const { t, locale } = useTranslation();
    const dialog = useDialog();
    const { subscribe } = useWebSocket();
    const ns = cfg.ns;

    const serverType = (status?.type || status?.server_type || '').toString();
    const serverVersion = status?.version || status?.minecraft_version || '';

    const [tab, setTab] = useState('browse');
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [installed, setInstalled] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [installing, setInstalling] = useState({});
    const [justInstalled, setJustInstalled] = useState({});
    const [progress, setProgress] = useState({});
    const [resolved, setResolved] = useState(new Set());
    const [filters, setFilters] = useState({
        loader: serverType.toLowerCase().includes('neoforge') ? 'neoforge' : serverType.toLowerCase().includes('forge') ? 'forge' : 'fabric',
        version: serverVersion,
        sort: 'downloads',
        category: 'all',
        side: cfg.sides ? cfg.sides[0] : 'all',
    });
    // filename -> { title, icon_url, current_version, update } for Modrinth jars.
    const [updates, setUpdates] = useState({});
    const [checkingUpdates, setCheckingUpdates] = useState(false);
    const [updating, setUpdating] = useState({});
    const [autoUpdate, setAutoUpdate] = useState(false);
    const serverOffline = (status?.status || 'offline') === 'offline';
    const lastSlug = useRef(null);
    const setFilter = (k, v) => setFilters((f) => ({ ...f, [k]: v }));

    useEffect(() => {
        if (serverVersion) setFilters((f) => ({ ...f, version: f.version || serverVersion }));
    }, [serverVersion]);

    const loadInstalled = useCallback(async () => {
        try {
            setInstalled(await cfg.list());
        } catch (e) {
            setError(e?.message || t('common.error'));
        }
    }, [cfg, t]);

    useEffect(() => { loadInstalled(); }, [loadInstalled]);

    const checkUpdates = useCallback(async () => {
        if (!cfg.updatable) return;
        setCheckingUpdates(true);
        try {
            const list = await api.checkModUpdates(filters.loader, filters.version);
            setUpdates(Object.fromEntries((list || []).map((m) => [m.filename, m])));
        } catch (e) {
            setError(`${t('mods.update_check_error')} ${e?.message || ''}`.trim());
        } finally {
            setCheckingUpdates(false);
        }
    }, [cfg, filters.loader, filters.version, t]);

    // Check once per visit to the Installed tab; hashing + 3 Modrinth calls.
    useEffect(() => {
        if (tab === 'installed' && cfg.updatable) checkUpdates();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tab]);

    useEffect(() => {
        if (!cfg.updatable) return;
        api.getModAutoUpdate().then((r) => setAutoUpdate(!!r?.enabled)).catch(() => {});
    }, [cfg]);

    const toggleAutoUpdate = async (enabled) => {
        setAutoUpdate(enabled);
        try {
            await api.setModAutoUpdate(enabled);
        } catch (e) {
            setAutoUpdate(!enabled);
            setError(e.message);
        }
    };

    const runUpdates = async (entries) => {
        if (entries.length === 0) return;
        setError(null);
        setUpdating((u) => ({ ...u, ...Object.fromEntries(entries.map((m) => [m.filename, true])) }));
        try {
            await api.updateMods(entries.map((m) => ({ filename: m.filename, version_id: m.update.version_id })));
        } catch (e) {
            setError(e.message);
            setUpdating((u) => { const n = { ...u }; entries.forEach((m) => delete n[m.filename]); return n; });
        }
    };

    useEffect(() => {
        if (tab === 'installed' || unsupported) return undefined;
        const timer = setTimeout(async () => {
            setLoading(true);
            setError(null);
            try {
                setResults(await cfg.search(query, filters, tab));
            } catch (e) {
                setError(e?.message || t('common.error'));
            } finally {
                setLoading(false);
            }
        }, 400);
        return () => clearTimeout(timer);
    }, [query, tab, filters, cfg, t, unsupported]);

    useEffect(() => {
        if (tab === 'installed' || results.length === 0) { setResolved(new Set()); return undefined; }
        let cancelled = false;
        resolveInstalledSlugs({ slugs: results.map((r) => r.slug), installed })
            .then((m) => { if (!cancelled) setResolved(m); });
        return () => { cancelled = true; };
    }, [tab, results, installed]);

    useEffect(() => subscribe(ns, (item) => {
        if (item.type === 'progress') {
            if (item.slug && typeof item.value === 'number') setProgress((p) => ({ ...p, [item.slug]: item.value }));
            return;
        }
        if (item.type === 'mod_update_complete' && cfg.updatable) {
            setUpdating((u) => { const n = { ...u }; delete n[item.filename]; return n; });
            setProgress((p) => { const n = { ...p }; delete n[item.filename]; return n; });
            if (item.success) {
                setUpdates((prev) => {
                    const n = { ...prev };
                    const old = n[item.filename];
                    delete n[item.filename];
                    if (old && item.new_filename) {
                        n[item.new_filename] = { ...old, filename: item.new_filename, current_version: old.update?.version_number, update: null };
                    }
                    return n;
                });
            } else {
                setError(t('mods.update_error').replace('{name}', item.filename));
            }
            loadInstalled();
            return;
        }
        if (item.type === cfg.installEvent) {
            const slug = item.slug || lastSlug.current;
            lastSlug.current = null;
            if (slug) {
                setProgress((p) => { const n = { ...p }; delete n[slug]; return n; });
                setInstalling((p) => ({ ...p, [slug]: false }));
            }
            loadInstalled();
            if (item.success !== false && slug) {
                setJustInstalled((p) => ({ ...p, [slug]: true }));
                setTimeout(() => setJustInstalled((p) => ({ ...p, [slug]: false })), 2500);
            } else if (item.success === false) {
                setError(t(`${ns}.install_error`));
            }
        }
    }), [subscribe, ns, cfg, loadInstalled, t]);

    const handleInstall = async (project) => {
        const slug = project.slug;
        try {
            setInstalling((p) => ({ ...p, [slug]: true }));
            setError(null);
            const versions = await cfg.versions(slug, filters);
            if (!versions || versions.length === 0) throw new Error(t('mods.no_versions'));
            const target = versions[0];
            const deps = (target.dependencies || []).filter((d) => d.dependency_type === 'required');
            if (kind === 'mod' && deps.length > 0) {
                const ok = await dialog.confirm(
                    t('mods.deps_confirm').replace('{name}', project.title || slug).replace('{count}', deps.length),
                    t('mods.deps_title'),
                    { variant: 'warning', confirmLabel: t('mods.install_anyway'), cancelLabel: t('common.cancel') },
                );
                if (!ok) { setInstalling((p) => ({ ...p, [slug]: false })); return; }
            }
            lastSlug.current = slug; // before the backend can emit progress
            await cfg.install(target.id, slug);
        } catch (e) {
            setError(e.message);
            setInstalling((p) => ({ ...p, [slug]: false }));
        }
    };

    const handleDelete = async (filename) => {
        const ok = await dialog.confirm(t('mods.delete_confirm').replace('{name}', filename), t(`${ns}.delete_title`), { variant: 'destructive', confirmLabel: t('common.delete'), cancelLabel: t('common.cancel') });
        if (!ok) return;
        try {
            await cfg.remove(filename);
            loadInstalled();
        } catch (e) {
            dialog.alert(e.message, t('common.error'), 'destructive');
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file) return;
        try {
            await cfg.upload(file);
            loadInstalled();
        } catch (err) {
            dialog.alert(err.message, t('common.error'), 'destructive');
        }
    };

    const tabOptions = cfg.tabs.map((v) => ({
        value: v,
        label: t(`content.tabs.${v}`),
        count: v === 'installed' ? installed.length : undefined,
    }));
    const isInstalled = (slug) => isSlugInstalled(slug, installed) || resolved.has(slug);
    const shownInstalled = installed.filter((f) => f.filename.toLowerCase().includes(query.toLowerCase())
        || (updates[f.filename]?.title || '').toLowerCase().includes(query.toLowerCase()));
    const pendingUpdates = Object.values(updates).filter((m) => m.update && installed.some((f) => f.filename === m.filename));

    return (
        <div className="flex h-full min-h-0 flex-col gap-4 animate-in fade-in duration-200">
            <PageHeader
                title={t(`${ns}.page_title`)}
                subtitle={t(`${ns}.page_subtitle`)}
                actions={(
                    <>
                        <button onClick={() => cfg.openFolder()} className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">
                            <FolderOpen size={15} /> {t('common.folder')}
                        </button>
                        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm text-ink-dim hover:bg-white/5 hover:text-ink">
                            <Upload size={15} /> {t('content.import_jar')}
                            <input type="file" accept=".jar" className="hidden" onChange={handleUpload} />
                        </label>
                    </>
                )}
            />

            {unsupported}
            {error && <div className="rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-300">{error}</div>}

            <div className="flex flex-wrap items-center gap-2">
                <Segmented value={tab} onChange={setTab} options={tabOptions} layoutId={`${ns}-tabs`} />
                <div className="relative min-w-[12rem] flex-1">
                    <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
                    <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder={tab === 'installed' ? t('content.search_installed') : t(`${ns}.search_placeholder`)}
                        className={`${inputClass} w-full pl-9`}
                    />
                </div>
            </div>

            {tab !== 'installed' && (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                    {kind === 'mod' && (
                        <>
                            <div className="w-36"><Select value={filters.loader} onChange={(v) => setFilter('loader', v)} options={['any', 'fabric', 'forge', 'neoforge', 'quilt'].map((v) => ({ value: v, label: t(`mods.loaders.${v}`) }))} /></div>
                            <input value={filters.version} onChange={(e) => setFilter('version', e.target.value)} placeholder={t('mods.version')} className={`${inputClass} w-24`} />
                        </>
                    )}
                    <div className="w-40"><Select value={filters.sort} onChange={(v) => setFilter('sort', v)} options={['relevance', 'downloads', 'newest', 'updated'].map((v) => ({ value: v, label: t(`${ns}.sort.${v}`) }))} /></div>
                    <div className="w-44"><Select value={filters.category} onChange={(v) => setFilter('category', v)} options={cfg.categories.map((v) => ({ value: v, label: t(`${ns}.categories.${v}`) }))} /></div>
                    {cfg.sides && (
                        <div className="w-52"><Select value={filters.side} onChange={(v) => setFilter('side', v)} options={cfg.sides.map((v) => ({ value: v, label: t(`mods.sides.${v}`) }))} /></div>
                    )}
                    {loading && <RefreshCw size={15} className="animate-spin text-ink-faint" />}
                </div>
            )}

            {tab === 'installed' && cfg.updatable && installed.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                    <button onClick={checkUpdates} disabled={checkingUpdates} className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-ink-dim hover:bg-white/5 hover:text-ink disabled:opacity-60">
                        <RefreshCw size={14} className={checkingUpdates ? 'animate-spin' : ''} /> {t('mods.check_updates')}
                    </button>
                    {pendingUpdates.length > 0 && (
                        <button
                            onClick={() => runUpdates(pendingUpdates.filter((m) => !updating[m.filename]))}
                            disabled={!serverOffline}
                            title={serverOffline ? undefined : t('mods.update_stop_first')}
                            className="inline-flex items-center gap-2 rounded-md bg-grass px-3 py-2 font-semibold text-ground hover:bg-mint disabled:opacity-60"
                        >
                            <Download size={14} /> {t('mods.update_all').replace('{count}', pendingUpdates.length)}
                        </button>
                    )}
                    {!checkingUpdates && pendingUpdates.length === 0 && Object.keys(updates).length > 0 && (
                        <span className="inline-flex items-center gap-1 text-xs text-mint"><Check size={13} /> {t('mods.up_to_date')}</span>
                    )}
                    <label className="ml-auto inline-flex items-center gap-2 text-ink-dim" title={t('mods.auto_update_hint')}>
                        <Toggle checked={autoUpdate} onChange={toggleAutoUpdate} label={t('mods.auto_update')} />
                        {t('mods.auto_update')}
                    </label>
                </div>
            )}

            <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                {tab !== 'installed' ? (
                    results.length === 0 && !loading ? (
                        <EmptyState icon={<Cubi mood="idle" size={64} />} title={t('content.no_results')}>{t(`${ns}.search_hint`)}</EmptyState>
                    ) : (
                        <div className="grid gap-3 xl:grid-cols-2">
                            {results.map((p) => (
                                <ProjectCard
                                    key={p.slug}
                                    project={p}
                                    installed={isInstalled(p.slug)}
                                    installing={!!installing[p.slug]}
                                    justInstalled={!!justInstalled[p.slug]}
                                    progress={progress[p.slug]}
                                    onInstall={() => handleInstall(p)}
                                    showSide={!!cfg.sides}
                                    t={t}
                                    locale={locale}
                                />
                            ))}
                        </div>
                    )
                ) : shownInstalled.length === 0 ? (
                    <EmptyState icon={<Cubi mood="sleep" size={64} />} title={query ? t('content.no_results') : t(`${ns}.installed_empty_title`)}>
                        {!query && t(`${ns}.installed_empty_desc`)}
                    </EmptyState>
                ) : (
                    <Card className="divide-y divide-white/[0.06]">
                        {shownInstalled.map((f) => {
                            const info = updates[f.filename];
                            const isUpdating = !!updating[f.filename];
                            return (
                            <div key={f.filename} className="group flex items-center gap-3 px-4 py-2.5">
                                {info?.icon_url ? (
                                    <img src={info.icon_url} alt="" className="h-9 w-9 shrink-0 rounded-md bg-ground/60 object-contain p-0.5" loading="lazy" />
                                ) : (
                                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-white/5 text-mint">
                                        <cfg.Icon size={17} />
                                    </div>
                                )}
                                <div className="min-w-0 flex-1">
                                    <div className={`truncate text-sm font-semibold text-ink ${info?.title ? '' : 'capitalize'}`}>{info?.title || prettyName(f.filename)}</div>
                                    <div className="truncate font-mono text-[11px] text-ink-faint" title={f.filename}>{f.filename}</div>
                                    {isUpdating && (
                                        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/5">
                                            <div className="h-full rounded-full bg-grass transition-all duration-300" style={{ width: `${Math.max(4, Math.min(100, progress[f.filename] ?? 0))}%` }} />
                                        </div>
                                    )}
                                </div>
                                {info?.update && (
                                    <button
                                        onClick={() => runUpdates([info])}
                                        disabled={isUpdating || !serverOffline}
                                        title={serverOffline ? `${info.current_version || '?'} → ${info.update.version_number}` : t('mods.update_stop_first')}
                                        className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-grass/15 px-2.5 py-1 text-xs font-semibold text-mint hover:bg-grass/25 disabled:opacity-60"
                                    >
                                        {isUpdating ? <RefreshCw size={12} className="animate-spin" /> : <Download size={12} />}
                                        {isUpdating ? t('mods.updating') : `${t('mods.update')} ${info.update.version_number}`}
                                    </button>
                                )}
                                <span className="shrink-0 text-xs tabular-nums text-ink-faint">{f.size}</span>
                                <button onClick={() => handleDelete(f.filename)} className="rounded-md p-2 text-ink-faint opacity-60 transition hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100" title={t('common.delete')} aria-label={t('common.delete')}>
                                    <Trash2 size={15} />
                                </button>
                            </div>
                            );
                        })}
                    </Card>
                )}
            </div>
        </div>
    );
}

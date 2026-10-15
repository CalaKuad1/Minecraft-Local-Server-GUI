import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Search, Download, Trash2, Package, RefreshCw, FolderOpen, Upload, Check, Plug } from './ui/PixelIcons';
import { useDialog } from './ui/DialogContext';
import { Select } from './ui/Select';
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
        search: (q, f, tab) => api.searchMods(q, f.loader, f.version, tab === 'modpacks' ? 'modpack' : 'mod', f.sort, f.category),
        versions: (slug, f) => api.getModVersions(slug, f.loader, f.version),
        install: (id, slug) => api.installMod(id, slug),
        remove: (filename) => api.deleteMod(filename),
        upload: (file) => api.importMod(file),
        openFolder: () => api.openModsFolder(),
        categories: ['all', 'technology', 'magic', 'adventure', 'decoration', 'optimization', 'library'],
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

function ProjectCard({ project, installed, installing, justInstalled, progress, onInstall, t, locale }) {
    const cats = (project.display_categories || project.categories || []).filter((c) => !PLATFORM_TAGS.has(c)).slice(0, 3);
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
    });
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
    const shownInstalled = installed.filter((f) => f.filename.toLowerCase().includes(query.toLowerCase()));

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
                    {loading && <RefreshCw size={15} className="animate-spin text-ink-faint" />}
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
                        {shownInstalled.map((f) => (
                            <div key={f.filename} className="group flex items-center gap-3 px-4 py-2.5">
                                <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-white/5 text-mint">
                                    <cfg.Icon size={17} />
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="truncate text-sm font-semibold capitalize text-ink">{prettyName(f.filename)}</div>
                                    <div className="truncate font-mono text-[11px] text-ink-faint" title={f.filename}>{f.filename}</div>
                                </div>
                                <span className="shrink-0 text-xs tabular-nums text-ink-faint">{f.size}</span>
                                <button onClick={() => handleDelete(f.filename)} className="rounded-md p-2 text-ink-faint opacity-60 transition hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100" title={t('common.delete')} aria-label={t('common.delete')}>
                                    <Trash2 size={15} />
                                </button>
                            </div>
                        ))}
                    </Card>
                )}
            </div>
        </div>
    );
}

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';
import { useTranslation } from '../contexts/LanguageContext';
import { useDialog } from './ui/DialogContext';
import { Search, Plus, Shield, ShieldOff, Ban, CheckCircle, User, Copy, Check, X } from './ui/PixelIcons';
import Cubi from './ui/Cubi';
import PlayerInventoryView from './PlayerInventoryView';

// Everyone the server knows about, in one list: who is online, operators,
// whitelist, bans, and anyone who has ever joined (saved player files).
// Selecting a player opens their card: status, actions and saved inventory.

const FILTERS = ['all', 'online', 'ops', 'whitelist', 'banned'];

const headUrl = (p, size = 32) => `https://minotar.net/helm/${encodeURIComponent(p.name || p.uuid)}/${size}`;

function relTime(ts, locale) {
    if (!ts) return '';
    const mins = Math.round((Date.now() / 1000 - ts) / 60);
    const rtf = new Intl.RelativeTimeFormat(locale || 'en', { numeric: 'auto', style: 'short' });
    if (mins < 60) return rtf.format(-Math.max(0, mins), 'minute');
    if (mins < 60 * 24) return rtf.format(-Math.round(mins / 60), 'hour');
    return rtf.format(-Math.round(mins / 1440), 'day');
}

function Avatar({ player, size = 32, className = '' }) {
    const [failed, setFailed] = useState(false);
    if (failed || !(player.name || player.uuid)) {
        return (
            <div className={`grid shrink-0 place-items-center rounded-md bg-white/5 text-ink-faint ${className}`} style={{ width: size, height: size }}>
                <User size={Math.round(size * 0.55)} />
            </div>
        );
    }
    return (
        <img
            src={headUrl(player, size >= 64 ? 128 : 64)}
            alt=""
            onError={() => setFailed(true)}
            className={`shrink-0 rounded-md ${className}`}
            style={{ width: size, height: size, imageRendering: 'pixelated' }}
        />
    );
}

function Badge({ tone, children }) {
    const tones = {
        online: 'bg-grass/15 text-mint',
        op: 'bg-amber-400/15 text-amber-200',
        whitelist: 'bg-sky-400/15 text-sky-200',
        banned: 'bg-red-500/15 text-red-300',
    };
    return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>{children}</span>;
}

function PlayerRow({ player, selected, onSelect, t, locale }) {
    return (
        <button
            onClick={onSelect}
            className={`flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left transition-colors ${selected ? 'bg-grass/10' : 'hover:bg-white/5'}`}
        >
            <div className="relative">
                <Avatar player={player} size={34} />
                {player.online && <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-panel bg-grass" />}
            </div>
            <div className="min-w-0 flex-1">
                <div className={`truncate text-sm font-semibold ${selected ? 'text-ink' : 'text-ink-dim'}`}>{player.name || player.uuid?.slice(0, 8)}</div>
                <div className="truncate text-xs text-ink-faint">
                    {player.online ? t('status.online') : player.lastSaved ? relTime(player.lastSaved, locale) : t('players.never_joined')}
                </div>
            </div>
            <div className="flex shrink-0 gap-1">
                {player.op && <Shield size={14} className="text-amber-300" aria-label={t('players.badge_op')} />}
                {player.whitelisted && <CheckCircle size={14} className="text-sky-300" aria-label={t('players.badge_whitelist')} />}
                {player.banned && <Ban size={14} className="text-red-400" aria-label={t('players.badge_banned')} />}
            </div>
        </button>
    );
}

function PlayerDetail({ player, onAction, onClose, t }) {
    const [copied, setCopied] = useState(false);
    const copyUuid = async () => {
        try {
            await navigator.clipboard.writeText(player.uuid);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch { /* ignore */ }
    };
    const action = (cls, onClick, Icon, label) => (
        <button onClick={onClick} className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${cls}`}>
            <Icon size={15} /> {label}
        </button>
    );
    const neutral = 'border-white/10 bg-white/5 text-ink-dim hover:bg-white/10 hover:text-ink';

    return (
        <div className="rounded-lg border border-white/[0.06] bg-panel/60 p-5">
            <div className="flex items-start gap-4">
                <Avatar player={player} size={72} className="shadow-lg" />
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate font-display text-2xl font-semibold text-ink">{player.name || t('players.unknown')}</h3>
                        {player.online && <Badge tone="online">● {t('status.online')}</Badge>}
                        {player.op && <Badge tone="op"><Shield size={11} /> {t('players.badge_op')}</Badge>}
                        {player.whitelisted && <Badge tone="whitelist"><CheckCircle size={11} /> {t('players.badge_whitelist')}</Badge>}
                        {player.banned && <Badge tone="banned"><Ban size={11} /> {t('players.badge_banned')}</Badge>}
                    </div>
                    {player.uuid && (
                        <button onClick={copyUuid} className="mt-1 inline-flex items-center gap-1.5 font-mono text-xs text-ink-faint hover:text-ink" title={t('players.copy_uuid')}>
                            {player.uuid} {copied ? <Check size={12} className="text-mint" /> : <Copy size={12} />}
                        </button>
                    )}
                </div>
                <button onClick={onClose} className="rounded-md p-1.5 text-ink-faint hover:bg-white/5 hover:text-ink lg:hidden" aria-label={t('common.close')}>
                    <X size={16} />
                </button>
            </div>

            {player.name && (
                <div className="mt-4 flex flex-wrap gap-2">
                    {player.op
                        ? action(neutral, () => onAction('deop', player), ShieldOff, t('players.deop'))
                        : action(neutral, () => onAction('op', player), Shield, t('players.op'))}
                    {player.whitelisted
                        ? action(neutral, () => onAction('unwhitelist', player), X, t('players.unwhitelist'))
                        : action(neutral, () => onAction('whitelist', player), CheckCircle, t('players.whitelist_add'))}
                    {player.online && action('border-orange-400/30 bg-orange-400/10 text-orange-200 hover:bg-orange-400/20', () => onAction('kick', player), User, t('players.kick'))}
                    {player.banned
                        ? action('border-grass/30 bg-grass/10 text-mint hover:bg-grass/20', () => onAction('pardon', player), CheckCircle, t('players.pardon'))
                        : action('border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20', () => onAction('ban', player), Ban, t('players.ban'))}
                </div>
            )}

            <div className="mt-5 border-t border-white/[0.06] pt-4">
                {player.hasData ? (
                    <PlayerInventoryView uuid={player.uuid} refreshKey={player.online ? 1 : 0} />
                ) : (
                    <p className="text-sm text-ink-faint">{t('players.no_saved_data')}</p>
                )}
            </div>
        </div>
    );
}

export default function Players({ focusPlayer, onFocusHandled }) {
    const { t, locale } = useTranslation();
    const dialog = useDialog();
    const [lists, setLists] = useState({ online: [], ops: [], whitelist: [], banned: [] });
    const [saved, setSaved] = useState([]);
    const [loaded, setLoaded] = useState(false);
    const [error, setError] = useState(null);
    const [filter, setFilter] = useState('all');
    const [query, setQuery] = useState('');
    const [selectedKey, setSelectedKey] = useState(null);
    const [extra, setExtra] = useState(null); // a player opened from elsewhere who is in no list yet
    const [showAdd, setShowAdd] = useState(false);
    const [addName, setAddName] = useState('');
    const [addTo, setAddTo] = useState('whitelist');
    const inFlight = useRef(false);

    const fetchData = useCallback(async () => {
        if (inFlight.current) return;
        inFlight.current = true;
        try {
            const [l, inv] = await Promise.all([
                api.getPlayers(),
                api.getInventoryPlayers().catch(() => ({ players: [] })),
            ]);
            setLists({ online: l.online || [], ops: l.ops || [], whitelist: l.whitelist || [], banned: l.banned || [] });
            setSaved(inv.players || []);
            setError(null);
        } catch (e) {
            setError(e?.message || t('players.error'));
        } finally {
            setLoaded(true);
            inFlight.current = false;
        }
    }, [t]);

    useEffect(() => {
        fetchData();
        const id = setInterval(fetchData, 5000);
        return () => clearInterval(id);
    }, [fetchData]);

    // Merge every source into one record per player (by name, else uuid).
    const players = useMemo(() => {
        const map = new Map();
        const keyOf = (p) => (p.name ? `n:${p.name.toLowerCase()}` : `u:${(p.uuid || '').toLowerCase()}`);
        const upsert = (p, patch) => {
            if (!p || !(p.name || p.uuid)) return;
            const byUuid = p.uuid && [...map.values()].find((x) => x.uuid && x.uuid.toLowerCase() === p.uuid.toLowerCase());
            const key = byUuid ? byUuid.key : keyOf(p);
            const cur = map.get(key) || { key, name: p.name, uuid: p.uuid };
            map.set(key, { ...cur, name: cur.name || p.name, uuid: cur.uuid || p.uuid, ...patch });
        };
        saved.forEach((p) => upsert(p, { hasData: true, lastSaved: p.last_saved }));
        lists.online.forEach((p) => upsert(p, { online: true }));
        lists.ops.forEach((p) => upsert(p, { op: true }));
        lists.whitelist.forEach((p) => upsert(p, { whitelisted: true }));
        lists.banned.forEach((p) => upsert(p, { banned: true }));
        if (extra && !map.has(keyOf(extra))) upsert(extra, {});
        return [...map.values()].sort((a, b) =>
            (b.online ? 1 : 0) - (a.online ? 1 : 0) || (b.lastSaved || 0) - (a.lastSaved || 0)
            || (a.name || '').localeCompare(b.name || ''));
    }, [saved, lists, extra]);

    // Opened from another screen (dashboard, console): select that player.
    useEffect(() => {
        if (!focusPlayer) return;
        const name = focusPlayer.toLowerCase();
        const found = players.find((p) => (p.name || '').toLowerCase() === name);
        if (found) {
            setSelectedKey(found.key);
        } else {
            setExtra({ name: focusPlayer });
            setSelectedKey(`n:${name}`);
        }
        setFilter('all');
        setQuery('');
        if (onFocusHandled) onFocusHandled();
    }, [focusPlayer, players, onFocusHandled]);

    const counts = {
        all: players.length,
        online: players.filter((p) => p.online).length,
        ops: players.filter((p) => p.op).length,
        whitelist: players.filter((p) => p.whitelisted).length,
        banned: players.filter((p) => p.banned).length,
    };
    const visible = players.filter((p) => {
        if (filter === 'online' && !p.online) return false;
        if (filter === 'ops' && !p.op) return false;
        if (filter === 'whitelist' && !p.whitelisted) return false;
        if (filter === 'banned' && !p.banned) return false;
        const q = query.trim().toLowerCase();
        return !q || (p.name || '').toLowerCase().includes(q) || (p.uuid || '').toLowerCase().includes(q);
    });
    const selected = players.find((p) => p.key === selectedKey) || null;

    const runAction = async (action, player) => {
        const name = player.name;
        if (!name) return;
        if (action === 'ban' || action === 'kick') {
            const ok = await dialog.confirm(
                t(`players.${action}_confirm`).replace('{name}', name),
                { title: t(`players.${action}`), variant: 'destructive', confirmLabel: t(`players.${action}`), cancelLabel: t('common.cancel') },
            );
            if (!ok) return;
        }
        try {
            switch (action) {
                case 'op': await api.opPlayer(name); break;
                case 'deop': await api.deopPlayer(name); break;
                case 'ban': await api.banPlayer(name); break;
                case 'pardon': await api.unbanPlayer(name); break;
                case 'kick': await api.kickPlayer(name); break;
                case 'whitelist': await api.whitelistAdd(name); break;
                case 'unwhitelist': await api.whitelistRemove(name); break;
                default: return;
            }
            setTimeout(fetchData, 500);
        } catch (e) {
            setError(e?.message || t('players.action_failed'));
        }
    };

    const submitAdd = async () => {
        const name = addName.trim();
        if (!name) return;
        const action = { whitelist: 'whitelist', ops: 'op', banned: 'ban' }[addTo];
        setShowAdd(false);
        setAddName('');
        setExtra({ name });
        setSelectedKey(`n:${name.toLowerCase()}`);
        await runAction(action, { name });
    };

    return (
        <div className="flex h-full min-h-0 flex-col gap-4 animate-in fade-in duration-200">
            <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <h2 className="font-display text-3xl font-semibold text-ink">{t('players.title')}</h2>
                    <p className="text-sm text-ink-faint">{t('players.subtitle_new')}</p>
                </div>
                <button
                    onClick={() => setShowAdd(true)}
                    className="inline-flex items-center gap-2 rounded-md bg-grass px-4 py-2 text-sm font-semibold text-ground transition-colors hover:bg-mint"
                >
                    <Plus size={16} /> {t('players.add_player')}
                </button>
            </div>

            {error && <div className="rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-300">{error}</div>}

            <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[19rem_minmax(0,1fr)]">
                <div className={`flex min-h-0 flex-col rounded-lg border border-white/[0.06] bg-panel/60 ${selected ? 'hidden lg:flex' : ''}`}>
                    <div className="space-y-2 border-b border-white/[0.06] p-3">
                        <div className="relative">
                            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
                            <input
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder={t('players.search')}
                                className="w-full rounded-md border border-white/10 bg-ground/60 py-2 pl-9 pr-3 text-sm text-ink placeholder-ink-faint outline-none focus:border-grass/50"
                            />
                        </div>
                        <div className="flex flex-wrap gap-1">
                            {FILTERS.map((f) => (
                                <button
                                    key={f}
                                    onClick={() => setFilter(f)}
                                    className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${filter === f ? 'bg-grass/15 text-mint' : 'text-ink-faint hover:bg-white/5 hover:text-ink'}`}
                                >
                                    {t(`players.filters.${f}`)} <span className="opacity-60">{counts[f]}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
                        {!loaded && <div className="p-3 text-sm text-ink-faint">{t('common.loading')}</div>}
                        {loaded && visible.length === 0 && (
                            <div className="px-3 py-8 text-center text-sm text-ink-faint">
                                {players.length === 0 ? t('players.empty_all') : t('players.no_matches')}
                            </div>
                        )}
                        {visible.map((p) => (
                            <PlayerRow key={p.key} player={p} selected={p.key === selectedKey} onSelect={() => setSelectedKey(p.key)} t={t} locale={locale} />
                        ))}
                    </div>
                </div>

                <div className="min-h-0 overflow-y-auto">
                    {selected ? (
                        <PlayerDetail player={selected} onAction={runAction} onClose={() => setSelectedKey(null)} t={t} />
                    ) : (
                        <div className="flex h-full min-h-[16rem] flex-col items-center justify-center rounded-lg border border-dashed border-white/10 bg-panel/30 p-8 text-center">
                            <Cubi mood={counts.online ? 'happy' : 'idle'} size={84} className="mb-3" interactive />
                            <p className="font-display text-lg font-semibold text-ink">{t('players.select_title')}</p>
                            <p className="mt-1 max-w-sm text-sm text-ink-faint">{t('players.select_desc')}</p>
                        </div>
                    )}
                </div>
            </div>

            {showAdd && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowAdd(false)}>
                    <div className="w-96 max-w-[calc(100vw-2rem)] rounded-lg border border-white/10 bg-panel p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                        <h3 className="mb-4 font-display text-xl font-semibold text-ink">{t('players.add_player')}</h3>
                        <input
                            autoFocus
                            value={addName}
                            onChange={(e) => setAddName(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && submitAdd()}
                            placeholder={t('players.player_name')}
                            className="mb-3 w-full rounded-md border border-white/10 bg-ground/60 px-3 py-2.5 text-ink outline-none focus:border-grass/50"
                        />
                        <div className="mb-5 grid grid-cols-3 gap-1 rounded-md bg-ground/60 p-1">
                            {['whitelist', 'ops', 'banned'].map((k) => (
                                <button key={k} onClick={() => setAddTo(k)} className={`rounded px-2 py-1.5 text-xs font-medium transition-colors ${addTo === k ? 'bg-white/10 text-ink' : 'text-ink-faint hover:text-ink'}`}>
                                    {t(`players.filters.${k}`)}
                                </button>
                            ))}
                        </div>
                        <div className="flex justify-end gap-2">
                            <button onClick={() => setShowAdd(false)} className="rounded-md px-4 py-2 text-sm text-ink-dim hover:bg-white/5">{t('common.cancel')}</button>
                            <button onClick={submitAdd} disabled={!addName.trim()} className="rounded-md bg-grass px-4 py-2 text-sm font-semibold text-ground hover:bg-mint disabled:opacity-40">{t('common.add')}</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

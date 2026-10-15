import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { useTranslation } from '../contexts/LanguageContext';
import { RefreshCw, Download, Loader2 } from './ui/PixelIcons';
import Cubi from './ui/Cubi';

// Player inventory inspector: pick a player, see their inventory, armor,
// offhand and ender chest the way the game lays them out. Item graphics are
// built on this PC from official game files (backend: utils/mc_assets.py).

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
const roman = (n) => ROMAN[n] || String(n);

function relTime(ts, locale) {
    if (!ts) return '';
    const mins = Math.round((Date.now() / 1000 - ts) / 60);
    const rtf = new Intl.RelativeTimeFormat(locale || 'en', { numeric: 'auto', style: 'short' });
    if (mins < 60) return rtf.format(-Math.max(0, mins), 'minute');
    if (mins < 60 * 24) return rtf.format(-Math.round(mins / 60), 'hour');
    return rtf.format(-Math.round(mins / 1440), 'day');
}

function ItemSlot({ item, iconVersion, selected, empty }) {
    const [broken, setBroken] = useState(false);
    const [hover, setHover] = useState(false);
    useEffect(() => setBroken(false), [item?.id, iconVersion]);
    const enchanted = item && (item.enchantments?.length || item.stored_enchantments?.length);
    const dur = item?.durability;
    const durPct = dur ? dur.remaining / dur.max : 1;
    return (
        <div
            className={`relative aspect-square rounded-md border bg-ground/80 ${selected ? 'border-mint/70 ring-1 ring-mint/40' : 'border-white/[0.07]'} ${item ? 'hover:border-white/25' : ''}`}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
        >
            {empty && !item && <div className="absolute inset-0 grid place-items-center text-[10px] text-ink-faint/50 select-none">{empty}</div>}
            {item && (
                <>
                    {iconVersion && !broken ? (
                        <img
                            src={api.itemIconUrl(item.id, iconVersion)}
                            alt=""
                            draggable={false}
                            onError={() => setBroken(true)}
                            className={`absolute inset-[12%] h-[76%] w-[76%] object-contain ${enchanted ? 'inv-glint' : ''}`}
                            style={{ imageRendering: 'pixelated' }}
                        />
                    ) : (
                        <div className="absolute inset-1 grid place-items-center text-center text-[9px] leading-tight text-ink-dim break-words overflow-hidden">
                            {item.name || item.id}
                        </div>
                    )}
                    {item.count > 1 && (
                        <span className="absolute bottom-0.5 right-1 text-xs font-semibold text-white tabular-nums" style={{ textShadow: '1px 1px 0 #000' }}>{item.count}</span>
                    )}
                    {dur && durPct < 1 && (
                        <div className="absolute bottom-1 left-1.5 right-1.5 h-[3px] rounded-full bg-black/70">
                            <div className="h-full rounded-full" style={{ width: `${Math.max(4, durPct * 100)}%`, background: `hsl(${Math.round(durPct * 120)} 80% 50%)` }} />
                        </div>
                    )}
                    {hover && <ItemTooltip item={item} />}
                </>
            )}
        </div>
    );
}

function ItemTooltip({ item }) {
    const { t } = useTranslation();
    const ench = [...(item.enchantments || []), ...(item.stored_enchantments || [])];
    return (
        <div className="pointer-events-none absolute left-1/2 top-full z-50 mt-1.5 w-max max-w-[16rem] -translate-x-1/2 rounded-md border border-[#2a0a5e] bg-[#100318]/95 px-2.5 py-1.5 text-xs shadow-xl">
            <div className={`font-semibold ${item.custom_name ? 'italic text-sky-300' : ench.length ? 'text-sky-300' : 'text-white'}`}>
                {item.custom_name || item.name || item.id}
            </div>
            {item.custom_name && <div className="text-ink-faint">{item.name}</div>}
            {ench.map((e) => (
                <div key={e.id} className="text-[#a8a8a8]">{e.name} {roman(e.level)}</div>
            ))}
            {item.durability && (
                <div className="text-ink-dim">{t('inventory.durability')}: {item.durability.remaining} / {item.durability.max}</div>
            )}
            <div className="mt-0.5 font-mono text-[10px] text-ink-faint/80">{item.id}</div>
        </div>
    );
}

function Grid({ cols = 9, slots, items, iconVersion, selectedSlot }) {
    const bySlot = useMemo(() => Object.fromEntries((items || []).map((i) => [i.slot, i])), [items]);
    return (
        <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
            {slots.map((s) => (
                <ItemSlot key={s} item={bySlot[s]} iconVersion={iconVersion} selected={s === selectedSlot} />
            ))}
        </div>
    );
}

const range = (a, b) => Array.from({ length: b - a }, (_, i) => a + i);

function AssetsBanner({ onReady }) {
    const { t, locale } = useTranslation();
    const [accepted, setAccepted] = useState(false);
    const [dl, setDl] = useState(null);
    // null = still checking; true = the server's EULA is already accepted, so
    // the graphics download by themselves (no second consent prompt).
    const [eulaDone, setEulaDone] = useState(null);

    useEffect(() => {
        let cancelled = false;
        api.getItemAssetsStatus().then(async (s) => {
            if (cancelled) return;
            setEulaDone(!!s.eula_accepted);
            if (s.download?.running) {
                setDl(s.download);
            } else if (s.eula_accepted) {
                try {
                    const r = await api.downloadItemAssets(locale);
                    if (!cancelled) setDl({ ...r.download, running: true });
                } catch (e) {
                    if (!cancelled) setDl({ running: false, error: e.message });
                }
            }
        }).catch(() => !cancelled && setEulaDone(false));
        return () => { cancelled = true; };
    }, [locale]);

    useEffect(() => {
        if (!dl?.running) return undefined;
        const id = setInterval(async () => {
            try {
                const s = await api.getItemAssetsStatus();
                setDl(s.download);
                if (!s.download.running) {
                    clearInterval(id);
                    if (!s.download.error) onReady();
                }
            } catch { /* keep polling */ }
        }, 700);
        return () => clearInterval(id);
    }, [dl?.running, onReady]);

    const start = async () => {
        try {
            const r = await api.downloadItemAssets(locale);
            setDl({ ...r.download, running: true });
        } catch (e) {
            setDl({ running: false, error: e.message });
        }
    };

    return (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-grass/25 bg-grass/[0.06] p-4">
            <Cubi mood={dl?.running ? 'busy' : 'idle'} size={48} className="shrink-0" />
            <div className="min-w-[16rem] flex-1">
                <div className="font-display text-base font-semibold text-ink">{t('inventory.assets_title')}</div>
                <p className="mt-0.5 text-sm text-ink-dim">{eulaDone ? t('inventory.assets_auto') : t('inventory.assets_desc')}</p>
                {!dl?.running && eulaDone === false && (
                    <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm text-ink-dim">
                        <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} className="accent-emerald-500" />
                        {t('inventory.assets_eula')}
                    </label>
                )}
                {dl?.running && (
                    <div className="mt-2 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-black/40">
                        <div className="h-full bg-grass transition-all" style={{ width: `${dl.progress || 2}%` }} />
                    </div>
                )}
                {dl?.error && <p className="mt-2 text-xs text-red-300">{dl.error}</p>}
            </div>
            {!dl?.running && (eulaDone === false || dl?.error) && (
                <button
                    onClick={start}
                    disabled={!accepted && !eulaDone}
                    className="inline-flex items-center gap-2 rounded-md bg-grass px-4 py-2 text-sm font-semibold text-ground transition-colors hover:bg-mint disabled:opacity-40"
                >
                    <Download size={15} /> {t('inventory.assets_button')}
                </button>
            )}
        </div>
    );
}

// Saved state of one player (stats, inventory, armor, ender chest). Used by
// the player detail panel in Players.
export default function PlayerInventoryView({ uuid, refreshKey = 0 }) {
    const { t, locale } = useTranslation();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [view, setView] = useState('inventory');

    const load = useCallback(async () => {
        if (!uuid) return;
        setLoading(true);
        setError('');
        try {
            setData(await api.getPlayerInventory(uuid, locale));
        } catch (e) {
            setError(e.message);
            setData(null);
        } finally {
            setLoading(false);
        }
    }, [uuid, locale]);

    useEffect(() => { setData(null); load(); }, [load, refreshKey]);

    if (!data) {
        return (
            <div className="rounded-lg border border-white/[0.06] bg-ground/40 p-4 text-sm text-ink-faint">
                {error ? <span className="text-red-300">{error}</span> : t('common.loading')}
            </div>
        );
    }

    const st = data.stats;
    const iconVersion = data.icons_version;
    const armorOrder = ['head', 'chest', 'legs', 'feet'];
    const dimension = (() => { const k = `inventory.dimension.${st.dimension}`; const v = t(k); return v === k ? st.dimension : v; })();

    return (
        <div className="space-y-4">
            {!iconVersion && <AssetsBanner onReady={load} />}

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                    { label: t('inventory.health'), value: `${st.health} / 20`, tone: 'text-red-300' },
                    { label: t('inventory.food'), value: `${st.food} / 20`, tone: 'text-amber-200' },
                    { label: t('inventory.level'), value: st.xp_level, tone: 'text-lime-300' },
                    { label: t('inventory.mode'), value: t(`inventory.gamemode.${st.gamemode}`), tone: 'text-ink' },
                ].map((c) => (
                    <div key={c.label} className="rounded-md border border-white/[0.06] bg-ground/40 px-3 py-2">
                        <div className="text-[11px] text-ink-faint">{c.label}</div>
                        <div className={`font-display text-lg font-semibold tabular-nums ${c.tone}`}>{c.value}</div>
                    </div>
                ))}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-faint">
                <span>{dimension}{st.position ? ` · X ${Math.round(st.position[0])}, Y ${Math.round(st.position[1])}, Z ${Math.round(st.position[2])}` : ''}</span>
                <span className="ml-auto">{t('inventory.saved')} {relTime(data.last_saved, locale)}</span>
                <button onClick={load} disabled={loading} className="rounded-md p-1 hover:bg-white/5 hover:text-ink" title={t('common.refresh')} aria-label={t('common.refresh')}>
                    {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                </button>
            </div>

            <div className="flex w-fit gap-1 rounded-md bg-ground/60 p-1">
                {['inventory', 'ender'].map((v) => (
                    <button key={v} onClick={() => setView(v)} className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${view === v ? 'bg-white/10 text-ink' : 'text-ink-faint hover:text-ink'}`}>
                        {t(`inventory.view_${v}`)}
                    </button>
                ))}
            </div>

            {view === 'inventory' ? (
                <div className="flex flex-wrap gap-4">
                    <div className="grid w-11 shrink-0 gap-1.5 self-start">
                        {armorOrder.map((k) => (
                            <ItemSlot key={k} item={data.armor?.[k]} iconVersion={iconVersion} empty={t(`inventory.armor.${k}`)} />
                        ))}
                        <div className="h-1" />
                        <ItemSlot item={data.offhand} iconVersion={iconVersion} empty={t('inventory.offhand')} />
                    </div>
                    <div className="min-w-[16rem] max-w-[30rem] flex-1 space-y-3">
                        <Grid slots={range(9, 36)} items={data.inventory} iconVersion={iconVersion} />
                        <Grid slots={range(0, 9)} items={data.inventory} iconVersion={iconVersion} selectedSlot={st.selected_slot} />
                    </div>
                </div>
            ) : (
                <div className="max-w-[30rem]">
                    <Grid slots={range(0, 27)} items={data.ender_chest} iconVersion={iconVersion} />
                </div>
            )}
        </div>
    );
}

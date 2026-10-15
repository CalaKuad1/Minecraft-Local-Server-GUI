// Small UI helpers shared by the server pages.

export const inputClass =
    'h-9 rounded-md border border-white/10 bg-ground/70 px-3 text-sm text-ink placeholder-ink-faint outline-none transition-colors focus:border-grass/60';

// "1.2 M", "34 k": Modrinth download counts at a glance.
export function compactNumber(n, locale) {
    try {
        return new Intl.NumberFormat(locale || 'en', { notation: 'compact', maximumFractionDigits: 1 }).format(n || 0);
    } catch {
        return String(n || 0);
    }
}

export function relativeTime(ts, locale) {
    if (!ts) return '';
    const secs = typeof ts === 'number' ? ts : Date.parse(ts) / 1000;
    const mins = Math.round((Date.now() / 1000 - secs) / 60);
    const rtf = new Intl.RelativeTimeFormat(locale || 'en', { numeric: 'auto', style: 'short' });
    if (Math.abs(mins) < 60) return rtf.format(-Math.max(0, mins), 'minute');
    if (Math.abs(mins) < 60 * 24) return rtf.format(-Math.round(mins / 60), 'hour');
    if (Math.abs(mins) < 60 * 24 * 60) return rtf.format(-Math.round(mins / 1440), 'day');
    return rtf.format(-Math.round(mins / 43200), 'month');
}

import React from 'react';
import { motion } from 'framer-motion';

// Shared building blocks for the server pages (Settings, Worlds, Mods,
// Plugins, Players), so every section has the same header, tabs and cards.

export function PageHeader({ title, subtitle, actions = null, children = null }) {
    return (
        <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
                <h2 className="font-display text-3xl font-semibold text-ink">{title}</h2>
                {subtitle && <p className="mt-0.5 text-sm text-ink-faint">{subtitle}</p>}
                {children}
            </div>
            {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
    );
}

export function Card({ className = '', children, ...rest }) {
    return (
        <div className={`rounded-lg border border-white/[0.06] bg-panel/60 ${className}`} {...rest}>
            {children}
        </div>
    );
}

// Pill tabs with a sliding highlight. options: [{ value, label, count?, icon? }]
export function Segmented({ value, onChange, options, layoutId }) {
    return (
        <div className="inline-flex w-fit gap-1 rounded-md bg-ground/70 p-1" role="tablist">
            {options.map((o) => {
                const active = o.value === value;
                const Icon = o.icon;
                return (
                    <button
                        key={o.value}
                        role="tab"
                        aria-selected={active}
                        onClick={() => onChange(o.value)}
                        className={`relative inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded px-3.5 py-1.5 text-sm font-medium transition-colors ${active ? 'text-ink' : 'text-ink-faint hover:text-ink'}`}
                    >
                        {active && (
                            <motion.span layoutId={layoutId} className="absolute inset-0 rounded bg-white/10" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />
                        )}
                        {Icon && <Icon size={15} className="relative" />}
                        <span className="relative">{o.label}</span>
                        {o.count !== undefined && <span className="relative text-xs opacity-60">{o.count}</span>}
                    </button>
                );
            })}
        </div>
    );
}

// Label + description on the left, control on the right (one row of a settings list).
export function SettingRow({ label, description, children, tone = '' }) {
    return (
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3.5">
            <div className="min-w-[12rem] flex-1">
                <div className={`text-sm font-semibold text-ink ${tone}`}>{label}</div>
                {description && <div className="mt-0.5 text-xs text-ink-faint">{description}</div>}
            </div>
            <div className="flex shrink-0 items-center gap-2">{children}</div>
        </div>
    );
}

// A titled group of SettingRows separated by hairlines.
export function SettingGroup({ title, children, className = '' }) {
    return (
        <section className={className}>
            {title && <h3 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-ink-faint">{title}</h3>}
            <Card className="divide-y divide-white/[0.06]">{children}</Card>
        </section>
    );
}

export function EmptyState({ icon = null, title, children }) {
    return (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-white/10 bg-panel/30 px-6 py-12 text-center">
            {icon}
            {title && <p className="mt-2 font-display text-lg font-semibold text-ink">{title}</p>}
            {children && <div className="mt-1 max-w-md text-sm text-ink-faint">{children}</div>}
        </div>
    );
}

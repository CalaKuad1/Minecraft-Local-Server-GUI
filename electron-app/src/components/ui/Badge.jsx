import React from 'react';
import { cn } from '../../utils/cn';

// One tone per meaning, never decoration: grass = running/ok, gold = in progress or
// caution, redstone = error, diamond = information, neutral = everything else.
const TONES = {
    neutral: 'bg-white/5 text-ink-dim border-white/10',
    grass: 'bg-grass/10 text-grass-lit border-grass/30',
    gold: 'bg-gold/10 text-gold border-gold/30',
    redstone: 'bg-redstone/10 text-redstone border-redstone/30',
    diamond: 'bg-diamond/10 text-diamond border-diamond/30',
};

export function Badge({ tone = 'neutral', dot = false, className, children, ...rest }) {
    return (
        <span
            className={cn('inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-xs font-semibold leading-4', TONES[tone], className)}
            {...rest}
        >
            {dot && <span className="h-1.5 w-1.5 rounded-sm bg-current" aria-hidden="true" />}
            {children}
        </span>
    );
}

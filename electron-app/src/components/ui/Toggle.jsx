import React from 'react';
import { cn } from '../../utils/cn';

// Square on/off switch. The thumb snaps between two positions (no spring): in a
// pixel UI the state change should read as a click, not a slide.
export function Toggle({ checked, onChange, label, disabled = false, className }) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={!!checked}
            aria-label={label}
            disabled={disabled}
            onClick={() => onChange?.(!checked)}
            className={cn(
                'relative inline-flex h-6 w-11 shrink-0 items-center rounded-sm p-0.5 transition-colors duration-100 disabled:opacity-45',
                checked ? 'bg-grass shadow-bevel' : 'bg-raised shadow-bevel-panel',
                className
            )}
        >
            <span
                className={cn(
                    'block h-4 w-4 rounded-sm transition-transform duration-100',
                    checked ? 'translate-x-5 bg-black/80' : 'translate-x-0.5 bg-ink-faint'
                )}
                aria-hidden="true"
            />
        </button>
    );
}

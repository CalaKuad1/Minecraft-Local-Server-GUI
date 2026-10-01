import React from 'react';
import { cn } from '../../utils/cn';

// Buttons carry the bevel (see tailwind.config.js): light edge on top, shade below,
// and they sink 1px when pressed. Labels are sentence case and 14px or larger.
const VARIANTS = {
    primary: 'bg-grass text-black shadow-bevel hover:brightness-110 active:shadow-bevel-press',
    secondary: 'bg-raised text-ink shadow-bevel-panel hover:bg-[#2a2a31] active:shadow-bevel-press',
    danger: 'bg-redstone/15 text-redstone border border-redstone/50 hover:bg-redstone/25',
    ghost: 'bg-transparent text-ink-dim hover:text-ink hover:bg-white/5',
};

const SIZES = {
    sm: 'h-8 px-3 text-sm gap-1.5',
    md: 'h-10 px-5 text-[15px] gap-2',
    lg: 'h-12 px-7 text-base gap-2.5',
};

export const Button = React.forwardRef(function Button(
    { variant = 'secondary', size = 'md', loading = false, icon: Icon, className, children, disabled, type = 'button', ...rest },
    ref
) {
    const isDisabled = disabled || loading;
    return (
        <button
            ref={ref}
            type={type}
            disabled={isDisabled}
            aria-busy={loading || undefined}
            className={cn(
                'inline-flex items-center justify-center rounded-sm font-minecraft font-semibold tracking-wide select-none',
                'transition-[filter,background-color,transform] duration-100 active:translate-y-px',
                'disabled:opacity-45 disabled:pointer-events-none',
                VARIANTS[variant],
                SIZES[size],
                className
            )}
            {...rest}
        >
            {loading
                ? <span className="h-3.5 w-3.5 border-2 border-current border-t-transparent animate-spin" aria-hidden="true" />
                : Icon && <Icon size={size === 'sm' ? 14 : 16} aria-hidden="true" />}
            {children}
        </button>
    );
});

// Icon-only button. `label` is required: it becomes the accessible name and the
// native tooltip, so screen readers and hover users get the same text.
export const IconButton = React.forwardRef(function IconButton(
    { label, icon: Icon, size = 16, tone = 'default', className, type = 'button', ...rest },
    ref
) {
    const tones = {
        default: 'text-ink-faint hover:text-ink hover:bg-white/5',
        active: 'text-ink bg-white/10',
        danger: 'text-ink-faint hover:text-redstone hover:bg-redstone/10',
    };
    return (
        <button
            ref={ref}
            type={type}
            aria-label={label}
            title={label}
            className={cn('inline-flex h-8 w-8 items-center justify-center rounded-sm transition-colors disabled:opacity-45', tones[tone], className)}
            {...rest}
        >
            <Icon size={size} aria-hidden="true" />
        </button>
    );
});

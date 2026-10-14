/** @type {import('tailwindcss').Config} */

// Colors are CSS variables (see index.css) holding "R G B" channels, so Tailwind
// opacity modifiers keep working: `bg-grass/20`, `text-ink-dim`, ...
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Surfaces
                ground: token('ground'),
                panel: token('panel'),
                raised: token('raised'),
                line: token('line'),             // hairline borders
                // Cubi's three faces: top (mint), left (grass), right (deep).
                mint: token('grass-lit'),
                deep: token('deep'),
                // Text. ink-dim and ink-faint both clear WCAG AA (4.5:1) on ground/panel;
                // the old zinc-500/600 used for hints did not.
                ink: token('ink'),
                "ink-dim": token('ink-dim'),
                "ink-faint": token('ink-faint'),
                // World colors: one per meaning, named after what they are in the game.
                grass: token('grass'),          // primary action, online
                "grass-lit": token('grass-lit'), // grass as text on dark
                gold: token('gold'),            // starting, caution
                redstone: token('redstone'),    // stop, error, destructive
                diamond: token('diamond'),      // info, focus ring

                // Legacy names, kept so existing screens keep rendering.
                background: token('ground'),
                surface: token('panel'),
                "surface-hover": token('raised'),
                primary: token('grass'),
                "primary-hover": "#059669",
                secondary: "#64748b",
                accent: token('diamond'),
                success: "#22c55e",
                warning: "#eab308",
                error: "#ef4444",
            },
            fontFamily: {
                sans: ['"Figtree Variable"', 'Figtree', 'system-ui', 'sans-serif'],
                // Headings: Outfit, geometric and clean. The class keeps its historical
                // name (`font-minecraft`, ~150 uses). Fredoka's rounder strokes are kept
                // for the "Cubi" wordmark only (`font-brand`).
                display: ['"Outfit Variable"', 'Outfit', '"Figtree Variable"', 'system-ui', 'sans-serif'],
                minecraft: ['"Outfit Variable"', 'Outfit', '"Figtree Variable"', 'system-ui', 'sans-serif'],
                brand: ['"Fredoka Variable"', 'Fredoka', '"Outfit Variable"', 'system-ui', 'sans-serif'],
                mono: ['ui-monospace', '"Cascadia Code"', 'Consolas', 'monospace'],
            },
            // Slightly softened corners. `rounded-sm` is the codebase's default
            // radius, so it carries the main value.
            borderRadius: {
                sm: '0.375rem',
                DEFAULT: '0.375rem',
                md: '0.5rem',
                lg: '0.625rem',
                xl: '0.75rem',
                '2xl': '1rem',
            },
            // Names kept from the old pixel-bevel style; values are now a soft
            // top highlight plus a quiet drop shadow.
            boxShadow: {
                bevel: 'inset 0 1px 0 rgb(255 255 255 / 0.18), 0 1px 2px rgb(0 0 0 / 0.35)',
                "bevel-press": 'inset 0 1px 2px rgb(0 0 0 / 0.35)',
                "bevel-panel": 'inset 0 1px 0 rgb(255 255 255 / 0.04), 0 0 0 1px rgb(var(--line)), 0 12px 32px -12px rgb(0 0 0 / 0.6)',
                glow: '0 0 0 1px rgb(var(--grass) / 0.35), 0 8px 24px -8px rgb(var(--grass) / 0.45)',
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }
        },
    },
    plugins: [],
}

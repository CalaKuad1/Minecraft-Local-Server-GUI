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
                background: "#09090b",
                surface: "#18181b",
                "surface-hover": "#27272a",
                primary: token('grass'),
                "primary-hover": "#059669",
                secondary: "#64748b",
                accent: token('diamond'),
                success: "#22c55e",
                warning: "#eab308",
                error: "#ef4444",
            },
            fontFamily: {
                sans: ['"Inter Variable"', 'Inter', 'system-ui', 'sans-serif'],
                minecraft: ['"Pixelify Sans Variable"', '"Pixelify Sans"', 'system-ui', 'sans-serif'],
            },
            // Pixel bevel: light edge on top, shade on the bottom, 1px dark outline.
            // The one recurring gesture of the UI, borrowed from the game's own widgets.
            boxShadow: {
                bevel: 'inset 0 2px 0 rgb(255 255 255 / 0.22), inset 0 -3px 0 rgb(0 0 0 / 0.32), 0 0 0 1px rgb(0 0 0 / 0.7)',
                "bevel-press": 'inset 0 3px 0 rgb(0 0 0 / 0.32), inset 0 -1px 0 rgb(255 255 255 / 0.1), 0 0 0 1px rgb(0 0 0 / 0.7)',
                "bevel-panel": 'inset 0 1px 0 rgb(255 255 255 / 0.06), inset 0 -2px 0 rgb(0 0 0 / 0.35), 0 0 0 1px rgb(0 0 0 / 0.55)',
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }
        },
    },
    plugins: [],
}

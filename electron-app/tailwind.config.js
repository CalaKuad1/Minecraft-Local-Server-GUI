/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "#09090b",
                surface: "#18181b",
                "surface-hover": "#27272a",
                primary: "#10b981", 
                "primary-hover": "#059669",
                secondary: "#64748b",
                accent: "#38bdf8",   
                success: "#22c55e",
                warning: "#eab308",
                error: "#ef4444",
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                minecraft: ['"Pixelify Sans"', 'cursive', 'system-ui', 'sans-serif'],
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }
        },
    },
    plugins: [],
}

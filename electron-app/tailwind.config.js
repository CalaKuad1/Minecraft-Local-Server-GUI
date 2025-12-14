/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "#0a0a0a",
                surface: "#1a1a1a",
                "surface-hover": "#252525",
                primary: "#6366f1", // Indigo 500
                "primary-hover": "#4f46e5",
                secondary: "#ec4899", // Pink 500
                accent: "#06b6d4",   // Cyan 500
                success: "#22c55e",
                warning: "#eab308",
                error: "#ef4444",
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }
        },
    },
    plugins: [],
}

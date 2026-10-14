import React, { useCallback, useEffect, useRef, useState } from 'react';
import './Cubi.css';

// Cubi, the app's mascot. Same drawing as src/assets/cubi-logo.svg, split into
// parts so each can move on its own. Moods map to what the server is doing:
//   idle  – floats and blinks (default)
//   sleep – eyes closed, slow breathing, little "z"s (server off)
//   busy  – hops with squash & stretch (starting, installing, loading)
//   happy – big smile and a celebration hop now and then (server online)
//   sad   – flat mouth, droops (errors)
// With `interactive`, clicking makes Cubi react (jump, wink or grin, with
// hearts/sparkles) and too many clicks in a row leave it dizzy for a moment.
// Motion is CSS-only and switched off by prefers-reduced-motion (index.css).
const MOODS = ['idle', 'sleep', 'busy', 'happy', 'sad'];
const REACTIONS = ['jump', 'wink', 'grin'];
const DIZZY_CLICKS = 7;      // clicks within DIZZY_WINDOW_MS to get dizzy
const DIZZY_WINDOW_MS = 2500;
const DIZZY_MS = 2600;

function CubiSvg({ mood, size, className, title, reaction }) {
    return (
        <svg
            viewBox="0 0 100 112"
            width={size}
            height={size * 1.12}
            className={`cubi cubi--${mood} ${reaction ? `cubi--react-${reaction}` : ''} ${className}`}
            role={title ? 'img' : undefined}
            aria-label={title}
            aria-hidden={title ? undefined : true}
        >
            <ellipse className="cubi-shadow" cx="50" cy="104" rx="27" ry="4.5" />
            <g className="cubi-body">
                <g strokeLinejoin="round" strokeWidth="5">
                    <polygon points="50,12 86,32 50,52 14,32" fill="#6ee7b7" stroke="#6ee7b7" />
                    <polygon points="14,32 50,52 50,92 14,72" fill="#10b981" stroke="#10b981" />
                    <polygon points="86,32 86,72 50,92 50,52" fill="#047857" stroke="#047857" />
                </g>
                {/* Face, drawn flat and sheared onto the right face of the cube. */}
                <g transform="matrix(1,-0.5556,0,1,50,52)">
                    <g className="cubi-eyes" fill="#032b1f">
                        <rect className="cubi-eye" x="9" y="10" width="5" height="9" rx="2" />
                        <rect className="cubi-eye cubi-eye--right" x="22" y="10" width="5" height="9" rx="2" />
                    </g>
                    <g className="cubi-eyes-closed" fill="none" stroke="#032b1f" strokeWidth="2.6" strokeLinecap="round">
                        <path d="M8.5 15 Q11.5 17.5 14.5 15" />
                        <path d="M21.5 15 Q24.5 17.5 27.5 15" />
                    </g>
                    <g className="cubi-eyes-dizzy" fill="none" stroke="#032b1f" strokeWidth="2" strokeLinecap="round">
                        <path d="M11.5 14.5 m-3 0 a3 3 0 1 0 6 0 a2 2 0 1 0 -4 0 a1 1 0 1 0 2 0" />
                        <path d="M24.5 14.5 m-3 0 a3 3 0 1 0 6 0 a2 2 0 1 0 -4 0 a1 1 0 1 0 2 0" />
                    </g>
                    <path className="cubi-mouth cubi-mouth--smile" d="M8 25 Q18 34 28 25" fill="none" stroke="#032b1f" strokeWidth="3.6" strokeLinecap="round" />
                    <path className="cubi-mouth cubi-mouth--grin" d="M8 24 Q18 37 28 24 Z" fill="#032b1f" stroke="#032b1f" strokeWidth="2" strokeLinejoin="round" />
                    <path className="cubi-mouth cubi-mouth--flat" d="M10 29 Q18 25 26 29" fill="none" stroke="#032b1f" strokeWidth="3.2" strokeLinecap="round" />
                    <path className="cubi-mouth cubi-mouth--wobbly" d="M9 28 Q12 25 15 28 T21 28 T27 28" fill="none" stroke="#032b1f" strokeWidth="2.6" strokeLinecap="round" />
                </g>
            </g>
            <g className="cubi-zs" fill="#6ee7b7" fontFamily="Fredoka Variable, Fredoka, sans-serif" fontWeight="600">
                <text className="cubi-z cubi-z--1" x="78" y="22" fontSize="12">z</text>
                <text className="cubi-z cubi-z--2" x="86" y="12" fontSize="9">z</text>
            </g>
        </svg>
    );
}

export default function Cubi({ mood = 'idle', size = 96, className = '', title, interactive = false }) {
    const base = MOODS.includes(mood) ? mood : 'idle';
    const [reaction, setReaction] = useState(null);
    const [dizzy, setDizzy] = useState(false);
    const [particles, setParticles] = useState([]);
    const clicks = useRef([]);
    const timers = useRef([]);
    const nextId = useRef(0);

    useEffect(() => () => timers.current.forEach(clearTimeout), []);
    const later = (fn, ms) => { timers.current.push(setTimeout(fn, ms)); };

    const onPoke = useCallback(() => {
        const now = Date.now();
        clicks.current = [...clicks.current.filter((t) => now - t < DIZZY_WINDOW_MS), now];
        if (clicks.current.length >= DIZZY_CLICKS) {
            clicks.current = [];
            setReaction(null);
            setDizzy(true);
            later(() => setDizzy(false), DIZZY_MS);
            return;
        }
        if (dizzy) return;
        const r = REACTIONS[Math.floor(Math.random() * REACTIONS.length)];
        // Re-trigger the CSS animation even when the same reaction repeats.
        setReaction(null);
        requestAnimationFrame(() => setReaction(r));
        later(() => setReaction((cur) => (cur === r ? null : cur)), 700);
        const burst = Array.from({ length: 4 }, () => ({
            id: nextId.current++,
            kind: Math.random() < 0.5 ? 'heart' : 'spark',
            x: Math.round((Math.random() - 0.5) * size * 0.9),
            delay: Math.round(Math.random() * 120),
        }));
        setParticles((p) => [...p, ...burst]);
        later(() => setParticles((p) => p.filter((q) => !burst.includes(q))), 1100);
    }, [dizzy, size]);

    const shownMood = dizzy ? 'dizzy' : base;
    if (!interactive) {
        return <CubiSvg mood={shownMood} size={size} className={className} title={title} reaction={reaction} />;
    }
    return (
        <span className={`relative inline-block ${className}`}>
            <button
                type="button"
                onClick={onPoke}
                className="cubi-poke block cursor-pointer rounded-full focus-visible:outline-none"
                aria-label={title || 'Cubi'}
            >
                <CubiSvg mood={shownMood} size={size} className="" reaction={reaction} />
            </button>
            <span className="pointer-events-none absolute inset-0" aria-hidden="true">
                {particles.map((p) => (
                    <span
                        key={p.id}
                        className={`cubi-particle cubi-particle--${p.kind}`}
                        style={{ left: `calc(50% + ${p.x}px)`, animationDelay: `${p.delay}ms`, fontSize: Math.max(10, size * 0.18) }}
                    >
                        {p.kind === 'heart' ? '♥' : '✦'}
                    </span>
                ))}
            </span>
        </span>
    );
}

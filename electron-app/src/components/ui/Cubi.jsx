import React from 'react';
import './Cubi.css';

// Cubi, the app's mascot. Same drawing as src/assets/cubi-logo.svg, split into
// parts so each can move on its own. Moods map to what the server is doing:
//   idle  – floats and blinks (default)
//   sleep – eyes closed, slow breathing, little "z"s (server off)
//   busy  – hops with squash & stretch (starting, installing, loading)
//   happy – big smile and a celebration hop now and then (server online)
//   sad   – flat mouth, droops (errors)
// Motion is CSS-only and switched off by prefers-reduced-motion (index.css).
const MOODS = ['idle', 'sleep', 'busy', 'happy', 'sad'];

export default function Cubi({ mood = 'idle', size = 96, className = '', title }) {
    const m = MOODS.includes(mood) ? mood : 'idle';
    return (
        <svg
            viewBox="0 0 100 112"
            width={size}
            height={size * 1.12}
            className={`cubi cubi--${m} ${className}`}
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
                        <rect className="cubi-eye" x="22" y="10" width="5" height="9" rx="2" />
                    </g>
                    <g className="cubi-eyes-closed" fill="none" stroke="#032b1f" strokeWidth="2.6" strokeLinecap="round">
                        <path d="M8.5 15 Q11.5 17.5 14.5 15" />
                        <path d="M21.5 15 Q24.5 17.5 27.5 15" />
                    </g>
                    <path className="cubi-mouth cubi-mouth--smile" d="M8 25 Q18 34 28 25" fill="none" stroke="#032b1f" strokeWidth="3.6" strokeLinecap="round" />
                    <path className="cubi-mouth cubi-mouth--grin" d="M8 24 Q18 37 28 24 Z" fill="#032b1f" stroke="#032b1f" strokeWidth="2" strokeLinejoin="round" />
                    <path className="cubi-mouth cubi-mouth--flat" d="M10 29 Q18 25 26 29" fill="none" stroke="#032b1f" strokeWidth="3.2" strokeLinecap="round" />
                </g>
            </g>
            <g className="cubi-zs" fill="#6ee7b7" fontFamily="Fredoka Variable, Fredoka, sans-serif" fontWeight="600">
                <text className="cubi-z cubi-z--1" x="78" y="22" fontSize="12">z</text>
                <text className="cubi-z cubi-z--2" x="86" y="12" fontSize="9">z</text>
            </g>
        </svg>
    );
}

import React from 'react';

export default function AbstractBackground() {
    return (
        <div className="fixed inset-0 z-[-1] bg-transparent pointer-events-none">
            {/* Vignette effect from edges to center (Sombra en los bordes para profundidad) */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_30%,_rgba(0,0,0,0.8)_100%)] pointer-events-none opacity-50" />
        </div>
    );
}

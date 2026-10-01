import React from 'react';

export default function NoiseGrain() {
    return (
        <div className="fx-noise pointer-events-none fixed inset-0 z-50 h-full w-full opacity-[0.035] mix-blend-overlay" aria-hidden="true">
            <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" className="absolute inset-0 h-full w-full opacity-100">
                <filter id="noiseFilter">
                    <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" stitchTiles="stitch" />
                </filter>
                <rect width="100%" height="100%" filter="url(#noiseFilter)" />
            </svg>
        </div>
    );
}

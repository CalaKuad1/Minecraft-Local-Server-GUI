import React from 'react';
import { Server } from 'lucide-react';
import { engineInfo } from './engines';

export function EngineIcon({ type, size = 16, className = '' }) {
    const { src, pixel, rounded } = engineInfo(type);
    if (!src) return <Server size={size} className={className} aria-hidden="true" />;
    return (
        <img
            src={src}
            alt=""
            aria-hidden="true"
            draggable={false}
            width={size}
            height={size}
            className={`shrink-0 object-contain ${rounded ? 'rounded-[22%]' : ''} ${className}`}
            style={{ width: size, height: size, imageRendering: pixel ? 'pixelated' : 'auto' }}
        />
    );
}

export default EngineIcon;

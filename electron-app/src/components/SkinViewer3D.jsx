import React, { useEffect, useRef, useState } from 'react';
import { SkinViewer, IdleAnimation } from 'skinview3d';
import { api } from '../api';

// 3D player model (skinview3d / three.js) showing the player's skin with the
// armor they wear painted on by the backend. Rotates slowly; drag to turn it.
// Loaded lazily from Players so three.js isn't part of the startup bundle.
export default function SkinViewer3D({ uuid, name, bust = '', width = 200, height = 280 }) {
    const canvasRef = useRef(null);
    const viewerRef = useRef(null);
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        const viewer = new SkinViewer({ canvas: canvasRef.current, width, height });
        viewer.animation = new IdleAnimation();
        viewer.autoRotate = true;
        viewer.autoRotateSpeed = 0.55;
        viewer.controls.enableZoom = false;
        viewer.zoom = 0.82;
        viewer.fov = 45;
        viewer.playerObject.rotation.y = -0.45;
        viewerRef.current = viewer;
        return () => {
            viewer.dispose();
            viewerRef.current = null;
        };
    }, [width, height]);

    useEffect(() => {
        let cancelled = false;
        let timer = null;
        const urls = [];
        setFailed(false);
        // Retry a few times: right after a server is created the game graphics
        // (default skin, armor textures) may still be downloading.
        const load = (attempt) => {
            api.getPlayerSkinUrl(uuid, name, `${bust}-${attempt}`)
                .then((u) => {
                    urls.push(u);
                    if (cancelled || !viewerRef.current) return null;
                    setFailed(false);
                    return viewerRef.current.loadSkin(u, { model: 'auto-detect' });
                })
                .catch(() => {
                    if (cancelled) return;
                    setFailed(true);
                    if (attempt < 4) timer = setTimeout(() => load(attempt + 1), 4000);
                });
        };
        load(0);
        return () => {
            cancelled = true;
            clearTimeout(timer);
            urls.forEach((u) => URL.revokeObjectURL(u));
        };
    }, [uuid, name, bust]);

    return (
        <div className="relative grid place-items-center" style={{ width, height }}>
            <canvas ref={canvasRef} className={`cursor-grab active:cursor-grabbing ${failed ? 'opacity-0' : ''}`} aria-label={name || uuid} />
            {failed && <span className="absolute text-xs text-ink-faint">—</span>}
        </div>
    );
}

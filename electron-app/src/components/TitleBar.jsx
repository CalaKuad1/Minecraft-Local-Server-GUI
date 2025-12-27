import React, { useState } from 'react';
import { Minus, Square, X } from 'lucide-react';

const TitleBar = () => {
    const handleMinimize = async () => {
        try { await window.electron.minimize(); } catch (e) { }
    };

    const handleMaximize = async () => {
        try { await window.electron.maximize(); } catch (e) { }
    };

    const handleClose = async () => {
        try { await window.electron.close(); } catch (e) { }
    };

    return (
        <div className="h-8 bg-[#0f0f0f] flex items-center justify-between select-none fixed top-0 left-0 right-0 z-[100] border-b border-white/5" style={{ WebkitAppRegion: 'drag' }}>
            {/* Title / Logo Area */}
            <div className="px-4 flex items-center gap-2">
                <div className="w-3 h-3 bg-primary rounded-sm rotate-45" />
                <span className="text-xs font-bold text-gray-400 tracking-wider uppercase">Minecraft Server GUI</span>
            </div>

            {/* Window Controls */}
            <div className="flex h-full" style={{ WebkitAppRegion: 'no-drag' }}>
                <button
                    onClick={handleMinimize}
                    className="w-10 h-full flex items-center justify-center hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                >
                    <Minus size={14} />
                </button>
                <button
                    onClick={handleMaximize}
                    className="w-10 h-full flex items-center justify-center hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                >
                    <Square size={12} />
                </button>
                <button
                    onClick={handleClose}
                    className="w-10 h-full flex items-center justify-center hover:bg-red-500 text-gray-400 hover:text-white transition-colors"
                >
                    <X size={14} />
                </button>
            </div>
        </div>
    );
};

export default TitleBar;

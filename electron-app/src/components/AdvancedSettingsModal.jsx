import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { X, Search, Save, Settings as SettingsIcon, AlertCircle } from 'lucide-react';

export default function AdvancedSettingsModal({ onClose, properties, onSave }) {
    const [localProps, setLocalProps] = useState({ ...properties });
    const [searchTerm, setSearchTerm] = useState('');
    const [debugMode, setDebugMode] = useState(false);

    const booleanKeys = [
        'allow-flight', 'allow-nether', 'broadcast-console-to-ops', 'broadcast-rcon-to-ops',
        'enable-command-block', 'enable-jmx-monitoring', 'enable-query', 'enable-rcon',
        'enable-status', 'enforce-secure-profile', 'enforce-whitelist', 'force-gamemode',
        'generate-structures', 'hardcore', 'online-mode', 'prevent-proxy-connections',
        'pvp', 'spawn-animals', 'spawn-monsters', 'spawn-npcs', 'use-native-transport',
        'white-list'
    ];

    const filteredKeys = Object.keys(localProps).filter(key =>
        key.toLowerCase().includes(searchTerm.toLowerCase())
    ).sort();

    const handleChange = (key, value) => {
        setLocalProps(prev => ({ ...prev, [key]: value }));
    };

    const handleSave = () => {
        onSave(localProps);
        onClose();
    };

    // Helper to determine if a value is boolean-like
    const isBoolean = (key) => booleanKeys.includes(key) || localProps[key] === 'true' || localProps[key] === 'false';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-[#0f0f0f] border border-white/10 rounded-2xl w-full max-w-4xl max-h-[85vh] shadow-2xl overflow-hidden relative z-10 flex flex-col mx-4"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-6 border-b border-white/5 bg-surface/50 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-primary/10 rounded-xl text-primary">
                            <SettingsIcon size={24} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white">Advanced Server Properties</h2>
                            <p className="text-sm text-gray-400">Edit raw server.properties values</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-white">
                        <X size={20} />
                    </button>
                </div>

                {/* Toolbar */}
                <div className="p-4 border-b border-white/5 bg-gray-900/50 flex items-center gap-4">
                    <div className="relative flex-1">
                        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                        <input
                            type="text"
                            placeholder="Search property..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full bg-[#0a0a0a] border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white focus:border-primary outline-none transition-colors"
                        />
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-gray-800">
                    {filteredKeys.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-20 text-gray-500">
                            <Search size={48} className="mb-4 opacity-20" />
                            <p>No properties found matching "{searchTerm}"</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 p-2">
                            {filteredKeys.map(key => (
                                <div key={key} className="flex flex-col p-3 bg-white/5 rounded-lg border border-white/5 hover:border-white/10 transition-colors">
                                    <label className="text-xs font-mono text-primary/80 mb-1.5 truncate" title={key}>{key}</label>
                                    {isBoolean(key) ? (
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={() => handleChange(key, 'true')}
                                                className={`flex-1 py-1.5 rounded text-xs font-bold transition-colors ${localProps[key] === 'true' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-black/20 text-gray-500 hover:bg-white/5'}`}
                                            >
                                                TRUE
                                            </button>
                                            <button
                                                onClick={() => handleChange(key, 'false')}
                                                className={`flex-1 py-1.5 rounded text-xs font-bold transition-colors ${localProps[key] === 'false' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-black/20 text-gray-500 hover:bg-white/5'}`}
                                            >
                                                FALSE
                                            </button>
                                        </div>
                                    ) : (
                                        <input
                                            type="text"
                                            value={localProps[key]}
                                            onChange={(e) => handleChange(key, e.target.value)}
                                            className="w-full bg-black/30 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:border-primary outline-none font-mono"
                                        />
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/5 bg-surface/50 flex justify-between items-center">
                    <div className="flex items-center gap-2 text-yellow-500/80 text-xs">
                        <AlertCircle size={14} />
                        <span>Advanced use only. Incorrect values may prevent server startup.</span>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={onClose}
                            className="px-6 py-2.5 rounded-xl text-sm font-bold text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSave}
                            className="px-8 py-2.5 rounded-xl text-sm font-bold text-white bg-primary hover:bg-primary-hover shadow-lg hover:shadow-primary/25 transition-all flex items-center gap-2"
                        >
                            <Save size={16} />
                            Save Configuration
                        </button>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}

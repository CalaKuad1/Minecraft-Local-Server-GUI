import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from './PixelIcons';
import { AnimatePresence, motion } from 'framer-motion';

// Helper to normalize simple arrays or mixed items to {value, label} objects
export function toSelectOptions(simpleArray) {
    if (!simpleArray || !Array.isArray(simpleArray)) return [];
    return simpleArray.map(item => {
        if (typeof item === 'object' && item !== null && 'value' in item) {
            return item;
        }
        return { value: String(item), label: String(item) };
    });
}

// Retain alias for compatibility
export const useSelectOptions = toSelectOptions;

export function Select({ value, onChange, options = [], placeholder = "Select option", className = "", disabled = false }) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);
    const normalizedOptions = toSelectOptions(options);

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Find label for current value
    const selectedLabel = normalizedOptions.find(opt => opt.value === value)?.label || value || placeholder;

    return (
        <div className={`relative ${className}`} ref={containerRef}>
            <button
                type="button"
                onClick={() => !disabled && setIsOpen(!isOpen)}
                disabled={disabled}
                className={`w-full h-full min-h-[2.25rem] flex items-center justify-between gap-2 bg-ground/70 border ${isOpen ? 'border-grass/50' : 'border-white/10'} hover:border-white/20 rounded-md px-3 text-sm font-medium text-ink transition-colors outline-none disabled:opacity-50`}
            >
                <span className="truncate">{selectedLabel}</span>
                <ChevronDown size={16} className={`text-gray-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -10, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute z-[200] w-full min-w-max mt-1 bg-raised border border-white/10 rounded-md shadow-2xl overflow-hidden max-h-60 overflow-y-auto p-1"
                    >
                        {normalizedOptions.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => {
                                    onChange(option.value);
                                    setIsOpen(false);
                                }}
                                className={`w-full text-left px-3 py-2 rounded flex items-center justify-between gap-3 text-sm transition-colors ${value === option.value ? 'bg-grass/10 text-mint font-semibold' : 'text-ink-dim hover:bg-white/5 hover:text-ink'}`}
                            >
                                <span className="truncate">{option.label}</span>
                                {value === option.value && <Check size={12} className="text-emerald-500" />}
                            </button>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

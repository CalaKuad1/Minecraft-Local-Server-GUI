import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from './PixelIcons';
import { AnimatePresence, motion } from 'framer-motion';

export function Select({ value, onChange, options, placeholder = "Select option", className = "", disabled = false }) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);

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
    const selectedLabel = options.find(opt => opt.value === value)?.label || value || placeholder;

    return (
        <div className={`relative ${className}`} ref={containerRef}>
            <button
                type="button"
                onClick={() => !disabled && setIsOpen(!isOpen)}
                disabled={disabled}
                className={`w-full h-full flex items-center justify-between bg-transparent border ${isOpen ? 'border-white/30' : 'border-white/10'} hover:border-white/20 rounded-inherit px-4 text-xs font-medium text-white transition-all outline-none disabled:opacity-50 shadow-sm`}
            >
                <span className="truncate tracking-widest uppercase">{selectedLabel}</span>
                <ChevronDown size={16} className={`text-gray-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -10, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute z-[200] w-full mt-1 bg-[#121212] border border-white/10 rounded-sm shadow-2xl overflow-hidden max-h-60 overflow-y-auto p-1 scrollbar-thin scrollbar-thumb-white/10"
                    >
                        {options.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => {
                                    onChange(option.value);
                                    setIsOpen(false);
                                }}
                                className={`w-full text-left px-3 py-2 rounded-sm flex items-center justify-between text-xs tracking-widest uppercase transition-all ${value === option.value ? 'bg-emerald-500/10 text-emerald-400 font-bold border-l-2 border-emerald-500' : 'text-zinc-500 hover:bg-white/5 hover:text-zinc-300'}`}
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

// Helper to normalize simple arrays to {value, label} objects
export function useSelectOptions(simpleArray) {
    if (!simpleArray) return [];
    if (typeof simpleArray[0] === 'string') {
        return simpleArray.map(item => ({ value: item, label: item }));
    }
    return simpleArray;
}

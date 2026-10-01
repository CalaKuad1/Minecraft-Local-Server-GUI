import React, { useCallback, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, CheckCircle, Info, X } from './PixelIcons';
import { IconButton } from './Button';
import { ToastContext } from './toastContext';
import { useTranslation } from '../../contexts/LanguageContext';
import { cn } from '../../utils/cn';

const MAX_VISIBLE = 4;
// Errors stay longer: they usually need to be read, not just noticed.
const DURATION = { success: 3500, info: 4500, error: 8000 };

const TONES = {
    success: { icon: CheckCircle, color: 'text-grass-lit', edge: 'bg-grass' },
    info: { icon: Info, color: 'text-diamond', edge: 'bg-diamond' },
    error: { icon: AlertTriangle, color: 'text-redstone', edge: 'bg-redstone' },
};

export function ToastProvider({ children }) {
    const { t } = useTranslation();
    const [toasts, setToasts] = useState([]);
    const timers = useRef(new Map());
    const counter = useRef(0);

    const dismiss = useCallback((id) => {
        clearTimeout(timers.current.get(id));
        timers.current.delete(id);
        setToasts((curr) => curr.filter((x) => x.id !== id));
    }, []);

    const push = useCallback((kind, message, options = {}) => {
        const id = ++counter.current;
        setToasts((curr) => [...curr, { id, kind, message, title: options.title }].slice(-MAX_VISIBLE));
        timers.current.set(id, setTimeout(() => dismiss(id), options.duration ?? DURATION[kind]));
        return id;
    }, [dismiss]);

    const api = useMemo(() => ({
        success: (m, o) => push('success', m, o),
        info: (m, o) => push('info', m, o),
        error: (m, o) => push('error', m, o),
        dismiss,
    }), [push, dismiss]);

    return (
        <ToastContext.Provider value={api}>
            {children}
            {/* Polite live region: screen readers announce toasts without stealing focus. */}
            <div className="pointer-events-none fixed bottom-5 right-5 z-[9990] flex w-80 max-w-[calc(100vw-2.5rem)] flex-col gap-2" aria-live="polite">
                <AnimatePresence initial={false}>
                    {toasts.map((x) => {
                        const tone = TONES[x.kind];
                        const Icon = tone.icon;
                        return (
                            <motion.div
                                key={x.id}
                                layout
                                role={x.kind === 'error' ? 'alert' : 'status'}
                                initial={{ opacity: 0, x: 24 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 24 }}
                                transition={{ duration: 0.18, ease: 'easeOut' }}
                                className="pointer-events-auto relative flex items-start gap-3 rounded-sm bg-panel py-3 pl-5 pr-2 shadow-bevel-panel"
                            >
                                <span className={cn('absolute inset-y-0 left-0 w-1', tone.edge)} aria-hidden="true" />
                                <Icon size={18} className={cn('mt-0.5 shrink-0', tone.color)} aria-hidden="true" />
                                <div className="min-w-0 flex-1 text-sm leading-snug">
                                    {x.title && <div className="font-minecraft font-semibold text-ink">{x.title}</div>}
                                    <div className="break-words text-ink-dim">{x.message}</div>
                                </div>
                                <IconButton label={t('common.close')} icon={X} size={14} onClick={() => dismiss(x.id)} />
                            </motion.div>
                        );
                    })}
                </AnimatePresence>
            </div>
        </ToastContext.Provider>
    );
}

import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X } from './PixelIcons';
import { IconButton } from './Button';
import { useTranslation } from '../../contexts/LanguageContext';
import { cn } from '../../utils/cn';

const SIZES = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg', xl: 'max-w-4xl' };
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

// The single modal shell for the app. Handles what every hand-rolled overlay was
// missing: role="dialog", Escape to close, focus moved in on open and restored on
// close, Tab kept inside, and a portal so no parent can clip or stack over it.
//
// Use inside <AnimatePresence> so it animates out:
//   <AnimatePresence>{open && <Modal title="..." onClose={...}>...</Modal>}</AnimatePresence>
// Mark the element that should receive focus first with `data-autofocus`.
export function Modal({ onClose, title, description, icon: Icon, iconClassName, size = 'md', dismissible = true, footer, children, className, zIndex = 200 }) {
    const { t } = useTranslation();
    const titleId = useId();
    const descId = useId();
    const panelRef = useRef(null);

    useEffect(() => {
        const previous = document.activeElement;
        const panel = panelRef.current;
        (panel?.querySelector('[data-autofocus]') || panel)?.focus({ preventScroll: true });
        return () => {
            if (previous instanceof HTMLElement) previous.focus({ preventScroll: true });
        };
    }, []);

    const onKeyDown = (e) => {
        if (e.key === 'Escape' && dismissible) {
            e.stopPropagation();
            onClose?.();
            return;
        }
        if (e.key !== 'Tab') return;
        const nodes = panelRef.current?.querySelectorAll(FOCUSABLE);
        if (!nodes || nodes.length === 0) {
            e.preventDefault();
            return;
        }
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        const active = document.activeElement;
        if (e.shiftKey && (active === first || active === panelRef.current)) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && active === last) {
            e.preventDefault();
            first.focus();
        }
    };

    return createPortal(
        <div className="fixed inset-0 flex items-center justify-center p-4" style={{ zIndex }}>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="absolute inset-0 bg-black/70 backdrop-blur-sm"
                onClick={dismissible ? onClose : undefined}
                aria-hidden="true"
            />
            <motion.div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? titleId : undefined}
                aria-describedby={description ? descId : undefined}
                tabIndex={-1}
                onKeyDown={onKeyDown}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                transition={{ duration: 0.15, ease: 'easeOut' }}
                className={cn(
                    'relative flex max-h-[88vh] w-full flex-col rounded-sm bg-panel text-ink shadow-bevel-panel outline-none',
                    SIZES[size],
                    className
                )}
            >
                {(title || description) && (
                    <header className="flex items-start gap-4 border-b border-white/5 p-6 pb-5">
                        {Icon && (
                            <div className={cn('mt-0.5 shrink-0', iconClassName || 'text-ink-dim')}>
                                <Icon size={24} aria-hidden="true" />
                            </div>
                        )}
                        <div className="min-w-0 flex-1">
                            {title && <h2 id={titleId} className="font-minecraft text-xl font-semibold tracking-wide text-ink">{title}</h2>}
                            {description && <p id={descId} className="mt-1 text-sm leading-relaxed text-ink-dim whitespace-pre-wrap">{description}</p>}
                        </div>
                        {dismissible && <IconButton label={t('common.close')} icon={X} size={18} onClick={onClose} />}
                    </header>
                )}
                <div className="min-h-0 flex-1 overflow-y-auto p-6">{children}</div>
                {footer && <footer className="flex flex-wrap items-center justify-end gap-3 border-t border-white/5 p-4">{footer}</footer>}
            </motion.div>
        </div>,
        document.body
    );
}

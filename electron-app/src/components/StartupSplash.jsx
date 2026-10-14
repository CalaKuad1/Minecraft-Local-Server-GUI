import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { api } from '../api';
import { APP_NAME } from '../brand';
import { useTranslation } from '../contexts/LanguageContext';
import Cubi from './ui/Cubi';

// Shown while the Python backend boots (a few seconds on a cold start), so the
// first thing people see is Cubi hopping instead of an empty library.
const MIN_VISIBLE_MS = 1300;
const GIVE_UP_MS = 30000;

export default function StartupSplash() {
    const { t } = useTranslation();
    const [ready, setReady] = useState(false);
    const [slow, setSlow] = useState(false);

    useEffect(() => {
        let cancelled = false;
        const started = Date.now();
        const slowTimer = setTimeout(() => !cancelled && setSlow(true), 6000);
        const poll = async () => {
            while (!cancelled && Date.now() - started < GIVE_UP_MS) {
                try {
                    await api.getStatus();
                    break;
                } catch {
                    await new Promise((r) => setTimeout(r, 400));
                }
            }
            const wait = Math.max(0, MIN_VISIBLE_MS - (Date.now() - started));
            setTimeout(() => !cancelled && setReady(true), wait);
        };
        poll();
        return () => { cancelled = true; clearTimeout(slowTimer); };
    }, []);

    return (
        <AnimatePresence>
            {!ready && (
                <motion.div
                    key="splash"
                    className="fixed inset-x-0 bottom-0 top-8 z-[90] flex flex-col items-center justify-center bg-ground"
                    initial={{ opacity: 1 }}
                    exit={{ opacity: 0, transition: { duration: 0.45, ease: 'easeOut' } }}
                >
                    <div
                        className="pointer-events-none absolute inset-0"
                        style={{ background: 'radial-gradient(28rem 20rem at 50% 42%, rgb(var(--grass) / 0.16), transparent 70%)' }}
                    />
                    <motion.div
                        initial={{ y: -60, opacity: 0, scale: 0.8 }}
                        animate={{ y: 0, opacity: 1, scale: 1 }}
                        exit={{ scale: 1.15, opacity: 0, transition: { duration: 0.35 } }}
                        transition={{ type: 'spring', stiffness: 260, damping: 14 }}
                    >
                        <Cubi mood="busy" size={112} />
                    </motion.div>
                    <motion.div
                        className="mt-5 font-brand text-4xl font-semibold tracking-tight text-ink"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.25, duration: 0.4 }}
                    >
                        {APP_NAME}
                    </motion.div>
                    <motion.p
                        className="mt-2 text-sm text-ink-faint"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.45, duration: 0.4 }}
                    >
                        {slow ? t('app.starting_slow') : t('app.starting')}
                    </motion.p>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

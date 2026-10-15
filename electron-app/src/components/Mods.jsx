import React from 'react';
import ContentBrowser from './ContentBrowser';
import Cubi from './ui/Cubi';
import { useTranslation } from '../contexts/LanguageContext';

export default function Mods({ status, onOpenWizard }) {
    const { t } = useTranslation();
    const serverType = (status?.type || status?.server_type || '').toString();
    const lower = serverType.toLowerCase();
    // Vanilla and Paper can't load mods: explain it and point to the wizard.
    const unsupported = (lower.includes('vanilla') || lower.includes('paper')) ? (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] p-4">
            <Cubi mood="sad" size={44} className="shrink-0" />
            <div className="min-w-[14rem] flex-1">
                <div className="font-display text-base font-semibold text-amber-100">{t('mods.unsupported_title')}</div>
                <p className="text-sm text-amber-100/70">{t('mods.unsupported_desc').replace('{type}', serverType || 'Vanilla/Paper')}</p>
            </div>
            {onOpenWizard && (
                <button onClick={onOpenWizard} className="rounded-md bg-white/10 px-4 py-2 text-sm font-semibold text-ink hover:bg-white/15">
                    {t('mods.open_wizard')}
                </button>
            )}
        </div>
    ) : null;
    return <ContentBrowser kind="mod" status={status} unsupported={unsupported} />;
}

import React from 'react';
import ContentBrowser from './ContentBrowser';
import Cubi from './ui/Cubi';
import { EmptyState } from './ui/Page';
import { useTranslation } from '../contexts/LanguageContext';

export default function Plugins({ status }) {
    const { t } = useTranslation();
    const serverType = (status?.type || status?.server_type || '').toString();
    const lower = serverType.toLowerCase();
    const supported = ['paper', 'spigot', 'bukkit', 'purpur', 'folia'].some((k) => lower.includes(k));
    if (!supported) {
        return (
            <div className="flex h-full items-center justify-center animate-in fade-in duration-200">
                <EmptyState icon={<Cubi mood="sad" size={72} />} title={t('plugins.unsupported_title')}>
                    {t('plugins.unsupported_desc')} {t('plugins.current_type').replace('{type}', serverType || '?')}
                </EmptyState>
            </div>
        );
    }
    return <ContentBrowser kind="plugin" status={status} />;
}

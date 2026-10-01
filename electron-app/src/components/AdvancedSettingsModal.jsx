import React, { useState } from 'react';
import { Search, Save, Settings as SettingsIcon, AlertCircle } from './ui/PixelIcons';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Toggle } from './ui/Toggle';
import { useTranslation } from '../contexts/LanguageContext';

export default function AdvancedSettingsModal({ onClose, properties, onSave }) {
    const { t } = useTranslation();
    const [localProps, setLocalProps] = useState({ ...properties });
    const [searchTerm, setSearchTerm] = useState('');

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
        <Modal
            size="xl"
            icon={SettingsIcon}
            title={t('advanced_props.title')}
            description={t('advanced_props.subtitle')}
            onClose={onClose}
            footer={
                <>
                    <p className="mr-auto flex items-center gap-2 text-sm text-gold">
                        <AlertCircle size={16} className="shrink-0" aria-hidden="true" />
                        {t('advanced_props.warning')}
                    </p>
                    <Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
                    <Button variant="primary" icon={Save} onClick={handleSave}>{t('advanced_props.save')}</Button>
                </>
            }
        >
            <div className="relative mb-4">
                <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
                <input
                    data-autofocus
                    type="search"
                    aria-label={t('advanced_props.search')}
                    placeholder={t('advanced_props.search')}
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="h-10 w-full rounded-sm border border-white/10 bg-ground pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-diamond"
                />
            </div>

            {filteredKeys.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-ink-faint">
                    <Search size={40} className="mb-4 opacity-30" aria-hidden="true" />
                    <p className="text-sm">{t('advanced_props.none_found')} &quot;{searchTerm}&quot;</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {filteredKeys.map(key => (
                        <div key={key} className="flex flex-col rounded-sm border border-white/5 bg-ground/60 p-3 transition-colors hover:border-white/15">
                            <div className="flex items-center justify-between gap-3">
                                <label htmlFor={`prop-${key}`} className="truncate font-mono text-xs text-ink-dim" title={key}>{key}</label>
                                {isBoolean(key) && (
                                    <Toggle
                                        label={key}
                                        checked={localProps[key] === 'true'}
                                        onChange={(on) => handleChange(key, on ? 'true' : 'false')}
                                    />
                                )}
                            </div>
                            {!isBoolean(key) && (
                                <input
                                    id={`prop-${key}`}
                                    type="text"
                                    value={localProps[key]}
                                    onChange={(e) => handleChange(key, e.target.value)}
                                    className="mt-2 h-9 w-full rounded-sm border border-white/10 bg-ground px-3 font-mono text-sm text-ink outline-none transition-colors focus:border-diamond"
                                />
                            )}
                        </div>
                    ))}
                </div>
            )}
        </Modal>
    );
}

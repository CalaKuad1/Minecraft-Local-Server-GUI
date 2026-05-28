import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Settings, Globe, Palette, Save, FolderOpen, Info } from './ui/PixelIcons';
import { api } from '../api';
import { useTranslation } from '../contexts/LanguageContext';

const LANGUAGES = [
    { code: 'en', label: 'English', native: 'English' },
    { code: 'es', label: 'Español', native: 'Español' },
    { code: 'fr', label: 'Français', native: 'Français' },
    { code: 'ru', label: 'Русский', native: 'Русский' },
];

const THEMES = [
    { id: 'dark', label: 'Dark (Default)' },
    { id: 'midnight', label: 'Midnight' },
    { id: 'emerald', label: 'Emerald' },
];

export default function AppSettings({ isOpen, onClose }) {
    const { t, changeLanguage } = useTranslation();
    const [settings, setSettings] = useState({
        language: 'en',
        theme: 'dark',
        notifications: true,
        autoStart: false,
        minimizeToTray: true,
        checkUpdates: true,
        dns_proxy_enabled: true,
    });
    const [activeSection, setActiveSection] = useState('general');
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        if (isOpen) {
            loadSettings();
        }
    }, [isOpen]);

    const loadSettings = async () => {
        try {
            const data = await api.getAppSettings();
            if (data && Object.keys(data).length > 0) {
                setSettings(prev => ({ ...prev, ...data }));
            }
        } catch (e) {
            console.error('Failed to load app settings', e);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await api.updateAppSettings(settings);
            await changeLanguage(settings.language); // Update UI immediately
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (e) {
            console.error('Failed to save settings', e);
        }
        setSaving(false);
    };

    const updateSetting = (key, value) => {
        setSettings(prev => ({ ...prev, [key]: value }));
    };

    const sections = [
        { id: 'general', label: t('settings.general'), Icon: Settings },
        { id: 'language', label: t('settings.language'), Icon: Globe },
        { id: 'appearance', label: t('settings.appearance'), Icon: Palette },
        { id: 'dns', label: 'Cloudflare', Icon: Globe },
        { id: 'about', label: t('settings.about'), Icon: Info },
    ];

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.98, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.98, y: 20 }}
                    transition={{ duration: 0.2, ease: "easeOut" }}
                    className="bg-[#0a0a0a] border border-white/10 rounded-sm w-[700px] max-h-[520px] flex overflow-hidden shadow-2xl"
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Left Navigation */}
                    <div className="w-48 bg-[#070707] border-r border-white/5 py-6 px-3 flex flex-col shrink-0">
                        <div className="flex items-center gap-2 px-3 mb-6">
                            <Settings size={14} className="text-emerald-400" />
                            <span className="font-minecraft text-xs tracking-widest uppercase text-zinc-300">Settings</span>
                        </div>

                        <nav className="space-y-0.5 flex-1">
                            {sections.map(({ id, label, Icon }) => (
                                <button
                                    key={id}
                                    onClick={() => setActiveSection(id)}
                                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-sm text-xs transition-all ${
                                        activeSection === id
                                            ? 'bg-white/10 text-white'
                                            : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5'
                                    }`}
                                >
                                    <Icon size={14} className={activeSection === id ? 'text-emerald-400' : ''} />
                                    <span className="font-minecraft tracking-wider uppercase">{label}</span>
                                </button>
                            ))}
                        </nav>

                    <div className="mt-auto p-6 border-t border-white/5">
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className={`w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-sm text-[10px] font-minecraft tracking-widest uppercase transition-all border ${
                                saved
                                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                                    : 'bg-white text-black border-transparent hover:bg-zinc-200 font-bold'
                            }`}
                        >
                            <Save size={12} />
                            {saving ? t('common.loading') : saved ? t('settings.saved') : t('settings.save')}
                        </button>
                    </div>
                    </div>

                    {/* Content Area */}
                    <div className="flex-1 py-6 px-8 overflow-y-auto">
                        {/* Close button */}
                        <button onClick={onClose} className="absolute top-4 right-4 p-1.5 text-zinc-600 hover:text-white hover:bg-white/10 rounded-sm transition-colors">
                            <X size={14} />
                        </button>

                        {activeSection === 'general' && (
                            <div>
                                <h2 className="font-minecraft text-sm tracking-widest uppercase text-zinc-300 mb-6">{t('settings.general_settings.title')}</h2>

                                <div className="space-y-5">
                                    {/* Auto-start server */}
                                    <ToggleSetting
                                        label={t('settings.auto_start.title')}
                                        description={t('settings.auto_start.desc')}
                                        value={settings.autoStart}
                                        onChange={(v) => updateSetting('autoStart', v)}
                                    />

                                    {/* Notifications */}
                                    <ToggleSetting
                                        label="Desktop Notifications"
                                        description="Show notifications when server status changes."
                                        value={settings.notifications}
                                        onChange={(v) => updateSetting('notifications', v)}
                                    />

                                    {/* Minimize to tray */}
                                    <ToggleSetting
                                        label="Minimize to Tray"
                                        description="Keep the app running in the system tray when closed."
                                        value={settings.minimizeToTray}
                                        onChange={(v) => updateSetting('minimizeToTray', v)}
                                    />

                                    {/* Check for updates */}
                                    <ToggleSetting
                                        label="Check for Updates"
                                        description="Automatically check for new app versions on launch."
                                        value={settings.checkUpdates}
                                        onChange={(v) => updateSetting('checkUpdates', v)}
                                    />
                                </div>
                            </div>
                        )}

                        {activeSection === 'language' && (
                            <div>
                                <h2 className="font-minecraft text-sm tracking-widest uppercase text-zinc-300 mb-2">{t('settings.language_settings.title')}</h2>
                                <p className="text-xs text-zinc-600 mb-6">{t('settings.language_settings.desc')}</p>

                                <div className="space-y-2">
                                    {LANGUAGES.map(lang => (
                                        <button
                                            key={lang.code}
                                            onClick={() => updateSetting('language', lang.code)}
                                            className={`w-full flex items-center justify-between px-4 py-3 rounded-md border transition-all ${
                                                settings.language === lang.code
                                                    ? 'bg-emerald-500/10 border-emerald-500/30 text-white'
                                                    : 'bg-transparent border-white/5 text-zinc-400 hover:bg-white/5 hover:border-white/10'
                                            }`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <span className="font-minecraft text-xs tracking-wider uppercase">{lang.label}</span>
                                                <span className="text-[10px] text-zinc-600 font-mono">{lang.native}</span>
                                            </div>
                                            {settings.language === lang.code && (
                                                <div className="w-2 h-2 rounded-sm bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {activeSection === 'appearance' && (
                            <div>
                                <h2 className="font-minecraft text-sm tracking-widest uppercase text-zinc-300 mb-2">{t('settings.appearance_settings.title')}</h2>
                                <p className="text-xs text-zinc-600 mb-6">{t('settings.appearance_settings.desc')}</p>

                                <div className="space-y-2">
                                    {THEMES.map(theme => (
                                        <button
                                            key={theme.id}
                                            onClick={() => updateSetting('theme', theme.id)}
                                            className={`w-full flex items-center justify-between px-4 py-3 rounded-md border transition-all ${
                                                settings.theme === theme.id
                                                    ? 'bg-emerald-500/10 border-emerald-500/30 text-white'
                                                    : 'bg-transparent border-white/5 text-zinc-400 hover:bg-white/5 hover:border-white/10'
                                            }`}
                                        >
                                            <span className="font-minecraft text-xs tracking-wider uppercase">{theme.label}</span>
                                            {settings.theme === theme.id && (
                                                <div className="w-2 h-2 rounded-sm bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {activeSection === 'dns' && (
                            <div>
                                <h2 className="font-minecraft text-sm tracking-widest uppercase text-zinc-300 mb-2">Fixed Address</h2>
                                <p className="text-xs text-zinc-600 mb-6">Give your server a permanent domain that never changes, even when the tunnel IP does.</p>

                                <div className="space-y-5">
                                    <ToggleSetting
                                        label="Enable Fixed Address"
                                        description="Auto-update DNS when tunnel starts. Your server gets a permanent domain like survival.play.ariser.com"
                                        value={settings.dns_proxy_enabled}
                                        onChange={(v) => updateSetting('dns_proxy_enabled', v)}
                                    />

                                    <div className="space-y-1">
                                        <label className="text-[10px] font-minecraft tracking-wider uppercase text-zinc-500">DNS Proxy URL</label>
                                        <input
                                            type="text"
                                            value={settings.dns_proxy_url || ''}
                                            onChange={(e) => updateSetting('dns_proxy_url', e.target.value)}
                                            placeholder="Default: community proxy (leave empty)"
                                            className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-xs text-white placeholder-zinc-700 font-mono outline-none focus:border-white/30 transition-colors"
                                        />
                                        <p className="text-[9px] text-zinc-600 mt-1">
                                            Leave empty to use the community proxy. Advanced users can host their own.
                                        </p>
                                    </div>

                                    <div className="p-3 bg-white/[0.02] border border-white/5 rounded-sm">
                                        <p className="text-[10px] text-zinc-500 leading-relaxed font-mono">
                                            When the tunnel starts, your server automatically gets a fixed address at{' '}
                                            <span className="text-emerald-400">[servername].play.ariser.com</span>.
                                            Max 1 update per minute per server. Free for everyone.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeSection === 'about' && (
                            <div>
                                <h2 className="font-minecraft text-sm tracking-widest uppercase text-zinc-300 mb-6">{t('settings.about_settings.title')}</h2>

                                <div className="space-y-4">
                                    <div className="bg-white/[0.02] border border-white/5 rounded-md p-5">
                                        <div className="font-minecraft text-lg tracking-wider text-emerald-400 mb-1">Minecraft Server GUI</div>
                                        <div className="text-xs font-mono text-zinc-500 mb-4">v1.3.0</div>
                                        <p className="text-xs text-zinc-500 leading-relaxed">
                                            A professional server management tool for Minecraft servers.
                                            Supports Vanilla, Paper, Spigot, Fabric, Forge, and NeoForge server types.
                                        </p>
                                    </div>

                                    <div className="flex items-center justify-between py-3 border-b border-white/[0.03]">
                                        <span className="text-xs font-minecraft tracking-wider uppercase text-zinc-500">{t('settings.developer')}</span>
                                        <span className="text-xs font-mono text-zinc-400">CalaKuad1</span>
                                    </div>
                                    <div className="flex items-center justify-between py-3 border-b border-white/[0.03]">
                                        <span className="text-xs font-minecraft tracking-wider uppercase text-zinc-500">{t('settings.framework')}</span>
                                        <span className="text-xs font-mono text-zinc-400">Electron + React + FastAPI</span>
                                    </div>
                                    <div className="flex items-center justify-between py-3 border-b border-white/[0.03]">
                                        <span className="text-xs font-minecraft tracking-wider uppercase text-zinc-500">{t('settings.license')}</span>
                                        <span className="text-xs font-mono text-zinc-400">MIT</span>
                                    </div>

                                    <a
                                        href="https://github.com/CalaKuad1"
                                        target="_blank"
                                        rel="noreferrer"
                                        className="inline-flex items-center gap-2 text-xs font-minecraft tracking-wider uppercase text-zinc-500 hover:text-emerald-400 transition-colors mt-2"
                                    >
                                        <FolderOpen size={12} />
                                        {t('settings.view_github')}
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}

// Reusable toggle setting component
function ToggleSetting({ label, description, value, onChange }) {
    return (
        <div className="flex items-center justify-between py-3 border-b border-white/[0.03]">
            <div className="min-w-0 mr-4">
                <div className="text-xs font-minecraft tracking-wider uppercase text-zinc-300">{label}</div>
                <div className="text-[10px] text-zinc-600 mt-0.5">{description}</div>
            </div>
            <button
                onClick={() => onChange(!value)}
                className={`relative w-10 h-5 rounded-sm transition-colors shrink-0 ${value ? 'bg-emerald-500/30' : 'bg-white/10'}`}
            >
                <div className={`absolute top-0.5 w-4 h-4 rounded-sm transition-all ${value ? 'left-[22px] bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'left-0.5 bg-zinc-500'}`}></div>
            </button>
        </div>
    );
}

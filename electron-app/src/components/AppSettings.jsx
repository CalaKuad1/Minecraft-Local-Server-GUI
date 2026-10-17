import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { APP_NAME } from '../brand';
import {
    X, Settings, Globe, Download, Info, Check, RefreshCw, Loader2, FolderOpen, ExternalLink, Github, AlertCircle, ChevronDown,
} from './ui/PixelIcons';
import { api } from '../api';
import { useTranslation } from '../contexts/LanguageContext';
import { Toggle } from './ui/Toggle';
import { Card, SettingRow } from './ui/Page';
import Cubi from './ui/Cubi';
import { getPerfMode, setPerfMode } from '../utils/perfMode';

const REPO = 'https://github.com/CalaKuad1/Minecraft-Local-Server-GUI';
const WEBSITE = 'https://mlsg-web.vercel.app';

const LANGUAGES = [
    { code: 'en', native: 'English' },
    { code: 'es', native: 'Español' },
    { code: 'fr', native: 'Français' },
    { code: 'ru', native: 'Русский' },
];

const UPDATE_POLICIES = ['auto', 'ask', 'off'];

// App-wide settings (not a server's). Every change is saved right away, so
// there is no Save button and nothing to lose when closing the window.
export default function AppSettings({ isOpen, onClose }) {
    const { t, changeLanguage } = useTranslation();
    const [settings, setSettings] = useState({ language: 'en', auto_update: 'ask', dns_proxy_enabled: true, dns_proxy_url: '' });
    const [section, setSection] = useState('general');
    const [savedAt, setSavedAt] = useState(0);
    const [appVersion, setAppVersion] = useState('');
    const [liteMode, setLiteMode] = useState(() => getPerfMode() === 'lite');
    const [update, setUpdate] = useState(null);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const savedTimer = useRef(null);

    useEffect(() => {
        if (!isOpen) return undefined;
        let cancelled = false;
        api.getAppSettings()
            .then((data) => { if (!cancelled && data) setSettings((prev) => ({ ...prev, ...data })); })
            .catch((e) => console.error('Failed to load app settings', e));
        window.electron?.getAppInfo?.()
            .then((info) => { if (!cancelled && info?.version) setAppVersion(info.version); })
            .catch(() => {});
        const off = window.electron?.onUpdateStatus?.((s) => setUpdate(s));
        return () => { cancelled = true; if (typeof off === 'function') off(); };
    }, [isOpen]);

    useEffect(() => () => clearTimeout(savedTimer.current), []);

    useEffect(() => {
        if (!isOpen) return undefined;
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [isOpen, onClose]);

    const save = async (patch) => {
        setSettings((prev) => ({ ...prev, ...patch }));
        try {
            await api.updateAppSettings(patch);
            if (patch.language) await changeLanguage(patch.language);
            if (patch.auto_update) window.electron?.setAutoUpdateMode?.(patch.auto_update);
            setSavedAt(Date.now());
            clearTimeout(savedTimer.current);
            savedTimer.current = setTimeout(() => setSavedAt(0), 1800);
        } catch (e) {
            console.error('Failed to save settings', e);
        }
    };

    const checkNow = async () => {
        setUpdate({ state: 'checking' });
        const r = await window.electron?.checkForUpdates?.();
        if (!r || r.state === 'disabled') setUpdate({ state: 'disabled' });
        else if (r.state === 'error') setUpdate(r);
    };

    if (!isOpen) return null;

    const sections = [
        { id: 'general', label: t('settings.general'), Icon: Settings },
        { id: 'updates', label: t('settings.updates.nav'), Icon: Download },
        { id: 'dns', label: t('settings.dns.nav'), Icon: Globe },
        { id: 'about', label: t('settings.about'), Icon: Info },
    ];

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6 backdrop-blur-sm"
            onClick={onClose}
        >
            <motion.div
                role="dialog"
                aria-modal="true"
                aria-label={t('settings.title')}
                initial={{ opacity: 0, y: 12, scale: 0.985 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.18, ease: 'easeOut' }}
                className="relative flex h-[540px] w-full max-w-[780px] overflow-hidden rounded-xl border border-white/10 bg-ground shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                <nav className="flex w-52 shrink-0 flex-col border-r border-white/[0.06] bg-panel/50 p-3">
                    <h2 className="px-3 pb-4 pt-2 font-display text-lg font-semibold text-ink">{t('settings.title')}</h2>
                    <div className="space-y-0.5">
                        {sections.map(({ id, label, Icon }) => {
                            const active = section === id;
                            return (
                                <button
                                    key={id}
                                    onClick={() => setSection(id)}
                                    className={`relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${active ? 'text-ink' : 'text-ink-faint hover:bg-white/[0.04] hover:text-ink'}`}
                                >
                                    {active && <motion.span layoutId="app-settings-nav" className="absolute inset-0 rounded-md bg-white/[0.08]" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
                                    <Icon size={17} className={`relative ${active ? 'text-grass-lit' : ''}`} />
                                    <span className="relative">{label}</span>
                                </button>
                            );
                        })}
                    </div>
                    <div className="mt-auto flex items-center gap-2 px-3 pb-1 text-xs text-ink-faint">
                        {savedAt ? (
                            <span className="inline-flex items-center gap-1.5 text-grass-lit"><Check size={14} /> {t('settings.saved')}</span>
                        ) : (
                            <span>{t('settings.autosave')}</span>
                        )}
                    </div>
                </nav>

                <button
                    onClick={onClose}
                    aria-label={t('common.close')}
                    className="absolute right-3 top-3 z-10 rounded-md p-1.5 text-ink-faint transition-colors hover:bg-white/10 hover:text-ink"
                >
                    <X size={18} />
                </button>

                <div className="min-w-0 flex-1 overflow-y-auto px-8 py-7">
                    {section === 'general' && (
                        <Section title={t('settings.general')} subtitle={t('settings.general_settings.desc')}>
                            <div>
                                <Label>{t('settings.language')}</Label>
                                <div className="grid grid-cols-2 gap-2">
                                    {LANGUAGES.map((lang) => (
                                        <Choice
                                            key={lang.code}
                                            active={settings.language === lang.code}
                                            onClick={() => save({ language: lang.code })}
                                            title={lang.native}
                                        />
                                    ))}
                                </div>
                            </div>
                            <div>
                                <Label>{t('settings.appearance')}</Label>
                                <Card>
                                    <SettingRow label={t('settings.appearance_settings.reduce_effects')} description={t('settings.appearance_settings.reduce_effects_desc')}>
                                        <Toggle
                                            label={t('settings.appearance_settings.reduce_effects')}
                                            checked={liteMode}
                                            onChange={(on) => { setLiteMode(on); setPerfMode(on ? 'lite' : 'full'); }}
                                        />
                                    </SettingRow>
                                </Card>
                            </div>
                        </Section>
                    )}

                    {section === 'updates' && (
                        <Section title={t('settings.updates.title')} subtitle={t('settings.auto_update.desc')}>
                            <Card className="flex items-center gap-4 p-4">
                                <UpdateStatus update={update} version={appVersion} t={t} />
                                <div className="ml-auto flex shrink-0 gap-2">
                                    {update?.state === 'available' && update.manual && (
                                        <button onClick={() => window.electron?.downloadUpdate?.()} className="inline-flex items-center gap-2 rounded-md bg-grass px-3.5 py-2 text-sm font-semibold text-black/85 transition-colors hover:bg-grass-lit">
                                            <Download size={15} /> {t('settings.updates.download')}
                                        </button>
                                    )}
                                    {update?.state === 'downloaded' ? (
                                        <button onClick={() => window.electron?.installUpdate?.()} className="inline-flex items-center gap-2 rounded-md bg-grass px-3.5 py-2 text-sm font-semibold text-black/85 transition-colors hover:bg-grass-lit">
                                            <RefreshCw size={15} /> {t('settings.updates.restart')}
                                        </button>
                                    ) : (
                                        <button
                                            onClick={checkNow}
                                            disabled={update?.state === 'checking' || update?.state === 'downloading'}
                                            className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3.5 py-2 text-sm font-medium text-ink transition-colors hover:bg-white/[0.08] disabled:opacity-50"
                                        >
                                            <RefreshCw size={15} className={update?.state === 'checking' ? 'animate-spin' : ''} /> {t('settings.updates.check')}
                                        </button>
                                    )}
                                </div>
                            </Card>
                            <div>
                                <Label>{t('settings.auto_update.title')}</Label>
                                <div className="space-y-2">
                                    {UPDATE_POLICIES.map((id) => (
                                        <Choice
                                            key={id}
                                            active={settings.auto_update === id}
                                            onClick={() => save({ auto_update: id })}
                                            title={t(`settings.auto_update.options.${id}`)}
                                            description={t(`settings.auto_update.options.${id}_desc`)}
                                        />
                                    ))}
                                </div>
                            </div>
                        </Section>
                    )}

                    {section === 'dns' && (
                        <Section title={t('settings.dns.title')} subtitle={t('settings.dns.desc')}>
                            <Card>
                                <SettingRow label={t('settings.dns.enable')} description={t('settings.dns.enable_desc')}>
                                    <Toggle
                                        label={t('settings.dns.enable')}
                                        checked={settings.dns_proxy_enabled !== false}
                                        onChange={(v) => save({ dns_proxy_enabled: v })}
                                    />
                                </SettingRow>
                            </Card>
                            <p className="text-sm leading-relaxed text-ink-dim">{t('settings.dns.info')}</p>
                            <div>
                                <button
                                    onClick={() => setShowAdvanced((v) => !v)}
                                    className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-faint transition-colors hover:text-ink"
                                    aria-expanded={showAdvanced}
                                >
                                    <ChevronDown size={16} className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                                    {t('settings.dns.advanced')}
                                </button>
                                {showAdvanced && (
                                    <div className="mt-3 space-y-1.5">
                                        <label htmlFor="dns-url" className="text-sm font-semibold text-ink">{t('settings.dns.url')}</label>
                                        <input
                                            id="dns-url"
                                            type="text"
                                            value={settings.dns_proxy_url || ''}
                                            onChange={(e) => setSettings((p) => ({ ...p, dns_proxy_url: e.target.value }))}
                                            onBlur={(e) => save({ dns_proxy_url: e.target.value.trim() })}
                                            placeholder={t('settings.dns.url_placeholder')}
                                            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 font-mono text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-grass/60"
                                        />
                                        <p className="text-xs text-ink-faint">{t('settings.dns.url_hint')}</p>
                                    </div>
                                )}
                            </div>
                        </Section>
                    )}

                    {section === 'about' && (
                        <div className="flex h-full flex-col">
                            <div className="flex items-center gap-5">
                                <Cubi mood="happy" size={76} interactive />
                                <div>
                                    <div className="font-brand text-3xl font-semibold text-grass-lit">{APP_NAME}</div>
                                    <div className="mt-0.5 text-sm text-ink-faint">{appVersion ? `${t('settings.version')} ${appVersion}` : ''}</div>
                                </div>
                            </div>
                            <p className="mt-5 text-sm leading-relaxed text-ink-dim">{t('settings.about_tagline')}</p>

                            <div className="mt-6 grid grid-cols-2 gap-2">
                                <LinkButton href={WEBSITE} Icon={Globe}>{t('settings.website')}</LinkButton>
                                <LinkButton href={REPO} Icon={Github}>{t('settings.view_github')}</LinkButton>
                                <LinkButton href={`${REPO}/issues`} Icon={AlertCircle}>{t('settings.report_issue')}</LinkButton>
                                <button
                                    onClick={() => window.electron?.openDataFolder?.()}
                                    className="flex items-center gap-2.5 rounded-md border border-white/[0.08] bg-white/[0.03] px-3.5 py-2.5 text-left text-sm font-medium text-ink transition-colors hover:bg-white/[0.07]"
                                    title={t('settings.open_logs_desc')}
                                >
                                    <FolderOpen size={16} className="text-ink-faint" /> {t('settings.open_logs')}
                                </button>
                            </div>

                            <div className="mt-auto pt-6 text-xs leading-relaxed text-ink-faint">
                                <p>{t('settings.made_by')} CalaKuad1 · MIT</p>
                                <p className="mt-1">{t('settings.about_disclaimer')}</p>
                            </div>
                        </div>
                    )}
                </div>
            </motion.div>
        </motion.div>
    );
}

function Section({ title, subtitle, children }) {
    return (
        <div>
            <h3 className="font-display text-2xl font-semibold text-ink">{title}</h3>
            {subtitle && <p className="mt-1 text-sm text-ink-faint">{subtitle}</p>}
            <div className="mt-6 space-y-6">{children}</div>
        </div>
    );
}

function Label({ children }) {
    return <div className="mb-2 px-0.5 text-xs font-semibold uppercase tracking-wider text-ink-faint">{children}</div>;
}

// Selectable card used as a radio option.
function Choice({ active, onClick, title, description }) {
    return (
        <button
            role="radio"
            aria-checked={active}
            onClick={onClick}
            className={`flex w-full items-center justify-between gap-4 rounded-md border px-4 py-3 text-left transition-colors ${
                active ? 'border-grass/50 bg-grass/10' : 'border-white/[0.08] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.05]'
            }`}
        >
            <div className="min-w-0">
                <div className={`text-sm font-semibold ${active ? 'text-ink' : 'text-ink-dim'}`}>{title}</div>
                {description && <div className="mt-0.5 text-xs text-ink-faint">{description}</div>}
            </div>
            <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${active ? 'border-grass bg-grass text-black/80' : 'border-white/20'}`}>
                {active && <Check size={13} strokeWidth={3} />}
            </span>
        </button>
    );
}

function LinkButton({ href, Icon, children }) {
    return (
        <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2.5 rounded-md border border-white/[0.08] bg-white/[0.03] px-3.5 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-white/[0.07]"
        >
            <Icon size={16} className="text-ink-faint" />
            <span className="flex-1">{children}</span>
            <ExternalLink size={13} className="text-ink-faint" />
        </a>
    );
}

function UpdateStatus({ update, version, t }) {
    const s = update?.state;
    const v = update?.version || '';
    let icon = <Check size={20} className="text-grass-lit" />;
    let title = t('settings.updates.current').replace('{version}', version || '—');
    let detail = t('settings.updates.idle');
    if (s === 'checking') {
        icon = <Loader2 size={20} className="animate-spin text-ink-faint" />;
        detail = t('settings.updates.checking');
    } else if (s === 'up-to-date') {
        detail = t('settings.updates.up_to_date');
    } else if (s === 'available') {
        icon = <Download size={20} className="text-grass-lit" />;
        title = t('settings.updates.available').replace('{version}', v);
        detail = update.manual ? t('settings.updates.available_ask') : t('settings.updates.available_auto');
    } else if (s === 'downloading') {
        icon = <Loader2 size={20} className="animate-spin text-grass-lit" />;
        title = t('settings.updates.downloading').replace('{percent}', String(update.percent ?? 0));
        detail = t('settings.updates.available_auto');
    } else if (s === 'downloaded') {
        icon = <Download size={20} className="text-grass-lit" />;
        title = t('settings.updates.ready').replace('{version}', v);
        detail = t('settings.updates.ready_desc');
    } else if (s === 'error') {
        icon = <AlertCircle size={20} className="text-redstone" />;
        detail = t('settings.updates.error');
    } else if (s === 'disabled') {
        detail = t('settings.updates.disabled');
    }
    return (
        <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/[0.05]">{icon}</span>
            <div className="min-w-0">
                <div className="text-sm font-semibold text-ink">{title}</div>
                <div className="text-xs text-ink-faint">{detail}</div>
            </div>
        </div>
    );
}

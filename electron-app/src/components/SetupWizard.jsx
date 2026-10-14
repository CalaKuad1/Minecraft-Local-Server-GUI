import React, { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { api, API_TOKEN, WS_BASE } from '../api';
import { useTranslation } from '../contexts/LanguageContext';
import { Select } from './ui/Select';
import Cubi from './ui/Cubi';
import { Check, Folder, Download, Server, Loader2, ArrowLeft, ArrowRight, Box, HardDrive, Terminal, AlertTriangle, Info, Plus, Play } from './ui/PixelIcons';
import fabricLogo from '../assets/engines/fabric.png';
import forgeLogo from '../assets/engines/forge.png';
import neoforgeLogo from '../assets/engines/neoforge.png';
import paperLogo from '../assets/engines/Paper_JE2_BE2.webp';
import spigotLogo from '../assets/engines/spigot.png';
import vanillaLogo from '../assets/engines/vanilla.webp';

function EngineIcon({ type, size = 16, className = "" }) {
    const t = (type || '').toLowerCase();
    let src = null;
    if (t.includes('paper')) src = paperLogo;
    else if (t.includes('neoforge')) src = neoforgeLogo;
    else if (t.includes('forge')) src = forgeLogo;
    else if (t.includes('fabric')) src = fabricLogo;
    else if (t.includes('spigot')) src = spigotLogo;
    else if (t.includes('vanilla')) src = vanillaLogo;

    if (src) {
        return (
            <div className={`flex items-center justify-center overflow-hidden ${className}`} style={{ width: size, height: size }}>
                <img src={src} className="w-full h-full object-contain brightness-0 invert" alt={type} />
            </div>
        );
    }
    return <Server size={size} className={className} />;
}

function StepItem({ icon, label, active, completed }) {
    return (
        <div className={`flex items-center gap-3 transition-all ${active ? 'opacity-100' : completed ? 'opacity-60' : 'opacity-30'}`}>
            <div className={`w-8 h-8 rounded-sm border flex items-center justify-center transition-all ${
                active ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                completed ? 'bg-white/5 border-white/10 text-white' :
                'bg-black/20 border-white/5 text-ink-faint'
            }`}>
                {completed ? <Check size={14} /> : icon}
            </div>
            <span className={`text-xs font-medium ${active ? 'text-white' : 'text-ink-faint'}`}>{label}</span>
        </div>
    );
}

// Order matters: the list reads from "simplest" to "most modded".
const ENGINES = ['paper', 'vanilla', 'fabric', 'forge', 'neoforge'];
const RECOMMENDED_ENGINE = 'paper';
const MODDED_ENGINES = ['fabric', 'forge', 'neoforge'];
const ENGINE_NAMES = { vanilla: 'Vanilla', paper: 'Paper', fabric: 'Fabric', forge: 'Forge', neoforge: 'NeoForge' };

const labelClass = "text-xs font-semibold text-gray-300 mb-2 block";
const hintClass = "text-[11px] text-ink-faint mt-2 leading-relaxed";
const backButtonClass = "text-xs text-ink-faint hover:text-white transition-colors flex items-center gap-2";
const primaryButtonClass = "ml-auto px-6 py-2.5 rounded-sm text-[11px] font-minecraft uppercase tracking-widest transition-all disabled:opacity-30 flex items-center gap-2";

export default function SetupWizard({ onComplete, onCancel }) {
    const { t } = useTranslation();
    const [step, setStep] = useState(1);
    const [mode, setMode] = useState('install');

    // Engine Data
    const [serverType, setServerType] = useState(RECOMMENDED_ENGINE);
    const [version, setVersion] = useState('');
    const [versionsList, setVersionsList] = useState([]);
    const [loadingVersions, setLoadingVersions] = useState(false);
    const [versionsError, setVersionsError] = useState(false);
    const [loaderVersionsList, setLoaderVersionsList] = useState([]);
    const [loaderVersion, setLoaderVersion] = useState('');
    const [allVersionData, setAllVersionData] = useState(null);

    // Configuration Data
    // `C:/MinecraftServers` was previously hardcoded: on Linux/macOS this silently
    // created a folder literally named `C:` in the backend's working directory.
    // In the real Electron shell we resolve the user's home directory via IPC and
    // default to `~/MinecraftServers`, which works on every platform. The hardcoded
    // value acts only as a fallback for plain-browser (Vite dev) previews.
    const [parentPath, setParentPath] = useState(() =>
        (typeof window !== 'undefined' && window.electron && window.electron.getAppInfo)
            ? ''
            : 'C:/MinecraftServers'
    );
    const [folderName, setFolderName] = useState('my-server');
    const [existingPath, setExistingPath] = useState('');

    useEffect(() => {
        let cancelled = false;
        window.electron?.getAppInfo?.()
            .then((info) => {
                if (!cancelled && info?.home) setParentPath(`${info.home}/MinecraftServers`);
            })
            .catch(() => { /* fall back to the browser default */ });
        return () => { cancelled = true; };
    }, []);

    // RAM config
    const [ramPreset, setRamPreset] = useState("4"); // Default 4GB
    const [eulaAccepted, setEulaAccepted] = useState(false);

    // Java status
    const [javaStatus, setJavaStatus] = useState(null);
    const [javaLoading, setJavaLoading] = useState(false);

    // Install State
    const [installing, setInstalling] = useState(false);
    const [progress, setProgress] = useState(0);
    const [statusMessage, setStatusMessage] = useState('');
    const [installError, setInstallError] = useState('');
    const [importing, setImporting] = useState(false);
    const [importError, setImportError] = useState('');
    const ws = useRef(null);
    const completedRef = useRef(false);
    const installedServerId = useRef(null);

    // Load versions when step 2 is active
    useEffect(() => {
        if (step === 2 && mode === 'install') {
            setLoadingVersions(true);
            setVersionsError(false);
            setVersionsList([]);
            setVersion('');

            api.getVersions(serverType).then(data => {
                if (data.versions && data.versions.length > 0) {
                    setVersionsList(data.versions);
                    setVersion(data.versions[0]);
                    setFolderName(`${serverType}-${data.versions[0]}`);

                    if (data.all_data) {
                        setAllVersionData(data.all_data);
                        const subVersions = data.all_data[data.versions[0]] || [];
                        setLoaderVersionsList(subVersions);
                        if (subVersions.length > 0) setLoaderVersion(subVersions[0]);
                    } else {
                        setAllVersionData(null);
                        setLoaderVersionsList([]);
                        setLoaderVersion('');
                    }
                } else {
                    setVersionsError(true);
                }
            }).catch(err => {
                console.error("Failed to load versions:", err);
                setVersionsList([]);
                setVersionsError(true);
            }).finally(() => setLoadingVersions(false));
        }
    }, [serverType, step, mode]);

    const handleVersionChange = (ver) => {
        setVersion(ver);
        setFolderName(`${serverType}-${ver}`);

        if (allVersionData) {
            const subVersions = allVersionData[ver] || [];
            setLoaderVersionsList(subVersions);
            if (subVersions.length > 0) setLoaderVersion(subVersions[0]);
            else setLoaderVersion('');
        }
    };

    useEffect(() => {
        if (!version) return;
        setJavaLoading(true);
        api.checkJava(version)
            .then(data => setJavaStatus(data))
            .catch(() => setJavaStatus(null))
            .finally(() => setJavaLoading(false));
    }, [version]);

    // WebSocket + Polling logic for installation progress
    useEffect(() => {
        if (step === 4 && installing) {
            if (ws.current) ws.current.close();
            ws.current = new WebSocket(`${WS_BASE}/ws/console${API_TOKEN ? `?token=${encodeURIComponent(API_TOKEN)}` : ''}`);

            const handleData = (d) => {
                if (d.type === 'progress') {
                    setProgress(d.value);
                    setStatusMessage(d.message);
                    if (d.error) {
                        setInstallError(String(d.error));
                        setInstalling(false);
                    }
                    if (d.server_id) installedServerId.current = d.server_id;
                    if (d.value >= 100 && !completedRef.current) {
                        completedRef.current = true;
                        setTimeout(() => onComplete && onComplete(installedServerId.current), 1500);
                    }
                }
                if (d.type === 'java_progress' && d.message) {
                    setStatusMessage(d.message);
                }
            };

            ws.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'batch') data.items.forEach(handleData);
                    else handleData(data);
                } catch (e) {
                    console.error('[SetupWizard] Failed to parse WebSocket message:', e);
                }
            };

            const intervalId = setInterval(async () => {
                if (completedRef.current) return;
                try {
                    const data = await api.getInstallProgress();
                    if (data && typeof data.value === 'number') {
                        setProgress(prev => Math.max(prev, data.value));
                        if (data.message) setStatusMessage(data.message);
                        if (data.error) {
                            setInstallError(String(data.error));
                            setInstalling(false);
                            clearInterval(intervalId);
                        }
                    }
                } catch (e) {
                    console.error('[SetupWizard] Progress check error:', e);
                }
            }, 1000);

            return () => {
                if (ws.current) ws.current.close();
                clearInterval(intervalId);
            };
        }
    }, [step, installing, onComplete]);

    const handleDeploy = async () => {
        setInstalling(true);
        setInstallError('');
        setStatusMessage('');
        setStep(4);
        setProgress(0);
        completedRef.current = false;

        try {
            await api.installServer({
                server_type: serverType,
                version: version,
                parent_path: parentPath,
                folder_name: folderName,
                forge_version: serverType === 'forge' ? loaderVersion : null,
                neoforge_version: serverType === 'neoforge' ? loaderVersion : null,
                ram_max: ramPreset,
                ram_min: "2",
                ram_unit: "G"
            });
        } catch (err) {
            console.error("Installation failed to start", err);
            setInstallError(err.message || String(err));
            setInstalling(false);
        }
    };

    const handleImport = async () => {
        if (!existingPath) return;
        setImporting(true);
        setImportError('');
        try {
            const result = await api.importServer(existingPath);
            if (result && result.id) {
                onComplete(result.id);
            } else {
                setImportError(t('wizard.import.invalid'));
            }
        } catch (err) {
            console.error("Import failed", err);
            setImportError(err.message || t('wizard.import.failed'));
        } finally {
            setImporting(false);
        }
    };

    const javaLine = () => {
        if (javaLoading) return { tone: 'muted', text: t('wizard.details.java_checking') };
        if (!javaStatus) return { tone: 'muted', text: t('wizard.details.java_unknown') };
        const v = String(javaStatus.required_version ?? '');
        if (javaStatus.status_color === 'green') {
            return { tone: 'ok', text: t('wizard.details.java_ready').replace('{v}', v) };
        }
        if (javaStatus.system_java) {
            return {
                tone: 'info',
                text: t('wizard.details.java_system').replace('{v}', v).replace('{sys}', String(javaStatus.system_java[0]))
            };
        }
        return { tone: 'info', text: t('wizard.details.java_download').replace('{v}', v) };
    };

    const needsJavaDownload = javaStatus && !javaStatus.local_java_available && javaStatus.needs_download;
    const done = step === 4 && !installError && progress >= 100;

    return (
        <div className="flex flex-col h-full w-full bg-transparent animate-in fade-in duration-500 relative">

            {/* Main Wizard Container */}
            <div className="w-full flex-1 flex overflow-hidden">

                {/* Sidebar */}
                <div className="w-64 bg-ground/80 border-r border-white/10 flex flex-col backdrop-blur-xl shadow-2xl z-10 flex-shrink-0">
                    <div className="p-8">
                        <div className="flex items-center gap-3 text-emerald-400 mb-10">
                            <Plus size={18} />
                            <span className="font-minecraft text-lg tracking-wide">{t('wizard.title')}</span>
                        </div>

                        <div className="space-y-6">
                            <StepItem icon={<Box size={14} />} label={t('wizard.steps.mode')} active={step === 1} completed={step > 1} />
                            {mode === 'install' && (
                                <StepItem icon={<Play size={14} />} label={t('wizard.steps.type')} active={step === 2} completed={step > 2} />
                            )}
                            <StepItem icon={<HardDrive size={14} />} label={t('wizard.steps.details')} active={step === 3} completed={step > 3} />
                            {mode === 'install' && (
                                <StepItem icon={<Download size={14} />} label={t('wizard.steps.install')} active={step === 4} completed={done} />
                            )}
                        </div>
                    </div>

                    <div className="mt-auto p-8 border-t border-white/5">
                        <p className="text-[11px] text-ink-faint leading-relaxed">{t('wizard.footer')}</p>
                    </div>
                </div>

                {/* Content Area */}
                <div className="flex-1 flex flex-col relative overflow-hidden bg-ground/70 backdrop-blur-md">
                    <AnimatePresence mode="wait">

                        {/* STEP 1: NEW OR EXISTING */}
                        {step === 1 && (
                            <motion.div
                                key="step1"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 justify-center max-w-3xl"
                            >
                                <h2 className="text-2xl font-minecraft tracking-wide text-emerald-400 mb-2">{t('wizard.mode.title')}</h2>
                                <p className="text-ink-faint text-sm mb-8">{t('wizard.mode.subtitle')}</p>

                                <div className="grid grid-cols-2 gap-4">
                                    <button
                                        onClick={() => { setMode('install'); setStep(2); }}
                                        className="p-6 bg-emerald-500/5 border border-emerald-500/30 hover:border-emerald-400/60 hover:bg-emerald-500/10 rounded-sm text-left transition-all group"
                                    >
                                        <Download size={28} className="text-emerald-400 mb-4" />
                                        <h3 className="text-sm font-minecraft tracking-wide text-white mb-2">{t('wizard.mode.new_title')}</h3>
                                        <p className="text-xs text-gray-400 leading-relaxed">{t('wizard.mode.new_desc')}</p>
                                    </button>

                                    <button
                                        onClick={() => { setMode('existing'); setStep(3); }}
                                        className="p-6 bg-black/40 border border-white/5 hover:border-white/20 rounded-sm text-left transition-all group"
                                    >
                                        <Folder size={28} className="text-gray-400 mb-4" />
                                        <h3 className="text-sm font-minecraft tracking-wide text-white mb-2">{t('wizard.mode.import_title')}</h3>
                                        <p className="text-xs text-gray-400 leading-relaxed">{t('wizard.mode.import_desc')}</p>
                                    </button>
                                </div>

                                <div className="mt-12 flex justify-start">
                                    <button onClick={onCancel} className={backButtonClass}>
                                        <ArrowLeft size={12} /> {t('wizard.exit')}
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* STEP 2: GAME TYPE + VERSION */}
                        {step === 2 && mode === 'install' && (
                            <motion.div
                                key="step2"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 max-w-4xl overflow-y-auto"
                            >
                                <h2 className="text-2xl font-minecraft tracking-wide text-emerald-400 mb-2">{t('wizard.type.title')}</h2>
                                <p className="text-ink-faint text-sm mb-6">{t('wizard.type.subtitle')}</p>

                                <div className="space-y-6">
                                    <div className="space-y-2" role="radiogroup">
                                        {ENGINES.map((type) => {
                                            const selected = serverType === type;
                                            return (
                                                <button
                                                    key={type}
                                                    role="radio"
                                                    aria-checked={selected}
                                                    onClick={() => setServerType(type)}
                                                    className={`w-full px-4 py-3 flex items-center gap-4 rounded-sm border text-left transition-all ${
                                                        selected
                                                            ? 'bg-emerald-500/5 border-emerald-500/40'
                                                            : 'bg-black/30 border-white/5 hover:border-white/15'
                                                    }`}
                                                >
                                                    <EngineIcon
                                                        type={type}
                                                        size={22}
                                                        className={`shrink-0 transition-opacity ${selected ? "opacity-100" : "opacity-40"}`}
                                                    />
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2">
                                                            <span className={`text-sm font-minecraft tracking-wide ${selected ? 'text-emerald-400' : 'text-white'}`}>{ENGINE_NAMES[type]}</span>
                                                            {type === RECOMMENDED_ENGINE && (
                                                                <span className="px-1.5 py-0.5 rounded-sm bg-emerald-500/15 text-emerald-300 text-[10px] font-semibold">
                                                                    {t('wizard.type.recommended')}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <p className="text-xs text-gray-400 mt-0.5">{t(`wizard.type.${type}`)}</p>
                                                    </div>
                                                    <div className={`w-4 h-4 rounded-full border-2 shrink-0 ${selected ? 'border-emerald-400 bg-emerald-400/30' : 'border-white/20'}`} />
                                                </button>
                                            );
                                        })}
                                    </div>

                                    {MODDED_ENGINES.includes(serverType) && (
                                        <div className="flex items-start gap-2 text-xs text-yellow-200/80 bg-yellow-500/5 border border-yellow-500/20 rounded-sm px-3 py-2">
                                            <Info size={14} className="shrink-0 mt-0.5" />
                                            <span>{t('wizard.type.mods_note')}</span>
                                        </div>
                                    )}

                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <label className={labelClass}>{t('wizard.type.version')}</label>
                                            <Select
                                                value={version}
                                                onChange={handleVersionChange}
                                                options={versionsList}
                                                placeholder={loadingVersions ? t('wizard.type.loading') : t('wizard.type.select')}
                                                disabled={loadingVersions}
                                                className="bg-black/30 border-white/5 rounded-sm h-10 text-[11px] font-minecraft tracking-widest"
                                            />
                                            <p className={versionsError ? "text-[11px] text-red-400 mt-2" : hintClass}>
                                                {versionsError ? t('wizard.type.versions_error') : t('wizard.type.version_hint')}
                                            </p>
                                        </div>

                                        {(serverType === 'forge' || serverType === 'neoforge') && version && (
                                            <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                                                <label className={labelClass}>
                                                    {t('wizard.type.loader_version').replace('{loader}', ENGINE_NAMES[serverType])}
                                                </label>
                                                <Select
                                                    value={loaderVersion}
                                                    onChange={setLoaderVersion}
                                                    options={loaderVersionsList}
                                                    placeholder={t('wizard.type.select')}
                                                    className="bg-black/30 border-white/5 rounded-sm h-10 text-[11px] font-minecraft tracking-widest"
                                                />
                                                <p className={hintClass}>{t('wizard.type.loader_hint')}</p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="mt-auto flex gap-4 pt-8 border-t border-white/5">
                                    <button onClick={() => setStep(1)} className={backButtonClass}><ArrowLeft size={12} /> {t('wizard.back')}</button>
                                    <button
                                        onClick={() => setStep(3)}
                                        disabled={!version || loadingVersions}
                                        className={`${primaryButtonClass} bg-white text-black hover:bg-gray-200`}
                                    >
                                        {t('wizard.next')} <ArrowRight size={14} />
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* STEP 3: DETAILS (INSTALL) */}
                        {step === 3 && mode === 'install' && (
                            <motion.div
                                key="step3"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 max-w-4xl overflow-y-auto"
                            >
                                <h2 className="text-2xl font-minecraft tracking-wide text-emerald-400 mb-2">{t('wizard.details.title')}</h2>
                                <p className="text-ink-faint text-sm mb-8">{t('wizard.details.subtitle')}</p>

                                <div className="space-y-6">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className={labelClass}>{t('wizard.details.name')}</label>
                                            <input
                                                type="text"
                                                value={folderName}
                                                onChange={(e) => setFolderName(e.target.value)}
                                                className="w-full bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-sm text-white focus:border-emerald-500/40 outline-none"
                                            />
                                        </div>
                                        <div>
                                            <label className={labelClass}>{t('wizard.details.folder')}</label>
                                            <div className="flex gap-2">
                                                <input
                                                    type="text"
                                                    value={parentPath}
                                                    onChange={(e) => setParentPath(e.target.value)}
                                                    className="flex-1 min-w-0 bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-xs text-gray-400 font-mono outline-none truncate focus:border-emerald-500/40"
                                                />
                                                <button onClick={async () => {
                                                    const path = await api.openDirectoryPicker();
                                                    if (path) setParentPath(path);
                                                }} className="px-3 bg-black/40 border border-white/10 hover:border-white/20 rounded-sm transition-colors">
                                                    <Folder size={14} className="text-ink-faint" />
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    <div>
                                        <label className={labelClass}>{t('wizard.details.ram')}</label>
                                        <div className="grid grid-cols-3 gap-3">
                                            {["2", "4", "8"].map((val) => (
                                                <button
                                                    key={val}
                                                    onClick={() => setRamPreset(val)}
                                                    className={`p-3 text-center border rounded-sm transition-all ${
                                                        ramPreset === val
                                                            ? 'border-emerald-500/40 bg-emerald-500/5 text-emerald-400'
                                                            : 'border-white/5 bg-black/20 text-gray-400 hover:border-white/15'
                                                    }`}
                                                >
                                                    <div className="text-sm font-minecraft tracking-wide">{val} GB</div>
                                                    <div className="text-[11px] mt-1 opacity-80">{t(`wizard.details.ram_${val}`)}</div>
                                                </button>
                                            ))}
                                        </div>
                                        <p className={hintClass}>{t('wizard.details.ram_hint')}</p>
                                    </div>

                                    <div className="flex items-center gap-2 text-xs">
                                        {(() => {
                                            const { tone, text } = javaLine();
                                            const color = tone === 'ok' ? 'text-emerald-400' : tone === 'info' ? 'text-sky-300' : 'text-ink-faint';
                                            return (
                                                <>
                                                    {javaLoading
                                                        ? <Loader2 size={12} className="animate-spin text-ink-faint" />
                                                        : tone === 'ok' ? <Check size={12} className={color} /> : <Info size={12} className={color} />}
                                                    <span className="font-semibold text-gray-300">{t('wizard.details.java')}:</span>
                                                    <span className={color}>{text}</span>
                                                </>
                                            );
                                        })()}
                                    </div>

                                    <div className="pt-4 border-t border-white/5">
                                        <label className="flex items-start gap-3 cursor-pointer group">
                                            <div className={`mt-0.5 w-4 h-4 rounded-sm flex items-center justify-center border transition-all shrink-0 ${eulaAccepted ? 'bg-emerald-500 border-emerald-500' : 'bg-black/40 border-white/20 group-hover:border-white/40'}`}>
                                                {eulaAccepted && <Check size={12} className="text-black" />}
                                            </div>
                                            <input type="checkbox" className="hidden" checked={eulaAccepted} onChange={(e) => setEulaAccepted(e.target.checked)} />
                                            <span className="select-none">
                                                <span className="block text-sm text-gray-200">{t('wizard.details.eula')}</span>
                                                <span className="block text-[11px] text-ink-faint mt-0.5">{t('wizard.details.eula_hint')}</span>
                                            </span>
                                        </label>
                                    </div>
                                </div>

                                <div className="mt-auto flex gap-4 pt-8 border-t border-white/5">
                                    <button onClick={() => setStep(2)} className={backButtonClass}><ArrowLeft size={12} /> {t('wizard.back')}</button>
                                    <button
                                        onClick={handleDeploy}
                                        disabled={!eulaAccepted || !parentPath.trim() || !folderName.trim()}
                                        className={`${primaryButtonClass} bg-emerald-500 text-black hover:bg-emerald-400`}
                                    >
                                        {needsJavaDownload ? t('wizard.details.create_download') : t('wizard.details.create')}
                                        <ArrowRight size={14} />
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* STEP 3: ADD EXISTING SERVER */}
                        {step === 3 && mode === 'existing' && (
                            <motion.div
                                key="step3_existing"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 max-w-4xl justify-center"
                            >
                                <h2 className="text-2xl font-minecraft tracking-wide text-emerald-400 mb-2">{t('wizard.import.title')}</h2>
                                <p className="text-ink-faint text-sm mb-8">{t('wizard.import.subtitle')}</p>

                                <div>
                                    <label className={labelClass}>{t('wizard.import.folder')}</label>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={existingPath}
                                            onChange={(e) => setExistingPath(e.target.value)}
                                            placeholder={t('wizard.import.placeholder')}
                                            className="flex-1 bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-500/40"
                                        />
                                        <button onClick={async () => {
                                            const path = await api.openDirectoryPicker();
                                            if (path) setExistingPath(path);
                                        }} className="px-3 bg-black/40 border border-white/10 hover:border-white/20 rounded-sm transition-colors flex items-center justify-center">
                                            <Folder size={16} className="text-emerald-500/60" />
                                        </button>
                                    </div>
                                </div>

                                {importError && (
                                    <div className="flex items-start gap-2 text-xs text-red-300 mt-4">
                                        <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                                        <span>{importError}</span>
                                    </div>
                                )}

                                <div className="mt-12 flex gap-4">
                                    <button onClick={() => setStep(1)} className={backButtonClass}><ArrowLeft size={12} /> {t('wizard.back')}</button>
                                    <button
                                        onClick={handleImport}
                                        disabled={!existingPath || importing}
                                        className={`${primaryButtonClass} bg-emerald-500 text-black hover:bg-emerald-400`}
                                    >
                                        {importing ? <><Loader2 size={12} className="animate-spin" /> {t('wizard.import.adding')}</> : t('wizard.import.button')}
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* STEP 4: INSTALLING */}
                        {step === 4 && (
                            <motion.div
                                key="step4"
                                initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
                                className="flex-1 flex flex-col items-center justify-center p-10 text-center"
                            >
                                {installError ? (
                                    <>
                                        <Cubi mood="sad" size={96} className="mb-5" />
                                        <h3 className="text-lg font-minecraft tracking-wide text-white mb-2">{t('wizard.install.failed_title')}</h3>
                                        <p className="text-sm text-gray-400 max-w-md mb-4">{t('wizard.install.failed_hint')}</p>
                                        <pre className="text-[11px] text-red-300/80 bg-black/40 border border-white/5 rounded-sm px-3 py-2 max-w-lg w-full whitespace-pre-wrap break-words text-left max-h-32 overflow-y-auto mb-8">{installError}</pre>
                                        <div className="flex gap-4">
                                            <button onClick={() => setStep(3)} className={backButtonClass}><ArrowLeft size={12} /> {t('wizard.back')}</button>
                                            <button onClick={handleDeploy} className={`${primaryButtonClass} ml-0 bg-white text-black hover:bg-gray-200`}>
                                                {t('wizard.install.retry')}
                                            </button>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        <Cubi mood={done ? 'happy' : 'busy'} size={104} className="mb-5" />
                                        <h3 className="text-lg font-minecraft tracking-wide text-white mb-2">
                                            {done ? t('wizard.install.done') : t('wizard.install.title')}
                                        </h3>
                                        <p className="text-ink-faint text-xs h-4 truncate max-w-md mb-8">{statusMessage || t('wizard.install.starting')}</p>

                                        <div className="w-72 max-w-full bg-black/40 rounded-sm h-1.5 overflow-hidden border border-white/5">
                                            <motion.div
                                                className="h-full bg-emerald-500"
                                                initial={{ width: 0 }}
                                                animate={{ width: `${progress}%` }}
                                                transition={{ ease: "easeOut" }}
                                            />
                                        </div>
                                        <div className="mt-3 text-[10px] font-minecraft text-emerald-500/60 tracking-widest">{Math.round(progress)}%</div>
                                    </>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
}

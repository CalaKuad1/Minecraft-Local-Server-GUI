import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import { Select, useSelectOptions } from './ui/Select';
import { Check, ChevronRight, Folder, Download, Server, Loader2, ArrowLeft, Coffee } from 'lucide-react';

export default function SetupWizard({ onComplete, onCancel }) {
    const [step, setStep] = useState(1);
    const [mode, setMode] = useState('install');

    // Form Data
    const [serverType, setServerType] = useState('vanilla');
    const [version, setVersion] = useState('');
    const [versionsList, setVersionsList] = useState([]);

    const [parentPath, setParentPath] = useState('C:/MinecraftServers');
    const [folderName, setFolderName] = useState('my-server');
    const [existingPath, setExistingPath] = useState('');

    const [installing, setInstalling] = useState(false);
    const [progress, setProgress] = useState(0);
    const [statusMessage, setStatusMessage] = useState('Initializing...');
    const ws = useRef(null);

    // Java State
    const [javaStatus, setJavaStatus] = useState(null);
    const [installingJava, setInstallingJava] = useState(false);
    const [javaProgress, setJavaProgress] = useState(0);
    const [javaProgressMsg, setJavaProgressMsg] = useState('');

    // Check Java capability
    const checkJava = async (ver) => {
        if (!ver) return;
        setJavaStatus(null);
        try {
            const status = await api.checkJava(ver);
            setJavaStatus(status);
        } catch (e) {
            console.error("Java check failed", e);
        }
    };

    useEffect(() => {
        if (step === 2 && mode === 'install') { // Only load logic for install mode
            if (versionsList.length === 0) {
                api.getVersions(serverType).then(data => {
                    if (data.versions) {
                        setVersionsList(data.versions);
                        if (data.versions.length > 0) {
                            setVersion(data.versions[0]);
                            checkJava(data.versions[0]);
                        }
                    }
                });
            }
        }
    }, [serverType, step, mode]);

    // Handle version change manually to trigger check
    const handleVersionChange = (ver) => {
        setVersion(ver);
        checkJava(ver);
    };

    useEffect(() => {
        // Connect to WS for installation AND Java progress
        if ((step === 4 && installing) || installingJava) {
            ws.current = new WebSocket('ws://127.0.0.1:8000/ws/console');

            ws.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'progress' && installing) {
                        setProgress(data.value);
                        setStatusMessage(data.message);
                        if (data.value >= 100) setTimeout(onComplete, 1500);
                        if (data.error) { setStatusMessage(`Error: ${data.error}`); setInstalling(false); }
                    }

                    // Handle Java Progress separately
                    if (data.type === 'java_progress') {
                        setJavaProgress(data.value);
                        if (data.message) setJavaProgressMsg(data.message);

                        if (data.value >= 100) {
                            setTimeout(() => {
                                setInstallingJava(false);
                                checkJava(version); // Re-check to get green status
                            }, 1000);
                        }
                        if (data.error) {
                            setJavaProgressMsg(`Error: ${data.error}`);
                            setInstallingJava(false);
                        }
                    }
                } catch (e) { }
            };

            return () => {
                if (ws.current) ws.current.close();
            };
        }
    }, [step, installing, installingJava, version]);

    const handleInstallJava = async () => {
        setInstallingJava(true);
        setJavaProgress(0);
        setJavaProgressMsg('Initializing download...');
        await api.installJava(version);
    };

    const handleInstall = async () => {
        setStep(4); // Move to progress screen
        setInstalling(true);
        setProgress(0);
        setStatusMessage("Starting installation process...");

        await api.installServer({
            server_type: serverType,
            version: version,
            parent_path: parentPath,
            folder_name: folderName
        });
    };

    const handleExisting = async () => {
        const val = await api.validatePath(existingPath);
        if (!val.valid) {
            alert("Invalid path");
            return;
        }

        // Extract folder name for server name
        const name = existingPath.split(/[\\/]/).pop() || "Imported Server";

        await api.addServer({
            name: name,
            path: existingPath,
            type: 'unknown',
            ram_min: "2",
            ram_max: "4",
            ram_unit: "G",
            version: version || "unknown"
        });
        onComplete();
    };

    // Auto-detection logic
    const detectRef = useRef(null);
    const [detectedInfo, setDetectedInfo] = useState(null);

    const triggerDetection = async (path) => {
        if (!path) return;
        setDetectedInfo(null);
        try {
            const info = await api.detectServer(path);
            if (info && info.detected) {
                setDetectedInfo(info);
                // Directly set version if detected, no need to check list
                if (info.version) {
                    setVersion(info.version);
                    checkJava(info.version);
                }
            }
        } catch (e) {
            console.warn("Detection failed", e);
        }
    };

    // Debounced detection when typing path
    useEffect(() => {
        if (mode === 'existing' && existingPath) {
            const timer = setTimeout(() => triggerDetection(existingPath), 1000);
            return () => clearTimeout(timer);
        }
    }, [existingPath, mode]);

    return (
        <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto animate-in fade-in zoom-in duration-500 relative">

            {/* Back Button */}
            <button
                onClick={onCancel}
                className="absolute top-0 left-0 text-gray-500 hover:text-white flex items-center gap-2 transition-colors"
            >
                <ArrowLeft size={20} />
                <span>Back to Library</span>
            </button>

            {/* Header */}
            <div className="text-center mb-8 mt-12">
                <div className="w-16 h-16 bg-primary/20 rounded-2xl flex items-center justify-center mx-auto mb-4 text-primary shadow-[0_0_20px_rgba(99,102,241,0.3)]">
                    <Server size={32} />
                </div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">Server Setup</h1>
                <p className="text-gray-500 mt-2">Let's get your Minecraft server running.</p>
            </div>

            {/* Step 1: Mode Selection */}
            {step === 1 && (
                <div className="grid grid-cols-2 gap-4 w-full">
                    <button
                        onClick={() => { setMode('install'); setStep(2); }}
                        className="p-6 bg-surface border border-white/5 hover:border-primary/50 hover:bg-surface-hover rounded-2xl text-left group transition-all hover:-translate-y-1"
                    >
                        <div className="w-10 h-10 bg-blue-500/20 rounded-full flex items-center justify-center text-blue-400 mb-3 group-hover:scale-110 transition-transform">
                            <Download size={20} />
                        </div>
                        <h3 className="text-lg font-bold">Install New</h3>
                        <p className="text-sm text-gray-500 mt-1">Download and set up a fresh server.</p>
                    </button>

                    <button
                        onClick={() => { setMode('existing'); setStep(2); }}
                        className="p-6 bg-surface border border-white/5 hover:border-primary/50 hover:bg-surface-hover rounded-2xl text-left group transition-all hover:-translate-y-1"
                    >
                        <div className="w-10 h-10 bg-green-500/20 rounded-full flex items-center justify-center text-green-400 mb-3 group-hover:scale-110 transition-transform">
                            <Folder size={20} />
                        </div>
                        <h3 className="text-lg font-bold">Use Existing</h3>
                        <p className="text-sm text-gray-500 mt-1">Import a server folder you already have.</p>
                    </button>
                </div>
            )}

            {/* Step 2 (Install): Version Selection */}
            {step === 2 && mode === 'install' && (
                <div className="w-full space-y-4 bg-surface p-6 rounded-2xl border border-white/5 shadow-2xl">
                    <h2 className="text-xl font-bold mb-4">Select Server Version</h2>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Server Type</label>
                            <div className="flex gap-2">
                                {['vanilla', 'paper', 'forge', 'fabric'].map(t => (
                                    <button
                                        key={t}
                                        onClick={() => setServerType(t)}
                                        className={`px-4 py-2 rounded-lg border capitalize transition-all ${serverType === t
                                            ? 'bg-primary/20 border-primary text-primary shadow-[0_0_10px_rgba(99,102,241,0.2)]'
                                            : 'bg-black/20 border-white/10 text-gray-400 hover:bg-white/5'
                                            }`}
                                    >
                                        {t}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Game Version</label>
                            <div className="relative">
                                <Select
                                    value={version}
                                    onChange={handleVersionChange}
                                    options={useSelectOptions(versionsList)}
                                    placeholder={versionsList.length === 0 ? "Loading versions..." : "Select Version"}
                                />
                            </div>
                        </div>

                        {/* Java Check Status */}
                        {version && javaStatus && (
                            <div className={`p-4 rounded-xl border ${javaStatus.needs_download ? 'bg-orange-500/10 border-orange-500/30' : 'bg-green-500/10 border-green-500/30'} transition-all`}>
                                <div className="flex items-start justify-between">
                                    <div className="flex gap-3">
                                        <div className={`p-2 rounded-lg ${javaStatus.needs_download ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400'}`}>
                                            <Coffee size={20} />
                                        </div>
                                        <div>
                                            <h4 className={`font-bold ${javaStatus.needs_download ? 'text-orange-400' : 'text-green-400'}`}>
                                                {javaStatus.needs_download ? 'Java Missing or Incompatible' : 'System Ready'}
                                            </h4>
                                            <p className="text-sm text-gray-400 mt-1">{javaStatus.status_message}</p>
                                        </div>
                                    </div>

                                    {javaStatus.needs_download && (
                                        <button
                                            onClick={handleInstallJava}
                                            disabled={installingJava}
                                            className="px-3 py-1.5 bg-orange-500 hover:bg-orange-400 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                                        >
                                            {installingJava ? (
                                                <><Loader2 size={14} className="animate-spin" /> Installing...</>
                                            ) : (
                                                <><Download size={14} /> Install Java</>
                                            )}
                                        </button>
                                    )}
                                </div>

                                {/* Java Progress Bar */}
                                {installingJava && (
                                    <div className="mt-3 pt-3 border-t border-orange-500/20">
                                        <div className="flex justify-between text-xs text-orange-400 mb-1">
                                            <span>{javaProgressMsg || 'Starting download...'}</span>
                                            <span>{Math.round(javaProgress)}%</span>
                                        </div>
                                        <div className="w-full bg-black/30 rounded-full h-1.5 overflow-hidden">
                                            <div
                                                className="h-full bg-orange-500 transition-all duration-300 rounded-full"
                                                style={{ width: `${javaProgress}%` }}
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="flex justify-between pt-4 mt-4 border-t border-white/5">
                        <button onClick={() => setStep(1)} className="text-gray-400 hover:text-white flex items-center gap-1">
                            <ArrowLeft size={16} /> Back
                        </button>
                        <button
                            onClick={() => setStep(3)}
                            disabled={!version}
                            className="px-6 py-2 bg-primary text-white rounded-lg font-bold hover:bg-primary-hover disabled:opacity-50 flex items-center gap-2 transition-all active:scale-95"
                        >
                            Next <ChevronRight size={16} />
                        </button>
                    </div>
                </div>
            )}

            {/* Step 3 (Install): Path */}
            {step === 3 && mode === 'install' && (
                <div className="w-full space-y-4 bg-surface p-6 rounded-2xl border border-white/5 shadow-2xl">
                    <h2 className="text-xl font-bold mb-4">Installation Location</h2>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Parent Directory</label>
                            <input
                                type="text"
                                value={parentPath}
                                onChange={(e) => setParentPath(e.target.value)}
                                className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-white outline-none focus:border-primary/50 font-mono text-sm"
                                placeholder="C:/Games/MinecraftServers"
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Server Folder Name</label>
                            <input
                                type="text"
                                value={folderName}
                                onChange={(e) => setFolderName(e.target.value)}
                                className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-white outline-none focus:border-primary/50"
                            />
                            <p className="text-xs text-gray-500 mt-2">Server will be installed at: <span className="text-gray-300 font-mono">{parentPath}/{folderName}</span></p>
                        </div>
                    </div>

                    <div className="flex justify-between pt-4 mt-4 border-t border-white/5">
                        <button onClick={() => setStep(2)} className="text-gray-400 hover:text-white flex items-center gap-1">
                            <ArrowLeft size={16} /> Back
                        </button>
                        <button
                            onClick={handleInstall}
                            className="px-6 py-2 bg-green-600 text-white rounded-lg font-bold hover:bg-green-500 bg-gradient-to-r from-green-600 to-green-500 shadow-lg hover:shadow-green-500/20 disabled:opacity-50 flex items-center gap-2 transition-all active:scale-95"
                        >
                            Install Server <Check size={18} />
                        </button>
                    </div>
                </div>
            )}

            {/* Step 4 (Install Progress) */}
            {step === 4 && (
                <div className="w-full space-y-6 bg-surface p-8 rounded-2xl border border-white/5 shadow-2xl text-center">
                    <div className="relative w-20 h-20 mx-auto">
                        <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                        <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <Download size={24} className="text-primary" />
                        </div>
                    </div>

                    <div>
                        <h2 className="text-2xl font-bold mb-2">Installing Server</h2>
                        <p className="text-gray-400">{statusMessage}</p>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-black/50 rounded-full h-4 overflow-hidden relative">
                        <div
                            className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-300 ease-out relative"
                            style={{ width: `${progress}%` }}
                        >
                            <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
                        </div>
                    </div>
                    <div className="text-right text-xs text-gray-500 font-mono">{Math.round(progress)}%</div>
                </div>
            )}

            {/* Step 2 (Existing): Path */}
            {step === 2 && mode === 'existing' && (
                <div className="w-full space-y-4 bg-surface p-6 rounded-2xl border border-white/5">
                    <h2 className="text-xl font-bold mb-4">Link Existing Server</h2>
                    <div>
                        <p className="text-xs text-gray-500 mt-2">Paste the absolute path to your server folder.</p>
                        {detectedInfo && (
                            <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-xs font-bold animate-in fade-in">
                                <Check size={12} />
                                Detected: {detectedInfo.type} {detectedInfo.version}
                            </div>
                        )}
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">Server Path</label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={existingPath}
                                onChange={(e) => setExistingPath(e.target.value)}
                                className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-white outline-none focus:border-primary/50 font-mono text-sm"
                                placeholder="C:/Path/To/Server"
                            />
                            <button
                                onClick={async () => {
                                    const path = await api.openDirectoryPicker();
                                    if (path) {
                                        setExistingPath(path);
                                        triggerDetection(path);
                                    }
                                }}
                                className="p-3 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 hover:border-primary/50 transition-colors"
                            >
                                <Folder size={20} className="text-gray-400" />
                            </button>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">Paste the absolute path or select folder.</p>
                    </div>

                    {/* Java Check Status for Existing too */}
                    {version && javaStatus && (
                        <div className={`p-4 rounded-xl border ${javaStatus.needs_download ? 'bg-orange-500/10 border-orange-500/30' : 'bg-green-500/10 border-green-500/30'} transition-all`}>
                            <div className="flex items-start justify-between">
                                <div className="flex gap-3">
                                    <div className={`p-2 rounded-lg ${javaStatus.needs_download ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400'}`}>
                                        <Coffee size={20} />
                                    </div>
                                    <div>
                                        <h4 className={`font-bold ${javaStatus.needs_download ? 'text-orange-400' : 'text-green-400'}`}>
                                            {javaStatus.needs_download ? 'Java Missing or Incompatible' : 'System Ready'}
                                        </h4>
                                        <p className="text-sm text-gray-400 mt-1">{javaStatus.status_message}</p>
                                    </div>
                                </div>

                                {javaStatus.needs_download && (
                                    <button
                                        onClick={handleInstallJava}
                                        disabled={installingJava}
                                        className="px-3 py-1.5 bg-orange-500 hover:bg-orange-400 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                                    >
                                        {installingJava ? (
                                            <><Loader2 size={14} className="animate-spin" /> Installing...</>
                                        ) : (
                                            <><Download size={14} /> Install Java</>
                                        )}
                                    </button>
                                )}
                            </div>
                        </div>
                    )}
                    <div className="flex justify-between pt-4 mt-4 border-t border-white/5">
                        <button onClick={() => setStep(1)} className="text-gray-400 hover:text-white flex items-center gap-1">
                            <ArrowLeft size={16} /> Back
                        </button>
                        <button
                            onClick={handleExisting}
                            className="px-6 py-2 bg-primary text-white rounded-lg font-bold hover:bg-primary-hover shadow-lg hover:shadow-primary/20 transition-all active:scale-95"
                        >
                            Link Server
                        </button>
                    </div>
                </div>
            )}

        </div>
    );
}

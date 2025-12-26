import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';
import { Select, useSelectOptions } from './ui/Select';
import { Check, ChevronRight, Folder, Download, Server, Loader2, ArrowLeft, Coffee, Cpu, Box } from 'lucide-react';

export default function SetupWizard({ onComplete, onCancel }) {
    const [step, setStep] = useState(1);
    const [mode, setMode] = useState('install');

    // Form Data
    const [serverType, setServerType] = useState('vanilla');
    const [version, setVersion] = useState('');
    const [versionsList, setVersionsList] = useState([]);
    const [loadingVersions, setLoadingVersions] = useState(false);

    const [parentPath, setParentPath] = useState('C:/MinecraftServers');
    const [folderName, setFolderName] = useState('my-server');
    const [existingPath, setExistingPath] = useState('');

    const [installing, setInstalling] = useState(false);
    const [progress, setProgress] = useState(0);
    const [statusMessage, setStatusMessage] = useState('Initializing...');
    const ws = useRef(null);
    const completedRef = useRef(false);
    const installedServerId = useRef(null);

    // Java Info (Visual only now)
    const [javaStatus, setJavaStatus] = useState(null);

    // Initial default path check
    useEffect(() => {
        // Try to set a sensible default path based on platform if possible, 
        // otherwise default state handles it.
    }, []);

    // Check Java capability (Just for information)
    const checkJava = async (ver) => {
        if (!ver) return;
        setJavaStatus(null);
        try {
            const status = await api.checkJava(ver);
            setJavaStatus(status);
        } catch (e) { console.error(e); }
    };

    // Load versions
    useEffect(() => {
        if (step === 2 && mode === 'install') {
            setLoadingVersions(true);
            setVersionsList([]);
            setVersion('');

            api.getVersions(serverType).then(data => {
                if (data.versions && data.versions.length > 0) {
                    setVersionsList(data.versions);
                    setVersion(data.versions[0]); // Default to latest
                    checkJava(data.versions[0]);
                }
            }).finally(() => setLoadingVersions(false));
        }
    }, [serverType, step, mode]);

    const handleVersionChange = (ver) => {
        setVersion(ver);
        checkJava(ver);
        // Auto update folder name suggestion
        setFolderName(`${serverType}-${ver}`);
    };

    // WebSocket logic for installation progress
    useEffect(() => {
        if (step === 4 && installing) {
            // Close existing if open
            if (ws.current) ws.current.close();

            ws.current = new WebSocket('ws://127.0.0.1:8000/ws/console');

            ws.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const handle = (d) => {
                        if (d.type === 'progress') {
                            setProgress(d.value);
                            setStatusMessage(d.message);
                            if (d.error) {
                                setStatusMessage(`Error: ${d.error}`);
                                setInstalling(false);
                            }
                            if (d.server_id) installedServerId.current = d.server_id;
                            if (d.value >= 100 && !completedRef.current) {
                                completedRef.current = true;
                                setTimeout(() => onComplete && onComplete(installedServerId.current), 1000);
                            }
                        }
                        // Java progress is now part of the main progress flow from backend
                        if (d.type === 'java_progress') {
                            setStatusMessage(d.message || "Setting up Java...");
                        }
                    };

                    if (data.type === 'batch') data.items.forEach(handle);
                    else handle(data);
                } catch (e) { }
            };

            return () => {
                if (ws.current) ws.current.close();
            };
        }
    }, [step, installing]);

    const handleInstall = async () => {
        setStep(4);
        setInstalling(true);
        setProgress(0);
        setStatusMessage("Starting engine...");

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
        const name = existingPath.split(/[\\/]/).pop() || "Imported Server";
        await api.addServer({
            name: name,
            path: existingPath,
            type: 'unknown',
            version: 'unknown',
            ram_min: "2", ram_max: "4", ram_unit: "G"
        });
        onComplete();
    };

    return (
        <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto animate-in fade-in zoom-in duration-500 relative">

            {/* Header */}
            <div className="text-center mb-8 w-full">
                <button
                    onClick={onCancel}
                    className="absolute top-0 left-0 text-gray-500 hover:text-white flex items-center gap-2 transition-colors p-2 rounded-lg hover:bg-white/5"
                >
                    <ArrowLeft size={20} />
                </button>
                <div className="w-16 h-16 bg-gradient-to-br from-primary/20 to-purple-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4 text-primary shadow-[0_0_20px_rgba(99,102,241,0.2)]">
                    <Server size={32} />
                </div>
                <h1 className="text-3xl font-bold text-white">
                    {step === 4 ? "Installing Server" : "Create Server"}
                </h1>
                <p className="text-gray-500 mt-2">
                    {step === 1 && "Choose how you want to start."}
                    {step === 2 && "Select your software and version."}
                    {step === 3 && "Where should we put the files?"}
                    {step === 4 && "Sit tight, we're building your world."}
                </p>
            </div>

            <AnimatePresence mode="wait">
                {/* STEP 1: MODE */}
                {step === 1 && (
                    <motion.div
                        key="step1"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="grid grid-cols-2 gap-4 w-full"
                    >
                        <button
                            onClick={() => { setMode('install'); setStep(2); }}
                            className="p-6 bg-surface/50 border border-white/10 hover:border-primary/50 hover:bg-surface-hover rounded-2xl text-left group transition-all"
                        >
                            <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center text-blue-400 mb-4 group-hover:scale-110 transition-transform">
                                <Download size={24} />
                            </div>
                            <h3 className="text-lg font-bold text-white">New Installation</h3>
                            <p className="text-sm text-gray-500 mt-1">Download Vanilla, Paper, Forge or Fabric automatically.</p>
                        </button>

                        <button
                            onClick={() => { setMode('existing'); setStep(2); }}
                            className="p-6 bg-surface/50 border border-white/10 hover:border-primary/50 hover:bg-surface-hover rounded-2xl text-left group transition-all"
                        >
                            <div className="w-12 h-12 bg-green-500/10 rounded-xl flex items-center justify-center text-green-400 mb-4 group-hover:scale-110 transition-transform">
                                <Folder size={24} />
                            </div>
                            <h3 className="text-lg font-bold text-white">Import Existing</h3>
                            <p className="text-sm text-gray-500 mt-1">Add a server you already have on your computer.</p>
                        </button>
                    </motion.div>
                )}

                {/* STEP 2: DETAILS */}
                {step === 2 && mode === 'install' && (
                    <motion.div
                        key="step2"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="w-full space-y-6 bg-surface/30 p-8 rounded-3xl border border-white/5"
                    >
                        {/* Server Type Grid */}
                        <div className="grid grid-cols-4 gap-3">
                            {[
                                { id: 'vanilla', label: 'Vanilla', icon: Box },
                                { id: 'paper', label: 'Paper', icon: Cpu },
                                { id: 'forge', label: 'Forge', icon: Server },
                                { id: 'fabric', label: 'Fabric', icon: Box }
                            ].map((type) => (
                                <button
                                    key={type.id}
                                    onClick={() => setServerType(type.id)}
                                    className={`flex flex-col items-center justify-center p-3 rounded-xl border transition-all ${serverType === type.id
                                        ? 'bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(99,102,241,0.15)]'
                                        : 'bg-black/20 border-white/5 text-gray-400 hover:bg-white/5'
                                        }`}
                                >
                                    <type.icon size={20} className="mb-2" />
                                    <span className="text-xs font-bold">{type.label}</span>
                                </button>
                            ))}
                        </div>

                        {/* Version Select */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-400 ml-1">Minecraft Version</label>
                            <Select
                                value={version}
                                onChange={handleVersionChange}
                                options={useSelectOptions(versionsList)}
                                placeholder={loadingVersions ? "Fetching versions..." : "Select Version"}
                                disabled={loadingVersions}
                            />
                        </div>

                        {/* Java Info Box - Non-interactive now, just informative */}
                        {version && javaStatus && (
                            <div className={`p-4 rounded-xl border flex items-center gap-4 ${javaStatus.needs_download
                                ? 'bg-blue-500/10 border-blue-500/20'
                                : 'bg-green-500/10 border-green-500/20'
                                }`}>
                                <div className={`p-2 rounded-lg ${javaStatus.needs_download ? 'bg-blue-500/20 text-blue-400' : 'bg-green-500/20 text-green-400'}`}>
                                    <Coffee size={20} />
                                </div>
                                <div className="flex-1">
                                    <div className="font-bold text-sm text-white">
                                        {javaStatus.needs_download ? `Java ${javaStatus.required_version} Required` : "Java Ready"}
                                    </div>
                                    <div className="text-xs text-gray-400">
                                        {javaStatus.needs_download
                                            ? "We will download and install it automatically for this server."
                                            : "Compatible Java version detected on your system."}
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="flex gap-3">
                            <button
                                onClick={() => setStep(1)}
                                className="px-6 py-4 bg-white/5 hover:bg-white/10 text-white rounded-xl font-bold transition-all"
                            >
                                Back
                            </button>
                            <button
                                onClick={() => setStep(3)}
                                disabled={!version || loadingVersions}
                                className="flex-1 py-4 bg-primary hover:bg-primary-hover text-white rounded-xl font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-primary/20"
                            >
                                Continue <ChevronRight size={18} />
                            </button>
                        </div>
                    </motion.div>
                )}

                {/* STEP 3: FOLDER */}
                {step === 3 && mode === 'install' && (
                    <motion.div
                        key="step3"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="w-full space-y-6 bg-surface/30 p-8 rounded-3xl border border-white/5"
                    >
                        <div className="space-y-4">
                            <div>
                                <label className="text-sm font-medium text-gray-400 ml-1">Installation Folder</label>
                                <div className="flex gap-2 mt-1">
                                    <input
                                        type="text"
                                        value={parentPath}
                                        onChange={(e) => setParentPath(e.target.value)}
                                        className="flex-1 bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-primary outline-none transition-colors font-mono text-sm"
                                    />
                                    <button
                                        onClick={async () => {
                                            const path = await api.openDirectoryPicker();
                                            if (path) setParentPath(path);
                                        }}
                                        className="p-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors"
                                    >
                                        <Folder size={20} className="text-gray-400" />
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="text-sm font-medium text-gray-400 ml-1">Server Name (Folder)</label>
                                <input
                                    type="text"
                                    value={folderName}
                                    onChange={(e) => setFolderName(e.target.value)}
                                    className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-primary outline-none transition-colors font-medium mt-1"
                                />
                            </div>
                        </div>

                        <div className="pt-2">
                            <button
                                onClick={handleInstall}
                                className="w-full py-4 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg hover:shadow-green-500/20"
                            >
                                <Download size={20} />
                                Install Server
                            </button>
                            <button
                                onClick={() => setStep(2)}
                                className="w-full mt-3 py-2 text-gray-500 hover:text-white text-sm font-medium transition-colors text-center"
                            >
                                Back
                            </button>
                        </div>
                    </motion.div>
                )}

                {/* STEP 4: INSTALLING */}
                {step === 4 && (
                    <motion.div
                        key="step4"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="w-full space-y-8 text-center"
                    >
                        <div className="relative mx-auto w-32 h-32">
                            <svg className="w-full h-full transform -rotate-90">
                                <circle
                                    cx="64" cy="64" r="60"
                                    stroke="currentColor" strokeWidth="8" fill="transparent"
                                    className="text-white/5"
                                />
                                <circle
                                    cx="64" cy="64" r="60"
                                    stroke="currentColor" strokeWidth="8" fill="transparent"
                                    strokeDasharray={377}
                                    strokeDashoffset={377 - (377 * progress) / 100}
                                    className="text-primary transition-all duration-500 ease-out"
                                    strokeLinecap="round"
                                />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center flex-col">
                                <span className="text-3xl font-bold text-white">{Math.round(progress)}%</span>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <h3 className="text-xl font-bold text-white animate-pulse">Installing...</h3>
                            <p className="text-gray-400 max-w-xs mx-auto break-words text-sm h-10">{statusMessage}</p>
                        </div>
                    </motion.div>
                )}

                {/* Existing Server Mode */}
                {step === 2 && mode === 'existing' && (
                    <motion.div className="w-full space-y-4 bg-surface/30 p-8 rounded-3xl border border-white/5">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-400 ml-1">Server Path</label>
                            <div className="flex gap-2 mt-1">
                                <input
                                    type="text"
                                    value={existingPath}
                                    onChange={(e) => setExistingPath(e.target.value)}
                                    placeholder="C:/Path/To/Server"
                                    className="flex-1 bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-primary outline-none transition-colors font-mono text-sm"
                                />
                                <button
                                    onClick={async () => {
                                        const path = await api.openDirectoryPicker();
                                        if (path) setExistingPath(path);
                                    }}
                                    className="p-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 hover:border-primary/50 transition-colors"
                                >
                                    <Folder size={20} className="text-gray-400" />
                                </button>
                            </div>
                        </div>
                        <div className="flex gap-3 mt-4">
                            <button
                                onClick={() => setStep(1)}
                                className="px-6 py-4 bg-white/5 hover:bg-white/10 text-white rounded-xl font-bold transition-all"
                            >
                                Back
                            </button>
                            <button
                                onClick={handleExisting}
                                className="flex-1 py-4 bg-primary hover:bg-primary-hover text-white rounded-xl font-bold shadow-lg hover:shadow-primary/20 transition-all"
                            >
                                Import Server
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

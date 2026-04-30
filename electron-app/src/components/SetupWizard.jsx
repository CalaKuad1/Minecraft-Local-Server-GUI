import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';
import { Select, useSelectOptions } from './ui/Select';
import { Check, ChevronRight, Folder, Download, Server, Loader2, ArrowLeft, ArrowRight, Cpu, Box, HardDrive, Terminal, Monitor } from './ui/PixelIcons';
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
                'bg-black/20 border-white/5 text-gray-500'
            }`}>
                {completed ? <Check size={14} /> : icon}
            </div>
            <span className={`text-[10px] uppercase tracking-widest font-minecraft ${active ? 'text-white' : 'text-gray-600'}`}>{label}</span>
        </div>
    );
}

export default function SetupWizard({ onComplete, onCancel }) {
    const [step, setStep] = useState(1);
    const [mode, setMode] = useState('install');

    // Engine Data
    const [serverType, setServerType] = useState('vanilla');
    const [version, setVersion] = useState('');
    const [versionsList, setVersionsList] = useState([]);
    const [loadingVersions, setLoadingVersions] = useState(false);
    const [loaderVersionsList, setLoaderVersionsList] = useState([]);
    const [loaderVersion, setLoaderVersion] = useState('');
    const [allVersionData, setAllVersionData] = useState(null);

    // Configuration Data
    const [parentPath, setParentPath] = useState('C:/MinecraftServers');
    const [folderName, setFolderName] = useState('my-server');
    const [existingPath, setExistingPath] = useState('');
    
    // RAM config
    const [ramPreset, setRamPreset] = useState("4"); // Default 4GB
    const [eulaAccepted, setEulaAccepted] = useState(false);

    // Java status
    const [javaStatus, setJavaStatus] = useState(null);
    const [javaLoading, setJavaLoading] = useState(false);

    // Install State
    const [installing, setInstalling] = useState(false);
    const [progress, setProgress] = useState(0);
    const [statusMessage, setStatusMessage] = useState('Initializing deployment...');
    const ws = useRef(null);
    const completedRef = useRef(false);
    const installedServerId = useRef(null);

    // Load versions when step 2 is active
    useEffect(() => {
        if (step === 2 && mode === 'install') {
            setLoadingVersions(true);
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
                }
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
            ws.current = new WebSocket('ws://127.0.0.1:8000/ws/console');

            const handleData = (d) => {
                if (d.type === 'progress') {
                    setProgress(d.value);
                    setStatusMessage(d.message);
                    if (d.error) {
                        setStatusMessage(`Deployment Failed: ${d.error}`);
                        setInstalling(false);
                    }
                    if (d.server_id) installedServerId.current = d.server_id;
                    if (d.value >= 100 && !completedRef.current) {
                        completedRef.current = true;
                        setTimeout(() => onComplete && onComplete(installedServerId.current), 1500);
                    }
                }
                if (d.type === 'java_progress') {
                    setStatusMessage(d.message || "Resolving dependencies...");
                }
            };

            ws.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'batch') data.items.forEach(handleData);
                    else handleData(data);
                } catch (e) { }
            };

            const intervalId = setInterval(async () => {
                if (completedRef.current) return;
                try {
                    const data = await api.getInstallProgress();
                    if (data && typeof data.value === 'number') {
                        setProgress(prev => Math.max(prev, data.value));
                        if (data.message) setStatusMessage(data.message);
                        if (data.error) {
                            setStatusMessage(`Deployment Failed: ${data.error}`);
                            setInstalling(false);
                            clearInterval(intervalId);
                        }
                    }
                } catch (e) { }
            }, 1000);

            return () => {
                if (ws.current) ws.current.close();
                clearInterval(intervalId);
            };
        }
    }, [step, installing, onComplete]);

    const handleDeploy = async () => {
        setInstalling(true);
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
            setStatusMessage(`Error: ${err.message}`);
            setInstalling(false);
        }
    };

    const handleImport = async () => {
        if (!existingPath) return;
        try {
            const result = await api.importServer(existingPath);
            if (result && result.id) {
                onComplete(result.id);
            }
        } catch (err) {
            console.error("Import failed", err);
        }
    };

    return (
        <div className="flex flex-col h-full w-full bg-transparent animate-in fade-in duration-500 relative">
            
            {/* Main Wizard Container */}
            <div className="w-full flex-1 flex overflow-hidden">
                
                {/* Sidebar */}
                <div className="w-64 bg-[#0a0a0a]/80 border-r border-white/10 flex flex-col backdrop-blur-xl shadow-2xl z-10 flex-shrink-0">
                    <div className="p-8">
                        <div className="flex items-center gap-3 text-emerald-400 mb-10">
                            <Terminal size={20} />
                            <span className="font-minecraft text-lg tracking-wide uppercase">Setup</span>
                        </div>
                        
                        <div className="space-y-6">
                            <StepItem icon={<Box size={14} />} label="Mode" active={step === 1} completed={step > 1} />
                            <StepItem icon={<Cpu size={14} />} label="Engine" active={step === 2} completed={step > 2} />
                            <StepItem icon={<HardDrive size={14} />} label="Config" active={step === 3} completed={step > 3} />
                            <StepItem icon={<Terminal size={14} />} label="Status" active={step === 4} />
                        </div>
                    </div>

                    <div className="mt-auto p-8 border-t border-white/5 opacity-40">
                        <div className="flex items-center gap-3">
                            <Monitor size={14} className="text-gray-400" />
                            <div className="text-[9px] uppercase tracking-widest font-minecraft text-gray-500">Provisioning</div>
                        </div>
                    </div>
                </div>

                {/* Content Area */}
                <div className="flex-1 flex flex-col relative overflow-hidden bg-[#050505]/70 backdrop-blur-md">
                    <AnimatePresence mode="wait">
                        
                        {/* STEP 1: PROJECT TYPE */}
                        {step === 1 && (
                            <motion.div
                                key="step1"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 justify-center max-w-3xl"
                            >
                                <h2 className="text-xl font-minecraft tracking-widest text-emerald-400 mb-1 uppercase text-left">Deploy Server</h2>
                                <p className="text-gray-500 text-xs mb-8 tracking-wide">Choose deployment architecture.</p>

                                <div className="grid grid-cols-2 gap-4">
                                    <button
                                        onClick={() => { setMode('install'); setStep(2); }}
                                        className="p-6 bg-black/40 border border-white/5 hover:border-white/20 rounded-sm text-left transition-all group"
                                    >
                                        <Download size={24} className="text-emerald-500/60 mb-4" />
                                        <h3 className="text-xs font-minecraft tracking-widest text-white mb-2 uppercase">New Profile</h3>
                                        <p className="text-[10px] text-gray-500 leading-relaxed">Install a fresh Minecraft server engine.</p>
                                    </button>

                                    <button
                                        onClick={() => { setMode('existing'); setStep(3); }}
                                        className="p-6 bg-black/40 border border-white/5 hover:border-white/20 rounded-sm text-left transition-all group"
                                    >
                                        <Folder size={24} className="text-emerald-500/60 mb-4" />
                                        <h3 className="text-xs font-minecraft tracking-widest text-white mb-2 uppercase">Import local</h3>
                                        <p className="text-[10px] text-gray-500 leading-relaxed">Link an existing server folder.</p>
                                    </button>
                                </div>
                                
                                <div className="mt-12 flex justify-start">
                                    <button onClick={onCancel} className="text-[10px] font-minecraft uppercase tracking-widest text-gray-600 hover:text-white transition-colors flex items-center gap-2">
                                        <ArrowLeft size={12} /> Exit setup
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* STEP 2: ENGINE SELECTION */}
                        {step === 2 && mode === 'install' && (
                            <motion.div
                                key="step2"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 max-w-4xl"
                            >
                                <h2 className="text-xl font-minecraft tracking-widest text-emerald-400 mb-1 uppercase">Configure Engine</h2>
                                <p className="text-gray-500 text-xs mb-10 tracking-wide">Select framework and target version.</p>

                                <div className="space-y-8">
                                    <div>
                                        <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-3 block">Framework</label>
                                        <div className="grid grid-cols-5 gap-3">
                                            {['vanilla', 'paper', 'forge', 'neoforge', 'fabric'].map((type) => (
                                                <button
                                                    key={type}
                                                    onClick={() => setServerType(type)}
                                                    className={`py-4 px-2 flex flex-col items-center justify-center rounded-sm border transition-all gap-3 ${
                                                        serverType === type 
                                                            ? 'bg-emerald-500/5 border-emerald-500/40 text-emerald-400' 
                                                            : 'bg-black/30 border-white/5 text-gray-500 hover:border-white/10'
                                                    }`}
                                                >
                                                    <EngineIcon 
                                                        type={type} 
                                                        size={24} 
                                                        className={`transition-opacity ${serverType === type ? "opacity-100" : "opacity-30"}`} 
                                                    />
                                                    <span className={`capitalize text-[10px] font-minecraft tracking-widest ${serverType === type ? "text-emerald-400" : "text-gray-600"}`}>{type}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div>
                                        <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-3 block">Minecraft Version</label>
                                        <div className="max-w-xs">
                                            <Select
                                                value={version}
                                                onChange={handleVersionChange}
                                                options={useSelectOptions(versionsList)}
                                                placeholder={loadingVersions ? "Loading..." : "Select version"}
                                                disabled={loadingVersions}
                                                className="bg-black/30 border-white/5 rounded-sm h-10 text-[11px] font-minecraft tracking-widest"
                                            />
                                        </div>
                                    </div>

                                    {(serverType === 'forge' || serverType === 'neoforge') && version && (
                                        <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                                            <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-3 block">
                                                {serverType === 'forge' ? 'Forge' : 'NeoForge'} Version
                                            </label>
                                            <div className="max-w-xs">
                                                <Select
                                                    value={loaderVersion}
                                                    onChange={setLoaderVersion}
                                                    options={useSelectOptions(loaderVersionsList)}
                                                    placeholder="Select loader version"
                                                    className="bg-black/30 border-white/5 rounded-sm h-10 text-[11px] font-minecraft tracking-widest"
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>

                                <div className="mt-auto flex gap-4 pt-10 border-t border-white/5">
                                    <button onClick={() => setStep(1)} className="text-[10px] font-minecraft uppercase tracking-widest text-gray-600 hover:text-white transition-colors">Back</button>
                                    <button 
                                        onClick={() => setStep(3)} 
                                        disabled={!version || loadingVersions}
                                        className="ml-auto px-6 py-2.5 bg-white text-black rounded-sm text-[10px] font-minecraft uppercase tracking-widest transition-colors hover:bg-gray-200 disabled:opacity-30 flex items-center gap-2"
                                    >
                                        Next <ArrowRight size={14} />
                                    </button>
                                </div>
                            </motion.div>
                        )}
                        
                        {/* STEP 3: CONFIGURATION (INSTALL) */}
                        {step === 3 && mode === 'install' && (
                            <motion.div
                                key="step3"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 max-w-4xl"
                            >
                                <h2 className="text-xl font-minecraft tracking-widest text-emerald-400 mb-1 uppercase">Parameters</h2>
                                <p className="text-gray-500 text-xs mb-10 tracking-wide">Environment details.</p>

                                <div className="space-y-6">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-2 block">Name</label>
                                            <input
                                                type="text"
                                                value={folderName}
                                                onChange={(e) => setFolderName(e.target.value)}
                                                className="w-full bg-black/40 border border-white/5 rounded-sm px-3 py-2 text-[11px] text-white focus:border-emerald-500/40 outline-none font-minecraft tracking-wider"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-2 block">Directory</label>
                                            <div className="flex gap-2">
                                                <input
                                                    type="text"
                                                    value={parentPath}
                                                    onChange={(e) => setParentPath(e.target.value)}
                                                    className="flex-1 bg-black/40 border border-white/5 rounded-sm px-3 py-2 text-[10px] text-gray-400 font-mono outline-none truncate"
                                                />
                                                <button onClick={async () => {
                                                    const path = await api.openDirectoryPicker();
                                                    if (path) setParentPath(path);
                                                }} className="px-3 bg-black/40 border border-white/5 hover:border-white/20 rounded-sm transition-colors">
                                                    <Folder size={14} className="text-gray-500" />
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    <div>
                                        <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-3 block">RAM Allocation</label>
                                        <div className="grid grid-cols-3 gap-3">
                                            {[
                                                { val: "2", label: "2 GB" },
                                                { val: "4", label: "4 GB" },
                                                { val: "8", label: "8 GB" }
                                            ].map((opt) => (
                                                <button
                                                    key={opt.val}
                                                    onClick={() => setRamPreset(opt.val)}
                                                    className={`p-3 text-center border rounded-sm transition-all ${
                                                        ramPreset === opt.val 
                                                            ? 'border-emerald-500/40 bg-emerald-500/5 text-emerald-400' 
                                                            : 'border-white/5 bg-black/20 text-gray-600 hover:border-white/10'
                                                    }`}
                                                >
                                                    <div className="text-[10px] font-minecraft uppercase tracking-widest">{opt.label}</div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="pt-4 border-t border-white/5">
                                        <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-3 block">Java Runtime</label>
                                        {javaLoading ? (
                                            <div className="text-[10px] text-gray-600 font-minecraft uppercase tracking-widest flex items-center gap-2">
                                                <Loader2 size={12} className="animate-spin" /> Checking...
                                            </div>
                                        ) : javaStatus ? (
                                            <div className={`p-3 rounded-sm border ${
                                                javaStatus.status_color === 'green' ? 'bg-emerald-500/5 border-emerald-500/20' :
                                                javaStatus.status_color === 'orange' ? 'bg-yellow-500/5 border-yellow-500/20' :
                                                'bg-red-500/5 border-red-500/20'
                                            }`}>
                                                <div className={`text-[10px] font-minecraft uppercase tracking-widest ${
                                                    javaStatus.status_color === 'green' ? 'text-emerald-400' :
                                                    javaStatus.status_color === 'orange' ? 'text-yellow-400' :
                                                    'text-red-400'
                                                }`}>
                                                    {javaStatus.status_color === 'green' ? 'Ready' : javaStatus.status_color === 'orange' ? 'Update Needed' : 'Missing'}
                                                </div>
                                                <div className="text-[10px] text-gray-500 mt-1">
                                                    Requires Java {javaStatus.required_version} — {
                                                        javaStatus.local_java_available ? 'Already installed' :
                        javaStatus.system_java ? `System has Java ${javaStatus.system_java[0]}` :
                        'Will be downloaded during setup'
                                                    }
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-[10px] text-gray-600 font-minecraft">Java {version ? 'check unavailable' : 'not selected'}</div>
                                        )}
                                    </div>

                                    <div className="pt-4 border-t border-white/5">
                                        <label className="flex items-center gap-3 cursor-pointer group">
                                            <div className={`w-4 h-4 rounded-sm flex items-center justify-center border transition-all ${eulaAccepted ? 'bg-emerald-500 border-emerald-500' : 'bg-black/40 border-white/5 group-hover:border-white/20'}`}>
                                                {eulaAccepted && <Check size={12} className="text-black" />}
                                            </div>
                                            <input type="checkbox" className="hidden" checked={eulaAccepted} onChange={(e) => setEulaAccepted(e.target.checked)} />
                                            <span className="text-[10px] text-gray-500 group-hover:text-gray-400 select-none uppercase tracking-widest font-minecraft transition-colors">Accept Minecraft EULA</span>
                                        </label>
                                    </div>
                                </div>

                                <div className="mt-auto flex gap-4 pt-10 border-t border-white/5">
                                    <button onClick={() => setStep(2)} className="text-[10px] font-minecraft uppercase tracking-widest text-gray-600 hover:text-white transition-colors">Back</button>
                                    <button 
                                        onClick={handleDeploy} 
                                        disabled={!eulaAccepted}
                                        className="ml-auto px-6 py-2.5 bg-emerald-500 text-black rounded-sm text-[10px] font-minecraft uppercase tracking-widest transition-all hover:bg-emerald-400 disabled:opacity-30"
                                    >
                                        {javaStatus && !javaStatus.local_java_available && javaStatus.needs_download ? 'Download & Deploy' : 'Deploy'}
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* STEP 3: CONFIGURATION (IMPORT) */}
                        {step === 3 && mode === 'existing' && (
                            <motion.div
                                key="step3_existing"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
                                className="flex-1 flex flex-col p-10 max-w-4xl justify-center"
                            >
                                <h2 className="text-xl font-minecraft tracking-widest text-emerald-400 mb-1 uppercase text-left">Mount Repository</h2>
                                <p className="text-gray-500 text-xs mb-8 tracking-wide">Import existing server files.</p>

                                <div className="space-y-4">
                                    <label className="text-[9px] font-minecraft text-gray-600 uppercase tracking-widest mb-2 block">Source Path</label>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={existingPath}
                                            onChange={(e) => setExistingPath(e.target.value)}
                                            placeholder="/path/to/server"
                                            className="flex-1 bg-black/40 border border-white/5 rounded-sm px-3 py-2 text-[10px] text-white font-mono outline-none focus:border-emerald-500/40"
                                        />
                                        <button onClick={async () => {
                                            const path = await api.openDirectoryPicker();
                                            if (path) setExistingPath(path);
                                        }} className="px-3 bg-black/40 border border-white/5 hover:border-white/20 rounded-sm transition-colors flex items-center justify-center">
                                            <Folder size={16} className="text-emerald-500/60" />
                                        </button>
                                    </div>
                                </div>

                                <div className="mt-12 flex gap-4">
                                    <button onClick={() => setStep(1)} className="text-[10px] font-minecraft uppercase tracking-widest text-gray-600 hover:text-white transition-colors">Back</button>
                                    <button 
                                        onClick={handleImport} 
                                        disabled={!existingPath}
                                        className="ml-auto px-6 py-2.5 bg-emerald-500 text-black rounded-sm text-[10px] font-minecraft uppercase tracking-widest transition-all hover:bg-emerald-400 disabled:opacity-30"
                                    >
                                        Link Project
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* STEP 4: DEPLOYING */}
                        {step === 4 && (
                            <motion.div
                                key="step4"
                                initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
                                className="flex-1 flex flex-col items-center justify-center p-10 text-center"
                            >
                                <div className="w-12 h-12 rounded-sm bg-black border border-white/10 flex items-center justify-center mb-6 shadow-xl relative overflow-hidden">
                                    <div className="absolute inset-0 bg-emerald-500/5 animate-pulse" />
                                    <Terminal size={20} className="text-emerald-400 relative z-10" />
                                </div>
                                <h3 className="text-sm font-minecraft tracking-widest text-white mb-2 uppercase">Deploying...</h3>
                                <p className="text-gray-500 text-[10px] h-4 font-mono truncate max-w-xs mb-8">{statusMessage}</p>

                                <div className="w-64 max-w-full bg-black/40 rounded-sm h-1 overflow-hidden border border-white/5">
                                    <motion.div 
                                        className="h-full bg-emerald-500"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${progress}%` }}
                                        transition={{ ease: "easeOut" }}
                                    />
                                </div>
                                <div className="mt-3 text-[9px] font-minecraft text-emerald-500/40 uppercase tracking-widest">{Math.round(progress)}%</div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
}

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { LayoutDashboard, Terminal, Settings as SettingsIcon, Users, Activity, Globe, Github, Package, Plug } from './components/ui/PixelIcons';
import { api } from './api';
import { useTranslation } from './contexts/LanguageContext';

import logo from './assets/logo-minimal.png';

// Effects
import AbstractBackground from './components/effects/AbstractBackground';
import NoiseGrain from './components/effects/NoiseGrain';
import MagneticButton from './components/effects/MagneticButton';

// Components
import Dashboard from './components/Dashboard';
import Console from './components/Console';
import SetupWizard from './components/SetupWizard';

import Players from './components/Players';
import AppSettings from './components/AppSettings';
import Worlds from './components/Worlds';
import Mods from './components/Mods';
import Plugins from './components/Plugins';

import ServerSelector from './components/ServerSelector';
import TitleBar from './components/TitleBar';
import Settings from './components/Settings';

// Sidebar component
function Sidebar({ activeTab, setActiveTab, onBack, onOpenAppSettings }) {
  const { t } = useTranslation();
  const menuItems = [
    { id: 'dashboard', Icon: LayoutDashboard, label: t('nav.dashboard') },
    { id: 'console', Icon: Terminal, label: t('nav.console') },
    { id: 'players', Icon: Users, label: t('nav.players') },
    { id: 'worlds', Icon: Globe, label: t('nav.worlds') },
    { id: 'mods', Icon: Package, label: t('nav.mods') },
    { id: 'plugins', Icon: Plug, label: t('nav.plugins') },
    { id: 'settings', Icon: SettingsIcon, label: t('nav.settings') },
  ];

  return (
    <div className="w-64 bg-[#0a0a0a]/80 backdrop-blur-xl flex flex-col z-10 relative border-r border-white/10 drag-region overflow-hidden shadow-2xl">
      {/* App Drag Region (Titlebar offset) */}
      <div className="h-4 w-full bg-transparent" style={{ WebkitAppRegion: 'drag' }}></div>
      <div className="p-6 flex justify-center mb-2">
        <img src={logo} alt="Server Manager" className="w-full max-h-16 object-contain opacity-90 drop-shadow-[0_0_15px_rgba(16,185,129,0.15)]" />
      </div>
      <div className="px-4 mb-2 mt-2">
        <button onClick={onBack} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-sm text-xs font-minecraft tracking-wider uppercase text-zinc-500 hover:text-white hover:bg-white/5 transition-colors border border-transparent">
          <span>&lt; {t('nav.back_to_library')}</span>
        </button>
      </div>
      <nav className="flex-1 px-4 space-y-1 mt-2 relative">
        {menuItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button key={item.id} onClick={() => setActiveTab(item.id)} className={`w-full flex items-center gap-4 px-4 py-3 rounded-md transition-all duration-200 group border-l-2 ${isActive ? 'bg-white/10 border-emerald-400 shadow-sm' : 'border-transparent text-gray-400 hover:bg-white/5 hover:border-white/20'}`}>
              <item.Icon size={18} className={`${isActive ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]' : 'text-zinc-500 group-hover:text-white transition-colors duration-200'}`} />
              <span className={`font-minecraft text-lg tracking-wider mt-0.5 uppercase ${isActive ? 'text-white' : 'text-zinc-500 group-hover:text-white transition-colors duration-200'}`}>{item.label}</span>
              {isActive && (
                 <div className="ml-auto w-1.5 h-1.5 rounded-sm bg-emerald-400 shadow-[0_0_8px_currentColor]" />
              )}
            </button>
          );
        })}
      </nav>
      <div className="p-4 border-t border-white/5 mt-auto">
        <div className="flex items-center gap-3 px-4 py-3 rounded-md bg-black/40 border border-white/5 text-sm text-gray-400">
          <Activity size={16} className="text-emerald-500 animate-pulse" />
          <span className="font-minecraft text-sm tracking-widest mt-0.5 text-zinc-400">{t('status.system_online')}</span>
        </div>
      </div>
      <div className="px-6 pb-6 pt-2 flex items-center justify-between">
        <div className="text-xs text-zinc-500 font-minecraft uppercase tracking-wider">
          <span>{t('common.made_by')} <span className="text-white">CalaKuad1</span></span>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={onOpenAppSettings} 
            className="p-2 hover:bg-white/10 rounded-sm transition-colors text-zinc-500 hover:text-white"
            title={t('settings.title')}
          >
            <SettingsIcon size={16} />
          </button>
          <a href="https://github.com/CalaKuad1" target="_blank" rel="noreferrer" className="p-2 hover:bg-white/10 rounded-sm transition-colors text-zinc-500 hover:text-white" title="View on GitHub"><Github size={16} /></a>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedServer, setSelectedServer] = useState(null);
  const [serverStatus, setServerStatus] = useState(null);
  const [showWizard, setShowWizard] = useState(false);
  const [showAppSettings, setShowAppSettings] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const { t, locale } = useTranslation();

  useEffect(() => {
    if (window.electron && window.electron.onCloseRequested) {
      window.electron.onCloseRequested(() => {
        setIsStopping(true);
      });
    }
  }, []);

  const isSameStatus = useCallback((a, b) => {
    if (!a || !b) return false;
    return (
      a.status === b.status &&
      a.pid === b.pid &&
      a.players === b.players &&
      a.cpu === b.cpu &&
      a.ram === b.ram
    );
  }, []);

  const triggerRefresh = useCallback(async () => {
    try {
      const status = await api.getStatus();
      setServerStatus(status);
    } catch (e) { }
  }, []);

  useEffect(() => {
    if (selectedServer) {
      let cancelled = false;
      let timer = null;

      const tick = async () => {
        if (cancelled) return;
        try {
          const status = await api.getStatus();
          if (!cancelled) {
            setServerStatus((prev) => {
              if (!prev) return status;
              const PRIORITY = { offline: 0, starting: 1, stopping: 2, online: 3 };
              const prevP = PRIORITY[prev.status] ?? 0;
              const newP = PRIORITY[status.status] ?? 0;

              if (prev.status === 'online' && status.status === 'starting' && prev.pid === status.pid) {
                return prev;
              }
              if (prev.status === 'online' && status.status === 'offline') {
                if (status.pid && prev.pid && status.pid === prev.pid) return prev;
              }
              if (prev.status === 'stopping' && status.status !== 'offline') {
                return prev;
              }

              return isSameStatus(prev, status) ? prev : status;
            });
          }
          // Aumentar el tiempo de polling a 3000ms (3s) para reducir carga en PCs lentos
          timer = setTimeout(tick, 3000);
        } catch (e) {
          timer = setTimeout(tick, 5000); // Si falla, esperar más
        }
      };

      tick();
      return () => {
        cancelled = true;
        if (timer) clearTimeout(timer);
      };
    }
  }, [selectedServer]);

  const handleServerSelected = useCallback(async (serverId = null) => {
    if (!serverId) {
      // If no ID provided, we just want to refresh or load default
      try {
        const servers = await api.getServers();
        if (servers && servers.length > 0) {
          serverId = servers[servers.length - 1].id;
        }
      } catch (e) { return; }
    }

    if (!serverId) return;

    // 1. Limpieza visual inmediata antes de la carga (solo si es un cambio de servidor)
    if (selectedServer?.id !== serverId) {
      setSelectedServer(null);
      setServerStatus(null);
    }

    try {
      // Ahora selectServer devuelve el estado actual también, aprovechémoslo
      const response = await api.selectServer(serverId);

      // Actualización atómica
      if (response.server_status) {
        setServerStatus(response.server_status);
        setSelectedServer(response.server_status); // Trigger UI render
      } else {
        const status = await api.getStatus();
        setServerStatus(status);
        setSelectedServer(status);
      }
    } catch (e) {
      setSelectedServer({ id: serverId }); // Fallback
    }
    setActiveTab('dashboard');
  }, []);

  const handleBackToLibrary = async () => {
    setSelectedServer(null);
    setServerStatus(null);
  };

  if (isStopping) {
    return (
      <div className="h-screen w-screen bg-black/90 flex flex-col items-center justify-center text-white z-[9999] fixed inset-0 font-sans">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary mb-6"></div>
        <h2 className="text-3xl font-minecraft mb-2">{t('status.stopping')}</h2>
        <p className="text-gray-400">Saving world and closing gracefully...</p>
      </div>
    );
  }

  if (showWizard) {
    return (
      <div className="h-screen w-screen bg-transparent text-white overflow-hidden flex flex-col pt-8 relative">
        <AbstractBackground />
        <NoiseGrain />
        <TitleBar />
        <div className="flex-1 overflow-y-auto relative z-10">
          <SetupWizard onComplete={(serverId) => { setShowWizard(false); handleServerSelected(serverId); }} onCancel={() => setShowWizard(false)} />
        </div>
      </div>
    );
  }

  if (!selectedServer) {
    return (
      <div className="h-screen w-screen bg-transparent overflow-hidden flex flex-col relative">
        <AbstractBackground />
        <NoiseGrain />
        <TitleBar />
        <div className="flex-1 w-full flex overflow-hidden relative z-10 pt-8" style={{ display: 'flex' }}>
          <ServerSelector onSelect={handleServerSelected} onAdd={() => setShowWizard(true)} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-transparent font-sans text-white overflow-hidden relative">
      <AbstractBackground />
      <NoiseGrain />
      
      <TitleBar />
      
      <div className="w-full flex h-full pt-8 relative z-10">
        <Sidebar 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          onBack={handleBackToLibrary} 
          onOpenAppSettings={() => setShowAppSettings(true)} 
        />
        
        <main className="flex-1 overflow-hidden relative flex flex-col bg-[#050505]/70 backdrop-blur-md w-full">
          <div className="flex-1 overflow-y-auto p-8 relative z-10 flex flex-col scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent w-full">
          <div className="mx-auto w-full flex-1 flex flex-col">
            <AnimatePresence mode="wait">
                <motion.div
                key={`${activeTab}-${selectedServer?.id}`}
                initial={{ opacity: 0, scale: 0.99, y: 10, filter: 'blur(4px)' }}
                animate={{ opacity: 1, scale: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, scale: 0.99, y: -10, filter: 'blur(4px)' }}
                transition={{ duration: 0.25, ease: "easeOut" }}
                className={activeTab === 'dashboard' ? 'flex-1 flex flex-col' : ''}
                 style={activeTab === 'console' ? { display: 'none' } : undefined}
               >
                 {activeTab === 'dashboard' && <Dashboard status={serverStatus} onRefresh={triggerRefresh} />}
                 {activeTab === 'players' && <Players status={serverStatus} />}
                 {activeTab === 'worlds' && <Worlds />}
                 {activeTab === 'mods' && <Mods status={serverStatus} onOpenWizard={() => setShowWizard(true)} />}
                 {activeTab === 'plugins' && <Plugins status={serverStatus} />}
                 {activeTab === 'settings' && <Settings />}
               </motion.div>
             </AnimatePresence>

             <AnimatePresence>
               {showAppSettings && (
                 <AppSettings isOpen={true} onClose={() => setShowAppSettings(false)} />
               )}
             </AnimatePresence>

             {activeTab === 'console' && (
               <Console key={selectedServer?.id} />
             )}
          </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;

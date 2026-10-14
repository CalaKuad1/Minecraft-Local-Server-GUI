import React, { useState, useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { LayoutDashboard, Terminal, Settings as SettingsIcon, Users, Globe, Github, Package, Plug, ArrowLeft } from './components/ui/PixelIcons';
import Cubi from './components/ui/Cubi';
import { api } from './api';
import { useTranslation } from './contexts/LanguageContext';

import { APP_NAME } from './brand';

// Effects
import AbstractBackground from './components/effects/AbstractBackground';
import NoiseGrain from './components/effects/NoiseGrain';

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

// Cubi's mood follows the server: asleep when off, hopping while it starts,
// cheering when friends can join.
const moodFor = (status) => ({
  online: 'happy', starting: 'busy', stopping: 'busy', offline: 'sleep',
}[status] || 'idle');

// Sidebar component
function Sidebar({ activeTab, setActiveTab, onBack, onOpenAppSettings, status }) {
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
  const state = status?.status || 'offline';
  const tone = state === 'online' ? 'text-mint bg-grass/10 border-grass/25'
    : (state === 'starting' || state === 'stopping') ? 'text-gold bg-gold/10 border-gold/25'
      : 'text-ink-faint bg-white/5 border-white/10';

  return (
    <div className="w-60 shrink-0 bg-panel/70 backdrop-blur-xl flex flex-col z-10 relative border-r border-line overflow-hidden">
      <div className="px-4 pt-5">
        <button onClick={onBack} className="flex items-center gap-1.5 rounded-sm px-2 py-1.5 text-sm text-ink-faint hover:text-ink hover:bg-white/5 transition-colors">
          <ArrowLeft size={15} />
          <span>{t('nav.back_to_library')}</span>
        </button>
      </div>
      <div className="flex flex-col items-center px-4 pt-3 pb-5">
        <Cubi mood={moodFor(state)} size={72} />
        <div className="mt-2 max-w-full truncate font-display text-lg font-semibold text-ink" title={status?.name || undefined}>
          {status?.name || APP_NAME}
        </div>
        <span className={`mt-1.5 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>
          <span className={`h-1.5 w-1.5 rounded-full bg-current ${state === 'starting' || state === 'stopping' ? 'animate-pulse' : ''}`} />
          {t(`status.${state}`)}
        </span>
      </div>
      <nav className="flex-1 px-3 space-y-0.5">
        {menuItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              aria-current={isActive ? 'page' : undefined}
              className={`relative w-full flex items-center gap-3 rounded-md px-3 py-2.5 text-[15px] font-medium transition-colors ${isActive ? 'bg-grass/10 text-ink' : 'text-ink-dim hover:bg-white/5 hover:text-ink'}`}
            >
              {isActive && <motion.span layoutId="nav-active" className="absolute left-0 top-2 bottom-2 w-1 rounded-full bg-mint" transition={{ type: 'spring', stiffness: 500, damping: 35 }} />}
              <item.Icon size={18} className={isActive ? 'text-mint' : 'text-ink-faint'} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="px-5 py-4 border-t border-line flex items-center justify-between">
        <span className="text-xs text-ink-faint">{t('common.made_by')} <span className="text-ink-dim">CalaKuad1</span></span>
        <div className="flex gap-1">
          <button
            onClick={onOpenAppSettings}
            className="p-2 hover:bg-white/10 rounded-sm transition-colors text-ink-faint hover:text-ink"
            title={t('settings.title')}
            aria-label={t('settings.title')}
          >
            <SettingsIcon size={16} />
          </button>
          <a href="https://github.com/CalaKuad1" target="_blank" rel="noreferrer" className="p-2 hover:bg-white/10 rounded-sm transition-colors text-ink-faint hover:text-ink" title={t('settings.view_github')} aria-label={t('settings.view_github')}><Github size={16} /></a>
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
  // Set when the wizard finishes so the new server starts by itself.
  const [autoStartServer, setAutoStartServer] = useState(false);
  const [showAppSettings, setShowAppSettings] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [updateStatus, setUpdateStatus] = useState(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (!window.electron || !window.electron.onUpdateStatus) return;
    const off = window.electron.onUpdateStatus((status) => setUpdateStatus(status));
    return () => { if (typeof off === 'function') off(); };
  }, []);

  useEffect(() => {
    if (window.electron && window.electron.onCloseRequested) {
      const off = window.electron.onCloseRequested(() => {
        setIsStopping(true);
      });
      return () => { if (typeof off === 'function') off(); };
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
    } catch (e) {
      console.error('Failed to refresh status:', e);
    }
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
          // Polling time 3000ms (3s)
          timer = setTimeout(tick, 3000);
        } catch (e) {
          timer = setTimeout(tick, 5000); // Wait longer on failure
        }
      };

      tick();
      return () => {
        cancelled = true;
        if (timer) clearTimeout(timer);
      };
    }
  }, [selectedServer, isSameStatus]);

  const handleServerSelected = useCallback(async (serverId = null) => {
    let targetId = serverId;
    if (!targetId) {
      // If no ID provided, we just want to refresh or load default
      try {
        const servers = await api.getServers();
        if (servers && servers.length > 0) {
          targetId = servers[servers.length - 1].id;
        }
      } catch (e) { return; }
    }

    if (!targetId) return;

    // 1. Limpieza visual inmediata antes de la carga (solo si es un cambio de servidor)
    if (selectedServer?.id !== targetId) {
      setSelectedServer(null);
      setServerStatus(null);
    }

    try {
      const response = await api.selectServer(targetId);

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
      setSelectedServer({ id: targetId }); // Fallback
    }
    setActiveTab('dashboard');
  }, [selectedServer?.id]);

  const handleBackToLibrary = async () => {
    setAutoStartServer(false);
    setSelectedServer(null);
    setServerStatus(null);
  };

  if (isStopping) {
    return (
      <div className="h-screen w-screen bg-black/90 flex flex-col items-center justify-center text-white z-[9999] fixed inset-0 font-sans">
        <Cubi mood="sleep" size={104} className="mb-4" />
        <h2 className="text-3xl font-display font-semibold mb-2">{t('status.stopping')}</h2>
        <p className="text-gray-400">{t('app.saving_world')}</p>
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
          <SetupWizard onComplete={(serverId) => { setShowWizard(false); setAutoStartServer(true); handleServerSelected(serverId); }} onCancel={() => setShowWizard(false)} />
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
          status={serverStatus}
        />
        
        <main className="flex-1 overflow-hidden relative flex flex-col bg-ground/70 backdrop-blur-md w-full">
          <div className="flex-1 overflow-y-auto px-6 py-5 relative z-10 flex flex-col [scrollbar-gutter:stable] w-full">
          <div className="mx-auto w-full flex-1 min-h-0 flex flex-col">
            {/* Dashboard - always mounted to preserve log state */}
            <div style={{ display: activeTab !== 'dashboard' ? 'none' : undefined }} className={activeTab === 'dashboard' ? 'flex-1 min-h-0 flex flex-col' : ''}>
              <Dashboard status={serverStatus} onRefresh={triggerRefresh} active={activeTab === 'dashboard'} onNavigate={setActiveTab} autoStart={autoStartServer} onAutoStartHandled={() => setAutoStartServer(false)} />
            </div>


            {/* Console - always mounted to preserve log state */}
            <div style={{ display: activeTab !== 'console' ? 'none' : undefined }}>
              <Console key={selectedServer?.server_id || selectedServer?.id} serverId={selectedServer?.server_id || selectedServer?.id} />
            </div>

            {/* Animated transitions for other tabs */}
            <AnimatePresence mode="wait">
              {activeTab !== 'dashboard' && activeTab !== 'console' && (
                <motion.div
                  key={`${activeTab}-${selectedServer?.id}`}
                  initial={{ opacity: 0, scale: 0.99, y: 10, filter: 'blur(4px)' }}
                  animate={{ opacity: 1, scale: 1, y: 0, filter: 'blur(0px)' }}
                  exit={{ opacity: 0, scale: 0.99, y: -10, filter: 'blur(4px)' }}
                  transition={{ duration: 0.25, ease: "easeOut" }}
                >
                  {activeTab === 'players' && <Players status={serverStatus} />}
                  {activeTab === 'worlds' && <Worlds />}
                  {activeTab === 'mods' && <Mods status={serverStatus} onOpenWizard={() => setShowWizard(true)} />}
                  {activeTab === 'plugins' && <Plugins status={serverStatus} />}
                  {activeTab === 'settings' && <Settings />}
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {showAppSettings && (
                <AppSettings isOpen={true} onClose={() => setShowAppSettings(false)} />
              )}
            </AnimatePresence>
          </div>
          </div>
        </main>
      </div>

      {updateStatus && ['available', 'downloading', 'downloaded', 'error'].includes(updateStatus.state) && (
        <div className="fixed bottom-5 right-5 z-[9998] max-w-xs bg-panel border border-white/10 rounded-sm shadow-2xl p-4 text-xs">
          <div className="font-minecraft uppercase tracking-widest text-white mb-1">{t('app.update')}</div>
          {updateStatus.state === 'available' && (
            <div className="text-zinc-400">
              New version {updateStatus.version} available.
              {updateStatus.manual && (
                <button
                  onClick={() => window.electron?.downloadUpdate?.()}
                  className="mt-2 w-full px-3 py-1.5 bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 rounded-sm font-minecraft uppercase tracking-wider hover:bg-emerald-500/25 transition-colors"
                >
                  Download
                </button>
              )}
            </div>
          )}
          {updateStatus.state === 'downloading' && <div className="text-zinc-400">Downloading… {updateStatus.percent}%</div>}
          {updateStatus.state === 'downloaded' && (
            <div className="text-zinc-400">
              Version {updateStatus.version} ready.
              <button
                onClick={() => window.electron?.installUpdate?.()}
                className="mt-2 w-full px-3 py-1.5 bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 rounded-sm font-minecraft uppercase tracking-wider hover:bg-emerald-500/25 transition-colors"
              >
                Restart &amp; install
              </button>
            </div>
          )}
          {updateStatus.state === 'error' && <div className="text-yellow-400">Update check failed: {updateStatus.message}</div>}
        </div>
      )}
    </div>
  );
}

export default App;

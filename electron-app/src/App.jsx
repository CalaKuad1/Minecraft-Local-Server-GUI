import React, { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { LayoutDashboard, Terminal, Settings as SettingsIcon, Users, Activity, Globe, Github, Package, Plug } from 'lucide-react';
import { api } from './api';

import logo from './assets/logo2.png';

// Components
import Dashboard from './components/Dashboard';
import Console from './components/Console';
import SetupWizard from './components/SetupWizard';

import Players from './components/Players';
import Settings from './components/Settings';
import Worlds from './components/Worlds';
import Mods from './components/Mods';
import Plugins from './components/Plugins';

import ServerSelector from './components/ServerSelector';
import TitleBar from './components/TitleBar';

// Sidebar component
function Sidebar({ activeTab, setActiveTab, onBack }) {
  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'console', icon: Terminal, label: 'Console' },
    { id: 'players', icon: Users, label: 'Players' },
    { id: 'worlds', icon: Globe, label: 'Worlds' },
    { id: 'mods', icon: Package, label: 'Mods' },
    { id: 'plugins', icon: Plug, label: 'Plugins' },
    { id: 'settings', icon: SettingsIcon, label: 'Settings' },
  ];

  return (
    <div className="w-64 bg-surface/60 backdrop-blur-xl h-screen flex flex-col border-r border-white/5 pt-8">
      <div className="p-6 flex justify-center mb-2">
        <img src={logo} alt="Server Manager" className="w-full max-h-24 object-contain drop-shadow-[0_0_15px_rgba(99,102,241,0.3)]" />
      </div>
      <div className="px-4 mb-2 mt-4">
        <button onClick={onBack} className="w-full flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors border border-transparent hover:border-white/10">
          <LayoutDashboard size={14} className="rotate-180" />
          <span>Back to Library</span>
        </button>
      </div>
      <nav className="flex-1 px-4 space-y-2 mt-2">
        {menuItems.map((item) => (
          <button key={item.id} onClick={() => setActiveTab(item.id)} className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${activeTab === item.id ? 'bg-primary/10 text-primary border border-primary/20 shadow-[0_0_15px_rgba(99,102,241,0.2)]' : 'text-gray-400 hover:bg-surface-hover hover:text-white'}`}>
            <item.icon size={20} className={activeTab === item.id ? 'stroke-[2.5px]' : 'stroke-2'} />
            <span className="font-medium">{item.label}</span>
            {activeTab === item.id && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_8px_currentColor]" />}
          </button>
        ))}
      </nav>
      <div className="p-4 border-t border-white/5">
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-black/40 text-sm text-gray-400">
          <Activity size={16} className="text-green-500 animate-pulse" />
          <span>System Online</span>
        </div>
      </div>
      <div className="px-6 pb-6 pt-2">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Made by <span className="text-white font-medium">CalaKuad1</span></span>
          <a href="https://github.com/CalaKuad1" target="_blank" rel="noreferrer" className="p-2 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-white" title="View on GitHub"><Github size={16} /></a>
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
  const [isStopping, setIsStopping] = useState(false);

  useEffect(() => {
    if (window.electron && window.electron.onCloseRequested) {
      window.electron.onCloseRequested(() => {
        setIsStopping(true);
      });
    }
  }, []);

  // Updated comparison function to handle minor differences gracefully
  const isSameStatus = (a, b) => {
    if (!a || !b) return false;
    return (
      a.status === b.status &&
      a.pid === b.pid &&
      a.players === b.players &&
      a.cpu === b.cpu &&
      a.ram === b.ram
    );
  };

  // Helper to force a fetch immediately
  const triggerRefresh = async () => {
    try {
      const status = await api.getStatus();
      setServerStatus(status);
    } catch (e) { }
  };

  useEffect(() => {
    if (selectedServer) {
      let cancelled = false;
      let timer = null;

      const tick = async () => {
        if (cancelled) return;
        try {
          const status = await api.getStatus();
          if (!cancelled) {
            setServerStatus((prev) => (isSameStatus(prev, status) ? prev : status));
          }
          const nextMs = status?.status === 'starting' || status?.status === 'stopping' ? 2000 : 4000;
          timer = setTimeout(tick, nextMs);
        } catch (e) {
          timer = setTimeout(tick, 5000);
        }
      };

      tick();
      return () => {
        cancelled = true;
        if (timer) clearTimeout(timer);
      };
    }
  }, [selectedServer]);

  const handleServerSelected = async (serverId = null) => {
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
  };

  const handleBackToLibrary = async () => {
    setSelectedServer(null);
    setServerStatus(null);
  };

  if (isStopping) {
    return (
      <div className="h-screen w-screen bg-black/90 flex flex-col items-center justify-center text-white z-[9999] fixed inset-0 font-sans">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary mb-6"></div>
        <h2 className="text-3xl font-bold mb-2">Stopping Server</h2>
        <p className="text-gray-400">Saving world and closing gracefully...</p>
      </div>
    );
  }

  if (showWizard) {
    return (
      <div className="h-screen w-screen bg-background text-white overflow-hidden flex flex-col pt-8">
        <TitleBar />
        <div className="flex-1 overflow-y-auto">
          <SetupWizard onComplete={(serverId) => { setShowWizard(false); handleServerSelected(serverId); }} onCancel={() => setShowWizard(false)} />
        </div>
      </div>
    );
  }

  if (!selectedServer) {
    return (
      <div className="pt-8 bg-[#050505] min-h-screen">
        <TitleBar />
        <ServerSelector onSelect={handleServerSelected} onAdd={() => setShowWizard(true)} />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-transparent font-sans selection:bg-primary/30 text-white overflow-hidden">
      <TitleBar />
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} onBack={handleBackToLibrary} />
      <main className="flex-1 overflow-hidden relative flex flex-col pt-8">
        <div className="flex-1 overflow-y-auto p-8 relative z-10">
          <div className="max-w-6xl mx-auto">
            <AnimatePresence mode="wait">
              <motion.div
                key={`${activeTab}-${selectedServer?.id}`}
                initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -10, filter: 'blur(4px)' }}
                transition={{ duration: 0.25, ease: "easeOut" }}
                style={{ display: activeTab === 'console' ? 'none' : 'block' }}
              >
                {activeTab === 'dashboard' && <Dashboard status={serverStatus} onRefresh={triggerRefresh} />}
                {activeTab === 'players' && <Players status={serverStatus} />}
                {activeTab === 'worlds' && <Worlds />}
                {activeTab === 'mods' && <Mods status={serverStatus} onOpenWizard={() => setShowWizard(true)} />}
                {activeTab === 'plugins' && <Plugins status={serverStatus} />}
                {activeTab === 'settings' && <Settings />}
              </motion.div>
            </AnimatePresence>

            <div style={{ display: activeTab === 'console' ? 'block' : 'none', height: '100%' }}>
              <Console key={selectedServer?.id} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

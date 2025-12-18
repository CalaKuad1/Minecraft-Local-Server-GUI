import React, { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { LayoutDashboard, Terminal, Settings as SettingsIcon, Users, Activity, Globe, Github, Package } from 'lucide-react';
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

import ServerSelector from './components/ServerSelector';

function Sidebar({ activeTab, setActiveTab, onBack }) {
  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'console', icon: Terminal, label: 'Console' },
    { id: 'players', icon: Users, label: 'Players' },
    { id: 'worlds', icon: Globe, label: 'Worlds' },
    { id: 'mods', icon: Package, label: 'Mods' },
    { id: 'settings', icon: SettingsIcon, label: 'Settings' },
  ];

  return (
    <div className="w-64 bg-surface/60 backdrop-blur-xl h-screen flex flex-col border-r border-white/5 drag-region">
      {/* App Drag Region (Titlebar) */}
      <div className="h-8 w-full bg-transparent" style={{ WebkitAppRegion: 'drag' }}></div>

      <div className="p-6 flex justify-center mb-2">
        <img
          src={logo}
          alt="Server Manager"
          className="w-full max-h-24 object-contain drop-shadow-[0_0_15px_rgba(99,102,241,0.3)]"
        />
      </div>

      {/* Back to Library Button */}
      <div className="px-4 mb-2 mt-4">
        <button
          onClick={onBack}
          className="w-full flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors border border-transparent hover:border-white/10"
        >
          <LayoutDashboard size={14} className="rotate-180" />
          <span>Back to Library</span>
        </button>
      </div>

      <nav className="flex-1 px-4 space-y-2 mt-2">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${activeTab === item.id
              ? 'bg-primary/10 text-primary border border-primary/20 shadow-[0_0_15px_rgba(99,102,241,0.2)]'
              : 'text-gray-400 hover:bg-surface-hover hover:text-white'
              }`}
          >
            <item.icon size={20} className={activeTab === item.id ? 'stroke-[2.5px]' : 'stroke-2'} />
            <span className="font-medium">{item.label}</span>
            {activeTab === item.id && (
              <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_8px_currentColor]" />
            )}
          </button>
        ))}
      </nav>

      <div className="p-4 border-t border-white/5">
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-black/40 text-sm text-gray-400">
          <Activity size={16} className="text-green-500 animate-pulse" />
          <span>System Online</span>
        </div>
      </div>

      {/* Author Footer */}
      <div className="px-6 pb-6 pt-2">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Made by <span className="text-white font-medium">CalaKuad1</span></span>
          <a
            href="https://github.com/CalaKuad1"
            target="_blank"
            rel="noreferrer"
            className="p-2 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-white"
            title="View on GitHub"
          >
            <Github size={16} />
          </a>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedServer, setSelectedServer] = useState(null); // Now stores actual server config or null
  const [serverStatus, setServerStatus] = useState(null); // Live status from backend
  const [checking, setChecking] = useState(true);
  const [showWizard, setShowWizard] = useState(false);

  // --- Shutdown Logic ---
  const [isStopping, setIsStopping] = useState(false);

  useEffect(() => {
    if (window.electron && window.electron.onCloseRequested) {
      window.electron.onCloseRequested(() => {
        console.log("Shutdown signal received from Main Process.");
        setIsStopping(true);
        // The main process will handle the actual exit after cleaning up
      });
    }
  }, []);

  const isSameStatus = (a, b) => {
    if (!a || !b) return false;

    const lastLogA = Array.isArray(a.recent_logs) && a.recent_logs.length > 0 ? a.recent_logs[a.recent_logs.length - 1] : null;
    const lastLogB = Array.isArray(b.recent_logs) && b.recent_logs.length > 0 ? b.recent_logs[b.recent_logs.length - 1] : null;
    const lastMsgA = lastLogA ? `${lastLogA.level || ''}:${lastLogA.message || ''}` : '';
    const lastMsgB = lastLogB ? `${lastLogB.level || ''}:${lastLogB.message || ''}` : '';

    return (
      a.status === b.status &&
      a.pid === b.pid &&
      a.server_type === b.server_type &&
      a.minecraft_version === b.minecraft_version &&
      a.cpu === b.cpu &&
      a.ram === b.ram &&
      a.players === b.players &&
      a.max_players === b.max_players &&
      a.uptime === b.uptime &&
      a.local_ip === b.local_ip &&
      a.port === b.port &&
      lastMsgA === lastMsgB
    );
  };

  // Fetch server status periodically when a server is selected
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

          const nextMs = status?.status === 'starting' ? 6000 : 3000;
          timer = setTimeout(tick, nextMs);
        } catch (e) {
          console.error("Failed to fetch status", e);
          timer = setTimeout(tick, 6000);
        }
      };

      tick();
      return () => {
        cancelled = true;
        if (timer) clearTimeout(timer);
      };
    }
  }, [selectedServer]);

  const handleServerSelected = async () => {
    // Fetch the current server status to get config details
    try {
      const status = await api.getStatus();
      setServerStatus(status);
      setSelectedServer(status); // Store full status object
    } catch (e) {
      setSelectedServer(true); // Fallback
    }
    setActiveTab('dashboard');
  };

  const handleBackToLibrary = async () => {
    setSelectedServer(null);
    setServerStatus(null);
  };

  // --- Render: Shutdown Overlay (Priority 1) ---
  if (isStopping) {
    return (
      <div className="h-screen w-screen bg-black/90 flex flex-col items-center justify-center text-white z-[9999] fixed inset-0 font-sans">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary mb-6"></div>
        <h2 className="text-3xl font-bold mb-2">Stopping Server</h2>
        <p className="text-gray-400">Saving world and closing gracefully...</p>
      </div>
    );
  }

  // If adding a new server (Wizard Mode)
  if (showWizard) {
    return (
      <div className="h-screen w-screen bg-background text-white overflow-hidden flex flex-col">
        <div className="h-8 w-full bg-background" style={{ WebkitAppRegion: 'drag' }}></div>
        <div className="flex-1 overflow-y-auto">
          <SetupWizard onComplete={() => { setShowWizard(false); handleServerSelected(); }} onCancel={() => setShowWizard(false)} />
        </div>
      </div>
    );
  }

  // If no server selected, show Library
  if (!selectedServer) {
    return (
      <>
        <div className="h-8 w-full bg-[#050505] fixed top-0 left-0 z-50" style={{ WebkitAppRegion: 'drag' }}></div>
        <ServerSelector
          onSelect={handleServerSelected}
          onAdd={() => setShowWizard(true)}
        />
      </>
    );
  }

  // Main Dashboard Layout
  return (
    <div className="flex h-screen bg-transparent font-sans selection:bg-primary/30 text-white overflow-hidden">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} onBack={handleBackToLibrary} />

      <main className="flex-1 overflow-hidden relative flex flex-col">
        {/* Draggable top area for the main content */}
        <div className="h-8 w-full shrink-0" style={{ WebkitAppRegion: 'drag' }}></div>

        <div className="flex-1 overflow-y-auto p-8 relative z-10">
          <div className="max-w-6xl mx-auto">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -10, filter: 'blur(4px)' }}
                transition={{ duration: 0.25, ease: "easeOut" }}
                style={{ display: activeTab === 'console' ? 'none' : 'block' }}
              >
                {activeTab === 'dashboard' && <Dashboard status={serverStatus} />}
                {activeTab === 'players' && <Players status={serverStatus} />}
                {activeTab === 'worlds' && <Worlds />}
                {activeTab === 'mods' && <Mods status={serverStatus} onOpenWizard={() => setShowWizard(true)} />}
                {activeTab === 'settings' && <Settings />}
              </motion.div>
            </AnimatePresence>

            {/* Keep Console mounted to preserve WebSocket connection and history */}
            <div style={{ display: activeTab === 'console' ? 'block' : 'none', height: '100%' }}>
              <Console />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

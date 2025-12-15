import { LayoutDashboard, Terminal, Users, Globe, Settings as SettingsIcon, Activity, Github } from 'lucide-react';
import logo from '../assets/logo2.png';

function Sidebar({ activeTab, setActiveTab }) {
    const menuItems = [
        { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
        { id: 'console', icon: Terminal, label: 'Console' },
        { id: 'players', icon: Users, label: 'Players' },
        { id: 'worlds', icon: Globe, label: 'Worlds' },
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

            <nav className="flex-1 px-4 space-y-2">
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

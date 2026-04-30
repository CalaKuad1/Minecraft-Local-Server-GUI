import { Activity, Github } from './ui/PixelIcons';
import logo from '../assets/logo2.png';

const PixelIcon = ({ type, active }) => {
    // 16x16 crisp pixel grid paths
    const paths = {
        'dashboard': 'M2 2h5v5H2zm7 0h5v5H9zm0 7h5v5H9zM2 9h5v5H2z', // 4 exact cubes
        'console': 'M2 3h12v10H2zm2 2v4h2V7h2V5H4zm5 6h4v-2H9z', // Terminal prompt
        'players': 'M5 2h6v6H5z M3 9h10v5H3z', // Little steve representation
        'worlds': 'M2 2h12v12H2z M3 3h3v3H3z M8 8h5v5H8z M4 9h2v2H4z', // Block chunks
        'settings': 'M6 1h4v2h2v2h2v4h-2v2h-2v2H6v-2H4v-2H2V7h2V5h2z M6 6h4v4H6z' // Gear
    };

    return (
        <svg viewBox="0 0 16 16" width="20" height="20" fill="currentColor" style={{ shapeRendering: 'crispEdges' }} className={`${active ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]' : 'text-gray-500'}`}>
            <path d={paths[type]} />
        </svg>
    );
};

function Sidebar({ activeTab, setActiveTab }) {
    const menuItems = [
        { id: 'dashboard', type: 'dashboard', label: 'Dashboard' },
        { id: 'console', type: 'console', label: 'Console' },
        { id: 'players', type: 'players', label: 'Players' },
        { id: 'worlds', type: 'worlds', label: 'Worlds' },
        { id: 'settings', type: 'settings', label: 'Settings' },
    ];

    return (
        <div className="w-64 bg-[#070707]/60 backdrop-blur-3xl h-full flex flex-col border border-white/5 shadow-2xl rounded-sm relative z-10 overflow-hidden drag-region">
            {/* App Drag Region (Titlebar) */}
            <div className="h-4 w-full bg-transparent" style={{ WebkitAppRegion: 'drag' }}></div>

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
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-sm transition-all duration-200 group border-l-2 ${activeTab === item.id
                            ? 'bg-white/10 text-emerald-400 border-primary shadow-sm'
                            : 'border-transparent text-gray-400 hover:bg-white/5 hover:border-white/20 hover:text-white'
                            }`}
                    >
                        <PixelIcon type={item.type} active={activeTab === item.id} />
                        <span className="font-minecraft text-lg tracking-wider mt-0.5 uppercase">{item.label}</span>
                        {activeTab === item.id && (
                            <div className="ml-auto w-1.5 h-1.5 rounded-sm bg-primary shadow-[0_0_8px_currentColor]" />
                        )}
                    </button>
                ))}
            </nav>

            <div className="p-4 border-t border-white/5">
                <div className="flex items-center gap-3 px-4 py-3 rounded-sm border border-white/5 bg-black/40 text-sm text-gray-400">
                    <Activity size={16} className="text-emerald-500 animate-pulse" />
                    <span className="font-minecraft text-sm tracking-widest mt-0.5">System Online</span>
                </div>
            </div>

            {/* Author Footer */}
            <div className="px-6 pb-6 pt-2">
                <div className="flex items-center justify-between text-xs text-gray-500 font-minecraft uppercase tracking-wider">
                    <span>Made by <span className="text-white">CalaKuad1</span></span>
                    <a
                        href="https://github.com/CalaKuad1"
                        target="_blank"
                        rel="noreferrer"
                        className="p-2 hover:bg-white/10 rounded-sm transition-colors text-gray-400 hover:text-white"
                        title="View on GitHub"
                    >
                        <Github size={16} />
                    </a>
                </div>
            </div>
        </div>
    );
}

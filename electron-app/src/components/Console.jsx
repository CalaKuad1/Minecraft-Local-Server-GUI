import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Download, Send } from './ui/PixelIcons';
import { api } from '../api';
import { useWebSocket, getStoredLogs } from '../contexts/WebSocketContext';
import { useTranslation } from '../contexts/LanguageContext';

const LogBadge = ({ level }) => {
    if (level === 'input') return <span className="px-1.5 py-0.5 bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 rounded mr-2 text-[10px] font-bold">CMD</span>;
    if (level === 'error') return <span className="px-1.5 py-0.5 bg-red-500/10 text-red-500 border border-red-500/20 rounded mr-2 text-[10px] font-bold">ERR</span>;
    if (level === 'warning') return <span className="px-1.5 py-0.5 bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 rounded mr-2 text-[10px] font-bold">WRN</span>;
    return <span className="px-1.5 py-0.5 bg-white/5 text-white/40 border border-white/10 rounded mr-2 text-[10px] font-bold">INF</span>;
};

// Common Minecraft server commands, for Tab-completion and suggestions.
const MC_COMMANDS = [
    'help', 'list', 'say', 'tell', 'me', 'msg', 'op', 'deop', 'kick', 'ban', 'ban-ip',
    'pardon', 'pardon-ip', 'whitelist', 'save-all', 'save-off', 'save-on', 'stop',
    'reload', 'gamemode', 'difficulty', 'time', 'weather', 'tp', 'teleport', 'give',
    'effect', 'enchant', 'xp', 'clear', 'kill', 'spawnpoint', 'setworldspawn', 'seed',
    'setblock', 'fill', 'clone', 'summon', 'particle', 'playsound', 'title', 'tellraw',
    'execute', 'function', 'tag', 'scoreboard', 'team', 'datapack', 'worldborder',
    'forceload', 'gamerule', 'advancement', 'recipe', 'attribute', 'publish', 'tps',
    'plugins', 'version',
];

const MAX_LOGS = 800;

export default function Console({ serverId }) {
    const { t } = useTranslation();
    const { isConnected, subscribe, send } = useWebSocket();
    const logIdRef = useRef(0);
    // Seed from the global store so returning from the library keeps the history
    // (including logs that arrived while this component was unmounted).
    const [logs, setLogs] = useState(() => {
        const stored = serverId ? getStoredLogs(serverId) : [];
        return stored.slice(-MAX_LOGS).map(item => ({
            ...item,
            _id: ++logIdRef.current,
            message: typeof item.message === 'string' ? item.message : String(item.message || ''),
            time: item.time || new Date().toTimeString().slice(0, 5)
        }));
    });
    const [inputObj, setInputObj] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
    const [levelFilter, setLevelFilter] = useState('all');
    const scrollRef = useRef(null);
    const userScrolledUpRef = useRef(false);

    // Command history (persisted) + Tab completion
    const [cmdHistory, setCmdHistory] = useState(() => {
        try { return JSON.parse(localStorage.getItem('mlsg_cmd_history') || '[]'); } catch { return []; }
    });
    const historyPosRef = useRef(-1);
    const draftRef = useRef('');

    // Incoming logs arrive in batches of up to 200 (see backend broadcaster).
    // Buffering them and flushing once per animation frame avoids hundreds of
    // setState calls (and full list re-renders) per batch.
    const pendingLogsRef = useRef([]);
    const flushFrameRef = useRef(0);

    const flushLogs = useCallback(() => {
        flushFrameRef.current = 0;
        const pending = pendingLogsRef.current;
        if (pending.length === 0) return;
        pendingLogsRef.current = [];
        setLogs(prev => {
            const next = prev.concat(pending);
            return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
        });
    }, []);

    const scheduleFlush = useCallback(() => {
        if (flushFrameRef.current) return;
        flushFrameRef.current = requestAnimationFrame(flushLogs);
    }, [flushLogs]);

    useEffect(() => {
        const handleMsg = (item) => {
            if (item && typeof item === 'object' && item.type && item.message === undefined) return;
            if (item.message === undefined && !item.level) return;

            pendingLogsRef.current.push({
                ...item,
                _id: ++logIdRef.current,
                message: typeof item.message === 'string' ? item.message : String(item.message || ''),
                time: item.time || new Date().toTimeString().slice(0, 5)
            });
            scheduleFlush();
        };

        const unsubscribe = subscribe('console', handleMsg);
        return () => {
            unsubscribe();
            if (flushFrameRef.current) cancelAnimationFrame(flushFrameRef.current);
            flushFrameRef.current = 0;
            pendingLogsRef.current = [];
        };
    }, [subscribe, scheduleFlush]);

    // Polling fallback when WebSocket is disconnected
    useEffect(() => {
        if (isConnected) return;
        let cancelled = false;
        let timer = null;

        const poll = async () => {
            if (cancelled) return;
            try {
                const status = await api.getStatus();
                if (cancelled) return;
                if (status?.recent_logs && Array.isArray(status.recent_logs)) {
                    setLogs(prev => {
                        if (prev.length === 0) {
                            const items = status.recent_logs.slice(-150).map(item => ({
                                ...item,
                                _id: ++logIdRef.current,
                                message: typeof item.message === 'string' ? item.message : String(item.message || ''),
                                time: item.time || new Date().toTimeString().slice(0, 5)
                            }));
                            return items.slice(-MAX_LOGS);
                        }
                        const lastLocal = prev[prev.length - 1];
                        const newItems = [];
                        for (const item of status.recent_logs) {
                            const msg = typeof item.message === 'string' ? item.message : String(item.message || '');
                            if (lastLocal && msg === lastLocal.message) break;
                            newItems.unshift({
                                ...item,
                                _id: ++logIdRef.current,
                                message: msg,
                                time: item.time || new Date().toTimeString().slice(0, 5)
                            });
                        }
                        if (newItems.length === 0) return prev;
                        const next = [...prev, ...newItems.reverse()];
                        return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
                    });
                }
            } catch (e) {}
            if (!cancelled) timer = setTimeout(poll, 3000);
        };

        poll();
        return () => {
            cancelled = true;
            if (timer) clearTimeout(timer);
        };
    }, [isConnected]);

    useEffect(() => {
        if (scrollRef.current && !userScrolledUpRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    const handleScroll = useCallback((e) => {
        const el = e.target;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        userScrolledUpRef.current = !atBottom;
    }, []);

    const handleDownload = useCallback(() => {
        if (logs.length === 0) return;
        const text = logs.map(log => {
            const time = log.level !== 'input' && log.time ? `[${log.time}] ` : '';
            const level = log.level ? `[${log.level.toUpperCase()}] ` : '';
            return `${time}${level}${log.message}`;
        }).join('\n');
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `server-console-${new Date().toISOString().slice(0, 10)}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }, [logs]);

    const filteredLogs = useMemo(() => {
        return logs.filter(log => {
            if (levelFilter !== 'all' && log.level !== levelFilter) return false;
            if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) return false;
            return true;
        });
    }, [logs, searchQuery, levelFilter]);

    const suggestions = useMemo(() => {
        const text = inputObj.trimStart();
        if (!text || text.includes(' ')) return [];
        const q = text.toLowerCase();
        return MC_COMMANDS.filter(c => c.startsWith(q) && c !== q).slice(0, 6);
    }, [inputObj]);

    const handleInputKeyDown = useCallback((e) => {
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (cmdHistory.length === 0) return;
            if (historyPosRef.current === -1) draftRef.current = inputObj;
            const pos = Math.min(historyPosRef.current + 1, cmdHistory.length - 1);
            historyPosRef.current = pos;
            setInputObj(cmdHistory[cmdHistory.length - 1 - pos]);
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (historyPosRef.current === -1) return;
            const pos = historyPosRef.current - 1;
            historyPosRef.current = pos;
            setInputObj(pos === -1 ? draftRef.current : cmdHistory[cmdHistory.length - 1 - pos]);
        } else if (e.key === 'Tab') {
            e.preventDefault();
            const text = inputObj.trimStart();
            if (!text || text.includes(' ')) return;
            const q = text.toLowerCase();
            const matches = MC_COMMANDS.filter(c => c.startsWith(q));
            if (matches.length === 0) return;
            if (matches.length === 1) { setInputObj(matches[0] + ' '); return; }
            // Complete to the longest common prefix of all matches.
            let lcp = matches[0];
            for (const m of matches) {
                while (!m.startsWith(lcp)) lcp = lcp.slice(0, -1);
            }
            setInputObj(lcp.length > q.length ? lcp : matches[0] + ' ');
        }
    }, [cmdHistory, inputObj]);

    const sendCommand = useCallback(async (e) => {
        e.preventDefault();
        if (!inputObj.trim()) return;

        const cmd = inputObj;
        historyPosRef.current = -1;
        draftRef.current = '';
        setCmdHistory(prev => {
            const next = prev[prev.length - 1] === cmd ? prev : [...prev, cmd].slice(-100);
            try { localStorage.setItem('mlsg_cmd_history', JSON.stringify(next)); } catch { /* ignore */ }
            return next;
        });
        setLogs(prev => {
            const next = [...prev, { _id: ++logIdRef.current, message: `> ${cmd}`, level: 'input', time: new Date().toTimeString().slice(0, 5) }];
            return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
        });

        if (isConnected) {
            send(cmd);
        } else {
            try {
                await api.sendCommand(cmd);
            } catch (err) {
                setLogs(prev => [...prev, { _id: ++logIdRef.current, message: `Error: ${err.message}`, level: 'error', time: new Date().toTimeString().slice(0, 5) }]);
            }
        }
        setInputObj('');
    }, [inputObj, isConnected, send]);

    return (
        <div className="bg-[#030303] rounded-2xl border border-white/10 flex flex-col h-[calc(100vh-140px)] shadow-2xl overflow-hidden font-mono text-sm">
            <div className="flex items-center justify-between px-4 py-2 bg-[#0a0a0a] border-b border-white/5 text-gray-400 text-xs uppercase tracking-widest font-bold">
                <div className="flex items-center gap-4">
                    <div className="flex gap-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/50"></div>
                    </div>
                    <span>Integrated Terminal</span>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleDownload}
                        disabled={logs.length === 0}
                        className="flex items-center gap-1.5 text-zinc-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-[10px] font-bold uppercase tracking-widest"
                        title="Download logs"
                    >
                        <Download size={12} />
                        Log
                    </button>
                    <div className={`flex items-center gap-2 ${isConnected ? 'text-green-500' : 'text-yellow-500'}`}>
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
                        {isConnected ? t('status.online') : 'Disconnected'}
                    </div>
                </div>
            </div>

            {/* Filter bar */}
            <div className="flex items-center gap-2 px-4 py-1.5 bg-[#080808] border-b border-white/5">
                <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search logs..."
                    className="flex-1 bg-[#050505] border border-white/5 rounded px-2 py-1 text-[11px] text-white placeholder-zinc-700 font-mono outline-none focus:border-white/20 transition-colors"
                />
                <div className="flex gap-1">
                    {['all', 'normal', 'input', 'warning', 'error'].map(lvl => (
                        <button
                            key={lvl}
                            onClick={() => setLevelFilter(lvl)}
                            className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest transition-all ${
                                levelFilter === lvl
                                    ? 'bg-white/10 text-white'
                                    : 'text-zinc-600 hover:text-zinc-400 hover:bg-white/5'
                            }`}
                        >
                            {lvl === 'all' ? 'All' : lvl.slice(0, 3)}
                        </button>
                    ))}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-white/10" ref={scrollRef} onScroll={handleScroll}>
                {filteredLogs.map((log, i) => (
                    <div key={log._id} className="flex items-start font-mono text-[11.5px] leading-relaxed hover:bg-white/5 px-2 py-0.5 rounded transition-colors group">
                        <div className="w-12 flex-shrink-0 text-white/10 select-none group-hover:text-white/30 transition-colors">
                            {String(i + 1).padStart(4, '0')}
                        </div>
                        {log.level !== 'input' && (
                            <div className="text-white/20 mr-3 select-none w-16">
                                {log.time}
                            </div>
                        )}
                        <div className="mt-0.5"><LogBadge level={log.level} /></div>
                        <div className={`flex-1 whitespace-pre-wrap break-words ${log.level === 'error' ? 'text-red-400' :
                            log.level === 'warning' ? 'text-yellow-400' :
                                log.level === 'input' ? 'text-white font-bold tracking-tight' :
                                    'text-zinc-300'
                            }`}>
                            {log.message}
                        </div>
                    </div>
                ))}
                {filteredLogs.length === 0 && (
                    <div className="text-zinc-600 italic flex items-center gap-2 h-full justify-center opacity-50 font-sans text-center px-8">
                        {logs.length === 0 ? t('dashboard.waiting_logs') : 'No logs match your filter'}
                    </div>
                )}
            </div>

            <div className="relative">
                {suggestions.length > 0 && (
                    <div className="absolute bottom-full left-2 mb-1 flex flex-wrap items-center gap-1 max-w-[calc(100%-1rem)]">
                        {suggestions.map(s => (
                            <button key={s} type="button" onClick={() => setInputObj(s + ' ')}
                                className="px-2 py-0.5 bg-[#0f0f0f] border border-white/10 rounded-sm text-[10px] font-mono text-zinc-400 hover:text-white hover:border-white/30 transition-colors">
                                {s}
                            </button>
                        ))}
                        <span className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-600">Tab</span>
                    </div>
                )}
                <form onSubmit={sendCommand} className="p-2 bg-[#050505] border-t border-white/5 flex gap-2">
                    <span className="text-white/30 flex items-center justify-center pl-4 font-bold pointer-events-none">~/minecraft $</span>
                        <input
                            type="text"
                            value={inputObj}
                            onChange={(e) => setInputObj(e.target.value)}
                            onKeyDown={handleInputKeyDown}
                            className="flex-1 bg-transparent border-none outline-none text-white placeholder-zinc-700 font-mono text-xs pl-2"
                            placeholder={t('nav.console') + "..."}
                            autoFocus
                        />
                    <button type="submit" className="text-primary hover:text-white p-2 transition-colors">
                        <Send size={16} />
                    </button>
                </form>
            </div>
        </div>
    );
}

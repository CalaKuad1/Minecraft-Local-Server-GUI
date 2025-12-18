import React, { useEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';

export default function Console() {
    const [isConnected, setIsConnected] = useState(false);
    const [logs, setLogs] = useState([]);
    const [inputObj, setInputObj] = useState('');
    const ws = useRef(null);
    const scrollRef = useRef(null);
    const MAX_LOGS = 800;

    useEffect(() => {
        let timeoutId;
        let isMounted = true;

        const connect = () => {
            // Clean up previous connection if it exists
            if (ws.current) {
                ws.current.onclose = null; // Prevent triggering reconnect
                ws.current.close();
            }

            ws.current = new WebSocket('ws://127.0.0.1:8000/ws/console');

            ws.current.onopen = () => {
                if (isMounted) setIsConnected(true);
            };

            ws.current.onmessage = (event) => {
                if (!isMounted) return;
                try {
                    const data = JSON.parse(event.data);

                    const appendItems = (items) => {
                        const filtered = items.filter((it) => {
                            // Ignore structured events that aren't real console lines
                            if (it && typeof it === 'object' && it.type && it.message === undefined) return false;
                            return true;
                        });

                        if (filtered.length === 0) return;

                        setLogs((prev) => {
                            const next = [...prev, ...filtered];
                            if (next.length > MAX_LOGS) {
                                return next.slice(next.length - MAX_LOGS);
                            }
                            return next;
                        });
                    };

                    if (data && typeof data === 'object' && data.type === 'batch' && Array.isArray(data.items)) {
                        appendItems(data.items);
                        return;
                    }

                    appendItems([data]);
                } catch (e) {
                    console.error("Failed to parse log", e);
                }
            };

            ws.current.onclose = () => {
                if (isMounted) {
                    setIsConnected(false);
                    // Reconnect only if mounted
                    timeoutId = setTimeout(connect, 3000);
                }
            };

            ws.current.onerror = (err) => {
                console.error('WS Error:', err);
                // The onerror event usually precedes onclose, so we let onclose handle the retry
            };
        };

        connect();

        return () => {
            isMounted = false;
            // Clear reconnection timeout
            if (timeoutId) clearTimeout(timeoutId);

            // Close socket cleanly
            if (ws.current) {
                // Remove listeners to prevent logic from running during close
                ws.current.onclose = null;
                ws.current.onerror = null;
                ws.current.onmessage = null;
                ws.current.onopen = null;

                if (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING) {
                    ws.current.close();
                }
            }
        };
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    const sendCommand = (e) => {
        e.preventDefault();
        if (!inputObj.trim()) return;

        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(inputObj);
            setLogs(prev => {
                const next = [...prev, { message: `> ${inputObj}`, level: 'input' }];
                if (next.length > MAX_LOGS) {
                    return next.slice(next.length - MAX_LOGS);
                }
                return next;
            });
            setInputObj('');
        } else {
            setLogs(prev => {
                const next = [...prev, { message: `Error: Not connected to console.`, level: 'error' }];
                if (next.length > MAX_LOGS) {
                    return next.slice(next.length - MAX_LOGS);
                }
                return next;
            });
        }
    };

    return (
        <div className="bg-[#0f0f0f]/85 backdrop-blur-xl rounded-2xl border border-white/10 flex flex-col h-[calc(100vh-140px)] shadow-2xl overflow-hidden font-mono text-sm">
            <div className="flex items-center justify-between px-4 py-2 bg-[#1a1a1a]/90 border-b border-white/5 text-gray-400 text-xs uppercase tracking-widest font-bold">
                <div className="flex items-center gap-4">
                    <div className="flex gap-2">
                        <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50"></div>
                        <div className="w-3 h-3 rounded-full bg-yellow-500/20 border border-yellow-500/50"></div>
                        <div className="w-3 h-3 rounded-full bg-green-500/20 border border-green-500/50"></div>
                    </div>
                    <span>Terminal Output</span>
                </div>
                <div className={`flex items-center gap-2 ${isConnected ? 'text-green-500' : 'text-red-500'}`}>
                    <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`}></div>
                    {isConnected ? 'Connected' : 'Disconnected'}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-1 scrollbar-thin scrollbar-thumb-gray-700" ref={scrollRef}>
                {logs.map((log, i) => (
                    <div key={i} className={`whitespace-pre-wrap break-all ${log.level === 'error' ? 'text-red-400' :
                        log.level === 'warning' ? 'text-yellow-400' :
                            log.level === 'input' ? 'text-cyan-400 font-bold opacity-80' :
                                'text-gray-300'
                        }`}>
                        {log.level !== 'input' && <span className="opacity-30 mr-2">[{new Date().toLocaleTimeString()}]</span>}
                        {log.message}
                    </div>
                ))}
                {logs.length === 0 && (
                    <div className="text-gray-600 italic flex items-center gap-2 h-full justify-center opacity-50">
                        {isConnected ? 'Waiting for server output...' : 'Connecting to console...'}
                    </div>
                )}
            </div>

            <form onSubmit={sendCommand} className="p-2 bg-[#1a1a1a] border-t border-white/5 flex gap-2">
                <span className="text-primary flex items-center justify-center pl-2 font-bold pointer-events-none">$</span>
                <input
                    type="text"
                    value={inputObj}
                    onChange={(e) => setInputObj(e.target.value)}
                    className="flex-1 bg-transparent border-none outline-none text-white placeholder-gray-600 font-mono"
                    placeholder={isConnected ? "Type a command..." : "Connecting..."}
                    autoFocus
                    disabled={!isConnected}
                />
                <button type="submit" disabled={!isConnected} className="text-primary hover:text-white p-2 transition-colors disabled:opacity-50">
                    <Send size={16} />
                </button>
            </form>
        </div>
    );
}

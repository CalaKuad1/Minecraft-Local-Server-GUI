import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { API_TOKEN } from '../api';

const WS_URL = `ws://127.0.0.1:8000/ws/console${API_TOKEN ? `?token=${encodeURIComponent(API_TOKEN)}` : ''}`;
const RECONNECT_DELAY = 3000;

// Global per-server log store. Kept at module scope so a component that
// unmounts (e.g. the Console when returning to the library) doesn't lose the
// history, and logs received while unmounted are still captured.
const LOG_STORE_MAX = 800;
const logStore = new Map(); // serverId -> items[]
const GLOBAL_LOG_KEY = '__global__';

function storeLog(item) {
    if (!item || typeof item !== 'object') return;
    if (item.message === undefined && !item.level) return;
    const key = item.server_id || GLOBAL_LOG_KEY;
    const arr = logStore.get(key) || [];
    arr.push(item);
    if (arr.length > LOG_STORE_MAX) arr.splice(0, arr.length - LOG_STORE_MAX);
    logStore.set(key, arr);
    if (logStore.size > 25) {
        // Bound the number of tracked servers.
        for (const k of logStore.keys()) {
            if (k !== key && k !== GLOBAL_LOG_KEY) { logStore.delete(k); break; }
        }
    }
}

export function getStoredLogs(serverId) {
    if (serverId && logStore.has(serverId)) return logStore.get(serverId);
    return logStore.get(GLOBAL_LOG_KEY) || [];
}

const WebSocketContext = createContext(null);

export function useWebSocket() {
    const ctx = useContext(WebSocketContext);
    if (!ctx) throw new Error('useWebSocket must be inside WebSocketProvider');
    return ctx;
}

export function WebSocketProvider({ children }) {
    const wsRef = useRef(null);
    const listenersRef = useRef(new Map());
    const [isConnected, setIsConnected] = useState(false);
    const mountedRef = useRef(true);
    const reconnectTimerRef = useRef(null);
    const sendQueueRef = useRef([]);

    const connect = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.onclose = null;
            wsRef.current.onerror = null;
            wsRef.current.onmessage = null;
            wsRef.current.onopen = null;
            if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
                wsRef.current.close();
            }
        }

        const ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            if (mountedRef.current) setIsConnected(true);
            while (sendQueueRef.current.length > 0) {
                const msg = sendQueueRef.current.shift();
                if (ws.readyState === WebSocket.OPEN) ws.send(msg);
            }
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const items = (data.type === 'batch' && Array.isArray(data.items)) ? data.items : [data];
                for (const item of items) {
                    storeLog(item);
                    listenersRef.current.forEach((fn) => {
                        try { fn(item, data); } catch (e) { console.error('[WS listener error]', e); }
                    });
                }
            } catch (e) {}
        };

        ws.onclose = () => {
            if (mountedRef.current) {
                setIsConnected(false);
                reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY);
            }
        };

        ws.onerror = (err) => {
            console.error('[WS] Connection error:', err);
        };

        wsRef.current = ws;
    }, []);

    const subscribe = useCallback((id, callback) => {
        listenersRef.current.set(id, callback);
        return () => listenersRef.current.delete(id);
    }, []);

    const send = useCallback((message) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(message);
        } else {
            sendQueueRef.current.push(message);
        }
    }, []);

    useEffect(() => {
        mountedRef.current = true;
        connect();
        return () => {
            mountedRef.current = false;
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            if (wsRef.current) {
                wsRef.current.onclose = null;
                wsRef.current.close();
            }
        };
    }, [connect]);

    return (
        <WebSocketContext.Provider value={{ isConnected, subscribe, send }}>
            {children}
        </WebSocketContext.Provider>
    );
}

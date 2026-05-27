import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';

const WS_URL = 'ws://127.0.0.1:8000/ws/console';
const RECONNECT_DELAY = 3000;

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

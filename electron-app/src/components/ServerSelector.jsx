import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Plus, Server, Trash2, Play, Settings } from 'lucide-react';
import logo from '../assets/logo2.png';
import { useDialog } from './ui/DialogContext';
import { motion } from 'framer-motion';

export default function ServerSelector({ onSelect, onAdd }) {
    const [servers, setServers] = useState([]);
    const [loading, setLoading] = useState(true);
    const dialog = useDialog();

    useEffect(() => {
        loadServers();
        const interval = setInterval(loadServers, 5000);
        return () => clearInterval(interval);
    }, []);

    const loadServers = async () => {
        try {
            const list = await api.getServers();
            setServers(list);
        } catch (err) {
            console.error("Failed to load servers", err);
        } finally {
            setLoading(false);
        }
    };

    const checkConflict = async () => {
        const activeServer = servers.find(s => s.status && s.status !== 'offline');
        if (activeServer) {
            const result = await dialog.confirm(
                `The server "${activeServer.name}" is currently ${activeServer.status}.\n\nYou must stop it before switching or creating a new server.`,
                "Server Conflict",
                {
                    variant: "warning",
                    confirmLabel: "Stop Server",
                    cancelLabel: "Go Back"
                }
            );
            if (result) {
                try {
                    setLoading(true);
                    // Ensure the active one is selected in backend so stop() works on it
                    await api.selectServer(activeServer.id);
                    await api.stop();
                    dialog.alert(`Stopping "${activeServer.name}"... Please wait for it to turn offline.`, "Stopping", "info");
                } catch (e) {
                    console.error("Stop error", e);
                }
                setLoading(false);
            }
            return true; // Conflict exists
        }
        return false;
    };

    const handleSelect = async (id) => {
        if (await checkConflict()) return;

        try {
            setLoading(true);
            await api.selectServer(id);
            onSelect(id); // Callback to App.jsx to switch view
        } catch (err) {
            console.error("Failed to select server", err);
            await dialog.alert(`Failed to load server: ${err.message}`, "Error", "destructive");
            setLoading(false);
        }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();

        // First confirmation
        if (!await dialog.confirm("Are you sure you want to delete this server profile?", "Delete Server?", "destructive")) return;

        // Second confirmation for file deletion
        const deleteFiles = await dialog.confirm("Do you also want to delete all server files?\n\n⚠️ This will permanently delete the world, config, and all server data!", "Delete Files?", "destructive");

        try {
            await api.deleteServer(id, deleteFiles);
            loadServers();
        } catch (err) {
            console.error("Failed to delete server", err);
            dialog.alert("Failed to delete server via API.", "Error", "destructive");
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="min-h-screen bg-[#050505] text-white flex flex-col p-10 font-sans selection:bg-primary/30 relative overflow-hidden"
        >

            {/* Background Effects */}
            <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-indigo-500/10 rounded-full blur-[120px] animate-pulse"></div>
            <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-purple-500/10 rounded-full blur-[120px] animate-pulse" style={{ animationDelay: '1s' }}></div>
            <div className="absolute top-[30%] left-[30%] w-[40%] h-[40%] bg-cyan-500/5 rounded-full blur-[100px] animate-bounce" style={{ animationDuration: '8s' }}></div>

            {/* Header */}
            <div className="flex items-center justify-between mb-10 relative z-10">
                <div className="flex items-center gap-4">
                    <img src={logo} className="h-12 w-auto opacity-80" alt="Logo" />
                    <h1 className="text-3xl font-bold tracking-tight text-white/90 border-l border-white/10 pl-4">Server Library</h1>
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                    Online
                </div>
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-in fade-in zoom-in duration-300 relative z-10">

                {/* Add New Card */}
                <button
                    onClick={async () => {
                        if (await checkConflict()) return;
                        onAdd();
                    }}
                    className="group relative h-64 rounded-2xl border-2 border-dashed border-white/10 bg-white/5 hover:bg-white/10 hover:border-primary/50 transition-all duration-300 flex flex-col items-center justify-center gap-4 cursor-pointer"
                >
                    <div className="p-4 rounded-full bg-white/5 group-hover:bg-primary/20 group-hover:scale-110 transition-all duration-300 text-gray-400 group-hover:text-primary">
                        <Plus size={32} />
                    </div>
                    <span className="font-medium text-gray-400 group-hover:text-white">Add New Server</span>
                </button>

                {/* Server Cards */}
                {servers.map((server) => (
                    <div
                        key={server.id}
                        className={`group relative h-64 bg-surface/40 backdrop-blur-md border rounded-2xl overflow-hidden transition-all duration-300 flex flex-col
                            ${server.status && server.status !== 'offline'
                                ? 'border-primary shadow-[0_0_30px_rgba(99,102,241,0.15)]'
                                : 'border-white/5 hover:border-primary/30 hover:shadow-[0_0_30px_rgba(99,102,241,0.15)]'}`}
                    >
                        {/* Banner Image Placeholder */}
                        <div className="h-32 w-full bg-gradient-to-br from-gray-800 to-black relative overflow-hidden">
                            <div className="absolute inset-0 bg-primary/10 group-hover:bg-primary/20 transition-colors duration-300"></div>

                            {/* Running Badge */}
                            {server.status && server.status !== 'offline' && (
                                <div className="absolute top-4 left-4 z-20">
                                    <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-lg
                                        ${server.status === 'online' ? 'bg-green-500 text-black' : 'bg-yellow-500 text-black animate-pulse'}`}>
                                        <span className={`w-1.5 h-1.5 rounded-full ${server.status === 'online' ? 'bg-black' : 'bg-black/50'}`}></span>
                                        {server.status}
                                    </span>
                                </div>
                            )}

                            <div className="absolute top-4 right-4">
                                <span className="px-2 py-1 rounded bg-black/50 backdrop-blur text-xs font-mono text-gray-300 border border-white/10">
                                    {server.minecraft_version || 'Latest'}
                                </span>
                            </div>
                        </div>

                        {/* Content */}
                        <div className="p-5 flex flex-col flex-1">
                            <h3 className="text-xl font-bold text-white mb-1 truncate">{server.name || "Minecraft Server"}</h3>
                            <p className="text-sm text-gray-500 mb-4">
                                <span className="capitalize">{server.type || server.server_type || 'Unknown'}</span>
                                {' • '}
                                {server.version || server.minecraft_version || 'Unknown'}
                            </p>

                            <div className="mt-auto flex gap-3">
                                <button
                                    onClick={() => handleSelect(server.id)}
                                    className={`flex-1 font-bold py-2 rounded-lg transition-all flex items-center justify-center gap-2
                                        ${server.status && server.status !== 'offline'
                                            ? 'bg-primary text-white shadow-[0_0_15px_rgba(99,102,241,0.4)] hover:scale-105'
                                            : 'bg-white text-black hover:bg-gray-200'}`}
                                >
                                    <Play size={16} fill="currentColor" />
                                    {server.status && server.status !== 'offline' ? 'Manage' : 'Play'}
                                </button>
                                <button
                                    onClick={(e) => handleDelete(server.id, e)}
                                    className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                    title="Delete Server"
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            <div className="mt-auto pt-10 flex justify-center text-sm text-gray-500 relative z-10">
                <span className="flex items-center gap-1">
                    Made by <a href="https://github.com/CalaKuad1" target="_blank" rel="noreferrer" className="text-white hover:text-primary transition-colors font-medium">CalaKuad1</a>
                </span>
            </div>
        </motion.div>
    );
}

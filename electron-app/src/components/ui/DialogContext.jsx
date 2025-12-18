import React, { createContext, useContext, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertTriangle, CheckCircle, Info } from 'lucide-react';

const DialogContext = createContext();

export const useDialog = () => useContext(DialogContext);

export const DialogProvider = ({ children }) => {
    const [dialogs, setDialogs] = useState([]);

    // Helper to add a dialog and return a promise that resolves when it closes
    const addDialog = (type, options) => {
        return new Promise((resolve) => {
            const id = Math.random().toString(36).substr(2, 9);
            setDialogs(prev => [...prev, {
                id,
                type,
                ...options,
                onClose: (result) => {
                    setDialogs(curr => curr.filter(d => d.id !== id));
                    resolve(result);
                }
            }]);
        });
    };

    const alert = (message, title = "Alert", variant = "info") => {
        return addDialog('alert', { message, title, variant });
    };

    const confirm = (message, title = "Confirm", variant = "warning") => {
        return addDialog('confirm', { message, title, variant });
    };

    return (
        <DialogContext.Provider value={{ alert, confirm }}>
            {children}
            <div className="fixed inset-0 z-[9999] pointer-events-none flex items-center justify-center">
                <AnimatePresence>
                    {dialogs.map((dialog) => (
                        <div key={dialog.id} className="absolute inset-0 flex items-center justify-center pointer-events-auto">
                            {/* Backdrop */}
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                                onClick={() => dialog.type === 'alert' && dialog.onClose(true)}
                            />

                            {/* Modal */}
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95, y: 10 }}
                                transition={{ duration: 0.2 }}
                                className="bg-[#0f0f0f] border border-white/10 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden relative z-10 mx-4"
                            >
                                {/* Header */}
                                <div className="p-6 pb-2">
                                    <div className="flex items-start gap-4">
                                        <div className={`p-3 rounded-xl bg-opacity-10 
                                            ${dialog.variant === 'warning' || dialog.variant === 'destructive' ? 'bg-red-500 text-red-500' :
                                                dialog.variant === 'success' ? 'bg-green-500 text-green-500' :
                                                    'bg-blue-500 text-primary'}`}>
                                            {dialog.variant === 'warning' || dialog.variant === 'destructive' ? <AlertTriangle size={24} /> :
                                                dialog.variant === 'success' ? <CheckCircle size={24} /> :
                                                    <Info size={24} />}
                                        </div>
                                        <div className="flex-1">
                                            <h3 className="text-lg font-bold text-white">{dialog.title}</h3>
                                            <div className="mt-2 text-gray-400 text-sm leading-relaxed whitespace-pre-wrap">
                                                {dialog.message}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Footer */}
                                <div className="p-4 bg-white/5 flex justify-end gap-3 mt-4">
                                    {dialog.type === 'confirm' && (
                                        <button
                                            onClick={() => dialog.onClose(false)}
                                            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                                        >
                                            Cancel
                                        </button>
                                    )}
                                    <button
                                        onClick={() => dialog.onClose(true)}
                                        className={`px-6 py-2 rounded-lg text-sm font-bold text-white transition-all shadow-lg hover:shadow-primary/20
                                            ${dialog.variant === 'destructive' ? 'bg-red-600 hover:bg-red-500' : 'bg-primary hover:bg-primary/80'}`}
                                    >
                                        {dialog.type === 'confirm' ? 'Confirm' : 'Okay'}
                                    </button>
                                </div>
                            </motion.div>
                        </div>
                    ))}
                </AnimatePresence>
            </div>
        </DialogContext.Provider>
    );
};

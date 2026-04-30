import React, { createContext, useContext, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertTriangle, CheckCircle, Info } from './PixelIcons';

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

    const alert = (message, titleOrOptions = "Alert", variant = "info") => {
        const options = typeof titleOrOptions === 'object'
            ? { message, ...titleOrOptions }
            : { message, title: titleOrOptions, variant };
        return addDialog('alert', options);
    };

    const confirm = (message, titleOrOptions = "Confirm", variantOrOptions = "warning") => {
        let options = { message };

        if (typeof titleOrOptions === 'object') {
            options = { ...options, ...titleOrOptions };
        } else {
            options.title = titleOrOptions;
            if (typeof variantOrOptions === 'object') {
                options = { ...options, ...variantOrOptions };
            } else {
                options.variant = variantOrOptions;
            }
        }

        return addDialog('confirm', options);
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
                                initial={{ opacity: 0, scale: 0.98, y: 10 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.98, y: 10 }}
                                transition={{ duration: 0.2 }}
                                className="bg-[#18181b]/80 border border-white/10 rounded-sm w-full max-w-md shadow-2xl overflow-hidden relative z-10 mx-4 backdrop-blur-2xl"
                            >
                                {/* Header */}
                                <div className="p-8 pb-2">
                                    <div className="flex items-start gap-4">
                                        <div className={`mt-0.5
                                            ${dialog.variant === 'warning' || dialog.variant === 'destructive' ? 'text-red-500' :
                                                dialog.variant === 'success' ? 'text-emerald-500' :
                                                    'text-white'}`}>
                                            {dialog.variant === 'warning' || dialog.variant === 'destructive' ? <AlertTriangle size={24} /> :
                                                dialog.variant === 'success' ? <CheckCircle size={24} /> :
                                                    <Info size={24} />}
                                        </div>
                                        <div className="flex-1">
                                            <h3 className="text-xl font-minecraft tracking-widest text-white uppercase">{dialog.title}</h3>
                                            <div className="mt-3 text-zinc-400 text-xs font-medium leading-relaxed whitespace-pre-wrap uppercase tracking-wider">
                                                {dialog.message}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Footer */}
                                <div className="p-6 bg-transparent flex justify-end gap-3 mt-4 border-t border-white/5">
                                    {(dialog.type === 'confirm') && (
                                        <button
                                            onClick={() => dialog.onClose(false)}
                                            className="px-6 py-2 rounded-sm text-[10px] font-minecraft tracking-widest uppercase text-zinc-500 border border-white/5 hover:border-white/10 hover:text-white hover:bg-white/5 transition-all"
                                        >
                                            {dialog.cancelLabel || 'Cancel'}
                                        </button>
                                    )}
                                    <button
                                        onClick={() => dialog.onClose(true)}
                                        className={`px-8 py-2 rounded-sm text-[10px] font-minecraft tracking-widest uppercase transition-all shadow-lg hover:opacity-90 border
                                            ${dialog.variant === 'destructive' ? 'bg-transparent border-red-500/50 text-red-500 hover:bg-red-500/10' :
                                                dialog.variant === 'warning' ? 'bg-transparent border-yellow-500/50 text-yellow-500 hover:bg-yellow-500/10' :
                                                    'bg-white border-white text-black'}`}
                                    >
                                        {dialog.type === 'confirm' ? (dialog.confirmLabel || 'Confirm') : (dialog.confirmLabel || 'Okay')}
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

import { createContext, useContext } from 'react';

export const ToastContext = createContext(null);

// const toast = useToast(); toast.success('Saved'); toast.error('Could not save', { title: 'Settings' })
// Non-blocking feedback. Use dialog.confirm for decisions the user must make.
export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used within a ToastProvider');
    return ctx;
}

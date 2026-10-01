import React, { createContext, useContext, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { AlertTriangle, CheckCircle, Info } from './PixelIcons';
import { Modal } from './Modal';
import { Button } from './Button';
import { useTranslation } from '../../contexts/LanguageContext';

const DialogContext = createContext();

export const useDialog = () => useContext(DialogContext);

const VARIANT_ICON = {
    warning: { icon: AlertTriangle, color: 'text-gold' },
    destructive: { icon: AlertTriangle, color: 'text-redstone' },
    success: { icon: CheckCircle, color: 'text-grass-lit' },
    info: { icon: Info, color: 'text-diamond' },
};

export const DialogProvider = ({ children }) => {
    const { t } = useTranslation();
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

    // Blocking dialogs are for decisions. For plain feedback ("saved", "failed")
    // prefer the non-blocking toast from useToast().
    const alert = (message, titleOrOptions = undefined, variant = "info") => {
        const options = typeof titleOrOptions === 'object'
            ? { message, ...titleOrOptions }
            : { message, title: titleOrOptions, variant };
        return addDialog('alert', options);
    };

    const confirm = (message, titleOrOptions = undefined, variantOrOptions = "warning") => {
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
            <AnimatePresence>
                {dialogs.map((dialog) => {
                    const isConfirm = dialog.type === 'confirm';
                    const isDestructive = dialog.variant === 'destructive';
                    const { icon, color } = VARIANT_ICON[dialog.variant] || VARIANT_ICON.info;
                    // Escape / backdrop = the safe answer: dismiss an alert, cancel a confirm.
                    const dismiss = () => dialog.onClose(isConfirm ? false : true);
                    // Destructive or three-way decisions start on Cancel, so Enter is never the dangerous key.
                    const cancelFirst = isConfirm && (isDestructive || dialog.dangerLabel);
                    return (
                        <Modal
                            key={dialog.id}
                            size="md"
                            zIndex={9999}
                            icon={icon}
                            iconClassName={color}
                            title={dialog.title || (isConfirm ? t('common.confirm') : (isDestructive ? t('common.error') : undefined))}
                            description={dialog.message}
                            onClose={dismiss}
                            footer={
                                <>
                                    {isConfirm && (
                                        <Button variant="ghost" onClick={() => dialog.onClose(false)} data-autofocus={cancelFirst ? '' : undefined}>
                                            {dialog.cancelLabel || t('common.cancel')}
                                        </Button>
                                    )}
                                    {isConfirm && dialog.dangerLabel && (
                                        <Button variant="danger" onClick={() => dialog.onClose('danger')}>
                                            {dialog.dangerLabel}
                                        </Button>
                                    )}
                                    <Button
                                        variant={isDestructive ? 'danger' : 'primary'}
                                        onClick={() => dialog.onClose(true)}
                                        data-autofocus={cancelFirst ? undefined : ''}
                                    >
                                        {dialog.confirmLabel || (isConfirm ? t('common.confirm') : t('common.ok'))}
                                    </Button>
                                </>
                            }
                        />
                    );
                })}
            </AnimatePresence>
        </DialogContext.Provider>
    );
};

import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api';

import en from '../i18n/locales/en.json';
import es from '../i18n/locales/es.json';
import fr from '../i18n/locales/fr.json';
import ru from '../i18n/locales/ru.json';

// Helper to handle potential .default property from Vite JSON imports
const getTranslations = (obj) => obj?.default || obj;

const translations = {
    en: getTranslations(en),
    es: getTranslations(es),
    fr: getTranslations(fr),
    ru: getTranslations(ru)
};

const LanguageContext = createContext();

export const LanguageProvider = ({ children }) => {
    const [locale, setLocale] = useState('en');

    console.log(`[i18n] LanguageProvider render. Current locale: ${locale}`);

    useEffect(() => {
        // Load initial language from app settings
        api.getAppSettings().then(settings => {
            if (settings && settings.language) {
                console.log(`[i18n] Initializing with: ${settings.language}`);
                if (translations[settings.language]) {
                    setLocale(settings.language);
                }
            }
        }).catch(err => console.error("[i18n] Failed to load initial settings", err));
    }, []);

    const t = (key) => {
        if (!key) return '';
        const keys = key.split('.');
        let value = translations[locale] || translations['en'];
        
        for (const k of keys) {
            if (value && typeof value === 'object' && value[k] !== undefined) {
                value = value[k];
            } else {
                // Fallback to English for this specific key
                let fallback = translations['en'];
                for (const fk of keys) {
                    if (fallback && typeof fallback === 'object' && fallback[fk] !== undefined) {
                        fallback = fallback[fk];
                    } else {
                        return key; 
                    }
                }
                return fallback;
            }
        }
        return value;
    };

    const changeLanguage = (newLocale) => {
        if (translations[newLocale]) {
            console.log(`[i18n] State updated to: ${newLocale}`);
            setLocale(newLocale);
        } else {
            console.warn(`[i18n] Unsupported locale attempt: ${newLocale}`);
        }
    };

    return (
        <LanguageContext.Provider value={{ locale, t, changeLanguage }}>
            {children}
        </LanguageContext.Provider>
    );
};

export const useTranslation = () => {
    const context = useContext(LanguageContext);
    if (!context) {
        throw new Error('useTranslation must be used within a LanguageProvider');
    }
    return context;
};

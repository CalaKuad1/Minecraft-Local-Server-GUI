import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MotionConfig } from 'framer-motion'
import '@fontsource-variable/figtree'
import '@fontsource-variable/fredoka'
import '@fontsource-variable/outfit'
import './index.css'
import App from './App.jsx'
import StartupSplash from './components/StartupSplash'
import ErrorBoundary from './components/ui/ErrorBoundary'
import { DialogProvider } from './components/ui/DialogContext'
import { ToastProvider } from './components/ui/Toast'
import { LanguageProvider } from './contexts/LanguageContext'
import { WebSocketProvider } from './contexts/WebSocketContext'
import { applyPerfMode, getPerfMode } from './utils/perfMode'

// Before the first paint, so "lite" doesn't flash the blurred version.
applyPerfMode(getPerfMode());

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <MotionConfig reducedMotion="user">
        <LanguageProvider>
          <WebSocketProvider>
            <ToastProvider>
              <DialogProvider>
                <App />
                <StartupSplash />
              </DialogProvider>
            </ToastProvider>
          </WebSocketProvider>
        </LanguageProvider>
      </MotionConfig>
    </ErrorBoundary>
  </StrictMode>,
)

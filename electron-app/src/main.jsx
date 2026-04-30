import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './components/ui/ErrorBoundary'
import { DialogProvider } from './components/ui/DialogContext'
import { LanguageProvider } from './contexts/LanguageContext'
import { WebSocketProvider } from './contexts/WebSocketContext'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <LanguageProvider>
        <WebSocketProvider>
          <DialogProvider>
            <App />
          </DialogProvider>
        </WebSocketProvider>
      </LanguageProvider>
    </ErrorBoundary>
  </StrictMode>,
)

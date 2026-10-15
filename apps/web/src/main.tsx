import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { registerSW } from 'virtual:pwa-register'
import './index.css'
import { I18nProvider } from './i18n'
import { AuthProvider } from './state/auth'
import { ServerTimeProvider } from './state/servertime'
import { LiveProvider } from './state/live'
import { ToastProvider } from './state/toast'
import App from './App'

registerSW({ immediate: true })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <BrowserRouter>
        <AuthProvider>
          <ServerTimeProvider>
            <ToastProvider>
              <LiveProvider>
                <App />
              </LiveProvider>
            </ToastProvider>
          </ServerTimeProvider>
        </AuthProvider>
      </BrowserRouter>
    </I18nProvider>
  </StrictMode>,
)

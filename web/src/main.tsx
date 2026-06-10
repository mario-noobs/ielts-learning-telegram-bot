import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './lib/i18n'
import App from './App'
import { ToastProvider } from './components/ui'
import { initTheme } from './lib/theme'

initTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Suspense fallback={null}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </Suspense>
  </StrictMode>,
)

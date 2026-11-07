import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles/index.css'

// Detect HA Ingress base path (e.g. /api/hassio_ingress/xxx)
const base = window.location.pathname.replace(/\/app.*$/, '') || '/'

// Register the offline service worker (controls the Ingress base path)
if ('serviceWorker' in navigator) {
  const swBase = window.location.pathname.replace(/\/react.*$/, '') || ''
  navigator.serviceWorker.register(swBase + '/offline-sw.js', { scope: swBase + '/' }).catch(() => {})
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter basename={base}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)

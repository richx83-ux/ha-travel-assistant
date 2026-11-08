import React, { useEffect, useState } from 'react'
import { listTrips, getTrip, putTrip, deleteTrip, saveTripForOffline } from '../offlineDb'


function OfflineTimer({ startedAt }) {
  const [elapsed, setElapsed] = React.useState('00:00')
  React.useEffect(() => {
    if (!startedAt) return
    const start = new Date(startedAt).getTime()
    const tick = () => {
      const secs = Math.max(0, Math.floor((Date.now() - start) / 1000))
      const h = Math.floor(secs / 3600)
      const m = String(Math.floor((secs % 3600) / 60)).padStart(2, '0')
      const s = String(secs % 60).padStart(2, '0')
      setElapsed(h ? h + ':' + m + ':' + s : m + ':' + s)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [startedAt])
  return <div className="text-3xl font-semibold tabular-nums">{elapsed}</div>
}

function StopCard({ stop }) {
  const initial = (stop.name || '?')[0]
  return (
    <div className="flex items-center gap-3">
      <div className="w-12 h-12 rounded-xl bg-teal-700 text-white flex items-center justify-center text-lg font-semibold flex-shrink-0">{initial}</div>
      <div className="min-w-0">
        <div className="font-semibold truncate">{stop.name}</div>
        {stop.city && <div className="text-sm text-slate-500 truncate">{stop.city}</div>}
        {stop.is_accommodation && <div className="text-xs text-slate-400">Stay</div>}
      </div>
    </div>
  )
}

function basePath() {
  return window.location.pathname.replace(/\/react.*$/, '') || ''
}

export default function OfflineApp() {
  const [trips, setTrips] = useState([])
  const [active, setActive] = useState(null)
  const [photo, setPhoto] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState('')
  const [online, setOnline] = useState(navigator.onLine)
  const [installEvent, setInstallEvent] = useState(null)
  const [showSetup, setShowSetup] = useState(false)
  const [serverTrips, setServerTrips] = useState([])
  const [savingId, setSavingId] = useState(null)
  const [needsLogin, setNeedsLogin] = useState(false)
  const [swStatus, setSwStatus] = useState('checking')

  const refresh = () => listTrips().then((rows) => setTrips(rows.sort((a, b) => (a.start_date || '').localeCompare(b.start_date || ''))))

  useEffect(() => {
    refresh()
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    const onPrompt = (e) => { e.preventDefault(); setInstallEvent(e) }
    window.addEventListener('beforeinstallprompt', onPrompt)

    // Register here as well so the offline page owns its service worker
    if ('serviceWorker' in navigator) {
      const swUrl = basePath() + '/offline-sw.js'
      navigator.serviceWorker.register(swUrl, { scope: basePath() + '/' })
        .then((reg) => {
          setSwStatus(navigator.serviceWorker.controller ? 'active' : 'installed')
          reg.addEventListener('updatefound', () => setSwStatus('updating'))
          return navigator.serviceWorker.ready
        })
        .then(() => setSwStatus(navigator.serviceWorker.controller ? 'active' : 'ready'))
        .catch((e) => setSwStatus('failed: ' + (e && e.message ? e.message : 'error')))
    } else {
      setSwStatus('unsupported')
    }

    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
      window.removeEventListener('beforeinstallprompt', onPrompt)
    }
  }, [])


  useEffect(() => {
    if (!showSetup || !online) return
    fetch(basePath() + '/api/trips', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : { trips: [] })
      .then((d) => setServerTrips(d.trips || []))
      .catch(() => setServerTrips([]))
  }, [showSetup, online])

  const saveFromServer = async (trip) => {
    setSavingId(trip.id)
    setMsg('')
    try {
      await saveTripForOffline(trip.id, basePath())
      setMsg(trip.name + ' saved on this phone')
      refresh()
    } catch (e) {
      setMsg('Could not save ' + trip.name + (e && e.message ? ': ' + e.message : ''))
    }
    setSavingId(null)
  }

  const cacheShell = async () => {
    setMsg('Caching…')
    try {
      if (!('serviceWorker' in navigator)) throw new Error('No service worker')
      const reg = await navigator.serviceWorker.ready
      const sw = reg.active || navigator.serviceWorker.controller
      if (!sw) throw new Error('Service worker not active yet — reload once online')
      const urls = [window.location.href]
      document.querySelectorAll('script[src],link[rel="stylesheet"]').forEach((el) => {
        const u = el.src || el.href
        if (u) urls.push(u)
      })
      sw.postMessage({ type: 'CACHE_URLS', urls })
      setMsg('Cached for offline. You can try airplane mode now.')
      setSwStatus('active')
    } catch (e) {
      setMsg(e.message || 'Cache failed')
    }
  }

  // ... rest of the component continues with the updated install text ...
  // (truncated in this example for brevity; full content will be used)

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

  const openTrip = async (id) => {
    const t = await getTrip(id)
    setActive(t)
    setPhoto(null)
    setMsg('')
  }

  const updateStop = async (id, patch) => {
    if (!active) return
    const stops = active.stops.map((s) => s.id === id ? { ...s, ...patch } : s)
    const updated = { ...active, stops }
    await putTrip(updated)
    setActive(updated)
    refresh()
    return updated
  }

  const incomplete = active ? (active.stops || []).filter((s) => !s.done) : []
  const currentDay = incomplete.length ? incomplete[0].day_number : (active && active.stops.length ? active.stops[active.stops.length - 1].day_number : 1)
  const dayStops = active ? (active.stops || []).filter((s) => s.day_number === currentDay) : []
  const totalDays = active ? Math.max(1, ...((active.stops || []).map((s) => s.day_number || 1))) : 1
  const visiting = dayStops.find((s) => s.arrivedAt && !s.done) || null
  const nextStop = dayStops.find((s) => !s.done && !s.arrivedAt) || null
  const upcoming = visiting ? nextStop : (nextStop || dayStops.find((s) => !s.done))

  const arrive = async (stop) => {
    setPhoto(null)
    await updateStop(stop.id, { arrivedAt: new Date().toISOString() })
    setMsg('')
  }
  const skipStop = async (stop) => {
    await updateStop(stop.id, { done: true, skipped: true, synced: false, doneAt: new Date().toISOString() })
    setMsg('Skipped')
  }
  const depart = async () => {
    if (!visiting) return
    await updateStop(visiting.id, {
      done: true,
      doneAt: new Date().toISOString(),
      photo: photo || visiting.photo || null,
      synced: false,
    })
    setPhoto(null)
    setMsg('Saved on this phone')
  }

  const postJson = async (url) => {
    const res = await fetch(url, { method: 'POST', credentials: 'include', redirect: 'manual' })
    return res
  }

  const isAuthFail = (res) => !res || res.status === 401 || res.status === 403 || res.type === 'opaqueredirect' || (res.status >= 300 && res.status < 400)

  const sync = async () => {
    if (!active) return
    const pendingStops = (active.stops || []).filter((s) => s.done && s.synced === false)
    if (!pendingStops.length) {
      setMsg('Nothing to sync')
      return
    }
    setSyncing(true)
    setMsg('Syncing…')
    const base = basePath()
    let ok = 0
    let fail = 0
    let unauth = false
    let detail = ''
    // Make sure the trip is active so stop updates are accepted
    try { await postJson(base + '/api/trips/' + active.id + '/start') } catch (e) {}
    const stops = []
    for (const s of active.stops) {
      if (!(s.done && s.synced === false)) { stops.push(s); continue }
      try {
        if (s.photo) {
          const fd = new FormData()
          const file = new File([s.photo], 'visit.jpg', { type: s.photo.type || 'image/jpeg' })
          fd.append('file', file)
          const pr = await fetch(base + '/api/trips/' + active.id + '/stop/' + s.id + '/photo', { method: 'POST', body: fd, credentials: 'include', redirect: 'manual' })
          if (isAuthFail(pr)) { unauth = true; throw new Error('auth') }
          if (!pr.ok) { detail = 'photo ' + pr.status; throw new Error('photo') }
        }
        const ar = await postJson(base + '/api/trips/' + active.id + '/stop/' + s.id + '/arrive')
        if (isAuthFail(ar)) { unauth = true; throw new Error('auth') }
        if (ar && !ar.ok && ar.status) { detail = 'arrive ' + ar.status; throw new Error('arrive') }
        const lr = await postJson(base + '/api/trips/' + active.id + '/stop/' + s.id + '/leave')
        if (isAuthFail(lr)) { unauth = true; throw new Error('auth') }
        if (!lr || !lr.ok) { detail = 'leave ' + (lr ? lr.status : 'no response'); throw new Error('leave') }
        stops.push({ ...s, synced: true })
        ok++
      } catch (e) {
        stops.push(s)
        fail++
      }
    }
    const updated = { ...active, stops }
    await putTrip(updated)
    setActive(updated)
    setSyncing(false)
    if (unauth) {
      setNeedsLogin(true)
      setMsg('This shortcut cannot stay logged in. Open Travel Assistant from Home Assistant and tap Sync visits.')
    } else if (fail) {
      setMsg('Synced ' + ok + ', ' + fail + ' failed' + (detail ? ' (' + detail + ')' : ''))
    } else {
      setMsg('Synced ' + ok + ' stop' + (ok === 1 ? '' : 's'))
    }
    refresh()
  }

  const install = async () => {
    if (!installEvent) return
    installEvent.prompt()
    await installEvent.userChoice
    setInstallEvent(null)
  }

  const pending = active ? active.stops.filter((s) => s.done && s.synced === false).length : 0

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <header className="sticky top-0 z-10 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 py-3 flex items-center justify-between gap-3">
        <div className="font-semibold">Travel Assistant</div>
        <div className="flex items-center gap-2">
          <span className={'px-2.5 py-1 rounded-full text-xs font-medium ' + (online ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-200' : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200')}>
            {online ? 'Online' : 'Offline'}
          </span>
          {pending > 0 && <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800">{pending} to sync</span>}
          {online && (
            <a href={window.location.origin + '/'} className="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-900 text-white dark:bg-white dark:text-slate-900">Log in</a>
          )}
          {active && (
            <button onClick={() => setActive(null)} className="text-sm px-3 py-1 rounded-lg border">Trips</button>
          )}
          <button onClick={() => setShowSetup((v) => !v)} className="p-2 rounded-lg border" title="Setup" aria-label="Setup">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </header>

      {showSetup && (() => {
        const installUrl = window.location.origin + basePath() + '/react?offline=1'
        const inFrame = window.top !== window.self
        const openInstall = () => { window.top.location.href = installUrl }
        const copy = () => navigator.clipboard && navigator.clipboard.writeText(installUrl).then(() => setMsg('Install link copied'))
        return (
          <div className="mx-4 mt-3 p-3 rounded-xl bg-teal-50 dark:bg-teal-900/30 border border-teal-200 dark:border-teal-800 space-y-2">
            <div className="text-sm font-medium">Pin Travel Assistant (Offline)</div>
            <div className="text-xs text-slate-600 dark:text-slate-300">
              Home Assistant embeds this page, so Add to Home screen would pin HA. Open the direct link first, then use Chrome’s menu → Add to Home screen.
            </div>
            <div className="text-xs break-all font-mono bg-white/70 dark:bg-slate-900/50 rounded p-2">{installUrl}</div>
            <div className="flex gap-2 flex-wrap">
              <button onClick={openInstall} className="px-3 py-1.5 rounded-lg bg-teal-700 text-white text-sm">Open install page</button>
              <button onClick={copy} className="px-3 py-1.5 rounded-lg border text-sm">Copy link</button>
              <button onClick={cacheShell} className="px-3 py-1.5 rounded-lg border text-sm">Cache for offline</button>
              {installEvent && <button onClick={install} className="px-3 py-1.5 rounded-lg border text-sm">Install</button>}
            </div>
            <div className="text-xs text-slate-500">Service worker: {swStatus}. Open this page once online, tap Cache for offline, then test airplane mode.</div>
            {inFrame && <div className="text-xs text-amber-700">You are inside Home Assistant. Use Open install page so the address bar is this app.</div>}
            <div className="pt-2 border-t border-teal-200 dark:border-teal-800">
              <div className="text-sm font-medium">Download a trip</div>
              <div className="text-xs text-slate-600 dark:text-slate-300 mb-2">Save a trip from Home Assistant onto this phone.</div>
              {!online && <div className="text-xs text-slate-500">Connect and log in to Home Assistant to download a trip.</div>}
              {online && serverTrips.length === 0 && <div className="text-xs text-slate-500">No trips found. Log in to Home Assistant if this list is empty.</div>}
              <div className="space-y-2">
                {serverTrips.filter((t) => t.status !== 'completed').map((t) => {
                  const already = trips.some((x) => String(x.id) === String(t.id))
                  return (
                    <div key={t.id} className="flex items-center justify-between gap-2 bg-white/70 dark:bg-slate-900/40 rounded-lg px-2 py-1.5">
                      <div className="min-w-0">
                        <div className="text-sm truncate">{t.name}</div>
                        <div className="text-xs text-slate-500">{t.start_date || ''}{already ? ' · on this phone' : ''}</div>
                      </div>
                      <button onClick={() => saveFromServer(t)} disabled={savingId === t.id} className="px-2 py-1 rounded-lg bg-teal-700 text-white text-xs disabled:opacity-50">
                        {already ? 'Update' : 'Save'}
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )
      })()}

      <div className="max-w-lg mx-auto p-4 space-y-3">
        {!active && (
          <>
            <p className="text-sm text-slate-500">Trips saved on this phone. Open one to record visits and move to the next stop without Home Assistant.</p>
            {trips.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-6 text-center text-sm text-slate-500">
                No trips saved yet. In the main app, open a trip and choose Save for offline.
              </div>
            )}
            {trips.map((t) => {
              const left = (t.stops || []).filter((s) => !s.done).length
              const unsynced = (t.stops || []).filter((s) => s.done && s.synced === false).length
              return (
                <button key={t.id} onClick={() => openTrip(t.id)} className="w-full text-left bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
                  <div className="font-medium">{t.name}</div>
                  <div className="text-xs text-slate-500 mt-1">{t.start_date}{t.end_date ? ' → ' + t.end_date : ''}</div>
                  <div className="text-xs text-slate-500 mt-1">{left} stop{left === 1 ? '' : 's'} left{unsynced ? ' · ' + unsynced + ' to sync' : ''}</div>
                </button>
              )
            })}
          </>
        )}

        {active && (
          <>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold">{active.name}</div>
                <div className="text-xs text-slate-500">Day {currentDay} of {totalDays}</div>
              </div>
              <button onClick={sync} disabled={!online || syncing || pending === 0} className="px-3 py-1.5 rounded-lg bg-teal-700 text-white text-sm disabled:opacity-40">
                {syncing ? 'Syncing…' : 'Sync'}
              </button>
            </div>
            {msg && (
              <div className="text-sm text-slate-600 dark:text-slate-300 space-y-2">
                <div>{msg}</div>
                {needsLogin && (
                  <a href={window.location.origin + '/'} className="inline-block px-3 py-1.5 rounded-lg bg-teal-700 text-white text-sm">Open Home Assistant</a>
                )}
              </div>
            )}

            {visiting && (
              <>
                <div className="text-sm font-medium text-slate-500">Currently visiting</div>
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3">
                  <StopCard stop={visiting} />
                  <OfflineTimer startedAt={visiting.arrivedAt} />
                  <label className="block">
                    <span className="text-sm text-slate-500">Visit photo</span>
                    <input type="file" accept="image/*" capture="environment" className="mt-1 block w-full text-sm" onChange={(e) => setPhoto(e.target.files && e.target.files[0] ? e.target.files[0] : null)} />
                  </label>
                  {(photo || visiting.photo) && <div className="text-xs text-slate-500">Photo ready</div>}
                  <button onClick={depart} className="px-4 py-2 rounded-lg bg-teal-700 text-white text-sm font-medium">Ready to depart</button>
                </div>
              </>
            )}

            <div className="text-sm font-medium text-slate-500">Next stop</div>
            {upcoming ? (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3">
                <StopCard stop={upcoming} />
                <div className="flex flex-wrap gap-2">
                  {upcoming.lat && upcoming.lon && (
                    <a href={'https://www.google.com/maps/dir/?api=1&destination=' + upcoming.lat + ',' + upcoming.lon + '&travelmode=driving'} target="_blank" rel="noreferrer" className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-sm font-medium rounded-lg">Open directions</a>
                  )}
                  <button type="button" onClick={() => {
                    const name = upcoming.name || 'Destination'
                    const isHome = name.trim().toLowerCase() === 'home'
                    const postcode = (isHome ? (active.home_postcode || upcoming.postcode) : upcoming.postcode) || ''
                    const text = postcode ? name + '\n' + postcode : name
                    if (navigator.share) navigator.share({ title: name, text }).catch(() => {})
                    else {
                      const intent = 'intent:#Intent;action=android.intent.action.SEND;type=text/plain;S.android.intent.extra.TEXT=' + encodeURIComponent(text) + ';S.android.intent.extra.SUBJECT=' + encodeURIComponent(name) + ';end'
                      window.location.href = intent
                    }
                  }} className="inline-flex items-center gap-2 px-4 py-2 border border-slate-300 dark:border-slate-600 text-sm font-medium rounded-lg bg-white dark:bg-slate-900">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                    </svg>
                    Share
                  </button>
                  {!visiting && (
                    <>
                      <button onClick={() => arrive(upcoming)} className="px-4 py-2 rounded-lg bg-teal-700 text-white text-sm font-medium">Arrived</button>
                      <button onClick={() => skipStop(upcoming)} className="px-4 py-2 rounded-lg border text-sm">Skip</button>
                    </>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 text-sm text-slate-500 text-center">
                {incomplete.length ? 'Day complete. Next day starts when you arrive at the next stop.' : 'All stops done. Sync from Travel Assistant in Home Assistant.'}
              </div>
            )}

            {!!dayStops.filter((s) => s.done).length && (
              <>
                <div className="text-sm font-medium text-slate-500">Done today</div>
                {dayStops.filter((s) => s.done).map((s) => (
                  <div key={s.id} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 opacity-60">
                    <StopCard stop={s} />
                    <div className="text-xs text-slate-500 mt-1">{s.skipped ? 'Skipped' : 'Done'}</div>
                  </div>
                ))}
              </>
            )}

            <button onClick={async () => {
              if (!confirm('Remove ' + active.name + ' from this phone? Photos not yet synced will be lost.')) return
              await deleteTrip(active.id)
              setActive(null)
              refresh()
            }} className="text-sm text-red-500">Remove from this phone</button>
          </>
        )}
      </div>
    </div>
  )
}

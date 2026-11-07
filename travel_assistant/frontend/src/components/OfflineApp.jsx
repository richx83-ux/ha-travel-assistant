import { useEffect, useState } from 'react'
import { listTrips, getTrip, putTrip, deleteTrip } from '../offlineDb'

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

  const refresh = () => listTrips().then((rows) => setTrips(rows.sort((a, b) => (a.start_date || '').localeCompare(b.start_date || ''))))

  useEffect(() => {
    refresh()
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    const onPrompt = (e) => { e.preventDefault(); setInstallEvent(e) }
    window.addEventListener('beforeinstallprompt', onPrompt)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
      window.removeEventListener('beforeinstallprompt', onPrompt)
    }
  }, [])

  const openTrip = async (id) => {
    const t = await getTrip(id)
    setActive(t)
    setPhoto(null)
    setMsg('')
  }

  const nextStop = active ? (active.stops || []).find((s) => !s.done) : null

  const markDone = async () => {
    if (!active || !nextStop) return
    const stops = active.stops.map((s) => s.id === nextStop.id
      ? { ...s, done: true, doneAt: new Date().toISOString(), photo: photo || s.photo, synced: false }
      : s)
    const updated = { ...active, stops }
    await putTrip(updated)
    setActive(updated)
    setPhoto(null)
    setMsg('Saved on this phone')
    refresh()
  }

  const sync = async () => {
    if (!active) return
    setSyncing(true)
    setMsg('')
    const base = basePath()
    let ok = 0
    let fail = 0
    const stops = []
    for (const s of active.stops) {
      if (s.done && s.synced === false) {
        try {
          if (s.photo) {
            const fd = new FormData()
            const file = new File([s.photo], 'visit.jpg', { type: s.photo.type || 'image/jpeg' })
            fd.append('file', file)
            const pr = await fetch(base + '/api/trips/' + active.id + '/stop/' + s.id + '/photo', { method: 'POST', body: fd })
            if (!pr.ok) throw new Error('photo')
          }
          await fetch(base + '/api/trips/' + active.id + '/stop/' + s.id + '/arrive', { method: 'POST' })
          const lr = await fetch(base + '/api/trips/' + active.id + '/stop/' + s.id + '/leave', { method: 'POST' })
          if (!lr.ok) throw new Error('leave')
          stops.push({ ...s, synced: true })
          ok++
        } catch (e) {
          stops.push(s)
          fail++
        }
      } else {
        stops.push(s)
      }
    }
    const updated = { ...active, stops }
    await putTrip(updated)
    setActive(updated)
    setSyncing(false)
    setMsg(fail ? ('Synced ' + ok + ', ' + fail + ' failed') : ('Synced ' + ok + ' stop' + (ok === 1 ? '' : 's')))
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
      <header className="sticky top-0 z-10 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 py-3 flex items-center justify-between">
        <div>
          <div className="font-semibold">Travel Assistant (Offline)</div>
          <div className="text-xs text-slate-500">{online ? 'Online' : 'Offline'}{pending ? ' · ' + pending + ' to sync' : ''}</div>
        </div>
        {active && (
          <button onClick={() => setActive(null)} className="text-sm px-3 py-1 rounded-lg border">Trips</button>
        )}
      </header>

      {(() => {
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
              {installEvent && <button onClick={install} className="px-3 py-1.5 rounded-lg border text-sm">Install</button>}
            </div>
            {inFrame && <div className="text-xs text-amber-700">You are inside Home Assistant. Use Open install page so the address bar is this app.</div>}
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
                <div className="text-xs text-slate-500">{(active.stops || []).filter((s) => s.done).length} / {(active.stops || []).length} done</div>
              </div>
              <button onClick={sync} disabled={!online || syncing || pending === 0} className="px-3 py-1.5 rounded-lg bg-teal-700 text-white text-sm disabled:opacity-40">
                {syncing ? 'Syncing…' : 'Sync'}
              </button>
            </div>
            {msg && <div className="text-sm text-slate-500">{msg}</div>}

            {nextStop ? (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">Next · Day {nextStop.day_number}</div>
                <div className="text-lg font-semibold">{nextStop.name}</div>
                {nextStop.city && <div className="text-sm text-slate-500">{nextStop.city}</div>}
                {nextStop.lat && nextStop.lon && (
                  <a className="text-sm text-teal-700" href={'https://www.google.com/maps/dir/?api=1&destination=' + nextStop.lat + ',' + nextStop.lon} target="_blank" rel="noreferrer">Directions</a>
                )}
                <label className="block">
                  <span className="text-sm text-slate-500">Visit photo</span>
                  <input type="file" accept="image/*" capture="environment" className="mt-1 block w-full text-sm" onChange={(e) => setPhoto(e.target.files && e.target.files[0] ? e.target.files[0] : null)} />
                </label>
                {photo && <div className="text-xs text-slate-500">Photo ready</div>}
                <button onClick={markDone} className="w-full py-2.5 rounded-lg bg-teal-700 text-white font-medium">Done — next stop</button>
              </div>
            ) : (
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-6 text-center">
                <div className="font-medium">All stops done</div>
                <p className="text-sm text-slate-500 mt-1">Sync when you can reach Home Assistant.</p>
              </div>
            )}

            <button onClick={async () => { await deleteTrip(active.id); setActive(null); refresh() }} className="text-sm text-red-500">Remove from this phone</button>
          </>
        )}
      </div>
    </div>
  )
}

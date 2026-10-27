import { useState, useEffect } from 'react'
import Button from './Button'
import PlaceCard from './PlaceCard'
import ImageUpload from './ImageUpload'
import TripEditor from './TripEditor'

function Timer({ startedAt }) {
  const [elapsed, setElapsed] = useState('00:00')
  useEffect(() => {
    // Server stores UTC; parse as UTC so the timer starts at 0
    const raw = String(startedAt).replace(' ', 'T')
    const start = new Date(raw.endsWith('Z') ? raw : raw + 'Z').getTime()
    const tick = () => {
      const secs = Math.max(0, Math.floor((Date.now() - start) / 1000))
      const m = String(Math.floor(secs / 60)).padStart(2, '0')
      const s = String(secs % 60).padStart(2, '0')
      setElapsed(m + ':' + s)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [startedAt])
  return <div className="text-3xl font-semibold tabular-nums">{elapsed}</div>
}

function fmtMins(mins) {
  const m = Math.round(mins || 0)
  if (m < 60) return m + 'm'
  const h = Math.floor(m / 60)
  const rem = m % 60
  return rem ? h + 'h ' + rem + 'm' : h + 'h'
}

function TravelInfo({ stop }) {
  if (!stop) return null
  const miles = stop.distance_from_prev_m ? (stop.distance_from_prev_m / 1609.344).toFixed(1) : null
  const arrive = stop.planned_arrive || stop.arrive
  const depart = stop.planned_depart || stop.depart
  return (
    <div className="px-3 pb-2 text-xs text-slate-500 space-y-0.5">
      <div>
        {arrive && <span>Arrive plan {arrive}</span>}
        {stop.actual_arrive && <span className="text-brand-700 dark:text-brand-400"> · actual {stop.actual_arrive}</span>}
        {stop.projected_arrive && !stop.actual_arrive && <span className="text-amber-600"> · now {stop.projected_arrive}</span>}
        {depart && <span> · Depart plan {depart}</span>}
        {stop.actual_depart && <span className="text-brand-700 dark:text-brand-400"> · actual {stop.actual_depart}</span>}
        {stop.projected_depart && !stop.actual_depart && <span className="text-amber-600"> · now {stop.projected_depart}</span>}
      </div>
      <div>
        {stop.drive_mins > 0 && <span>{fmtMins(stop.drive_mins)} drive</span>}
        {miles && <span> · {miles} mi</span>}
        {stop.visit_mins > 0 && <span> · {fmtMins(stop.visit_mins)} visit</span>}
      </div>
    </div>
  )
}

export default function LiveTrip({ tripId, onClose }) {
  const [editing, setEditing] = useState(false)
  const [data, setData] = useState(null)
  const [finished, setFinished] = useState(false)
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''

  const load = () => {
    Promise.all([
      fetch(base + '/api/trips/' + tripId + '/live').then((r) => r.json()),
      fetch(base + '/api/trips/' + tripId).then((r) => r.json()),
    ]).then(([live, detail]) => {
      const byId = {}
      ;(detail.days || []).forEach((d) => (d.stops || []).forEach((s) => { byId[s.id] = s }))
      const merge = (s) => s ? { ...s, ...(byId[s.id] || {}) } : s
      setData({
        ...live,
        next: merge(live.next),
        remaining: (live.remaining || []).map(merge),
        done: (live.done || []).map(merge),
      })
    })
  }
  useEffect(() => { load() }, [tripId])

  const act = async (path) => {
    await fetch(base + path, { method: 'POST' })
    if (path.endsWith('/finish')) {
      setFinished(true)
      setTimeout(() => onClose && onClose(), 1200)
      return
    }
    load()
  }

  if (finished) return <div className="fixed inset-0 top-16 z-[900] flex items-center justify-center bg-black/50"><div className="bg-white dark:bg-slate-900 rounded-2xl p-6 text-center"><div className="text-lg font-semibold">Trip complete</div><p className="text-sm text-slate-500 mt-1">Well done.</p></div></div>
  if (editing) return <TripEditor tripId={tripId} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); window.location.reload() }} />
  if (!data) return <div className="fixed inset-0 top-16 z-[900] flex items-center justify-center bg-black/50"><div className="bg-white dark:bg-slate-900 rounded-2xl p-6">Loading…</div></div>

  const nxt = data.next
  const arrived = nxt && nxt.arrived_at
  const place = (s) => ({ ...s, name: s.location_name || s.custom_name, id: s.location_id })

  return (
    <div className="fixed inset-0 top-16 z-[900] flex flex-col bg-slate-50 dark:bg-slate-950">
      <header className="flex-shrink-0 bg-white dark:bg-slate-900 border-b px-4 py-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold">{data.trip?.name}</h2>
          <p className="text-sm text-slate-500">Day {data.day} of {data.total_days}</p>
        </div>
        <div className="flex items-center gap-6">
          <Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
          <button onClick={onClose} className="text-2xl text-slate-500 px-2">&times;</button>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Currently visiting */}
        {arrived && (
          <>
            <div className="text-sm font-medium text-slate-500">Currently visiting</div>
            <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
              <PlaceCard place={place(nxt)} />
              <TravelInfo stop={nxt} />
              <Timer startedAt={nxt.arrived_at} />
              <ImageUpload
                value={nxt.visit_photo_url}
                uploadUrl={base + '/api/trips/' + tripId + '/stop/' + nxt.id + '/photo'}
                onUploaded={() => load()}
              />
              <Button onClick={() => act('/api/trips/' + tripId + '/stop/' + nxt.id + '/leave')}>Ready to depart</Button>
            </div>
          </>
        )}

        {/* Next stop */}
        {(() => {
          const upcoming = arrived ? (data.remaining || []).find((s) => s.id !== nxt.id) : nxt
          if (!upcoming && !arrived) return null
          return (
            <>
              <div className="text-sm font-medium text-slate-500">{arrived ? 'Next stop' : 'Next stop'}</div>
              {upcoming ? (
                <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
                  <PlaceCard place={place(upcoming)} />
                  <TravelInfo stop={upcoming} />
                  <div className="flex flex-wrap gap-2">
                    {upcoming.latitude != null && upcoming.longitude != null && (
                      <a href={'https://www.google.com/maps/dir/?api=1&destination=' + upcoming.latitude + ',' + upcoming.longitude + '&travelmode=driving'} target="_blank" rel="noopener" className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-sm font-medium rounded-lg">
                        Open directions
                      </a>
                    )}
                    <button type="button" onClick={() => {
                      const name = upcoming.location_name || upcoming.name || 'Destination'
                      if (navigator.share) navigator.share({ title: name, text: name }).catch(() => {})
                      else {
                        const intent = 'intent:#Intent;action=android.intent.action.SEND;type=text/plain;S.android.intent.extra.TEXT=' + encodeURIComponent(name) + ';S.android.intent.extra.SUBJECT=' + encodeURIComponent(name) + ';end'
                        window.location.href = intent
                      }
                    }} className="inline-flex items-center gap-2 px-4 py-2 border border-slate-300 dark:border-slate-600 text-sm font-medium rounded-lg bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                      </svg>
                      Share
                    </button>
                    <button type="button" title="Coming soon" className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-sm rounded-lg text-slate-400" disabled>
                      Send to car
                    </button>
                    {!arrived && (
                      <>
                        <Button onClick={() => act('/api/trips/' + tripId + '/stop/' + upcoming.id + '/arrive')}>Arrived</Button>
                        <Button variant="secondary" onClick={() => act('/api/trips/' + tripId + '/stop/' + upcoming.id + '/skip')}>Skip</Button>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 text-sm text-slate-500">No more stops after this.</div>
              )}
            </>
          )
        })()}

        {!nxt && (
          <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 text-center">
            <p className="text-slate-600">No more stops today.</p>
            {data.day < data.total_days ? (
              <Button className="mt-3" onClick={() => act('/api/trips/' + tripId + '/end-day')}>End day</Button>
            ) : (
              <Button className="mt-3" onClick={() => act('/api/trips/' + tripId + '/finish')}>Finish trip</Button>
            )}
          </div>
        )}

        {/* All stops today */}
        <div className="text-sm font-medium text-slate-500">Today</div>
        {data.remaining?.filter((s) => s.id !== nxt?.id).map((s) => (
          <div key={s.id} className="mb-1"><PlaceCard place={place(s)} /><TravelInfo stop={s} /></div>
        ))}
        {data.done?.map((s) => (
          <div key={s.id} className="mb-1 opacity-60">
            <PlaceCard place={place(s)} />
            <div className="text-xs text-slate-500 px-3 pb-1">{s.skipped ? 'Skipped' : 'Done'}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

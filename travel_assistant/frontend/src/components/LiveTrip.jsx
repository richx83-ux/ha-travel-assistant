import { useState, useEffect } from 'react'
import Button from './Button'
import PlaceCard from './PlaceCard'
import ImageUpload from './ImageUpload'

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
  return (
    <div className="px-3 pb-2 text-xs text-slate-500">
      {stop.arrive && <span>Arrive {stop.arrive}</span>}
      {stop.depart && <span>{stop.arrive ? ' · ' : ''}Depart {stop.depart}</span>}
      {stop.drive_mins > 0 && <span> · {fmtMins(stop.drive_mins)} drive</span>}
      {miles && <span> · {miles} mi</span>}
      {stop.visit_mins > 0 && <span> · {fmtMins(stop.visit_mins)} visit</span>}
    </div>
  )
}

export default function LiveTrip({ tripId, onClose }) {
  const [data, setData] = useState(null)
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
    load()
  }

  if (!data) return <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50"><div className="bg-white dark:bg-slate-900 rounded-2xl p-6">Loading…</div></div>

  const nxt = data.next
  const arrived = nxt && nxt.arrived_at
  const place = (s) => ({ ...s, name: s.location_name || s.custom_name, id: s.location_id })

  return (
    <div className="fixed inset-0 z-[2000] flex flex-col bg-slate-50 dark:bg-slate-950">
      <header className="flex-shrink-0 bg-white dark:bg-slate-900 border-b px-4 py-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold">{data.trip?.name}</h2>
          <p className="text-sm text-slate-500">Day {data.day} of {data.total_days}</p>
        </div>
        <button onClick={onClose} className="text-xl text-slate-500">&times;</button>
      </header>

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Next stop */}
        <div className="text-sm font-medium text-slate-500">Next stop</div>
        {nxt ? (
          <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
            <PlaceCard place={place(nxt)} />
            <TravelInfo stop={nxt} />
            {arrived && (
              <>
                <Timer startedAt={nxt.arrived_at} />
                <ImageUpload
                  value={nxt.visit_photo_url}
                  uploadUrl={base + '/api/trips/' + tripId + '/stop/' + nxt.id + '/photo'}
                  onUploaded={() => load()}
                />
              </>
            )}
            <div className="flex flex-wrap gap-2">
              {nxt.latitude != null && nxt.longitude != null && (
                <a href={'https://www.google.com/maps/dir/?api=1&destination=' + nxt.latitude + ',' + nxt.longitude + '&travelmode=driving'} target="_blank" rel="noopener" className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-sm font-medium rounded-lg">
                  Open directions
                </a>
              )}
              <button type="button" onClick={() => {
                const name = nxt.location_name || nxt.name || 'Destination'
                if (navigator.share) navigator.share({ title: name, text: name }).catch(() => {})
                else {
                  const intent = 'intent:#Intent;action=android.intent.action.SEND;type=text/plain;S.android.intent.extra.TEXT=' + encodeURIComponent(name) + ';S.android.intent.extra.SUBJECT=' + encodeURIComponent(name) + ';end'
                  window.location.href = intent
                }
              }} className="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg">
                Share
              </button>
              <button type="button" title="Coming soon" className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-sm rounded-lg text-slate-400" disabled>
                Send to car
              </button>
              {!arrived ? (
                <>
                  <Button onClick={() => act('/api/trips/' + tripId + '/stop/' + nxt.id + '/arrive')}>Arrived</Button>
                  <Button variant="secondary" onClick={() => act('/api/trips/' + tripId + '/stop/' + nxt.id + '/skip')}>Skip</Button>
                </>
              ) : (
                <Button onClick={() => act('/api/trips/' + tripId + '/stop/' + nxt.id + '/leave')}>Ready to depart</Button>
              )}
            </div>
          </div>
        ) : (
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

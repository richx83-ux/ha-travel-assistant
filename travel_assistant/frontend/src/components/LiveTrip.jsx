import { useState, useEffect } from 'react'
import Button from './Button'
import PlaceCard from './PlaceCard'
import ImageUpload from './ImageUpload'

function Timer({ startedAt }) {
  const [elapsed, setElapsed] = useState('00:00')
  useEffect(() => {
    const start = new Date(String(startedAt).replace(' ', 'T')).getTime()
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

export default function LiveTrip({ tripId, onClose }) {
  const [data, setData] = useState(null)
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''

  const load = () => {
    fetch(base + '/api/trips/' + tripId + '/live').then((r) => r.json()).then(setData)
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
            <div className="flex gap-2">
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
          <div key={s.id} className="mb-1"><PlaceCard place={place(s)} /></div>
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

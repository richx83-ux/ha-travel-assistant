import { useState, useEffect } from 'react'
import Button from './Button'
import PlaceCard from './PlaceCard'

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
        {nxt ? (
          <div className="bg-white dark:bg-slate-900 rounded-xl border p-4">
            <div className="text-xs text-slate-500 mb-2">{arrived ? 'At this stop' : 'Next stop'}</div>
            <PlaceCard place={{ ...nxt, name: nxt.location_name || nxt.custom_name }} />
            <div className="flex gap-2 mt-4">
              {!arrived ? (
                <>
                  <Button onClick={() => act('/api/trips/' + tripId + '/stop/' + nxt.id + '/arrive')}>Arrived</Button>
                  <Button variant="secondary" onClick={() => act('/api/trips/' + tripId + '/stop/' + nxt.id + '/skip')}>Skip</Button>
                </>
              ) : (
                <Button onClick={() => act('/api/trips/' + tripId + '/stop/' + nxt.id + '/leave')}>Ready to leave</Button>
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

        {data.done?.length > 0 && (
          <div>
            <div className="text-sm font-medium mb-2">Done today</div>
            {data.done.map((s) => (
              <div key={s.id} className="mb-1 opacity-70">
                <PlaceCard place={{ ...s, name: s.location_name || s.custom_name }} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

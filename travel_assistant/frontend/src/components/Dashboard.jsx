import { useState, useEffect } from 'react'
import Button from './Button'

function TeslaBar({ progress, base }) {
  const pct = Math.max(0, Math.min(100, progress || 0))
  return (
    <div className="relative h-8 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
      <div className="absolute inset-y-0 left-0 bg-brand-500 rounded-full transition-all" style={{ width: pct + '%' }} />
      <img
        src={asset(base, "/static/react/tesla-y.jpg")}
        alt=""
        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-10 h-6 object-contain drop-shadow"
        style={{ left: Math.max(8, Math.min(92, pct)) + '%' }}
      />
      <span className="absolute inset-0 flex items-center justify-center text-xs font-medium">{pct}%</span>
    </div>
  )
}

function asset(base, path) {
  return (base || '') + path
}
export default function Dashboard({ base = '', onContinue }) {
  const [trips, setTrips] = useState([])
  const [live, setLive] = useState(null)

  useEffect(() => {
    fetch(base + '/api/trips').then((r) => r.json()).then((d) => {
      const list = d.trips || []
      setTrips(list)
      const active = list.find((t) => t.status === 'active')
      if (active) {
        fetch(base + '/api/trips/' + active.id + '/live').then((r) => r.json()).then(setLive)
      }
    })
  }, [base])

  const active = trips.find((t) => t.status === 'active')

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-4">
      {active ? (
        <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold">{active.name}</h2>
              <p className="text-sm text-slate-500">
                Day {live?.day || active.active_day || 1} of {live?.total_days || active.total_days || 1}
              </p>
            </div>
            <Button onClick={() => onContinue && onContinue(active.id)}>Continue trip</Button>
          </div>
          <TeslaBar progress={active.progress} base={base} />
          <p className="text-xs text-slate-500">{active.done_count} of {active.stop_count} stops complete</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-xl border p-6 text-center text-slate-500">
          No trip in progress.
        </div>
      )}
    </div>
  )
}

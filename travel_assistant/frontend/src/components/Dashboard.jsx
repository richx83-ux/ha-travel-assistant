import { useState, useEffect } from 'react'
import Button from './Button'

function TeslaBar({ progress, base, dark }) {
  const pct = Math.max(0, Math.min(100, progress || 0))
  return (
    <div className="relative h-12">
      {/* Road */}
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-6 rounded-full overflow-hidden" style={{ background: 'repeating-linear-gradient(90deg, #4b5563 0 12px, #6b7280 12px 20px)', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.3)' }}>
        <div className="absolute inset-y-1 left-2 right-2 border-t border-dashed border-white/50" />
        <div className="absolute inset-y-0 left-0 transition-all" style={{ width: pct + '%', background: 'linear-gradient(180deg, #0f766e, #14b8a6)' }} />
      </div>
      {/* Car bigger than the road, sits at the end of the progress */}
      <img
        src={asset(base, "/static/react/tesla-y-white.png")}
        alt=""
        className="absolute top-1/2 -translate-y-1/2 w-40 h-24 object-contain drop-shadow-lg transition-all"
        style={{ left: `calc(${pct}% - 120px)` }}
      />
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-medium text-white">{pct}%</span>
    </div>
  )
}

function asset(base, path) {
  return (base || '') + path
}
function countdown(date) {
  if (!date) return null
  const start = new Date(date + 'T00:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = Math.round((start - today) / 86400000)
  if (days < 0) return null
  if (days === 0) return 'Starts today'
  if (days === 1) return 'Starts tomorrow'
  return days + ' days to go'
}

export default function Dashboard({ base = '', onContinue, onNewTrip, onView, onEdit }) {
  const [trips, setTrips] = useState([])
  const [command, setCommand] = useState('')
  const [plan, setPlan] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
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

  const upcoming = trips
    .filter((t) => t.status !== 'active' && t.status !== 'completed')
    .map((t) => ({ ...t, countdown: countdown(t.start_date) || (t.start_date ? 'Date passed' : 'No date set') }))
    .sort((a, b) => (a.start_date || '9999').localeCompare(b.start_date || '9999'))

  return (
    <div className="p-4 max-w-2xl mx-auto">
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-4">
        <div className="space-y-2 pb-3 border-b border-slate-200 dark:border-slate-800">
          <div className="text-xs font-medium text-slate-500">Ask Travel Assistant</div>
          <textarea className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" rows={2} placeholder="Create a trip for 7th November called Visit Paul, staying in a Holiday Inn on the A55" value={command} onChange={(e) => setCommand(e.target.value)} />
          <Button onClick={async () => {
            setBusy(true); setMsg(''); setPlan(null)
            const res = await fetch(base + '/api/command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: command }) })
            const d = await res.json()
            setBusy(false)
            if (d.ok) setPlan(d.plan); else setMsg(d.detail || 'Could not plan that')
          }} disabled={busy || !command.trim()}>{busy ? 'Planning…' : 'Plan'}</Button>
          {msg && <p className="text-sm text-red-500">{msg}</p>}
          {plan && (
            <div className="border rounded-lg p-3 space-y-1 text-sm">
              <div className="font-medium">{plan.trip?.name}</div>
              <div className="text-slate-500">{plan.trip?.start_date} → {plan.trip?.end_date}</div>
              {(plan.places || []).map((p, i) => (
                <div key={i}>{p.name}{p.city ? ' · ' + p.city : ''}{p.is_accommodation ? ' (stay)' : ''}</div>
              ))}
              <Button onClick={async () => {
                const res = await fetch(base + '/api/command/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan }) })
                const d = await res.json()
                if (d.ok) { setPlan(null); setCommand(''); window.location.reload() }
              }}>Create this trip</Button>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Trips</h3>
          <Button onClick={() => onNewTrip && onNewTrip()}>New trip</Button>
        </div>

        {active ? (
          <div className="space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs text-slate-500">In progress</div>
                <div className="font-medium">{active.name}</div>
                <div className="text-sm text-slate-500">
                  Day {live?.day || active.active_day || 1} of {live?.total_days || active.total_days || 1}
                </div>
              </div>
              <Button onClick={() => onContinue && onContinue(active.id)}>Continue</Button>
            </div>
            <TeslaBar progress={active.progress} base={base} dark={document.documentElement.classList.contains("dark")} />
            <p className="text-xs text-slate-500">{active.done_count} of {active.stop_count} stops complete</p>
          </div>
        ) : (
          <p className="text-sm text-slate-500">No trip in progress.</p>
        )}

        <div className="border-t border-slate-200 dark:border-slate-800 pt-3 space-y-2">
          <div className="text-xs text-slate-500">Upcoming</div>
          {upcoming.length === 0 && <p className="text-sm text-slate-500">No upcoming trips.</p>}
          {upcoming.map((t) => (
            <div key={t.id} className="bg-slate-50 dark:bg-slate-800 rounded-lg overflow-hidden">
              {t.image_url && (
                <img src={asset(base, t.image_url)} alt="" className="w-full h-32 object-cover" />
              )}
              <div className="flex items-center justify-between p-3 gap-2">
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{t.name}</div>
                  <div className="text-sm text-slate-500">{t.start_date || 'No date'}</div>
                  <div className="text-sm font-medium text-brand-600">{t.countdown}</div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <Button variant="secondary" onClick={() => onView && onView(t.id)}>View</Button>
                  <Button variant="secondary" onClick={() => onEdit && onEdit(t.id)}>Edit</Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

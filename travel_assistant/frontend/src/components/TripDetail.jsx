import { useState, useEffect } from 'react'
import Button from './Button'
import Badge from './Badge'
import PlaceCard from './PlaceCard'
import TripEditor from './TripEditor'
import LiveTrip from './LiveTrip'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

function fmtMins(mins) {
  if (!mins && mins !== 0) return ''
  const m = Math.round(mins)
  if (m < 60) return m + 'm'
  const h = Math.floor(m / 60)
  const mm = m % 60
  return mm ? h + 'h ' + mm + 'm' : h + 'h'
}

export default function TripDetail({ tripId, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [view, setView] = useState('summary')
  const [editing, setEditing] = useState(false)
  const [live, setLive] = useState(false)
  const [dayNum, setDayNum] = useState(1) // summary | itinerary
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''

  useEffect(() => {
    fetch(base + '/api/trips/' + tripId)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load trip (' + r.status + ')')
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [tripId])

  if (error) {
    if (live) return <LiveTrip tripId={tripId} onClose={() => setLive(false)} />
  if (editing) {
    return <TripEditor tripId={tripId} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); window.location.reload() }} />
  }

  return (
      <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50" onClick={onClose}>
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-6">{error}</div>
      </div>
    )
  }
  if (!data) {
    if (live) return <LiveTrip tripId={tripId} onClose={() => setLive(false)} />
  if (editing) {
    return <TripEditor tripId={tripId} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); window.location.reload() }} />
  }

  return (
      <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-6">Loading…</div>
      </div>
    )
  }

  const trip = data.trip || {}
  const days = data.days || []
  const photo = assetUrl(trip.image_url)

  if (live) return <LiveTrip tripId={tripId} onClose={() => setLive(false)} />
  if (editing) {
    return <TripEditor tripId={tripId} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); window.location.reload() }} />
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white dark:bg-slate-900 rounded-t-2xl md:rounded-2xl shadow-xl max-h-[92vh] overflow-auto">
        <div className="relative h-36 bg-slate-200 dark:bg-slate-800">
          {photo ? (
            <img src={photo} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-3xl text-white" style={{ background: '#0d9488' }}>
              {(trip.name || '?')[0]}
            </div>
          )}
          <button onClick={onClose} className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/40 text-white">&times;</button>
        </div>

        <div className="p-4">
          <h2 className="text-xl font-semibold">{trip.name}</h2>
          <p className="text-sm text-slate-500">{[trip.start_date, trip.end_date].filter(Boolean).join(' → ')}</p>

          {view === 'summary' && (
            <div className="flex gap-2 mt-4">
              <Button className="flex-1" onClick={async () => {
                await fetch(base + '/api/trips/' + tripId + '/start', { method: 'POST' })
                setLive(true)
              }}>Start / Continue</Button>
              <Button variant="secondary" onClick={() => setView('itinerary')}>View</Button>
              <Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
            </div>
          )}

          {view === 'itinerary' && (
            <div className="mt-4">
              <button onClick={() => setView('summary')} className="text-sm text-brand-600 mb-3">← Back</button>
              <div className="flex gap-2 mb-4 overflow-x-auto">
                {days.map((d) => (
                  <button key={d.day} onClick={() => setDayNum(d.day)} className={`px-4 py-2 rounded-full text-base font-medium ${d.day === dayNum ? 'bg-brand-600 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}>
                    Day {d.day}
                  </button>
                ))}
              </div>
              {days.filter((d) => d.day === dayNum).map((day) => (
                <div key={day.day} className="mb-6">
                  <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 mb-3 grid grid-cols-3 gap-2 text-center text-sm">
                    <div><div className="text-xs text-slate-500">Drive</div><div className="font-medium">{fmtMins(Math.round((day.drive_secs || 0) / 60))}</div></div>
                    <div><div className="text-xs text-slate-500">Miles</div><div className="font-medium">{day.miles}</div></div>
                    <div><div className="text-xs text-slate-500">Spare</div><div className="font-medium">{fmtMins(day.spare_mins || 0)}</div></div>
                  </div>
                  <div className="text-xs text-slate-500 mb-2">Start {day.start} · Finish by {day.finish}</div>
                  <div className="space-y-2">
                    {day.stops.map((s, i) => (
                      <div key={s.id || 'start-' + i} className={s.is_accommodation ? 'ring-2 ring-amber-300 dark:ring-amber-700 rounded-xl' : ''}>
                        <PlaceCard place={{
                          ...s,
                          name: s.location_name || s.custom_name || 'Stop',
                          image_url: s.image_url || s.visit_photo_url,
                        }} />
                        <div className="px-4 pb-3 pt-1 text-sm text-slate-600 dark:text-slate-300">
                          {s.is_start && <span className="text-amber-700 dark:text-amber-400 font-medium">Start · </span>}
                          {s.depart && <span>Depart {s.depart}</span>}
                          {!s.is_start && s.arrive && <span> · Arrive {s.arrive}</span>}
                          {!s.is_start && s.drive_mins > 0 && <span> · {fmtMins(s.drive_mins)} drive</span>}
                          {!s.is_start && s.miles > 0 && <span> · {s.miles} mi</span>}
                          {!s.is_start && s.visit_mins > 0 && <span> · {fmtMins(s.visit_mins)} visit</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

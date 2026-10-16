import { useState, useEffect } from 'react'
import Button from './Button'
import Badge from './Badge'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

function fmt(secs) {
  if (!secs) return ''
  const m = Math.round(secs / 60)
  if (m < 60) return m + ' min'
  const h = Math.floor(m / 60)
  const mm = m % 60
  return mm ? h + 'h ' + mm + 'm' : h + 'h'
}

export default function TripDetail({ tripId, onClose }) {
  const [data, setData] = useState(null)
  const [view, setView] = useState('summary') // summary | itinerary
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''

  useEffect(() => {
    fetch(base + '/api/trips/' + tripId)
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
  }, [tripId])

  if (!data) {
    return (
      <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-6">Loading…</div>
      </div>
    )
  }

  const trip = data.trip || {}
  const days = data.days || []
  const photo = assetUrl(trip.image_url)

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
              <a href={base + '/trip/' + trip.id + '/live'} className="flex-1">
                <Button className="w-full">Start / Continue</Button>
              </a>
              <Button variant="secondary" onClick={() => setView('itinerary')}>View</Button>
              <a href={base + '/trip/' + trip.id + '/wizard'}>
                <Button variant="secondary">Edit</Button>
              </a>
            </div>
          )}

          {view === 'itinerary' && (
            <div className="mt-4">
              <button onClick={() => setView('summary')} className="text-sm text-brand-600 mb-3">← Back</button>
              {days.map((day) => (
                <div key={day.day} className="mb-6">
                  <div className="flex items-baseline justify-between mb-2">
                    <h3 className="font-semibold">Day {day.day}</h3>
                    <span className="text-xs text-slate-500">{day.miles} mi · {fmt(day.drive_secs)} drive</span>
                  </div>
                  <div className="space-y-2">
                    {day.stops.map((s) => (
                      <div
                        key={s.id}
                        className={`p-3 rounded-xl border ${s.is_accommodation ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800'}`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="font-medium truncate">{s.location_name || s.custom_name || 'Stop'}</div>
                            <div className="text-xs text-slate-500">{s.theme_name}</div>
                          </div>
                          {s.is_accommodation && <Badge color="amber">Stay</Badge>}
                        </div>
                        <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                          {s.depart && <span>Depart {s.depart}</span>}
                          {s.arrive && <span> · Arrive {s.arrive}</span>}
                          {s.drive_mins > 0 && <span> · {s.drive_mins} min drive</span>}
                          {s.miles > 0 && <span> · {s.miles} mi</span>}
                          {s.visit_mins > 0 && <span> · {s.visit_mins} min visit</span>}
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

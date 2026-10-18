import { useState, useEffect } from 'react'
import Button from './Button'
import Input from './Input'
import PlaceCard from './PlaceCard'
import Filters from './Filters'
import MapView from './MapView'
import PlaceDetail from './PlaceDetail'
import ImageUpload from './ImageUpload'

const STEPS = ['Setup', 'Accommodation', 'Days', 'Summary']

export default function TripEditor({ tripId, onClose, onSaved }) {
  const [step, setStep] = useState(0)
  const [day, setDay] = useState(1)
  const [draft, setDraft] = useState(null)
  const [places, setPlaces] = useState([])
  const [hotels, setHotels] = useState([])
  const [home, setHome] = useState(null)
  const [saving, setSaving] = useState(false)
  const [filters, setFilters] = useState({ search: '', type: '', theme: '', region: '', county: '' })
  const [adding, setAdding] = useState(false)
  const [viewPlace, setViewPlace] = useState(null)
  const [dragIdx, setDragIdx] = useState(null)
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''

  useEffect(() => {
    Promise.all([
      fetch(base + '/api/trips/' + tripId).then((r) => r.json()),
      fetch(base + '/api/places').then((r) => r.json()),
    ]).then(([tripData, placesData]) => {
      const trip = tripData.trip || {}
      const days = tripData.days || []
      // Build draft stops from existing (exclude is_start markers)
      const stops = []
      days.forEach((d) => {
        (d.stops || []).forEach((s) => {
          if (s.is_start) return
          stops.push({
            id: s.id,
            location_id: s.location_id,
            day_number: d.day,
            name: s.location_name || s.custom_name,
            city: s.city,
            county: s.county,
            theme_name: s.theme_name,
            primary_color: s.primary_color,
            icon_url: s.icon_url,
            image_url: s.image_url || s.visit_photo_url,
            is_accommodation: s.is_accommodation,
            visited: s.visited,
          })
        })
      })
      setDraft({
        name: trip.name || '',
        start_date: trip.start_date || '',
        end_date: trip.end_date || '',
        image_url: trip.image_url || '',
        notes: trip.notes || '',
        finish_by: trip.finish_by || '17:00',
        start_time: trip.start_time || '09:00',
        day1_depart: trip.day1_depart || '',
        start_place_id: trip.start_place_id || '',
        finish_place_id: trip.finish_place_id || '',
        align: trip.align || 'start',
        stops,
      })
      const all = placesData.places || []
      setPlaces(all)
      setHotels(all.filter((p) => Number(p.hidden) !== 1 && ((p.category_type_name || '').toLowerCase() === 'accommodation' || (p.theme_name || '').toLowerCase() === 'home' || (p.category_type_name || '').toLowerCase() === 'home location' || (p.theme_name || '').toLowerCase() === 'hotels')))
      fetch(base + '/api/settings').then((r) => r.json()).then((d) => setHome(d.home || null))
    })
  }, [tripId])

  const matches = (p) => {
    const q = (filters.search || '').toLowerCase()
    if (q && !((p.name || '').toLowerCase().includes(q) || (p.city || '').toLowerCase().includes(q))) return false
    if (filters.type && (p.category_type_name || '') !== filters.type) return false
    if (filters.theme && String(p.theme_id) !== String(filters.theme)) return false
    if (filters.region && (p.region || '') !== filters.region) return false
    if (filters.county && (p.county || '') !== filters.county) return false
    return true
  }
  const filteredPlaces = places.filter(matches)
  const unique = (arr) => [...new Set(arr.filter(Boolean))].sort()
  const typeOptions = [{ value: '', label: 'All types' }, ...unique(places.map((p) => p.category_type_name)).map((n) => ({ value: n, label: n }))]
  const themeOptions = [{ value: '', label: 'All categories' }, ...[...new Map(places.map((p) => [String(p.theme_id), p.theme_name])).entries()].map(([id, name]) => ({ value: id, label: name }))]
  const regionOptions = [{ value: '', label: 'All regions' }, ...unique(places.map((p) => p.region)).map((n) => ({ value: n, label: n }))]
  const countyOptions = [{ value: '', label: 'All counties' }, ...unique(places.map((p) => p.county)).map((n) => ({ value: n, label: n }))]

  if (!draft) {
    return (
      <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-6">Loading…</div>
      </div>
    )
  }

  const nDays = (() => {
    if (!draft.start_date || !draft.end_date) return 1
    const a = new Date(draft.start_date)
    const b = new Date(draft.end_date)
    return Math.max(1, Math.round((b - a) / 86400000) + 1)
  })()

  const dayStops = draft.stops.filter((s) => s.day_number === day && !s.is_accommodation)
  const dayHotel = draft.stops.find((s) => s.day_number === day && s.is_accommodation)

    const placeOptions = () => {
    const list = []
    if (home) list.push(home)
    hotels.forEach((h) => { if (!list.some((p) => p.id === h.id)) list.push(h) })
    places.forEach((p) => { if (!list.some((x) => x.id === p.id)) list.push(p) })
    return list
  }
  const placeById = (id) => placeOptions().find((p) => String(p.id) === String(id))

  const setHotel = (dayNum, placeId) => {
    setDraft((d) => {
      const others = d.stops.filter((s) => !(s.day_number === dayNum && s.is_accommodation))
      if (!placeId) return { ...d, stops: others }
      const place = hotels.find((h) => String(h.id) === String(placeId))
      if (!place) return d
      return {
        ...d,
        stops: [...others, {
          location_id: place.id,
          day_number: dayNum,
          name: place.name,
          city: place.city,
          county: place.county,
          theme_name: place.theme_name,
          primary_color: place.primary_color,
          icon_url: place.icon_url,
          image_url: place.image_url,
          is_accommodation: true,
          visited: place.visited,
        }],
      }
    })
  }

  const addStop = (place) => {
    setDraft((d) => ({
      ...d,
      stops: [...d.stops, {
        location_id: place.id,
        day_number: day,
        name: place.name,
        city: place.city,
        county: place.county,
        theme_name: place.theme_name,
        primary_color: place.primary_color,
        icon_url: place.icon_url,
        image_url: place.image_url,
        is_accommodation: false,
        visited: place.visited,
      }],
    }))
  }

  const moveStop = (fromIdx, dir) => {
    setDraft((d) => {
      const dayIdxs = d.stops.map((s, i) => ({ s, i })).filter((x) => x.s.day_number === day && !x.s.is_accommodation)
      const pos = dayIdxs.findIndex((x) => x.i === fromIdx)
      const swap = pos + dir
      if (pos < 0 || swap < 0 || swap >= dayIdxs.length) return d
      const next = [...d.stops]
      const a = dayIdxs[pos].i
      const b = dayIdxs[swap].i
      ;[next[a], next[b]] = [next[b], next[a]]
      return { ...d, stops: next }
    })
  }

  const onDrop = (toIdx) => {
    if (dragIdx == null || dragIdx === toIdx) { setDragIdx(null); return }
    setDraft((d) => {
      const dayItems = d.stops.map((s, i) => ({ s, i })).filter((x) => x.s.day_number === day && !x.s.is_accommodation)
      const fromPos = dayItems.findIndex((x) => x.i === dragIdx)
      const toPos = dayItems.findIndex((x) => x.i === toIdx)
      if (fromPos < 0 || toPos < 0) return d
      const reordered = [...dayItems]
      const [moved] = reordered.splice(fromPos, 1)
      reordered.splice(toPos, 0, moved)
      // Rebuild stops: keep non-day items, replace day activity items in new order
      const next = d.stops.filter((s) => !(s.day_number === day && !s.is_accommodation))
      reordered.forEach((x) => next.push(x.s))
      return { ...d, stops: next }
    })
    setDragIdx(null)
  }

    const moveToDay = (idx, newDay) => {
    setDraft((d) => ({ ...d, stops: d.stops.map((s, i) => i === idx ? { ...s, day_number: Number(newDay) } : s) }))
  }

  const removeStop = (idx) => {
    setDraft((d) => ({ ...d, stops: d.stops.filter((_, i) => i !== idx) }))
  }

  const save = async () => {
    setSaving(true)
    try {
      const res = await fetch(base + '/api/trips/' + tripId + '/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      })
      if (!res.ok) throw new Error('Save failed')
      onSaved && onSaved()
      onClose()
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[2000] flex flex-col bg-slate-50 dark:bg-slate-950">
      {/* Header + stepper */}
      <header className="flex-shrink-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 py-3">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Edit trip</h2>
          <button onClick={onClose} className="text-slate-500 text-xl">&times;</button>
        </div>
        <div className="flex gap-1 overflow-x-auto">
          {STEPS.map((label, i) => (
            <button
              key={label}
              onClick={() => setStep(i)}
              className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap ${i === step ? 'bg-brand-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}`}
            >
              {i + 1}. {label}
            </button>
          ))}
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {step === 0 && (
          <div className="max-w-lg mx-auto space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Start date</label>
                <Input type="date" value={draft.start_date} onChange={(e) => setDraft({ ...draft, start_date: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">End date</label>
                <Input type="date" value={draft.end_date} onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">Day 1 departure</label>
                <Input type="time" value={draft.day1_depart || draft.start_time || '09:00'} onChange={(e) => setDraft({ ...draft, day1_depart: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">Other days start</label>
                <Input type="time" value={draft.start_time || '09:00'} onChange={(e) => setDraft({ ...draft, start_time: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">Finish by</label>
                <Input type="time" value={draft.finish_by || '17:00'} onChange={(e) => setDraft({ ...draft, finish_by: e.target.value })} />
              </div>
              <div className="col-span-2">
                <label className="text-sm font-medium">Align times to</label>
                <select className="w-full mt-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" value={draft.align || 'start'} onChange={(e) => setDraft({ ...draft, align: e.target.value })}>
                  <option value="start">Start time</option>
                  <option value="finish">Finish time</option>
                </select>
              </div>
            </div>
            <ImageUpload
              value={draft.image_url}
              uploadUrl={base + '/api/trips/' + tripId + '/image'}
              onUploaded={(url) => setDraft({ ...draft, image_url: url })}
            />
            <div>
              <label className="text-sm font-medium">Notes</label>
              <textarea className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" rows={3} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
            </div>
            <div className="border border-red-200 dark:border-red-900 rounded-xl p-3">
              <div className="text-xs font-medium text-red-600 mb-2">Danger zone</div>
              <Button variant="secondary" onClick={async () => {
                if (!window.confirm('Delete this trip? This cannot be undone.')) return
                await fetch(base + '/api/trips/' + tripId + '/delete', { method: 'POST' })
                onSaved && onSaved()
                onClose && onClose()
              }}>Delete trip</Button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="max-w-lg mx-auto space-y-4">
            <div>
              <label className="text-sm font-medium">Day 1 starting location</label>
              <select className="w-full mt-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" value={draft.start_place_id || ''} onChange={(e) => setDraft({ ...draft, start_place_id: e.target.value })}>
                <option value="">Choose starting location</option>
                {placeOptions().map((h) => <option key={h.id} value={h.id}>{h.name}{h.city ? ' · ' + h.city : ''}</option>)}
              </select>
            </div>
            <div className="space-y-3">
              <p className="text-sm text-slate-500">End-of-day accommodation for each night.</p>
              {Array.from({ length: Math.max(0, nDays - 1) }, (_, i) => i + 1).map((d) => {
                const current = draft.stops.find((s) => s.day_number === d && s.is_accommodation)
                return (
                  <div key={d} className="flex items-center gap-3">
                    <span className="w-16 text-sm font-medium">Day {d}</span>
                    <select className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" value={current?.location_id || ''} onChange={(e) => setHotel(d, e.target.value)}>
                      <option value="">No accommodation</option>
                      {placeOptions().map((h) => <option key={h.id} value={h.id}>{h.name}{h.city ? ' · ' + h.city : ''}</option>)}
                    </select>
                  </div>
                )
              })}
            </div>
            <div>
              <label className="text-sm font-medium">Final day finishing place</label>
              <select className="w-full mt-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" value={draft.finish_place_id || ''} onChange={(e) => setDraft({ ...draft, finish_place_id: e.target.value })}>
                <option value="">Choose finishing place</option>
                {placeOptions().map((h) => <option key={h.id} value={h.id}>{h.name}{h.city ? ' · ' + h.city : ''}</option>)}
              </select>
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <div className="flex gap-2 mb-3 overflow-x-auto">
              {Array.from({ length: nDays }, (_, i) => i + 1).map((d) => (
                <button key={d} onClick={() => setDay(d)} className={`px-4 py-2 rounded-full text-base font-medium ${d === day ? 'bg-brand-600 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}>
                  Day {d}
                </button>
              ))}
            </div>
            {adding && (
              <Filters
                value={filters}
                onChange={setFilters}
                resultCount={filteredPlaces.length}
                fields={['search', 'type', 'theme', 'region', 'county']}
                options={{ type: typeOptions, theme: themeOptions, region: regionOptions, county: countyOptions }}
              />
            )}
            <div className="flex flex-col md:flex-row gap-4 mt-3">
              <div className="md:w-1/2 h-64 md:h-96">
                <MapView places={adding ? filteredPlaces.filter((p) => !draft.stops.some((s) => s.location_id === p.id && s.day_number === day)) : draft.stops.filter((s) => s.day_number === day)} onSelect={adding ? addStop : undefined} onView={(p) => setViewPlace(places.find((x) => x.id === (p.location_id || p.id)) || { ...p, id: p.location_id || p.id })} />
              </div>
              <div className="md:w-1/2 space-y-2">
                <div className="flex justify-between items-center py-3 px-1">
                  <span className="text-sm font-medium">Day {day}{adding ? ' · ' + draft.stops.filter((s) => s.day_number === day && !s.is_accommodation).length + ' added' : ''}</span>
                  <Button variant="secondary" className="px-5 py-2.5" onClick={() => setAdding(!adding)}>{adding ? 'Done adding' : 'Add place'}</Button>
                </div>
                {/* Day 1 starting location */}
                {day === 1 && placeById(draft.start_place_id) && (
                  <div className="ring-2 ring-amber-300 rounded-xl">
                    <PlaceCard place={placeById(draft.start_place_id)} />
                    <div className="px-3 pb-2 text-xs text-amber-700">Start</div>
                  </div>
                )}
                {/* Start accommodation */}
                {day > 1 && (() => {
                  const prev = draft.stops.find((s) => s.day_number === day - 1 && s.is_accommodation)
                  return prev ? (
                    <div className="ring-2 ring-amber-300 rounded-xl">
                      <PlaceCard place={prev} />
                      <div className="px-3 pb-2 text-xs text-amber-700">Start</div>
                    </div>
                  ) : null
                })()}
                {dayStops.map((s) => {
                  const idx = draft.stops.indexOf(s)
                  return (
                    <div
                      key={idx}
                      draggable
                      onDragStart={() => setDragIdx(idx)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => onDrop(idx)}
                      className={`flex items-start gap-2 w-full min-w-0 ${dragIdx === idx ? 'opacity-50' : ''}`}
                    >
                      <div className="flex flex-col gap-1 cursor-grab text-slate-400 pt-3 flex-shrink-0" title="Drag to reorder">
                        <span>⋮⋮</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <PlaceCard place={s} />
                        <select className="mt-1 text-xs px-2 py-1 border rounded bg-white dark:bg-slate-800" value={s.day_number} onChange={(e) => moveToDay(idx, e.target.value)}>
                          {Array.from({ length: nDays }, (_, i) => i + 1).map((d) => (
                            <option key={d} value={d}>Day {d}</option>
                          ))}
                        </select>
                      </div>
                      <button onClick={() => removeStop(idx)} className="text-red-500 text-lg px-2 flex-shrink-0">✕</button>
                    </div>
                  )
                })}
                {dayStops.length === 0 && <p className="text-sm text-slate-500">{adding ? 'Tap a place on the map to add it.' : 'No places yet. Press Add place.'}</p>}
                {/* Destination hotel last */}
                {dayHotel && (
                  <div className="ring-2 ring-amber-300 rounded-xl">
                    <PlaceCard place={dayHotel} />
                    <div className="px-3 pb-2 text-xs text-amber-700">Stay</div>
                  </div>
                )}
                {/* Final day finishing place */}
                {day === nDays && placeById(draft.finish_place_id) && (
                  <div className="ring-2 ring-amber-300 rounded-xl">
                    <PlaceCard place={placeById(draft.finish_place_id)} />
                    <div className="px-3 pb-2 text-xs text-amber-700">Finish</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="max-w-lg mx-auto space-y-4">
            <h3 className="font-semibold">{draft.name}</h3>
            <p className="text-sm text-slate-500">{draft.start_date} → {draft.end_date} · {nDays} days · {draft.stops.length} stops</p>
            {Array.from({ length: nDays }, (_, i) => i + 1).map((d) => {
              const dayItems = draft.stops.filter((s) => s.day_number === d)
              const activities = dayItems.filter((s) => !s.is_accommodation)
              const dest = dayItems.find((s) => s.is_accommodation)
              const start = d === 1 ? placeById(draft.start_place_id) : draft.stops.find((s) => s.day_number === d - 1 && s.is_accommodation)
              const finish = d === nDays ? placeById(draft.finish_place_id) : null
              return (
                <div key={d}>
                  <div className="text-sm font-medium mb-1">Day {d}</div>
                  {start && (
                    <div className="ring-2 ring-amber-300 rounded-xl mb-1">
                      <PlaceCard place={start} />
                      <div className="px-3 pb-1 text-xs text-amber-700">Start</div>
                    </div>
                  )}
                  {activities.map((s, i) => (
                    <div key={i} className="mb-1"><PlaceCard place={s} /></div>
                  ))}
                  {dest && (
                    <div className="ring-2 ring-amber-300 rounded-xl mb-1">
                      <PlaceCard place={dest} />
                      <div className="px-3 pb-1 text-xs text-amber-700">Stay</div>
                    </div>
                  )}
                  {finish && (
                    <div className="ring-2 ring-amber-300 rounded-xl mb-1">
                      <PlaceCard place={finish} />
                      <div className="px-3 pb-1 text-xs text-amber-700">Finish</div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Sticky footer */}
      <footer className="flex-shrink-0 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 px-4 py-3 flex gap-2">
        <Button variant="secondary" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>Back</Button>
        <div className="flex-1" />
        {step < STEPS.length - 1 ? (
          <Button onClick={() => setStep(step + 1)}>Next</Button>
        ) : (
          <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
        )}
      </footer>
      {viewPlace && <PlaceDetail place={viewPlace} onClose={() => setViewPlace(null)} />}
    </div>
  )
}

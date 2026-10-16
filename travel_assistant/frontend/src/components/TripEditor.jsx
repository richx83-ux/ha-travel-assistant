import { useState, useEffect } from 'react'
import Button from './Button'
import Input from './Input'
import PlaceCard from './PlaceCard'
import Filters from './Filters'
import MapView from './MapView'
import ImageUpload from './ImageUpload'

const STEPS = ['Setup', 'Hotels', 'Days', 'Summary']

export default function TripEditor({ tripId, onClose, onSaved }) {
  const [step, setStep] = useState(0)
  const [day, setDay] = useState(1)
  const [draft, setDraft] = useState(null)
  const [places, setPlaces] = useState([])
  const [hotels, setHotels] = useState([])
  const [saving, setSaving] = useState(false)
  const [filters, setFilters] = useState({ search: '', type: '', theme: '', region: '', county: '' })
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
        stops,
      })
      const all = placesData.places || []
      setPlaces(all)
      setHotels(all.filter((p) => (p.category_type_name || '').toLowerCase() === 'accommodation' || (p.theme_name || '').toLowerCase() === 'home'))
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
                <label className="text-sm font-medium">Start</label>
                <Input type="date" value={draft.start_date} onChange={(e) => setDraft({ ...draft, start_date: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">End</label>
                <Input type="date" value={draft.end_date} onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
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
          </div>
        )}

        {step === 1 && (
          <div className="max-w-lg mx-auto space-y-3">
            <p className="text-sm text-slate-500">Pick end-of-day accommodation for each night.</p>
            {Array.from({ length: nDays }, (_, i) => i + 1).map((d) => {
              const current = draft.stops.find((s) => s.day_number === d && s.is_accommodation)
              return (
                <div key={d} className="flex items-center gap-3">
                  <span className="w-16 text-sm font-medium">Day {d}</span>
                  <select
                    className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800"
                    value={current?.location_id || ''}
                    onChange={(e) => setHotel(d, e.target.value)}
                  >
                    <option value="">No hotel</option>
                    {hotels.map((h) => (
                      <option key={h.id} value={h.id}>{h.name}{h.city ? ' · ' + h.city : ''}</option>
                    ))}
                  </select>
                </div>
              )
            })}
          </div>
        )}

        {step === 2 && (
          <div>
            <div className="flex gap-2 mb-3 overflow-x-auto">
              {Array.from({ length: nDays }, (_, i) => i + 1).map((d) => (
                <button key={d} onClick={() => setDay(d)} className={`px-+3 py-1 rounded-full text-sm ${d === day ? 'bg-brand-600 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}>
                  Day {d}
                </button>
              ))}
            </div>
            <Filters
              value={filters}
              onChange={setFilters}
              resultCount={filteredPlaces.length}
              fields={['search', 'type', 'theme', 'region', 'county']}
              options={{ type: typeOptions, theme: themeOptions, region: regionOptions, county: countyOptions }}
            />
            <div className="flex flex-col md:flex-row gap-4 mt-3">
              <div className="md:w-1/2 h-64 md:h-96">
                <MapView places={filteredPlaces} onSelect={addStop} />
              </div>
              <div className="md:w-1/2 space-y-2">
                {dayHotel && (
                  <div className="ring-2 ring-amber-300 rounded-xl">
                    <PlaceCard place={dayHotel} />
                  </div>
                )}
                {dayStops.map((s, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex-1"><PlaceCard place={s} /></div>
                    <button onClick={() => removeStop(draft.stops.indexOf(s))} className="text-red-500 text-sm px-2">Remove</button>
                  </div>
                ))}
                {dayStops.length === 0 && <p className="text-sm text-slate-500">Tap a place on the map to add it.</p>}
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="max-w-lg mx-auto space-y-4">
            <h3 className="font-semibold">{draft.name}</h3>
            <p className="text-sm text-slate-500">{draft.start_date} → {draft.end_date} · {nDays} days · {draft.stops.length} stops</p>
            {Array.from({ length: nDays }, (_, i) => i + 1).map((d) => (
              <div key={d}>
                <div className="text-sm font-medium mb-1">Day {d}</div>
                {draft.stops.filter((s) => s.day_number === d).map((s, i) => (
                  <div key={i} className={s.is_accommodation ? 'ring-2 ring-amber-300 rounded-xl mb-1' : 'mb-1'}>
                    <PlaceCard place={s} />
                  </div>
                ))}
              </div>
            ))}
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
    </div>
  )
}

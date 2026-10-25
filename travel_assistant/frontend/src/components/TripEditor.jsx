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
  const [cruiseShipId, setCruiseShipId] = useState(null)
  const [cruiseItin, setCruiseItin] = useState([])
  const [cruiseUrl, setCruiseUrl] = useState('')
  const [cruiseStart, setCruiseStart] = useState('')
  const [cruiseMsg, setCruiseMsg] = useState('')
  const [shipCruises, setShipCruises] = useState([])
  const [cruiseId, setCruiseId] = useState(null)
  const [cruiseDays, setCruiseDays] = useState([])
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
            category_type_name: s.category_type_name,
            primary_color: s.primary_color,
            icon_url: s.icon_url,
            image_url: s.image_url || s.visit_photo_url,
            latitude: s.latitude,
            longitude: s.longitude,
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
        trip_type: (trip.trip_type === 'standard' ? 'road_trip' : trip.trip_type) || 'road_trip',
        day_times: (() => { try { return JSON.parse(trip.day_times_json || '{}') } catch { return {} } })(),
        finish_place_id: trip.finish_place_id || '',
        align: trip.align || 'start',
        stops,
      })
      const all = placesData.places || []
      setPlaces(all)
      setHotels(all.filter((p) => {
        if (Number(p.hidden) === 1) return false
        const type = (p.category_type_name || '').toLowerCase()
        const theme = (p.theme_name || '').toLowerCase()
        return type === 'accommodation' || theme === 'hotels' || type === 'home location' || theme === 'home' || type.includes('cruise')
      }))
      fetch(base + '/api/settings').then((r) => r.json()).then((d) => setHome(d.home || null))
      fetch(base + '/api/trips/' + tripId + '/cruise').then(r => r.json()).then(d => {
        setCruiseShipId(d.ship?.id || null)
        setCruiseItin(d.itinerary || [])
      }).catch(() => {})
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
    return list
  }
  const placeById = (id) => placeOptions().find((p) => String(p.id) === String(id))

  const numCoord = (v) => {
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }
  const catalogById = (id) => {
    if (id == null || id === '') return null
    return places.find((p) => String(p.id) === String(id))
      || hotels.find((p) => String(p.id) === String(id))
      || (home && String(home.id) === String(id) ? home : null)
  }
  const asMapPoint = (item) => {
    if (!item) return null
    const catalog = catalogById(item.location_id || item.id)
    const lat = numCoord(item.latitude ?? item.lat ?? catalog?.latitude ?? catalog?.lat)
    const lng = numCoord(item.longitude ?? item.lng ?? catalog?.longitude ?? catalog?.lng)
    if (lat == null || lng == null) return null
    return {
      ...(catalog || {}),
      ...item,
      id: item.location_id || item.id,
      location_id: item.location_id || item.id,
      name: item.name || item.location_name || catalog?.name || 'Place',
      theme_name: item.theme_name || catalog?.theme_name,
      category_type_name: item.category_type_name || catalog?.category_type_name,
      primary_color: item.primary_color || catalog?.primary_color,
      latitude: lat,
      longitude: lng,
    }
  }

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
          category_type_name: place.category_type_name,
          primary_color: place.primary_color,
          icon_url: place.icon_url,
          image_url: place.image_url,
          latitude: place.latitude,
          longitude: place.longitude,
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
        category_type_name: place.category_type_name,
        primary_color: place.primary_color,
        icon_url: place.icon_url,
        image_url: place.image_url,
        latitude: place.latitude,
        longitude: place.longitude,
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


  // Map a cruise itinerary entry to a trip day number
  const tripDayFor = (entry, tripStart) => {
    if (tripStart && entry.date) {
      const a = new Date(tripStart)
      const b = new Date(entry.date)
      const diff = Math.round((b - a) / 86400000) + 1
      if (diff >= 1) return diff
    }
    return entry.trip_day || entry.day || 1
  }

  // Ship position for a trip day from the itinerary (source of truth)
  const shipForDay = (dayNum) => {
    // Match trip day to a cruise day by date (trip start is cruise start - 1)
    const entry = (cruiseDays || []).find((e) => {
      if (!draft.start_date || !e.date) return (e.day + 1) === dayNum
      const a = new Date(draft.start_date)
      const b = new Date(e.date)
      return Math.round((b - a) / 86400000) + 1 === dayNum
    })
    const ship = hotels.find((h) => String(h.id) === String(cruiseShipId))
    if (!entry || !ship) return null
    return {
      ...ship,
      name: ship.name + (entry.port ? ' · ' + entry.port : ''),
      city: entry.port || ship.city,
      latitude: entry.lat,
      longitude: entry.lon,
      cruise_port: entry.port,
      cruise_status: entry.status,
      image_url: entry.image_url || ship.image_url,
      is_accommodation: true,
      location_id: ship.id,
    }
  }


  const applyCruiseDays = (days, tripStart, shipId) => {
    const ship = hotels.find(h => String(h.id) === String(shipId || cruiseShipId))
    if (!ship || !days || !days.length || !tripStart) return
    const nights = days.slice(0, -1) // not the disembarkation day
    setDraft(d => {
      let stops = d.stops.filter(s => !(s.is_accommodation && String(s.location_id) === String(ship.id)))
      nights.forEach((entry) => {
        const cruiseDate = new Date(entry.date)
        const start = new Date(tripStart)
        const dayNum = Math.round((cruiseDate - start) / 86400000) + 1
        if (dayNum < 1) return
        stops = stops.filter(s => !(s.day_number === dayNum && s.is_accommodation))
        stops.push({
          location_id: ship.id,
          day_number: dayNum,
          name: ship.name + (entry.port ? ' · ' + entry.port : ''),
          city: entry.port || ship.city,
          latitude: entry.lat,
          longitude: entry.lon,
          is_accommodation: true,
          theme_name: ship.theme_name,
          category_type_name: ship.category_type_name,
          primary_color: ship.primary_color,
          icon_url: ship.icon_url,
          image_url: entry.image_url || ship.image_url,
          cruise_port: entry.port,
          cruise_status: entry.status,
        })
      })
      return { ...d, stops }
    })
    setCruiseMsg('Ship set for ' + nights.length + ' nights. Save to keep.')
  }

  const applyItinerary = (itin) => {
    if (!itin || !itin.length || !cruiseShipId) return
    const ship = hotels.find(h => String(h.id) === String(cruiseShipId))
    if (!ship) return
    const first = itin[0]
    const last = itin[itin.length - 1]
    setDraft(d => {
      // Drop previous ship nights
      let stops = d.stops.filter(s => !(s.is_accommodation && String(s.location_id) === String(cruiseShipId)))
      // Overnight on every cruise day except the last (disembarkation)
      itin.slice(0, -1).forEach((entry) => {
        const dayNum = tripDayFor(entry, d.start_date)
        if (dayNum < 1) return
        stops = stops.filter(s => !(s.day_number === dayNum && s.is_accommodation))
        const loc = entry.location || {}
        stops.push({
          location_id: ship.id,
          day_number: dayNum,
          name: ship.name + (entry.port ? ' · ' + entry.port : ''),
          city: entry.port || ship.city,
          latitude: loc.lat,
          longitude: loc.lon,
          is_accommodation: true,
          theme_name: ship.theme_name,
          category_type_name: ship.category_type_name,
          primary_color: ship.primary_color,
          icon_url: ship.icon_url,
          image_url: ship.image_url,
          cruise_port: entry.port,
          cruise_status: entry.status,
        })
      })
      return {
        ...d,
        start_date: d.start_date || first.date || '',
        end_date: d.end_date || last.date || '',
        stops,
      }
    })
    setCruiseMsg('Applied ' + (itin.length - 1) + ' nights. Last day starts at ' + (last.port || 'disembarkation') + '. Save to keep.')
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
              <label className="text-sm font-medium">Trip type</label>
              <select className="w-full mt-1 px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={draft.trip_type || 'road_trip'} onChange={(e) => setDraft({ ...draft, trip_type: e.target.value })}>
                <option value="road_trip">Road trip</option>
                <option value="cruise">Cruise</option>
                <option value="holiday">Holiday (including flight)</option>
                <option value="coach">Coach trip</option>
              </select>
              {(draft.trip_type === 'holiday' || draft.trip_type === 'coach') && (
                <p className="text-sm text-amber-600 mt-2">This trip type is not set up yet.</p>
              )}
            </div>
            {draft.trip_type === 'cruise' && (
              <div className="border border-slate-200 dark:border-slate-700 rounded-xl p-3 space-y-2">
                <div className="text-sm font-medium">1. Choose the ship</div>
                <select className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={cruiseShipId || ''} onChange={async (e) => {
                  const id = e.target.value ? Number(e.target.value) : null
                  setCruiseShipId(id); setCruiseId(null); setCruiseDays([])
                  if (id) {
                    const r = await fetch(base + '/api/ships/' + id + '/cruises')
                    const d = await r.json()
                    setShipCruises(d.cruises || [])
                  } else setShipCruises([])
                }}>
                  <option value="">Choose ship</option>
                  {hotels.filter(h => ((h.category_type_name || '') + ' ' + (h.theme_name || '')).toLowerCase().includes('cruise')).map(h => (
                    <option key={h.id} value={h.id}>{h.name}</option>
                  ))}
                </select>
                {cruiseShipId && (
                  <>
                    <div className="text-sm font-medium">2. Choose the cruise</div>
                    <select className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={cruiseId || ''} onChange={async (e) => {
                      const id = e.target.value ? Number(e.target.value) : null
                      setCruiseId(id)
                      if (!id) { setCruiseDays([]); return }
                      const r = await fetch(base + '/api/cruises/' + id)
                      const d = await r.json()
                      const days = d.days || []
                      setCruiseDays(days)
                      const use = await fetch(base + '/api/trips/' + tripId + '/use-cruise', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ cruise_id: id }) })
                      const u = await use.json()
                      if (u.ok) {
                        setDraft(dr => ({ ...dr, start_date: u.start_date, end_date: u.end_date, trip_type: 'cruise' }))
                        applyCruiseDays(days, u.start_date)
                      }
                    }}>
                      <option value="">Choose cruise</option>
                      {shipCruises.map(cr => (
                        <option key={cr.id} value={cr.id}>{cr.name || (cr.code + '-' + cr.year)}</option>
                      ))}
                    </select>
                    <p className="text-xs text-slate-500">Day 1 is the day before the cruise starts (travel day).</p>
                  </>
                )}
              </div>
            )}
            {(draft.trip_type === 'holiday' || draft.trip_type === 'coach') ? null : (
            <>
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
              {draft.trip_type !== 'cruise' && (
                <>
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
                </>
              )}
            </div>
            {draft.trip_type === 'cruise' && draft.start_date && draft.end_date && (
              <div className="space-y-2">
                <div className="text-sm font-medium">Times for each day</div>
                <p className="text-xs text-slate-500">Finish by is the time to be back on the ship. It can differ each day.</p>
                {Array.from({ length: nDays }, (_, i) => i + 1).map((d) => {
                  const t = (draft.day_times || {})[d] || {}
                  const setTime = (key, val) => setDraft(dr => ({ ...dr, day_times: { ...(dr.day_times || {}), [d]: { ...(dr.day_times || {})[d], [key]: val } } }))
                  return (
                    <div key={d} className="flex items-center gap-2">
                      <span className="w-14 text-sm">Day {d}</span>
                      <input type="time" className="flex-1 px-2 py-1 border rounded text-sm bg-white dark:bg-slate-800" value={t.start || '09:00'} onChange={(e) => setTime('start', e.target.value)} />
                      <input type="time" className="flex-1 px-2 py-1 border rounded text-sm bg-white dark:bg-slate-800" value={t.finish || '17:00'} onChange={(e) => setTime('finish', e.target.value)} />
                    </div>
                  )
                })}
              </div>
            )}
            <ImageUpload
              value={draft.image_url}
              uploadUrl={base + '/api/trips/' + tripId + '/image'}
              onUploaded={(url) => setDraft({ ...draft, image_url: url })}
            />
            <div>
              <label className="text-sm font-medium">Notes</label>
              <textarea className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" rows={3} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
            </div>
            </>
            )}
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
            {false && draft.trip_type === 'cruise' && (
            <div className="border border-slate-200 dark:border-slate-700 rounded-xl p-3 space-y-2">
              <div className="text-sm font-medium">Cruise</div>
              <p className="text-xs text-slate-500">Pick the ship, then a sailing (cruise number and year). Dates come from the sailing.</p>
              <select className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={cruiseShipId || ''} onChange={async (e) => {
                const id = e.target.value ? Number(e.target.value) : null
                setCruiseShipId(id)
                setCruiseId(null)
                setCruiseDays([])
                if (id) {
                  const r = await fetch(base + '/api/ships/' + id + '/cruises')
                  const d = await r.json()
                  setShipCruises(d.cruises || [])
                } else setShipCruises([])
              }}>
                <option value="">Choose ship</option>
                {hotels.filter(h => (h.category_type_name || '').toLowerCase().includes('cruise')).map(h => (
                  <option key={h.id} value={h.id}>{h.name}</option>
                ))}
              </select>
              {cruiseShipId && (
                <>
                  <select className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={cruiseId || ''} onChange={async (e) => {
                    const id = e.target.value ? Number(e.target.value) : null
                    setCruiseId(id)
                    if (!id) { setCruiseDays([]); return }
                    const r = await fetch(base + '/api/cruises/' + id)
                    const d = await r.json()
                    setCruiseDays(d.days || [])
                    const use = await fetch(base + '/api/trips/' + tripId + '/use-cruise', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ cruise_id: id }) })
                    const u = await use.json()
                    if (u.ok) setDraft(dr => ({ ...dr, start_date: u.start_date, end_date: u.end_date, trip_type: 'cruise' }))
                  }}>
                    <option value="">Choose cruise number</option>
                    {shipCruises.map(cr => (
                      <option key={cr.id} value={cr.id}>{cr.name || (cr.code + '-' + cr.year)}{cr.start_date ? ' · ' + cr.start_date : ''}</option>
                    ))}
                  </select>
                  <input className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" placeholder="Or paste a SeaScanner or P&O URL" value={cruiseUrl} onChange={e => setCruiseUrl(e.target.value)} />
                  <input type="date" className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={cruiseStart || ''} onChange={e => setCruiseStart(e.target.value)} title="Cruise departure date if the page does not show one" />
                  <Button variant="secondary" type="button" onClick={async () => {
                    if (!cruiseUrl.trim()) return
                    setCruiseMsg('Importing…')
                    const res = await fetch(base + '/api/ships/' + cruiseShipId + '/cruises/import', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ url: cruiseUrl, start_date: cruiseStart || undefined }) })
                    const d = await res.json()
                    if (d.ok) {
                      setCruiseMsg('Added ' + d.name)
                      const r = await fetch(base + '/api/ships/' + cruiseShipId + '/cruises')
                      const list = await r.json()
                      setShipCruises(list.cruises || [])
                      setCruiseId(d.cruise_id)
                      setCruiseDays(d.days || [])
                      const use = await fetch(base + '/api/trips/' + tripId + '/use-cruise', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ cruise_id: d.cruise_id }) })
                      const u = await use.json()
                      if (u.ok) setDraft(dr => ({ ...dr, start_date: u.start_date, end_date: u.end_date, trip_type: 'cruise' }))
                    } else setCruiseMsg(d.detail || 'Import failed')
                  }}>Import sailing</Button>
                  {cruiseMsg && <div className="text-xs text-slate-500">{cruiseMsg}</div>}
                  {cruiseDays.length > 0 && (
                    <div className="text-sm space-y-1 max-h-48 overflow-y-auto">
                      {cruiseDays.map((d, i) => (
                        <div key={i} className="flex items-center gap-2">
                          {d.image_url && <img src={d.image_url} alt="" className="w-10 h-10 rounded object-cover" />}
                          <span className="text-xs text-slate-400 w-16">Day {d.day}</span>
                          <span className="flex-1 truncate">{d.port}</span>
                          {d.date && <span className="text-xs text-slate-400">{d.date.slice(5)}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
            )}
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
                <MapView
                  zoom={(() => {
                    const acc = draft.stops.find(s => s.day_number === day && s.is_accommodation)
                    return (acc && acc.cruise_status === 'at_sea') ? 6 : undefined
                  })()}
                  places={(() => {
                    if (adding) {
                      return filteredPlaces.filter((p) => numCoord(p.latitude) != null && numCoord(p.longitude) != null && !draft.stops.some((s) => String(s.location_id) === String(p.id) && s.day_number === day))
                    }
                    const out = []
                    const push = (item, extra) => {
                      const point = asMapPoint(item)
                      if (!point) return
                      const marked = extra ? { ...point, ...extra } : point
                      const key = item._mapKey || (String(marked.location_id) + ':' + (marked.is_start ? 's' : 'p'))
                      if (out.some((x) => x._key === key)) return
                      marked._key = key
                      out.push(marked)
                    }
                    const isShip = (s) => s && cruiseShipId && String(s.location_id) === String(cruiseShipId)
                    const prevNight = draft.stops.find((s) => s.day_number === day - 1 && s.is_accommodation)
                    if (day === 1) {
                      push(placeById(draft.start_place_id) || home, { is_start: true, _mapKey: 'start-1' })
                    } else if (draft.trip_type === 'cruise' && !(prevNight && !isShip(prevNight))) {
                      // On the ship: start at today's itinerary position
                      const pos = shipForDay(day)
                      if (pos) push({ ...pos, _mapKey: 'start-' + day }, { is_start: true })
                    } else {
                      push(prevNight, { is_start: true, _mapKey: 'start-' + day })
                    }
                    draft.stops.filter((s) => s.day_number === day).forEach((s) => push({ ...s, _mapKey: 'stop-' + (s.id || s.location_id) + '-' + day }))
                    if (day === nDays) push(placeById(draft.finish_place_id))
                    return out
                  })()}
                  onSelect={adding ? addStop : undefined}
                  onView={(p) => setViewPlace(places.find((x) => x.id === (p.location_id || p.id)) || { ...p, id: p.location_id || p.id })}
                  connect={!adding}
                />
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
                  const prevNight = draft.stops.find((s) => s.day_number === day - 1 && s.is_accommodation)
                  const isShip = prevNight && cruiseShipId && String(prevNight.location_id) === String(cruiseShipId)
                  const prev = (draft.trip_type === 'cruise' && (isShip || !prevNight))
                    ? shipForDay(day)
                    : prevNight
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
              const prevNight = draft.stops.find((s) => s.day_number === d - 1 && s.is_accommodation)
              const isShip = prevNight && cruiseShipId && String(prevNight.location_id) === String(cruiseShipId)
              const start = d === 1
                ? (placeById(draft.start_place_id) || home)
                : ((draft.trip_type === 'cruise' && (isShip || !prevNight)) ? shipForDay(d) : prevNight)
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

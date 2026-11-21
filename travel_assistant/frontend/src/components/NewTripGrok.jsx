import { useEffect, useMemo, useRef, useState } from 'react'
import Button from './Button'
import Input from './Input'
import PlaceCard from './PlaceCard'
import Badge from './Badge'
import GrokNearbyMap from './GrokNearbyMap'
import GrokRouteReview from './GrokRouteReview'

export default function NewTripGrok({ base = '', onClose, onCreated }) {
  const [configured, setConfigured] = useState(null)
  const [text, setText] = useState('im going to Normanton Park Hotel on 15th January and would like to visit english heritage sites nearby please on the 16th and 17th')
  const [plan, setPlan] = useState(null)
  const [nearbyMap, setNearbyMap] = useState(null)
  const [step, setStep] = useState('pick') // pick | route
  const [routeDays, setRouteDays] = useState([])
  const [categories, setCategories] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const textRef = useRef(null)

  useEffect(() => {
    fetch(base + '/api/grok/status')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setConfigured(!!d.configured))
      .catch(() => setConfigured(null))
  }, [base])

  useEffect(() => {
    if (!plan) {
      // Let the modal paint, then focus so the box is ready to type into
      const t = setTimeout(() => textRef.current?.focus(), 50)
      return () => clearTimeout(t)
    }
  }, [plan])

  const setTrip = (field, value) => {
    setPlan((p) => ({ ...p, trip: { ...p.trip, [field]: value } }))
  }

  const applyMatch = (place, matched) => {
    if (!matched) {
      return { ...place, location_id: null, matched_place: null }
    }
    return {
      ...place,
      location_id: matched.id,
      matched_place: matched,
      category: matched.theme_name || place.category,
      city: place.city || matched.city || '',
      postcode: place.postcode || matched.postcode || '',
    }
  }

  const rematchPlace = async (index, name) => {
    try {
      const r = await fetch(base + '/api/command/match-places', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const d = await r.json().catch(() => ({}))
      const matched = d.matches?.[0]?.matched_place || null
      setPlan((p) => {
        const places = p.places.map((place, i) => (i === index ? applyMatch({ ...place, name }, matched) : place))
        return { ...p, places }
      })
    } catch (e) {
      // Leave the current match state alone if lookup fails
    }
  }

  const setPlace = (index, field, value) => {
    setPlan((p) => {
      const places = p.places.map((place, i) => {
        if (i !== index) return place
        const next = { ...place, [field]: value }
        if (field === 'name') {
          // Clear stale match until blur rematch runs
          next.location_id = null
          next.matched_place = null
        }
        if (field === 'is_accommodation') {
          const hotelCat = categories.find((c) => /hotel|accommodation/i.test(c.name || ''))
          const activities = categories.find((c) => (c.name || '').toLowerCase() === 'activities')
          if (value) next.category = hotelCat?.name || next.category || 'Hotels'
          else if (!next.category || /hotel|accommodation/i.test(next.category)) {
            next.category = activities?.name || 'Activities'
          }
        }
        return next
      })
      return { ...p, places }
    })
  }

  const removePlace = (index) => {
    setPlan((p) => ({ ...p, places: p.places.filter((_, i) => i !== index) }))
  }

  const planWithGrok = async () => {
    if (!text.trim()) {
      setError('Describe where you are going, when, and where you are staying.')
      return
    }
    setError('')
    setBusy(true)
    try {
      const r = await fetch(base + '/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.trim() }),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(d.detail || `Could not plan (${r.status})`)
      const cats = d.categories || []
      setCategories(cats)
      const activities = cats.find((c) => (c.name || '').toLowerCase() === 'activities')?.name || 'Activities'
      const hotelCat = cats.find((c) => /hotel|accommodation/i.test(c.name || ''))?.name || 'Hotels'
      const nameLooksHotel = (name) => /\b(hotel|motel|inn|guesthouse|guest house|b&b|bed and breakfast)\b/i.test(name || '')
      const places = (d.plan?.places || []).map((p) => {
        const name = p.name || ''
        const isHotel = !!p.is_accommodation || nameLooksHotel(name)
        let category = (p.category || '').trim()
        if (isHotel) category = hotelCat
        else if (!category) category = activities
        else if (/hotel|accommodation/i.test(category)) category = activities
        // Don't trust a matched cruise-ship card for a hotel name
        let matched = p.matched_place || null
        if (isHotel && matched && /cruise/i.test(`${matched.theme_name || ''} ${matched.category_type_name || ''}`)) {
          matched = null
        }
        const dayNumber = Math.max(1, Number(p.day_number) || 1)
        const dayNumbers = Array.isArray(p.day_numbers) && p.day_numbers.length
          ? [...new Set(p.day_numbers.map((d) => Math.max(1, Number(d) || 1)))].sort((a, b) => a - b)
          : [dayNumber]
        return {
          name,
          postcode: p.postcode || '',
          city: p.city || '',
          category: isHotel ? hotelCat : (matched?.theme_name || category),
          is_accommodation: isHotel,
          day_number: dayNumbers[0],
          day_numbers: dayNumbers,
          notes: p.notes || '',
          miles_from_hotel: p.miles_from_hotel,
          location_id: matched?.id || (matched ? p.location_id : null) || null,
          matched_place: matched,
        }
      })
      setPlan({
        trip: {
          name: d.plan?.trip?.name || 'New trip',
          start_date: d.plan?.trip?.start_date || '',
          end_date: d.plan?.trip?.end_date || '',
          notes: d.plan?.trip?.notes || '',
        },
        places,
      })
      setNearbyMap(d.nearby_map || null)
    } catch (e) {
      setError(e.message || 'Could not plan that trip.')
    }
    setBusy(false)
  }

  const dayByPlaceId = useMemo(() => {
    const map = {}
    for (const p of plan?.places || []) {
      if (p.location_id != null && !p.is_accommodation) map[p.location_id] = p.day_number
    }
    return map
  }, [plan])

  const addSiteToDay = (site, day) => {
    setPlan((p) => {
      if (!p) return p
      const id = site.id
      const existing = p.places.findIndex((x) => x.location_id === id && !x.is_accommodation)
      const row = {
        name: site.name || '',
        postcode: site.postcode || '',
        city: site.city || '',
        category: site.theme_name || 'English Heritage',
        is_accommodation: false,
        day_number: day,
        day_numbers: [day],
        notes: site.miles_from_hotel != null ? `${site.miles_from_hotel} miles from hotel` : '',
        miles_from_hotel: site.miles_from_hotel,
        location_id: id,
        matched_place: site,
        latitude: site.latitude,
        longitude: site.longitude,
      }
      const places = [...p.places]
      if (existing >= 0) places[existing] = { ...places[existing], ...row }
      else places.push(row)
      return { ...p, places }
    })
  }

  const removeSite = (site) => {
    setPlan((p) => {
      if (!p) return p
      return {
        ...p,
        places: p.places.filter((x) => !(x.location_id === site.id && !x.is_accommodation)),
      }
    })
  }

  const hotelForRoute = useMemo(() => {
    const fromPlan = (plan?.places || []).find((p) => p.is_accommodation)
    if (fromPlan) {
      return {
        name: fromPlan.name,
        latitude: fromPlan.latitude ?? fromPlan.matched_place?.latitude ?? nearbyMap?.hotel?.latitude,
        longitude: fromPlan.longitude ?? fromPlan.matched_place?.longitude ?? nearbyMap?.hotel?.longitude,
      }
    }
    return nearbyMap?.hotel || null
  }, [plan, nearbyMap])

  const buildDaysPayload = () => {
    const visits = (plan?.places || []).filter((p) => !p.is_accommodation)
    const byDay = {}
    for (const p of visits) {
      const day = Math.max(1, Number(p.day_number) || 1)
      if (!byDay[day]) byDay[day] = []
      byDay[day].push({
        ...p,
        latitude: p.latitude ?? p.matched_place?.latitude,
        longitude: p.longitude ?? p.matched_place?.longitude,
      })
    }
    return Object.keys(byDay)
      .map(Number)
      .sort((a, b) => a - b)
      .map((day) => ({ day, places: byDay[day] }))
  }

  const planRoute = async () => {
    if (!plan) return
    if (!(plan.trip?.name || '').trim()) {
      setError('Give the trip a name.')
      return
    }
    const days = buildDaysPayload()
    if (!days.length) {
      setError('Add at least one place from the map before creating the trip.')
      return
    }
    if (!hotelForRoute?.latitude || !hotelForRoute?.longitude) {
      setError('Hotel location is missing — cannot plan a route yet.')
      return
    }
    setError('')
    setBusy(true)
    try {
      const r = await fetch(base + '/api/command/order-days', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hotel: hotelForRoute, days }),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(d.detail || `Could not order days (${r.status})`)
      setRouteDays(d.days || days)
      setStep('route')
    } catch (e) {
      setError(e.message || 'Could not plan the route.')
    }
    setBusy(false)
  }

  const createTrip = async () => {
    if (!plan) return
    setError('')
    setBusy(true)
    try {
      const hotels = (plan.places || []).filter((p) => p.is_accommodation)
      const orderedVisits = []
      for (const block of routeDays) {
        for (const p of block.places || []) {
          orderedVisits.push({
            ...p,
            day_number: block.day,
            day_numbers: [block.day],
            is_accommodation: false,
          })
        }
      }
      const finalPlan = { ...plan, places: [...hotels, ...orderedVisits] }
      const r = await fetch(base + '/api/command/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: finalPlan }),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(d.detail || `Could not create trip (${r.status})`)
      onCreated?.(d.trip_id, d)
    } catch (e) {
      setError(e.message || 'Could not create the trip.')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4">
      <div className="bg-white dark:bg-slate-900 w-full sm:max-w-3xl sm:rounded-xl shadow-xl max-h-[92vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-lg font-semibold">New trip with Grok</h2>
          <button onClick={onClose} className="text-slate-500 text-sm px-2 py-1" disabled={busy}>Close</button>
        </div>

        <div className="overflow-y-auto p-4 space-y-4 flex-1">
          {configured === false && (
            <p className="text-sm text-amber-600">
              Add an xAI API key in Settings → xAI API key (or the add-on configuration) before planning with Grok.
            </p>
          )}

          {!plan && (
            <div className="space-y-3">
              <p className="text-sm text-slate-500">
                Describe where you are going, when, where you are staying, and any places you want to visit.
              </p>
              <textarea
                ref={textRef}
                className="w-full min-h-[160px] px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                placeholder="Type your trip details here…"
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={busy}
                autoFocus
              />
              <p className="text-xs text-slate-400">
                Example: Weekend in York, 14–16 March. Staying at The Grand York. Visit York Minster and the National Railway Museum.
              </p>
            </div>
          )}

          {plan && step === 'route' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold">Review driving order</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Grok ordered each day from the hotel. Check the map route and reorder stops if needed, then create the trip.
                </p>
              </div>
              <GrokRouteReview
                hotel={hotelForRoute}
                days={routeDays}
                onChangeDays={setRouteDays}
              />
              <button
                type="button"
                className="text-sm text-slate-500 underline"
                onClick={() => { setStep('pick'); setError('') }}
                disabled={busy}
              >
                Back to places
              </button>
            </div>
          )}

          {plan && step === 'pick' && (
            <div className="space-y-4">
              {nearbyMap?.hotel && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Nearby English Heritage</h3>
                  <p className="text-xs text-slate-500">
                    Hotel centred with 25 and 50 mile rings. Click a site to open details and add it to a day — nothing is added until you choose.
                  </p>
                  <GrokNearbyMap
                    hotel={nearbyMap.hotel}
                    sites={nearbyMap.sites || []}
                    visitDays={nearbyMap.visit_days || []}
                    dayByPlaceId={dayByPlaceId}
                    onAddToDay={addSiteToDay}
                    onRemove={removeSite}
                  />
                </div>
              )}

              <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl border p-3 space-y-2">
                <div>
                  <label className="text-xs font-medium text-slate-500">Trip name</label>
                  <Input value={plan.trip.name} onChange={(e) => setTrip('name', e.target.value)} disabled={busy} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-medium text-slate-500">Start</label>
                    <Input type="date" value={plan.trip.start_date} onChange={(e) => setTrip('start_date', e.target.value)} disabled={busy} />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-500">End</label>
                    <Input type="date" value={plan.trip.end_date} onChange={(e) => setTrip('end_date', e.target.value)} disabled={busy} />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-500">Notes</label>
                  <Input value={plan.trip.notes} onChange={(e) => setTrip('notes', e.target.value)} disabled={busy} />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Places</h3>
                  <span className="text-xs text-slate-500">{plan.places.length} in draft</span>
                </div>
                {plan.places.length === 0 && (
                  <p className="text-sm text-slate-500">No places in the draft. Go back and try a clearer description.</p>
                )}
                {plan.places.map((place, index) => (
                  <div key={index} className="bg-white dark:bg-slate-900 rounded-xl border p-3 space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      {place.matched_place ? (
                        <Badge color="green">Matched</Badge>
                      ) : (
                        <Badge color="amber">Unmatched</Badge>
                      )}
                      <span className="text-xs text-slate-400">
                        {place.is_accommodation && (place.day_numbers || []).length > 1
                          ? `Nights ${(place.day_numbers || []).join(' and ')}`
                          : place.is_accommodation
                            ? `Night ${place.day_number}`
                            : `Day ${place.day_number}`}
                        {place.miles_from_hotel != null ? ` · ${place.miles_from_hotel} mi` : ''}
                      </span>
                      <div className="flex-1" />
                      <button
                        type="button"
                        onClick={() => removePlace(index)}
                        className="text-xs text-red-500 px-2"
                        disabled={busy}
                      >
                        Remove
                      </button>
                    </div>

                    {place.matched_place ? (
                      <PlaceCard place={place.matched_place} />
                    ) : (
                      <p className="text-xs text-amber-700 dark:text-amber-300">
                        No existing place found — a new one will be created on save.
                      </p>
                    )}

                    <div className="flex gap-2">
                      <Input
                        className="flex-1"
                        value={place.name}
                        onChange={(e) => setPlace(index, 'name', e.target.value)}
                        onBlur={(e) => rematchPlace(index, e.target.value)}
                        placeholder="Place name"
                        disabled={busy}
                      />
                    </div>
                    {!place.matched_place && (
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-xs font-medium text-slate-500">City</label>
                          <Input value={place.city} onChange={(e) => setPlace(index, 'city', e.target.value)} disabled={busy} />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-slate-500">Postcode</label>
                          <Input value={place.postcode} onChange={(e) => setPlace(index, 'postcode', e.target.value)} disabled={busy} />
                        </div>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs font-medium text-slate-500">
                          {place.is_accommodation ? 'Nights (e.g. 1,2)' : 'Day'}
                        </label>
                        {place.is_accommodation ? (
                          <Input
                            value={(place.day_numbers || [place.day_number]).join(',')}
                            onChange={(e) => {
                              const days = e.target.value
                                .split(/[,\s]+/)
                                .map((x) => Number(x))
                                .filter((n) => Number.isFinite(n) && n >= 1)
                              const unique = [...new Set(days)].sort((a, b) => a - b)
                              setPlan((p) => {
                                const places = p.places.map((placeRow, i) => {
                                  if (i !== index) return placeRow
                                  const nextDays = unique.length ? unique : [1]
                                  return { ...placeRow, day_numbers: nextDays, day_number: nextDays[0] }
                                })
                                return { ...p, places }
                              })
                            }}
                            disabled={busy}
                          />
                        ) : (
                          <Input
                            type="number"
                            min="1"
                            value={place.day_number}
                            onChange={(e) => setPlace(index, 'day_number', Math.max(1, Number(e.target.value) || 1))}
                            disabled={busy}
                          />
                        )}
                      </div>
                      <div>
                        <label className="text-xs font-medium text-slate-500">Category</label>
                        <select
                          className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800"
                          value={place.category}
                          onChange={(e) => setPlace(index, 'category', e.target.value)}
                          disabled={busy || !!place.matched_place}
                        >
                          {!categories.some((c) => c.name === place.category) && place.category && (
                            <option value={place.category}>{place.category}</option>
                          )}
                          {categories.map((c) => (
                            <option key={c.id ?? c.name} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <label className="inline-flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={!!place.is_accommodation}
                        onChange={(e) => setPlace(index, 'is_accommodation', e.target.checked)}
                        disabled={busy}
                      />
                      Overnight / hotel
                    </label>
                  </div>
                ))}
              </div>

              <button
                type="button"
                className="text-sm text-slate-500 underline"
                onClick={() => {
                  setPlan(null)
                  setNearbyMap(null)
                  setRouteDays([])
                  setStep('pick')
                  setError('')
                }}
                disabled={busy}
              >
                Back to description
              </button>
            </div>
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>

        <div className="flex gap-2 justify-end px-4 py-3 border-t border-slate-200 dark:border-slate-700">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          {!plan ? (
            <Button onClick={planWithGrok} disabled={busy || configured === false}>
              {busy ? 'Planning… (can take a minute)' : 'Plan with Grok'}
            </Button>
          ) : step === 'route' ? (
            <Button onClick={createTrip} disabled={busy || !routeDays.length}>
              {busy ? 'Creating…' : 'Create trip'}
            </Button>
          ) : (
            <Button onClick={planRoute} disabled={busy}>
              {busy ? 'Ordering route…' : 'Create trip'}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

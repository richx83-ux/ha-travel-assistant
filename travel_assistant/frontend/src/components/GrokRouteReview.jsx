import { useMemo, useState } from 'react'
import MapView from './MapView'
import Button from './Button'

function coordsOf(p) {
  const lat = Number(p?.latitude ?? p?.matched_place?.latitude)
  const lon = Number(p?.longitude ?? p?.matched_place?.longitude)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  return { lat, lon }
}

function asMapPin(p, extras = {}) {
  const c = coordsOf(p)
  if (!c || !p) return null
  return {
    ...p,
    name: p.name || extras.name || 'Place',
    latitude: c.lat,
    longitude: c.lon,
    ...extras,
  }
}

/**
 * Review Grok's day routes: map with driving path + reorderable stop list.
 * Day 1 starts from startPlace (home); last day ends at finishPlace (home), not the hotel.
 */
export default function GrokRouteReview({
  hotel,
  startPlace,
  finishPlace,
  totalDays = 1,
  days = [],
  onChangeDays,
}) {
  const dayNums = days.map((d) => d.day)
  const lastDay = Math.max(totalDays || 1, ...(dayNums.length ? dayNums : [1]))
  const [activeDay, setActiveDay] = useState(dayNums[0] || 1)

  const block = days.find((d) => d.day === activeDay) || days[0]
  const places = block?.places || []
  const day = block?.day || activeDay

  const dayStart = day === 1 ? (startPlace || hotel) : hotel
  const dayEnd = day >= lastDay ? (finishPlace || startPlace) : hotel
  const endsAtHotel = day < lastDay

  const mapPlaces = useMemo(() => {
    const out = []
    const startPin = asMapPin(dayStart, {
      is_start: true,
      is_accommodation: !!(dayStart?.is_accommodation || dayStart?.is_home),
      theme_name: dayStart?.theme_name || (dayStart?.is_home ? 'Home' : undefined),
      _mapKey: 'day-start',
    })
    if (startPin) out.push(startPin)

    places.forEach((p, i) => {
      const pin = asMapPin(p, {
        id: p.location_id || p.id || i,
        location_id: p.location_id || p.id,
        icon_url: p.matched_place?.icon_url || p.icon_url,
        primary_color: p.matched_place?.primary_color || p.primary_color,
        theme_name: p.matched_place?.theme_name || p.category,
        _mapKey: 'stop-' + (p.location_id || p.name || i),
      })
      if (pin) out.push(pin)
    })

    const endPin = asMapPin(dayEnd, {
      is_accommodation: !!(dayEnd?.is_accommodation || dayEnd?.is_home || endsAtHotel),
      theme_name: dayEnd?.theme_name || (dayEnd?.is_home ? 'Home' : undefined),
      name: endsAtHotel
        ? ((dayEnd?.name || 'Hotel') + ' (overnight)')
        : ((dayEnd?.name || 'Home') + ' (finish)'),
      _mapKey: 'day-end',
    })
    // Only add end if it differs from start (or there are stops to connect)
    if (endPin && (places.length || endPin._mapKey !== startPin?._mapKey)) {
      const sameAsStart =
        startPin &&
        Math.abs(startPin.latitude - endPin.latitude) < 1e-5 &&
        Math.abs(startPin.longitude - endPin.longitude) < 1e-5
      if (!sameAsStart || places.length) {
        out.push(endPin)
      }
    }
    return out
  }, [dayStart, dayEnd, places, endsAtHotel])

  const updatePlaces = (next) => {
    onChangeDays?.(
      days.map((d) => (d.day === block.day ? { ...d, places: next } : d)),
    )
  }

  const move = (index, dir) => {
    const next = places.slice()
    const j = index + dir
    if (j < 0 || j >= next.length) return
    ;[next[index], next[j]] = [next[j], next[index]]
    updatePlaces(next)
  }

  const removeAt = (index) => {
    updatePlaces(places.filter((_, i) => i !== index))
  }

  if (!days.length) {
    return <p className="text-sm text-slate-500">No days to review.</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {days.map((d) => (
          <button
            key={d.day}
            type="button"
            onClick={() => setActiveDay(d.day)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium ${activeDay === d.day ? 'bg-brand-600 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}
          >
            Day {d.day}
            <span className="ml-1 opacity-70">({(d.places || []).length})</span>
          </button>
        ))}
      </div>

      <p className="text-xs text-slate-500">
        {day === 1 && day >= lastDay
          ? 'Day trip: from start, through stops, finish at end (no hotel return).'
          : day === 1
            ? 'Day 1: start → stops on the way → hotel overnight.'
            : day >= lastDay
              ? 'Last day: hotel → stops → finish (home) — not back to the hotel.'
              : 'Overnight day: hotel → stops → hotel.'}
        {' '}Reorder or remove stops before creating the trip.
      </p>

      <div className="h-64 sm:h-80 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800">
        <MapView places={mapPlaces} connect roadRoute zoom={10} />
      </div>

      <ol className="space-y-2">
        <li className="flex items-center gap-2 text-sm text-teal-700 dark:text-teal-300 px-1">
          <span className="w-6 h-6 rounded-full bg-teal-700 text-white text-xs flex items-center justify-center font-bold">S</span>
          Start: {dayStart?.name || 'Start'}
        </li>
        {places.map((p, i) => (
          <li
            key={(p.location_id || p.name || i) + '-' + i}
            className="flex items-center gap-2 bg-white dark:bg-slate-900 border rounded-xl p-2"
          >
            <span className="w-6 h-6 rounded-full bg-brand-600 text-white text-xs flex items-center justify-center font-bold shrink-0">
              {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{p.name}</div>
              <div className="text-xs text-slate-500 truncate">
                {[p.city, p.matched_place?.theme_name || p.category].filter(Boolean).join(' · ')}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <div className="flex flex-col gap-0.5">
                <Button
                  variant="secondary"
                  className="!px-2 !py-0.5 text-xs"
                  disabled={i === 0}
                  onClick={() => move(i, -1)}
                >
                  ↑
                </Button>
                <Button
                  variant="secondary"
                  className="!px-2 !py-0.5 text-xs"
                  disabled={i === places.length - 1}
                  onClick={() => move(i, 1)}
                >
                  ↓
                </Button>
              </div>
              <Button
                variant="secondary"
                className="!px-2 !py-1 text-xs text-red-600"
                onClick={() => removeAt(i)}
              >
                Remove
              </Button>
            </div>
          </li>
        ))}
        {places.length === 0 && (
          <li className="text-sm text-slate-500 px-1">No places on this day.</li>
        )}
        <li className={`flex items-center gap-2 text-sm px-1 ${endsAtHotel ? 'text-amber-700 dark:text-amber-300' : 'text-teal-700 dark:text-teal-300'}`}>
          <span className={`w-6 h-6 rounded-full text-white text-xs flex items-center justify-center font-bold ${endsAtHotel ? 'bg-amber-500' : 'bg-teal-700'}`}>
            {endsAtHotel ? 'B' : 'F'}
          </span>
          {endsAtHotel ? 'Overnight: ' : 'Finish: '}
          {dayEnd?.name || (endsAtHotel ? 'Hotel' : 'Home')}
        </li>
      </ol>
    </div>
  )
}

import { useMemo, useState } from 'react'
import MapView from './MapView'
import Button from './Button'

function coordsOf(p) {
  const lat = Number(p?.latitude ?? p?.matched_place?.latitude)
  const lon = Number(p?.longitude ?? p?.matched_place?.longitude)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  return { lat, lon }
}

/**
 * Review Grok's day routes: map with driving path + reorderable stop list.
 */
export default function GrokRouteReview({ hotel, days = [], onChangeDays }) {
  const dayNums = days.map((d) => d.day)
  const [activeDay, setActiveDay] = useState(dayNums[0] || 1)

  const block = days.find((d) => d.day === activeDay) || days[0]
  const places = block?.places || []

  const mapPlaces = useMemo(() => {
    const out = []
    if (hotel && coordsOf(hotel)) {
      out.push({
        ...hotel,
        name: hotel.name || 'Hotel',
        latitude: coordsOf(hotel).lat,
        longitude: coordsOf(hotel).lon,
        is_start: true,
        is_accommodation: true,
        _mapKey: 'hotel',
      })
    }
    places.forEach((p, i) => {
      const c = coordsOf(p)
      if (!c) return
      out.push({
        ...p,
        id: p.location_id || p.id || i,
        location_id: p.location_id || p.id,
        latitude: c.lat,
        longitude: c.lon,
        name: p.name,
        icon_url: p.matched_place?.icon_url || p.icon_url,
        primary_color: p.matched_place?.primary_color || p.primary_color,
        theme_name: p.matched_place?.theme_name || p.category,
        _mapKey: 'stop-' + (p.location_id || p.name || i),
      })
    })
    // Return to hotel at end of the day for a loop preview
    if (hotel && coordsOf(hotel) && places.length) {
      out.push({
        ...hotel,
        name: (hotel.name || 'Hotel') + ' (return)',
        latitude: coordsOf(hotel).lat,
        longitude: coordsOf(hotel).lon,
        is_accommodation: true,
        _mapKey: 'hotel-return',
      })
    }
    return out
  }, [hotel, places])

  const move = (index, dir) => {
    const next = places.slice()
    const j = index + dir
    if (j < 0 || j >= next.length) return
    ;[next[index], next[j]] = [next[j], next[index]]
    onChangeDays?.(
      days.map((d) => (d.day === block.day ? { ...d, places: next } : d)),
    )
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
        Suggested driving order from the hotel. Use the arrows to reorder stops before creating the trip.
      </p>

      <div className="h-64 sm:h-80 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800">
        <MapView places={mapPlaces} connect roadRoute zoom={10} />
      </div>

      <ol className="space-y-2">
        <li className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-300 px-1">
          <span className="w-6 h-6 rounded-full bg-amber-500 text-white text-xs flex items-center justify-center font-bold">H</span>
          Start / finish: {hotel?.name || 'Hotel'}
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
          </li>
        ))}
        {places.length === 0 && (
          <li className="text-sm text-slate-500 px-1">No places on this day.</li>
        )}
      </ol>
    </div>
  )
}

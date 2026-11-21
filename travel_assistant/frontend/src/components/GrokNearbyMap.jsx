import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import PlaceCard from './PlaceCard'
import Button from './Button'

const MILES_TO_M = 1609.344

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = (window.TA_BASE || window.location.pathname.replace(/\/react.*$/, '') || '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

function coords(p) {
  if (!p) return null
  const lat = Number(p.latitude ?? p.lat)
  const lng = Number(p.longitude ?? p.lng ?? p.lon)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  return [lat, lng]
}

function hotelIcon() {
  return L.divIcon({
    className: 'ta-pin',
    html: `<div style="width:32px;height:32px;border-radius:999px;background:#d97706;color:#fff;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;font:700 12px/1 system-ui,sans-serif">H</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  })
}

function siteIcon(selected, inTrip) {
  const bg = selected ? '#0f766e' : inTrip ? '#0d9488' : '#64748b'
  return L.divIcon({
    className: 'ta-pin',
    html: `<div style="width:24px;height:24px;border-radius:999px;background:${bg};color:#fff;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;font:700 10px/1 system-ui,sans-serif">EH</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  })
}

/**
 * Hotel-centred map with 25/50 mile rings and clickable English Heritage markers.
 */
export default function GrokNearbyMap({
  hotel,
  sites = [],
  visitDays = [],
  dayByPlaceId = {},
  onAddToDay,
  onRemove,
}) {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const layersRef = useRef(null)
  const [selected, setSelected] = useState(null)

  const hotelAt = coords(hotel)

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return
    const map = L.map(mapRef.current, {
      scrollWheelZoom: true,
      dragging: true,
      doubleClickZoom: true,
      boxZoom: false,
      keyboard: false,
      touchZoom: true,
    }).setView(hotelAt || [54.5, -3], 9)
    L.tileLayer(assetUrl('/api/tiles/{z}/{x}/{y}.png'), {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 19,
    }).addTo(map)
    layersRef.current = L.layerGroup().addTo(map)
    mapInstance.current = map
    const fix = () => map.invalidateSize()
    setTimeout(fix, 100)
    setTimeout(fix, 400)
    window.addEventListener('resize', fix)
    return () => {
      window.removeEventListener('resize', fix)
      map.remove()
      mapInstance.current = null
      layersRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapInstance.current
    const group = layersRef.current
    if (!map || !group || !hotelAt) return
    group.clearLayers()

    const circle50 = L.circle(hotelAt, {
      radius: 50 * MILES_TO_M,
      color: '#94a3b8',
      weight: 1,
      dashArray: '6 6',
      fillColor: '#94a3b8',
      fillOpacity: 0.06,
    }).addTo(group)
    L.circle(hotelAt, {
      radius: 25 * MILES_TO_M,
      color: '#0d9488',
      weight: 1.5,
      dashArray: '4 4',
      fillColor: '#0d9488',
      fillOpacity: 0.08,
    }).addTo(group)

    L.marker(hotelAt, { icon: hotelIcon(), zIndexOffset: 1000 })
      .bindTooltip(hotel?.name || 'Hotel', { direction: 'top' })
      .addTo(group)

    sites.forEach((site) => {
      const at = coords(site)
      if (!at) return
      const id = site.id
      const inTrip = dayByPlaceId[id] != null
      const isSel = selected && selected.id === id
      const marker = L.marker(at, { icon: siteIcon(isSel, inTrip) }).addTo(group)
      const tip = `${site.name || 'Place'}${site.miles_from_hotel != null ? ` · ${site.miles_from_hotel} mi` : ''}`
      marker.bindTooltip(tip, { direction: 'top' })
      marker.on('click', () => setSelected(site))
    })

    try {
      map.fitBounds(circle50.getBounds(), { padding: [20, 20], maxZoom: 10 })
    } catch (e) {
      map.setView(hotelAt, 9)
    }
    setTimeout(() => map.invalidateSize(), 50)
  }, [hotelAt, hotel, sites, dayByPlaceId, selected])

  if (!hotelAt) {
    return (
      <p className="text-sm text-slate-500">
        Could not place the hotel on the map (no coordinates yet).
      </p>
    )
  }

  const currentDay = selected ? dayByPlaceId[selected.id] : null

  return (
    <div className="space-y-3">
      <div className="relative w-full h-64 sm:h-80 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800">
        <div ref={mapRef} className="absolute inset-0 z-0" />
        <div className="absolute top-2 left-2 z-[500] bg-white/90 dark:bg-slate-900/90 rounded-lg px-2 py-1 text-[11px] text-slate-600 dark:text-slate-300 shadow">
          <span className="inline-block w-3 border-t border-teal-600 border-dashed mr-1 align-middle" />25 mi
          <span className="inline-block w-3 border-t border-slate-400 border-dashed mx-1 ml-2 align-middle" />50 mi
        </div>
      </div>

      {selected && (
        <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl border p-3 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="text-sm font-medium">
              {selected.name}
              {selected.miles_from_hotel != null && (
                <span className="text-slate-500 font-normal"> · {selected.miles_from_hotel} mi from hotel</span>
              )}
            </div>
            <button type="button" className="text-xs text-slate-500" onClick={() => setSelected(null)}>Close</button>
          </div>
          <PlaceCard place={selected} />
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">Add to day:</span>
            {(visitDays.length ? visitDays : [1]).map((day) => (
              <Button
                key={day}
                variant={currentDay === day ? 'primary' : 'secondary'}
                className="!px-3 !py-1 text-xs"
                onClick={() => onAddToDay?.(selected, day)}
              >
                Day {day}{currentDay === day ? ' ✓' : ''}
              </Button>
            ))}
            {currentDay != null && (
              <button
                type="button"
                className="text-xs text-red-500 px-2"
                onClick={() => onRemove?.(selected)}
              >
                Remove from trip
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

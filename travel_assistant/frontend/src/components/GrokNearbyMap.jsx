import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import PlaceDetail from './PlaceDetail'
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

function siteIcon(site, selected, inTrip) {
  const ring = selected ? '#0f766e' : inTrip ? '#0d9488' : '#ffffff'
  const iconUrl = assetUrl(site?.icon_url)
  const safe = iconUrl.replace(/"/g, '')
  // Use the category icon as the pin (circular clip). Fallback to a plain coloured dot.
  const inner = safe
    ? `<img src="${safe}" alt="" style="width:100%;height:100%;object-fit:contain;pointer-events:none;display:block" />`
    : `<span style="font:700 10px/1 system-ui,sans-serif;color:#fff">EH</span>`
  return L.divIcon({
    className: 'ta-pin',
    html: `<div style="width:28px;height:28px;border-radius:999px;background:#fff;border:2px solid ${ring};box-shadow:0 1px 4px rgba(0,0,0,.4);overflow:hidden;display:flex;align-items:center;justify-content:center;cursor:pointer;${!safe ? 'background:#0d9488;' : ''}">${inner}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
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
  const markersRef = useRef(new Map())
  const [selected, setSelected] = useState(null)
  const fittedRef = useRef(false)

  const hotelAt = useMemo(
    () => coords(hotel),
    [hotel?.latitude, hotel?.longitude, hotel?.lat, hotel?.lon],
  )

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
      markersRef.current = new Map()
      fittedRef.current = false
    }
  }, [])

  // Circles + hotel + site markers (rebuild when sites/hotel change, not on every selection)
  useEffect(() => {
    const map = mapInstance.current
    const group = layersRef.current
    if (!map || !group || !hotelAt) return
    group.clearLayers()
    markersRef.current = new Map()

    const circleOpts = { interactive: false, bubblingMouseEvents: false }
    const circle50 = L.circle(hotelAt, {
      ...circleOpts,
      radius: 50 * MILES_TO_M,
      color: '#94a3b8',
      weight: 1,
      dashArray: '6 6',
      fillColor: '#94a3b8',
      fillOpacity: 0.06,
    }).addTo(group)
    L.circle(hotelAt, {
      ...circleOpts,
      radius: 25 * MILES_TO_M,
      color: '#0d9488',
      weight: 1.5,
      dashArray: '4 4',
      fillColor: '#0d9488',
      fillOpacity: 0.08,
    }).addTo(group)

    L.marker(hotelAt, { icon: hotelIcon(), zIndexOffset: 1000, interactive: true })
      .bindTooltip(hotel?.name || 'Hotel', { direction: 'top' })
      .addTo(group)

    sites.forEach((site) => {
      const at = coords(site)
      if (!at) return
      const id = site.id
      const inTrip = dayByPlaceId[id] != null
      const isSel = selected && selected.id === id
      const marker = L.marker(at, {
        icon: siteIcon(site, isSel, inTrip),
        zIndexOffset: isSel ? 800 : 400,
        riseOnHover: true,
      }).addTo(group)
      const tip = `${site.name || 'Place'}${site.miles_from_hotel != null ? ` · ${site.miles_from_hotel} mi` : ''}`
      marker.bindTooltip(tip, { direction: 'top', sticky: true })
      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e)
        setSelected(site)
      })
      markersRef.current.set(id, marker)
    })

    if (!fittedRef.current) {
      try {
        map.fitBounds(circle50.getBounds(), { padding: [20, 20], maxZoom: 10 })
        fittedRef.current = true
      } catch (e) {
        map.setView(hotelAt, 9)
      }
    }
    setTimeout(() => map.invalidateSize(), 50)
  }, [hotelAt, hotel?.name, sites, dayByPlaceId])

  // Update selected marker style without rebuilding the whole layer
  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      const site = sites.find((s) => s.id === id)
      if (!site) return
      const inTrip = dayByPlaceId[id] != null
      const isSel = selected && selected.id === id
      marker.setIcon(siteIcon(site, isSel, inTrip))
      marker.setZIndexOffset(isSel ? 800 : 400)
    })
  }, [selected, sites, dayByPlaceId])

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
        <div className="absolute top-2 left-2 z-[500] bg-white/90 dark:bg-slate-900/90 rounded-lg px-2 py-1 text-[11px] text-slate-600 dark:text-slate-300 shadow pointer-events-none">
          <span className="inline-block w-3 border-t border-teal-600 border-dashed mr-1 align-middle" />25 mi
          <span className="inline-block w-3 border-t border-slate-400 border-dashed mx-1 ml-2 align-middle" />50 mi
        </div>
      </div>

      {selected && (
        <PlaceDetail
          place={selected}
          onClose={() => setSelected(null)}
          footer={
            <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-700 space-y-2">
              {selected.miles_from_hotel != null && (
                <p className="text-xs text-slate-500">{selected.miles_from_hotel} miles from hotel</p>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">Add to trip:</span>
                {(visitDays.length ? visitDays : [1]).map((day) => (
                  <Button
                    key={day}
                    variant={currentDay === day ? 'primary' : 'secondary'}
                    className="!px-3 !py-1.5 text-sm"
                    onClick={() => {
                      onAddToDay?.(selected, day)
                      setSelected(null)
                    }}
                  >
                    Day {day}{currentDay === day ? ' ✓' : ''}
                  </Button>
                ))}
              </div>
              {currentDay != null && (
                <button
                  type="button"
                  className="text-sm text-red-500"
                  onClick={() => {
                    onRemove?.(selected)
                    setSelected(null)
                  }}
                >
                  Remove from trip
                </button>
              )}
            </div>
          }
        />
      )}
    </div>
  )
}

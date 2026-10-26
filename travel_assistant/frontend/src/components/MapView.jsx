import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

function coords(p) {
  const lat = Number(p.latitude ?? p.lat)
  const lng = Number(p.longitude ?? p.lng ?? p.lon)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  return [lat, lng]
}

function pinKind(p) {
  const type = String(p.category_type_name || '').toLowerCase()
  const theme = String(p.theme_name || '').toLowerCase()
  if (p.is_start || type.includes('home') || theme === 'home' || theme === 'homes') return 'home'
  if (p.is_accommodation || type === 'accommodation' || theme === 'hotel' || theme === 'hotels') return 'hotel'
  return 'place'
}

function pinIcon(p, index) {
  const iconUrl = assetUrl(p.icon_url)
  if (iconUrl) {
    return L.icon({ iconUrl, iconSize: [28, 28], iconAnchor: [14, 28], popupAnchor: [0, -28] })
  }
  const kind = pinKind(p)
  const label = p.is_start ? 'S' : kind === 'home' ? 'H' : kind === 'hotel' ? 'B' : String(index)
  const bg = p.is_start || kind === 'hotel' ? '#d97706' : kind === 'home' ? '#0f766e' : (p.primary_color || '#0d9488')
  return L.divIcon({
    className: 'ta-pin',
    html: `<div style="width:28px;height:28px;border-radius:999px;background:${bg};color:#fff;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;font:700 12px/1 system-ui,sans-serif">${label}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -16],
  })
}

export default function MapView({ places = [], onSelect, onView, connect = false, zoom, focus }) {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const [active, setActive] = useState(false)

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return
    const tesla = /tesla/i.test(navigator.userAgent)
    const map = L.map(mapRef.current, {
      scrollWheelZoom: true,
      dragging: true,
      doubleClickZoom: true,
      boxZoom: false,
      keyboard: false,
      touchZoom: true,
    }).setView([54.5, -3], 6)
    L.tileLayer(assetUrl('/api/tiles/{z}/{x}/{y}.png'), {
      attribution: '&copy; OpenStreetMap France',
      maxZoom: 19,
    }).addTo(map)
    mapInstance.current = map
    if (tesla) setActive(true)
    const fix = () => map.invalidateSize()
    setTimeout(fix, 100)
    setTimeout(fix, 500)
    window.addEventListener('resize', fix)
    return () => {
      window.removeEventListener('resize', fix)
      map.remove()
      mapInstance.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapInstance.current
    if (!map) return
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker || layer instanceof L.Polyline) map.removeLayer(layer)
    })
    const plotted = []
    places.forEach((p) => {
      const at = coords(p)
      if (!at) return
      plotted.push({ p, at })
    })
    if (focus && focus.lat != null && focus.lon != null) {
      const at = [Number(focus.lat), Number(focus.lon)]
      const marker = L.marker(at, { icon: pinIcon({ is_accommodation: true, name: focus.port }, 1) }).addTo(map)
      marker.bindPopup('<div class="text-sm font-medium">' + (focus.port || 'Port') + '</div>')
      map.setView(at, focus.status === 'at_sea' ? 6 : (zoom || 10))
      setTimeout(() => map.invalidateSize(), 50)
      return
    }
    if (plotted.length === 0) return
    const bounds = []
    plotted.forEach(({ p, at }, i) => {
      const marker = L.marker(at, { icon: pinIcon(p, i + 1) }).addTo(map)
      const name = (p.name || p.location_name || 'Place').replace(/</g, '')
      const popup = L.popup().setContent(
        '<div class="text-sm">' +
        '<div class="font-medium mb-2">' + name + '</div>' +
        '<div class="flex gap-2">' +
        '<button class="map-view px-2 py-1 border rounded text-xs">View details</button>' +
        (onSelect ? '<button class="map-add px-2 py-1 bg-teal-600 text-white rounded text-xs">Add to trip</button>' : '') +
        '</div></div>'
      )
      marker.bindPopup(popup)
      marker.on('popupopen', (e) => {
        const el = e.popup.getElement()
        el.querySelector('.map-view')?.addEventListener('click', () => onView && onView(p))
        el.querySelector('.map-add')?.addEventListener('click', () => { onSelect && onSelect(p); marker.closePopup() })
      })
      bounds.push(at)
    })
    if (connect && bounds.length > 1) {
      L.polyline(bounds, { color: '#0d9488', weight: 4, opacity: 0.9 }).addTo(map)
    }
    const z = zoom || 12
    const key = bounds.map((b) => b[0].toFixed(4) + ',' + b[1].toFixed(4)).join('|') + '|' + (zoom || '')
    const fit = () => {
      map.invalidateSize()
      if (bounds.length === 1) map.setView(bounds[0], z)
      else if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: z })
    }
    if (map._fitKey !== key) {
      map._fitKey = key
      setTimeout(fit, 50)
    }
  }, [places, onSelect, onView, connect, zoom, focus])

  const enable = () => setActive(true)

  return (
    <div className="relative w-full h-full min-h-[280px] md:min-h-[400px] rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 z-0">
      <div ref={mapRef} className="absolute inset-0 z-0" />
      {!active && (
        <button
          onClick={enable}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-white dark:bg-slate-900 rounded-full text-sm font-medium shadow-lg border border-slate-300 pointer-events-auto" style={{ zIndex: 2000 }}
        >
          Click to move map
        </button>
      )}
    </div>
  )
}

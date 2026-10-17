import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function MapView({ places = [], onSelect, onView }) {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const [active, setActive] = useState(false)

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return
    const map = L.map(mapRef.current, {
      scrollWheelZoom: false,
      dragging: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
      touchZoom: false,
    }).setView([54.5, -3], 6)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 20,
    }).addTo(map)
    mapInstance.current = map
    return () => {
      map.remove()
      mapInstance.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapInstance.current
    if (!map) return
    // Clear existing markers
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker) map.removeLayer(layer)
    })
    const withCoords = places.filter((p) => p.latitude && p.longitude)
    if (withCoords.length === 0) return
    const bounds = []
    withCoords.forEach((p) => {
      const iconUrl = assetUrl(p.icon_url)
      const icon = iconUrl
        ? L.icon({ iconUrl, iconSize: [28, 28], iconAnchor: [14, 28], popupAnchor: [0, -28] })
        : L.divIcon({
            className: '',
            html: `<div style="width:24px;height:24px;border-radius:50%;background:${p.primary_color || '#0d9488'};border:2px solid white"></div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          })
      const marker = L.marker([p.latitude, p.longitude], { icon }).addTo(map)
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
      bounds.push([p.latitude, p.longitude])
    })
    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 })
  }, [places, onSelect])

  const enable = () => {
    const map = mapInstance.current
    if (!map) return
    map.dragging.enable()
    map.scrollWheelZoom.enable()
    map.doubleClickZoom.enable()
    map.touchZoom.enable()
    setActive(true)
  }

  return (
    <div className="relative w-full h-full min-h-[280px] md:min-h-[400px] rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 z-0">
      <div ref={mapRef} className="absolute inset-0" />
      {!active && (
        <button
          onClick={enable}
          className="absolute inset-0 z-10 bg-black/10 flex items-center justify-center"
        >
          <span className="px-3 py-1.5 bg-white/90 dark:bg-slate-900/90 rounded-full text-sm font-medium shadow">
            Click to move map
          </span>
        </button>
      )}
    </div>
  )
}

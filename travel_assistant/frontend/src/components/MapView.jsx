import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function MapView({ places = [], onSelect }) {
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
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
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
      marker.on('click', () => onSelect && onSelect(p))
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

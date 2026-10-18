import { useState } from 'react'
import Badge from './Badge'
import PlaceDetail from './PlaceDetail'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function PlaceCard({ place, onUpdated }) {
  const [open, setOpen] = useState(false)
  const [full, setFull] = useState(null)
  const location = [place.city, place.county].filter(Boolean).join(', ') || place.region || ''
  const raw = place.image_url || place.visit_photo_url || place.default_image_url || ''
  const photo = assetUrl(raw)
  const icon = assetUrl(place.icon_url)

  // Normalise so PlaceDetail always has the fields it expects
  const detail = {
    ...place,
    id: place.id || place.location_id,
    name: place.name || place.location_name || place.custom_name || 'Place',
  }

  return (
    <>
      <div onClick={() => {
        const id = place.location_id || place.id
        if (id) {
          const base = window.location.pathname.replace(/\/react.*$/, '') || ''
          fetch(base + '/api/places/' + id).then((r) => r.ok ? r.json() : null).then((p) => setFull(p)).catch(() => {})
        }
        setOpen(true)
      }} className="flex items-center gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:shadow-sm transition-shadow cursor-pointer">
        <div className="relative flex-shrink-0">
          <div
            className="w-12 h-12 rounded-lg flex items-center justify-center text-white text-sm font-medium overflow-hidden"
            style={{ backgroundColor: place.primary_color || '#0d9488' }}
          >
            {photo ? (
              <img src={photo} alt="" className="w-full h-full object-cover" />
            ) : (
              (detail.name || '?')[0]
            )}
          </div>
          {icon && (
            <img
              src={icon}
              alt=""
              className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-white dark:border-slate-900 bg-white object-contain"
            />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-slate-900 dark:text-slate-100 truncate">{detail.name}</div>
          {location && <div className="text-sm text-slate-500 truncate">{location}</div>}
          <div className="text-xs text-slate-400 truncate">{place.theme_name}</div>
        </div>
        {(() => {
          const noVisits = place.hide_visit_status || ['accommodation', 'hotel', 'hotels', 'home'].includes((place.category_type_name || '').toLowerCase()) || (place.theme_name || '').toLowerCase() === 'hotels'
          if (noVisits && !place.hidden) return null
          return (
            <Badge color={place.hidden ? 'gray' : place.visited ? 'green' : 'gray'}>
              {place.hidden ? 'Hidden' : place.visited ? 'Visited' : 'Not visited'}
            </Badge>
          )
        })()}
      </div>
      {open && (
        <PlaceDetail
          place={full || detail}
          onClose={() => setOpen(false)}
          onSaved={(updated) => { onUpdated && onUpdated(updated); setOpen(false) }}
        />
      )}
    </>
  )
}

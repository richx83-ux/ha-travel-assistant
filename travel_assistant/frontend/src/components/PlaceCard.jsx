import { useState, useEffect } from 'react'
import Badge from './Badge'
import PlaceDetail from './PlaceDetail'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}



function gbDate(iso) {
  if (!iso) return ''
  const [y, m, d] = String(iso).slice(0, 10).split('-')
  return d && m && y ? d + '-' + m + '-' + y : iso
}
function isCruise(place) {
  const t = ((place.category_type_name || '') + ' ' + (place.theme_name || '')).toLowerCase()
  return t.includes('cruise')
}

function ShipTree({ shipId, onShowDay }) {
  const [cruises, setCruises] = useState([])
  const [openId, setOpenId] = useState(null)
  const [days, setDays] = useState({})
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  useEffect(() => {
    fetch(base + '/api/ships/' + shipId + '/cruises')
      .then(r => r.json())
      .then(d => setCruises(d.cruises || []))
      .catch(() => {})
  }, [shipId])
  const toggle = async (id, e) => {
    e.stopPropagation()
    if (openId === id) { setOpenId(null); return }
    setOpenId(id)
    if (!days[id]) {
      const r = await fetch(base + '/api/cruises/' + id)
      const d = await r.json()
      setDays(prev => ({ ...prev, [id]: d.days || [] }))
    }
  }
  if (!cruises.length) return <div className="px-3 pb-2 text-xs text-slate-500">No sailings yet. Open the ship and import a cruise URL.</div>
  return (
    <div className="px-3 pb-2 space-y-1" onClick={(e) => e.stopPropagation()}>
      {cruises.map((cr) => (
        <div key={cr.id} className="border border-slate-200 dark:border-slate-700 rounded-lg">
          <button type="button" className="w-full flex items-center justify-between px-2 py-1.5 text-sm" onClick={(e) => toggle(cr.id, e)}>
            <span>{cr.name || (cr.code + '-' + cr.year)}</span>
            <span className="text-xs text-slate-400">{openId === cr.id ? '▾' : '▸'}</span>
          </button>
          {openId === cr.id && (
            <div className="px-2 pb-2 space-y-1">
              {(days[cr.id] || []).map((d) => (
                <button type="button" key={d.day} className="w-full flex items-center gap-2 text-xs text-left hover:bg-slate-100 dark:hover:bg-slate-800 rounded px-1 py-0.5" onClick={() => onShowDay && onShowDay(d)}>
                  {d.image_url && <img src={d.image_url} alt="" className="w-6 h-6 rounded object-cover" />}
                  <span className="text-slate-400 w-10">Day {d.day}</span>
                  <span className="text-slate-400 w-20">{gbDate(d.date)}</span>
                  <span className="flex-1 truncate">{d.port}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default function PlaceCard({ place, onUpdated, onShowDay }) {
  const [open, setOpen] = useState(false)
  const [full, setFull] = useState(null)
  const [expanded, setExpanded] = useState(false)
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
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
      <div onClick={() => {
        const id = place.location_id || place.id
        if (id) {
          const base = window.location.pathname.replace(/\/react.*$/, '') || ''
          fetch(base + '/api/places/' + id).then((r) => r.ok ? r.json() : null).then((p) => setFull(p)).catch(() => {})
        }
        setOpen(true)
      }} className="flex items-center gap-3 p-3 cursor-pointer">
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
        {isCruise(place) && (
          <button type="button" className="text-slate-400 px-2 text-lg" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}>{expanded ? '▾' : '▸'}</button>
        )}
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
      {isCruise(place) && expanded && <ShipTree shipId={place.id || place.location_id} onShowDay={onShowDay} />}
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

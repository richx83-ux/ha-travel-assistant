import { useState, useEffect } from 'react'

function assetUrl(url, base) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return (base || '') + (url.startsWith('/') ? url : '/' + url)
}

function daysToGo(trip) {
  if (!trip?.start_date) return null
  const start = new Date(trip.start_date + 'T00:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((start - today) / 86400000)
}

const ICONS = {
  trips: 'M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7',
  places: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z',
  categories: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z',
  cupboard: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
  achievements: 'M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z',
  settings: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
}

const SIZES = ['small', 'medium', 'large', 'wide']
const SIZE_CLASS = {
  small: 'col-span-1 row-span-1 min-h-[140px]',
  medium: 'col-span-1 sm:col-span-2 row-span-1 min-h-[160px]',
  large: 'col-span-1 sm:col-span-2 row-span-2 min-h-[320px]',
  wide: 'col-span-1 sm:col-span-2 lg:col-span-4 min-h-[200px]',
}

function Icon({ d }) {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d={d} />
    </svg>
  )
}

export default function Dashboard({ base = '', onOpenTrips, onOpenPlaces, onOpenCategories, onOpenCupboard, onOpenSettings, onViewPlace, onViewTrip }) {
  const [trips, setTrips] = useState([])
  const [places, setPlaces] = useState([])
  const [categories, setCategories] = useState([])
  const [items, setItems] = useState([])
  const [bags, setBags] = useState([])
  const [sizes, setSizes] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ta-tile-sizes') || '{}') } catch { return {} }
  })
  const [editing, setEditing] = useState(null)
  const [chosen, setChosen] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ta-tile-trips') || 'null') } catch { return null }
  })

  useEffect(() => {
    fetch(base + '/api/trips').then((r) => r.ok ? r.json() : { trips: [] }).then((d) => setTrips(d.trips || [])).catch(() => {})
    fetch(base + '/api/places').then((r) => r.ok ? r.json() : { places: [] }).then((d) => setPlaces(d.places || [])).catch(() => {})
    fetch(base + '/api/categories').then((r) => r.ok ? r.json() : { categories: [] }).then((d) => setCategories(d.categories || [])).catch(() => {})
    fetch(base + '/api/packing').then((r) => r.ok ? r.json() : { items: [], bags: [] }).then((d) => {
      setItems(d.items || [])
      setBags(d.bags || [])
    }).catch(() => {})
  }, [base])

  const setSize = (id, size) => {
    const next = { ...sizes, [id]: size }
    setSizes(next)
    localStorage.setItem('ta-tile-sizes', JSON.stringify(next))
    setEditing(null)
  }

  const inProgress = trips.filter((t) => t.status === 'active')
  const upcoming = trips
    .filter((t) => t.status !== 'completed' && t.status !== 'active')
    .map((t) => ({ ...t, days: daysToGo(t) }))
    .filter((t) => t.days == null || t.days >= 0)
    .sort((a, b) => (a.days ?? 9999) - (b.days ?? 9999))
  const next = upcoming[0]
  const recent = places.filter((p) => p.visited && p.visit_date).sort((a, b) => String(b.visit_date).localeCompare(String(a.visit_date))).slice(0, 5)
  const byCat = {}
  items.forEach((it) => { const c = it.category || 'Other'; byCat[c] = (byCat[c] || 0) + 1 })
  const topCats = Object.entries(byCat).sort((a, b) => b[1] - a[1]).slice(0, 4)
  const totalItems = items.length || 1

  const Tile = ({ id, title, icon, accent, onClick, children, extraEdit }) => {
    const size = sizes[id] || 'medium'
    return (
      <div className={`relative text-left rounded-2xl p-4 ${accent} ${SIZE_CLASS[size]}`}>
        <button type="button" onClick={onClick} className="absolute inset-0 rounded-2xl" aria-label={title} />
        <div className="relative pointer-events-none">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-9 h-9 rounded-lg bg-white/70 dark:bg-black/30 flex items-center justify-center"><Icon d={icon} /></span>
            <span className="font-semibold">{title}</span>
          </div>
          {children}
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setEditing(editing === id ? null : id) }}
          className="absolute top-2 right-2 z-10 w-7 h-7 rounded-full bg-white/80 dark:bg-black/40 text-slate-600 dark:text-white flex items-center justify-center"
          title="Resize"
          aria-label="Resize tile"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
        </button>
        {editing === id && (
          <div className="absolute top-10 right-2 z-20 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-1 text-sm">
            {SIZES.map((s) => (
              <button key={s} type="button" onClick={() => setSize(id, s)} className={`block w-full text-left px-3 py-1.5 rounded capitalize ${size === s ? 'bg-slate-100 dark:bg-slate-700' : ''}`}>{s}</button>
            ))}
            {extraEdit}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      {inProgress.length > 0 && (
        <div className="rounded-2xl border border-teal-300 dark:border-teal-700 bg-teal-50 dark:bg-teal-950 p-4">
          <div className="text-xs font-medium text-teal-700 dark:text-teal-300 mb-2">In progress</div>
          <ul className="space-y-2">
            {inProgress.map((t) => (
              <li key={t.id}>
                <button type="button" onClick={onOpenTrips} className="w-full text-left flex items-center justify-between">
                  <span className="font-medium">{t.name}</span>
                  <span className="text-xs text-teal-700 dark:text-teal-300">{t.start_date}{t.end_date ? ' → ' + t.end_date : ''}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 auto-rows-min">
      <Tile id="trips" title="Trips" icon={ICONS.trips} accent="bg-gradient-to-br from-teal-50 to-white dark:from-teal-900 dark:to-slate-900 text-slate-800 dark:text-white border border-teal-200 dark:border-teal-800" onClick={onOpenTrips}
        extraEdit={
          <div className="border-t border-slate-200 dark:border-slate-700 mt-1 pt-1 max-h-48 overflow-auto">
            <div className="px-3 py-1 text-xs text-slate-500">Show on tile</div>
            {upcoming.map((t) => {
              const on = !chosen || chosen.includes(t.id)
              return (
                <label key={t.id} className="flex items-center gap-2 px-3 py-1 text-sm">
                  <input type="checkbox" checked={on} onChange={() => {
                    const base = chosen || upcoming.map((x) => x.id)
                    const next = on ? base.filter((id) => id !== t.id) : [...base, t.id]
                    setChosen(next)
                    localStorage.setItem('ta-tile-trips', JSON.stringify(next))
                  }} />
                  <span className="truncate">{t.name}</span>
                </label>
              )
            })}
          </div>
        }>
        <ul className={(sizes.trips === 'wide' || sizes.trips === 'large') ? 'grid grid-cols-2 md:grid-cols-3 gap-3' : 'space-y-2'}>
          {(chosen ? upcoming.filter((t) => chosen.includes(t.id)) : upcoming).slice(0, (sizes.trips === 'wide' ? 6 : 4)).map((t) => (
            <li key={t.id} className="pointer-events-auto relative z-10" onClick={(e) => { e.stopPropagation(); onViewTrip && onViewTrip(t.id) }}>
              <div className={(sizes.trips === 'wide' || sizes.trips === 'large') ? 'rounded-xl bg-white/70 dark:bg-black/20 overflow-hidden' : 'flex items-center gap-2'}>
                {(sizes.trips === 'wide' || sizes.trips === 'large') && (
                  t.image_url
                    ? <img src={assetUrl(t.image_url, base)} alt="" className="w-full h-28 object-cover" />
                    : <div className="w-full h-28 bg-teal-100 dark:bg-teal-900 flex items-center justify-center text-2xl text-teal-700 dark:text-teal-200">{(t.name || '?')[0]}</div>
                )}
                <div className={(sizes.trips === 'wide' || sizes.trips === 'large') ? 'p-3' : 'flex-1 flex items-center justify-between gap-2'}>
                  {!(sizes.trips === 'wide' || sizes.trips === 'large') && (
                    t.image_url
                      ? <img src={assetUrl(t.image_url, base)} alt="" className="w-10 h-10 rounded object-cover" />
                      : <span className="w-10 h-10 rounded bg-teal-100 dark:bg-teal-900 flex items-center justify-center text-teal-700">{(t.name || '?')[0]}</span>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-lg font-semibold truncate">{t.name}</div>
                    <span className="inline-block mt-1 text-sm font-medium px-2.5 py-1 rounded-full bg-teal-600 text-white whitespace-nowrap">
                      {t.days === 0 ? 'Today' : t.days === 1 ? '1 day' : (t.days ?? '') + ' days'}
                    </span>
                  </div>
                </div>
              </div>
            </li>
          ))}
          {upcoming.length === 0 && <li className="text-sm text-teal-700 dark:text-teal-200">No upcoming trips</li>}
        </ul>
      </Tile>

      <Tile id="places" title="Places" icon={ICONS.places} accent="bg-gradient-to-br from-sky-50 to-white dark:from-sky-900 dark:to-slate-900 text-slate-800 dark:text-white border border-sky-200 dark:border-sky-800" onClick={onOpenPlaces}>
        <div className="text-xs text-sky-700 dark:text-sky-200 mb-1">Recent visits</div>
        {recent.length === 0 && <p className="text-sm text-sky-700 dark:text-sky-200">No visits yet.</p>}
        <ul className={(sizes.places === 'wide' || sizes.places === 'large') ? 'grid grid-cols-2 md:grid-cols-5 gap-3' : 'space-y-1'}>
          {recent.map((v) => (
            <li key={v.id} className={(sizes.places === 'wide' || sizes.places === 'large') ? 'pointer-events-auto relative z-10 rounded-xl bg-white/70 dark:bg-black/20 p-2' : 'flex items-center gap-2 text-sm pointer-events-auto relative z-10'} onClick={(e) => { e.stopPropagation(); onViewPlace && onViewPlace(v) }}>
              {(sizes.places === 'wide' || sizes.places === 'large') ? (
                <>
                  {v.visit_photo_url || v.image_url ? <img src={assetUrl(v.visit_photo_url || v.image_url, base)} alt="" className="w-full h-20 rounded object-cover" /> : <div className="w-full h-20 rounded bg-slate-200 dark:bg-slate-700" />}
                  <div className="mt-1 text-sm truncate">{v.name}</div>
                  {!v.visit_photo_url && <span className="text-[10px] px-1 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">No visit photo</span>}
                  <div className="text-xs text-sky-600 dark:text-sky-300">{v.visit_date}</div>
                </>
              ) : (
                <>
                  {v.visit_photo_url || v.image_url ? <img src={assetUrl(v.visit_photo_url || v.image_url, base)} alt="" className="w-7 h-7 rounded object-cover" /> : <span className="w-7 h-7 rounded bg-slate-200 dark:bg-slate-700" />}
                  <span className="truncate flex-1">
                    {v.name}
                    {!v.visit_photo_url && <span className="ml-1 text-[10px] px-1 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">No visit photo</span>}
                  </span>
                  <span className="text-xs text-sky-600 dark:text-sky-300">{v.visit_date}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      </Tile>

      <Tile id="categories" title="Categories" icon={ICONS.categories} accent="bg-gradient-to-br from-violet-50 to-white dark:from-violet-900 dark:to-slate-900 text-slate-800 dark:text-white border border-violet-200 dark:border-violet-800" onClick={onOpenCategories}>
        <div className="text-3xl font-bold">{categories.length}</div>
        <div className="text-sm text-violet-700 dark:text-violet-200">categories</div>
      </Tile>

      <Tile id="cupboard" title="Store cupboard" icon={ICONS.cupboard} accent="bg-gradient-to-br from-amber-50 to-white dark:from-amber-900 dark:to-slate-900 text-slate-800 dark:text-white border border-amber-200 dark:border-amber-800" onClick={onOpenCupboard}>
        <div className="text-3xl font-bold">{items.length}</div>
        <div className="text-sm text-amber-700 dark:text-amber-200">items · {bags.length} bags</div>
        {topCats.length > 0 && (
          <ul className="text-xs mt-2 space-y-1">
            {topCats.map(([name, n]) => (
              <li key={name}>
                <div className="flex justify-between"><span className="truncate">{name}</span><span>{n}</span></div>
                <div className="h-1 bg-amber-100 dark:bg-slate-700 rounded-full"><div className="h-1 bg-amber-500 rounded-full" style={{ width: Math.round(100 * n / totalItems) + '%' }} /></div>
              </li>
            ))}
          </ul>
        )}
      </Tile>

      <Tile id="achievements" title="Achievements" icon={ICONS.achievements} accent="bg-gradient-to-br from-rose-50 to-white dark:from-rose-900 dark:to-slate-900 text-slate-800 dark:text-white border border-rose-200 dark:border-rose-800" onClick={() => { window.location.href = base + '/achievements' }}>
        <div className="text-sm text-rose-700 dark:text-rose-200">Coming soon</div>
      </Tile>

      <Tile id="settings" title="Settings" icon={ICONS.settings} accent="bg-gradient-to-br from-slate-100 to-white dark:from-slate-800 dark:to-slate-900 text-slate-800 dark:text-white border border-slate-200 dark:border-slate-700" onClick={onOpenSettings}>
        <div className="flex items-center justify-center py-2">
          <svg className="w-12 h-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d={ICONS.settings} /></svg>
        </div>
      </Tile>
      </div>
    </div>
  )
}

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

export default function Dashboard({ base = '', onOpenTrips, onOpenPlaces, onOpenCategories, onOpenCupboard, onOpenSettings, onViewPlace }) {
  const [trips, setTrips] = useState([])
  const [places, setPlaces] = useState([])
  const [categories, setCategories] = useState([])
  const [items, setItems] = useState([])
  const [bags, setBags] = useState([])

  useEffect(() => {
    fetch(base + '/api/trips').then((r) => r.ok ? r.json() : { trips: [] }).then((d) => setTrips(d.trips || [])).catch(() => {})
    fetch(base + '/api/places').then((r) => r.ok ? r.json() : { places: [] }).then((d) => setPlaces(d.places || [])).catch(() => {})
    fetch(base + '/api/categories').then((r) => r.ok ? r.json() : { categories: [] }).then((d) => setCategories(d.categories || d.themes || [])).catch(() => {})
    fetch(base + '/api/packing').then((r) => r.ok ? r.json() : { items: [], bags: [] }).then((d) => {
      setItems(d.items || [])
      setBags(d.bags || [])
    }).catch(() => {})
  }, [base])

  const upcoming = trips
    .filter((t) => t.status !== 'completed' && t.status !== 'active')
    .map((t) => ({ ...t, days: daysToGo(t) }))
    .filter((t) => t.days == null || t.days >= 0)
    .sort((a, b) => (a.days ?? 9999) - (b.days ?? 9999))
  const next = upcoming[0]
  const recent = places
    .filter((p) => p.visited && p.visit_date)
    .sort((a, b) => String(b.visit_date).localeCompare(String(a.visit_date)))
    .slice(0, 5)

  const Tile = ({ title, onClick, children, accent }) => (
    <button type="button" onClick={onClick} className="w-full text-left bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 hover:shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 rounded-lg text-white flex items-center justify-center text-lg ${accent}`}>{title[0]}</div>
        <div className="font-semibold">{title}</div>
      </div>
      {children}
    </button>
  )

  return (
    <div className="max-w-3xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-4">
      <Tile title="Trips" accent="bg-teal-600" onClick={onOpenTrips}>
        <div className="text-2xl font-semibold">{upcoming.length}</div>
        <div className="text-sm text-slate-500">upcoming</div>
        {next && next.days != null && (
          <div className="text-sm text-slate-600 dark:text-slate-300 mt-1">
            Next: {next.name} · {next.days === 0 ? 'today' : next.days === 1 ? '1 day to go' : next.days + ' days to go'}
          </div>
        )}
      </Tile>

      <Tile title="Places" accent="bg-sky-600" onClick={onOpenPlaces}>
        <div className="text-xs text-slate-500 mb-2">Recent visits</div>
        {recent.length === 0 && <p className="text-sm text-slate-500">No visits yet.</p>}
        <ul className="space-y-1">
          {recent.map((v) => (
            <li key={v.id} className="flex items-center gap-2 text-sm" onClick={(e) => { e.stopPropagation(); onViewPlace && onViewPlace(v) }}>
              {v.visit_photo_url || v.image_url ? (
                <img src={assetUrl(v.visit_photo_url || v.image_url, base)} alt="" className="w-8 h-8 rounded object-cover" />
              ) : (
                <span className="w-8 h-8 rounded bg-slate-100 dark:bg-slate-700" />
              )}
              <span className="truncate flex-1">{v.name}</span>
              <span className="text-xs text-slate-400">{v.visit_date}</span>
            </li>
          ))}
        </ul>
      </Tile>

      <Tile title="Categories" accent="bg-violet-600" onClick={onOpenCategories}>
        <div className="text-2xl font-semibold">{categories.length}</div>
        <div className="text-sm text-slate-500">categories</div>
      </Tile>

      <Tile title="Store cupboard" accent="bg-amber-600" onClick={onOpenCupboard}>
        <div className="text-2xl font-semibold">{items.length}</div>
        <div className="text-sm text-slate-500">items · {bags.length} bags</div>
      </Tile>

      <Tile title="Achievements" accent="bg-rose-600" onClick={() => { window.location.href = base + '/achievements' }}>
        <div className="text-sm text-slate-500">Coming soon</div>
      </Tile>

      <Tile title="Settings" accent="bg-slate-600" onClick={onOpenSettings}>
        <div className="flex items-center justify-center py-2">
          <svg className="w-12 h-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
      </Tile>
    </div>
  )
}

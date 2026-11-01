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
    fetch(base + '/api/categories').then((r) => r.ok ? r.json() : { categories: [] }).then((d) => setCategories(d.categories || [])).catch(() => {})
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

  const byCat = {}
  items.forEach((it) => {
    const c = it.category || 'Other'
    byCat[c] = (byCat[c] || 0) + 1
  })
  const topCats = Object.entries(byCat).sort((a, b) => b[1] - a[1]).slice(0, 4)
  const totalItems = items.length || 1

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Trips */}
      <button type="button" onClick={onOpenTrips} className="text-left rounded-2xl p-5 bg-gradient-to-br from-teal-900 to-slate-900 text-white border border-teal-800">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center font-semibold">T</span>
          <span className="font-semibold tracking-wide">TRIPS</span>
        </div>
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-4xl font-bold">{upcoming.length}</div>
            <div className="text-sm text-teal-200">upcoming</div>
            {next && (
              <div className="text-sm mt-3 text-teal-100">
                Next: {next.name} · {next.days === 0 ? 'today' : next.days === 1 ? '1 day to go' : next.days + ' days to go'}
              </div>
            )}
          </div>
          {next && (
            <div className="bg-slate-800/80 rounded-xl p-3 min-w-[140px]">
              <div className="text-xs text-slate-400">Next</div>
              <div className="font-medium truncate">{next.name}</div>
              <div className="text-sm text-teal-300 mt-1">
                {next.days === 0 ? 'Today' : next.days + ' days to go'}
              </div>
            </div>
          )}
        </div>
      </button>

      {/* Places */}
      <button type="button" onClick={onOpenPlaces} className="text-left rounded-2xl p-5 bg-gradient-to-br from-sky-900 to-slate-900 text-white border border-sky-800">
        <div className="flex items-center gap-2 mb-3">
          <span className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center font-semibold">P</span>
          <span className="font-semibold tracking-wide">PLACES</span>
        </div>
        <div className="text-xs text-sky-200 mb-2">Recent visits</div>
        {recent.length === 0 && <p className="text-sm text-sky-200">No visits yet.</p>}
        <ul className="space-y-1.5">
          {recent.map((v) => (
            <li key={v.id} className="flex items-center gap-2 text-sm" onClick={(e) => { e.stopPropagation(); onViewPlace && onViewPlace(v) }}>
              {v.visit_photo_url || v.image_url ? (
                <img src={assetUrl(v.visit_photo_url || v.image_url, base)} alt="" className="w-8 h-8 rounded object-cover" />
              ) : (
                <span className="w-8 h-8 rounded bg-slate-700" />
              )}
              <span className="truncate flex-1">{v.name}</span>
              <span className="text-xs text-sky-300">{v.visit_date}</span>
            </li>
          ))}
        </ul>
      </button>

      {/* Categories */}
      <button type="button" onClick={onOpenCategories} className="text-left rounded-2xl p-5 bg-gradient-to-br from-violet-900 to-slate-900 text-white border border-violet-800">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-9 h-9 rounded-lg bg-violet-600 flex items-center justify-center font-semibold">C</span>
          <span className="font-semibold">Categories</span>
        </div>
        <div className="flex items-center gap-6">
          <div>
            <div className="text-4xl font-bold">{categories.length}</div>
            <div className="text-sm text-violet-200">categories</div>
          </div>
          <ul className="text-sm space-y-1 flex-1">
            {categories.slice(0, 5).map((c) => (
              <li key={c.id} className="flex justify-between text-violet-100">
                <span className="truncate">{c.name}</span>
                <span className="text-violet-300">{c.total || 0}</span>
              </li>
            ))}
          </ul>
        </div>
      </button>

      {/* Store cupboard */}
      <button type="button" onClick={onOpenCupboard} className="text-left rounded-2xl p-5 bg-gradient-to-br from-amber-900 to-slate-900 text-white border border-amber-800">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-9 h-9 rounded-lg bg-amber-600 flex items-center justify-center font-semibold">S</span>
          <span className="font-semibold">Store cupboard</span>
        </div>
        <div className="flex items-start gap-6">
          <div>
            <div className="text-4xl font-bold">{items.length}</div>
            <div className="text-sm text-amber-200">items · {bags.length} bags</div>
          </div>
          <ul className="text-sm space-y-1.5 flex-1">
            {topCats.map(([name, n]) => (
              <li key={name}>
                <div className="flex justify-between text-amber-100">
                  <span className="truncate">{name}</span>
                  <span>{n}</span>
                </div>
                <div className="h-1.5 bg-slate-700 rounded-full mt-0.5">
                  <div className="h-1.5 bg-amber-500 rounded-full" style={{ width: Math.round(100 * n / totalItems) + '%' }} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </button>

      {/* Achievements */}
      <button type="button" onClick={() => { window.location.href = base + '/achievements' }} className="text-left rounded-2xl p-5 bg-gradient-to-br from-rose-900 to-slate-900 text-white border border-rose-800">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-9 h-9 rounded-lg bg-rose-600 flex items-center justify-center font-semibold">A</span>
          <span className="font-semibold">Achievements</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-rose-200">Coming soon</div>
          <div className="bg-slate-800/80 rounded-xl px-4 py-3 text-sm">
            <div className="text-2xl">🏆</div>
            <div className="text-rose-200 text-xs mt-1">Badges on the way</div>
          </div>
        </div>
      </button>

      {/* Settings */}
      <button type="button" onClick={onOpenSettings} className="text-left rounded-2xl p-5 bg-gradient-to-br from-slate-800 to-slate-900 text-white border border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-9 h-9 rounded-lg bg-slate-600 flex items-center justify-center font-semibold">S</span>
          <span className="font-semibold">Settings</span>
        </div>
        <div className="flex items-center justify-center py-2">
          <svg className="w-16 h-16 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
      </button>
    </div>
  )
}

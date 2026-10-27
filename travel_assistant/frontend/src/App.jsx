import { useState, useEffect, useMemo } from 'react'
import Filters from './components/Filters'
import PlaceCard from './components/PlaceCard'
import PlaceDetail from './components/PlaceDetail'
import Sidebar from './components/Sidebar'
import Settings from './components/Settings'
import CategoryCard from './components/CategoryCard'
import CategoryDetail from './components/CategoryDetail'
import Dashboard from './components/Dashboard'
import MapView from './components/MapView'
import TripCard from './components/TripCard'
import TripDetail from './components/TripDetail'
import TripEditor from './components/TripEditor'
import LiveTrip from './components/LiveTrip'
import Button from './components/Button'

export default function App() {
  const [data, setData] = useState({ places: [], themes: [], types: [], regions: [], counties: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [mapFocus, setMapFocus] = useState(null)
  const [addPlace, setAddPlace] = useState(null)
  const [addTrip, setAddTrip] = useState(null)
  const [addDays, setAddDays] = useState([])
  const [page, setPage] = useState('dashboard')
  const [accent, setAccent] = useState('#14b8a6')
  const [dark, setDark] = useState(() => localStorage.getItem('ta-dark') === '1')
  const [trips, setTrips] = useState([])
  const [showCompleted, setShowCompleted] = useState(false)
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [types, setTypes] = useState([])
  const [addingCategory, setAddingCategory] = useState(false)
  const [newName, setNewName] = useState('')
  const [selectedTrip, setSelectedTrip] = useState(null)
  const [editingTrip, setEditingTrip] = useState(null)
  const [editStep, setEditStep] = useState(0)
  const [autoLive, setAutoLive] = useState(false)
  const [liveTrip, setLiveTrip] = useState(null)
  const [filters, setFilters] = useState({
    search: '',
    type: '',
    theme: '',
    region: '',
    county: '',
    hideVisited: true,
  })

  useEffect(() => {
    // Respect Ingress base path
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    fetch(base + '/api/places')
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load places')
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetch(base + '/api/settings').then((r) => r.json()).then((d) => {
      const c = d.ui?.accent_color
      if (c) {
        setAccent(c)
        document.documentElement.style.setProperty('--accent', c)
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (page !== 'trips' && !addPlace) return
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    fetch(base + '/api/trips').then((r) => r.json()).then((d) => setTrips(d.trips || [])).catch(() => {})
  }, [page, addPlace])

  useEffect(() => {
    if (page !== 'categories') return
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    fetch(base + '/api/categories').then((r) => r.json()).then((d) => setCategories(d.categories || [])).catch(() => {})
    fetch(base + '/api/settings').then((r) => r.json()).then((d) => setTypes(d.category_types || [])).catch(() => {})
  }, [page])

  const filtered = useMemo(() => {
    const q = (filters.search || '').toLowerCase()
    return data.places.filter((p) => {
      if (q && !((p.name || '').toLowerCase().includes(q) || (p.city || '').toLowerCase().includes(q) || (p.county || '').toLowerCase().includes(q))) return false
      if (filters.type && (p.category_type_name || '') !== filters.type) return false
      if (filters.theme && String(p.theme_id) !== String(filters.theme)) return false
      if (filters.region && (p.region || '') !== filters.region) return false
      if (filters.county && (p.county || '') !== filters.county) return false
      if (filters.hideVisited && p.visited) return false
      return true
    })
  }, [data.places, filters])

  // Options derived from places that match the other filters (only values with places)
  const matchesExcept = (p, skip) => {
    const q = (filters.search || '').toLowerCase()
    if (skip !== 'search' && q && !((p.name || '').toLowerCase().includes(q) || (p.city || '').toLowerCase().includes(q) || (p.county || '').toLowerCase().includes(q))) return false
    if (skip !== 'type' && filters.type && (p.category_type_name || '') !== filters.type) return false
    if (skip !== 'theme' && filters.theme && String(p.theme_id) !== String(filters.theme)) return false
    if (skip !== 'region' && filters.region && (p.region || '') !== filters.region) return false
    if (skip !== 'county' && filters.county && (p.county || '') !== filters.county) return false
    return true
  }

  const unique = (arr) => [...new Set(arr.filter(Boolean))].sort()

  const typeOptions = useMemo(() => {
    const names = unique(data.places.filter((p) => matchesExcept(p, 'type')).map((p) => p.category_type_name))
    return [{ value: '', label: 'All types' }, ...names.map((n) => ({ value: n, label: n }))]
  }, [data.places, filters])

  const themeOptions = useMemo(() => {
    const seen = new Map()
    data.places.filter((p) => matchesExcept(p, 'theme')).forEach((p) => {
      if (p.theme_id && !seen.has(String(p.theme_id))) seen.set(String(p.theme_id), p.theme_name)
    })
    return [{ value: '', label: 'All categories' }, ...[...seen.entries()].map(([id, name]) => ({ value: id, label: name })).sort((a, b) => (a.label || '').localeCompare(b.label || ''))]
  }, [data.places, filters])

  const regionOptions = useMemo(() => {
    const names = unique(data.places.filter((p) => matchesExcept(p, 'region')).map((p) => p.region))
    return [{ value: '', label: 'All regions' }, ...names.map((n) => ({ value: n, label: n }))]
  }, [data.places, filters])

  const countyOptions = useMemo(() => {
    const names = unique(data.places.filter((p) => matchesExcept(p, 'county')).map((p) => p.county))
    return [{ value: '', label: 'All counties' }, ...names.map((n) => ({ value: n, label: n }))]
  }, [data.places, filters])

  const base = typeof window !== 'undefined' ? window.location.pathname.replace(/\/react.*$/, '') : ''

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('ta-dark', dark ? '1' : '0')
  }, [dark])

  return (
    <>
    <style>{`
      .bg-brand-600, .bg-brand-700, .hover\:bg-brand-700:hover { background-color: var(--accent) !important; }
      .text-brand-600, .text-brand-700, .text-brand-400 { color: var(--accent) !important; }
      .border-brand-600 { border-color: var(--accent) !important; }
    `}</style>
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <header className="fixed top-0 left-0 right-0 z-[1000] border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 flex items-center gap-3">
        <Sidebar base={base} page={page} onNavigate={setPage} />
        <h1 className="text-lg font-semibold flex-1">{page === "trips" ? "Trips" : page === "settings" ? "Settings" : page === "dashboard" ? "Dashboard" : page === "categories" ? "Categories" : "Places"}</h1>
        {/* Dark mode toggle */}
        <button onClick={() => setDark(!dark)} className="flex items-center" title={dark ? 'Light mode' : 'Dark mode'} aria-label="Toggle dark mode">
          <span className={`relative w-10 h-6 rounded-full transition-colors ${dark ? 'bg-brand-600' : 'bg-slate-300'}`}>
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${dark ? 'translate-x-4' : ''}`} />
          </span>
        </button>
        {/* Settings cog */}
        <button onClick={() => setPage('settings')} className="p-2 rounded-lg text-slate-500 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800" title="Settings" aria-label="Settings">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </header>
      <main className="p-4 pt-16">
        {page === 'dashboard' ? (
          <Dashboard base={base} onOpenTrips={() => setPage('trips')}
          onViewPlace={(place) => setSelected(place)}
        />
        ) : page === 'settings' ? (
          <Settings base={base} onAccent={(c) => { setAccent(c); document.documentElement.style.setProperty('--accent', c) }} />
        ) : page === 'trips' ? (
          <div className="max-w-2xl mx-auto space-y-2">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Trips</h2>
              <Button onClick={async () => {
                const res = await fetch(base + '/api/trips', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'New trip' }) })
                const d = await res.json()
                if (d.id) { setEditStep(0); setEditingTrip(d.id) }
              }}>New trip</Button>
              <label className="flex items-center gap-2 text-sm text-slate-500">
                <span>Show completed</span>
                <button onClick={() => setShowCompleted(!showCompleted)} className="flex items-center" aria-label="Show completed trips">
                  <span className={`relative w-10 h-6 rounded-full transition-colors ${showCompleted ? 'bg-brand-600' : 'bg-slate-300'}`}>
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${showCompleted ? 'translate-x-4' : ''}`} />
                  </span>
                </button>
              </label>
            </div>
            {(() => {
              const today = new Date()
              today.setHours(0, 0, 0, 0)
              const daysToGo = (t) => {
                if (!t.start_date) return 9999
                const start = new Date(t.start_date + 'T00:00:00')
                return Math.round((start - today) / 86400000)
              }
              const visible = trips.filter((t) => showCompleted || t.status !== 'completed')
              const inProgress = visible.filter((t) => t.status === 'active')
              const future = visible
                .filter((t) => t.status !== 'active')
                .sort((a, b) => daysToGo(a) - daysToGo(b))
              const renderCard = (t) => (
                <TripCard key={t.id} trip={t}
                  onView={() => { setEditStep(3); setEditingTrip(t.id) }}
                  onEdit={() => { setEditStep(0); setEditingTrip(t.id) }}
                  onStart={async () => {
                    if (t.status !== 'active') {
                      await fetch(base + '/api/trips/' + t.id + '/start', { method: 'POST' })
                    }
                    setLiveTrip(t.id)
                    fetch(base + '/api/trips').then((r) => r.json()).then((d) => setTrips(d.trips || []))
                  }}
                  onDelete={async () => { if (confirm('Delete ' + t.name + '?')) { await fetch(base + '/api/trips/' + t.id + '/delete', { method: 'POST' }); setTrips((list) => list.filter((x) => x.id !== t.id)) } }}
                />
              )
              return (
                <>
                  {inProgress.length > 0 && (
                    <div className="mb-8 p-4 rounded-2xl bg-teal-50 dark:bg-teal-950/40 border-2 border-teal-400 dark:border-teal-600">
                      <h3 className="text-base font-semibold mb-3 text-teal-700 dark:text-teal-400">Trips in progress</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {inProgress.map(renderCard)}
                      </div>
                    </div>
                  )}
                  {future.length > 0 && (
                    <div>
                      <h3 className="text-base font-semibold mb-3">Upcoming trips</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {future.map(renderCard)}
                      </div>
                    </div>
                  )}
                  {inProgress.length === 0 && future.length === 0 && <p className="text-slate-500">No trips yet.</p>}
                </>
              )
            })()}
          </div>
        ) : page === 'categories' ? (
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Categories</h2>
              <Button onClick={() => setAddingCategory(true)}>Add category</Button>
            </div>
            {addingCategory && (
              <div className="flex gap-2 mb-3">
                <input className="flex-1 px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" placeholder="Category name" value={newName} onChange={(e) => setNewName(e.target.value)} />
                <Button onClick={async () => {
                  if (!newName.trim()) return
                  const res = await fetch(base + '/api/categories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newName }) })
                  if (res.ok) {
                    setNewName('')
                    setAddingCategory(false)
                    const d = await fetch(base + '/api/categories').then((r) => r.json())
                    setCategories(d.categories || [])
                  }
                }}>Save</Button>
                <Button variant="secondary" onClick={() => { setAddingCategory(false); setNewName('') }}>Cancel</Button>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              {categories.map((c) => (
                <CategoryCard
                  key={c.id}
                  category={c}
                  onClick={() => setSelectedCategory(c)}
                  onViewPlaces={(cat) => { setFilters((f) => ({ ...f, theme: String(cat.id), hideVisited: false })); setPage('places') }}
                />
              ))}
            </div>
            {categories.length === 0 && <p className="text-slate-500">No categories yet.</p>}
          </div>
        ) : (
          <>
            <Filters
              value={filters}
              onChange={setFilters}
              resultCount={filtered.length}
              fields={['search', 'type', 'theme', 'region', 'county']}
              options={{ type: typeOptions, theme: themeOptions, region: regionOptions, county: countyOptions }}
            />
            {loading && <p className="mt-6 text-slate-500">Loading places…</p>}
            {error && <p className="mt-6 text-red-600">{error}</p>}
            <div className="mt-4 flex flex-col md:flex-row gap-4">
              <div className="order-1 md:order-2 md:w-1/2 h-[360px] md:h-[calc(100vh-8rem)] md:sticky md:top-16">
                <MapView places={filtered} onView={setSelected} onSelect={setAddPlace} focus={mapFocus} />
              </div>
              <div className="order-2 md:order-1 md:w-1/2 space-y-2">
                {filtered.map((p) => (
                  <PlaceCard key={p.id} place={p} onShowDay={setMapFocus} onUpdated={(updated) => setData((d) => ({ ...d, places: updated._deleted ? d.places.filter((x) => x.id !== updated.id) : d.places.map((x) => x.id === updated.id ? { ...x, ...updated } : x) }))} />
                ))}
              </div>
            </div>
          </>
        )}
        {liveTrip && (
          <LiveTrip
            tripId={liveTrip}
            onClose={() => { setLiveTrip(null); fetch(base + '/api/trips').then((r) => r.json()).then((d) => setTrips(d.trips || [])) }}
          />
        )}
        {editingTrip && (
          <TripEditor
            key={editingTrip + '-' + editStep}
            tripId={editingTrip}
            initialStep={editStep}
            onClose={() => { setEditingTrip(null); fetch(base + '/api/trips').then((r) => r.json()).then((d) => setTrips(d.trips || [])) }}
            onSaved={() => { setEditingTrip(null); fetch(base + '/api/trips').then((r) => r.json()).then((d) => setTrips(d.trips || [])) }}
          />
        )}
        {selectedCategory && (
          <CategoryDetail
            category={selectedCategory}
            base={base}
            types={types}
            onClose={() => setSelectedCategory(null)}
            onSaved={(updated) => {
              if (updated._deleted) {
                setCategories((list) => list.filter((c) => c.id !== updated.id))
                setSelectedCategory(null)
                return
              }
              setCategories((list) => list.map((c) => c.id === updated.id ? { ...c, ...updated } : c))
              setSelectedCategory((c) => ({ ...c, ...updated }))
            }}
            onViewPlaces={(cat) => { setSelectedCategory(null); setFilters((f) => ({ ...f, theme: String(cat.id), hideVisited: false })); setPage('places') }}
          />
        )}
        {selected && (
          <PlaceDetail
            place={selected}
            onClose={() => setSelected(null)}
            onSaved={(updated) => {
              setData((d) => ({
                ...d,
                places: d.places.map((p) => p.id === updated.id ? { ...p, ...updated } : p),
              }))
              setSelected(updated)
            }}
          />
        )}
        {addPlace && (
          <div className="fixed inset-0 z-[3000] flex items-center justify-center bg-black/50 p-4" onClick={() => { setAddPlace(null); setAddTrip(null) }}>
            <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 w-full max-w-sm space-y-2" onClick={(e) => e.stopPropagation()}>
              <div className="font-semibold">Add {addPlace.name} to a trip</div>
              {!addTrip ? (
                <>
                  {trips.length === 0 && <p className="text-sm text-slate-500">No trips yet.</p>}
                  {trips.filter((t) => t.status !== 'completed').map((t) => (
                    <button key={t.id} className="block w-full text-left px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-800" onClick={async () => {
                      const res = await fetch(base + '/api/trips/' + t.id).then((r) => r.json())
                      const days = (res.days || []).map((d) => d.day)
                      const n = res.n_days || days.length || 1
                      setAddDays(Array.from({ length: n }, (_, i) => i + 1))
                      setAddTrip(t)
                    }}>{t.name}</button>
                  ))}
                </>
              ) : (
                <>
                  <div className="text-sm text-slate-500">{addTrip.name} · which day?</div>
                  {addDays.map((d) => (
                    <button key={d} className="block w-full text-left px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-800" onClick={async () => {
                      await fetch(base + '/api/trips/' + addTrip.id + '/stops', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location_id: addPlace.id, day_number: d }) })
                      setAddPlace(null); setAddTrip(null)
                    }}>Day {d}</button>
                  ))}
                  <button className="text-sm text-slate-500" onClick={() => setAddTrip(null)}>Back</button>
                </>
              )}
              <button className="text-sm text-slate-500" onClick={() => { setAddPlace(null); setAddTrip(null) }}>Cancel</button>
            </div>
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <p className="mt-6 text-slate-500 text-center">No places match the filters.</p>
        )}
      </main>
    </div>
    </>
  )
}

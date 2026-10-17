import { useState, useEffect, useMemo } from 'react'
import Filters from './components/Filters'
import PlaceCard from './components/PlaceCard'
import PlaceDetail from './components/PlaceDetail'
import Sidebar from './components/Sidebar'
import Settings from './components/Settings'
import Dashboard from './components/Dashboard'
import MapView from './components/MapView'
import TripCard from './components/TripCard'
import TripDetail from './components/TripDetail'

export default function App() {
  const [data, setData] = useState({ places: [], themes: [], types: [], regions: [], counties: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [page, setPage] = useState('dashboard')
  const [dark, setDark] = useState(() => localStorage.getItem('ta-dark') === '1')
  const [trips, setTrips] = useState([])
  const [selectedTrip, setSelectedTrip] = useState(null)
  const [autoLive, setAutoLive] = useState(false)
  const [filters, setFilters] = useState({
    search: '',
    type: '',
    theme: '',
    region: '',
    county: '',
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
    if (page !== 'trips') return
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    fetch(base + '/api/trips').then((r) => r.json()).then((d) => setTrips(d.trips || [])).catch(() => {})
  }, [page])

  const filtered = useMemo(() => {
    const q = (filters.search || '').toLowerCase()
    return data.places.filter((p) => {
      if (q && !((p.name || '').toLowerCase().includes(q) || (p.city || '').toLowerCase().includes(q) || (p.county || '').toLowerCase().includes(q))) return false
      if (filters.type && (p.category_type_name || '') !== filters.type) return false
      if (filters.theme && String(p.theme_id) !== String(filters.theme)) return false
      if (filters.region && (p.region || '') !== filters.region) return false
      if (filters.county && (p.county || '') !== filters.county) return false
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
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <header className="fixed top-0 left-0 right-0 z-[1000] border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 flex items-center gap-3">
        <Sidebar base={base} page={page} onNavigate={setPage} />
        <h1 className="text-lg font-semibold flex-1">{page === "trips" ? "Trips" : page === "settings" ? "Settings" : page === "dashboard" ? "Dashboard" : "Places"}</h1>
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
          <Dashboard base={base} onContinue={(id) => { setAutoLive(true); setSelectedTrip(id); setPage('trips') }} />
        ) : page === 'settings' ? (
          <Settings base={base} />
        ) : page === 'trips' ? (
          <div className="max-w-2xl mx-auto space-y-2">
            <h2 className="text-lg font-semibold mb-3">Trips</h2>
            {trips.map((t) => <TripCard key={t.id} trip={t} onClick={() => setSelectedTrip(t.id)} />)}
            {trips.length === 0 && <p className="text-slate-500">No trips yet.</p>}
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
              <div className="order-1 md:order-2 md:w-1/2 h-[280px] md:h-auto md:sticky md:top-4">
                <MapView places={filtered} onSelect={setSelected} />
              </div>
              <div className="order-2 md:order-1 md:w-1/2 space-y-2">
                {filtered.map((p) => (
                  <PlaceCard key={p.id} place={p} onUpdated={(updated) => setData((d) => ({ ...d, places: updated._deleted ? d.places.filter((x) => x.id !== updated.id) : d.places.map((x) => x.id === updated.id ? { ...x, ...updated } : x) }))} />
                ))}
              </div>
            </div>
          </>
        )}
        {selectedTrip && <TripDetail tripId={selectedTrip} autoLive={autoLive} onClose={() => { setSelectedTrip(null); setAutoLive(false) }} />}
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
        {!loading && filtered.length === 0 && (
          <p className="mt-6 text-slate-500 text-center">No places match the filters.</p>
        )}
      </main>
    </div>
  )
}

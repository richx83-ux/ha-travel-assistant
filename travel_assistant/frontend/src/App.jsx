import { useState, useEffect, useMemo } from 'react'
import Filters from './components/Filters'
import PlaceCard from './components/PlaceCard'
import PlaceDetail from './components/PlaceDetail'
import Sidebar from './components/Sidebar'
import MapView from './components/MapView'
import TripCard from './components/TripCard'
import TripDetail from './components/TripDetail'

export default function App() {
  const [data, setData] = useState({ places: [], themes: [], types: [], regions: [], counties: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [page, setPage] = useState('places')
  const [trips, setTrips] = useState([])
  const [selectedTrip, setSelectedTrip] = useState(null)
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

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 flex items-center gap-3">
        <Sidebar base={base} page={page} onNavigate={setPage} />
        <h1 className="text-lg font-semibold">{page === "trips" ? "Trips" : "Places"}</h1>
      </header>
      <main className="p-4">
        {page === 'trips' ? (
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
                  <PlaceCard key={p.id} place={p} />
                ))}
              </div>
            </div>
          </>
        )}
        {selectedTrip && <TripDetail tripId={selectedTrip} onClose={() => setSelectedTrip(null)} />}
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

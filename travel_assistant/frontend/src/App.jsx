import { useState, useEffect, useMemo } from 'react'
import Filters from './components/Filters'
import PlaceCard from './components/PlaceCard'
import PlaceDetail from './components/PlaceDetail'

export default function App() {
  const [data, setData] = useState({ places: [], themes: [], types: [], regions: [], counties: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
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

  // Dynamic options for Filters
  const typeOptions = [{ value: '', label: 'All types' }, ...data.types.map((t) => ({ value: t.name, label: t.name }))]
  const themeOptions = [{ value: '', label: 'All categories' }, ...data.themes.map((t) => ({ value: String(t.id), label: t.name }))]
  const regionOptions = [{ value: '', label: 'All regions' }, ...data.regions.map((r) => ({ value: r, label: r }))]
  const countyOptions = [{ value: '', label: 'All counties' }, ...data.counties.map((c) => ({ value: c, label: c }))]

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3">
        <h1 className="text-lg font-semibold">Places</h1>
      </header>
      <main className="p-4 max-w-3xl mx-auto">
        <Filters
          value={filters}
          onChange={setFilters}
          resultCount={filtered.length}
          fields={['search', 'type', 'theme', 'region', 'county']}
          options={{ type: typeOptions, theme: themeOptions, region: regionOptions, county: countyOptions }}
        />
        {loading && <p className="mt-6 text-slate-500">Loading places…</p>}
        {error && <p className="mt-6 text-red-600">{error}</p>}
        <div className="mt-4 space-y-2">
          {filtered.map((p) => (
            <PlaceCard key={p.id} place={p} onClick={() => setSelected(p)} />
          ))}
        </div>
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

import { useState, useEffect } from 'react'

export default function TripPack({ tripId, base = '', onBack }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState({})

  const load = () => {
    fetch(base + '/api/trips/' + tripId + '/luggage')
      .then((r) => r.ok ? r.json() : { items: [] })
      .then((d) => setItems(d.items || []))
      .finally(() => setLoading(false))
  }

  useEffect(() => { if (tripId) load() }, [tripId, base])

  const toggle = async (it) => {
    const next = !it.packed
    setItems((list) => list.map((x) => x.id === it.id ? { ...x, packed: next ? 1 : 0 } : x))
    await fetch(base + '/api/trips/' + tripId + '/luggage/' + it.id + '/packed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ packed: next }),
    })
  }

  if (loading) return <p className="text-slate-500">Loading…</p>

  const byCat = {}
  items.forEach((it) => {
    const cat = it.bag_name ? ('Bags · ' + it.bag_name) : (it.category || 'Other')
    const sub = it.bag_name ? 'In bag' : (it.clothing_type || 'General')
    byCat[cat] = byCat[cat] || {}
    byCat[cat][sub] = byCat[cat][sub] || []
    byCat[cat][sub].push(it)
  })
  const cats = Object.keys(byCat).sort()
  const colours = [
    'bg-teal-50 border-teal-200 dark:bg-teal-950 dark:border-teal-800',
    'bg-sky-50 border-sky-200 dark:bg-sky-950 dark:border-sky-800',
    'bg-amber-50 border-amber-200 dark:bg-amber-950 dark:border-amber-800',
    'bg-violet-50 border-violet-200 dark:bg-violet-950 dark:border-violet-800',
    'bg-rose-50 border-rose-200 dark:bg-rose-950 dark:border-rose-800',
    'bg-emerald-50 border-emerald-200 dark:bg-emerald-950 dark:border-emerald-800',
  ]
  const packed = items.filter((i) => i.packed).length

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-sm text-slate-500 hover:underline">← Back</button>
        <h1 className="text-xl font-semibold">Pack</h1>
        <span className="text-xs text-slate-400">{packed} / {items.length} packed</span>
      </div>
      {items.length === 0 && <p className="text-sm text-slate-500">No items on this trip yet. Use Plan and Add to trip first.</p>}
      <div className="space-y-2">
        {cats.map((cat, ci) => {
          const subs = Object.keys(byCat[cat]).sort()
          const catOpen = open[cat] !== false
          return (
            <div key={cat} className={`border rounded-lg ${colours[ci % colours.length]}`}>
              <button type="button" className="w-full flex items-center justify-between px-3 py-2 text-left text-sm font-medium" onClick={() => setOpen((g) => ({ ...g, [cat]: !catOpen }))}>
                <span>{cat}</span>
                <span className={`text-slate-400 transition-transform ${catOpen ? 'rotate-90' : ''}`}>›</span>
              </button>
              {catOpen && (
                <div className="px-3 pb-2 space-y-1">
                  {subs.map((sub) => (
                    <div key={sub} className="border-l-2 border-slate-200 dark:border-slate-600 pl-3">
                      <div className="py-1 text-sm text-slate-600 dark:text-slate-300">{sub} <span className="text-slate-400">({byCat[cat][sub].length})</span></div>
                      <ul>
                        {byCat[cat][sub].map((it) => (
                          <li key={it.id} className="py-1.5 flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={!!it.packed} onChange={() => toggle(it)} />
                            <span className={it.packed ? 'line-through text-slate-400' : ''}>{it.name}</span>
                            <span className="ml-auto text-xs text-slate-400 tabular-nums">×{it.needed || it.qty || 1}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

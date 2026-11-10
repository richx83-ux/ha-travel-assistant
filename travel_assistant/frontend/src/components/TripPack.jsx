import { useState, useEffect, useMemo } from 'react'
import Button from './Button'

export default function TripPack({ tripId, base = '', onBack }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState({})
  const [storeItems, setStoreItems] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [adding, setAdding] = useState(false)

  const load = () => {
    fetch(base + '/api/trips/' + tripId + '/luggage')
      .then((r) => r.ok ? r.json() : { items: [] })
      .then((d) => setItems(d.items || []))
      .finally(() => setLoading(false))
    fetch(base + '/api/packing')
      .then((r) => r.ok ? r.json() : { items: [] })
      .then((d) => setStoreItems(d.items || []))
      .catch(() => {})
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

  const toggleSelected = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const addSelected = async () => {
    if (selected.size === 0) return
    setAdding(true)
    const toAdd = storeItems.filter((it) => selected.has(it.id)).map((it) => ({
      kit_item_id: it.id,
      name: it.name,
      category: it.category || 'Other',
      qty: it.qty || 1,
      bag_id: it.bag_id || null,
    }))
    await fetch(base + '/api/trips/' + tripId + '/luggage/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: toAdd }),
    })
    setSelected(new Set())
    setAdding(false)
    load()
  }

  const removeItem = async (it) => {
    if (!confirm('Remove ' + it.name + ' from this trip?')) return
    setItems((list) => list.filter((x) => x.id !== it.id))
    await fetch(base + '/api/trips/' + tripId + '/luggage/' + it.id + '/delete', { method: 'POST' })
    load()
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
        <Button variant="secondary" onClick={onBack}>Back</Button>
        <h1 className="text-xl font-semibold">Pack</h1>
        <span className="text-sm text-slate-400">{packed} / {items.length} packed</span>
      </div>
      {items.length === 0 && <p className="text-sm text-slate-500">No items on this trip yet. Use Plan and Add to trip first.</p>}
      <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
        <div className="text-sm font-medium mb-2">Add from store cupboard</div>
        <StorePicker
          storeItems={storeItems}
          tripItems={items}
          selected={selected}
          toggleSelected={toggleSelected}
          onAdd={addSelected}
          adding={adding}
        />
      </div>
      <div className="space-y-2">
        {cats.map((cat, ci) => {
          const subs = Object.keys(byCat[cat]).sort()
          const catOpen = open[cat] !== false
          return (
            <div key={cat} className={`border rounded-lg ${colours[ci % colours.length]}`}>
              <button type="button" className="w-full flex items-center justify-between px-3 py-3 text-left text-base font-medium" onClick={() => setOpen((g) => ({ ...g, [cat]: !catOpen }))}>
                <span>{cat}</span>
                <span className={`text-slate-400 transition-transform ${catOpen ? 'rotate-90' : ''}`}>›</span>
              </button>
              {catOpen && (
                <div className="px-3 pb-2 space-y-1">
                  {subs.map((sub) => (
                    <div key={sub} className="border-l-2 border-slate-200 dark:border-slate-600 pl-3">
                      <div className="py-1.5 text-base text-slate-600 dark:text-slate-300">{sub} <span className="text-slate-400">({byCat[cat][sub].length})</span></div>
                      <ul>
                        {byCat[cat][sub].map((it) => (
                          <li key={it.id} className="py-2 flex items-center gap-3 text-base">
                            <input type="checkbox" className="w-5 h-5" checked={!!it.packed} onChange={() => toggle(it)} />
                            <span className={it.packed ? 'line-through text-slate-400' : ''}>{it.name}</span>
                            <span className="ml-auto text-base font-medium text-slate-500 tabular-nums">×{it.needed || it.qty || 1}</span>
                            <button type="button" onClick={() => removeItem(it)} className="text-xs text-red-500">Remove</button>
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


function StorePicker({ storeItems, tripItems, selected, toggleSelected, onAdd, adding }) {
  const tripIds = new Set((tripItems || []).map((t) => t.kit_item_id).filter(Boolean))
  const available = (storeItems || []).filter((it) => !tripIds.has(it.id))
  const byCat = {}
  available.forEach((it) => {
    const cat = it.bag_name ? ('Bags · ' + it.bag_name) : (it.category || 'Other')
    byCat[cat] = byCat[cat] || []
    byCat[cat].push(it)
  })
  const cats = Object.keys(byCat).sort()

  if (!available.length) return <p className="text-xs text-slate-400">Nothing left in the cupboard that isn’t already on this trip.</p>

  return (
    <div>
      <div className="max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-700 rounded p-2 text-sm space-y-2">
        {cats.map((cat) => (
          <div key={cat}>
            <div className="font-medium text-slate-700 dark:text-slate-300 mb-1">{cat}</div>
            <ul className="space-y-1 pl-2">
              {byCat[cat].map((it) => (
                <li key={it.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selected.has(it.id)}
                    onChange={() => toggleSelected(it.id)}
                    className="w-4 h-4"
                  />
                  <span>{it.name}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {selected.size > 0 && (
        <Button className="mt-2" onClick={onAdd} disabled={adding}>
          {adding ? 'Adding…' : `Add ${selected.size} selected`}
        </Button>
      )}
    </div>
  )
}

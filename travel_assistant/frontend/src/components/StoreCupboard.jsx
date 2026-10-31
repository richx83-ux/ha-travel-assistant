import { useState, useEffect, useMemo } from 'react'
import Button from './Button'


export default function StoreCupboard({ base = '' }) {
  const [bags, setBags] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('')
  const [showAddItem, setShowAddItem] = useState(false)
  const [showCreateBag, setShowCreateBag] = useState(false)
  const [editingBag, setEditingBag] = useState(null)
  const [renaming, setRenaming] = useState(null)
  const [moving, setMoving] = useState(null)
  const [newItem, setNewItem] = useState({ name: '', category: '', qty: 1, per_day: false })
  const [newBagName, setNewBagName] = useState('')
  const [renameName, setRenameName] = useState('')
  const [moveBagId, setMoveBagId] = useState('')

  const load = () => {
    setLoading(true)
    fetch(base + '/api/packing')
      .then((r) => r.ok ? r.json() : Promise.reject('Failed to load'))
      .then((d) => {
        setBags(d.bags || [])
        setItems(d.items || [])
        setError(null)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [base])

  const clothes = useMemo(() => items.filter((i) => !i.bag_id), [items])
  const categories = useMemo(() => {
    const cats = [...new Set(clothes.map((i) => i.category || 'Other'))].filter(Boolean).sort()
    return cats
  }, [clothes])

  useEffect(() => {
    if (!tab && categories.length) setTab(categories[0])
    else if (!tab) setTab('Bags')
  }, [categories, tab])

  const addItem = async () => {
    if (!newItem.name.trim()) return
    await fetch(base + '/api/packing/item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: newItem.name,
        category: newItem.category || 'Other',
        qty: Number(newItem.qty) || 1,
        per_day: newItem.per_day,
      }),
    })
    setNewItem({ name: '', category: '', qty: 1, per_day: false })
    setShowAddItem(false)
    load()
  }

  const createBag = async () => {
    if (!newBagName.trim()) return
    await fetch(base + '/api/packing/bag', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newBagName, category: '' }),
    })
    setNewBagName('')
    setShowCreateBag(false)
    load()
  }

  const deleteItem = async (id) => {
    if (!confirm('Remove this item?')) return
    await fetch(base + '/api/packing/item/' + id + '/delete', { method: 'POST' })
    load()
  }

  const deleteBag = async (id) => {
    if (!confirm('Delete this bag? Items will become loose.')) return
    await fetch(base + '/api/packing/bag/' + id + '/delete', { method: 'POST' })
    load()
  }

  const renameItem = async () => {
    if (!renaming || !renameName.trim()) return
    await fetch(base + '/api/packing/item/' + renaming.id + '/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: renameName }),
    })
    setRenaming(null)
    setRenameName('')
    load()
  }

  const moveItem = async () => {
    if (!moving || !moveBagId) return
    // Use existing form endpoint via fetch isn't ideal; we'll just update by re-adding logic
    // For now call a simple update if available, else skip. We'll add move via existing POST form style.
    const form = new FormData()
    form.append('bag_id', moveBagId)
    await fetch(base + '/packing/item/' + moving.id + '/move', { method: 'POST', body: form })
    setMoving(null)
    setMoveBagId('')
    load()
  }

  const addItemToBag = async (bagId, name) => {
    if (!name.trim()) return
    await fetch(base + '/api/packing/item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, bag_id: bagId, category: '' }),
    })
    load()
  }

  if (loading) return <p className="text-slate-500">Loading store cupboard…</p>
  if (error) return <p className="text-red-600">{error}</p>

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Store cupboard</h1>
          <p className="mt-1 text-slate-500">Things available to take. Set up bags once, then use them on every trip.</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowAddItem(true)}>Add item</Button>
          <Button variant="secondary" onClick={() => setShowCreateBag(true)}>Create bag</Button>
        </div>
      </div>
      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-4">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setTab(cat)}
            className={`px-4 py-2 text-sm font-medium rounded-lg ${tab === cat ? 'bg-brand-600 text-white' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200'}`}
          >
            {cat}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setTab('Bags')}
          className={`px-4 py-2 text-sm font-medium rounded-lg ${tab === 'Bags' ? 'bg-brand-600 text-white' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200'}`}
        >
          Bags
        </button>
      </div>

      {/* Category panels */}
      {categories.map((cat) => tab === cat && (
        <div key={cat} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <h2 className="font-semibold text-slate-900 dark:text-slate-100 mb-3">{cat}</h2>
          <ul className="divide-y divide-slate-100 dark:divide-slate-700">
            {clothes.filter((i) => (i.category || 'Other') === cat).map((it) => (
              <li key={it.id} className="py-2 flex items-center justify-between text-sm">
                <span>
                  {it.name}
                  {it.every_days === 1 && <span className="text-slate-400"> · 1 per day</span>}
                  {it.every_days > 1 && <span className="text-slate-400"> · lasts {it.every_days} days</span>}
                </span>
                <span className="flex items-center gap-3">
                  <button type="button" onClick={() => { setMoving(it); setMoveBagId(bags[0]?.id || '') }} className="text-xs text-brand-700">+ Add to bag</button>
                  <button type="button" onClick={() => { setRenaming(it); setRenameName(it.name) }} className="text-xs text-slate-500">Rename</button>
                  <button type="button" onClick={() => deleteItem(it.id)} className="text-xs text-red-500">Remove</button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {/* Bags tab */}
      {tab === 'Bags' && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <h2 className="font-semibold text-slate-900 dark:text-slate-100 mb-3">Bags</h2>
          {bags.length === 0 && <p className="text-sm text-slate-500">No bags yet.</p>}
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {bags.map((b) => {
              const bagItems = items.filter((i) => i.bag_id === b.id)
              return (
                <div key={b.id} className="border border-slate-100 dark:border-slate-700 rounded-lg p-4">
                  <div className="font-medium text-slate-900 dark:text-slate-100">{b.name}</div>
                  <div className="text-xs text-slate-400 mb-3">{b.category || 'Bag'} · {bagItems.length} items</div>
                  <button type="button" onClick={() => setEditingBag(editingBag === b.id ? null : b.id)} className="text-sm text-brand-700">
                    {editingBag === b.id ? 'Close' : 'Edit bag'}
                  </button>
                  {editingBag === b.id && (
                    <div className="mt-3">
                      <ul className="text-sm space-y-1 mb-2">
                        {bagItems.map((it) => (
                          <li key={it.id} className="flex justify-between">
                            <span>{it.name}</span>
                            <button onClick={() => deleteItem(it.id)} className="text-xs text-red-400">Remove</button>
                          </li>
                        ))}
                        {bagItems.length === 0 && <li className="text-xs text-slate-400">Empty bag</li>}
                      </ul>
                      <form onSubmit={(e) => { e.preventDefault(); const n = e.target.itemName.value; addItemToBag(b.id, n); e.target.reset() }} className="flex gap-2">
                        <input name="itemName" required placeholder="Add item" className="flex-1 px-2 py-1 border border-slate-200 rounded text-sm" />
                        <button className="text-sm text-brand-700">Add</button>
                      </form>
                      <button onClick={() => deleteBag(b.id)} className="mt-2 text-xs text-red-500">Delete bag</button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Add item modal */}
      {showAddItem && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setShowAddItem(false)}>
          <div className="bg-white dark:bg-slate-900 rounded-xl max-w-lg w-full max-h-[80vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">Add item</h2>
              <button type="button" onClick={() => setShowAddItem(false)} className="text-slate-400">Close</button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Item name</label>
                <input value={newItem.name} onChange={(e) => setNewItem({ ...newItem, name: e.target.value })} placeholder="e.g. Socks" className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Category</label>
                <input value={newItem.category} onChange={(e) => setNewItem({ ...newItem, category: e.target.value })} list="categories" placeholder="Pick or type a category" className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
                <datalist id="categories">
                  <option value="Clothes" /><option value="Health" /><option value="Tech" /><option value="Documents" /><option value="Toiletries" /><option value="Other" />
                </datalist>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Quantity</label>
                <input type="number" min="1" value={newItem.qty} onChange={(e) => setNewItem({ ...newItem, qty: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <input type="checkbox" checked={newItem.per_day} onChange={(e) => setNewItem({ ...newItem, per_day: e.target.checked })} /> One per day
              </label>
              <Button onClick={addItem}>Add item</Button>
            </div>
          </div>
        </div>
      )}

      {/* Create bag modal */}
      {showCreateBag && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setShowCreateBag(false)}>
          <div className="bg-white dark:bg-slate-900 rounded-xl max-w-lg w-full p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">Create bag</h2>
              <button type="button" onClick={() => setShowCreateBag(false)} className="text-slate-400">Close</button>
            </div>
            <input value={newBagName} onChange={(e) => setNewBagName(e.target.value)} placeholder="Bag name" className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3" />
            <Button onClick={createBag}>Save bag</Button>
          </div>
        </div>
      )}

      {/* Rename modal */}
      {renaming && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setRenaming(null)}>
          <div className="bg-white dark:bg-slate-900 rounded-xl max-w-sm w-full p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">Rename</h2>
              <button type="button" onClick={() => setRenaming(null)} className="text-slate-400">Close</button>
            </div>
            <input value={renameName} onChange={(e) => setRenameName(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3" />
            <Button onClick={renameItem}>Save</Button>
          </div>
        </div>
      )}

      {/* Move to bag modal */}
      {moving && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setMoving(null)}>
          <div className="bg-white dark:bg-slate-900 rounded-xl max-w-sm w-full p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">Add {moving.name} to a bag</h2>
              <button type="button" onClick={() => setMoving(null)} className="text-slate-400">Close</button>
            </div>
            <select value={moveBagId} onChange={(e) => setMoveBagId(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3">
              {bags.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <Button onClick={moveItem}>Add to bag</Button>
          </div>
        </div>
      )}
    </div>
  )
}

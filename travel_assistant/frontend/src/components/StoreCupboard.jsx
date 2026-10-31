import { useState, useEffect } from 'react'
import Button from './Button'

export default function StoreCupboard({ base = '' }) {
  const [bags, setBags] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [addingBag, setAddingBag] = useState(false)
  const [addingItem, setAddingItem] = useState(false)
  const [newBagName, setNewBagName] = useState('')
  const [newBagCat, setNewBagCat] = useState('')
  const [newItem, setNewItem] = useState({ name: '', category: '', bag_id: '', qty: 1 })

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

  const addBag = async () => {
    if (!newBagName.trim()) return
    const res = await fetch(base + '/api/packing/bag', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newBagName, category: newBagCat }),
    })
    if (res.ok) {
      setNewBagName('')
      setNewBagCat('')
      setAddingBag(false)
      load()
    }
  }

  const addItem = async () => {
    if (!newItem.name.trim()) return
    const body = {
      ...newItem,
      bag_id: newItem.bag_id ? Number(newItem.bag_id) : null,
      qty: Number(newItem.qty) || 1,
    }
    const res = await fetch(base + '/api/packing/item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (res.ok) {
      setNewItem({ name: '', category: '', bag_id: '', qty: 1 })
      setAddingItem(false)
      load()
    }
  }

  const deleteItem = async (id) => {
    if (!confirm('Delete this item?')) return
    await fetch(base + '/api/packing/item/' + id + '/delete', { method: 'POST' })
    load()
  }

  const deleteBag = async (id) => {
    if (!confirm('Delete this bag? Items will become loose.')) return
    await fetch(base + '/api/packing/bag/' + id + '/delete', { method: 'POST' })
    load()
  }

  const loose = items.filter((i) => !i.bag_id)

  if (loading) return <p className="text-slate-500">Loading store cupboard…</p>
  if (error) return <p className="text-red-600">{error}</p>

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Store cupboard</h2>
        <div className="flex gap-2">
          <Button onClick={() => setAddingBag(true)}>+ Bag</Button>
          <Button onClick={() => setAddingItem(true)}>+ Item</Button>
        </div>
      </div>

      {addingBag && (
        <div className="flex gap-2 p-3 border rounded-lg bg-white dark:bg-slate-800">
          <input
            className="flex-1 px-3 py-2 border rounded text-sm bg-white dark:bg-slate-700"
            placeholder="Bag name"
            value={newBagName}
            onChange={(e) => setNewBagName(e.target.value)}
          />
          <input
            className="w-32 px-3 py-2 border rounded text-sm bg-white dark:bg-slate-700"
            placeholder="Category"
            value={newBagCat}
            onChange={(e) => setNewBagCat(e.target.value)}
          />
          <Button onClick={addBag}>Save</Button>
          <Button variant="secondary" onClick={() => setAddingBag(false)}>Cancel</Button>
        </div>
      )}

      {addingItem && (
        <div className="flex flex-wrap gap-2 p-3 border rounded-lg bg-white dark:bg-slate-800">
          <input
            className="flex-1 min-w-[140px] px-3 py-2 border rounded text-sm bg-white dark:bg-slate-700"
            placeholder="Item name"
            value={newItem.name}
            onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
          />
          <input
            className="w-32 px-3 py-2 border rounded text-sm bg-white dark:bg-slate-700"
            placeholder="Category"
            value={newItem.category}
            onChange={(e) => setNewItem({ ...newItem, category: e.target.value })}
          />
          <select
            className="px-3 py-2 border rounded text-sm bg-white dark:bg-slate-700"
            value={newItem.bag_id}
            onChange={(e) => setNewItem({ ...newItem, bag_id: e.target.value })}
          >
            <option value="">Loose</option>
            {bags.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            className="w-16 px-2 py-2 border rounded text-sm bg-white dark:bg-slate-700"
            value={newItem.qty}
            onChange={(e) => setNewItem({ ...newItem, qty: e.target.value })}
          />
          <Button onClick={addItem}>Save</Button>
          <Button variant="secondary" onClick={() => setAddingItem(false)}>Cancel</Button>
        </div>
      )}

      {bags.map((bag) => {
        const bagItems = items.filter((i) => i.bag_id === bag.id)
        return (
          <div key={bag.id} className="border rounded-lg p-3 bg-white dark:bg-slate-800">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-medium">{bag.name}</span>
                {bag.category && <span className="ml-2 text-xs text-slate-500">{bag.category}</span>}
              </div>
              <button onClick={() => deleteBag(bag.id)} className="text-red-500 text-sm">Delete</button>
            </div>
            {bagItems.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">Empty</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {bagItems.map((i) => (
                  <li key={i.id} className="flex items-center justify-between text-sm">
                    <span>{i.name}{i.qty > 1 ? ` ×${i.qty}` : ''}{i.category ? ` · ${i.category}` : ''}</span>
                    <button onClick={() => deleteItem(i.id)} className="text-red-500 text-xs">Remove</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}

      {loose.length > 0 && (
        <div className="border rounded-lg p-3 bg-white dark:bg-slate-800">
          <div className="font-medium">Loose items</div>
          <ul className="mt-2 space-y-1">
            {loose.map((i) => (
              <li key={i.id} className="flex items-center justify-between text-sm">
                <span>{i.name}{i.qty > 1 ? ` ×${i.qty}` : ''}{i.category ? ` · ${i.category}` : ''}</span>
                <button onClick={() => deleteItem(i.id)} className="text-red-500 text-xs">Remove</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {bags.length === 0 && loose.length === 0 && (
        <p className="text-slate-500">No bags or items yet. Add some above.</p>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'

export default function StoreCupboard({ base = '' }) {
  const [bags, setBags] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(base + '/api/packing')
      .then((r) => r.ok ? r.json() : Promise.reject('Failed to load'))
      .then((d) => {
        setBags(d.bags || [])
        setItems(d.items || [])
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [base])

  if (loading) return <p className="text-slate-500">Loading store cupboard…</p>
  if (error) return <p className="text-red-600">{error}</p>

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h2 className="text-xl font-semibold">Store cupboard</h2>
      {bags.length === 0 && items.length === 0 && (
        <p className="text-slate-500">No bags or items yet. Add them from the classic packing page for now.</p>
      )}
      {bags.map((bag) => (
        <div key={bag.id} className="border rounded-lg p-3 bg-white dark:bg-slate-800">
          <div className="font-medium">{bag.name}</div>
          <ul className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {items.filter((i) => i.bag_id === bag.id).map((i) => (
              <li key={i.id}>{i.name}</li>
            ))}
          </ul>
        </div>
      ))}
      {items.filter((i) => !i.bag_id).length > 0 && (
        <div className="border rounded-lg p-3 bg-white dark:bg-slate-800">
          <div className="font-medium">Loose items</div>
          <ul className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {items.filter((i) => !i.bag_id).map((i) => (
              <li key={i.id}>{i.name}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

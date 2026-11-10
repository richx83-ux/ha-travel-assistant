
import { useState, useEffect } from 'react'
import Button from './Button'


function alwaysPack(it) {
  const n = (it.name || '').toLowerCase()
  return !!it.in_bag || n.includes('electrolyte')
}
function seedChecks(store, items) {
  const init = {}
  ;(items || []).forEach((it) => { if (alwaysPack(it)) init[Number(it.id)] = true })
  ;(store || []).forEach((s) => {
    const pack = s.pack === true || s.pack === 'true' || s.pack === 1 || s.pack === 'yes'
    if (!pack) return
    const byId = (items || []).find((it) => Number(it.id) === Number(s.id))
    const byName = (items || []).find((it) => (it.name || '').toLowerCase() === (s.name || '').toLowerCase())
    const hit = byId || byName
    if (hit) init[Number(hit.id)] = true
    else if (s.id != null) init[Number(s.id)] = true
  })
  return init
}

function tempColor(c) {
  if (c == null) return 'bg-slate-200 text-slate-700'
  if (c < 5) return 'bg-blue-600 text-white'
  if (c < 12) return 'bg-sky-500 text-white'
  if (c < 18) return 'bg-emerald-500 text-white'
  if (c < 24) return 'bg-amber-500 text-white'
  return 'bg-red-500 text-white'
}

function fmtDate(d) {
  if (!d) return ''
  const m = String(d).match(/(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return d
  return m[3] + '-' + m[2] + '-' + m[1].slice(2)
}

function conditionIcon(cond) {
  const s = (cond || '').toLowerCase()
  if (s.includes('snow')) return '❄️'
  if (s.includes('rain') || s.includes('shower')) return '🌧️'
  if (s.includes('storm') || s.includes('thunder')) return '⛈️'
  if (s.includes('cloud')) return '☁️'
  if (s.includes('sun') || s.includes('clear')) return '☀️'
  if (s.includes('fog') || s.includes('mist')) return '🌫️'
  if (s.includes('wind')) return '💨'
  return '🌤️'
}

export default function TripPlan({ tripId, base = '', onBack }) {
  const [trip, setTrip] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [raw, setRaw] = useState('')
  const [saved, setSaved] = useState(false)
  const [packList, setPackList] = useState([])
  const [tripDays, setTripDays] = useState(1)
  const [checked, setChecked] = useState({})
  const [openGroups, setOpenGroups] = useState({})
  const [savedMsg, setSavedMsg] = useState('')

  useEffect(() => {
    if (!tripId) return
    setLoading(true)
    Promise.all([
      fetch(base + '/api/trips/' + tripId).then((r) => r.ok ? r.json() : Promise.reject('Failed to load trip')),
      fetch(base + '/api/trips/' + tripId + '/plan').then((r) => r.ok ? r.json() : { saved: false }),
      fetch(base + '/api/trips/' + tripId + '/packing-list').then((r) => r.ok ? r.json() : { items: [] }),
    ])
      .then(([d, plan, list]) => {
        const t = d.trip || d
        setTrip(t)
        const start = t.start_date || ''
        const end = t.end_date || ''
        const dest = t.name || 'the destination'
        setPrompt(
          `I am going on a trip from ${start} to ${end} in ${dest}. ` +
          `What do I need to pack? What is the average temperature and the current forecasted temperatures for those dates?`
        )
        if (plan.saved) {
          setResult(plan.result || {})
          setRaw(plan.raw || '')
          setSaved(true)
          setChecked(seedChecks(plan.result?.store, list.items))
          if (plan.prompt) setPrompt(plan.prompt)
        }
        setPackList(list.items || [])
        setTripDays(list.days || 1)
        setError(null)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [tripId, base])

  const send = async () => {
    setSending(true)
    setError(null)
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 130000)
    try {
      const res = await fetch(base + '/api/trips/' + tripId + '/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
        signal: ctrl.signal,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Grok call failed')
      setResult(data.result || {})
      setRaw(data.raw || '')
      setSaved(true)
      setChecked(seedChecks(data.result?.store, packList))
      if (data.prompt) setPrompt(data.prompt)
    } catch (e) {
      if (e.name === 'AbortError') setError('Grok took too long. Try again.')
      else setError(String(e.message || e))
    } finally {
      clearTimeout(timer)
      setSending(false)
    }
  }


  const reset = async () => {
    if (!confirm('Clear the saved plan for this trip?')) return
    await fetch(base + '/api/trips/' + tripId + '/plan/reset', { method: 'POST' })
    setResult(null)
    setRaw('')
    setSaved(false)
    setChecked(seedChecks(null, packList))
  }


  const addToTrip = async () => {
    const ids = packList.filter((it) => alwaysPack(it) || checked[Number(it.id)]).map((it) => it.id)
    const res = await fetch(base + '/api/trips/' + tripId + '/packing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_ids: ids }),
    })
    const data = await res.json()
    if (!res.ok) { setError(data.detail || 'Could not save'); return }
    setError(null)
    setSavedMsg(data.count + ' items added to the trip')
  }

  if (loading) return <p className="text-slate-500">Loading trip…</p>
  if (!trip) return <p className="text-red-600">Trip not found</p>

  const weather = result?.weather
  const packing = result?.packing
  const forecast = Array.isArray(weather?.forecast) ? weather.forecast : []

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={onBack}>Back</Button>
        <h1 className="text-xl font-semibold">{trip.name} · Plan</h1>
        {saved && <span className="text-xs text-slate-400">Saved</span>}
      </div>
      <p className="text-sm text-slate-500">
        {trip.start_date} → {trip.end_date}
      </p>

      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
        <label className="block text-sm font-medium mb-2">Prompt for Grok</label>
        <textarea
          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm min-h-[120px] bg-white dark:bg-slate-700"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div className="mt-3">
          <Button onClick={send} disabled={sending}>{sending ? 'Asking Grok…' : saved ? 'Refresh from Grok' : 'Send to Grok'}</Button>
          {saved && <button type="button" onClick={reset} className="ml-2 text-sm text-slate-500 hover:underline">Reset plan</button>}
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {weather && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Weather</h2>
            {weather.average_temp_c != null && (
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${tempColor(weather.average_temp_c)}`}>
                Avg {weather.average_temp_c}°C
              </span>
            )}
          </div>
          {weather.summary && <p className="text-sm text-slate-600 dark:text-slate-300 mb-4">{weather.summary}</p>}
          {forecast.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {forecast.map((f, i) => (
                <div key={i} className={`rounded-xl p-3 min-h-[110px] flex flex-col ${tempColor(f.high_c)}`}>
                  <div className="flex items-start justify-between">
                    <div className="text-lg font-semibold">{fmtDate(f.date)}</div>
                    <div className="text-4xl leading-none">{conditionIcon(f.conditions)}</div>
                  </div>
                  <div className="text-sm mt-1 truncate">{f.location || ''}</div>
                  <div className="mt-auto flex items-end justify-between">
                    <div className="text-xs opacity-90">{f.conditions}</div>
                    <div className="text-xl font-bold">{f.high_c}°</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="mt-3 flex gap-2 text-xs text-slate-500">
            <span className="px-2 py-0.5 rounded bg-blue-600 text-white">{"<5°"}</span>
            <span className="px-2 py-0.5 rounded bg-sky-500 text-white">5–12°</span>
            <span className="px-2 py-0.5 rounded bg-emerald-500 text-white">12–18°</span>
            <span className="px-2 py-0.5 rounded bg-amber-500 text-white">18–24°</span>
            <span className="px-2 py-0.5 rounded bg-red-500 text-white">{">24°"}</span>
          </div>
        </div>
      )}

      {packList.length > 0 && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-semibold">From your store</h2>
            <Button onClick={addToTrip}>Add to trip</Button>
          </div>
          {savedMsg && <p className="text-xs text-emerald-600 mb-2">{savedMsg}</p>}
          <p className="text-xs text-slate-500 mb-3">
            {tripDays} day trip · {(result?.store || []).filter((s) => s.pack === true || s.pack === 'true').length} recommended by Grok · quantities from your rules
          </p>
          <StoreGroups
            items={packList}
            recs={result?.store || []}
            checked={checked}
            setChecked={setChecked}
            openGroups={openGroups}
            setOpenGroups={setOpenGroups}
          />
        </div>
      )}

      {Array.isArray(result?.extra) && result.extra.length > 0 && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h2 className="font-semibold mb-2">Recommended but not in store</h2>
          <ul className="divide-y divide-slate-100 dark:divide-slate-700 text-sm">
            {result.extra.map((s, i) => (
              <li key={i} className="py-2 flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-slate-500">
                    {s.category}{s.clothing_type ? ` · ${s.clothing_type}` : ''}
                    {s.reason ? ` — ${s.reason}` : ''}
                  </div>
                </div>
                <div className="flex flex-col gap-1 shrink-0">
                  <button
                    type="button"
                    className="text-xs text-brand-700"
                    onClick={async () => {
                      await fetch(base + '/api/packing/item', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: s.name, category: s.category || 'Other', qty: 1 }),
                      })
                      alert('Added to store cupboard')
                    }}
                  >Add to cupboard</button>
                  <button
                    type="button"
                    className="text-xs text-brand-700"
                    onClick={async () => {
                      await fetch(base + '/api/trips/' + tripId + '/luggage/add', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: s.name, category: s.category || 'Other', qty: 1 }),
                      })
                      alert('Added to this trip')
                    }}
                  >Add to trip</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result && (!weather?.summary && !forecast.length && !(packing?.suggested||[]).length) && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h2 className="font-semibold mb-2">Grok reply</h2>
          <pre className="text-xs whitespace-pre-wrap text-slate-600 dark:text-slate-300">{raw || JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}


function StoreGroups({ items, recs, checked, setChecked, openGroups, setOpenGroups }) {
  const byCat = {}
  items.forEach((it) => {
    const cat = it.in_bag ? ('Bags · ' + (it.bag_name || 'Bag')) : (it.category || 'Other')
    const sub = it.in_bag ? 'In bag' : (it.clothing_type || 'General')
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
    'bg-orange-50 border-orange-200 dark:bg-orange-950 dark:border-orange-800',
    'bg-indigo-50 border-indigo-200 dark:bg-indigo-950 dark:border-indigo-800',
  ]

  return (
    <div className="space-y-2">
      {cats.map((cat, ci) => {
        const subs = Object.keys(byCat[cat]).sort()
        const catOpen = openGroups[cat] !== false
        const colour = colours[ci % colours.length]
        return (
          <div key={cat} className={`border rounded-lg ${colour}`}>
            <button type="button" className="w-full flex items-center justify-between px-3 py-2 text-left text-sm font-medium" onClick={() => setOpenGroups((g) => ({ ...g, [cat]: !catOpen }))}>
              <span>{cat}</span>
              <span className={`text-slate-400 transition-transform ${catOpen ? 'rotate-90' : ''}`}>›</span>
            </button>
            {catOpen && (
              <div className="px-3 pb-2 space-y-1">
                {subs.map((sub) => {
                  const key = cat + ':' + sub
                  const subOpen = openGroups[key] !== false
                  const list = byCat[cat][sub]
                  return (
                    <div key={sub} className="border-l-2 border-slate-200 dark:border-slate-600 pl-3">
                      <button type="button" className="w-full flex items-center justify-between py-1 text-left text-sm" onClick={() => setOpenGroups((g) => ({ ...g, [key]: !subOpen }))}>
                        <span className="text-slate-600 dark:text-slate-300">{sub} <span className="text-slate-400">({list.length})</span></span>
                        <span className={`text-slate-400 transition-transform ${subOpen ? 'rotate-90' : ''}`}>›</span>
                      </button>
                      {subOpen && (
                        <ul className="pb-1">
                          {list.map((it) => {
                            const rec = recs.find((s) => Number(s.id) === Number(it.id))
                              || recs.find((s) => (s.name || '').toLowerCase() === (it.name || '').toLowerCase())
                            const on = alwaysPack(it) || !!checked[Number(it.id)]
                            return (
                              <li key={it.id} className="py-1.5 flex items-start gap-2 text-sm">
                                <input type="checkbox" className="mt-0.5" checked={on} onChange={(e) => setChecked((c) => ({ ...c, [Number(it.id)]: e.target.checked }))} />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className={on ? '' : 'text-slate-400'}>{it.name}</span>
                                    <span className="text-xs text-slate-400 tabular-nums">×{it.need}</span>
                                  </div>
                                  {rec?.reason && <div className="text-xs text-slate-500">{rec.reason}</div>}
                                </div>
                              </li>
                            )
                          })}
                        </ul>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

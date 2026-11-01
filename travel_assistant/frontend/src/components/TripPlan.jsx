
function seedChecks(store) {
  const init = {}
  ;(store || []).forEach((s) => {
    const pack = s.pack === true || s.pack === 'true' || s.pack === 1
    if (pack) init[Number(s.id)] = true
  })
  return init
}
import { useState, useEffect } from 'react'
import Button from './Button'

function tempColor(c) {
  if (c == null) return 'bg-slate-200 text-slate-700'
  if (c < 5) return 'bg-blue-600 text-white'
  if (c < 12) return 'bg-sky-500 text-white'
  if (c < 18) return 'bg-emerald-500 text-white'
  if (c < 24) return 'bg-amber-500 text-white'
  return 'bg-red-500 text-white'
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
          setChecked(seedChecks(plan.result?.store))
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
      setChecked(seedChecks(data.result?.store))
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
    setChecked({})
  }

  if (loading) return <p className="text-slate-500">Loading trip…</p>
  if (!trip) return <p className="text-red-600">Trip not found</p>

  const weather = result?.weather
  const packing = result?.packing
  const forecast = Array.isArray(weather?.forecast) ? weather.forecast : []

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-sm text-slate-500 hover:underline">← Back</button>
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
                <div key={i} className={`rounded-xl p-3 ${tempColor(f.high_c)}`}>
                  <div className="text-2xl">{conditionIcon(f.conditions)}</div>
                  <div className="text-xs opacity-90 mt-1">{f.date}</div>
                  <div className="text-lg font-semibold">{f.low_c}° / {f.high_c}°</div>
                  <div className="text-xs opacity-90">{f.conditions}</div>
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
          <h2 className="font-semibold mb-1">From your store</h2>
          <p className="text-xs text-slate-500 mb-3">
            {tripDays} day trip · {(result?.store || []).filter((s) => s.pack === true || s.pack === 'true').length} recommended by Grok · quantities from your rules
          </p>
          <StoreGroups
            items={packList}
            recs={result.store || []}
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
              <li key={i} className="py-2">
                <div className="font-medium">{s.name}</div>
                <div className="text-xs text-slate-500">
                  {s.category}{s.clothing_type ? ` · ${s.clothing_type}` : ''}
                  {s.reason ? ` — ${s.reason}` : ''}
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
    const cat = it.category || 'Other'
    const sub = it.clothing_type || 'General'
    byCat[cat] = byCat[cat] || {}
    byCat[cat][sub] = byCat[cat][sub] || []
    byCat[cat][sub].push(it)
  })
  const cats = Object.keys(byCat).sort()

  return (
    <div className="space-y-2">
      {cats.map((cat) => {
        const subs = Object.keys(byCat[cat]).sort()
        const catOpen = openGroups[cat] !== false
        return (
          <div key={cat} className="border border-slate-100 dark:border-slate-700 rounded-lg">
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
                            const on = !!checked[Number(it.id)]
                            return (
                              <li key={it.id} className="py-1 flex items-center gap-2 text-sm">
                                <input type="checkbox" checked={on} onChange={(e) => setChecked((c) => ({ ...c, [Number(it.id)]: e.target.checked }))} />
                                <span className={on ? '' : 'text-slate-400'}>{it.name}</span>
                                <span className="ml-auto text-xs text-slate-400 tabular-nums">×{it.need}</span>
                                {rec?.reason && <span className="text-xs text-slate-400 hidden sm:inline">{rec.reason}</span>}
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

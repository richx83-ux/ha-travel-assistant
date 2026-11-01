import { useState, useEffect } from 'react'
import Button from './Button'

export default function TripPlan({ tripId, base = '', onBack }) {
  const [trip, setTrip] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [raw, setRaw] = useState('')

  useEffect(() => {
    if (!tripId) return
    setLoading(true)
    fetch(base + '/api/trips/' + tripId)
      .then((r) => r.ok ? r.json() : Promise.reject('Failed to load trip'))
      .then((d) => {
        setTrip(d.trip || d)
        // Build a draft prompt from what we know; the server will rebuild if empty
        const t = d.trip || d
        const start = t.start_date || ''
        const end = t.end_date || ''
        const dest = t.name || 'the destination'
        setPrompt(
          `I am going on a trip from ${start} to ${end} in ${dest}. ` +
          `What do I need to pack? What is the average temperature and the current forecasted temperatures for those dates?`
        )
        setError(null)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [tripId, base])

  const send = async () => {
    setSending(true)
    setError(null)
    try {
      const res = await fetch(base + '/api/trips/' + tripId + '/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Grok call failed')
      setResult(data.result || {})
      setRaw(data.raw || '')
      if (data.prompt) setPrompt(data.prompt)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setSending(false)
    }
  }

  if (loading) return <p className="text-slate-500">Loading trip…</p>
  if (!trip) return <p className="text-red-600">Trip not found</p>

  const weather = result?.weather
  const packing = result?.packing

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-sm text-slate-500 hover:underline">← Back</button>
        <h1 className="text-xl font-semibold">{trip.name} · Plan</h1>
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
          <Button onClick={send} disabled={sending}>{sending ? 'Asking Grok…' : 'Send to Grok'}</Button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {weather && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h2 className="font-semibold mb-2">Weather</h2>
          {weather.average_temp_c != null && (
            <p className="text-sm mb-1">Average: {weather.average_temp_c}°C</p>
          )}
          {weather.summary && <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">{weather.summary}</p>}
          {Array.isArray(weather.forecast) && weather.forecast.length > 0 && (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700 text-sm">
              {weather.forecast.map((f, i) => (
                <li key={i} className="py-2 flex justify-between">
                  <span>{f.date}</span>
                  <span>{f.low_c}° / {f.high_c}° · {f.conditions}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {packing && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h2 className="font-semibold mb-2">Suggested packing</h2>
          {packing.notes && <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">{packing.notes}</p>}
          {Array.isArray(packing.suggested) && packing.suggested.length > 0 && (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700 text-sm">
              {packing.suggested.map((s, i) => (
                <li key={i} className="py-2">
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-slate-500">
                    {s.category}{s.clothing_type ? ` · ${s.clothing_type}` : ''}
                    {s.reason ? ` — ${s.reason}` : ''}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result && !weather && !packing && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h2 className="font-semibold mb-2">Grok reply</h2>
          <pre className="text-xs whitespace-pre-wrap text-slate-600 dark:text-slate-300">{raw || JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

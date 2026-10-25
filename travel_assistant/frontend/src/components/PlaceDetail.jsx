import { useState, useEffect, useRef } from 'react'
import Button from './Button'
import Input from './Input'
import Badge from './Badge'
import ImageUpload from './ImageUpload'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

function todayISO() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export default function PlaceDetail({ place, onClose, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ ...place })
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const fileRef = useRef(null)

  // Always load the full place by id so trip stops and lists show the same details
  useEffect(() => {
    const id = place.id || place.location_id
    if (!id) return
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    fetch(base + '/api/places/' + id)
      .then((r) => r.ok ? r.json() : null)
      .then((p) => {
        if (p) {
          setForm({ ...place, ...p, id: p.id, name: p.name || place.name, url: p.url || place.url || place.location_url || '' })
          setLoaded(true)
        }
      })
      .catch(() => {})
  }, [place.id, place.location_id])

  const photo = assetUrl(form.image_url || form.visit_photo_url || '')
  const visitPhoto = assetUrl(form.visit_photo_url || '')
  const icon = assetUrl(place.icon_url)
  const location = [place.city, place.county, place.region].filter(Boolean).join(', ')

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const uploadVisitPhoto = async (file) => {
    if (!file) return
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(base + '/api/places/' + (form.id || place.id) + '/image', {
        method: 'POST',
        body: formData,
      })
      const d = await res.json()
      if (!res.ok) throw new Error(d.detail || 'Upload failed')
      setForm((f) => ({ ...f, visit_photo_url: d.url || '' }))
    } catch (e) {
      alert(e.message || 'Upload failed')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const save = async () => {
    setSaving(true)
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    try {
      const res = await fetch(base + '/api/places/' + place.id, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          address: form.address,
          notes: form.notes,
          url: form.url,
          opening_hours: form.opening_hours,
          city: form.city,
          county: form.county,
          region: form.region,
          postcode: form.postcode,
          visit_duration_mins: form.visit_duration_mins,
          visited: !!form.visited,
          visit_date: form.visited ? (form.visit_date || null) : null,
          image_url: form.image_url || '',
          visit_photo_url: form.visit_photo_url || '',
          hidden: form.hidden ? 1 : 0,
        }),
      })
      if (!res.ok) throw new Error('Save failed')
      setEditing(false)
      onSaved && onSaved({ ...place, ...form })
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!confirm('Delete this place? This cannot be undone.')) return
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    const res = await fetch(base + '/api/places/' + place.id + '/delete', { method: 'POST' })
    if (!res.ok) { alert('Delete failed'); return }
    onSaved && onSaved({ ...place, _deleted: true })
    onClose()
  }

  const cancel = () => {
    setForm({ ...place })
    setEditing(false)
  }

  const toggleVisited = () => {
    const next = !form.visited
    setForm((f) => ({
      ...f,
      visited: next,
      visit_date: next ? (f.visit_date || todayISO()) : null,
    }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-0 md:p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white dark:bg-slate-900 rounded-t-2xl md:rounded-2xl shadow-xl max-h-[90vh] overflow-auto">
        {/* Header image */}
        <div className="relative h-40 bg-slate-200 dark:bg-slate-800">
          {photo ? (
            <img src={photo} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-4xl text-slate-400" style={{ backgroundColor: place.primary_color || '#0d9488' }}>
              {(place.name || '?')[0]}
            </div>
          )}
          {icon && (
            <img src={icon} alt="" className="absolute bottom-3 left-3 w-10 h-10 rounded-full border-2 border-white bg-white object-contain" />
          )}
          <button onClick={onClose} className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/40 text-white flex items-center justify-center">&times;</button>
        </div>

        <div className="p-4">
          <div className="flex items-start justify-between gap-2">
            {editing ? (
              <Input value={form.name || ''} onChange={(e) => set('name', e.target.value)} className="text-lg font-semibold" />
            ) : (
              <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{place.name}</h2>
            )}
            <Badge color={form.visited ? 'green' : 'gray'}>
              {form.visited ? 'Visited' : 'Not visited'}
            </Badge>
          </div>
          {!editing && location && <p className="text-sm text-slate-500 mt-1">{location}</p>}
          {!editing && place.theme_name && <p className="text-xs text-slate-400">{place.theme_name}</p>}

          {/* Read-only visit details in view mode */}
          {!editing && form.visited && (
            <div className="mt-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2">
              <div className="text-sm font-medium">Visit details</div>
              {form.visit_date && (
                <div className="text-sm text-slate-600 dark:text-slate-300">Visited on {form.visit_date}</div>
              )}
              {visitPhoto ? (
                <img src={visitPhoto} alt="Visit" className="w-full max-h-48 object-cover rounded-lg border border-slate-200 dark:border-slate-700" />
              ) : (
                <div className="text-sm text-slate-500">No visit picture</div>
              )}
            </div>
          )}

          {/* Cruise itinerary (shown for cruise ship type or when itinerary exists) */}
          {((form.category_type_name || '') + ' ' + (form.theme_name || '') + ' ' + (place.theme_name || '')).toLowerCase().includes('cruise') || form.itinerary_json ? (
            <CruiseItinerary placeId={form.id || place.id} base={window.location.pathname.replace(/\/react.*$/, '') || ''} editing={editing} />
          ) : null}

          <div className="mt-4 space-y-3 text-sm">
            {editing && (
              <label className="flex items-center justify-between text-sm">
                <span>Hide from places</span>
                <button type="button" onClick={() => set('hidden', form.hidden ? 0 : 1)} className="flex items-center">
                  <span className={`relative w-10 h-6 rounded-full transition-colors ${form.hidden ? 'bg-brand-600' : 'bg-slate-300'}`}>
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${form.hidden ? 'translate-x-4' : ''}`} />
                  </span>
                </button>
              </label>
            )}

            {/* Visit editing controls — only in Edit mode */}
            {editing && (
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Visit status</span>
                  <button type="button" onClick={toggleVisited} className="flex items-center">
                    <span className={`relative w-10 h-6 rounded-full transition-colors ${form.visited ? 'bg-emerald-600' : 'bg-slate-300'}`}>
                      <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${form.visited ? 'translate-x-4' : ''}`} />
                    </span>
                  </button>
                </div>

                {form.visited && (
                  <>
                    <div>
                      <label className="text-xs font-medium text-slate-500">Visit date</label>
                      <input
                        type="date"
                        className="mt-1 w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800"
                        value={form.visit_date || ''}
                        onChange={(e) => set('visit_date', e.target.value || null)}
                      />
                    </div>

                    <div>
                      <div className="text-xs font-medium text-slate-500 mb-1">Visit picture</div>
                      {visitPhoto ? (
                        <img src={visitPhoto} alt="Visit" className="w-full max-h-40 object-cover rounded-lg border border-slate-200 dark:border-slate-700" />
                      ) : (
                        <div className="text-sm text-slate-500 py-1">No visit picture</div>
                      )}
                      <div className="flex gap-2 mt-2">
                        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => uploadVisitPhoto(e.target.files?.[0])} />
                        <Button variant="secondary" type="button" onClick={() => fileRef.current?.click()}>
                          {visitPhoto ? 'Change picture' : 'Add picture'}
                        </Button>
                        {visitPhoto && (
                          <Button variant="secondary" type="button" onClick={() => set('visit_photo_url', '')}>
                            Remove picture
                          </Button>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {editing && (
              <ImageUpload
                value={form.image_url || ''}
                uploadUrl={(window.location.pathname.replace(/\/react.*$/, '') || '') + '/api/places/' + place.id + '/image'}
                onUploaded={async (url) => {
                  setForm((f) => ({ ...f, image_url: url }))
                  if (!url) {
                    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
                    await fetch(base + '/api/places/' + place.id + '/clear-image', { method: 'POST' })
                  }
                }}
                label="Place image"
              />
            )}
            <Field label="Address" editing={editing} value={form.address} onChange={(v) => set('address', v)} />
            <div className="grid grid-cols-2 gap-2">
              <Field label="City" editing={editing} value={form.city} onChange={(v) => set('city', v)} />
              <Field label="County" editing={editing} value={form.county} onChange={(v) => set('county', v)} />
              <Field label="Region" editing={editing} value={form.region} onChange={(v) => set('region', v)} />
              <Field label="Postcode" editing={editing} value={form.postcode} onChange={(v) => set('postcode', v)} />
            </div>
            <Field label="Notes" editing={editing} value={form.notes} onChange={(v) => set('notes', v)} multiline />
            <Field label="Website" editing={editing} value={form.url} onChange={(v) => set('url', v)} link={!editing} />
            <Field label="Opening hours" editing={editing} value={form.opening_hours} onChange={(v) => set('opening_hours', v)} />
            <Field label="Visit duration (mins)" editing={editing} value={form.visit_duration_mins} onChange={(v) => set('visit_duration_mins', v)} />
          </div>

          <div className="flex justify-between gap-2 mt-6">
            {editing ? (
              <>
                <Button variant="secondary" onClick={remove}>Delete</Button>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={cancel} disabled={saving}>Cancel</Button>
                  <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
                </div>
              </>
            ) : (
              <div className="flex-1 flex justify-end">
                <Button onClick={() => setEditing(true)}>Edit</Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Field({ label, editing, value, onChange, multiline, link }) {
  return (
    <div>
      <div className="text-xs font-medium text-slate-500 mb-0.5">{label}</div>
      {editing ? (
        multiline ? (
          <textarea
            className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800"
            rows={3}
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
          />
        ) : (
          <Input value={value || ''} onChange={(e) => onChange(e.target.value)} />
        )
      ) : link && value ? (
        <a href={value} target="_blank" rel="noopener" className="text-brand-600 hover:underline break-all">{value}</a>
      ) : (
        <div className="text-slate-800 dark:text-slate-200 whitespace-pre-wrap">{value || '—'}</div>
      )}
    </div>
  )
}


function CruiseItinerary({ placeId, base, editing }) {
  const [cruises, setCruises] = useState([])
  const [openId, setOpenId] = useState(null)
  const [days, setDays] = useState({})
  const [url, setUrl] = useState('')
  const [startDate, setStartDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const load = () => {
    fetch(base + '/api/ships/' + placeId + '/cruises')
      .then(r => r.json())
      .then(d => setCruises(d.cruises || []))
      .catch(() => {})
  }
  useEffect(() => { if (placeId) load() }, [placeId])

  const toggle = async (id) => {
    if (openId === id) { setOpenId(null); return }
    setOpenId(id)
    if (!days[id]) {
      const r = await fetch(base + '/api/cruises/' + id)
      const d = await r.json()
      setDays(prev => ({ ...prev, [id]: d.days || [] }))
    }
  }

  const doImport = async () => {
    if (!url.trim()) return
    setBusy(true); setMsg('')
    const res = await fetch(base + '/api/ships/' + placeId + '/cruises/import', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ url, start_date: startDate || undefined })
    })
    const d = await res.json()
    setBusy(false)
    if (d.ok) { setMsg('Added ' + d.name); setUrl(''); load() }
    else setMsg(d.detail || 'Import failed')
  }

  return (
    <div className="mt-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2">
      <div className="text-sm font-medium">Cruises</div>
      {cruises.length === 0 && <div className="text-sm text-slate-500">No sailings yet. Import a cruise URL.</div>}
      {cruises.map((cr) => (
        <div key={cr.id} className="border border-slate-200 dark:border-slate-700 rounded-lg">
          <button type="button" className="w-full flex items-center justify-between px-3 py-2 text-sm" onClick={() => toggle(cr.id)}>
            <span className="font-medium">{cr.name || (cr.code + '-' + cr.year)}</span>
            <span className="text-xs text-slate-400">{cr.start_date || ''} {openId === cr.id ? '▾' : '▸'}</span>
          </button>
          {openId === cr.id && (
            <div className="px-3 pb-2 space-y-1">
              {(days[cr.id] || []).map((d) => (
                <div key={d.id || d.day} className="flex items-center gap-2 text-sm">
                  {d.image_url && <img src={d.image_url} alt="" className="w-8 h-8 rounded object-cover" />}
                  <span className="text-xs text-slate-400 w-12">Day {d.day}</span>
                  <span className="flex-1 truncate">{d.port}</span>
                  {d.date && <span className="text-xs text-slate-400">{d.date.slice(5)}</span>}
                </div>
              ))}
              {(days[cr.id] || []).length === 0 && <div className="text-xs text-slate-500">No ports.</div>}
            </div>
          )}
        </div>
      ))}
      <div className="pt-2 space-y-2">
        <input className="w-full px-2 py-1 border rounded text-sm bg-white dark:bg-slate-800" placeholder="Paste cruise URL (SeaScanner or P&O)" value={url} onChange={e => setUrl(e.target.value)} />
        <input type="date" className="w-full px-2 py-1 border rounded text-sm bg-white dark:bg-slate-800" value={startDate} onChange={e => setStartDate(e.target.value)} title="Departure date if the page does not show one" />
        <Button variant="secondary" type="button" onClick={doImport} disabled={busy || !url.trim()}>{busy ? 'Importing…' : 'Import sailing'}</Button>
        {msg && <div className="text-xs text-slate-500">{msg}</div>}
      </div>
    </div>
  )
}

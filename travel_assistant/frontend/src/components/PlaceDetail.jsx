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
  const [visitOpen, setVisitOpen] = useState(false)
  const [visitBusy, setVisitBusy] = useState(false)
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
          if (p.visited) setVisitOpen(true)
        }
      })
      .catch(() => {})
  }, [place.id, place.location_id])

  const photo = assetUrl(form.image_url || form.visit_photo_url || '')
  const visitPhoto = assetUrl(form.visit_photo_url || '')
  const icon = assetUrl(place.icon_url)
  const location = [place.city, place.county, place.region].filter(Boolean).join(', ')

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const saveVisit = async (updates) => {
    setVisitBusy(true)
    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
    const next = { ...form, ...updates }
    try {
      const res = await fetch(base + '/api/places/' + (form.id || place.id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visited: !!next.visited,
          visit_date: next.visited ? (next.visit_date || todayISO()) : null,
          visit_photo_url: next.visit_photo_url || '',
        }),
      })
      if (!res.ok) throw new Error('Save failed')
      setForm(next)
      onSaved && onSaved({ ...place, ...next })
    } catch (e) {
      alert(e.message || 'Could not update visit')
    } finally {
      setVisitBusy(false)
    }
  }

  const onBadgeClick = async () => {
    if (form.visited) {
      setVisitOpen((o) => !o)
      return
    }
    // Mark as visited with today
    await saveVisit({ visited: true, visit_date: todayISO() })
    setVisitOpen(true)
  }

  const clearVisit = async () => {
    if (!confirm('Remove visit status? The date will be cleared.')) return
    await saveVisit({ visited: false, visit_date: null, visit_photo_url: '' })
    setVisitOpen(false)
  }

  const uploadVisitPhoto = async (file) => {
    if (!file) return
    setVisitBusy(true)
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
      // The image endpoint sets image_url; also copy it to visit_photo_url
      await saveVisit({ visit_photo_url: d.url || '' })
    } catch (e) {
      alert(e.message || 'Upload failed')
    } finally {
      setVisitBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const removeVisitPhoto = async () => {
    await saveVisit({ visit_photo_url: '' })
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
            <button type="button" onClick={onBadgeClick} disabled={visitBusy} className="flex-shrink-0" title={form.visited ? 'Show visit details' : 'Mark as visited'}>
              <Badge color={form.visited ? 'green' : 'gray'}>
                {form.visited ? 'Visited' : 'Not visited'}
              </Badge>
            </button>
          </div>
          {!editing && location && <p className="text-sm text-slate-500 mt-1">{location}</p>}
          {!editing && place.theme_name && <p className="text-xs text-slate-400">{place.theme_name}</p>}

          {/* Visit details panel (opened by clicking the badge) */}
          {(visitOpen || form.visited) && !editing && (
            <div className="mt-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">Visit details</div>
                {visitBusy && <span className="text-xs text-slate-500">Saving…</span>}
              </div>

              <div>
                <label className="text-xs font-medium text-slate-500">Visit date</label>
                <input
                  type="date"
                  className="mt-1 w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800"
                  value={form.visit_date || ''}
                  onChange={(e) => saveVisit({ visited: true, visit_date: e.target.value || null })}
                  disabled={visitBusy}
                />
              </div>

              <div>
                <div className="text-xs font-medium text-slate-500 mb-1">Visit picture</div>
                {visitPhoto ? (
                  <img src={visitPhoto} alt="Visit" className="w-full max-h-48 object-cover rounded-lg border border-slate-200 dark:border-slate-700" />
                ) : (
                  <div className="text-sm text-slate-500 py-2">No visit picture</div>
                )}
                <div className="flex gap-2 mt-2">
                  <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => uploadVisitPhoto(e.target.files?.[0])} />
                  <Button variant="secondary" type="button" onClick={() => fileRef.current?.click()} disabled={visitBusy}>
                    {visitPhoto ? 'Change picture' : 'Add picture'}
                  </Button>
                  {visitPhoto && (
                    <Button variant="secondary" type="button" onClick={removeVisitPhoto} disabled={visitBusy}>
                      Remove picture
                    </Button>
                  )}
                </div>
              </div>

              <div className="pt-1">
                <Button variant="secondary" type="button" onClick={clearVisit} disabled={visitBusy}>
                  Remove visit status
                </Button>
              </div>
            </div>
          )}

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
            {editing && (
              <ImageUpload
                value={form.image_url || form.visit_photo_url || ''}
                uploadUrl={(window.location.pathname.replace(/\/react.*$/, '') || '') + '/api/places/' + place.id + '/image'}
                onUploaded={async (url) => {
                  setForm((f) => ({ ...f, image_url: url, visit_photo_url: '' }))
                  if (!url) {
                    const base = window.location.pathname.replace(/\/react.*$/, '') || ''
                    await fetch(base + '/api/places/' + place.id + '/clear-image', { method: 'POST' })
                  }
                }}
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

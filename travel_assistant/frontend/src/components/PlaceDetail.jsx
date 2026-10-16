import { useState } from 'react'
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

export default function PlaceDetail({ place, onClose, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ ...place })
  const [saving, setSaving] = useState(false)

  const photo = assetUrl(place.image_url || place.default_image_url || place.visit_photo_url)
  const icon = assetUrl(place.icon_url)
  const location = [place.city, place.county, place.region].filter(Boolean).join(', ')

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

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
            <Badge color={place.visited ? 'green' : 'gray'}>
              {place.visited ? 'Visited' : 'Not visited'}
            </Badge>
          </div>
          {!editing && location && <p className="text-sm text-slate-500 mt-1">{location}</p>}
          {!editing && place.theme_name && <p className="text-xs text-slate-400">{place.theme_name}</p>}

          <div className="mt-4 space-y-3 text-sm">
            {editing && (
              <ImageUpload
                value={form.image_url}
                uploadUrl={(window.location.pathname.replace(/\/react.*$/, '') || '') + '/api/places/' + place.id + '/image'}
                onUploaded={(url) => {
                  set('image_url', url)
                  onSaved && onSaved({ ...place, ...form, image_url: url })
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

          <div className="flex justify-end gap-2 mt-6">
            {editing ? (
              <>
                <Button variant="secondary" onClick={cancel} disabled={saving}>Cancel</Button>
                <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
              </>
            ) : (
              <Button onClick={() => setEditing(true)}>Edit</Button>
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

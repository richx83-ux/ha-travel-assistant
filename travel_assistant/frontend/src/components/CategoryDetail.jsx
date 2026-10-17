import { useEffect, useState } from 'react'
import Button from './Button'
import ImageUpload from './ImageUpload'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function CategoryDetail({ category, base, types, onClose, onSaved, onViewPlaces }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(category)
  const [saving, setSaving] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  useEffect(() => { setForm(category) }, [category])

  const save = async () => {
    setSaving(true)
    const res = await fetch(base + '/api/categories/' + category.id, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setSaving(false)
    if (res.ok) {
      setEditing(false)
      onSaved && onSaved(form)
    }
  }

  const showVisits = !category.hide_visit_status && category.total > 0
  const photo = assetUrl(form.default_image_url)
  const icon = assetUrl(form.icon_url)

  return (
    <div className="fixed inset-0 z-[2000] flex items-end sm:items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl w-full sm:max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="relative h-40 bg-slate-100 dark:bg-slate-800">
          {photo ? (
            <img src={photo} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full" style={{ background: form.primary_color || '#0d9488' }} />
          )}
          {icon && <img src={icon} alt="" className="absolute bottom-3 left-3 w-10 h-10 rounded-lg bg-white/90 p-1 object-contain" />}
          <button onClick={onClose} className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/40 text-white">✕</button>
        </div>
        <div className="p-4 space-y-3">
          {editing ? (
            <input className="w-full text-lg font-semibold bg-transparent border-b border-slate-300 dark:border-slate-600" value={form.name || ''} onChange={(e) => set('name', e.target.value)} />
          ) : (
            <h2 className="text-lg font-semibold">{form.name}</h2>
          )}
          <div className="text-sm text-slate-500">
            {category.total || 0} places
            {showVisits && <> · {category.visited || 0} visited · {category.percentage || 0}%</>}
          </div>
          <button onClick={() => onViewPlaces && onViewPlaces(category)} className="text-sm text-brand-600 dark:text-brand-400 font-medium">View places</button>

          <Field label="Description" editing={editing} value={form.description} onChange={(v) => set('description', v)} multiline />
          <div>
            <div className="text-xs text-slate-500 mb-1">Category type</div>
            {editing ? (
              <select className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={form.category_type_id || ''} onChange={(e) => set('category_type_id', e.target.value || null)}>
                <option value="">None</option>
                {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            ) : (
              <div className="text-sm">{form.category_type_name || '—'}</div>
            )}
          </div>
          <div className="flex gap-4">
            <ColorField label="Primary colour" editing={editing} value={form.primary_color} onChange={(v) => set('primary_color', v)} />
            <ColorField label="Secondary colour" editing={editing} value={form.secondary_color} onChange={(v) => set('secondary_color', v)} />
          </div>
          {editing && (
            <>
              <ImageUpload label="Icon" value={form.icon_url} uploadUrl={base + '/api/upload'} onUploaded={(url) => set('icon_url', url)} />
              <ImageUpload label="Default picture" value={form.default_image_url} uploadUrl={base + '/api/upload'} onUploaded={(url) => set('default_image_url', url)} />
            </>
          )}
        </div>
        <div className="sticky bottom-0 p-4 bg-white dark:bg-slate-900 border-t flex gap-2">
          {editing ? (
            <>
              <Button variant="secondary" onClick={() => { setForm(category); setEditing(false) }} className="flex-1">Cancel</Button>
              <Button onClick={save} disabled={saving} className="flex-1">{saving ? 'Saving…' : 'Save'}</Button>
            </>
          ) : (
            <Button onClick={() => setEditing(true)} className="flex-1">Edit</Button>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, editing, value, onChange, multiline }) {
  return (
    <div>
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      {editing ? (
        multiline ? (
          <textarea className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" rows={3} value={value || ''} onChange={(e) => onChange(e.target.value)} />
        ) : (
          <input className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={value || ''} onChange={(e) => onChange(e.target.value)} />
        )
      ) : (
        <div className="text-sm whitespace-pre-wrap">{value || '—'}</div>
      )}
    </div>
  )
}

function ColorField({ label, editing, value, onChange }) {
  return (
    <div className="flex-1">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      {editing ? (
        <input type="color" value={value || '#0d9488'} onChange={(e) => onChange(e.target.value)} className="w-full h-9 rounded" />
      ) : (
        <div className="flex items-center gap-2 text-sm">
          <span className="w-5 h-5 rounded" style={{ background: value || '#ccc' }} />
          {value || '—'}
        </div>
      )}
    </div>
  )
}

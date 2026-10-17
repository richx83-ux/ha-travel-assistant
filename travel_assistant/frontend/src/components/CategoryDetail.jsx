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
  const [paste, setPaste] = useState('')
  const [busy, setBusy] = useState('')
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

  const act = async (path, confirmMsg) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return
    setBusy(path)
    await fetch(base + path, { method: 'POST' })
    setBusy('')
    if (path.endsWith('/delete')) { onSaved && onSaved({ ...category, _deleted: true }); onClose() }
  }
  const importCsv = async () => {
    if (!paste.trim()) return
    setBusy('import')
    const form = new FormData()
    form.append('theme_name', category.name)
    form.append('paste', paste)
    await fetch(base + '/import/csv', { method: 'POST', body: form })
    setBusy('')
    setPaste('')
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
              <label className="flex items-center justify-between text-sm">
                <span>Active</span>
                <button type="button" onClick={() => set('is_active', form.is_active ? 0 : 1)} className="flex items-center">
                  <span className={`relative w-10 h-6 rounded-full transition-colors ${form.is_active ? 'bg-brand-600' : 'bg-slate-300'}`}>
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${form.is_active ? 'translate-x-4' : ''}`} />
                  </span>
                </button>
              </label>
            </>
          )}
          {!editing && (
            <div className="text-sm text-slate-500">Status: {form.is_active ? 'Active' : 'Inactive'}</div>
          )}

          <div className="border-t pt-3 space-y-2">
            <div className="text-xs font-medium text-slate-500">Import places</div>
            <textarea className="w-full px-3 py-2 border rounded-lg text-sm font-mono" rows={3} placeholder="Paste CSV text" value={paste} onChange={(e) => setPaste(e.target.value)} />
            <Button variant="secondary" onClick={importCsv} disabled={busy === 'import'}>{busy === 'import' ? 'Importing…' : 'Import CSV'}</Button>
          </div>

          <div className="border-t pt-3 space-y-2">
            <Button variant="secondary" onClick={() => act('/api/categories/' + category.id + '/refresh')} disabled={!!busy}>Refresh from postcodes</Button>
          </div>
          {editing && (
            <div className="border border-red-200 dark:border-red-900 rounded-xl p-3 space-y-2">
              <div className="text-xs font-medium text-red-600">Danger zone</div>
              <Button variant="secondary" onClick={() => act('/api/categories/' + category.id + '/delete-places', 'Delete ALL places in this category? This cannot be undone.')} disabled={!!busy}>Delete all places</Button>
              <Button variant="secondary" onClick={() => act('/api/categories/' + category.id + '/delete', 'Delete this category and all its places? This cannot be undone.')} disabled={!!busy}>Delete category</Button>
            </div>
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

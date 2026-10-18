import { useState, useEffect, useRef } from 'react'
import Button from './Button'
import Input from './Input'
import ImageUpload from './ImageUpload'

const TABS = [
  { id: 'types', label: 'Category types' },
  { id: 'home', label: 'Home' },
  { id: 'appearance', label: 'Appearance' },
  { id: 'library', label: 'Image library' },
  { id: 'data', label: 'Data' },
]

const FLAGS = [
  { key: 'achievement_eligible', label: 'Counts towards achievements' },
  { key: 'exclude_from_places', label: 'Hide from places list' },
  { key: 'exclude_from_maps', label: 'Hide from maps' },
  { key: 'exclude_from_counts', label: 'Exclude from counts' },
  { key: 'hide_visit_status', label: 'Hide visit status' },
]

const ROLES = [
  { value: '', label: 'None' },
  { value: 'visit', label: 'Place to visit' },
  { value: 'overnight', label: 'Accommodation' },
  { value: 'flexible', label: 'Flexible (e.g. supercharger)' },
  { value: 'home', label: 'Home' },
]

export default function Settings({ base = '', onAccent }) {
  const [tab, setTab] = useState('types')
  const [data, setData] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = () => {
    fetch(base + '/api/settings').then((r) => r.json()).then(setData)
  }
  useEffect(() => { load() }, [])

  if (!data) return <div className="p-4 text-slate-500">Loading settings…</div>

  const saveType = async (t) => {
    setSaving(true)
    await fetch(base + '/api/category-types/' + t.id, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(t),
    })
    setSaving(false)
    load()
  }

  const addType = async (name) => {
    if (!name.trim()) return
    await fetch(base + '/api/category-types', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() }),
    })
    load()
  }

  const deleteType = async (id) => {
    if (!confirm('Remove this type? Categories using it will be unassigned.')) return
    await fetch(base + '/api/category-types/' + id + '/delete', { method: 'POST' })
    load()
  }

  const saveUi = async (ui) => {
    setSaving(true)
    const res = await fetch(base + '/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ui),
    }).then((r) => r.json())
    setSaving(false)
    if (res.ui?.accent_color && onAccent) onAccent(res.ui.accent_color)
    load()
  }

  const saveHome = async (home) => {
    setSaving(true)
    await fetch(base + '/api/settings/home', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(home),
    })
    setSaving(false)
    load()
  }

  return (
    <div className="p-4 max-w-2xl mx-auto">
      {/* Tabs */}
      <div className="flex gap-1 mb-4 overflow-x-auto border-b border-slate-200 dark:border-slate-700">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 ${tab === t.id ? 'border-brand-600 text-brand-700 dark:text-brand-400' : 'border-transparent text-slate-500'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'types' && (
        <TypesTab types={data.category_types || []} onSave={saveType} onAdd={addType} onDelete={deleteType} saving={saving} />
      )}
      {tab === 'home' && (
        <HomeTab home={data.home} onSave={saveHome} saving={saving} />
      )}
      {tab === 'appearance' && (
        <AppearanceTab ui={data.ui} onSave={saveUi} saving={saving} />
      )}
      {tab === 'library' && <LibraryTab base={base} />}
      {tab === 'data' && (
        <div className="bg-white dark:bg-slate-900 rounded-xl border p-4">
          <h3 className="font-semibold mb-1">Export</h3>
          <p className="text-sm text-slate-500 mb-3">Download every theme, place, trip and setting as one JSON file.</p>
          <a href={base + '/settings/export'} className="inline-block px-4 py-2 bg-brand-600 text-white text-sm rounded-lg">Export all data</a>
        </div>
      )}
    </div>
  )
}

function TypesTab({ types, onSave, onAdd, onDelete, saving }) {
  const [newName, setNewName] = useState('')
  const [editing, setEditing] = useState(null)

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">Types control what a category does: achievements, visibility, and how it behaves on a trip.</p>
      <div className="flex gap-2">
        <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New type" />
        <Button onClick={() => { onAdd(newName); setNewName('') }}>Add</Button>
      </div>
      {types.map((t) => (
        <div key={t.id} className="bg-white dark:bg-slate-900 rounded-xl border p-4">
          {editing === t.id ? (
            <TypeForm type={t} onSave={(updated) => { onSave(updated); setEditing(null) }} onCancel={() => setEditing(null)} saving={saving} />
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">{t.name}</div>
                <div className="text-xs text-slate-500">{t.trip_role || 'no role'}</div>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setEditing(t.id)}>Edit</Button>
                <button onClick={() => onDelete(t.id)} className="text-red-500 text-sm px-2">Remove</button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function TypeForm({ type, onSave, onCancel, saving }) {
  const [form, setForm] = useState({ ...type })
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  return (
    <div className="space-y-3">
      <Input value={form.name || ''} onChange={(e) => set('name', e.target.value)} />
      <div>
        <label className="text-xs font-medium text-slate-500">Trip role</label>
        <select className="w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800" value={form.trip_role || ''} onChange={(e) => set('trip_role', e.target.value)}>
          {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </div>
      <div className="space-y-1">
        {FLAGS.map((f) => (
          <label key={f.key} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!form[f.key]} onChange={(e) => set(f.key, e.target.checked)} />
            {f.label}
          </label>
        ))}
      </div>
      <div className="flex gap-2">
        <Button onClick={() => onSave(form)} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  )
}

function HomeTab({ home, onSave, saving }) {
  const [form, setForm] = useState({ name: home?.name || 'Home', postcode: home?.postcode || '', icon_url: home?.icon_url || '', default_image_url: home?.default_image_url || '' })
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
      <p className="text-sm text-slate-500">Used as the start of day 1 and can be the final day destination. Visits are not tracked.</p>
      <div>
        <label className="text-xs font-medium">Name</label>
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </div>
      <div>
        <label className="text-xs font-medium">Postcode</label>
        <Input value={form.postcode} onChange={(e) => setForm({ ...form, postcode: e.target.value })} />
      </div>
      <ImageUpload label="Icon" value={form.icon_url} uploadUrl={base + '/api/upload'} onUploaded={(url) => setForm({ ...form, icon_url: url })} />
      <ImageUpload label="Default picture" value={form.default_image_url} uploadUrl={base + '/api/upload'} onUploaded={(url) => setForm({ ...form, default_image_url: url })} />
      <Button onClick={() => onSave(form)} disabled={saving}>{saving ? 'Saving…' : 'Save home'}</Button>
    </div>
  )
}

function AppearanceTab({ ui, onSave, saving }) {
  const [form, setForm] = useState({ ...ui })
  const fields = [
    { key: 'accent_color', label: 'Accent (buttons)' },
    { key: 'xai_api_key', label: 'xAI API key (for Add from link)' },
  ]
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="flex items-center gap-2">
          <label className="w-32 text-sm">{f.label}</label>
          <input type="color" value={form[f.key] || '#000000'} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} className="w-10 h-10 rounded border" />
          <Input value={form[f.key] || ''} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} className="font-mono" />
        </div>
      ))}
      <div className="flex gap-2">
        <Button onClick={() => onSave(form)} disabled={saving}>{saving ? 'Saving…' : 'Save colours'}</Button>
        <Button variant="secondary" onClick={() => onSave({ reset: true })}>Reset</Button>
      </div>
    </div>
  )
}

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

function LibraryTab({ base }) {
  const [images, setImages] = useState([])
  const [replaceFor, setReplaceFor] = useState(null)
  const inputRef = useRef(null)
  const load = () => fetch(base + '/api/library').then((r) => r.json()).then((d) => setImages(d.images || []))
  useEffect(() => { load() }, [])

  const remove = async (url) => {
    if (!window.confirm('Delete this unused image?')) return
    await fetch(base + '/api/library/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) })
    load()
  }
  const replace = async (oldUrl, file) => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const up = await fetch(base + '/api/upload', { method: 'POST', body: form }).then((r) => r.json())
    if (!up.url) return
    await fetch(base + '/api/library/replace', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ old: oldUrl, new: up.url }) })
    setReplaceFor(null)
    load()
  }

  return (
    <div className="space-y-2">
      <h3 className="font-semibold">Manage image library</h3>
      <p className="text-sm text-slate-500">Images you have uploaded. Unused images can be deleted. Replace swaps an image everywhere it is used.</p>
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f && replaceFor) replace(replaceFor, f); e.target.value = '' }} />
      {images.map((img) => (
        <div key={img.url} className="flex items-center gap-3 bg-white dark:bg-slate-900 border rounded-xl p-2">
          <img src={assetUrl(img.url)} alt="" className="w-12 h-12 rounded-lg object-cover bg-slate-100" />
          <div className="flex-1 min-w-0">
            <div className="text-sm truncate">{img.name}</div>
            <div className="text-xs text-slate-500">Used by {img.count} {img.count === 1 ? 'place' : 'places'}</div>
          </div>
          <Button variant="secondary" onClick={() => { setReplaceFor(img.url); inputRef.current?.click() }}>Replace</Button>
          {img.count === 0 && <Button variant="secondary" onClick={() => remove(img.url)}>Delete</Button>}
        </div>
      ))}
      {images.length === 0 && <p className="text-slate-500">No uploaded images yet.</p>}
    </div>
  )
}

import { useState, useEffect, useRef } from 'react'
import Button from './Button'
import Input from './Input'
import ImageUpload from './ImageUpload'

// Grouped by what you're changing, not by implementation detail
const TABS = [
  { id: 'places', label: 'Places' },
  { id: 'trips', label: 'Trips' },
  { id: 'appearance', label: 'Appearance' },
  { id: 'advanced', label: 'Advanced' },
]

const DEFAULT_ACCENT = '#14b8a6'

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

function SectionHeading({ children }) {
  return <h2 className="text-base font-semibold mt-6 mb-2 first:mt-0">{children}</h2>
}

export default function Settings({ base = '', onAccent }) {
  const [tab, setTab] = useState('places')
  const [data, setData] = useState(null)
  const [clothingCats, setClothingCats] = useState([])
  const [saving, setSaving] = useState(false)

  const load = () => {
    fetch(base + '/api/settings').then((r) => r.json()).then(setData)
  }
  useEffect(() => { load() }, [])
  const loadClothing = () => fetch(base + '/api/clothing-categories').then((r) => r.json()).then((d) => setClothingCats(d.categories || [])).catch(() => {})
  useEffect(() => { if (tab === 'trips') loadClothing() }, [tab])

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

  // Sends only the fields given, so saving one setting never touches another
  const saveUi = async (fields) => {
    setSaving(true)
    const res = await fetch(base + '/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields),
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
      {/* Tabs: one row, so every section is one tap away */}
      <div className="flex gap-1 mb-4 border-b border-slate-200 dark:border-slate-700 overflow-x-auto">
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

      {tab === 'places' && (
        <>
          <SectionHeading>Category types</SectionHeading>
          <TypesTab types={data.category_types || []} onSave={saveType} onAdd={addType} onDelete={deleteType} saving={saving} />
          <SectionHeading>Image library</SectionHeading>
          <LibraryTab base={base} />
        </>
      )}

      {tab === 'trips' && (
        <>
          <SectionHeading>Home</SectionHeading>
          <HomeTab home={data.home} onSave={saveHome} saving={saving} />
          <SectionHeading>Clothes categories</SectionHeading>
          <ClothesCategoriesTab
            base={base}
            categories={clothingCats}
            onAdd={async (name) => {
              await fetch(base + '/api/clothing-categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
              })
              loadClothing()
            }}
            onDelete={async (id) => {
              if (!confirm('Remove this clothing category?')) return
              await fetch(base + '/api/clothing-categories/' + id + '/delete', { method: 'POST' })
              loadClothing()
            }}
          />
        </>
      )}

      {tab === 'appearance' && (
        <AppearanceTab ui={data.ui} onSave={saveUi} saving={saving} />
      )}

      {tab === 'advanced' && (
        <>
          <SectionHeading>Connections</SectionHeading>
          <ApiKeySection ui={data.ui} onSave={saveUi} saving={saving} />
          <SectionHeading>Data</SectionHeading>
          <div className="bg-white dark:bg-slate-900 rounded-xl border p-4">
            <h3 className="font-semibold mb-1">Export</h3>
            <p className="text-sm text-slate-500 mb-3">Download every theme, place, trip and setting as one JSON file.</p>
            <a href={base + '/settings/export'} className="inline-block px-4 py-2 bg-brand-600 text-white text-sm rounded-lg">Export all data</a>
          </div>
        </>
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
  const base = (window.TA_BASE || window.location.pathname.replace(/\/react.*$/, '') || '') || ''
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
  const [color, setColor] = useState(ui.accent_color || DEFAULT_ACCENT)
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
      <p className="text-sm text-slate-500">The colour used for buttons and highlights across the app.</p>
      <div className="flex items-center gap-2">
        <label className="w-32 text-sm">Accent colour</label>
        <input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="w-10 h-10 rounded border" />
        <Input value={color} onChange={(e) => setColor(e.target.value)} className="font-mono" />
      </div>
      <div className="flex gap-2">
        <Button onClick={() => onSave({ accent_color: color })} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
        <Button variant="secondary" onClick={() => { setColor(DEFAULT_ACCENT); onSave({ accent_color: DEFAULT_ACCENT }) }}>Reset to default</Button>
      </div>
    </div>
  )
}

function ApiKeySection({ ui, onSave, saving }) {
  const [key, setKey] = useState('')
  const isSet = !!ui.xai_api_key_set
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3">
      <div>
        <h3 className="font-semibold">xAI API key</h3>
        <p className="text-sm text-slate-500">Used by the AI trip planner. Get a key from console.x.ai.</p>
      </div>
      <p className="text-sm">
        {isSet
          ? <>Status: <span className="text-green-600">key saved</span> <span className="font-mono text-slate-500">{ui.xai_api_key}</span></>
          : <span className="text-amber-600">No key saved</span>}
      </p>
      <Input
        type="password"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder={isSet ? 'Enter a new key to replace it' : 'Paste your xAI API key'}
        className="font-mono"
      />
      <div className="flex gap-2">
        <Button onClick={() => { onSave({ xai_api_key: key.trim() }); setKey('') }} disabled={saving || !key.trim()}>
          {saving ? 'Saving…' : 'Save key'}
        </Button>
        {isSet && (
          <Button
            variant="secondary"
            onClick={() => { if (confirm('Remove the key saved here? The AI planner will use the add-on configuration key, if there is one.')) onSave({ xai_api_key: '' }) }}
          >
            Remove key
          </Button>
        )}
      </div>
      <p className="text-xs text-slate-500">A key saved here takes priority. If none is saved, the key in the add-on configuration is used.</p>
    </div>
  )
}

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = (window.TA_BASE || window.location.pathname.replace(/\/react.*$/, '') || '') || ''
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

function ClothesCategoriesTab({ categories, onAdd, onDelete, base }) {
  const [name, setName] = useState('')
  const saveLasts = async (c, days) => {
    await fetch(base + '/api/clothing-categories/' + c.id, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lasts_days: days }),
    })
  }
  return (
    <div className="max-w-xl space-y-4">
      <p className="text-sm text-slate-500">Set how long each clothing type lasts. 0 means it lasts the whole trip (e.g. coat, shoes). 1 means one per day (e.g. underwear, socks).</p>
      <div className="flex gap-2">
        <input
          className="flex-1 px-3 py-2 border rounded-lg text-sm bg-white dark:bg-slate-800"
          placeholder="New category name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button onClick={() => { if (name.trim()) { onAdd(name.trim()); setName('') } }}>Add</Button>
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-700 border rounded-lg">
        {categories.map((c) => (
          <li key={c.id} className="flex items-center justify-between px-4 py-2 text-sm gap-3">
            <span className="flex-1">{c.name}</span>
            <label className="flex items-center gap-1 text-xs text-slate-500">
              Lasts
              <input
                type="number"
                min="0"
                defaultValue={c.lasts_days || 0}
                onBlur={(e) => saveLasts(c, Number(e.target.value) || 0)}
                className="w-14 px-2 py-1 border rounded text-sm"
              />
              days
            </label>
            <button onClick={() => onDelete(c.id)} className="text-xs text-red-500">Remove</button>
          </li>
        ))}
        {categories.length === 0 && <li className="px-4 py-3 text-sm text-slate-500">No clothing categories yet.</li>}
      </ul>
      <p className="text-xs text-slate-400">0 = whole trip. A 7-day trip with lasts 1 needs 7; lasts 3 needs 3.</p>
    </div>
  )
}

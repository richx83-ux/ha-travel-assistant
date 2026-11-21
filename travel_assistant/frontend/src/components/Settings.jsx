import { useState, useEffect, useRef } from 'react'
import Button from './Button'
import Input from './Input'
import ImageUpload from './ImageUpload'

// One page per setting. The list on the left is grouped only to make it easy to scan.
const GROUPS = ['Places', 'Trips', 'App']
const PAGES = [
  {
    id: 'types', group: 'Places', label: 'Category types',
    description: 'Types control what a category does: achievements, visibility, and how it behaves on a trip.',
  },
  {
    id: 'pictures', group: 'Places', label: 'Pictures',
    description: 'Photos used for places, visits and trips. Unused pictures can be deleted. Replace swaps a picture everywhere it is used.',
  },
  {
    id: 'icons', group: 'Places', label: 'Icons',
    description: 'Icons used for categories. Unused icons can be deleted. Replace swaps an icon everywhere it is used.',
  },
  {
    id: 'home', group: 'Trips', label: 'Home',
    description: 'Used as the start of day 1 and can be the final day destination. Visits are not tracked.',
  },
  {
    id: 'clothes', group: 'Trips', label: 'Clothes categories',
    description: 'Set how long each clothing type lasts. 0 means it lasts the whole trip (e.g. coat, shoes). 1 means one per day (e.g. underwear, socks).',
  },
  {
    id: 'appearance', group: 'App', label: 'Appearance',
    description: 'The colour used for buttons and highlights across the app.',
  },
  {
    id: 'apikey', group: 'App', label: 'xAI API key',
    description: 'Used by the AI trip planner. Get a key from console.x.ai.',
  },
  {
    id: 'export', group: 'App', label: 'Export data',
    description: 'Download every theme, place, trip and setting as one JSON file.',
  },
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

export default function Settings({ base = '', onAccent }) {
  const [pageId, setPageId] = useState(PAGES[0].id)
  const [data, setData] = useState(null)
  const [clothingCats, setClothingCats] = useState([])
  const [saving, setSaving] = useState(false)

  const load = () => {
    fetch(base + '/api/settings').then((r) => r.json()).then(setData)
  }
  useEffect(() => { load() }, [])
  const loadClothing = () => fetch(base + '/api/clothing-categories').then((r) => r.json()).then((d) => setClothingCats(d.categories || [])).catch(() => {})
  useEffect(() => { if (pageId === 'clothes') loadClothing() }, [pageId])

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

  const page = PAGES.find((p) => p.id === pageId) || PAGES[0]

  return (
    <div className="p-4 max-w-5xl mx-auto md:flex md:gap-8">
      {/* Page list: down the left on a wide screen, a scrolling row on a phone */}
      <nav className="md:w-52 md:shrink-0 mb-4 md:mb-0" aria-label="Settings pages">
        <div className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
          {GROUPS.map((group) => (
            <div key={group} className="flex gap-1 md:flex-col md:mb-3">
              <div className="hidden md:block px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{group}</div>
              {PAGES.filter((p) => p.group === group).map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPageId(p.id)}
                  className={`px-3 py-2 text-sm text-left rounded-lg whitespace-nowrap ${pageId === p.id ? 'bg-slate-200 dark:bg-slate-800 font-medium text-brand-700 dark:text-brand-400' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      </nav>

      {/* The chosen page, in the middle */}
      <main className="flex-1 min-w-0 max-w-2xl">
        <h2 className="text-lg font-semibold">{page.label}</h2>
        <p className="text-sm text-slate-500 mt-1 mb-4">{page.description}</p>

        {page.id === 'types' && (
          <TypesTab types={data.category_types || []} onSave={saveType} onAdd={addType} onDelete={deleteType} saving={saving} />
        )}
        {page.id === 'pictures' && <LibraryTab key="picture" base={base} kind="picture" />}
        {page.id === 'icons' && <LibraryTab key="icon" base={base} kind="icon" />}
        {page.id === 'home' && <HomeTab home={data.home} onSave={saveHome} saving={saving} />}
        {page.id === 'clothes' && (
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
        )}
        {page.id === 'appearance' && <AppearanceTab ui={data.ui} onSave={saveUi} saving={saving} />}
        {page.id === 'apikey' && <ApiKeySection ui={data.ui} onSave={saveUi} saving={saving} />}
        {page.id === 'export' && (
          <a href={base + '/settings/export'} className="inline-block px-4 py-2 bg-brand-600 text-white text-sm rounded-lg">Export all data</a>
        )}
      </main>
    </div>
  )
}

function TypesTab({ types, onSave, onAdd, onDelete, saving }) {
  const [newName, setNewName] = useState('')
  const [editing, setEditing] = useState(null)
  const used = types.filter((t) => (t.category_count || 0) > 0)
  const unused = types.filter((t) => !(t.category_count > 0))

  const renderType = (t) => (
    <div key={t.id} className="bg-white dark:bg-slate-900 rounded-xl border p-4">
      {editing === t.id ? (
        <TypeForm type={t} onSave={(updated) => { onSave(updated); setEditing(null) }} onCancel={() => setEditing(null)} saving={saving} />
      ) : (
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">{t.name}</div>
            <div className="text-xs text-slate-500">
              {t.trip_role || 'no role'}
              {t.category_count > 0 ? ` · ${t.category_count} categor${t.category_count === 1 ? 'y' : 'ies'}` : ''}
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setEditing(t.id)}>Edit</Button>
            <button onClick={() => onDelete(t.id)} className="text-red-500 text-sm px-2">Remove</button>
          </div>
        </div>
      )}
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New type" />
        <Button onClick={() => { onAdd(newName); setNewName('') }}>Add</Button>
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Used categories</h3>
        {used.length ? used.map(renderType) : <p className="text-sm text-slate-500">No types are assigned to a category yet.</p>}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Unused categories</h3>
        {unused.length ? unused.map(renderType) : <p className="text-sm text-slate-500">Every type is in use.</p>}
      </section>
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

function LibraryTab({ base, kind }) {
  const [images, setImages] = useState(null)
  const [replaceFor, setReplaceFor] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState('all') // all | unused
  const [selected, setSelected] = useState(() => new Set())
  const [view, setView] = useState(() => localStorage.getItem('ta_library_view') || 'thumbs')
  const inputRef = useRef(null)
  const noun = kind === 'icon' ? 'icon' : 'picture'

  const changeView = (v) => { setView(v); localStorage.setItem('ta_library_view', v) }
  const load = () =>
    fetch(base + '/api/library', { cache: 'no-store' })
      .then((r) => r.json())
      .then((d) => {
        const list = (d.images || []).filter((i) => i.kind === kind)
        setImages(list)
        setSelected((prev) => {
          const next = new Set()
          for (const url of prev) {
            const img = list.find((i) => i.url === url)
            if (img && img.count === 0) next.add(url)
          }
          return next
        })
      })
      .catch(() => setError('Could not load the library.'))
  useEffect(() => { load() }, [])

  const visible = (images || []).filter((img) => filter === 'unused' ? img.count === 0 : true)
  const unusedVisible = visible.filter((img) => img.count === 0)
  const allUnusedSelected = unusedVisible.length > 0 && unusedVisible.every((img) => selected.has(img.url))

  const toggleOne = (url) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(url)) next.delete(url)
      else next.add(url)
      return next
    })
  }
  const toggleAllUnused = () => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (allUnusedSelected) {
        for (const img of unusedVisible) next.delete(img.url)
      } else {
        for (const img of unusedVisible) next.add(img.url)
      }
      return next
    })
  }

  const deleteUrls = async (urls) => {
    if (!urls.length) return
    setError('')
    setBusy(true)
    setImages((list) => (list || []).filter((i) => !urls.includes(i.url)))
    setSelected((prev) => {
      const next = new Set(prev)
      for (const u of urls) next.delete(u)
      return next
    })
    const failed = []
    for (const url of urls) {
      try {
        const r = await fetch(base + '/api/library/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        })
        if (!r.ok) {
          const d = await r.json().catch(() => ({}))
          failed.push(`${url.split('/').pop()}${d.detail ? ': ' + d.detail : ''}`)
        }
      } catch (e) {
        failed.push(`${url.split('/').pop()}: ${e.message || 'network error'}`)
      }
    }
    setBusy(false)
    if (failed.length) setError(`Could not delete ${failed.length}: ${failed.slice(0, 3).join('; ')}${failed.length > 3 ? '…' : ''}`)
    load()
  }

  const remove = async (url) => {
    if (!window.confirm('Delete this unused ' + noun + '?')) return
    await deleteUrls([url])
  }
  const removeSelected = async () => {
    const urls = [...selected]
    if (!urls.length) return
    if (!window.confirm(`Delete ${urls.length} unused ${urls.length === 1 ? noun : noun + 's'}?`)) return
    await deleteUrls(urls)
  }

  const replace = async (oldUrl, file) => {
    if (!file) return
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const up = await fetch(base + '/api/upload', { method: 'POST', body: form }).then((r) => r.json())
      if (!up.url) throw new Error('upload failed')
      await fetch(base + '/api/library/replace', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ old: oldUrl, new: up.url }) })
    } catch (e) {
      setError('Could not replace that ' + noun + '.')
    }
    setReplaceFor(null)
    load()
  }
  const startReplace = (url) => { setReplaceFor(url); inputRef.current?.click() }
  const usedText = (img) => (img.count === 0 ? 'Not used' : `Used by ${img.count} ${img.count === 1 ? 'place' : 'places'}`)

  const seg = (id, label, active, onClick) => (
    <button
      key={id}
      onClick={onClick}
      className={`px-3 py-1 text-sm rounded-md ${active ? 'bg-white dark:bg-slate-700 shadow-sm font-medium' : 'text-slate-500'}`}
    >{label}</button>
  )

  return (
    <div className="space-y-3">
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f && replaceFor) replace(replaceFor, f); e.target.value = '' }} />

      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="inline-flex p-0.5 rounded-lg bg-slate-100 dark:bg-slate-800">
          {seg('all', 'All', filter === 'all', () => setFilter('all'))}
          {seg('unused', 'Not used', filter === 'unused', () => setFilter('unused'))}
        </div>
        <div className="inline-flex p-0.5 rounded-lg bg-slate-100 dark:bg-slate-800">
          {seg('thumbs', 'Thumbnails', view === 'thumbs', () => changeView('thumbs'))}
          {seg('details', 'Details', view === 'details', () => changeView('details'))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className={`inline-flex items-center gap-2 ${unusedVisible.length ? '' : 'text-slate-400'}`}>
          <input
            type="checkbox"
            checked={allUnusedSelected}
            disabled={!unusedVisible.length || busy}
            onChange={toggleAllUnused}
          />
          Select all unused{unusedVisible.length ? ` (${unusedVisible.length})` : ''}
        </label>
        <span className="text-slate-500">
          {images ? `${visible.length} shown` : ''}
          {selected.size > 0 ? ` · ${selected.size} selected` : ''}
        </span>
        <Button
          variant="secondary"
          disabled={!selected.size || busy}
          onClick={removeSelected}
        >
          Delete selected{selected.size ? ` (${selected.size})` : ''}
        </Button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {images === null && <p className="text-slate-500">Loading…</p>}

      {images && view === 'thumbs' && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {visible.map((img) => {
            const unused = img.count === 0
            const isSel = selected.has(img.url)
            return (
              <div
                key={img.url}
                className={`bg-white dark:bg-slate-900 border rounded-xl p-2 flex flex-col gap-2 ${isSel ? 'border-brand-500 ring-1 ring-brand-500' : ''}`}
              >
                <div className="relative">
                  {unused && (
                    <label className="absolute top-1.5 left-1.5 z-10 bg-white/90 dark:bg-slate-900/90 rounded p-0.5 shadow-sm">
                      <input type="checkbox" checked={isSel} disabled={busy} onChange={() => toggleOne(img.url)} />
                    </label>
                  )}
                  <img
                    src={assetUrl(img.url)}
                    alt={img.name}
                    title={img.name}
                    className={`w-full aspect-square rounded-lg bg-slate-100 dark:bg-slate-800 ${kind === 'icon' ? 'object-contain p-3' : 'object-cover'}`}
                  />
                </div>
                <div className="text-xs text-slate-500 truncate" title={img.used_by?.join(', ')}>{usedText(img)}</div>
                <div className="flex gap-1 mt-auto">
                  <button onClick={() => startReplace(img.url)} className="flex-1 text-xs px-2 py-1 border rounded-lg" disabled={busy}>Replace</button>
                  {unused && <button onClick={() => remove(img.url)} className="flex-1 text-xs px-2 py-1 border rounded-lg text-red-500" disabled={busy}>Delete</button>}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {images && view === 'details' && (
        <div className="space-y-2">
          {visible.map((img) => {
            const unused = img.count === 0
            const isSel = selected.has(img.url)
            return (
              <div
                key={img.url}
                className={`flex items-center gap-3 bg-white dark:bg-slate-900 border rounded-xl p-2 ${isSel ? 'border-brand-500 ring-1 ring-brand-500' : ''}`}
              >
                {unused ? (
                  <input type="checkbox" checked={isSel} disabled={busy} onChange={() => toggleOne(img.url)} />
                ) : (
                  <span className="w-4" />
                )}
                <img src={assetUrl(img.url)} alt="" className={`w-12 h-12 rounded-lg bg-slate-100 dark:bg-slate-800 ${kind === 'icon' ? 'object-contain p-1' : 'object-cover'}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{img.name}</div>
                  <div className="text-xs text-slate-500">{usedText(img)}</div>
                  {img.used_by?.length > 0 && (
                    <div className="text-xs text-slate-400 truncate" title={img.used_by.join(', ')}>
                      {img.used_by.map((u) => u.replace(/^[a-z]+:/, '')).join(', ')}
                    </div>
                  )}
                </div>
                <Button variant="secondary" onClick={() => startReplace(img.url)} disabled={busy}>Replace</Button>
                {unused && <Button variant="secondary" onClick={() => remove(img.url)} disabled={busy}>Delete</Button>}
              </div>
            )
          })}
        </div>
      )}

      {images && visible.length === 0 && (
        <p className="text-slate-500">
          {filter === 'unused' ? `No unused ${noun}s.` : `No ${noun}s yet.`}
        </p>
      )}
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
    <div className="space-y-4">
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

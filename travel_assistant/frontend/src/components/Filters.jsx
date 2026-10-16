import { useState } from 'react'
import Input from './Input'
import Button from './Button'
import BottomSheet from './BottomSheet'

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'places', label: 'Places to visit' },
  { value: 'accommodation', label: 'Accommodation' },
  { value: 'superchargers', label: 'Superchargers' },
]

export default function Filters({ value, onChange, resultCount, fields = ['search'] }) {
  const [sheetOpen, setSheetOpen] = useState(false)
  const activeCount = Object.values(value).filter(Boolean).length

  const update = (key, val) => onChange({ ...value, [key]: val })

  const clear = () => onChange({
    search: '', type: '', theme: '', region: '', county: '',
  })

  const filterFields = (
    <div className="space-y-3">
      {fields.includes('search') && (
        <Input
          placeholder="Search..."
          value={value.search || ''}
          onChange={(e) => update('search', e.target.value)}
        />
      )}
      {fields.includes('type') && (
        <select
          className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800"
          value={value.type || ''}
          onChange={(e) => update('type', e.target.value)}
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      )}
      {fields.includes('theme') && (
        <select className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" value={value.theme || ''} onChange={(e) => update('theme', e.target.value)}>
          <option value="">All categories</option>
        </select>
      )}
      {fields.includes('region') && (
        <select className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" value={value.region || ''} onChange={(e) => update('region', e.target.value)}>
          <option value="">All regions</option>
        </select>
      )}
      {fields.includes('county') && (
        <select className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800" value={value.county || ''} onChange={(e) => update('county', e.target.value)}>
          <option value="">All counties</option>
        </select>
      )}
    </div>
  )

  return (
    <>
      {/* Desktop bar */}
      <div className="hidden md:flex items-end gap-3 flex-wrap">
        <div className="flex-1 min-w-[180px]">{filterFields}</div>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span>{resultCount} shown</span>
          {activeCount > 0 && <Button variant="ghost" onClick={clear}>Clear</Button>}
        </div>
      </div>

      {/* Mobile button */}
      <div className="md:hidden">
        <Button variant="secondary" onClick={() => setSheetOpen(true)} className="w-full">
          Filters{activeCount > 0 ? ` (${activeCount})` : ''}
        </Button>
        <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Filters">
          {filterFields}
          <div className="flex gap-2 mt-4">
            <Button variant="secondary" onClick={clear} className="flex-1">Clear</Button>
            <Button onClick={() => setSheetOpen(false)} className="flex-1">Apply</Button>
          </div>
          <p className="text-xs text-slate-500 mt-2">{resultCount} shown</p>
        </BottomSheet>
      </div>
    </>
  )
}

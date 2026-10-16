import { useState } from 'react'
import Input from './Input'
import Button from './Button'
import BottomSheet from './BottomSheet'

function Select({ value, onChange, options }) {
  return (
    <select
      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

export default function Filters({ value, onChange, resultCount, fields = ['search'], options = {} }) {
  const [sheetOpen, setSheetOpen] = useState(false)
  const activeCount = Object.values(value).filter(Boolean).length

  const update = (key, val) => onChange({ ...value, [key]: val })
  const clear = () => onChange({ search: '', type: '', theme: '', region: '', county: '' })

  const filterFields = (
    <div className="space-y-3">
      {fields.includes('search') && (
        <Input
          placeholder="Search places..."
          value={value.search || ''}
          onChange={(e) => update('search', e.target.value)}
        />
      )}
      {fields.includes('type') && options.type && (
        <Select value={value.type} onChange={(v) => update('type', v)} options={options.type} />
      )}
      {fields.includes('theme') && options.theme && (
        <Select value={value.theme} onChange={(v) => update('theme', v)} options={options.theme} />
      )}
      {fields.includes('region') && options.region && (
        <Select value={value.region} onChange={(v) => update('region', v)} options={options.region} />
      )}
      {fields.includes('county') && options.county && (
        <Select value={value.county} onChange={(v) => update('county', v)} options={options.county} />
      )}
    </div>
  )

  return (
    <>
      <div className="hidden md:block">
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 grid grid-cols-2 lg:grid-cols-5 gap-2 min-w-0">{filterFields}</div>
          <div className="flex items-center gap-2 text-sm text-slate-500 whitespace-nowrap">
            <span>{resultCount} shown</span>
            {activeCount > 0 && <Button variant="ghost" onClick={clear}>Clear</Button>}
          </div>
        </div>
      </div>

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

import { useState, useEffect } from 'react'
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
  const [compact, setCompact] = useState(false)
  useEffect(() => {
    const check = () => {
      const tesla = /tesla/i.test(navigator.userAgent)
      setCompact(tesla || window.innerWidth < 1024)
    }
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])
  const activeCount = Object.entries(value).filter(([k, v]) => k !== 'hideVisited' && v).length

  const update = (key, val) => onChange({ ...value, [key]: val })
  const clear = () => onChange({ search: '', type: '', theme: '', region: '', county: '', hideVisited: true })

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
      <label className="flex items-center justify-between text-sm text-slate-600 dark:text-slate-300">
        <span>Hide visited</span>
        <button type="button" onClick={() => update('hideVisited', !value.hideVisited)} className="flex items-center" aria-label="Hide visited places">
          <span className={`relative w-10 h-6 rounded-full transition-colors ${value.hideVisited ? 'bg-brand-600' : 'bg-slate-300'}`}>
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${value.hideVisited ? 'translate-x-4' : ''}`} />
          </span>
        </button>
      </label>
    </div>
  )

  return (
    <>
      <div className={compact ? "hidden" : "block"}>
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 grid grid-cols-2 lg:grid-cols-5 gap-2 min-w-0">{filterFields}</div>
          <div className="flex items-center gap-2 text-sm text-slate-500 whitespace-nowrap">
            <span>{resultCount} shown</span>
            {activeCount > 0 && <Button variant="ghost" onClick={clear}>Clear</Button>}
          </div>
        </div>
      </div>

      <div className={compact ? "flex justify-end" : "hidden"}>
        <button
          onClick={() => setSheetOpen(true)}
          className="relative p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200"
          aria-label="Filters"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          {activeCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-brand-600 text-white text-[10px] flex items-center justify-center">{activeCount}</span>
          )}
        </button>
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

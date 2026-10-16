import { useState } from 'react'
import Filters from './components/Filters'
import Button from './components/Button'

export default function App() {
  const [filters, setFilters] = useState({
    search: '',
    type: '',
    theme: '',
    region: '',
    county: '',
  })

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-4 py-3">
        <h1 className="text-lg font-semibold">Travel Assistant</h1>
      </header>
      <main className="p-4 max-w-4xl mx-auto">
        <h2 className="text-xl font-semibold mb-4">Places (React preview)</h2>
        <Filters
          value={filters}
          onChange={setFilters}
          resultCount={42}
          fields={['search', 'type', 'theme', 'region', 'county']}
        />
        <div className="mt-6">
          <Button>Example button</Button>
        </div>
        <p className="mt-4 text-sm text-slate-500">
          Shared Filters component. On mobile it opens a bottom sheet.
        </p>
      </main>
    </div>
  )
}

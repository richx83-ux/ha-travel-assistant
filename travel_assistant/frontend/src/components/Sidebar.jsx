import { useState } from 'react'

export default function Sidebar({ base = '', page = 'places', onNavigate }) {
  const [open, setOpen] = useState(false)

  const links = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'places', label: 'Places' },
    { id: 'trips', label: 'Trips' },
    { href: base + '/themes', label: 'Categories', todo: true },
    { href: base + '/packing', label: 'Store cupboard', todo: true },
    { href: base + '/achievements', label: 'Achievements', todo: true },
  ]

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="p-2 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
        aria-label="Open menu"
      >
        {/* Compass / map-style icon, not a burger */}
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" strokeWidth="1.5" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z" />
        </svg>
      </button>

      {open && (
        <div className="fixed inset-0 z-[2000] flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="relative w-64 max-w-[80vw] bg-slate-900 text-slate-100 h-full shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-4 border-b border-slate-800">
              <span className="font-semibold">Travel Assistant</span>
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white text-xl">&times;</button>
            </div>
            <nav className="flex-1 py-2">
              {links.map((l) => l.id ? (
                <button
                  key={l.id}
                  onClick={() => { onNavigate && onNavigate(l.id); setOpen(false) }}
                  className={`block w-full text-left px-4 py-3 text-sm ${page === l.id ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                >
                  {l.label}
                </button>
              ) : (
                <a
                  key={l.href}
                  href={l.href}
                  className="block px-4 py-3 text-sm text-slate-300 hover:bg-slate-800"
                >
                  {l.label}{l.todo ? ' *' : ''}
                </a>
              ))}
            </nav>
          </div>
        </div>
      )}
    </>
  )
}

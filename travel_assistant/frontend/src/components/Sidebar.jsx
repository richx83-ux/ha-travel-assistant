import { useState } from 'react'

export default function Sidebar({ base = '', page = 'places', onNavigate }) {
  const [open, setOpen] = useState(false)

  const links = [
    { id: 'dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
    { id: 'places', label: 'Places', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z' },
    { id: 'trips', label: 'Trips', icon: 'M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7' },
    { id: 'categories', label: 'Categories', icon: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z' },
    { id: 'cupboard', label: 'Store cupboard', icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' },
    { href: base + '/achievements', label: 'Achievements', icon: 'M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z', todo: true },
  ]

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="p-2 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
        aria-label="Open menu"
      >
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
                  className={`flex items-center gap-3 w-full text-left px-4 py-3 text-sm ${page === l.id ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                >
                  <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d={l.icon} />
                  </svg>
                  {l.label}
                </button>
              ) : (
                <a
                  key={l.href}
                  href={l.href}
                  className="flex items-center gap-3 px-4 py-3 text-sm text-slate-300 hover:bg-slate-800"
                >
                  <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d={l.icon} />
                  </svg>
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

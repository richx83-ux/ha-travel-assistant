import { useState, useEffect } from 'react'

function assetUrl(url, base = '') {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const b = base || (typeof window !== 'undefined' ? window.location.pathname.replace(/\/react.*$/, '') : '') || ''
  return b + (url.startsWith('/') ? url : '/' + url)
}

export default function Dashboard({ base = '', onOpenTrips, onViewPlace }) {
  const [recentVisits, setRecentVisits] = useState([])

  useEffect(() => {
    fetch(base + '/api/places').then((r) => r.json()).then((d) => {
      const places = d.places || []
      const visited = places
        .filter((p) => p.visited && p.visit_date)
        .sort((a, b) => String(b.visit_date).localeCompare(String(a.visit_date)))
        .slice(0, 8)
      setRecentVisits(visited)
    }).catch(() => {})
  }, [base])

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <button
        type="button"
        onClick={() => onOpenTrips && onOpenTrips()}
        className="w-full flex items-center gap-4 p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:shadow-sm text-left"
      >
        <div className="w-12 h-12 rounded-lg bg-brand-600 text-white flex items-center justify-center text-xl">✈</div>
        <div>
          <div className="font-semibold">Trips</div>
          <div className="text-sm text-slate-500">Open trips</div>
        </div>
      </button>

      <div className="border-t border-slate-200 dark:border-slate-800 pt-3 space-y-2">
        <div className="text-xs text-slate-500">Recent visits</div>
        {recentVisits.length === 0 && <p className="text-sm text-slate-500">No visits yet.</p>}
        {recentVisits.map((v) => (
          <button
            key={v.id}
            type="button"
            onClick={() => onViewPlace && onViewPlace(v)}
            className="w-full flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 text-left"
          >
            {v.visit_photo_url ? (
              <img src={assetUrl(v.visit_photo_url, base)} alt="" className="w-14 h-14 rounded-lg object-cover flex-shrink-0" />
            ) : v.image_url ? (
              <img src={assetUrl(v.image_url, base)} alt="" className="w-14 h-14 rounded-lg object-cover flex-shrink-0 opacity-70" />
            ) : (
              <div className="w-14 h-14 rounded-lg bg-slate-100 dark:bg-slate-700 flex-shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <div className="font-medium truncate flex items-center gap-2">
                {v.name}
                {!v.visit_photo_url && (
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">No visit photo</span>
                )}
              </div>
              <div className="text-sm text-slate-500 truncate">{v.city}{v.county ? ', ' + v.county : ''}</div>
            </div>
            {v.visit_date && <div className="text-xs text-slate-400">{v.visit_date}</div>}
          </button>
        ))}
      </div>
    </div>
  )
}

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function TripCard({ trip }) {
  const dates = [trip.start_date, trip.end_date].filter(Boolean).join(' → ')
  return (
    <a
      href={(window.location.pathname.replace(/\/react.*$/, '') || '') + '/trip/' + trip.id}
      className="flex items-center gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:shadow-sm"
    >
      <div className="w-12 h-12 rounded-lg bg-brand-100 dark:bg-brand-900/40 flex items-center justify-center overflow-hidden flex-shrink-0">
        {trip.image_url ? (
          <img src={assetUrl(trip.image_url)} alt="" className="w-full h-full object-cover" />
        ) : (
          <span className="text-brand-700 text-sm font-medium">{(trip.name || '?')[0]}</span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-slate-900 dark:text-slate-100 truncate">{trip.name}</div>
        {dates && <div className="text-sm text-slate-500">{dates}</div>}
        <div className="text-xs text-slate-400">{trip.stop_count || 0} stops</div>
      </div>
    </a>
  )
}

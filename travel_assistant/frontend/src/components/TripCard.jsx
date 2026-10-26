function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function TripCard({ trip, onView, onEdit, onStart, onDelete }) {
  const dates = [trip.start_date, trip.end_date].filter(Boolean).join(' → ')
  const miles = Number(trip.total_miles || 0).toFixed(1)
  const travel = (Number(trip.total_drive_secs || 0) / 3600).toFixed(1)
  const visit = (Number(trip.total_visit_mins || 0) / 60).toFixed(1)
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden flex flex-col">
      <div className="h-48 bg-slate-100 dark:bg-slate-800">
        {trip.image_url ? (
          <img src={assetUrl(trip.image_url)} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400 text-2xl">{(trip.name || '?')[0]}</div>
        )}
      </div>
      <div className="p-3 flex-1">
        <div className="flex items-center gap-2">
          <div className="font-semibold text-lg truncate">{trip.name}</div>
          {trip.status === 'completed' && <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700">Completed</span>}
        </div>
        {dates && <div className="text-sm text-slate-500">{dates} · {trip.n_days || trip.total_days || 1} days</div>}
        <div className="text-xs text-slate-500 mt-1">{miles} mi · {travel} hrs travel · {visit} hrs visiting</div>
      </div>
      <div className="p-3 pt-0 flex gap-2 flex-wrap">
        <button className="px-3 py-1.5 rounded-lg bg-brand-600 text-white text-sm" onClick={onView}>View</button>
        <button className="px-3 py-1.5 rounded-lg border text-sm" onClick={onEdit}>Edit</button>
        {trip.status !== 'completed' && <button className="px-3 py-1.5 rounded-lg border text-sm" onClick={onStart}>Start</button>}
        <button className="px-3 py-1.5 rounded-lg text-sm text-red-500" onClick={onDelete}>Delete</button>
      </div>
    </div>
  )
}

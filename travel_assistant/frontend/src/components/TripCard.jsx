function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

function fmtDrive(secs) {
  const m = Math.round((secs || 0) / 60)
  if (m < 60) return m + 'm'
  const h = Math.floor(m / 60)
  const rem = m % 60
  return rem ? h + 'h ' + rem + 'm' : h + 'h'
}
export default function TripCard({ trip, onClick }) {
  const dates = [trip.start_date, trip.end_date].filter(Boolean).join(' → ')
  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:shadow-sm cursor-pointer"
    >
      <div className="w-12 h-12 rounded-lg bg-brand-100 dark:bg-brand-900/40 flex items-center justify-center overflow-hidden flex-shrink-0">
        {trip.image_url ? (
          <img src={assetUrl(trip.image_url)} alt="" className="w-full h-full object-cover" />
        ) : (
          <span className="text-brand-700 text-sm font-medium">{(trip.name || '?')[0]}</span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <div className="font-medium text-slate-900 dark:text-slate-100 truncate">{trip.name}</div>
          {trip.status === 'completed' && <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300">Completed</span>}
        </div>
        {dates && <div className="text-sm text-slate-500">{dates}</div>}
        {trip.status === 'completed' ? (
          <div className="text-xs text-slate-500 mt-0.5">
            {trip.completed_count || 0} completed · {trip.skipped_count || 0} skipped · {fmtDrive(trip.total_drive_secs)} drive · {trip.total_miles || 0} mi
          </div>
        ) : (
          <div className="text-xs text-slate-400">{trip.stop_count || 0} stops</div>
        )}
      </div>
    </div>
  )
}

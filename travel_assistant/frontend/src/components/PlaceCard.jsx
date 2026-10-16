import Badge from './Badge'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function PlaceCard({ place }) {
  const location = [place.city, place.county].filter(Boolean).join(', ') || place.region || ''
  const photo = assetUrl(place.visit_photo_url)
  return (
    <div className="flex items-center gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:shadow-sm transition-shadow">
      <div
        className="w-12 h-12 rounded-lg flex-shrink-0 flex items-center justify-center text-white text-sm font-medium overflow-hidden"
        style={{ backgroundColor: place.primary_color || '#0d9488' }}
      >
        {photo ? (
          <img src={photo} alt="" className="w-full h-full object-cover" />
        ) : (
          (place.name || '?')[0]
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-slate-900 dark:text-slate-100 truncate">{place.name}</div>
        {location && <div className="text-sm text-slate-500 truncate">{location}</div>}
        <div className="text-xs text-slate-400 truncate">{place.theme_name}</div>
      </div>
      <Badge color={place.visited ? 'green' : 'gray'}>
        {place.visited ? 'Visited' : 'Not visited'}
      </Badge>
    </div>
  )
}

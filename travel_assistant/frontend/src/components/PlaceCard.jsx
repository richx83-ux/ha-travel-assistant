import Badge from './Badge'

function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function PlaceCard({ place, onClick }) {
  const location = [place.city, place.county].filter(Boolean).join(', ') || place.region || ''
  // Prefer place/website image, then theme default, then visit photo
  const raw = place.image_url || place.default_image_url || place.visit_photo_url || place.icon_url
  const photo = assetUrl(raw)
  const icon = assetUrl(place.icon_url)
  return (
    <div onClick={onClick} className="flex items-center gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:shadow-sm transition-shadow cursor-pointer">
      <div className="relative flex-shrink-0">
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center text-white text-sm font-medium overflow-hidden"
          style={{ backgroundColor: place.primary_color || '#0d9488' }}
        >
          {photo ? (
            <img src={photo} alt="" className="w-full h-full object-cover" />
          ) : (
            (place.name || '?')[0]
          )}
        </div>
        {icon && (
          <img
            src={icon}
            alt=""
            className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-white dark:border-slate-900 bg-white object-contain"
          />
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

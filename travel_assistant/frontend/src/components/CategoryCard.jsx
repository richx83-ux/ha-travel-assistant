function assetUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const base = window.location.pathname.replace(/\/react.*$/, '') || ''
  return base + (url.startsWith('/') ? url : '/' + url)
}

export default function CategoryCard({ category, onClick, onViewPlaces }) {
  const photo = assetUrl(category.default_image_url)
  const icon = assetUrl(category.icon_url)
  const showVisits = !category.hide_visit_status && category.total > 0

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
      <div onClick={onClick} className="cursor-pointer">
        <div className="relative h-28 bg-slate-100 dark:bg-slate-800">
          {photo ? (
            <img src={photo} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full" style={{ background: category.primary_color || '#0d9488' }} />
          )}
          {icon && (
            <img src={icon} alt="" className="absolute bottom-2 left-2 w-8 h-8 rounded-lg bg-white/90 p-0.5 object-contain" />
          )}
        </div>
        <div className="p-3">
          <div className="font-medium text-slate-900 dark:text-slate-100 truncate">{category.name}</div>
          <div className="text-xs text-slate-500 mt-0.5">
            {category.total || 0} places
            {showVisits && <> · {category.visited || 0} visited · {category.percentage || 0}%</>}
          </div>
        </div>
      </div>
      <div className="px-3 pb-3">
        <button
          onClick={(e) => { e.stopPropagation(); onViewPlaces && onViewPlaces(category) }}
          className="text-sm text-brand-600 dark:text-brand-400 font-medium"
        >
          View places
        </button>
      </div>
    </div>
  )
}

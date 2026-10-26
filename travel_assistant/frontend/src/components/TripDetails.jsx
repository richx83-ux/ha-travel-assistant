export default function TripDetails({ details, first }) {
  if (!details) return null
  if (first || details.mode === 'ship') {
    return (
      <div className="px-3 py-2 text-xs text-slate-500 border-t border-slate-200 dark:border-slate-700">
        {details.mode === 'ship' ? <div>Overnight on ship</div> : null}
        <div>Depart {details.depart}</div>
      </div>
    )
  }
  const label = details.mode === 'walk' ? 'Walk' : 'Drive'
  return (
    <div className="px-3 py-2 text-xs text-slate-500 border-t border-slate-200 dark:border-slate-700 grid grid-cols-2 gap-x-3 gap-y-0.5">
      <span>{label} {details.travelHrs} hrs</span>
      {details.mode === 'walk' ? <span>{details.miles} miles</span> : <span>{details.miles} miles</span>}
      <span>Arrive {details.arrive}</span>
      <span>Stay {details.duration} min</span>
      <span>Depart {details.depart}</span>
    </div>
  )
}

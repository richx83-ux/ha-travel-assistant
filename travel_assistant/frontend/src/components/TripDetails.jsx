export default function TripDetails({ details, first }) {
  if (!details) return null
  return (
    <div className="px-3 py-2 text-xs text-slate-500 border-t border-slate-200 dark:border-slate-700 grid grid-cols-2 gap-x-3 gap-y-0.5">
      {first ? (
        <span className="col-span-2">Depart {details.depart}</span>
      ) : (
        <>
          <span>Travel {details.travelHrs} hrs</span>
          <span>{details.miles} miles</span>
          <span>Arrive {details.arrive}</span>
          <span>Stay {details.duration} min</span>
          <span>Depart {details.depart}</span>
        </>
      )}
    </div>
  )
}

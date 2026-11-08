const DB_NAME = 'ta-offline'
const DB_VERSION = 1
const STORE = 'trips'

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'id' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function listTrips() {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).getAll()
    req.onsuccess = () => resolve(req.result || [])
    req.onerror = () => reject(req.error)
  })
}

export async function getTrip(id) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).get(Number(id))
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

export async function putTrip(trip) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).put(trip)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function deleteTrip(id) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).delete(Number(id))
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function saveTripForOffline(tripId, base) {
  const res = await fetch(base + '/api/trips/' + tripId)
  if (!res.ok) throw new Error('Could not load trip')
  const detail = await res.json()
  const trip = detail.trip || {}
  const days = detail.days || []
  const stops = []
  days.forEach((d) => {
    ;(d.stops || []).forEach((s) => {
      stops.push({
        id: s.id,
        location_id: s.location_id,
        name: s.name || s.location_name || 'Stop',
        day_number: d.day_number || s.day_number || 1,
        lat: s.latitude,
        lon: s.longitude,
        city: s.city || '',
        postcode: s.postcode || '',
        is_accommodation: !!(s.is_accommodation || s.is_hotel),
        done: !!s.completed_at,
        doneAt: s.completed_at || null,
        photo: null,
        synced: true,
      })
    })
  })
  const pack = {
    id: Number(trip.id || tripId),
    name: trip.name || 'Trip',
    start_date: trip.start_date || '',
    end_date: trip.end_date || '',
    stops,
    savedAt: Date.now(),
  }
  await putTrip(pack)
  return pack
}

function isAuthFail(res) {
  return !res || res.status === 401 || res.status === 403 || res.type === 'opaqueredirect' || (res.status >= 300 && res.status < 400)
}

export async function pendingCount() {
  const trips = await listTrips()
  return trips.reduce((n, t) => n + (t.stops || []).filter((s) => s.done && s.synced === false).length, 0)
}

export async function syncOfflineTrips(base) {
  const trips = await listTrips()
  let ok = 0
  let fail = 0
  let unauth = false
  let detail = ''
  for (const trip of trips) {
    const pending = (trip.stops || []).filter((s) => s.done && s.synced === false)
    if (!pending.length) continue
    try { await fetch(base + '/api/trips/' + trip.id + '/start', { method: 'POST', credentials: 'include', redirect: 'manual' }) } catch (e) {}
    const stops = []
    for (const s of trip.stops) {
      if (!(s.done && s.synced === false)) { stops.push(s); continue }
      try {
        if (s.photo) {
          const fd = new FormData()
          fd.append('file', new File([s.photo], 'visit.jpg', { type: s.photo.type || 'image/jpeg' }))
          const pr = await fetch(base + '/api/trips/' + trip.id + '/stop/' + s.id + '/photo', { method: 'POST', body: fd, credentials: 'include', redirect: 'manual' })
          if (isAuthFail(pr)) { unauth = true; throw new Error('auth') }
          if (!pr.ok) { detail = 'photo ' + pr.status; throw new Error('photo') }
        }
        const ar = await fetch(base + '/api/trips/' + trip.id + '/stop/' + s.id + '/arrive', { method: 'POST', credentials: 'include', redirect: 'manual' })
        if (isAuthFail(ar)) { unauth = true; throw new Error('auth') }
        const lr = await fetch(base + '/api/trips/' + trip.id + '/stop/' + s.id + '/leave', { method: 'POST', credentials: 'include', redirect: 'manual' })
        if (isAuthFail(lr)) { unauth = true; throw new Error('auth') }
        if (!lr || !lr.ok) { detail = 'leave ' + (lr ? lr.status : 'none'); throw new Error('leave') }
        stops.push({ ...s, synced: true })
        ok++
      } catch (e) {
        stops.push(s)
        fail++
        if (unauth) break
      }
    }
    await putTrip({ ...trip, stops })
    if (unauth) break
  }
  return { ok, fail, unauth, detail }
}

"""Trip planner and quick-visit routes for Travel Assistant."""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse

app = None
templates = None
get_db = None
get_base = None
redirect = None
save_upload = None
_http_get_json = None


LOCAL_TZ = ZoneInfo("Europe/London")


def _now():
    return datetime.now(LOCAL_TZ)


def format_duration(secs: Optional[int]) -> str:
    if secs is None:
        return "—"
    mins = int(round(secs / 60))
    if mins <= 0:
        return "0 min"
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _hours_conflict(stop, arrive_hhmm: Optional[str]):
    text = (stop or {}).get("opening_hours") or ""
    match = re.search(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})", text)
    if not match or not arrive_hhmm or ":" not in arrive_hhmm:
        return None
    open_m = int(match.group(1)) * 60 + int(match.group(2))
    close_m = int(match.group(3)) * 60 + int(match.group(4))
    hour, minute = [int(p) for p in arrive_hhmm.split(":", 1)]
    arrive = hour * 60 + minute
    if arrive < open_m:
        return f"Arrives {arrive_hhmm}, opens {_hhmm(open_m)}"
    if arrive >= close_m:
        return f"Arrives {arrive_hhmm}, closes {_hhmm(close_m)}"
    leave = arrive + _visit_mins(stop)
    if leave > close_m:
        return f"Visit runs to {_hhmm(leave)}, closes {_hhmm(close_m)}"
    return None


def _hhmm(mins: int) -> str:
    mins = int(round(mins)) % (24 * 60)
    h, m = divmod(mins, 60)
    return f"{h:02d}:{m:02d}"


def format_distance(meters: Optional[int]) -> str:
    if meters is None:
        return ""
    if meters < 1000:
        return f"{meters} m"
    return f"{meters / 1000:.1f} km"


def format_miles(meters: Optional[int]) -> str:
    if not meters:
        return ""
    miles = meters / 1609.344
    return f"{miles:.1f} mi" if miles >= 0.1 else f"{int(round(meters))} m"


async def osrm_leg_times(coords: list) -> list:
    if len(coords) < 2:
        return []
    parts = ";".join(f"{lng},{lat}" for lat, lng in coords)
    url = (
        f"https://router.project-osrm.org/route/v1/driving/{parts}"
        f"?overview=false&annotations=false"
    )
    result = await asyncio.to_thread(_http_get_json, url, 20.0)
    if not result or result.get("code") != "Ok":
        return [{"duration_secs": None, "distance_m": None} for _ in range(len(coords) - 1)]
    routes = result.get("routes") or []
    if not routes:
        return [{"duration_secs": None, "distance_m": None} for _ in range(len(coords) - 1)]
    legs = routes[0].get("legs") or []
    out = []
    for leg in legs:
        out.append({
            "duration_secs": int(round(leg.get("duration") or 0)),
            "distance_m": int(round(leg.get("distance") or 0)),
        })
    while len(out) < len(coords) - 1:
        out.append({"duration_secs": None, "distance_m": None})
    return out


async def get_trip(trip_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


def _visit_mins(stop) -> int:
    if not stop:
        return 0
    name = (stop.get("theme_name") or "").strip().lower()
    if name in ("hotel", "hotels"):
        return 0
    if "supercharger" in name or "tesla" in name:
        return 25
    stored = stop.get("visit_duration_mins")
    return stored if stored is not None else 60


def _is_hotel(stop) -> bool:
    if not stop:
        return False
    if stop.get("is_hotel"):
        return True
    # Prefer category type
    type_name = (stop.get("category_type_name") or "").strip().lower()
    if type_name in ("accommodation", "home location"):
        return True
    # Fallback for older data
    name = (stop.get("theme_name") or "").strip().lower()
    return name in ("hotel", "hotels", "home")


def _is_flexible(stop) -> bool:
    """Hotels and Superchargers may be after the day's finish time."""
    if not stop:
        return False
    if _is_hotel(stop):
        return True
    name = (stop.get("theme_name") or "").strip().lower()
    return "supercharger" in name or "tesla" in name


async def get_trip_stops(trip_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT s.*, l.name as location_name, l.latitude, l.longitude,
                      l.postcode, l.city, l.county, l.url as location_url,
                      l.visited, l.visit_date, l.visit_duration_mins, l.opening_hours, l.theme_id,
                      l.visit_photo_url, l.image_url,
                      t.name as theme_name, t.primary_color, t.icon_url
               FROM trip_stops s
               LEFT JOIN locations l ON l.id = s.location_id
               LEFT JOIN themes t ON t.id = l.theme_id
               WHERE s.trip_id = ?
               ORDER BY s.day_number, s.sort_order, s.id""",
            (trip_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def _recalc_trip_times(trip_id: int):
    stops = await get_trip_stops(trip_id)
    by_day = {}
    for s in stops:
        by_day.setdefault(s["day_number"] or 1, []).append(s)
    async with get_db() as db:
        for day_stops in by_day.values():
            others = [s for s in day_stops if not _is_hotel(s)]
            hotels = [s for s in day_stops if _is_hotel(s)]
            for i, s in enumerate(others + hotels):
                if s.get("sort_order") != i:
                    await db.execute("UPDATE trip_stops SET sort_order = ? WHERE id = ?", (i, s["id"]))
        await db.commit()
    stops = await get_trip_stops(trip_id)
    by_day = {}
    for s in stops:
        by_day.setdefault(s["day_number"] or 1, []).append(s)
    async with get_db() as db:
        for day, day_stops in by_day.items():
            prev_hotel = None
            if day > 1:
                prev = by_day.get(day - 1) or []
                if prev and _is_hotel(prev[-1]):
                    prev_hotel = prev[-1]
            elif day == 1:
                home = await (await db.execute(
                    """SELECT l.name as location_name, l.latitude, l.longitude
                       FROM locations l JOIN themes t ON t.id = l.theme_id
                       WHERE lower(t.name) = 'home' ORDER BY l.id LIMIT 1"""
                )).fetchone()
                if home and home["latitude"] is not None:
                    prev_hotel = dict(home)
            if day_stops and not prev_hotel:
                await db.execute(
                    "UPDATE trip_stops SET travel_from_prev_secs = NULL, distance_from_prev_m = NULL WHERE id = ?",
                    (day_stops[0]["id"],),
                )
            coords = []
            valid_ids = []
            if prev_hotel and prev_hotel.get("latitude") is not None and prev_hotel.get("longitude") is not None:
                coords.append((float(prev_hotel["latitude"]), float(prev_hotel["longitude"])))
                valid_ids.append(None)
            for s in day_stops:
                lat, lng = s.get("latitude"), s.get("longitude")
                if lat is not None and lng is not None:
                    coords.append((float(lat), float(lng)))
                    valid_ids.append(s["id"])
            if len(coords) >= 2:
                legs = await osrm_leg_times(coords)
                for i, leg in enumerate(legs):
                    stop_id = valid_ids[i + 1]
                    if not stop_id:
                        continue
                    await db.execute(
                        """UPDATE trip_stops SET travel_from_prev_secs = ?, distance_from_prev_m = ?
                           WHERE id = ?""",
                        (leg.get("duration_secs"), leg.get("distance_m"), stop_id),
                    )
        await db.commit()


def register_routes(_app, _templates, deps: dict):
    global app, templates, get_db, get_base, redirect, save_upload, _http_get_json
    app = _app
    templates = _templates
    get_db = deps["get_db"]
    get_base = deps["get_base"]
    redirect = deps["redirect"]
    save_upload = deps["save_upload"]
    _http_get_json = deps["_http_get_json"]

    @app.get("/trips", response_class=HTMLResponse)
    async def trips_list(request: Request):
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM trips ORDER BY start_date DESC, name")
            trips = [dict(r) for r in await cursor.fetchall()]
            for t in trips:
                c = await db.execute(
                    "SELECT COUNT(*) as c FROM trip_stops WHERE trip_id = ?", (t["id"],)
                )
                t["stop_count"] = (await c.fetchone())["c"] or 0
        return templates.TemplateResponse("trips.html", {
            "request": request, "base": get_base(request), "active_nav": "trips", "trips": trips,
        })

    @app.get("/trip/new", response_class=HTMLResponse)
    async def trip_new_form(request: Request):
        base = get_base(request)
        return templates.TemplateResponse("trip_form.html", {
            "request": request, "base": base, "active_nav": "trips",
            "trip": None, "action": f"{base}/trip/new",
        })

    @app.post("/trip/new")
    async def trip_create(
        request: Request,
        name: str = Form(...),
        start_date: str = Form(""),
        end_date: str = Form(""),
        notes: str = Form(""),
        image: Optional[UploadFile] = File(None),
    ):
        image_url = ""
        if image and image.filename:
            image_url = await save_upload(image)
        async with get_db() as db:
            cursor = await db.execute(
                """INSERT INTO trips (name, start_date, end_date, notes, image_url)
                   VALUES (?, ?, ?, ?, ?)""",
                (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip(), image_url),
            )
            await db.commit()
            trip_id = cursor.lastrowid
        return redirect(request, f"/trip/{trip_id}")

    @app.get("/trip/{trip_id}", response_class=HTMLResponse)
    async def trip_detail(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        stops = await get_trip_stops(trip_id)
        days = {}
        for s in stops:
            d = s.get("day_number") or 1
            days.setdefault(d, []).append(s)
        day_list = sorted(days.keys())
        # Home location for day 1 start
        async with get_db() as db:
            home = await (await db.execute(
                """SELECT l.id, l.name as location_name, l.latitude, l.longitude, l.city, l.county,
                          l.image_url, l.visit_photo_url, l.image_url, t.name as theme_name, t.primary_color, t.icon_url
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE lower(t.name) = 'home' ORDER BY l.id LIMIT 1"""
            )).fetchone()
            home = dict(home) if home else None
        total_drive = sum((s.get("travel_from_prev_secs") or 0) for s in stops)
        total_visit = sum(_visit_mins(s) for s in stops)
        total_miles = sum((s.get("distance_from_prev_m") or 0) for s in stops) / 1609.344
        FINISH = 17 * 60
        day_summaries = []
        for d in day_list:
            ds = days[d]
            last_real = None
            for s in ds:
                if not _is_flexible(s):
                    last_real = s
            constrained = 0
            if last_real:
                for s in ds:
                    constrained += int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s)
                    if s is last_real:
                        break
            start = max(0, FINISH - constrained) if last_real else 9 * 60
            cursor = start
            for i, s in enumerate(ds):
                drive = int(round((s.get("travel_from_prev_secs") or 0) / 60))
                if i == 0:
                    s["arrive"] = None
                    s["depart"] = _hhmm(cursor)
                    cursor += _visit_mins(s)
                else:
                    cursor += drive
                    s["arrive"] = _hhmm(cursor)
                    cursor += _visit_mins(s)
                    s["depart"] = _hhmm(cursor)
            for s in ds:
                s["hours_warning"] = _hours_conflict(s, s.get("arrive"))
            day_summaries.append({
                "day": d,
                "stops": len(ds),
                "drive": sum((s.get("travel_from_prev_secs") or 0) for s in ds),
                "visit": sum(_visit_mins(s) for s in ds),
                "miles": sum((s.get("distance_from_prev_m") or 0) for s in ds) / 1609.344,
                "start": _hhmm(start),
                "last_name": last_real.get("location_name") if last_real else None,
                "flexible": bool(last_real and ds[-1] is not last_real),
                "full": bool(last_real and start < 8 * 60),
            })
        n_days = len(day_list) or 1
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.id, l.name, l.city, l.county, l.region, l.postcode,
                          l.theme_id, l.visited, l.latitude, l.longitude,
                          t.name as theme_name, t.primary_color, t.icon_url
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE COALESCE(t.exclude_from_places, 0) = 0
                   ORDER BY l.name"""
            )
            places = [dict(r) for r in await cursor.fetchall()]
        total_travel = sum((s.get("travel_from_prev_secs") or 0) for s in stops if s.get("travel_from_prev_secs"))
        return templates.TemplateResponse("trip.html", {
            "request": request, "base": get_base(request), "active_nav": "trips",
            "trip": trip, "stops": stops, "days": days, "day_list": day_list,
            "places": places, "total_travel": total_drive, "total_visit": total_visit,
            "total_miles": total_miles, "day_summaries": day_summaries, "n_days": n_days,
            "format_duration": format_duration, "format_distance": format_distance,
            "visit_mins": _visit_mins,
        })



    @app.post("/api/trips/{trip_id}/save")
    async def api_trip_save(request: Request, trip_id: int):
        """Save a draft trip edit from the React editor."""
        body = await request.json()
        async with get_db() as db:
            await db.execute(
                "UPDATE trips SET name = ?, start_date = ?, end_date = ?, notes = ?, image_url = ?, start_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (body.get("name") or "", body.get("start_date") or "", body.get("end_date") or "", body.get("notes") or "", body.get("image_url") or "", body.get("start_time") or "09:00", trip_id),
            )
            # Keep arrive/leave state so editing doesn't restart the day
            existing = [dict(r) for r in await (await db.execute(
                "SELECT location_id, day_number, arrived_at, completed_at, skipped FROM trip_stops WHERE trip_id = ?",
                (trip_id,),
            )).fetchall()]
            state = {(e["location_id"], e["day_number"]): e for e in existing}
            await db.execute("DELETE FROM trip_stops WHERE trip_id = ?", (trip_id,))
            for i, s in enumerate(body.get("stops") or []):
                key = (s.get("location_id"), s.get("day_number") or 1)
                prev = state.get(key, {})
                await db.execute(
                    """INSERT INTO trip_stops (trip_id, location_id, day_number, sort_order, is_hotel, arrived_at, completed_at, skipped)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (trip_id, s.get("location_id"), s.get("day_number") or 1, i,
                     1 if s.get("is_accommodation") else 0,
                     prev.get("arrived_at"), prev.get("completed_at"), prev.get("skipped") or 0),
                )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return {"ok": True}

    @app.post("/api/trips/{trip_id}/image")
    async def api_trip_image(request: Request, trip_id: int, file: UploadFile = File(...)):
        url = await save_upload(file)
        async with get_db() as db:
            await db.execute("UPDATE trips SET image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (url, trip_id))
            await db.commit()
        return {"ok": True, "url": url}

    @app.get("/api/trips/{trip_id}")
    async def api_trip_detail(request: Request, trip_id: int):
        """Trip with days and stops for the React UI."""
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        stops = await get_trip_stops(trip_id)
        days = {}
        for s in stops:
            d = s.get("day_number") or 1
            days.setdefault(d, []).append(s)
        day_list = sorted(days.keys())
        # Home location for day 1 start
        async with get_db() as db:
            home_row = await (await db.execute(
                """SELECT l.id, l.name as location_name, l.latitude, l.longitude, l.city, l.county,
                          l.image_url, l.visit_photo_url, t.name as theme_name, t.primary_color, t.icon_url
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE lower(t.name) = 'home' ORDER BY l.id LIMIT 1"""
            )).fetchone()
            home = dict(home_row) if home_row else None
        FINISH = 17 * 60
        day_out = []
        for d in day_list:
            ds = days[d]
            last_real = None
            for s in ds:
                if not _is_flexible(s):
                    last_real = s
            constrained = 0
            if last_real:
                for s in ds:
                    constrained += int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s)
                    if s is last_real:
                        break
            start = max(0, FINISH - constrained) if last_real else 9 * 60
            cursor = start
            for i, s in enumerate(ds):
                drive = int(round((s.get("travel_from_prev_secs") or 0) / 60))
                # Planned times: original schedule, never changed by actuals
                cursor += drive
                s["planned_arrive"] = _hhmm(cursor) if drive else None
                s["arrive"] = s["planned_arrive"]
                cursor += _visit_mins(s)
                s["planned_depart"] = _hhmm(cursor)
                s["depart"] = s["planned_depart"]
                s["is_accommodation"] = _is_hotel(s)
                s["miles"] = round((s.get("distance_from_prev_m") or 0) / 1609.344, 1)
                s["drive_mins"] = drive
                s["visit_mins"] = _visit_mins(s)
                # Actual times from arrive / leave
                if s.get("arrived_at"):
                    try:
                        s["actual_arrive"] = datetime.fromisoformat(str(s["arrived_at"]).replace(" ", "T")).strftime("%H:%M")
                    except Exception:
                        s["actual_arrive"] = None
                if s.get("completed_at"):
                    try:
                        s["actual_depart"] = datetime.fromisoformat(str(s["completed_at"]).replace(" ", "T")).strftime("%H:%M")
                    except Exception:
                        s["actual_depart"] = None
            # Project remaining stops from the last actual departure
            last_actual = None
            for s in ds:
                if s.get("actual_depart"):
                    last_actual = s
            if last_actual:
                proj = int(last_actual["actual_depart"].split(":")[0]) * 60 + int(last_actual["actual_depart"].split(":")[1])
                past = True
                for s in ds:
                    if s is last_actual:
                        past = False
                        continue
                    if past:
                        continue
                    drive = int(round((s.get("travel_from_prev_secs") or 0) / 60))
                    proj += drive
                    s["projected_arrive"] = _hhmm(proj)
                    proj += _visit_mins(s)
                    s["projected_depart"] = _hhmm(proj)
            # Prepend start location: home on day 1, previous day's hotel afterwards
            start_stop = None
            if d == day_list[0] and home:
                start_stop = {**home, "is_start": True, "is_accommodation": True, "depart": _hhmm(start), "arrive": None, "drive_mins": 0, "miles": 0, "visit_mins": 0}
            elif d > day_list[0]:
                prev_ds = days.get(d - 1, [])
                prev_hotel = next((s for s in reversed(prev_ds) if _is_hotel(s)), None)
                if prev_hotel:
                    start_stop = {**prev_hotel, "is_start": True, "is_accommodation": True, "depart": _hhmm(start), "arrive": None, "drive_mins": 0, "miles": 0, "visit_mins": 0}
            if start_stop:
                ds = [start_stop] + ds
            used = sum((s.get("travel_from_prev_secs") or 0) for s in ds) / 60 + sum(_visit_mins(s) for s in ds)
            spare = max(0, FINISH - start - used)
            day_out.append({
                "day": d,
                "stops": ds,
                "miles": round(sum((s.get("distance_from_prev_m") or 0) for s in ds) / 1609.344, 1),
                "drive_secs": sum((s.get("travel_from_prev_secs") or 0) for s in ds),
                "visit_mins": sum(_visit_mins(s) for s in ds),
                "start": _hhmm(start),
                "finish": _hhmm(FINISH),
                "spare_mins": int(spare),
            })
        return {"trip": trip, "days": day_out}

    @app.get("/trip/{trip_id}/edit", response_class=HTMLResponse)
    async def trip_edit_form(request: Request, trip_id: int):
        return redirect(request, f"/trip/{trip_id}/wizard?step=setup")
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        base = get_base(request)
        return templates.TemplateResponse("trip_form.html", {
            "request": request, "base": base, "active_nav": "trips",
            "trip": trip, "action": f"{base}/trip/{trip_id}/edit",
        })

    @app.post("/trip/{trip_id}/edit")
    async def trip_update(
        request: Request, trip_id: int,
        name: str = Form(...),
        start_date: str = Form(""),
        end_date: str = Form(""),
        notes: str = Form(""),
        image: Optional[UploadFile] = File(None),
    ):
        image_url = None
        if image and image.filename:
            image_url = await save_upload(image)
        async with get_db() as db:
            if image_url:
                await db.execute(
                    """UPDATE trips SET name = ?, start_date = ?, end_date = ?, notes = ?,
                        image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip(), image_url, trip_id),
                )
            else:
                await db.execute(
                    """UPDATE trips SET name = ?, start_date = ?, end_date = ?, notes = ?,
                        updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip(), trip_id),
                )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}")

    @app.post("/trip/{trip_id}/delete")
    async def trip_delete(request: Request, trip_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM trip_stops WHERE trip_id = ?", (trip_id,))
            await db.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            await db.commit()
        return redirect(request, "/trips")

    def _next_or_trip(request: Request, trip_id: int):
        nxt = (request.query_params.get("next") or "").strip()
        if nxt.startswith(f"/trip/{trip_id}"):
            return redirect(request, nxt)
        return redirect(request, f"/trip/{trip_id}")

    @app.post("/trip/{trip_id}/add-stop")
    async def trip_add_stop(
        request: Request, trip_id: int,
        location_id: int = Form(...),
        day_number: int = Form(1),
    ):
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404)
        day_number = max(1, day_number)
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sort_order), -1) as m FROM trip_stops WHERE trip_id = ? AND day_number = ?",
                (trip_id, day_number),
            )
            next_order = ((await cursor.fetchone())["m"] or -1) + 1
            cursor = await db.execute(
                """SELECT t.name, ct.name as category_type_name
                   FROM locations l
                   JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE l.id = ?""",
                (location_id,),
            )
            theme_row = await cursor.fetchone()
            type_name = ""
            if theme_row:
                # theme_row currently only has name; we'll improve the query next
                type_name = (theme_row.get("category_type_name") or "").strip().lower()
            is_hotel = 1 if type_name in ("accommodation", "home location") or (theme_row and (theme_row["name"] or "").strip().lower() in ("hotel", "hotels", "home")) else 0
            await db.execute(
                """INSERT INTO trip_stops (trip_id, location_id, day_number, sort_order, is_hotel)
                   VALUES (?, ?, ?, ?, ?)""",
                (trip_id, location_id, day_number, next_order, is_hotel),
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/wizard/dates")
    async def wizard_save_dates(
        request: Request, trip_id: int,
        name: str = Form(""),
        start_date: str = Form(""), end_date: str = Form(""),
        notes: str = Form(""), finish: str = Form("17:00"),
        start_time: str = Form("09:00"),
        image: Optional[UploadFile] = File(None),
        action: str = Form(""),
    ):
        image_url = None
        image_error = ""
        if image and image.filename:
            try:
                image_url = await save_upload(image)
            except Exception as e:
                image_error = str(getattr(e, "detail", e))
        start_time = (start_time or "09:00").strip()[:5] or "09:00"
        async with get_db() as db:
            if image_url:
                await db.execute(
                    """UPDATE trips SET name = COALESCE(NULLIF(?, ''), name), start_date = ?, end_date = ?,
                        notes = ?, image_url = ?, start_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip(), image_url, start_time, trip_id),
                )
            else:
                await db.execute(
                    """UPDATE trips SET name = COALESCE(NULLIF(?, ''), name), start_date = ?, end_date = ?,
                        notes = ?, start_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip(), start_time, trip_id),
                )
            await db.commit()
        if action == "upload" or image_error:
            from urllib.parse import quote
            q = "uploaded=1" if image_url else f"image_error={quote(image_error or 'Choose an image first')}"
            return redirect(request, f"/trip/{trip_id}/wizard?step=setup&finish={finish}&{q}")
        return redirect(request, f"/trip/{trip_id}/wizard?step=packing&finish={finish}")

    @app.post("/trip/{trip_id}/wizard/packing")
    async def wizard_save_packing(request: Request, trip_id: int):
        form = await request.form()
        finish = form.get("finish") or "17:00"
        ids = [int(x) for x in form.getlist("item") if str(x).isdigit()]
        bag_ids = [int(x) for x in form.getlist("bag") if str(x).isdigit()]
        custom = (form.get("custom") or "").strip()
        async with get_db() as db:
            trip = await get_trip(trip_id)
            days = 1
            if trip and trip.get("start_date") and trip.get("end_date"):
                try:
                    start = date.fromisoformat(str(trip["start_date"])[:10])
                    end = date.fromisoformat(str(trip["end_date"])[:10])
                    days = max(1, (end - start).days + 1)
                except Exception:
                    days = 1
            order = (await (await db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) AS n FROM trip_kit WHERE trip_id = ?", (trip_id,)
            )).fetchone())["n"] or 0
            rows = []
            for item_id in ids:
                row = await (await db.execute("SELECT * FROM kit_items WHERE id = ?", (item_id,))).fetchone()
                if row:
                    rows.append(dict(row))
            for bag_id in bag_ids:
                bag_rows = await (await db.execute("SELECT * FROM kit_items WHERE bag_id = ?", (bag_id,))).fetchall()
                rows.extend(dict(r) for r in bag_rows)
            from packing_routes import _need
            for it in rows:
                order += 1
                needed = _need(it, days)
                await db.execute(
                    """INSERT INTO trip_kit (trip_id, kit_item_id, bag_id, name, category, per_day, every_days, qty, needed, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (trip_id, it["id"], it.get("bag_id"), it["name"], it.get("category") or "",
                     it.get("per_day") or 0, it.get("every_days") or 0, it.get("qty") or 1, needed, order),
                )
            if custom:
                order += 1
                await db.execute(
                    """INSERT INTO trip_kit (trip_id, name, category, qty, needed, sort_order)
                       VALUES (?, ?, 'Other', 1, 1, ?)""",
                    (trip_id, custom, order),
                )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/wizard?step=hotels&finish={finish}")

    @app.post("/trip/{trip_id}/wizard/hotels")
    async def wizard_save_hotels(request: Request, trip_id: int):
        form = await request.form()
        finish = form.get("finish") or "17:00"
        stops = await get_trip_stops(trip_id)
        async with get_db() as db:
            for key, value in form.items():
                if not key.startswith("hotel_"):
                    continue
                try:
                    day = int(key.split("_", 1)[1])
                except ValueError:
                    continue
                existing = next((s for s in stops if (s.get("day_number") or 1) == day and _is_hotel(s)), None)
                location_id = int(value) if str(value).isdigit() else 0
                if location_id:
                    if existing:
                        await db.execute(
                            "UPDATE trip_stops SET location_id = ?, is_hotel = 1 WHERE id = ? AND trip_id = ?",
                            (location_id, existing["id"], trip_id),
                        )
                    else:
                        cursor = await db.execute(
                            "SELECT COALESCE(MAX(sort_order), -1) as m FROM trip_stops WHERE trip_id = ? AND day_number = ?",
                            (trip_id, day),
                        )
                        order = ((await cursor.fetchone())["m"] or -1) + 1
                        await db.execute(
                            "INSERT INTO trip_stops (trip_id, location_id, day_number, sort_order, is_hotel) VALUES (?, ?, ?, ?, 1)",
                            (trip_id, location_id, day, order),
                        )
                elif existing:
                    await db.execute("DELETE FROM trip_stops WHERE id = ? AND trip_id = ?", (existing["id"], trip_id))
            await db.commit()
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}/wizard?step=day&day=1&finish={finish}")

    @app.post("/trip/{trip_id}/stop/{stop_id}/move-day")
    async def trip_move_day(request: Request, trip_id: int, stop_id: int, to_day: int = Form(...)):
        stops = await get_trip_stops(trip_id)
        target = next((s for s in stops if s["id"] == stop_id), None)
        if not target or _is_hotel(target):
            return _next_or_trip(request, trip_id)
        to_day = max(1, to_day)
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sort_order), -1) as m FROM trip_stops WHERE trip_id = ? AND day_number = ? AND COALESCE(is_hotel, 0) = 0",
                (trip_id, to_day),
            )
            order = ((await cursor.fetchone())["m"] or -1) + 1
            await db.execute(
                "UPDATE trip_stops SET day_number = ?, sort_order = ? WHERE id = ? AND trip_id = ?",
                (to_day, order, stop_id, trip_id),
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/stop/{stop_id}/remove")
    async def trip_remove_stop(request: Request, trip_id: int, stop_id: int):
        stops = await get_trip_stops(trip_id)
        target = next((s for s in stops if s["id"] == stop_id), None)
        if target and _is_hotel(target):
            return _next_or_trip(request, trip_id)
        async with get_db() as db:
            await db.execute(
                "DELETE FROM trip_stops WHERE id = ? AND trip_id = ?", (stop_id, trip_id)
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/stop/{stop_id}/move")
    async def trip_move_stop(
        request: Request, trip_id: int, stop_id: int,
        direction: str = Form(...),
    ):
        stops = await get_trip_stops(trip_id)
        by_day = {}
        for s in stops:
            by_day.setdefault(s["day_number"] or 1, []).append(s)
        target = next((s for s in stops if s["id"] == stop_id), None)
        if not target:
            return redirect(request, f"/trip/{trip_id}")
        day = target["day_number"] or 1
        day_stops = by_day.get(day, [])
        idx = next((i for i, s in enumerate(day_stops) if s["id"] == stop_id), None)
        if idx is None:
            return redirect(request, f"/trip/{trip_id}")
        if direction == "up" and idx > 0:
            day_stops[idx], day_stops[idx - 1] = day_stops[idx - 1], day_stops[idx]
        elif direction == "down" and idx < len(day_stops) - 1:
            day_stops[idx], day_stops[idx + 1] = day_stops[idx + 1], day_stops[idx]
        async with get_db() as db:
            for i, s in enumerate(day_stops):
                await db.execute(
                    "UPDATE trip_stops SET sort_order = ? WHERE id = ?", (i, s["id"])
                )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/reorder")
    async def trip_reorder(request: Request, trip_id: int, order: str = Form(...), day_number: int = Form(0)):
        ids = [int(x) for x in order.split(",") if x.strip().isdigit()]
        async with get_db() as db:
            for i, stop_id in enumerate(ids):
                if day_number and day_number > 0:
                    await db.execute(
                        "UPDATE trip_stops SET sort_order = ?, day_number = ? WHERE id = ? AND trip_id = ?",
                        (i, day_number, stop_id, trip_id),
                    )
                else:
                    await db.execute(
                        "UPDATE trip_stops SET sort_order = ? WHERE id = ? AND trip_id = ?",
                        (i, stop_id, trip_id),
                    )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/stop/{stop_id}/hotel")
    async def trip_toggle_hotel(request: Request, trip_id: int, stop_id: int):
        stops = await get_trip_stops(trip_id)
        target = next((s for s in stops if s["id"] == stop_id), None)
        if not target:
            return _next_or_trip(request, trip_id)
        new_val = 0 if target.get("is_hotel") else 1
        day = target.get("day_number") or 1
        async with get_db() as db:
            if new_val:
                await db.execute(
                    "UPDATE trip_stops SET is_hotel = 0 WHERE trip_id = ? AND day_number = ?",
                    (trip_id, day),
                )
            await db.execute(
                "UPDATE trip_stops SET is_hotel = ? WHERE id = ? AND trip_id = ?",
                (new_val, stop_id, trip_id),
            )
            if new_val:
                cursor = await db.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) as m FROM trip_stops WHERE trip_id = ? AND day_number = ?",
                    (trip_id, day),
                )
                last = (await cursor.fetchone())["m"] or 0
                await db.execute(
                    "UPDATE trip_stops SET sort_order = ? WHERE id = ?",
                    (last + 1, stop_id),
                )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/location/{loc_id}/visit-time")
    async def set_visit_time(request: Request, loc_id: int, visit_duration_mins: int = Form(...)):
        mins = max(0, visit_duration_mins)
        async with get_db() as db:
            await db.execute(
                "UPDATE locations SET visit_duration_mins = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (mins, loc_id),
            )
            await db.commit()
        nxt = (request.query_params.get("next") or "").strip()
        if nxt.startswith("/trip/"):
            return redirect(request, nxt)
        return redirect(request, "/")

    @app.post("/trip/{trip_id}/stop/{stop_id}/day")
    async def trip_set_stop_day(
        request: Request, trip_id: int, stop_id: int,
        day_number: int = Form(...),
    ):
        day_number = max(1, day_number)
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sort_order), -1) as m FROM trip_stops WHERE trip_id = ? AND day_number = ?",
                (trip_id, day_number),
            )
            next_order = ((await cursor.fetchone())["m"] or -1) + 1
            await db.execute(
                "UPDATE trip_stops SET day_number = ?, sort_order = ? WHERE id = ? AND trip_id = ?",
                (day_number, next_order, stop_id, trip_id),
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/recalc")
    async def trip_recalc(request: Request, trip_id: int):
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}")

    @app.get("/trip/{trip_id}/wizard", response_class=HTMLResponse)
    async def trip_wizard(request: Request, trip_id: int):
        from datetime import datetime, timedelta
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        await _recalc_trip_times(trip_id)
        stops = await get_trip_stops(trip_id)
        days = {}
        for s in stops:
            days.setdefault(s.get("day_number") or 1, []).append(s)
        n_days = 1
        day_dates = []
        if trip.get("start_date") and trip.get("end_date"):
            try:
                start = datetime.strptime(trip["start_date"], "%Y-%m-%d").date()
                end = datetime.strptime(trip["end_date"], "%Y-%m-%d").date()
                n_days = max(1, (end - start).days + 1)
                day_dates = [(start + timedelta(days=i)).isoformat() for i in range(n_days)]
            except ValueError:
                n_days = max(days.keys() or [1])
        else:
            n_days = max([1] + list(days.keys()))
        step = request.query_params.get("step") or "setup"
        try:
            day = max(1, min(int(request.query_params.get("day") or 1), n_days))
        except ValueError:
            day = 1
        finish_by = request.query_params.get("finish") or "17:00"
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.id, l.name, l.city, l.county, l.region, l.postcode,
                          l.latitude, l.longitude, l.visit_duration_mins,
                          l.url, l.theme_id, l.visit_photo_url, l.image_url, l.visited,
                          t.name as theme_name, t.primary_color, t.icon_url,
                          ct.name as category_type_name
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE COALESCE(t.exclude_from_places, 0) = 0
                   ORDER BY l.name"""
            )
            places = [dict(r) for r in await cursor.fetchall()]
            home_row = await (await db.execute(
                """SELECT l.id, l.name, l.city, l.county, l.region, l.postcode,
                          l.latitude, l.longitude, l.visit_duration_mins,
                          l.url, l.theme_id, l.visit_photo_url, l.image_url, l.visited,
                          t.name as theme_name, t.primary_color, t.icon_url,
                          ct.name as category_type_name
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE lower(t.name) = 'home'
                   ORDER BY l.id LIMIT 1"""
            )).fetchone()
            if home_row and not any(p["id"] == home_row["id"] for p in places):
                places.append(dict(home_row))
            # Accommodation / Home places for the hotels step (may be excluded from Places)
            cursor = await db.execute(
                """SELECT l.id, l.name, l.city, l.county, l.region, l.postcode,
                          l.latitude, l.longitude, l.visit_duration_mins,
                          l.url, l.theme_id, l.visit_photo_url, l.image_url, l.visited,
                          t.name as theme_name, t.primary_color, t.icon_url,
                          ct.name as category_type_name
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE lower(ct.name) IN ('accommodation', 'home location')
                      OR lower(t.name) IN ('hotel', 'hotels', 'home')
                   ORDER BY l.name"""
            )
            accommodation_places = [dict(r) for r in await cursor.fetchall()]
        day_stops = days.get(day, [])
        finish_mins = 17 * 60
        try:
            fh, fm = [int(p) for p in finish_by.split(":", 1)]
            finish_mins = fh * 60 + fm
        except ValueError:
            pass
        last_real = next((s for s in reversed(day_stops) if not _is_flexible(s)), None)
        constrained = 0
        if last_real:
            for s in day_stops:
                constrained += int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s)
                if s is last_real:
                    break
        cursor = max(0, finish_mins - constrained) if last_real else 9 * 60
        leave_at = _hhmm(cursor)
        start_time = (trip.get("start_time") or "09:00")[:5]
        try:
            sh, sm = [int(p) for p in start_time.split(":")]
            start_mins = sh * 60 + sm
        except ValueError:
            start_mins = 9 * 60
        used_mins = sum(int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s) for s in day_stops)
        spare_mins = (finish_mins - start_mins) - used_mins
        for s in day_stops:
            drive = int(round((s.get("travel_from_prev_secs") or 0) / 60))
            cursor += drive
            s["arrive"] = _hhmm(cursor)
            s["hours_warning"] = _hours_conflict(s, s.get("arrive"))
            cursor += _visit_mins(s)
            s["depart"] = _hhmm(cursor)
            s["miles"] = format_miles(s.get("distance_from_prev_m"))
        for d in range(1, n_days + 1):
            ds = days.get(d, [])
            last = next((s for s in reversed(ds) if not _is_flexible(s)), None)
            used = 0
            if last:
                for s in ds:
                    used += int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s)
                    if s is last:
                        break
            t = max(0, finish_mins - used) if last else 9 * 60
            for s in ds:
                t += int(round((s.get("travel_from_prev_secs") or 0) / 60))
                s["arrive"] = _hhmm(t)
                t += _visit_mins(s)
                s["depart"] = _hhmm(t)
                s["miles"] = format_miles(s.get("distance_from_prev_m"))
        prev_hotel = None
        if day > 1:
            for s in reversed(days.get(day - 1) or []):
                if _is_hotel(s) and s is (days.get(day - 1) or [])[-1]:
                    prev_hotel = s
                    break
        else:
            home = next((p for p in places if (p.get("theme_name") or "").strip().lower() == "home"), None)
            if home and home.get("latitude") is not None:
                prev_hotel = {
                    "location_name": home.get("name") or "Home",
                    "latitude": home.get("latitude"),
                    "longitude": home.get("longitude"),
                    "theme_name": "Home",
                    "is_hotel": 1,
                }
        summary = []
        for d in range(1, n_days + 1):
            ds = days.get(d, [])
            drive = sum((s.get("travel_from_prev_secs") or 0) for s in ds)
            visit = sum(_visit_mins(s) for s in ds)
            last_real = None
            for s in ds:
                if not _is_flexible(s):
                    last_real = s
            constrained_drive = 0
            constrained_visit = 0
            if last_real:
                for s in ds:
                    constrained_drive += s.get("travel_from_prev_secs") or 0
                    constrained_visit += _visit_mins(s)
                    if s is last_real:
                        break
            summary.append({
                "day": d,
                "date": day_dates[d - 1] if d - 1 < len(day_dates) else None,
                "stops": ds,
                "drive_secs": drive,
                "visit_mins": visit,
                "miles": format_miles(sum((s.get("distance_from_prev_m") or 0) for s in ds)),
                "constrained_drive": constrained_drive,
                "constrained_visit": constrained_visit,
                "last_name": (last_real.get("location_name") if last_real else None),
                "flexible_after": bool(last_real and ds and ds[-1] is not last_real),
            })
        # Accommodation (and Home) for end-of-day stops — include even if excluded from Places page
        hotels = list(accommodation_places)
        # Deduplicate just in case
        seen = set()
        unique = []
        for h in hotels:
            if h["id"] not in seen:
                unique.append(h)
                seen.add(h["id"])
        hotels = unique
        hotel_by_day = {}
        for s in stops:
            if _is_hotel(s):
                hotel_by_day[s.get("day_number") or 1] = s
        async with get_db() as db:
            from packing_routes import _tidy_wardrobe
            await _tidy_wardrobe()
            wardrobe = [dict(r) for r in await (await db.execute(
                """SELECT i.*, b.name AS bag_name FROM kit_items i
                   LEFT JOIN kit_bags b ON b.id = i.bag_id
                   ORDER BY b.name, i.name"""
            )).fetchall()]
        return templates.TemplateResponse("wizard.html", {
            "request": request, "base": get_base(request), "active_nav": "trips",
            "trip": trip, "n_days": n_days, "day": day, "step": step,
            "finish_by": finish_by, "day_dates": day_dates,
            "day_stops": day_stops, "stops": stops, "days": days, "prev_hotel": prev_hotel, "places": places, "summary": summary,
            "hotels": hotels, "hotel_by_day": hotel_by_day, "wardrobe": wardrobe,
            "leave_at": leave_at,
            "day_miles": format_miles(sum((s.get("distance_from_prev_m") or 0) for s in day_stops)),
            "start_time": start_time, "spare_mins": spare_mins,
            "format_duration": format_duration, "format_miles": format_miles, "visit_mins": _visit_mins,
        })

    def _active_day(trip, stops):
        stored = int(trip.get("active_day") or 0)
        calendar = 0
        if trip.get("start_date"):
            try:
                start = datetime.strptime(trip["start_date"], "%Y-%m-%d").date()
                calendar = max(1, (_now().date() - start).days + 1)
            except ValueError:
                pass
        if stored or calendar:
            return max(stored, calendar, 1)
        incomplete = [s.get("day_number") or 1 for s in stops if not s.get("completed_at") and not s.get("skipped")]
        return min(incomplete) if incomplete else 1

    def _share_url(stop):
        from urllib.parse import quote
        name = stop.get("location_name") or "Destination"
        return (
            "intent:#Intent;action=android.intent.action.SEND;type=text/plain;"
            f"S.android.intent.extra.TEXT={quote(name)};"
            f"S.android.intent.extra.SUBJECT={quote(name)};end"
        )

    def _maps_url(stop):
        lat, lng = stop.get("latitude"), stop.get("longitude")
        if lat is None or lng is None:
            return ""
        return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&travelmode=driving"


    @app.get("/api/trips/{trip_id}/live")
    async def api_trip_live(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        day_stops = [s for s in stops if (s.get("day_number") or 1) == day]
        remaining = [s for s in day_stops if not s.get("completed_at") and not s.get("skipped")]
        done = [s for s in day_stops if s.get("completed_at") or s.get("skipped")]
        nxt = remaining[0] if remaining else None
        return {
            "trip": trip,
            "day": day,
            "next": nxt,
            "remaining": remaining,
            "done": done,
            "total_days": max((s.get("day_number") or 1) for s in stops) if stops else 1,
        }

    @app.post("/api/trips/{trip_id}/start")
    async def api_trip_start(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        async with get_db() as db:
            await db.execute(
                """UPDATE trips SET status = 'active', started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                   active_day = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (day, trip_id),
            )
            await db.commit()
        return {"ok": True, "day": day}

    @app.post("/api/trips/{trip_id}/stop/{stop_id}/arrive")
    async def api_arrive(request: Request, trip_id: int, stop_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE trip_stops SET arrived_at = CURRENT_TIMESTAMP WHERE id = ? AND trip_id = ? AND arrived_at IS NULL",
                (stop_id, trip_id),
            )
            await db.commit()
        return {"ok": True}


    @app.post("/api/trips/{trip_id}/stop/{stop_id}/photo")
    async def api_stop_photo(request: Request, trip_id: int, stop_id: int, file: UploadFile = File(...)):
        url = await save_upload(file)
        async with get_db() as db:
            row = await (await db.execute("SELECT location_id FROM trip_stops WHERE id = ? AND trip_id = ?", (stop_id, trip_id))).fetchone()
            if row and row["location_id"]:
                await db.execute("UPDATE locations SET visit_photo_url = ? WHERE id = ?", (url, row["location_id"]))
                await db.commit()
        return {"ok": True, "url": url}

    @app.post("/api/trips/{trip_id}/stop/{stop_id}/leave")
    async def api_leave(request: Request, trip_id: int, stop_id: int):
        async with get_db() as db:
            row = await (await db.execute(
                "SELECT location_id, arrived_at FROM trip_stops WHERE id = ? AND trip_id = ?",
                (stop_id, trip_id),
            )).fetchone()
            mins = 0
            if row and row["arrived_at"]:
                try:
                    start = datetime.fromisoformat(str(row["arrived_at"]).replace(" ", "T"))
                    mins = max(1, int((datetime.now() - start).total_seconds() / 60))
                except Exception:
                    mins = 0
            await db.execute(
                "UPDATE trip_stops SET completed_at = CURRENT_TIMESTAMP WHERE id = ? AND trip_id = ?",
                (stop_id, trip_id),
            )
            if row and row["location_id"]:
                await db.execute(
                    """UPDATE locations SET visited = 1, visit_date = date('now'),
                       visit_duration_mins = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (mins, row["location_id"]),
                )
            await db.commit()
        return {"ok": True}

    @app.post("/api/trips/{trip_id}/stop/{stop_id}/skip")
    async def api_skip(request: Request, trip_id: int, stop_id: int):
        async with get_db() as db:
            await db.execute("UPDATE trip_stops SET skipped = 1 WHERE id = ? AND trip_id = ?", (stop_id, trip_id))
            await db.commit()
        return {"ok": True}

    @app.post("/api/trips/{trip_id}/end-day")
    async def api_end_day(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        async with get_db() as db:
            await db.execute(
                "UPDATE trip_stops SET completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP) WHERE trip_id = ? AND day_number = ?",
                (trip_id, day),
            )
            await db.execute("UPDATE trips SET active_day = ? WHERE id = ?", (day + 1, trip_id))
            await db.commit()
        return {"ok": True, "day": day + 1}

    @app.post("/api/trips/{trip_id}/finish")
    async def api_finish(request: Request, trip_id: int):
        async with get_db() as db:
            await db.execute("UPDATE trips SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (trip_id,))
            await db.commit()
        return {"ok": True}

    @app.post("/trip/{trip_id}/start")
    async def trip_start(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        async with get_db() as db:
            await db.execute(
                """UPDATE trips SET status = 'active', started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                   active_day = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (day, trip_id),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/live")

    @app.post("/trip/{trip_id}/finish")
    async def trip_finish(request: Request, trip_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE trips SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (trip_id,),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}")

    @app.get("/trip/{trip_id}/live", response_class=HTMLResponse)
    async def trip_live(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        day_stops = [s for s in stops if (s.get("day_number") or 1) == day]
        remaining = [s for s in day_stops if not s.get("completed_at") and not s.get("skipped")]
        done = [s for s in day_stops if s.get("completed_at") or s.get("skipped")]
        nxt = remaining[0] if remaining else None
        now = _now()
        now_mins = now.hour * 60 + now.minute
        finish = 17 * 60
        constrained = 0
        last_real = None
        for s in remaining:
            if not _is_flexible(s):
                last_real = s
        if last_real:
            for s in remaining:
                constrained += int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s)
                if s is last_real:
                    break
        can_finish = (now_mins + constrained) <= finish if last_real else True
        next_drive = int(round(((nxt or {}).get("travel_from_prev_secs") or 0) / 60))
        if nxt:
            nxt["hours_warning"] = _hours_conflict(nxt, _hhmm(now_mins + next_drive))
        tomorrow = [s for s in stops if (s.get("day_number") or 1) == day + 1]
        start_time = (trip.get("start_time") or "09:00")[:5]
        try:
            sh, sm = [int(p) for p in start_time.split(":")]
            start_mins = sh * 60 + sm
        except ValueError:
            start_mins = 9 * 60
        finish_mins = 17 * 60
        last_real_t = next((s for s in reversed(tomorrow) if not _is_flexible(s)), None)
        constrained_t = 0
        if last_real_t:
            for s in tomorrow:
                constrained_t += int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s)
                if s is last_real_t:
                    break
        cursor = max(0, finish_mins - constrained_t) if last_real_t else start_mins
        tomorrow_leave = _hhmm(cursor)
        for s in tomorrow:
            cursor += int(round((s.get("travel_from_prev_secs") or 0) / 60))
            s["arrive"] = _hhmm(cursor)
            cursor += _visit_mins(s)
            s["depart"] = _hhmm(cursor)
            s["miles"] = format_miles(s.get("distance_from_prev_m"))
        used_t = sum(int(round((s.get("travel_from_prev_secs") or 0) / 60)) + _visit_mins(s) for s in tomorrow)
        tomorrow_spare = (finish_mins - start_mins) - used_t
        tomorrow_miles = format_miles(sum((s.get("distance_from_prev_m") or 0) for s in tomorrow))
        tomorrow_visits = [s for s in tomorrow if not _is_hotel(s)]
        tomorrow_hotel = next((s for s in reversed(tomorrow) if _is_hotel(s)), None)
        tonight = next((s for s in reversed(day_stops) if _is_hotel(s)), None)
        return templates.TemplateResponse("live.html", {
            "request": request, "base": get_base(request), "active_nav": "trips",
            "trip": trip, "day": day, "next": nxt, "remaining": remaining, "done": done,
            "tomorrow": tomorrow, "tomorrow_visits": tomorrow_visits, "tomorrow_hotel": tomorrow_hotel,
            "tomorrow_leave": tomorrow_leave, "tomorrow_spare": tomorrow_spare, "tomorrow_miles": tomorrow_miles,
            "tonight": tonight,
            "now": now.strftime("%H:%M"), "next_drive": next_drive,
            "can_finish": can_finish, "constrained": constrained,
            "finish_by": "17:00",
            "maps_url": _maps_url(nxt) if nxt else "",
            "tesla_url": _share_url(nxt) if nxt else "",
            "format_duration": format_duration, "format_miles": format_miles, "visit_mins": _visit_mins,
        })

    @app.post("/trip/{trip_id}/stop/{stop_id}/arrive")
    async def trip_arrive(request: Request, trip_id: int, stop_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE trip_stops SET arrived_at = CURRENT_TIMESTAMP WHERE id = ? AND trip_id = ? AND arrived_at IS NULL",
                (stop_id, trip_id),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/live")

    @app.post("/trip/{trip_id}/stop/{stop_id}/photo")
    async def trip_visit_photo(request: Request, trip_id: int, stop_id: int, photo: Optional[UploadFile] = File(None)):
        if photo and photo.filename:
            photo_url = await save_upload(photo)
            async with get_db() as db:
                row = await (await db.execute("SELECT location_id FROM trip_stops WHERE id = ? AND trip_id = ?", (stop_id, trip_id))).fetchone()
                if row and row["location_id"]:
                    await db.execute(
                        "UPDATE locations SET visit_photo_url = ? WHERE id = ?",
                        (photo_url, row["location_id"]),
                    )
                    await db.commit()
        return redirect(request, f"/trip/{trip_id}/live")

    @app.post("/trip/{trip_id}/stop/{stop_id}/leave")
    async def trip_leave(request: Request, trip_id: int, stop_id: int):
        async with get_db() as db:
            row = await (await db.execute(
                "SELECT location_id, arrived_at FROM trip_stops WHERE id = ? AND trip_id = ?",
                (stop_id, trip_id),
            )).fetchone()
            mins = 0
            if row and row["arrived_at"]:
                try:
                    from datetime import datetime
                    start = datetime.fromisoformat(str(row["arrived_at"]).replace(" ", "T"))
                    mins = max(1, int((datetime.now() - start).total_seconds() / 60))
                except Exception:
                    mins = 0
            await db.execute(
                "UPDATE trip_stops SET completed_at = CURRENT_TIMESTAMP WHERE id = ? AND trip_id = ?",
                (stop_id, trip_id),
            )
            if row and row["location_id"]:
                await db.execute(
                    """UPDATE locations SET visited = 1, visit_date = date('now'),
                       visit_duration_mins = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (mins, row["location_id"]),
                )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/live")

    @app.post("/trip/{trip_id}/stop/{stop_id}/skip")
    async def trip_skip(request: Request, trip_id: int, stop_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE trip_stops SET skipped = 1 WHERE id = ? AND trip_id = ?",
                (stop_id, trip_id),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/live")

    @app.post("/trip/{trip_id}/move-remaining")
    async def trip_move_remaining(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        nxt_day = day + 1
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sort_order), -1) as m FROM trip_stops WHERE trip_id = ? AND day_number = ?",
                (trip_id, nxt_day),
            )
            order = ((await cursor.fetchone())["m"] or -1) + 1
            cursor = await db.execute(
                """SELECT id FROM trip_stops WHERE trip_id = ? AND day_number = ?
                   AND completed_at IS NULL AND COALESCE(skipped, 0) = 0
                   AND COALESCE(is_hotel, 0) = 0 ORDER BY sort_order""",
                (trip_id, day),
            )
            for row in await cursor.fetchall():
                await db.execute(
                    "UPDATE trip_stops SET day_number = ?, sort_order = ? WHERE id = ?",
                    (nxt_day, order, row["id"]),
                )
                order += 1
            await db.execute("UPDATE trips SET active_day = ? WHERE id = ?", (nxt_day, trip_id))
            await db.commit()
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}/live")

    @app.post("/trip/{trip_id}/remove-remaining")
    async def trip_remove_remaining(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        async with get_db() as db:
            await db.execute(
                """DELETE FROM trip_stops WHERE trip_id = ? AND day_number = ?
                   AND completed_at IS NULL AND COALESCE(skipped, 0) = 0""",
                (trip_id, day),
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}/live")

    @app.post("/trip/{trip_id}/end-day")
    async def trip_end_day(request: Request, trip_id: int):
        trip = await get_trip(trip_id)
        stops = await get_trip_stops(trip_id)
        day = _active_day(trip, stops)
        async with get_db() as db:
            await db.execute("UPDATE trips SET active_day = ? WHERE id = ?", (day + 1, trip_id))
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/live?review=1")

    @app.get("/visit", response_class=HTMLResponse)
    async def visit_select(request: Request):
        q = (request.query_params.get("q") or "").strip().lower()
        theme_id = request.query_params.get("theme") or "all"
        type_id = request.query_params.get("type") or "all"
        region = request.query_params.get("region") or "all"
        county = request.query_params.get("county") or "all"
        show_visited = request.query_params.get("show_visited") == "1"
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM themes WHERE COALESCE(exclude_from_places, 0) = 0 ORDER BY name"
            )
            themes = [dict(r) for r in await cursor.fetchall()]
            cursor = await db.execute(
                """SELECT l.*, t.name as theme_name, t.primary_color, t.icon_url,
                          t.category_type_id, ct.name as category_type_name
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE COALESCE(t.exclude_from_places, 0) = 0
                     AND COALESCE(t.hide_visit_status, 0) = 0
                   ORDER BY l.name"""
            )
            locations = [dict(r) for r in await cursor.fetchall()]
            cursor = await db.execute(
                """SELECT DISTINCT region FROM locations WHERE region IS NOT NULL AND region != '' ORDER BY region"""
            )
            regions = [r["region"] for r in await cursor.fetchall()]
            cursor = await db.execute(
                """SELECT DISTINCT county FROM locations WHERE county IS NOT NULL AND county != '' ORDER BY county"""
            )
            counties = [r["county"] for r in await cursor.fetchall()]
            filter_index = [
                {"type": {"value": str(loc.get("category_type_id") or ""), "label": loc.get("category_type_name") or ""},
                 "theme": {"value": str(loc.get("theme_id") or ""), "label": loc.get("theme_name") or ""},
                 "region": loc.get("region") or "", "county": loc.get("county") or ""}
                for loc in locations
            ]
        if q:
            locations = [
                loc for loc in locations
                if q in (loc.get("name") or "").lower()
                or q in (loc.get("city") or "").lower()
                or q in (loc.get("postcode") or "").lower()
                or q in (loc.get("county") or "").lower()
            ]
        if type_id != "all":
            locations = [loc for loc in locations if str(loc.get("category_type_id") or "") == str(type_id)]
        if theme_id != "all":
            locations = [loc for loc in locations if str(loc.get("theme_id")) == str(theme_id)]
        if region != "all":
            locations = [loc for loc in locations if (loc.get("region") or "") == region]
        if county != "all":
            locations = [loc for loc in locations if (loc.get("county") or "") == county]
        if not show_visited:
            locations = [loc for loc in locations if not loc.get("visited")]
        selected = request.query_params.get("place")
        selected_loc = None
        if selected:
            selected_loc = next((loc for loc in locations if str(loc["id"]) == str(selected)), None)
            if not selected_loc:
                async with get_db() as db:
                    c = await db.execute(
                        """SELECT l.*, t.name as theme_name FROM locations l
                           JOIN themes t ON t.id = l.theme_id WHERE l.id = ?""",
                        (int(selected),),
                    )
                    row = await c.fetchone()
                    selected_loc = dict(row) if row else None
        return templates.TemplateResponse("visit.html", {
            "request": request, "base": get_base(request), "active_nav": "dashboard",
            "themes": themes, "locations": locations, "regions": regions,
            "q": request.query_params.get("q") or "",
            "theme_filter": theme_id, "type_filter": type_id, "region_filter": region, "county_filter": county,
            "show_visited": show_visited, "counties": counties, "filter_index": filter_index,
            "selected": selected_loc,
            "today": date.today().isoformat(),
            "return_to": request.query_params.get("return") or "",
        })

    @app.get("/visit/{loc_id}/edit", response_class=HTMLResponse)
    async def visit_edit_form(request: Request, loc_id: int):
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.*, t.name as theme_name
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE l.id = ?""",
                (loc_id,),
            )
            loc = await cursor.fetchone()
        if not loc or not loc["visited"]:
            raise HTTPException(status_code=404, detail="Visit not found")
        return templates.TemplateResponse("visit_edit.html", {
            "request": request, "base": get_base(request), "active_nav": "dashboard",
            "visit": dict(loc),
        })

    @app.post("/visit/{loc_id}/edit")
    async def visit_edit_save(
        request: Request, loc_id: int,
        visit_date: str = Form(...),
        photo: Optional[UploadFile] = File(None),
        clear_photo: Optional[str] = Form(None),
    ):
        photo_url = None
        if photo and photo.filename:
            photo_url = await save_upload(photo)
        async with get_db() as db:
            if photo_url:
                await db.execute(
                    """UPDATE locations SET visit_date = ?, visit_photo_url = ?,
                        updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (visit_date.strip(), photo_url, loc_id),
                )
            elif clear_photo == "on":
                await db.execute(
                    """UPDATE locations SET visit_date = ?, visit_photo_url = '',
                        updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (visit_date.strip(), loc_id),
                )
            else:
                await db.execute(
                    "UPDATE locations SET visit_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (visit_date.strip(), loc_id),
                )
            await db.commit()
        return redirect(request, "/visits")
    async def visits_list(request: Request):
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.*, t.name as theme_name, t.primary_color, t.icon_url
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE l.visited = 1 AND l.visit_date IS NOT NULL
                     AND COALESCE(t.exclude_from_counts, 0) = 0
                   ORDER BY l.visit_date DESC, l.updated_at DESC"""
            )
            visits = [dict(r) for r in await cursor.fetchall()]
        return templates.TemplateResponse("visits.html", {
            "request": request, "base": get_base(request), "active_nav": "dashboard",
            "visits": visits,
        })

    @app.post("/visit")
    async def visit_save(
        request: Request,
        location_id: int = Form(...),
        visit_date: str = Form(...),
        photo: Optional[UploadFile] = File(None),
    ):
        photo_url = ""
        if photo and photo.filename:
            photo_url = await save_upload(photo)
        async with get_db() as db:
            await db.execute(
                """UPDATE locations SET visited = 1, visit_date = ?,
                    visit_photo_url = CASE WHEN ? != '' THEN ? ELSE visit_photo_url END,
                    updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (visit_date.strip(), photo_url, photo_url, location_id),
            )
            await db.commit()
        nxt = (request.query_params.get("return") or "").strip()
        if nxt.startswith("/trip/"):
            return redirect(request, nxt)
        return redirect(request, "/")


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
    match = re.search(r"(\d{1,2}):(\d{2})\s*[-\u2013]\s*(\d{1,2}):(\d{2})", text)
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
                      l.visit_photo_url,
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
                """SELECT t.name FROM locations l JOIN themes t ON t.id = l.theme_id WHERE l.id = ?""",
                (location_id,),
            )
            theme_row = await cursor.fetchone()
            theme_name = (theme_row["name"] or "").strip().lower() if theme_row else ""
            is_hotel = theme_name in ("hotel", "hotels", "home")
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
        name: str = Form(...),
        start_date: str = Form(""),
        end_date: str = Form(""),
        notes: str = Form(""),
        start_time: str = Form("09:00"),
        finish: str = Form("17:00"),
        image: Optional[UploadFile] = File(None),
        action: str = Form(""),
    ):
        image_url = None
        if image and image.filename:
            image_url = await save_upload(image)
        async with get_db() as db:
            if image_url:
                await db.execute(
                    """UPDATE trips SET name = ?, start_date = ?, end_date = ?, notes = ?,
                        start_time = ?, image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip(), start_time.strip() or "09:00", image_url, trip_id),
                )
            else:
                await db.execute(
                    """UPDATE trips SET name = ?, start_date = ?, end_date = ?, notes = ?,
                        start_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip(), start_time.strip() or "09:00", trip_id),
                )
            await db.commit()
        q = "uploaded=1" if image_url else ""
        if action == "upload":
            return redirect(request, f"/trip/{trip_id}/wizard?step=setup&finish={finish}&{q}")
        return redirect(request, f"/trip/{trip_id}/wizard?step=packing&finish={finish}")

    @app.post("/trip/{trip_id}/wizard/packing")
    async def wizard_save_packing(request: Request, trip_id: int):
        form = await request.form()
        finish = form.get("finish") or "17:00"
        items = form.getlist("item")
        bags = form.getlist("bag")
        custom = (form.get("custom") or "").strip()
        async with get_db() as db:
            await db.execute("DELETE FROM trip_packing WHERE trip_id = ?", (trip_id,))
            for item_id in items:
                if str(item_id).isdigit():
                    await db.execute(
                        "INSERT INTO trip_packing (trip_id, wardrobe_item_id) VALUES (?, ?)",
                        (trip_id, int(item_id)),
                    )
            for bag_id in bags:
                if str(bag_id).isdigit():
                    await db.execute(
                        "INSERT INTO trip_packing (trip_id, bag_id) VALUES (?, ?)",
                        (trip_id, int(bag_id)),
                    )
            if custom:
                await db.execute(
                    "INSERT INTO trip_packing (trip_id, custom_name) VALUES (?, ?)",
                    (trip_id, custom),
                )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/wizard?step=hotels&finish={finish}")

    @app.post("/trip/{trip_id}/wizard/hotels")
    async def wizard_save_hotels(request: Request, trip_id: int):
        form = await request.form()
        finish = form.get("finish") or "17:00"
        async with get_db() as db:
            for key, value in form.items():
                if not key.startswith("hotel_"):
                    continue
                try:
                    day = int(key.split("_", 1)[1])
                except ValueError:
                    continue
                location_id = int(value) if str(value).isdigit() else 0
                if location_id:
                    cursor = await db.execute(
                        "SELECT id FROM trip_stops WHERE trip_id = ? AND day_number = ? AND COALESCE(is_hotel, 0) = 1",
                        (trip_id, day),
                    )
                    existing = await cursor.fetchone()
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
                else:
                    await db.execute(
                        "DELETE FROM trip_stops WHERE trip_id = ? AND day_number = ? AND COALESCE(is_hotel, 0) = 1",
                        (trip_id, day),
                    )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}/wizard?step=day&day=1&finish={finish}")

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
                          l.url, l.theme_id, l.visit_photo_url, l.visited,
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
                          l.url, l.theme_id, l.visit_photo_url, l.visited,
                          t.name as theme_name, t.primary_color, t.icon_url,
                          ct.name as category_type_name
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE lower(t.name) = 'home'
                   ORDER BY l.id LIMIT 1"""
            )).fetchone()
            if home_row and not any(p["id"] == home_row["id"] for p in places):
                places.append(dict(home_row))
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
            sh, sm = [int(p) for p in start_time.split(":", 1)]
            start_mins = sh * 60 + sm
        except ValueError:
            start_mins = 9 * 60
        spare_mins = finish_mins - start_mins - constrained if last_real else 0
        hotel_by_day = {}
        for s in stops:
            if s.get("is_hotel"):
                hotel_by_day[s.get("day_number") or 1] = s
        prev_hotel = hotel_by_day.get(day - 1) if day > 1 else None
        if day == 1:
            home = next((p for p in places if (p.get("theme_name") or "").strip().lower() == "home"), None)
            if home:
                prev_hotel = {"location_name": home["name"], "location_id": home["id"]}
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM wardrobe_items ORDER BY category, name")
            wardrobe = [dict(r) for r in await cursor.fetchall()]
            cursor = await db.execute(
                """SELECT tp.*, wi.name, wi.category, wi.every_days, wi.bag_id, b.name as bag_name
                   FROM trip_packing tp
                   LEFT JOIN wardrobe_items wi ON wi.id = tp.wardrobe_item_id
                   LEFT JOIN bags b ON b.id = tp.bag_id
                   WHERE tp.trip_id = ?""",
                (trip_id,),
            )
            packing = [dict(r) for r in await cursor.fetchall()]
        hotels = [p for p in places if (p.get("theme_name") or "").strip().lower() in ("hotel", "hotels", "home")]
        summary = {
            "n_days": n_days,
            "total_drive": sum((s.get("travel_from_prev_secs") or 0) for s in stops),
            "total_visit": sum(_visit_mins(s) for s in stops),
            "total_miles": sum((s.get("distance_from_prev_m") or 0) for s in stops) / 1609.344,
        }
        return templates.TemplateResponse("wizard.html", {
            "request": request, "base": get_base(request), "active_nav": "trips",
            "trip": trip, "step": step, "day": day, "n_days": n_days, "day_dates": day_dates,
            "finish_by": finish_by, "day_stops": day_stops, "stops": stops, "prev_hotel": prev_hotel,
            "places": places, "summary": summary, "wardrobe": wardrobe, "packing": packing,
            "hotels": hotels, "hotel_by_day": hotel_by_day, "leave_at": leave_at,
            "spare_mins": spare_mins, "format_duration": format_duration, "visit_mins": _visit_mins,
            "days": days,
        })

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
        async with get_db() as db:
            await db.execute("DELETE FROM trip_stops WHERE id = ? AND trip_id = ?", (stop_id, trip_id))
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/reorder")
    async def trip_reorder(request: Request, trip_id: int, order: str = Form(...)):
        ids = [int(i) for i in order.split(",") if i.strip().isdigit()]
        async with get_db() as db:
            for i, stop_id in enumerate(ids):
                await db.execute(
                    "UPDATE trip_stops SET sort_order = ? WHERE id = ? AND trip_id = ?",
                    (i, stop_id, trip_id),
                )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/stop/{stop_id}/toggle-hotel")
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

    # Additional routes for packing, visits etc. would continue here in the full file
    # (truncated in this response for length, but the key wizard query is updated)

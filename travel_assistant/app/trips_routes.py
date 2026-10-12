"""Trip planner and quick-visit routes for Travel Assistant."""
from __future__ import annotations

import asyncio
from datetime import date
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


def format_duration(secs: Optional[int]) -> str:
    if secs is None:
        return "—"
    mins = max(1, int(round(secs / 60)))
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _hhmm(mins: int) -> str:
    mins = int(round(mins)) % (24 * 60)
    h, m = divmod(mins, 60)
    return f"{h:02d}:{m:02d}"
    if meters is None:
        return ""
    if meters < 1000:
        return f"{meters} m"
    return f"{meters / 1000:.1f} km"


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
    return name in ("hotel", "hotels")


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
                      l.visited, l.visit_date, l.visit_duration_mins, l.theme_id,
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
        for day, day_stops in by_day.items():
            prev_hotel = None
            if day > 1:
                prev = by_day.get(day - 1) or []
                if prev and _is_hotel(prev[-1]):
                    prev_hotel = prev[-1]
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
    ):
        async with get_db() as db:
            cursor = await db.execute(
                """INSERT INTO trips (name, start_date, end_date, notes)
                   VALUES (?, ?, ?, ?)""",
                (name.strip(), start_date.strip() or None, end_date.strip() or None, notes.strip()),
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
            for s in ds:
                drive = int(round((s.get("travel_from_prev_secs") or 0) / 60))
                s["depart"] = _hhmm(cursor)
                cursor += drive
                s["arrive"] = _hhmm(cursor)
                cursor += _visit_mins(s)
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
    ):
        async with get_db() as db:
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
            is_hotel = 1 if theme_row and (theme_row["name"] or "").strip().lower() in ("hotel", "hotels") else 0
            await db.execute(
                """INSERT INTO trip_stops (trip_id, location_id, day_number, sort_order, is_hotel)
                   VALUES (?, ?, ?, ?, ?)""",
                (trip_id, location_id, day_number, next_order, is_hotel),
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return _next_or_trip(request, trip_id)

    @app.post("/trip/{trip_id}/stop/{stop_id}/remove")
    async def trip_remove_stop(request: Request, trip_id: int, stop_id: int):
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
    async def trip_reorder(request: Request, trip_id: int, order: str = Form(...), day_number: int = Form(1)):
        ids = [int(x) for x in order.split(",") if x.strip().isdigit()]
        async with get_db() as db:
            for i, stop_id in enumerate(ids):
                await db.execute(
                    "UPDATE trip_stops SET sort_order = ?, day_number = ? WHERE id = ? AND trip_id = ?",
                    (i, day_number, stop_id, trip_id),
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
                          t.name as theme_name, t.primary_color, t.icon_url
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE COALESCE(t.exclude_from_places, 0) = 0
                   ORDER BY l.name"""
            )
            places = [dict(r) for r in await cursor.fetchall()]
        day_stops = days.get(day, [])
        prev_hotel = None
        if day > 1:
            for s in reversed(days.get(day - 1) or []):
                if _is_hotel(s) and s is (days.get(day - 1) or [])[-1]:
                    prev_hotel = s
                    break
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
                "constrained_drive": constrained_drive,
                "constrained_visit": constrained_visit,
                "last_name": (last_real.get("location_name") if last_real else None),
                "flexible_after": bool(last_real and ds and ds[-1] is not last_real),
            })
        return templates.TemplateResponse("wizard.html", {
            "request": request, "base": get_base(request), "active_nav": "trips",
            "trip": trip, "n_days": n_days, "day": day, "step": step,
            "finish_by": finish_by, "day_dates": day_dates,
            "day_stops": day_stops, "stops": stops, "prev_hotel": prev_hotel, "places": places, "summary": summary,
            "format_duration": format_duration, "visit_mins": _visit_mins,
        })

    @app.get("/visit", response_class=HTMLResponse)
    async def visit_select(request: Request):
        q = (request.query_params.get("q") or "").strip().lower()
        theme_id = request.query_params.get("theme") or "all"
        region = request.query_params.get("region") or "all"
        county = request.query_params.get("county") or "all"
        show_visited = request.query_params.get("show_visited") == "1"
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM themes WHERE COALESCE(exclude_from_places, 0) = 0 ORDER BY name"
            )
            themes = [dict(r) for r in await cursor.fetchall()]
            cursor = await db.execute(
                """SELECT l.*, t.name as theme_name, t.primary_color, t.icon_url
                   FROM locations l JOIN themes t ON t.id = l.theme_id
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
                {"theme": str(loc.get("theme_id") or ""), "region": loc.get("region") or "", "county": loc.get("county") or ""}
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
            "theme_filter": theme_id, "region_filter": region, "county_filter": county,
            "show_visited": show_visited, "counties": counties, "filter_index": filter_index,
            "selected": selected_loc,
            "today": date.today().isoformat(),
        })

    @app.get("/visits", response_class=HTMLResponse)
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
        return redirect(request, "/")

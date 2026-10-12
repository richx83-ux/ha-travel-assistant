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


def format_distance(meters: Optional[int]) -> str:
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


async def get_trip_stops(trip_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT s.*, l.name as location_name, l.latitude, l.longitude,
                      l.postcode, l.city, l.county, l.url as location_url,
                      l.visited, l.visit_date, t.name as theme_name, t.primary_color, t.icon_url
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
            if day_stops:
                await db.execute(
                    "UPDATE trip_stops SET travel_from_prev_secs = NULL, distance_from_prev_m = NULL WHERE id = ?",
                    (day_stops[0]["id"],),
                )
            coords = []
            valid_ids = []
            for s in day_stops:
                lat, lng = s.get("latitude"), s.get("longitude")
                if lat is not None and lng is not None:
                    coords.append((float(lat), float(lng)))
                    valid_ids.append(s["id"])
            if len(coords) >= 2:
                legs = await osrm_leg_times(coords)
                for i, leg in enumerate(legs):
                    stop_id = valid_ids[i + 1]
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
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.id, l.name, l.city, l.county, l.region, l.postcode,
                          l.theme_id, l.visited, t.name as theme_name
                   FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE COALESCE(t.exclude_from_places, 0) = 0
                   ORDER BY l.name"""
            )
            places = [dict(r) for r in await cursor.fetchall()]
        total_travel = sum((s.get("travel_from_prev_secs") or 0) for s in stops if s.get("travel_from_prev_secs"))
        return templates.TemplateResponse("trip.html", {
            "request": request, "base": get_base(request), "active_nav": "trips",
            "trip": trip, "stops": stops, "days": days, "day_list": day_list,
            "places": places, "total_travel": total_travel,
            "format_duration": format_duration, "format_distance": format_distance,
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
            await db.execute(
                """INSERT INTO trip_stops (trip_id, location_id, day_number, sort_order)
                   VALUES (?, ?, ?, ?)""",
                (trip_id, location_id, day_number, next_order),
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}")

    @app.post("/trip/{trip_id}/stop/{stop_id}/remove")
    async def trip_remove_stop(request: Request, trip_id: int, stop_id: int):
        async with get_db() as db:
            await db.execute(
                "DELETE FROM trip_stops WHERE id = ? AND trip_id = ?", (stop_id, trip_id)
            )
            await db.commit()
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}")

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
        return redirect(request, f"/trip/{trip_id}")

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
        return redirect(request, f"/trip/{trip_id}")

    @app.post("/trip/{trip_id}/recalc")
    async def trip_recalc(request: Request, trip_id: int):
        await _recalc_trip_times(trip_id)
        return redirect(request, f"/trip/{trip_id}")

    @app.get("/visit", response_class=HTMLResponse)
    async def visit_select(request: Request):
        q = (request.query_params.get("q") or "").strip().lower()
        theme_id = request.query_params.get("theme") or "all"
        region = request.query_params.get("region") or "all"
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
            "theme_filter": theme_id, "region_filter": region,
            "show_visited": show_visited,
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

"""Additional API routes for Travel Assistant (tiles, places, cruise, etc.)."""
from __future__ import annotations

import asyncio
import urllib.request
import json
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse

# Injected by register_extra_routes
app = None
templates = None
get_db = None
save_upload = None
get_base = None
redirect = None
geocode_postcode = None
geocode_postcodes_bulk = None
geocode_place_name = None
grok_key = None
load_ui_settings = None
save_ui_settings = None
list_assets = None
seed_category_icons = None
_http_get_json = None
_http_post_json = None
get_locations = None

def register_extra_routes(_app, _templates, deps: dict):
    global app, templates, get_db, save_upload, get_base, redirect
    global geocode_postcode, geocode_postcodes_bulk, geocode_place_name
    global grok_key, load_ui_settings, save_ui_settings, list_assets, seed_category_icons
    global _http_get_json, _http_post_json, get_locations
    app = _app
    templates = _templates
    get_db = deps["get_db"]
    save_upload = deps.get("save_upload")
    get_base = deps.get("get_base")
    redirect = deps.get("redirect")
    geocode_postcode = deps.get("geocode_postcode")
    geocode_postcodes_bulk = deps.get("geocode_postcodes_bulk")
    geocode_place_name = deps.get("geocode_place_name")
    grok_key = deps.get("grok_key")
    load_ui_settings = deps.get("load_ui_settings")
    save_ui_settings = deps.get("save_ui_settings")
    list_assets = deps.get("list_assets")
    seed_category_icons = deps.get("seed_category_icons")
    _http_get_json = deps.get("_http_get_json")
    _http_post_json = deps.get("_http_post_json")
    get_locations = deps.get("get_locations")

    @app.get("/api/tiles/{z}/{x}/{y}.png")
    async def tile_proxy(z: int, x: int, y: int):
        """Proxy OSM tiles with a proper User-Agent so they are not blocked."""
        url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        def fetch():
            req = urllib.request.Request(url, headers={
                "User-Agent": "TravelAssistant/1.0 (Home Assistant add-on; contact: local)",
                "Accept": "image/png",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read()
        try:
            data = await asyncio.to_thread(fetch)
            return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            raise HTTPException(status_code=502, detail="Tile unavailable")

    @app.get("/api/places/{place_id}")
    async def api_place_detail(request: Request, place_id: int):
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.*, t.name as theme_name, t.primary_color, t.icon_url,
                          t.default_image_url, ct.name as category_type_name
                   FROM locations l
                   JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE l.id = ?""",
                (place_id,),
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404)
            return dict(row)

    @app.get("/api/places")
    async def api_places(request: Request):
        """JSON list of places + filter options for the React UI."""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.id, l.name, l.city, l.county, l.region, l.district, l.postcode,
                          l.address, l.notes, l.url, l.opening_hours, l.visit_duration_mins,
                          l.latitude, l.longitude, l.visited, l.visit_date, l.visit_photo_url, l.image_url, COALESCE(l.hidden, 0) as hidden,
                          l.theme_id, t.name as theme_name, t.primary_color,
                          t.default_image_url, t.icon_url,
                          ct.name as category_type_name
                   FROM locations l
                   JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE COALESCE(t.exclude_from_places, 0) = 0
                   ORDER BY l.name"""
            )
            places = [dict(r) for r in await cursor.fetchall()]
            cursor = await db.execute(
                "SELECT id, name FROM themes WHERE COALESCE(exclude_from_places, 0) = 0 ORDER BY name"
            )
            themes = [dict(r) for r in await cursor.fetchall()]
            cursor = await db.execute(
                "SELECT id, name FROM category_types ORDER BY sort_order, name"
            )
            types = [dict(r) for r in await cursor.fetchall()]
        regions = sorted({(p.get("region") or "").strip() for p in places if (p.get("region") or "").strip()})
        counties = sorted({(p.get("county") or "").strip() for p in places if (p.get("county") or "").strip()})
        return {
            "places": places,
            "themes": themes,
            "types": types,
            "regions": regions,
            "counties": counties,
        }




    @app.post("/api/places/{place_id}/image")
    async def api_place_image(request: Request, place_id: int, file: UploadFile = File(...)):
        """Upload a new image for a place. Returns the stored URL."""
        url = await save_upload(file)
        async with get_db() as db:
            await db.execute(
                "UPDATE locations SET image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (url, place_id),
            )
            await db.commit()
        return {"ok": True, "url": url}



    @app.post("/api/places/{place_id}/clear-image")
    async def api_place_clear_image(request: Request, place_id: int):
        """Clear both place image and visit photo."""
        async with get_db() as db:
            await db.execute(
                "UPDATE locations SET image_url = '', visit_photo_url = '', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (place_id,),
            )
            await db.commit()
        return {"ok": True, "image_url": "", "visit_photo_url": ""}



    @app.post("/api/places/{place_id}/delete")
    async def api_place_delete(request: Request, place_id: int):
        """Delete a place and its trip stops."""
        async with get_db() as db:
            await db.execute("DELETE FROM trip_stops WHERE location_id = ?", (place_id,))
            await db.execute("DELETE FROM locations WHERE id = ?", (place_id,))
            await db.commit()
        return {"ok": True}


    @app.post("/api/places/{place_id}")
    async def api_place_update(request: Request, place_id: int):
        """Update a place from the React detail popup."""
        body = await request.json()
        fields = ["name", "address", "notes", "url", "opening_hours", "city", "county", "region", "postcode", "visit_duration_mins", "image_url", "visit_photo_url", "hidden", "visit_date"]
        sets = []
        vals = []
        for f in fields:
            if f in body:
                sets.append(f"{f} = ?")
                vals.append(body[f] if body[f] is not None else None)
        if "visited" in body:
            sets.append("visited = ?")
            vals.append(1 if body["visited"] else 0)
            # When clearing visited, also clear date if not explicitly set
            if not body["visited"] and "visit_date" not in body:
                sets.append("visit_date = ?")
                vals.append(None)
        if not sets:
            return {"ok": True}
        vals.append(place_id)
        async with get_db() as db:
            await db.execute(
                f"UPDATE locations SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                vals,
            )
            await db.commit()
        return {"ok": True}


    @app.get("/api/places/{place_id}/itinerary")
    async def api_place_itinerary(place_id: int):
        """Return the cruise itinerary for a place (empty for normal places)."""
        from cruise import parse_itinerary, get_current_location, is_cruise_ship
        async with get_db() as db:
            row = await (await db.execute(
                """SELECT l.*, ct.name as category_type_name
                   FROM locations l
                   LEFT JOIN themes t ON t.id = l.theme_id
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE l.id = ?""",
                (place_id,),
            )).fetchone()
            if not row:
                raise HTTPException(status_code=404)
            loc = dict(row)
        itin = parse_itinerary(loc.get("itinerary_json"))
        current = get_current_location(loc)
        return {"itinerary": itin, "current": current, "is_cruise": is_cruise_ship(loc)}


    @app.post("/api/places/{place_id}/itinerary")
    async def api_place_itinerary_save(place_id: int, request: Request):
        """Save itinerary JSON for a cruise ship location."""
        from cruise import fill_at_sea_positions
        body = await request.json()
        itin = body.get("itinerary") or []
        if not isinstance(itin, list):
            raise HTTPException(status_code=400, detail="itinerary must be a list")
        itin = fill_at_sea_positions(itin)
        raw = json.dumps(itin)
        async with get_db() as db:
            await db.execute(
                "UPDATE locations SET itinerary_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (raw, place_id),
            )
            await db.commit()
        return {"ok": True, "itinerary": itin}


    @app.post("/api/places/{place_id}/itinerary/import")
    async def api_place_itinerary_import(place_id: int, request: Request):
        """Import itinerary from a cruise URL (best-effort parse + geocode)."""
        from cruise import extract_itinerary_from_html, geocode_port, fill_at_sea_positions
        body = await request.json()
        url = (body.get("url") or "").strip()
        if not url:
            raise HTTPException(status_code=400, detail="url required")
        # Fetch page
        html = ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TravelAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not fetch URL: {e}")
        days = extract_itinerary_from_html(html)
        if not days:
            raise HTTPException(status_code=422, detail="Could not extract itinerary from that page")
        # Geocode ports
        for d in days:
            if (d.get("status") or "") == "at_sea":
                continue
            geo = await geocode_port(d.get("port") or "")
            if geo.get("lat") is not None:
                d["location"] = {"lat": geo["lat"], "lon": geo["lon"]}
        days = fill_at_sea_positions(days)
        raw = json.dumps(days)
        async with get_db() as db:
            await db.execute(
                "UPDATE locations SET itinerary_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (raw, place_id),
            )
            await db.commit()
        return {"ok": True, "itinerary": days, "imported": len(days)}


    @app.get("/api/trips/{trip_id}/cruise")
    async def api_trip_cruise(trip_id: int):
        """Cruise ship + itinerary for this trip (locations are trip-specific)."""
        from cruise import parse_itinerary, get_current_location
        async with get_db() as db:
            row = await (await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))).fetchone()
            if not row:
                raise HTTPException(status_code=404)
            trip = dict(row)
            ship = None
            if trip.get("cruise_ship_id"):
                srow = await (await db.execute(
                    """SELECT l.*, ct.name as category_type_name
                       FROM locations l
                       LEFT JOIN themes t ON t.id = l.theme_id
                       LEFT JOIN category_types ct ON ct.id = t.category_type_id
                       WHERE l.id = ?""",
                    (trip["cruise_ship_id"],),
                )).fetchone()
                ship = dict(srow) if srow else None
        itin = parse_itinerary(trip.get("cruise_itinerary_json"))
        days = []
        if trip.get("cruise_id"):
            async with get_db() as db:
                rows = await (await db.execute(
                    "SELECT * FROM cruise_days WHERE cruise_id = ? ORDER BY day",
                    (trip["cruise_id"],),
                )).fetchall()
                days = [dict(r) for r in rows]
        current = None
        if itin:
            fake = {"itinerary_json": trip.get("cruise_itinerary_json"), "category_type_name": "Cruise ship"}
            current = get_current_location(fake)
        return {"ship": ship, "itinerary": itin, "days": days, "cruise_id": trip.get("cruise_id"), "current": current}


    @app.post("/api/trips/{trip_id}/cruise")
    async def api_trip_cruise_save(trip_id: int, request: Request):
        """Set the cruise ship and/or itinerary for this trip."""
        from cruise import fill_at_sea_positions
        body = await request.json()
        ship_id = body.get("cruise_ship_id")
        itin = body.get("itinerary")
        async with get_db() as db:
            sets, vals = [], []
            if ship_id is not None:
                sets.append("cruise_ship_id = ?")
                vals.append(ship_id or None)
            if itin is not None:
                if not isinstance(itin, list):
                    raise HTTPException(status_code=400, detail="itinerary must be a list")
                itin = fill_at_sea_positions(itin)
                sets.append("cruise_itinerary_json = ?")
                vals.append(json.dumps(itin))
            if sets:
                vals.append(trip_id)
                await db.execute(f"UPDATE trips SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
                await db.commit()
        return {"ok": True, "itinerary": itin}


    @app.post("/api/trips/{trip_id}/cruise/import")
    async def api_trip_cruise_import(trip_id: int, request: Request):
        """Import cruise itinerary from a URL into this trip."""
        from cruise import extract_itinerary_from_html, geocode_port, fill_at_sea_positions
        body = await request.json()
        url = (body.get("url") or "").strip()
        if not url:
            raise HTTPException(status_code=400, detail="url required")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TravelAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not fetch URL: {e}")
        days = extract_itinerary_from_html(html)
        if not days:
            raise HTTPException(status_code=422, detail="Could not extract itinerary from that page")
        # Align dates: cruise day 1 may not be trip day 1
        from cruise import assign_dates
        async with get_db() as db:
            trow = await (await db.execute("SELECT start_date FROM trips WHERE id = ?", (trip_id,))).fetchone()
            trip_start = (trow["start_date"] if trow else None) or body.get("trip_start")
            # Prefer explicit cruise start, then date extracted from the page, then trip start
            extracted = next((d.get("date") for d in days if d.get("day") == 1 and d.get("date")), None)
            cruise_start = body.get("cruise_start") or extracted or trip_start
            days = assign_dates(days, cruise_start=cruise_start, trip_start=trip_start)
            for d in days:
                if (d.get("status") or "") == "at_sea":
                    continue
                geo = await geocode_port(d.get("port") or "")
                if geo.get("lat") is not None:
                    d["location"] = {"lat": geo["lat"], "lon": geo["lon"]}
            days = fill_at_sea_positions(days)
            await db.execute(
                "UPDATE trips SET cruise_itinerary_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(days), trip_id),
            )
            await db.commit()
        return {"ok": True, "itinerary": days, "imported": len(days)}




    @app.get("/api/ships/{ship_id}/cruises")
    async def api_ship_cruises(ship_id: int):
        """Cruises (sailings) stored under a ship."""
        async with get_db() as db:
            rows = await (await db.execute(
                "SELECT * FROM cruises WHERE ship_id = ? ORDER BY year DESC, start_date",
                (ship_id,),
            )).fetchall()
        return {"cruises": [dict(r) for r in rows]}


    @app.get("/api/cruises/{cruise_id}")
    async def api_cruise_detail(cruise_id: int):
        """A sailing with its port days."""
        async with get_db() as db:
            row = await (await db.execute("SELECT * FROM cruises WHERE id = ?", (cruise_id,))).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Cruise not found")
            days = await (await db.execute(
                "SELECT * FROM cruise_days WHERE cruise_id = ? ORDER BY day",
                (cruise_id,),
            )).fetchall()
        return {"cruise": dict(row), "days": [dict(d) for d in days]}


    @app.post("/api/ships/{ship_id}/cruises/import")
    async def api_ship_cruise_import(ship_id: int, request: Request):
        """Import a sailing from a cruise URL and store it under the ship as CODE-YEAR."""
        from cruise import (
            extract_itinerary_from_html, extract_cruise_start, extract_cruise_code,
            extract_day_images, geocode_port, fill_at_sea_positions, assign_dates,
            extract_itinerary_from_seascanner, extract_seascanner_code,
        )
        from datetime import date as _date, timedelta
        body = await request.json()
        url = (body.get("url") or "").strip()
        if not url:
            raise HTTPException(status_code=400, detail="url required")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=25) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            msg = str(e)
            if "403" in msg:
                raise HTTPException(status_code=502, detail="P&O blocked the request (403). Set the departure date and try again, or the site is blocking the add-on.")
            raise HTTPException(status_code=502, detail=f"Could not fetch URL: {e}")
        is_sea = "seascanner.com" in url.lower()
        if is_sea:
            days = extract_itinerary_from_seascanner(html)
        else:
            days = extract_itinerary_from_html(html)
        if not days:
            raise HTTPException(status_code=422, detail="Could not extract itinerary from that page")
        plain = re.sub(r"<[^>]+>", " ", html)
        start = body.get("start_date") or (days[0].get("date") if is_sea else None) or extract_cruise_start(plain) or (days[0].get("date") if days else None)
        if not start:
            raise HTTPException(status_code=422, detail="Could not find a departure date. Set the cruise start date and try again.")
        year = int(str(start)[:4])
        code = (extract_seascanner_code(html, url) if is_sea else None) or extract_cruise_code(url) or body.get("code") or "CRUISE"
        days = assign_dates(days, cruise_start=start)
        images = extract_day_images(html)
        for d in days:
            if (d.get("status") or "") != "at_sea":
                geo = await geocode_port(d.get("port") or "")
                if geo.get("lat") is not None:
                    d["location"] = {"lat": geo["lat"], "lon": geo["lon"]}
            d["image_url"] = images.get(d["day"]) or ""
        days = fill_at_sea_positions(days)
        end = days[-1].get("date") if days else start
        async with get_db() as db:
            existing = await (await db.execute(
                "SELECT id FROM cruises WHERE ship_id = ? AND code = ? AND year = ?",
                (ship_id, code, year),
            )).fetchone()
            if existing:
                cruise_id = existing["id"]
                await db.execute(
                    "UPDATE cruises SET url = ?, start_date = ?, end_date = ?, name = ? WHERE id = ?",
                    (url, start, end, f"{code}-{year}", cruise_id),
                )
                await db.execute("DELETE FROM cruise_days WHERE cruise_id = ?", (cruise_id,))
            else:
                cur = await db.execute(
                    "INSERT INTO cruises (ship_id, code, year, name, url, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ship_id, code, year, f"{code}-{year}", url, start, end),
                )
                cruise_id = cur.lastrowid
            for d in days:
                loc = d.get("location") or {}
                await db.execute(
                    """INSERT INTO cruise_days (cruise_id, day, date, port, lat, lon, status, image_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (cruise_id, d["day"], d.get("date"), d.get("port"), loc.get("lat"), loc.get("lon"), d.get("status") or "port", d.get("image_url") or ""),
                )
            await db.commit()
        return {"ok": True, "cruise_id": cruise_id, "code": code, "year": year, "name": f"{code}-{year}", "start_date": start, "end_date": end, "days": days}


    @app.post("/api/trips/{trip_id}/use-cruise")
    async def api_trip_use_cruise(trip_id: int, request: Request):
        """Attach a sailing to a trip and set dates: start = cruise start - 1, end = disembarkation."""
        from datetime import date as _date, timedelta
        body = await request.json()
        cruise_id = body.get("cruise_id")
        if not cruise_id:
            raise HTTPException(status_code=400, detail="cruise_id required")
        async with get_db() as db:
            crow = await (await db.execute("SELECT * FROM cruises WHERE id = ?", (cruise_id,))).fetchone()
            if not crow:
                raise HTTPException(status_code=404, detail="Cruise not found")
            cruise = dict(crow)
            start = _date.fromisoformat(str(cruise["start_date"])[:10])
            end = _date.fromisoformat(str(cruise["end_date"])[:10]) if cruise.get("end_date") else start
            trip_start = (start - timedelta(days=1)).isoformat()
            trip_end = end.isoformat()
            await db.execute(
                "UPDATE trips SET cruise_id = ?, cruise_ship_id = ?, trip_type = 'cruise', start_date = ?, end_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (cruise_id, cruise["ship_id"], trip_start, trip_end, trip_id),
            )
            await db.commit()
        return {"ok": True, "start_date": trip_start, "end_date": trip_end, "cruise": cruise}



    def _parse_plan_locally(text: str) -> list:
        """Best-effort parse of a pasted plan: dates, Stop N, time, name, GPS."""
        from datetime import date as _date
        months = {m.lower(): i for i, m in enumerate(
            ["january","february","march","april","may","june","july","august","september","october","november","december"], 1)}
        current = None
        year = None
        stops = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            ym = re.search(r"(20\d{2})", line)
            if ym:
                year = ym.group(1)
            dm = re.search(r"(\d{1,2})\s+([A-Za-z]+)(?:\s+(20\d{2}))?", line)
            if dm and dm.group(2).lower() in months:
                y = dm.group(3) or year
                if y:
                    current = f"{y}-{months[dm.group(2).lower()]:02d}-{int(dm.group(1)):02d}"
            sm = re.match(r"Stop\s+\d+\s*[–-]\s*(\d{1,2}:\d{2})", line)
            if sm:
                time = sm.group(1)
                name = lines[i+1] if i + 1 < len(lines) else ""
                # name is the next non-meta line
                j = i + 1
                name = ""
                gps = None
                address = ""
                notes = []
                while j < len(lines) and not re.match(r"Stop\s+\d+", lines[j]) and not re.search(r"\d{1,2}\s+[A-Za-z]+", lines[j]):
                    l = lines[j]
                    gm = re.search(r"(\d{2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", l)
                    if gm:
                        gps = (float(gm.group(1)), float(gm.group(2)))
                    elif l.lower().startswith("address"):
                        address = l.split(":", 1)[-1].strip()
                    elif not name and not l.lower().startswith("gps") and not l.lower().startswith("allow"):
                        name = l
                    else:
                        notes.append(l)
                    j += 1
                if name:
                    stops.append({
                        "date": current,
                        "time": time,
                        "name": name.split("–")[0].strip(),
                        "lat": gps[0] if gps else None,
                        "lon": gps[1] if gps else None,
                        "address": address,
                        "notes": " ".join(notes)[:200],
                        "kind": "self_guided",
                    })
                i = j
                continue
            i += 1
        return stops


    async def lookup_activity(name: str, lat, lon) -> dict:
        """Find a short description, a picture, and a Google Maps link for an activity."""
        import urllib.parse
        info = {"description": "", "image_url": "", "maps_url": ""}
        if lat is not None and lon is not None:
            info["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        try:
            q = urllib.parse.quote(name)
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{q}"
            data = await asyncio.to_thread(_http_get_json, url)
            if isinstance(data, dict) and data.get("title"):
                info["description"] = (data.get("extract") or "")[:400]
                thumb = (data.get("thumbnail") or {}).get("source") or (data.get("originalimage") or {}).get("source")
                if thumb:
                    info["image_url"] = thumb
            if not info["description"]:
                search = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=1"
                found = await asyncio.to_thread(_http_get_json, search)
                hits = ((found or {}).get("query") or {}).get("search") or []
                if hits:
                    title = urllib.parse.quote(hits[0]["title"].replace(" ", "_"))
                    page = await asyncio.to_thread(_http_get_json, f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}")
                    if isinstance(page, dict):
                        info["description"] = (page.get("extract") or "")[:400]
                        thumb = (page.get("thumbnail") or {}).get("source")
                        if thumb:
                            info["image_url"] = thumb
        except Exception:
            pass
        return info

    @app.post("/api/trips/{trip_id}/import-activities")
    async def api_import_activities(trip_id: int, request: Request):
        """Parse a free-form activity plan with Grok, create places, return timed stops."""
        import json as _json
        body = await request.json()
        text = (body.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Paste an itinerary")
        key = grok_key()
        if not key:
            raise HTTPException(status_code=400, detail="Add your xAI API key in the add-on configuration")
        prompt = (
            "Extract every timed stop from this trip plan. Reply with JSON only, no markdown: "
            '{"stops":[{"date":"YYYY-MM-DD","time":"HH:MM","name":"","lat":0,"lon":0,"address":"","notes":"","kind":"self_guided"}]}. '
            "kind is self_guided or excursion. Use the GPS in the text. "
            "Dates must be real. Plan:\n" + text
        )
        try:
            payload = _json.dumps({"model": "grok-4.7", "messages": [{"role": "user", "content": prompt}]}).encode()
            req = urllib.request.Request(
                "https://api.x.ai/v1/chat/completions",
                data=payload,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = _json.loads(resp.read().decode())
            content_text = data["choices"][0]["message"]["content"]
            jm = re.search(r"\{.*\}", content_text, re.S)
            parsed = _json.loads(jm.group(0)) if jm else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", "ignore")[:400]
            parsed = {"stops": _parse_plan_locally(text), "_grok_error": str(e) + " " + err_body}
        except Exception as e:
            parsed = {"stops": _parse_plan_locally(text), "_grok_error": str(e)}
        stops_in = parsed.get("stops") or []
        if not stops_in:
            detail = parsed.get("_grok_error") or "No stops found in that plan"
            raise HTTPException(status_code=422, detail=detail)
        async with get_db() as db:
            trip = await (await db.execute("SELECT start_date FROM trips WHERE id = ?", (trip_id,))).fetchone()
            theme = await (await db.execute("SELECT id FROM themes WHERE lower(name) LIKE '%activ%' OR lower(name) LIKE '%sight%' ORDER BY id LIMIT 1")).fetchone()
            if not theme:
                cur = await db.execute(
                    "INSERT INTO themes (name, description, primary_color, icon_url) VALUES ('Activities', 'Imported trip activities', '#0d9488', '/static/react/activities-icon.svg')"
                )
                theme_id = cur.lastrowid
            else:
                theme_id = theme["id"]
            from datetime import date as _date
            trip_start = None
            start_src = body.get("start_date") or (trip["start_date"] if trip else None)
            if start_src:
                try:
                    trip_start = _date.fromisoformat(str(start_src)[:10])
                except Exception:
                    trip_start = None
            created = []
            for s in stops_in:
                name = (s.get("name") or "").strip()
                looked = {}
                if not name:
                    continue
                try:
                    lat = float(s["lat"]) if s.get("lat") not in (None, "") else None
                    lon = float(s["lon"]) if s.get("lon") not in (None, "") else None
                except (TypeError, ValueError):
                    lat = lon = None
                existing = await (await db.execute(
                    "SELECT id FROM locations WHERE lower(name) = lower(?) LIMIT 1", (name,)
                )).fetchone()
                if existing:
                    place_id = existing["id"]
                    if lat is not None:
                        await db.execute("UPDATE locations SET latitude = COALESCE(latitude, ?), longitude = COALESCE(longitude, ?) WHERE id = ?", (lat, lon, place_id))
                else:
                    cruise_row = await (await db.execute("SELECT id, name, code, year FROM cruises WHERE id = (SELECT cruise_id FROM trips WHERE id = ?)", (trip_id,))).fetchone()
                    cruise_label = (cruise_row["name"] if cruise_row else "") or ""
                    display = (cruise_label + " · " + name) if cruise_label else name
                    looked = await lookup_activity(name, lat, lon)
                    note = " ".join(p for p in [s.get("notes") or "", looked.get("description") or "", "[" + (s.get("kind") or "self_guided") + "]"] if p)
                    cur = await db.execute(
                        """INSERT INTO locations (theme_id, name, latitude, longitude, address, notes, url, image_url, visit_duration_mins, cruise_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 45, ?)""",
                        (theme_id, display, lat, lon, s.get("address") or "", note[:500], looked.get("maps_url") or "", looked.get("image_url") or "", cruise_row["id"] if cruise_row else None),
                    )
                    place_id = cur.lastrowid
                    name = display
                day_number = 1
                if trip_start and s.get("date"):
                    try:
                        from datetime import date as _date
                        day_number = (_date.fromisoformat(str(s["date"])[:10]) - trip_start).days + 1
                        if day_number < 1:
                            day_number = 1
                    except Exception:
                        day_number = 1
                created.append({
                    "location_id": place_id,
                    "day_number": day_number,
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "time": s.get("time") or "",
                    "notes": s.get("notes") or "",
                    "kind": s.get("kind") or "self_guided",
                    "image_url": looked.get("image_url") or "",
                    "maps_url": looked.get("maps_url") or "",
                    "is_accommodation": False,
                })
            await db.execute("UPDATE themes SET icon_url = '/static/react/activities-icon.svg' WHERE name = 'Activities' AND (icon_url IS NULL OR icon_url = '')")
            await db.commit()
        return {"ok": True, "stops": created, "count": len(created)}


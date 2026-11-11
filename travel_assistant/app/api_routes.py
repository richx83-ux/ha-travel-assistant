"""API routes for Travel Assistant (places, categories, cruise, commands, etc.)."""
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

# Injected by register_routes
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

def register_routes(_app, _templates, deps: dict):
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

    @app.post("/api/trips/{trip_id}/totals")
    async def api_trip_totals(trip_id: int, request: Request):
        body = await request.json()
        async with get_db() as db:
            await db.execute(
                "UPDATE trips SET summary_miles = ?, summary_travel_hrs = ?, summary_visit_hrs = ? WHERE id = ?",
                (body.get("miles"), body.get("travel_hrs"), body.get("visit_hrs"), trip_id),
            )
            await db.commit()
        return {"ok": True}


    async def _compute_trip_totals(db, trip_id: int) -> dict:
        """Same totals the summary shows: full route including start and finish."""
        from datetime import date as _date, timedelta
        trip = await (await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))).fetchone()
        if not trip:
            return {}
        trip = dict(trip)
        stops = [dict(r) for r in await (await db.execute(
            """SELECT s.day_number, s.is_hotel, s.location_id, l.latitude, l.longitude, l.visit_duration_mins
               FROM trip_stops s LEFT JOIN locations l ON l.id = s.location_id
               WHERE s.trip_id = ? ORDER BY s.day_number, s.sort_order, s.id""",
            (trip_id,),
        )).fetchall()]
        async def loc(pid):
            if not pid:
                return None
            row = await (await db.execute("SELECT latitude, longitude, visit_duration_mins FROM locations WHERE id = ?", (pid,))).fetchone()
            return dict(row) if row else None
        start_loc = await loc(trip.get("start_place_id"))
        finish_loc = await loc(trip.get("finish_place_id"))
        n = 1
        if trip.get("start_date") and trip.get("end_date"):
            try:
                n = max(1, (_date.fromisoformat(str(trip["end_date"])[:10]) - _date.fromisoformat(str(trip["start_date"])[:10])).days + 1)
            except Exception:
                n = 1
        cruise_days = {}
        if trip.get("cruise_id"):
            for r in await (await db.execute("SELECT date, lat, lon FROM cruise_days WHERE cruise_id = ?", (trip["cruise_id"],))).fetchall():
                cruise_days[r["date"]] = r
        miles = travel_min = visit_min = 0
        from trips_routes import osrm_leg_times
        for d in range(1, n + 1):
            day_stops = [s for s in stops if (s["day_number"] or 1) == d]
            activities = [s for s in day_stops if not s["is_hotel"]]
            dest = next((s for s in day_stops if s["is_hotel"]), None)
            prev = next((s for s in reversed([s for s in stops if (s["day_number"] or 1) == d - 1]) if s["is_hotel"]), None)
            seq = []
            if d == 1:
                seq.append(start_loc)
            elif trip.get("trip_type") == "cruise" and trip.get("start_date"):
                on = (_date.fromisoformat(str(trip["start_date"])[:10]) + timedelta(days=d - 1)).isoformat()
                cd = cruise_days.get(on)
                if cd and cd["lat"] is not None:
                    seq.append({"latitude": cd["lat"], "longitude": cd["lon"], "visit_duration_mins": 0})
                else:
                    seq.append(prev)
            else:
                seq.append(prev)
            seq.extend(activities)
            seq.append(dest)
            if d == n:
                seq.append(finish_loc)
            seq = [p for p in seq if p and p.get("latitude") is not None]
            if len(seq) >= 2:
                coords = [(p["latitude"], p["longitude"]) for p in seq]
                legs = await osrm_leg_times(coords)
                for leg in legs:
                    miles += (leg.get("distance_m") or 0) / 1609.344
                    travel_min += (leg.get("duration_secs") or 0) / 60
            for i, p in enumerate(seq):
                if i == 0:
                    continue
                visit_min += p.get("visit_duration_mins") or (0 if p.get("is_hotel") else 45)
        return {"miles": round(miles, 1), "travel_hrs": round(travel_min / 60, 1), "visit_hrs": round(visit_min / 60, 1)}

    @app.get("/api/trips")
    async def api_trips(request: Request):
        """JSON list of trips for the React UI."""
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM trips ORDER BY start_date DESC, name")
            trips = [dict(r) for r in await cursor.fetchall()]
            for t in trips:
                c = await db.execute("SELECT COUNT(*) as c FROM trip_stops WHERE trip_id = ?", (t["id"],))
                t["stop_count"] = (await c.fetchone())["c"] or 0
                active_day = t.get("active_day") or 1
                # Count done: explicitly completed/skipped, or on a day already finished
                done = await db.execute(
                    """SELECT COUNT(*) as c FROM trip_stops WHERE trip_id = ?
                       AND (completed_at IS NOT NULL OR skipped = 1 OR day_number < ?)""",
                    (t["id"], active_day),
                )
                t["done_count"] = (await done.fetchone())["c"] or 0
                days = await db.execute("SELECT COUNT(DISTINCT day_number) as c FROM trip_stops WHERE trip_id = ?", (t["id"],))
                t["total_days"] = (await days.fetchone())["c"] or 1
                t["active_day"] = active_day
                total = t["stop_count"] or 1
                t["progress"] = round(100 * t["done_count"] / total)
                skipped = await db.execute("SELECT COUNT(*) as c FROM trip_stops WHERE trip_id = ? AND skipped = 1", (t["id"],))
                t["skipped_count"] = (await skipped.fetchone())["c"] or 0
                # Count places on this trip that are actually visited
                completed = await db.execute(
                    """SELECT COUNT(*) as c FROM trip_stops s
                       JOIN locations l ON l.id = s.location_id
                       WHERE s.trip_id = ? AND l.visited = 1""",
                    (t["id"],),
                )
                t["completed_count"] = (await completed.fetchone())["c"] or 0
                totals = await db.execute(
                    "SELECT COALESCE(SUM(travel_from_prev_secs),0) as secs, COALESCE(SUM(distance_from_prev_m),0) as metres FROM trip_stops WHERE trip_id = ?",
                    (t["id"],),
                )
                row = await totals.fetchone()
                t["total_drive_secs"] = row["secs"] or 0
                t["total_miles"] = t.get("summary_miles") if t.get("summary_miles") else round((row["metres"] or 0) / 1609.344, 1)
                if t.get("summary_travel_hrs") is not None:
                    t["total_drive_secs"] = t["summary_travel_hrs"] * 3600
                visit = await db.execute(
                    """SELECT COALESCE(SUM(l.visit_duration_mins),0) as mins
                       FROM trip_stops s LEFT JOIN locations l ON l.id = s.location_id
                       WHERE s.trip_id = ? AND COALESCE(s.is_hotel,0) = 0""",
                    (t["id"],),
                )
                t["total_visit_mins"] = (t["summary_visit_hrs"] * 60) if t.get("summary_visit_hrs") else ((await visit.fetchone())["mins"] or 0)
                if t.get("start_date") and t.get("end_date"):
                    from datetime import date as _date
                    try:
                        a = _date.fromisoformat(str(t["start_date"])[:10])
                        b = _date.fromisoformat(str(t["end_date"])[:10])
                        t["n_days"] = max(1, (b - a).days + 1)
                    except Exception:
                        t["n_days"] = t["total_days"]
                else:
                    t["n_days"] = t["total_days"]
            await db.commit()
        return {"trips": trips}




    from fastapi.responses import Response
    import asyncio


    @app.post("/api/upload")
    async def api_upload(request: Request, file: UploadFile = File(...)):
        """Save an image and return its URL. Used by the shared uploader."""
        url = await save_upload(file)
        return {"ok": True, "url": url}


    @app.get("/api/library")
    async def api_library(request: Request):
        """Images with a count of where each is used."""
        async with get_db() as db:
            usage = {}
            def add(url, where):
                if not url:
                    return
                usage.setdefault(url, []).append(where)
            for row in await (await db.execute("SELECT id, name, image_url, visit_photo_url FROM locations")).fetchall():
                add(row["image_url"], f"place:{row['name']}")
                add(row["visit_photo_url"], f"visit:{row['name']}")
            for row in await (await db.execute("SELECT id, name, icon_url, default_image_url FROM themes")).fetchall():
                add(row["icon_url"], f"icon:{row['name']}")
                add(row["default_image_url"], f"default:{row['name']}")
            for row in await (await db.execute("SELECT id, name, image_url FROM trips")).fetchall():
                add(row["image_url"], f"trip:{row['name']}")
        files = list_assets()
        known = {f["url"] for f in files}
        items = []
        for f in files:
            used = usage.get(f["url"], [])
            items.append({"name": f["name"], "url": f["url"], "count": len(used), "used_by": used, "built_in": False})
        return {"images": items}

    @app.post("/api/library/delete")
    async def api_library_delete(request: Request):
        body = await request.json()
        url = body.get("url") or ""
        name = url.rsplit("/", 1)[-1]
        if not name or "/" in name or name.startswith("."):
            raise HTTPException(status_code=400, detail="Invalid image")
        path = UPLOAD_DIR / name
        if path.is_file():
            path.unlink()
        return {"ok": True}

    @app.post("/api/library/replace")
    async def api_library_replace(request: Request):
        body = await request.json()
        old = body.get("old") or ""
        new = body.get("new") or ""
        if not old or not new:
            raise HTTPException(status_code=400, detail="Need old and new")
        async with get_db() as db:
            for table, cols in (("locations", ("image_url", "visit_photo_url")), ("themes", ("icon_url", "default_image_url")), ("trips", ("image_url",))):
                for col in cols:
                    await db.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (new, old))
            await db.commit()
        return {"ok": True}

    @app.get("/api/uploads")
    async def api_uploads(request: Request):
        built_in = [
            {"name": "House", "url": "/static/react/house-icon.png"},
        ]
        return {"uploads": built_in + list_assets()}

    @app.get("/api/categories")
    async def api_categories(request: Request):
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT t.*, ct.name as category_type_name, COALESCE(ct.hide_visit_status, 0) as hide_visit_status, COALESCE(ct.hide_visit_status, 0) as hide_visit_status
                   FROM themes t
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE lower(t.name) != 'home'
                   ORDER BY t.name"""
            )
            cats = [dict(r) for r in await cursor.fetchall()]
            for c in cats:
                counts = await db.execute(
                    "SELECT COUNT(*) as total, SUM(CASE WHEN visited = 1 THEN 1 ELSE 0 END) as visited FROM locations WHERE theme_id = ?",
                    (c["id"],),
                )
                row = await counts.fetchone()
                c["total"] = row["total"] or 0
                c["visited"] = row["visited"] or 0
                c["percentage"] = round(100 * c["visited"] / c["total"]) if c["total"] else 0
            return {"categories": cats}

    @app.get("/api/categories/{category_id}")
    async def api_category_detail(request: Request, category_id: int):
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT t.*, ct.name as category_type_name, COALESCE(ct.hide_visit_status, 0) as hide_visit_status
                   FROM themes t
                   LEFT JOIN category_types ct ON ct.id = t.category_type_id
                   WHERE t.id = ?""",
                (category_id,),
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404)
            c = dict(row)
            counts = await db.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN visited = 1 THEN 1 ELSE 0 END) as visited FROM locations WHERE theme_id = ?",
                (category_id,),
            )
            r = await counts.fetchone()
            c["total"] = r["total"] or 0
            c["visited"] = r["visited"] or 0
            c["percentage"] = round(100 * c["visited"] / c["total"]) if c["total"] else 0
            return c


    @app.post("/api/command")
    async def api_command(request: Request):
        """Turn a natural language request into a plan."""
        import json as _json
        body = await request.json()
        text = (body.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Type a request")
        key = grok_key()
        if not key:
            raise HTTPException(status_code=400, detail="Add your xAI API key in the add-on configuration")
        async with get_db() as db:
            cats = [dict(r) for r in await (await db.execute("SELECT id, name FROM themes ORDER BY name")).fetchall()]
        prompt = (
            "You plan trips for a travel app. Today is " + date.today().isoformat() + ". "
            "Reply with JSON only, no markdown: "
            '{"trip":{"name":"","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","notes":""},'
            '"places":[{"name":"","postcode":"","city":"","category":"","is_accommodation":false,"notes":""}]}. '
            "Dates must be real. Use UK postcodes where you know them. "
            "Categories available: " + ", ".join(c["name"] for c in cats) + ". "
            "Request: " + text
        )
        try:
            payload = _json.dumps({"model": "grok-4.7", "messages": [{"role": "user", "content": prompt}]}).encode()
            req = urllib.request.Request(
                "https://api.x.ai/v1/chat/completions",
                data=payload,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = _json.loads(resp.read().decode())
            content_text = data["choices"][0]["message"]["content"]
            import re as _re
            jm = _re.search(r"\{.*\}", content_text, _re.S)
            plan = _json.loads(jm.group(0)) if jm else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            raise HTTPException(status_code=400, detail="Grok call failed: " + str(e) + " " + body)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Grok call failed: " + str(e))
        return {"ok": True, "plan": plan, "categories": cats}





    @app.get("/api/grok/status")
    async def api_grok_status():
        """Report whether an API key is configured, without revealing it."""
        key = grok_key()
        source = "none"
        ui = str(load_ui_settings().get("xai_api_key") or "").strip()
        opt = addon_option("xai_api_key")
        if ui and not ui.startswith("••••"):
            source = "settings"
        elif opt:
            source = "addon"
        return {
            "configured": bool(key),
            "source": source,
            "length": len(key) if key else 0,
            "prefix": (key[:4] + "…") if key and len(key) >= 4 else "",
        }


    @app.get("/api/trips/{trip_id}/plan")
    async def api_trip_plan_get(trip_id: int):
        async with get_db() as db:
            row = await (await db.execute("SELECT plan_json FROM trips WHERE id = ?", (trip_id,))).fetchone()
        if not row or not row["plan_json"]:
            return {"ok": True, "saved": False}
        try:
            data = json.loads(row["plan_json"])
        except Exception:
            data = {}
        return {"ok": True, "saved": True, "result": data.get("result") or {}, "raw": data.get("raw") or "", "prompt": data.get("prompt") or ""}


    @app.post("/api/trips/{trip_id}/plan/reset")
    async def api_trip_plan_reset(trip_id: int):
        async with get_db() as db:
            await db.execute("UPDATE trips SET plan_json = '' WHERE id = ?", (trip_id,))
            await db.commit()
        return {"ok": True}

    @app.post("/api/trips/{trip_id}/plan")
    async def api_trip_plan(trip_id: int, request: Request):
        """Build a packing/weather prompt from the trip and ask Grok for structured JSON."""
        import json as _json
        import re as _re
        from datetime import date as _date
        body = await request.json()
        custom_prompt = (body.get("prompt") or "").strip()
        key = grok_key()
        if not key:
            raise HTTPException(status_code=400, detail="Add your xAI API key in Settings → Appearance or the add-on configuration")
        async with get_db() as db:
            trip = await (await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))).fetchone()
            if not trip:
                raise HTTPException(status_code=404, detail="Trip not found")
            trip = dict(trip)
            store = [dict(r) for r in await (await db.execute(
                """SELECT i.id, i.name, i.category, c.name as clothing_type
                   FROM kit_items i
                   LEFT JOIN clothing_categories c ON c.id = i.clothing_category_id
                   WHERE i.bag_id IS NULL
                   ORDER BY i.category, i.name"""
            )).fetchall()]
            stops = [dict(r) for r in await (await db.execute(
                """SELECT s.day_number, s.is_hotel, l.name as location_name, l.city, l.country
                   FROM trip_stops s LEFT JOIN locations l ON l.id = s.location_id
                   WHERE s.trip_id = ? ORDER BY s.day_number, s.sort_order""",
                (trip_id,),
            )).fetchall()]
        # Derive destination from hotel stops or trip name
        dest_parts = []
        for s in stops:
            if s.get("is_hotel") and s.get("city"):
                dest_parts.append(s["city"])
            elif s.get("location_name"):
                dest_parts.append(s["location_name"])
        destination = ", ".join(dict.fromkeys([d for d in dest_parts if d])) or trip.get("name") or "the destination"
        start = trip.get("start_date") or ""
        end = trip.get("end_date") or ""
        notes = trip.get("notes") or ""
        by_day = {}
        for s in stops:
            d = s.get("day_number") or 1
            label = s.get("city") or s.get("location_name") or ""
            if not label:
                continue
            by_day.setdefault(d, [])
            if label not in by_day[d]:
                by_day[d].append(label)
        itinerary = "\n".join(
            f"Day {d}: {', '.join(by_day[d])}" for d in sorted(by_day)
        ) or "(no places on the trip)"
        store_lines = "\n".join(
            f'- id {s["id"]}: {s["name"]}' + (f' ({s["clothing_type"]})' if s.get("clothing_type") else '')
            for s in store
        ) or "(no loose items)"
        prompt = (
            f"Trip: {trip.get('name') or 'Trip'}, {start} to {end}. Places by day:\n{itinerary}\n"
            + (f"Notes: {notes}. " if notes else "")
            + "Loose store items (not in a bag):\n" + store_lines + "\n"
            + "For EACH item above, decide pack true or false for this trip and weather. "
            + "Everyday clothes and toiletries that fit the weather should be pack true. Electrolyte tablets must always be pack true. "
            + "Skip sunscreen, shorts, swimwear if under 12C. Skip hiking gear unless notes mention hiking. "
            + "Reply with JSON only: "
            + '{"weather":{"average_temp_c":0,"summary":"","forecast":[{"date":"YYYY-MM-DD","location":"city or port","high_c":0,"low_c":0,"conditions":""}]},'
            + '"store":[{"id":1,"name":"exact name","pack":true,"reason":"short"}],'
            + '"extra":[{"name":"","reason":""}]}. '
            + "Each forecast day must include the location from the places listed for that day, not the trip name. store must contain one entry per loose item, using the exact id and name. "
            + "extra must list 8 to 12 useful things NOT already in the store that are worth taking for this destination, dates, and weather. "
            + "Include practical extras such as an adaptor, rain layer, medications, copies of documents, a portable charger, and anything specific to the destination. Give a short reason for each."
        )
        try:
            payload = _json.dumps({
                "model": "grok-4.7",
                "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Reply with one JSON object only. No markdown. store must list every loose item with its exact id, name, and pack true or false."},
                    {"role": "user", "content": prompt},
                ],
            }).encode()
            def _call():
                req = urllib.request.Request(
                    "https://api.x.ai/v1/chat/completions",
                    data=payload,
                    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return _json.loads(resp.read().decode())
            data = await asyncio.to_thread(_call)
            content_text = data["choices"][0]["message"]["content"]
            result = {}
            try:
                jm = _re.search(r"\{.*\}", content_text, _re.S)
                if jm:
                    result = _json.loads(jm.group(0))
            except Exception:
                result = {}
            # Normalise store entries so the UI can tick them
            store_in = result.get("store") or result.get("items") or []
            norm = []
            for s in store_in:
                if not isinstance(s, dict):
                    continue
                pack = s.get("pack")
                if pack is None:
                    pack = s.get("recommend") or s.get("should_pack")
                pack_bool = pack in (True, 1, "true", "True", "yes", "Yes")
                norm.append({
                    "id": s.get("id"),
                    "name": s.get("name") or "",
                    "pack": pack_bool,
                    "reason": s.get("reason") or "",
                })
            result["store"] = norm
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "ignore")[:300]
            raise HTTPException(status_code=400, detail="Grok call failed: " + str(e) + " " + err)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Grok call failed: " + str(e))
        # Save against the trip so we don't need to call again
        async with get_db() as db:
            await db.execute(
                "UPDATE trips SET plan_json = ? WHERE id = ?",
                (_json.dumps({"result": result, "raw": content_text, "prompt": prompt}), trip_id),
            )
            await db.commit()
        return {"ok": True, "prompt": prompt, "result": result, "raw": content_text, "destination": destination, "start_date": start, "end_date": end}


    @app.post("/api/command/apply")
    async def api_command_apply(request: Request):
        """Create the places and trip from a confirmed plan."""
        body = await request.json()
        plan = body.get("plan") or {}
        trip = plan.get("trip") or {}
        places = plan.get("places") or []
        async with get_db() as db:
            cats = { (r["name"] or "").lower(): r["id"] for r in await (await db.execute("SELECT id, name FROM themes")).fetchall() }
            created = []
            for p in places:
                name = (p.get("name") or "").strip()
                if not name:
                    continue
                theme_id = cats.get((p.get("category") or "").lower())
                if not theme_id:
                    theme_id = next(iter(cats.values()), None)
                pc = (p.get("postcode") or "").strip()
                geo = await geocode_postcode(pc) if pc else {}
                cursor = await db.execute(
                    """INSERT INTO locations (theme_id, name, postcode, city, latitude, longitude, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (theme_id, name, pc, p.get("city") or "", geo.get("latitude"), geo.get("longitude"), p.get("notes") or ""),
                )
                created.append({"id": cursor.lastrowid, "is_accommodation": bool(p.get("is_accommodation"))})
            cursor = await db.execute(
                "INSERT INTO trips (name, start_date, end_date, notes) VALUES (?, ?, ?, ?)",
                (trip.get("name") or "New trip", trip.get("start_date") or "", trip.get("end_date") or "", trip.get("notes") or ""),
            )
            trip_id = cursor.lastrowid
            for i, c in enumerate(created):
                await db.execute(
                    "INSERT INTO trip_stops (trip_id, location_id, day_number, sort_order, is_hotel) VALUES (?, ?, 1, ?, ?)",
                    (trip_id, c["id"], i, 1 if c["is_accommodation"] else 0),
                )
            await db.commit()
        return {"ok": True, "trip_id": trip_id}

    @app.post("/api/categories")
    async def api_category_create(request: Request):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name required")
        async with get_db() as db:
            cursor = await db.execute(
                """INSERT INTO themes (name, description, primary_color, secondary_color, category_type_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, body.get("description") or "", body.get("primary_color") or "#0d9488",
                 body.get("secondary_color") or "#134e4a", body.get("category_type_id") or None),
            )
            await db.commit()
            return {"ok": True, "id": cursor.lastrowid}

    @app.post("/api/categories/{category_id}")
    async def api_category_update(request: Request, category_id: int):
        body = await request.json()
        fields = ["name", "description", "primary_color", "secondary_color", "icon_url", "default_image_url", "category_type_id", "is_active"]
        sets, vals = [], []
        for f in fields:
            if f in body:
                sets.append(f + " = ?")
                vals.append(body[f])
        if not sets:
            return {"ok": True}
        vals.append(category_id)
        async with get_db() as db:
            await db.execute(f"UPDATE themes SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
            await db.commit()
        return {"ok": True}




    @app.post("/api/categories/{category_id}/from-link")
    async def api_category_from_link(request: Request, category_id: int):
        """Create a place from a shared link. Best effort extraction."""
        import re
        from urllib.parse import urlparse, parse_qs, unquote
        body = await request.json()
        url = (body.get("url") or "").strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL required")
        name = ""
        postcode = ""
        city = ""
        notes = ""
        website = url
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        def looks_like_coords(s):
            return bool(re.match(r"^-?\d+(\.\d+)?[,\s]+-?\d+(\.\d+)?$", (s or "").strip()))
        if qs.get("q") and not looks_like_coords(unquote(qs["q"][0])):
            name = unquote(qs["q"][0]).replace("+", " ")
        text = ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; TravelAssistant/1.0)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                final = resp.geturl()
                website = final
                fqs = parse_qs(urlparse(final).query)
                if not name and fqs.get("q") and not looks_like_coords(unquote(fqs["q"][0])):
                    name = unquote(fqs["q"][0]).replace("+", " ")
                text = resp.read().decode("utf-8", "ignore")
            if not name:
                m = re.search(r'[?&]q=([^&"\']+)', text)
                if m and not looks_like_coords(unquote(m.group(1))):
                    name = unquote(m.group(1)).replace("+", " ")
            if not name:
                m = re.search(r"<title>([^<]+)</title>", text, re.I)
                if m:
                    name = re.sub(r"\s*[-|].*$", "", m.group(1)).strip()
            pm = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", text)
            if pm:
                postcode = pm.group(1)
        except Exception:
            pass
        grok_error = ""
        if not name or name.lower() in ("google search", "share.google") or looks_like_coords(name):
            key = grok_key()
            if not key:
                grok_error = "No API key found in the add-on configuration"
            else:
                try:
                    import json as _json
                    prompt = (
                        "A user shared this link to add a place. Identify the place. "
                        "Reply with JSON only, no markdown: "
                        '{"name":"","postcode":"","city":"","address":"","website":"","notes":""}. '
                        "Link: " + url + " Page text: " + (text[:3000] or "(none)")
                    )
                    payload = _json.dumps({
                        "model": "grok-4.7",
                        "messages": [{"role": "user", "content": prompt}],
                    }).encode()
                    req = urllib.request.Request(
                        "https://api.x.ai/v1/chat/completions",
                        data=payload,
                        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=40) as resp:
                        data = _json.loads(resp.read().decode())
                    content_text = data["choices"][0]["message"]["content"]
                    jm = re.search(r"\{.*\}", content_text, re.S)
                    if jm:
                        info = _json.loads(jm.group(0))
                        name = (info.get("name") or "").strip() or name
                        postcode = info.get("postcode") or postcode
                        city = info.get("city") or city
                        notes = info.get("notes") or notes
                        website = info.get("website") or website
                    else:
                        grok_error = "Grok reply had no place JSON"
                except Exception as e:
                    grok_error = "Grok call failed: " + str(e)
        if not name or name.lower() in ("google search", "share.google"):
            detail = "Could not read a name from that link"
            if grok_error:
                detail += ". " + grok_error
            raise HTTPException(status_code=400, detail=detail)
        geo = await geocode_postcode(postcode) if postcode else {}
        async with get_db() as db:
            cursor = await db.execute(
                """INSERT INTO locations (theme_id, name, postcode, city, latitude, longitude, url, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (category_id, name, postcode, city, geo.get("latitude"), geo.get("longitude"), website, notes),
            )
            await db.commit()
            images = []
            for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', text, re.I):
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = urllib.parse.urljoin(website, src)
                if src.startswith("http") and src not in images and not any(x in src.lower() for x in ["logo", "icon", "sprite", "pixel", "1x1"]):
                    images.append(src)
                if len(images) >= 10:
                    break
            og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', text, re.I)
            if og and og.group(1) not in images:
                images.insert(0, og.group(1))
            return {"ok": True, "id": cursor.lastrowid, "name": name, "postcode": postcode, "images": images[:10]}

    @app.post("/api/categories/{category_id}/places")
    async def api_category_add_place(request: Request, category_id: int):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name required")
        pc = (body.get("postcode") or "").strip()
        geo = await geocode_postcode(pc) if pc else {}
        lat = geo.get("latitude")
        lng = geo.get("longitude")
        city = (body.get("city") or "").strip()
        county = (body.get("county") or "").strip() or (geo.get("county") or "")
        region = geo.get("region") or ""
        country = (body.get("country") or "").strip() or (geo.get("country") or "")
        address = ", ".join([p for p in [city, county, pc] if p])
        async with get_db() as db:
            cursor = await db.execute(
                """INSERT INTO locations
                   (theme_id, name, latitude, longitude, postcode, city, county, region, country, address,
                    visit_duration_mins, notes, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (category_id, name, lat, lng, pc, city, county, region, country, address,
                 int(body.get("visit_duration_mins") or 60), body.get("notes") or "", body.get("url") or ""),
            )
            await db.commit()
            return {"ok": True, "id": cursor.lastrowid}

    @app.post("/api/categories/{category_id}/delete-places")
    async def api_category_delete_places(request: Request, category_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM locations WHERE theme_id = ?", (category_id,))
            await db.commit()
        return {"ok": True}

    @app.post("/api/categories/{category_id}/delete")
    async def api_category_delete(request: Request, category_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM locations WHERE theme_id = ?", (category_id,))
            await db.execute("DELETE FROM themes WHERE id = ?", (category_id,))
            await db.commit()
        return {"ok": True}

    @app.post("/api/categories/{category_id}/refresh")
    async def api_category_refresh(request: Request, category_id: int):
        locations = await get_locations(category_id)
        need = [loc for loc in locations if loc.get("postcode") and (
            not loc.get("region") or not loc.get("country") or not loc.get("county") or loc.get("latitude") is None
        )]
        geo = await geocode_postcodes_bulk([loc["postcode"] for loc in need])
        async with get_db() as db:
            for loc in need:
                pc = (loc.get("postcode") or "").strip()
                info = geo.get(pc.upper().replace(" ", "")) or geo.get(pc.upper()) or {}
                await db.execute(
                    """UPDATE locations SET latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude),
                       region = ?, country = ?, county = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (info.get("latitude"), info.get("longitude"), info.get("region") or loc.get("region") or "",
                     info.get("country") or loc.get("country") or "", info.get("county") or loc.get("county") or "", loc["id"]),
                )
            await db.commit()
        return {"ok": True, "updated": len(need)}




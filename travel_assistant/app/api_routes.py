"""API routes for Travel Assistant (places, categories, cruise, commands, etc.)."""
from __future__ import annotations

import asyncio
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

def register_routes(_app, _templates, deps: dict):
    global app, templates, get_db, save_upload, get_base, redirect
    global geocode_postcode, geocode_postcodes_bulk, geocode_place_name
    global grok_key, load_ui_settings, save_ui_settings, list_assets, seed_category_icons
    global _http_get_json, _http_post_json
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


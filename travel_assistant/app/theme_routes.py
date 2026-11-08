"""Theme, location, settings and achievements HTML routes for Travel Assistant."""
from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

# Injected
app = None
templates = None
get_db = None
save_upload = None
get_base = None
redirect = None
geocode_postcode = None
geocode_postcodes_bulk = None
geocode_place_name = None
list_assets = None
seed_category_icons = None
load_ui_settings = None
save_ui_settings = None
get_theme = None
get_theme_by_name = None
get_locations = None
get_theme_stats = None
sync_achievements = None
get_home_location = None
grok_key = None
DEFAULT_UI = None

def register_routes(_app, _templates, deps: dict):
    global app, templates, get_db, save_upload, get_base, redirect
    global geocode_postcode, geocode_postcodes_bulk, geocode_place_name
    global list_assets, seed_category_icons, load_ui_settings, save_ui_settings
    global get_theme, get_theme_by_name, get_locations, get_theme_stats, sync_achievements, get_home_location, grok_key, DEFAULT_UI
    app = _app
    templates = _templates
    get_db = deps["get_db"]
    save_upload = deps.get("save_upload")
    get_base = deps.get("get_base")
    redirect = deps.get("redirect")
    geocode_postcode = deps.get("geocode_postcode")
    geocode_postcodes_bulk = deps.get("geocode_postcodes_bulk")
    geocode_place_name = deps.get("geocode_place_name")
    list_assets = deps.get("list_assets")
    seed_category_icons = deps.get("seed_category_icons")
    load_ui_settings = deps.get("load_ui_settings")
    save_ui_settings = deps.get("save_ui_settings")
    get_theme = deps.get("get_theme")
    get_theme_by_name = deps.get("get_theme_by_name")
    get_locations = deps.get("get_locations")
    get_theme_stats = deps.get("get_theme_stats")
    sync_achievements = deps.get("sync_achievements")
    get_home_location = deps.get("get_home_location")
    grok_key = deps.get("grok_key")
    DEFAULT_UI = deps.get("DEFAULT_UI")

    # Old HTML dashboard removed; React SPA now serves at /

    @app.get("/api/settings")
    async def api_settings(request: Request):
        ui = load_ui_settings()
        # Prefer add-on option; mask the key in the response
        key = grok_key()
        ui["xai_api_key"] = ("••••" + key[-4:]) if key and len(key) > 4 else (key or "")
        ui["xai_api_key_set"] = bool(key)
        return {
            "ui": ui,
            "category_types": await list_category_types(),
            "home": await get_home_location(),
        }

    @app.post("/api/settings")
    async def api_settings_save(request: Request):
        body = await request.json()
        if body.get("reset"):
            save_ui_settings(DEFAULT_UI)
        else:
            current = load_ui_settings()
            for k in DEFAULT_UI:
                if k in body:
                    val = body[k]
                    # Ignore masked placeholder so we don't wipe a real key
                    if k == "xai_api_key" and isinstance(val, str) and val.startswith("••••"):
                        continue
                    current[k] = val
            save_ui_settings(current)
        ui = load_ui_settings()
        key = grok_key()
        ui["xai_api_key"] = ("••••" + key[-4:]) if key and len(key) > 4 else (key or "")
        ui["xai_api_key_set"] = bool(key)
        return {"ok": True, "ui": ui}

    @app.post("/api/category-types")
    async def api_category_type_create(request: Request):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if name:
            async with get_db() as db:
                await db.execute(
                    "INSERT OR IGNORE INTO category_types (name, sort_order) VALUES (?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM category_types))",
                    (name,),
                )
                await db.commit()
        return {"ok": True, "category_types": await list_category_types()}

    @app.post("/api/category-types/{type_id}")
    async def api_category_type_update(request: Request, type_id: int):
        body = await request.json()
        fields = ["name", "achievement_eligible", "exclude_from_counts", "exclude_from_places",
                  "exclude_from_maps", "hide_visit_status", "trip_role"]
        sets, vals = [], []
        for f in fields:
            if f in body:
                sets.append(f"{f} = ?")
                v = body[f]
                if f != "name" and f != "trip_role":
                    v = 1 if v else 0
                vals.append(v)
        if sets:
            vals.append(type_id)
            async with get_db() as db:
                await db.execute(f"UPDATE category_types SET {', '.join(sets)} WHERE id = ?", vals)
                await db.commit()
        return {"ok": True, "category_types": await list_category_types()}

    @app.post("/api/category-types/{type_id}/delete")
    async def api_category_type_delete(request: Request, type_id: int):
        async with get_db() as db:
            await db.execute("UPDATE themes SET category_type_id = NULL WHERE category_type_id = ?", (type_id,))
            await db.execute("DELETE FROM category_types WHERE id = ?", (type_id,))
            await db.commit()
        return {"ok": True}

    @app.post("/api/settings/home")
    async def api_settings_home(request: Request):
        body = await request.json()
        name = (body.get("name") or "Home").strip()
        postcode = (body.get("postcode") or "").strip()
        # Reuse existing home save by calling the form handler logic simply
        geo = await geocode_postcode(postcode) if postcode else {}
        async with get_db() as db:
            cursor = await db.execute("SELECT id FROM themes WHERE lower(name) = 'home' LIMIT 1")
            theme = await cursor.fetchone()
            theme_id = theme["id"] if theme else None
            if not theme_id:
                await db.execute("INSERT INTO themes (name, exclude_from_places, exclude_from_maps, hide_visit_status) VALUES ('Home', 0, 0, 1)")
                theme_id = (await db.execute("SELECT last_insert_rowid()")).fetchone()[0]
            else:
                await db.execute("UPDATE themes SET exclude_from_places = 0, exclude_from_maps = 0, hide_visit_status = 1 WHERE id = ?", (theme_id,))
            if body.get("icon_url") is not None:
                await db.execute("UPDATE themes SET icon_url = ? WHERE id = ?", (body.get("icon_url") or "", theme_id))
            if body.get("default_image_url") is not None:
                await db.execute("UPDATE themes SET default_image_url = ? WHERE id = ?", (body.get("default_image_url") or "", theme_id))
            cursor = await db.execute("SELECT id FROM locations WHERE theme_id = ? LIMIT 1", (theme_id,))
            row = await cursor.fetchone()
            if row:
                await db.execute(
                    "UPDATE locations SET name = ?, postcode = ?, latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude) WHERE id = ?",
                    (name, postcode, geo.get("latitude"), geo.get("longitude"), row["id"]),
                )
            else:
                # Find or create Home theme
                cursor = await db.execute("SELECT id FROM themes WHERE lower(name) = 'home' LIMIT 1")
                theme = await cursor.fetchone()
                theme_id = theme["id"] if theme else None
                if not theme_id:
                    await db.execute("INSERT INTO themes (name) VALUES ('Home')")
                    theme_id = (await db.execute("SELECT last_insert_rowid()")).fetchone()[0]
                await db.execute(
                    "INSERT INTO locations (name, postcode, theme_id) VALUES (?, ?, ?)",
                    (name, postcode, theme_id),
                )
            await db.commit()
        return {"ok": True, "home": await get_home_location()}

    @app.post("/settings/home")
    async def settings_home(request: Request, name: str = Form("Home"), postcode: str = Form(...)):
        from urllib.parse import quote
        info = await geocode_postcode(postcode)
        if info.get("latitude") is None:
            return redirect(request, f"/settings?home_error={quote('Postcode not found')}")
        async with get_db() as db:
            await db.execute(
                "INSERT OR IGNORE INTO category_types (name, sort_order) VALUES ('Home location', 0)"
            )
            cursor = await db.execute("SELECT id FROM category_types WHERE name = 'Home location'")
            type_id = (await cursor.fetchone())["id"]
            cursor = await db.execute("SELECT id FROM themes WHERE lower(name) = 'home'")
            theme = await cursor.fetchone()
            if theme:
                theme_id = theme["id"]
                await db.execute(
                    """UPDATE themes SET category_type_id = ?, is_system_theme = 1, achievement_eligible = 0,
                        exclude_from_counts = 1, exclude_from_places = 1 WHERE id = ?""",
                    (type_id, theme_id),
                )
            else:
                cursor = await db.execute(
                    """INSERT INTO themes (name, description, is_active, is_system_theme, achievement_eligible,
                        exclude_from_counts, exclude_from_places, category_type_id)
                       VALUES ('Home', 'Home location', 1, 1, 0, 1, 1, ?)""",
                    (type_id,),
                )
                theme_id = cursor.lastrowid
            cursor = await db.execute("SELECT id FROM locations WHERE theme_id = ?", (theme_id,))
            existing = await cursor.fetchone()
            values = (
                name.strip() or "Home", postcode.strip().upper(), info.get("county") or "",
                info.get("region") or "", info.get("country") or "United Kingdom",
                info["latitude"], info["longitude"], theme_id,
            )
            if existing:
                await db.execute(
                    """UPDATE locations SET name = ?, postcode = ?, county = ?, region = ?, country = ?,
                        latitude = ?, longitude = ?, visit_duration_mins = 0, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (*values, existing["id"]),
                )
            else:
                await db.execute(
                    """INSERT INTO locations (name, postcode, county, region, country, latitude, longitude,
                        theme_id, visit_duration_mins) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                    values,
                )
            await db.commit()
        return redirect(request, "/settings?home=1")


    async def get_home_location():
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT l.*, t.icon_url, t.default_image_url FROM locations l JOIN themes t ON t.id = l.theme_id
                   WHERE lower(t.name) = 'home' ORDER BY l.id LIMIT 1"""
            )
            row = await cursor.fetchone()
        return dict(row) if row else None


    @app.get("/settings/export")
    async def settings_export():
        async with get_db() as db:
            data = {"exported_at": date.today().isoformat()}
            for table in ("themes", "locations", "trips", "trip_stops", "category_types"):
                cursor = await db.execute(f"SELECT * FROM {table}")
                data[table] = [dict(r) for r in await cursor.fetchall()]
        data["ui_settings"] = load_ui_settings()
        body = json.dumps(data, indent=2, default=str)
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=travel-assistant-export.json"},
        )


    @app.post("/settings/upload")
    async def settings_upload(request: Request, image: UploadFile = File(...)):
        try:
            await save_upload(image)
        except HTTPException as e:
            return redirect(request, f"/settings?error={urllib.parse.quote(str(e.detail))}")
        except Exception as e:
            return redirect(request, f"/settings?error={urllib.parse.quote(str(e))}")
        return redirect(request, "/settings?upload=1")


    @app.post("/settings/category-type")
    async def category_type_create(request: Request, name: str = Form(...)):
        name = name.strip()
        if name:
            async with get_db() as db:
                await db.execute(
                    "INSERT OR IGNORE INTO category_types (name, sort_order) VALUES (?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM category_types))",
                    (name,),
                )
                await db.commit()
        return redirect(request, "/settings")


    @app.post("/settings/category-type/{type_id}/update")
    async def category_type_update(request: Request, type_id: int, name: str = Form(...)):
        name = name.strip()
        if name:
            async with get_db() as db:
                await db.execute("UPDATE category_types SET name = ? WHERE id = ?", (name, type_id))
                await db.commit()
        return redirect(request, "/settings")


    @app.post("/settings/category-type/{type_id}/delete")
    async def category_type_delete(request: Request, type_id: int):
        async with get_db() as db:
            await db.execute("UPDATE themes SET category_type_id = NULL WHERE category_type_id = ?", (type_id,))
            await db.execute("DELETE FROM category_types WHERE id = ?", (type_id,))
            await db.commit()
        return redirect(request, "/settings")


    @app.post("/settings/delete-asset")
    async def settings_delete_asset(request: Request, filename: str = Form(...)):
        safe = Path(filename).name
        path = UPLOAD_DIR / safe
        if path.exists() and path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXT:
            path.unlink()
        return redirect(request, "/settings")


    @app.post("/settings")
    async def settings_save(
        request: Request,
        bg_color: str = Form("#fafaf9"),
        sidebar_color: str = Form("#1e293b"),
        sidebar_text_color: str = Form("#e2e8f0"),
        sidebar_active_color: str = Form("#334155"),
        accent_color: str = Form("#14b8a6"),
        reset: Optional[str] = Form(None),
    ):
        form = await request.form()
        if form.get("reset") == "1":
            save_ui_settings(DEFAULT_UI)
        else:
            save_ui_settings({
                "bg_color": bg_color.strip(),
                "sidebar_color": sidebar_color.strip(),
                "sidebar_text_color": sidebar_text_color.strip(),
                "sidebar_active_color": sidebar_active_color.strip(),
                "accent_color": accent_color.strip(),
            })
        return redirect(request, "/settings?saved=1")


    @app.post("/theme/new")
    async def theme_create(
        request: Request,
        name: str = Form(...),
        description: str = Form(""),
        primary_color: str = Form("#0d9488"),
        secondary_color: str = Form("#134e4a"),
        icon_url: str = Form(""),
        default_image_url: str = Form(""),
        is_active: Optional[str] = Form(None),
        exclude_from_counts: Optional[str] = Form(None),
        exclude_from_places: Optional[str] = Form(None),
        exclude_from_maps: Optional[str] = Form(None),
        hide_visit_status: Optional[str] = Form(None),
        is_system_theme: Optional[str] = Form(None),
        achievement_eligible: Optional[str] = Form(None),
        category_type_id: str = Form(""),
        icon_file: Optional[UploadFile] = File(None),
        default_image_file: Optional[UploadFile] = File(None),
    ):
        active = 1 if is_active == "on" else 0
        pc = primary_color.strip() or "#0d9488"
        sc = secondary_color.strip() or "#134e4a"
        icon = icon_url.strip()
        def_img = default_image_url.strip()
        try:
            if icon_file and icon_file.filename:
                icon = await save_upload(icon_file)
            if default_image_file and default_image_file.filename:
                def_img = await save_upload(default_image_file)
        except HTTPException as e:
            return redirect(request, f"/theme/new?error={urllib.parse.quote(str(e.detail))}")
        type_id = int(category_type_id) if str(category_type_id).isdigit() else None
        # Apply type defaults; individual flags only override if explicitly sent
        ex_c = 1 if exclude_from_counts == "on" else 0
        ex_p = 1 if exclude_from_places == "on" else 0
        ex_m = 1 if exclude_from_maps == "on" else 0
        hide_v = 1 if hide_visit_status == "on" else 0
        sys_t = 1 if is_system_theme == "on" else 0
        ach = 1 if achievement_eligible == "on" else 0
        if type_id:
            async with get_db() as db:
                row = await (await db.execute("SELECT * FROM category_types WHERE id = ?", (type_id,))).fetchone()
                if row:
                    r = dict(row)
                    # Prefer type defaults unless the form explicitly checked an override box
                    # For this first pass we always apply type defaults (checkboxes become optional overrides later)
                    ex_c = r.get("exclude_from_counts", ex_c)
                    ex_p = r.get("exclude_from_places", ex_p)
                    ex_m = r.get("exclude_from_maps", ex_m)
                    hide_v = r.get("hide_visit_status", hide_v)
                    ach = r.get("achievement_eligible", ach)
        async with get_db() as db:
            cursor = await db.execute(
                """INSERT INTO themes (
                    name, description, primary_color, secondary_color, is_active,
                    icon_url, default_image_url,
                    exclude_from_counts, exclude_from_places, exclude_from_maps,
                    hide_visit_status, is_system_theme, achievement_eligible, category_type_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name.strip(), description.strip(), pc, sc, active, icon, def_img, ex_c, ex_p, ex_m, hide_v, sys_t, ach, type_id),
            )
            await db.commit()
            theme_id = cursor.lastrowid
        return redirect(request, f"/theme/{theme_id}")


    @app.post("/import/csv")
    async def import_csv(
        request: Request,
        file: UploadFile = File(None),
        paste: str = Form(""),
        theme_name: str = Form("English Heritage"),
    ):
        raw = await file.read() if file and file.filename else b""
        filename = (file.filename or "").lower() if file else ""
        if not raw and paste.strip():
            raw = paste.encode("utf-8")
            filename = "paste.csv"
        if not raw:
            raise HTTPException(status_code=400, detail="Choose a file or paste the CSV text")
        if filename.endswith(".xlsx"):
            try:
                import openpyxl
            except ImportError:
                raise HTTPException(status_code=400, detail="Excel support not installed")
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            headers = [str(h).strip() if h is not None else "" for h in next(rows_iter, [])]
            all_rows = []
            for row in rows_iter:
                if not any(row):
                    continue
                all_rows.append({headers[i]: ("" if row[i] is None else str(row[i]).strip()) for i in range(len(headers))})
            fieldmap = {h.lower().strip().replace("_", " "): h for h in headers if h}
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames:
                raise HTTPException(status_code=400, detail="Invalid CSV")
            fieldmap = {h.lower().strip().replace("_", " "): h for h in reader.fieldnames}
            all_rows = list(reader)
        if not fieldmap:
            raise HTTPException(status_code=400, detail="No columns found")

        def col(*names):
            for n in names:
                if n in fieldmap:
                    return fieldmap[n]
            return None

        name_col = col("name", "location name", "location", "site", "site name")
        lat_col = col("latitude", "lat")
        lng_col = col("longitude", "lng", "lon")
        operator_col = col("operator")
        availability_col = col("availability")
        if not name_col:
            raise HTTPException(status_code=400, detail="CSV must have a name column")
        postcode_col = col("postcode", "post_code", "zip")
        city_col = col("city", "town")
        county_col = col("county")
        address_col = col("address", "street")
        notes_col = col("notes", "description")
        url_col = col("url", "website", "link", "official tesla url", "official url", "tesla url")
        image_col = col("image_url", "image", "photo")
        theme_col = col("theme")
        type_col = col("type")
        amenities_col = col("amenities")
        parking_col = col("car park status", "parking", "parking status")
        alt_url_col = col("supercharge.info url", "supercharge url")
        status_col = col("status")
        stalls_col = col("stalls")
        power_col = col("power (kw)", "power", "power_kw")

        if not all_rows:
            raise HTTPException(status_code=400, detail="CSV has no data rows")
        if theme_col and all_rows[0].get(theme_col):
            theme_name = all_rows[0].get(theme_col) or theme_name
        theme_name = (theme_name or "Imported").strip()

        theme = await get_theme_by_name(theme_name)
        if not theme:
            async with get_db() as db:
                cursor = await db.execute(
                    "INSERT INTO themes (name, description) VALUES (?, ?)",
                    (theme_name, f"Imported from {file.filename or 'CSV'}"),
                )
                await db.commit()
                theme_id = cursor.lastrowid
        else:
            theme_id = theme["id"]

        existing = await get_locations(theme_id)
        existing_names = {loc["name"].strip().lower() for loc in existing}
        rows = []
        for r in all_rows:
            name = (r.get(name_col) or "").strip()
            if not name or name.lower() in existing_names:
                continue
            rows.append(r)

        postcodes = [(r.get(postcode_col) or "").strip() if postcode_col else "" for r in rows]
        geo = await geocode_postcodes_bulk(postcodes) if any(postcodes) else {}

        prepared = []
        for r in rows:
            name = (r.get(name_col) or "").strip()
            postcode = (r.get(postcode_col) or "").strip() if postcode_col else ""
            city = (r.get(city_col) or "").strip() if city_col else ""
            county = (r.get(county_col) or "").strip() if county_col else ""
            notes = (r.get(notes_col) or "").strip() if notes_col else ""
            url = (r.get(url_col) or "").strip() if url_col else ""
            image_url = (r.get(image_col) or "").strip() if image_col else ""
            address_raw = (r.get(address_col) or "").strip() if address_col else ""

            note_bits = []
            if notes:
                note_bits.append(notes)
            if status_col and (r.get(status_col) or "").strip():
                note_bits.append("Status: " + (r.get(status_col) or "").strip())
            if type_col and (r.get(type_col) or "").strip():
                note_bits.append((r.get(type_col) or "").strip())
            if stalls_col and (r.get(stalls_col) or "").strip():
                note_bits.append("Stalls: " + (r.get(stalls_col) or "").strip())
            if power_col and (r.get(power_col) or "").strip():
                note_bits.append("Power: " + (r.get(power_col) or "").strip() + " kW")
            if parking_col and (r.get(parking_col) or "").strip():
                note_bits.append("Parking: " + (r.get(parking_col) or "").strip())
            if amenities_col and (r.get(amenities_col) or "").strip():
                note_bits.append("Amenities: " + (r.get(amenities_col) or "").strip())
            if alt_url_col and (r.get(alt_url_col) or "").strip():
                note_bits.append("Map: " + (r.get(alt_url_col) or "").strip())
            if operator_col and (r.get(operator_col) or "").strip():
                note_bits.append("Operator: " + (r.get(operator_col) or "").strip())
            if availability_col and (r.get(availability_col) or "").strip():
                note_bits.append("Availability: " + (r.get(availability_col) or "").strip())
            notes = "\n".join(note_bits)
            if not city and address_raw:
                city = address_raw.split(",")[0].strip()

            lat = lng = None
            if lat_col and lng_col and r.get(lat_col) and r.get(lng_col):
                try:
                    lat = float(r.get(lat_col))
                    lng = float(r.get(lng_col))
                except ValueError:
                    lat = lng = None
            key1 = postcode.upper().replace(" ", "")
            key2 = postcode.upper()
            info = geo.get(key1) or geo.get(key2) or {}
            if lat is None:
                lat = info.get("latitude")
                lng = info.get("longitude")
            region = info.get("region") or ""
            country = info.get("country") or "United Kingdom"
            if not county:
                county = info.get("county") or ""

            if lat is None or lng is None:
                place_info = await geocode_place_name(name)
                lat = place_info.get("latitude")
                lng = place_info.get("longitude")
                if not region:
                    region = place_info.get("region") or ""
                if not country:
                    country = place_info.get("country") or ""
                if not county:
                    county = place_info.get("county") or ""
                if not city:
                    city = place_info.get("city") or ""
                await asyncio.sleep(1.1)

            if address_raw:
                address = address_raw
            else:
                address = ", ".join([p for p in [city, county, postcode] if p])

            prepared.append((
                theme_id, name, lat, lng, postcode, city, county,
                region, country, address, notes, url, image_url,
            ))

        async with get_db() as db:
            await db.executemany(
                """INSERT INTO locations
                   (theme_id, name, latitude, longitude, postcode, city, county,
                    region, country, address, notes, url, image_url, visited, visit_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)""",
                prepared,
            )
            await db.commit()
        return redirect(request, f"/theme/{theme_id}")


    @app.post("/theme/{theme_id}/refresh-regions")
    async def refresh_regions(request: Request, theme_id: int):
        theme = await get_theme(theme_id)
        if not theme:
            raise HTTPException(status_code=404, detail="Theme not found")
        locations = await get_locations(theme_id)
        need = [loc for loc in locations if loc.get("postcode") and (
            not loc.get("region") or not loc.get("country")
            or not loc.get("county") or loc.get("latitude") is None
        )]
        postcodes = [loc["postcode"] for loc in need]
        geo = await geocode_postcodes_bulk(postcodes)
        async with get_db() as db:
            for loc in need:
                pc = (loc.get("postcode") or "").strip()
                key1 = pc.upper().replace(" ", "")
                key2 = pc.upper()
                info = geo.get(key1) or geo.get(key2) or {}
                await db.execute(
                    """UPDATE locations SET
                        latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude),
                        region = ?, country = ?, county = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (info.get("latitude"), info.get("longitude"),
                     info.get("region") or loc.get("region") or "",
                     info.get("country") or loc.get("country") or "United Kingdom",
                     info.get("county") or loc.get("county") or "",
                     loc["id"]),
                )
            await db.commit()
        return redirect(request, f"/theme/{theme_id}")


    @app.post("/theme/{theme_id}/edit")
    async def theme_update(
        request: Request,
        theme_id: int,
        name: str = Form(...),
        description: str = Form(""),
        primary_color: str = Form("#0d9488"),
        secondary_color: str = Form("#134e4a"),
        icon_url: str = Form(""),
        default_image_url: str = Form(""),
        is_active: Optional[str] = Form(None),
        exclude_from_counts: Optional[str] = Form(None),
        exclude_from_places: Optional[str] = Form(None),
        exclude_from_maps: Optional[str] = Form(None),
        hide_visit_status: Optional[str] = Form(None),
        is_system_theme: Optional[str] = Form(None),
        achievement_eligible: Optional[str] = Form(None),
        category_type_id: str = Form(""),
        icon_file: Optional[UploadFile] = File(None),
        default_image_file: Optional[UploadFile] = File(None),
    ):
        active = 1 if is_active == "on" else 0
        pc = primary_color.strip() or "#0d9488"
        sc = secondary_color.strip() or "#134e4a"
        icon = icon_url.strip()
        def_img = default_image_url.strip()
        try:
            if icon_file and icon_file.filename:
                icon = await save_upload(icon_file)
            if default_image_file and default_image_file.filename:
                def_img = await save_upload(default_image_file)
        except HTTPException as e:
            return redirect(request, f"/theme/{theme_id}/edit?error={urllib.parse.quote(str(e.detail))}")
        type_id = int(category_type_id) if str(category_type_id).isdigit() else None
        ex_c = 1 if exclude_from_counts == "on" else 0
        ex_p = 1 if exclude_from_places == "on" else 0
        ex_m = 1 if exclude_from_maps == "on" else 0
        hide_v = 1 if hide_visit_status == "on" else 0
        sys_t = 1 if is_system_theme == "on" else 0
        ach = 1 if achievement_eligible == "on" else 0
        if type_id:
            async with get_db() as db:
                row = await (await db.execute("SELECT * FROM category_types WHERE id = ?", (type_id,))).fetchone()
                if row:
                    r = dict(row)
                    ex_c = r.get("exclude_from_counts", ex_c)
                    ex_p = r.get("exclude_from_places", ex_p)
                    ex_m = r.get("exclude_from_maps", ex_m)
                    hide_v = r.get("hide_visit_status", hide_v)
                    ach = r.get("achievement_eligible", ach)
        async with get_db() as db:
            await db.execute(
                """UPDATE themes SET name = ?, description = ?,
                    primary_color = ?, secondary_color = ?, is_active = ?,
                    icon_url = ?, default_image_url = ?,
                    exclude_from_counts = ?, exclude_from_places = ?, exclude_from_maps = ?,
                    hide_visit_status = ?, is_system_theme = ?, achievement_eligible = ?, category_type_id = ?,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (name.strip(), description.strip(), pc, sc, active, icon, def_img, ex_c, ex_p, ex_m, hide_v, sys_t, ach, type_id, theme_id),
            )
            await db.commit()
        return redirect(request, f"/theme/{theme_id}")


    @app.post("/theme/{theme_id}/delete-places")
    async def theme_delete_places(request: Request, theme_id: int):
        theme = await get_theme(theme_id)
        if not theme:
            raise HTTPException(status_code=404, detail="Theme not found")
        async with get_db() as db:
            await db.execute("DELETE FROM locations WHERE theme_id = ?", (theme_id,))
            await db.commit()
        return redirect(request, f"/theme/{theme_id}/edit")


    @app.post("/theme/{theme_id}/delete")
    async def theme_delete(request: Request, theme_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM locations WHERE theme_id = ?", (theme_id,))
            await db.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
            await db.commit()
        return redirect(request, "/themes")


    @app.post("/theme/{theme_id}/location/new")
    async def location_create(
        request: Request, theme_id: int,
        name: str = Form(...), postcode: str = Form(""), city: str = Form(""), county: str = Form(""),
        country: str = Form(""),
        visit_duration_mins: int = Form(60), opening_hours: str = Form(""), notes: str = Form(""),
        url: str = Form(""), visited: Optional[str] = Form(None), visit_date: Optional[str] = Form(None),
    ):
        is_visited = 1 if visited == "on" else 0
        vdate = visit_date if is_visited and visit_date else None
        pc = postcode.strip()
        geo = await geocode_postcode(pc)
        lat, lng = geo.get("latitude"), geo.get("longitude")
        region = geo.get("region") or ""
        ctry = country.strip() or (geo.get("country") or "")
        cty = county.strip() or (geo.get("county") or "")
        address = ", ".join([p for p in [city.strip(), cty, pc] if p])
        async with get_db() as db:
            await db.execute(
                """INSERT INTO locations
                   (theme_id, name, latitude, longitude, postcode, city, county,
                    region, country, address, visit_duration_mins, opening_hours, notes, url,
                    visited, visit_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (theme_id, name.strip(), lat, lng, pc, city.strip(), cty, region, ctry, address,
                 visit_duration_mins, opening_hours.strip(), notes.strip(), url.strip(), is_visited, vdate),
            )
            await db.commit()
        return redirect(request, f"/theme/{theme_id}")


    @app.post("/theme/{theme_id}/location/{loc_id}/edit")
    async def location_update(
        request: Request, theme_id: int, loc_id: int,
        name: str = Form(...), postcode: str = Form(""), city: str = Form(""), county: str = Form(""),
        country: str = Form(""),
        visit_duration_mins: int = Form(60), opening_hours: str = Form(""), notes: str = Form(""),
        url: str = Form(""), visited: Optional[str] = Form(None), visit_date: Optional[str] = Form(None),
    ):
        is_visited = 1 if visited == "on" else 0
        vdate = visit_date if is_visited and visit_date else None
        pc = postcode.strip()
        geo = await geocode_postcode(pc)
        lat, lng = geo.get("latitude"), geo.get("longitude")
        region = geo.get("region") or ""
        ctry = country.strip() or (geo.get("country") or "")
        cty = county.strip() or (geo.get("county") or "")
        address = ", ".join([p for p in [city.strip(), cty, pc] if p])
        async with get_db() as db:
            await db.execute(
                """UPDATE locations SET name = ?, latitude = ?, longitude = ?, postcode = ?,
                    city = ?, county = ?, region = ?, country = ?, address = ?,
                    visit_duration_mins = ?, opening_hours = ?, notes = ?, url = ?,
                    visited = ?, visit_date = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND theme_id = ?""",
                (name.strip(), lat, lng, pc, city.strip(), cty, region, ctry, address,
                 visit_duration_mins, opening_hours.strip(), notes.strip(), url.strip(),
                 is_visited, vdate, loc_id, theme_id),
            )
            await db.commit()
        return redirect(request, f"/theme/{theme_id}")


    @app.post("/theme/{theme_id}/location/{loc_id}/delete")
    async def location_delete(request: Request, theme_id: int, loc_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM locations WHERE id = ? AND theme_id = ?", (loc_id, theme_id))
            await db.commit()
        return redirect(request, f"/theme/{theme_id}")


    @app.post("/theme/{theme_id}/location/{loc_id}/toggle_visited")
    async def toggle_visited(request: Request, theme_id: int, loc_id: int):
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT visited FROM locations WHERE id = ? AND theme_id = ?", (loc_id, theme_id)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404)
            new_visited = 0 if row["visited"] else 1
            vdate = date.today().isoformat() if new_visited else None
            await db.execute(
                "UPDATE locations SET visited = ?, visit_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_visited, vdate, loc_id),
            )
            await db.commit()
        return redirect(request, f"/theme/{theme_id}")

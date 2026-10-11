"""
Travel Assistant - Home Assistant Add-on
Theme & Places admin with visit tracking
"""

import os
import csv
import io
import json
import asyncio
import urllib.request
import urllib.parse
from datetime import date
from typing import Optional
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import aiosqlite

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "travel_assistant.db"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Travel Assistant")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_base(request: Request) -> str:
    return request.headers.get("x-ingress-path", "").rstrip("/")


def redirect(request: Request, path: str) -> RedirectResponse:
    base = get_base(request)
    if not path.startswith("/"):
        path = "/" + path
    return RedirectResponse(url=f"{base}{path}", status_code=303)


def _http_get_json(url: str, timeout: float = 10.0) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TravelAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _http_post_json(url: str, payload: dict, timeout: float = 30.0) -> Optional[dict]:
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": "TravelAssistant/1.0",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


async def geocode_postcode(postcode: str) -> dict:
    empty = {"latitude": None, "longitude": None, "region": None, "district": None, "county": None}
    if not postcode or not postcode.strip():
        return empty
    pc = postcode.strip().replace(" ", "")
    url = f"https://api.postcodes.io/postcodes/{urllib.parse.quote(pc)}"
    result = await asyncio.to_thread(_http_get_json, url)
    if not result or result.get("status") != 200:
        return empty
    r = result.get("result") or {}
    return {
        "latitude": r.get("latitude"),
        "longitude": r.get("longitude"),
        "region": r.get("region") or r.get("european_electoral_region"),
        "district": r.get("admin_district"),
        "county": r.get("admin_county") or r.get("admin_district"),
    }


async def geocode_postcodes_bulk(postcodes: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    clean = [pc.strip() for pc in postcodes if pc and pc.strip()]
    for i in range(0, len(clean), 100):
        batch = clean[i : i + 100]
        result = await asyncio.to_thread(
            _http_post_json,
            "https://api.postcodes.io/postcodes",
            {"postcodes": batch},
        )
        if not result or result.get("status") != 200:
            continue
        for item in result.get("result") or []:
            query = item.get("query")
            res = item.get("result")
            if query and res:
                info = {
                    "latitude": res.get("latitude"),
                    "longitude": res.get("longitude"),
                    "region": res.get("region") or res.get("european_electoral_region"),
                    "district": res.get("admin_district"),
                    "county": res.get("admin_county") or res.get("admin_district"),
                }
                out[query.upper().replace(" ", "")] = info
                out[query.strip().upper()] = info
    return out


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def migrate_db(db: aiosqlite.Connection):
    cursor = await db.execute("PRAGMA table_info(locations)")
    cols = {row[1] for row in await cursor.fetchall()}
    for col, typedef in [
        ("postcode", "TEXT DEFAULT ''"),
        ("city", "TEXT DEFAULT ''"),
        ("county", "TEXT DEFAULT ''"),
        ("region", "TEXT DEFAULT ''"),
        ("district", "TEXT DEFAULT ''"),
        ("url", "TEXT DEFAULT ''"),
        ("image_url", "TEXT DEFAULT ''"),
    ]:
        if col not in cols:
            await db.execute(f"ALTER TABLE locations ADD COLUMN {col} {typedef}")

    cursor = await db.execute("PRAGMA table_info(themes)")
    tcols = {row[1] for row in await cursor.fetchall()}
    for col, typedef in [
        ("primary_color", "TEXT DEFAULT '#0d9488'"),
        ("secondary_color", "TEXT DEFAULT '#134e4a'"),
        ("is_active", "INTEGER DEFAULT 1"),
    ]:
        if col not in tcols:
            await db.execute(f"ALTER TABLE themes ADD COLUMN {col} {typedef}")


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                primary_color TEXT DEFAULT '#0d9488',
                secondary_color TEXT DEFAULT '#134e4a',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                postcode TEXT DEFAULT '',
                city TEXT DEFAULT '',
                county TEXT DEFAULT '',
                region TEXT DEFAULT '',
                district TEXT DEFAULT '',
                address TEXT DEFAULT '',
                visit_duration_mins INTEGER DEFAULT 60,
                opening_hours TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                url TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                visited INTEGER DEFAULT 0,
                visit_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (theme_id) REFERENCES themes (id) ON DELETE CASCADE
            )
        """)
        await migrate_db(db)
        await db.commit()


@app.on_event("startup")
async def startup():
    await init_db()


async def get_theme(theme_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM themes WHERE id = ?", (theme_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_theme_by_name(name: str):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM themes WHERE lower(name) = lower(?)", (name.strip(),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_locations(theme_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM locations WHERE theme_id = ? ORDER BY name",
            (theme_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_theme_stats(theme_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN visited = 1 THEN 1 ELSE 0 END) as visited_count
            FROM locations WHERE theme_id = ?
            """,
            (theme_id,)
        )
        row = await cursor.fetchone()
        total = row["total"] or 0
        visited = row["visited_count"] or 0
        pct = round((visited / total * 100) if total > 0 else 0)
        return {"total": total, "visited": visited, "percent": pct}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM themes ORDER BY name")
        themes = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN visited = 1 THEN 1 ELSE 0 END) as visited_count
            FROM locations
            """
        )
        row = await cursor.fetchone()
        total_places = row["total"] or 0
        visited_places = row["visited_count"] or 0

        month_prefix = date.today().strftime("%Y-%m")
        cursor = await db.execute(
            """
            SELECT COUNT(*) as c FROM locations
            WHERE visited = 1 AND visit_date IS NOT NULL AND visit_date LIKE ?
            """,
            (month_prefix + "%",),
        )
        visits_this_month = (await cursor.fetchone())["c"] or 0

        cursor = await db.execute(
            """
            SELECT l.*, t.name as theme_name, t.primary_color
            FROM locations l
            JOIN themes t ON t.id = l.theme_id
            WHERE l.visited = 1 AND l.visit_date IS NOT NULL
            ORDER BY l.visit_date DESC, l.updated_at DESC
            LIMIT 8
            """
        )
        recent = [dict(r) for r in await cursor.fetchall()]

    for t in themes:
        stats = await get_theme_stats(t["id"])
        t.update(stats)
        if not t.get("primary_color"):
            t["primary_color"] = "#0d9488"
        if not t.get("secondary_color"):
            t["secondary_color"] = "#134e4a"
        if t.get("is_active") is None:
            t["is_active"] = 1

    active_themes = sum(1 for t in themes if t.get("is_active", 1))
    still_to_visit = max(total_places - visited_places, 0)
    pct = round((visited_places / total_places * 100) if total_places else 0)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "base": get_base(request),
        "themes": themes,
        "stats": {
            "total_places": total_places,
            "visited_places": visited_places,
            "percent": pct,
            "active_themes": active_themes,
            "theme_count": len(themes),
            "visits_this_month": visits_this_month,
            "still_to_visit": still_to_visit,
            "month_label": date.today().strftime("%B"),
        },
        "recent": recent,
    })


@app.get("/theme/new", response_class=HTMLResponse)
async def theme_new_form(request: Request):
    base = get_base(request)
    return templates.TemplateResponse("theme_form.html", {
        "request": request,
        "base": base,
        "theme": None,
        "action": f"{base}/theme/new",
    })


@app.post("/theme/new")
async def theme_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    primary_color: str = Form("#0d9488"),
    secondary_color: str = Form("#134e4a"),
    is_active: Optional[str] = Form(None),
):
    active = 1 if is_active == "on" else 0
    pc = primary_color.strip() or "#0d9488"
    sc = secondary_color.strip() or "#134e4a"
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO themes (name, description, primary_color, secondary_color, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), description.strip(), pc, sc, active),
        )
        await db.commit()
        theme_id = cursor.lastrowid
    return redirect(request, f"/theme/{theme_id}")


@app.post("/import/csv")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    theme_name: str = Form("English Heritage"),
):
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Invalid CSV")

    fieldmap = {h.lower().strip(): h for h in reader.fieldnames}

    def col(*names):
        for n in names:
            if n in fieldmap:
                return fieldmap[n]
        return None

    name_col = col("name")
    if not name_col:
        raise HTTPException(status_code=400, detail="CSV must have a name column")

    postcode_col = col("postcode", "post_code", "zip")
    city_col = col("city", "town")
    county_col = col("county")
    notes_col = col("notes", "description")
    url_col = col("url", "website", "link")
    image_col = col("image_url", "image", "photo")
    theme_col = col("theme")

    all_rows = list(reader)
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
    geo = await geocode_postcodes_bulk(postcodes)

    async with get_db() as db:
        for r in rows:
            name = (r.get(name_col) or "").strip()
            postcode = (r.get(postcode_col) or "").strip() if postcode_col else ""
            city = (r.get(city_col) or "").strip() if city_col else ""
            county = (r.get(county_col) or "").strip() if county_col else ""
            notes = (r.get(notes_col) or "").strip() if notes_col else ""
            url = (r.get(url_col) or "").strip() if url_col else ""
            image_url = (r.get(image_col) or "").strip() if image_col else ""

            key1 = postcode.upper().replace(" ", "")
            key2 = postcode.upper()
            info = geo.get(key1) or geo.get(key2) or {}
            lat = info.get("latitude")
            lng = info.get("longitude")
            region = info.get("region") or ""
            district = info.get("district") or ""
            if not county:
                county = info.get("county") or ""

            address_parts = [p for p in [city, county, postcode] if p]
            address = ", ".join(address_parts)

            await db.execute(
                """
                INSERT INTO locations
                (theme_id, name, latitude, longitude, postcode, city, county,
                 region, district, address, notes, url, image_url, visited, visit_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (
                    theme_id, name, lat, lng, postcode, city, county,
                    region, district, address, notes, url, image_url,
                ),
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
        not loc.get("region") or not loc.get("district")
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
            new_region = info.get("region") or loc.get("region") or ""
            new_district = info.get("district") or loc.get("district") or ""
            new_county = info.get("county") or loc.get("county") or ""
            await db.execute(
                """
                UPDATE locations SET
                    latitude = COALESCE(?, latitude),
                    longitude = COALESCE(?, longitude),
                    region = ?,
                    district = ?,
                    county = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    info.get("latitude"),
                    info.get("longitude"),
                    new_region,
                    new_district,
                    new_county,
                    loc["id"],
                ),
            )
        await db.commit()
    return redirect(request, f"/theme/{theme_id}")


@app.get("/theme/{theme_id}", response_class=HTMLResponse)
async def theme_detail(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    locations = await get_locations(theme_id)
    stats = await get_theme_stats(theme_id)
    has_coords = any(
        loc.get("latitude") is not None and loc.get("longitude") is not None
        for loc in locations
    )
    regions = sorted({
        (loc.get("region") or "").strip()
        for loc in locations
        if (loc.get("region") or "").strip()
    })
    districts = sorted({
        (loc.get("district") or "").strip()
        for loc in locations
        if (loc.get("district") or "").strip()
    })
    counties = sorted({
        (loc.get("county") or "").strip()
        for loc in locations
        if (loc.get("county") or "").strip()
    })
    if not theme.get("primary_color"):
        theme["primary_color"] = "#0d9488"

    return templates.TemplateResponse("theme.html", {
        "request": request,
        "base": get_base(request),
        "theme": theme,
        "locations": locations,
        "stats": stats,
        "has_coords": has_coords,
        "regions": regions,
        "districts": districts,
        "counties": counties,
    })


@app.get("/theme/{theme_id}/edit", response_class=HTMLResponse)
async def theme_edit_form(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    base = get_base(request)
    return templates.TemplateResponse("theme_form.html", {
        "request": request,
        "base": base,
        "theme": theme,
        "action": f"{base}/theme/{theme_id}/edit",
    })


@app.post("/theme/{theme_id}/edit")
async def theme_update(
    request: Request,
    theme_id: int,
    name: str = Form(...),
    description: str = Form(""),
    primary_color: str = Form("#0d9488"),
    secondary_color: str = Form("#134e4a"),
    is_active: Optional[str] = Form(None),
):
    active = 1 if is_active == "on" else 0
    pc = primary_color.strip() or "#0d9488"
    sc = secondary_color.strip() or "#134e4a"
    async with get_db() as db:
        await db.execute(
            """
            UPDATE themes SET name = ?, description = ?,
                primary_color = ?, secondary_color = ?, is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name.strip(), description.strip(), pc, sc, active, theme_id),
        )
        await db.commit()
    return redirect(request, f"/theme/{theme_id}")


@app.post("/theme/{theme_id}/delete")
async def theme_delete(request: Request, theme_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
        await db.commit()
    return redirect(request, "/")


@app.get("/theme/{theme_id}/location/new", response_class=HTMLResponse)
async def location_new_form(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    base = get_base(request)
    return templates.TemplateResponse("location_form.html", {
        "request": request,
        "base": base,
        "theme": theme,
        "location": None,
        "action": f"{base}/theme/{theme_id}/location/new",
    })


@app.post("/theme/{theme_id}/location/new")
async def location_create(
    request: Request,
    theme_id: int,
    name: str = Form(...),
    postcode: str = Form(""),
    city: str = Form(""),
    county: str = Form(""),
    visit_duration_mins: int = Form(60),
    opening_hours: str = Form(""),
    notes: str = Form(""),
    url: str = Form(""),
    visited: Optional[str] = Form(None),
    visit_date: Optional[str] = Form(None),
):
    is_visited = 1 if visited == "on" else 0
    vdate = visit_date if is_visited and visit_date else None
    pc = postcode.strip()
    geo = await geocode_postcode(pc)
    lat = geo.get("latitude")
    lng = geo.get("longitude")
    region = geo.get("region") or ""
    district = geo.get("district") or ""
    cty = county.strip() or (geo.get("county") or "")
    address_parts = [p for p in [city.strip(), cty, pc] if p]
    address = ", ".join(address_parts)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO locations
            (theme_id, name, latitude, longitude, postcode, city, county,
             region, district, address, visit_duration_mins, opening_hours, notes, url,
             visited, visit_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                theme_id, name.strip(), lat, lng, pc,
                city.strip(), cty, region, district, address,
                visit_duration_mins, opening_hours.strip(), notes.strip(),
                url.strip(), is_visited, vdate,
            ),
        )
        await db.commit()
    return redirect(request, f"/theme/{theme_id}")


@app.get("/theme/{theme_id}/location/{loc_id}/edit", response_class=HTMLResponse)
async def location_edit_form(request: Request, theme_id: int, loc_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM locations WHERE id = ? AND theme_id = ?",
            (loc_id, theme_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")
        location = dict(row)

    base = get_base(request)
    return templates.TemplateResponse("location_form.html", {
        "request": request,
        "base": base,
        "theme": theme,
        "location": location,
        "action": f"{base}/theme/{theme_id}/location/{loc_id}/edit",
    })


@app.post("/theme/{theme_id}/location/{loc_id}/edit")
async def location_update(
    request: Request,
    theme_id: int,
    loc_id: int,
    name: str = Form(...),
    postcode: str = Form(""),
    city: str = Form(""),
    county: str = Form(""),
    visit_duration_mins: int = Form(60),
    opening_hours: str = Form(""),
    notes: str = Form(""),
    url: str = Form(""),
    visited: Optional[str] = Form(None),
    visit_date: Optional[str] = Form(None),
):
    is_visited = 1 if visited == "on" else 0
    vdate = visit_date if is_visited and visit_date else None
    pc = postcode.strip()
    geo = await geocode_postcode(pc)
    lat = geo.get("latitude")
    lng = geo.get("longitude")
    region = geo.get("region") or ""
    district = geo.get("district") or ""
    cty = county.strip() or (geo.get("county") or "")
    address_parts = [p for p in [city.strip(), cty, pc] if p]
    address = ", ".join(address_parts)

    async with get_db() as db:
        await db.execute(
            """
            UPDATE locations SET
                name = ?, latitude = ?, longitude = ?, postcode = ?,
                city = ?, county = ?, region = ?, district = ?, address = ?,
                visit_duration_mins = ?, opening_hours = ?, notes = ?,
                url = ?, visited = ?, visit_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND theme_id = ?
            """,
            (
                name.strip(), lat, lng, pc, city.strip(), cty,
                region, district, address, visit_duration_mins, opening_hours.strip(),
                notes.strip(), url.strip(), is_visited, vdate,
                loc_id, theme_id,
            ),
        )
        await db.commit()
    return redirect(request, f"/theme/{theme_id}")


@app.post("/theme/{theme_id}/location/{loc_id}/delete")
async def location_delete(request: Request, theme_id: int, loc_id: int):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM locations WHERE id = ? AND theme_id = ?",
            (loc_id, theme_id)
        )
        await db.commit()
    return redirect(request, f"/theme/{theme_id}")


@app.post("/theme/{theme_id}/location/{loc_id}/toggle_visited")
async def toggle_visited(request: Request, theme_id: int, loc_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT visited FROM locations WHERE id = ? AND theme_id = ?",
            (loc_id, theme_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404)

        new_visited = 0 if row["visited"] else 1
        vdate = date.today().isoformat() if new_visited else None

        await db.execute(
            "UPDATE locations SET visited = ?, visit_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_visited, vdate, loc_id)
        )
        await db.commit()
    return redirect(request, f"/theme/{theme_id}")

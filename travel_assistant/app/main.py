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

# Paths
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


async def geocode_postcode(postcode: str) -> tuple[Optional[float], Optional[float]]:
    if not postcode or not postcode.strip():
        return None, None
    pc = postcode.strip().replace(" ", "")
    url = f"https://api.postcodes.io/postcodes/{urllib.parse.quote(pc)}"
    result = await asyncio.to_thread(_http_get_json, url)
    if not result or result.get("status") != 200:
        return None, None
    result_data = result.get("result") or {}
    return result_data.get("latitude"), result_data.get("longitude")


async def geocode_postcodes_bulk(postcodes: list[str]) -> dict[str, tuple[Optional[float], Optional[float]]]:
    out: dict[str, tuple[Optional[float], Optional[float]]] = {}
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
                out[query.upper().replace(" ", "")] = (res.get("latitude"), res.get("longitude"))
                out[query.strip().upper()] = (res.get("latitude"), res.get("longitude"))
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
        ("url", "TEXT DEFAULT ''"),
        ("image_url", "TEXT DEFAULT ''"),
    ]:
        if col not in cols:
            await db.execute(f"ALTER TABLE locations ADD COLUMN {col} {typedef}")


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
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

    for t in themes:
        stats = await get_theme_stats(t["id"])
        t.update(stats)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "base": get_base(request),
        "themes": themes,
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
):
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO themes (name, description) VALUES (?, ?)",
            (name.strip(), description.strip())
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
    """Import places from a CSV upload (name, postcode, city, county, notes, url, image_url, theme)."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Invalid CSV")

    # Normalise header names
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

    # Theme from form or first row
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

    postcodes = []
    for r in rows:
        pc = (r.get(postcode_col) or "").strip() if postcode_col else ""
        postcodes.append(pc)

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
            lat, lng = geo.get(key1) or geo.get(key2) or (None, None)

            address_parts = [p for p in [city, county, postcode] if p]
            address = ", ".join(address_parts)

            await db.execute(
                """
                INSERT INTO locations
                (theme_id, name, latitude, longitude, postcode, city, county,
                 address, notes, url, image_url, visited, visit_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (
                    theme_id, name, lat, lng, postcode, city, county,
                    address, notes, url, image_url,
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

    return templates.TemplateResponse("theme.html", {
        "request": request,
        "base": get_base(request),
        "theme": theme,
        "locations": locations,
        "stats": stats,
        "has_coords": has_coords,
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
):
    async with get_db() as db:
        await db.execute(
            "UPDATE themes SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name.strip(), description.strip(), theme_id)
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
    lat, lng = await geocode_postcode(pc)
    address_parts = [p for p in [city.strip(), county.strip(), pc] if p]
    address = ", ".join(address_parts)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO locations
            (theme_id, name, latitude, longitude, postcode, city, county,
             address, visit_duration_mins, opening_hours, notes, url,
             visited, visit_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                theme_id, name.strip(), lat, lng, pc,
                city.strip(), county.strip(), address,
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
    lat, lng = await geocode_postcode(pc)
    address_parts = [p for p in [city.strip(), county.strip(), pc] if p]
    address = ", ".join(address_parts)

    async with get_db() as db:
        await db.execute(
            """
            UPDATE locations SET
                name = ?, latitude = ?, longitude = ?, postcode = ?,
                city = ?, county = ?, address = ?,
                visit_duration_mins = ?, opening_hours = ?, notes = ?,
                url = ?, visited = ?, visit_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND theme_id = ?
            """,
            (
                name.strip(), lat, lng, pc, city.strip(), county.strip(),
                address, visit_duration_mins, opening_hours.strip(),
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

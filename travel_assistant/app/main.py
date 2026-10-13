"""
Travel Assistant - Home Assistant Add-on
Theme & Places admin with visit tracking
"""

import os
import uuid
import re
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
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import aiosqlite

# trips_routes is imported inside startup so a failure there cannot
# prevent the ASGI app from being created (uvicorn then says
# "Attribute app not found in module main").
register_trip_routes = None

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "travel_assistant.db"
UPLOAD_DIR = DATA_DIR / "uploads"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

# Ensure directories exist before anything tries to mount them.
# An empty static/ dir is often omitted by Docker COPY, which then
# makes StaticFiles() raise and uvicorn report "Attribute app not found".
STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Travel Assistant")

try:
    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
except Exception as _e:
    print(f"WARNING: could not mount /static: {_e}")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

UI_SETTINGS_PATH = DATA_DIR / "ui_settings.json"
DEFAULT_UI = {
    "bg_color": "#fafaf9",
    "sidebar_color": "#1e293b",
    "sidebar_text_color": "#e2e8f0",
    "sidebar_active_color": "#334155",
    "accent_color": "#14b8a6",
}


def load_ui_settings() -> dict:
    out = dict(DEFAULT_UI)
    try:
        if UI_SETTINGS_PATH.exists():
            data = json.loads(UI_SETTINGS_PATH.read_text())
            if isinstance(data, dict):
                for k in DEFAULT_UI:
                    v = data.get(k)
                    if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7):
                        out[k] = v
    except Exception:
        pass
    return out


def save_ui_settings(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cleaned = dict(DEFAULT_UI)
    for k in DEFAULT_UI:
        v = settings.get(k, DEFAULT_UI[k])
        if isinstance(v, str) and v.startswith("#"):
            cleaned[k] = v
    UI_SETTINGS_PATH.write_text(json.dumps(cleaned, indent=2))


class _UIProxy:
    def __getattr__(self, key):
        return load_ui_settings().get(key, DEFAULT_UI.get(key, ""))


templates.env.globals["ui"] = _UIProxy()


def ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def list_assets() -> list[dict]:
    ensure_upload_dir()
    out = []
    for p in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.name.lower()):
        if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXT:
            out.append({"name": p.name, "url": f"/uploads/{p.name}"})
    return out


async def save_upload(file: UploadFile) -> str:
    ensure_upload_dir()
    original = file.filename or "image.png"
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {ext}")
    name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / name
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
    dest.write_bytes(data)
    return f"/uploads/{name}"


def get_base(request: Request) -> str:
    return request.headers.get("x-ingress-path", "").rstrip("/")


def redirect(request: Request, path: str) -> RedirectResponse:
    base = get_base(request)
    if not path.startswith("/"):
        path = "/" + path
    return RedirectResponse(url=f"{base}{path}", status_code=303)


def _http_get_json(url: str, timeout: float = 10.0):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TravelAssistant/1.0 (Home Assistant add-on)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _http_post_json(url: str, payload: dict, timeout: float = 30.0) -> Optional[dict]:
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"User-Agent": "TravelAssistant/1.0", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


async def geocode_postcode(postcode: str) -> dict:
    empty = {"latitude": None, "longitude": None, "region": None, "county": None, "country": "United Kingdom"}
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
        "county": r.get("admin_county") or r.get("admin_district"),
        "country": r.get("country") or "United Kingdom",
    }


async def geocode_postcodes_bulk(postcodes: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    clean = [pc.strip() for pc in postcodes if pc and pc.strip()]
    for i in range(0, len(clean), 100):
        batch = clean[i : i + 100]
        result = await asyncio.to_thread(
            _http_post_json, "https://api.postcodes.io/postcodes", {"postcodes": batch},
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
                    "county": res.get("admin_county") or res.get("admin_district"),
                    "country": res.get("country") or "United Kingdom",
                }
                out[query.upper().replace(" ", "")] = info
                out[query.strip().upper()] = info
    return out


async def geocode_place_name(name: str) -> dict:
    empty = {"latitude": None, "longitude": None, "region": None, "county": None, "country": None, "city": None}
    if not name or not name.strip():
        return empty
    q = name.strip()
    for noise in (" Supercharger", " Tesla"):
        q = q.replace(noise, "")
    query = urllib.parse.quote(f"{q}, United Kingdom")
    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1&addressdetails=1&countrycodes=gb"
    result = await asyncio.to_thread(_http_get_json, url)
    if not result or not isinstance(result, list) or not result:
        return empty
    hit = result[0]
    addr = hit.get("address") or {}
    try:
        lat = float(hit.get("lat"))
        lng = float(hit.get("lon"))
    except (TypeError, ValueError):
        return empty
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb") or ""
    county = addr.get("county") or addr.get("state_district") or ""
    region = addr.get("state") or ""
    country = addr.get("country") or ""
    return {"latitude": lat, "longitude": lng, "region": region, "county": county, "country": country, "city": city}


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")
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
        ("country", "TEXT DEFAULT ''"),
        ("url", "TEXT DEFAULT ''"),
        ("image_url", "TEXT DEFAULT ''"),
        ("visit_photo_url", "TEXT DEFAULT ''"),
    ]:
        if col not in cols:
            await db.execute(f"ALTER TABLE locations ADD COLUMN {col} {typedef}")

    cursor = await db.execute("PRAGMA table_info(themes)")
    tcols = {row[1] for row in await cursor.fetchall()}
    for col, typedef in [
        ("primary_color", "TEXT DEFAULT '#0d9488'"),
        ("secondary_color", "TEXT DEFAULT '#134e4a'"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("icon_url", "TEXT DEFAULT ''"),
        ("exclude_from_counts", "INTEGER DEFAULT 0"),
        ("exclude_from_places", "INTEGER DEFAULT 0"),
        ("exclude_from_maps", "INTEGER DEFAULT 0"),
        ("default_image_url", "TEXT DEFAULT ''"),
        ("hide_visit_status", "INTEGER DEFAULT 0"),
        ("is_system_theme", "INTEGER DEFAULT 0"),
    ]:
        if col not in tcols:
            await db.execute(f"ALTER TABLE themes ADD COLUMN {col} {typedef}")

    cursor = await db.execute("PRAGMA table_info(trip_stops)")
    scols = {row[1] for row in await cursor.fetchall()}
    if scols and "is_hotel" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN is_hotel INTEGER DEFAULT 0")
    if scols and "completed_at" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN completed_at TEXT")
    if scols and "skipped" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN skipped INTEGER DEFAULT 0")

    cursor = await db.execute("PRAGMA table_info(trips)")
    trcols = {row[1] for row in await cursor.fetchall()}
    if trcols and "status" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN status TEXT DEFAULT 'planned'")
    if trcols and "started_at" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN started_at TEXT")
    if trcols and "active_day" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN active_day INTEGER DEFAULT 1")
    if trcols and "image_url" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN image_url TEXT DEFAULT ''")


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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                notes TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trip_stops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                location_id INTEGER,
                custom_name TEXT DEFAULT '',
                day_number INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                travel_from_prev_secs INTEGER,
                distance_from_prev_m INTEGER,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE SET NULL
            )
        """)
        await migrate_db(db)
        await db.commit()


@app.on_event("startup")
async def startup():
    global register_trip_routes
    ensure_upload_dir()
    try:
        app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
    except Exception as e:
        print(f"WARNING: could not mount /uploads: {e}")
    try:
        await init_db()
    except Exception as e:
        print(f"ERROR: database init failed: {e}")
        raise
    try:
        from trips_routes import register_routes as register_trip_routes
        register_trip_routes(app, templates, {
            "get_db": get_db,
            "get_base": get_base,
            "redirect": redirect,
            "save_upload": save_upload,
            "_http_get_json": _http_get_json,
        })
        print("Trip routes registered")
    except Exception as e:
        print(f"ERROR: failed to register trip routes: {e}")
        import traceback
        traceback.print_exc()


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
            "SELECT * FROM locations WHERE theme_id = ? ORDER BY name", (theme_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_theme_stats(theme_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN visited = 1 THEN 1 ELSE 0 END) as visited_count
               FROM locations WHERE theme_id = ?""",
            (theme_id,),
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
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN l.visited = 1 THEN 1 ELSE 0 END) as visited_count
               FROM locations l JOIN themes t ON t.id = l.theme_id
               WHERE COALESCE(t.exclude_from_counts, 0) = 0"""
        )
        row = await cursor.fetchone()
        total_places = row["total"] or 0
        visited_places = row["visited_count"] or 0
        month_prefix = date.today().strftime("%Y-%m")
        cursor = await db.execute(
            """SELECT COUNT(*) as c FROM locations l JOIN themes t ON t.id = l.theme_id
               WHERE l.visited = 1 AND l.visit_date IS NOT NULL AND l.visit_date LIKE ?
                 AND COALESCE(t.exclude_from_counts, 0) = 0""",
            (month_prefix + "%",),
        )
        visits_this_month = (await cursor.fetchone())["c"] or 0
        cursor = await db.execute(
            """SELECT l.*, t.name as theme_name, t.primary_color, t.icon_url
               FROM locations l JOIN themes t ON t.id = l.theme_id
               WHERE l.visited = 1 AND l.visit_date IS NOT NULL
                 AND COALESCE(t.exclude_from_counts, 0) = 0
               ORDER BY l.visit_date DESC, l.updated_at DESC LIMIT 8"""
        )
        recent = [dict(r) for r in await cursor.fetchall()]
        cursor = await db.execute(
            "SELECT * FROM trips WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        active_trip = dict(row) if row else None
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
        "request": request, "base": get_base(request), "active_nav": "dashboard",
        "themes": themes,
        "stats": {
            "total_places": total_places, "visited_places": visited_places, "percent": pct,
            "active_themes": active_themes, "theme_count": len(themes),
            "visits_this_month": visits_this_month, "still_to_visit": still_to_visit,
            "month_label": date.today().strftime("%B"),
        },
        "recent": recent,
        "active_trip": active_trip,
    })


@app.get("/themes", response_class=HTMLResponse)
async def themes_list(request: Request):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM themes ORDER BY name")
        themes = [dict(r) for r in await cursor.fetchall()]
    for t in themes:
        stats = await get_theme_stats(t["id"])
        t.update(stats)
        if not t.get("primary_color"):
            t["primary_color"] = "#0d9488"
        if t.get("is_active") is None:
            t["is_active"] = 1
    return templates.TemplateResponse("themes.html", {
        "request": request, "base": get_base(request), "active_nav": "themes", "themes": themes,
    })


@app.get("/places", response_class=HTMLResponse)
async def places_list(request: Request):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM themes WHERE COALESCE(exclude_from_places, 0) = 0 ORDER BY name"
        )
        themes = [dict(r) for r in await cursor.fetchall()]
        cursor = await db.execute(
            """SELECT l.*, t.name as theme_name, t.primary_color, t.icon_url,
                      t.default_image_url,
                      COALESCE(t.exclude_from_maps, 0) as exclude_from_maps,
                      COALESCE(t.hide_visit_status, 0) as hide_visit_status,
                      COALESCE(t.is_system_theme, 0) as is_system_theme
               FROM locations l JOIN themes t ON t.id = l.theme_id
               WHERE COALESCE(t.exclude_from_places, 0) = 0 ORDER BY l.name"""
        )
        locations = [dict(r) for r in await cursor.fetchall()]
        cursor = await db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN l.visited = 1 THEN 1 ELSE 0 END) as visited_count
               FROM locations l JOIN themes t ON t.id = l.theme_id
               WHERE COALESCE(t.exclude_from_places, 0) = 0"""
        )
        row = await cursor.fetchone()
        total = row["total"] or 0
        visited = row["visited_count"] or 0
    regions = sorted({(loc.get("region") or "").strip() for loc in locations if (loc.get("region") or "").strip()})
    counties = sorted({(loc.get("county") or "").strip() for loc in locations if (loc.get("county") or "").strip()})
    regular_themes = [t for t in themes if not t.get("is_system_theme")]
    system_themes = [t for t in themes if t.get("is_system_theme")]
    return templates.TemplateResponse("places.html", {
        "request": request, "base": get_base(request), "active_nav": "places",
        "themes": themes, "regular_themes": regular_themes, "system_themes": system_themes,
        "locations": locations, "regions": regions, "counties": counties,
        "stats": {"total": total, "visited": visited},
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request, "base": get_base(request), "active_nav": "settings",
        "saved": request.query_params.get("saved") == "1",
        "upload_ok": request.query_params.get("upload") == "1",
        "upload_error": request.query_params.get("error"),
        "assets": list_assets(),
    })


@app.get("/settings/export")
async def settings_export():
    async with get_db() as db:
        data = {"exported_at": date.today().isoformat()}
        for table in ("themes", "locations", "trips", "trip_stops"):
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


@app.get("/theme/new", response_class=HTMLResponse)
async def theme_new_form(request: Request):
    base = get_base(request)
    return templates.TemplateResponse("theme_form.html", {
        "request": request, "base": base, "active_nav": "themes",
        "theme": None, "action": f"{base}/theme/new", "assets": list_assets(),
    })


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
    icon_file: Optional[UploadFile] = File(None),
    default_image_file: Optional[UploadFile] = File(None),
):
    active = 1 if is_active == "on" else 0
    pc = primary_color.strip() or "#0d9488"
    sc = secondary_color.strip() or "#134e4a"
    icon = icon_url.strip()
    def_img = default_image_url.strip()
    if icon_file and icon_file.filename:
        icon = await save_upload(icon_file)
    if default_image_file and default_image_file.filename:
        def_img = await save_upload(default_image_file)
    ex_c = 1 if exclude_from_counts == "on" else 0
    ex_p = 1 if exclude_from_places == "on" else 0
    ex_m = 1 if exclude_from_maps == "on" else 0
    hide_v = 1 if hide_visit_status == "on" else 0
    sys_t = 1 if is_system_theme == "on" else 0
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO themes (
                name, description, primary_color, secondary_color, is_active,
                icon_url, default_image_url,
                exclude_from_counts, exclude_from_places, exclude_from_maps,
                hide_visit_status, is_system_theme
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name.strip(), description.strip(), pc, sc, active, icon, def_img, ex_c, ex_p, ex_m, hide_v, sys_t),
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

    name_col = col("name", "location name", "location", "site", "site name")
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
        notes = "\n".join(note_bits)
        if not city and address_raw:
            city = address_raw.split(",")[0].strip()

        key1 = postcode.upper().replace(" ", "")
        key2 = postcode.upper()
        info = geo.get(key1) or geo.get(key2) or {}
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


@app.get("/theme/{theme_id}", response_class=HTMLResponse)
async def theme_detail(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    locations = await get_locations(theme_id)
    stats = await get_theme_stats(theme_id)
    has_coords = any(loc.get("latitude") is not None and loc.get("longitude") is not None for loc in locations)
    regions = sorted({(loc.get("region") or "").strip() for loc in locations if (loc.get("region") or "").strip()})
    countries = sorted({(loc.get("country") or "").strip() for loc in locations if (loc.get("country") or "").strip()})
    counties = sorted({(loc.get("county") or "").strip() for loc in locations if (loc.get("county") or "").strip()})
    if not theme.get("primary_color"):
        theme["primary_color"] = "#0d9488"
    return templates.TemplateResponse("theme.html", {
        "request": request, "base": get_base(request), "active_nav": "places",
        "theme": theme, "locations": locations, "stats": stats, "has_coords": has_coords,
        "regions": regions, "countries": countries, "counties": counties,
    })


@app.get("/theme/{theme_id}/edit", response_class=HTMLResponse)
async def theme_edit_form(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    base = get_base(request)
    return templates.TemplateResponse("theme_form.html", {
        "request": request, "base": base, "active_nav": "themes",
        "theme": theme, "action": f"{base}/theme/{theme_id}/edit", "assets": list_assets(),
    })


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
    icon_file: Optional[UploadFile] = File(None),
    default_image_file: Optional[UploadFile] = File(None),
):
    active = 1 if is_active == "on" else 0
    pc = primary_color.strip() or "#0d9488"
    sc = secondary_color.strip() or "#134e4a"
    icon = icon_url.strip()
    def_img = default_image_url.strip()
    if icon_file and icon_file.filename:
        icon = await save_upload(icon_file)
    if default_image_file and default_image_file.filename:
        def_img = await save_upload(default_image_file)
    ex_c = 1 if exclude_from_counts == "on" else 0
    ex_p = 1 if exclude_from_places == "on" else 0
    ex_m = 1 if exclude_from_maps == "on" else 0
    hide_v = 1 if hide_visit_status == "on" else 0
    sys_t = 1 if is_system_theme == "on" else 0
    async with get_db() as db:
        await db.execute(
            """UPDATE themes SET name = ?, description = ?,
                primary_color = ?, secondary_color = ?, is_active = ?,
                icon_url = ?, default_image_url = ?,
                exclude_from_counts = ?, exclude_from_places = ?, exclude_from_maps = ?,
                hide_visit_status = ?, is_system_theme = ?,
                updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (name.strip(), description.strip(), pc, sc, active, icon, def_img, ex_c, ex_p, ex_m, hide_v, sys_t, theme_id),
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


@app.get("/theme/{theme_id}/location/new", response_class=HTMLResponse)
async def location_new_form(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    base = get_base(request)
    return templates.TemplateResponse("location_form.html", {
        "request": request, "base": base, "active_nav": "places",
        "theme": theme, "location": None, "action": f"{base}/theme/{theme_id}/location/new",
    })


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


@app.get("/theme/{theme_id}/location/{loc_id}", response_class=HTMLResponse)
async def location_detail(request: Request, theme_id: int, loc_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM locations WHERE id = ? AND theme_id = ?", (loc_id, theme_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")
        location = dict(row)
    photos = []
    if location.get("visit_photo_url"):
        photos.append(location["visit_photo_url"])
    return templates.TemplateResponse("location.html", {
        "request": request, "base": get_base(request), "active_nav": "places",
        "theme": theme, "location": location, "photos": photos,
    })


@app.get("/theme/{theme_id}/location/{loc_id}/edit", response_class=HTMLResponse)
async def location_edit_form(request: Request, theme_id: int, loc_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM locations WHERE id = ? AND theme_id = ?", (loc_id, theme_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")
        location = dict(row)
    base = get_base(request)
    return templates.TemplateResponse("location_form.html", {
        "request": request, "base": base, "active_nav": "places",
        "theme": theme, "location": location,
        "action": f"{base}/theme/{theme_id}/location/{loc_id}/edit",
    })


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

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
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
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

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".heic", ".heif"}

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
    "accent_color": "#14b8a6",
    "xai_api_key": "",
}



def addon_option(key: str, default: str = "") -> str:
    """Read a value from the Home Assistant add-on configuration."""
    try:
        import json as _json
        data = _json.loads(Path("/data/options.json").read_text())
        v = str(data.get(key) or default).strip().strip('"').strip("'")
        return v
    except Exception:
        return default

def grok_key() -> str:
    return (addon_option("xai_api_key") or str(load_ui_settings().get("xai_api_key") or "")).strip().strip('"').strip("'")

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



def seed_category_icons():
    """Write simple default SVG icons for category types into uploads."""
    ensure_upload_dir()
    icons = {
        "places-to-visit": ("#0d9488", "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"),
        "superchargers": ("#e11d48", "M7 2v11h3v9l7-12h-4l4-8z"),
        "accommodation": ("#f59e0b", "M7 13c1.66 0 3-1.34 3-3S8.66 7 7 7s-3 1.34-3 3 1.34 3 3 3zm12-6h-8v7H3V5H1v15h2v-3h18v3h2v-9c0-2.21-1.79-4-4-4z"),
        "places-to-eat": ("#ea580c", "M11 9H9V2H7v7H5V2H3v7c0 2.12 1.66 3.84 3.75 3.97V22h2.5v-9.03C11.34 12.84 13 11.12 13 9V2h-2v7zm5-3v8h2.5v8H21V2c-2.76 0-5 2.24-5 4z"),
        "airport": ("#2563eb", "M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"),
        "sea-port": ("#0284c7", "M20 21c-1.39 0-2.78-.47-4-1.32-2.44 1.71-5.56 1.71-8 0C6.78 20.53 5.39 21 4 21H2v2h2c1.38 0 2.74-.35 4-.99 2.52 1.29 5.48 1.29 8 0 1.26.65 2.62.99 4 .99h2v-2h-2zM3.95 19H4c1.6 0 3.02-.88 4-2 .98 1.12 2.4 2 4 2s3.02-.88 4-2c.98 1.12 2.4 2 4 2h.05l1.89-6.68c.08-.26.06-.54-.06-.78s-.34-.42-.6-.5L20 10.62V6c0-1.1-.9-2-2-2h-3V1H9v3H6c-1.1 0-2 .9-2 2v4.62l-1.29.42c-.26.08-.48.26-.6.5s-.15.52-.06.78L3.95 19z"),
        "parking": ("#4f46e5", "M13 3H6v18h4v-6h3c3.31 0 6-2.69 6-6s-2.69-6-6-6zm.2 8H10V7h3.2c1.1 0 2 .9 2 2s-.9 2-2 2z"),
        "viewpoint": ("#7c3aed", "M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"),
        "museum": ("#b45309", "M22 11V9L12 2 2 9v2h2v9H2v2h20v-2h-2v-9h2zm-6 7h-2v-4l-2 3-2-3v4H8v-7h2l2 3 2-3h2v7z"),
        "nature": ("#16a34a", "M17 12h2L12 2 5.05 12H7l-3.9 6h6.92v4h1.96v-4H19z"),
        "shopping": ("#db2777", "M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12.9-1.63h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49c.08-.14.12-.31.12-.48 0-.55-.45-1-1-1H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.89 2 1.99 2 2-.9 2-2-.9-2-2-2z"),
        "activity": ("#0891b2", "M13.49 5.48c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm-3.6 13.9l1-4.4 2.1 2v6h2v-7.5l-2.1-2 .6-3c1.3 1.5 3.3 2.5 5.5 2.5v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1l-5.2 2.2v4.7h2v-3.4l1.8-.7-1.6 8.1-4.9-1-.4 2 7 1.4z"),
        "services": ("#64748b", "M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"),
        "cruise-ship": ("#0e7490", "M20 21c-1.39 0-2.78-.47-4-1.32-2.44 1.71-5.56 1.71-8 0C6.78 20.53 5.39 21 4 21H2v2h2c1.38 0 2.74-.35 4-.99 2.52 1.29 5.48 1.29 8 0 1.26.65 2.62.99 4 .99h2v-2h-2zM3.95 19H4c1.6 0 3.02-.88 4-2 .98 1.12 2.4 2 4 2s3.02-.88 4-2c.98 1.12 2.4 2 4 2h.05l1.89-6.68c.08-.26.06-.54-.06-.78s-.34-.42-.6-.5L20 10.62V6c0-1.1-.9-2-2-2h-3V1H9v3H6c-1.1 0-2 .9-2 2v4.62l-1.29.42c-.26.08-.48.26-.6.5s-.15.52-.06.78L3.95 19zM6 6h12v3.97L12 8 6 9.97V6z"),
    }
    for slug, (color, path) in icons.items():
        dest = UPLOAD_DIR / f"icon-{slug}.svg"
        if dest.exists():
            continue
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}"><path d="{path}"/></svg>'
        dest.write_text(svg)

def list_assets() -> list[dict]:
    ensure_upload_dir()
    out = []
    for p in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.name.lower()):
        if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXT:
            out.append({"name": p.name, "url": f"/uploads/{p.name}"})
    return out


async def save_upload(file: UploadFile) -> str:
    ensure_upload_dir()
    original = file.filename or "image.jpg"
    ext = Path(original).suffix.lower()
    ctype = (file.content_type or "").lower()
    if ext not in ALLOWED_IMAGE_EXT:
        if "png" in ctype:
            ext = ".png"
        elif "webp" in ctype:
            ext = ".webp"
        elif "gif" in ctype:
            ext = ".gif"
        elif "svg" in ctype:
            ext = ".svg"
        elif "heic" in ctype or "heif" in ctype:
            ext = ".heic"
        elif ctype.startswith("image/"):
            ext = ".jpg"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported image type: {ext or ctype or 'unknown'}")
    data = await file.read()
    if len(data) > 40 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 40MB)")
    if ext != ".svg":
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((2000, 2000))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=85, optimize=True)
            data = out.getvalue()
            ext = ".jpg"
        except Exception:
            if ext in {".heic", ".heif"}:
                raise HTTPException(status_code=400, detail="Could not read this photo. Save it as JPEG and try again.")
    name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / name
    dest.write_bytes(data)
    return f"/uploads/{name}"


def get_base(request: Request) -> str:
    return request.headers.get("x-ingress-path", "").rstrip("/")


def is_companion_app(request: Request) -> bool:
    ua = (request.headers.get("user-agent") or "").lower()
    return "home assistant" in ua or "io.robbie.homeassistant" in ua


def is_mobile_ua(request: Request) -> bool:
    ua = (request.headers.get("user-agent") or "").lower()
    return is_companion_app(request) or any(x in ua for x in ("android", "iphone", "ipad", "mobile"))


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


async def sync_achievements(db, theme_id=None, type_id=None, region=None, county=None, country=None):
    sql = """SELECT l.county, l.region, l.country, l.visited
             FROM locations l JOIN themes t ON t.id = l.theme_id
             WHERE COALESCE(t.achievement_eligible, 1) = 1"""
    params = []
    if theme_id:
        sql += " AND l.theme_id = ?"
        params.append(theme_id)
    if type_id:
        sql += " AND t.category_type_id = ?"
        params.append(type_id)
    if region:
        sql += " AND l.region = ?"
        params.append(region)
    if county:
        sql += " AND l.county = ?"
        params.append(county)
    if country:
        sql += " AND l.country = ?"
        params.append(country)
    cursor = await db.execute(sql, params)
    rows = [dict(r) for r in await cursor.fetchall()]
    groups = {"county": {}, "region": {}, "country": {}}
    overall = {"total": 0, "visited": 0}
    coverage = {"county": 0, "region": 0, "country": 0}
    for row in rows:
        overall["total"] += 1
        overall["visited"] += 1 if row.get("visited") else 0
        for level, field in (("county", "county"), ("region", "region"), ("country", "country")):
            value = (row.get(field) or "").strip()
            if not value:
                continue
            coverage[level] += 1
            bucket = groups[level].setdefault(value, {"total": 0, "visited": 0})
            bucket["total"] += 1
            bucket["visited"] += 1 if row.get("visited") else 0
    items = []
    for level, label in (("county", "County"), ("region", "Region"), ("country", "Country")):
        reliable = overall["total"] > 0 and coverage[level] / overall["total"] >= 0.5
        for name, stats in sorted(groups[level].items()):
            pct = round(100 * stats["visited"] / stats["total"]) if stats["total"] else 0
            all_visited = stats["total"] > 0 and stats["visited"] >= stats["total"]
            items.append({
                "key": f"{level}:{name.lower()}",
                "level": level,
                "level_label": label,
                "name": name,
                "title": f"All of {name}",
                "total": stats["total"],
                "visited": stats["visited"],
                "percent": pct,
                "complete": all_visited and reliable,
                "unreliable": all_visited and not reliable,
            })
    pct = round(100 * overall["visited"] / overall["total"]) if overall["total"] else 0
    items.append({
        "key": "overall",
        "level": "overall",
        "level_label": "Overall",
        "name": "All places",
        "title": "All places visited",
        "total": overall["total"],
        "visited": overall["visited"],
        "percent": pct,
        "complete": overall["total"] > 0 and overall["visited"] >= overall["total"],
        "unreliable": False,
    })
    for item in items:
        if item["complete"]:
            await db.execute(
                "INSERT OR IGNORE INTO achievement_unlocks (key, level, name) VALUES (?, ?, ?)",
                (item["key"], item["level"], item["title"]),
            )
        elif item.get("unreliable"):
            await db.execute("DELETE FROM achievement_unlocks WHERE key = ?", (item["key"],))
    await db.commit()
    cursor = await db.execute("SELECT key, unlocked_at FROM achievement_unlocks")
    unlocked = {r["key"]: r["unlocked_at"] for r in await cursor.fetchall()}
    for item in items:
        item["unlocked_at"] = unlocked.get(item["key"])
    recent = sorted([i for i in items if i["complete"]], key=lambda i: i.get("unlocked_at") or "", reverse=True)[:5]
    near = sorted([i for i in items if not i["complete"] and i["total"]], key=lambda i: i["percent"], reverse=True)[:3]
    coverage_note = {
        "total": overall["total"],
        "country": coverage["country"],
        "region": coverage["region"],
        "county": coverage["county"],
    }
    return items, recent, near, coverage_note


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
        ("hidden", "INTEGER DEFAULT 0"),
        ("visit_photo_url", "TEXT DEFAULT ''"),
        ("itinerary_json", "TEXT DEFAULT ''"),
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
        ("category_type_id", "INTEGER"),
    ]:
        if col not in tcols:
            await db.execute(f"ALTER TABLE themes ADD COLUMN {col} {typedef}")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS category_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0,
            achievement_eligible INTEGER DEFAULT 0,
            exclude_from_counts INTEGER DEFAULT 1,
            exclude_from_places INTEGER DEFAULT 1,
            exclude_from_maps INTEGER DEFAULT 1,
            hide_visit_status INTEGER DEFAULT 1,
            trip_role TEXT DEFAULT ''
        )
    """)
    # Add columns if table already existed
    cursor = await db.execute("PRAGMA table_info(category_types)")
    ctcols = {row[1] for row in await cursor.fetchall()}
    for col, typedef in [
        ("achievement_eligible", "INTEGER DEFAULT 0"),
        ("exclude_from_counts", "INTEGER DEFAULT 1"),
        ("exclude_from_places", "INTEGER DEFAULT 1"),
        ("exclude_from_maps", "INTEGER DEFAULT 1"),
        ("hide_visit_status", "INTEGER DEFAULT 1"),
        ("trip_role", "TEXT DEFAULT ''"),
    ]:
        if col not in ctcols:
            await db.execute(f"ALTER TABLE category_types ADD COLUMN {col} {typedef}")
    # Set sensible defaults by name
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 1, exclude_from_counts = 0, exclude_from_places = 0,
            exclude_from_maps = 0, hide_visit_status = 0, trip_role = 'visit'
        WHERE lower(name) = 'places to visit'
    """)
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 0, exclude_from_counts = 1, exclude_from_places = 1,
            exclude_from_maps = 1, hide_visit_status = 1, trip_role = 'overnight'
        WHERE lower(name) IN ('accommodation', 'hotel', 'hotels', 'hotels')
    """)
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 0, exclude_from_counts = 1, exclude_from_places = 0,
            exclude_from_maps = 0, hide_visit_status = 1, trip_role = 'flexible'
        WHERE lower(name) = 'superchargers'
    """)
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 0, exclude_from_counts = 1, exclude_from_places = 1,
            exclude_from_maps = 1, hide_visit_status = 1, trip_role = 'home'
        WHERE lower(name) = 'home location'
    """)
    cursor = await db.execute("SELECT COUNT(*) FROM category_types")
    row = await cursor.fetchone()
    if row and row[0] == 0:
        for i, name in enumerate([
            "Places to visit", "Superchargers", "Accommodation", "Places to eat",
            "Airport", "Sea port", "Parking", "Viewpoint", "Museum", "Nature",
            "Shopping", "Activity", "Services", "Cruise ship",
        ]):
            await db.execute(
                "INSERT OR IGNORE INTO category_types (name, sort_order) VALUES (?, ?)",
                (name, i),
            )

    
    # Ensure cruise ship type exists
    await db.execute("INSERT OR IGNORE INTO category_types (name, sort_order) VALUES ('Cruise ship', 20)")
    cursor = await db.execute("PRAGMA table_info(trip_stops)")
    scols = {row[1] for row in await cursor.fetchall()}
    if scols and "is_hotel" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN is_hotel INTEGER DEFAULT 0")
    if scols and "completed_at" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN completed_at TEXT")
    if scols and "skipped" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN skipped INTEGER DEFAULT 0")
    if scols and "arrived_at" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN arrived_at TEXT")

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
    if trcols and "start_time" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN start_time TEXT DEFAULT '09:00'")
    if trcols and "trip_type" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN trip_type TEXT DEFAULT 'standard'")
    if trcols and "cruise_id" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN cruise_id INTEGER")
    lcols = {r[1] for r in await (await db.execute("PRAGMA table_info(locations)")).fetchall()}
    if lcols and "cruise_id" not in lcols:
        await db.execute("ALTER TABLE locations ADD COLUMN cruise_id INTEGER")
    tcols = {r[1] for r in await (await db.execute("PRAGMA table_info(trips)")).fetchall()}
    if tcols and "summary_miles" not in tcols:
        await db.execute("ALTER TABLE trips ADD COLUMN summary_miles REAL")
        await db.execute("ALTER TABLE trips ADD COLUMN summary_travel_hrs REAL")
        await db.execute("ALTER TABLE trips ADD COLUMN summary_visit_hrs REAL")
    if trcols and "day_times_json" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN day_times_json TEXT DEFAULT ''")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS cruises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            year INTEGER NOT NULL,
            name TEXT DEFAULT '',
            url TEXT DEFAULT '',
            start_date TEXT,
            end_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ship_id, code, year)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS cruise_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cruise_id INTEGER NOT NULL,
            day INTEGER NOT NULL,
            date TEXT,
            port TEXT DEFAULT '',
            lat REAL,
            lon REAL,
            status TEXT DEFAULT 'port',
            image_url TEXT DEFAULT '',
            FOREIGN KEY (cruise_id) REFERENCES cruises(id) ON DELETE CASCADE
        )
    """)
    if trcols and "cruise_ship_id" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN cruise_ship_id INTEGER")
    if trcols and "cruise_itinerary_json" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN cruise_itinerary_json TEXT DEFAULT ''")

    theme_cols = {r[1] for r in await (await db.execute("PRAGMA table_info(themes)")).fetchall()}
    if theme_cols and "achievement_eligible" not in theme_cols:
        await db.execute("ALTER TABLE themes ADD COLUMN achievement_eligible INTEGER DEFAULT 1")
        await db.execute(
            "UPDATE themes SET achievement_eligible = 0 WHERE lower(name) IN ('hotel', 'hotels')"
        )
    await db.execute("""
        CREATE TABLE IF NOT EXISTS achievement_unlocks (
            key TEXT PRIMARY KEY,
            level TEXT NOT NULL,
            name TEXT NOT NULL,
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor = await db.execute("PRAGMA table_info(kit_items)")
    kcols = {row[1] for row in await cursor.fetchall()}
    if kcols and "every_days" not in kcols:
        await db.execute("ALTER TABLE kit_items ADD COLUMN every_days INTEGER DEFAULT 0")
    cursor = await db.execute("PRAGMA table_info(trip_kit)")
    tkcols = {row[1] for row in await cursor.fetchall()}
    if tkcols and "every_days" not in tkcols:
        await db.execute("ALTER TABLE trip_kit ADD COLUMN every_days INTEGER DEFAULT 0")

    # Clothing categories for store cupboard
    await db.execute("""
        CREATE TABLE IF NOT EXISTS clothing_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0
        )
    """)
    cursor = await db.execute("PRAGMA table_info(kit_items)")
    kcols2 = {row[1] for row in await cursor.fetchall()}
    if kcols2 and "clothing_category_id" not in kcols2:
        await db.execute("ALTER TABLE kit_items ADD COLUMN clothing_category_id INTEGER")
    # Seed suggested clothing categories if empty
    cursor = await db.execute("SELECT COUNT(*) as c FROM clothing_categories")
    count = (await cursor.fetchone())["c"] or 0
    if count == 0:
        suggestions = [
            "Shoes", "Smart", "Casual", "Winter", "Summer",
            "Underwear", "Outerwear", "Accessories", "Sleepwear", "Swimwear"
        ]
        for i, name in enumerate(suggestions):
            await db.execute(
                "INSERT OR IGNORE INTO clothing_categories (name, sort_order) VALUES (?, ?)",
                (name, i),
            )



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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS packing_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                parent_id INTEGER,
                is_bag INTEGER DEFAULT 0,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                per_day INTEGER DEFAULT 0,
                qty INTEGER DEFAULT 1,
                packed INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kit_bags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kit_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bag_id INTEGER,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                per_day INTEGER DEFAULT 0,
                qty INTEGER DEFAULT 1,
                weather_tags TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trip_kit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                kit_item_id INTEGER,
                bag_id INTEGER,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                per_day INTEGER DEFAULT 0,
                qty INTEGER DEFAULT 1,
                needed INTEGER DEFAULT 1,
                packed INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
            )
        """)
        await migrate_db(db)
        await db.commit()


@app.on_event("startup")
async def startup():
    global register_trip_routes
    ensure_upload_dir()
    try:
        seed_category_icons()
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
        from packing_routes import register_routes as register_packing_routes
        register_packing_routes(app, templates, {
            "get_db": get_db,
            "get_base": get_base,
            "redirect": redirect,
        })
        print("Packing routes registered")
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

@app.get("/react", response_class=HTMLResponse)
@app.get("/react/{path:path}", response_class=HTMLResponse)
async def react_preview(request: Request, path: str = ""):
    """Serve the React SPA preview. Rewrite asset paths so they load under Ingress."""
    index = STATIC_DIR / "react" / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>React UI not built</h1><p>The frontend has not been built into this image yet.</p>", status_code=404)
    base = get_base(request)
    html = index.read_text(encoding="utf-8")
    # Rewrite any asset reference to live under the Ingress base + /static/react/
    asset_prefix = f"{base}/static/react/"
    # Relative (./assets/ or assets/)
    html = html.replace('src="./assets/', f'src="{asset_prefix}assets/')
    html = html.replace("src='./assets/", f"src='{asset_prefix}assets/")
    html = html.replace('href="./assets/', f'href="{asset_prefix}assets/')
    html = html.replace("href='./assets/", f"href='{asset_prefix}assets/")
    html = html.replace('src="assets/', f'src="{asset_prefix}assets/')
    html = html.replace('href="assets/', f'href="{asset_prefix}assets/')
    # Absolute /assets/
    html = html.replace('src="/assets/', f'src="{asset_prefix}assets/')
    html = html.replace('href="/assets/', f'href="{asset_prefix}assets/')
    # Inject a tiny error surface so a JS failure is visible instead of a blank page
    html = html.replace(
        '<div id="root"></div>',
        '<div id="root"></div><script>window.addEventListener("error",function(e){document.body.insertAdjacentHTML("beforeend","<pre style=\"margin:1rem;padding:1rem;background:#fee;color:#900;white-space:pre-wrap\">"+e.message+"</pre>")});</script>'
    )
    return HTMLResponse(html)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM themes ORDER BY name")
        themes = [dict(r) for r in await cursor.fetchall()]
        _, recent_achievements, near_achievements, _ = await sync_achievements(db)
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
        active_trip = None
        try:
            cursor = await db.execute(
                "SELECT * FROM trips WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            active_trip = dict(row) if row else None
        except Exception:
            active_trip = None
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
        "recent_achievements": recent_achievements,
        "near_achievements": near_achievements,
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
                      t.default_image_url, t.category_type_id,
                      ct.name as category_type_name,
                      COALESCE(t.exclude_from_maps, 0) as exclude_from_maps,
                      COALESCE(t.hide_visit_status, 0) as hide_visit_status,
                      COALESCE(t.is_system_theme, 0) as is_system_theme
               FROM locations l JOIN themes t ON t.id = l.theme_id
               LEFT JOIN category_types ct ON ct.id = t.category_type_id
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
        "category_types": await list_category_types(),
    })


async def list_category_types():
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM category_types ORDER BY sort_order, name")
        return [dict(r) for r in await cursor.fetchall()]



@app.get("/api/settings")
async def api_settings(request: Request):
    return {
        "ui": load_ui_settings(),
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
                current[k] = body[k]
        save_ui_settings(current)
    return {"ok": True, "ui": load_ui_settings()}

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

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request, "base": get_base(request), "active_nav": "settings",
        "saved": request.query_params.get("saved") == "1",
        "upload_ok": request.query_params.get("upload") == "1",
        "upload_error": request.query_params.get("error"),
        "assets": list_assets(),
        "category_types": await list_category_types(),
        "home": await get_home_location(),
    })


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


@app.get("/theme/new", response_class=HTMLResponse)
async def theme_new_form(request: Request):
    base = get_base(request)
    return templates.TemplateResponse("theme_form.html", {
        "request": request, "base": base, "active_nav": "themes",
        "theme": None, "action": f"{base}/theme/new", "assets": list_assets(),
        "category_types": await list_category_types(),
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
        "category_types": await list_category_types(),
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


@app.get("/achievements", response_class=HTMLResponse)
async def achievements_page(request: Request):
    theme_id = request.query_params.get("theme") or ""
    type_id = request.query_params.get("type") or ""
    region = request.query_params.get("region") or ""
    county = request.query_params.get("county") or ""
    country = request.query_params.get("country") or ""
    async with get_db() as db:
        themes = [dict(r) for r in await (await db.execute(
            "SELECT id, name FROM themes WHERE COALESCE(achievement_eligible, 1) = 1 ORDER BY name"
        )).fetchall()]
        types = [dict(r) for r in await (await db.execute(
            "SELECT id, name FROM category_types ORDER BY sort_order, name"
        )).fetchall()]
        places = [dict(r) for r in await (await db.execute(
            """SELECT DISTINCT l.region, l.county, l.country
               FROM locations l JOIN themes t ON t.id = l.theme_id
               WHERE COALESCE(t.achievement_eligible, 1) = 1"""
        )).fetchall()]
        items, recent, near, coverage = await sync_achievements(
            db,
            int(theme_id) if theme_id.isdigit() else None,
            int(type_id) if type_id.isdigit() else None,
            region or None, county or None, country or None,
        )
    grouped = {"county": [], "region": [], "country": [], "overall": []}
    for item in items:
        grouped.setdefault(item["level"], []).append(item)
    return templates.TemplateResponse("achievements.html", {
        "request": request, "base": get_base(request), "active_nav": "achievements",
        "grouped": grouped, "recent": recent, "near": near, "coverage": coverage,
        "themes": themes, "category_types": types,
        "regions": sorted({(p.get("region") or "").strip() for p in places if (p.get("region") or "").strip()}),
        "counties": sorted({(p.get("county") or "").strip() for p in places if (p.get("county") or "").strip()}),
        "countries": sorted({(p.get("country") or "").strip() for p in places if (p.get("country") or "").strip()}),
        "filters": {"theme": theme_id, "type": type_id, "region": region, "county": county, "country": country},
    })


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

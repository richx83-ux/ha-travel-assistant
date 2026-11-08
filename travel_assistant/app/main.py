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
from datetime import date
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_db, init_db, sync_achievements, get_theme, get_theme_by_name, get_locations, get_theme_stats
from geocode import geocode_postcode, geocode_postcodes_bulk, geocode_place_name, _http_get_json, _http_post_json

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "travel_assistant.db"
UPLOAD_DIR = DATA_DIR / "uploads"
STATIC_DIR = Path(__file__).parent / "static"

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".heic", ".heif"}

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Travel Assistant")

try:
    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
except Exception as _e:
    print(f"WARNING: could not mount /static: {_e}")


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
    def clean(v: str) -> str:
        s = (v or "")
        s = "".join(ch for ch in s if ch.isprintable())
        s = s.strip().strip('"').strip("'").strip()
        if s.lower().startswith("bearer "):
            s = s[7:].strip()
        return s
    ui = clean(str(load_ui_settings().get("xai_api_key") or ""))
    if ui and not ui.startswith("••••"):
        return ui
    return clean(addon_option("xai_api_key"))

def load_ui_settings() -> dict:
    out = dict(DEFAULT_UI)
    try:
        if UI_SETTINGS_PATH.exists():
            data = json.loads(UI_SETTINGS_PATH.read_text())
            if isinstance(data, dict):
                for k in DEFAULT_UI:
                    v = data.get(k)
                    if isinstance(v, str):
                        out[k] = v
    except Exception:
        pass
    return out


def save_ui_settings(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cleaned = dict(DEFAULT_UI)
    for k in DEFAULT_UI:
        v = settings.get(k, DEFAULT_UI[k])
        if isinstance(v, str):
            cleaned[k] = v
    UI_SETTINGS_PATH.write_text(json.dumps(cleaned, indent=2))


class _UIProxy:
    def __getattr__(self, key):
        return load_ui_settings().get(key, DEFAULT_UI.get(key, ""))




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


@app.on_event("startup")
async def startup():
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
    deps = {
        "get_db": get_db,
        "get_base": get_base,
        "redirect": redirect,
        "save_upload": save_upload,
        "geocode_postcode": geocode_postcode,
        "geocode_postcodes_bulk": geocode_postcodes_bulk,
        "geocode_place_name": geocode_place_name,
        "grok_key": grok_key,
        "load_ui_settings": load_ui_settings,
        "save_ui_settings": save_ui_settings,
        "list_assets": list_assets,
        "seed_category_icons": seed_category_icons,
        "_http_get_json": _http_get_json,
        "_http_post_json": _http_post_json,
        "get_theme": get_theme,
        "get_theme_by_name": get_theme_by_name,
        "get_locations": get_locations,
        "get_theme_stats": get_theme_stats,
        "sync_achievements": sync_achievements,
        "DEFAULT_UI": DEFAULT_UI,
    }
    try:
        from trips_routes import register_routes as register_trip_routes
        register_trip_routes(app, None, deps)
        print("Trip routes registered")
        from packing_routes import register_routes as register_packing_routes
        register_packing_routes(app, None, deps)
        print("Packing routes registered")
        from api_routes import register_routes as register_api_routes
        register_api_routes(app, None, deps)
        print("API routes registered")
        from theme_routes import register_routes as register_theme_routes
        register_theme_routes(app, None, deps)
        print("Theme routes registered")
    except Exception as e:
        print(f"ERROR: failed to register routes: {e}")
        import traceback
        traceback.print_exc()



@app.get("/")
async def root_redirect(request: Request):
    """Send the landing page to the React UI (frontend expects to run under /react for base path)."""
    return redirect(request, "/react")

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
    # Offline app manifest (dynamic, knows the Ingress base)
    html = html.replace(
        "</head>",
        f'<link rel="manifest" href="{base}/api/offline/manifest.webmanifest" crossorigin="use-credentials"></head>',
        1,
    )
    # Inject a tiny error surface so a JS failure is visible instead of a blank page
    html = html.replace(
        '<div id="root"></div>',
        """<div id="root"></div><script>window.addEventListener('error',function(e){document.body.insertAdjacentHTML('beforeend','<pre style="margin:1rem;padding:1rem;background:#fee;color:#900;white-space:pre-wrap">'+e.message+'</pre>')});</script>"""
    )
    return HTMLResponse(html)

@app.get("/offline-sw.js")
async def offline_sw():
    """Service worker with a header that lets it control the Ingress base path."""
    sw = STATIC_DIR / "react" / "sw.js"
    body = sw.read_text(encoding="utf-8") if sw.exists() else "/* service worker missing */"
    return Response(
        body,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )

@app.get("/api/offline/manifest.webmanifest")
async def offline_manifest(request: Request):
    """Web app manifest for the pinned Travel Assistant (Offline) app."""
    import json as _json
    base = get_base(request)
    manifest = {
        "name": "Travel Assistant (Offline)",
        "short_name": "TA Offline",
        "start_url": f"{base}/react?offline=1",
        "scope": f"{base}/" if base else "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f766e",
        "description": "Offline companion for Travel Assistant trips",
        "icons": [
            {"src": f"{base}/api/offline/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"{base}/api/offline/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ],
    }
    return Response(_json.dumps(manifest), media_type="application/manifest+json")

@app.get("/api/offline/icon-192.png")
async def offline_icon_192():
    from offline_manifest import icon_response
    return icon_response(192)

@app.get("/api/offline/icon-512.png")
async def offline_icon_512():
    from offline_manifest import icon_response
    return icon_response(512)


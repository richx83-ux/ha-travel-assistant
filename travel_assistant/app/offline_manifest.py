"""Web app manifest and icon serving for the Travel Assistant offline companion."""
import json
import io
from pathlib import Path
from fastapi import Request
from fastapi.responses import Response

STATIC_DIR = Path(__file__).parent / "static"

def get_base(request: Request) -> str:
    return request.headers.get("x-ingress-path", "").rstrip("/")

def offline_manifest_response(request: Request) -> Response:
    base = get_base(request)
    manifest = {
        "name": "Travel Assistant (Offline)",
        "short_name": "TA Offline",
        "description": "Offline companion for Travel Assistant trips",
        "start_url": f"{base}/react?offline=1",
        "scope": f"{base}/" if base else "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f766e",
        "icons": [
            {"src": f"{base}/api/offline/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"{base}/api/offline/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ],
    }
    return Response(json.dumps(manifest), media_type="application/manifest+json")

def icon_response(size: int) -> Response:
    """Serve a correctly sized PNG icon generated from house-icon.png."""
    try:
        from PIL import Image
        src = STATIC_DIR / "react" / "house-icon.png"
        if not src.exists():
            return Response(status_code=404)
        im = Image.open(src).convert("RGBA")
        w, h = im.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        sq = im.crop((left, top, left + side, top + side))
        out = sq.resize((size, size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png")
    except Exception:
        return Response(status_code=500)

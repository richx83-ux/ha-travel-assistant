"""Web app manifest for the Travel Assistant offline companion."""
import json
from fastapi import Request
from fastapi.responses import Response

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
            {"src": f"{base}/static/react/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"{base}/static/react/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ],
    }
    return Response(json.dumps(manifest), media_type="application/manifest+json")

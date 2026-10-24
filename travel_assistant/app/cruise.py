"""Cruise ship itinerary helpers.

A cruise_ship accommodation stores an itinerary as JSON on the location.
Normal accommodations keep a single static lat/lon.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

# Earth radius in km for great-circle
R_KM = 6371.0


def parse_itinerary(raw: Any) -> list[dict]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def is_cruise_ship(loc: dict) -> bool:
    if not loc:
        return False
    type_name = (loc.get("category_type_name") or "").strip().lower()
    if type_name in ("cruise ship", "cruise-ship", "cruise_ship"):
        return True
    # Fallback: has itinerary
    return bool(parse_itinerary(loc.get("itinerary_json")))


def get_current_location(loc: dict, on_date: Optional[str] = None) -> dict:
    """Return the location that should be used for 'where is this accommodation?'.

    For normal places: static lat/lon.
    For cruise ships: the matching itinerary day's port (or interpolated at-sea).
    """
    static = {
        "lat": loc.get("latitude"),
        "lon": loc.get("longitude"),
        "port": loc.get("city") or loc.get("name") or "",
        "status": "static",
        "day": None,
        "date": None,
    }
    if not is_cruise_ship(loc):
        return static

    itin = parse_itinerary(loc.get("itinerary_json"))
    if not itin:
        return static

    target = on_date or date.today().isoformat()
    # Exact date match
    for entry in itin:
        if (entry.get("date") or "")[:10] == target[:10]:
            return _entry_to_loc(entry)
    # Closest by date
    best = None
    best_diff = None
    try:
        t = datetime.fromisoformat(target[:10]).date()
    except Exception:
        t = date.today()
    for entry in itin:
        dstr = (entry.get("date") or "")[:10]
        try:
            d = datetime.fromisoformat(dstr).date()
            diff = abs((d - t).days)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best = entry
        except Exception:
            continue
    if best:
        return _entry_to_loc(best)
    return _entry_to_loc(itin[0])


def _entry_to_loc(entry: dict) -> dict:
    loc = entry.get("location") or {}
    return {
        "lat": loc.get("lat"),
        "lon": loc.get("lon"),
        "port": entry.get("port") or "",
        "status": entry.get("status") or "port",
        "day": entry.get("day"),
        "date": entry.get("date"),
    }


def interpolate_at_sea(prev_lat: float, prev_lon: float, next_lat: float, next_lon: float, progress: float = 0.5) -> dict:
    """Great-circle interpolation. progress 0.0 = previous, 1.0 = next."""
    progress = max(0.0, min(1.0, float(progress)))
    # Convert to radians
    φ1 = math.radians(prev_lat)
    λ1 = math.radians(prev_lon)
    φ2 = math.radians(next_lat)
    λ2 = math.radians(next_lon)

    d = 2 * math.asin(math.sqrt(
        math.sin((φ2 - φ1) / 2) ** 2 +
        math.cos(φ1) * math.cos(φ2) * math.sin((λ2 - λ1) / 2) ** 2
    ))
    if d == 0:
        return {"lat": prev_lat, "lon": prev_lon}

    a = math.sin((1 - progress) * d) / math.sin(d)
    b = math.sin(progress * d) / math.sin(d)

    x = a * math.cos(φ1) * math.cos(λ1) + b * math.cos(φ2) * math.cos(λ2)
    y = a * math.cos(φ1) * math.sin(λ1) + b * math.cos(φ2) * math.sin(λ2)
    z = a * math.sin(φ1) + b * math.sin(φ2)

    lat = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
    lon = math.degrees(math.atan2(y, x))
    return {"lat": round(lat, 5), "lon": round(lon, 5)}


def fill_at_sea_positions(itinerary: list[dict]) -> list[dict]:
    """For any at_sea entry with null location, interpolate between nearest ports."""
    ports = []
    for i, e in enumerate(itinerary):
        loc = e.get("location") or {}
        if loc.get("lat") is not None and loc.get("lon") is not None and (e.get("status") or "") != "at_sea":
            ports.append((i, float(loc["lat"]), float(loc["lon"])))

    for i, e in enumerate(itinerary):
        if (e.get("status") or "").lower() != "at_sea":
            continue
        loc = e.get("location") or {}
        if loc.get("lat") is not None and loc.get("lon") is not None:
            continue  # manual override
        # Find previous and next port
        prev = next((p for p in reversed(ports) if p[0] < i), None)
        nxt = next((p for p in ports if p[0] > i), None)
        if not prev or not nxt:
            continue
        # Progress based on day index between the two ports
        span = nxt[0] - prev[0]
        progress = (i - prev[0]) / span if span else 0.5
        pos = interpolate_at_sea(prev[1], prev[2], nxt[1], nxt[2], progress)
        e["location"] = pos
        e["progress"] = round(progress, 3)
    return itinerary


async def geocode_port(port: str) -> dict:
    """Geocode a port name. UK postcode via postcodes.io, otherwise Nominatim worldwide."""
    if not port or not port.strip() or port.strip().lower() in ("at sea", "sea day", "at-sea"):
        return {"lat": None, "lon": None}
    name = port.strip()
    # UK postcode pattern
    pc_match = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", name.upper())
    if pc_match:
        from main import geocode_postcode  # local import to avoid cycle at module load
        geo = await geocode_postcode(pc_match.group(1))
        if geo.get("latitude") is not None:
            return {"lat": geo["latitude"], "lon": geo["longitude"], "country": geo.get("country")}
    # Nominatim worldwide
    from main import _http_get_json
    import urllib.parse
    import asyncio
    q = urllib.parse.quote(name)
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1&addressdetails=1"
    result = await asyncio.to_thread(_http_get_json, url)
    if result and isinstance(result, list) and result:
        hit = result[0]
        try:
            return {
                "lat": float(hit["lat"]),
                "lon": float(hit["lon"]),
                "country": (hit.get("address") or {}).get("country"),
            }
        except Exception:
            pass
    return {"lat": None, "lon": None}


def extract_itinerary_from_html(html: str) -> list[dict]:
    """Best-effort extraction of day + port from cruise page HTML (P&O style)."""
    # Strip tags for text
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    # Look for patterns like "Day 1" ... port name
    days = []
    # Common patterns
    for m in re.finditer(r"(?:Day|DAY)\s*(\d+)[:\s]+([A-Z][A-Za-z\s,\.'-]{2,40})", text):
        day = int(m.group(1))
        port = m.group(2).strip(" ,.-")
        if port.lower() in ("at sea", "sea day", "at-sea"):
            status = "at_sea"
            port = "At sea"
        else:
            status = "port"
        days.append({"day": day, "port": port, "status": status, "location": {"lat": None, "lon": None}})
    # Deduplicate by day
    seen = set()
    out = []
    for d in days:
        if d["day"] in seen:
            continue
        seen.add(d["day"])
        out.append(d)
    return sorted(out, key=lambda x: x["day"])

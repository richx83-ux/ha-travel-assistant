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
    # Prefer the cruise / passenger terminal over the city centre
    from main import _http_get_json
    import urllib.parse
    import asyncio
    parts = [p.strip() for p in name.split(",") if p.strip()]
    city = parts[0]
    country = parts[-1] if len(parts) > 1 else ""
    where = f"{city}, {country}" if country else city
    queries = [
        f"Passenger Terminal {city}, {country}".strip(", "),
        f"{city} cruise terminal, {country}".strip(", "),
        f"Ocean Terminal {city}",
        f"{city} port, {country}".strip(", "),
        where,
    ]
    for query in queries:
        q = urllib.parse.quote(query)
        url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1&addressdetails=1"
        result = await asyncio.to_thread(_http_get_json, url)
        if result and isinstance(result, list) and result:
            hit = result[0]
            try:
                return {
                    "lat": float(hit["lat"]),
                    "lon": float(hit["lon"]),
                    "country": (hit.get("address") or {}).get("country"),
                    "label": hit.get("display_name") or query,
                }
            except Exception:
                continue
    return {"lat": None, "lon": None}



def extract_cruise_start(text: str) -> Optional[str]:
    """Find a departure date on the page (P&O style). Returns YYYY-MM-DD or None."""
    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    # Prefer labelled dates
    patterns = [
        r"(?:departs?|departure|sails?|embark)\s*[:\-]?\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        r"(\d{4})-(\d{2})-(\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        g = m.groups()
        if len(g) == 3 and g[0].isdigit() and len(g[0]) == 4:
            return f"{g[0]}-{g[1]}-{g[2]}"
        day, mon, year = g
        mi = months.get(mon.lower())
        if mi:
            try:
                return f"{int(year):04d}-{mi:02d}-{int(day):02d}"
            except Exception:
                continue
    return None


def extract_itinerary_from_html(html: str) -> list[dict]:
    """Extract day + clean port from a cruise page (P&O style).

    Only looks at the section between "Cruise itinerary" and "On this cruise"
    (or similar end markers). Matches every "Day X" followed by the port name.
    """
    # Drop scripts/styles, then tags to text while keeping line breaks from headings
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(h[1-6]|p|div|li|tr)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text, flags=re.I)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*", "\n", text)

    # Isolate itinerary section
    start_m = re.search(r"Cruise\s+itinerary", text, re.I)
    if start_m:
        text = text[start_m.end():]
    end_m = re.search(r"\n\s*(On this cruise|Overnight in port|What.?s included|About this cruise)\b", text, re.I)
    if end_m:
        text = text[:end_m.start()]

    # Match Day N followed by the port line (may be on next line, may have #####)
    days = []
    for m in re.finditer(
        r"Day\s*(\d+)\s*[:\-]?\s*(?:#{1,6}\s*)?([A-Z][^\n]{1,60})",
        text,
        re.I,
    ):
        day = int(m.group(1))
        port = m.group(2)
        port = re.sub(r"#{1,6}", "", port)
        port = re.sub(r"\s*(Day|On this cruise|Overnight.*|\bUK Day\b).*$", "", port, flags=re.I)
        port = port.strip(" ,.-:\t")
        port = re.sub(r"\s+", " ", port)
        if not port:
            continue
        # Normalise at sea
        if port.lower() in ("at sea", "at-sea", "sea day", "a day at sea"):
            port = "At sea"
            status = "at_sea"
        else:
            status = "port"
        days.append({
            "day": day,
            "port": port,
            "status": status,
            "location": {"lat": None, "lon": None},
        })

    # Deduplicate by day, keep first
    seen = set()
    out = []
    for d in days:
        if d["day"] in seen:
            continue
        seen.add(d["day"])
        out.append(d)
    out = sorted(out, key=lambda x: x["day"])
    # Stamp dates if a departure date was found on the page
    plain = re.sub(r"<[^>]+>", " ", html)
    start = extract_cruise_start(plain)
    if start and out:
        from datetime import date, timedelta
        try:
            base = date.fromisoformat(start)
            for e in out:
                e["date"] = (base + timedelta(days=int(e["day"]) - 1)).isoformat()
        except Exception:
            pass
    return out


def assign_dates(itinerary: list[dict], cruise_start: Optional[str] = None, trip_start: Optional[str] = None) -> list[dict]:
    """Fill date and trip_day. Cruise day 1 may not be trip day 1."""
    from datetime import date, timedelta
    if not itinerary:
        return itinerary
    # Cruise start: explicit, or first entry's date, or trip start
    start = None
    for candidate in (cruise_start, itinerary[0].get("date"), trip_start):
        if candidate:
            try:
                start = date.fromisoformat(str(candidate)[:10])
                break
            except Exception:
                continue
    if not start:
        return itinerary
    trip_base = None
    if trip_start:
        try:
            trip_base = date.fromisoformat(str(trip_start)[:10])
        except Exception:
            trip_base = None
    for e in itinerary:
        day = int(e.get("day") or 1)
        d = start + timedelta(days=day - 1)
        e["date"] = d.isoformat()
        if trip_base:
            e["trip_day"] = (d - trip_base).days + 1
        else:
            e["trip_day"] = day
    return itinerary


def extract_cruise_code(url: str) -> Optional[str]:
    """Pull a cruise code like N630 from a P&O-style URL."""
    m = re.search(r"/([A-Z]\d{2,})(?:/|$)", url or "", re.I)
    return m.group(1).upper() if m else None


def extract_day_images(html: str) -> dict:
    """Map day number -> image URL from itinerary cards. Ranges (Day 2-3) apply to each day."""
    # Keep a window of html around itinerary
    text = html
    images = {}
    # Find img tags and nearby Day N text
    for m in re.finditer(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", html, re.I):
        src = m.group(1)
        window = html[max(0, m.start() - 400):m.end() + 200]
        dm = re.search(r"Day\s*(\d+)(?:\s*[-–]\s*(\d+))?", window, re.I)
        if not dm:
            continue
        start = int(dm.group(1))
        end = int(dm.group(2)) if dm.group(2) else start
        for d in range(start, end + 1):
            if d not in images:
                images[d] = src
    return images


def extract_itinerary_from_seascanner(html: str) -> list[dict]:
    """Parse a SeaScanner itinerary table into day/port/date entries."""
    rows = re.findall(r'<tr class="Table-tr"[^>]*>(.*?)</tr>', html, re.S)
    days = []
    n = 0
    for row in rows:
        date_m = re.search(r'(\d{2})/(\d{2})/(\d{2})', row)
        if not date_m:
            continue
        dd, mm, yy = date_m.groups()
        date = f"20{yy}-{mm}-{dd}"
        dest_m = re.search(r'aria-label="([^"]+)"', row)
        port = dest_m.group(1).strip() if dest_m else ""
        if not port or "sea" in row.lower() and not dest_m:
            port = "At sea"
        if port.lower() in ("at sea", "sea day"):
            port = "At sea"
            status = "at_sea"
        else:
            status = "port"
        n += 1
        days.append({
            "day": n,
            "date": date,
            "port": port,
            "status": status,
            "location": {"lat": None, "lon": None},
        })
    if days:
        days[0]["status"] = "embarkation"
        if days[-1]["status"] != "at_sea":
            days[-1]["status"] = "disembarkation"
    return days


def extract_seascanner_code(html: str, url: str) -> Optional[str]:
    """Prefer the operator code (N630) from the page, else the SeaScanner id."""
    m = re.search(r'\(([A-Z]\d{2,})\)', html)
    if m:
        return m.group(1)
    m = re.search(r'cruise-k(\d+)', url or "", re.I)
    return f"K{m.group(1)}" if m else None

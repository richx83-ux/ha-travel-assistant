"""Trip planner and quick-visit routes for Travel Assistant."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse

app = None
templates = None
get_db = None
get_base = None
redirect = None
save_upload = None
_http_get_json = None


LOCAL_TZ = ZoneInfo("Europe/London")


def _now():
    return datetime.now(LOCAL_TZ)


def format_duration(secs: Optional[int]) -> str:
    if secs is None:
        return "—"
    mins = int(round(secs / 60))
    if mins <= 0:
        return "0 min"
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _hours_conflict(stop, arrive_hhmm: Optional[str]):
    text = (stop or {}).get("opening_hours") or ""
    match = re.search(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})", text)
    if not match or not arrive_hhmm or ":" not in arrive_hhmm:
        return None
    open_m = int(match.group(1)) * 60 + int(match.group(2))
    close_m = int(match.group(3)) * 60 + int(match.group(4))
    hour, minute = [int(p) for p in arrive_hhmm.split(":", 1)]
    arrive = hour * 60 + minute
    if arrive < open_m:
        return f"Arrives {arrive_hhmm}, opens {_hhmm(open_m)}"
    if arrive >= close_m:
        return f"Arrives {arrive_hhmm}, closes {_hhmm(close_m)}"
    leave = arrive + _visit_mins(stop)
    if leave > close_m:
        return f"Visit runs to {_hhmm(leave)}, closes {_hhmm(close_m)}"
    return None


def _hhmm(mins: int) -> str:
    mins = int(round(mins)) % (24 * 60)
    h, m = divmod(mins, 60)
    return f"{h:02d}:{m:02d}"


def format_distance(meters: Optional[int]) -> str:
    if meters is None:
        return ""
    if meters < 1000:
        return f"{meters} m"
    return f"{meters / 1000:.1f} km"


def format_miles(meters: Optional[int]) -> str:
    if not meters:
        return ""
    miles = meters / 1609.344
    return f"{miles:.1f} mi" if miles >= 0.1 else f"{int(round(meters))} m"


async def osrm_route(coords: list, profile: str = "driving", overview: str = "false") -> dict:
    """Return legs (and optional geometry) from OSRM. overview is 'false', 'simplified' or 'full'."""
    if len(coords) < 2:
        return {"legs": [], "geometry": None}
    parts = ";".join(f"{lng},{lat}" for lat, lng in coords)
    url = (
        f"https://router.project-osrm.org/route/v1/{profile}/{parts}"
        f"?overview={overview}&geometries=polyline&annotations=false"
    )
    result = await asyncio.to_thread(_http_get_json, url, 20.0)
    empty_legs = [{"duration_secs": None, "distance_m": None} for _ in range(len(coords) - 1)]
    if not result or result.get("code") != "Ok":
        return {"legs": empty_legs, "geometry": None}
    routes = result.get("routes") or []
    if not routes:
        return {"legs": empty_legs, "geometry": None}
    route = routes[0]
    legs = []
    for leg in route.get("legs") or []:
        legs.append({
            "duration_secs": int(round(leg.get("duration") or 0)),
            "distance_m": int(round(leg.get("distance") or 0)),
        })
    while len(legs) < len(coords) - 1:
        legs.append({"duration_secs": None, "distance_m": None})
    geometry = route.get("geometry") if overview and overview != "false" else None
    return {"legs": legs, "geometry": geometry}


async def osrm_leg_times(coords: list, profile: str = "driving") -> list:
    """Backward-compatible wrapper that returns only the legs."""
    return (await osrm_route(coords, profile, "false"))["legs"]


async def get_trip(trip_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

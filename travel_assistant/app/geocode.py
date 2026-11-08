"""Geocoding helpers for Travel Assistant."""
from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from typing import Optional

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

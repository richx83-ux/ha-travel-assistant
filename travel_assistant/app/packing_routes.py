"""Kit library and trip packing for Travel Assistant."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

from fastapi import Request, Form
from fastapi.responses import HTMLResponse

get_db = None
get_base = None
redirect = None
templates = None
app = None

SUGGESTIONS = [
    {"name": "Underwear", "category": "Clothes", "per_day": 1, "tags": []},
    {"name": "Socks", "category": "Clothes", "per_day": 1, "tags": []},
    {"name": "Hiking socks", "category": "Clothes", "per_day": 1, "tags": ["hiking", "cold"]},
    {"name": "Short sleeve shirts", "category": "Clothes", "per_day": 1, "tags": ["hot"]},
    {"name": "Long sleeve shirts", "category": "Clothes", "per_day": 1, "tags": ["cold", "mild"]},
    {"name": "T-shirts", "category": "Clothes", "per_day": 1, "tags": []},
    {"name": "Trousers", "category": "Clothes", "per_day": 1, "tags": []},
    {"name": "Jeans", "category": "Clothes", "per_day": 0, "tags": []},
    {"name": "Hiking shorts", "category": "Clothes", "per_day": 1, "tags": ["hiking", "hot"]},
    {"name": "Shorts", "category": "Clothes", "per_day": 1, "tags": ["hot"]},
    {"name": "Hotel room clothes", "category": "Clothes", "per_day": 0, "tags": []},
    {"name": "Pyjamas", "category": "Clothes", "per_day": 0, "tags": []},
    {"name": "Formal shirt", "category": "Clothes", "per_day": 0, "tags": ["formal"]},
    {"name": "Formal trousers", "category": "Clothes", "per_day": 0, "tags": ["formal"]},
    {"name": "Jacket", "category": "Clothes", "per_day": 0, "tags": ["cold", "mild"]},
    {"name": "Waterproof jacket", "category": "Clothes", "per_day": 0, "tags": ["rain"]},
    {"name": "Fleece", "category": "Clothes", "per_day": 0, "tags": ["cold"]},
    {"name": "Sunglasses", "category": "Clothes", "per_day": 0, "tags": ["hot"]},
    {"name": "Sunglasses case", "category": "Clothes", "per_day": 0, "tags": []},
    {"name": "Sun hat", "category": "Clothes", "per_day": 0, "tags": ["hot"]},
    {"name": "Warm hat", "category": "Clothes", "per_day": 0, "tags": ["cold"]},
    {"name": "Gloves", "category": "Clothes", "per_day": 0, "tags": ["cold"]},
    {"name": "Trainers", "category": "Clothes", "per_day": 0, "tags": []},
    {"name": "Walking shoes", "category": "Clothes", "per_day": 0, "tags": ["hiking"]},
    {"name": "Smart shoes", "category": "Clothes", "per_day": 0, "tags": ["formal"]},
    {"name": "Belt", "category": "Clothes", "per_day": 0, "tags": []},
    {"name": "Toothbrush", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Toothpaste", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Deodorant", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Razor", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Shampoo", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Soap", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Hairbrush", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Moisturiser", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Sunscreen", "category": "Toiletries", "per_day": 0, "tags": ["hot"], "bag": "Toiletry bag"},
    {"name": "Lip balm", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Nail clippers", "category": "Toiletries", "per_day": 0, "tags": [], "bag": "Toiletry bag"},
    {"name": "Phone charger", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Charging cable", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Power bank", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Headphones", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Earbuds", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Smartwatch", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Watch charger", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "USB cable", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Laptop charger", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Travel adapter", "category": "Tech", "per_day": 0, "tags": [], "bag": "Tech bag"},
    {"name": "Passport", "category": "Documents", "per_day": 0, "tags": []},
    {"name": "Driving licence", "category": "Documents", "per_day": 0, "tags": []},
    {"name": "Membership card", "category": "Documents", "per_day": 0, "tags": []},
    {"name": "Wallet", "category": "Documents", "per_day": 0, "tags": []},
    {"name": "Hotel booking", "category": "Documents", "per_day": 0, "tags": []},
    {"name": "Travel insurance", "category": "Documents", "per_day": 0, "tags": []},
    {"name": "Medication", "category": "Health", "per_day": 0, "tags": []},
    {"name": "Electrolyte tablets", "category": "Health", "per_day": 0, "tags": ["hot", "hiking"]},
    {"name": "First aid kit", "category": "Health", "per_day": 0, "tags": ["hiking"]},
    {"name": "Water bottle", "category": "Other", "per_day": 0, "tags": []},
    {"name": "Reusable water bottle", "category": "Other", "per_day": 0, "tags": []},
    {"name": "Bottled water", "category": "Other", "per_day": 0, "tags": []},
    {"name": "Tea bags", "category": "Other", "per_day": 0, "tags": []},
    {"name": "Snacks", "category": "Other", "per_day": 0, "tags": []},
    {"name": "Reusable bag", "category": "Other", "per_day": 0, "tags": []},
    {"name": "Book or kindle", "category": "Other", "per_day": 0, "tags": []},
]


def _trip_days(trip: dict) -> int:
    try:
        if trip.get("start_date") and trip.get("end_date"):
            start = date.fromisoformat(str(trip["start_date"])[:10])
            end = date.fromisoformat(str(trip["end_date"])[:10])
            return max(1, (end - start).days + 1)
    except Exception:
        pass
    return 1


def _need(item: dict, days: int) -> int:
    base = max(1, int(item.get("qty") or 1))
    if item.get("per_day"):
        return base * max(1, days)
    return base


def _weather_tags(summary: dict) -> list[str]:
    tags = []
    if not summary:
        return tags
    tmax = summary.get("max_temp")
    tmin = summary.get("min_temp")
    rain = summary.get("rain_mm") or 0
    if tmax is not None and tmax >= 22:
        tags.append("hot")
    if tmin is not None and tmin <= 8:
        tags.append("cold")
    if tmax is not None and 12 <= tmax < 22:
        tags.append("mild")
    if rain >= 3:
        tags.append("rain")
    return tags


def _fetch_weather(lat: float, lng: float, start: str | None, end: str | None) -> dict | None:
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lng}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            "&timezone=Europe/London"
        )
        if start and end:
            url += f"&start_date={start}&end_date={end}"
        req = urllib.request.Request(url, headers={"User-Agent": "TravelAssistant/1.2"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        daily = data.get("daily") or {}
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        rain = daily.get("precipitation_sum") or []
        if not tmax:
            return None
        return {
            "max_temp": max(tmax),
            "min_temp": min(tmin) if tmin else None,
            "rain_mm": sum(rain) if rain else 0,
            "days": len(tmax),
        }
    except Exception:
        return None


def _item_category(name: str) -> str:
    for template in BAG_TEMPLATES.values():
        if name in template["items"]:
            return template["category"]
    for s in SUGGESTIONS:
        if s["name"] == name:
            return s["category"]
    return ""


async def _tidy_wardrobe():
    async with get_db() as db:
        items = [dict(r) for r in await (await db.execute("SELECT * FROM kit_items ORDER BY id")).fetchall()]
        seen = set()
        for it in items:
            key = (it["name"].strip().lower(), it.get("bag_id"))
            if key in seen:
                await db.execute("DELETE FROM kit_items WHERE id = ?", (it["id"],))
                continue
            seen.add(key)
            cat = _item_category(it["name"])
            if cat and cat != it.get("category"):
                await db.execute("UPDATE kit_items SET category = ? WHERE id = ?", (cat, it["id"]))
        await db.commit()
    try:
        q = urllib.parse.quote(name.strip())
        url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "TravelAssistant/1.2"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        if not data:
            return None
        return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"]), "name": data[0].get("display_name", name)}
    except Exception:
        return None


BAG_TEMPLATES = {
    "toiletry": {
        "name": "Toiletry bag",
        "category": "Toiletries",
        "items": ["Toothbrush", "Toothpaste", "Dental floss", "Deodorant", "Razor", "Shaving cream",
                  "Shampoo", "Conditioner", "Soap", "Hairbrush", "Moisturiser", "Sunscreen",
                  "Lip balm", "Nail clippers", "Tweezers", "Cotton buds", "Hair ties"],
    },
    "tech": {
        "name": "Tech bag",
        "category": "Tech",
        "items": ["Phone charger", "Charging cable", "Power bank", "Headphones", "Earbuds", "Smartwatch",
                  "Watch charger", "USB cable", "Laptop charger", "Travel adapter", "Camera",
                  "Memory card", "Kindle charger", "Cable organiser"],
    },
    "documents": {
        "name": "Documents pouch",
        "category": "Documents",
        "items": ["Passport", "Driving licence", "Membership card", "Wallet", "Hotel booking",
                  "Travel insurance", "Car documents", "Cash", "Cards"],
    },
    "firstaid": {
        "name": "First aid kit",
        "category": "Health",
        "items": ["Plasters", "Blister plasters", "Painkillers", "Antiseptic", "Antihistamine",
                  "Electrolyte tablets", "Any prescription medication", "Insect repellent"],
    },
    "day": {
        "name": "Day bag",
        "category": "Other",
        "items": ["Water bottle", "Reusable water bottle", "Bottled water", "Snacks", "Sunglasses",
                  "Sunglasses case", "Sun hat", "Reusable bag", "Tissues", "Hand sanitiser",
                  "Book or kindle", "Tea bags"],
    },
}


def register_routes(_app, _templates, deps: dict):
    global app, templates, get_db, get_base, redirect
    app = _app
    templates = _templates
    get_db = deps["get_db"]
    get_base = deps["get_base"]
    redirect = deps["redirect"]

    @app.get("/packing", response_class=HTMLResponse)
    async def kit_library(request: Request, wizard: str = ""):
        await _tidy_wardrobe()
        async with get_db() as db:
            bags = [dict(r) for r in await (await db.execute("SELECT * FROM kit_bags ORDER BY sort_order, name")).fetchall()]
            items = [dict(r) for r in await (await db.execute("SELECT * FROM kit_items ORDER BY sort_order, name")).fetchall()]
        by_bag = {}
        clothes = []
        for it in items:
            if it.get("bag_id"):
                by_bag.setdefault(it["bag_id"], []).append(it)
            else:
                clothes.append(it)
        return templates.TemplateResponse("packing.html", {
            "request": request, "base": get_base(request), "active_nav": "packing",
            "bags": bags, "by_bag": by_bag, "clothes": clothes,
            "bag_templates": BAG_TEMPLATES, "wizard": wizard,
        })

    @app.post("/packing/bag/wizard")
    async def bag_wizard(request: Request):
        form = await request.form()
        kind = form.get("kind") or "custom"
        name = (form.get("name") or "").strip()
        items = form.getlist("item")
        custom = (form.get("custom") or "").strip()
        template = BAG_TEMPLATES.get(kind) or {}
        allowed = set(template.get("items") or [])
        bag_name = name or template.get("name") or "Bag"
        category = template.get("category") or "Other"
        async with get_db() as db:
            cursor = await db.execute(
                "INSERT INTO kit_bags (name, category) VALUES (?, ?)", (bag_name, category)
            )
            bag_id = cursor.lastrowid
            for item in items:
                item = item.strip()
                if not item or (allowed and item not in allowed):
                    continue
                await db.execute(
                    "INSERT INTO kit_items (bag_id, name, category) VALUES (?, ?, ?)",
                    (bag_id, item, category),
                )
            if custom:
                await db.execute(
                    "INSERT INTO kit_items (bag_id, name, category) VALUES (?, ?, ?)",
                    (bag_id, custom, category),
                )
            await db.commit()
        return redirect(request, "/packing")

    @app.post("/packing/bag")
    async def add_bag(request: Request, name: str = Form(...), category: str = Form("")):
        async with get_db() as db:
            await db.execute("INSERT INTO kit_bags (name, category) VALUES (?, ?)", (name.strip(), category.strip()))
            await db.commit()
        return redirect(request, "/packing")

    @app.post("/packing/item")
    async def add_item(
        request: Request, name: str = Form(...), category: str = Form(""),
        bag_id: str = Form(""), per_day: str = Form(""), qty: int = Form(1),
    ):
        bag = int(bag_id) if bag_id.isdigit() else None
        async with get_db() as db:
            await db.execute(
                "INSERT INTO kit_items (bag_id, name, category, per_day, qty) VALUES (?, ?, ?, ?, ?)",
                (bag, name.strip(), category.strip(), 1 if per_day else 0, max(1, qty)),
            )
            await db.commit()
        return redirect(request, "/packing")

    @app.post("/packing/item/{item_id}/delete")
    async def delete_item(request: Request, item_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM kit_items WHERE id = ?", (item_id,))
            await db.commit()
        return redirect(request, "/packing")

    @app.post("/packing/bag/{bag_id}/delete")
    async def delete_bag(request: Request, bag_id: int):
        async with get_db() as db:
            await db.execute("UPDATE kit_items SET bag_id = NULL WHERE bag_id = ?", (bag_id,))
            await db.execute("DELETE FROM kit_bags WHERE id = ?", (bag_id,))
            await db.commit()
        return redirect(request, "/packing")

    @app.get("/trip/{trip_id}/prepare", response_class=HTMLResponse)
    async def prepare(request: Request, trip_id: int, place: str = ""):
        async with get_db() as db:
            trip = dict(await (await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))).fetchone() or {})
            if not trip:
                return redirect(request, "/packing")
            kit = [dict(r) for r in await (await db.execute(
                "SELECT * FROM trip_kit WHERE trip_id = ? ORDER BY sort_order, name", (trip_id,)
            )).fetchall()]
            stop = await (await db.execute(
                """SELECT l.latitude, l.longitude, l.city, l.county FROM trip_stops s
                   JOIN locations l ON l.id = s.location_id
                   WHERE s.trip_id = ? AND l.latitude IS NOT NULL LIMIT 1""",
                (trip_id,),
            )).fetchone()
        days = _trip_days(trip)
        weather = None
        weather_place = place.strip()
        tags = []
        lat = lng = None
        if place.strip():
            geo = _geocode(place.strip())
            if geo:
                lat, lng = geo["lat"], geo["lng"]
                weather_place = geo["name"]
        elif stop and stop["latitude"]:
            lat, lng = stop["latitude"], stop["longitude"]
            weather_place = ", ".join(x for x in (stop["city"], stop["county"]) if x) or "trip location"
        if lat is not None:
            weather = _fetch_weather(lat, lng, trip.get("start_date"), trip.get("end_date"))
            tags = _weather_tags(weather)
        async with get_db() as db:
            wardrobe = [dict(r) for r in await (await db.execute(
                """SELECT i.*, b.name AS bag_name FROM kit_items i
                   LEFT JOIN kit_bags b ON b.id = i.bag_id
                   ORDER BY b.name, i.name"""
            )).fetchall()]
        for it in kit:
            it["need"] = _need(it, days)
        return templates.TemplateResponse("prepare.html", {
            "request": request, "base": get_base(request), "active_nav": "packing",
            "trip": trip, "days": days, "kit": kit, "wardrobe": wardrobe,
            "weather": weather, "weather_place": weather_place, "tags": tags, "place": place,
        })

    @app.post("/trip/{trip_id}/prepare/add")
    async def prepare_add(request: Request, trip_id: int):
        form = await request.form()
        ids = [int(x) for x in form.getlist("item") if str(x).isdigit()]
        bag_ids = [int(x) for x in form.getlist("bag") if str(x).isdigit()]
        custom = (form.get("custom") or "").strip()
        async with get_db() as db:
            trip = dict(await (await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))).fetchone() or {})
            days = _trip_days(trip)
            order = (await (await db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) AS n FROM trip_kit WHERE trip_id = ?", (trip_id,)
            )).fetchone())["n"] or 0
            rows = []
            for item_id in ids:
                row = await (await db.execute("SELECT * FROM kit_items WHERE id = ?", (item_id,))).fetchone()
                if row:
                    rows.append(dict(row))
            for bag_id in bag_ids:
                bag_rows = await (await db.execute("SELECT * FROM kit_items WHERE bag_id = ?", (bag_id,))).fetchall()
                rows.extend(dict(r) for r in bag_rows)
            for it in rows:
                order += 1
                needed = _need(it, days)
                await db.execute(
                    """INSERT INTO trip_kit (trip_id, kit_item_id, bag_id, name, category, per_day, qty, needed, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (trip_id, it["id"], it.get("bag_id"), it["name"], it.get("category") or "",
                     it.get("per_day") or 0, it.get("qty") or 1, needed, order),
                )
            if custom:
                order += 1
                await db.execute(
                    """INSERT INTO trip_kit (trip_id, name, category, per_day, qty, needed, sort_order)
                       VALUES (?, ?, 'Other', 0, 1, 1, ?)""",
                    (trip_id, custom, order),
                )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/prepare")

    @app.post("/trip/{trip_id}/prepare/{item_id}/delete")
    async def prepare_delete(request: Request, trip_id: int, item_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM trip_kit WHERE id = ? AND trip_id = ?", (item_id, trip_id))
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/prepare")

    @app.get("/trip/{trip_id}/pack", response_class=HTMLResponse)
    async def pack(request: Request, trip_id: int):
        async with get_db() as db:
            trip = dict(await (await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))).fetchone() or {})
            if not trip:
                return redirect(request, "/packing")
            kit = [dict(r) for r in await (await db.execute(
                "SELECT * FROM trip_kit WHERE trip_id = ? ORDER BY sort_order, name", (trip_id,)
            )).fetchall()]
            bags = [dict(r) for r in await (await db.execute("SELECT * FROM kit_bags ORDER BY name")).fetchall()]
        days = _trip_days(trip)
        for it in kit:
            it["need"] = _need(it, days)
        by_bag = {}
        loose = []
        for it in kit:
            if it.get("bag_id"):
                by_bag.setdefault(it["bag_id"], []).append(it)
            else:
                loose.append(it)
        packed = sum(1 for it in kit if it.get("packed"))
        return templates.TemplateResponse("pack.html", {
            "request": request, "base": get_base(request), "active_nav": "packing",
            "trip": trip, "days": days, "kit": kit, "bags": bags,
            "by_bag": by_bag, "loose": loose, "packed": packed, "total": len(kit),
        })

    @app.post("/trip/{trip_id}/pack/{item_id}/toggle")
    async def pack_toggle(request: Request, trip_id: int, item_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE trip_kit SET packed = CASE WHEN packed = 1 THEN 0 ELSE 1 END WHERE id = ? AND trip_id = ?",
                (item_id, trip_id),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/pack")

    @app.post("/trip/{trip_id}/pack/{item_id}/bag")
    async def pack_bag(request: Request, trip_id: int, item_id: int, bag_id: str = Form("")):
        bag = int(bag_id) if bag_id.isdigit() else None
        async with get_db() as db:
            await db.execute(
                "UPDATE trip_kit SET bag_id = ? WHERE id = ? AND trip_id = ?",
                (bag, item_id, trip_id),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/pack")

"""Kit library and trip packing for Travel Assistant."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse

get_db = None
get_base = None
redirect = None
templates = None
app = None

SUGGESTIONS = [
    {"name": "Underwear", "category": "Clothes", "every_days": 1, "tags": []},
    {"name": "Socks", "category": "Clothes", "every_days": 1, "tags": []},
    {"name": "Hiking socks", "category": "Clothes", "every_days": 1, "tags": ["hiking", "cold"]},
    {"name": "Short sleeve shirts", "category": "Clothes", "every_days": 3, "tags": ["hot"]},
    {"name": "Long sleeve shirts", "category": "Clothes", "every_days": 3, "tags": ["cold", "mild"]},
    {"name": "T-shirts", "category": "Clothes", "every_days": 3, "tags": []},
    {"name": "Trousers", "category": "Clothes", "every_days": 3, "tags": []},
    {"name": "Jeans", "category": "Clothes", "every_days": 0, "tags": []},
    {"name": "Hiking shorts", "category": "Clothes", "every_days": 3, "tags": ["hiking", "hot"]},
    {"name": "Shorts", "category": "Clothes", "every_days": 3, "tags": ["hot"]},
    {"name": "Hotel room clothes", "category": "Clothes", "every_days": 0, "tags": []},
    {"name": "Pyjamas", "category": "Clothes", "every_days": 0, "tags": []},
    {"name": "Formal shirt", "category": "Clothes", "every_days": 0, "tags": ["formal"]},
    {"name": "Formal trousers", "category": "Clothes", "every_days": 0, "tags": ["formal"]},
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
    every = int(item.get("every_days") or 0)
    if every > 0:
        return base * max(1, -(-max(1, days) // every))
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
            sug = next((s for s in SUGGESTIONS if s["name"] == it["name"]), None)
            every = sug.get("every_days", 0) if sug else int(it.get("every_days") or 0)
            if sug and every != int(it.get("every_days") or 0):
                await db.execute("UPDATE kit_items SET every_days = ? WHERE id = ?", (every, it["id"]))
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

    @app.post("/packing/suggest")
    async def add_clothing(request: Request):
        form = await request.form()
        names = form.getlist("item")
        async with get_db() as db:
            existing = {r["name"].strip().lower() for r in await (await db.execute("SELECT name FROM kit_items")).fetchall()}
            for name in names:
                sug = next((s for s in SUGGESTIONS if s["name"] == name), None)
                if not sug or name.strip().lower() in existing:
                    continue
                await db.execute(
                    """INSERT INTO kit_items (bag_id, name, category, per_day, every_days, qty)
                       VALUES (NULL, ?, ?, ?, ?, ?)""",
                    (sug["name"], sug["category"], 1 if sug.get("every_days") else 0,
                     sug.get("every_days", 0), sug.get("qty", 1)),
                )
            await db.commit()
        return redirect(request, "/packing")

    @app.post("/packing/item/{item_id}/rename")
    async def rename_item(request: Request, item_id: int, name: str = Form(...)):
        async with get_db() as db:
            await db.execute("UPDATE kit_items SET name = ? WHERE id = ?", (name.strip(), item_id))
            await db.commit()
        return redirect(request, "/packing")

    @app.post("/packing/item/{item_id}/move")
    async def move_item(request: Request, item_id: int, bag_id: str = Form(...)):
        async with get_db() as db:
            await db.execute(
                "UPDATE kit_items SET bag_id = ? WHERE id = ?",
                (int(bag_id) if bag_id.isdigit() else None, item_id),
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

    @app.post("/trip/{trip_id}/prepare/reset")
    async def prepare_reset(request: Request, trip_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM trip_kit WHERE trip_id = ?", (trip_id,))
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/prepare")

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
                    """INSERT INTO trip_kit (trip_id, kit_item_id, bag_id, name, category, per_day, every_days, qty, needed, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (trip_id, it["id"], it.get("bag_id"), it["name"], it.get("category") or "",
                     it.get("per_day") or 0, it.get("every_days") or 0, it.get("qty") or 1, needed, order),
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


    # --- JSON APIs for React Store cupboard ---

    
    @app.get("/api/trips/{trip_id}/packing-list")
    async def api_trip_packing_list(request: Request, trip_id: int):
        from datetime import date as _date
        async with get_db() as db:
            trip = await (await db.execute("SELECT start_date, end_date FROM trips WHERE id = ?", (trip_id,))).fetchone()
            if not trip:
                raise HTTPException(status_code=404, detail="Trip not found")
            days = 1
            if trip["start_date"] and trip["end_date"]:
                try:
                    a = _date.fromisoformat(str(trip["start_date"])[:10])
                    b = _date.fromisoformat(str(trip["end_date"])[:10])
                    days = max(1, (b - a).days + 1)
                except Exception:
                    days = 1
            items = [dict(r) for r in await (await db.execute(
                """SELECT i.*, c.name as clothing_type, c.lasts_days, b.name as bag_name
                   FROM kit_items i
                   LEFT JOIN clothing_categories c ON c.id = i.clothing_category_id
                   LEFT JOIN kit_bags b ON b.id = i.bag_id
                   ORDER BY i.bag_id IS NULL, b.name, i.category, i.name"""
            )).fetchall()]
        out = []
        for it in items:
            lasts = int(it.get("lasts_days") or 0)
            qty = max(1, int(it.get("qty") or 1))
            if lasts <= 0:
                need = qty  # whole trip
            else:
                need = qty * max(1, -(-days // lasts))  # ceil
            out.append({
                "id": it["id"],
                "name": it["name"],
                "category": it.get("category") or "Other",
                "clothing_type": it.get("clothing_type") or "",
                "lasts_days": lasts,
                "need": need,
                "image_url": it.get("image_url") or "",
                "in_bag": bool(it.get("bag_id")),
                "bag_name": it.get("bag_name") or "",
            })
        return {"ok": True, "days": days, "items": out}

    
    
    
    @app.post("/api/trips/{trip_id}/luggage/{item_id}/delete")
    async def api_trip_delete_luggage(trip_id: int, item_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM trip_kit WHERE id = ? AND trip_id = ?", (item_id, trip_id))
            await db.commit()
        return {"ok": True}

    @app.post("/api/trips/{trip_id}/luggage/{item_id}/packed")
    async def api_trip_mark_packed(trip_id: int, item_id: int, request: Request):
        body = await request.json()
        packed = 1 if body.get("packed") else 0
        async with get_db() as db:
            await db.execute("UPDATE trip_kit SET packed = ? WHERE id = ? AND trip_id = ?", (packed, item_id, trip_id))
            await db.commit()
        return {"ok": True}

    @app.get("/api/trips/{trip_id}/luggage")
    async def api_trip_luggage(trip_id: int):
        import json as _json
        async with get_db() as db:
            items = [dict(r) for r in await (await db.execute(
                """SELECT tk.*, c.name as clothing_type, b.name as bag_name
                   FROM trip_kit tk
                   LEFT JOIN kit_items i ON i.id = tk.kit_item_id
                   LEFT JOIN clothing_categories c ON c.id = i.clothing_category_id
                   LEFT JOIN kit_bags b ON b.id = tk.bag_id
                   WHERE tk.trip_id = ?
                   ORDER BY tk.sort_order, tk.name""",
                (trip_id,),
            )).fetchall()]
            row = await (await db.execute("SELECT plan_json FROM trips WHERE id = ?", (trip_id,))).fetchone()
        extras = []
        if row and row["plan_json"]:
            try:
                data = _json.loads(row["plan_json"])
                extras = (data.get("result") or {}).get("extra") or []
            except Exception:
                extras = []
        return {"ok": True, "items": items, "extra": extras}

    @app.post("/api/trips/{trip_id}/luggage/add")
    async def api_trip_add_luggage(request: Request, trip_id: int):
        """Add one or more items to a trip's packing list without wiping existing items or packed status."""
        body = await request.json()
        # Support either a list of items or a single item
        items_in = body.get("items") or ([body] if body.get("name") or body.get("kit_item_id") else [])
        if not items_in:
            raise HTTPException(status_code=400, detail="No items to add")
        added = 0
        async with get_db() as db:
            order_row = await (await db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) AS n FROM trip_kit WHERE trip_id = ?", (trip_id,)
            )).fetchone()
            order = (order_row["n"] or 0) if order_row else 0
            trip = await (await db.execute("SELECT start_date, end_date FROM trips WHERE id = ?", (trip_id,))).fetchone()
            days = 1
            if trip and trip["start_date"] and trip["end_date"]:
                from datetime import date as _date
                try:
                    a = _date.fromisoformat(str(trip["start_date"])[:10])
                    b = _date.fromisoformat(str(trip["end_date"])[:10])
                    days = max(1, (b - a).days + 1)
                except Exception:
                    days = 1
            for raw in items_in:
                name = (raw.get("name") or "").strip()
                if not name:
                    continue
                kit_id = raw.get("kit_item_id")
                category = (raw.get("category") or "Other").strip()
                qty = max(1, int(raw.get("qty") or 1))
                bag_id = raw.get("bag_id")
                # If kit_item_id given, pull defaults from kit_items
                if kit_id:
                    row = await (await db.execute("SELECT * FROM kit_items WHERE id = ?", (kit_id,))).fetchone()
                    if row:
                        it = dict(row)
                        name = it.get("name") or name
                        category = it.get("category") or category
                        qty = max(1, int(it.get("qty") or qty))
                        bag_id = it.get("bag_id") if bag_id is None else bag_id
                lasts = int(raw.get("lasts_days") or 0)
                need = qty if lasts <= 0 else qty * max(1, -(-days // lasts))
                order += 1
                await db.execute(
                    """INSERT INTO trip_kit (trip_id, kit_item_id, bag_id, name, category, per_day, qty, needed, packed, sort_order)
                       VALUES (?, ?, ?, ?, ?, 0, ?, ?, 0, ?)""",
                    (trip_id, kit_id, bag_id, name, category, qty, need, order),
                )
                added += 1
            await db.commit()
        return {"ok": True, "added": added}

    @app.post("/api/trips/{trip_id}/packing")
    async def api_trip_save_packing(request: Request, trip_id: int):
        body = await request.json()
        ids = [int(i) for i in (body.get("item_ids") or []) if str(i).isdigit() or isinstance(i, int)]
        async with get_db() as db:
            await db.execute("DELETE FROM trip_kit WHERE trip_id = ?", (trip_id,))
            if ids:
                placeholders = ",".join("?" * len(ids))
                rows = [dict(r) for r in await (await db.execute(
                    f"""SELECT i.*, c.lasts_days
                        FROM kit_items i
                        LEFT JOIN clothing_categories c ON c.id = i.clothing_category_id
                        WHERE i.id IN ({placeholders})""",
                    ids,
                )).fetchall()]
                trip = await (await db.execute("SELECT start_date, end_date FROM trips WHERE id = ?", (trip_id,))).fetchone()
                days = 1
                if trip and trip["start_date"] and trip["end_date"]:
                    from datetime import date as _date
                    try:
                        a = _date.fromisoformat(str(trip["start_date"])[:10])
                        b = _date.fromisoformat(str(trip["end_date"])[:10])
                        days = max(1, (b - a).days + 1)
                    except Exception:
                        days = 1
                for i, it in enumerate(rows):
                    lasts = int(it.get("lasts_days") or 0)
                    qty = max(1, int(it.get("qty") or 1))
                    need = qty if lasts <= 0 else qty * max(1, -(-days // lasts))
                    await db.execute(
                        """INSERT INTO trip_kit (trip_id, kit_item_id, bag_id, name, category, per_day, qty, needed, packed, sort_order)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                        (trip_id, it["id"], it.get("bag_id"), it["name"], it.get("category") or "", it.get("per_day") or 0, qty, need, i),
                    )
            await db.commit()
        return {"ok": True, "count": len(ids)}

    @app.get("/api/packing")
    async def api_packing(request: Request):
        async with get_db() as db:
            bags = [dict(r) for r in await (await db.execute("SELECT * FROM kit_bags ORDER BY sort_order, name")).fetchall()]
            items = [dict(r) for r in await (await db.execute("SELECT * FROM kit_items ORDER BY sort_order, name")).fetchall()]
        return {"bags": bags, "items": items}

    @app.post("/api/packing/bag")
    async def api_add_bag(request: Request):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name required")
        category = (body.get("category") or "").strip()
        async with get_db() as db:
            cursor = await db.execute(
                "INSERT INTO kit_bags (name, category) VALUES (?, ?)", (name, category)
            )
            await db.commit()
            bag_id = cursor.lastrowid
            row = await (await db.execute("SELECT * FROM kit_bags WHERE id = ?", (bag_id,))).fetchone()
        return {"ok": True, "bag": dict(row) if row else None}

    @app.post("/api/packing/item")
    async def api_add_item(request: Request):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name required")
        category = (body.get("category") or "").strip()
        bag_id = body.get("bag_id")
        qty = max(1, int(body.get("qty") or 1))
        every_days = int(body.get("every_days") or 0)
        per_day = 1 if body.get("per_day") else 0
        clothing_category_id = body.get("clothing_category_id")
        if clothing_category_id == "":
            clothing_category_id = None
        async with get_db() as db:
            cursor = await db.execute(
                "INSERT INTO kit_items (bag_id, name, category, per_day, every_days, qty, clothing_category_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bag_id, name, category, per_day, every_days, qty, clothing_category_id),
            )
            await db.commit()
            item_id = cursor.lastrowid
            row = await (await db.execute("SELECT * FROM kit_items WHERE id = ?", (item_id,))).fetchone()
        return {"ok": True, "item": dict(row) if row else None}

    @app.post("/api/packing/item/{item_id}/delete")
    async def api_delete_item(request: Request, item_id: int):
        async with get_db() as db:
            await db.execute("DELETE FROM kit_items WHERE id = ?", (item_id,))
            await db.commit()
        return {"ok": True}

    @app.post("/api/packing/bag/{bag_id}/delete")
    async def api_delete_bag(request: Request, bag_id: int):
        async with get_db() as db:
            await db.execute("UPDATE kit_items SET bag_id = NULL WHERE bag_id = ?", (bag_id,))
            await db.execute("DELETE FROM kit_bags WHERE id = ?", (bag_id,))
            await db.commit()
        return {"ok": True}

    @app.post("/api/packing/item/{item_id}/rename")
    async def api_rename_item(request: Request, item_id: int):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name required")
        async with get_db() as db:
            await db.execute("UPDATE kit_items SET name = ? WHERE id = ?", (name, item_id))
            await db.commit()
        return {"ok": True}

    @app.post("/api/packing/item/{item_id}")
    async def api_update_item(request: Request, item_id: int):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name required")
        category = (body.get("category") or "").strip()
        clothing_category_id = body.get("clothing_category_id")
        if clothing_category_id == "" or clothing_category_id is None:
            clothing_category_id = None
        bag_id = body.get("bag_id")
        if bag_id == "" or bag_id is None:
            bag_id = None
        qty = max(1, int(body.get("qty") or 1))
        image_url = body.get("image_url") or ""
        async with get_db() as db:
            await db.execute(
                """UPDATE kit_items
                   SET name = ?, category = ?, clothing_category_id = ?, bag_id = ?, qty = ?, image_url = ?
                   WHERE id = ?""",
                (name, category, clothing_category_id, bag_id, qty, image_url, item_id),
            )
            await db.commit()
            row = await (await db.execute("SELECT * FROM kit_items WHERE id = ?", (item_id,))).fetchone()
        return {"ok": True, "item": dict(row) if row else None}

    # --- Clothing categories ---

    @app.get("/api/clothing-categories")
    async def api_clothing_categories(request: Request):
        async with get_db() as db:
            rows = [dict(r) for r in await (await db.execute("SELECT * FROM clothing_categories ORDER BY sort_order, name")).fetchall()]
        return {"categories": rows}

    @app.post("/api/clothing-categories")
    async def api_add_clothing_category(request: Request):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name required")
        async with get_db() as db:
            cursor = await db.execute(
                "INSERT INTO clothing_categories (name) VALUES (?)", (name,)
            )
            await db.commit()
            cid = cursor.lastrowid
            row = await (await db.execute("SELECT * FROM clothing_categories WHERE id = ?", (cid,))).fetchone()
        return {"ok": True, "category": dict(row) if row else None}

    
    @app.post("/api/clothing-categories/{cid}")
    async def api_update_clothing_category(request: Request, cid: int):
        body = await request.json()
        name = (body.get("name") or "").strip()
        lasts = body.get("lasts_days")
        async with get_db() as db:
            if name:
                await db.execute("UPDATE clothing_categories SET name = ? WHERE id = ?", (name, cid))
            if lasts is not None:
                await db.execute("UPDATE clothing_categories SET lasts_days = ? WHERE id = ?", (int(lasts), cid))
            await db.commit()
            row = await (await db.execute("SELECT * FROM clothing_categories WHERE id = ?", (cid,))).fetchone()
        return {"ok": True, "category": dict(row) if row else None}

    @app.post("/api/clothing-categories/{cid}/delete")
    async def api_delete_clothing_category(request: Request, cid: int):
        async with get_db() as db:
            await db.execute("UPDATE kit_items SET clothing_category_id = NULL WHERE clothing_category_id = ?", (cid,))
            await db.execute("DELETE FROM clothing_categories WHERE id = ?", (cid,))
            await db.commit()
        return {"ok": True}

    @app.post("/api/packing/item/{item_id}/clothing-category")
    async def api_set_clothing_category(request: Request, item_id: int):
        body = await request.json()
        cid = body.get("clothing_category_id")
        async with get_db() as db:
            await db.execute(
                "UPDATE kit_items SET clothing_category_id = ? WHERE id = ?",
                (cid, item_id),
            )
            await db.commit()
        return {"ok": True}

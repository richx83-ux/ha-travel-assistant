"""Packing lists for Travel Assistant trips."""
from __future__ import annotations

from datetime import date
from fastapi import Request, Form
from fastapi.responses import HTMLResponse

get_db = None
get_base = None
redirect = None
templates = None
app = None


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
    if item.get("is_bag"):
        return 1
    if item.get("per_day"):
        return base * max(1, days)
    return base


async def _items(trip_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM packing_items WHERE trip_id = ? ORDER BY sort_order, id",
            (trip_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


def register_routes(_app, _templates, deps: dict):
    global app, templates, get_db, get_base, redirect
    app = _app
    templates = _templates
    get_db = deps["get_db"]
    get_base = deps["get_base"]
    redirect = deps["redirect"]

    @app.get("/packing", response_class=HTMLResponse)
    async def packing_index(request: Request):
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM trips ORDER BY start_date DESC, name")
            trips = [dict(r) for r in await cursor.fetchall()]
        return templates.TemplateResponse("packing.html", {
            "request": request, "base": get_base(request), "active_nav": "packing",
            "mode": "index", "trips": trips,
        })

    @app.get("/trip/{trip_id}/packing", response_class=HTMLResponse)
    async def packing_trip(request: Request, trip_id: int):
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
            row = await cursor.fetchone()
            trip = dict(row) if row else None
            cursor = await db.execute("SELECT id, name FROM trips WHERE id != ? ORDER BY name", (trip_id,))
            others = [dict(r) for r in await cursor.fetchall()]
        if not trip:
            return redirect(request, "/packing")
        days = _trip_days(trip)
        items = await _items(trip_id)
        for it in items:
            it["need"] = _need(it, days)
        by_parent = {}
        for it in items:
            by_parent.setdefault(it.get("parent_id") or 0, []).append(it)
        tops = by_parent.get(0, [])
        packed = sum(1 for it in tops if it.get("packed"))
        return templates.TemplateResponse("packing.html", {
            "request": request, "base": get_base(request), "active_nav": "packing",
            "mode": "trip", "trip": trip, "days": days, "tops": tops,
            "by_parent": by_parent, "others": others,
            "packed": packed, "total": len(tops),
        })

    @app.post("/trip/{trip_id}/packing/add")
    async def packing_add(
        request: Request, trip_id: int,
        name: str = Form(...), category: str = Form(""),
        qty: int = Form(1), per_day: str = Form(""),
        bag_id: str = Form(""), is_bag: str = Form(""),
    ):
        parent = int(bag_id) if bag_id.isdigit() else None
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM packing_items WHERE trip_id = ?",
                (trip_id,),
            )
            order = (await cursor.fetchone())["n"]
            await db.execute(
                """INSERT INTO packing_items
                   (trip_id, parent_id, is_bag, name, category, per_day, qty, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (trip_id, parent, 1 if is_bag else 0, name.strip(), category.strip(),
                 1 if per_day else 0, max(1, qty), order),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/packing")

    @app.post("/trip/{trip_id}/packing/{item_id}/toggle")
    async def packing_toggle(request: Request, trip_id: int, item_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE packing_items SET packed = CASE WHEN packed = 1 THEN 0 ELSE 1 END WHERE id = ? AND trip_id = ?",
                (item_id, trip_id),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/packing")

    @app.post("/trip/{trip_id}/packing/{item_id}/delete")
    async def packing_delete(request: Request, trip_id: int, item_id: int):
        async with get_db() as db:
            await db.execute(
                "DELETE FROM packing_items WHERE trip_id = ? AND (id = ? OR parent_id = ?)",
                (trip_id, item_id, item_id),
            )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/packing")

    @app.post("/trip/{trip_id}/packing/copy")
    async def packing_copy(request: Request, trip_id: int, from_trip: int = Form(...)):
        src = await _items(from_trip)
        async with get_db() as db:
            id_map = {}
            for it in src:
                if it.get("parent_id"):
                    continue
                cursor = await db.execute(
                    """INSERT INTO packing_items
                       (trip_id, parent_id, is_bag, name, category, per_day, qty, packed, sort_order)
                       VALUES (?, NULL, ?, ?, ?, ?, ?, 0, ?)""",
                    (trip_id, it["is_bag"], it["name"], it["category"], it["per_day"], it["qty"], it["sort_order"]),
                )
                id_map[it["id"]] = cursor.lastrowid
            for it in src:
                parent = id_map.get(it.get("parent_id"))
                if not parent:
                    continue
                await db.execute(
                    """INSERT INTO packing_items
                       (trip_id, parent_id, is_bag, name, category, per_day, qty, packed, sort_order)
                       VALUES (?, ?, 0, ?, ?, ?, ?, 0, ?)""",
                    (trip_id, parent, it["name"], it["category"], it["per_day"], it["qty"], it["sort_order"]),
                )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/packing")

    @app.post("/trip/{trip_id}/packing/suggest")
    async def packing_suggest(request: Request, trip_id: int):
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) AS n FROM packing_items WHERE trip_id = ?",
                (trip_id,),
            )
            order = (await cursor.fetchone())["n"] or 0
            clothes = [("Boxers", 1), ("Socks", 1), ("T-shirts", 1), ("Trousers", 1)]
            for name, per in clothes:
                order += 1
                await db.execute(
                    """INSERT INTO packing_items
                       (trip_id, is_bag, name, category, per_day, qty, sort_order)
                       VALUES (?, 0, ?, 'Clothes', ?, 1, ?)""",
                    (trip_id, name, per, order),
                )
            order += 1
            cursor = await db.execute(
                """INSERT INTO packing_items
                   (trip_id, is_bag, name, category, per_day, qty, sort_order)
                   VALUES (?, 1, 'Toiletry bag', 'Toiletries', 0, 1, ?)""",
                (trip_id, order),
            )
            bag_id = cursor.lastrowid
            for name in ("Toothbrush", "Toothpaste", "Deodorant", "Razor"):
                order += 1
                await db.execute(
                    """INSERT INTO packing_items
                       (trip_id, parent_id, is_bag, name, category, per_day, qty, sort_order)
                       VALUES (?, ?, 0, ?, 'Toiletries', 0, 1, ?)""",
                    (trip_id, bag_id, name, order),
                )
            await db.commit()
        return redirect(request, f"/trip/{trip_id}/packing")

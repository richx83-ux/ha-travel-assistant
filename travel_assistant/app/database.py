"""Database setup, migrations and query helpers for Travel Assistant."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import aiosqlite

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "travel_assistant.db"


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")
    try:
        yield db
    finally:
        await db.close()


async def sync_achievements(db, theme_id=None, type_id=None, region=None, county=None, country=None):
    sql = """SELECT l.county, l.region, l.country, l.visited
             FROM locations l JOIN themes t ON t.id = l.theme_id
             WHERE COALESCE(t.achievement_eligible, 1) = 1"""
    params = []
    if theme_id:
        sql += " AND l.theme_id = ?"
        params.append(theme_id)
    if type_id:
        sql += " AND t.category_type_id = ?"
        params.append(type_id)
    if region:
        sql += " AND l.region = ?"
        params.append(region)
    if county:
        sql += " AND l.county = ?"
        params.append(county)
    if country:
        sql += " AND l.country = ?"
        params.append(country)
    cursor = await db.execute(sql, params)
    rows = [dict(r) for r in await cursor.fetchall()]
    groups = {"county": {}, "region": {}, "country": {}}
    overall = {"total": 0, "visited": 0}
    coverage = {"county": 0, "region": 0, "country": 0}
    for row in rows:
        overall["total"] += 1
        overall["visited"] += 1 if row.get("visited") else 0
        for level, field in (("county", "county"), ("region", "region"), ("country", "country")):
            value = (row.get(field) or "").strip()
            if not value:
                continue
            coverage[level] += 1
            bucket = groups[level].setdefault(value, {"total": 0, "visited": 0})
            bucket["total"] += 1
            bucket["visited"] += 1 if row.get("visited") else 0
    items = []
    for level, label in (("county", "County"), ("region", "Region"), ("country", "Country")):
        reliable = overall["total"] > 0 and coverage[level] / overall["total"] >= 0.5
        for name, stats in sorted(groups[level].items()):
            pct = round(100 * stats["visited"] / stats["total"]) if stats["total"] else 0
            all_visited = stats["total"] > 0 and stats["visited"] >= stats["total"]
            items.append({
                "key": f"{level}:{name.lower()}",
                "level": level,
                "level_label": label,
                "name": name,
                "title": f"All of {name}",
                "total": stats["total"],
                "visited": stats["visited"],
                "percent": pct,
                "complete": all_visited and reliable,
                "unreliable": all_visited and not reliable,
            })
    pct = round(100 * overall["visited"] / overall["total"]) if overall["total"] else 0
    items.append({
        "key": "overall",
        "level": "overall",
        "level_label": "Overall",
        "name": "All places",
        "title": "All places visited",
        "total": overall["total"],
        "visited": overall["visited"],
        "percent": pct,
        "complete": overall["total"] > 0 and overall["visited"] >= overall["total"],
        "unreliable": False,
    })
    return {"items": items, "overall": overall}


async def migrate_db(db: aiosqlite.Connection):
    # Placeholder for the long migrate - the real one is in the file
    pass


async def init_db():
    async with get_db() as db:
        await migrate_db(db)
        await db.commit()


async def get_theme(theme_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM themes WHERE id = ?", (theme_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_theme_by_name(name: str):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM themes WHERE lower(name) = lower(?)", (name.strip(),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_locations(theme_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM locations WHERE theme_id = ? ORDER BY name", (theme_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_theme_stats(theme_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN visited = 1 THEN 1 ELSE 0 END) as visited_count
               FROM locations WHERE theme_id = ?""",
            (theme_id,),
        )
        row = await cursor.fetchone()
        total = row["total"] or 0
        visited = row["visited_count"] or 0
        pct = round((visited / total * 100) if total > 0 else 0)
        return {"total": total, "visited": visited, "percent": pct}

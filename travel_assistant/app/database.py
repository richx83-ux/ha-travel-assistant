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
    for item in items:
        if item["complete"]:
            await db.execute(
                "INSERT OR IGNORE INTO achievement_unlocks (key, level, name) VALUES (?, ?, ?)",
                (item["key"], item["level"], item["title"]),
            )
        elif item.get("unreliable"):
            await db.execute("DELETE FROM achievement_unlocks WHERE key = ?", (item["key"],))
    await db.commit()
    cursor = await db.execute("SELECT key, unlocked_at FROM achievement_unlocks")
    unlocked = {r["key"]: r["unlocked_at"] for r in await cursor.fetchall()}
    for item in items:
        item["unlocked_at"] = unlocked.get(item["key"])
    recent = sorted([i for i in items if i["complete"]], key=lambda i: i.get("unlocked_at") or "", reverse=True)[:5]
    near = sorted([i for i in items if not i["complete"] and i["total"]], key=lambda i: i["percent"], reverse=True)[:3]
    coverage_note = {
        "total": overall["total"],
        "country": coverage["country"],
        "region": coverage["region"],
        "county": coverage["county"],
    }
    return items, recent, near, coverage_note


async def migrate_db(db: aiosqlite.Connection):
    cursor = await db.execute("PRAGMA table_info(locations)")
    cols = {row[1] for row in await cursor.fetchall()}
    for col, typedef in [
        ("postcode", "TEXT DEFAULT ''"),
        ("city", "TEXT DEFAULT ''"),
        ("county", "TEXT DEFAULT ''"),
        ("region", "TEXT DEFAULT ''"),
        ("district", "TEXT DEFAULT ''"),
        ("country", "TEXT DEFAULT ''"),
        ("url", "TEXT DEFAULT ''"),
        ("image_url", "TEXT DEFAULT ''"),
        ("hidden", "INTEGER DEFAULT 0"),
        ("visit_photo_url", "TEXT DEFAULT ''"),
        ("itinerary_json", "TEXT DEFAULT ''"),
    ]:
        if col not in cols:
            await db.execute(f"ALTER TABLE locations ADD COLUMN {col} {typedef}")

    cursor = await db.execute("PRAGMA table_info(themes)")
    tcols = {row[1] for row in await cursor.fetchall()}
    for col, typedef in [
        ("primary_color", "TEXT DEFAULT '#0d9488'"),
        ("secondary_color", "TEXT DEFAULT '#134e4a'"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("icon_url", "TEXT DEFAULT ''"),
        ("exclude_from_counts", "INTEGER DEFAULT 0"),
        ("exclude_from_places", "INTEGER DEFAULT 0"),
        ("exclude_from_maps", "INTEGER DEFAULT 0"),
        ("default_image_url", "TEXT DEFAULT ''"),
        ("hide_visit_status", "INTEGER DEFAULT 0"),
        ("is_system_theme", "INTEGER DEFAULT 0"),
        ("category_type_id", "INTEGER"),
    ]:
        if col not in tcols:
            await db.execute(f"ALTER TABLE themes ADD COLUMN {col} {typedef}")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS category_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0,
            achievement_eligible INTEGER DEFAULT 0,
            exclude_from_counts INTEGER DEFAULT 1,
            exclude_from_places INTEGER DEFAULT 1,
            exclude_from_maps INTEGER DEFAULT 1,
            hide_visit_status INTEGER DEFAULT 1,
            trip_role TEXT DEFAULT ''
        )
    """)
    # Add columns if table already existed
    cursor = await db.execute("PRAGMA table_info(category_types)")
    ctcols = {row[1] for row in await cursor.fetchall()}
    for col, typedef in [
        ("achievement_eligible", "INTEGER DEFAULT 0"),
        ("exclude_from_counts", "INTEGER DEFAULT 1"),
        ("exclude_from_places", "INTEGER DEFAULT 1"),
        ("exclude_from_maps", "INTEGER DEFAULT 1"),
        ("hide_visit_status", "INTEGER DEFAULT 1"),
        ("trip_role", "TEXT DEFAULT ''"),
    ]:
        if col not in ctcols:
            await db.execute(f"ALTER TABLE category_types ADD COLUMN {col} {typedef}")
    # Set sensible defaults by name
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 1, exclude_from_counts = 0, exclude_from_places = 0,
            exclude_from_maps = 0, hide_visit_status = 0, trip_role = 'visit'
        WHERE lower(name) = 'places to visit'
    """)
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 0, exclude_from_counts = 1, exclude_from_places = 1,
            exclude_from_maps = 1, hide_visit_status = 1, trip_role = 'overnight'
        WHERE lower(name) IN ('accommodation', 'hotel', 'hotels', 'hotels')
    """)
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 0, exclude_from_counts = 1, exclude_from_places = 0,
            exclude_from_maps = 0, hide_visit_status = 1, trip_role = 'flexible'
        WHERE lower(name) = 'superchargers'
    """)
    await db.execute("""
        UPDATE category_types SET
            achievement_eligible = 0, exclude_from_counts = 1, exclude_from_places = 1,
            exclude_from_maps = 1, hide_visit_status = 1, trip_role = 'home'
        WHERE lower(name) = 'home location'
    """)
    cursor = await db.execute("SELECT COUNT(*) FROM category_types")
    row = await cursor.fetchone()
    if row and row[0] == 0:
        for i, name in enumerate([
            "Places to visit", "Superchargers", "Accommodation", "Places to eat",
            "Airport", "Sea port", "Parking", "Viewpoint", "Museum", "Nature",
            "Shopping", "Activity", "Services", "Cruise ship",
        ]):
            await db.execute(
                "INSERT OR IGNORE INTO category_types (name, sort_order) VALUES (?, ?)",
                (name, i),
            )

    
    # Ensure cruise ship type exists
    await db.execute("INSERT OR IGNORE INTO category_types (name, sort_order) VALUES ('Cruise ship', 20)")
    cursor = await db.execute("PRAGMA table_info(trip_stops)")
    scols = {row[1] for row in await cursor.fetchall()}
    if scols and "is_hotel" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN is_hotel INTEGER DEFAULT 0")
    if scols and "completed_at" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN completed_at TEXT")
    if scols and "skipped" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN skipped INTEGER DEFAULT 0")
    if scols and "arrived_at" not in scols:
        await db.execute("ALTER TABLE trip_stops ADD COLUMN arrived_at TEXT")

    cursor = await db.execute("PRAGMA table_info(trips)")
    trcols = {row[1] for row in await cursor.fetchall()}
    if trcols and "status" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN status TEXT DEFAULT 'planned'")
    if trcols and "started_at" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN started_at TEXT")
    if trcols and "active_day" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN active_day INTEGER DEFAULT 1")
    if trcols and "image_url" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN image_url TEXT DEFAULT ''")
    if trcols and "start_time" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN start_time TEXT DEFAULT '09:00'")
    if trcols and "trip_type" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN trip_type TEXT DEFAULT 'standard'")
    if trcols and "cruise_id" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN cruise_id INTEGER")
    lcols = {r[1] for r in await (await db.execute("PRAGMA table_info(locations)")).fetchall()}
    if lcols and "cruise_id" not in lcols:
        await db.execute("ALTER TABLE locations ADD COLUMN cruise_id INTEGER")
    tcols = {r[1] for r in await (await db.execute("PRAGMA table_info(trips)")).fetchall()}
    if tcols and "summary_miles" not in tcols:
        await db.execute("ALTER TABLE trips ADD COLUMN summary_miles REAL")
    if tcols and "summary_travel_hrs" not in tcols:
        await db.execute("ALTER TABLE trips ADD COLUMN summary_travel_hrs REAL")
    if tcols and "summary_visit_hrs" not in tcols:
        await db.execute("ALTER TABLE trips ADD COLUMN summary_visit_hrs REAL")
    if tcols and "plan_json" not in tcols:
        await db.execute("ALTER TABLE trips ADD COLUMN plan_json TEXT DEFAULT ''")
    if trcols and "day_times_json" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN day_times_json TEXT DEFAULT ''")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS cruises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            year INTEGER NOT NULL,
            name TEXT DEFAULT '',
            url TEXT DEFAULT '',
            start_date TEXT,
            end_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ship_id, code, year)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS cruise_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cruise_id INTEGER NOT NULL,
            day INTEGER NOT NULL,
            date TEXT,
            port TEXT DEFAULT '',
            lat REAL,
            lon REAL,
            status TEXT DEFAULT 'port',
            image_url TEXT DEFAULT '',
            FOREIGN KEY (cruise_id) REFERENCES cruises(id) ON DELETE CASCADE
        )
    """)
    if trcols and "cruise_ship_id" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN cruise_ship_id INTEGER")
    if trcols and "cruise_itinerary_json" not in trcols:
        await db.execute("ALTER TABLE trips ADD COLUMN cruise_itinerary_json TEXT DEFAULT ''")

    theme_cols = {r[1] for r in await (await db.execute("PRAGMA table_info(themes)")).fetchall()}
    if theme_cols and "achievement_eligible" not in theme_cols:
        await db.execute("ALTER TABLE themes ADD COLUMN achievement_eligible INTEGER DEFAULT 1")
        await db.execute(
            "UPDATE themes SET achievement_eligible = 0 WHERE lower(name) IN ('hotel', 'hotels')"
        )
    await db.execute("""
        CREATE TABLE IF NOT EXISTS achievement_unlocks (
            key TEXT PRIMARY KEY,
            level TEXT NOT NULL,
            name TEXT NOT NULL,
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor = await db.execute("PRAGMA table_info(kit_items)")
    kcols = {row[1] for row in await cursor.fetchall()}
    if kcols and "every_days" not in kcols:
        await db.execute("ALTER TABLE kit_items ADD COLUMN every_days INTEGER DEFAULT 0")
    cursor = await db.execute("PRAGMA table_info(trip_kit)")
    tkcols = {row[1] for row in await cursor.fetchall()}
    if tkcols and "every_days" not in tkcols:
        await db.execute("ALTER TABLE trip_kit ADD COLUMN every_days INTEGER DEFAULT 0")

    # Clothing categories for store cupboard
    await db.execute("""
        CREATE TABLE IF NOT EXISTS clothing_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0
        )
    """)
    cursor = await db.execute("PRAGMA table_info(kit_items)")
    kcols2 = {row[1] for row in await cursor.fetchall()}
    if kcols2 and "clothing_category_id" not in kcols2:
        await db.execute("ALTER TABLE kit_items ADD COLUMN clothing_category_id INTEGER")
    cursor = await db.execute("PRAGMA table_info(clothing_categories)")
    cccols = {row[1] for row in await cursor.fetchall()}
    if cccols and "lasts_days" not in cccols:
        await db.execute("ALTER TABLE clothing_categories ADD COLUMN lasts_days INTEGER DEFAULT 0")
    cursor = await db.execute("PRAGMA table_info(kit_items)")
    kcols3 = {row[1] for row in await cursor.fetchall()}
    if kcols3 and "image_url" not in kcols3:
        await db.execute("ALTER TABLE kit_items ADD COLUMN image_url TEXT DEFAULT ''")
    # Seed suggested clothing categories if empty
    cursor = await db.execute("SELECT COUNT(*) as c FROM clothing_categories")
    row = await cursor.fetchone(); count = (row[0] if row else 0)
    if count == 0:
        suggestions = [
            "Shoes", "Smart", "Casual", "Winter", "Summer",
            "Underwear", "Outerwear", "Accessories", "Sleepwear", "Swimwear", "Hiking"
        ]
        for i, name in enumerate(suggestions):
            await db.execute(
                "INSERT OR IGNORE INTO clothing_categories (name, sort_order) VALUES (?, ?)",
                (name, i),
            )
    # Apply default lasting rules (0 = whole trip)
    defaults = {
        "Underwear": 1, "Socks": 1, "Sleepwear": 0, "Shoes": 0,
        "Smart": 3, "Casual": 3, "Winter": 0, "Summer": 3,
        "Outerwear": 0, "Accessories": 0, "Swimwear": 0, "Hiking": 0,
    }
    await db.execute(
        "INSERT OR IGNORE INTO clothing_categories (name, sort_order) VALUES ('Hiking', 99)"
    )
    for name, days in defaults.items():
        await db.execute(
            "UPDATE clothing_categories SET lasts_days = ? WHERE name = ? AND (lasts_days IS NULL OR lasts_days = 0)",
            (days, name),
        )



async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                primary_color TEXT DEFAULT '#0d9488',
                secondary_color TEXT DEFAULT '#134e4a',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                postcode TEXT DEFAULT '',
                city TEXT DEFAULT '',
                county TEXT DEFAULT '',
                region TEXT DEFAULT '',
                district TEXT DEFAULT '',
                address TEXT DEFAULT '',
                visit_duration_mins INTEGER DEFAULT 60,
                opening_hours TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                url TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                visited INTEGER DEFAULT 0,
                visit_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (theme_id) REFERENCES themes (id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                notes TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trip_stops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                location_id INTEGER,
                custom_name TEXT DEFAULT '',
                day_number INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                travel_from_prev_secs INTEGER,
                distance_from_prev_m INTEGER,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE SET NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS packing_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                parent_id INTEGER,
                is_bag INTEGER DEFAULT 0,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                per_day INTEGER DEFAULT 0,
                qty INTEGER DEFAULT 1,
                packed INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kit_bags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kit_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bag_id INTEGER,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                per_day INTEGER DEFAULT 0,
                qty INTEGER DEFAULT 1,
                weather_tags TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trip_kit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                kit_item_id INTEGER,
                bag_id INTEGER,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                per_day INTEGER DEFAULT 0,
                qty INTEGER DEFAULT 1,
                needed INTEGER DEFAULT 1,
                packed INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
            )
        """)
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




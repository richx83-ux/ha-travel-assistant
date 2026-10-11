"""
Travel Assistant - Home Assistant Add-on
Theme & Places admin with visit tracking
"""

import os
from datetime import date
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import aiosqlite

# Paths
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "travel_assistant.db"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Travel Assistant")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
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
                address TEXT DEFAULT '',
                visit_duration_mins INTEGER DEFAULT 60,
                opening_hours TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                visited INTEGER DEFAULT 0,
                visit_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (theme_id) REFERENCES themes (id) ON DELETE CASCADE
            )
        """)
        await db.commit()


@app.on_event("startup")
async def startup():
    await init_db()


async def get_theme(theme_id: int):
    async with await get_db() as db:
        cursor = await db.execute("SELECT * FROM themes WHERE id = ?", (theme_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_locations(theme_id: int):
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM locations WHERE theme_id = ? ORDER BY name",
            (theme_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_theme_stats(theme_id: int):
    async with await get_db() as db:
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN visited = 1 THEN 1 ELSE 0 END) as visited_count
            FROM locations WHERE theme_id = ?
            """,
            (theme_id,)
        )
        row = await cursor.fetchone()
        total = row["total"] or 0
        visited = row["visited_count"] or 0
        pct = round((visited / total * 100) if total > 0 else 0)
        return {"total": total, "visited": visited, "percent": pct}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    async with await get_db() as db:
        cursor = await db.execute("SELECT * FROM themes ORDER BY name")
        themes = [dict(r) for r in await cursor.fetchall()]

    for t in themes:
        stats = await get_theme_stats(t["id"])
        t.update(stats)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "themes": themes,
    })


@app.get("/theme/{theme_id}", response_class=HTMLResponse)
async def theme_detail(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    locations = await get_locations(theme_id)
    stats = await get_theme_stats(theme_id)

    return templates.TemplateResponse("theme.html", {
        "request": request,
        "theme": theme,
        "locations": locations,
        "stats": stats,
    })


@app.get("/theme/new", response_class=HTMLResponse)
async def theme_new_form(request: Request):
    return templates.TemplateResponse("theme_form.html", {
        "request": request,
        "theme": None,
        "action": "/theme/new",
    })


@app.post("/theme/new")
async def theme_create(
    name: str = Form(...),
    description: str = Form(""),
):
    async with await get_db() as db:
        cursor = await db.execute(
            "INSERT INTO themes (name, description) VALUES (?, ?)",
            (name.strip(), description.strip())
        )
        await db.commit()
        theme_id = cursor.lastrowid
    return RedirectResponse(url=f"/theme/{theme_id}", status_code=303)


@app.get("/theme/{theme_id}/edit", response_class=HTMLResponse)
async def theme_edit_form(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return templates.TemplateResponse("theme_form.html", {
        "request": request,
        "theme": theme,
        "action": f"/theme/{theme_id}/edit",
    })


@app.post("/theme/{theme_id}/edit")
async def theme_update(
    theme_id: int,
    name: str = Form(...),
    description: str = Form(""),
):
    async with await get_db() as db:
        await db.execute(
            "UPDATE themes SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name.strip(), description.strip(), theme_id)
        )
        await db.commit()
    return RedirectResponse(url=f"/theme/{theme_id}", status_code=303)


@app.post("/theme/{theme_id}/delete")
async def theme_delete(theme_id: int):
    async with await get_db() as db:
        await db.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
        await db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/theme/{theme_id}/location/new", response_class=HTMLResponse)
async def location_new_form(request: Request, theme_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return templates.TemplateResponse("location_form.html", {
        "request": request,
        "theme": theme,
        "location": None,
        "action": f"/theme/{theme_id}/location/new",
    })


@app.post("/theme/{theme_id}/location/new")
async def location_create(
    theme_id: int,
    name: str = Form(...),
    latitude: Optional[str] = Form(None),
    longitude: Optional[str] = Form(None),
    address: str = Form(""),
    visit_duration_mins: int = Form(60),
    opening_hours: str = Form(""),
    notes: str = Form(""),
    visited: Optional[str] = Form(None),
    visit_date: Optional[str] = Form(None),
):
    is_visited = 1 if visited == "on" else 0
    lat = float(latitude) if latitude else None
    lng = float(longitude) if longitude else None
    vdate = visit_date if is_visited and visit_date else None

    async with await get_db() as db:
        await db.execute(
            """
            INSERT INTO locations 
            (theme_id, name, latitude, longitude, address, visit_duration_mins, 
             opening_hours, notes, visited, visit_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (theme_id, name.strip(), lat, lng, address.strip(),
             visit_duration_mins, opening_hours.strip(), notes.strip(),
             is_visited, vdate)
        )
        await db.commit()
    return RedirectResponse(url=f"/theme/{theme_id}", status_code=303)


@app.get("/theme/{theme_id}/location/{loc_id}/edit", response_class=HTMLResponse)
async def location_edit_form(request: Request, theme_id: int, loc_id: int):
    theme = await get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM locations WHERE id = ? AND theme_id = ?",
            (loc_id, theme_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")
        location = dict(row)

    return templates.TemplateResponse("location_form.html", {
        "request": request,
        "theme": theme,
        "location": location,
        "action": f"/theme/{theme_id}/location/{loc_id}/edit",
    })


@app.post("/theme/{theme_id}/location/{loc_id}/edit")
async def location_update(
    theme_id: int,
    loc_id: int,
    name: str = Form(...),
    latitude: Optional[str] = Form(None),
    longitude: Optional[str] = Form(None),
    address: str = Form(""),
    visit_duration_mins: int = Form(60),
    opening_hours: str = Form(""),
    notes: str = Form(""),
    visited: Optional[str] = Form(None),
    visit_date: Optional[str] = Form(None),
):
    is_visited = 1 if visited == "on" else 0
    lat = float(latitude) if latitude else None
    lng = float(longitude) if longitude else None
    vdate = visit_date if is_visited and visit_date else None

    async with await get_db() as db:
        await db.execute(
            """
            UPDATE locations SET
                name = ?, latitude = ?, longitude = ?, address = ?,
                visit_duration_mins = ?, opening_hours = ?, notes = ?,
                visited = ?, visit_date = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND theme_id = ?
            """,
            (name.strip(), lat, lng, address.strip(),
             visit_duration_mins, opening_hours.strip(), notes.strip(),
             is_visited, vdate, loc_id, theme_id)
        )
        await db.commit()
    return RedirectResponse(url=f"/theme/{theme_id}", status_code=303)


@app.post("/theme/{theme_id}/location/{loc_id}/delete")
async def location_delete(theme_id: int, loc_id: int):
    async with await get_db() as db:
        await db.execute(
            "DELETE FROM locations WHERE id = ? AND theme_id = ?",
            (loc_id, theme_id)
        )
        await db.commit()
    return RedirectResponse(url=f"/theme/{theme_id}", status_code=303)


@app.post("/theme/{theme_id}/location/{loc_id}/toggle_visited")
async def toggle_visited(theme_id: int, loc_id: int):
    """Quick toggle visited status (sets today's date if newly visited)"""
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT visited FROM locations WHERE id = ? AND theme_id = ?",
            (loc_id, theme_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404)

        new_visited = 0 if row["visited"] else 1
        vdate = date.today().isoformat() if new_visited else None

        await db.execute(
            "UPDATE locations SET visited = ?, visit_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_visited, vdate, loc_id)
        )
        await db.commit()
    return RedirectResponse(url=f"/theme/{theme_id}", status_code=303)

"""
Travel Assistant - Home Assistant Add-on
Theme & Places admin with visit tracking
"""

import os
import uuid
import re
import csv
import io
import json
import asyncio
import urllib.request
import urllib.parse
from datetime import date
from typing import Optional
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import aiosqlite

# trips_routes is imported inside startup so a failure there cannot
# prevent the ASGI app from being created (uvicorn then says
# "Attribute app not found in module main").
register_trip_routes = None

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "travel_assistant.db"
UPLOAD_DIR = DATA_DIR / "uploads"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".heic", ".heif"}

# Ensure directories exist before anything tries to mount them.
# An empty static/ dir is often omitted by Docker COPY, which then
# makes StaticFiles() raise and uvicorn report "Attribute app not found".
STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Travel Assistant")

try:
    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
except Exception as _e:
    print(f"WARNING: could not mount /static: {_e}")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

UI_SETTINGS_PATH = DATA_DIR / "ui_settings.json"
DEFAULT_UI = {
    "accent_color": "#14b8a6",
    "xai_api_key": "",
}

# NOTE: This is a partial restore of the header to get the app starting.
# The full main.py from commit a851c32 should be restored for complete functionality.

print("Travel Assistant main.py partially restored. Full restore recommended.")

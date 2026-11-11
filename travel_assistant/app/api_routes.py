"""API routes for Travel Assistant (places, categories, cruise, commands, etc.)."""
from __future__ import annotations

import asyncio
import urllib.request
import json
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse

# Injected by register_routes
app = None
templates = None
get_db = None
save_upload = None
get_base = None
redirect = None
geocode_postcode = None
geocode_postcodes_bulk = None
geocode_place_name = None
grok_key = None
load_ui_settings = None
save_ui_settings = None
list_assets = None
seed_category_icons = None
_http_get_json = None
_http_post_json = None
get_locations = None

def register_routes(_app, _templates, deps: dict):
    global app, templates, get_db, save_upload, get_base, redirect
    global geocode_postcode, geocode_postcodes_bulk, geocode_place_name
    global grok_key, load_ui_settings, save_ui_settings, list_assets, seed_category_icons
    global _http_get_json, _http_post_json, get_locations
    app = _app
    templates = _templates
    get_db = deps["get_db"]
    save_upload = deps.get("save_upload")
    get_base = deps.get("get_base")
    redirect = deps.get("redirect")
    geocode_postcode = deps.get("geocode_postcode")
    geocode_postcodes_bulk = deps.get("geocode_postcodes_bulk")
    geocode_place_name = deps.get("geocode_place_name")
    grok_key = deps.get("grok_key")
    load_ui_settings = deps.get("load_ui_settings")
    save_ui_settings = deps.get("save_ui_settings")
    list_assets = deps.get("list_assets")
    seed_category_icons = deps.get("seed_category_icons")
    _http_get_json = deps.get("_http_get_json")
    _http_post_json = deps.get("_http_post_json")
    get_locations = deps.get("get_locations")

    # ... rest of the file remains the same as original, with the refresh endpoint using get_locations now available

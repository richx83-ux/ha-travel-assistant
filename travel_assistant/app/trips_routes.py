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

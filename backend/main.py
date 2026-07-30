"""
Backend API for the till PWA.

Runs locally at the shop — http://localhost:8000 on the same machine as
everything else (or a shared machine/Raspberry Pi on the local WiFi if
multiple till devices need to reach it). No internet connection required;
the SQLite database file lives on disk right next to this process.

The Streamlit manager dashboard does NOT go through this API — it talks to
database/services.py directly (same SQLite database, different process).
"""

import os
import sys
from pathlib import Path

# Make the sibling `database/` package importable (db.py, auth.py,
# services.py, audit.py) without turning this into an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from seed import seed as seed_database
from routers.auth_router import router as auth_router
from routers.menu_router import router as menu_router
from routers.sales_router import router as sales_router
from routers.photos_router import router as photos_router
from routers.tables_router import router as tables_router

app = FastAPI(title="Colonel's Bakery and Restaurant — Till API")

# ALLOWED_ORIGINS is a comma-separated list of exact origins allowed to call
# this API from a browser. Defaults cover the local dev server and the
# till app served from this same machine; set it explicitly (e.g. to
# "http://192.168.1.50:4173") if a till device reaches this API over the
# shop's local WiFi instead of localhost.
_default_dev_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"
allowed_origins = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", _default_dev_origins).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(menu_router)
app.include_router(sales_router)
app.include_router(photos_router)
app.include_router(tables_router)


@app.on_event("startup")
def on_startup():
    init_db()
    # Idempotent (upserts menu items, skips existing usernames), so safe to
    # run on every boot — a fresh database file gets the starter menu and
    # first accounts the moment the service starts. Temporary passwords for
    # newly-created accounts print to this service's logs.
    seed_database()


@app.get("/health")
def health():
    return {"status": "ok"}

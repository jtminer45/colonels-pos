"""
Backend API for the till PWA.

Originally local-only (http://localhost:8000 on the same laptop as
everything else). Now deployable to Render for public access, with the
till app (on Netlify) and the Streamlit dashboard (also on Render) as its
clients. If this later moves to a Raspberry Pi on local WiFi instead, only
the hosting target changes — no database or business-logic code changes.

The Streamlit manager dashboard does NOT go through this API — it talks to
database/services.py directly (same Postgres database, different process).
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
# this API from a browser (e.g. "https://colonels-till.netlify.app"). This
# API now sits on the public internet, so — unlike the original local-only
# version — CORS is locked down to known origins rather than left wide
# open. Auth itself does not depend on CORS (the till sends a Bearer token,
# not a cookie), but restricting origins still stops arbitrary websites
# from directing a browser to probe this API. Local dev origins are always
# allowed so `npm run dev` keeps working without extra config.
_default_dev_origins = "http://localhost:5173,http://127.0.0.1:5173"
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
    # Idempotent (ON CONFLICT DO NOTHING / "skip if username exists"), so
    # safe to run on every boot. Runs here — rather than requiring someone
    # to exec into the container or run it from a machine that can reach
    # the database directly — so a fresh Postgres instance gets the starter
    # menu and first accounts the moment the service comes up. Temporary
    # passwords for newly-created accounts print to this service's logs.
    seed_database()


@app.get("/health")
def health():
    return {"status": "ok"}

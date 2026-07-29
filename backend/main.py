"""
Local backend API for the till PWA.

Runs on the same laptop as everything else today (http://localhost:8000).
When this moves to a Raspberry Pi serving multiple tablets over LAN, this
is the ONLY piece that changes host — the till app's API base URL becomes
the Pi's LAN IP instead of localhost, and this file runs on the Pi instead
of the laptop. No database or business-logic code changes.

The Streamlit manager dashboard does NOT go through this API — it is a
same-machine Python process and talks to database/services.py directly.
Both surfaces still end up reading/writing the exact same SQLite file.
"""

import sys
from pathlib import Path

# Make the sibling `database/` package importable (db.py, auth.py,
# services.py, audit.py) without turning this into an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from routers.auth_router import router as auth_router
from routers.menu_router import router as menu_router
from routers.sales_router import router as sales_router

app = FastAPI(title="Colonel's Bakery and Restaurant — Till API")

# This API is only ever reached over localhost or the local WiFi network —
# it is never exposed to the public internet — so a permissive local CORS
# policy is appropriate here and keeps till-app dev/deploy simple.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(menu_router)
app.include_router(sales_router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}

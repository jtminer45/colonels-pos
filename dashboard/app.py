"""
Colonel's Bakery and Restaurant — Manager Dashboard entry point.

Run with:  streamlit run app.py   (from inside the dashboard/ directory)

This process talks directly to the shared SQLite database (see
database/db.py) — it does not go through the till's FastAPI backend. Both
surfaces end up reading and writing the exact same database file.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "database"))
sys.path.insert(0, str(ROOT / "dashboard" / "lib"))

import streamlit as st

from db import init_db
from theme import inject_css, sidebar_header
from session import require_login, do_logout, current_user

st.set_page_config(
    page_title="Colonel's Bakery — Manager Dashboard",
    page_icon="👨‍🍳",
    layout="wide",
)

init_db()
inject_css()

user = require_login()  # halts here (login form / forced password change) until authenticated as manager

pages = [
    st.Page("pages/snapshot.py", title="Today's Snapshot", icon="📊", default=True),
    st.Page("pages/sales_analytics.py", title="Sales Analytics", icon="📈"),
    st.Page("pages/inventory.py", title="Inventory", icon="📦"),
    st.Page("pages/costs_purchases.py", title="Costs & Purchases", icon="💰"),
    st.Page("pages/reconciliation.py", title="Reconciliation", icon="🧾"),
    st.Page("pages/staff_management.py", title="Staff Management", icon="👥"),
    st.Page("pages/audit_log.py", title="Audit Log", icon="🔍"),
]

with st.sidebar:
    sidebar_header()
    st.markdown(f"Logged in as **{user['username']}** (manager)")
    if st.button("Log Out", width="stretch"):
        do_logout()
        st.rerun()
    st.divider()

nav = st.navigation(pages)
nav.run()

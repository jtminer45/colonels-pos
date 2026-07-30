#!/usr/bin/env bash
# One-command local startup: backend API, manager dashboard, and till app —
# everything on this one computer, everything saved to the local SQLite
# file at database/colonels_pos.db. No internet connection required once
# dependencies are installed.
#
# Double-click "Start Colonels POS.command" instead of running this
# directly if you're not comfortable with a terminal — it just calls this
# script for you.
set -euo pipefail
cd "$(dirname "$0")"

echo "Starting Colonels POS — this window must stay open while the till/dashboard are in use."
echo "Close this window (or press Ctrl+C) to shut everything down."
echo

# ---- Python environment (backend + dashboard + database) ----
if [ ! -d venv ]; then
  echo "First-time setup: creating Python environment..."
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r backend/requirements.txt -r dashboard/requirements.txt -r database/requirements.txt

# ---- Till app: build once, then serve the built files (fast, no dev-server
# overhead, and matches what will actually run day to day) ----
if [ ! -d till-app/node_modules ]; then
  echo "First-time setup: installing till app dependencies..."
  (cd till-app && npm install)
fi
echo "Building till app..."
(cd till-app && npm run build)

PIDS=()
cleanup() {
  echo
  echo "Shutting down..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

# ---- Backend API (till talks to this; dashboard talks to the database directly) ----
(cd backend && exec uvicorn main:app --host 0.0.0.0 --port 8000) &
PIDS+=($!)

# ---- Manager dashboard ----
(cd dashboard && exec streamlit run app.py --server.port 8501 --server.headless true) &
PIDS+=($!)

# ---- Till app (serves the production build from step above) ----
(cd till-app && exec npm run preview -- --port 5173 --host) &
PIDS+=($!)

sleep 3
echo
echo "Ready:"
echo "  Till app          http://localhost:5173"
echo "  Manager dashboard http://localhost:8501"
echo
echo "On the shop's WiFi, other devices (a tablet at the counter, etc.) can reach these at"
echo "http://$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "<this-computer's-IP>"):5173 instead of localhost."
echo

wait

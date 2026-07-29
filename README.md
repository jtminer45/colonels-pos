# Colonel's Bakery and Restaurant — POS & Management System

A local-first point-of-sale and management system: one shared SQLite database,
a Streamlit manager dashboard, and a React till app (installable as an
offline-capable PWA). Everything runs on one laptop today; the architecture
is designed so it can move to a small local server (e.g. a Raspberry Pi)
serving multiple tablets over WiFi later, **without changing the database
schema or business logic** — only where the till's backend API is hosted.

## How the pieces fit together

```
database/    SQLite schema, seed data, auth, and shared business logic
             (record_sale, void, purchases, wastage, reconciliation, ...)
                         ▲                              ▲
                         │ direct import                │ direct import
                         │                               │
              dashboard/ │ (Streamlit)          backend/ │ (FastAPI)
              reads/writes the DB directly               │ same functions,
              in-process — no network hop                │ exposed over HTTP
                                                           ▲
                                                           │ HTTP (localhost
                                                           │ today, LAN later)
                                                    till-app/ (React PWA)
                                                    runs in a browser/tablet,
                                                    cannot touch SQLite
                                                    directly — talks to the
                                                    backend instead
```

The dashboard and the till app both end up reading/writing the exact same
`database/colonels_pos.db` file — a sale rung up on the till is visible on
the dashboard immediately, with no sync step.

## First-time setup

### 1. Python environment (backend + dashboard + database)

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt -r dashboard/requirements.txt
```

### 2. Seed the database

```bash
cd database
python3 seed.py
```

This creates the schema (if not already created), the starter menu,
starter ingredients/recipes, today's opening inventory counts, and the
first two accounts:

- `manager` (role: manager)
- `staff1` (role: staff)

**The temporary passwords are printed once, to the terminal, when accounts
are created — write them down.** Passwords are never stored in recoverable
form (only a PBKDF2-SHA256 hash + salt), so if you lose a temporary
password before first login, a manager must reset it (Staff Management
page) rather than look it up. Both accounts are forced to set a real
password on first login.

Re-running `seed.py` is safe — it will not duplicate menu items or
overwrite existing accounts.

### 3. Logo

Drop the real logo at `assets/logo.png` (500×500 or larger, square, PNG).
Both the dashboard and the till app reference that exact path — replacing
the file is enough, no code changes needed. If you replace it, re-run:

```bash
sips -z 192 192 assets/logo.png --out till-app/public/icons/icon-192.png
sips -z 512 512 assets/logo.png --out till-app/public/icons/icon-512.png
sips -z 180 180 assets/logo.png --out till-app/public/icons/apple-touch-icon.png
cp assets/logo.png till-app/public/logo.png
```
(macOS `sips` is used above; on Linux/Windows use any image tool to produce
the same three sizes into `till-app/public/icons/`.)

## Running each part

Run these in separate terminals. All three (backend, dashboard, till app)
can run at the same time on the same laptop.

### Manager Dashboard (Streamlit)

```bash
source venv/bin/activate
cd dashboard
streamlit run app.py
```

Open the URL Streamlit prints (typically http://localhost:8501). Log in
with the `manager` account. Manager-role is enforced server-side on every
page load and every data-mutating action — a staff account cannot log into
this dashboard at all, and the check is re-verified from the database on
every rerun, not just at login.

### Till backend (FastAPI)

The React till app needs this running to load the menu or record sales.

```bash
source venv/bin/activate
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` is what lets a tablet on the same WiFi network reach it
later (once moved off "everything on one laptop"); on a single laptop
`localhost` alone is enough.

### Till app (React PWA)

```bash
cd till-app
npm install        # first time only
npm run dev
```

Open http://localhost:5173 in a browser (Chrome/Edge recommended for PWA
install support). To install it as an app: browser menu → "Install
Colonel's Till" (or the install icon in the address bar). Once installed,
it opens in its own window and works with the OS reporting "offline" —
the app shell, menu photos, and icons are all precached by a service
worker. It still needs the backend (above) reachable at its configured
URL to load the menu or record a sale — see **Offline model** below.

For a real deployed build (e.g. installed permanently on a shop tablet):

```bash
cd till-app
npm run build       # outputs to till-app/dist/
npm run preview     # serves the production build locally to test it
```

Set `VITE_API_BASE_URL` (in a `.env` file in `till-app/`, e.g.
`VITE_API_BASE_URL=http://192.168.1.50:8000`) before building if the
backend runs on a different device than the till — the only change needed
when this moves off a single laptop.

## Offline model — what "fully offline" means here

Everything runs on the local machine/network with **zero dependency on the
public internet**. Concretely:

- The till app's UI shell, fonts, icons, and menu photos are precached by
  a service worker (`vite-plugin-pwa`) — the app opens and renders even
  with the device's WiFi/internet fully disconnected.
- Menu data and sales still require the FastAPI backend to be reachable —
  today that's `localhost` (same device, always reachable regardless of
  internet status), and later the Pi's LAN address (same local network,
  still no internet required). If the backend process isn't running, the
  till shows a clear "Can't reach the till server" message rather than
  silently failing or losing a sale.
- There is no queue-and-sync-later mechanism for sales made while the
  backend is unreachable — that's out of scope for this single-device
  phase (see project scope notes below) and would be the first thing to
  add if this becomes genuinely multi-device.

## Receipt printing

`ReceiptModal.tsx` calls the browser's native print (`window.print()`)
against a receipt-formatted view. This requires a physical USB or
Bluetooth thermal receipt printer connected and installed as an OS-level
printer (most thermal receipt printers ship a driver that registers them
as a normal system print destination — set it as default, or pick it from
the print dialog each time). There is no raw ESC/POS byte-level printer
integration implemented; this is a standard print-dialog call, not a
direct printer protocol.

## Security model (read this before adding features)

- Passwords: PBKDF2-HMAC-SHA256, 600,000 iterations, unique random salt
  per user, constant-time comparison on login. See `database/auth.py`.
- **Role checks happen at the data layer, not the UI.** Every manager-only
  operation — in the dashboard, in the backend API, anywhere — calls
  `auth.require_manager()` / re-derives the role from the `users` table.
  A staff account is structurally unable to reach manager data even by
  calling the API directly or inspecting network requests, because the
  role is never trusted from the client — it's always re-read from SQLite.
- The till backend issues a signed opaque token on login
  (`backend/security.py`) that identifies a session row; it proves the
  token wasn't forged, it does not itself grant permissions — every
  request re-checks the user's current role/active status from the DB.
- Deactivated staff are never deleted (`users.active = 0`), so historical
  sales and audit entries always resolve to a valid user.
- Every void, manual stock adjustment, purchase, wastage entry, password
  reset, and staff-account change is written to `audit_log` in the same
  transaction as the action itself.

## What's intentionally not built (see project scope)

Online/customer ordering, SMS/digital receipts, multi-device sync, real
payment processor integration, and ML/forecasting are all out of scope for
this build — see the original project brief. Payment method "Card" is
recorded for later manual reconciliation against the physical POS
terminal's own report, not processed by this system.

## Project layout

```
assets/                 Logo + bundled category placeholder icons
database/                SQLite schema, seed data, auth, shared business logic
  schema.sql
  db.py                  connection helper, timezone/VAT constants
  auth.py                password hashing, login/logout, role checks
  audit.py                audit_log writer
  services.py             record_sale, void, purchases, wastage, reconciliation, staff mgmt
  seed.py
backend/                FastAPI app used only by the till PWA
  main.py, security.py, deps.py, schemas.py, routers/
dashboard/              Streamlit manager dashboard
  app.py, lib/ (session/theme/queries), pages/ (7 sections)
till-app/                React + TypeScript + Vite PWA (the till)
  src/ (contexts, hooks, components, pages), public/ (icons, menu photos)
```

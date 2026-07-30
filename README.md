# Colonels Restaurant & Garden — POS & Management System

A point-of-sale and management system for one shop: a SQLite database, a
Streamlit manager dashboard, a FastAPI backend, and a React till app
(installable as a PWA). Everything runs on one computer at the shop and
works with **zero internet connection** — sales, the menu, and the manager
dashboard all keep working through an internet outage, because nothing
about ringing up a sale or checking today's numbers ever leaves the
building.

## Quick start (for the shop — no terminal knowledge needed)

1. Double-click **`Start Colonels POS.command`** in this folder.
2. A window opens and does some setup the first time (a minute or two);
   after that it's fast. Leave that window open — closing it shuts
   everything down.
3. Two browser tabs open on their own:
   - **Till** — where sales are rung up.
   - **Manager dashboard** — sales numbers, inventory, expenses, staff.
4. To stop for the day, close (or Ctrl+C in) the terminal window that
   opened in step 1.

Everything is saved to one file, `database/colonels_pos.db`, on this
computer. **Back that file up regularly** (copy it to a USB drive or cloud
storage folder every so often) — it is the only copy of every sale, and
losing the computer without a backup means losing the sales history.

First-time login accounts (`manager` / `staff1`) and their one-time
temporary passwords print to that terminal window the very first time it
runs — write them down immediately, they are not shown again and are never
stored anywhere in a recoverable form (only as a one-way hash). Both
accounts are forced to set a real password on first login.

## How the pieces fit together

```
database/    SQLite schema, seed data, auth, and shared business logic
             (record_sale, void, expenses, wastage, reconciliation, ...)
                         ▲                              ▲
                         │ direct import                │ direct import
                         │                               │
              dashboard/ │ (Streamlit)          backend/ │ (FastAPI)
              reads/writes the DB directly               │ same functions,
              in-process — no network hop                │ exposed over HTTP
                                                           ▲
                                                           │ localhost (or the
                                                           │ shop's WiFi if a
                                                           │ separate till
                                                           │ device is used)
                                                    till-app/ (React PWA)
                                                    runs in a browser/tablet,
                                                    cannot touch the database
                                                    directly — talks to the
                                                    backend instead
```

The dashboard and the backend both read/write the exact same
`database/colonels_pos.db` file — a sale rung up on the till is visible on
the dashboard immediately, with no sync step.

## First-time setup (developer / manual path)

`Start Colonels POS.command` (see **Quick start** above) does all of this
automatically. Use the manual steps below only if you're developing,
debugging, or on a platform where the `.command` file doesn't work
(Windows — use Git Bash or WSL to run `start.sh`, or follow the manual
steps).

### 1. Python environment (backend + dashboard + database)

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt -r dashboard/requirements.txt -r database/requirements.txt
```

No database server to install or configure — `database/db.py` opens
`database/colonels_pos.db` directly (created automatically on first run).

### 2. Seed the database

```bash
cd database
python3 seed.py
```

This creates the schema (if not already created), the starter menu,
starter ingredients/recipes, today's opening inventory counts, and the
first two accounts (`manager`, `staff1`) with printed temporary passwords —
see **Quick start** above for what to do with them.

Re-running `seed.py` is safe — it won't duplicate menu items or overwrite
existing accounts. It also runs automatically every time the backend
starts (see `backend/main.py`), so editing the `MENU` dict in `seed.py`
and restarting is how a menu/price/photo change reaches the till — no
separate migration step. Removing an item (or a variant) from `seed.py`
deactivates it rather than deleting it, so historical sales referencing it
still resolve correctly.

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

## Running each part manually

`start.sh` (or the `.command` wrapper) does this for you. To run pieces by
hand instead (useful for development):

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

`--host 0.0.0.0` is what lets another device on the same WiFi network
reach it (e.g. a tablet at the counter); on a single laptop `localhost`
alone is enough.

### Till app (React PWA)

For day-to-day use, build once and serve the build (faster, closer to how
`start.sh` runs it):

```bash
cd till-app
npm install        # first time only
npm run build
npm run preview -- --port 5173
```

Or for active development (hot reload on save):

```bash
npm run dev
```

Open http://localhost:5173 in a browser (Chrome/Edge recommended for PWA
install support). To install it as an app: browser menu → "Install
Colonels Till" (or the install icon in the address bar). It talks to the
backend at `VITE_API_BASE_URL` (default `http://localhost:8000`,
configured in `till-app/.env.production` — see that file's comments for
the separate-device/LAN case).

## Running the till on a separate device (optional)

By default everything — including the till — runs on one computer. If a
tablet at the counter should run the till instead while the backend stays
on the main computer:

1. Find the main computer's LAN IP (macOS: `ipconfig getifaddr en0`).
2. In `till-app/.env.production`, set
   `VITE_API_BASE_URL=http://<that-ip>:8000`, then rebuild (`npm run
   build`).
3. On the main computer, set `ALLOWED_ORIGINS` to include the tablet's
   origin (e.g. `http://<tablet-ip>:5173`) before starting the backend —
   see `.env.example` for the exact variable and how to export it.
4. Start the backend with `--host 0.0.0.0` (already the default in
   `start.sh`) so it accepts connections from other devices on the WiFi.

This is still entirely local — no internet leaves the building, it's just
two devices on the same shop WiFi instead of one.

## Offline model

The till app's UI shell, fonts, icons, and menu photos are precached by a
service worker (`vite-plugin-pwa`), and the backend/database are on the
same local network (or the same machine) — there is no dependency on the
public internet anywhere in the sale-ringing path. If the shop's internet
goes down entirely, sales, the dashboard, inventory, and everything else
keep working exactly as before.

The one thing that does depend on this computer specifically: the
database is a single file (`database/colonels_pos.db`) on local disk, not
replicated anywhere automatically. **Back it up regularly** (see **Quick
start**) — that file, not any server, is the entire system of record.

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
  role is never trusted from the client — it's always re-read from the database.
- The till backend issues a signed opaque token on login
  (`backend/security.py`) that identifies a session row; it proves the
  token wasn't forged, it does not itself grant permissions — every
  request re-checks the user's current role/active status from the DB.
  The signing key is generated once and saved to `backend/.secret_key`
  (gitignored) so it survives restarts without needing any manual setup.
- CORS on the backend defaults to `localhost`/`127.0.0.1` origins only —
  see **Running the till on a separate device** if a tablet needs access
  from elsewhere on the shop's WiFi.
- Deactivated staff are never deleted (`users.active = 0`), so historical
  sales and audit entries always resolve to a valid user.
- Every void, manual stock adjustment, expense, wastage entry, password
  reset, and staff-account change is written to `audit_log` in the same
  transaction as the action itself.

## What's intentionally not built (see project scope)

Online/customer ordering, SMS/digital receipts, multi-device sync, real
payment processor integration, and ML/forecasting are all out of scope for
this build — see the original project brief. Payment method "POS" is
recorded for later manual reconciliation against the physical POS
terminal's own report, not processed by this system.

## Legacy cloud deployment (Render/Netlify) — not currently active

This system briefly ran on Render (backend + dashboard) and Netlify (till
app) with a Postgres database, for remote access. It has since moved back
to local-first (this README) because the free Postgres tier expires and
gets deleted after 30 days, and the till required internet reachability to
ring up a sale — both unacceptable for a shop's primary point of sale.

The Render/Netlify/Postgres resources from that period may still exist
(not yet torn down as of this writing) but are not being kept in sync with
this codebase going forward. `render.yaml` documents that deployment's
shape if it's ever needed again, but treat it as historical reference, not
a maintained deployment target.

## Project layout

```
assets/                 Logo + bundled category placeholder icons
database/               SQLite schema, seed data, auth, shared business logic
  schema.sql
  db.py                  sqlite3 connection helper, timezone/VAT constants
  auth.py                password hashing, login/logout, role checks
  audit.py                audit_log writer
  services.py             record_sale, void, expenses, wastage, reconciliation, staff mgmt
  seed.py
backend/                FastAPI app used only by the till PWA
  main.py, security.py, deps.py, schemas.py, routers/
dashboard/              Streamlit manager dashboard
  app.py, lib/ (session/theme/queries), pages/ (8 sections)
till-app/                React + TypeScript + Vite PWA (the till)
  src/ (contexts, hooks, components, pages), public/ (icons, menu photos)
start.sh                One-command local startup (backend + dashboard + till)
Start Colonels POS.command   Double-click wrapper for start.sh (macOS)
render.yaml             Historical Render Blueprint (see Legacy cloud deployment)
.env.example            Optional local env var overrides (multi-device LAN setup only)
```

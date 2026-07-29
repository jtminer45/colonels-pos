# Colonel's Bakery and Restaurant — POS & Management System

A point-of-sale and management system: one shared Postgres database, a
Streamlit manager dashboard, a FastAPI backend, and a React till app
(installable as a PWA). Originally built local-first on SQLite for a single
laptop; migrated to Postgres so the backend and dashboard could be hosted
on Render with the till app on Netlify — see **Live deployment** below.
The database schema and business logic (`database/services.py`) did not
change in that move, only the storage engine and where things run.

## Live deployment

| Piece | URL | Host |
|---|---|---|
| Till app | https://colonels-bakery-till.netlify.app | Netlify |
| Manager dashboard | https://colonels-pos-dashboard.onrender.com | Render (free web service) |
| Backend API | https://colonels-pos-backend.onrender.com | Render (free web service) |
| Database | (internal only) | Render Postgres (**free tier — see warning below**) |

**⚠️ The free Render Postgres instance expires 30 days after creation and is then deleted, taking all sales data with it.** Before that date, either upgrade it to a paid Render Postgres plan, or export the data (`pg_dump`) and migrate it. This is a hard limit of Render's free tier, not something configurable from this codebase.

**⚠️ Free-tier Render web services spin down after ~15 minutes of inactivity** and take 30–60 seconds to cold-start on the next request. The backend and dashboard will feel slow on the first request after a quiet period — this is expected on the free plan, not a bug.

**⚠️ The till now depends on internet reachability to the Render backend** — this was a deliberate tradeoff (see project history) to allow remote/public access, at the cost of the original "works with zero internet connection" guarantee. If the shop's internet goes down, the till cannot ring up sales. Running everything locally again (see **Local development** below) restores full offline operation.

**Repo:** https://github.com/jtminer45/colonels-pos — public (no secrets are committed; all credentials and connection strings live in Render's environment variables, set via their dashboard or API, never in this repo).

Initial `manager` and `staff1` account temporary passwords were printed once to the backend service's logs on first boot (Render dashboard → colonels-pos-backend → Logs) and were shared with the project owner directly — they are not recoverable from anywhere else. Both accounts force a password change on first login.

## How the pieces fit together

```
database/    Postgres schema, seed data, auth, and shared business logic
             (record_sale, void, purchases, wastage, reconciliation, ...)
                         ▲                              ▲
                         │ direct import                │ direct import
                         │                               │
              dashboard/ │ (Streamlit)          backend/ │ (FastAPI)
              reads/writes the DB directly               │ same functions,
              in-process — no network hop                │ exposed over HTTP
                                                           ▲
                                                           │ HTTPS (Render/
                                                           │ Netlify today,
                                                           │ localhost for
                                                           │ local dev)
                                                    till-app/ (React PWA)
                                                    runs in a browser/tablet,
                                                    cannot touch Postgres
                                                    directly — talks to the
                                                    backend instead
```

The dashboard and the backend both end up reading/writing the exact same
Postgres database (connected via `DATABASE_URL`) — a sale rung up on the
till is visible on the dashboard immediately, with no sync step.

## Local development

Everything can still run entirely on one laptop against a local (or any)
Postgres instance — set `DATABASE_URL` accordingly and follow the setup
below. The original SQLite version is in this repo's git history if a
fully offline, zero-dependency deployment is ever needed again.

## First-time setup

### 1. Python environment (backend + dashboard + database)

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt -r dashboard/requirements.txt -r database/requirements.txt
```

### 2. Point at a Postgres database

Copy `.env.example` to `.env` and set `DATABASE_URL` to a Postgres
instance (a free local one, a Render Postgres instance, whatever you're
targeting). `database/db.py` loads `.env` automatically for local dev.

### 3. Seed the database

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
overwrite existing accounts. The deployed backend also runs this
automatically on every boot (see `backend/main.py`), so a freshly created
Postgres instance gets the starter menu and first accounts the moment the
service comes up, without needing direct database access from your machine.

### 4. Logo

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

## Running each part locally

Run these in separate terminals. All three (backend, dashboard, till app)
can run at the same time on the same laptop, or you can point your local
till app at the live Render backend instead of a local one.

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
reach it; on a single laptop `localhost` alone is enough.

### Till app (React PWA)

```bash
cd till-app
npm install        # first time only
npm run dev
```

Open http://localhost:5173 in a browser (Chrome/Edge recommended for PWA
install support). To install it as an app: browser menu → "Install
Colonel's Till" (or the install icon in the address bar). It still needs
the backend reachable at its configured URL (`VITE_API_BASE_URL`, default
`http://localhost:8000`) to load the menu or record a sale.

## Deploying (Render + Netlify)

This is how the live deployment above was set up — useful if it needs to
be redone (e.g. after the free Postgres instance expires) or moved to a
different account.

1. **Postgres**: create a Render Postgres instance. Grab its *internal*
   connection string (Render dashboard → your database → Connections) —
   internal, not external, since the backend/dashboard run on Render too
   and don't need to leave Render's network.
2. **Backend**: new Render web service from this repo, root directory
   `backend`, build command
   `pip install -r requirements.txt -r ../database/requirements.txt`,
   start command `uvicorn main:app --host 0.0.0.0 --port $PORT`, health
   check path `/health`. Env vars: `DATABASE_URL` (from step 1),
   `SECRET_KEY` (generate a random value — Render can auto-generate one),
   `ALLOWED_ORIGINS` (set after step 4, once the Netlify URL is known).
3. **Dashboard**: new Render web service, root directory `dashboard`, same
   build command pattern, start command
   `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false`.
   Env var: `DATABASE_URL` (same as step 2).
4. **Till app**: `cd till-app && echo "VITE_API_BASE_URL=https://<your-backend>.onrender.com" > .env.production && npm run build`,
   then deploy the `dist/` folder to Netlify (`netlify deploy --prod --dir=dist`
   via the Netlify CLI, or drag-and-drop in their dashboard).
5. Go back to the backend service and set `ALLOWED_ORIGINS` to the
   Netlify URL from step 4 (comma-separate multiple origins if needed),
   then trigger a fresh deploy — a plain restart does not reliably pick up
   env var changes on Render; a real redeploy does.
6. `render.yaml` in the repo root documents this same shape as a Render
   Blueprint, if you'd rather deploy via Render's Blueprint UI instead of
   the steps above.

## Offline model — what changed, and what didn't

The till app's UI shell, fonts, icons, and menu photos are still precached
by a service worker (`vite-plugin-pwa`) — the app opens and renders its
shell even with the device's WiFi/internet disconnected.

What changed with the move to Render/Netlify: menu data and sales require
the backend to be reachable over the **public internet** now, not just the
local network — there is no local/offline fallback for actually ringing up
a sale. If the backend is unreachable (or cold-starting on Render's free
tier), the till shows a clear "Can't reach the till server" message rather
than silently failing or losing a sale, but it cannot complete a sale
until connectivity returns. There is no queue-and-sync-later mechanism.

If a genuinely offline, zero-internet-dependency deployment is needed
again (e.g. unreliable shop internet), run the backend and dashboard
locally against a local Postgres instance instead — see **Local
development** above — which restores the original guarantee.

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
  The signing key is a `SECRET_KEY` environment variable (not a local
  file) so it survives Render's redeploys — a locally-persisted key would
  silently invalidate every session on the next deploy or restart.
- CORS on the backend is locked to an explicit `ALLOWED_ORIGINS` allowlist
  now that it's public, rather than the wide-open `*` appropriate for a
  local-only deployment.
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
database/                Postgres schema, seed data, auth, shared business logic
  schema.sql
  db.py                  psycopg2 connection helper, timezone/VAT constants
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
render.yaml             Render Blueprint documenting the deployed shape
.env.example            Local dev env var template (DATABASE_URL, ALLOWED_ORIGINS)
```

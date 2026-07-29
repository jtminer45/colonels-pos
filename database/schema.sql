-- Colonel's Bakery and Restaurant — POS & Management System
-- PostgreSQL schema (migrated from an initial SQLite version — see git
-- history for that variant, kept for local single-laptop deployments).
-- Foreign keys are always enforced by Postgres; no PRAGMA needed.

-- ============================================================
-- USERS & SESSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,      -- PBKDF2-SHA256 hex digest
    salt            TEXT NOT NULL,      -- unique random salt, hex, per user
    role            TEXT NOT NULL CHECK (role IN ('manager', 'staff')),
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS')
);

-- Deactivated staff are never deleted (active=0) so historical sales/audit rows
-- keep a valid foreign key and remain attributable.

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    login_at    TEXT NOT NULL,
    logout_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- ============================================================
-- MENU: categories -> menu_items -> item_variants
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    colour_hex  TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS menu_items (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    has_variants    INTEGER NOT NULL DEFAULT 0 CHECK (has_variants IN (0, 1)),
    base_photo_url  TEXT,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE (category_id, name)
);

-- A manager-uploaded item photo (e.g. a new item added from the dashboard)
-- is stored directly in the database rather than on disk — Render's
-- filesystem is ephemeral, so a file saved locally would vanish on the
-- next redeploy/restart. base_photo_url then points at the backend's
-- GET /photos/{item_id} route, which streams these bytes back out.
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS photo_blob BYTEA;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS photo_content_type TEXT;

CREATE INDEX IF NOT EXISTS idx_menu_items_category ON menu_items(category_id);

-- Every sellable thing is an item_variant, even single-price items (they get
-- exactly one variant row, e.g. label 'Standard'). This keeps every table that
-- references "the thing that was sold" (recipes, inventory_daily, sale_items,
-- wastage) pointing at a single id type instead of juggling nullable
-- menu_item_id / item_variant_id pairs everywhere.
CREATE TABLE IF NOT EXISTS item_variants (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_item_id    INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE RESTRICT,
    variant_label   TEXT NOT NULL,      -- e.g. 'Small', 'Slice', 'Whole Cake', 'Standard'
    price           REAL NOT NULL CHECK (price >= 0),
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE (menu_item_id, variant_label)
);

CREATE INDEX IF NOT EXISTS idx_item_variants_menu_item ON item_variants(menu_item_id);

-- ============================================================
-- INGREDIENTS & RECIPES
-- ============================================================

CREATE TABLE IF NOT EXISTS ingredients (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    unit                TEXT NOT NULL,          -- e.g. 'kg', 'litre', 'unit'
    current_stock       REAL NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    reorder_threshold   REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipes (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_variant_id INTEGER NOT NULL REFERENCES item_variants(id) ON DELETE RESTRICT,
    ingredient_id   INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    quantity_used   REAL NOT NULL CHECK (quantity_used >= 0),
    UNIQUE (item_variant_id, ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_recipes_variant ON recipes(item_variant_id);
CREATE INDEX IF NOT EXISTS idx_recipes_ingredient ON recipes(ingredient_id);

-- ============================================================
-- DAILY INVENTORY (per sellable variant, per day)
-- ============================================================

-- "Sold so far today" is NOT stored here — it is derived by summing
-- non-voided sale_items for that date/variant, so there is a single source
-- of truth for sales counts. opening_count is set at start of day (or by a
-- manager/staff stock take); closing_count is entered manually at day's end
-- and compared against opening_count - sold to flag inventory mismatches.
CREATE TABLE IF NOT EXISTS inventory_daily (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date            TEXT NOT NULL,          -- 'YYYY-MM-DD'
    item_variant_id INTEGER NOT NULL REFERENCES item_variants(id) ON DELETE RESTRICT,
    opening_count   INTEGER NOT NULL DEFAULT 0 CHECK (opening_count >= 0),
    closing_count   INTEGER,                -- NULL until entered
    UNIQUE (date, item_variant_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_daily_date ON inventory_daily(date);

-- ============================================================
-- RESTAURANT TABLES (dine-in service) — table itself, defined here;
-- table_orders/table_order_items are defined after SALES below, since a
-- table_order references a sales row once its bill is paid.
-- ============================================================

-- A fixed set of physical tables (seeded once, see seed.py). Dine-in
-- ordering works as a running tab (table_orders/table_order_items) that
-- accumulates over the course of a meal, separate from the till's
-- ring-up-and-pay-immediately counter sales — a table only turns into a
-- `sales` row (via checkout_table_order) once the bill is actually paid.
CREATE TABLE IF NOT EXISTS restaurant_tables (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label       TEXT NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- SALES
-- ============================================================

-- payment_method: 'cash', 'card' (POS terminal), or 'transfer' (bank
-- transfer). Stored as 'card' for historical/schema reasons — the till and
-- dashboard both display it as "POS".
CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    staff_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    payment_method  TEXT NOT NULL CHECK (payment_method IN ('cash', 'card', 'transfer')),
    subtotal        REAL NOT NULL CHECK (subtotal >= 0),
    vat_amount      REAL NOT NULL CHECK (vat_amount >= 0),
    total           REAL NOT NULL CHECK (total >= 0)
);

-- Re-applied on every boot so an already-existing `sales` table (from
-- before "transfer" existed) picks up the wider CHECK too.
ALTER TABLE sales DROP CONSTRAINT IF EXISTS sales_payment_method_check;
ALTER TABLE sales ADD CONSTRAINT sales_payment_method_check CHECK (payment_method IN ('cash', 'card', 'transfer'));

-- NULL for a walk-in counter sale; set for a dine-in sale created via
-- checkout_table_order(), so sales can be reported/filtered by table too.
ALTER TABLE sales ADD COLUMN IF NOT EXISTS table_id INTEGER REFERENCES restaurant_tables(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales(timestamp);
CREATE INDEX IF NOT EXISTS idx_sales_staff ON sales(staff_user_id);

CREATE TABLE IF NOT EXISTS sale_items (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sale_id         INTEGER NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
    item_variant_id INTEGER NOT NULL REFERENCES item_variants(id) ON DELETE RESTRICT,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      REAL NOT NULL CHECK (unit_price >= 0),
    is_voided       INTEGER NOT NULL DEFAULT 0 CHECK (is_voided IN (0, 1)),
    voided_by       INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    void_reason     TEXT,
    voided_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_variant ON sale_items(item_variant_id);

-- ============================================================
-- TABLE ORDERS (dine-in running tab, closes out into a sales row)
-- ============================================================

CREATE TABLE IF NOT EXISTS table_orders (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id        INTEGER NOT NULL REFERENCES restaurant_tables(id) ON DELETE RESTRICT,
    staff_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'bill_requested', 'closed')),
    sale_id         INTEGER REFERENCES sales(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_table_orders_table ON table_orders(table_id);
CREATE INDEX IF NOT EXISTS idx_table_orders_status ON table_orders(status);
-- Only one non-closed order per table at a time.
CREATE UNIQUE INDEX IF NOT EXISTS idx_table_orders_one_open_per_table
    ON table_orders(table_id) WHERE status <> 'closed';

-- Items build up here as the meal progresses; a line only becomes a
-- sale_items row (financial record) at final checkout. Ingredient stock is
-- depleted the moment an item is added here (the kitchen starts cooking
-- then, not when the bill is eventually paid) — see services.py.
CREATE TABLE IF NOT EXISTS table_order_items (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_order_id      INTEGER NOT NULL REFERENCES table_orders(id) ON DELETE RESTRICT,
    item_variant_id     INTEGER NOT NULL REFERENCES item_variants(id) ON DELETE RESTRICT,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price          REAL NOT NULL CHECK (unit_price >= 0),
    added_at            TEXT NOT NULL,
    added_by_user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    is_voided           INTEGER NOT NULL DEFAULT 0 CHECK (is_voided IN (0, 1)),
    voided_by           INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    void_reason         TEXT,
    voided_at           TEXT
);

CREATE INDEX IF NOT EXISTS idx_table_order_items_order ON table_order_items(table_order_id);

-- ============================================================
-- PURCHASES & WASTAGE (ingredient stock movements)
-- ============================================================

CREATE TABLE IF NOT EXISTS purchases (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingredient_id   INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    supplier_name   TEXT,
    quantity        REAL NOT NULL CHECK (quantity > 0),
    cost            REAL NOT NULL CHECK (cost >= 0),
    date            TEXT NOT NULL,
    logged_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_purchases_ingredient ON purchases(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date);

CREATE TABLE IF NOT EXISTS wastage (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_variant_id INTEGER NOT NULL REFERENCES item_variants(id) ON DELETE RESTRICT,
    quantity        REAL NOT NULL CHECK (quantity > 0),
    reason          TEXT NOT NULL,
    value_lost      REAL NOT NULL CHECK (value_lost >= 0),
    date            TEXT NOT NULL,
    logged_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_wastage_date ON wastage(date);

-- ============================================================
-- RECONCILIATION
-- ============================================================

CREATE TABLE IF NOT EXISTS reconciliation (
    id                      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date                    TEXT NOT NULL,
    staff_user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    system_cash_total       REAL NOT NULL CHECK (system_cash_total >= 0),
    counted_cash_total      REAL NOT NULL CHECK (counted_cash_total >= 0),
    discrepancy_amount      REAL NOT NULL,
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS')
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_date ON reconciliation(date);
CREATE INDEX IF NOT EXISTS idx_reconciliation_staff ON reconciliation(staff_user_id);

-- ============================================================
-- AUDIT LOG — every void, manual adjustment, and manager override
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action_type     TEXT NOT NULL,      -- e.g. 'VOID_SALE_ITEM', 'RESET_PASSWORD', 'STOCK_ADJUST'
    details         TEXT                -- free-text / JSON description
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);

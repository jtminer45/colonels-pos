-- Colonel's Bakery and Restaurant — POS & Management System
-- SQLite schema — local-first by design: everything runs on one machine at
-- the shop with zero setup (no database server to install/manage), and
-- keeps working with zero internet dependency. This project briefly ran on
-- a hosted Postgres instance (see git history) for remote dashboard access;
-- that traded away the offline guarantee and depended on a third-party
-- database with its own lifecycle, so it moved back here.

PRAGMA foreign_keys = ON;

-- ============================================================
-- USERS & SESSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,      -- PBKDF2-SHA256 hex digest
    salt            TEXT NOT NULL,      -- unique random salt, hex, per user
    role            TEXT NOT NULL CHECK (role IN ('manager', 'staff')),
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

-- Deactivated staff are never deleted (active=0) so historical sales/audit rows
-- keep a valid foreign key and remain attributable.

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    login_at    TEXT NOT NULL,
    logout_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- ============================================================
-- MENU: categories -> menu_items -> item_variants
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    colour_hex  TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS menu_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    has_variants    INTEGER NOT NULL DEFAULT 0 CHECK (has_variants IN (0, 1)),
    base_photo_url  TEXT,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    -- A manager-uploaded item photo (e.g. a new seasonal item added from the
    -- dashboard) is stored directly here rather than as a file on disk —
    -- keeps the whole app's data in the one SQLite file, so a single backup
    -- of that file backs up everything, photos included.
    photo_blob          BLOB,
    photo_content_type  TEXT,
    UNIQUE (category_id, name)
);

CREATE INDEX IF NOT EXISTS idx_menu_items_category ON menu_items(category_id);

-- Every sellable thing is an item_variant, even single-price items (they get
-- exactly one variant row, e.g. label 'Standard'). This keeps every table that
-- references "the thing that was sold" (recipes, inventory_daily, sale_items,
-- wastage) pointing at a single id type instead of juggling nullable
-- menu_item_id / item_variant_id pairs everywhere.
CREATE TABLE IF NOT EXISTS item_variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,
    unit                TEXT NOT NULL,          -- e.g. 'kg', 'litre', 'unit'
    current_stock       REAL NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    reorder_threshold   REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
-- of truth for sales counts. opening_count is how many of an item are
-- available today — set (and freely adjustable during the day) by a
-- manager; closing_count is entered manually at day's end and compared
-- against opening_count - sold to flag inventory mismatches.
CREATE TABLE IF NOT EXISTS inventory_daily (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,          -- 'YYYY-MM-DD'
    item_variant_id INTEGER NOT NULL REFERENCES item_variants(id) ON DELETE RESTRICT,
    opening_count   INTEGER NOT NULL DEFAULT 0 CHECK (opening_count >= 0),
    closing_count   INTEGER,                -- NULL until entered
    UNIQUE (date, item_variant_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_daily_date ON inventory_daily(date);

-- ============================================================
-- RESTAURANT TABLES (dine-in service)
-- ============================================================

-- A fixed set of physical tables (seeded once, see seed.py). Dine-in
-- ordering works as a running tab (table_orders/table_order_items) that
-- accumulates over the course of a meal, separate from the till's
-- ring-up-and-pay-immediately counter sales — a table only turns into a
-- `sales` row (via checkout_table_order) once the bill is actually paid.
CREATE TABLE IF NOT EXISTS restaurant_tables (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- SALES
-- ============================================================

CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,      -- full date+time, e.g. '2026-07-30T14:05:00'
    staff_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    -- 'cash', 'card' (POS terminal, displayed as "POS"), or 'transfer'.
    payment_method  TEXT NOT NULL CHECK (payment_method IN ('cash', 'card', 'transfer')),
    subtotal        REAL NOT NULL CHECK (subtotal >= 0),
    vat_amount      REAL NOT NULL CHECK (vat_amount >= 0),
    total           REAL NOT NULL CHECK (total >= 0),
    -- NULL for a walk-in counter sale; set for a dine-in sale created via
    -- checkout_table_order(), so sales can be reported/filtered by table too.
    table_id        INTEGER REFERENCES restaurant_tables(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales(timestamp);
CREATE INDEX IF NOT EXISTS idx_sales_staff ON sales(staff_user_id);

CREATE TABLE IF NOT EXISTS sale_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
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
-- EXPENSES & WASTAGE
-- ============================================================

-- A free-form expense log — ingredient purchases (flour, sugar...) and
-- everything else a business actually spends money on (salaries,
-- electricity, water, repairs, rent...). Deliberately NOT tied to a
-- picklist of ingredients: whoever's logging it types what it was, picks a
-- category (for reporting — "how much on electricity this month"), how
-- much (quantity + unit, when that's meaningful — leave quantity blank for
-- a lump-sum bill like electricity), the TOTAL paid, and how it was paid.
-- ingredient_id is set automatically only for category='ingredients' (see
-- services.record_expense) — matched against an existing ingredient by
-- name, or a brand new one is created — so recipe-based stock depletion
-- keeps working without a separate "register this ingredient" step.
-- `date` stays a plain 'YYYY-MM-DD' for date-range filtering everywhere
-- else in the app; `logged_at` is the full timestamp, so the manager can
-- see what hour an entry was actually made.
CREATE TABLE IF NOT EXISTS expenses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name           TEXT NOT NULL,          -- e.g. 'Flour', 'NEPA Bill', 'Staff Salary — June'
    category            TEXT NOT NULL CHECK (category IN
                            ('ingredients', 'salary', 'electricity', 'water', 'rent', 'repairs_maintenance', 'other')),
    quantity            REAL,                    -- nullable — not every expense has a meaningful quantity
    unit                TEXT,                    -- e.g. 'kg', 'grams', 'litres', 'units' — nullable
    total_cost          REAL NOT NULL CHECK (total_cost >= 0),
    payment_method      TEXT NOT NULL CHECK (payment_method IN ('cash', 'card', 'transfer')),
    supplier_or_payee   TEXT,
    ingredient_id       INTEGER REFERENCES ingredients(id) ON DELETE RESTRICT,
    date                TEXT NOT NULL,
    logged_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    logged_by_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_ingredient ON expenses(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);

CREATE TABLE IF NOT EXISTS wastage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_variant_id INTEGER NOT NULL REFERENCES item_variants(id) ON DELETE RESTRICT,
    quantity        REAL NOT NULL CHECK (quantity > 0),
    reason          TEXT NOT NULL,
    value_lost      REAL NOT NULL CHECK (value_lost >= 0),
    date            TEXT NOT NULL,
    logged_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    logged_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_wastage_date ON wastage(date);

-- ============================================================
-- RECONCILIATION
-- ============================================================

CREATE TABLE IF NOT EXISTS reconciliation (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    date                    TEXT NOT NULL,
    staff_user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    system_cash_total       REAL NOT NULL CHECK (system_cash_total >= 0),
    cash_expenses_total     REAL NOT NULL DEFAULT 0 CHECK (cash_expenses_total >= 0),
    counted_cash_total      REAL NOT NULL CHECK (counted_cash_total >= 0),
    discrepancy_amount      REAL NOT NULL,
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_date ON reconciliation(date);
CREATE INDEX IF NOT EXISTS idx_reconciliation_staff ON reconciliation(staff_user_id);

-- ============================================================
-- AUDIT LOG — every void, manual adjustment, and manager override
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action_type     TEXT NOT NULL,      -- e.g. 'VOID_SALE_ITEM', 'RESET_PASSWORD', 'STOCK_ADJUST'
    details         TEXT                -- free-text / JSON description
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);

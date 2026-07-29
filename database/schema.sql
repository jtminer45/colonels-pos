-- Colonel's Bakery and Restaurant — POS & Management System
-- SQLite schema. Designed to move to a networked (Pi + LAN) deployment later
-- without structural changes — only the connection target changes, not this schema.

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
-- of truth for sales counts. opening_count is set at start of day (or by a
-- manager/staff stock take); closing_count is entered manually at day's end
-- and compared against opening_count - sold to flag inventory mismatches.
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
-- SALES
-- ============================================================

CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    staff_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    payment_method  TEXT NOT NULL CHECK (payment_method IN ('cash', 'card')),
    subtotal        REAL NOT NULL CHECK (subtotal >= 0),
    vat_amount      REAL NOT NULL CHECK (vat_amount >= 0),
    total           REAL NOT NULL CHECK (total >= 0)
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
-- PURCHASES & WASTAGE (ingredient stock movements)
-- ============================================================

CREATE TABLE IF NOT EXISTS purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    date                    TEXT NOT NULL,
    staff_user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    system_cash_total       REAL NOT NULL CHECK (system_cash_total >= 0),
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

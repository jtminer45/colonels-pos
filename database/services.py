"""
Shared business logic for Colonel's Bakery and Restaurant POS.

This module is imported by BOTH the FastAPI till backend and the Streamlit
manager dashboard, so a sale recorded from the till and a manual stock
adjustment made from the dashboard go through the exact same code paths,
constraints, and audit logging — there is no separate "sync" step because
both surfaces read and write the same SQLite database via these functions.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from db import get_connection, now_iso, today_str, VAT_RATE
from auth import require_manager, hash_new_password, generate_temp_password
from audit import log_action


class ServiceError(Exception):
    """Raised for business-rule violations (insufficient stock, bad input, etc.)."""


# Used as base_photo_url for a newly-created menu item that has no specific
# photo uploaded yet — one generic bundled icon per category, shipped in
# both assets/menu_photos/ and till-app/public/menu_photos/.
CATEGORY_FALLBACK_PHOTOS = {
    "Cakes": "cakes.svg",
    "Bread": "bread.svg",
    "Drinks": "drinks.svg",
    "Ice Cream": "ice_cream.svg",
    "Restaurant — Local Dishes": "local_dishes.svg",
    "Restaurant — Intercontinental Dishes": "intercontinental_dishes.svg",
    "Snacks & Pies": "pies.svg",
}

# Public URL of the backend, used to build an absolute photo URL
# (PUBLIC_BACKEND_URL/photos/{item_id}) for manager-uploaded photos so the
# dashboard (a different process/host) and the till app can both load them
# directly in an <img>/st.image — no auth needed, it's just a food photo.
PUBLIC_BACKEND_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8000")


# ============================================================
# MENU / AVAILABILITY
# ============================================================

def get_menu_tree(date: Optional[str] = None) -> list[dict]:
    """Returns categories -> active menu items -> active variants, each variant
    annotated with today's remaining available count (None = not tracked / unlimited).
    """
    date = date or today_str()
    conn = get_connection()
    try:
        categories = conn.execute(
            "SELECT id, name, colour_hex, sort_order FROM categories ORDER BY sort_order, name"
        ).fetchall()

        result = []
        for cat in categories:
            items = conn.execute(
                "SELECT id, name, has_variants, base_photo_url FROM menu_items "
                "WHERE category_id = ? AND active = 1 ORDER BY name",
                (cat["id"],),
            ).fetchall()

            item_list = []
            for item in items:
                variants = conn.execute(
                    "SELECT id, variant_label, price FROM item_variants "
                    "WHERE menu_item_id = ? AND active = 1 ORDER BY price",
                    (item["id"],),
                ).fetchall()

                variant_list = []
                for v in variants:
                    available = _available_count(conn, v["id"], date)
                    variant_list.append({
                        "id": v["id"],
                        "variant_label": v["variant_label"],
                        "price": v["price"],
                        "available": available,
                        "sold_out": available is not None and available <= 0,
                    })

                item_list.append({
                    "id": item["id"],
                    "name": item["name"],
                    "has_variants": bool(item["has_variants"]),
                    "base_photo_url": item["base_photo_url"],
                    "variants": variant_list,
                })

            result.append({
                "id": cat["id"],
                "name": cat["name"],
                "colour_hex": cat["colour_hex"],
                "items": item_list,
            })
        return result
    finally:
        conn.close()


def _available_count(conn, item_variant_id: int, date: str) -> Optional[int]:
    """opening_count - sold (non-voided) - wasted, for that date. None if the
    variant has no inventory_daily row for the date (not stock-tracked today)."""
    row = conn.execute(
        "SELECT opening_count FROM inventory_daily WHERE item_variant_id = ? AND date = ?",
        (item_variant_id, date),
    ).fetchone()
    if row is None:
        return None

    sold = conn.execute(
        "SELECT COALESCE(SUM(si.quantity), 0) AS qty FROM sale_items si "
        "JOIN sales s ON s.id = si.sale_id "
        "WHERE si.item_variant_id = ? AND si.is_voided = 0 AND date(s.timestamp) = ?",
        (item_variant_id, date),
    ).fetchone()["qty"]

    wasted = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS qty FROM wastage "
        "WHERE item_variant_id = ? AND date = ?",
        (item_variant_id, date),
    ).fetchone()["qty"]

    # Dine-in items reserve stock the moment they're added to a table's tab
    # (the kitchen starts cooking then), not only once the bill is paid —
    # otherwise a table's in-progress order wouldn't show up against
    # availability at the counter, and both channels could oversell the
    # same last few units of something.
    table_reserved = conn.execute(
        "SELECT COALESCE(SUM(toi.quantity), 0) AS qty FROM table_order_items toi "
        "JOIN table_orders too ON too.id = toi.table_order_id "
        "WHERE toi.item_variant_id = ? AND toi.is_voided = 0 AND too.status <> 'closed' "
        "AND date(toi.added_at) = ?",
        (item_variant_id, date),
    ).fetchone()["qty"]

    return row["opening_count"] - sold - wasted - table_reserved


def initialize_inventory_for_date(date: str, opening_counts: dict[int, int]) -> None:
    """Sets today's opening counts. opening_counts maps item_variant_id -> count.
    Existing rows for the date are left untouched (idempotent / additive)."""
    conn = get_connection()
    try:
        for item_variant_id, count in opening_counts.items():
            conn.execute(
                "INSERT INTO inventory_daily (date, item_variant_id, opening_count) "
                "VALUES (?, ?, ?) ON CONFLICT (date, item_variant_id) DO NOTHING",
                (date, item_variant_id, count),
            )
        conn.commit()
    finally:
        conn.close()


def set_opening_count(date: str, item_variant_id: int, opening_count: int, user_id: int) -> None:
    """Sets (or changes) how many of an item are available today — this is
    what drives the till's "Sold Out" state (available = opening_count -
    sold - wasted - reserved-by-open-table-tabs). Unlike
    initialize_inventory_for_date(), this UPSERTs — a manager can adjust it
    mid-day (kitchen made more, or something ran out), not just set it once
    at day-start."""
    if opening_count < 0:
        raise ServiceError("Opening count cannot be negative.")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO inventory_daily (date, item_variant_id, opening_count) VALUES (?, ?, ?) "
            "ON CONFLICT (date, item_variant_id) DO UPDATE SET opening_count = EXCLUDED.opening_count",
            (date, item_variant_id, opening_count),
        )
        log_action(conn, user_id, "INVENTORY_OPENING_COUNT_SET",
                   f"variant={item_variant_id} date={date} opening_count={opening_count}")
        conn.commit()
    finally:
        conn.close()


def set_closing_count(date: str, item_variant_id: int, closing_count: int, user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE inventory_daily SET closing_count = ? WHERE date = ? AND item_variant_id = ?",
            (closing_count, date, item_variant_id),
        )
        log_action(conn, user_id, "INVENTORY_CLOSING_COUNT",
                   f"variant={item_variant_id} date={date} closing_count={closing_count}")
        conn.commit()
    finally:
        conn.close()


# ============================================================
# SALES
# ============================================================

@dataclass
class CartLine:
    item_variant_id: int
    quantity: int


@dataclass
class SaleReceipt:
    sale_id: int
    timestamp: str
    staff_username: str
    payment_method: str
    lines: list[dict] = field(default_factory=list)
    subtotal: float = 0.0
    vat_amount: float = 0.0
    total: float = 0.0


def record_sale(cart: list[CartLine], staff_user_id: int, payment_method: str) -> SaleReceipt:
    if not cart:
        raise ServiceError("Cannot record an empty sale.")
    if payment_method not in ("cash", "card", "transfer"):
        raise ServiceError("Invalid payment method.")

    date = today_str()
    conn = get_connection()
    try:
        staff_row = conn.execute(
            "SELECT username FROM users WHERE id = ? AND active = 1", (staff_user_id,)
        ).fetchone()
        if staff_row is None:
            raise ServiceError("Staff account is not valid or is inactive.")

        # Validate availability and fetch current prices server-side — never
        # trust a price sent by the client.
        line_details = []
        for line in cart:
            if line.quantity <= 0:
                raise ServiceError("Quantity must be positive.")
            variant = conn.execute(
                "SELECT iv.id, iv.price, iv.variant_label, mi.name AS item_name "
                "FROM item_variants iv JOIN menu_items mi ON mi.id = iv.menu_item_id "
                "WHERE iv.id = ? AND iv.active = 1",
                (line.item_variant_id,),
            ).fetchone()
            if variant is None:
                raise ServiceError(f"Item variant {line.item_variant_id} is not available.")

            available = _available_count(conn, variant["id"], date)
            if available is not None and available < line.quantity:
                raise ServiceError(f"{variant['item_name']} ({variant['variant_label']}) is sold out.")

            line_details.append({
                "item_variant_id": variant["id"],
                "item_name": variant["item_name"],
                "variant_label": variant["variant_label"],
                "quantity": line.quantity,
                "unit_price": variant["price"],
                "line_total": variant["price"] * line.quantity,
            })

        subtotal = sum(l["line_total"] for l in line_details)
        vat_amount = round(subtotal * VAT_RATE, 2)
        total = round(subtotal + vat_amount, 2)
        timestamp = now_iso()

        cur = conn.execute(
            "INSERT INTO sales (timestamp, staff_user_id, payment_method, subtotal, vat_amount, total) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, staff_user_id, payment_method, subtotal, vat_amount, total),
        )
        sale_id = cur.lastrowid

        for l in line_details:
            item_cur = conn.execute(
                "INSERT INTO sale_items (sale_id, item_variant_id, quantity, unit_price) "
                "VALUES (?, ?, ?, ?)",
                (sale_id, l["item_variant_id"], l["quantity"], l["unit_price"]),
            )
            l["sale_item_id"] = item_cur.lastrowid
            _deplete_ingredients(conn, l["item_variant_id"], l["quantity"])

        conn.commit()

        return SaleReceipt(
            sale_id=sale_id,
            timestamp=timestamp,
            staff_username=staff_row["username"],
            payment_method=payment_method,
            lines=line_details,
            subtotal=subtotal,
            vat_amount=vat_amount,
            total=total,
        )
    finally:
        conn.close()


def _deplete_ingredients(conn, item_variant_id: int, quantity_sold: int) -> None:
    recipe_rows = conn.execute(
        "SELECT ingredient_id, quantity_used FROM recipes WHERE item_variant_id = ?",
        (item_variant_id,),
    ).fetchall()
    for r in recipe_rows:
        conn.execute(
            "UPDATE ingredients SET current_stock = MAX(0, current_stock - ?) WHERE id = ?",
            (r["quantity_used"] * quantity_sold, r["ingredient_id"]),
        )


def void_sale_item(sale_item_id: int, user_id: int, reason: str) -> None:
    if not reason or not reason.strip():
        raise ServiceError("A void reason is required.")

    conn = get_connection()
    try:
        item = conn.execute(
            "SELECT si.*, s.subtotal, s.vat_amount, s.total, s.id AS sale_id "
            "FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE si.id = ?",
            (sale_item_id,),
        ).fetchone()
        if item is None:
            raise ServiceError("Sale item not found.")
        if item["is_voided"]:
            raise ServiceError("This item has already been voided.")

        line_total = item["unit_price"] * item["quantity"]
        line_vat = round(line_total * VAT_RATE, 2)

        conn.execute(
            "UPDATE sale_items SET is_voided = 1, voided_by = ?, void_reason = ?, voided_at = ? "
            "WHERE id = ?",
            (user_id, reason, now_iso(), sale_item_id),
        )
        conn.execute(
            "UPDATE sales SET subtotal = subtotal - ?, vat_amount = vat_amount - ?, "
            "total = total - ? WHERE id = ?",
            (line_total, line_vat, line_total + line_vat, item["sale_id"]),
        )
        # Return depleted ingredient stock for the voided item.
        recipe_rows = conn.execute(
            "SELECT ingredient_id, quantity_used FROM recipes WHERE item_variant_id = ?",
            (item["item_variant_id"],),
        ).fetchall()
        for r in recipe_rows:
            conn.execute(
                "UPDATE ingredients SET current_stock = current_stock + ? WHERE id = ?",
                (r["quantity_used"] * item["quantity"], r["ingredient_id"]),
            )

        log_action(conn, user_id, "VOID_SALE_ITEM",
                   f"sale_item={sale_item_id} sale={item['sale_id']} reason={reason}")
        conn.commit()
    finally:
        conn.close()


def get_shift_summary(user_id: int, session_id: int) -> dict:
    """Running total for the staff member's CURRENT shift only — sales since
    their most recent login — not their whole day or lifetime, matching the
    till UI's "current shift running total" requirement."""
    conn = get_connection()
    try:
        session = conn.execute(
            "SELECT login_at FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if session is None:
            raise ServiceError("Session not found.")

        row = conn.execute(
            "SELECT COUNT(*) AS sale_count, COALESCE(SUM(total), 0) AS total_sales "
            "FROM sales WHERE staff_user_id = ? AND timestamp >= ?",
            (user_id, session["login_at"]),
        ).fetchone()
        return {
            "since": session["login_at"],
            "sale_count": row["sale_count"],
            "total_sales": row["total_sales"],
        }
    finally:
        conn.close()


# ============================================================
# DINE-IN TABLES — a running tab per table (table_orders/table_order_items)
# that only becomes a `sales` record once the bill is actually paid
# (checkout_table_order). Ingredient stock is depleted the moment an item
# is added to a table's tab (see _deplete_ingredients calls below), not
# deferred to payment — the kitchen is cooking it either way.
# ============================================================

def list_tables() -> list[dict]:
    """All tables with their current open order summary, for the till's
    table grid — status is 'empty' if nothing is open right now."""
    conn = get_connection()
    try:
        tables = conn.execute(
            "SELECT id, label, sort_order FROM restaurant_tables ORDER BY sort_order, label"
        ).fetchall()
        result = []
        for t in tables:
            order = conn.execute(
                "SELECT id, status, opened_at FROM table_orders WHERE table_id = ? AND status <> 'closed'",
                (t["id"],),
            ).fetchone()
            running_total = 0.0
            item_count = 0
            if order is not None:
                totals = conn.execute(
                    "SELECT COALESCE(SUM(quantity * unit_price), 0) AS total, COALESCE(SUM(quantity), 0) AS qty "
                    "FROM table_order_items WHERE table_order_id = ? AND is_voided = 0",
                    (order["id"],),
                ).fetchone()
                running_total = totals["total"]
                item_count = totals["qty"]
            result.append({
                "id": t["id"],
                "label": t["label"],
                "status": order["status"] if order is not None else "empty",
                "table_order_id": order["id"] if order is not None else None,
                "opened_at": order["opened_at"] if order is not None else None,
                "running_total": running_total,
                "item_count": item_count,
            })
        return result
    finally:
        conn.close()


def get_open_table_order_id(table_id: int) -> Optional[int]:
    """The current non-closed order id for a table, or None if it's empty
    right now. The till mostly thinks in terms of "table 5", not order ids —
    this is how a route resolves one from the other."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM table_orders WHERE table_id = ? AND status <> 'closed'", (table_id,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_table_order_detail(table_order_id: int) -> dict:
    """Full itemized detail for one table's tab — used both to render the
    till's per-table order screen and to render/print the pre-payment bill."""
    conn = get_connection()
    try:
        order = conn.execute(
            "SELECT too.*, rt.label AS table_label FROM table_orders too "
            "JOIN restaurant_tables rt ON rt.id = too.table_id WHERE too.id = ?",
            (table_order_id,),
        ).fetchone()
        if order is None:
            raise ServiceError("Table order not found.")

        items = conn.execute(
            "SELECT toi.id AS table_order_item_id, toi.item_variant_id, toi.quantity, toi.unit_price, "
            "toi.is_voided, mi.name AS item_name, iv.variant_label "
            "FROM table_order_items toi "
            "JOIN item_variants iv ON iv.id = toi.item_variant_id "
            "JOIN menu_items mi ON mi.id = iv.menu_item_id "
            "WHERE toi.table_order_id = ? ORDER BY toi.id",
            (table_order_id,),
        ).fetchall()

        active = [dict(i) for i in items if not i["is_voided"]]
        subtotal = sum(i["quantity"] * i["unit_price"] for i in active)
        vat_amount = round(subtotal * VAT_RATE, 2)
        total = round(subtotal + vat_amount, 2)

        return {
            "table_order_id": order["id"],
            "table_id": order["table_id"],
            "table_label": order["table_label"],
            "status": order["status"],
            "opened_at": order["opened_at"],
            "items": [dict(i) for i in items],
            "subtotal": subtotal,
            "vat_amount": vat_amount,
            "total": total,
        }
    finally:
        conn.close()


def add_item_to_table_order(table_id: int, item_variant_id: int, quantity: int, staff_user_id: int) -> int:
    """Adds a line to the table's current open tab, opening one if this
    table doesn't already have one. Validates availability and depletes
    ingredient stock immediately, exactly like a counter sale does."""
    if quantity <= 0:
        raise ServiceError("Quantity must be positive.")

    date = today_str()
    conn = get_connection()
    try:
        table = conn.execute("SELECT label FROM restaurant_tables WHERE id = ?", (table_id,)).fetchone()
        if table is None:
            raise ServiceError("Table not found.")

        order_row = conn.execute(
            "SELECT id FROM table_orders WHERE table_id = ? AND status <> 'closed'", (table_id,)
        ).fetchone()
        if order_row is None:
            cur = conn.execute(
                "INSERT INTO table_orders (table_id, staff_user_id, opened_at, status) "
                "VALUES (?, ?, ?, 'open')",
                (table_id, staff_user_id, now_iso()),
            )
            table_order_id = cur.lastrowid
        else:
            table_order_id = order_row["id"]

        variant = conn.execute(
            "SELECT iv.id, iv.price, iv.variant_label, mi.name AS item_name "
            "FROM item_variants iv JOIN menu_items mi ON mi.id = iv.menu_item_id "
            "WHERE iv.id = ? AND iv.active = 1",
            (item_variant_id,),
        ).fetchone()
        if variant is None:
            raise ServiceError("Item variant is not available.")

        available = _available_count(conn, item_variant_id, date)
        if available is not None and available < quantity:
            raise ServiceError(f"{variant['item_name']} ({variant['variant_label']}) is sold out.")

        cur = conn.execute(
            "INSERT INTO table_order_items (table_order_id, item_variant_id, quantity, unit_price, "
            "added_at, added_by_user_id) VALUES (?, ?, ?, ?, ?, ?)",
            (table_order_id, item_variant_id, quantity, variant["price"], now_iso(), staff_user_id),
        )
        table_order_item_id = cur.lastrowid
        _deplete_ingredients(conn, item_variant_id, quantity)

        log_action(conn, staff_user_id, "TABLE_ORDER_ITEM_ADDED",
                   f"table={table['label']} item={variant['item_name']} ({variant['variant_label']}) qty={quantity}")
        conn.commit()
        return table_order_item_id
    finally:
        conn.close()


def void_table_order_item(table_order_item_id: int, user_id: int, reason: str) -> None:
    """Voids an unpaid line before checkout (e.g. the kitchen got the order
    wrong) — reason required and audit-logged, same as voiding a completed
    sale. Restores the ingredient stock that was depleted when it was added."""
    if not reason or not reason.strip():
        raise ServiceError("A void reason is required.")

    conn = get_connection()
    try:
        item = conn.execute(
            "SELECT toi.*, too.table_id, rt.label AS table_label "
            "FROM table_order_items toi "
            "JOIN table_orders too ON too.id = toi.table_order_id "
            "JOIN restaurant_tables rt ON rt.id = too.table_id "
            "WHERE toi.id = ?",
            (table_order_item_id,),
        ).fetchone()
        if item is None:
            raise ServiceError("Item not found.")
        if item["is_voided"]:
            raise ServiceError("This item has already been voided.")

        conn.execute(
            "UPDATE table_order_items SET is_voided = 1, voided_by = ?, void_reason = ?, voided_at = ? "
            "WHERE id = ?",
            (user_id, reason, now_iso(), table_order_item_id),
        )
        recipe_rows = conn.execute(
            "SELECT ingredient_id, quantity_used FROM recipes WHERE item_variant_id = ?",
            (item["item_variant_id"],),
        ).fetchall()
        for r in recipe_rows:
            conn.execute(
                "UPDATE ingredients SET current_stock = current_stock + ? WHERE id = ?",
                (r["quantity_used"] * item["quantity"], r["ingredient_id"]),
            )

        log_action(conn, user_id, "TABLE_ORDER_ITEM_VOIDED",
                   f"table={item['table_label']} table_order_item={table_order_item_id} reason={reason}")
        conn.commit()
    finally:
        conn.close()


def request_table_bill(table_order_id: int, user_id: int) -> None:
    """Marks a table as having asked for the bill — a status flag only
    (printing the bill itself needs no DB write); doesn't close the tab, so
    more items can still be added if the table orders something else."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE table_orders SET status = 'bill_requested' WHERE id = ? AND status <> 'closed'",
            (table_order_id,),
        )
        conn.commit()
    finally:
        conn.close()


def checkout_table_order(table_order_id: int, payment_method: str, staff_user_id: int) -> SaleReceipt:
    """Pays off a table's tab: turns its (non-voided) items into a real
    `sales` + `sale_items` record — the same financial record a counter sale
    produces, so it shows up identically in analytics/reconciliation — and
    closes the table so it's free for the next customers. Does NOT deplete
    ingredients again; that already happened when each item was ordered."""
    if payment_method not in ("cash", "card", "transfer"):
        raise ServiceError("Invalid payment method.")

    conn = get_connection()
    try:
        order = conn.execute(
            "SELECT too.*, rt.label AS table_label FROM table_orders too "
            "JOIN restaurant_tables rt ON rt.id = too.table_id WHERE too.id = ?",
            (table_order_id,),
        ).fetchone()
        if order is None:
            raise ServiceError("Table order not found.")
        if order["status"] == "closed":
            raise ServiceError("This table has already been paid.")

        items = conn.execute(
            "SELECT toi.item_variant_id, toi.quantity, toi.unit_price, "
            "mi.name AS item_name, iv.variant_label "
            "FROM table_order_items toi "
            "JOIN item_variants iv ON iv.id = toi.item_variant_id "
            "JOIN menu_items mi ON mi.id = iv.menu_item_id "
            "WHERE toi.table_order_id = ? AND toi.is_voided = 0",
            (table_order_id,),
        ).fetchall()
        if not items:
            raise ServiceError("Cannot check out a table with no items.")

        staff_row = conn.execute(
            "SELECT username FROM users WHERE id = ? AND active = 1", (staff_user_id,)
        ).fetchone()
        if staff_row is None:
            raise ServiceError("Staff account is not valid or is inactive.")

        subtotal = sum(i["quantity"] * i["unit_price"] for i in items)
        vat_amount = round(subtotal * VAT_RATE, 2)
        total = round(subtotal + vat_amount, 2)
        timestamp = now_iso()

        cur = conn.execute(
            "INSERT INTO sales (timestamp, staff_user_id, payment_method, subtotal, vat_amount, total, table_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (timestamp, staff_user_id, payment_method, subtotal, vat_amount, total, order["table_id"]),
        )
        sale_id = cur.lastrowid

        line_details = []
        for i in items:
            item_cur = conn.execute(
                "INSERT INTO sale_items (sale_id, item_variant_id, quantity, unit_price) "
                "VALUES (?, ?, ?, ?)",
                (sale_id, i["item_variant_id"], i["quantity"], i["unit_price"]),
            )
            line_details.append({
                "sale_item_id": item_cur.lastrowid,
                "item_variant_id": i["item_variant_id"],
                "item_name": i["item_name"],
                "variant_label": i["variant_label"],
                "quantity": i["quantity"],
                "unit_price": i["unit_price"],
                "line_total": i["quantity"] * i["unit_price"],
            })

        conn.execute(
            "UPDATE table_orders SET status = 'closed', closed_at = ?, sale_id = ? WHERE id = ?",
            (timestamp, sale_id, table_order_id),
        )
        log_action(conn, staff_user_id, "TABLE_CHECKOUT",
                   f"table={order['table_label']} table_order={table_order_id} sale={sale_id} total={total}")
        conn.commit()

        return SaleReceipt(
            sale_id=sale_id,
            timestamp=timestamp,
            staff_username=staff_row["username"],
            payment_method=payment_method,
            lines=line_details,
            subtotal=subtotal,
            vat_amount=vat_amount,
            total=total,
        )
    finally:
        conn.close()


# ============================================================
# EXPENSES & WASTAGE
# ============================================================

EXPENSE_CATEGORIES = ("ingredients", "salary", "electricity", "water", "rent", "repairs_maintenance", "other")


def record_expense(
    item_name: str,
    category: str,
    quantity: Optional[float],
    unit: Optional[str],
    total_cost: float,
    payment_method: str,
    date: str,
    user_id: int,
    supplier_or_payee: str = "",
) -> int:
    """Logs any business cost — ingredient restocking, salaries, electricity,
    water, rent, repairs, or anything else — as one free-text entry rather
    than requiring everything to be pre-registered as a known "ingredient"
    first. Only category='ingredients' touches stock: if item_name matches
    an existing ingredient (case-insensitive), that ingredient's
    current_stock goes up by quantity; if it doesn't match anything yet,
    a new ingredient is created automatically from the name/unit typed
    here — there is no separate "add an ingredient" step to do first.
    """
    if not item_name.strip():
        raise ServiceError("Item name is required.")
    if category not in EXPENSE_CATEGORIES:
        raise ServiceError("Invalid expense category.")
    if total_cost < 0:
        raise ServiceError("Total cost cannot be negative.")
    if payment_method not in ("cash", "card", "transfer"):
        raise ServiceError("Invalid payment method.")
    if quantity is not None and quantity <= 0:
        raise ServiceError("Quantity must be positive if given.")

    conn = get_connection()
    try:
        ingredient_id = None
        if category == "ingredients":
            existing = conn.execute(
                "SELECT id FROM ingredients WHERE lower(name) = lower(?)", (item_name.strip(),)
            ).fetchone()
            if existing:
                ingredient_id = existing["id"]
                if quantity:
                    conn.execute(
                        "UPDATE ingredients SET current_stock = current_stock + ? WHERE id = ?",
                        (quantity, ingredient_id),
                    )
            elif quantity and unit:
                # First time this ingredient has been bought — register it
                # automatically instead of making the manager do that
                # separately before she can log the purchase.
                cur = conn.execute(
                    "INSERT INTO ingredients (name, unit, current_stock, reorder_threshold) "
                    "VALUES (?, ?, ?, 0)",
                    (item_name.strip(), unit.strip(), quantity),
                )
                ingredient_id = cur.lastrowid

        cur = conn.execute(
            "INSERT INTO expenses (item_name, category, quantity, unit, total_cost, payment_method, "
            "supplier_or_payee, ingredient_id, date, logged_by_user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_name.strip(), category, quantity, unit, total_cost, payment_method,
             supplier_or_payee, ingredient_id, date, user_id),
        )
        expense_id = cur.lastrowid
        log_action(conn, user_id, "EXPENSE_LOGGED",
                   f"item={item_name} category={category} total_cost={total_cost} payment_method={payment_method}")
        conn.commit()
        return expense_id
    finally:
        conn.close()


def set_ingredient_stock(item_name: str, quantity: float, unit: str, user_id: int) -> int:
    """Manually sets an ingredient's stock to a physically-counted amount —
    e.g. after a stocktake, or to correct drift from unlogged use. Free-text
    name, same as record_expense(): if it matches an existing ingredient
    (case-insensitive) that ingredient's current_stock is overwritten with
    the counted amount; if it doesn't match anything yet, a new ingredient
    is created with this as its starting stock. This overwrites the stock
    figure rather than adding to it, since the manager is reporting what's
    actually on the shelf right now, not a delta.
    """
    if not item_name.strip():
        raise ServiceError("Ingredient name is required.")
    if quantity < 0:
        raise ServiceError("Amount cannot be negative.")
    if not unit or not unit.strip():
        raise ServiceError("Unit is required.")

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, current_stock FROM ingredients WHERE lower(name) = lower(?)", (item_name.strip(),)
        ).fetchone()
        if existing:
            ingredient_id = existing["id"]
            previous = existing["current_stock"]
            conn.execute("UPDATE ingredients SET current_stock = ? WHERE id = ?", (quantity, ingredient_id))
        else:
            cur = conn.execute(
                "INSERT INTO ingredients (name, unit, current_stock, reorder_threshold) VALUES (?, ?, ?, 0)",
                (item_name.strip(), unit.strip(), quantity),
            )
            ingredient_id = cur.lastrowid
            previous = None
        log_action(conn, user_id, "STOCK_COUNT_SET",
                   f"ingredient={item_name} new_stock={quantity} {unit} (was {previous})")
        conn.commit()
        return ingredient_id
    finally:
        conn.close()


def record_wastage(item_variant_id: int, quantity: float, reason: str,
                    value_lost: float, date: str, user_id: int) -> int:
    if quantity <= 0:
        raise ServiceError("Wastage quantity must be positive.")
    if not reason or not reason.strip():
        raise ServiceError("A wastage reason is required.")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO wastage (item_variant_id, quantity, reason, value_lost, date, logged_by_user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (item_variant_id, quantity, reason, value_lost, date, user_id),
        )
        wastage_id = cur.lastrowid
        log_action(conn, user_id, "WASTAGE_LOGGED",
                   f"variant={item_variant_id} qty={quantity} value_lost={value_lost} reason={reason}")
        conn.commit()
        return wastage_id
    finally:
        conn.close()


# ============================================================
# RECONCILIATION
# ============================================================

def record_reconciliation(date: str, staff_user_id: int, counted_cash_total: float,
                           notes: str, logged_by_user_id: int) -> dict:
    """Compares the physically-counted cash drawer against what the system
    expects to be there: that staff member's cash sales for the day, minus
    any cash-paid expenses logged that same day (supplies/repairs paid for
    out of the drawer are a legitimate reason cash is short, not a
    discrepancy). Also returns this month's total cash sales for context.
    """
    conn = get_connection()
    try:
        system_cash_total = conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS t FROM sales "
            "WHERE payment_method = 'cash' AND date(timestamp) = ? AND staff_user_id = ?",
            (date, staff_user_id),
        ).fetchone()["t"]

        cash_expenses_total = conn.execute(
            "SELECT COALESCE(SUM(total_cost), 0) AS t FROM expenses "
            "WHERE payment_method = 'cash' AND date = ?",
            (date,),
        ).fetchone()["t"]

        expected_cash = system_cash_total - cash_expenses_total
        discrepancy = round(counted_cash_total - expected_cash, 2)

        conn.execute(
            "INSERT INTO reconciliation (date, staff_user_id, system_cash_total, "
            "cash_expenses_total, counted_cash_total, discrepancy_amount, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (date, staff_user_id, system_cash_total, cash_expenses_total,
             counted_cash_total, discrepancy, notes),
        )
        if abs(discrepancy) > 0.01:
            log_action(conn, logged_by_user_id, "RECONCILIATION_MISMATCH",
                       f"date={date} staff={staff_user_id} discrepancy={discrepancy}")
        conn.commit()

        month_prefix = date[:7]  # YYYY-MM
        month_cash_total = conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS t FROM sales "
            "WHERE payment_method = 'cash' AND strftime('%Y-%m', timestamp) = ?",
            (month_prefix,),
        ).fetchone()["t"]

        return {
            "system_cash_total": system_cash_total,
            "cash_expenses_total": cash_expenses_total,
            "expected_cash": expected_cash,
            "counted_cash_total": counted_cash_total,
            "discrepancy_amount": discrepancy,
            "month_cash_total": month_cash_total,
        }
    finally:
        conn.close()


# ============================================================
# STAFF MANAGEMENT (manager only — every function re-checks the role
# server-side; a hidden button on the dashboard is not the security boundary)
# ============================================================

def create_staff_account(username: str, role: str, created_by_user_id: int) -> str:
    require_manager(created_by_user_id)
    if role not in ("manager", "staff"):
        raise ServiceError("Invalid role.")

    temp_password = generate_temp_password()
    password_hash, salt = hash_new_password(temp_password)

    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise ServiceError("A user with that username already exists.")

        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, active, must_change_password) "
            "VALUES (?, ?, ?, ?, 1, 1)",
            (username, password_hash, salt, role),
        )
        log_action(conn, created_by_user_id, "STAFF_ACCOUNT_CREATED", f"username={username} role={role}")
        conn.commit()
        return temp_password
    finally:
        conn.close()


def deactivate_staff(user_id: int, by_user_id: int) -> None:
    require_manager(by_user_id)
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET active = 0 WHERE id = ?", (user_id,))
        log_action(conn, by_user_id, "STAFF_ACCOUNT_DEACTIVATED", f"user_id={user_id}")
        conn.commit()
    finally:
        conn.close()


def reactivate_staff(user_id: int, by_user_id: int) -> None:
    require_manager(by_user_id)
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET active = 1 WHERE id = ?", (user_id,))
        log_action(conn, by_user_id, "STAFF_ACCOUNT_REACTIVATED", f"user_id={user_id}")
        conn.commit()
    finally:
        conn.close()


def reset_staff_password(user_id: int, by_user_id: int) -> str:
    require_manager(by_user_id)
    temp_password = generate_temp_password()
    password_hash, salt = hash_new_password(temp_password)
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ?, must_change_password = 1 WHERE id = ?",
            (password_hash, salt, user_id),
        )
        log_action(conn, by_user_id, "STAFF_PASSWORD_RESET", f"user_id={user_id}")
        conn.commit()
        return temp_password
    finally:
        conn.close()


# ============================================================
# MENU MANAGEMENT (manager only) — lets a manager add a seasonal item
# (e.g. a Valentine's package, Christmas cookies) or a whole new category
# straight from the dashboard, with no code change or redeploy needed.
# Nothing here is ever hard-deleted: "removing" an item/variant/category
# just deactivates it, so historical sales keep resolving correctly.
# ============================================================

def list_categories_admin() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, colour_hex, sort_order FROM categories ORDER BY sort_order, name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_menu_items_admin(category_id: Optional[int] = None) -> list[dict]:
    """All menu items (active AND inactive) with their variants, for the
    management table — unlike get_menu_tree(), which only returns what the
    till should show customers."""
    conn = get_connection()
    try:
        sql = (
            "SELECT mi.id, mi.name, mi.active, mi.has_variants, mi.base_photo_url, "
            "c.id AS category_id, c.name AS category_name "
            "FROM menu_items mi JOIN categories c ON c.id = mi.category_id"
        )
        params: tuple = ()
        if category_id is not None:
            sql += " WHERE mi.category_id = ?"
            params = (category_id,)
        sql += " ORDER BY c.sort_order, mi.name"
        items = conn.execute(sql, params).fetchall()

        result = []
        for item in items:
            variants = conn.execute(
                "SELECT id, variant_label, price, active FROM item_variants "
                "WHERE menu_item_id = ? ORDER BY price",
                (item["id"],),
            ).fetchall()
            row = dict(item)
            row["variants"] = [dict(v) for v in variants]
            result.append(row)
        return result
    finally:
        conn.close()


def create_category(name: str, colour_hex: str, sort_order: int, created_by_user_id: int) -> int:
    require_manager(created_by_user_id)
    if not name.strip():
        raise ServiceError("Category name is required.")
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
        if existing:
            raise ServiceError("A category with that name already exists.")
        cur = conn.execute(
            "INSERT INTO categories (name, colour_hex, sort_order) VALUES (?, ?, ?)",
            (name.strip(), colour_hex, sort_order),
        )
        category_id = cur.lastrowid
        log_action(conn, created_by_user_id, "CATEGORY_CREATED", f"name={name} colour={colour_hex}")
        conn.commit()
        return category_id
    finally:
        conn.close()


def create_menu_item(
    category_id: int,
    name: str,
    has_variants: bool,
    created_by_user_id: int,
    photo_bytes: Optional[bytes] = None,
    photo_content_type: Optional[str] = None,
) -> int:
    require_manager(created_by_user_id)
    if not name.strip():
        raise ServiceError("Item name is required.")

    conn = get_connection()
    try:
        category = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
        if category is None:
            raise ServiceError("Category not found.")

        existing = conn.execute(
            "SELECT id FROM menu_items WHERE category_id = ? AND name = ?", (category_id, name)
        ).fetchone()
        if existing:
            raise ServiceError("An item with that name already exists in this category.")

        # Photo comes later: create the row first (need its id for the photo
        # URL), then attach the photo/URL in a second update.
        cur = conn.execute(
            "INSERT INTO menu_items (category_id, name, has_variants, base_photo_url) "
            "VALUES (?, ?, ?, ?)",
            (category_id, name.strip(), 1 if has_variants else 0,
             CATEGORY_FALLBACK_PHOTOS.get(category["name"], "cakes.svg")),
        )
        item_id = cur.lastrowid

        if photo_bytes:
            photo_url = f"{PUBLIC_BACKEND_URL}/photos/{item_id}"
            conn.execute(
                "UPDATE menu_items SET photo_blob = ?, photo_content_type = ?, base_photo_url = ? "
                "WHERE id = ?",
                (photo_bytes, photo_content_type, photo_url, item_id),
            )

        log_action(conn, created_by_user_id, "MENU_ITEM_CREATED",
                   f"item={name} category={category['name']} photo={'uploaded' if photo_bytes else 'default'}")
        conn.commit()
        return item_id
    finally:
        conn.close()


def get_item_photo(item_id: int) -> Optional[tuple[bytes, str]]:
    """Returns (bytes, content_type) for a manager-uploaded photo, or None
    if this item has no uploaded photo (e.g. it uses a bundled/static one)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT photo_blob, photo_content_type FROM menu_items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None or row["photo_blob"] is None:
            return None
        return bytes(row["photo_blob"]), row["photo_content_type"] or "image/jpeg"
    finally:
        conn.close()


def create_item_variant(menu_item_id: int, variant_label: str, price: float, created_by_user_id: int) -> int:
    require_manager(created_by_user_id)
    if not variant_label.strip():
        raise ServiceError("Variant label is required.")
    if price < 0:
        raise ServiceError("Price cannot be negative.")

    conn = get_connection()
    try:
        item = conn.execute("SELECT name FROM menu_items WHERE id = ?", (menu_item_id,)).fetchone()
        if item is None:
            raise ServiceError("Menu item not found.")

        existing = conn.execute(
            "SELECT id FROM item_variants WHERE menu_item_id = ? AND variant_label = ?",
            (menu_item_id, variant_label),
        ).fetchone()
        if existing:
            raise ServiceError("A variant with that label already exists for this item.")

        cur = conn.execute(
            "INSERT INTO item_variants (menu_item_id, variant_label, price) VALUES (?, ?, ?)",
            (menu_item_id, variant_label.strip(), price),
        )
        variant_id = cur.lastrowid
        log_action(conn, created_by_user_id, "VARIANT_CREATED",
                   f"item={item['name']} label={variant_label} price={price}")
        conn.commit()
        return variant_id
    finally:
        conn.close()


def update_variant_price(variant_id: int, new_price: float, by_user_id: int) -> None:
    require_manager(by_user_id)
    if new_price < 0:
        raise ServiceError("Price cannot be negative.")
    conn = get_connection()
    try:
        conn.execute("UPDATE item_variants SET price = ? WHERE id = ?", (new_price, variant_id))
        log_action(conn, by_user_id, "VARIANT_PRICE_UPDATED", f"variant={variant_id} new_price={new_price}")
        conn.commit()
    finally:
        conn.close()


def set_menu_item_active(item_id: int, active: bool, by_user_id: int) -> None:
    require_manager(by_user_id)
    conn = get_connection()
    try:
        conn.execute("UPDATE menu_items SET active = ? WHERE id = ?", (1 if active else 0, item_id))
        log_action(conn, by_user_id, "MENU_ITEM_ACTIVE_CHANGED", f"item={item_id} active={active}")
        conn.commit()
    finally:
        conn.close()


def set_item_variant_active(variant_id: int, active: bool, by_user_id: int) -> None:
    require_manager(by_user_id)
    conn = get_connection()
    try:
        conn.execute("UPDATE item_variants SET active = ? WHERE id = ?", (1 if active else 0, variant_id))
        log_action(conn, by_user_id, "VARIANT_ACTIVE_CHANGED", f"variant={variant_id} active={active}")
        conn.commit()
    finally:
        conn.close()

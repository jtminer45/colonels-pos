"""
Shared business logic for Colonel's Bakery and Restaurant POS.

This module is imported by BOTH the FastAPI till backend and the Streamlit
manager dashboard, so a sale recorded from the till and a manual stock
adjustment made from the dashboard go through the exact same code paths,
constraints, and audit logging — there is no separate "sync" step because
both surfaces read and write the same SQLite database via these functions.
"""

from dataclasses import dataclass, field
from typing import Optional

from db import get_connection, now_iso, today_str, VAT_RATE
from auth import require_role, require_manager, hash_new_password, generate_temp_password
from audit import log_action


class ServiceError(Exception):
    """Raised for business-rule violations (insufficient stock, bad input, etc.)."""


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

    return row["opening_count"] - sold - wasted


def initialize_inventory_for_date(date: str, opening_counts: dict[int, int]) -> None:
    """Sets today's opening counts. opening_counts maps item_variant_id -> count.
    Existing rows for the date are left untouched (idempotent / additive)."""
    conn = get_connection()
    try:
        for item_variant_id, count in opening_counts.items():
            conn.execute(
                "INSERT OR IGNORE INTO inventory_daily (date, item_variant_id, opening_count) "
                "VALUES (?, ?, ?)",
                (date, item_variant_id, count),
            )
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
    if payment_method not in ("cash", "card"):
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
# PURCHASES & WASTAGE
# ============================================================

def record_purchase(ingredient_id: int, supplier_name: str, quantity: float,
                     cost: float, date: str, user_id: int) -> int:
    if quantity <= 0 or cost < 0:
        raise ServiceError("Quantity must be positive and cost cannot be negative.")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO purchases (ingredient_id, supplier_name, quantity, cost, date, logged_by_user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ingredient_id, supplier_name, quantity, cost, date, user_id),
        )
        conn.execute(
            "UPDATE ingredients SET current_stock = current_stock + ? WHERE id = ?",
            (quantity, ingredient_id),
        )
        log_action(conn, user_id, "PURCHASE_LOGGED",
                   f"ingredient={ingredient_id} qty={quantity} cost={cost} supplier={supplier_name}")
        conn.commit()
        return cur.lastrowid
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
        log_action(conn, user_id, "WASTAGE_LOGGED",
                   f"variant={item_variant_id} qty={quantity} value_lost={value_lost} reason={reason}")
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ============================================================
# RECONCILIATION
# ============================================================

def record_reconciliation(date: str, staff_user_id: int, counted_cash_total: float,
                           notes: str, logged_by_user_id: int) -> dict:
    conn = get_connection()
    try:
        system_cash_total = conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS t FROM sales "
            "WHERE payment_method = 'cash' AND date(timestamp) = ? AND staff_user_id = ?",
            (date, staff_user_id),
        ).fetchone()["t"]

        discrepancy = round(counted_cash_total - system_cash_total, 2)

        conn.execute(
            "INSERT INTO reconciliation (date, staff_user_id, system_cash_total, "
            "counted_cash_total, discrepancy_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (date, staff_user_id, system_cash_total, counted_cash_total, discrepancy, notes),
        )
        if abs(discrepancy) > 0.01:
            log_action(conn, logged_by_user_id, "RECONCILIATION_MISMATCH",
                       f"date={date} staff={staff_user_id} discrepancy={discrepancy}")
        conn.commit()
        return {
            "system_cash_total": system_cash_total,
            "counted_cash_total": counted_cash_total,
            "discrepancy_amount": discrepancy,
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

"""Read-only aggregate queries shared across dashboard pages. Kept separate
from database/services.py because these are reporting queries (pandas
DataFrames for Plotly) rather than transactional writes used by the till.
"""

from datetime import timedelta

import pandas as pd

from db import get_connection, now_local


def _df(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


# ---------------------------------------------------------------
# Snapshot (today)
# ---------------------------------------------------------------

def todays_totals(date: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS revenue, COALESCE(SUM(vat_amount), 0) AS vat, "
            "COALESCE(SUM(CASE WHEN payment_method='cash' THEN total ELSE 0 END), 0) AS cash, "
            "COALESCE(SUM(CASE WHEN payment_method='card' THEN total ELSE 0 END), 0) AS card, "
            "COALESCE(SUM(CASE WHEN payment_method='transfer' THEN total ELSE 0 END), 0) AS transfer, "
            "COUNT(*) AS sale_count "
            "FROM sales WHERE date(timestamp) = ?",
            (date,),
        ).fetchone()

        # Naira prices move day to day, so "ingredient cost" uses the MOST
        # RECENT restock price per ingredient (from the expenses log), not a
        # lifetime average — a bag of flour bought 3 months ago at a lower
        # price shouldn't water down today's estimate.
        ingredient_cost = conn.execute(
            "SELECT COALESCE(SUM(si.quantity * r.quantity_used * "
            "  (SELECT e.total_cost / NULLIF(e.quantity, 0) FROM expenses e "
            "   WHERE e.ingredient_id = r.ingredient_id AND e.category = 'ingredients' "
            "   ORDER BY e.date DESC, e.id DESC LIMIT 1)), 0) AS cost "
            "FROM sale_items si "
            "JOIN sales s ON s.id = si.sale_id "
            "JOIN recipes r ON r.item_variant_id = si.item_variant_id "
            "WHERE si.is_voided = 0 AND date(s.timestamp) = ?",
            (date,),
        ).fetchone()["cost"] or 0

        wastage_value = conn.execute(
            "SELECT COALESCE(SUM(value_lost), 0) AS v FROM wastage WHERE date = ?", (date,)
        ).fetchone()["v"]

        return {
            "revenue": row["revenue"],
            "vat": row["vat"],
            "cash": row["cash"],
            "card": row["card"],
            "transfer": row["transfer"],
            "sale_count": row["sale_count"],
            "ingredient_cost": ingredient_cost,
            "wastage_value": wastage_value,
            "estimated_profit": row["revenue"] - row["vat"] - ingredient_cost - wastage_value,
        }
    finally:
        conn.close()


def payment_method_breakdown(start_date: str, end_date: str) -> pd.DataFrame:
    """Transaction count + total per payment method (cash/card/transfer) for
    a date range — used for both a single day and a full month view."""
    return _df(
        """
        SELECT payment_method, COUNT(*) AS transaction_count, COALESCE(SUM(total), 0) AS total_amount
        FROM sales
        WHERE date(timestamp) BETWEEN ? AND ?
        GROUP BY payment_method
        ORDER BY payment_method
        """,
        (start_date, end_date),
    )


def reconciliation_mismatches(date: str) -> pd.DataFrame:
    return _df(
        "SELECT r.*, u.username FROM reconciliation r JOIN users u ON u.id = r.staff_user_id "
        "WHERE r.date = ? AND ABS(r.discrepancy_amount) > 0.01 ORDER BY r.created_at DESC",
        (date,),
    )


def low_stock_ingredients() -> pd.DataFrame:
    return _df(
        "SELECT name, unit, current_stock, reorder_threshold FROM ingredients "
        "WHERE current_stock <= reorder_threshold ORDER BY (current_stock - reorder_threshold)"
    )


def sold_out_today(date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT * FROM (
            SELECT mi.name AS item_name, iv.variant_label,
                   idl.opening_count,
                   COALESCE(sold.qty, 0) AS sold,
                   COALESCE(wasted.qty, 0) AS wasted,
                   idl.opening_count - COALESCE(sold.qty, 0) - COALESCE(wasted.qty, 0) AS available
            FROM inventory_daily idl
            JOIN item_variants iv ON iv.id = idl.item_variant_id
            JOIN menu_items mi ON mi.id = iv.menu_item_id
            LEFT JOIN (
                SELECT si.item_variant_id, SUM(si.quantity) AS qty
                FROM sale_items si JOIN sales s ON s.id = si.sale_id
                WHERE si.is_voided = 0 AND date(s.timestamp) = ?
                GROUP BY si.item_variant_id
            ) sold ON sold.item_variant_id = idl.item_variant_id
            LEFT JOIN (
                SELECT item_variant_id, SUM(quantity) AS qty FROM wastage WHERE date = ?
                GROUP BY item_variant_id
            ) wasted ON wasted.item_variant_id = idl.item_variant_id
            WHERE idl.date = ?
        ) sub
        WHERE available <= 0
        ORDER BY item_name
        """,
        (date, date, date),
    )


# ---------------------------------------------------------------
# Sales analytics
# ---------------------------------------------------------------

def sales_by_item(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT mi.name AS item_name, iv.variant_label, c.name AS category,
               SUM(si.quantity) AS units_sold,
               SUM(si.quantity * si.unit_price) AS revenue
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN item_variants iv ON iv.id = si.item_variant_id
        JOIN menu_items mi ON mi.id = iv.menu_item_id
        JOIN categories c ON c.id = mi.category_id
        WHERE si.is_voided = 0 AND date(s.timestamp) BETWEEN ? AND ?
        GROUP BY mi.name, iv.variant_label, c.name
        ORDER BY revenue DESC
        """,
        (start_date, end_date),
    )


def sales_by_category(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT c.name AS category, SUM(si.quantity * si.unit_price) AS revenue
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN item_variants iv ON iv.id = si.item_variant_id
        JOIN menu_items mi ON mi.id = iv.menu_item_id
        JOIN categories c ON c.id = mi.category_id
        WHERE si.is_voided = 0 AND date(s.timestamp) BETWEEN ? AND ?
        GROUP BY c.name ORDER BY revenue DESC
        """,
        (start_date, end_date),
    )


def sales_by_staff(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT u.username, COUNT(DISTINCT s.id) AS sale_count, SUM(s.total) AS revenue
        FROM sales s JOIN users u ON u.id = s.staff_user_id
        WHERE date(s.timestamp) BETWEEN ? AND ?
        GROUP BY u.username ORDER BY revenue DESC
        """,
        (start_date, end_date),
    )


def sales_by_hour(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT strftime('%H', timestamp) AS hour, SUM(total) AS revenue, COUNT(*) AS sale_count
        FROM sales WHERE date(timestamp) BETWEEN ? AND ?
        GROUP BY hour ORDER BY hour
        """,
        (start_date, end_date),
    )


def sales_over_time(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT date(timestamp) AS day, SUM(total) AS revenue
        FROM sales WHERE date(timestamp) BETWEEN ? AND ?
        GROUP BY day ORDER BY day
        """,
        (start_date, end_date),
    )


# ---------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------

def sold_quantity_for_variant(item_variant_id: int, date: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(si.quantity), 0) AS qty FROM sale_items si "
            "JOIN sales s ON s.id = si.sale_id "
            "WHERE si.item_variant_id = ? AND si.is_voided = 0 AND date(s.timestamp) = ?",
            (item_variant_id, date),
        ).fetchone()
        return row["qty"]
    finally:
        conn.close()


def ingredient_usage_rate(days: int = 7) -> pd.DataFrame:
    """Average daily consumption per ingredient over the trailing `days`,
    used to predict days-until-empty."""
    cutoff = (now_local().date() - timedelta(days=days)).isoformat()
    return _df(
        """
        SELECT i.id, i.name, i.unit, i.current_stock, i.reorder_threshold,
               COALESCE(SUM(si.quantity * r.quantity_used), 0) / ? AS avg_daily_usage
        FROM ingredients i
        LEFT JOIN recipes r ON r.ingredient_id = i.id
        LEFT JOIN sale_items si ON si.item_variant_id = r.item_variant_id AND si.is_voided = 0
        LEFT JOIN sales s ON s.id = si.sale_id AND date(s.timestamp) >= ?
        GROUP BY i.id
        ORDER BY i.name
        """,
        (days, cutoff),
    )


def wastage_log(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT w.date, mi.name AS item_name, iv.variant_label, w.quantity, w.reason,
               w.value_lost, u.username AS logged_by
        FROM wastage w
        JOIN item_variants iv ON iv.id = w.item_variant_id
        JOIN menu_items mi ON mi.id = iv.menu_item_id
        JOIN users u ON u.id = w.logged_by_user_id
        WHERE w.date BETWEEN ? AND ?
        ORDER BY w.date DESC
        """,
        (start_date, end_date),
    )


# ---------------------------------------------------------------
# Costs & expenses
# ---------------------------------------------------------------

def latest_ingredient_prices() -> pd.DataFrame:
    """Most recent restock price per ingredient — a quick reference for
    what was last paid, since Naira prices can move day to day."""
    return _df(
        """
        SELECT i.name AS ingredient, i.unit, e.total_cost AS cost, e.quantity,
               ROUND(e.total_cost / NULLIF(e.quantity, 0), 2) AS price_per_unit,
               e.date AS last_purchased
        FROM ingredients i
        LEFT JOIN expenses e ON e.id = (
            SELECT id FROM expenses
            WHERE ingredient_id = i.id AND category = 'ingredients'
            ORDER BY date DESC, id DESC LIMIT 1
        )
        ORDER BY i.name
        """
    )


def expenses_log(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT e.date, e.item_name, e.category, e.quantity, e.unit, e.total_cost,
               e.payment_method, e.supplier_or_payee, u.username AS logged_by
        FROM expenses e JOIN users u ON u.id = e.logged_by_user_id
        WHERE e.date BETWEEN ? AND ?
        ORDER BY e.date DESC, e.logged_at DESC
        """,
        (start_date, end_date),
    )


def profit_summary(start_date: str, end_date: str) -> dict:
    conn = get_connection()
    try:
        revenue = conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS r, COALESCE(SUM(vat_amount), 0) AS vat "
            "FROM sales WHERE date(timestamp) BETWEEN ? AND ?",
            (start_date, end_date),
        ).fetchone()
        expense_cost = conn.execute(
            "SELECT COALESCE(SUM(total_cost), 0) AS c FROM expenses WHERE date BETWEEN ? AND ?",
            (start_date, end_date),
        ).fetchone()["c"]
        wastage_cost = conn.execute(
            "SELECT COALESCE(SUM(value_lost), 0) AS v FROM wastage WHERE date BETWEEN ? AND ?",
            (start_date, end_date),
        ).fetchone()["v"]
        return {
            "revenue": revenue["r"],
            "vat_collected": revenue["vat"],
            "total_expenses": expense_cost,
            "wastage_cost": wastage_cost,
            "estimated_profit": revenue["r"] - revenue["vat"] - expense_cost - wastage_cost,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------

def reconciliation_history(start_date: str, end_date: str) -> pd.DataFrame:
    return _df(
        """
        SELECT r.date, u.username AS staff, r.system_cash_total, r.cash_expenses_total,
               r.counted_cash_total, r.discrepancy_amount, r.notes, r.created_at
        FROM reconciliation r JOIN users u ON u.id = r.staff_user_id
        WHERE r.date BETWEEN ? AND ?
        ORDER BY r.date DESC, r.created_at DESC
        """,
        (start_date, end_date),
    )


# ---------------------------------------------------------------
# Staff
# ---------------------------------------------------------------

def all_staff() -> pd.DataFrame:
    return _df(
        "SELECT id, username, role, active, must_change_password, created_at FROM users ORDER BY active DESC, username"
    )


def staff_login_history(user_id: int, limit: int = 50) -> pd.DataFrame:
    return _df(
        "SELECT login_at, logout_at FROM sessions WHERE user_id = ? ORDER BY login_at DESC LIMIT ?",
        (user_id, limit),
    )


def staff_sales_performance(user_id: int, start_date: str, end_date: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS sale_count, COALESCE(SUM(total), 0) AS revenue "
            "FROM sales WHERE staff_user_id = ? AND date(timestamp) BETWEEN ? AND ?",
            (user_id, start_date, end_date),
        ).fetchone()
        voids = conn.execute(
            "SELECT COUNT(*) AS c FROM sale_items WHERE voided_by = ? "
            "AND date(voided_at) BETWEEN ? AND ?",
            (user_id, start_date, end_date),
        ).fetchone()["c"]
        return {"sale_count": row["sale_count"], "revenue": row["revenue"], "voids_made": voids}
    finally:
        conn.close()


# ---------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------

def audit_log(start_date: str, end_date: str, action_type: str | None = None) -> pd.DataFrame:
    sql = (
        "SELECT a.timestamp, u.username, a.action_type, a.details "
        "FROM audit_log a JOIN users u ON u.id = a.user_id "
        "WHERE date(a.timestamp) BETWEEN ? AND ?"
    )
    params = [start_date, end_date]
    if action_type:
        sql += " AND a.action_type = ?"
        params.append(action_type)
    sql += " ORDER BY a.timestamp DESC"
    return _df(sql, tuple(params))


def distinct_action_types() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT DISTINCT action_type FROM audit_log ORDER BY action_type").fetchall()
        return [r["action_type"] for r in rows]
    finally:
        conn.close()

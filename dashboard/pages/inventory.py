from datetime import date, timedelta

import streamlit as st

from db import get_connection, today_str
import queries
import services
from session import current_user

st.title("📦 Inventory")
user = current_user()

tab_stock, tab_wastage, tab_daily = st.tabs(["Ingredient Stock", "Wastage Log", "Today's Item Counts"])

with tab_stock:
    st.subheader("Current Ingredient Stock")
    usage = queries.ingredient_usage_rate(days=7)

    def days_until_empty(row):
        if row["avg_daily_usage"] <= 0:
            return None
        return round(row["current_stock"] / row["avg_daily_usage"], 1)

    usage["days_until_empty"] = usage.apply(days_until_empty, axis=1)
    usage["low_stock"] = usage["current_stock"] <= usage["reorder_threshold"]

    display = usage.rename(columns={
        "name": "Ingredient", "unit": "Unit", "current_stock": "Current Stock",
        "reorder_threshold": "Reorder Threshold", "avg_daily_usage": "Avg Daily Usage (7d)",
        "days_until_empty": "Days Until Empty",
    })
    st.dataframe(
        display[["Ingredient", "Unit", "Current Stock", "Reorder Threshold", "Avg Daily Usage (7d)", "Days Until Empty", "low_stock"]],
        width="stretch", hide_index=True,
        column_config={"low_stock": st.column_config.CheckboxColumn("Low Stock?", disabled=True)},
    )

    low = usage[usage["low_stock"]]
    if not low.empty:
        st.error(f"⚠️ {len(low)} ingredient(s) at or below reorder threshold — log a purchase on the Costs & Purchases page.")

with tab_wastage:
    st.subheader("Log Wastage")
    conn = get_connection()
    variants = conn.execute(
        "SELECT iv.id, mi.name || ' — ' || iv.variant_label AS label, iv.price "
        "FROM item_variants iv JOIN menu_items mi ON mi.id = iv.menu_item_id "
        "WHERE iv.active = 1 ORDER BY mi.name"
    ).fetchall()
    conn.close()
    variant_options = {v["label"]: (v["id"], v["price"]) for v in variants}

    with st.form("wastage_form"):
        col1, col2, col3 = st.columns(3)
        variant_label = col1.selectbox("Item", options=list(variant_options.keys()))
        quantity = col2.number_input("Quantity", min_value=1, step=1, value=1)
        reason = col3.text_input("Reason", placeholder="e.g. dropped, expired, burnt")
        submitted = st.form_submit_button("Log Wastage", type="primary")

    if submitted:
        if not reason.strip():
            st.error("A reason is required.")
        else:
            variant_id, price = variant_options[variant_label]
            value_lost = price * quantity
            services.record_wastage(variant_id, quantity, reason, value_lost, today_str(), user["id"])
            st.success(f"Logged wastage of {quantity} × {variant_label} (₦{value_lost:,.0f} lost).")
            st.rerun()

    st.divider()
    st.subheader("Wastage History")
    c1, c2 = st.columns(2)
    start = c1.date_input("From", value=date.today() - timedelta(days=13), key="waste_start")
    end = c2.date_input("To", value=date.today(), key="waste_end")
    log = queries.wastage_log(start.isoformat(), end.isoformat())
    if log.empty:
        st.info("No wastage logged in this range.")
    else:
        st.metric("Total Value Lost", f"₦{log['value_lost'].sum():,.0f}")
        st.dataframe(log, width="stretch", hide_index=True)

with tab_daily:
    st.subheader(f"Opening / Closing Counts — {today_str()}")
    st.caption(
        "Opening count is what the till checks against to show 'Sold Out'. "
        "Closing count is entered at end of day and compared to the system-computed "
        "remaining count to flag inventory mismatches."
    )
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT idl.id AS inv_id, mi.name AS item_name, iv.variant_label, idl.item_variant_id,
               idl.opening_count, idl.closing_count
        FROM inventory_daily idl
        JOIN item_variants iv ON iv.id = idl.item_variant_id
        JOIN menu_items mi ON mi.id = iv.menu_item_id
        WHERE idl.date = %s
        ORDER BY mi.name, iv.variant_label
        """,
        (today_str(),),
    ).fetchall()
    conn.close()

    for row in rows:
        sold = queries.sold_quantity_for_variant(row["item_variant_id"], today_str())
        expected_remaining = row["opening_count"] - sold

        with st.expander(f"{row['item_name']} — {row['variant_label']} (opening: {row['opening_count']}, sold: {sold}, expected remaining: {expected_remaining})"):
            new_closing = st.number_input(
                "Closing count", min_value=0, step=1,
                value=int(row["closing_count"]) if row["closing_count"] is not None else int(expected_remaining),
                key=f"closing_{row['inv_id']}",
            )
            if st.button("Save Closing Count", key=f"save_{row['inv_id']}"):
                services.set_closing_count(today_str(), row["item_variant_id"], new_closing, user["id"])
                mismatch = new_closing - expected_remaining
                if mismatch != 0:
                    st.warning(f"Mismatch of {mismatch:+d} vs. expected — recorded in audit log.")
                else:
                    st.success("Closing count matches expected remaining stock.")
                st.rerun()

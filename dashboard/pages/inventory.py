from datetime import timedelta

import pandas as pd
import streamlit as st

from db import get_connection, today_str, now_local
import queries
import services
from session import require_user

st.title("📦 Inventory")
user = require_user()

tab_daily, tab_stock, tab_wastage = st.tabs(["Today's Available Counts", "Ingredient Stock", "Wastage Log"])

with tab_daily:
    st.subheader(f"How many of each item are available today — {today_str()}")
    st.caption(
        "This is what the till checks — once an item's available count reaches 0, it shows 'Sold Out' "
        "automatically, no need to tell whoever's on the till. Change a count any time during the day "
        "(kitchen made more, or something just ran out) — it takes effect immediately."
    )

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT idl.id AS inv_id, mi.name AS item_name, iv.variant_label, idl.item_variant_id,
               idl.opening_count, idl.closing_count, c.name AS category_name
        FROM inventory_daily idl
        JOIN item_variants iv ON iv.id = idl.item_variant_id
        JOIN menu_items mi ON mi.id = iv.menu_item_id
        JOIN categories c ON c.id = mi.category_id
        WHERE idl.date = %s
        ORDER BY c.sort_order, mi.name, iv.variant_label
        """,
        (today_str(),),
    ).fetchall()
    conn.close()

    table_rows = []
    for row in rows:
        sold = queries.sold_quantity_for_variant(row["item_variant_id"], today_str())
        available = row["opening_count"] - sold
        table_rows.append({
            "item_variant_id": row["item_variant_id"],
            "Category": row["category_name"],
            "Item": row["item_name"],
            "Variant": row["variant_label"],
            "Available Today": row["opening_count"],
            "Sold So Far": sold,
            "Remaining": available,
        })
    df = pd.DataFrame(table_rows)

    if df.empty:
        st.info("No items are stock-tracked for today yet.")
    else:
        edited = st.data_editor(
            df,
            width="stretch",
            hide_index=True,
            disabled=["item_variant_id", "Category", "Item", "Variant", "Sold So Far", "Remaining"],
            column_config={
                "item_variant_id": None,
                "Available Today": st.column_config.NumberColumn(min_value=0, step=1, help="How many are available to sell today — edit and save."),
            },
            key="opening_count_editor",
        )

        sold_out_now = df[df["Remaining"] <= 0]
        if not sold_out_now.empty:
            st.warning(f"Currently showing 'Sold Out' on the till: {', '.join(sold_out_now['Item'] + ' (' + sold_out_now['Variant'] + ')')}")

        if st.button("Save Changes", type="primary"):
            changed = 0
            for _, orig_row in df.iterrows():
                new_row = edited[edited["item_variant_id"] == orig_row["item_variant_id"]].iloc[0]
                if int(new_row["Available Today"]) != int(orig_row["Available Today"]):
                    services.set_opening_count(
                        today_str(), int(orig_row["item_variant_id"]), int(new_row["Available Today"]), user["id"]
                    )
                    changed += 1
            if changed:
                st.success(f"Updated {changed} item(s). The till reflects this within its next background refresh (≤30s).")
                st.rerun()
            else:
                st.info("No changes to save.")

    st.divider()
    st.subheader("End-of-Day Closing Counts")
    st.caption(
        "Optional: count what's physically left at close and enter it here — if it doesn't match the "
        "system's expected remaining count, the mismatch is flagged and logged for the audit trail."
    )
    for row in rows:
        sold = queries.sold_quantity_for_variant(row["item_variant_id"], today_str())
        expected_remaining = row["opening_count"] - sold
        with st.expander(f"{row['item_name']} — {row['variant_label']} (expected remaining: {expected_remaining})"):
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
    today_local = now_local().date()  # Lagos time — see sales_analytics.py
    c1, c2 = st.columns(2)
    start = c1.date_input("From", value=today_local - timedelta(days=13), key="waste_start")
    end = c2.date_input("To", value=today_local, key="waste_end")
    log = queries.wastage_log(start.isoformat(), end.isoformat())
    if log.empty:
        st.info("No wastage logged in this range.")
    else:
        st.metric("Total Value Lost", f"₦{log['value_lost'].sum():,.0f}")
        st.dataframe(log, width="stretch", hide_index=True)

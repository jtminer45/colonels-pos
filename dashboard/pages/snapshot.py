import streamlit as st

from db import today_str
import queries

st.title("📊 Today's Snapshot")
date = today_str()
st.caption(f"Live figures for {date}. This page reflects sales as they happen — no refresh step needed.")

totals = queries.todays_totals(date)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"₦{totals['revenue']:,.0f}")
c2.metric("VAT Collected (7.5%)", f"₦{totals['vat']:,.0f}")
c3.metric("Estimated Profit", f"₦{totals['estimated_profit']:,.0f}")
c4.metric("Sales Count", f"{totals['sale_count']:,}")

c5, c6 = st.columns(2)
c5.metric("Cash Sales", f"₦{totals['cash']:,.0f}")
c6.metric("Card Sales", f"₦{totals['card']:,.0f}")

st.caption(
    "Estimated profit = revenue − VAT − estimated ingredient cost of items sold − wastage value. "
    "Ingredient cost uses the average purchase price logged so far for each ingredient."
)

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("⚠️ Reconciliation Mismatches Today")
    mismatches = queries.reconciliation_mismatches(date)
    if mismatches.empty:
        st.success("No cash discrepancies recorded today.")
    else:
        st.error(f"{len(mismatches)} mismatch(es) found — see Reconciliation page for details.")
        st.dataframe(
            mismatches[["username", "system_cash_total", "counted_cash_total", "discrepancy_amount", "notes"]],
            width="stretch", hide_index=True,
        )

with col_b:
    st.subheader("📦 Low Stock / Sold Out")
    low_stock = queries.low_stock_ingredients()
    sold_out = queries.sold_out_today(date)

    if low_stock.empty and sold_out.empty:
        st.success("Everything is adequately stocked.")
    else:
        if not low_stock.empty:
            st.error(f"{len(low_stock)} ingredient(s) at or below reorder threshold:")
            st.dataframe(low_stock, width="stretch", hide_index=True)
        if not sold_out.empty:
            st.warning(f"{len(sold_out)} menu item(s) sold out today:")
            st.dataframe(
                sold_out[["item_name", "variant_label", "opening_count", "sold", "wasted"]],
                width="stretch", hide_index=True,
            )

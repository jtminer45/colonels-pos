import streamlit as st

from db import today_str, now_local
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

c5, c6, c7 = st.columns(3)
c5.metric("Cash", f"₦{totals['cash']:,.0f}")
c6.metric("POS", f"₦{totals['card']:,.0f}")
c7.metric("Transfer", f"₦{totals['transfer']:,.0f}")

st.caption(
    "Estimated profit = revenue − VAT − estimated ingredient cost of items sold − wastage value. "
    "Ingredient cost uses the average purchase price logged so far for each ingredient."
)

st.divider()

st.subheader("💳 Payment Method Breakdown")
pcol1, pcol2 = st.columns(2)

with pcol1:
    st.markdown(f"**Today ({date})**")
    today_breakdown = queries.payment_method_breakdown(date, date)
    if today_breakdown.empty:
        st.info("No sales yet today.")
    else:
        st.dataframe(
            today_breakdown.rename(columns={
                "payment_method": "Method", "transaction_count": "Transactions", "total_amount": "Total (₦)",
            }),
            width="stretch", hide_index=True,
        )

with pcol2:
    month_start = now_local().replace(day=1).strftime("%Y-%m-%d")
    st.markdown(f"**This Month ({month_start} to {date})**")
    month_breakdown = queries.payment_method_breakdown(month_start, date)
    if month_breakdown.empty:
        st.info("No sales yet this month.")
    else:
        st.dataframe(
            month_breakdown.rename(columns={
                "payment_method": "Method", "transaction_count": "Transactions", "total_amount": "Total (₦)",
            }),
            width="stretch", hide_index=True,
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

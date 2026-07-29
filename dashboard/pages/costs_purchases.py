from datetime import timedelta

import streamlit as st

from db import get_connection, today_str, now_local
import queries
import services
from session import require_user

st.title("💰 Costs & Purchases")
user = require_user()

st.subheader("Log a New Purchase")
st.caption(
    "Enter the quantity and the TOTAL you paid — e.g. 25 kg of flour for ₦45,000, not a per-kg price. "
    "Naira prices move day to day, so every purchase is logged with today's date and its own price; "
    "cost estimates elsewhere in the dashboard always use the most recent price, never an old average."
)
conn = get_connection()
ingredients = conn.execute("SELECT id, name, unit FROM ingredients ORDER BY name").fetchall()
conn.close()
ingredient_options = {f"{i['name']} ({i['unit']})": i["id"] for i in ingredients}

with st.form("purchase_form"):
    col1, col2, col3, col4 = st.columns(4)
    ingredient_label = col1.selectbox("Ingredient", options=list(ingredient_options.keys()))
    supplier = col2.text_input("Supplier")
    quantity = col3.number_input("Quantity", min_value=0.0, step=0.5, format="%.2f")
    cost = col4.number_input("Total Cost (₦)", min_value=0.0, step=100.0, format="%.2f")
    submitted = st.form_submit_button("Log Purchase", type="primary")

if submitted:
    if quantity <= 0:
        st.error("Quantity must be greater than zero.")
    else:
        services.record_purchase(
            ingredient_options[ingredient_label], supplier, quantity, cost, today_str(), user["id"]
        )
        per_unit = cost / quantity
        st.success(f"Logged {quantity} of {ingredient_label} for ₦{cost:,.0f} (₦{per_unit:,.2f} per unit).")
        st.rerun()

st.divider()
st.subheader("Most Recent Price Paid — By Ingredient")
latest_prices = queries.latest_ingredient_prices()
st.dataframe(
    latest_prices.rename(columns={
        "ingredient": "Ingredient", "unit": "Unit", "price_per_unit": "Price / Unit (₦)",
        "cost": "Last Total Paid (₦)", "quantity": "Last Quantity", "last_purchased": "Date",
    }),
    width="stretch", hide_index=True,
)

st.divider()

st.subheader("Profit Summary")
today_local = now_local().date()  # Lagos time — see sales_analytics.py
col1, col2 = st.columns(2)
start = col1.date_input("From", value=today_local - timedelta(days=29), key="cost_start")
end = col2.date_input("To", value=today_local, key="cost_end")

summary = queries.profit_summary(start.isoformat(), end.isoformat())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"₦{summary['revenue']:,.0f}")
c2.metric("VAT Collected", f"₦{summary['vat_collected']:,.0f}")
c3.metric("Ingredient Purchases", f"₦{summary['ingredient_purchase_cost']:,.0f}")
c4.metric("Wastage Cost", f"₦{summary['wastage_cost']:,.0f}")
st.metric("Estimated Profit", f"₦{summary['estimated_profit']:,.0f}")
st.caption(
    "Estimated profit = revenue − VAT − ingredient purchases logged − wastage value, for the selected range. "
    "This uses actual purchase spend (not a per-item recipe cost estimate), so it is most accurate over "
    "longer ranges where purchasing has caught up with usage."
)

st.divider()
st.subheader("Purchase History")
log = queries.purchases_log(start.isoformat(), end.isoformat())
if log.empty:
    st.info("No purchases logged in this range.")
else:
    st.dataframe(log, width="stretch", hide_index=True)

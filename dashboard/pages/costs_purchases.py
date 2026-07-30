from datetime import timedelta

import streamlit as st

from db import today_str, now_local
import queries
import services
from session import require_user

st.title("💰 Costs & Expenses")
user = require_user()

PAYMENT_LABELS = {"cash": "Cash", "card": "POS", "transfer": "Transfer"}
CATEGORY_LABELS = {
    "ingredients": "Ingredients", "salary": "Salary", "electricity": "Electricity",
    "water": "Water", "rent": "Rent", "repairs_maintenance": "Repairs / Maintenance", "other": "Other",
}
UNIT_OPTIONS = ["", "kg", "grams", "litre", "units"]

st.subheader("Log an Expense")
st.caption(
    "Write in whatever you spent money on today — no need to pick from a list. If it's an ingredient "
    "restock, add the quantity and unit so stock goes up automatically; leave those blank for things "
    "like salaries, electricity, or repairs. Enter the TOTAL you paid, then how you paid for it."
)

with st.form("expense_form"):
    col1, col2 = st.columns(2)
    item_name = col1.text_input("What did you pay for?", placeholder="e.g. Flour, or Generator repair")
    category = col2.selectbox(
        "Category", options=list(CATEGORY_LABELS.keys()), format_func=lambda k: CATEGORY_LABELS[k]
    )

    col3, col4, col5 = st.columns(3)
    quantity = col3.number_input("Quantity (optional)", min_value=0.0, step=0.5, format="%.2f")
    unit = col4.selectbox("Unit (optional)", options=UNIT_OPTIONS)
    total_cost = col5.number_input("Total Cost (₦)", min_value=0.0, step=100.0, format="%.2f")

    col6, col7 = st.columns(2)
    payment_method = col6.selectbox(
        "Paid with", options=list(PAYMENT_LABELS.keys()), format_func=lambda k: PAYMENT_LABELS[k]
    )
    supplier = col7.text_input("Supplier / Payee (optional)")

    submitted = st.form_submit_button("Log Expense", type="primary")

if submitted:
    try:
        services.record_expense(
            item_name=item_name,
            category=category,
            quantity=quantity if quantity > 0 else None,
            unit=unit if unit else None,
            total_cost=total_cost,
            payment_method=payment_method,
            date=today_str(),
            user_id=user["id"],
            supplier_or_payee=supplier,
        )
        st.success(f"Logged {item_name} — ₦{total_cost:,.0f} ({PAYMENT_LABELS[payment_method]}).")
        st.rerun()
    except services.ServiceError as e:
        st.error(str(e))

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
c3.metric("Total Expenses", f"₦{summary['total_expenses']:,.0f}")
c4.metric("Wastage Cost", f"₦{summary['wastage_cost']:,.0f}")
st.metric("Estimated Profit", f"₦{summary['estimated_profit']:,.0f}")
st.caption(
    "Estimated profit = revenue − VAT − all expenses logged (ingredients, salaries, electricity, water, "
    "rent, repairs, other) − wastage value, for the selected range."
)

st.divider()
st.subheader("Expense History")
log = queries.expenses_log(start.isoformat(), end.isoformat())
if log.empty:
    st.info("No expenses logged in this range.")
else:
    st.dataframe(
        log.rename(columns={
            "date": "Date", "item_name": "Item", "category": "Category", "quantity": "Quantity",
            "unit": "Unit", "total_cost": "Total Cost (₦)", "payment_method": "Paid With",
            "supplier_or_payee": "Supplier / Payee", "logged_by": "Logged By",
        }),
        width="stretch", hide_index=True,
    )

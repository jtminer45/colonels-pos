from datetime import date, timedelta

import streamlit as st
import plotly.express as px

import queries

st.title("📈 Sales Analytics")

col1, col2 = st.columns(2)
start_date = col1.date_input("From", value=date.today() - timedelta(days=6))
end_date = col2.date_input("To", value=date.today())

if start_date > end_date:
    st.error("Start date must be before end date.")
    st.stop()

s, e = start_date.isoformat(), end_date.isoformat()

by_item = queries.sales_by_item(s, e)
by_category = queries.sales_by_category(s, e)
by_staff = queries.sales_by_staff(s, e)
by_hour = queries.sales_by_hour(s, e)
over_time = queries.sales_over_time(s, e)

if by_item.empty:
    st.info("No sales recorded in this date range yet.")
    st.stop()

total_revenue = by_item["revenue"].sum()
total_units = by_item["units_sold"].sum()
c1, c2 = st.columns(2)
c1.metric("Total Revenue", f"₦{total_revenue:,.0f}")
c2.metric("Total Units Sold", f"{total_units:,}")

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Revenue by Category")
    fig = px.pie(by_category, names="category", values="revenue", hole=0.45)
    st.plotly_chart(fig, width="stretch")

with col_b:
    st.subheader("Revenue Over Time")
    fig = px.line(over_time, x="day", y="revenue", markers=True)
    fig.update_layout(yaxis_title="Revenue (₦)", xaxis_title="")
    st.plotly_chart(fig, width="stretch")

st.subheader("Revenue by Hour of Day")
fig = px.bar(by_hour, x="hour", y="revenue")
fig.update_layout(yaxis_title="Revenue (₦)", xaxis_title="Hour")
st.plotly_chart(fig, width="stretch")

st.subheader("Top Items")
top_n = by_item.sort_values("revenue", ascending=False).head(15)
fig = px.bar(
    top_n, x="revenue", y=top_n["item_name"] + " — " + top_n["variant_label"],
    orientation="h", color="category",
)
fig.update_layout(yaxis_title="", xaxis_title="Revenue (₦)", yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, width="stretch")

with st.expander("Full item breakdown"):
    st.dataframe(by_item, width="stretch", hide_index=True)

st.subheader("Sales by Staff Member")
fig = px.bar(by_staff, x="username", y="revenue", text="sale_count")
fig.update_layout(yaxis_title="Revenue (₦)", xaxis_title="")
st.plotly_chart(fig, width="stretch")
st.dataframe(by_staff, width="stretch", hide_index=True)

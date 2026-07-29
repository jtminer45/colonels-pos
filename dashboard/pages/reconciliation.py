from datetime import date, timedelta

import streamlit as st

from db import get_connection, today_str
import queries
import services
from session import current_user

st.title("🧾 Cash Reconciliation")
user = current_user()

st.subheader("Record Today's Cash Count")
conn = get_connection()
staff = conn.execute(
    "SELECT id, username FROM users WHERE active = 1 ORDER BY username"
).fetchall()
conn.close()
staff_options = {s["username"]: s["id"] for s in staff}

with st.form("reconciliation_form"):
    col1, col2 = st.columns(2)
    staff_label = col1.selectbox("Staff / Shift", options=list(staff_options.keys()))
    counted = col2.number_input("Counted Cash Total (₦)", min_value=0.0, step=50.0, format="%.2f")
    notes = st.text_area("Notes (optional)")
    submitted = st.form_submit_button("Record Reconciliation", type="primary")

if submitted:
    result = services.record_reconciliation(
        today_str(), staff_options[staff_label], counted, notes, user["id"]
    )
    if abs(result["discrepancy_amount"]) < 0.01:
        st.success(f"Matches system total of ₦{result['system_cash_total']:,.0f}. No discrepancy.")
    else:
        st.error(
            f"Discrepancy of ₦{result['discrepancy_amount']:,.0f} "
            f"(system expected ₦{result['system_cash_total']:,.0f}, counted ₦{result['counted_cash_total']:,.0f}). "
            f"Logged to the audit trail."
        )
    st.rerun()

st.divider()
st.subheader("Reconciliation History")
col1, col2 = st.columns(2)
start = col1.date_input("From", value=date.today() - timedelta(days=29), key="rec_start")
end = col2.date_input("To", value=date.today(), key="rec_end")

history = queries.reconciliation_history(start.isoformat(), end.isoformat())
if history.empty:
    st.info("No reconciliation records in this range.")
else:
    def highlight_mismatch(row):
        return ["background-color: rgba(255,59,48,0.15)" if abs(row["discrepancy_amount"]) > 0.01 else "" for _ in row]

    st.dataframe(
        history.style.apply(highlight_mismatch, axis=1),
        width="stretch", hide_index=True,
    )
    mismatches = history[history["discrepancy_amount"].abs() > 0.01]
    if not mismatches.empty:
        st.error(f"{len(mismatches)} mismatch(es) in this range, linked to the staff member on shift at the time.")

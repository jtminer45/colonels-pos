from datetime import date, timedelta

import streamlit as st

import queries

st.title("🔍 Audit Log")
st.caption(
    "Every void, manual stock adjustment, purchase, wastage entry, reconciliation mismatch, and "
    "staff-account change is recorded here — who, when, and why. Nothing here is ever silently deleted."
)

col1, col2, col3 = st.columns([1, 1, 2])
start = col1.date_input("From", value=date.today() - timedelta(days=6))
end = col2.date_input("To", value=date.today())
action_types = ["All"] + queries.distinct_action_types()
action_filter = col3.selectbox("Action Type", options=action_types)

log = queries.audit_log(
    start.isoformat(), end.isoformat(),
    action_type=None if action_filter == "All" else action_filter,
)

if log.empty:
    st.info("No audit entries in this range.")
else:
    st.metric("Entries", len(log))
    st.dataframe(
        log.rename(columns={
            "timestamp": "Timestamp", "username": "User", "action_type": "Action", "details": "Details",
        }),
        width="stretch", hide_index=True,
    )

from datetime import date, timedelta

import streamlit as st

import queries
import services
from session import current_user

st.title("👥 Staff Management")
user = current_user()

st.subheader("Create Staff Account")
st.caption(
    "There is no self-registration anywhere in this system — every account is created here by a manager, "
    "with a temporary password the new user must change on first login."
)
with st.form("create_staff_form"):
    col1, col2 = st.columns(2)
    username = col1.text_input("Username")
    role = col2.selectbox("Role", options=["staff", "manager"])
    submitted = st.form_submit_button("Create Account", type="primary")

if submitted:
    if not username.strip():
        st.error("Username is required.")
    else:
        try:
            temp_password = services.create_staff_account(username.strip(), role, user["id"])
            st.success(
                f"Account created for **{username}** ({role}). "
                f"Temporary password: `{temp_password}` — share this securely; it cannot be retrieved again, only reset."
            )
        except services.ServiceError as e:
            st.error(str(e))

st.divider()
st.subheader("All Accounts")
staff_df = queries.all_staff()
st.dataframe(
    staff_df.rename(columns={
        "username": "Username", "role": "Role", "active": "Active",
        "must_change_password": "Must Change Password", "created_at": "Created",
    }),
    width="stretch", hide_index=True,
)

st.divider()
st.subheader("Manage an Individual Account")
staff_options = {f"{row['username']} ({row['role']}, {'active' if row['active'] else 'inactive'})": row["id"]
                  for _, row in staff_df.iterrows()}
if not staff_options:
    st.info("No accounts yet.")
    st.stop()

selected_label = st.selectbox("Select account", options=list(staff_options.keys()))
selected_id = staff_options[selected_label]
selected_row = staff_df[staff_df["id"] == selected_id].iloc[0]

col1, col2, col3 = st.columns(3)

with col1:
    if selected_row["active"]:
        if st.button("Deactivate Account", type="secondary"):
            if selected_id == user["id"]:
                st.error("You cannot deactivate your own account.")
            else:
                services.deactivate_staff(int(selected_id), user["id"])
                st.success("Account deactivated. Their historical sales and audit records are preserved.")
                st.rerun()
    else:
        if st.button("Reactivate Account", type="secondary"):
            services.reactivate_staff(int(selected_id), user["id"])
            st.success("Account reactivated.")
            st.rerun()

with col2:
    if st.button("Reset Password"):
        temp_password = services.reset_staff_password(int(selected_id), user["id"])
        st.success(
            f"Password reset. New temporary password: `{temp_password}` — "
            f"they must change it on next login. The old password no longer works."
        )

with col3:
    st.caption("The real password is never stored or retrievable — only reset.")

st.markdown("#### Sales Performance & Login History")
col1, col2 = st.columns(2)
start = col1.date_input("From", value=date.today() - timedelta(days=29), key="staff_start")
end = col2.date_input("To", value=date.today(), key="staff_end")

perf = queries.staff_sales_performance(int(selected_id), start.isoformat(), end.isoformat())
c1, c2, c3 = st.columns(3)
c1.metric("Sales Made", perf["sale_count"])
c2.metric("Revenue Generated", f"₦{perf['revenue']:,.0f}")
c3.metric("Voids Made", perf["voids_made"])

history = queries.staff_login_history(int(selected_id))
if history.empty:
    st.info("No login history yet.")
else:
    st.dataframe(
        history.rename(columns={"login_at": "Login", "logout_at": "Logout"}),
        width="stretch", hide_index=True,
    )

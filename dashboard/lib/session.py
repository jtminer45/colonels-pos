"""
Login gate for the manager dashboard.

require_login() is called once at the top of app.py, before any page is
rendered. It is the single point that enforces "manager role only" for the
whole dashboard: a staff account can authenticate (username/password are
valid), but is explicitly rejected here and never reaches a page — the
per-page code never has to re-check role for basic page access. Individual
actions that mutate manager-only data (staff creation, password resets)
still call auth.require_manager()/services functions that re-check role
themselves, so the protection is not solely this one gate.
"""

import streamlit as st

import auth as auth_module
from db import get_connection
from theme import sidebar_header


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_user() -> dict:
    """Like current_user(), but for pages that mutate data (they call this
    instead of current_user() directly). On Render's free tier the process
    can restart between page load and a click (idle spin-down, a redeploy),
    which wipes server-side session_state — app.py's require_login() gate
    normally catches this, but if a stale page still manages to submit
    after that happens, this turns what would be a raw `None["id"]`
    crash into a clear "please log in again" message instead."""
    user = current_user()
    if user is None:
        st.error("Your session has ended (the app may have restarted) — please refresh and log in again.")
        st.stop()
    return user


def _do_login(username: str, password: str) -> None:
    try:
        user = auth_module.login(username, password)
    except auth_module.AuthError as e:
        st.session_state["login_error"] = str(e)
        return

    if user.role != "manager":
        # Close the session we just opened rather than leaving it dangling —
        # a rejected login attempt is still honestly recorded as an
        # instantaneous login/logout pair, not left "stuck open".
        auth_module.logout(user.session_id)
        st.session_state["login_error"] = "This dashboard is for managers only."
        return

    st.session_state["login_error"] = None
    st.session_state["user"] = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "session_id": user.session_id,
        "must_change_password": user.must_change_password,
    }


def _render_login_form() -> None:
    sidebar_header()
    st.markdown("## Manager Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary")

    if submitted:
        _do_login(username, password)
        if current_user() is not None:
            st.rerun()

    if st.session_state.get("login_error"):
        st.error(st.session_state["login_error"])


def _render_force_password_change() -> None:
    sidebar_header()
    st.markdown("## Set a New Password")
    st.info("This is a temporary password. Choose a permanent password to continue.")
    with st.form("change_password_form"):
        pw1 = st.text_input("New password", type="password")
        pw2 = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Set Password", type="primary")

    if submitted:
        if len(pw1) < 8:
            st.error("Password must be at least 8 characters.")
        elif pw1 != pw2:
            st.error("Passwords do not match.")
        else:
            auth_module.set_password(current_user()["id"], pw1, force_change_next_login=False)
            st.session_state["user"]["must_change_password"] = False
            st.success("Password updated.")
            st.rerun()


def require_login() -> dict:
    """Returns the logged-in manager's session dict, or halts page execution
    (via st.stop()) after rendering a login / forced-password-change screen."""
    user = current_user()
    if user is None:
        _render_login_form()
        st.stop()
    if user["must_change_password"]:
        _render_force_password_change()
        st.stop()

    # Defense in depth: re-verify the role from the database on every rerun,
    # in case the account was deactivated or changed mid-session.
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT role, active FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
    finally:
        conn.close()
    if row is None or not row["active"] or row["role"] != "manager":
        do_logout()
        st.error("Your access has changed. Please log in again.")
        st.stop()

    return user


def do_logout() -> None:
    user = current_user()
    if user:
        auth_module.logout(user["session_id"])
    st.session_state.pop("user", None)

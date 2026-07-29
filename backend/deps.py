"""FastAPI dependencies for authenticating a request and enforcing role.

Every route that returns or mutates data imports one of these — there is no
route in this backend that trusts a role or user id supplied by the client
itself (query param, body field, etc.). The user's identity always comes
from validating the bearer token against the sessions table, and the role
is always re-read from the users table on every single request.
"""

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from security import verify_token
from db import get_connection


@dataclass
class CurrentUser:
    id: int
    username: str
    role: str
    session_id: int


def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or malformed Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        session_id = verify_token(token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")

    conn = get_connection()
    try:
        session = conn.execute(
            "SELECT user_id, logout_at FROM sessions WHERE id = %s", (session_id,)
        ).fetchone()
        if session is None or session["logout_at"] is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has ended. Please log in again.")

        user = conn.execute(
            "SELECT id, username, role, active FROM users WHERE id = %s", (session["user_id"],)
        ).fetchone()
        if user is None or not user["active"]:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is inactive.")

        return CurrentUser(id=user["id"], username=user["username"], role=user["role"], session_id=session_id)
    finally:
        conn.close()


def require_manager(current_user: CurrentUser) -> CurrentUser:
    if current_user.role != "manager":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager role required.")
    return current_user

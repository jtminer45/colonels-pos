"""
Authentication and role-enforcement for Colonel's Bakery and Restaurant POS.

Security notes (read before touching this file):
- Passwords are hashed with PBKDF2-HMAC-SHA256, 600,000 iterations, a unique
  random salt per user (via `secrets.token_hex`). The plaintext password is
  never stored anywhere, including in memory beyond the call stack.
- Login comparisons use `secrets.compare_digest` (constant-time) so response
  timing cannot be used to guess a password hash byte-by-byte.
- `require_role()` / `require_manager()` are the SINGLE enforcement point.
  Every code path that touches manager-level data — dashboard pages AND
  every backend API route — must call one of these before doing anything
  else. The till React UI hiding a button is a convenience, not security;
  the actual check always happens here, server-side, against the database.
"""

import hashlib
import secrets
import string
from dataclasses import dataclass
from typing import Optional

from db import get_connection, now_iso

PBKDF2_ITERATIONS = 600_000


class AuthError(Exception):
    """Raised for any authentication or authorization failure."""


@dataclass
class AuthenticatedUser:
    id: int
    username: str
    role: str
    active: bool
    must_change_password: bool
    session_id: int


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    ).hex()


def generate_temp_password(length: int = 10) -> str:
    """Generates a random, human-typeable temporary password (used by managers
    when creating staff accounts or resetting a forgotten one)."""
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_new_password(password: str) -> tuple[str, str]:
    """Returns (password_hash, salt) for a brand new / reset password."""
    salt = secrets.token_hex(16)
    return _hash_password(password, salt), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate = _hash_password(password, salt)
    return secrets.compare_digest(candidate, password_hash)


# ----------------------------------------------------------------------
# Login / logout
# ----------------------------------------------------------------------

def login(username: str, password: str) -> AuthenticatedUser:
    """Validates credentials, opens a session row, and returns the user.

    Raises AuthError with a generic message on any failure — we do not
    reveal whether the username exists or the password was wrong, since
    that distinction helps an attacker enumerate valid usernames.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, salt, role, active, must_change_password "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        # Always run a hash comparison even on unknown usernames, using a
        # fixed dummy salt, so login timing does not reveal whether the
        # username exists.
        if row is None:
            _hash_password(password, secrets.token_hex(16))
            raise AuthError("Invalid username or password.")

        if not verify_password(password, row["password_hash"], row["salt"]):
            raise AuthError("Invalid username or password.")

        if not row["active"]:
            raise AuthError("This account has been deactivated. Contact a manager.")

        login_at = now_iso()
        cur = conn.execute(
            "INSERT INTO sessions (user_id, login_at) VALUES (?, ?)",
            (row["id"], login_at),
        )
        conn.commit()

        return AuthenticatedUser(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            active=bool(row["active"]),
            must_change_password=bool(row["must_change_password"]),
            session_id=cur.lastrowid,
        )
    finally:
        conn.close()


def logout(session_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE sessions SET logout_at = ? WHERE id = ? AND logout_at IS NULL",
            (now_iso(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_password(user_id: int, new_password: str, *, force_change_next_login: bool = False) -> None:
    password_hash, salt = hash_new_password(new_password)
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ?, must_change_password = ? WHERE id = ?",
            (password_hash, salt, 1 if force_change_next_login else 0, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------------
# Role enforcement — call these at the top of every manager-only operation,
# in every layer (Streamlit pages, FastAPI routes, any future integration).
# Never trust a role value passed in from a client; always re-derive it from
# the database using the authenticated user's id.
# ----------------------------------------------------------------------

def get_user_role(user_id: int) -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT role FROM users WHERE id = ? AND active = 1", (user_id,)
        ).fetchone()
        return row["role"] if row else None
    finally:
        conn.close()


def require_role(user_id: int, allowed_roles: tuple[str, ...]) -> None:
    role = get_user_role(user_id)
    if role is None or role not in allowed_roles:
        raise AuthError("You do not have permission to perform this action.")


def require_manager(user_id: int) -> None:
    require_role(user_id, ("manager",))

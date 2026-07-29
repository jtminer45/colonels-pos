"""
Stateless API token signing for the till backend.

The till PWA is a browser app on the local network, so it cannot use a
plain server-side session cookie the way the Streamlit dashboard (a
same-process Python app) can. Instead, on login we hand back an opaque
token of the form "<session_id>.<hmac-signature>". The signature proves the
token was issued by this server and was not guessed or tampered with; it is
NOT itself the authorization check.

The actual authorization check happens on every request in deps.py, which
re-reads the user's role and active flag from the database — the token only
identifies *which* session/user is asking, never what they're allowed to do.
This is what "role checks happen server-side on every request" means in
practice: the token can't be forged to claim a different user, and even if
it could, the role/active check is re-derived from the DB, not decoded from
the token.
"""

import hmac
import hashlib
import os
import secrets
from pathlib import Path

_SECRET_PATH = Path(__file__).resolve().parent / ".secret_key"


def _load_or_create_secret() -> bytes:
    # On Render (and most PaaS hosts) the filesystem is ephemeral — a key
    # persisted only to a local file would be regenerated on every
    # redeploy/restart, silently invalidating every logged-in session. Set
    # SECRET_KEY as a real environment variable there (generate once,
    # store it in the service's env vars) so it survives restarts.
    #
    # Treated as an opaque string (UTF-8 encoded), not required to be hex —
    # Render's own `generateValue: true` produces an arbitrary random
    # string, not necessarily valid hex.
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")

    if _SECRET_PATH.exists():
        return _SECRET_PATH.read_text().strip().encode("utf-8")
    key = secrets.token_hex(32)
    _SECRET_PATH.write_text(key)
    _SECRET_PATH.chmod(0o600)
    return key.encode("utf-8")


_SECRET_KEY = _load_or_create_secret()


def create_token(session_id: int) -> str:
    signature = hmac.new(_SECRET_KEY, str(session_id).encode(), hashlib.sha256).hexdigest()
    return f"{session_id}.{signature}"


def verify_token(token: str) -> int:
    """Returns the session_id if the token's signature is valid. Raises ValueError otherwise."""
    try:
        session_id_str, signature = token.split(".", 1)
    except ValueError:
        raise ValueError("Malformed token.")

    expected = hmac.new(_SECRET_KEY, session_id_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid token signature.")
    return int(session_id_str)

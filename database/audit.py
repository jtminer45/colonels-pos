"""Audit log helper. Every void, manual stock adjustment, and manager
override must call log_action() as part of the same operation — never as an
afterthought — so the audit trail can never silently fall out of sync with
what actually happened.
"""

from db import get_connection, now_iso


def log_action(conn, user_id: int, action_type: str, details: str = "") -> None:
    """Writes an audit row using the caller's connection/transaction, so the
    log entry commits atomically together with the action it describes.
    """
    conn.execute(
        "INSERT INTO audit_log (timestamp, user_id, action_type, details) VALUES (%s, %s, %s, %s)",
        (now_iso(), user_id, action_type, details),
    )


def log_action_standalone(user_id: int, action_type: str, details: str = "") -> None:
    """Use only when there is no existing open transaction (e.g. a login event
    logged outside of another write). Prefer log_action() inside a shared
    connection wherever the audited action itself also writes to the DB.
    """
    conn = get_connection()
    try:
        log_action(conn, user_id, action_type, details)
        conn.commit()
    finally:
        conn.close()

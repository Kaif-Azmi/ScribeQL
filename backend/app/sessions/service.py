"""
Query Session service for ScribeQL.
Manages mode, dialect locking, ownership, TTL expiry, recovery, and 5-session eviction limit.
"""

from datetime import datetime, timedelta, timezone
import secrets
from typing import Dict, Any, Optional, List
from app.db.session import check_db_health, get_app_connection


class DialectLockedError(Exception):
    """Raised when attempting to upload a schema with a different dialect on a locked custom session."""
    pass


class WrongSessionModeError(Exception):
    """Raised when performing schema upload on a demo session."""
    pass


class InMemoryQuerySessionStore:
    """In-memory store for query sessions used in unit testing and fallback mode."""
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> session_dict

    def clear(self):
        self.sessions.clear()


in_memory_query_store = InMemoryQuerySessionStore()


class QuerySessionService:
    MAX_ACTIVE_SESSIONS_PER_USER = 5
    DEFAULT_TTL_HOURS = 24

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def create_session(self, user_id: str, mode: str) -> Dict[str, Any]:
        """
        Create a new query session.
        Demo mode fixes dialect to 'postgres' and has_schema=True.
        Custom mode sets dialect=None and has_schema=False.
        Evicts oldest unexpired sessions if count > 5.
        """
        if mode not in ("demo", "custom"):
            raise ValueError(f"Invalid mode '{mode}'. Must be 'demo' or 'custom'.")

        session_id = secrets.token_urlsafe(24)
        now = self._now()
        expires_at = now + timedelta(hours=self.DEFAULT_TTL_HOURS)

        if mode == "demo":
            dialect = "postgres"
            has_schema = True
        else:  # custom
            dialect = None
            has_schema = False

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "mode": mode,
            "dialect": dialect,
            "has_schema": has_schema,
            "schema_id": None,
            "created_at": now,
            "expires_at": expires_at
        }

        # 1. Enforce max 5 active sessions per user (evict oldest)
        self._evict_excess_sessions(user_id)

        # 2. Store session
        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO app.sessions (id, user_id, mode, dialect, has_schema, schema_id, created_at, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        session_id, user_id, mode, dialect, has_schema, None, now, expires_at
                    ))
            return session_data

        in_memory_query_store.sessions[session_id] = session_data
        return session_data

    def get_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch an unexpired session owned by user_id.
        Returns None if expired, non-existent, or owned by someone else.
        """
        now = self._now()

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, user_id, mode, dialect, has_schema, schema_id, created_at, expires_at
                        FROM app.sessions
                        WHERE id = %s AND user_id = %s;
                    """, (session_id, user_id))
                    row = cur.fetchone()
                    if not row:
                        return None
                    s_id, u_id, mode, dialect, has_schema, schema_id, created_at, expires_at = row
                    if expires_at and expires_at < now:
                        return None
                    return {
                        "session_id": s_id,
                        "user_id": u_id,
                        "mode": mode,
                        "dialect": dialect,
                        "has_schema": has_schema,
                        "schema_id": schema_id,
                        "created_at": created_at,
                        "expires_at": expires_at
                    }

        sess = in_memory_query_store.sessions.get(session_id)
        if not sess or sess["user_id"] != user_id or sess["expires_at"] < now:
            return None
        return sess

    def recover_session(self, user_id: str, mode: str) -> Optional[Dict[str, Any]]:
        """
        Recover caller's most recent unexpired session of the requested mode.
        """
        now = self._now()

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, user_id, mode, dialect, has_schema, schema_id, created_at, expires_at
                        FROM app.sessions
                        WHERE user_id = %s AND mode = %s AND expires_at > %s
                        ORDER BY created_at DESC
                        LIMIT 1;
                    """, (user_id, mode, now))
                    row = cur.fetchone()
                    if not row:
                        return None
                    s_id, u_id, m_val, dialect, has_schema, schema_id, created_at, expires_at = row
                    return {
                        "session_id": s_id,
                        "user_id": u_id,
                        "mode": m_val,
                        "dialect": dialect,
                        "has_schema": has_schema,
                        "schema_id": schema_id,
                        "created_at": created_at,
                        "expires_at": expires_at
                    }

        user_sessions = [
            s for s in in_memory_query_store.sessions.values()
            if s["user_id"] == user_id and s["mode"] == mode and s["expires_at"] > now
        ]
        if not user_sessions:
            return None

        # Sort by created_at descending
        user_sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return user_sessions[0]

    def lock_custom_dialect(self, session_id: str, user_id: str, dialect: str, schema_id: str) -> Dict[str, Any]:
        """
        Lock dialect for a custom mode session upon successful schema upload.
        If session dialect is already locked to a different dialect, raises DialectLockedError.
        """
        sess = self.get_session(session_id, user_id)
        if not sess:
            raise KeyError("session_not_found")

        if sess["mode"] != "custom":
            raise WrongSessionModeError("The session is demo mode.")

        current_dialect = sess.get("dialect")
        clean_dialect = dialect.lower().strip()

        if current_dialect is not None and current_dialect.lower() != clean_dialect:
            raise DialectLockedError(
                f"The session dialect is locked to '{current_dialect}'. Start a new session to switch dialect."
            )

        sess["dialect"] = clean_dialect
        sess["has_schema"] = True
        sess["schema_id"] = schema_id

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE app.sessions
                        SET dialect = %s, has_schema = true, schema_id = %s
                        WHERE id = %s AND user_id = %s;
                    """, (clean_dialect, schema_id, session_id, user_id))

        return sess

    def _evict_excess_sessions(self, user_id: str):
        """Evict oldest unexpired sessions if user exceeds 5 active sessions limit."""
        now = self._now()

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM app.sessions
                        WHERE user_id = %s AND expires_at > %s
                        ORDER BY created_at DESC;
                    """, (user_id, now))
                    rows = cur.fetchall()
                    if len(rows) >= self.MAX_ACTIVE_SESSIONS_PER_USER:
                        # Evict oldest unexpired sessions past limit (keep newest 4)
                        to_evict = [r[0] for r in rows[self.MAX_ACTIVE_SESSIONS_PER_USER - 1:]]
                        cur.execute("DELETE FROM app.sessions WHERE id = ANY(%s);", (to_evict,))
            return

        active_user_sessions = [
            s for s in in_memory_query_store.sessions.values()
            if s["user_id"] == user_id and s["expires_at"] > now
        ]
        if len(active_user_sessions) >= self.MAX_ACTIVE_SESSIONS_PER_USER:
            active_user_sessions.sort(key=lambda s: s["created_at"], reverse=True)
            for s in active_user_sessions[self.MAX_ACTIVE_SESSIONS_PER_USER - 1:]:
                in_memory_query_store.sessions.pop(s["session_id"], None)

    def delete_user_sessions(self, user_id: str):
        """Permanently delete all query sessions owned by user_id."""
        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM app.sessions WHERE user_id = %s;", (user_id,))
            return

        to_delete = [
            sid for sid, s in in_memory_query_store.sessions.items()
            if s["user_id"] == user_id
        ]
        for sid in to_delete:
            in_memory_query_store.sessions.pop(sid, None)


query_session_service = QuerySessionService()


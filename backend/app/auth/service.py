"""
Authentication service implementing core auth logic, server-side auth sessions,
token management, and account deletion rules.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List
import secrets
from app.auth.password import hash_password, verify_password
from app.auth.tokens import generate_secure_token, hash_token
from app.db.session import check_db_health, get_app_connection


class InMemoryAuthStore:
    """In-memory authentication store used for fast unit testing & isolated execution."""
    def __init__(self):
        self.users: Dict[str, Dict[str, Any]] = {}  # key: user_id
        self.users_by_email: Dict[str, str] = {}    # email -> user_id
        self.sessions: Dict[str, Dict[str, Any]] = {} # token_hash -> session_info
        self.tokens: Dict[str, Dict[str, Any]] = {}   # token_hash -> token_info

    def clear(self):
        self.users.clear()
        self.users_by_email.clear()
        self.sessions.clear()
        self.tokens.clear()


in_memory_auth_store = InMemoryAuthStore()


class AuthService:
    def __init__(self):
        pass

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # --- SIGN UP ---
    def signup(self, email: str, password: str) -> Tuple[str, str]:
        """
        Create a new unverified user account or generate a verification token for an existing address.
        Returns (user_id, raw_verification_token).
        """
        clean_email = email.lower().strip()
        raw_token = generate_secure_token()
        token_h = hash_token(raw_token)
        expires_at = self._now() + timedelta(hours=24)

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, is_verified FROM app.users WHERE email = %s;", (clean_email,))
                    row = cur.fetchone()
                    if row:
                        user_id = str(row[0])
                    else:
                        pwd_hash = hash_password(password)
                        cur.execute("""
                            INSERT INTO app.users (email, password_hash, is_verified, created_at, updated_at)
                            VALUES (%s, %s, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            RETURNING id;
                        """, (clean_email, pwd_hash))
                        user_id = str(cur.fetchone()[0])

                    cur.execute("""
                        INSERT INTO app.email_tokens (user_id, token_hash, token_type, expires_at)
                        VALUES (%s, %s, 'verify', %s);
                    """, (user_id, token_h, expires_at))
            return user_id, raw_token

        # In-memory fallback
        if clean_email in in_memory_auth_store.users_by_email:
            user_id = in_memory_auth_store.users_by_email[clean_email]
        else:
            user_id = f"usr_{secrets.token_hex(8)}"
            pwd_hash = hash_password(password)
            user_obj = {
                "id": user_id,
                "email": clean_email,
                "password_hash": pwd_hash,
                "is_verified": False,
                "google_sub": None,
                "created_at": self._now()
            }
            in_memory_auth_store.users[user_id] = user_obj
            in_memory_auth_store.users_by_email[clean_email] = user_id

        in_memory_auth_store.tokens[token_h] = {
            "user_id": user_id,
            "token_type": "verify",
            "expires_at": expires_at,
            "used_at": None
        }
        return user_id, raw_token

    # --- VERIFY ---
    def verify_email(self, token: str) -> Tuple[Dict[str, Any], str]:
        """
        Verify email token, mark user verified, create auth session.
        Returns (user_dict, raw_session_token).
        """
        token_h = hash_token(token)
        now = self._now()

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_id, token_type, expires_at, used_at
                        FROM app.email_tokens
                        WHERE token_hash = %s AND token_type = 'verify';
                    """, (token_h,))
                    row = cur.fetchone()
                    if not row:
                        raise ValueError("invalid_or_expired_token")

                    user_id, t_type, expires_at, used_at = row
                    if used_at is not None or (expires_at and expires_at < now):
                        raise ValueError("invalid_or_expired_token")

                    # Mark verified & used
                    cur.execute("UPDATE app.users SET is_verified = true WHERE id = %s;", (user_id,))
                    cur.execute("UPDATE app.email_tokens SET used_at = CURRENT_TIMESTAMP WHERE token_hash = %s;", (token_h,))

                    cur.execute("SELECT email, password_hash, google_sub FROM app.users WHERE id = %s;", (user_id,))
                    u_row = cur.fetchone()
                    user_dict = {
                        "id": str(user_id),
                        "email": u_row[0],
                        "has_password": u_row[1] is not None,
                        "google_linked": u_row[2] is not None
                    }

            raw_session_token = self.create_auth_session(user_dict["id"])
            return user_dict, raw_session_token

        # In-memory fallback
        t_info = in_memory_auth_store.tokens.get(token_h)
        if not t_info or t_info["token_type"] != "verify" or t_info["used_at"] or t_info["expires_at"] < now:
            raise ValueError("invalid_or_expired_token")

        t_info["used_at"] = now
        user_obj = in_memory_auth_store.users[t_info["user_id"]]
        user_obj["is_verified"] = True

        user_dict = {
            "id": user_obj["id"],
            "email": user_obj["email"],
            "has_password": user_obj["password_hash"] is not None,
            "google_linked": user_obj.get("google_sub") is not None
        }
        raw_session_token = self.create_auth_session(user_dict["id"])
        return user_dict, raw_session_token

    # --- SIGN IN ---
    def signin(self, email: str, password: str) -> Tuple[Dict[str, Any], str]:
        """
        Authenticate email and password.
        Returns (user_dict, raw_session_token).
        """
        clean_email = email.lower().strip()

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, email, password_hash, is_verified, google_sub
                        FROM app.users
                        WHERE email = %s;
                    """, (clean_email,))
                    row = cur.fetchone()
                    if not row or not row[2] or not verify_password(row[2], password):
                        raise ValueError("invalid_credentials")

                    user_id, email_val, pwd_hash, is_verified, google_sub = row
                    if not is_verified:
                        raise ValueError("email_not_verified")

                    user_dict = {
                        "id": str(user_id),
                        "email": email_val,
                        "has_password": True,
                        "google_linked": google_sub is not None
                    }
            raw_session_token = self.create_auth_session(user_dict["id"])
            return user_dict, raw_session_token

        # In-memory fallback
        user_id = in_memory_auth_store.users_by_email.get(clean_email)
        if not user_id:
            raise ValueError("invalid_credentials")

        user_obj = in_memory_auth_store.users[user_id]
        if not user_obj.get("password_hash") or not verify_password(user_obj["password_hash"], password):
            raise ValueError("invalid_credentials")

        if not user_obj.get("is_verified"):
            raise ValueError("email_not_verified")

        user_dict = {
            "id": user_obj["id"],
            "email": user_obj["email"],
            "has_password": True,
            "google_linked": user_obj.get("google_sub") is not None
        }
        raw_session_token = self.create_auth_session(user_dict["id"])
        return user_dict, raw_session_token

    def _user_dict(self, user_id: str, email: str, has_password: bool, google_linked: bool) -> Dict[str, Any]:
        return {
            "id": str(user_id),
            "email": email,
            "has_password": has_password,
            "google_linked": google_linked,
        }

    def signin_google(self, google_sub: str, email: str) -> Tuple[Dict[str, Any], str]:
        """
        Create or link a verified account for a Google identity, then start an auth session.
        """
        clean_email = email.lower().strip()
        sub = str(google_sub).strip()
        if not clean_email or not sub:
            raise ValueError("google_failed")

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT u.id, u.email, u.password_hash, u.google_sub
                        FROM app.auth_identities i
                        JOIN app.users u ON u.id = i.user_id
                        WHERE i.provider = 'google' AND i.provider_user_id = %s;
                        """,
                        (sub,),
                    )
                    row = cur.fetchone()
                    if not row:
                        cur.execute(
                            """
                            SELECT id, email, password_hash, google_sub
                            FROM app.users
                            WHERE google_sub = %s OR email = %s
                            ORDER BY CASE WHEN google_sub = %s THEN 0 ELSE 1 END
                            LIMIT 1;
                            """,
                            (sub, clean_email, sub),
                        )
                        row = cur.fetchone()

                    if row:
                        user_id, email_val, pwd_hash, existing_sub = row
                        if existing_sub and existing_sub != sub:
                            raise ValueError("google_failed")
                        cur.execute(
                            """
                            UPDATE app.users
                            SET google_sub = %s, is_verified = true, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s;
                            """,
                            (sub, user_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO app.users (email, password_hash, is_verified, google_sub, created_at, updated_at)
                            VALUES (%s, NULL, true, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            RETURNING id, email, password_hash;
                            """,
                            (clean_email, sub),
                        )
                        user_id, email_val, pwd_hash = cur.fetchone()

                    cur.execute(
                        """
                        INSERT INTO app.auth_identities (user_id, provider, provider_user_id)
                        VALUES (%s, 'google', %s)
                        ON CONFLICT (provider, provider_user_id) DO NOTHING;
                        """,
                        (user_id, sub),
                    )
                    user_dict = self._user_dict(user_id, email_val, pwd_hash is not None, True)
            return user_dict, self.create_auth_session(str(user_id))

        # In-memory fallback
        matched = None
        for user_obj in in_memory_auth_store.users.values():
            if user_obj.get("google_sub") == sub:
                matched = user_obj
                break
        if matched is None:
            uid = in_memory_auth_store.users_by_email.get(clean_email)
            if uid:
                matched = in_memory_auth_store.users[uid]
                if matched.get("google_sub") and matched["google_sub"] != sub:
                    raise ValueError("google_failed")
        if matched is None:
            user_id = f"usr_{secrets.token_hex(8)}"
            matched = {
                "id": user_id,
                "email": clean_email,
                "password_hash": None,
                "is_verified": True,
                "google_sub": sub,
                "created_at": self._now(),
            }
            in_memory_auth_store.users[user_id] = matched
            in_memory_auth_store.users_by_email[clean_email] = user_id
        else:
            matched["google_sub"] = sub
            matched["is_verified"] = True

        user_dict = self._user_dict(
            matched["id"],
            matched["email"],
            matched.get("password_hash") is not None,
            True,
        )
        return user_dict, self.create_auth_session(user_dict["id"])

    # --- CREATE AUTH SESSION ---
    def create_auth_session(self, user_id: str) -> str:
        """Create a server-side auth session and return raw token for HttpOnly cookie."""
        raw_session_token = generate_secure_token()
        session_h = hash_token(raw_session_token)
        now = self._now()
        expires_at = now + timedelta(days=7)

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO app.auth_sessions (user_id, session_token_hash, created_at, last_active_at, expires_at)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (user_id, session_h, now, now, expires_at))
            return raw_session_token

        # In-memory fallback
        in_memory_auth_store.sessions[session_h] = {
            "user_id": user_id,
            "created_at": now,
            "last_active_at": now,
            "expires_at": expires_at
        }
        return raw_session_token

    # --- VALIDATE AUTH SESSION ---
    def validate_auth_session(self, raw_session_token: str) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Validate auth session cookie token.
        Returns Optional[Tuple[user_dict, session_age_minutes]].
        """
        if not raw_session_token:
            return None

        session_h = hash_token(raw_session_token)
        now = self._now()

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT s.user_id, s.created_at, s.last_active_at, s.expires_at,
                               u.email, u.password_hash, u.google_sub
                        FROM app.auth_sessions s
                        JOIN app.users u ON u.id = s.user_id
                        WHERE s.session_token_hash = %s;
                    """, (session_h,))
                    row = cur.fetchone()
                    if not row:
                        return None

                    u_id, created_at, last_active, expires_at, email, pwd_hash, g_sub = row
                    if expires_at and expires_at < now:
                        return None

                    # Calculate session age in minutes
                    age_minutes = (now - created_at).total_seconds() / 60.0

                    user_dict = {
                        "id": str(u_id),
                        "email": email,
                        "has_password": pwd_hash is not None,
                        "google_linked": g_sub is not None
                    }
                    return user_dict, age_minutes

        # In-memory fallback
        sess = in_memory_auth_store.sessions.get(session_h)
        if not sess or sess["expires_at"] < now:
            return None

        user_obj = in_memory_auth_store.users.get(sess["user_id"])
        if not user_obj:
            return None

        age_minutes = (now - sess["created_at"]).total_seconds() / 60.0
        user_dict = {
            "id": user_obj["id"],
            "email": user_obj["email"],
            "has_password": user_obj.get("password_hash") is not None,
            "google_linked": user_obj.get("google_sub") is not None
        }
        return user_dict, age_minutes

    # --- SIGNOUT ---
    def signout(self, raw_session_token: str):
        """Revoke a single auth session."""
        if not raw_session_token:
            return
        session_h = hash_token(raw_session_token)

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM app.auth_sessions WHERE session_token_hash = %s;", (session_h,))
            return

        in_memory_auth_store.sessions.pop(session_h, None)

    # --- FORGOT PASSWORD ---
    def forgot_password(self, email: str) -> Optional[str]:
        """
        Generate password reset token if account exists and is verified.
        Always returns 202 status logically.
        """
        clean_email = email.lower().strip()
        raw_token = generate_secure_token()
        token_h = hash_token(raw_token)
        expires_at = self._now() + timedelta(hours=1)

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, is_verified FROM app.users WHERE email = %s;", (clean_email,))
                    row = cur.fetchone()
                    if row and row[1]:  # exists & verified
                        user_id = str(row[0])
                        cur.execute("""
                            INSERT INTO app.email_tokens (user_id, token_hash, token_type, expires_at)
                            VALUES (%s, %s, 'reset', %s);
                        """, (user_id, token_h, expires_at))
                        return raw_token
            return None

        user_id = in_memory_auth_store.users_by_email.get(clean_email)
        if user_id:
            user_obj = in_memory_auth_store.users[user_id]
            if user_obj.get("is_verified"):
                in_memory_auth_store.tokens[token_h] = {
                    "user_id": user_id,
                    "token_type": "reset",
                    "expires_at": expires_at,
                    "used_at": None
                }
                return raw_token
        return None

    # --- RESET PASSWORD ---
    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Update user password and revoke ALL auth sessions for that user.
        """
        token_h = hash_token(token)
        now = self._now()
        new_pwd_hash = hash_password(new_password)

        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_id, token_type, expires_at, used_at
                        FROM app.email_tokens
                        WHERE token_hash = %s AND token_type = 'reset';
                    """, (token_h,))
                    row = cur.fetchone()
                    if not row:
                        raise ValueError("invalid_or_expired_token")

                    user_id, t_type, expires_at, used_at = row
                    if used_at is not None or (expires_at and expires_at < now):
                        raise ValueError("invalid_or_expired_token")

                    # Update password
                    cur.execute("""
                        UPDATE app.users
                        SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (new_pwd_hash, user_id))

                    # Mark token used
                    cur.execute("UPDATE app.email_tokens SET used_at = CURRENT_TIMESTAMP WHERE token_hash = %s;", (token_h,))

                    # Revoke ALL auth sessions for user
                    cur.execute("DELETE FROM app.auth_sessions WHERE user_id = %s;", (user_id,))
            return True

        t_info = in_memory_auth_store.tokens.get(token_h)
        if not t_info or t_info["token_type"] != "reset" or t_info["used_at"] or t_info["expires_at"] < now:
            raise ValueError("invalid_or_expired_token")

        t_info["used_at"] = now
        user_id = t_info["user_id"]
        user_obj = in_memory_auth_store.users[user_id]
        user_obj["password_hash"] = new_pwd_hash

        # Revoke all sessions for this user in memory
        to_delete = [th for th, s in in_memory_auth_store.sessions.items() if s["user_id"] == user_id]
        for th in to_delete:
            in_memory_auth_store.sessions.pop(th, None)

        return True

    # --- DELETE ACCOUNT ---
    def delete_account(self, user_id: str) -> bool:
        """
        Permanently delete user account and all owned resources.
        Deletes auth sessions, email tokens, query sessions, and user records.
        """
        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM app.auth_sessions WHERE user_id = %s;", (user_id,))
                    cur.execute("DELETE FROM app.email_tokens WHERE user_id = %s;", (user_id,))
                    cur.execute("DELETE FROM app.sessions WHERE user_id = %s;", (user_id,))
                    cur.execute("DELETE FROM app.query_logs WHERE user_id = %s;", (user_id,))
                    cur.execute("DELETE FROM app.users WHERE id = %s;", (user_id,))
            return True

        # In-memory cleanup
        email_to_remove = None
        for email, uid in in_memory_auth_store.users_by_email.items():
            if uid == user_id:
                email_to_remove = email
                break
        if email_to_remove:
            in_memory_auth_store.users_by_email.pop(email_to_remove, None)

        in_memory_auth_store.users.pop(user_id, None)

        # Delete user auth sessions
        to_del_sessions = [th for th, s in in_memory_auth_store.sessions.items() if s["user_id"] == user_id]
        for th in to_del_sessions:
            in_memory_auth_store.sessions.pop(th, None)

        # Delete user tokens
        to_del_tokens = [th for th, t in in_memory_auth_store.tokens.items() if t["user_id"] == user_id]
        for th in to_del_tokens:
            in_memory_auth_store.tokens.pop(th, None)

        # Delete in-memory query sessions only (do not hit Postgres with synthetic ids)
        from app.sessions.service import in_memory_query_store
        to_delete_qs = [
            sid for sid, s in in_memory_query_store.sessions.items()
            if s["user_id"] == user_id
        ]
        for sid in to_delete_qs:
            in_memory_query_store.sessions.pop(sid, None)
        return True


auth_service = AuthService()


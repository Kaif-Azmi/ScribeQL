from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.service import auth_service, in_memory_auth_store
from app.sessions.service import query_session_service, in_memory_query_store, DialectLockedError

client = TestClient(app)
ORIGIN_HEADER = {"Origin": "http://localhost:5173"}


def setup_function():
    in_memory_auth_store.clear()
    in_memory_query_store.clear()


def create_authenticated_user(email: str = "user@example.com") -> Tuple[Dict[str, Any], str]:
    _, v_token = auth_service.signup(email, "password123456")
    user_dict, session_token = auth_service.verify_email(v_token)
    return user_dict, session_token


def test_create_demo_session():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_dict, auth_cookie = create_authenticated_user("asha@example.com")

        resp = client.post(
            "/api/session",
            json={"mode": "demo"},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "demo"
        assert data["dialect"] == "postgres"
        assert "session_id" in data


def test_create_custom_session():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_dict, auth_cookie = create_authenticated_user("rohan@example.com")

        resp = client.post(
            "/api/session",
            json={"mode": "custom"},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "custom"
        assert data["dialect"] is None


def test_create_session_rejects_dialect_field():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_dict, auth_cookie = create_authenticated_user("vikram@example.com")

        resp = client.post(
            "/api/session",
            json={"mode": "demo", "dialect": "postgres"},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "invalid_request"



def test_recover_session_flow():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_dict, auth_cookie = create_authenticated_user("priya@example.com")

        # 1. Recover without active session -> 404
        rec_404 = client.get("/api/session?mode=demo", cookies={"__Host-sid": auth_cookie})
        assert rec_404.status_code == 404
        assert rec_404.json()["error"]["type"] == "session_not_found"

        # 2. Create demo session -> recover demo -> 200
        client.post("/api/session", json={"mode": "demo"}, cookies={"__Host-sid": auth_cookie}, headers=ORIGIN_HEADER)
        rec_demo = client.get("/api/session?mode=demo", cookies={"__Host-sid": auth_cookie})
        assert rec_demo.status_code == 200
        assert rec_demo.json()["mode"] == "demo"
        assert rec_demo.json()["dialect"] == "postgres"
        assert rec_demo.json()["has_schema"] is True

        # 3. Create custom session -> recover custom -> 200
        client.post("/api/session", json={"mode": "custom"}, cookies={"__Host-sid": auth_cookie}, headers=ORIGIN_HEADER)
        rec_custom = client.get("/api/session?mode=custom", cookies={"__Host-sid": auth_cookie})
        assert rec_custom.status_code == 200
        assert rec_custom.json()["mode"] == "custom"
        assert rec_custom.json()["dialect"] is None
        assert rec_custom.json()["has_schema"] is False


def test_session_ownership_boundary():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_a, cookie_a = create_authenticated_user("usera@example.com")
        user_b, cookie_b = create_authenticated_user("userb@example.com")

        # User A creates session
        sess_a = query_session_service.create_session(user_a["id"], "demo")

        # User B attempting to fetch User A's session -> returns None (404)
        assert query_session_service.get_session(sess_a["session_id"], user_b["id"]) is None


def test_max_active_sessions_eviction():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_dict, auth_cookie = create_authenticated_user("limit@example.com")

        created_ids = []
        for i in range(6):
            s = query_session_service.create_session(user_dict["id"], "demo")
            created_ids.append(s["session_id"])

        # Oldest session created_ids[0] should be evicted
        assert query_session_service.get_session(created_ids[0], user_dict["id"]) is None
        # Newest session created_ids[-1] should be active
        assert query_session_service.get_session(created_ids[-1], user_dict["id"]) is not None


def test_custom_dialect_locking():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_dict, auth_cookie = create_authenticated_user("lock@example.com")
        sess = query_session_service.create_session(user_dict["id"], "custom")

        # First upload locks to postgres
        locked = query_session_service.lock_custom_dialect(sess["session_id"], user_dict["id"], "postgres", "sch_001")
        assert locked["dialect"] == "postgres"
        assert locked["has_schema"] is True

        # Same dialect upload succeeds
        locked_again = query_session_service.lock_custom_dialect(sess["session_id"], user_dict["id"], "postgres", "sch_002")
        assert locked_again["dialect"] == "postgres"

        # Different dialect upload raises DialectLockedError
        with pytest.raises(DialectLockedError):
            query_session_service.lock_custom_dialect(sess["session_id"], user_dict["id"], "mysql", "sch_003")

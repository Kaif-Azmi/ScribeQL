from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.config.settings import settings
from app.auth.google import OAUTH_COOKIE, dump_oauth_cookie
from app.auth.service import auth_service, in_memory_auth_store

client = TestClient(app)

ORIGIN_HEADER = {"Origin": "http://localhost:5173"}


def setup_function():
    in_memory_auth_store.clear()


def test_signup_always_returns_202():
    with patch("app.auth.service.check_db_health", return_value=False):
        response = client.post(
            "/api/auth/signup",
            json={"email": "asha@example.com", "password": "correct horse battery staple"},
            headers=ORIGIN_HEADER
        )
        assert response.status_code == 202
        assert response.json() == {"status": "verification_sent"}


def test_signup_password_length_validation():
    response = client.post(
        "/api/auth/signup",
        json={"email": "asha@example.com", "password": "short"},
        headers=ORIGIN_HEADER
    )
    assert response.status_code in (400, 422)


def test_verify_email_and_signin_flow():
    with patch("app.auth.service.check_db_health", return_value=False):
        # 1. Signup
        user_id, raw_verify_token = auth_service.signup("rohan@example.com", "securepassword123")

        # 2. Attempt signin before verification -> 403 email_not_verified
        signin_resp = client.post(
            "/api/auth/signin",
            json={"email": "rohan@example.com", "password": "securepassword123"},
            headers=ORIGIN_HEADER
        )
        assert signin_resp.status_code == 403
        assert signin_resp.json()["error"]["type"] == "email_not_verified"

        # 3. Verify email -> 200 and sets cookie
        verify_resp = client.post(
            "/api/auth/verify",
            json={"token": raw_verify_token},
            headers=ORIGIN_HEADER
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["user"]["email"] == "rohan@example.com"
        assert "__Host-sid" in verify_resp.cookies

        # 4. Sign in after verification -> 200
        signin_ok = client.post(
            "/api/auth/signin",
            json={"email": "rohan@example.com", "password": "securepassword123"},
            headers=ORIGIN_HEADER
        )
        assert signin_ok.status_code == 200
        assert signin_ok.json()["user"]["email"] == "rohan@example.com"


def test_invalid_credentials_returns_generic_401():
    with patch("app.auth.service.check_db_health", return_value=False):
        auth_service.signup("neha@example.com", "password123456")
        # Mark verified directly
        u_id = in_memory_auth_store.users_by_email["neha@example.com"]
        in_memory_auth_store.users[u_id]["is_verified"] = True

        resp = client.post(
            "/api/auth/signin",
            json={"email": "neha@example.com", "password": "wrongpassword123"},
            headers=ORIGIN_HEADER
        )
        assert resp.status_code == 401
        assert resp.json() == {"error": {"type": "invalid_credentials", "message": "Invalid email or password."}}


def test_get_me_unauthenticated_and_authenticated():
    with patch("app.auth.service.check_db_health", return_value=False):
        # Unauthenticated call -> 401
        resp_unauth = client.get("/api/me")
        assert resp_unauth.status_code == 401

        # Create verified user and signin
        _, token = auth_service.signup("arjun@example.com", "mysecretpassword123")
        user_dict, session_token = auth_service.verify_email(token)

        # Authenticated call -> 200
        resp_auth = client.get("/api/me", cookies={"__Host-sid": session_token})
        assert resp_auth.status_code == 200
        data = resp_auth.json()
        assert data["user"]["email"] == "arjun@example.com"
        assert data["usage"]["queries"]["limit"] == 20


def test_bad_origin_rejection():
    # Missing Origin header on non-GET request -> 403 bad_origin
    resp = client.post(
        "/api/auth/signup",
        json={"email": "test@example.com", "password": "password123456"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"]["type"] == "bad_origin"


def test_forgot_and_reset_password_revokes_sessions():
    with patch("app.auth.service.check_db_health", return_value=False):
        # 1. User signs up & verifies
        _, v_token = auth_service.signup("priya@example.com", "oldpassword123")
        _, sess_token = auth_service.verify_email(v_token)

        # 2. Verify active session works
        me_before = client.get("/api/me", cookies={"__Host-sid": sess_token})
        assert me_before.status_code == 200

        # 3. Forgot password -> 202
        forgot_resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "priya@example.com"},
            headers=ORIGIN_HEADER
        )
        assert forgot_resp.status_code == 202

        # Fetch reset token generated
        reset_token = auth_service.forgot_password("priya@example.com")
        assert reset_token is not None

        # 4. Reset password -> 200
        reset_resp = client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "newpassword123"},
            headers=ORIGIN_HEADER
        )
        assert reset_resp.status_code == 200

        # 5. Previous session must now be revoked -> 401
        me_after = client.get("/api/me", cookies={"__Host-sid": sess_token})
        assert me_after.status_code == 401

        # 6. Sign in with new password -> 200
        signin_new = client.post(
            "/api/auth/signin",
            json={"email": "priya@example.com", "password": "newpassword123"},
            headers=ORIGIN_HEADER
        )
        assert signin_new.status_code == 200


def test_delete_account_reauth_rule():
    with patch("app.auth.service.check_db_health", return_value=False):
        # Create user & session
        _, v_token = auth_service.signup("kabir@example.com", "password123456")
        _, sess_token = auth_service.verify_email(v_token)

        # Mock session age to 20 minutes (> 15 min limit)
        with patch.object(auth_service, "validate_auth_session", return_value=({"id": "usr_kabir", "email": "kabir@example.com", "has_password": True, "google_linked": False}, 20.0)):
            del_resp = client.request(
                "DELETE",
                "/api/me",
                json={"confirm": True},
                cookies={"__Host-sid": sess_token},
                headers=ORIGIN_HEADER
            )
            assert del_resp.status_code == 403
            assert del_resp.json()["error"]["type"] == "reauth_required"

        # Fresh session (< 15 min limit) -> 204
        with patch.object(auth_service, "validate_auth_session", return_value=({"id": "usr_kabir", "email": "kabir@example.com", "has_password": True, "google_linked": False}, 2.0)):
            del_ok = client.request(
                "DELETE",
                "/api/me",
                json={"confirm": True},
                cookies={"__Host-sid": sess_token},
                headers=ORIGIN_HEADER
            )
            assert del_ok.status_code == 204


def test_delete_account_cascades_query_sessions_and_tokens():
    from app.sessions.service import query_session_service, in_memory_query_store

    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False):
        user_id, v_token = auth_service.signup("cascade@example.com", "password123456")
        user_dict, sess_token = auth_service.verify_email(v_token)

        # Create query session for this user
        sess = query_session_service.create_session(user_id, "demo")
        session_id = sess["session_id"]
        assert session_id in in_memory_query_store.sessions

        # Delete account
        del_resp = client.request(
            "DELETE",
            "/api/me",
            json={"confirm": True},
            cookies={"__Host-sid": sess_token},
            headers=ORIGIN_HEADER
        )
        assert del_resp.status_code == 204

        # Verify full cascade
        assert user_id not in in_memory_auth_store.users
        assert "cascade@example.com" not in in_memory_auth_store.users_by_email
        assert session_id not in in_memory_query_store.sessions


def test_google_start_without_credentials_fails_closed():
    with patch.object(settings, "google_client_id", ""), patch.object(settings, "google_client_secret", ""):
        resp = client.get("/api/auth/google/start?next=/start", follow_redirects=False)
        assert resp.status_code == 302
        assert "error=google_failed" in resp.headers["location"]


def test_google_start_redirects_to_google_and_sets_pkce_cookie():
    with patch.object(settings, "google_client_id", "cid.apps.googleusercontent.com"), patch.object(
        settings, "google_client_secret", "gsecret"
    ):
        resp = client.get("/api/auth/google/start?next=/start", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"].startswith("https://accounts.google.com/")
        assert "code_challenge" in resp.headers["location"]
        assert OAUTH_COOKIE in resp.cookies


def test_google_callback_error_query_fails_closed():
    resp = client.get("/api/auth/google/callback?error=access_denied", follow_redirects=False)
    assert resp.status_code == 302
    assert "error=google_failed" in resp.headers["location"]
    assert "access_denied" not in resp.headers["location"]


def test_google_callback_success_sets_auth_cookie():
    nonce = "n1"
    cookie = dump_oauth_cookie("verifier", nonce, "/start")
    with patch("app.auth.service.check_db_health", return_value=False), patch(
        "app.auth.routes.exchange_code", new=AsyncMock(return_value={"access_token": "tok"})
    ), patch(
        "app.auth.routes.fetch_userinfo",
        new=AsyncMock(return_value={"sub": "gid-1", "email": "asha@example.com"}),
    ):
        resp = client.get(
            f"/api/auth/google/callback?code=ok&state={nonce}",
            cookies={OAUTH_COOKIE: cookie},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["location"].endswith("/start")
        assert "google_failed" not in resp.headers["location"]
        assert "__Host-sid" in resp.cookies


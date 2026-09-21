"""
Google OAuth 2.0 PKCE helper.
"""

import base64
import hashlib
import hmac
import json
import secrets
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config.settings import settings

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

OAUTH_COOKIE = "sq_oauth"
OAUTH_COOKIE_MAX_AGE = 600


def generate_pkce_pair() -> Tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def get_google_auth_url(state: str, code_challenge: str) -> str:
    """Build authorization URL for Google OAuth."""
    client_id = (settings.google_client_id or "").strip()
    if not client_id:
        raise ValueError("google_not_configured")
    params = {
        "client_id": client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _sign(payload: str) -> str:
    key = (settings.secret_key or "dev").encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def dump_oauth_cookie(code_verifier: str, nonce: str, next_path: str) -> str:
    raw = json.dumps(
        {"v": code_verifier, "n": nonce, "next": next_path},
        separators=(",", ":"),
    )
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    return f"{_sign(encoded)}.{encoded}"


def load_oauth_cookie(value: Optional[str]) -> Optional[Dict[str, str]]:
    if not value or "." not in value:
        return None
    sig, encoded = value.split(".", 1)
    if not hmac.compare_digest(sig, _sign(encoded)):
        return None
    try:
        raw = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("v") or not data.get("n"):
        return None
    return data


async def exchange_code(code: str, code_verifier: str) -> Dict[str, Any]:
    client_id = (settings.google_client_id or "").strip()
    client_secret = (settings.google_client_secret or "").strip()
    if not client_id or not client_secret:
        raise ValueError("google_failed")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
        )
    if response.status_code >= 400:
        raise ValueError("google_failed")
    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise ValueError("google_failed")
    return payload


async def fetch_userinfo(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise ValueError("google_failed")
    profile = response.json()
    email = (profile.get("email") or "").strip().lower()
    sub = profile.get("sub")
    verified = profile.get("email_verified")
    if verified is True or verified == "true":
        email_verified = True
    else:
        email_verified = False
    if not email or not sub or not email_verified:
        raise ValueError("google_failed")
    return {"sub": str(sub), "email": email}

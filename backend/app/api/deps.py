"""
FastAPI authentication dependencies and security enforcement.
"""

from typing import Tuple, Dict, Any
from fastapi import Request, HTTPException, status
from app.config.settings import settings
from app.auth.service import auth_service


async def enforce_origin_header(request: Request):
    """
    Enforce Origin header check on non-GET requests according to docs/api.md Section 1.1.
    Prevents CSRF attacks when using HttpOnly cookie authentication.
    """
    if request.method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        if not origin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"type": "bad_origin", "message": "Missing Origin header."}}
            )

        clean_origin = origin.rstrip("/")
        allowed_origins = [o.rstrip("/") for o in settings.cors_origins]

        if clean_origin not in allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"type": "bad_origin", "message": "Origin not allowed."}}
            )


async def get_current_user(request: Request) -> Tuple[Dict[str, Any], float]:
    """
    FastAPI dependency to authenticate requests via server-side session cookie __Host-sid.
    Returns Tuple[user_dict, session_age_minutes].
    Raises HTTP 401 not_authenticated if invalid or expired.
    """
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if not cookie_token:
        # Fallback for dev/test header if needed
        cookie_token = request.headers.get("X-Auth-Session-Token")

    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "not_authenticated", "message": "Authentication required."}}
        )

    auth_result = auth_service.validate_auth_session(cookie_token)
    if not auth_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "not_authenticated", "message": "Session expired or invalid."}}
        )

    return auth_result

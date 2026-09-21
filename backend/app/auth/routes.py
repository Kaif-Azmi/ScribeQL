"""
Authentication and account management endpoints for ScribeQL.
Matches specification in docs/api.md Sections 3.5 & 3.6.
"""

from typing import Any, Dict, Tuple
import secrets
from fastapi import APIRouter, Response, Request, Depends, status, Query
from fastapi.responses import JSONResponse, RedirectResponse
from app.config.settings import settings
from app.api.deps import enforce_origin_header, get_current_user
from app.auth.schemas import (
    SignUpRequest,
    VerifyTokenRequest,
    ResendVerificationRequest,
    SignInRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    DeleteAccountRequest,
)
from app.auth.service import auth_service
from app.auth.google import (
    OAUTH_COOKIE,
    OAUTH_COOKIE_MAX_AGE,
    dump_oauth_cookie,
    exchange_code,
    fetch_userinfo,
    generate_pkce_pair,
    get_google_auth_url,
    load_oauth_cookie,
)

auth_router = APIRouter()


def _set_auth_cookie(response: Response, raw_token: str):
    cookie_name = settings.auth_cookie_name
    # __Host- prefix cookies are rejected unless Secure and Path=/
    secure = True if cookie_name.startswith("__Host-") else settings.auth_cookie_secure
    response.set_cookie(
        key=cookie_name,
        value=raw_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=7 * 86400,
        path="/"
    )


def _clear_auth_cookie(response: Response):
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/"
    )


# --- SIGN UP ---
@auth_router.post("/auth/signup", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(enforce_origin_header)])
async def signup(req: SignUpRequest):
    auth_service.signup(req.email, req.password)
    return {"status": "verification_sent"}


# --- VERIFY ---
@auth_router.post("/auth/verify", dependencies=[Depends(enforce_origin_header)])
async def verify_email(req: VerifyTokenRequest, response: Response):
    try:
        user_dict, session_token = auth_service.verify_email(req.token)
        _set_auth_cookie(response, session_token)
        return {"user": user_dict}
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "invalid_or_expired_token", "message": "This link has expired or was already used."}}
        )


# --- RESEND VERIFICATION ---
@auth_router.post("/auth/resend-verification", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(enforce_origin_header)])
async def resend_verification(req: ResendVerificationRequest):
    return {"status": "verification_sent"}


# --- SIGN IN ---
@auth_router.post("/auth/signin", dependencies=[Depends(enforce_origin_header)])
async def signin(req: SignInRequest, response: Response):
    try:
        user_dict, session_token = auth_service.signin(req.email, req.password)
        _set_auth_cookie(response, session_token)
        return {"user": user_dict}
    except ValueError as err:
        err_code = str(err)
        if err_code == "email_not_verified":
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": {"type": "email_not_verified", "message": "Check your inbox to verify this account."}}
            )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": {"type": "invalid_credentials", "message": "Invalid email or password."}}
        )


# --- SIGN OUT ---
@auth_router.post("/auth/signout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(enforce_origin_header)])
async def signout(request: Request, response: Response):
    token = request.cookies.get(settings.auth_cookie_name) or request.headers.get("X-Auth-Session-Token")
    if token:
        auth_service.signout(token)
    _clear_auth_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- FORGOT PASSWORD ---
@auth_router.post("/auth/forgot-password", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(enforce_origin_header)])
async def forgot_password(req: ForgotPasswordRequest):
    auth_service.forgot_password(req.email)
    return {"status": "reset_link_sent"}


# --- RESET PASSWORD ---
@auth_router.post("/auth/reset-password", dependencies=[Depends(enforce_origin_header)])
async def reset_password(req: ResetPasswordRequest):
    try:
        auth_service.reset_password(req.token, req.new_password)
        return {"status": "password_updated"}
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "invalid_or_expired_token", "message": "This link has expired or was already used."}}
        )


def safe_next(value: str | None, default: str = "/start") -> str:
    """Reject open redirects. Client-side next sanitizing is UX only."""
    if not value:
        return default
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return default
    if "\\" in value or "://" in value:
        return default
    return value


def frontend_redirect(path: str) -> RedirectResponse:
    origin = (settings.frontend_origin or "").rstrip("/")
    location = f"{origin}{path}" if origin else path
    return RedirectResponse(url=location, status_code=status.HTTP_302_FOUND)


def _oauth_cookie_kwargs() -> dict:
    cookie_secure = True if settings.app_env != "development" else False
    return {
        "key": OAUTH_COOKIE,
        "httponly": True,
        "secure": cookie_secure,
        "samesite": "lax",
        "path": "/",
    }


# --- GOOGLE OAUTH START ---
@auth_router.get("/auth/google/start")
async def google_start(next_path: str = Query("/start", alias="next")):
    target_next = safe_next(next_path)
    if not (settings.google_client_id or "").strip() or not (settings.google_client_secret or "").strip():
        return frontend_redirect("/signin?error=google_failed")
    code_verifier, code_challenge = generate_pkce_pair()
    nonce = secrets.token_urlsafe(16)
    try:
        auth_url = get_google_auth_url(state=nonce, code_challenge=code_challenge)
    except ValueError:
        return frontend_redirect("/signin?error=google_failed")
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        value=dump_oauth_cookie(code_verifier, nonce, target_next),
        max_age=OAUTH_COOKIE_MAX_AGE,
        **_oauth_cookie_kwargs(),
    )
    return response


# --- GOOGLE OAUTH CALLBACK ---
@auth_router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
):
    failed = frontend_redirect("/signin?error=google_failed")
    failed.delete_cookie(key=OAUTH_COOKIE, path="/")
    if error or not code or not state:
        return failed

    blob = load_oauth_cookie(request.cookies.get(OAUTH_COOKIE))
    if not blob or blob.get("n") != state:
        return failed

    try:
        tokens = await exchange_code(code, blob["v"])
        profile = await fetch_userinfo(tokens["access_token"])
        _user, session_token = auth_service.signin_google(profile["sub"], profile["email"])
    except Exception:
        return failed

    target_next = safe_next(blob.get("next"))
    response = frontend_redirect(target_next)
    _set_auth_cookie(response, session_token)
    response.delete_cookie(key=OAUTH_COOKIE, path="/")
    return response


# --- GET /me ---
@auth_router.get("/me")
async def get_me(current_user: Tuple[Dict[str, Any], float] = Depends(get_current_user)):
    user_dict, _ = current_user
    # Standard initial daily usage
    usage = {
        "queries": {"limit": 20, "used": 0, "remaining": 20},
        "uploads": {"limit": 3, "used": 0, "remaining": 3},
        "resets_at": "2026-09-20T00:00:00Z"
    }
    return {
        "user": user_dict,
        "usage": usage
    }


# --- DELETE /me ---
@auth_router.delete("/me", dependencies=[Depends(enforce_origin_header)])
async def delete_account(
    req: DeleteAccountRequest,
    response: Response,
    current_user: Tuple[Dict[str, Any], float] = Depends(get_current_user)
):
    user_dict, session_age_minutes = current_user

    # Require re-auth if session is older than 15 minutes
    if session_age_minutes >= 15.0:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": {"type": "reauth_required", "message": "Re-authentication required before account deletion."}}
        )

    auth_service.delete_account(user_dict["id"])
    _clear_auth_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

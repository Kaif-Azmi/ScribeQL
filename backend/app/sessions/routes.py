"""
Query session HTTP endpoints for ScribeQL.
Matches contract in docs/api.md Sections 3.1 and 3.7.
"""

from typing import Tuple, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Query, status
from fastapi.responses import JSONResponse
from app.api.deps import enforce_origin_header, get_current_user
from app.sessions.schemas import CreateSessionRequest, CreateSessionResponse, RecoverSessionResponse
from app.sessions.service import query_session_service

session_router = APIRouter()


def _format_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d%T%H:%M:%SZ") if dt else ""


# --- POST /session ---
@session_router.post("/session", dependencies=[Depends(enforce_origin_header)])
async def create_session(
    req: CreateSessionRequest,
    current_user: Tuple[Dict[str, Any], float] = Depends(get_current_user)
):
    user_dict, _ = current_user
    sess = query_session_service.create_session(user_dict["id"], req.mode)

    expires_iso = sess["expires_at"].isoformat() if isinstance(sess["expires_at"], datetime) else str(sess["expires_at"])

    return CreateSessionResponse(
        session_id=sess["session_id"],
        mode=sess["mode"],
        dialect=sess["dialect"],
        expires_at=expires_iso
    )


# --- GET /session ---
@session_router.get("/session")
async def recover_session(
    mode: str = Query(..., description="Session mode to recover ('demo' or 'custom')"),
    current_user: Tuple[Dict[str, Any], float] = Depends(get_current_user)
):
    user_dict, _ = current_user
    clean_mode = mode.lower().strip()
    if clean_mode not in ("demo", "custom"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "invalid_request", "message": "Invalid mode parameter."}}
        )

    sess = query_session_service.recover_session(user_dict["id"], clean_mode)
    if not sess:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"type": "session_not_found", "message": "Session does not exist or has expired."}}
        )

    expires_iso = sess["expires_at"].isoformat() if isinstance(sess["expires_at"], datetime) else str(sess["expires_at"])

    return RecoverSessionResponse(
        session_id=sess["session_id"],
        mode=sess["mode"],
        dialect=sess["dialect"],
        has_schema=sess["has_schema"],
        expires_at=expires_iso
    )

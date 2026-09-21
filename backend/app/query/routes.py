"""POST /query — docs/api.md Section 3.3."""

from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import enforce_origin_header, get_current_user
from app.config.settings import settings
from app.query.pipeline import run_query_pipeline
from app.sessions.service import query_session_service

query_router = APIRouter()

_in_flight: set[str] = set()


class QueryRequest(BaseModel):
    session_id: str
    question: str = Field(..., min_length=1)


@query_router.post("/query", dependencies=[Depends(enforce_origin_header)])
async def submit_query(
    req: QueryRequest,
    current_user: Tuple[Dict[str, Any], float] = Depends(get_current_user),
):
    user_dict, _ = current_user
    question = req.question.strip()
    if not question:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "invalid_request", "message": "Question is required."}},
        )
    if len(question) > settings.max_question_chars:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": {"type": "question_too_long", "message": "Question exceeds the length cap."}},
        )

    sess = query_session_service.get_session(req.session_id, user_dict["id"])
    if not sess:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"type": "session_not_found", "message": "Session does not exist or has expired."}},
        )
    if sess["mode"] == "custom" and not sess.get("has_schema"):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"type": "schema_required", "message": "Upload a schema before asking a question."}},
        )

    if req.session_id in _in_flight:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"type": "query_in_progress", "message": "A query is already running on this session."}},
        )

    _in_flight.add(req.session_id)
    try:
        result = await run_query_pipeline(sess, question)
    finally:
        _in_flight.discard(req.session_id)

    http_status = status.HTTP_200_OK
    if result["status"] == "llm_error":
        http_status = status.HTTP_502_BAD_GATEWAY
        return JSONResponse(status_code=http_status, content=result)
    return result

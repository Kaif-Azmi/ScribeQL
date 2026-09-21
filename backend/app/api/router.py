from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from typing import Dict, Any
from app.auth.routes import auth_router
from app.sessions.routes import session_router
from app.schema.routes import schema_router
from app.query.routes import query_router
from app.db.session import check_db_health

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(session_router)
api_router.include_router(schema_router)
api_router.include_router(query_router)


@api_router.get("/health")
async def health_check() -> Any:
    """Liveness and dependency check according to docs/api.md Section 3.4."""
    if not check_db_health():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "type": "dependency_unavailable",
                    "message": "Database is unreachable."
                }
            }
        )
    return {"status": "ok"}



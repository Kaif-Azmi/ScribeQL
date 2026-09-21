import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.settings import settings
from app.api.router import api_router


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title="ScribeQL API",
    description="Natural-language-to-SQL API with RAG and SQL safety pipeline",
    version="0.1.0",
)

# CORS middleware for development and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)

# Mount the main API router under /api
app.include_router(api_router, prefix="/api")

# Exception handlers for docs/api.md Section 1.2 error envelope
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        err_obj = exc.detail["error"]
    else:
        err_obj = {"type": "http_error", "message": str(exc.detail)}

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": err_obj,
            "detail": {"error": err_obj}  # Backwards compatibility
        }
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []) if l != "body")
        msg = err.get("msg", "Invalid value")
        messages.append(f"{loc}: {msg}" if loc else msg)
    combined_msg = "; ".join(messages) if messages else "Validation failed for request parameters."

    err_obj = {
        "type": "invalid_request",
        "message": combined_msg
    }
    # docs/api.md Section 1.3 maps failed validation to 400
    return JSONResponse(
        status_code=400,
        content={
            "error": err_obj,
            "detail": {"error": err_obj}
        }
    )


# Convenience root health alias
@app.get("/health")
async def root_health():
    from app.api.router import health_check
    return await health_check()


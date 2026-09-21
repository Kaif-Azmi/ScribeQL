"""
HTTP Endpoints for Custom Schema Upload (POST /schema/upload).
Matches contract specified in docs/api.md Section 3.2.
"""

import json
import secrets
from typing import Tuple, Dict, Any, Optional
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.deps import enforce_origin_header, get_current_user
from app.sessions.service import query_session_service, DialectLockedError, WrongSessionModeError
from app.schema.parser import (
    parse_ddl_to_catalog,
    DDLParseError,
    ReservedNamespaceError,
    SchemaTooLargeError,
    InvalidHintsError,
)
from app.schema.storage import schema_storage_service

schema_router = APIRouter()

MAX_FILE_SIZE_BYTES = 200 * 1024  # 200 KB cap
MAX_HINTS_SIZE_BYTES = 2 * 1024   # 2 KB cap


@schema_router.post("/schema/upload", dependencies=[Depends(enforce_origin_header)])
async def upload_custom_schema(
    session_id: str = Form(...),
    dialect: str = Form(...),
    file: UploadFile = File(...),
    hints: Optional[str] = Form(None),
    current_user: Tuple[Dict[str, Any], float] = Depends(get_current_user)
):
    user_dict, _ = current_user
    clean_dialect = dialect.lower().strip()

    # 1. Validate dialect
    if clean_dialect not in ("postgres", "mysql"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "invalid_request", "message": "Dialect must be 'postgres' or 'mysql'."}}
        )

    # 2. Validate file extension
    filename = file.filename or ""
    if not (filename.lower().endswith(".sql") or filename.lower().endswith(".txt")):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "invalid_request", "message": "File must be a .sql or .txt file."}}
        )

    # 3. Read file content & validate size
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={"error": {"type": "file_too_large", "message": "File exceeds the 200 KB cap."}}
        )

    try:
        ddl_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            ddl_text = content_bytes.decode("latin-1")
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": {"type": "invalid_request", "message": "Could not decode text file."}}
            )

    # 4. Validate query session & mode
    sess = query_session_service.get_session(session_id, user_dict["id"])
    if not sess:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"type": "session_not_found", "message": "Session does not exist or has expired."}}
        )

    if sess["mode"] != "custom":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"type": "wrong_session_mode", "message": "Schema upload is only allowed for custom sessions."}}
        )

    # Check if session dialect is locked to a different dialect
    current_locked_dialect = sess.get("dialect")
    if current_locked_dialect is not None and current_locked_dialect.lower() != clean_dialect:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"type": "dialect_locked", "message": "The session dialect is locked. Create a new session to switch dialect."}}
        )

    # 5. Validate hints if provided
    hints_dict: Optional[Dict[str, Any]] = None
    if hints and hints.strip():
        if len(hints.encode("utf-8")) > MAX_HINTS_SIZE_BYTES:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": {"type": "invalid_request", "message": "Hints text must be under 2 KB."}}
            )
        try:
            hints_dict = json.loads(hints)
            if not isinstance(hints_dict, dict):
                raise ValueError("Hints must be a JSON object.")
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": {"type": "invalid_request", "message": "Check your hints: malformed JSON."}}
            )

    # 6. Parse DDL into SchemaCatalog (never executed)
    try:
        catalog = parse_ddl_to_catalog(ddl_text, dialect=clean_dialect, hints=hints_dict)
    except DDLParseError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "ddl_parse_error", "message": str(exc)}}
        )
    except ReservedNamespaceError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "reserved_namespace", "message": str(exc)}}
        )
    except SchemaTooLargeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "schema_too_large", "message": str(exc)}}
        )
    except InvalidHintsError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"type": "invalid_request", "message": str(exc)}}
        )

    # 7. Persist catalog & lock session dialect
    schema_id = f"sch_{secrets.token_hex(12)}"
    schema_storage_service.save_catalog(schema_id, catalog)

    try:
        query_session_service.lock_custom_dialect(session_id, user_dict["id"], clean_dialect, schema_id)
    except DialectLockedError:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"type": "dialect_locked", "message": "The session dialect is locked. Create a new session to switch dialect."}}
        )

    # 8. Build response
    tables_summary = [
        {"name": tbl.name, "column_count": len(tbl.columns)}
        for tbl in catalog.tables.values()
    ]

    return {
        "schema_id": schema_id,
        "dialect": clean_dialect,
        "tables": tables_summary,
        "fk_count": catalog.total_foreign_keys(),
        "warnings": catalog.warnings
    }

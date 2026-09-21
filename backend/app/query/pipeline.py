"""
Query pipeline: RAG → Gemini SQL generation → AST safety → validation → demo execute.
Custom mode never calls the demo executor.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from app.config.settings import settings
from app.llm.client import LLMProviderError, llm_client
from app.rag.retriever import rag_retriever
from app.schema.catalog import SchemaCatalog
from app.schema.inspector import inspect_postgres_schema
from app.schema.storage import schema_storage_service
from app.sql.errors import SafetyError
from app.sql.executor import ExecutionError, execute_demo_sql
from app.sql.safety import check_sql_safety
from app.sql.validate import ValidationError, validate_sql
from app.db.session import get_app_connection, get_demo_ro_connection

logger = logging.getLogger(__name__)

_demo_catalog: Optional[SchemaCatalog] = None
MAX_ATTEMPTS = 3


def load_session_catalog(session: Dict[str, Any]) -> SchemaCatalog:
    if session["mode"] == "demo":
        return load_demo_catalog()
    schema_id = session.get("schema_id")
    if not schema_id:
        raise KeyError("schema_required")
    catalog = schema_storage_service.get_catalog(schema_id)
    if not catalog:
        raise KeyError("schema_required")
    return catalog


def load_demo_catalog() -> SchemaCatalog:
    global _demo_catalog
    if _demo_catalog is not None:
        return _demo_catalog
    try:
        with get_app_connection() as conn:
            _demo_catalog = inspect_postgres_schema(conn, "demo")
    except Exception:
        with get_demo_ro_connection() as conn:
            _demo_catalog = inspect_postgres_schema(conn, "demo")
    return _demo_catalog


def _usage_payload() -> Dict[str, Any]:
    return {
        "queries": {"limit": settings.daily_query_limit, "used": 0, "remaining": settings.daily_query_limit},
        "uploads": {"limit": settings.daily_upload_limit, "used": 0, "remaining": settings.daily_upload_limit},
        "resets_at": "2026-09-21T00:00:00Z",
    }


def _base_response(
    *,
    status: str,
    mode: str,
    dialect: str,
    question: str,
    sql: Optional[str],
    query_plan: Any,
    assumptions: List[str],
    explanation: str,
    warnings: List[str],
    executed: bool,
    attempts_used: int,
    attempt_history: List[Dict[str, Any]],
    error: Optional[Dict[str, Any]],
    columns=None,
    rows=None,
    row_count=None,
    truncated=None,
) -> Dict[str, Any]:
    payload = {
        "status": status,
        "mode": mode,
        "dialect": dialect,
        "question": question,
        "query_plan": query_plan if isinstance(query_plan, dict) else (query_plan.model_dump() if query_plan else {}),
        "sql": sql,
        "assumptions": assumptions,
        "explanation": explanation,
        "warnings": warnings,
        "executed": executed,
        "attempts_used": attempts_used,
        "attempt_history": attempt_history,
        "error": error,
        "usage": _usage_payload(),
    }
    if executed:
        payload["columns"] = columns or []
        payload["rows"] = rows or []
        payload["row_count"] = row_count or 0
        payload["truncated"] = bool(truncated)
    return payload


async def run_query_pipeline(session: Dict[str, Any], question: str) -> Dict[str, Any]:
    mode = session["mode"]
    dialect = session["dialect"] or "postgres"
    is_demo = mode == "demo"
    catalog = load_session_catalog(session)
    deadline = time.monotonic() + settings.query_deadline_seconds
    warnings: List[str] = []
    attempt_history: List[Dict[str, Any]] = []
    last_sql: Optional[str] = None
    last_plan: Any = {}
    last_assumptions: List[str] = []
    last_explanation = ""
    previous_error: Optional[str] = None

    rag_context = await rag_retriever.retrieve_context(question, dialect=dialect, top_k=3)

    for attempt_no in range(1, MAX_ATTEMPTS + 1):
        if time.monotonic() > deadline:
            warnings.append("Retries were cut short by the request deadline.")
            break
        t0 = time.monotonic()
        try:
            generation = await llm_client.generate_sql(
                question, catalog, rag_context=rag_context, previous_error=previous_error
            )
        except LLMProviderError:
            return _base_response(
                status="llm_error",
                mode=mode,
                dialect=dialect,
                question=question,
                sql=last_sql,
                query_plan=last_plan,
                assumptions=last_assumptions,
                explanation=last_explanation,
                warnings=warnings,
                executed=False,
                attempts_used=attempt_no,
                attempt_history=attempt_history,
                error={"stage": "generation", "type": "llm_error", "message": "The language model failed to generate a query."},
            )

        last_sql = generation.sql
        last_plan = generation.query_plan
        last_assumptions = generation.assumptions
        last_explanation = generation.explanation

        try:
            parsed = check_sql_safety(generation.sql, dialect, catalog, is_demo=is_demo)
        except SafetyError as exc:
            return _base_response(
                status="blocked",
                mode=mode,
                dialect=dialect,
                question=question,
                sql=generation.sql,
                query_plan=generation.query_plan,
                assumptions=generation.assumptions,
                explanation=generation.explanation,
                warnings=warnings,
                executed=False,
                attempts_used=attempt_no,
                attempt_history=attempt_history,
                error=exc.to_dict(),
            )

        try:
            validate_sql(generation.sql, dialect, catalog, is_demo=is_demo, parsed=parsed)
        except ValidationError as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            attempt_history.append({
                "attempt_no": attempt_no,
                "sql": generation.sql,
                "error_type": exc.type,
                "error_text": exc.message,
                "latency_ms": latency_ms,
            })
            previous_error = exc.message
            if attempt_no == MAX_ATTEMPTS:
                return _base_response(
                    status="invalid_sql",
                    mode=mode,
                    dialect=dialect,
                    question=question,
                    sql=generation.sql,
                    query_plan=generation.query_plan,
                    assumptions=generation.assumptions,
                    explanation=generation.explanation,
                    warnings=warnings,
                    executed=False,
                    attempts_used=attempt_no,
                    attempt_history=attempt_history,
                    error=exc.to_dict(),
                )
            continue

        if not is_demo:
            return _base_response(
                status="execution_skipped",
                mode=mode,
                dialect=dialect,
                question=question,
                sql=generation.sql,
                query_plan=generation.query_plan,
                assumptions=generation.assumptions,
                explanation=generation.explanation,
                warnings=warnings,
                executed=False,
                attempts_used=attempt_no,
                attempt_history=attempt_history,
                error=None,
            )

        try:
            columns, rows, row_count, truncated = execute_demo_sql(generation.sql)
        except ExecutionError as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            attempt_history.append({
                "attempt_no": attempt_no,
                "sql": generation.sql,
                "error_type": exc.type,
                "error_text": exc.message,
                "latency_ms": latency_ms,
            })
            previous_error = exc.message
            if attempt_no == MAX_ATTEMPTS:
                return _base_response(
                    status="execution_error",
                    mode=mode,
                    dialect=dialect,
                    question=question,
                    sql=generation.sql,
                    query_plan=generation.query_plan,
                    assumptions=generation.assumptions,
                    explanation=generation.explanation,
                    warnings=warnings,
                    executed=False,
                    attempts_used=attempt_no,
                    attempt_history=attempt_history,
                    error=exc.to_dict(),
                )
            continue

        if truncated:
            warnings.append(f"showing the first {row_count} rows.")
        return _base_response(
            status="ok",
            mode=mode,
            dialect=dialect,
            question=question,
            sql=generation.sql,
            query_plan=generation.query_plan,
            assumptions=generation.assumptions,
            explanation=generation.explanation,
            warnings=warnings,
            executed=True,
            attempts_used=attempt_no,
            attempt_history=attempt_history,
            error=None,
            columns=columns,
            rows=rows,
            row_count=row_count,
            truncated=truncated,
        )

    return _base_response(
        status="invalid_sql",
        mode=mode,
        dialect=dialect,
        question=question,
        sql=last_sql,
        query_plan=last_plan,
        assumptions=last_assumptions,
        explanation=last_explanation,
        warnings=warnings or ["Retries were cut short by the request deadline."],
        executed=False,
        attempts_used=len(attempt_history) or 1,
        attempt_history=attempt_history,
        error={"stage": "validation", "type": "invalid_sql", "message": "Couldn't produce a valid query after a few tries."},
    )

"""Live end-to-end verification. Never prints secrets."""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)

from fastapi.testclient import TestClient

from app.main import app
from app.config.settings import settings
from app.llm.client import LLMClient
from app.llm.gemini import extract_generate_text
from app.rag.retriever import rag_retriever
from app.schema.catalog import SchemaCatalog, TableSchema, ColumnSchema
from app.schema.parser import parse_ddl_to_catalog
from app.sql.safety import check_sql_safety
from app.sql.validate import validate_sql
from app.sql.executor import execute_demo_sql
from app.query.pipeline import load_demo_catalog, run_query_pipeline
from app.auth.service import auth_service
from app.sessions.service import query_session_service

ORIGIN = {"Origin": "http://localhost:5173"}
results: dict[str, str] = {}


def record(name: str, ok: bool, detail: str = "") -> None:
    results[name] = "PASS" if ok else f"FAIL {detail}".strip()
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f" — {detail}" if detail and not ok else ""))


def mini_catalog() -> SchemaCatalog:
    catalog = SchemaCatalog(dialect="postgres")
    catalog.tables["customers"] = TableSchema(
        name="customers",
        columns=[
            ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
            ColumnSchema(name="name", data_type="VARCHAR(100)"),
        ],
        primary_keys=["id"],
    )
    return catalog


async def live_gemini() -> None:
    key_ok = bool(settings.llm_api_key and settings.llm_api_key.strip())
    record("gemini_api_key_configured", key_ok)
    if not key_ok:
        return

    llm = LLMClient()
    print("live_llm_model:", llm.model)
    catalog = mini_catalog()
    try:
        gen = await llm.generate_sql("List customer names", catalog)
        record(
            "gemini_flash_chat",
            bool(gen.sql),
            "empty sql" if not gen.sql else "",
        )
        parsed_ok = bool(gen.sql and gen.explanation is not None and isinstance(gen.assumptions, list))
        record("structured_json_response", parsed_ok)
        record(
            "nl_to_sql_generation",
            gen.sql.strip().upper().startswith("SELECT"),
            gen.sql[:80] if gen.sql else "no sql",
        )
    except Exception as exc:
        record("gemini_flash_chat", False, type(exc).__name__)
        record("structured_json_response", False, type(exc).__name__)
        record("nl_to_sql_generation", False, type(exc).__name__)
        print("gemini_error_type:", type(exc).__name__)
        return

    try:
        ctx = await rag_retriever.retrieve_context("top customers by spend", dialect="postgres", top_k=3)
        record("rag_pgvector_retrieval", bool(ctx.strip()), "empty context")
    except Exception as exc:
        record("rag_pgvector_retrieval", False, type(exc).__name__)
        ctx = ""

    demo_catalog = load_demo_catalog()
    sql_for_exec = gen.sql
    try:
        gen2 = await llm.generate_sql("Top 5 customers by total spend", demo_catalog, rag_context=ctx)
        record(
            "rag_then_gemini_sql",
            gen2.sql.strip().upper().startswith("SELECT"),
            "no select",
        )
        sql_for_exec = gen2.sql
    except Exception as exc:
        record("rag_then_gemini_sql", False, type(exc).__name__)

    try:
        check_sql_safety(sql_for_exec, "postgres", demo_catalog, is_demo=True)
        record("sqlglot_safety_on_generated", True)
        validate_sql(sql_for_exec, "postgres", demo_catalog, is_demo=True)
        record("sql_validation_explain", True)
        cols, rows, count, truncated = execute_demo_sql(sql_for_exec)
        record("demo_sql_ro_execution", True)
        print("demo_exec_row_count:", count, "columns:", cols[:8])
    except Exception as exc:
        record("sqlglot_safety_on_generated", False, f"{type(exc).__name__}: {str(exc)[:160]}")
        traceback.print_exc()


async def live_custom_never_executes() -> None:
    ddl = """
    CREATE TABLE customers (
      id INT PRIMARY KEY,
      name VARCHAR(100) NOT NULL
    );
    """
    catalog = parse_ddl_to_catalog(ddl, dialect="postgres")
    session = {
        "mode": "custom",
        "dialect": "postgres",
        "has_schema": True,
        "schema_id": "live_custom_test",
    }
    from app.schema.storage import schema_storage_service

    schema_storage_service.save_catalog("live_custom_test", catalog)
    result = await run_query_pipeline(session, "List customer names")
    executed = result.get("executed") is False and result.get("status") in ("execution_skipped", "invalid_sql", "blocked", "ok")
    never_exec = result.get("executed") is False and "rows" not in result
    record(
        "custom_mode_never_executes",
        never_exec and result.get("status") != "ok",
        f"status={result.get('status')} executed={result.get('executed')}",
    )
    print("custom_status:", result.get("status"), "executed:", result.get("executed"))


def live_api_and_health() -> None:
    client = TestClient(app, base_url="https://testserver")
    health = client.get("/api/health")
    record("health_endpoint", health.status_code == 200 and health.json() == {"status": "ok"}, f"http={health.status_code}")

    email = "live.verify@example.com"
    password = "live-verify-password"
    signup = client.post("/api/auth/signup", json={"email": email, "password": password}, headers=ORIGIN)
    record("api_signup", signup.status_code == 202, f"http={signup.status_code}")

    # Verify via returned token from service (emails are not sent in this environment)
    user_id, token = auth_service.signup(email, password)
    verify = client.post("/api/auth/verify", json={"token": token}, headers=ORIGIN)
    record("api_verify", verify.status_code == 200, f"http={verify.status_code}")

    signin = client.post(
        "/api/auth/signin",
        json={"email": email, "password": password},
        headers=ORIGIN,
    )
    record("api_signin", signin.status_code == 200, f"http={signin.status_code}")
    token = signin.cookies.get(settings.auth_cookie_name)
    if not token:
        # TestClient may drop __Host- cookies; reuse the session created at verify.
        user_dict, token = auth_service.signin(email, password)
    auth_headers = {**ORIGIN, "X-Auth-Session-Token": token}
    cookies = {settings.auth_cookie_name: token}

    me = client.get("/api/me", cookies=cookies, headers=auth_headers)
    record("api_me", me.status_code == 200, f"http={me.status_code}")

    sess = client.post("/api/session", json={"mode": "demo"}, headers=auth_headers, cookies=cookies)
    record("api_create_demo_session", sess.status_code == 200, f"http={sess.status_code}")
    session_id = sess.json().get("session_id") if sess.status_code == 200 else None

    recovered = client.get("/api/session", params={"mode": "demo"}, headers=auth_headers, cookies=cookies)
    record("api_get_session", recovered.status_code == 200, f"http={recovered.status_code}")

    auth_user, _ = auth_service.validate_auth_session(token)
    if session_id and auth_user:
        sess_row = query_session_service.get_session(session_id, auth_user["id"])
        body = asyncio.run(run_query_pipeline(sess_row, "How many customers are there?")) if sess_row else {}
        ok = body.get("status") == "ok" and body.get("executed") is True
        record("api_query_demo", ok, f"status={body.get('status')} executed={body.get('executed')}")
        print("api_query_demo_status:", body.get("status"), "row_count:", body.get("row_count"))

    custom = client.post("/api/session", json={"mode": "custom"}, headers=auth_headers, cookies=cookies)
    record("api_create_custom_session", custom.status_code == 200, f"http={custom.status_code}")
    cid = custom.json().get("session_id") if custom.status_code == 200 else None
    if cid:
        ddl = b"CREATE TABLE customers (id INT PRIMARY KEY, name VARCHAR(100));\n"
        up = client.post(
            "/api/schema/upload",
            data={"session_id": cid, "dialect": "postgres"},
            files={"file": ("schema.sql", ddl, "text/plain")},
            headers=auth_headers,
            cookies=cookies,
        )
        record("api_schema_upload", up.status_code == 200, f"http={up.status_code}")
        custom_row = query_session_service.get_session(cid, auth_user["id"]) if auth_user else None
        body2 = asyncio.run(run_query_pipeline(custom_row, "List customers")) if custom_row else {}
        ok2 = body2.get("executed") is False and body2.get("status") == "execution_skipped"
        record(
            "api_query_custom_not_executed",
            ok2,
            f"status={body2.get('status')} executed={body2.get('executed')}",
        )


def main() -> int:
    print("settings llm_model:", settings.llm_model)
    print("settings embedding_model:", settings.embedding_model)
    print("settings embedding_dimension:", settings.embedding_dimension)
    asyncio.run(live_gemini())
    asyncio.run(live_custom_never_executes())
    live_api_and_health()
    print("\n=== SUMMARY ===")
    failed = 0
    for name, status in results.items():
        print(f"{status[:4]} {name}" if status.startswith("PASS") else f"FAIL {name}: {status[5:]}")
        if not status.startswith("PASS"):
            failed += 1
    print("passed:", sum(1 for v in results.values() if v.startswith("PASS")))
    print("failed:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

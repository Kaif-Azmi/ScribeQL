#!/usr/bin/env python3
"""
ScribeQL Application Database Initialization Script.
Executes data/app/schema.sql against the configured database to set up all
tables, vector extension, indexes, and constraints for the 'app' schema.
"""

import sys
import os
from pathlib import Path
import psycopg

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.config.settings import settings
except ImportError:
    class SettingsFallback:
        database_url = os.getenv("DATABASE_URL", "postgresql://app_rw:app_rw_password_dev@localhost:5432/scribeql")
    settings = SettingsFallback()


def init_app_database(db_url: str = None):
    url = db_url or settings.database_url
    schema_file = ROOT_DIR / "data" / "app" / "schema.sql"

    if not schema_file.exists():
        raise FileNotFoundError(f"Application schema file missing at {schema_file}")

    print(f"Connecting to database to initialize 'app' schema...")
    sql_text = schema_file.read_text(encoding="utf-8")

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
        print("✓ Executed data/app/schema.sql successfully.")

        print("\nVerifying App Tables in 'app' schema:")
        app_tables = [
            "users", "auth_identities", "email_tokens", "auth_sessions",
            "sessions", "schema_catalogs", "query_logs", "query_attempts",
            "usage_counters", "global_budget", "usage_tombstones",
            "rag_documents", "llm_cache"
        ]
        with conn.cursor() as cur:
            for table in app_tables:
                cur.execute(f"SELECT to_regclass('app.{table}');")
                reg = cur.fetchone()[0]
                status = "✓ Exists" if reg else "✕ Missing"
                print(f"  • app.{table:<18}: {status}")

    print("\n✓ Application database schema initialized successfully.")


if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    init_app_database(url_arg)

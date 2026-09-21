#!/usr/bin/env python3
"""
ScribeQL Demo Database Seed Script
Executes demo/schema.sql and demo/seed.sql against the configured database,
then verifies table row counts.
"""

import sys
import os
from pathlib import Path
import psycopg

# Add project root and backend to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.config.settings import settings
except ImportError:
    class SettingsFallback:
        database_url = os.getenv("DATABASE_URL", "postgresql://app_rw:app_rw_password_dev@localhost:5432/scribeql")
        demo_database_url = os.getenv("DEMO_DATABASE_URL", "")
        admin_database_url = os.getenv("ADMIN_DATABASE_URL", "")
    settings = SettingsFallback()


def _host_only(url: str) -> str:
    """Return host/db without userinfo so credentials are never printed."""
    try:
        after = url.split("://", 1)[1]
        if "@" in after:
            after = after.split("@", 1)[1]
        return after.split("?")[0]
    except Exception:
        return "(unparseable)"


def run_sql_file(conn, file_path: Path):
    print(f"Executing: {file_path.name}...")
    sql_text = file_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql_text)
    conn.commit()
    print(f"Completed: {file_path.name}")


def grant_demo_privileges(conn):
    """Tables created by the admin/owner must be explicitly granted to app_rw and sql_ro."""
    with conn.cursor() as cur:
        cur.execute("GRANT USAGE ON SCHEMA demo TO app_rw;")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA demo TO app_rw;")
        cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA demo TO app_rw;")
        cur.execute("GRANT USAGE ON SCHEMA demo TO sql_ro;")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA demo TO sql_ro;")
        cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA demo TO sql_ro;")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA demo GRANT SELECT ON TABLES TO sql_ro;")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA demo GRANT SELECT ON TABLES TO app_rw;")
    conn.commit()
    print("Granted SELECT on demo tables to sql_ro and app_rw.")


def seed_demo_database(db_url: str = None):
    # Prefer ADMIN_DATABASE_URL: app_rw has USAGE but not CREATE on the demo schema
    # when roles/schemas were provisioned by a database admin (e.g. Neon).
    url = (
        db_url
        or getattr(settings, "admin_database_url", None)
        or os.getenv("ADMIN_DATABASE_URL")
        or settings.database_url
    )
    print(f"Connecting to seed demo data at {_host_only(url)} ...")
    schema_file = ROOT_DIR / "data" / "demo" / "schema.sql"
    seed_file = ROOT_DIR / "data" / "demo" / "seed.sql"

    if not schema_file.exists() or not seed_file.exists():
        raise FileNotFoundError("Demo schema or seed SQL file missing.")

    demo_tables = [
        "categories", "products", "customers", "orders",
        "order_items", "payments", "shipments", "reviews"
    ]

    with psycopg.connect(url) as conn:
        run_sql_file(conn, schema_file)
        run_sql_file(conn, seed_file)
        grant_demo_privileges(conn)

        print("\nVerifying Demo Tables in 'demo' schema:")
        with conn.cursor() as cur:
            for table in demo_tables:
                cur.execute(f"SELECT COUNT(*) FROM demo.{table}")
                count = cur.fetchone()[0]
                print(f"  - demo.{table:<15}: {count} rows")

    demo_url = getattr(settings, "demo_database_url", None) or os.getenv("DEMO_DATABASE_URL")
    if demo_url:
        print("\nVerifying sql_ro can SELECT from demo...")
        with psycopg.connect(demo_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                print(f"  sql_ro user: {cur.fetchone()[0]}")
                for table in demo_tables:
                    cur.execute(f"SELECT COUNT(*) FROM demo.{table}")
                    print(f"  SELECT demo.{table:<15}: {cur.fetchone()[0]} rows")

    print("\nDemo database successfully initialized and seeded.")


if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    seed_demo_database(url_arg)

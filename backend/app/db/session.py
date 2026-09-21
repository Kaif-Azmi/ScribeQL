"""
Database connection layer for ScribeQL.
Manages connections for application read-write access (app_rw)
and demo execution read-only access (sql_ro).
"""

from contextlib import contextmanager
from typing import Generator
import psycopg
from psycopg.rows import dict_row
from app.config.settings import settings


@contextmanager
def get_app_connection() -> Generator[psycopg.Connection, None, None]:
    """Provide a connection for application read/write operations (app schema)."""
    conn = psycopg.connect(
        settings.database_url,
        autocommit=False
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_demo_ro_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Provide a connection for demo query execution (demo schema).
    Hardened with read-only transaction, statement timeout, and lock timeout.
    """
    conn = psycopg.connect(
        settings.demo_database_url,
        autocommit=False
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;")
            cur.execute("SET statement_timeout = '15s';")
            cur.execute("SET lock_timeout = '3s';")
        yield conn
        conn.rollback()  # Always rollback read-only execution
    finally:
        conn.close()


def check_db_health() -> bool:
    """Check if the primary PostgreSQL instance is reachable."""
    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone() is not None
    except Exception:
        return False

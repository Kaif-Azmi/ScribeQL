"""
Unit tests for Phase 8 — SQL Safety Layer.

Every rejection path and every allowed pattern has a dedicated test.
No database connection is required; all checks operate purely on AST.
"""

import pytest
from app.sql.safety import SQLSafetyChecker
from app.sql.errors import SafetyError
from app.schema.catalog import SchemaCatalog, TableSchema, ColumnSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_catalog(
    tables: list[str] | None = None,
    dialect: str = "postgres",
) -> SchemaCatalog:
    """Build a minimal SchemaCatalog for testing."""
    catalog = SchemaCatalog(dialect=dialect)
    for t in (tables or []):
        catalog.tables[t] = TableSchema(
            name=t,
            columns=[ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True)],
        )
    return catalog


checker = SQLSafetyChecker()

DEMO_CATALOG = make_catalog(["customers", "orders", "products", "categories", "order_items"])
EMPTY_CATALOG = make_catalog([])


def safe(sql: str, dialect: str = "postgres", catalog: SchemaCatalog | None = None, is_demo: bool = False):
    """Assert that a SQL string passes the safety check and return the AST."""
    c = catalog if catalog is not None else DEMO_CATALOG
    return checker.check(sql, dialect=dialect, catalog=c, is_demo=is_demo)


def blocked(sql: str, expected_type: str, dialect: str = "postgres", catalog: SchemaCatalog | None = None, is_demo: bool = False):
    """Assert that a SQL string raises SafetyError with the expected type."""
    c = catalog if catalog is not None else DEMO_CATALOG
    with pytest.raises(SafetyError) as exc_info:
        checker.check(sql, dialect=dialect, catalog=c, is_demo=is_demo)
    err = exc_info.value
    assert err.type == expected_type, (
        f"Expected SafetyError.type='{expected_type}' but got '{err.type}'. "
        f"Message: {err.message}"
    )
    assert err.stage == "safety"
    assert err.message  # must have a non-empty user-facing message


# ---------------------------------------------------------------------------
# 1. Allowed queries — these must all PASS
# ---------------------------------------------------------------------------

def test_simple_select_passes():
    safe("SELECT id FROM orders")


def test_select_with_join_passes():
    safe("SELECT c.id, o.id FROM customers c JOIN orders o ON o.id = c.id")


def test_select_with_where_passes():
    safe("SELECT id FROM orders WHERE id = 1")


def test_select_with_aggregation_passes():
    safe("SELECT id, COUNT(*) FROM orders GROUP BY id HAVING COUNT(*) > 1")


def test_select_star_passes():
    safe("SELECT * FROM orders")


def test_select_with_limit_offset_passes():
    safe("SELECT id FROM orders LIMIT 10 OFFSET 5")


def test_union_select_passes():
    safe("SELECT id FROM orders UNION SELECT id FROM customers")


def test_union_all_select_passes():
    safe("SELECT id FROM orders UNION ALL SELECT id FROM customers")


def test_intersect_passes():
    safe("SELECT id FROM orders INTERSECT SELECT id FROM customers")


def test_except_passes():
    safe("SELECT id FROM orders EXCEPT SELECT id FROM customers")


def test_cte_select_passes():
    safe("WITH cte AS (SELECT id FROM orders) SELECT * FROM cte")


def test_nested_cte_passes():
    safe(
        "WITH a AS (SELECT id FROM orders), b AS (SELECT id FROM customers) "
        "SELECT a.id FROM a JOIN b ON a.id = b.id"
    )


def test_subquery_in_from_passes():
    safe("SELECT * FROM (SELECT id FROM orders) sub")


def test_subquery_in_where_passes():
    safe("SELECT id FROM orders WHERE id IN (SELECT id FROM customers)")


def test_scalar_subquery_passes():
    safe("SELECT id, (SELECT COUNT(*) FROM orders) AS cnt FROM customers")


def test_demo_mode_qualified_table_passes():
    """demo.X qualified references are allowed in demo mode without catalog lookup."""
    safe("SELECT id FROM demo.orders", catalog=EMPTY_CATALOG, is_demo=True)


def test_multiple_demo_tables_pass():
    safe(
        "SELECT c.id FROM demo.customers c JOIN demo.orders o ON o.id = c.id",
        catalog=EMPTY_CATALOG,
        is_demo=True,
    )


def test_safe_builtin_functions_pass():
    safe("SELECT LOWER(id), UPPER(id), LENGTH(id), NOW() FROM customers")


def test_mysql_simple_select_passes():
    cat = make_catalog(["orders"], dialect="mysql")
    safe("SELECT id FROM orders", dialect="mysql", catalog=cat)


# ---------------------------------------------------------------------------
# 2. Parse errors
# ---------------------------------------------------------------------------

def test_unparseable_sql_raises_parse_error():
    blocked("THIS IS NOT SQL $$$$", "parse_error")


def test_empty_sql_raises_parse_error():
    blocked("", "parse_error")


# ---------------------------------------------------------------------------
# 3. Multiple statements
# ---------------------------------------------------------------------------

def test_multiple_statements_blocked():
    blocked("SELECT 1; SELECT 2", "multiple_statements")


def test_select_then_drop_blocked():
    blocked("SELECT id FROM orders; DROP TABLE orders", "multiple_statements")


def test_select_then_insert_blocked():
    blocked("SELECT id FROM orders; INSERT INTO orders VALUES (1)", "multiple_statements")


# ---------------------------------------------------------------------------
# 4. Disallowed root statement types
# ---------------------------------------------------------------------------

def test_insert_root_blocked():
    blocked("INSERT INTO orders (id) VALUES (1)", "disallowed_statement")


def test_update_root_blocked():
    blocked("UPDATE orders SET id = 1 WHERE id = 2", "disallowed_statement")


def test_delete_root_blocked():
    blocked("DELETE FROM orders WHERE id = 1", "disallowed_statement")


def test_drop_table_blocked():
    blocked("DROP TABLE orders", "disallowed_statement")


def test_create_table_blocked():
    blocked("CREATE TABLE hacked (id INT)", "disallowed_statement")


def test_alter_table_blocked():
    blocked("ALTER TABLE orders ADD COLUMN hacked INT", "disallowed_statement")


def test_truncate_blocked():
    blocked("TRUNCATE TABLE orders", "disallowed_statement")


# ---------------------------------------------------------------------------
# 5. Write / DDL inside CTEs and subqueries
# ---------------------------------------------------------------------------

def test_delete_in_cte_body_blocked():
    blocked(
        "WITH x AS (DELETE FROM orders RETURNING id) SELECT * FROM x",
        "disallowed_statement",
    )


def test_insert_in_cte_body_blocked():
    blocked(
        "WITH x AS (INSERT INTO orders (id) VALUES (1) RETURNING id) SELECT * FROM x",
        "disallowed_statement",
    )


def test_update_in_cte_body_blocked():
    blocked(
        "WITH x AS (UPDATE orders SET id = 99 RETURNING id) SELECT * FROM x",
        "disallowed_statement",
    )


# ---------------------------------------------------------------------------
# 6. Locking clauses
# ---------------------------------------------------------------------------

def test_for_update_blocked():
    blocked("SELECT id FROM orders FOR UPDATE", "disallowed_construct")


def test_for_share_blocked():
    blocked("SELECT id FROM orders FOR SHARE", "disallowed_construct")


def test_for_no_key_update_blocked():
    blocked("SELECT id FROM orders FOR NO KEY UPDATE", "disallowed_construct")


def test_for_key_share_blocked():
    blocked("SELECT id FROM orders FOR KEY SHARE", "disallowed_construct")


# ---------------------------------------------------------------------------
# 7. Blocked functions — PostgreSQL
# ---------------------------------------------------------------------------

def test_pg_sleep_blocked():
    blocked("SELECT pg_sleep(5)", "disallowed_function")


def test_pg_read_file_blocked():
    blocked("SELECT pg_read_file('/etc/passwd')", "disallowed_function")


def test_pg_ls_dir_blocked():
    blocked("SELECT * FROM pg_ls_dir('/tmp')", "disallowed_function")


def test_pg_cancel_backend_blocked():
    blocked("SELECT pg_cancel_backend(12345)", "disallowed_function")


def test_pg_terminate_backend_blocked():
    blocked("SELECT pg_terminate_backend(12345)", "disallowed_function")


def test_lo_import_blocked():
    blocked("SELECT lo_import('/etc/passwd')", "disallowed_function")


def test_dblink_blocked():
    blocked("SELECT * FROM dblink('host=evil', 'SELECT 1') AS t(col INT)", "disallowed_function")


def test_set_config_blocked():
    blocked("SELECT set_config('search_path', 'evil', false)", "disallowed_function")


def test_current_setting_blocked():
    blocked("SELECT current_setting('is_superuser')", "disallowed_function")


# ---------------------------------------------------------------------------
# 8. Blocked functions — MySQL
# ---------------------------------------------------------------------------

def test_mysql_sleep_blocked():
    cat = make_catalog(["orders"], dialect="mysql")
    blocked("SELECT sleep(5)", "disallowed_function", dialect="mysql", catalog=cat)


def test_mysql_load_file_blocked():
    cat = make_catalog(["orders"], dialect="mysql")
    blocked("SELECT load_file('/etc/passwd')", "disallowed_function", dialect="mysql", catalog=cat)


def test_mysql_benchmark_blocked():
    cat = make_catalog(["orders"], dialect="mysql")
    blocked("SELECT benchmark(1000000, md5('hello'))", "disallowed_function", dialect="mysql", catalog=cat)


def test_mysql_get_lock_blocked():
    cat = make_catalog(["orders"], dialect="mysql")
    blocked("SELECT get_lock('mylock', 10)", "disallowed_function", dialect="mysql", catalog=cat)


# ---------------------------------------------------------------------------
# 9. System / application namespace access
# ---------------------------------------------------------------------------

def test_pg_catalog_access_blocked():
    blocked("SELECT * FROM pg_catalog.pg_tables", "system_namespace_access")


def test_information_schema_postgres_blocked():
    blocked("SELECT * FROM information_schema.tables", "system_namespace_access")


def test_information_schema_mysql_blocked():
    cat = make_catalog(["orders"], dialect="mysql")
    blocked(
        "SELECT * FROM information_schema.tables",
        "system_namespace_access",
        dialect="mysql",
        catalog=cat,
    )


def test_app_schema_blocked():
    """The 'app' namespace (ScribeQL's own tables) must never be exposed."""
    blocked("SELECT * FROM app.users", "system_namespace_access")


def test_app_schema_sessions_blocked():
    blocked("SELECT * FROM app.auth_sessions", "system_namespace_access")


def test_mysql_system_schema_blocked():
    cat = make_catalog(["orders"], dialect="mysql")
    blocked("SELECT * FROM mysql.user", "system_namespace_access", dialect="mysql", catalog=cat)


def test_mysql_performance_schema_blocked():
    cat = make_catalog(["orders"], dialect="mysql")
    blocked(
        "SELECT * FROM performance_schema.events_statements_history",
        "system_namespace_access",
        dialect="mysql",
        catalog=cat,
    )


def test_pg_toast_blocked():
    blocked("SELECT * FROM pg_toast.pg_toast_1234", "system_namespace_access")


# ---------------------------------------------------------------------------
# 10. Unknown table references
# ---------------------------------------------------------------------------

def test_unknown_table_blocked():
    blocked("SELECT id FROM ghost_table", "unknown_table")


def test_unknown_table_in_join_blocked():
    blocked("SELECT id FROM orders JOIN nonexistent_table ON orders.id = nonexistent_table.id", "unknown_table")


def test_known_table_passes():
    safe("SELECT id FROM orders")


def test_cte_alias_not_flagged_as_unknown():
    """A CTE's own alias should not be treated as an unknown table."""
    safe("WITH cte AS (SELECT id FROM orders) SELECT id FROM cte")


# ---------------------------------------------------------------------------
# 11. SafetyError properties
# ---------------------------------------------------------------------------

def test_safety_error_to_dict():
    err = SafetyError("disallowed_function", "Function 'pg_sleep' is not permitted.")
    d = err.to_dict()
    assert d["stage"] == "safety"
    assert d["type"] == "disallowed_function"
    assert "pg_sleep" in d["message"]


def test_safety_error_str():
    err = SafetyError("multiple_statements", "Only a single SQL statement is permitted.")
    assert "Only a single SQL statement is permitted." in str(err)

"""
SQL Safety Checker for ScribeQL — Phase 8.

This is the first hard security boundary after LLM generation. Every generated
SQL string passes through here before it can reach the validator or executor.

Security model
--------------
- LLM output is UNTRUSTED. Prompt instructions are not a security boundary.
- AST parsing catches text-obfuscation tricks that bypass regex-only checks.
- Failures are terminal: a blocked query is NEVER retried.
- No raw parser / database error messages are passed to the caller.

Checks performed (in order)
----------------------------
1. Parse with sqlglot in the session dialect. Reject if unparseable.
2. Require exactly one non-null root statement.
3. Root must be SELECT / set-op (UNION, INTERSECT, EXCEPT) / WITH-SELECT.
   Everything else — INSERT, UPDATE, DELETE, DDL, EXPLAIN, CALL, SET, etc. — is
   blocked here before any further processing.
4. Recursive AST walk across the full tree (covers CTE bodies and subqueries):
   a. Block write / DDL / admin statement node types anywhere in the tree.
   b. Block locking clauses (FOR UPDATE, FOR SHARE, FOR NO KEY UPDATE, …).
   c. Block functions on the per-dialect blocked list.
   d. Block table references in system / application namespaces.
5. Validate every referenced table name against SchemaCatalog.
   In demo mode, demo.X qualified tables are accepted without a catalog lookup.
"""

import logging
from typing import Optional

import sqlglot
import sqlglot.expressions as exp

from app.sql.errors import SafetyError
from app.sql.allowlists import (
    BLOCKED_FUNCTIONS_POSTGRES,
    BLOCKED_FUNCTIONS_MYSQL,
    SYSTEM_NAMESPACES_POSTGRES,
    SYSTEM_NAMESPACES_MYSQL,
    BLOCKED_ROOT_NODE_TYPES,
)
from app.schema.catalog import SchemaCatalog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dialect helpers
# ---------------------------------------------------------------------------

_DIALECT_MAP: dict[str, str] = {
    "postgres": "postgres",
    "mysql": "mysql",
}


def _sqlglot_dialect(dialect: str) -> str:
    return _DIALECT_MAP.get(dialect.lower(), "postgres")


def _blocked_functions(dialect: str) -> frozenset[str]:
    if dialect.lower() == "mysql":
        return BLOCKED_FUNCTIONS_MYSQL
    return BLOCKED_FUNCTIONS_POSTGRES


def _system_namespaces(dialect: str) -> frozenset[str]:
    if dialect.lower() == "mysql":
        return SYSTEM_NAMESPACES_MYSQL
    return SYSTEM_NAMESPACES_POSTGRES


# ---------------------------------------------------------------------------
# AST node helpers
# ---------------------------------------------------------------------------

def _is_select_root(node: exp.Expression) -> bool:
    """
    Return True if the root statement is a read-only SELECT or set-operation.

    exp.Subquery is intentionally excluded: a bare parenthesised SELECT
    at statement level is not valid SQL and sqlglot would parse it as a
    plain exp.Select anyway.
    """
    return isinstance(node, (
        exp.Select,
        exp.Union,
        exp.Intersect,
        exp.Except,
        exp.With,
    ))


def _get_function_name(node: exp.Expression) -> Optional[str]:
    """
    Extract the SQL-level function name from an AST function node, lowercased.

    Strategy
    --------
    - exp.Anonymous  → use .name directly (this is exactly what the parser saw).
    - exp.Func subclass (sqlglot built-in) → use the class-level sql_name()
      which maps Python class names like PgSleep back to "pg_sleep".
      Falls back to the class name if sql_name() is unavailable.
    """
    if isinstance(node, exp.Anonymous):
        return node.name.lower() if node.name else None
    if isinstance(node, exp.Func):
        try:
            name = type(node).sql_name()
            return name.lower() if name else None
        except (AttributeError, NotImplementedError):
            return type(node).__name__.lower()
    return None


def _get_schema_qualifier(table_node: exp.Table) -> Optional[str]:
    """
    Extract the schema (db) qualifier from a table reference, lowercased.

    sqlglot populates the "db" arg with the schema name for schema.table
    references and "catalog" for three-part catalog.schema.table references.
    Strips quotes/backticks for reliable comparison.
    """
    schema_part = table_node.args.get("db") or table_node.args.get("catalog")
    if not schema_part:
        return None
    if hasattr(schema_part, "name") and schema_part.name:
        return schema_part.name.lower()
    # Fallback for unusual node types
    raw = str(schema_part).strip().strip('"').strip("`").lower()
    return raw or None


# ---------------------------------------------------------------------------
# Recursive AST walker
# ---------------------------------------------------------------------------

def _walk_for_violations(
    root: exp.Expression,
    dialect: str,
    blocked_fns: frozenset[str],
    system_ns: frozenset[str],
) -> None:
    """
    Walk every node in the AST and raise SafetyError on the first violation.

    sqlglot's .walk() already recurses into CTE bodies, subqueries, CASE
    expressions, etc., so a single call covers the entire query tree.
    The root itself is skipped here — it was validated in step 3.
    """
    for child in root.walk():
        if child is root:
            continue

        child_type = type(child).__name__

        # 4a ── Write / DDL / admin statement types ─────────────────────────
        if child_type in BLOCKED_ROOT_NODE_TYPES:
            raise SafetyError(
                "disallowed_statement",
                f"Statement type '{child_type}' is not permitted inside a query.",
            )

        # 4b ── Locking clauses ──────────────────────────────────────────────
        # sqlglot represents FOR UPDATE / FOR SHARE / FOR NO KEY UPDATE / etc.
        # as exp.Lock nodes. The exp.Var check from earlier versions was fragile
        # and is no longer needed.
        if isinstance(child, exp.Lock):
            raise SafetyError(
                "disallowed_construct",
                "Locking clauses (FOR UPDATE / FOR SHARE / FOR NO KEY UPDATE) "
                "are not permitted.",
            )

        # 4c ── Blocked functions ─────────────────────────────────────────────
        if isinstance(child, (exp.Anonymous, exp.Func)):
            fn_name = _get_function_name(child)
            if fn_name and fn_name in blocked_fns:
                raise SafetyError(
                    "disallowed_function",
                    f"Function '{fn_name}' is not permitted.",
                )

        # 4d ── System / application namespace access ─────────────────────────
        if isinstance(child, exp.Table):
            schema_qualifier = _get_schema_qualifier(child)
            if schema_qualifier and schema_qualifier in system_ns:
                raise SafetyError(
                    "system_namespace_access",
                    f"Access to schema '{schema_qualifier}' is not permitted.",
                )


# ---------------------------------------------------------------------------
# Table reference extraction
# ---------------------------------------------------------------------------

def _extract_table_references(root: exp.Expression) -> list[tuple[str, Optional[str]]]:
    """
    Return (table_name_lower, schema_qualifier_or_None) for every real table
    reference in the AST. CTE-defined aliases are excluded because they are
    resolved within the query itself and have no corresponding catalog entry.
    """
    cte_names: set[str] = {
        cte.alias.lower()
        for cte in root.find_all(exp.CTE)
        if cte.alias
    }

    seen: set[tuple[str, Optional[str]]] = set()
    refs: list[tuple[str, Optional[str]]] = []

    for table_node in root.find_all(exp.Table):
        tbl_name = table_node.name
        if not tbl_name:
            continue
        tbl_lower = tbl_name.lower()
        if tbl_lower in cte_names:
            continue

        schema_qualifier = _get_schema_qualifier(table_node)
        key = (tbl_lower, schema_qualifier)
        if key not in seen:
            seen.add(key)
            refs.append(key)

    return refs


# ---------------------------------------------------------------------------
# Public checker
# ---------------------------------------------------------------------------

class SQLSafetyChecker:
    """
    Stateless, reusable SQL safety checker. Instantiate once at module level.

    All checks operate purely on the AST — no database connection is required.
    """

    def check(
        self,
        sql: str,
        dialect: str,
        catalog: SchemaCatalog,
        is_demo: bool = False,
    ) -> exp.Expression:
        """
        Run all safety checks on *sql* and return the parsed AST on success.

        The returned expression is the parsed sqlglot AST and can be reused
        directly by the Phase 9 validator (avoids parsing the same SQL twice).

        Parameters
        ----------
        sql      : Raw SQL string from the LLM.
        dialect  : "postgres" or "mysql". Controls the parsing dialect and
                   which function / namespace blocklists are applied.
        catalog  : SchemaCatalog for the current session. Used to validate
                   every table reference in the query.
        is_demo  : When True, tables qualified with the "demo" schema prefix
                   are accepted without a catalog lookup.

        Returns
        -------
        exp.Expression — the parsed sqlglot root node.

        Raises
        ------
        SafetyError — on any violation. The stage is always "safety".
        """
        sq_dialect = _sqlglot_dialect(dialect)
        blocked_fns = _blocked_functions(dialect)
        system_ns = _system_namespaces(dialect)

        # ── 1. Parse ──────────────────────────────────────────────────────────
        try:
            raw_statements = sqlglot.parse(
                sql.strip(),
                dialect=sq_dialect,
                error_level=sqlglot.ErrorLevel.RAISE,
            )
        except Exception:
            raise SafetyError(
                "parse_error",
                "The generated SQL could not be parsed. "
                "Please try rephrasing your question.",
            )

        # Filter out None entries that sqlglot can return for blank statements
        statements = [s for s in (raw_statements or []) if s is not None]

        if not statements:
            raise SafetyError("parse_error", "No SQL statement was produced.")

        # ── 2. Exactly one statement ──────────────────────────────────────────
        if len(statements) > 1:
            raise SafetyError(
                "multiple_statements",
                "Only a single SQL statement is permitted.",
            )

        root = statements[0]

        # ── 3. Root must be SELECT / set-op / WITH-SELECT ─────────────────────
        if not _is_select_root(root):
            root_type = type(root).__name__
            raise SafetyError(
                "disallowed_statement",
                f"Only SELECT queries are permitted. Received: {root_type}.",
            )

        # Extra guard: WITH bodies must ultimately be read-only queries
        if isinstance(root, exp.With):
            inner = root.args.get("this")
            if inner is not None and not isinstance(
                inner, (exp.Select, exp.Union, exp.Intersect, exp.Except)
            ):
                raise SafetyError(
                    "disallowed_statement",
                    "A WITH clause must terminate with a SELECT statement.",
                )

        # ── 4. Full AST walk ──────────────────────────────────────────────────
        _walk_for_violations(root, dialect, blocked_fns, system_ns)

        # ── 5. Table reference validation ─────────────────────────────────────
        for tbl_name, schema_qualifier in _extract_table_references(root):
            # System namespace: belt-and-suspenders (also caught in walk step 4d)
            if schema_qualifier and schema_qualifier in system_ns:
                raise SafetyError(
                    "system_namespace_access",
                    f"Access to schema '{schema_qualifier}' is not permitted.",
                )

            # Demo mode: demo.X tables are accepted without a catalog lookup
            if is_demo and schema_qualifier == "demo":
                continue

            # Validate against the session's SchemaCatalog
            if not catalog.has_table(tbl_name):
                raise SafetyError(
                    "unknown_table",
                    f"Table '{tbl_name}' is not in the schema.",
                )

        logger.debug(
            "SQL passed safety check (dialect=%s, demo=%s, tables=%d)",
            dialect,
            is_demo,
            len(_extract_table_references(root)),
        )
        return root


# ---------------------------------------------------------------------------
# Module-level singleton + convenience function
# ---------------------------------------------------------------------------

sql_safety_checker = SQLSafetyChecker()


def check_sql_safety(
    sql: str,
    dialect: str,
    catalog: SchemaCatalog,
    is_demo: bool = False,
) -> exp.Expression:
    """
    Module-level convenience wrapper around the shared SQLSafetyChecker instance.

    Equivalent to ``sql_safety_checker.check(sql, dialect, catalog, is_demo)``.
    """
    return sql_safety_checker.check(sql, dialect=dialect, catalog=catalog, is_demo=is_demo)

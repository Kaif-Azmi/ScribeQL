"""
Dialect-aware SQL validation using sqlglot qualification and demo-mode EXPLAIN.
Raw parser/driver messages are never returned to callers.
"""

import logging
from typing import Optional

import sqlglot
from sqlglot.optimizer.qualify import qualify

from app.schema.catalog import SchemaCatalog
from app.sql.errors import SafetyError
from app.db.session import get_demo_ro_connection

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    def __init__(self, error_type: str, message: str, stage: str = "validation"):
        self.stage = stage
        self.type = error_type
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"stage": self.stage, "type": self.type, "message": self.message}


def _sqlglot_dialect(dialect: str) -> str:
    return "mysql" if dialect.lower() == "mysql" else "postgres"


def catalog_to_mapping(catalog: SchemaCatalog, is_demo: bool) -> dict:
    tables = {}
    for name, table in catalog.tables.items():
        tables[name] = {col.name: (col.data_type or "UNKNOWN") for col in table.columns}
    # sqlglot MappingSchema requires a single nesting level. Demo SQL may
    # qualify tables as demo.X or rely on sql_ro search_path=demo.
    if is_demo:
        return {"demo": tables}
    return tables


def validate_sql(
    sql: str,
    dialect: str,
    catalog: SchemaCatalog,
    is_demo: bool = False,
    parsed: Optional[sqlglot.Expression] = None,
) -> None:
    sq_dialect = _sqlglot_dialect(dialect)
    try:
        expression = parsed or sqlglot.parse_one(sql, dialect=sq_dialect)
        qualify(
            expression,
            schema=catalog_to_mapping(catalog, is_demo),
            dialect=sq_dialect,
            qualify_columns=True,
            validate_qualify_columns=False,
        )
    except SafetyError:
        raise
    except Exception:
        if not is_demo:
            raise ValidationError(
                "unknown_identifier",
                "The generated SQL references an unknown table or column.",
            )

    if is_demo:
        _explain_demo(sql)


def _explain_demo(sql: str) -> None:
    try:
        with get_demo_ro_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("EXPLAIN " + sql)
                cur.fetchall()
    except ValidationError:
        raise
    except Exception:
        raise ValidationError(
            "invalid_sql",
            "The generated SQL could not be validated against the demo database.",
        )

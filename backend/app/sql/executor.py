"""
Read-only demo SQL executor (sql_ro). Custom-mode SQL must never reach this module.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple
from uuid import UUID

from app.config.settings import settings
from app.db.session import get_demo_ro_connection

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    def __init__(self, error_type: str, message: str, stage: str = "execution"):
        self.stage = stage
        self.type = error_type
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"stage": self.stage, "type": self.type, "message": self.message}


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def execute_demo_sql(sql: str, row_cap: Optional[int] = None) -> Tuple[List[str], List[List[Any]], int, bool]:
    """
    Execute a safety-checked SELECT against the demo schema using sql_ro.
    Returns (columns, rows, row_count, truncated).
    """
    cap = row_cap or settings.query_row_cap
    try:
        with get_demo_ro_connection() as conn:
            with conn.cursor(name="scribeql_demo_cur") as cur:
                cur.itersize = min(50, cap)
                cur.execute(sql)
                fetched = cur.fetchmany(cap + 1)
                columns = [d[0] for d in (cur.description or [])]
    except Exception as exc:
        err_name = type(exc).__name__.lower()
        message = str(exc).lower()
        if "timeout" in err_name or "timeout" in message or "cancel" in message:
            raise ExecutionError("timeout", "The query took too long to run.") from exc
        raise ExecutionError("execution_error", "The query could not be executed.") from exc

    truncated = len(fetched) > cap
    rows = [[_jsonable(v) for v in row] for row in fetched[:cap]]
    return columns, rows, len(rows), truncated

"""
DDL Parser for ScribeQL using sqlglot.
Parses PostgreSQL and MySQL DDL statements into a canonical SchemaCatalog object.
"""

import re
from typing import Dict, List, Optional, Any, Set
import sqlglot
from sqlglot import exp
from app.schema.catalog import (
    SchemaCatalog,
    TableSchema,
    ColumnSchema,
    ForeignKeySchema,
    HintsSchema,
)

RESERVED_NAMESPACES = {
    "pg_catalog",
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
}

MAX_TABLES_CAP = 15


class DDLParseError(Exception):
    """Raised when DDL fails to parse or contains no valid CREATE TABLE statements."""
    pass


class ReservedNamespaceError(Exception):
    """Raised when DDL attempts to declare tables in a system namespace."""
    pass


class SchemaTooLargeError(Exception):
    """Raised when DDL declares more tables than the allowed cap."""
    pass


class InvalidHintsError(Exception):
    """Raised when hints reference non-existent columns or are malformed."""
    pass


def parse_ddl_to_catalog(
    ddl_text: str,
    dialect: str = "postgres",
    hints: Optional[Dict[str, Any]] = None
) -> SchemaCatalog:
    """
    Parse PostgreSQL or MySQL DDL text into a canonical SchemaCatalog.
    Does NOT execute any SQL.
    """
    clean_dialect = dialect.lower().strip()
    if clean_dialect not in ("postgres", "mysql"):
        raise ValueError(f"Unsupported dialect: {dialect}. Must be 'postgres' or 'mysql'.")

    try:
        statements = sqlglot.parse(ddl_text, read=clean_dialect)
    except Exception as exc:
        raise DDLParseError(f"Failed to parse DDL syntax in {clean_dialect} dialect: {exc}")

    # Remove None or empty statements
    statements = [s for s in statements if s is not None]

    if not statements:
        raise DDLParseError(f"No parseable SQL statements found in input.")

    catalog = SchemaCatalog(dialect=clean_dialect, tables={}, warnings=[])
    enum_types: Dict[str, List[str]] = {}
    skipped_types: Set[str] = set()
    create_table_count = 0

    for stmt in statements:
        if isinstance(stmt, exp.Create):
            kind = (stmt.args.get("kind") or "").upper()
            if kind == "TABLE" or (not kind and isinstance(stmt.this, exp.Schema)):
                create_table_count += 1
                _process_create_table(stmt, catalog, enum_types, clean_dialect)
            elif kind == "TYPE":
                _process_create_type(stmt, enum_types)
            elif kind == "INDEX":
                skipped_types.add("CREATE INDEX")
            else:
                skipped_types.add(f"CREATE {kind}" if kind else "CREATE")

        elif isinstance(stmt, exp.Alter):
            _process_alter_table(stmt, catalog)

        else:
            # Statement type name for warnings
            stmt_name = stmt.key.upper() if hasattr(stmt, "key") and stmt.key else type(stmt).__name__.upper()
            skipped_types.add(stmt_name)

    if create_table_count == 0:
        raise DDLParseError(f"No CREATE TABLE statement could be parsed in {clean_dialect} dialect.")

    if len(catalog.tables) > MAX_TABLES_CAP:
        raise SchemaTooLargeError(
            f"Schema contains {len(catalog.tables)} tables, exceeding the limit of {MAX_TABLES_CAP}."
        )

    if skipped_types:
        skipped_list = ", ".join(sorted(skipped_types))
        catalog.warnings.append(f"Skipped unsupported statements ({skipped_list}).")

    # Apply & validate hints if provided
    if hints:
        _apply_hints(catalog, hints)

    return catalog


def _process_create_table(
    stmt: exp.Create,
    catalog: SchemaCatalog,
    enum_types: Dict[str, List[str]],
    dialect: str
):
    schema_expr = stmt.this
    raw_table_name = schema_expr.this.name if hasattr(schema_expr.this, "this") else str(schema_expr.this)

    # Check namespace / table qualifier
    namespace = None
    if hasattr(schema_expr.this, "db") and schema_expr.this.db:
        namespace = schema_expr.this.db
    elif "." in raw_table_name:
        parts = raw_table_name.split(".")
        namespace = parts[0]
        raw_table_name = parts[1]

    table_name = raw_table_name.strip("`\"'[]")

    if namespace and namespace.lower().strip("`\"'[]") in RESERVED_NAMESPACES:
        raise ReservedNamespaceError(
            f"The schema declares tables in reserved system namespace '{namespace}'."
        )

    columns: List[ColumnSchema] = []
    primary_keys: List[str] = []
    foreign_keys: List[ForeignKeySchema] = []

    if hasattr(schema_expr, "expressions"):
        for expr in schema_expr.expressions:
            if isinstance(expr, exp.ColumnDef):
                col_name = expr.this.name.strip("`\"'[]")
                col_type = expr.kind.sql(dialect=dialect) if hasattr(expr, "kind") and expr.kind else "VARCHAR"

                is_pk = False
                is_nullable = True
                default_val = None
                col_enums: List[str] = []

                # Column constraints
                if hasattr(expr, "constraints") and expr.constraints:
                    for const in expr.constraints:
                        kind_sql = const.sql(dialect=dialect).upper()
                        if "PRIMARY KEY" in kind_sql:
                            is_pk = True
                            is_nullable = False
                            if col_name not in primary_keys:
                                primary_keys.append(col_name)
                        if "NOT NULL" in kind_sql:
                            is_nullable = False
                        if "DEFAULT" in kind_sql:
                            if hasattr(const, "this") and const.this is not None:
                                default_val = const.this.sql(dialect=dialect)
                            else:
                                default_val = const.sql(dialect=dialect)
                        if "REFERENCES" in kind_sql:
                            # Inline foreign key
                            ref_match = re.search(r"REFERENCES\s+[`\"']?(\w+)[`\"']?\s*\(([`\"']?\w+[`\"']?)\)", const.sql(dialect=dialect), re.IGNORECASE)
                            if ref_match:
                                foreign_keys.append(
                                    ForeignKeySchema(
                                        column=col_name,
                                        ref_table=ref_match.group(1),
                                        ref_column=ref_match.group(2)
                                    )
                                )

                # Check if col_type references a CREATE TYPE enum
                if col_type in enum_types:
                    col_enums = enum_types[col_type]

                # Handle MySQL inline ENUM syntax: e.g. ENUM('active', 'inactive')
                if "ENUM(" in col_type.upper():
                    enum_matches = re.findall(r"['\"](\w+)['\"]", col_type)
                    if enum_matches:
                        col_enums = enum_matches
                        col_type = "ENUM"

                columns.append(
                    ColumnSchema(
                        name=col_name,
                        data_type=col_type,
                        is_nullable=is_nullable,
                        is_primary_key=is_pk,
                        default=default_val,
                        enum_values=col_enums
                    )
                )

            elif isinstance(expr, exp.PrimaryKey):
                for col_identifier in expr.expressions:
                    pk_name = col_identifier.name.strip("`\"'[]")
                    if pk_name not in primary_keys:
                        primary_keys.append(pk_name)

            elif isinstance(expr, exp.Constraint):
                # Table-level constraints (e.g. FOREIGN KEY)
                const_sql = expr.sql(dialect=dialect)
                fk_match = re.search(
                    r"FOREIGN KEY\s*\(([`\"']?\w+[`\"']?)\)\s*REFERENCES\s+[`\"']?(\w+)[`\"']?\s*\(([`\"']?\w+[`\"']?)\)",
                    const_sql,
                    re.IGNORECASE
                )
                if fk_match:
                    foreign_keys.append(
                        ForeignKeySchema(
                            column=fk_match.group(1).strip("`\"'[]"),
                            ref_table=fk_match.group(2).strip("`\"'[]"),
                            ref_column=fk_match.group(3).strip("`\"'[]")
                        )
                    )

    # Mark PK columns
    for col in columns:
        if col.name in primary_keys:
            col.is_primary_key = True
            col.is_nullable = False

    # Check table warning
    if not primary_keys:
        catalog.warnings.append(f"Table '{table_name}' has no primary key.")

    catalog.tables[table_name] = TableSchema(
        name=table_name,
        columns=columns,
        primary_keys=primary_keys,
        foreign_keys=foreign_keys
    )


def _process_create_type(stmt: exp.Create, enum_types: Dict[str, List[str]]):
    """Process PostgreSQL CREATE TYPE ... AS ENUM ('a', 'b')."""
    type_name = stmt.this.name if hasattr(stmt.this, "name") else str(stmt.this)
    type_name = type_name.strip("`\"'[]")

    labels = []
    if hasattr(stmt, "expressions") and stmt.expressions:
        for expr in stmt.expressions:
            val = expr.sql().strip("`\"'[]")
            labels.append(val)
    elif "AS ENUM" in stmt.sql().upper():
        labels = re.findall(r"['\"](\w+)['\"]", stmt.sql())

    if labels:
        enum_types[type_name] = labels


def _process_alter_table(stmt: exp.Alter, catalog: SchemaCatalog):
    """Process ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY."""
    alter_sql = stmt.sql()
    table_match = re.search(r"ALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?", alter_sql, re.IGNORECASE)
    fk_match = re.search(
        r"FOREIGN\s+KEY\s*\(([`\"']?\w+[`\"']?)\)\s*REFERENCES\s+[`\"']?(\w+)[`\"']?\s*\(([`\"']?\w+[`\"']?)\)",
        alter_sql,
        re.IGNORECASE
    )

    if table_match and fk_match:
        table_name = table_match.group(1).strip("`\"'[]")
        src_col = fk_match.group(1).strip("`\"'[]")
        ref_table = fk_match.group(2).strip("`\"'[]")
        ref_col = fk_match.group(3).strip("`\"'[]")

        table = catalog.get_table(table_name)
        if table:
            table.foreign_keys.append(
                ForeignKeySchema(column=src_col, ref_table=ref_table, ref_column=ref_col)
            )


def _apply_hints(catalog: SchemaCatalog, hints: Dict[str, Any]):
    """Validate and merge user hints into SchemaCatalog."""
    hints_obj = HintsSchema()

    # 1. Enums hint
    if "enums" in hints and isinstance(hints["enums"], dict):
        for col_key, enum_list in hints["enums"].items():
            if not isinstance(enum_list, list):
                raise InvalidHintsError(f"Enum values for key '{col_key}' must be a list.")

            # Validate column existence
            col_found = False
            if "." in col_key:
                t_name, c_name = col_key.split(".", 1)
                table = catalog.get_table(t_name)
                if table and table.get_column(c_name):
                    col = table.get_column(c_name)
                    col.enum_values = [str(x) for x in enum_list]
                    col_found = True
            else:
                for table in catalog.tables.values():
                    col = table.get_column(col_key)
                    if col:
                        col.enum_values = [str(x) for x in enum_list]
                        col_found = True

            if not col_found:
                raise InvalidHintsError(
                    f"Hint enum key '{col_key}' does not match any column in the uploaded schema."
                )

            hints_obj.enums[col_key] = [str(x) for x in enum_list]

    # 2. Metrics hint
    if "metrics" in hints and isinstance(hints["metrics"], dict):
        for metric_name, expr in hints["metrics"].items():
            hints_obj.metrics[str(metric_name)] = str(expr)

    # 3. Notes hint
    if "notes" in hints and hints["notes"]:
        hints_obj.notes = str(hints["notes"])

    catalog.hints = hints_obj

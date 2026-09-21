"""
PostgreSQL Schema Inspector for ScribeQL.
Inspects live PostgreSQL databases (such as the demo database)
and constructs a canonical SchemaCatalog object.
"""

from typing import Dict, List
import psycopg
from app.schema.catalog import (
    SchemaCatalog,
    TableSchema,
    ColumnSchema,
    ForeignKeySchema,
)


def inspect_postgres_schema(conn: psycopg.Connection, schema_name: str = "demo") -> SchemaCatalog:
    """
    Inspect a PostgreSQL schema (defaults to 'demo') and build a SchemaCatalog.
    """
    catalog = SchemaCatalog(dialect="postgres", tables={})

    with conn.cursor() as cur:
        # 1. Fetch all base tables in the schema
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """, (schema_name,))
        table_names = [row[0] for row in cur.fetchall()]

        # 2. Fetch primary keys
        cur.execute("""
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s;
        """, (schema_name,))
        pks_by_table: Dict[str, List[str]] = {}
        for t_name, col_name in cur.fetchall():
            pks_by_table.setdefault(t_name, []).append(col_name)

        # 3. Fetch foreign keys
        cur.execute("""
            SELECT
                kcu.table_name AS src_table,
                kcu.column_name AS src_column,
                ccu.table_name AS ref_table,
                ccu.column_name AS ref_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s;
        """, (schema_name,))
        fks_by_table: Dict[str, List[ForeignKeySchema]] = {}
        for src_t, src_c, ref_t, ref_c in cur.fetchall():
            fk_obj = ForeignKeySchema(column=src_c, ref_table=ref_t, ref_column=ref_c)
            fks_by_table.setdefault(src_t, []).append(fk_obj)

        # 4. Fetch enum values in PostgreSQL
        cur.execute("""
            SELECT t.typname, e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = %s
            ORDER BY t.typname, e.enumsortorder;
        """, (schema_name,))
        enums_by_type: Dict[str, List[str]] = {}
        for typname, enumlabel in cur.fetchall():
            enums_by_type.setdefault(typname, []).append(enumlabel)

        # 5. Build TableSchema for each table
        for table_name in table_names:
            cur.execute("""
                SELECT column_name, data_type, udt_name, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """, (schema_name, table_name))

            columns: List[ColumnSchema] = []
            pk_cols = pks_by_table.get(table_name, [])

            for col_name, data_type, udt_name, is_nullable, col_default in cur.fetchall():
                is_pk = col_name in pk_cols
                enum_vals = enums_by_type.get(udt_name, [])
                type_display = data_type if data_type != 'USER-DEFINED' else udt_name

                columns.append(
                    ColumnSchema(
                        name=col_name,
                        data_type=type_display,
                        is_nullable=(is_nullable.upper() == 'YES'),
                        is_primary_key=is_pk,
                        default=col_default,
                        enum_values=enum_vals
                    )
                )

            table_schema = TableSchema(
                name=table_name,
                columns=columns,
                primary_keys=pk_cols,
                foreign_keys=fks_by_table.get(table_name, [])
            )
            catalog.tables[table_name] = table_schema

    return catalog

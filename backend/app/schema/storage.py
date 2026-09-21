"""
Schema Catalog Storage Service for ScribeQL.
Persists parsed custom SchemaCatalog objects in memory or database.
"""

from typing import Dict, Any, Optional
import json
from app.schema.catalog import SchemaCatalog
from app.db.session import check_db_health, get_app_connection


class InMemorySchemaStore:
    def __init__(self):
        self.catalogs: Dict[str, SchemaCatalog] = {}

    def clear(self):
        self.catalogs.clear()


in_memory_schema_store = InMemorySchemaStore()


class SchemaStorageService:
    def save_catalog(self, schema_id: str, catalog: SchemaCatalog):
        """Save a SchemaCatalog object."""
        if check_db_health():
            catalog_json = catalog.model_dump_json()
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO app.schema_catalogs (id, dialect, catalog_data, created_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET catalog_data = EXCLUDED.catalog_data;
                    """, (schema_id, catalog.dialect, catalog_json))
            return

        in_memory_schema_store.catalogs[schema_id] = catalog

    def get_catalog(self, schema_id: str) -> Optional[SchemaCatalog]:
        """Retrieve a stored SchemaCatalog by schema_id."""
        if check_db_health():
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT catalog_data FROM app.schema_catalogs WHERE id = %s;
                    """, (schema_id,))
                    row = cur.fetchone()
                    if row:
                        raw_data = row[0]
                        if isinstance(raw_data, str):
                            raw_data = json.loads(raw_data)
                        return SchemaCatalog.model_validate(raw_data)
                    return None

        return in_memory_schema_store.catalogs.get(schema_id)


schema_storage_service = SchemaStorageService()

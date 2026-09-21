"""
VectorStore using PostgreSQL + pgvector for RAG similarity retrieval.
Manages schema initialization, document indexing, and cosine distance search.
"""

import json
import logging
from typing import List, Optional
import psycopg
from psycopg.rows import dict_row

from app.db.session import get_app_connection
from app.rag.models import RAGDocument
from app.config.settings import settings

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def ensure_rag_schema(self) -> bool:
        """
        Verify app.rag_documents exists. pgvector and the app schema are provisioned
        by the database admin — this must not CREATE EXTENSION or CREATE SCHEMA.
        """
        try:
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('app.rag_documents');")
                    if cur.fetchone()[0] is None:
                        logger.warning("app.rag_documents is missing.")
                        return False
                    cur.execute(
                        """
                        SELECT atttypmod
                        FROM pg_attribute a
                        JOIN pg_class c ON a.attrelid = c.oid
                        JOIN pg_namespace n ON c.relnamespace = n.oid
                        WHERE n.nspname = 'app'
                          AND c.relname = 'rag_documents'
                          AND a.attname = 'embedding';
                        """
                    )
                    row = cur.fetchone()
                    if row and row[0] not in (None, -1) and int(row[0]) != self.dimension:
                        logger.warning(
                            "rag_documents.embedding dimension is %s; expected %s",
                            row[0],
                            self.dimension,
                        )
            logger.info("Verified app.rag_documents table.")
            return True
        except Exception as exc:
            logger.warning("Could not verify pgvector schema: %s", exc)
            return False

    def replace_corpus(self, documents: List[RAGDocument], embeddings: List[List[float]]) -> int:
        """Replace all RAG documents with a new indexed corpus."""
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings.")
        if not self.ensure_rag_schema():
            raise RuntimeError("app.rag_documents is not available.")
        with get_app_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE app.rag_documents;")
                inserted_count = 0
                for doc, emb in zip(documents, embeddings):
                    if len(emb) != self.dimension:
                        raise ValueError(
                            f"Embedding length {len(emb)} does not match vector({self.dimension})."
                        )
                    emb_str = "[" + ",".join(str(f) for f in emb) + "]"
                    cur.execute(
                        """
                        INSERT INTO app.rag_documents (title, content, dialect, category, metadata_json, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s::vector);
                        """,
                        (
                            doc.title,
                            doc.content,
                            doc.dialect.lower(),
                            doc.category.lower(),
                            json.dumps(doc.metadata_json),
                            emb_str,
                        ),
                    )
                    inserted_count += 1
        return inserted_count

    def add_documents(self, documents: List[RAGDocument], embeddings: List[List[float]]) -> int:
        """Insert a batch of documents and their corresponding embeddings into app.rag_documents."""
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings.")

        inserted_count = 0
        try:
            self.ensure_rag_schema()
            with get_app_connection() as conn:
                with conn.cursor() as cur:
                    for doc, emb in zip(documents, embeddings):
                        emb_str = "[" + ",".join(str(f) for f in emb) + "]"
                        cur.execute(
                            """
                            INSERT INTO app.rag_documents (title, content, dialect, category, metadata_json, embedding)
                            VALUES (%s, %s, %s, %s, %s, %s::vector);
                            """,
                            (
                                doc.title,
                                doc.content,
                                doc.dialect.lower(),
                                doc.category.lower(),
                                json.dumps(doc.metadata_json),
                                emb_str
                            )
                        )
                        inserted_count += 1
            return inserted_count
        except Exception as exc:
            logger.error(f"Failed to insert documents into VectorStore: {exc}")
            raise

    def similarity_search(
        self,
        query_embedding: List[float],
        dialect: str = "postgres",
        category: Optional[str] = None,
        top_k: int = 3
    ) -> List[RAGDocument]:
        """
        Perform pgvector cosine similarity search against app.rag_documents.
        Returns top_k most similar RAGDocuments with similarity_score populated.
        """
        emb_str = "[" + ",".join(str(f) for f in query_embedding) + "]"
        results: List[RAGDocument] = []

        try:
            with get_app_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    query = """
                        SELECT id, title, content, dialect, category, metadata_json,
                               (1 - (embedding <=> %s::vector)) AS similarity
                        FROM app.rag_documents
                        WHERE (dialect = 'all' OR LOWER(dialect) = %s)
                    """
                    params = [emb_str, dialect.lower()]

                    if category:
                        query += " AND LOWER(category) = %s"
                        params.append(category.lower())

                    query += f" ORDER BY embedding <=> %s::vector ASC LIMIT %s;"
                    params.extend([emb_str, top_k])

                    cur.execute(query, params)
                    rows = cur.fetchall()

                    for row in rows:
                        doc = RAGDocument(
                            id=str(row["id"]),
                            title=row["title"],
                            content=row["content"],
                            dialect=row["dialect"],
                            category=row["category"],
                            metadata_json=row["metadata_json"] or {},
                            similarity_score=float(row["similarity"]) if row["similarity"] is not None else None
                        )
                        results.append(doc)

        except Exception as exc:
            logger.warning(f"VectorStore similarity search failed (DB offline or pgvector uninitialized): {exc}")
            # Graceful fallback: return empty list, pipeline handles empty context cleanly
            return []

        return results


vector_store = VectorStore()

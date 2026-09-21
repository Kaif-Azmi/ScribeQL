"""
Ingestion & Indexing Script for ScribeQL RAG Corpus.
Populates PostgreSQL pgvector table app.rag_documents with curated NL->SQL examples,
SQL design patterns, and dialect-specific syntax guidance.
"""

import sys
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.rag.models import RAGDocument
from app.rag.embeddings import embedding_service
from app.rag.vector_store import vector_store


import json

DEFAULT_CORPUS = [
    RAGDocument(
        title="Top Spending Customers in Demo Schema",
        content=(
            "Question: Find the top 5 customers by total order amount.\n"
            "SQL Pattern:\n"
            "SELECT c.id, c.name, SUM(o.total_amount) AS total_spent\n"
            "FROM demo.customers c\n"
            "JOIN demo.orders o ON c.id = o.customer_id\n"
            "WHERE o.status = 'COMPLETED'\n"
            "GROUP BY c.id, c.name\n"
            "ORDER BY total_spent DESC\n"
            "LIMIT 5;"
        ),
        dialect="postgres",
        category="example",
        metadata_json={"tags": ["e-commerce", "aggregation", "top-k"]}
    ),
    RAGDocument(
        title="Monthly Order Trends and Revenue Breakdown",
        content=(
            "Question: Show total monthly revenue for the current year.\n"
            "SQL Pattern (PostgreSQL):\n"
            "SELECT DATE_TRUNC('month', created_at) AS month, SUM(total_amount) AS revenue, COUNT(id) AS order_count\n"
            "FROM demo.orders\n"
            "WHERE status != 'CANCELLED'\n"
            "GROUP BY DATE_TRUNC('month', created_at)\n"
            "ORDER BY month ASC;"
        ),
        dialect="postgres",
        category="pattern",
        metadata_json={"tags": ["date_trunc", "monthly_revenue", "postgres"]}
    ),
    RAGDocument(
        title="Monthly Revenue Breakdown (MySQL Dialect)",
        content=(
            "Question: Show total monthly revenue for MySQL dialect.\n"
            "SQL Pattern (MySQL):\n"
            "SELECT DATE_FORMAT(created_at, '%Y-%m-01') AS month, SUM(total_amount) AS revenue, COUNT(id) AS order_count\n"
            "FROM orders\n"
            "WHERE status != 'CANCELLED'\n"
            "GROUP BY DATE_FORMAT(created_at, '%Y-%m-01')\n"
            "ORDER BY month ASC;"
        ),
        dialect="mysql",
        category="pattern",
        metadata_json={"tags": ["date_format", "monthly_revenue", "mysql"]}
    ),
    RAGDocument(
        title="Category Sales Performance and Item Counts",
        content=(
            "Question: List product categories with total items sold and net revenue.\n"
            "SQL Pattern:\n"
            "SELECT cat.name AS category_name, SUM(oi.quantity) AS total_items_sold, SUM(oi.unit_price * oi.quantity) AS category_revenue\n"
            "FROM demo.categories cat\n"
            "JOIN demo.products p ON cat.id = p.category_id\n"
            "JOIN demo.order_items oi ON p.id = oi.product_id\n"
            "GROUP BY cat.id, cat.name\n"
            "ORDER BY category_revenue DESC;"
        ),
        dialect="all",
        category="example",
        metadata_json={"tags": ["category", "revenue", "multi-join"]}
    ),
    RAGDocument(
        title="Customer Order Count and Activity Status",
        content=(
            "Question: Find customers who have placed more than 3 orders.\n"
            "SQL Pattern:\n"
            "SELECT c.id, c.name, c.email, COUNT(o.id) AS order_count\n"
            "FROM demo.customers c\n"
            "JOIN demo.orders o ON c.id = o.customer_id\n"
            "GROUP BY c.id, c.name, c.email\n"
            "HAVING COUNT(o.id) > 3\n"
            "ORDER BY order_count DESC;"
        ),
        dialect="all",
        category="example",
        metadata_json={"tags": ["having", "customer_orders", "count"]}
    ),
    RAGDocument(
        title="Safe Read-Only Query Constraints",
        content=(
            "Guideline: Always produce single SELECT statements. Never produce DROP, ALTER, INSERT, UPDATE, DELETE, or EXECUTE. "
            "In Demo mode, qualify tables with 'demo.' prefix. In Custom mode, use table names exactly as provided in SchemaCatalog."
        ),
        dialect="all",
        category="documentation",
        metadata_json={"tags": ["safety", "rules"]}
    )
]


def load_jsonl_documents(data_dir: Path) -> list[RAGDocument]:
    """Load RAG documents from data/rag/*.jsonl files."""
    documents = []
    if not data_dir.exists():
        return documents

    for jsonl_path in data_dir.glob("*.jsonl"):
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    item = json.loads(line_str)
                    doc = RAGDocument(
                        title=item.get("title", "Untitled"),
                        content=item.get("content", ""),
                        dialect=item.get("dialect", "all"),
                        category=item.get("category", "example"),
                        metadata_json=item.get("metadata_json", {})
                    )
                    documents.append(doc)
        except Exception as exc:
            print(f"Warning: Failed to load documents from {jsonl_path.name}: {exc}")

    return documents


async def main():
    data_dir = Path(__file__).resolve().parent.parent / "data" / "rag"
    jsonl_docs = load_jsonl_documents(data_dir)

    corpus = jsonl_docs if jsonl_docs else DEFAULT_CORPUS
    print(f"Loaded {len(corpus)} RAG corpus documents (from {'data/rag/*.jsonl' if jsonl_docs else 'DEFAULT_CORPUS'}).")

    print("Initializing RAG vector schema in PostgreSQL...")
    schema_ok = vector_store.ensure_rag_schema()
    if not schema_ok:
        print("Warning: Could not connect to PostgreSQL or initialize pgvector extension.")
        print("Note: In test or dev mode without PostgreSQL running, vector_store will handle search gracefully.")
        return

    print(f"Generating embeddings for {len(corpus)} RAG corpus documents...")
    texts = [f"{doc.title}\n{doc.content}" for doc in corpus]
    embeddings = await embedding_service.generate_embeddings_batch(texts)

    dim = embedding_service.dimension
    if embeddings and len(embeddings[0]) != dim:
        print(f"Error: embedding length {len(embeddings[0])} does not match configured dimension {dim}.")
        return
    if dim != 1536:
        print(f"Warning: configured embedding dimension is {dim}; app.rag_documents.embedding is vector(1536).")

    print("Replacing corpus in app.rag_documents...")
    try:
        count = vector_store.replace_corpus(corpus, embeddings)
        print(f"Successfully indexed {count} RAG documents into PostgreSQL + pgvector (vector({dim})).")
    except Exception as e:
        print(f"Error during document indexing: {type(e).__name__}")


if __name__ == "__main__":
    asyncio.run(main())


"""
Unit tests for RAG + pgvector layer (Phase 7).
Tests embeddings generator, RAG data models, VectorStore fallback, and RAGRetriever prompt context formatting.
"""

import math
import pytest
from unittest.mock import patch, MagicMock

from app.rag.models import RAGDocument, RAGSearchResult
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStore
from app.rag.retriever import RAGRetriever
from app.schema.catalog import SchemaCatalog, TableSchema, ColumnSchema
from app.llm.prompt import build_user_prompt


def test_embedding_service_mock_generation():
    service = EmbeddingService(api_key=None, dimension=1536)
    
    # Generate single embedding
    import asyncio
    emb = asyncio.run(service.generate_embedding("Top customers in demo database"))

    assert isinstance(emb, list)
    assert len(emb) == 1536
    
    # Check L2 normalization (sum of squares should equal ~1.0)
    l2_norm = math.sqrt(sum(v * v for v in emb))
    assert abs(l2_norm - 1.0) < 1e-4

    # Check deterministic behavior
    emb2 = asyncio.run(service.generate_embedding("Top customers in demo database"))
    assert emb == emb2


def test_rag_document_models():
    doc = RAGDocument(
        title="Top Orders",
        content="SELECT * FROM demo.orders LIMIT 10",
        dialect="postgres",
        category="example",
        similarity_score=0.92
    )
    assert doc.title == "Top Orders"
    assert doc.similarity_score == 0.92

    search_result = RAGSearchResult(query="show orders", documents=[doc])
    assert len(search_result.documents) == 1
    assert search_result.documents[0].title == "Top Orders"


@pytest.mark.asyncio
async def test_rag_retriever_context_formatting():
    from unittest.mock import AsyncMock
    embedder = MagicMock()
    embedder.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

    mock_doc1 = RAGDocument(
        title="Monthly Revenue",
        content="SELECT DATE_TRUNC('month', created_at), SUM(total_amount) FROM demo.orders GROUP BY 1;",
        dialect="postgres",
        similarity_score=0.88
    )
    mock_doc2 = RAGDocument(
        title="Top Categories",
        content="SELECT category_id, COUNT(*) FROM demo.products GROUP BY 1;",
        dialect="postgres",
        similarity_score=0.75
    )

    store = MagicMock()
    store.similarity_search.return_value = [mock_doc1, mock_doc2]

    retriever = RAGRetriever(embedder=embedder, store=store)
    context = await retriever.retrieve_context("What are monthly sales?", dialect="postgres", top_k=2)

    assert "--- RAG Context Item #1: Monthly Revenue (relevance: 0.88) ---" in context
    assert "--- RAG Context Item #2: Top Categories (relevance: 0.75) ---" in context
    assert "SELECT DATE_TRUNC" in context
    assert "SELECT category_id" in context


@pytest.mark.asyncio
async def test_prompt_builder_incorporates_rag_retrieval():
    catalog = SchemaCatalog(dialect="postgres")
    catalog.tables["orders"] = TableSchema(
        name="orders",
        columns=[ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True)]
    )

    rag_text = "--- RAG Context Item #1: Example ---\nSELECT id FROM demo.orders LIMIT 5;"
    user_prompt = build_user_prompt(
        question="Show orders",
        schema_catalog=catalog,
        rag_context=rag_text
    )

    assert "USER QUESTION: Show orders" in user_prompt
    assert "RETRIEVED EXAMPLES & CONTEXT" in user_prompt
    assert "SELECT id FROM demo.orders LIMIT 5;" in user_prompt


def test_vector_store_graceful_fallback_when_db_down():
    store = VectorStore(dimension=1536)
    # Even if PostgreSQL is not reachable, similarity_search should not crash the app
    with patch("app.rag.vector_store.get_app_connection", side_effect=Exception("DB Connection failed")):
        results = store.similarity_search([0.0] * 1536, dialect="postgres")
        assert results == []


@pytest.mark.asyncio
async def test_gemini_embedding_batch_parsed_to_1536():
    service = EmbeddingService(
        api_key="valid_api_key",
        model="gemini-embedding-001",
        dimension=1536,
        provider="gemini",
    )
    values = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"embeddings": [{"values": values}]}

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        vectors = await service.generate_embeddings_batch(["Top customers"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 1536
    l2_norm = math.sqrt(sum(v * v for v in vectors[0]))
    assert abs(l2_norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_embedding_service_batch_generation():
    service = EmbeddingService(api_key=None, dimension=1536)
    batch = ["First text", "Second text", "Third text"]
    embeddings = await service.generate_embeddings_batch(batch)

    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 1536
        l2_norm = math.sqrt(sum(v * v for v in emb))
        assert abs(l2_norm - 1.0) < 1e-4

    # Empty batch returns empty list
    empty_res = await service.generate_embeddings_batch([])
    assert empty_res == []


@pytest.mark.asyncio
async def test_rag_retriever_empty_question_or_error():
    retriever = RAGRetriever()
    # Empty question -> empty string
    res = await retriever.retrieve_context("", dialect="postgres")
    assert res == ""

    # Exception during retrieval -> returns empty string gracefully
    with patch.object(retriever.embedder, "generate_embedding", side_effect=Exception("Embedder error")):
        res_err = await retriever.retrieve_context("Any question", dialect="postgres")
        assert res_err == ""


def test_vector_store_add_documents_validation():
    store = VectorStore(dimension=1536)
    doc = RAGDocument(title="T", content="C")
    with pytest.raises(ValueError, match="Number of documents must match number of embeddings"):
        store.add_documents([doc], [])


def test_load_jsonl_documents():
    import sys
    from pathlib import Path
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    scripts_dir = root_dir / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from build_rag_index import load_jsonl_documents
    data_dir = root_dir / "data" / "rag"
    docs = load_jsonl_documents(data_dir)
    assert isinstance(docs, list)
    assert len(docs) > 0
    assert any(d.title == "Top 5 Spending Customers" for d in docs)



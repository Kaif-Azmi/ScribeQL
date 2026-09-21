"""
RAGRetriever orchestrates embedding generation and vector search to construct
compact, high-relevance prompt context for the LLM pipeline.
"""

import logging
from typing import List, Optional

from app.rag.embeddings import EmbeddingService, embedding_service
from app.rag.vector_store import VectorStore, vector_store
from app.rag.models import RAGDocument

logger = logging.getLogger(__name__)


class RAGRetriever:
    def __init__(
        self,
        embedder: Optional[EmbeddingService] = None,
        store: Optional[VectorStore] = None
    ):
        self.embedder = embedder or embedding_service
        self.store = store or vector_store

    async def retrieve_context(
        self,
        question: str,
        dialect: str = "postgres",
        top_k: int = 3
    ) -> str:
        """
        Embed the user question, retrieve top_k matching RAG documents from pgvector,
        and format them into a clean context block for the LLM prompt.
        """
        if not question or not question.strip():
            return ""

        try:
            # 1. Generate query vector
            query_embedding = await self.embedder.generate_embedding(question)

            # 2. Vector search via pgvector
            docs = self.store.similarity_search(
                query_embedding=query_embedding,
                dialect=dialect,
                top_k=top_k
            )

            if not docs:
                return ""

            # 3. Format into structured context string
            context_blocks = []
            for i, doc in enumerate(docs, start=1):
                score_str = f" (relevance: {doc.similarity_score:.2f})" if doc.similarity_score is not None else ""
                block = f"--- RAG Context Item #{i}: {doc.title}{score_str} ---\n{doc.content}"
                context_blocks.append(block)

            return "\n\n".join(context_blocks)

        except Exception as exc:
            logger.warning(f"RAG retrieval encountered an error: {exc}. Proceeding with empty RAG context.")
            return ""


rag_retriever = RAGRetriever()

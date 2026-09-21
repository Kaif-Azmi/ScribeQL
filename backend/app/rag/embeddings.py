"""
Embedding Service for ScribeQL RAG pipeline.
Default provider is Gemini (`gemini-embedding-001`) with output_dimensionality=1536
to match app.rag_documents.embedding vector(1536).
"""

import math
import hashlib
import logging
from typing import List, Optional
import httpx

from app.config.settings import settings
from app.llm.gemini import (
    build_embed_payload,
    embed_content_url,
    extract_embeddings,
    gemini_headers,
    l2_normalize,
    uses_gemini,
)

logger = logging.getLogger(__name__)


class EmbeddingProviderError(Exception):
    """Raised when embedding generation fails."""
    pass


class EmbeddingService:
    def __init__(
        self,
        api_key: Optional[str] = ...,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
        provider: Optional[str] = None,
    ):
        if api_key is ...:
            self.api_key = settings.llm_api_key
        else:
            self.api_key = api_key or ""
        self.model = model or settings.embedding_model or "gemini-embedding-001"
        self.dimension = dimension or settings.embedding_dimension or 1536
        self.base_url = base_url or settings.llm_base_url or "https://generativelanguage.googleapis.com/v1beta"
        self.timeout = timeout
        self.provider = provider or settings.llm_provider or "gemini"

    def _gemini_enabled(self) -> bool:
        return uses_gemini(self.provider, self.model, self.base_url)

    async def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> List[float]:
        results = await self.generate_embeddings_batch([text], task_type=task_type)
        return results[0]

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> List[List[float]]:
        if not texts:
            return []

        if not self.api_key or self.api_key.strip() in ("", "dummy", "placeholder"):
            return [self._generate_mock_embedding(t) for t in texts]

        try:
            if self._gemini_enabled():
                vectors = await self._embed_gemini(texts, task_type)
            else:
                vectors = await self._embed_openai_compatible(texts)
            normalized = []
            for vec in vectors:
                if len(vec) != self.dimension:
                    raise EmbeddingProviderError(
                        f"Embedding length {len(vec)} does not match required {self.dimension}."
                    )
                normalized.append(l2_normalize(vec))
            return normalized
        except EmbeddingProviderError:
            logger.warning("Embedding request failed; using mock fallback.")
            return [self._generate_mock_embedding(t) for t in texts]
        except Exception as exc:
            logger.warning("Embedding request failed: %s, using mock fallback.", type(exc).__name__)
            return [self._generate_mock_embedding(t) for t in texts]

    async def _embed_gemini(self, texts: List[str], task_type: str) -> List[List[float]]:
        url = embed_content_url(self.base_url, self.model)
        payload = build_embed_payload(texts, self.model, self.dimension, task_type)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers=gemini_headers(self.api_key),
                json=payload,
            )
        if response.status_code != 200:
            raise EmbeddingProviderError(f"Embedding API error HTTP {response.status_code}")
        vectors = extract_embeddings(response.json())
        if len(vectors) != len(texts):
            raise EmbeddingProviderError("Gemini returned a different number of embeddings than inputs.")
        return vectors

    async def _embed_openai_compatible(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": texts},
            )
        if response.status_code != 200:
            raise EmbeddingProviderError(f"Embedding API error HTTP {response.status_code}")
        data = response.json()
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    def _generate_mock_embedding(self, text: str) -> List[float]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(self.dimension):
            byte_val = seed[(i + (i // len(seed))) % len(seed)]
            val = ((byte_val ^ (i * 31 % 256)) / 255.0) - 0.5
            vector.append(val)
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


embedding_service = EmbeddingService()

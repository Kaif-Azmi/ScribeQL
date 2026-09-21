"""
Pydantic models for RAG (Retrieval-Augmented Generation) documents and search results.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class RAGDocument(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., description="Short title describing the example or pattern.")
    content: str = Field(..., description="The actual text content (e.g. NL question + SQL query).")
    dialect: str = Field(default="all", description="Target SQL dialect: postgres, mysql, or all.")
    category: str = Field(default="example", description="Category: example, pattern, or documentation.")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Additional context or metadata.")
    similarity_score: Optional[float] = Field(default=None, description="Similarity score from vector search (0.0 to 1.0).")


class RAGSearchResult(BaseModel):
    query: str
    documents: List[RAGDocument] = Field(default_factory=list)

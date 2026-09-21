"""
Structured Pydantic models for LLM SQL generation.
Matches specification in docs/architecture.md and docs/api.md Section 3.3.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class LLMQueryPlan(BaseModel):
    select: List[str] = Field(default_factory=list)
    distinct: bool = False
    group_by: List[str] = Field(default_factory=list)
    having: Optional[str] = None
    limit: Optional[int] = None
    ctes: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


class LLMGenerationResult(BaseModel):
    query_plan: LLMQueryPlan = Field(default_factory=LLMQueryPlan)
    sql: str
    assumptions: List[str] = Field(default_factory=list)
    explanation: str
    raw_response: Optional[str] = None

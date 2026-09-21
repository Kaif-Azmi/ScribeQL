"""
Pydantic schemas for Query Session management.
Matches specification in docs/api.md Sections 3.1 and 3.7.
"""

from typing import Optional, Literal, Any
from pydantic import BaseModel, Field, model_validator


class CreateSessionRequest(BaseModel):
    mode: Literal["demo", "custom"]

    @model_validator(mode="before")
    @classmethod
    def reject_dialect_field(cls, data: Any) -> Any:
        if isinstance(data, dict) and "dialect" in data:
            raise ValueError("dialect field must not be sent to POST /session.")
        return data


class CreateSessionResponse(BaseModel):
    session_id: str
    mode: str
    dialect: Optional[str] = None
    expires_at: str


class RecoverSessionResponse(BaseModel):
    session_id: str
    mode: str
    dialect: Optional[str] = None
    has_schema: bool
    expires_at: str

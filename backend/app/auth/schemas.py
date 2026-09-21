"""
Pydantic schemas for authentication and user account endpoints.
Matches contract defined in docs/api.md Section 3.5 & 3.6.
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr, field_validator


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)


class VerifyTokenRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10, max_length=128)


class DeleteAccountRequest(BaseModel):
    confirm: bool

    @field_validator("confirm")
    @classmethod
    def must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("confirm field must be true")
        return v


class UserResponse(BaseModel):
    email: str
    has_password: bool
    google_linked: bool


class UsageQuotaItem(BaseModel):
    limit: int
    used: int
    remaining: int


class UsageSummary(BaseModel):
    queries: UsageQuotaItem
    uploads: UsageQuotaItem
    resets_at: str


class MeResponse(BaseModel):
    user: UserResponse
    usage: UsageSummary

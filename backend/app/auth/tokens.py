"""
Token generation and hashing utilities for email verification, reset links, and sessions.
"""

import hashlib
import secrets


def generate_secure_token() -> str:
    """Generate a high-entropy URL-safe token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

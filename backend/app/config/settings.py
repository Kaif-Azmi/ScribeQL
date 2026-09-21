from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    database_url: str = "postgresql://app_rw:password@localhost:5432/scribeql"
    demo_database_url: str = "postgresql://sql_ro:password@localhost:5432/scribeql"
    admin_database_url: str = ""

    auth_cookie_name: str = "__Host-sid"
    auth_cookie_secure: bool = False
    session_ttl_hours: int = 24

    secret_key: str = "insecure-dev-secret-key-change-in-production"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:5173/api/auth/google/callback"

    # LLM Settings (Gemini)
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_model: str = "gemini-3.6-flash"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_timeout_seconds: float = 60.0
    global_daily_llm_budget: int = 1000
    daily_query_limit: int = 20
    daily_upload_limit: int = 3
    query_row_cap: int = 200
    query_deadline_seconds: float = 40.0
    max_question_chars: int = 500

    # RAG & Embedding Settings (Gemini, must match app.rag_documents.embedding vector(1536))
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = 1536

    @property
    def cors_origins(self) -> List[str]:
        origins = ["https://www.sqlsense.tech"]
        if self.app_env == "development":
            origins.append("http://localhost:5173")
            origins.append("http://127.0.0.1:5173")
            if self.frontend_origin and self.frontend_origin not in origins:
                origins.append(self.frontend_origin)
        return origins

    model_config = SettingsConfigDict(
        env_file=[str(_PROJECT_ROOT / ".env"), ".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

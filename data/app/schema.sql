-- ScribeQL Application Database Schema
-- Dialect: PostgreSQL
-- Matches architecture specification in docs/architecture.md Section 8

-- pgvector and app schema are provisioned by the database admin.

-- 1. Users
CREATE TABLE IF NOT EXISTS app.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    is_verified BOOLEAN NOT NULL DEFAULT false,
    google_sub VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON app.users(email);

-- 2. Auth Identities (OAuth providers)
CREATE TABLE IF NOT EXISTS app.auth_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_auth_identities_user_id ON app.auth_identities(user_id);

-- 3. Email Tokens (Verification and Password Reset)
CREATE TABLE IF NOT EXISTS app.email_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    token_type VARCHAR(20) NOT NULL, -- 'verify' | 'reset'
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_email_tokens_hash ON app.email_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_email_tokens_user_id ON app.email_tokens(user_id);

-- 4. Auth Sessions (Server-side login sessions)
CREATE TABLE IF NOT EXISTS app.auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash ON app.auth_sessions(session_token_hash);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON app.auth_sessions(user_id);

-- 5. Query Sessions (Workspace mode, dialect, and schema)
CREATE TABLE IF NOT EXISTS app.sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    mode VARCHAR(20) NOT NULL, -- 'demo' | 'custom'
    dialect VARCHAR(20),       -- 'postgres' | 'mysql'
    has_schema BOOLEAN NOT NULL DEFAULT false,
    schema_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON app.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON app.sessions(expires_at);

-- 6. Schema Catalogs (Stored custom DDL schemas)
CREATE TABLE IF NOT EXISTS app.schema_catalogs (
    id VARCHAR(64) PRIMARY KEY,
    dialect VARCHAR(20) NOT NULL,
    catalog_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Query Logs
CREATE TABLE IF NOT EXISTS app.query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(64) REFERENCES app.sessions(id) ON DELETE SET NULL,
    user_id UUID REFERENCES app.users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    sql TEXT,
    status VARCHAR(50) NOT NULL,
    latency_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_logs_user_id ON app.query_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_session_id ON app.query_logs(session_id);

-- 8. Query Attempts (Retry history for validation / execution errors)
CREATE TABLE IF NOT EXISTS app.query_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_log_id UUID NOT NULL REFERENCES app.query_logs(id) ON DELETE CASCADE,
    attempt_no INT NOT NULL,
    sql TEXT,
    error_type VARCHAR(100),
    error_text TEXT,
    latency_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_attempts_log_id ON app.query_attempts(query_log_id);

-- 9. Usage Counters (Daily per-user query and upload allowances)
CREATE TABLE IF NOT EXISTS app.usage_counters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL,
    query_count INT NOT NULL DEFAULT 0,
    upload_count INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, usage_date)
);

CREATE INDEX IF NOT EXISTS idx_usage_counters_user_date ON app.usage_counters(user_id, usage_date);

-- 10. Global Budget (Daily aggregate LLM budget)
CREATE TABLE IF NOT EXISTS app.global_budget (
    budget_date DATE PRIMARY KEY,
    call_count INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. Usage Tombstones (Prevent quota reset gaming through account recreation)
CREATE TABLE IF NOT EXISTS app.usage_tombstones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    email_hash VARCHAR(64) NOT NULL,
    deleted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usage_tombstones_email_hash ON app.usage_tombstones(email_hash);

-- 12. RAG Documents (Vector store for NL->SQL examples and guidance)
CREATE TABLE IF NOT EXISTS app.rag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    dialect VARCHAR(20) NOT NULL DEFAULT 'all',
    category VARCHAR(50) NOT NULL DEFAULT 'example',
    metadata_json JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS rag_documents_embedding_hnsw_idx 
ON app.rag_documents USING hnsw (embedding vector_cosine_ops);

-- 13. LLM Response Cache
CREATE TABLE IF NOT EXISTS app.llm_cache (
    prompt_hash VARCHAR(64) PRIMARY KEY,
    model VARCHAR(100) NOT NULL,
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_cache_expires_at ON app.llm_cache(expires_at);

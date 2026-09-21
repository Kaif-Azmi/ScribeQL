# ScribeQL: Architecture

Natural-language-to-SQL platform with **RAG**, **PostgreSQL + pgvector**, a safety-first SQL pipeline, and measurable evaluation.

## 1. System Overview

A user signs in, chooses a mode, asks a question in English or Hinglish, and receives SQL.

- **Demo:** built-in PostgreSQL e-commerce database; SQL is generated, safety-checked, validated, and executed read-only; rows are returned.
- **Custom:** user uploads DDL and selects PostgreSQL or MySQL; SQL is generated and validated but never executed.

```text
Landing → Auth → Mode
              ├── Demo   → Studio → RAG → LLM → Safety → Validate → Execute → Results
              └── Custom → Upload → Studio → RAG → LLM → Safety → Validate → SQL
```

There is no anonymous mode. A verified account is required.

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | JavaScript + React + Vite |
| Backend | Python + FastAPI |
| Database | PostgreSQL |
| Vector search | pgvector |
| AI retrieval | RAG + embedding model |
| LLM | Hosted LLM provider |
| SQL parsing / validation | sqlglot |
| Authentication | Server-side sessions + HttpOnly cookie |
| OAuth | Google OAuth with PKCE |
| Password hashing | Argon2id |
| Reverse proxy | Caddy |
| Deployment | Docker Compose + single VM |

## 3. High-Level Architecture

```text
React + Vite
     │
    HTTPS
     ▼
   Caddy
     │
     ▼
  FastAPI
     │
     ├── Auth / Sessions
     │
     ├── Query Pipeline
     │      ├── SchemaCatalog
     │      ├── RAG Retrieval
     │      │      ├── Embeddings
     │      │      └── PostgreSQL + pgvector
     │      ├── LLM Generation
     │      ├── AST Safety
     │      ├── Validation
     │      └── Demo Executor
     │
     └── PostgreSQL + pgvector
            ├── app schema
            └── demo schema
```

`pgvector` runs inside the existing PostgreSQL instance. No separate vector database is required in v1.

## 4. Core Components

### 4.1 Frontend

React + Vite SPA responsible for routing, authentication screens, mode selection, schema upload, Studio UI, query results, usage states, and error states.

The exact screen/state contract is defined in `ui.md`.

### 4.2 FastAPI Backend

FastAPI exposes the API and coordinates authentication, query sessions, schema processing, RAG, LLM generation, SQL safety, validation, execution, usage limits, and logging.

The exact endpoint contract is defined in `api.md`.

### 4.3 SchemaCatalog

`SchemaCatalog` is the authoritative schema representation.

It contains tables, columns, types, PK/FK relationships, enum/check information, comments, and accepted user hints.

It is built from:

- the live demo database, or
- parsed uploaded DDL.

RAG adds supporting examples/patterns but does not override the catalog.

## 5. RAG Architecture

RAG retrieves relevant examples and SQL patterns before generation.

```text
Question
   ↓
Embedding model
   ↓
pgvector similarity search
   ↓
Top-k relevant context
   ↓
Prompt + SchemaCatalog
   ↓
LLM
```

The RAG corpus can contain curated natural-language-to-SQL examples and reusable SQL patterns.

Retrieval should be filtered by metadata such as dialect and corpus scope where needed. Retrieved content is untrusted context and still passes through the same SQL safety and validation pipeline.

RAG is an augmentation layer, not the source of truth for schema structure.

## 6. Query Pipeline

```text
1. Authenticate
      ↓
2. Validate question + session
      ↓
3. Load SchemaCatalog + dialect
      ↓
4. Retrieve RAG context
      ↓
5. Generate SQL
      ↓
6. AST safety allowlist
      ↓
7. sqlglot validation
      ↓
8. Demo: EXPLAIN + execute
   Custom: return SQL
      ↓
9. Retry when allowed
      ↓
10. Log
```

### Mode differences

| Stage | Demo | Custom |
|---|---|---|
| Dialect | PostgreSQL | PostgreSQL / MySQL |
| RAG | Yes | Yes |
| Safety | Dialect-aware AST allowlist | Dialect-aware AST allowlist |
| Validation | `sqlglot qualify` + `EXPLAIN` | `sqlglot qualify` |
| Execution | Yes | No |
| Results | Rows | SQL only |
| Retry triggers | SQL errors + result sanity | Validation errors |

The executor is deliberately pluggable: `sql_ro` for demo and `None` for custom.

## 7. Safety Architecture

Model output is untrusted. Prompt instructions are not a security boundary.

### Boundary 1: AST allowlist

The generated SQL is parsed using the session dialect. The layer:

- requires a single statement
- allows `SELECT` / select-based set operations, optionally with `WITH`
- rejects writes, DDL, dangerous commands, locking clauses, and disallowed functions
- verifies table references against `SchemaCatalog`
- blocks system and application namespaces

The allowlist is dialect-aware for PostgreSQL and MySQL.

### Boundary 2: Database permissions

Only demo SQL reaches a database.

```text
sql_ro
 ├── SELECT on demo schema
 ├── no write access
 ├── no app-schema access
 └── timeout / resource limits
```

An application watchdog also bounds execution. Results are capped with a server-side cursor.

Custom schemas are parsed only; uploaded SQL is never executed.

## 8. Database Architecture

```text
PostgreSQL
│
├── demo schema
│     └── 8-table e-commerce database
│
└── app schema
      ├── users
      ├── auth_identities
      ├── auth_sessions
      ├── email_tokens
      ├── sessions
      ├── schema_catalogs
      ├── query_logs
      ├── query_attempts
      ├── usage_counters
      ├── global_budget
      ├── usage_tombstones
      ├── rag_documents
      └── llm_cache
```

`rag_documents` stores retrieval content, embeddings, and metadata used by pgvector search.

Application access uses `app_rw`; demo execution uses `sql_ro`.

## 9. Authentication and Sessions

Two separate concepts exist:

- **Auth session:** server-side login session referenced by an `HttpOnly` cookie.
- **Query session:** mode, dialect, optional uploaded schema, and query state.

Rules:

- Demo sessions are always PostgreSQL.
- Custom dialect is set on the first successful upload and then locked.
- Sessions have a fixed TTL.
- Every query session belongs to exactly one user.
- `GET /session` recovers the current session after refresh.

Authentication supports Google and email/password with verification, reset, and account deletion.

## 10. Usage, Quotas, and Caching

Default personal limits:

- 20 queries/day
- 3 successful schema uploads/day

Additional protection includes per-user/per-IP rate limits and a global daily LLM budget.

Personal query usage is charged once for the first live LLM call of a query. Retries consume global LLM budget per call.

There are two separate caching concepts:

```text
pgvector / RAG retrieval
→ finds relevant context

LLM response cache
→ reuses generated responses for matching prompt/model/version inputs
```

A fully cached query does not consume the personal query allowance. In demo mode a cached SQL response can still execute live, so database safeguards remain mandatory.

## 11. Evaluation

Primary demo metric: **execution accuracy**.

Generated SQL is compared with gold SQL by executing both against a frozen database and comparing result sets.

Evaluation includes:

- development and test splits
- English/Hinglish paired questions
- difficulty breakdowns
- repeated runs and confidence intervals
- component ablations
- executable rate reported separately

The optimization sequence is:

```text
Baseline
  ↓
+ RAG
  ↓
+ Plan
  ↓
+ Validation
  ↓
+ Retry
```

Custom mode is not execution-tested in v1, so it reports valid-SQL rate rather than execution accuracy.

## 12. Deployment

```text
Single VM
├── Caddy
├── FastAPI
└── PostgreSQL + pgvector
```

Production serves the frontend and `/api` from the same host.

Caddy provides TLS, canonical-host redirect, security headers, and proxy controls.

Secrets such as LLM, OAuth, and email credentials remain server-side.

Nightly application-schema backups are taken; the demo database is rebuilt from its frozen dump.

## 13. Key Architectural Decisions

| Decision | Reason |
|---|---|
| React + Vite | Lightweight SPA with explicit UI state flow |
| FastAPI | Single Python application/API layer |
| PostgreSQL + pgvector | Relational data and vector retrieval in one datastore |
| RAG | Adds relevant examples and SQL patterns to generation |
| Full SchemaCatalog context | Keeps schema context explicit in v1 |
| sqlglot | Dialect-aware SQL parsing and validation |
| AST allowlist + DB role | Defense in depth against unsafe model output |
| Read-only demo executor | Real results without write access |
| No custom execution | Uploaded schemas must never execute on the app database |
| Server-side auth sessions | Revocable authentication without exposing tokens to scripts |
| Single process | Small demo audience; avoids unnecessary distributed infrastructure |

## 14. Non-Goals for v1

- high-throughput distributed processing
- multi-turn conversation
- query history/workspaces
- teams, roles, billing, or paid tiers
- execution against uploaded schemas
- MySQL demo database
- separate vector database
- large-schema retrieval replacing full-schema prompting

## 15. Known Limitations

- Custom SQL is not execution-verified.
- MySQL has less evaluation coverage than the PostgreSQL demo path.
- RAG quality depends on corpus quality and retrieval accuracy.
- Demo accuracy does not automatically generalize to arbitrary schemas.
- Free-tier model behavior may change over time.
- Multiple-account abuse cannot be completely eliminated.
- Demo and app schemas share one PostgreSQL instance, so resource controls remain important.

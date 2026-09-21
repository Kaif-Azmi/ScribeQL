# ScribeQL — Development Plan

## 1. Objective

Build ScribeQL as a web-based natural-language-to-SQL application with two modes:

- **Demo mode:** uses the built-in PostgreSQL e-commerce database, executes safe SQL, and shows results.
- **Custom mode:** accepts a user DDL schema, generates and validates SQL in PostgreSQL or MySQL dialect, but never executes uploaded-schema SQL.

Core stack:

- **Frontend:** JavaScript + React + Vite
- **Backend:** Python + FastAPI
- **Database:** PostgreSQL + pgvector
- **AI:** LLM + RAG + embeddings
- **SQL:** sqlglot
- **Authentication:** server-side sessions, email/password, Google OAuth

Detailed API behavior belongs in `docs/api.md`. Screen behavior belongs in `docs/ui.md`. High-level system design belongs in `docs/architecture.md`.

---

## 2. Development Principles

1. Build from the backend contract outward.
2. Keep `SchemaCatalog` as the single source of truth for schema-aware operations.
3. Treat all LLM output and user-provided text as untrusted input.
4. Build SQL safety before optimizing generation quality.
5. Keep RAG inside the backend; the frontend never talks directly to pgvector or the LLM provider.
6. Do not introduce Docker, Caddy, CI/CD, or production infrastructure during the initial local-build stages.
7. Complete and verify each phase before moving to the next phase.

---

## Phase 0 — Project Foundation

### Deliverables

- Create the repository structure.
- Create `frontend/` with React + Vite using JavaScript.
- Create `backend/` with FastAPI.
- Create `docs/` and place:
  - `architecture.md`
  - `api.md`
  - `ui.md`
  - `plan.md`
- Create `.env.example` and `.gitignore`.
- Set up local development commands.
- Add a minimal FastAPI health endpoint.
- Verify React → FastAPI connectivity.

### Exit criteria

- Frontend runs locally.
- Backend runs locally.
- Frontend can successfully call the backend.

---

## Phase 1 — PostgreSQL Foundation

### Deliverables

- Set up PostgreSQL locally.
- Enable the `pgvector` extension.
- Create the application database/schema.
- Create the demo database schema.
- Add seeded e-commerce data.
- Create separate database access roles for application data and demo read-only execution.
- Establish the backend database connection layer.
- Add migrations with Alembic once persistent application tables are introduced.

### Exit criteria

- PostgreSQL is reachable from FastAPI.
- Demo data is available.
- `pgvector` is enabled.
- Read/write application access is separated from demo read-only access.

---

## Phase 2 — SchemaCatalog

### Deliverables

Build the common schema representation used throughout the system.

`SchemaCatalog` should represent:

- tables
- columns
- data types
- primary keys
- foreign keys
- enums / CHECK-derived values
- comments where available
- dialect

Implement two sources:

- Demo DB inspector → catalog
- Uploaded DDL parser → catalog

### Exit criteria

- Demo PostgreSQL schema produces a valid catalog.
- A sample PostgreSQL DDL produces a valid catalog.
- A sample MySQL DDL produces a valid catalog.
- Prompt building, validation, safety, and RAG can consume the same catalog structure.

---

## Phase 3 — Authentication and User Model

### Deliverables

Implement the authentication foundation:

- users
- email/password sign-up
- password hashing with Argon2id
- email verification
- sign-in
- sign-out
- server-side auth sessions
- `HttpOnly` auth cookie
- `GET /me`
- Google OAuth
- forgot password
- reset password
- account deletion

Implement the user ownership boundary for query sessions.

### Exit criteria

- A verified user can sign in and sign out.
- Protected endpoints reject unauthenticated users.
- Sessions are server-side and revocable.
- User A cannot access User B's resources.

---

## Phase 4 — Query Sessions

### Deliverables

Implement query-session management:

- `POST /session`
- `GET /session`
- demo/custom modes
- fixed dialect behavior
- custom-session dialect locking
- session ownership
- session expiry
- session recovery
- maximum active-session limit

### Exit criteria

- Demo session can be created/recovered.
- Custom session can be created/recovered.
- Dialect behavior matches `api.md`.
- Expired or non-owned sessions are handled correctly.

---

## Phase 5 — Custom Schema Upload

### Deliverables

Implement:

- `.sql` / `.txt` upload
- PostgreSQL/MySQL dialect selector
- DDL parsing with sqlglot
- table-count and file-size limits
- system namespace protection
- supported statement extraction
- warnings for skipped statements
- optional JSON hints
- schema replacement within the same dialect
- schema catalog persistence

Uploaded DDL must **never be executed**.

### Exit criteria

- Valid PostgreSQL and MySQL DDL can be uploaded.
- Invalid DDL receives the correct error.
- Reserved namespaces are rejected.
- Unsupported statements are skipped safely.
- Uploaded SQL never reaches a database executor.

---

## Phase 6 — LLM Integration

### Deliverables

Create the internal LLM layer:

- provider client
- environment-based API configuration
- structured generation
- JSON-schema output
- model configuration
- prompt versioning
- timeout handling
- provider-error handling

Generation output should contain the core fields required by the query pipeline:

- plan
- SQL
- assumptions
- explanation

### Exit criteria

- Backend can send a schema-aware request to the LLM.
- Structured output can be parsed reliably.
- Provider failures become controlled application errors.

---

## Phase 7 — RAG + pgvector

### Deliverables

Build the retrieval layer using PostgreSQL + pgvector.

Create:

- embedding generation
- RAG document/example storage
- vector schema and indexes
- ingestion/indexing script
- similarity retrieval
- retrieval filtering by relevant context
- prompt-context builder

Initial RAG data should focus on:

- curated NL → SQL examples
- SQL patterns
- schema/query knowledge useful for generation

The retriever should return compact, relevant context rather than dumping the entire vector store into the prompt.

### Exit criteria

- RAG documents can be indexed into PostgreSQL.
- A question can retrieve relevant examples/context.
- Retrieved context is passed into the LLM pipeline.
- No frontend code directly accesses pgvector.

---

## Phase 8 — SQL Safety Layer

### Deliverables

Implement the first hard boundary after generation:

- Parse SQL with sqlglot.
- Use the session dialect.
- Require exactly one statement.
- Allow only SELECT/set-operation roots.
- Reject writes, DDL, dangerous commands, locking clauses, and disallowed constructs.
- Walk CTEs and subqueries.
- Validate referenced tables against `SchemaCatalog`.
- Block system/app namespaces.
- Use per-dialect function allowlists.

### Exit criteria

- Safe SELECT queries pass.
- Unsafe queries are blocked before execution.
- PostgreSQL and MySQL syntax are parsed using the correct dialect.

---

## Phase 9 — Validation

### Deliverables

Implement dialect-aware SQL validation:

- sqlglot qualification against `SchemaCatalog`
- demo-mode PostgreSQL `EXPLAIN`
- validation error classification
- custom-mode validation without execution

### Exit criteria

- Unknown tables/columns are detected.
- Invalid SQL is surfaced as controlled validation failures.
- Demo queries are validated before execution.

---

## Phase 10 — Demo Executor

### Deliverables

Implement the PostgreSQL read-only execution boundary:

- dedicated read-only role
- read-only transaction
- statement timeout
- lock timeout
- application watchdog
- server-side cursor
- result row cap
- truncation detection
- cancellation of long-running execution

### Exit criteria

- Valid demo SQL returns rows.
- Writes cannot modify the database.
- App schema is inaccessible through the demo executor.
- Long-running queries are terminated safely.

---

## Phase 11 — Query Pipeline

### Deliverables

Connect the complete backend pipeline:

```text
Request
  ↓
Authentication
  ↓
Session ownership
  ↓
Question validation
  ↓
SchemaCatalog
  ↓
RAG retrieval
  ↓
Prompt/context build
  ↓
LLM generation
  ↓
SQL safety
  ↓
Validation
  ↓
Demo execution (demo only)
  ↓
Retry when allowed
  ↓
Response
```

Implement:

- structured query response
- retry loop
- attempt history
- request deadline
- logging
- status mapping

### Exit criteria

A user can successfully submit one question and receive:

- generated SQL
- assumptions
- explanation
- demo rows when applicable
- `execution_skipped` in custom mode

---

## Phase 12 — Usage Limits and Reliability

### Deliverables

Implement:

- per-user query limits
- per-user upload limits
- per-user/IP rate limits
- global LLM budget
- atomic usage counters
- one in-flight query per session
- response caching
- retry/backoff behavior
- `Retry-After` handling

### Exit criteria

- Limits cannot be bypassed through concurrent requests.
- A second query on the same session is rejected while one is running.
- Cache behavior matches the API contract.
- Usage is returned consistently.

---

## Phase 13 — Frontend Core

### Deliverables

Implement the React application structure:

- routing
- layouts
- API client
- authentication state
- session state
- usage state
- protected-route handling
- error handling

Implement public screens:

- Landing
- Sign in
- Sign up
- Verification
- Forgot/reset password
- Privacy

### Exit criteria

- Authentication flow works from the browser.
- Protected pages redirect correctly.
- API errors map to the UI states defined in `ui.md`.

---

## Phase 14 — Studio UI

### Deliverables

Implement `/start`:

- Demo Database card
- Use My Schema card
- usage summary

Implement Demo Studio:

- question input
- example chips
- loading state
- results table
- SQL disclosure
- assumptions
- explanation
- warnings
- errors
- usage meter

Implement Custom Studio:

- schema upload
- dialect selector
- hints
- upload progress
- schema summary
- replace schema
- SQL-only result state
- Copy SQL

### Exit criteria

All frontend states described in `ui.md` are implemented and connected to the API.

---

## Phase 15 — End-to-End Integration

### Deliverables

Verify complete user journeys.

### Demo flow

```text
Landing
→ Sign in
→ Start
→ Demo
→ Ask question
→ RAG
→ LLM
→ Safety
→ Validation
→ Execution
→ Results
```

### Custom flow

```text
Landing
→ Sign in
→ Start
→ Use my schema
→ Upload DDL + dialect
→ Parse schema
→ Ask question
→ RAG
→ LLM
→ Safety
→ Validation
→ SQL only
```

### Exit criteria

- No dead-end states.
- Refresh recovers the current session.
- Expired sessions are handled correctly.
- Usage updates correctly.
- Custom SQL is never executed.
- Demo execution remains read-only.

---

## Phase 16 — Security Hardening

### Deliverables

Test:

- multi-statement SQL
- write statements
- dangerous functions
- system catalog access
- app-schema access
- locking queries
- timeout bypass attempts
- prompt injection through questions
- prompt injection through DDL comments
- prompt injection through hints
- Unicode/comment obfuscation
- session ownership attacks
- open redirect attempts
- authentication enumeration
- rate-limit concurrency

Verify demo database row counts/checksums remain unchanged.

### Exit criteria

The safety and ownership boundaries behave as defined in `architecture.md` and `api.md`.

---

## Phase 17 — Production Readiness

Only after the application works locally:

- Docker
- Caddy
- HTTPS
- production environment configuration
- production PostgreSQL hardening
- backups
- cleanup jobs
- cache warming
- CI/CD
- deployment
- monitoring/logging

These are intentionally deferred until the core product is stable.

---

## 3. Recommended Build Order

```text
Phase 0  Foundation
   ↓
Phase 1  PostgreSQL + pgvector
   ↓
Phase 2  SchemaCatalog
   ↓
Phase 3  Authentication
   ↓
Phase 4  Query Sessions
   ↓
Phase 5  Custom Schema Upload
   ↓
Phase 6  LLM
   ↓
Phase 7  RAG + pgvector
   ↓
Phase 8  SQL Safety
   ↓
Phase 9  Validation
   ↓
Phase 10 Demo Executor
   ↓
Phase 11 Complete Query Pipeline
   ↓
Phase 12 Usage + Reliability
   ↓
Phase 13 Frontend Core
   ↓
Phase 14 Studio UI
   ↓
Phase 15 End-to-End Integration
   ↓
Phase 16 Security Hardening
   ↓
Phase 17 Production
```

## 4. MVP Release Scope

The first usable MVP is complete when Phases **0–15** are complete.

Required capabilities:

- React + Vite frontend
- FastAPI backend
- PostgreSQL + pgvector
- RAG retrieval
- LLM SQL generation
- sqlglot safety/validation
- Demo PostgreSQL execution
- Custom PostgreSQL/MySQL schema generation
- Authentication
- Sessions
- Usage limits
- Core Studio UI

Production infrastructure and hardening can follow as a separate release track.

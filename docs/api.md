# ScribeQL: API Reference

HTTP API for the ScribeQL Studio. Companion to [`architecture.md`](architecture.md).

- **Base URL (production):** `https://www.sqlsense.tech/api`
- **Base URL (development):** `http://localhost:8000/api`
- **Format:** JSON over HTTPS, except `POST /schema/upload` (multipart).
- **Auth:** every endpoint except `/health` and `/auth/*` requires a signed-in user, identified by an auth cookie (see Section 2.1). Query sessions belong to the user who created them (see Section 2.2).
- **Versioning:** none in v1. A breaking change would ship under `/api/v2`.
- **Internal AI retrieval:** the `/query` pipeline may use RAG with embeddings stored in PostgreSQL via pgvector. This is internal to the server; v1 exposes no public embedding or vector-search endpoints.

Limits below are defaults and are configurable through environment variables.

---

## 1. Conventions

### 1.1 Request and response

- Requests with a body use `Content-Type: application/json` unless stated otherwise.
- All timestamps are ISO 8601 in UTC.
- Every response carries an `X-Request-ID` header. Quote it when reporting a problem.
- `session_id` is sent in the request body, never in a URL, so it does not end up in access logs.
- Authentication uses an `HttpOnly` cookie named `__Host-sid`. The browser is the supported client. For testing with curl, keep a cookie jar (`-c` and `-b`). Every non-GET request must carry an `Origin` header matching the site, otherwise it gets `403 bad_origin`.

### 1.2 Error envelope

Errors from endpoints other than `/query` use this shape:

```json
{
  "error": {
    "type": "session_not_found",
    "message": "Session does not exist or has expired."
  }
}
```

`/query` uses its own response shape (Section 3.3), where `error` also carries a `stage`.

### 1.3 HTTP status codes

| Code | Meaning |
|---|---|
| 200 | Request handled. For `/query`, read the `status` field: a blocked or invalid query is still a well-formed response. |
| 400 | Malformed request, failed validation, or an unparseable upload. |
| 401 | Not signed in, or the auth session has expired. |
| 403 | Signed in or attempting to, but not allowed: email not verified, or a bad `Origin`. |
| 404 | Unknown, expired or not-owned `session_id`. The same code is used for all three so a caller cannot probe which sessions exist. |
| 409 | The session is in the wrong state for this call: `wrong_session_mode`, `schema_required`, `dialect_locked` or `query_in_progress` (see each endpoint). |
| 413 | Upload or question exceeds the size cap. |
| 429 | Rate limit hit, or the daily LLM quota is exhausted. |
| 502 | The LLM provider failed after handling. |
| 503 | The service is up but a dependency (database) is unreachable. |

### 1.4 Rate limits

Limits apply per IP at the proxy and per user (or per account, for sign-in) in the app.

| Scope | Default |
|---|---|
| `POST /auth/signin` | 10 per 10 minutes per IP and 5 per 10 minutes per account, with backoff |
| `POST /auth/signup` | 5 per hour per IP |
| Emails sent (verification, reset) | 3 per hour per address and 10 per hour per IP |
| `POST /session` | 10 per minute per user |
| `GET /session` | 30 per minute per user |
| `POST /schema/upload` | 5 per hour per user |
| `POST /query` | 10 per minute per user, 30 per minute per IP |
| Concurrent queries | One in flight per session. A second call gets `409 query_in_progress`. |
| Daily LLM budget | Global. When it is spent, `/query` returns 429 with `status: "quota_exceeded"`. |

A 429 response includes a `Retry-After` header in seconds.

### 1.5 Daily usage limits

Each account has a daily allowance that resets at 00:00 UTC. Defaults:

| Allowance | Default |
|---|---|
| Queries | 20 per day |
| Schema uploads | 3 per day |

- A query uses one unit on its first live LLM call, however many retry attempts follow. A query served entirely from the response cache uses none, and neither does one that fails with `llm_error`. A cache hit still costs no allowance even when it drives live execution in demo mode — see `architecture.md`, Section 6.6.
- When the allowance is used up, `/query` returns `429` with `status: "user_limit_reached"` and `/schema/upload` returns `429 upload_limit_reached`. Both include `Retry-After` (seconds until the reset).
- Only a successful upload uses an upload unit. Failed uploads (`400`, `409`, `413`) do not, though they still count toward the hourly upload rate limit.
- The global LLM budget counts every live LLM call, retries included, while the personal allowance counts queries. If the global budget runs out during a retry, the response is the last attempt's outcome with a `warnings` entry, and the query's unit stays spent because a live call was made.
- Every `/query` response and `GET /me` include a `usage` object (Section 3.3) so the client can show what is left.
- This is separate from the global daily LLM budget, which returns `quota_exceeded` when it runs out.

---

## 2. Authentication and sessions

Two different things are called "session" here, so the terms are fixed:

- An **auth session** is the login. It lives in a cookie and identifies the user.
- A **query session** (`session_id`) is a workspace: a mode, a dialect, an optional uploaded schema and the query log. It belongs to one user.

### 2.1 Authentication

- Users sign in with Google or with email and password (Section 3.5). Both end with an auth cookie, `__Host-sid`, which is `HttpOnly`, `Secure` and `SameSite=Lax`. Page scripts cannot read it.
- Every endpoint except `/health` and every `/auth/*` endpoint requires a signed-in user. Otherwise the API returns `401 not_authenticated`.
- Accounts must have a verified email. An unverified account cannot sign in.
- Auth sessions expire after 7 days of inactivity or 30 days in total. Signing out, resetting the password and deleting the account end them immediately.
- Passwords are 10 to 128 characters.
- There is no anonymous access. "Try for free" on the landing page leads to sign-in, not to a session — see the entry flow in `architecture.md`, Section 1.1.

### 2.2 Sessions

A query session ties together a mode, a dialect, an optional uploaded schema and the query log. Each one belongs to exactly one user.

- Created by `POST /session`. The returned `session_id` is generated with `secrets.token_urlsafe` and is unguessable.
- **Mode fixes the dialect.** A `demo` session is always `postgres`; the dialect is not a request field and is set by the server. A `custom` session has no dialect until a schema is uploaded (Section 3.2); until then it is `null`.
- The `session_id` is an identifier, not a credential. Every call checks that the session belongs to the signed-in user. Someone else's session behaves exactly like a nonexistent one (`404 session_not_found`).
- A session expires after a fixed TTL (default 24 hours). Uploaded catalogs expire with it. After expiry every call returns `404 session_not_found`.
- A session's mode is fixed at creation. To switch modes, or to switch dialect in custom mode, create a new session.
- A custom session's dialect is set by its first successful upload and never changes afterwards (`409 dialect_locked`).
- A user holds at most 5 unexpired sessions. Creating another evicts the oldest, which then behaves like an expired session.
- A client that has lost its `session_id` (a refresh, a new tab) recovers the current one with `GET /session` (Section 3.7) instead of creating a new session.

---

## 3. Endpoints

### 3.1 `POST /session`

Create a session.

**Request**

```json
{ "mode": "demo" }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `mode` | `"demo"` or `"custom"` | yes | `demo` uses the built-in e-commerce database and is always Postgres. `custom` waits for a schema upload, which sets its dialect. |

Do not send `dialect` here. Demo mode has a fixed dialect and custom mode does not have one yet; either case is a `400`.

**Response `200`**

```json
{ "session_id": "k3F9x...redacted", "mode": "demo", "dialect": "postgres", "expires_at": "2026-09-20T10:15:00Z" }
```

A `custom` session returns `"dialect": null` until a schema is uploaded. `expires_at` is fixed at creation (default TTL 24 hours) and is not extended by activity.

**Errors:** `400 invalid_request` (missing or unknown `mode`, or a `dialect` field present), `401 not_authenticated`, `429`.

---

### 3.2 `POST /schema/upload`

Attach a schema to a `custom` session. The DDL is parsed with sqlglot and **never executed**.

**Request:** `multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string | yes | Must belong to a `custom` session. |
| `file` | file (`.sql` or `.txt`) | yes | Default cap 200 KB. |
| `dialect` | string | yes | One of `postgres`, `mysql` in v1. The first successful upload sets the session's dialect, which then drives safety parsing and validation for the rest of the session's life (`architecture.md`, Section 6.1). A later upload on the same session must send the same value, otherwise `409 dialect_locked`. |
| `hints` | JSON string | no | See below. |

**Statements read:** `CREATE TABLE`, `CREATE INDEX`, `ALTER TABLE ... ADD CONSTRAINT` and `CREATE TYPE ... AS ENUM` (its values feed the schema's enums). Other statements common in real dumps (`SET`, `CREATE SEQUENCE`, `COMMENT ON`, ownership and grants) are skipped and listed in `warnings`; nothing in the file is ever executed. The upload is rejected only if no `CREATE TABLE` can be parsed, if it declares tables in a system namespace, or if it exceeds a cap. The schema is capped at about 15 tables.

**Hints format** (all keys optional):

```json
{
  "enums": { "orders.status": ["pending", "shipped", "cancelled"] },
  "metrics": { "revenue": "sum(order_items.quantity * order_items.unit_price)" },
  "notes": "All amounts are in INR."
}
```

Hints are merged into the schema catalog and are shown to the model as user-supplied context. The query pipeline may combine this schema context with retrieved RAG context before generation. The `hints` string is capped at 2 KB, each `enums` key must name a column in the uploaded schema (otherwise `400 invalid_request`), and `metrics` values are passed to the model as plain text and never executed.

**Response `200`**

```json
{
  "schema_id": "sch_8f2c...",
  "dialect": "postgres",
  "tables": [
    { "name": "customers", "column_count": 7 },
    { "name": "orders", "column_count": 9 }
  ],
  "fk_count": 4,
  "warnings": [
    "Table 'audit_log' has no primary key.",
    "Skipped 3 unsupported statements (SET, COMMENT ON)."
  ]
}
```

**Errors**

| Code | `error.type` | When |
|---|---|---|
| 400 | `invalid_request` | Missing field, bad `dialect`, or malformed `hints`. |
| 400 | `ddl_parse_error` | No `CREATE TABLE` statement could be parsed in the chosen dialect. |
| 400 | `reserved_namespace` | The file declares tables in a system namespace (`pg_catalog`, `information_schema`, `mysql`, `performance_schema`, `sys`). |
| 400 | `schema_too_large` | More tables than the cap. |
| 404 | `session_not_found` | Unknown or expired session. |
| 409 | `wrong_session_mode` | The session is `demo`. |
| 409 | `dialect_locked` | The session already has a schema with a different dialect. Create a new session to switch. |
| 413 | `file_too_large` | Above the size cap. |
| 429 | `rate_limited` | Upload rate limit reached. |
| 429 | `upload_limit_reached` | The daily upload allowance is used. See Section 1.5. |

Uploading again on the same session replaces the previous schema and keeps the session's dialect. Sending a different `dialect` is a `409 dialect_locked`; to switch dialect, create a new session.

---

### 3.3 `POST /query`

Ask a question. Runs the full pipeline described in `architecture.md` in the session's dialect. The server may use the internal RAG layer to retrieve relevant curated examples and context from embeddings stored in PostgreSQL with pgvector before the LLM generation step. Retrieval is an internal implementation detail and is not controlled by the client in v1.

**Request**

```json
{
  "session_id": "k3F9x...redacted",
  "question": "Top 5 customers by total spend last month"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string | yes | |
| `question` | string | yes | English or Hinglish. Default cap 500 characters. Leading and trailing whitespace is trimmed. |

**Preconditions:** a `custom` session must have uploaded a schema first, otherwise `409 schema_required`. A session runs one query at a time; while one is in flight, another call on the same session gets `409 query_in_progress`.

**Response `200`** (demo mode, success)

```json
{
  "status": "ok",
  "mode": "demo",
  "dialect": "postgres",
  "question": "Top 5 customers by total spend last month",
  "query_plan": {
    "select": ["customers.name", "sum(orders.total) AS total_spend"],
    "distinct": false,
    "group_by": ["customers.id", "customers.name"],
    "having": null,
    "limit": 5,
    "ctes": [],
    "assumptions": ["'last month' means the previous calendar month."]
  },
  "sql": "SELECT c.name, SUM(o.total) AS total_spend FROM demo.customers c JOIN demo.orders o ON o.customer_id = c.id WHERE ... GROUP BY c.id, c.name ORDER BY total_spend DESC LIMIT 5",
  "assumptions": ["'last month' means the previous calendar month."],
  "explanation": "Sums each customer's order totals for the previous calendar month and returns the five highest.",
  "warnings": [],
  "executed": true,
  "columns": ["name", "total_spend"],
  "rows": [["Asha Verma", 48210.5], ["Rohan Mehta", 45990.0]],
  "row_count": 5,
  "truncated": false,
  "attempts_used": 1,
  "attempt_history": [],
  "error": null,
  "usage": {
    "queries": { "limit": 20, "used": 4, "remaining": 16 },
    "uploads": { "limit": 3, "used": 1, "remaining": 2 },
    "resets_at": "2026-09-20T00:00:00Z"
  }
}
```

**Response `200`** (custom mode, success)

Same shape, with `status: "execution_skipped"`, `executed: false`, `"dialect": "postgres"` or `"mysql"` depending on the upload, and no `columns`, `rows`, `row_count` or `truncated`. The UI shows a "Not executed" banner and a Copy SQL button. The dialect is included so the client can label the copied SQL correctly without keeping its own session state.

#### Response fields

| Field | Type | Notes |
|---|---|---|
| `status` | string | See the table below. |
| `mode` | string | `demo` or `custom`. Echo of the session's mode. |
| `dialect` | string | `postgres` or `mysql`. Echo of the session's dialect. |
| `question` | string | Echo of the trimmed question. |
| `query_plan` | object | The structured plan. Empty object if the plan step is off or generation failed. |
| `sql` | string or null | The final SQL. On a failure this is the last attempt, or null if none was produced. |
| `assumptions` | string[] | Interpretations the model made (for example, what "recent" means). |
| `explanation` | string | Plain-language summary of the query. |
| `warnings` | string[] | Non-fatal notes, for example truncated results, or that retries were cut short by the request deadline or by demo capacity. |
| `executed` | boolean | True only when the query ran against the demo database. Always false for `custom` sessions in either dialect, since custom mode never executes. |
| `columns` | string[] | Ordered column names. Present only when `executed` is true. |
| `rows` | array of arrays | Values in `columns` order. Present only when `executed` is true. |
| `row_count` | integer | Rows returned (after the cap). Present only when `executed` is true. |
| `truncated` | boolean | True if more rows existed than the cap (default 200). Present only when `executed` is true. |
| `attempts_used` | integer | 1 to 3. |
| `attempt_history` | array | One entry per failed attempt (see below). Error text is sanitized. |
| `error` | object or null | Set when `status` is not `ok` or `execution_skipped`. |
| `usage` | object | The caller's daily usage after this request, in the same shape as `GET /me`. Present on every 200 response and on `user_limit_reached`. |

#### `status` values

| `status` | HTTP | `executed` | Meaning |
|---|---|---|---|
| `ok` | 200 | true | Generated, validated and executed (demo). |
| `execution_skipped` | 200 | false | Generated and validated. Not executed by design (custom, either dialect). |
| `invalid_sql` | 200 | false | Validation failed and retries were exhausted. |
| `blocked` | 200 | false | The safety check rejected the SQL. Terminal, no retry. |
| `execution_error` | 200 | false | Execution failed or timed out after retries. `error.type` is `timeout` for a statement timeout. |
| `llm_error` | 502 | false | The LLM provider failed. |
| `user_limit_reached` | 429 | false | The caller's daily allowance is used. Includes `Retry-After` and `usage`. |
| `quota_exceeded` | 429 | false | The daily LLM budget was spent before the first call could be made. Includes `Retry-After`. If it runs out during a retry, the response is instead the last attempt's outcome with a `warnings` entry. |

#### `attempt_history` entry

```json
{
  "attempt_no": 1,
  "sql": "SELECT ...",
  "error_type": "unknown_identifier",
  "error_text": "Unknown column 'customer_name'.",
  "latency_ms": 1840
}
```

`error_text` is composed from an error-class template plus identifiers taken from the model's own SQL. Raw driver or parser messages never appear in it.

#### `error` object

```json
{
  "stage": "safety",
  "type": "disallowed_function",
  "message": "Function 'pg_sleep' is not permitted."
}
```

`stage` is one of `intake`, `generation`, `safety`, `validation`, `execution`.

Error messages returned to the client are written for users. Raw database errors are kept in `query_attempts` on the server and are not passed through unfiltered. This applies to `error.message` and to `attempt_history[].error_text` alike.

**Other errors**

| Code | `error.type` | When |
|---|---|---|
| 400 | `invalid_request` | Missing field or empty question. |
| 404 | `session_not_found` | Unknown or expired session. |
| 409 | `schema_required` | `custom` session with no uploaded schema. |
| 409 | `query_in_progress` | Another `/query` on this session has not finished. Wait for it, or retry after it returns. |
| 413 | `question_too_long` | Above the length cap. |
| 429 | `rate_limited` | Per-user or per-IP limit. |

**Notes**

- Not idempotent: each call is logged, and the same question may return different SQL between calls.
- A response may be served from the LLM response cache. This is transparent to callers, and a fully cached query does not use any of the daily allowance — but in demo mode it can still execute live against the database, since the cache sits in front of generation, not execution. The generation pipeline may also use RAG retrieval backed by PostgreSQL + pgvector before a live LLM call. Neither retrieval nor cache internals are exposed as separate client endpoints in v1.
- Latency is typically a few seconds. Up to three LLM calls plus executions can run in the worst case, but the server enforces a 40-second deadline per request (`architecture.md`, Section 5.1): when it would be crossed, retries stop and the best available result comes back with a `warnings` entry. Clients should show a loading state and use a timeout of at least 45 seconds.
- The "try these examples" set in the UI is static frontend data sent through this same endpoint. There is no separate examples endpoint.

---

### 3.4 `GET /health`

Liveness and dependency check.

**Response `200`**

```json
{ "status": "ok" }
```

**Response `503`** when the database is unreachable:

```json
{ "error": { "type": "dependency_unavailable", "message": "Database is unreachable." } }
```

The response does not reveal the model name, quota state or any configuration.

### 3.5 Authentication endpoints

None of these need a signed-in user. Endpoints that create or change credentials are rate limited (Section 1.4). The server sends the emails; see `architecture.md`, Section 6.5.

**`POST /auth/signup`**

```json
{ "email": "asha@example.com", "password": "correct horse battery" }
```

Response `202`: `{ "status": "verification_sent" }`. The same response is returned whether or not the address is already registered. For an existing address no new account is created, and its owner gets an email instead.

Errors: `400 invalid_request` (malformed email, or a password shorter than 10 or longer than 128 characters), `429 rate_limited`.

**`POST /auth/verify`** with `{ "token": "..." }`

Confirms the email address and signs the user in by setting the auth cookie. Response `200`: `{ "user": { ... } }` (user object below). Errors: `400 invalid_or_expired_token`.

**`POST /auth/resend-verification`** with `{ "email": "..." }`

Response `202`, always. Rate limited per address.

**`POST /auth/signin`** with `{ "email": "...", "password": "..." }`

Response `200`: `{ "user": { ... } }` plus the auth cookie. Errors:

| Code | `error.type` | When |
|---|---|---|
| 401 | `invalid_credentials` | Unknown email, wrong password, or an account with no password. The message is identical in all three cases. |
| 403 | `email_not_verified` | The password was correct but the email is not verified yet. |
| 429 | `rate_limited` | Too many attempts. Includes `Retry-After`. |

**`POST /auth/signout`**

Response `204`. Deletes the server-side session and clears the cookie. Safe to call when already signed out.

**`POST /auth/forgot-password`** with `{ "email": "..." }`

Response `202`, always. If the address belongs to a verified account, a reset link valid for 1 hour is emailed. This also works for a Google-only account and lets its owner add a password.

**`POST /auth/reset-password`** with `{ "token": "...", "new_password": "..." }`

Response `200`: `{ "status": "password_updated" }`. All existing auth sessions for the user are revoked, so the user signs in again. Errors: `400 invalid_or_expired_token`, `400 invalid_request` (password length).

**`GET /auth/google/start?next=/start`**

Redirects (`302`) to Google. `next` must be a relative path on this site, otherwise it is ignored and `/start` is used. `/start` is the two-card mode-choice screen (demo database / use my schema).

**`GET /auth/google/callback?code=...&state=...`**

Handled by the server. On success it sets the auth cookie and redirects (`302`) to the saved `next` path. On any failure it redirects to `/signin?error=google_failed` and puts no details in the URL. Google must report the email as verified.

**User object**

```json
{ "email": "asha@example.com", "has_password": true, "google_linked": false }
```

### 3.6 Account endpoints

Both require a signed-in user.

**`GET /me`**

Response `200`:

```json
{
  "user": { "email": "asha@example.com", "has_password": true, "google_linked": false },
  "usage": {
    "queries": { "limit": 20, "used": 4, "remaining": 16 },
    "uploads": { "limit": 3, "used": 1, "remaining": 2 },
    "resets_at": "2026-09-20T00:00:00Z"
  }
}
```

Errors: `401 not_authenticated`. The front end calls this on load to learn whether the user is signed in.

**`DELETE /me`** with `{ "confirm": true }`

Deletes the account and everything attached to it: auth sessions, query sessions, uploaded schemas and query logs. Requires an auth session younger than 15 minutes; otherwise the call fails with `403 reauth_required` and the client signs the user in again first (password, or the Google flow) and retries. Response `204`, and the cookie is cleared. Errors: `400 invalid_request` (missing `confirm`), `403 reauth_required`.

### 3.7 `GET /session`

Recover the caller's current session after a page refresh, a lost tab or a deep link, so the client does not create a new session (and, in custom mode, re-upload a schema).

**Request:** `GET /session?mode=demo` or `GET /session?mode=custom`. The mode is a query parameter; no session identifier is sent.

**Response `200`**

```json
{
  "session_id": "k3F9x...redacted",
  "mode": "custom",
  "dialect": "mysql",
  "has_schema": true,
  "expires_at": "2026-09-20T10:15:00Z"
}
```

The caller's most recent unexpired session of that mode is returned. For a `demo` session, `dialect` is always `postgres` and `has_schema` is `true` (the schema is built in). For a `custom` session that has not received an upload, `dialect` is `null` and `has_schema` is `false`.

**Errors:** `400 invalid_request` (missing or unknown `mode`), `401 not_authenticated`, `404 session_not_found` (no unexpired session of that mode, so create one with `POST /session`), `429 rate_limited`.

---

## 4. Typical flows

### 4.0 Sign in (all flows)

The browser handles this with the auth cookie. To try the API with curl, keep a cookie jar and send the `Origin` header on non-GET requests:

```bash
curl -s -c cookies.txt -X POST https://www.sqlsense.tech/api/auth/signin \
  -H "Content-Type: application/json" -H "Origin: https://www.sqlsense.tech" \
  -d '{"email":"asha@example.com","password":"..."}'
```

Add `-b cookies.txt -H "Origin: https://www.sqlsense.tech"` to each command in 4.1 and 4.2.

### 4.1 Demo mode

```bash
# 1. Create a session (always Postgres — do not send `dialect`)
curl -s -X POST https://www.sqlsense.tech/api/session \
  -H "Content-Type: application/json" \
  -d '{"mode":"demo"}'
# -> {"session_id":"...","mode":"demo","dialect":"postgres"}

# 2. Ask a question
curl -s -X POST https://www.sqlsense.tech/api/query \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","question":"Kaun se 5 products sabse zyada bike?"}'
```

### 4.2 Custom mode

```bash
# 1. Create a session
curl -s -X POST https://www.sqlsense.tech/api/session \
  -H "Content-Type: application/json" \
  -d '{"mode":"custom"}'
# -> {"session_id":"...","mode":"custom","dialect":null}

# 2. Upload DDL and choose a dialect in the same call
curl -s -X POST https://www.sqlsense.tech/api/schema/upload \
  -F "session_id=<id>" \
  -F "dialect=mysql" \
  -F "file=@schema.sql" \
  -F 'hints={"notes":"Amounts are in INR."}'
# -> {"schema_id":"...","dialect":"mysql", ...}

# 3. Ask a question (SQL is generated in that dialect and validated, never executed)
curl -s -X POST https://www.sqlsense.tech/api/query \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","question":"Monthly revenue for 2025"}'
```

The dialect selector belongs on the same screen as the file picker in the UI: both are
required fields of one upload call, not two steps.

### 4.3 Handling responses in a client

1. Check the HTTP status first: 401 (send the user to sign in), 429 (back off using `Retry-After` for `rate_limited`, or show the limit state for `user_limit_reached` and `quota_exceeded`), 404 (session expired or not yours: call `GET /session`, and create a new one only if that also returns 404), 409 (`query_in_progress`: keep the loading state and do not resubmit; `dialect_locked`: offer a new session), 502/503 (show a retry option). Disable the submit control while a query is in flight.
2. On 200, switch on `status`.
3. Render `rows` only when `executed` is true. Never assume `rows` exists.
4. Use `dialect` to label the SQL panel and the Copy SQL button, rather than tracking the upload choice separately in client state.
5. Always show `assumptions`. They explain results the user might not expect.

### 4.4 Recovering after a refresh

```bash
# Ask for the current session of a mode instead of creating a new one
curl -s -b cookies.txt "https://www.sqlsense.tech/api/session?mode=custom"
# -> {"session_id":"...","mode":"custom","dialect":"mysql","has_schema":true,"expires_at":"..."}
# 404 session_not_found -> create one with POST /session
```

---

## 5. Security notes for API consumers

- **Model output is untrusted.** Retrieved RAG context and model output are treated as untrusted input. Every generated query passes an AST allowlist, parameterized by the session's dialect, and then runs under a read-only database role with a timeout and an application-side watchdog in demo mode. See `architecture.md`.
- **Uploads are parsed, not executed, in either dialect.** A malicious DDL file cannot affect any database.
- **Same-origin in production.** The API is served from the same host as the app. CORS allows only `https://www.sqlsense.tech`, plus `http://localhost:5173` in development.
- **Privacy.** Questions are stored in the query log, and account emails are stored until the account is deleted. Questions, uploaded schemas and hints are sent to a third-party LLM provider. A cached response can be shared across users who send an identical prompt; what is shared is generated SQL text, never row data. The Studio shows a privacy notice stating this.
- **Cookies, not tokens in scripts.** The auth cookie is `HttpOnly`, `Secure` and `SameSite=Lax`, and non-GET requests must carry a matching `Origin` header.
- **No account enumeration.** Sign-up, resend and forgot-password always answer the same way, and failed sign-ins use one message.
- **Single-use, expiring tokens.** Verification and reset tokens are stored hashed, used once, and expire.
- **No open redirects.** The `next` parameter accepts only relative paths on this site.
- **No secrets in responses.** Provider keys, model names and quota state are never returned.
- **Sanitized errors.** Raw database and parser messages stay on the server. Error text returned to clients, including `attempt_history`, is composed from templates.
- **Untrusted text in, plain text out.** Questions, DDL comments and hints are treated as untrusted input. `assumptions` and `explanation` are model-written text and should be rendered as plain text, never as HTML or Markdown.

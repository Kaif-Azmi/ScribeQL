# ScribeQL: UI

Screen-by-screen spec for the React + Vite SPA. Companion to [`architecture.md`](architecture.md)
(entry flow, Section 1.1) and [`api.md`](api.md) (every state below names the endpoint
and `status` value that drives it). This document describes screens and states, not
visual design.

**Architecture note:** RAG is an internal part of the `/query` pipeline. The UI does not expose embedding, vector-search, or retrieval controls in v1. Retrieval may use embeddings stored in PostgreSQL via pgvector, but the user-facing flow remains the same.

---

## 1. Screen map

```
/                    Landing            "Try for free" → /signin
/signin              Sign in            Google | email+password → /start
/signup              Sign up            email+password → check-email notice
/verify?token=       Verification       consumes token → signs in → /start
/reset-password?token=   Password reset → /signin
/start               Mode choice        two cards → /studio/demo or /studio/custom
/studio/demo         Studio (demo)      ask → results table
/studio/custom       Studio (custom)    upload+dialect → ask → SQL, not executed
/account             Account            usage, sign-out, delete
/privacy             Privacy notice     public, linked from every footer
```

Only `/`, `/signin`, `/signup`, `/verify`, `/reset-password` and `/privacy` are public.
Everything else requires a signed-in, verified session (`GET /me` on load; a `401` sends
the user to `/signin` with the current path as `next`).

## 2. Landing (`/`)

One "Try for free" call to action. It is a label, not an access tier — there is no
anonymous mode (`architecture.md` §1.1, §6.6). It leads to `/signin`, never directly to
`/start`. Every page footer links to the privacy notice (Section 11).

## 3. Sign in / sign up

### 3.1 Sign in (`/signin`)

- Two entry points: a Google button (→ `GET /auth/google/start?next=<current-or-/start>`)
  and an email/password form (→ `POST /auth/signin`).
- Error mapping:
  - `401 invalid_credentials` → one message, "Invalid email or password." Never reveal
    which field was wrong.
  - `403 email_not_verified` → "Check your inbox to verify this account," with a resend
    link (→ `POST /auth/resend-verification`).
  - `429 rate_limited` → disable the form until `Retry-After` elapses; show a countdown,
    not a raw retry-after value.
- On success: `POST /auth/signin` sets the cookie; redirect to `next` or `/start`. The SPA
  validates `next` itself: it must start with a single `/` (reject `//host`, `/\host` and
  anything with a scheme), otherwise use `/start`.
- A static line under the form, shown to everyone: "Signed up with Google? Use the Google
  button." It helps Google-only users without revealing anything about any account.
- Google failure returns to this screen via `?error=google_failed` — show a generic
  "Google sign-in didn't work, try again or use email" banner. Never surface OAuth error
  detail from the query string.

### 3.2 Sign up (`/signup`)

- Email + password form → `POST /auth/signup`.
- Always responds `202 verification_sent` regardless of whether the address is already
  registered (`api.md` §3.5). The UI must show the same "check your email" screen in both
  cases — do not branch on the response to guess account existence.
- Password field: client-side length hint (10–128 chars), no composition rules to
  enforce, since the API has none.
- Under the submit button: "By creating an account you agree to the privacy notice",
  linking to `/privacy` (Section 11).

### 3.3 Verification (`/verify?token=`)

- Fires `POST /auth/verify` on load with the token from the query string, then
  immediately strips the token from the URL (`architecture.md` §6.5) before rendering
  anything else, success or failure. Guard this one-shot call against double invocation
  (for example a development-mode effect that runs twice): the token is single-use, so a
  second call would turn a success into "expired".
- Success signs the user in and redirects to `/start`.
- `400 invalid_or_expired_token` → "This link has expired or was already used," with a
  resend action.

### 3.4 Forgot / reset password

- `/signin` links to a forgot-password form → `POST /auth/forgot-password`, always
  `202`, always the same confirmation copy.
- `/reset-password?token=` → new-password form → `POST /auth/reset-password`. On success,
  say plainly that this signed the user out everywhere else, then send them to `/signin`
  (a reset revokes all auth sessions, so this instance is signed out too).

## 4. Mode choice (`/start`)

Two cards, side by side, entered once per visit to this screen:

```
┌─────────────────────────┐   ┌─────────────────────────┐
│ Demo database            │   │ Use my schema            │
│ Postgres e-commerce      │   │ Upload your own DDL      │
│ data, runs live           │   │ Generates SQL, doesn't   │
│                           │   │ execute it               │
│ [ Try the demo ]          │   │ [ Upload a schema ]      │
└─────────────────────────┘   └─────────────────────────┘
```

- "Demo database" → `/studio/demo`, where the session bootstrap (Section 10) resumes the
  user's live demo session or creates one. No dialect prompt here: demo is always
  Postgres and the card should not imply a choice that doesn't exist.
- "Use my schema" → `/studio/custom`. The same bootstrap resumes a live custom session,
  so a user who already uploaded a schema goes straight to the ask step, and a new
  session opens directly into the upload step (Section 5.1).
- A usage summary line reads from `GET /me`'s `usage` object (e.g. "16 of 20 queries left
  today") so limits are visible before the user commits to a mode.

## 5. Studio (custom mode) — `/studio/custom`

### 5.1 Upload step

The screen first runs the session bootstrap (Section 10). The upload step is shown
whenever the session's `dialect` is `null` (`api.md` §2.2).

- One screen, two required fields together: a file picker (`.sql`/`.txt`, 200 KB cap)
  and a dialect selector (`Postgres` / `MySQL`, radio or segmented control — exactly the
  two values `POST /schema/upload` accepts). They submit in one request; there is no
  intermediate "file chosen, dialect pending" state to design for
  (`architecture.md` §7).
- Optional hints field: free-text JSON with a collapsed "advanced" disclosure, plus one
  example (`enums`, `metrics`, `notes`) so users don't need the API doc to use it. It
  shows the 2 KB cap and says that `enums` keys must name columns in the uploaded schema.
- On submit, show upload progress, then switch on the response:
  - `200` → move to the ask step (5.2), with a summary strip: table count, FK count, and
    any `warnings` (e.g. "Table 'audit_log' has no primary key", or "Skipped 3
    unsupported statements") shown as non-blocking notices, collapsed behind a count
    when there are several. Then refresh the usage meter with `GET /me`, because the
    upload response carries no `usage`.
  - `400 ddl_parse_error` → "Couldn't find any CREATE TABLE statements that parse as
    {dialect}." While no upload has succeeded, offer to re-pick the dialect without
    re-uploading the file if the client still holds it in memory; otherwise ask for both
    again.
  - `400 reserved_namespace` → "This file declares tables in a system schema (for
    example `sys` or `mysql`). Rename or remove them and upload again."
  - `400 invalid_request` → if hints were sent, "Check your hints: enum keys must match
    columns in your schema, and the JSON must be under 2 KB."
  - `400 schema_too_large` → "Schemas are capped at about 15 tables."
  - `413 file_too_large` → show the cap.
  - `429 upload_limit_reached` → show remaining allowance as zero and the reset time.
  - `409 wrong_session_mode` should not be reachable from this screen; if seen, it's a
    client bug — log it, don't show API text to the user.
  - `409 dialect_locked` should not be reachable either, because the selector is
    read-only after the first upload (below); if seen, show the "start a new session"
    action instead of the API text.
  - `404 session_not_found` → the session expired; see "Session expiry" in Section 10.
- Re-uploading (a "Replace schema" action, always visible once a schema exists) replaces
  the catalog and keeps the session's dialect. The dialect selector is shown read-only,
  labelled with the current dialect, next to a "Need a different dialect? Start a new
  schema" action that creates a new session (`POST /session {mode: "custom"}`) and opens
  a fresh upload step. The dialect never changes inside a session, so the dialect label
  on the ask step cannot change under the user.

### 5.2 Ask step

Once `dialect` is non-null:

- A persistent banner: "Not executed — SQL only," with the current dialect
  (`Postgres` / `MySQL`) always visible next to it. This is the one fact in custom mode
  that must never be ambiguous, since it's what distinguishes this screen from demo mode.
- Question input, capped at 500 characters client-side ahead of the server's `413`.
- A one-line reminder near the input: "Questions and schemas are sent to a third-party AI
  provider," linking to `/privacy`.
- After a refresh the client only knows the session's dialect, not the table counts (the
  recovery call does not return them), so the summary strip shows "Schema loaded" with
  the dialect and no counts.
- On submit → `POST /query`. Response handling shared with demo mode; see Section 6.

## 6. Studio (demo mode) — `/studio/demo`

- No upload step. The session is resumed or created by the bootstrap (Section 10) and
  the ask step is immediate.
- Question input, same 500-character cap, with the static "try these examples" chips
  (frontend data, sent through the same `POST /query` call — `api.md` §3.3, §4.1). Any
  RAG retrieval and pgvector search are server-side and are not separately exposed in the UI.
- Loading state: a client timeout of at least 45s (the server stops at 40s, `api.md`
  §3.3) with a message that reflects the actual worst case — "Generating and checking
  your query, this can take up to 40 seconds" — not a generic spinner that looks stuck
  past 3 seconds.
- While a query is in flight the submit control and the example chips are disabled. A
  `409 query_in_progress` (for instance from a second tab) keeps the loading state and
  never triggers a resubmit.

## 7. Query response rendering (shared, both modes)

Switch on `status`:

| `status` | UI |
|---|---|
| `ok` | Results table from `columns`/`rows`. `truncated: true` → footer note "showing the first {row_count} rows." `row_count === 0` → an explicit empty state, "The query ran and returned no rows," rather than a blank table. Show `assumptions` above the table, always, even if empty-list (render nothing, don't hide the slot — keeps layout stable across responses). Show `explanation` as a one-line caption. Show the generated `sql` in a collapsed "Show SQL" disclosure with a Copy SQL button labelled with the response's `dialect`, since the checked SQL is the product's main claim. |
| `execution_skipped` | No table. Show `sql` in a code block with a Copy SQL button, `assumptions`, `explanation`, and any `warnings`. This is the expected custom-mode outcome, not an error — no error styling. |
| `invalid_sql` | "Couldn't produce a valid query after a few tries." Optionally expose `attempt_history` behind a "show attempts" disclosure for the curious, not by default. |
| `blocked` | "This request was rejected by the safety check." The server sanitizes `error.message`, but still prefer the generic phrasing, since a message that names an internal function or table tells the user more about engine internals than they need. |
| `execution_error` | If `error.type === "timeout"`, say the query took too long to run rather than "an error occurred." Otherwise a generic execution-failed message. |
| `llm_error` (502) | Retry button. Note this did not use any of the daily allowance. |
| `user_limit_reached` (429) | Replace the ask step with the usage-exhausted state: remaining = 0, countdown to `resets_at` (local time, converted from the UTC value), no input box. |
| `quota_exceeded` (429) | Distinct from the above — this is the shared budget, not personal usage. "ScribeQL has hit its daily demo capacity. Try the example questions" (cache hits still work, §12 of the architecture doc) "or come back after the reset." This status means the very first call could not be made. If capacity runs out during a retry, the response is the last attempt's outcome (for example `invalid_sql`) with a "retries were cut short" entry in `warnings`, rendered as usual. |

Rules that apply across every state:

- Never render `rows` unless `executed === true`, regardless of `status`. Don't infer
  execution from `status === "ok"` alone — check the field.
- `usage` arrives on every `200` and on `user_limit_reached`; update the persistent usage
  indicator (Section 8) from it on every response rather than only fetching it on page
  load.
- `dialect` on the response, not just on session state, is what labels the SQL panel and
  the Copy button — use it even if the client already "knows" the dialect, so a stale
  client can't mislabel a response.
- Render `assumptions`, `explanation`, `warnings` and `attempt_history` text as plain
  text, never as HTML or Markdown: it is model-written or derived from user input.
- Render every `warnings` entry as a non-blocking notice, including "retries were cut
  short" (deadline or demo capacity).

## 8. Usage indicator (persistent, both Studio screens)

A small, always-visible meter — "14 / 20 queries today" — sourced from `usage.queries` on
the last `/query` response or from `GET /me` on load. Uploads remaining shown only on the
custom-mode upload step, since it's irrelevant once a schema exists for the session; it
refreshes from `GET /me` after each successful upload. Failed uploads do not use the
allowance, and the upload step says so.

## 9. Account (`/account`)

- Shows `user.email`, sign-in methods (`has_password`, `google_linked`), and today's
  usage.
- "Add a password" if `google_linked && !has_password` → routes through
  `/reset-password`'s flow via forgot-password, since that's the only path the API
  exposes for a Google-only account to set one (`api.md` §3.5). Say up front that
  finishing the reset signs the user out on every device.
- Sign out → `POST /auth/signout`, then `/`.
- Delete account → confirmation dialog that states plainly what is deleted (sessions,
  uploaded schemas, query logs — `architecture.md` §6.5) before calling
  `DELETE /me {confirm: true}`. Requires explicit confirmation text or a checkbox, not a
  single accidental click, since this is irreversible. If the call returns
  `403 reauth_required` (the sign-in is older than 15 minutes), ask the user to confirm
  their password, or to sign in with Google again, then repeat the deletion; do not
  present it as an error.

## 10. Cross-cutting

- **Credentials and Origin.** Production is same-origin, so the browser sends the
  `__Host-sid` cookie with ordinary same-origin fetches and sets `Origin` itself; the UI
  layer adds neither by hand. A fetch wrapper that omits credentials fails with
  `401 not_authenticated`. Local development is the reverse gap: the SPA on `:5173`
  calling the API on `:8000` is cross-origin, so requests need `credentials: "include"`
  and the API's credentialed CORS setting for `http://localhost:5173`. A
  `403 bad_origin` means the `Origin` header did not match the site (for example a proxy
  that strips it), not that the cookie is missing.
- **`X-Request-ID`.** Surface it in any "report a problem" affordance or error toast's
  detail view, not in the primary message.
- **Session bootstrap (both Studio screens).** On load the client calls
  `GET /session?mode=<mode>`. A `200` resumes that session: for a custom session,
  `has_schema: false` shows the upload step and `true` shows the ask step. A `404` means
  there is no live session, so the client creates one with `POST /session {mode}`. The
  `session_id` is kept in memory only and never put in a URL.
- **Session expiry.** Any `404 session_not_found` during use (the 24-hour TTL, or
  eviction by a newer session) means the session is gone: run the bootstrap again. In
  custom mode say so plainly, "Your session expired. Upload your schema again to
  continue." In demo mode continue with the fresh session and keep the question text in
  the input.
- **No client-side session cache beyond the current session's id.** Mode and dialect are
  always read from the latest server response or from `GET /session`, never assumed from
  a previous screen. A custom session's dialect is fixed once set, but expiry or eviction
  can still replace the session between actions.
- **Empty and loading states get equal design attention to error states.** A blank
  results table before the first question and a "still validating" state at 2–3 seconds
  in are as much a first impression as a `blocked` response.

## 11. Privacy notice (`/privacy`)

A public static page linked from every footer, from the sign-up form and from the
reminder next to the question input and the upload step. In plain language it states:

- Questions, uploaded schemas and hints are sent to a third-party AI provider, which may
  use inputs to improve its products.
- Questions are stored in the query log, and account emails are stored, until the account
  is deleted (Section 9).
- Generated SQL for an identical schema and question may be served to another user from
  a shared cache. What is shared is SQL text, never row data, and cached entries for
  uploaded schemas expire after a few days.
- Uploaded schemas are parsed but never executed.

export const AUTH_COPY = {
  invalid_credentials: "Invalid email or password.",
  email_not_verified: "Check your inbox to verify this account.",
  google_failed: "Google sign-in didn't work, try again or use email.",
  invalid_or_expired_token: "This link has expired or was already used.",
  verification_sent: "Check your email to verify this account.",
  forgot_sent: "If that address has an account, we sent a reset link.",
  signup_privacy: "By creating an account you agree to the privacy notice",
  google_hint: "Signed up with Google? Use the Google button.",
};

export const QUERY_COPY = {
  invalid_sql: "Couldn't produce a valid query after a few tries.",
  blocked: "This request was rejected by the safety check.",
  execution_error: "The query failed while running.",
  execution_timeout: "The query took too long to run.",
  llm_error: "The AI provider failed. This did not use any of today's allowance.",
  quota_exceeded:
    "ScribeQL has hit its daily demo capacity. Try the example questions or come back after the reset.",
  query_in_progress: "A previous query is still running.",
  empty_rows: "The query ran and returned no rows.",
  truncated: (n) => `Showing the first ${n} rows.`,
  loading: "Generating and checking your query, this can take up to 40 seconds",
  custom_banner: "Not executed — SQL only",
  network: "Couldn't reach ScribeQL. Check your connection and try again.",
  timeout: "This request timed out. Try again.",
  server: "ScribeQL is temporarily unavailable. Try again.",
  session_expired_custom: "Your session expired. Upload your schema again to continue.",
};

export const UPLOAD_COPY = {
  ddl_parse_error: (dialect) =>
    `Couldn't find any CREATE TABLE statements that parse as ${dialect}.`,
  reserved_namespace:
    "This file declares tables in a system schema (for example sys or mysql). Rename or remove them and upload again.",
  invalid_request: "Check your file and dialect, then upload again.",
  schema_too_large: "Schemas are capped at about 15 tables.",
  file_too_large: "Files are capped at 200 KB.",
  upload_limit_reached: "You've used today's schema uploads.",
  failed_free: "Failed uploads do not use the daily upload allowance.",
};

export function formatUsageLine(usage) {
  if (!usage?.queries) return null;
  const { remaining, limit } = usage.queries;
  return `${remaining} of ${limit} queries left today`;
}

export function formatUsageMeter(usage) {
  if (!usage?.queries) return "Usage";
  const { used, limit } = usage.queries;
  return `${used} / ${limit} queries today`;
}

export function formatRetryLabel(secondsLeft) {
  const s = Math.max(0, Math.ceil(secondsLeft));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m > 0) {
    return `Try again in ${m}:${String(rem).padStart(2, "0")}`;
  }
  return `Try again in ${s}s`;
}

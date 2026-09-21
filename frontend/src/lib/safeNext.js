const DEFAULT_NEXT = "/start";

/**
 * Client-side `next` sanitizer (UX only). The server must re-validate.
 * Accepts a same-origin relative path starting with a single "/".
 */
export function safeNext(value, fallback = DEFAULT_NEXT) {
  if (typeof value !== "string" || value.length === 0) {
    return fallback;
  }
  if (!value.startsWith("/")) {
    return fallback;
  }
  if (value.startsWith("//") || value.startsWith("/\\")) {
    return fallback;
  }
  if (value.includes("\\") || value.includes("://")) {
    return fallback;
  }
  return value;
}

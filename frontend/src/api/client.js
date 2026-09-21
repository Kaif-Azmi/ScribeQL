export class ApiError extends Error {
  constructor({ status, type, message, requestId, retryAfter, data }) {
    super(message || type || "Request failed");
    this.name = "ApiError";
    this.status = status;
    this.type = type;
    this.requestId = requestId;
    this.retryAfter = retryAfter;
    this.data = data;
  }
}

export class NetworkError extends Error {
  constructor(message = "Couldn't reach ScribeQL. Check your connection and try again.") {
    super(message);
    this.name = "NetworkError";
    this.type = "network_error";
  }
}

export class TimeoutError extends Error {
  constructor(message = "This request timed out. Try again.") {
    super(message);
    this.name = "TimeoutError";
    this.type = "timeout";
  }
}

const DEFAULT_TIMEOUT_MS = 20000;
const QUERY_TIMEOUT_MS = 45000;

let onUnauthorized = null;

export function setOnUnauthorized(handler) {
  onUnauthorized = typeof handler === "function" ? handler : null;
}

function parseRetryAfter(header) {
  if (!header) return null;
  const seconds = Number(header);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return seconds;
  }
  return null;
}

async function parseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

function errorFromBody(status, data, requestId, retryAfter) {
  const errObj = data?.error || {};
  return new ApiError({
    status,
    type: errObj.type || data?.status || "http_error",
    message: errObj.message || data?.message || `HTTP ${status}`,
    requestId,
    retryAfter,
    data,
  });
}

/**
 * @param {string} path - API path beginning with /
 * @param {object} options
 * @param {"none"|"optional"|"required"} options.auth
 */
export async function request(path, options = {}) {
  const {
    method = "GET",
    json,
    formData,
    auth = "required",
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal,
  } = options;

  const headers = new Headers(options.headers || {});
  let body;
  if (formData) {
    body = formData;
  } else if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort("timeout"), timeoutMs);
  const onOuterAbort = () => controller.abort(signal?.reason);
  if (signal) {
    if (signal.aborted) {
      controller.abort(signal.reason);
    } else {
      signal.addEventListener("abort", onOuterAbort, { once: true });
    }
  }

  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (signal) signal.removeEventListener("abort", onOuterAbort);
    if (err?.name === "AbortError" && controller.signal.reason !== "timeout") {
      throw err;
    }
    const error =
      controller.signal.aborted && controller.signal.reason === "timeout"
        ? new TimeoutError()
        : err?.name === "AbortError"
          ? new TimeoutError()
          : new NetworkError();
    return { ok: false, status: 0, data: null, requestId: null, retryAfter: null, error };
  }
  clearTimeout(timeoutId);
  if (signal) signal.removeEventListener("abort", onOuterAbort);

  const requestId = response.headers.get("X-Request-ID");
  const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
  const data = await parseBody(response);

  if (response.status === 401 && auth === "required") {
    onUnauthorized?.({
      path,
      requestId,
      next: `${window.location.pathname}${window.location.search}`,
    });
  }

  if (response.status === 204) {
    return { ok: true, status: 204, data: null, requestId, retryAfter };
  }

  const result = {
    ok: response.ok,
    status: response.status,
    data,
    requestId,
    retryAfter,
  };

  if (!response.ok) {
    result.error = errorFromBody(response.status, data, requestId, retryAfter);
  }

  return result;
}

export async function requestJson(path, options = {}) {
  const result = await request(path, options);
  if (!result.ok) {
    throw result.error || new ApiError({ status: result.status, type: "http_error" });
  }
  return result;
}

export const timeouts = { default: DEFAULT_TIMEOUT_MS, query: QUERY_TIMEOUT_MS };

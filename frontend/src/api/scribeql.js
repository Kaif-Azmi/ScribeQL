import { request, requestJson, timeouts } from "./client.js";

export function getMe() {
  return request("/me", { auth: "optional" });
}

export function signIn(email, password) {
  return request("/auth/signin", {
    method: "POST",
    json: { email, password },
    auth: "none",
  });
}

export function signUp(email, password) {
  return request("/auth/signup", {
    method: "POST",
    json: { email, password },
    auth: "none",
  });
}

export function verifyEmail(token) {
  return request("/auth/verify", {
    method: "POST",
    json: { token },
    auth: "none",
  });
}

export function resendVerification(email) {
  return request("/auth/resend-verification", {
    method: "POST",
    json: { email },
    auth: "none",
  });
}

export function signOut() {
  return request("/auth/signout", { method: "POST", auth: "none" });
}

export function forgotPassword(email) {
  return request("/auth/forgot-password", {
    method: "POST",
    json: { email },
    auth: "none",
  });
}

export function resetPassword(token, new_password) {
  return request("/auth/reset-password", {
    method: "POST",
    json: { token, new_password },
    auth: "none",
  });
}

export function deleteMe() {
  return request("/me", {
    method: "DELETE",
    json: { confirm: true },
    auth: "required",
  });
}

export function googleStartUrl(nextPath) {
  const params = new URLSearchParams({ next: nextPath });
  return `/api/auth/google/start?${params.toString()}`;
}

export function getSession(mode) {
  return request(`/session?mode=${encodeURIComponent(mode)}`, { auth: "required" });
}

export function createSession(mode) {
  return request("/session", {
    method: "POST",
    json: { mode },
    auth: "required",
  });
}

export function uploadSchema({ sessionId, dialect, file }) {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("dialect", dialect);
  formData.append("file", file);
  return request("/schema/upload", {
    method: "POST",
    formData,
    auth: "required",
    timeoutMs: 30000,
  });
}

export function runQuery({ sessionId, question, signal }) {
  return request("/query", {
    method: "POST",
    json: { session_id: sessionId, question },
    auth: "required",
    timeoutMs: timeouts.query,
    signal,
  });
}

export { requestJson };

import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { forgotPassword, googleStartUrl, resendVerification, signIn } from "../api/scribeql.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import PublicLayout from "../components/layout/PublicLayout.jsx";
import useCountdown from "../hooks/useCountdown.js";
import { AUTH_COPY, formatRetryLabel, QUERY_COPY } from "../lib/errors.js";
import { safeNext } from "../lib/safeNext.js";
import styles from "./auth.module.css";

export default function SignInPage() {
  const { refreshMe } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const googleFailed = params.get("error") === "google_failed";
  const resetNotice = location.state?.notice;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState(googleFailed ? AUTH_COPY.google_failed : "");
  const [showResend, setShowResend] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lockUntil, setLockUntil] = useState(null);
  const secondsLeft = useCountdown(lockUntil);
  const locked = secondsLeft > 0;

  async function onSubmit(event) {
    event.preventDefault();
    if (locked) return;
    setBusy(true);
    setMessage("");
    setShowResend(false);
    const result = await signIn(email, password);
    setBusy(false);
    if (result.ok) {
      if (result.data?.user) {
        await refreshMe();
      }
      navigate(next, { replace: true });
      return;
    }
    const type = result.error?.type;
    if (type === "invalid_credentials") {
      setMessage(AUTH_COPY.invalid_credentials);
    } else if (type === "email_not_verified") {
      setMessage(AUTH_COPY.email_not_verified);
      setShowResend(true);
    } else if (result.status === 429) {
      const wait = result.retryAfter ?? 30;
      setLockUntil(Date.now() + wait * 1000);
      setMessage("");
    } else if (result.status >= 500) {
      setMessage(QUERY_COPY.server);
    } else if (result.error?.name === "NetworkError" || result.error?.type === "network_error") {
      setMessage(result.error.message);
    } else {
      setMessage(result.error?.message || "Couldn't sign in.");
    }
  }

  async function onResend() {
    await resendVerification(email);
    setMessage(AUTH_COPY.verification_sent);
  }

  async function onForgot(event) {
    event.preventDefault();
    await forgotPassword(email);
    setMessage(AUTH_COPY.forgot_sent);
  }

  return (
    <PublicLayout ctaTo="/signup" ctaLabel="Sign up">
      <div className={styles.card}>
        <p className={styles.badge}>Welcome back</p>
        <h1 className={styles.title}>Sign in</h1>
        <p className={styles.lede}>Google or email and password. There is no anonymous studio.</p>
        {resetNotice ? (
          <div className={styles.notice} role="status">
            {resetNotice}
          </div>
        ) : null}
        {message ? (
          <div className={styles.error} role="alert">
            {message}
          </div>
        ) : null}
        {locked ? (
          <div className={styles.live} aria-live="polite">
            {formatRetryLabel(secondsLeft)}
          </div>
        ) : null}
        <a className={styles.google} href={googleStartUrl(next)}>
          Continue with Google
        </a>
        <div className={styles.divider}>or</div>
        <form onSubmit={onSubmit}>
          <div className={styles.field}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              className={styles.input}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={locked}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className={styles.input}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={locked}
            />
          </div>
          <button className={styles.primary} type="submit" disabled={busy || locked}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        {showResend ? (
          <p className={styles.linkRow}>
            <button type="button" className={styles.secondary} onClick={onResend}>
              Resend verification email
            </button>
          </p>
        ) : null}
        <p className={styles.hint}>{AUTH_COPY.google_hint}</p>
        <p className={styles.linkRow}>
          <button type="button" className={styles.textBtn} onClick={() => setShowForgot(true)}>
            Forgot password?
          </button>
        </p>
        {showForgot ? (
          <form className={styles.forgot} onSubmit={onForgot}>
            <p className={styles.hint}>We&apos;ll send a reset link if the account exists. Uses the email above.</p>
            <button className={styles.secondary} type="submit">
              Send reset link
            </button>
          </form>
        ) : null}
        <p className={styles.linkRow}>
          No account? <Link to="/signup">Sign up</Link>
        </p>
      </div>
    </PublicLayout>
  );
}

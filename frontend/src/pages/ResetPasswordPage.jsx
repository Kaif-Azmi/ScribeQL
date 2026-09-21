import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { resetPassword } from "../api/scribeql.js";
import PublicLayout from "../components/layout/PublicLayout.jsx";
import useNoReferrer from "../hooks/useNoReferrer.js";
import { AUTH_COPY } from "../lib/errors.js";
import styles from "./auth.module.css";

export default function ResetPasswordPage() {
  useNoReferrer();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const result = await resetPassword(token, password);
    setBusy(false);
    if (result.ok) {
      navigate("/signin", {
        replace: true,
        state: { notice: "Your password was updated. This signed you out everywhere else." },
      });
      return;
    }
    if (result.error?.type === "invalid_or_expired_token") {
      setError(AUTH_COPY.invalid_or_expired_token);
    } else {
      setError(result.error?.message || "Couldn't reset the password.");
    }
  }

  return (
    <PublicLayout ctaTo="/signin" ctaLabel="Sign in">
      <div className={styles.card}>
        <p className={styles.badge}>Secure account</p>
        <h1 className={styles.title}>Reset password</h1>
        <p className={styles.lede}>
          Choose a new password (10–128 characters). This signs you out on every device.
        </p>
        {error ? (
          <div className={styles.error} role="alert">
            {error}
          </div>
        ) : null}
        {!token ? (
          <div className={styles.error} role="alert">
            {AUTH_COPY.invalid_or_expired_token}
          </div>
        ) : null}
        <form onSubmit={onSubmit}>
          <div className={styles.field}>
            <label htmlFor="password">New password</label>
            <input
              id="password"
              className={styles.input}
              type="password"
              autoComplete="new-password"
              minLength={10}
              maxLength={128}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={!token}
            />
          </div>
          <button className={styles.primary} disabled={busy || !token} type="submit">
            {busy ? "Updating…" : "Update password"}
          </button>
        </form>
        <p className={styles.linkRow}>
          <Link to="/signin">Back to sign in</Link>
        </p>
      </div>
    </PublicLayout>
  );
}

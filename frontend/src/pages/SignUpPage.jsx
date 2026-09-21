import { useState } from "react";
import { Link } from "react-router-dom";
import { signUp } from "../api/scribeql.js";
import PublicLayout from "../components/layout/PublicLayout.jsx";
import { AUTH_COPY } from "../lib/errors.js";
import styles from "./auth.module.css";

export default function SignUpPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const result = await signUp(email, password);
    setBusy(false);
    if (result.ok || result.status === 202) {
      setDone(true);
      return;
    }
    if (result.status >= 500) {
      setError("ScribeQL is temporarily unavailable. Try again.");
      return;
    }
    setError(result.error?.message || "Couldn't create the account.");
  }

  return (
    <PublicLayout>
      <div className={styles.card}>
        <h1 className={styles.title}>Create an account</h1>
        {done ? (
          <p className={styles.lede}>{AUTH_COPY.verification_sent}</p>
        ) : (
          <>
            <p className={styles.lede}>Email and a password between 10 and 128 characters.</p>
            {error ? (
              <div className={styles.error} role="alert">
                {error}
              </div>
            ) : null}
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
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="password">Password</label>
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
                />
                <span className={styles.hint}>10–128 characters. No other composition rules.</span>
              </div>
              <button className={styles.primary} type="submit" disabled={busy}>
                {busy ? "Creating…" : "Create account"}
              </button>
            </form>
            <p className={styles.hint}>
              By creating an account you agree to the <Link to="/privacy">privacy notice</Link>.
            </p>
          </>
        )}
        <p className={styles.linkRow}>
          Already have an account? <Link to="/signin">Sign in</Link>
        </p>
      </div>
    </PublicLayout>
  );
}

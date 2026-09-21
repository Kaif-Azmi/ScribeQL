import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { resendVerification, verifyEmail } from "../api/scribeql.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import PublicLayout from "../components/layout/PublicLayout.jsx";
import useNoReferrer from "../hooks/useNoReferrer.js";
import { AUTH_COPY } from "../lib/errors.js";
import styles from "./auth.module.css";

export default function VerifyPage() {
  useNoReferrer();
  const { refreshMe } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState("working");
  const [email, setEmail] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    const token = params.get("token") || "";
    if (params.has("token")) {
      const nextParams = new URLSearchParams(params);
      nextParams.delete("token");
      setParams(nextParams, { replace: true });
    }
    if (ran.current) return;
    ran.current = true;
    if (!token) {
      setStatus("failed");
      return;
    }
    (async () => {
      const result = await verifyEmail(token);
      if (result.ok) {
        await refreshMe();
        navigate("/start", { replace: true });
        return;
      }
      setStatus("failed");
    })();
  }, [params, setParams, refreshMe, navigate]);

  async function onResend(event) {
    event.preventDefault();
    await resendVerification(email);
    setStatus("resent");
  }

  return (
    <PublicLayout>
      <div className={styles.card}>
        <h1 className={styles.title}>Verify email</h1>
        {status === "working" ? <p className={styles.lede}>Confirming your email…</p> : null}
        {status === "failed" ? (
          <>
            <p className={styles.lede}>{AUTH_COPY.invalid_or_expired_token}</p>
            <form onSubmit={onResend}>
              <div className={styles.field}>
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  className={styles.input}
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <button className={styles.primary} type="submit">
                Resend verification
              </button>
            </form>
          </>
        ) : null}
        {status === "resent" ? <p className={styles.lede}>{AUTH_COPY.verification_sent}</p> : null}
        <p className={styles.linkRow}>
          <Link to="/signin">Back to sign in</Link>
        </p>
      </div>
    </PublicLayout>
  );
}

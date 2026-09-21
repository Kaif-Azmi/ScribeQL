import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { deleteMe, forgotPassword, googleStartUrl, signIn } from "../api/scribeql.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import { formatUsageLine } from "../lib/errors.js";
import styles from "./auth.module.css";
import studio from "./Studio.module.css";

export default function AccountPage() {
  const { user, usage, signOut, refreshMe, setUser } = useAuth();
  const [params] = useSearchParams();
  const [confirm, setConfirm] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(params.get("reauth") === "1");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState(
    params.get("reauth") === "1" ? "You're signed in again — confirm to delete." : ""
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (params.get("reauth") === "1") {
      setDeleteOpen(true);
    }
  }, [params]);

  async function onDelete(event) {
    event.preventDefault();
    if (!confirm) return;
    setBusy(true);
    const result = await deleteMe();
    setBusy(false);
    if (result.ok) {
      setUser(null);
      window.location.assign("/");
      return;
    }
    if (result.error?.type === "reauth_required") {
      if (user?.has_password) {
        setNotice("Confirm your password, then delete again. This is not an error.");
      } else {
        setNotice("Sign in with Google again, then confirm delete.");
      }
      return;
    }
    setNotice(result.error?.message || "Couldn't delete the account.");
  }

  async function onReauthPassword(event) {
    event.preventDefault();
    const result = await signIn(user.email, password);
    if (result.ok) {
      await refreshMe();
      setNotice("You're signed in again — confirm to delete.");
      setDeleteOpen(true);
    } else {
      setNotice("Couldn't confirm the password.");
    }
  }

  async function onAddPassword() {
    await forgotPassword(user.email);
    setNotice(
      "We sent a reset link. Finishing it sets a password and signs you out on every device."
    );
  }

  return (
    <>
      <h1>Account</h1>
      <p>{user?.email}</p>
      <p className={styles.hint}>
        Password: {user?.has_password ? "yes" : "no"} · Google: {user?.google_linked ? "linked" : "not linked"}
      </p>
      <p>{formatUsageLine(usage)}</p>
      {user?.google_linked && !user?.has_password ? (
        <p>
          <button type="button" className={studio.secondary} onClick={onAddPassword}>
            Add a password
          </button>
        </p>
      ) : null}
      {notice ? <p className={studio.notice}>{notice}</p> : null}
      <div className={studio.actions}>
        <button type="button" className={studio.secondary} onClick={signOut}>
          Sign out
        </button>
        <button type="button" className={studio.secondary} onClick={() => setDeleteOpen(true)}>
          Delete account
        </button>
      </div>
      {deleteOpen ? (
        <form className={styles.card} onSubmit={onDelete} style={{ marginTop: "1rem" }}>
          <h2>Delete this account?</h2>
          <p className={styles.lede}>
            This permanently deletes sessions, uploaded schemas, and query logs. It cannot be undone.
          </p>
          {notice?.includes("password") && user?.has_password ? (
            <div className={styles.field}>
              <label htmlFor="reauth-password">Password</label>
              <input
                id="reauth-password"
                className={styles.input}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button type="button" className={styles.primary} onClick={onReauthPassword}>
                Confirm password
              </button>
            </div>
          ) : null}
          {user?.google_linked && !user?.has_password ? (
            <p>
              <a className={styles.google} href={googleStartUrl("/account?reauth=1")}>
                Sign in with Google again
              </a>
            </p>
          ) : null}
          <label>
            <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} /> I
            understand this cannot be undone
          </label>
          <button className={styles.primary} type="submit" disabled={!confirm || busy}>
            {busy ? "Deleting…" : "Delete account"}
          </button>
        </form>
      ) : null}
      <p className={styles.linkRow}>
        <Link to="/start">Back to start</Link>
      </p>
    </>
  );
}

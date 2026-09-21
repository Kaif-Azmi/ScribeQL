import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { runQuery } from "../api/scribeql.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import QueryResult from "../components/QueryResult.jsx";
import { DEMO_EXAMPLES } from "../data/demoExamples.js";
import useCountdown from "../hooks/useCountdown.js";
import { formatRetryLabel, QUERY_COPY } from "../lib/errors.js";
import styles from "./Studio.module.css";

const QUERY_IN_PROGRESS_DEFAULT = 8;

function dialectLabel(dialect) {
  if (dialect === "mysql") return "MySQL";
  if (dialect === "postgres") return "Postgres";
  return dialect;
}

function formatLocalReset(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export default function StudioAsk({
  session,
  onSessionMissing,
  custom = false,
  schemaSummary,
}) {
  const { setUsage, usage } = useAuth();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [lockMsg, setLockMsg] = useState("");
  const [lockUntil, setLockUntil] = useState(null);
  const [clientError, setClientError] = useState(null);
  const abortRef = useRef(null);
  const secondsLeft = useCountdown(lockUntil);
  const locked = secondsLeft > 0;

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const remaining = usage?.queries?.remaining;
  const exhausted = remaining === 0 && result?.status === "user_limit_reached";

  async function submit(text) {
    const q = (text ?? question).trim();
    if (!q || busy || locked || !session?.session_id) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setLockMsg("");
    setClientError(null);
    setResult(null);
    let response;
    try {
      response = await runQuery({
        sessionId: session.session_id,
        question: q,
        signal: controller.signal,
      });
    } catch (err) {
      setBusy(false);
      if (err?.name === "AbortError") return;
      setClientError({ kind: "network" });
      return;
    }
    setBusy(false);
    if (response.error?.name === "AbortError") return;

    if (response.status === 404) {
      onSessionMissing?.(q);
      return;
    }
    if (response.status === 409 && response.error?.type === "query_in_progress") {
      const wait = response.retryAfter ?? QUERY_IN_PROGRESS_DEFAULT;
      setLockUntil(Date.now() + wait * 1000);
      setLockMsg(QUERY_COPY.query_in_progress);
      return;
    }
    if (!response.ok && response.error?.type === "network_error") {
      setClientError({ kind: "network", requestId: response.requestId });
      return;
    }
    if (!response.ok && response.error?.type === "timeout") {
      setClientError({ kind: "timeout", requestId: response.requestId });
      return;
    }
    if (response.status >= 500 && !response.data?.status) {
      setClientError({ kind: "server", requestId: response.requestId });
      return;
    }

    const payload = response.data || {};
    if (payload.usage) setUsage(payload.usage);
    setResult({ ...payload, requestId: response.requestId });
  }

  if (exhausted) {
    return (
      <div className={styles.exhausted}>
        <p>0 queries remaining today.</p>
        <p>Resets at {formatLocalReset(usage?.resets_at)} (your local time).</p>
      </div>
    );
  }

  if (result?.status === "quota_exceeded" || result?.status === "user_limit_reached") {
    if (result.status === "user_limit_reached") {
      return (
        <div className={styles.exhausted}>
          <p>0 queries remaining today.</p>
          <p>Resets at {formatLocalReset(result.usage?.resets_at || usage?.resets_at)} (your local time).</p>
        </div>
      );
    }
  }

  return (
    <div>
      {custom ? (
        <div className={styles.banner}>
          {QUERY_COPY.custom_banner}
          {session?.dialect ? ` · ${dialectLabel(session.dialect)}` : ""}
        </div>
      ) : null}
      {schemaSummary}
      <p className={styles.privacy}>
        Questions and schemas are sent to a third-party AI provider.{" "}
        <Link to="/privacy">Privacy notice</Link>
      </p>
      <form
        className={styles.composer}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label className="sr-only" htmlFor="question">
          Question
        </label>
        <textarea
          id="question"
          className={styles.input}
          maxLength={500}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask in English or Hinglish"
          disabled={busy}
        />
        <div className={styles.row}>
          <span className={styles.count}>{question.length} / 500</span>
          <button className={styles.submit} type="submit" disabled={busy || locked || !question.trim()}>
            {busy ? "Working…" : "Ask"}
          </button>
        </div>
      </form>
      {!custom ? (
        <div className={styles.chips}>
          {DEMO_EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className={styles.chip}
              disabled={busy || locked}
              onClick={() => {
                setQuestion(example);
                submit(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>
      ) : null}
      {busy ? (
        <p className={styles.loading} aria-live="polite">
          {QUERY_COPY.loading}
        </p>
      ) : null}
      {lockMsg ? (
        <div className={styles.lock} aria-live="polite">
          <p>
            {lockMsg} Retry in {secondsLeft}s. The earlier result is not available in this tab.
          </p>
          <button
            className={styles.submit}
            type="button"
            disabled={locked}
            onClick={() => {
              setLockMsg("");
              submit();
            }}
          >
            {locked ? formatRetryLabel(secondsLeft) : "Retry"}
          </button>
        </div>
      ) : null}
      {clientError ? (
        <div className={styles.lock}>
          <p>
            {clientError.kind === "timeout"
              ? QUERY_COPY.timeout
              : clientError.kind === "server"
                ? QUERY_COPY.server
                : QUERY_COPY.network}
          </p>
          {clientError.requestId ? <p>Request ID: {clientError.requestId}</p> : null}
          <button className={styles.submit} type="button" onClick={() => submit()}>
            Retry
          </button>
        </div>
      ) : null}
      {result?.status === "quota_exceeded" ? <QueryResult result={result} /> : null}
      {result && result.status !== "quota_exceeded" && result.status !== "user_limit_reached" ? (
        <QueryResult result={result} onRetry={() => submit()} />
      ) : null}
    </div>
  );
}

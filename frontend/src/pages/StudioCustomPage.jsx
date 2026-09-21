import { useState } from "react";
import { Link } from "react-router-dom";
import { uploadSchema } from "../api/scribeql.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import useStudioSession from "../hooks/useStudioSession.js";
import { QUERY_COPY, UPLOAD_COPY } from "../lib/errors.js";
import StudioAsk from "./StudioAsk.jsx";
import styles from "./Studio.module.css";
import StudioWorkspace from "../components/layout/StudioWorkspace.jsx";

function dialectLabel(dialect) {
  if (dialect === "mysql") return "MySQL";
  if (dialect === "postgres") return "Postgres";
  return dialect || "";
}

export default function StudioCustomPage() {
  const { refreshMe, usage } = useAuth();
  const { session, setSession, loading, error, refresh, replaceSession } = useStudioSession("custom");
  const [file, setFile] = useState(null);
  const [dialect, setDialect] = useState("postgres");
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [expired, setExpired] = useState(false);

  const needsUpload = session && (session.dialect == null || session.has_schema === false);
  const dialectLocked = Boolean(session?.dialect);

  async function onUpload(event) {
    event.preventDefault();
    if (!file || !session?.session_id) return;
    setUploading(true);
    setUploadError("");
    const result = await uploadSchema({
      sessionId: session.session_id,
      dialect: dialectLocked ? session.dialect : dialect,
      file,
    });
    setUploading(false);
    if (result.status === 404) {
      setExpired(true);
      await refresh();
      setSummary(null);
      return;
    }
    if (!result.ok) {
      const type = result.error?.type;
      if (type === "ddl_parse_error") {
        setUploadError(UPLOAD_COPY.ddl_parse_error(dialectLocked ? session.dialect : dialect));
      } else if (type === "reserved_namespace") {
        setUploadError(UPLOAD_COPY.reserved_namespace);
      } else if (type === "invalid_request") {
        setUploadError(UPLOAD_COPY.invalid_request);
      } else if (type === "schema_too_large") {
        setUploadError(UPLOAD_COPY.schema_too_large);
      } else if (type === "file_too_large") {
        setUploadError(UPLOAD_COPY.file_too_large);
      } else if (type === "upload_limit_reached") {
        setUploadError(UPLOAD_COPY.upload_limit_reached);
      } else if (type === "dialect_locked") {
        setUploadError("Need a different dialect? Start a new schema.");
      } else {
        setUploadError(result.error?.message || "Upload failed.");
      }
      return;
    }
    setSummary(result.data);
    setSession({
      ...session,
      dialect: result.data.dialect,
      has_schema: true,
    });
    await refreshMe();
  }

  async function startNewSchema() {
    const next = await replaceSession();
    setSummary(null);
    setFile(null);
    setExpired(false);
    setSession(next);
  }

  if (loading) return <div className={styles.workspaceLoading}>Starting custom workspace…</div>;
  if (error) {
    return (
      <StudioWorkspace mode="DDL">
        <p>{QUERY_COPY.network}</p>
        <button type="button" className={styles.submit} onClick={() => refresh()}>
          Retry
        </button>
      </StudioWorkspace>
    );
  }

  return (
    <StudioWorkspace mode="DDL">
    <section className={styles.studioCanvas}>
      <p className={styles.workspaceEyebrow}>YOUR SCHEMA · SQL GENERATION</p>
      <h1>Build SQL for your schema</h1>
      {expired ? <p className={styles.notice}>{QUERY_COPY.session_expired_custom}</p> : null}
      {needsUpload ? (
        <form className={styles.customCanvas} onSubmit={onUpload}>
          <p className={styles.schema}>
            Upload remaining today: {usage?.uploads?.remaining ?? "—"} / {usage?.uploads?.limit ?? "—"}
          </p>
          <p className={styles.privacy}>{UPLOAD_COPY.failed_free}</p>
          <p className={styles.privacy}>
            Questions and schemas are sent to a third-party AI provider.{" "}
            <Link to="/privacy">Privacy notice</Link>
          </p>
          {uploadError ? <p className={styles.notice}>{uploadError}</p> : null}
          <label htmlFor="schema-file">Schema file (.sql or .txt, 200 KB)</label>
          <input
            id="schema-file"
            className={styles.file}
            type="file"
            accept=".sql,.txt,text/plain"
            required
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <fieldset className={styles.segmented}>
            <legend className="sr-only">Dialect</legend>
            {dialectLocked ? (
              <p>Dialect: {dialectLabel(session.dialect)} (locked for this session)</p>
            ) : (
              <>
                <label>
                  <input
                    type="radio"
                    name="dialect"
                    value="postgres"
                    checked={dialect === "postgres"}
                    onChange={() => setDialect("postgres")}
                  />{" "}
                  Postgres
                </label>
                <label>
                  <input
                    type="radio"
                    name="dialect"
                    value="mysql"
                    checked={dialect === "mysql"}
                    onChange={() => setDialect("mysql")}
                  />{" "}
                  MySQL
                </label>
              </>
            )}
          </fieldset>
          <div className={styles.actions}>
            <button className={styles.submit} type="submit" disabled={uploading || !file}>
              {uploading ? "Uploading…" : "Upload schema"}
            </button>
          </div>
        </form>
      ) : (
        <div className={styles.customCanvas}>
          <div className={styles.actions}>
            <span className={styles.schema}>
              {summary
                ? `${summary.tables?.length || 0} tables · ${summary.fk_count ?? 0} foreign keys`
                : `Schema loaded · ${dialectLabel(session.dialect)}`}
            </span>
            <button
              className={styles.secondary}
              type="button"
              onClick={() => {
                document.getElementById("replace-file")?.focus();
              }}
            >
              Replace schema
            </button>
            <button className={styles.secondary} type="button" onClick={startNewSchema}>
              Need a different dialect? Start a new schema
            </button>
          </div>
          {summary?.warnings?.length ? (
            <details className={styles.warnings}>
              <summary>{summary.warnings.length} notice{summary.warnings.length === 1 ? "" : "s"}</summary>
              <ul>
                {summary.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </details>
          ) : null}
          <form id="replace" onSubmit={onUpload} className={styles.actions} style={{ flexDirection: "column", alignItems: "flex-start" }}>
            <label htmlFor="replace-file">Replace schema (keeps {dialectLabel(session.dialect)})</label>
            <input
              id="replace-file"
              className={styles.file}
              type="file"
              accept=".sql,.txt,text/plain"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <button className={styles.secondary} type="submit" disabled={!file || uploading}>
              Replace schema
            </button>
          </form>
          <StudioAsk
            session={session}
            custom
            schemaSummary={null}
            onSessionMissing={async () => {
              setExpired(true);
              setSummary(null);
              await refresh();
            }}
          />
        </div>
      )}
    </section>
    </StudioWorkspace>
  );
}

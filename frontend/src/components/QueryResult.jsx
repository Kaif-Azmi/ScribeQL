import SqlDisclosure from "./SqlDisclosure.jsx";
import Warnings from "./Warnings.jsx";
import { QUERY_COPY } from "../lib/errors.js";
import styles from "./QueryResult.module.css";

function cellValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Assumptions({ items }) {
  return (
    <div className={styles.slot} data-slot="assumptions">
      {items?.length
        ? items.map((text, i) => (
            <p key={i} className={styles.assumption}>
              {text}
            </p>
          ))
        : null}
    </div>
  );
}

function AttemptHistory({ history }) {
  if (!history?.length) return null;
  return (
    <details>
      <summary>Show attempts</summary>
      <ol className={styles.history}>
        {history.map((entry, i) => (
          <li key={i}>
            Attempt {entry.attempt_no}: {entry.error_type}
            {entry.error_text ? ` — ${entry.error_text}` : ""}
            {entry.sql ? (
              <pre>
                <code>{entry.sql}</code>
              </pre>
            ) : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

export default function QueryResult({ result, onRetry }) {
  if (!result) return null;

  const executed = result.executed === true;
  const dialect = result.dialect;
  const warnings = result.warnings || [];
  const status = result.status;

  if (status === "ok" && executed) {
    const rows = result.rows || [];
    const columns = result.columns || [];
    return (
      <div className={styles.wrap}>
        <Assumptions items={result.assumptions} />
        {result.explanation ? <p className={styles.caption}>{result.explanation}</p> : null}
        <Warnings items={warnings} />
        <div className={styles.tableWrap}>
          {result.row_count === 0 ? (
            <p className={styles.empty}>{QUERY_COPY.empty_rows}</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, ri) => (
                  <tr key={ri}>
                    {columns.map((col, ci) => (
                      <td key={col}>{cellValue(Array.isArray(row) ? row[ci] : row[col])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {result.truncated ? (
          <p className={styles.foot}>{QUERY_COPY.truncated(result.row_count)}</p>
        ) : null}
        <SqlDisclosure sql={result.sql} dialect={dialect} />
      </div>
    );
  }

  if (status === "execution_skipped") {
    return (
      <div className={styles.wrap}>
        <Assumptions items={result.assumptions} />
        {result.explanation ? <p className={styles.caption}>{result.explanation}</p> : null}
        <Warnings items={warnings} />
        <SqlDisclosure sql={result.sql} dialect={dialect} open />
      </div>
    );
  }

  if (status === "invalid_sql") {
    return (
      <div className={styles.wrap}>
        <div className={`${styles.message} ${styles.error}`}>{QUERY_COPY.invalid_sql}</div>
        <Warnings items={warnings} />
        <AttemptHistory history={result.attempt_history} />
      </div>
    );
  }

  if (status === "blocked") {
    return (
      <div className={styles.wrap}>
        <div className={`${styles.message} ${styles.error}`}>{QUERY_COPY.blocked}</div>
        <Warnings items={warnings} />
      </div>
    );
  }

  if (status === "execution_error") {
    const timeout = result.error?.type === "timeout";
    return (
      <div className={styles.wrap}>
        <div className={`${styles.message} ${styles.error}`}>
          {timeout ? QUERY_COPY.execution_timeout : QUERY_COPY.execution_error}
        </div>
        <Warnings items={warnings} />
      </div>
    );
  }

  if (status === "llm_error") {
    return (
      <div className={styles.wrap}>
        <div className={`${styles.message} ${styles.error}`}>{QUERY_COPY.llm_error}</div>
        {onRetry ? (
          <button type="button" className={styles.retry} onClick={onRetry}>
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  if (status === "quota_exceeded") {
    return (
      <div className={styles.wrap}>
        <div className={styles.message}>{QUERY_COPY.quota_exceeded}</div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.message}>Something went wrong. Try again.</div>
      {result.requestId ? (
        <p className={styles.foot}>Request ID: {result.requestId}</p>
      ) : null}
    </div>
  );
}

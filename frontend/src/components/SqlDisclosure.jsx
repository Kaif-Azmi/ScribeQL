import { useState } from "react";
import styles from "./SqlDisclosure.module.css";

function dialectLabel(dialect) {
  if (dialect === "mysql") return "MySQL";
  if (dialect === "postgres") return "Postgres";
  return dialect || "SQL";
}

export default function SqlDisclosure({ sql, dialect, open = false }) {
  const [copied, setCopied] = useState(false);
  if (!sql) return null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <details className={styles.block} open={open || undefined}>
      <summary className={styles.summary}>{open ? "SQL" : "Show SQL"}</summary>
      <div className={styles.inner}>
        <div className={styles.toolbar}>
          <button type="button" className={styles.copy} onClick={copy}>
            {copied ? "Copied" : `Copy ${dialectLabel(dialect)} SQL`}
          </button>
        </div>
        <pre className={styles.code}>
          <code>{sql}</code>
        </pre>
      </div>
    </details>
  );
}

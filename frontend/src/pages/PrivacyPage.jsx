import PublicLayout from "../components/layout/PublicLayout.jsx";
import styles from "./auth.module.css";

export default function PrivacyPage() {
  return (
    <PublicLayout>
      <article className={styles.card}>
        <h1 className={styles.title}>Privacy notice</h1>
        <p className={styles.lede}>
          Questions, uploaded schemas and hints are sent to a third-party AI provider, which may
          use inputs to improve its products.
        </p>
        <p className={styles.lede}>
          Questions are stored in the query log, and account emails are stored, until the account
          is deleted.
        </p>
        <p className={styles.lede}>
          Generated SQL for an identical schema and question may be served to another user from a
          shared cache. What is shared is SQL text, never row data, and cached entries for
          uploaded schemas expire after a few days.
        </p>
        <p className={styles.lede}>Uploaded schemas are parsed but never executed.</p>
      </article>
    </PublicLayout>
  );
}

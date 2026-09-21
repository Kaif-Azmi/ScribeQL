import StudioAsk from "./StudioAsk.jsx";
import useStudioSession from "../hooks/useStudioSession.js";
import { QUERY_COPY } from "../lib/errors.js";
import styles from "./Studio.module.css";
import StudioWorkspace from "../components/layout/StudioWorkspace.jsx";

export default function StudioDemoPage() {
  const { session, loading, error, refresh } = useStudioSession("demo");

  if (loading) return <div className={styles.workspaceLoading}>Starting demo workspace…</div>;
  if (error) {
    return (
      <StudioWorkspace mode="Demo">
        <p>{QUERY_COPY.network}</p>
        {error.requestId ? <p>Request ID: {error.requestId}</p> : null}
        <button type="button" className={styles.submit} onClick={() => refresh()}>
          Retry
        </button>
      </StudioWorkspace>
    );
  }
  if (!session) return null;

  return <StudioWorkspace mode="Demo"><section className={styles.studioCanvas}>
    <p className={styles.workspaceEyebrow}>LIVE DATABASE · POSTGRESQL</p>
    <h1>Ready to explore your data?</h1>
    <div className={styles.databaseBar}><span>Database:</span><strong>◫ &nbsp; Demo E-commerce DB</strong><i>⌄</i></div>
    <div className={styles.studioPanel}><StudioAsk session={session} onSessionMissing={async () => { await refresh(); }} /></div>
    <div className={styles.shortcutBar}><button type="button">ϟ Generate SQL</button><button type="button">ϟ Optimize SQL</button><button type="button">ϟ Explain SQL</button><button type="button">More templates →</button></div>
    <div className={styles.studioNote}><span>Demo mode · every query is read-only</span><span>Explore safely →</span></div>
  </section></StudioWorkspace>;
}

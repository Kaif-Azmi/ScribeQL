import { Link } from "react-router-dom";
import Footer from "./Footer.jsx";
import styles from "./StudioWorkspace.module.css";

const groups = [
  { label: "Chat", items: [["◷", "History"], ["ϟ", "Templates"]] },
  { label: "Insights", items: [["▦", "Browse all"]] },
  { label: "Configuration", items: [["◫", "Databases"], ["⌘", "API settings"], ["⚙", "Settings"]] },
];

export default function StudioWorkspace({ mode, children }) {
  return (
    <div className={styles.workspace}>
      <aside className={styles.sidebar}>
        <Link to="/start" className={styles.brand}><span>◉</span> ScribeQL</Link>
        <Link to="/start" className={styles.newButton}><b>＋</b> New</Link>
        <nav className={styles.navigation}>
          {groups.map((group) => (
            <section key={group.label}>
              <h2>{group.label}<span>⌃</span></h2>
              <div>{group.items.map(([icon, label]) => <button type="button" key={label}><i>{icon}</i>{label}</button>)}</div>
            </section>
          ))}
        </nav>
        <div className={styles.demoNotice}><span>◫</span><p>{mode === "Demo" ? "You're using the read-only demo database." : "Your DDL is parsed locally and never executed."}</p></div>
      </aside>
      <div className={styles.content}>
        <header className={styles.topbar}><span>{mode} studio</span><div><Link to="/start">← Workspaces</Link><Link to="/account" className={styles.avatar}>SQ</Link></div></header>
        <main className={styles.main}>{children}</main>
        <Footer />
      </div>
    </div>
  );
}

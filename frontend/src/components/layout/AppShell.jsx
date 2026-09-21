import SiteHeader from "./SiteHeader.jsx";
import Footer from "./Footer.jsx";
import styles from "./AppShell.module.css";

export default function AppShell({ children, wide = false }) {
  return (
    <div className={styles.shell}>
      <SiteHeader />
      <main className={`${styles.main} ${wide ? styles.mainWide : ""}`}>{children}</main>
      <Footer />
    </div>
  );
}

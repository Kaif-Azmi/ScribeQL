import SiteHeader from "./SiteHeader.jsx";
import Footer from "./Footer.jsx";
import styles from "./PublicLayout.module.css";

export default function PublicLayout({
  children,
  wide = false,
}) {
  return (
    <div className={styles.shell}>
      <SiteHeader />
      <div className={styles.stage}>
        <div className={styles.horizon} aria-hidden="true">
          <span className={styles.horizonLeft} />
          <span className={styles.horizonRight} />
        </div>
        <main className={`${styles.main} ${wide ? styles.wide : ""}`}>{children}</main>
      </div>
      <Footer />
    </div>
  );
}

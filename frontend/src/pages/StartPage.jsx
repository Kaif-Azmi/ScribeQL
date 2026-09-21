import { Link } from "react-router-dom";
import LogoMark from "../components/LogoMark.jsx";
import SiteHeader from "../components/layout/SiteHeader.jsx";
import Footer from "../components/layout/Footer.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { formatUsageLine } from "../lib/errors.js";
import styles from "./StartPage.module.css";

export default function StartPage() {
  const { usage } = useAuth();
  const usageLine = formatUsageLine(usage);

  return (
    <div className={styles.page}>
      <SiteHeader />

      <section className={styles.hero}>
        <div className={styles.horizon} aria-hidden="true">
          <span className={styles.horizonLeft} />
          <span className={styles.horizonRight} />
        </div>

        <p className={styles.badge}>
          <LogoMark className={styles.badgeMark} />
          Choose a mode
        </p>
        <h1 className={styles.title}>
          Where should this
          <br />
          question run?
        </h1>
        {usageLine ? <p className={styles.usage}>{usageLine}</p> : null}

        <div className={styles.grid}>
          <article className={styles.card}>
            <div className={`${styles.art} ${styles.artDemo}`}>
              <span className={styles.live} />
              <small>Postgres · live</small>
              <table>
                <tbody>
                  <tr>
                    <td>Asha Verma</td>
                    <td>48210</td>
                  </tr>
                  <tr>
                    <td>Rohan Mehta</td>
                    <td>45990</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className={styles.body}>
              <h2>Demo database</h2>
              <p>Postgres e-commerce data, runs live.</p>
              <Link className={styles.cta} to="/studio/demo">
                Try the demo
              </Link>
            </div>
          </article>

          <article className={styles.card}>
            <div className={`${styles.art} ${styles.artCustom}`}>
              <code>.sql</code>
              <small>Parsed, never executed</small>
            </div>
            <div className={styles.body}>
              <h2>Use my schema</h2>
              <p>Upload your own DDL. Generates SQL, doesn&apos;t execute it.</p>
              <Link className={styles.ctaGhost} to="/studio/custom">
                Upload a schema
              </Link>
            </div>
          </article>
        </div>
      </section>

      <Footer />
    </div>
  );
}

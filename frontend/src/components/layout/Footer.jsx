import { Link } from "react-router-dom";
import LogoMark from "../LogoMark.jsx";
import styles from "./Footer.module.css";

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <section className={styles.ctaBand}>
        <div>
          <p>Ready to query your data?</p>
          <h2>Turn plain questions into<br />checked SQL.</h2>
        </div>
        <Link className={styles.cta} to="/signin">Start for free <span>→</span></Link>
      </section>
      <div className={styles.content}>
        <div className={styles.intro}>
          <Link to="/" className={styles.brand}><LogoMark className={styles.mark} />ScribeQL</Link>
          <p>Natural language to safe, schema-aware SQL.</p>
          <div className={styles.socials} aria-label="Product links"><Link to="/privacy" aria-label="Privacy notice">◌</Link><Link to="/signin" aria-label="Sign in">↗</Link></div>
        </div>
        <nav className={styles.links} aria-label="Footer navigation">
          <div><h3>Product</h3><Link to="/studio/demo">Demo database</Link><Link to="/studio/custom">Use my schema</Link><Link to="/start">Workspaces</Link></div>
          <div><h3>Account</h3><Link to="/signin">Sign in</Link><Link to="/signup">Create account</Link><Link to="/account">Account</Link></div>
          <div><h3>Company</h3><Link to="/privacy">Privacy notice</Link><Link to="/">About ScribeQL</Link></div>
        </nav>
      </div>
      <div className={styles.bottom}><span>© {new Date().getFullYear()} ScribeQL. Built for safer SQL exploration.</span><div><Link to="/privacy">Privacy</Link><Link to="/privacy">Terms</Link></div></div>
    </footer>
  );
}

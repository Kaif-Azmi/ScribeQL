import { Link } from "react-router-dom";
import LogoMark from "../LogoMark.jsx";
import styles from "./SiteHeader.module.css";

/** The shared site header used by public and signed-in screens. */
export default function SiteHeader() {
  return (
    <header className={styles.nav}>
      <Link to="/" className={styles.brand}>
        <LogoMark className={styles.mark} />
        ScribeQL
      </Link>
      <div className={styles.navActions}>
        <Link className={styles.navGhost} to="/signin">
          Sign in
        </Link>
        <Link className={styles.navCta} to="/signin">
          Try for free
        </Link>
      </div>
    </header>
  );
}

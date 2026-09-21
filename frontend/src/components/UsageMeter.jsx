import { useAuth } from "../auth/AuthProvider.jsx";
import { formatUsageMeter } from "../lib/errors.js";
import styles from "./UsageMeter.module.css";

export default function UsageMeter() {
  const { usage } = useAuth();
  return <div className={styles.meter}>{formatUsageMeter(usage)}</div>;
}

import styles from "./Warnings.module.css";

export default function Warnings({ items }) {
  if (!items?.length) return null;
  return (
    <ul className={styles.list}>
      {items.map((text, i) => (
        <li key={i} className={styles.item}>
          {text}
        </li>
      ))}
    </ul>
  );
}

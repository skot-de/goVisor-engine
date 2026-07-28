import Link from "next/link";
import { Brand } from "./Brand";
import { copy } from "@/lib/copy";
import styles from "./SiteFooter.module.css";

export function SiteFooter() {
  const year = 2026; // Build-Jahr; bewusst statisch (kein Date.now zur Render-Zeit nötig)
  return (
    <footer className={styles.foot}>
      <div className={`wrap ${styles.inner}`}>
        <div className={styles.brandcol}>
          <Brand />
          <p className={styles.tagline}>{copy.footer.tagline}</p>
        </div>
        <nav className={styles.links}>
          <Link href="/preise" className={styles.link}>
            {copy.footer.pricing}
          </Link>
          <Link href="/impressum" className={styles.link}>
            {copy.footer.impressum}
          </Link>
          <Link href="/datenschutz" className={styles.link}>
            {copy.footer.datenschutz}
          </Link>
        </nav>
      </div>
      <div className={`wrap ${styles.legal}`}>
        <span>
          © {year} {copy.brand}. {copy.footer.rights}
        </span>
        <span className={styles.creed}>{copy.creed}</span>
      </div>
    </footer>
  );
}

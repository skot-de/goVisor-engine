import Link from "next/link";
import { Brand } from "./Brand";
import { copy } from "@/lib/copy";
import styles from "./SiteHeader.module.css";

export function SiteHeader() {
  return (
    <header className={styles.bar}>
      <div className={`wrap ${styles.inner}`}>
        <Brand />
        <nav className={styles.nav}>
          <Link href="/#funktionsweise" className={styles.link}>
            {copy.nav.features}
          </Link>
          <Link href="/preise" className={styles.link}>
            {copy.nav.pricing}
          </Link>
          <span className={styles.sep} aria-hidden />
          <Link href="/login" className={styles.link}>
            {copy.nav.login}
          </Link>
          <Link href="/registrieren" className="btn btn-primary">
            {copy.nav.signup}
          </Link>
        </nav>
      </div>
    </header>
  );
}

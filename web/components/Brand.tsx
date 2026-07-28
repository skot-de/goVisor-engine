import Link from "next/link";

/** goVisor-Wortmarke — das „V" in Signalgrün, wie im Prototyp (.brandcell span). */
export function Brand({ size = 16 }: { size?: number }) {
  return (
    <Link
      href="/"
      aria-label="goVisor — Startseite"
      style={{
        fontSize: size,
        fontWeight: 700,
        letterSpacing: "-.03em",
        color: "var(--ink-900)",
      }}
    >
      go<span style={{ color: "var(--signal)" }}>V</span>isor
    </Link>
  );
}

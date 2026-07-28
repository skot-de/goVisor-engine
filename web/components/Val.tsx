import type { Herkunft } from "@/lib/copy";

/**
 * Beleg-Strich (Übergabenotiz §2). Ein Wert trägt IMMER seine Herkunft.
 * Asymmetrisch: `echt` bekommt kein Zeichen. Nur Abweichungen werden markiert.
 *
 *  echt       — aus der Quelle, unverändert (kein Punkt)
 *  schaetz    — abgeleitet, grauer Punkt, Begründung im title/Tooltip
 *  unsicher   — amber Punkt (z. B. Entity nur über Namensähnlichkeit)
 *  unbekannt  — grauer Text „nicht angegeben"; die Quelle nennt nichts
 *  na         — fachlich nicht anwendbar
 */
export function Val({
  src = "echt",
  reason,
  num = false,
  children,
}: {
  src?: Herkunft;
  /** Begründung im Tooltip — bei geschätzt/unsicher Pflicht, sonst Dekoration. */
  reason?: string;
  /** Zahl → tabellarische Mono-Ziffern. */
  num?: boolean;
  children?: React.ReactNode;
}) {
  const content = src === "unbekannt" ? "nicht angegeben" : children;
  return (
    <span className={`val${num ? " num" : ""}`} data-src={src} title={reason}>
      {content}
    </span>
  );
}

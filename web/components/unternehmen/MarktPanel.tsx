"use client";
/**
 * Der Markt in Zahlen — für den abgemeldeten Zustand von „Unser Unternehmen".
 *
 * **Warum Zahlen statt Aufzählung.** Vorher standen hier drei Sätze darüber, was ein Profil
 * bewirkt. Das ist eine Behauptung. Svens Vorschlag war besser: allgemeine Marktdaten
 * zeigen, solange das Unternehmen noch nicht angemeldet ist — dann sieht man, worum es
 * überhaupt geht, bevor man etwas eingibt.
 *
 * **Es sind ECHTE Zahlen, keine Beispiele.** Sie kommen aus `/api/branchen`, derselben
 * Quelle wie die Grundraum-Zähler in der Akquise. Erfundene Marktzahlen auf einer
 * Einstiegsseite wären genau die Sorte Zierde, die das Produkt sonst vermeidet — und
 * jemand würde sie zitieren.
 *
 * Die Aussage der Seite entsteht erst aus dem Verhältnis: so viele Vergaben laufen, und
 * ohne Profil sind sie alle gleich weit weg.
 */
import { useEffect, useState } from "react";
import { useSprache } from "@/lib/i18n";

const LABEL: Record<string, string> = {
  bau: "Bau & Infrastruktur", it: "IT & Software", beratung: "Beratung & Dienstleistung",
  energie: "Energie & Umwelt", medizin: "Medizin & Gesundheit", sicherheit: "Sicherheit",
  ohne: "Ohne Kategorie",
};

export function MarktPanel() {
  const { t } = useSprache();
  const [zahlen, setZahlen] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    fetch("/api/branchen", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setZahlen(d && typeof d === "object" ? d : null))
      .catch(() => setZahlen(null));
  }, []);

  // Fehlt die Quelle, wird NICHTS gezeigt — kein Platzhalter, keine geratene Zahl.
  // Eine leere Stelle ist ehrlicher als eine erfundene.
  if (!zahlen) return null;

  const paare = Object.entries(zahlen)
    .filter(([k, v]) => k !== "ohne" && v > 0)
    .sort((a, b) => b[1] - a[1]);
  if (!paare.length) return null;

  const gesamt = paare.reduce((s, [, v]) => s + v, 0);
  const groesster = paare[0][1];

  return (
    <section className="mk-panel">
      <div className="mk-kopf">
        <div className="mk-zahl">{gesamt.toLocaleString("de-DE")}</div>
        <div className="mk-lbl">
          {t("Vergaben im Bestand")}
          <span>{t("alle Fachgebiete, laufend aktualisiert")}</span>
        </div>
      </div>

      <ul className="mk-balken">
        {paare.map(([k, v]) => (
          <li key={k}>
            <span className="mk-name">{LABEL[k] || k}</span>
            <span className="mk-bahn">
              <span className="mk-fuell" style={{ width: `${Math.max(2, (v / groesster) * 100)}%` }} />
            </span>
            <span className="mk-wert">{v.toLocaleString("de-DE")}</span>
          </li>
        ))}
      </ul>

      {/* Der Satz, der die Zahlen zur Aussage macht. Ohne ihn ist es eine Statistik. */}
      <p className="mk-fuss">
        {t("Ohne Profil sind das alles gleich weite Treffer. Mit Profil sortiert goVisor nach eurem Fachgebiet und eurem Umkreis, und hält die Eignungsnachweise gegen das, was in den Unterlagen verlangt wird.")}
      </p>
    </section>
  );
}

export default MarktPanel;

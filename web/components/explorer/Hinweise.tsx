"use client";
/**
 * Die Hinweis-Spalte in der Lead-Detailseite.
 *
 * Regeln und Begründung stehen in `lib/hinweise.ts` — hier nur die Darstellung. Zwei Dinge,
 * die absichtlich so sind und nicht anders:
 *
 * 1. Der Beleg steht IMMER da, nicht in einem Tooltip. Ein Hinweis, dessen Begründung man
 *    erst aufklappen muss, wird als Behauptung gelesen. Bei „Frist verlängert" ist die
 *    Begründung sogar die eigentliche Information (welches Datum galt vorher, welches jetzt).
 *
 * 2. „mehr" klappt nur die ÜBERZÄHLIGEN auf, nie die ersten vier. Wer die Spalte öffnet,
 *    soll nie erst suchen müssen, was schon sichtbar war.
 */
import { useState } from "react";
import { baueHinweise, teile, type Hinweis, type HinweisFelder } from "@/lib/hinweise";

const SYMBOL: Record<Hinweis["art"], string> = {
  warnung: "⚡",
  chance: "◆",
  herkunft: "○",
};

function Zeile({ h }: { h: Hinweis }) {
  return (
    <li className={`hinweis hinweis--${h.art}`}>
      <span className="hinweis-symbol" aria-hidden="true">{SYMBOL[h.art]}</span>
      <span className="hinweis-text">
        <span className="hinweis-label">{h.label}</span>
        <span className="hinweis-beleg">{h.beleg}</span>
      </span>
    </li>
  );
}

export function Hinweise({ felder }: { felder: HinweisFelder }) {
  const [alleZeigen, setAlleZeigen] = useState(false);
  const hinweise = baueHinweise(felder);
  // Keine leere Überschrift: hat ein Lead keine Hinweise, ist das kein Mangel, sondern der
  // Normalfall — eine Sektion „Zusätzliche Hinweise: keine" wäre nur Lärm.
  if (hinweise.length === 0) return null;

  const { offen, versteckt } = teile(hinweise);
  return (
    <section className="hinweise-block">
      <h3 className="hinweise-titel">Zusätzliche Hinweise</h3>
      <ul className="hinweise-liste">
        {offen.map((h, i) => <Zeile key={`o${i}`} h={h} />)}
        {alleZeigen && versteckt.map((h, i) => <Zeile key={`v${i}`} h={h} />)}
      </ul>
      {versteckt.length > 0 && (
        <button className="hinweise-mehr" onClick={() => setAlleZeigen((v) => !v)}>
          {alleZeigen ? "weniger" : `${versteckt.length} weitere`}
        </button>
      )}
    </section>
  );
}

export default Hinweise;

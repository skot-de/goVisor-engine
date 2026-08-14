"use client";
/**
 * Die Hinweise am Lead — als Label-Chips in EINER Zeile.
 *
 * Regeln und Begründung der Hinweise selbst stehen in `lib/hinweise.ts`; hier nur die
 * Darstellung.
 *
 * **Umgebaut am 2026-08-15, und die vorherige Fassung war nicht falsch, sondern zu laut.**
 * Sie zeigte jeden Hinweis als eigenen Kasten mit Label UND vollem Belegsatz, alle
 * untereinander. Bei vier Hinweisen waren das acht Zeilen ganz oben in der Übersicht — die
 * Eckdaten (Volumen, Frist, Leistungsort) rutschten unter die Falz. Ein Nebenhinweis
 * verdrängte damit die Hauptsache.
 *
 * Chips lösen das, und sie sind ohnehin die Form, für die das geschlossene Vokabular
 * gebaut wurde: feste Label sind scannbar und später als Filter verwendbar — ein Kasten
 * mit Fließtext ist beides nicht.
 *
 * **Der Beleg bleibt Pflicht, er wandert nur.** Das ist der Punkt, an dem ich beim Umbau
 * aufgepasst habe: „nur Label" allein würde aus jedem Hinweis eine Behauptung machen
 * („Frist verlängert" — sagt wer?). Deshalb steht unter der Chip-Zeile eine feste
 * Belegzeile, die den Satz des angeklickten Chips zeigt. Beim Öffnen ist der ERSTE Chip
 * gewählt, und die Sortierung stellt die Warnung nach vorn — der teuerste Hinweis ist also
 * ohne einen einzigen Klick vollständig zu lesen.
 *
 * Die Zeile ist reserviert, auch wenn sie kurz ist: sonst springt das Layout bei jedem
 * Klick, und Springen liest sich als Fehler.
 */
import { useState } from "react";
import { baueHinweise, sortiere, type Hinweis, type HinweisFelder } from "@/lib/hinweise";

const SYMBOL: Record<Hinweis["art"], string> = {
  warnung: "⚡",
  chance: "◆",
  herkunft: "○",
};

export function Hinweise({ felder }: { felder: HinweisFelder }) {
  const hinweise = sortiere(baueHinweise(felder));
  const [gewaehlt, setGewaehlt] = useState(0);

  // Keine leere Überschrift: hat ein Lead keine Hinweise, ist das kein Mangel, sondern der
  // Normalfall — eine Sektion „Zusätzliche Hinweise: keine" wäre nur Lärm.
  if (hinweise.length === 0) return null;

  // Nach einem Lead-Wechsel kann der alte Index ins Leere zeigen.
  const aktiv = Math.min(gewaehlt, hinweise.length - 1);

  return (
    <section className="hinweise-block" aria-label="Zusätzliche Hinweise">
      <div className="hinweise-chips" role="tablist">
        {hinweise.map((h, i) => (
          <button
            key={h.label}
            role="tab"
            aria-selected={i === aktiv}
            className={`hinweis-chip hinweis-chip--${h.art}${i === aktiv ? " ist-aktiv" : ""}`}
            onClick={() => setGewaehlt(i)}
            // Der Beleg hängt zusätzlich am title: wer mit der Maus darüberfährt oder einen
            // Screenreader benutzt, bekommt ihn, ohne die Auswahl zu ändern.
            title={h.beleg}
          >
            <span className="hinweis-chip-symbol" aria-hidden="true">{SYMBOL[h.art]}</span>
            {h.label}
          </button>
        ))}
      </div>
      <p className="hinweis-beleg" role="note">{hinweise[aktiv].beleg}</p>
    </section>
  );
}

export default Hinweise;

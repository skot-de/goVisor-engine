"use client";
/**
 * Die Abschnitte EINES Bereichs — eine Bauform für alle.
 *
 * **Warum es das gibt.** Dieselbe Aufgabe — innerhalb eines Bereichs den Abschnitt
 * wechseln — war bis 2026-08-16 viermal verschieden gelöst: Unternehmen hatte waagerechte
 * Reiter in der Kopfzeile, Strategie eine senkrechte Liste in einer zweiten Spalte,
 * Bausteine eine dritte senkrechte Liste in einer anderen zweiten Spalte, und die
 * Lead-Ansichten stecken in der Rail. Vier Orte, vier Aussehen, ein Zweck.
 *
 * Das war nie entschieden worden — jeder Bereich hatte seine Navigation mitgebracht, als er
 * gebaut wurde. Für den Nutzer ist das Ergebnis, dass er in jedem Bereich neu suchen muss,
 * wo er hinklicken kann.
 *
 * **Gruppen statt Verschachtelung.** Strategie hat neun Abschnitte in zwei Sinngruppen
 * („Markt" / „Wir"). Die bleiben erhalten, aber als Trennstrich in derselben Zeile — eine
 * zweite Ebene aufzuklappen wäre wieder eine eigene Bauform für einen einzigen Bereich.
 *
 * **Zahlen nur, wo sie etwas sagen.** Bausteine zählt seine Themen (wie viele Bausteine
 * liegen darin), Strategie und Unternehmen haben nichts zu zählen. Ein Feld, das mal Zahlen
 * trägt und mal nicht, ist kein Mangel — eine erfundene Null wäre einer.
 */
import { useSprache } from "@/lib/i18n";

export type NavPunkt = { key: string; label: string; anzahl?: number };
export type NavGruppe = { titel?: string; punkte: NavPunkt[] };

export function BereichsNav({ gruppen, aktiv, onWechsel, hinweis }: {
  gruppen: NavGruppe[];
  aktiv: string;
  onWechsel: (key: string) => void;
  /** Optionaler Text am rechten Rand — z. B. „Was kommt in 24 Monaten?". */
  hinweis?: string;
}) {
  const { t } = useSprache();

  return (
    <nav className="bnav" role="tablist" aria-label={t("Abschnitte")}>
      {gruppen.map((g, gi) => (
        <span key={g.titel ?? gi} className="bnav-g">
          {/* Der Trenner steht ZWISCHEN den Gruppen, nicht vor jeder — sonst beginnt die
              Zeile mit einem Strich, der nichts trennt. */}
          {gi > 0 ? <span className="bnav-trenner" aria-hidden="true" /> : null}
          {g.titel ? <span className="bnav-gt">{t(g.titel)}</span> : null}
          {g.punkte.map((p) => (
            <button key={p.key} role="tab" aria-selected={aktiv === p.key}
              className={`bnav-i ${aktiv === p.key ? "on" : ""}`}
              onClick={() => onWechsel(p.key)}>
              {t(p.label)}
              {typeof p.anzahl === "number" ? <span className="bnav-n">{p.anzahl}</span> : null}
            </button>
          ))}
        </span>
      ))}
      {hinweis ? <span className="bnav-hinweis">{hinweis}</span> : null}
    </nav>
  );
}

export default BereichsNav;

/**
 * Zusätzliche Hinweise am Lead — der Sammelplatz für Signale, die eine Entscheidung ändern.
 *
 * **Warum ein Sammelplatz und nicht je Signal ein Ort.** Vorher wäre jedes Signal an seine
 * eigene Stelle gewandert: Amtsinhaber-Dauer in den Bewertungs-Reiter, Fristkorrektur in die
 * Übersicht, Kategorie-Herkunft ans Label. Das zwingt bei jedem neuen Signal zu einer neuen
 * Design-Entscheidung — und es kommen laufend welche dazu.
 *
 * **Die Aufnahmeregel: ein Hinweis muss eine ENTSCHEIDUNG ändern.**
 *
 *   „Frist verlängert"      ändert Verhalten   — der Bieter hielt die Vergabe für tot
 *   „4× erfolglos gesucht"  ändert die Bietentscheidung
 *   „Kategorie abgeleitet"  ändert das Vertrauen in den Filter
 *   „CPV 45000000-7"        ändert nichts       → gehört NICHT hierher, das ist Metadatum
 *
 * Ohne diese Regel wird die Spalte eine Halde, und eine Halde liest niemand. Genau dann geht
 * auch der eine Hinweis unter, der wirklich zählt.
 *
 * **Der Beleg ist Pflicht.** Jeder Hinweis trägt den einen Satz, der ihn überprüfbar macht —
 * dieselbe Logik wie bei `deadline_source` und `band_source`: das Produkt behauptet nichts,
 * es zeigt, woher es etwas weiß. Ein Hinweis ohne Beleg ist eine Behauptung.
 *
 * Wo der Beleg STEHT, entscheidet die Darstellung (seit 2026-08-15 eine feste Zeile unter
 * den Chips, s. `Hinweise.tsx`). Dass es ihn gibt, entscheidet diese Datei — ein Label ohne
 * Satz darf hier gar nicht erst entstehen.
 */

/** Steuert Rangfolge und Farbe. Nicht kosmetisch: die Reihenfolge ist die Aussage. */
export type HinweisArt =
  | "warnung"   // etwas stimmt nicht mit dem, was anderswo steht — zuerst lesen
  | "chance"    // ein Grund, eher zu bieten
  | "herkunft"; // woher wir etwas wissen; schafft Vertrauen, drängt aber nicht

/**
 * GESCHLOSSENES LABEL-VOKABULAR. Die Zahl gehört in den Beleg, nicht ins Label.
 *
 * Erster Entwurf hatte „4× erfolglos gesucht" — für das Auge sind „4×" und „7×" zwei
 * verschiedene Dinge, obwohl es dieselbe Aussage ist. Feste Label lösen drei Probleme auf
 * einmal:
 *
 *   FILTERBAR      Freitext lässt sich nicht filtern. Ein geschlossenes Vokabular wird zu
 *                  Filter-Chips („zeig mir alle mit Mehrmals ohne Zuschlag") — das ist der
 *                  eigentliche Gewinn, nicht die Optik.
 *   SCANNBAR       Das Auge erkennt eine wiederkehrende Phrase, keine wechselnde Zahl.
 *   ÜBERSETZBAR    Das Projekt nimmt den deutschen Satz als i18n-Schlüssel. Ein Label mit
 *                  eingebauter Zahl bräuchte Interpolation; ein festes ist EIN Schlüssel.
 *
 * Wer hier ein Label ergänzt, ergänzt einen Filter — deshalb steht die Liste im Code und
 * nicht als Freitext an der Fundstelle.
 */
export const LABEL = {
  fristVerlaengert:   "Frist verlängert",
  mehrmalsOhne:       "Mehrmals ohne Zuschlag",
  amtsinhaberNeu:     "Amtsinhaber neu",
  amtsinhaberFest:    "Amtsinhaber etabliert",
  mehrerePortale:     "Auf mehreren Portalen",
  kategorieAbgeleitet: "Kategorie abgeleitet",
  kategorieZweitquelle: "Kategorie aus Zweitquelle",
} as const;

export type Label = (typeof LABEL)[keyof typeof LABEL];

export type Hinweis = {
  art: HinweisArt;
  label: Label;
  /** Der eine Satz, der den Hinweis überprüfbar macht — hier steht die Zahl. Pflicht. */
  beleg: string;
};

/* `SICHTBAR` und `teile()` sind am 2026-08-15 entfallen. Sie deckelten die Liste auf vier
 * Einträge und schoben den Rest hinter ein „mehr" — sinnvoll, solange jeder Hinweis ein
 * Kasten mit Belegsatz war. Als Chips passen alle in eine Zeile; ein Aufklapper für etwas,
 * das ohnehin nebeneinander steht, wäre nur ein zusätzlicher Klick.
 *
 * Sie stehen bewusst NICHT als ungenutzte Exporte weiter hier: eine Funktion, die eine
 * abgeschaffte Mechanik beschreibt, lädt dazu ein, sie wieder einzubauen. */

const RANG: Record<HinweisArt, number> = { warnung: 0, chance: 1, herkunft: 2 };

/** Sortiert nach Belegkraft der Art, innerhalb der Art stabil (Eingabereihenfolge). */
export function sortiere(hinweise: Hinweis[]): Hinweis[] {
  return [...hinweise].sort((a, b) => RANG[a.art] - RANG[b.art]);
}

/**
 * Rohfelder eines Leads → Hinweise.
 *
 * Die Feldnamen entsprechen dem, was `export_web_leads.py` liefern wird. Fehlt ein Feld,
 * entsteht schlicht kein Hinweis — die Komponente muss nie wissen, welche Signale die
 * Pipeline gerade kann. So lässt sich ein neues Signal anschliessen, ohne die Oberfläche
 * anzufassen.
 */
export type HinweisFelder = {
  /** `lead_deadline.deadline_source` — 'echt_verlaengert' heisst: veröffentlicht war früher. */
  deadlineSource?: string | null;
  deadlineVeroeffentlicht?: string | null;
  deadlineAktuell?: string | null;
  /** Anzahl Portale, auf denen dieselbe Vergabe steht (aus `notice_duplicates`). */
  portale?: string[] | null;
  /** `lead_kategorie.quelle` — 'modell' heisst abgeleitet statt veröffentlicht. */
  kategorieQuelle?: string | null;
  /** `incumbent_tenure` — wie lange sitzt der Amtsinhaber schon. */
  amtsinhaberSeitJahre?: number | null;
  amtsinhaberZyklen?: number | null;
  /** Chronisch erfolglos ausgeschriebener Bedarf (aus `retender_signal`, sobald verknüpft). */
  erfolgloseVersuche?: number | null;
  erfolgloseJahre?: number | null;
};

function datum(s?: string | null): string | null {
  if (!s) return null;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString("de-DE");
}

export function baueHinweise(f: HinweisFelder): Hinweis[] {
  const out: Hinweis[] = [];

  // WARNUNG. Die verlängerte Frist steht ganz oben, weil sie als einzige einen Lead
  // betrifft, den der Bieter anderswo als abgelaufen gesehen hat. Wer nur eine Quelle
  // liest, verpasst ihn — das ist unser Vorsprung, und er ist wertlos, wenn er nicht
  // sichtbar ist.
  if (f.deadlineSource === "echt_verlaengert" && f.deadlineAktuell) {
    const alt = datum(f.deadlineVeroeffentlicht);
    out.push({
      art: "warnung",
      label: LABEL.fristVerlaengert,
      beleg: alt
        ? `Veröffentlicht war der ${alt}, die aktuelle Frist ist der ${datum(f.deadlineAktuell)}.`
        : `Die aktuelle Frist ist der ${datum(f.deadlineAktuell)} — später als zunächst veröffentlicht.`,
    });
  }

  // CHANCE.
  if ((f.erfolgloseVersuche ?? 0) >= 2) {
    out.push({
      art: "chance",
      label: LABEL.mehrmalsOhne,
      beleg: `Derselbe Bedarf wurde ${f.erfolgloseVersuche}-mal${
        f.erfolgloseJahre ? ` in ${f.erfolgloseJahre} Jahren` : ""
      } ohne Zuschlag ausgeschrieben.`,
    });
  }
  // AMTSINHABER — zwei Label, weil es zwei ENTGEGENGESETZTE Aussagen sind.
  //
  // „Amtsinhaber neu" bringt jemanden zum Bieten, „etabliert" haelt ihn davon ab. Ein
  // gemeinsames Label mit wechselnder Zahl („seit 7 Jahren") ueberliesse dem Leser die
  // Deutung — und genau die Deutung ist die Information.
  //
  // Bewusst NICHT „Kein Amtsinhaberwechsel": das behauptet zusaetzlich, dass es
  // Gelegenheiten zum Wechsel GAB. Das stimmt erst ab mehreren Zyklen; bei einem einzigen
  // langen Vertrag waere es schlicht falsch. `chain_depth` zaehlt die Zyklen und ist
  // deshalb der richtige Massstab, nicht die Jahre.
  const zyklen = f.amtsinhaberZyklen ?? 0;
  if (zyklen >= 3) {
    out.push({
      art: "herkunft",   // GRAU, nicht gruen: das ist ein Grund GEGEN das Bieten.
      label: LABEL.amtsinhaberFest,
      beleg: `Derselbe Auftragnehmer hat den Bedarf ${zyklen}-mal in Folge gewonnen`
           + `${f.amtsinhaberSeitJahre ? `, seit ${f.amtsinhaberSeitJahre} Jahren` : ""}.`,
    });
  } else if (zyklen === 1 || ((f.amtsinhaberSeitJahre ?? 0) > 0 && zyklen === 0)) {
    out.push({
      art: "chance",
      label: LABEL.amtsinhaberNeu,
      beleg: "Der bisherige Auftragnehmer hält den Bedarf erst seit einem Vergabezyklus —"
           + " es gibt keine gewachsene Bindung.",
    });
  }

  // HERKUNFT.
  if (f.portale && f.portale.length > 1) {
    out.push({
      art: "herkunft",
      label: LABEL.mehrerePortale,
      beleg: `Dieselbe Vergabe erscheint auf ${f.portale.length} Portalen (${f.portale.join(", ")})`
           + " — die Angaben sind zusammengeführt.",
    });
  }
  if (f.kategorieQuelle === "modell") {
    out.push({
      art: "herkunft",
      label: LABEL.kategorieAbgeleitet,
      beleg: "Die Quelle führt keinen CPV-Code. Die Kategorie wurde aus dem Titel bestimmt "
           + "(Treffergenauigkeit rund 82 % gegen veröffentlichte Codes).",
    });
  } else if (f.kategorieQuelle === "zwilling") {
    out.push({
      art: "herkunft",
      label: LABEL.kategorieZweitquelle,
      beleg: "Die Quelle führt keinen CPV-Code; übernommen wurde der veröffentlichte Code "
           + "derselben Vergabe von einem anderen Portal.",
    });
  }

  return sortiere(out);
}

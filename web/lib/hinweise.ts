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
 */

/** Steuert Rangfolge und Farbe. Nicht kosmetisch: die Reihenfolge ist die Aussage. */
export type HinweisArt =
  | "warnung"   // etwas stimmt nicht mit dem, was anderswo steht — zuerst lesen
  | "chance"    // ein Grund, eher zu bieten
  | "herkunft"; // woher wir etwas wissen; schafft Vertrauen, drängt aber nicht

export type Hinweis = {
  art: HinweisArt;
  label: string;
  /** Der eine Satz, der den Hinweis überprüfbar macht. Pflicht. */
  beleg: string;
};

/**
 * Höchstens so viele stehen offen, der Rest kommt hinter „mehr".
 *
 * Vier ist keine runde Zahl, sondern die Grenze, ab der eine Liste zur Tapete wird. Wer
 * zwölf Labels sieht, liest keins — und dann ist der teuerste Hinweis (die verlängerte
 * Frist) genauso unsichtbar wie ohne die ganze Spalte.
 */
export const SICHTBAR = 4;

const RANG: Record<HinweisArt, number> = { warnung: 0, chance: 1, herkunft: 2 };

/** Sortiert nach Belegkraft der Art, innerhalb der Art stabil (Eingabereihenfolge). */
export function sortiere(hinweise: Hinweis[]): Hinweis[] {
  return [...hinweise].sort((a, b) => RANG[a.art] - RANG[b.art]);
}

export function teile(hinweise: Hinweis[]): { offen: Hinweis[]; versteckt: Hinweis[] } {
  const s = sortiere(hinweise);
  return { offen: s.slice(0, SICHTBAR), versteckt: s.slice(SICHTBAR) };
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
      label: "Frist verlängert",
      beleg: alt
        ? `Veröffentlicht war der ${alt}, die aktuelle Frist ist der ${datum(f.deadlineAktuell)}.`
        : `Die aktuelle Frist ist der ${datum(f.deadlineAktuell)} — später als zunächst veröffentlicht.`,
    });
  }

  // CHANCE.
  if ((f.erfolgloseVersuche ?? 0) >= 2) {
    out.push({
      art: "chance",
      label: `${f.erfolgloseVersuche}× erfolglos gesucht`,
      beleg: `Derselbe Bedarf wurde ${f.erfolgloseVersuche}-mal${
        f.erfolgloseJahre ? ` in ${f.erfolgloseJahre} Jahren` : ""
      } ohne Zuschlag ausgeschrieben.`,
    });
  }
  if ((f.amtsinhaberSeitJahre ?? 0) > 0 || (f.amtsinhaberZyklen ?? 0) > 0) {
    // Beides ist eine Chance-Aussage, aber in BEIDE Richtungen — deshalb sagt der Beleg die
    // Zahl und nicht deren Deutung. Ein Amtsinhaber seit einem Zyklus ist angreifbar, einer
    // seit neun sitzt fest; welche Schwelle für den Bieter zählt, weiss er besser als wir.
    // Dativ, nicht Nominativ: „seit 7 Jahren", nicht „seit 7 Jahre". Aufgefallen erst beim
    // AUSFÜHREN — eine Zusicherung über den Quelltext hätte den Satz nie gelesen.
    const teile: string[] = [];
    if (f.amtsinhaberSeitJahre) {
      teile.push(`${f.amtsinhaberSeitJahre} ${f.amtsinhaberSeitJahre === 1 ? "Jahr" : "Jahren"}`);
    }
    if (f.amtsinhaberZyklen) {
      teile.push(`${f.amtsinhaberZyklen} ${f.amtsinhaberZyklen === 1 ? "Vergabezyklus" : "Vergabezyklen"}`);
    }
    out.push({
      art: "chance",
      label: `Amtsinhaber seit ${teile[0]}`,
      beleg: `Der bisherige Auftragnehmer hält den Auftrag seit ${teile.join(" bzw. ")}.`,
    });
  }

  // HERKUNFT.
  if (f.portale && f.portale.length > 1) {
    out.push({
      art: "herkunft",
      label: `Auf ${f.portale.length} Portalen`,
      beleg: `Dieselbe Vergabe erscheint auf ${f.portale.join(", ")} — die Angaben sind zusammengeführt.`,
    });
  }
  if (f.kategorieQuelle === "modell") {
    out.push({
      art: "herkunft",
      label: "Kategorie abgeleitet",
      beleg: "Die Quelle führt keinen CPV-Code. Die Kategorie wurde aus dem Titel bestimmt "
           + "(Treffergenauigkeit rund 82 % gegen veröffentlichte Codes).",
    });
  } else if (f.kategorieQuelle === "zwilling") {
    out.push({
      art: "herkunft",
      label: "Kategorie aus Zweitquelle",
      beleg: "Die Quelle führt keinen CPV-Code; übernommen wurde der veröffentlichte Code "
           + "derselben Vergabe von einem anderen Portal.",
    });
  }

  return sortiere(out);
}

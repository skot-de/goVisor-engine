/* Welche Filter sind gerade gesetzt — und wie nimmt man genau einen zurueck?
 *
 * WOFUER. Bis zum 2026-09-17 zeigte die Oberflaeche neben „Filter" nur eine ZAHL
 * (`advCount`). Beobachtet in einer Vorfuehrung: „zudem sehe ich meine aktiven
 * Filtereinstellungen nicht." Eine Zahl sagt, DASS etwas die Liste beschneidet, und laesst
 * raten, was. Ist die Liste kuerzer als erwartet, lautet die erste Frage immer „liegt das
 * an den Daten oder an meinen Filtern" — und eine Zahl beantwortet sie nicht.
 *
 * ⚠ WARUM PLAIN JS UND NICHT IM .tsx. Damit der Waechter `pruefe-filtermarken.mjs` die
 * ECHTE Funktion fahren kann statt einer Abschrift. Dieselbe Begruendung wie bei
 * `profileEngine.js`, `cronWache.js` und `ladegrund.js`: eine Abschrift geht gruen,
 * waehrend die benutzte Fassung eine Filterart verschweigt.
 *
 * ⚠ DIE BESCHRIFTUNGSTABELLEN LIEGEN MIT HIER, und `FilterPanel.tsx` holt sie von hier.
 * Zwei Listen derselben Woerter laufen unweigerlich auseinander, und der Unterschied
 * faellt genau dann auf, wenn jemand vor der Liste sitzt und nicht versteht, warum sie
 * kurz ist.
 */
import { STAATEN } from "@/lib/staaten";

export const PHASEN = [
  ["auslauf", "Auslaufende Verträge"],
  ["f02", "Aktive Ausschreibungen"],
  ["f01", "Ankündigungen"],
  ["award", "Zuschlag erteilt"],
];
export const HORIZONTE = [[1, "1 Mon."], [3, "3 Mon."], [6, "6 Mon."], [12, "12 Mon."], [18, "18 Mon."]];
export const LEISTUNG = [["dienst", "Dienstleistung"], ["liefer", "Lieferung"], ["bau", "Bauleistung"]];
export const RAHMEN = [["vgv", "VgV"], ["vob", "VOB/A"], ["uvgo", "UVgO"], ["sektvo", "SektVO"]];
export const BAND = [["niedrig", "niedrig"], ["mittel", "mittel"], ["hoch", "hoch"]];
export const ART = [["rahmen", "Rahmenvertrag"], ["wiederkehrend", "Wiederkehrend"], ["einzel", "Einzelauftrag"]];
export const LAENDER = [
  ["DE1", "Baden-Württemberg"], ["DE2", "Bayern"], ["DE3", "Berlin"], ["DE4", "Brandenburg"],
  ["DE5", "Bremen"], ["DE6", "Hamburg"], ["DE7", "Hessen"], ["DE8", "Mecklenburg-Vorp."],
  ["DE9", "Niedersachsen"], ["DEA", "Nordrhein-Westf."], ["DEB", "Rheinland-Pfalz"], ["DEC", "Saarland"],
  ["DED", "Sachsen"], ["DEE", "Sachsen-Anhalt"], ["DEF", "Schleswig-Holstein"], ["DEG", "Thüringen"],
];

/** Grosse Zahlen kurz: 2.000.000 → „2 Mio.". Ohne Nachkommastelle, wo keine noetig ist. */
export function kurzEur(n) {
  const f = (w, e) => {
    const g = w >= 100 || Number.isInteger(w) ? Math.round(w) : Math.round(w * 10) / 10;
    return String(g).replace(".", ",") + " " + e;
  };
  if (n >= 1e9) return f(n / 1e9, "Mrd.");
  if (n >= 1e6) return f(n / 1e6, "Mio.");
  if (n >= 1e3) return f(n / 1e3, "Tsd.");
  return String(n);
}

/**
 * Alle gesetzten Filter als Marken — je Marke der Text und der Patch, der GENAU sie
 * zuruecknimmt.
 *
 * ⚠ WERTGRENZEN STEHEN EINZELN, nicht als Spanne. Am 2026-09-17 stellte ein Nutzer
 * „2 bis 10 Mio" ein und meinte „bis 10 Mio"; dass daraus auch eine UNTERGRENZE wurde,
 * verbarg 91,9 % der Bau-Leads. Zwei Marken zeigen genau das, was eine zusammengezogene
 * Spanne verschweigt.
 *
 * ⚠ JEDE ART EINZELN. `advCount` summiert 22 Filterarten; wer hier eine auslaesst, baut
 * einen Zustand, in dem die Liste beschnitten ist UND keine Marke es sagt — schlimmer als
 * vorher, weil dann nicht einmal mehr die Zahl stimmt.
 *
 * @param {Record<string, unknown>} a       der Filterzustand (`Adv`)
 * @param {{cpv4: string, label: string}[]} segmente  CPV-Beschriftungen des Grundraums
 * @param {(k: string, v?: Record<string, string|number>) => string} t  Uebersetzung
 */
export function filterMarken(a, segmente, t) {
  const m = [];
  const paar = (liste, k) => (liste.find(([x]) => x === k) || [])[1] || k;
  /** Einen Wert aus einer Mehrfachauswahl nehmen, die anderen behalten. */
  const ohne = (xs, x) => xs.filter((y) => y !== x);

  for (const k of a.phases) m.push({ schluessel: `phases:${k}`, text: t(paar(PHASEN, k)),
    weg: { phases: ohne(a.phases, k) } });
  // Einzahl getrennt: „Zeithorizont 1 Monate" ist der Satz, an dem man sieht, dass niemand
  // hingeschaut hat — und 1 Monat ist die haeufigste Einstellung.
  if (a.horizon != null) m.push({ schluessel: "horizon", weg: { horizon: null },
    text: a.horizon === 1 ? t("Zeithorizont 1 Monat")
                          : t("Zeithorizont {n} Monate", { n: a.horizon }) });
  for (const c of a.cpvFields) m.push({ schluessel: `cpv:${c}`,
    text: (segmente.find((s) => s.cpv4 === c) || {}).label || c,
    weg: { cpvFields: ohne(a.cpvFields, c) } });
  for (const r of a.regions) m.push({ schluessel: `region:${r}`, text: paar(LAENDER, r),
    weg: { regions: ohne(a.regions, r) } });
  if (a.nationwide) m.push({ schluessel: "nationwide", text: t("Bundesweit erbringbare"),
    weg: { nationwide: false } });
  if (a.buyer.trim()) m.push({ schluessel: "buyer", weg: { buyer: "" },
    text: t("Vergabestelle: {v}", { v: a.buyer.trim() }) });
  for (const k of a.leistung) m.push({ schluessel: `leistung:${k}`, text: t(paar(LEISTUNG, k)),
    weg: { leistung: ohne(a.leistung, k) } });
  for (const k of a.art) m.push({ schluessel: `art:${k}`, text: t(paar(ART, k)),
    weg: { art: ohne(a.art, k) } });
  for (const k of a.rahmen) m.push({ schluessel: `rahmen:${k}`, text: paar(RAHMEN, k),
    weg: { rahmen: ohne(a.rahmen, k) } });
  if (a.valMin != null) m.push({ schluessel: "valMin", weg: { valMin: null },
    text: t("ab {v}", { v: kurzEur(a.valMin) }) });
  if (a.valMax != null) m.push({ schluessel: "valMax", weg: { valMax: null },
    text: t("bis {v}", { v: kurzEur(a.valMax) }) });
  if (a.neu !== "all") m.push({ schluessel: "neu", weg: { neu: "all" },
    text: t(a.neu === "neu" ? "Neuvergabe (kein Amtsinhaber)" : "Folgevergabe") });
  if (a.wenigWettbewerb) m.push({ schluessel: "wenigWettbewerb", text: t("Zuletzt wenig Bieter"),
    weg: { wenigWettbewerb: false } });
  for (const k of a.aufwand) m.push({ schluessel: `aufwand:${k}`,
    text: t("Aufwand {v}", { v: t(paar(BAND, k)) }), weg: { aufwand: ohne(a.aufwand, k) } });
  if (a.buergschaft !== "all") m.push({ schluessel: "buergschaft", weg: { buergschaft: "all" },
    text: t(a.buergschaft === "ja" ? "Bürgschaft gefordert" : "Ohne Bürgschaft") });
  for (const k of a.chance) m.push({ schluessel: `chance:${k}`,
    text: t("Chance {v}", { v: t(paar(BAND, k)) }), weg: { chance: ohne(a.chance, k) } });
  for (const k of a.relevanz) m.push({ schluessel: `relevanz:${k}`,
    text: t("Relevanz {v}", { v: t(paar(BAND, k)) }), weg: { relevanz: ohne(a.relevanz, k) } });
  if (a.multiLot) m.push({ schluessel: "multiLot", text: t("Nur mit mehreren Losen"),
    weg: { multiLot: false } });
  if (a.hasDetail) m.push({ schluessel: "hasDetail", text: t("Nur mit ausführlicher Beschreibung"),
    weg: { hasDetail: false } });
  if (a.unterlagen) m.push({ schluessel: "unterlagen", weg: { unterlagen: false },
    text: t("Nur mit Link zu den Vergabeunterlagen") });
  if (a.ausgewertet) m.push({ schluessel: "ausgewertet", weg: { ausgewertet: false },
    text: t("Nur mit ausgewerteten Unterlagen") });
  for (const k of a.staaten) m.push({ schluessel: `staat:${k}`,
    text: (STAATEN.find((x) => x[0] === k) || [])[1] || k, weg: { staaten: ohne(a.staaten, k) } });
  return m;
}

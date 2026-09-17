// Sagt die Oberflaeche, WELCHE Filter gesetzt sind — oder nur, wie viele?
//
// WARUM ES DIESE PRUEFUNG GIBT. Bis zum 2026-09-17 stand neben „Filter" eine Zahl und
// sonst nichts. Beobachtet in einer Vorfuehrung: „zudem sehe ich meine aktiven
// Filtereinstellungen nicht." Wer das Filterfeld zuklappt, weiss danach nicht mehr, was
// die Liste beschneidet — und bei einer kuerzeren Liste als erwartet ist genau das die
// erste Frage.
//
// ⚠ JEDE FILTERART EINZELN, NIE IN SUMME. Eine Summenpruefung („so viele Marken wie
// advCount") bleibt gruen, wenn zwei Zweige sich gegenseitig ausgleichen: eine Art
// verschwindet, eine andere erscheint doppelt. Der Zustand, den diese Pruefung verhindern
// soll, ist genau der: die Liste ist beschnitten UND keine Marke sagt es. Das waere
// schlimmer als vorher, weil dann nicht einmal mehr die Zahl stimmt.
//
// ⚠ SIE FAEHRT DIE ECHTE FUNKTION aus `lib/filterMarken.js`, nicht eine Abschrift.
// Deshalb liegt jene Datei in Plain JS.
import { readFileSync } from "node:fs";

const quelle = readFileSync(new URL("../lib/filterMarken.js", import.meta.url), "utf8")
  // Der einzige Import ist `@/lib/staaten` — ein TS-Pfadalias, den `node` nicht aufloest.
  // Er wird unten als Wert hereingereicht.
  .replace(/^import \{ STAATEN \} from .*$/m, "")
  .replace(/^export /gm, "");

const STAATEN = [["DE", "Deutschland"], ["AT", "Österreich"], ["CH", "Schweiz"]];
const tk = (k, v) => String(k).replace(/\{(\w+)\}/g, (_, n) => (v && v[n] != null ? v[n] : ""));
const { filterMarken } = new Function("STAATEN", `${quelle}\nreturn { filterMarken };`)(STAATEN);

const LEER = {
  phases: [], horizon: null, cpvFields: [], regionAxis: "perf", regions: [], nationwide: false,
  buyer: "", leistung: [], art: [], rahmen: [], valMin: null, valMax: null,
  neu: "all", wenigWettbewerb: false, aufwand: [], buergschaft: "all", chance: [],
  relevanz: [], multiLot: false, hasDetail: false, unterlagen: false, ausgewertet: false,
  staaten: [],
};
const SEG = [{ cpv4: "4522", label: "Hochbau" }];

/* Jede Filterart mit EINEM gesetzten Wert. Die Liste ist die Pflicht: sie muss jede Art
   abdecken, die `advCount` zaehlt. Zweiter Wert nur dort, wo Mehrfachauswahl moeglich ist
   — daran zeigt sich, ob eine Marke wirklich nur IHREN Wert zuruecknimmt. */
const FAELLE = [
  ["phases",          { phases: ["f02", "award"] },      2],
  ["horizon",         { horizon: 3 },                    1],
  ["cpvFields",       { cpvFields: ["4522"] },           1],
  ["regions",         { regions: ["DEA", "DE2"] },       2],
  ["nationwide",      { nationwide: true },              1],
  ["buyer",           { buyer: "Stadt Hamm" },           1],
  ["leistung",        { leistung: ["bau"] },             1],
  ["art",             { art: ["rahmen"] },               1],
  ["rahmen",          { rahmen: ["vob"] },               1],
  ["valMin",          { valMin: 2e6 },                   1],
  ["valMax",          { valMax: 1e7 },                   1],
  ["neu",             { neu: "folge" },                  1],
  ["wenigWettbewerb", { wenigWettbewerb: true },         1],
  ["aufwand",         { aufwand: ["niedrig"] },          1],
  ["buergschaft",     { buergschaft: "ja" },             1],
  ["chance",          { chance: ["hoch"] },              1],
  ["relevanz",        { relevanz: ["hoch"] },            1],
  ["multiLot",        { multiLot: true },                1],
  ["hasDetail",       { hasDetail: true },               1],
  ["unterlagen",      { unterlagen: true },              1],
  ["ausgewertet",     { ausgewertet: true },             1],
  ["staaten",         { staaten: ["AT"] },               1],
];

let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

/* ── 1. Deckt die Fallliste alles ab, was `advCount` zaehlt? ──────────────────────── */
// Ohne diese Pruefung waere die Fallliste selbst die Luecke: eine neue Filterart kaeme
// dazu, niemand traegt sie hier ein, und der Waechter bliebe gruen.
const panel = readFileSync(new URL("../components/explorer/FilterPanel.tsx", import.meta.url), "utf8");
const zaehlBlock = panel.slice(panel.indexOf("export function advCount"),
                              panel.indexOf("export type Segment"));
const gezaehlt = new Set([...zaehlBlock.matchAll(/\ba\.(\w+)/g)].map((m) => m[1]));
const geprueft = new Set(FAELLE.map(([n]) => n));
for (const art of gezaehlt) {
  if (!geprueft.has(art)) klage(`\`advCount\` zaehlt \`${art}\`, diese Pruefung kennt die Art nicht. `
                              + "Eintragen — sonst filtert sie stumm.");
}

/* ── 2. Jede Art erzeugt Marken, und jede Marke nimmt genau ihre Einstellung zurueck ─ */
for (const [name, patch, erwartet] of FAELLE) {
  const a = { ...LEER, ...patch };
  const marken = filterMarken(a, SEG, tk);
  if (marken.length !== erwartet) {
    klage(`\`${name}\`: ${marken.length} Marke(n) statt ${erwartet}. `
        + "Eine gesetzte Einstellung ohne Marke beschneidet die Liste unsichtbar.");
    continue;
  }
  for (const mk of marken) {
    if (!mk.text || !String(mk.text).trim()) {
      klage(`\`${name}\`: Marke ohne Beschriftung (Schluessel ${mk.schluessel}).`);
    }
    // Die Ruecknahme muss GENAU diese Marke entfernen — nicht mehr, nicht weniger.
    const danach = filterMarken({ ...a, ...mk.weg }, SEG, tk);
    if (danach.length !== marken.length - 1) {
      klage(`\`${name}\`: Ruecknahme von \`${mk.schluessel}\` laesst ${danach.length} Marken `
          + `statt ${marken.length - 1}. Sie nimmt zu viel oder zu wenig zurueck.`);
    }
    if (danach.some((d) => d.schluessel === mk.schluessel)) {
      klage(`\`${name}\`: \`${mk.schluessel}\` ueberlebt die eigene Ruecknahme.`);
    }
  }
}

/* ── 3. Ohne Filter keine Marken ──────────────────────────────────────────────────── */
// Sonst stuende dauerhaft eine Leiste ueber der Liste, die nichts aussagt.
const leer = filterMarken({ ...LEER }, SEG, tk);
if (leer.length) klage(`Leerer Filterzustand erzeugt ${leer.length} Marke(n).`);

/* ── 4. Die Wertgrenzen stehen EINZELN ────────────────────────────────────────────── */
// Am 2026-09-17 stellte ein Nutzer „2 bis 10 Mio" ein und meinte „bis 10 Mio". Dass daraus
// auch eine Untergrenze wurde, verbarg 91,9 % der Bau-Leads. Eine zusammengezogene Spanne
// verschweigt genau das wieder.
const spanne = filterMarken({ ...LEER, valMin: 2e6, valMax: 1e7 }, SEG, tk);
if (spanne.length !== 2) {
  klage(`Wertspanne erzeugt ${spanne.length} Marke(n) statt 2 — Unter- und Obergrenze `
      + "muessen getrennt sichtbar und getrennt aufhebbar sein.");
}

console.log(`  ${FAELLE.length} Filterarten geprueft, `
          + `${gezaehlt.size} von \`advCount\` gezaehlt`);
console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Jede Filterart zeigt und loest ihre Marke");
process.exit(fehler ? 1 : 0);

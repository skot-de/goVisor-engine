/* Sonde: was zeigt die Marktzeile wirklich, je Land und Branche?
 *
 * ⚠ WARUM UNTER NODE UND NICHT ALS UNIT-TEST. Dieselbe Lehre wie bei `netzMatch` und der
 * Passwortregel: eine Abschrift der Rechnung geht gruen, waehrend die benutzte Fassung
 * falsch ist. Diese Sonde liest die ECHTE `data/strategie.json` und rechnet mit denselben
 * Schwellen wie `StrategieView` — sie ist dazu da, VOR dem Deployment zu sehen, wo die
 * Zeile schweigt und wo sie etwas Sinnloses sagen wuerde.
 *
 *     node web/scripts/pruefe-marktwert.mjs
 */
import { readFileSync } from "node:fs";

const MIND_STELLEN = 10;
const MIND_FAELLE = 8;

function marktLage(werte) {
  const v = werte.filter((x) => x != null && Number.isFinite(x)).sort((a, b) => a - b);
  if (v.length < MIND_STELLEN) return null;
  const bei = (p) => v[Math.min(v.length - 1, Math.floor(v.length * p))];
  return { med: bei(0.5), unten: bei(0.25), oben: bei(0.75), n: v.length,
           gleich: v[0] === v[v.length - 1] };
}
const ausQuote = (feld) => (s) => {
  const q = s[feld];
  return q && q.n >= MIND_FAELLE ? q.pct : null;
};

const pfad = new URL("../data/strategie.json", import.meta.url);
const daten = JSON.parse(readFileSync(pfad, "utf8"));
const FELDER = [
  ["Vergaben pro Jahr", (s) => s.vergabenJahr],
  ["Neue Anbieter", ausQuote("neuAnteil")],
  ["Ø Bieter je Vergabe", (s) => s.bieterMedian],
  ["Zuschläge an KMU", ausQuote("kmu")],
  ["Nur über den Preis", ausQuote("preis")],
  ["Wechsel bei Nachfolge", ausQuote("wechsel")],
];

let stumm = 0, ohneStreuung = 0, gesamt = 0;
for (const land of Object.keys(daten)) {
  console.log(`\n══ ${land} ══`);
  for (const [branche, s] of Object.entries(daten[land])) {
    const stellen = s.stellen || [];
    if (!stellen.length) continue;
    const teile = [];
    for (const [name, pick] of FELDER) {
      gesamt++;
      const l = marktLage(stellen.map(pick));
      if (!l) { stumm++; teile.push(`${name}: —`); continue; }
      if (l.gleich) { ohneStreuung++; teile.push(`${name}: ${l.med} (alle gleich)`); continue; }
      teile.push(`${name}: ${l.med}`);
    }
    console.log(`  ${branche.padEnd(11)} ${teile.join(" · ")}`);
  }
}
console.log(`\n  ${gesamt} Kacheln geprüft · ${stumm} ohne Marktwert (zu wenige Stellen)`
          + ` · ${ohneStreuung} ohne Streuung (Kennzahl unterscheidet dort nichts)`);

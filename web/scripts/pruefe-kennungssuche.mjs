/* Sonde: findet die Suche einen Vorgang, dessen Nummer man in der Hand haelt?
 *
 * ⚠ SIE SCHNEIDET DIE ECHTEN FUNKTIONEN AUS `lib/explorerCore.js` heraus und fuehrt sie gegen
 * die ECHTEN Lead-Dateien aus. Eine Abschrift der Regel ginge gruen, waehrend die benutzte
 * Fassung eine Vergabenummer weiter als Postleitzahl liest.
 *
 *     node web/scripts/pruefe-kennungssuche.mjs
 */
import { readFileSync, readdirSync } from "node:fs";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
function schnitt(name, art = "function") {
  const marke = art === "const" ? `const ${name} =` : `function ${name}(`;
  const a = core.indexOf(marke);
  if (a < 0) throw new Error(`${name} fehlt in explorerCore.js`);
  const b = art === "const" ? core.indexOf("\n", a) + 1 : core.indexOf("\n}", a) + 3;
  return core.slice(a, b);
}

// Nur die Stuecke, die die Kennungssuche braucht; alles andere wird gestubbt.
const quelle = [schnitt("_kennNorm", "const"), schnitt("kennungIndex"), schnitt("classifyQuery")].join("\n");
const daten = new URL("../data/", import.meta.url);
const LEADS = [];
for (const f of readdirSync(daten).filter((x) => /^leads-.*\.json$/.test(x))) {
  const roh = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
  for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) LEADS.push(l);
}
const ORTE = {}, PLZ = { "1": "DE3", "2": "DE9", "4": "DEA", "8": "DE2" }, PLZ_GEO = {};
const plzLookup = () => null;
const tk = (k, v) => String(k).replace(/\{(\w+)\}/g, (_, n) => (v && v[n] != null ? v[n] : ""));
let _kennIndex = null;
const classify = new Function(
  "LEADS", "ORTE", "PLZ", "PLZ_GEO", "plzLookup", "tk",
  `let _kennIndex = null;\n${quelle}\nreturn {classifyQuery, kennungIndex, _kennNorm};`
)(LEADS, ORTE, PLZ, PLZ_GEO, plzLookup, tk);

const idx = classify.kennungIndex();
console.log(`  ${LEADS.length.toLocaleString("de")} Leads · ${idx.size.toLocaleString("de")} Kennungen im Index`);

// 1) Jede BRAUCHBARE Vergabenummer muss ihren Lead finden.
// ⚠ Zu kurze werden bewusst nicht indiziert: „GST" und „_ELT" schrumpfen normalisiert auf drei
// Zeichen und traefen bei jeder zweiten Eingabe zufaellig. Sie sind keine Kennung, sondern eine
// Abteilungsabkuerzung, die im Feld gelandet ist. Die Sonde zaehlt sie, statt sie zu fordern.
let treffer = 0, zuKurz = 0;
const fehl = [];
for (const l of LEADS) {
  if (!l.vergabenr) continue;
  if (classify._kennNorm(l.vergabenr).length < 4) { zuKurz++; continue; }
  const r = classify.classifyQuery(l.vergabenr);
  if (r && r.type === "kennung") treffer++;
  else if (fehl.length < 5) fehl.push(`${l.vergabenr} → ${r ? r.type : "nichts"}`);
}
if (fehl.length) throw new Error("Vergabenummern ohne Treffer: " + fehl.join(" · "));
console.log(`  ${treffer.toLocaleString("de")} Vergabenummern gefunden, 0 verfehlt`);
console.log(`  ${zuKurz.toLocaleString("de")} zu kurz zum Indizieren (unter 4 Zeichen)`);

// 2) ⚠ Der Kollisionsfall: eine rein numerische Vergabenummer darf NICHT als PLZ gelesen werden.
const numerisch = LEADS.filter((l) => /^\d{4,5}$/.test(String(l.vergabenr || "")));
for (const l of numerisch.slice(0, 20)) {
  const r = classify.classifyQuery(l.vergabenr);
  if (!r || r.type !== "kennung") throw new Error(`${l.vergabenr} wurde als ${r && r.type} gelesen, nicht als Kennung`);
}
console.log(`  ${numerisch.length} rein numerische Vergabenummern schlagen die PLZ-Regel`);

// 3) Eine unbekannte Zahl bleibt eine PLZ.
const frei = classify.classifyQuery("89999");
if (!frei || frei.type !== "ort") throw new Error(`unbekannte Zahl wurde ${frei && frei.type}, erwartet ort`);
console.log("  unbekannte Zahl bleibt Ortssuche ✓");

// 4) Zu kurze Eingaben treffen nicht zufaellig.
for (const kurz of ["1", "ab", "12"]) {
  const r = classify.classifyQuery(kurz);
  if (r && r.type === "kennung") throw new Error(`„${kurz}" traf eine Kennung`);
}
console.log("  kurze Eingaben treffen keine Kennung ✓");

// 5) Schreibweisen: Trenner duerfen abweichen.
const mitTrenner = LEADS.find((l) => /[-/ ]/.test(String(l.vergabenr || "")));
if (mitTrenner) {
  const ohne = mitTrenner.vergabenr.replace(/[^A-Za-z0-9]/g, "");
  const r = classify.classifyQuery(ohne);
  if (!r || r.type !== "kennung") throw new Error(`„${ohne}" ohne Trenner nicht gefunden`);
  console.log(`  Schreibweise egal: „${mitTrenner.vergabenr}" = „${ohne}" ✓`);
}

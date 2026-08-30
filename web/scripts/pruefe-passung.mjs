/* Prueft die Passungszahl gegen die Relevanz-Stufe.
 *     node web/scripts/pruefe-passung.mjs
 *
 * Die Zahl und die Stufe stammen aus DERSELBEN Groesse `s` in profileEngine.js. Genau darin
 * liegt die Gefahr: verschiebt jemand eine Schwelle (4,5 / 3) oder die Spanne (S_MIN/S_MAX)
 * nur an einer Stelle, zeigt die Oberflaeche „niedrig · 86" oder „hoch · 12" — eine Zahl,
 * die ihrem eigenen Wort widerspricht. Das faellt niemandem im Betrieb auf, weil beide
 * Angaben fuer sich plausibel aussehen.
 *
 * Darum prueft dieses Skript den ECHTEN Code (profileEngine.js ist importfrei, also direkt
 * unter node ladbar) und nicht eine nachgebaute Regel: geprueft wird das VERHALTEN ueber
 * alle erreichbaren Kombinationen, nicht der Wortlaut der Quelle. */

import { emptyProfile, matchLead, passungsZahl } from "../lib/profileEngine.js";

let fehler = 0;
const nicht = (bedingung, text) => { if (!bedingung) { console.error("  ✗ " + text); fehler++; } };

// Die skalierten Bandgrenzen. Sie stehen hier als ZAHL und nicht als Import, damit eine
// Aenderung an S_MIN/S_MAX oder an den Schwellen hier auffaellt statt stillschweigend
// mitzuwandern. Wer sie bewusst verschiebt, muss diese Zeile mit anfassen.
const HOCH_AB = 71, MITTEL_AB = 29;

const profil = () => Object.assign(emptyProfile(), {
  cpvFields: ["4531"], cpvFields6: ["453112"], nachbarFields: ["4521"],
  regions: ["DE1"], volMin: 10_000, volMax: 1_000_000,
});

// Alle erreichbaren Kombinationen aus Feld x Region x Volumen x Zielrichtung.
const FELDER = { treffer: "453112", nachbar: "452100", aussen: "999999" };
const REGIONEN = { drin: "DE123", draussen: "DE999" };
const WERTE = { passt: 100_000, klein: 1_000, gross: 9_000_000, unbekannt: null };

let geprueft = 0;
const gesehen = new Set();

for (const [fn, cpv] of Object.entries(FELDER))
for (const [rn, nuts] of Object.entries(REGIONEN))
for (const [wn, wert] of Object.entries(WERTE))
for (const ziel of ["ausgewogen", "bestand", "expandieren"]) {
  const p = profil(); p.zielrichtung = ziel;
  const m = matchLead({ cpv, nuts }, p, wert);
  const fall = `Feld=${fn} Region=${rn} Wert=${wn} Ziel=${ziel} → ${m.relevanz} · ${m.passung}`;
  geprueft++;
  gesehen.add(m.passung);

  nicht(typeof m.passung === "number", `keine Zahl geliefert: ${fall}`);
  nicht(m.passung >= 0 && m.passung <= 100, `Zahl ausserhalb 0..100: ${fall}`);

  // DIE Kernaussage: Wort und Zahl duerfen sich nie widersprechen.
  if (m.relevanz === "hoch")    nicht(m.passung >= HOCH_AB,   `„hoch" mit Zahl unter ${HOCH_AB}: ${fall}`);
  if (m.relevanz === "mittel")  nicht(m.passung >= MITTEL_AB && m.passung < HOCH_AB, `„mittel" ausserhalb ${MITTEL_AB}..${HOCH_AB - 1}: ${fall}`);
  if (m.relevanz === "niedrig") nicht(m.passung < MITTEL_AB,  `„niedrig" mit Zahl ab ${MITTEL_AB}: ${fall}`);
}

// Der Hoechstwert ist nur mit eigenem Zuschlag im Feld erreichbar (Zielrichtung „bestand"
// belohnt Bekanntes, #27 §6.2). Ohne diesen Fall wuerde die Obergrenze nie geprueft.
const pBest = profil();
pBest.zielrichtung = "bestand";
pBest.cpvWins = { "4531": 3 };
const best = matchLead({ cpv: "453112", nuts: "DE123" }, pBest, 100_000);
gesehen.add(best.passung);
nicht(best.passung === 100, "bester Fall (Feld+Region+Wert+eigener Zuschlag) muesste 100 sein, ist " + best.passung);
nicht(best.relevanz === "hoch", `bester Fall muesste "hoch" sein, ist ${best.relevanz}`);

// Ohne Profil ist die Passung NICHT bestimmbar. `null` und nicht 0 — „wir wissen es nicht"
// ist etwas anderes als „passt nicht", und 0 wuerde den Lead faelschlich nach unten sortieren.
const ohne = matchLead({ cpv: "453112", nuts: "DE123" }, emptyProfile(), 100_000);
nicht(ohne.relevanz === "na", `ohne Profil muesste die Stufe "na" sein, nicht ${ohne.relevanz}`);
nicht(ohne.passung === null, "ohne Profil muesste die Zahl null sein, nicht " + ohne.passung);

// Bewusste Abwahl (#27 §6.3) gehoert ans untere Ende, nicht in die Mitte.
const pAus = profil();
pAus.exclusions = { cpv_aus: ["4531"], regionen_aus: [], wert_min: null, wert_max: null };
const aus = matchLead({ cpv: "453112", nuts: "DE123" }, pAus, 100_000);
nicht(aus.passung === 0, "abgewaehlte Leistungsart muesste 0 ergeben, nicht " + aus.passung);

// Die Skala ist grob, und das soll sie bleiben: `s` springt in Halbschritten. Taucht hier
// ein krummer Zwischenwert auf, hat jemand die Gewichte verfeinert, ohne die Darstellung
// anzupassen — dann behauptet „/100" eine Genauigkeit, die es nicht gibt.
const ERLAUBT = new Set([0, 14, 29, 43, 57, 71, 86, 100]);
for (const v of gesehen) nicht(ERLAUBT.has(v), `unerwarteter Zwischenwert ${v} — Skala verfeinert?`);

// Die Umrechnung selbst: Raender und Monotonie.
nicht(passungsZahl(2) === 0, "s=2 muesste 0 ergeben");
nicht(passungsZahl(5.5) === 100, "s=5,5 muesste 100 ergeben");
nicht(passungsZahl(4.5) === HOCH_AB, `s=4,5 (Grenze „hoch") muesste ${HOCH_AB} ergeben`);
nicht(passungsZahl(3) === MITTEL_AB, `s=3 (Grenze „mittel") muesste ${MITTEL_AB} ergeben`);
nicht(passungsZahl(-99) === 0 && passungsZahl(99) === 100, "Umrechnung muesste kappen");
for (let s = 2; s < 5.5; s += 0.5) nicht(passungsZahl(s) <= passungsZahl(s + 0.5), `nicht monoton bei s=${s}`);

console.log(`Passungszahl: ${geprueft} Kombinationen geprueft, ${gesehen.size} verschiedene Werte (${[...gesehen].sort((a,b)=>a-b).join(", ")}).`);
if (fehler) { console.error(`\n${fehler} Abweichung(en).`); process.exit(1); }
console.log("Wort und Zahl stimmen ueberein.");

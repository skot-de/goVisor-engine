// Faellt die Paywall im Zweifel ZU, und sind die zwei bezahlten Stufen getrennt?
//
// WARUM ES DIESE PRUEFUNG GIBT. `lib/tier.ts` entscheidet, ob echte Premium-Werte den Server
// verlassen. Sie hat diese Entscheidung zweimal verloren:
//
//   1. Bis 2026-08-22 stand dort `select("tier")` auf eine Spalte, die es in keiner Migration
//      gab. Solange PAYWALL_ENFORCED aus war, fiel das niemandem auf — am Tag der
//      Scharfschaltung haette der catch daraus lautlos „free" gemacht und JEDER Zahlende waere
//      auf den Free-Umfang gefallen.
//   2. Bis 2026-10-01 kannte `Tier` nur `free|pro`: EINE Schwelle fuer ZWEI bezahlte Stufen.
//      `redact.ts` prueffte viermal `if (tier === "pro") return map`. Wer Analyse fuer 99 €
//      kaufte, bekam Strategie fuer 349 € mit, obwohl §3.6 den ganzen Strategie-Bereich auf
//      `++` legt. 250 € je Kunde und Monat, unsichtbar — weil kein Test die Stufen
//      unterscheiden KONNTE.
//
// ⚠ SIE RUFT DIE ECHTEN FUNKTIONEN AUF, nicht Nachbildungen, und tastet NICHT den Quelltext
// ab. Ein Wortwaechter waere hier besonders wertlos: `tier.ts` ERWAEHNT die alten Zustaende
// (`user_profiles.plan`, `=== "pro"`) in seinen Kommentaren, eine Regex darauf schlaegt also an
// der Begruendung an statt am Code (Lehre „Waechter messen Prosa statt Code").

import { stufeZuTier, darfAnalyse, darfStrategie } from "../lib/stufeZuTier.js";

const JETZT = Date.parse("2026-10-01T12:00:00Z");
const SPAETER = "2026-11-01T00:00:00Z";
const FRUEHER = "2026-09-01T00:00:00Z";

// [Bezeichnung, org, erwartete Stufe]
const FAELLE = [
  ["Analyse aktiv",                    { tier: "analyse",   abo_status: "aktiv" }, "analyse"],
  ["Strategie aktiv",                  { tier: "strategie", abo_status: "aktiv" }, "strategie"],
  ["Free",                             { tier: "free",      abo_status: "aktiv" }, "free"],
  // §3a: vier Wochen „alle Funktionen BEIDER Stufen" → strategie, nicht analyse
  ["Testphase laeuft noch",            { tier: "trial", trial_ends_at: SPAETER },  "strategie"],
  ["Testphase abgelaufen",             { tier: "trial", trial_ends_at: FRUEHER },  "free"],
  ["Testphase ohne Datum",             { tier: "trial" },                          "free"],
  // ⚠ Gekuendigt BEHAELT die Stufe bis plan_until — faellt nicht auf die mittlere.
  ["gekuendigt Strategie, laeuft noch", { tier: "strategie", abo_status: "gekuendigt", plan_until: SPAETER }, "strategie"],
  ["gekuendigt Analyse, laeuft noch",  { tier: "analyse",   abo_status: "gekuendigt", plan_until: SPAETER }, "analyse"],
  ["gekuendigt, Zeitraum vorbei",      { tier: "analyse",   abo_status: "gekuendigt", plan_until: FRUEHER }, "free"],
  ["gekuendigt ohne Datum",            { tier: "analyse",   abo_status: "gekuendigt" }, "free"],
  // ── fail-closed: alles Unbekannte, Fehlende, Kaputte ──
  ["unbekannte Stufe",                 { tier: "enterprise", abo_status: "aktiv" }, "free"],
  ["Stufe fehlt",                      { abo_status: "aktiv" },                    "free"],
  ["leeres Objekt",                    {},                                        "free"],
  ["null",                             null,                                      "free"],
  ["undefined",                        undefined,                                 "free"],
  ["kein Objekt",                      "analyse",                                 "free"],
  ["Datum unlesbar",                   { tier: "trial", trial_ends_at: "morgen" }, "free"],
  ["alter Wert 'paid' zaehlt NICHT",   { tier: "paid",  abo_status: "aktiv" },     "free"],
  ["alter Wert 'pro' zaehlt NICHT",    { tier: "pro",   abo_status: "aktiv" },     "free"],
];

// [Stufe, darfAnalyse, darfStrategie] — die Tabelle, um die es geht
const RECHTE = [
  ["free",      false, false],
  ["analyse",   true,  false],   // ⛔ die eine Zeile, die vorher falsch war
  ["strategie", true,  true],
  ["pro",       false, false],   // alter Wert ist keine Stufe mehr
  [undefined,   false, false],
  [null,        false, false],
];

/** Den Fallsatz gegen EINE Abbildung fahren. Rueckgabe: Liste der Abweichungen. */
function durchlauf(abbildung) {
  const raus = [];
  for (const [name, org, soll] of FAELLE) {
    let ist;
    try { ist = abbildung(org, JETZT); }
    catch (e) { ist = `WURF: ${e instanceof Error ? e.message : e}`; }
    if (ist !== soll) raus.push(`${name}: erwartet ${soll}, bekommen ${ist}`);
  }
  return raus;
}

/** Die Rechtetabelle gegen EIN Praedikatpaar fahren. */
function rechte(fAnalyse, fStrategie) {
  const raus = [];
  for (const [stufe, sollA, sollS] of RECHTE) {
    if (fAnalyse(stufe) !== sollA)
      raus.push(`darfAnalyse(${stufe}): erwartet ${sollA}, bekommen ${fAnalyse(stufe)}`);
    if (fStrategie(stufe) !== sollS)
      raus.push(`darfStrategie(${stufe}): erwartet ${sollS}, bekommen ${fStrategie(stufe)}`);
  }
  return raus;
}

let fehler = 0;
for (const a of durchlauf(stufeZuTier)) { console.error(`  ✗ ${a}`); fehler++; }
for (const a of rechte(darfAnalyse, darfStrategie)) { console.error(`  ✗ ${a}`); fehler++; }

// ⚠ SELBSTPROBE 1 — eine zu durchlaessige STUFENABBILDUNG muss auffallen.
const ZU_DURCHLAESSIG = (org) =>
  (org && typeof org === "object" && org.tier !== "free" ? "strategie" : "free");
const g1 = durchlauf(ZU_DURCHLAESSIG);
if (g1.length === 0) {
  console.error("  ✗ SELBSTPROBE 1: der Fallsatz findet eine offene Paywall NICHT");
  fehler++;
}

// ⚠ SELBSTPROBE 2 — GENAU DER BEFUND VOM 2026-10-01 muss auffallen: ein `darfStrategie`,
// das auch Analyse durchlaesst. Das war der Zustand, der 250 € je Kunde verschenkte.
const g2 = rechte(darfAnalyse, (t) => t === "analyse" || t === "strategie");
if (g2.length === 0) {
  console.error("  ✗ SELBSTPROBE 2: die Rechtetabelle wuerde die Verwechslung von Analyse "
              + "und Strategie NICHT finden — genau den Befund, fuer den sie gebaut wurde");
  fehler++;
}

console.log(`  ${FAELLE.length} Stufenfaelle, davon ${FAELLE.filter(f => f[2] === "free").length} fail-closed`);
console.log(`  ${RECHTE.length * 2} Rechtepruefungen (darfAnalyse/darfStrategie)`);
console.log(`  Selbstproben: offene Paywall faellt an ${g1.length} Faellen auf, `
          + `Analyse-statt-Strategie an ${g2.length}`);
console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Stufen getrennt, faellt im Zweifel zu");
process.exit(fehler ? 1 : 0);

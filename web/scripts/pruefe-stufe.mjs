// Faellt die Paywall im Zweifel ZU? — Abbildung der vier Stufen auf free|pro.
//
// WARUM ES DIESE PRUEFUNG GIBT. `lib/tier.ts` entscheidet, ob echte Premium-Werte den Server
// verlassen. Sie hat diese Entscheidung schon einmal verloren: bis 2026-08-22 stand dort
// `select("tier")` auf eine Spalte, die es in keiner Migration gab. Solange PAYWALL_ENFORCED
// aus war, fiel das niemandem auf — am Tag der Scharfschaltung haette der catch daraus
// lautlos „free" gemacht und JEDER Zahlende waere auf den Free-Umfang gefallen.
//
// Am 2026-10-01 ist die Quelle von `user_profiles.plan` auf `organizations.tier` gewandert
// (Preismodell v1.9 §2, Migration 0028). Derselbe Fehler kann damit erneut passieren, nur mit
// einer anderen Spalte. Diese Pruefung haelt die Abbildung fest.
//
// ⚠ SIE RUFT DIE ECHTE FUNKTION AUF, nicht eine Nachbildung, und tastet NICHT den Quelltext
// ab. Ein Wortwaechter waere hier besonders wertlos: `tier.ts` ERWAEHNT `user_profiles.plan`
// in seinen Kommentaren, eine Regex darauf schlaegt also an der Begruendung an statt am Code
// (Lehre „Waechter messen Prosa statt Code"). Genau deshalb liegt die Logik in
// `lib/stufeZuTier.js` als reines JS — nach dem Muster von `filterMarken.js`.

import { stufeZuTier } from "../lib/stufeZuTier.js";

const JETZT = Date.parse("2026-10-01T12:00:00Z");
const SPAETER = "2026-11-01T00:00:00Z";
const FRUEHER = "2026-09-01T00:00:00Z";

const FAELLE = [
  // [Bezeichnung, org, erwartet]
  ["Analyse aktiv",                      { tier: "analyse",   abo_status: "aktiv" }, "pro"],
  ["Strategie aktiv",                    { tier: "strategie", abo_status: "aktiv" }, "pro"],
  ["Free",                               { tier: "free",      abo_status: "aktiv" }, "free"],
  ["Testphase laeuft noch",              { tier: "trial", trial_ends_at: SPAETER },  "pro"],
  ["Testphase abgelaufen",               { tier: "trial", trial_ends_at: FRUEHER },  "free"],
  ["Testphase ohne Datum",               { tier: "trial" },                          "free"],
  ["gekuendigt, Zeitraum laeuft noch",   { tier: "analyse", abo_status: "gekuendigt", plan_until: SPAETER }, "pro"],
  ["gekuendigt, Zeitraum vorbei",        { tier: "analyse", abo_status: "gekuendigt", plan_until: FRUEHER }, "free"],
  ["gekuendigt ohne Datum",              { tier: "analyse", abo_status: "gekuendigt" }, "free"],
  // ── fail-closed: alles Unbekannte, Fehlende, Kaputte ──
  ["unbekannte Stufe",                   { tier: "enterprise", abo_status: "aktiv" }, "free"],
  ["Stufe fehlt",                        { abo_status: "aktiv" },                    "free"],
  ["leeres Objekt",                      {},                                        "free"],
  ["null",                               null,                                      "free"],
  ["undefined",                          undefined,                                 "free"],
  ["kein Objekt",                        "analyse",                                 "free"],
  ["Datum unlesbar",                     { tier: "trial", trial_ends_at: "morgen" }, "free"],
  ["alter Wert 'paid' zaehlt NICHT mehr",{ tier: "paid", abo_status: "aktiv" },      "free"],
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

let fehler = 0;
for (const abweichung of durchlauf(stufeZuTier)) {
  console.error(`  ✗ ${abweichung}`);
  fehler++;
}

// ⚠ SELBSTPROBE — SIE MUSS DEN FUND ERZWINGEN, nicht nur moeglich machen. Ein Waechter, der
// nie anschlagen KANN, ist Zierde. Geprueft wird deshalb der DURCHLAUF selbst: eine bewusst
// zu durchlaessige Abbildung (alles ausser 'free' gilt als zahlend — die naheliegendste
// Fehlimplementierung, und genau die, die eine Paywall oeffnet) muss Abweichungen liefern.
// Liefert sie keine, taugt der Fallsatz nicht und das Gruen oben bedeutet nichts.
const ZU_DURCHLAESSIG = (org) => (org && typeof org === "object" && org.tier !== "free" ? "pro" : "free");
const gefunden = durchlauf(ZU_DURCHLAESSIG);
if (gefunden.length === 0) {
  console.error("  ✗ SELBSTPROBE: der Fallsatz findet eine offene Paywall NICHT — er prueft nichts");
  fehler++;
}

console.log(`  ${FAELLE.length} Faelle geprueft, davon ${FAELLE.filter(f => f[2] === "free").length} fail-closed`);
console.log(`  Selbstprobe: eine zu durchlaessige Abbildung faellt an ${gefunden.length} Faellen auf`);
console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Stufenabbildung faellt im Zweifel zu");
process.exit(fehler ? 1 : 0);

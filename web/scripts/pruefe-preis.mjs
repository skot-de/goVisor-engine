// Stimmt der Erweiterungspreis mit §5.2 des Preismodells, und bleibt es EINE Position?
//
// WARUM ES DIESE PRUEFUNG GIBT. `lib/preise.ts` stand bis zum 2026-10-01 auf `0` mit der
// Begruendung „das Kostenmodell ist offen (Sven, 2026-09-30)". v1.9 traegt genau dieses Datum
// und legt 29 €/Mon · 299 €/Jahr fest — die Datei wurde geschrieben, bevor die Entscheidung im
// Dokument stand, und niemand hat sie nachgezogen. Die Variablen waren nirgends gesetzt, weder
// in `.env.local` noch dokumentiert, und jeder Kauf scheiterte an einer Meldung, die auf das
// falsche Hindernis zeigte.
//
// Zwei Eigenschaften koennen still zurueckfallen, und beide kosten Geld:
//   1. ZWEI getrennte Preise statt einer Position. Das war die Tafel von v1.7; v1.9 sagt
//      „weiterer Nutzer ODER weiteres Unternehmensprofil", gleicher Preis.
//   2. Ein Jahrespreis, der nicht gerechnet, sondern geraten ist. §13: 10,25 × Monat,
//      aufgerundet auf 9er-Endung.
//
// ⚠ Faehrt die ECHTE Datei (Node 25 kann TypeScript; nur `server-only` wird fuer den Lauf
// entfernt, der Rumpf bleibt unveraendert).

import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const HIER = new URL(".", import.meta.url).pathname;
const QUELLE = resolve(HIER, "../lib/preise.ts");

let fehler = 0;
const klage = (s) => { console.error(`  ✗ ${s}`); fehler++; };

const roh = readFileSync(QUELLE, "utf8");
if (!roh.includes('import "server-only";')) klage("preise.ts sieht anders aus als erwartet");
const verz = await mkdtemp(join(tmpdir(), "preis-"));
await writeFile(join(verz, "preise.ts"), roh.replace('import "server-only";', ""));
const P = await import(join(verz, "preise.ts"));

// ── §5.2: die Tafel ──────────────────────────────────────────────────────────────────────
const MONAT = 2900, JAHR = 29900;
if (P.ERWEITERUNG_CENTS.monat !== MONAT) klage(`Monatspreis ${P.ERWEITERUNG_CENTS.monat}, §5.2 nennt ${MONAT}`);
if (P.ERWEITERUNG_CENTS.jahr !== JAHR) klage(`Jahrespreis ${P.ERWEITERUNG_CENTS.jahr}, §5.2 nennt ${JAHR}`);

// ⛔ EINE POSITION. Nutzer und Profil muessen DENSELBEN Preis haben, in jedem Takt.
for (const takt of ["monat", "jahr"]) {
  if (P.preisCents("seat", takt) !== P.preisCents("profile", takt))
    klage(`seat und profile kosten im Takt ${takt} verschieden — §5.2 verlangt eine Position`);
}

// ⚠ DER JAHRESPREIS IST GERECHNET, NICHT GERATEN. §13: 10,25 × Monat, auf 9er-Endung hoch.
const auf9er = (c) => { const e = Math.ceil(c / 100); return (e % 10 === 9 ? e : e + ((19 - (e % 10)) % 10)) * 100; };
const soll = auf9er(Math.round(P.ERWEITERUNG_CENTS.monat * 10.25));
if (soll !== P.ERWEITERUNG_CENTS.jahr)
  klage(`Jahrespreis ${P.ERWEITERUNG_CENTS.jahr} folgt nicht der Regel 10,25×Monat auf 9er-Endung (${soll})`);

// ── Menge: linear, keine Staffel (§5.2) ─────────────────────────────────────────────────
for (const [menge, erwartet] of [[1, MONAT], [3, 3 * MONAT], [35, 35 * MONAT]]) {
  const ist = P.betragCents("seat", menge);
  if (ist !== erwartet) klage(`betragCents(seat,${menge}) = ${ist}, linear waeren ${erwartet}`);
}
for (const menge of [0, -1, 0.5]) {
  if (P.betragCents("seat", menge) !== 0) klage(`Menge ${menge} ergibt keinen Betrag von 0`);
}

// ── Der Riegel bleibt: 0 darf keinen Kauf erlauben ──────────────────────────────────────
if (!P.preisOk("seat") || !P.preisOk("profile")) klage("preisOk ist falsch, obwohl ein Preis gesetzt ist");

// ⚠ SELBSTPROBE — die zwei Rueckfaelle MUESSEN auffallen.
const getrennt = { monat: { seat: 2900, profile: 3900 } };
if (getrennt.monat.seat === getrennt.monat.profile)
  klage("SELBSTPROBE 1 taugt nicht — der Vergleich kann zwei Preise nicht trennen");
const geraten = auf9er(Math.round(2900 * 10.25));
if (geraten === 30000) klage("SELBSTPROBE 2 taugt nicht — die 9er-Regel liefert eine runde Zahl");

await rm(verz, { recursive: true, force: true });
console.log(`  §5.2: ${(MONAT / 100).toFixed(2)} € / Monat · ${(JAHR / 100).toFixed(2)} € / Jahr, `
          + `eine Position fuer Nutzer und Profil`);
console.log(`  Jahresregel 10,25×Monat auf 9er-Endung: ${(soll / 100).toFixed(2)} € — stimmt mit der Tafel`);
console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Erweiterungspreis trifft §5.2");
process.exit(fehler ? 1 : 0);

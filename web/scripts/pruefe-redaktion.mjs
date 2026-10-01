// Verlassen Premium-Werte den Server auf der falschen Stufe? — `lib/redact.ts`, echt gefahren.
//
// WARUM ES DIESE PRUEFUNG GIBT. `redact.ts` entscheidet, ob echte Analytik-Werte den Server
// verlassen; CSS-Blur allein ist per DevTools lesbar (docs/security-review.md). Gemessen am
// 2026-10-01: fuer diese Datei gab es KEINEN Test. Sie hat zwei Befunde ueberlebt, ohne dass
// etwas anschlug:
//
//   1. Viermal `if (tier === "pro") return …` — EINE Schwelle fuer ZWEI bezahlte Stufen. Wer
//      Analyse fuer 99 € kaufte, bekam Strategie fuer 349 € mit (§3.6 legt den ganzen Bereich
//      auf `++`).
//   2. `redactFirma` schuetzte nur `expiring`, obwohl §3.5 fuenf Dinge dem `++`-Tab
//      „Angriffspunkte" zuordnet. `sits` („Wo festsitzt") und `signale` („Weitere Signale")
//      verliessen den Server fuer JEDE Stufe.
//
// ⚠ SIE FAEHRT DIE ECHTE DATEI, nicht eine Nachbildung. Node 25 kann TypeScript direkt; was
// fehlt, sind nur zwei Importe, die ausserhalb von Next nicht aufloesen (`server-only` und der
// `@/`-Alias). Die werden fuer den Lauf umgeschrieben — DER RUMPF BLEIBT UNVERAENDERT. Eine
// Nachbildung waere wertlos: sie ginge gruen, waehrend die benutzte Fassung falsch ist (genau
// die Lehre aus `filterMarken.js`).

import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const HIER = new URL(".", import.meta.url).pathname;
const QUELLE = resolve(HIER, "../lib/redact.ts");
const STUFEN = resolve(HIER, "../lib/stufeZuTier.js");

let fehler = 0;
const klage = (s) => { console.error(`  ✗ ${s}`); fehler++; };

const roh = readFileSync(QUELLE, "utf8");
// ⚠ Schlaegt der Umschreib fehl, MUSS die Pruefung rot werden — nicht stillschweigend eine
// andere Datei fahren.
if (!roh.includes('import "server-only";') || !roh.includes('from "@/lib/stufeZuTier"')) {
  klage("die Importe von redact.ts sehen anders aus als erwartet — Umschreib geprueft?");
}
const umgeschrieben = roh
  .replace('import "server-only";', "")
  .replace(/from "@\/lib\/tier"/g, 'from "./tier_stub.ts"')
  .replace(/from "@\/lib\/stufeZuTier"/g, `from ${JSON.stringify(STUFEN)}`);

const verz = await mkdtemp(join(tmpdir(), "redakt-"));
await writeFile(join(verz, "tier_stub.ts"), 'export type Tier = "free" | "analyse" | "strategie";\n');
await writeFile(join(verz, "redact.ts"), umgeschrieben);
const R = await import(join(verz, "redact.ts"));

// ── Nutzlasten, den echten Feldern nachgebaut ───────────────────────────────────────────
const firma = () => ({
  name: "Beispiel GmbH",
  kpi: { wins36: 12, aus18_n: 7, aus18_vol: 900000, verteidigung: 61, markt_verteidigung: 48 },
  sits: [{ buyer: "Stadt X", wins: 9 }], n_vergabestellen: 12,
  expiring: [{ titel: "Rahmenvertrag", bis: "2027-03-01" }],
  felder: [{ code: "45", n: 9 }], regionen: [{ code: "DE1", n: 4 }],
  signale: { subcontracting: 5, subcontracting_total: 12, bietergemeinschaften: 3, netzwerk: "aktiv" },
});
const detail = () => ({
  marktSegment: { nAwards: 8883, erfolglos: 12, singleBidder: 7, top3: 61, score: 44,
                  dominatoren: ["A GmbH", "B AG"], chronic: true },
  buyerProfile: { mix: [{ cpv: "45", pct: 62, n: 31 }] },
});
const strategie = () => ({ bau: {
  felder: [{ code: "45", vergabenJahr: 120, trend: 3, bieterMedian: 4, kleinstesLos: 5000, buergschaft: 1 }],
  wettbewerb: { anbieter: [1, 2, 3, 4, 5], matrix: { a: 1 }, profile: { x: [{ buyer: "S", wins: 4, anteil: 2, markt: 1, ueber: 0 }] } },
  faehigkeiten: { a: 1 }, bindung: { b: 2 }, pipeline: { frei: true },
} });
const markt = () => ({ bau: {
  topStellen: [{ name: "Stadt X", vergaben: 44, offen: 3 }],
  einstieg: [{ titel: "Los 1", bieter: 6, wert: 120000 }],
} });

// ── Was auf welcher Stufe sichtbar sein MUSS (§3, nachgelesen) ──────────────────────────
// [Bezeichnung, Funktion, Nutzlast, Pruefung je Stufe]
const FAELLE = [
  ["§3.2 Lead-Detail (+)", R.redactDetail, detail,
   (d) => d.marktSegment.nAwards === 8883 && d.marktSegment.dominatoren.length === 2,
   { free: false, analyse: true, strategie: true }],
  ["§3.2 Markt-Tab (+)", R.redactMarkt, markt,
   (d) => d.bau.topStellen[0].vergaben === 44 && d.bau.einstieg[0].wert === 120000,
   { free: false, analyse: true, strategie: true }],
  ["§3.6 Strategie (++)", R.redactStrategie, strategie,
   (d) => d.bau.wettbewerb.matrix !== null && d.bau.faehigkeiten.a === 1
          && d.bau.felder[0].vergabenJahr === 120,
   { free: false, analyse: false, strategie: true }],
  ["§3.5 Angriffspunkte: Wo festsitzt (++)", R.redactFirma, firma,
   (d) => d.sits.length === 1 && d.n_vergabestellen === 12,
   { free: false, analyse: false, strategie: true }],
  ["§3.5 Angriffspunkte: Was auslaeuft (++)", R.redactFirma, firma,
   (d) => d.expiring.length === 1,
   { free: false, analyse: false, strategie: true }],
  ["§3.5 Angriffspunkte: Weitere Signale (++)", R.redactFirma, firma,
   (d) => d.signale.bietergemeinschaften === 3 && d.signale.netzwerk === "aktiv",
   { free: false, analyse: false, strategie: true }],
  // ⚠ Die Uebersicht MUSS auf jeder Stufe durchkommen — eine Redaktion, die zu viel nimmt,
  // ist genauso ein Fehler wie eine, die zu wenig nimmt.
  ["§3.5 Uebersicht: Kennzahlen bleiben frei", R.redactFirma, firma,
   (d) => d.kpi.wins36 === 12 && d.kpi.verteidigung === 61,
   { free: true, analyse: true, strategie: true }],
  ["§3.5 Uebersicht: aus18-Zaehler ist der Teaser", R.redactFirma, firma,
   (d) => d.kpi.aus18_n === 7,
   { free: true, analyse: true, strategie: true }],
  ["§3.5 Uebersicht: Felder und Regionen frei", R.redactFirma, firma,
   (d) => d.felder.length === 1 && d.regionen.length === 1,
   { free: true, analyse: true, strategie: true }],
];

for (const [name, fn, bau, sichtbar, erwartet] of FAELLE) {
  for (const stufe of ["free", "analyse", "strategie"]) {
    let ist;
    try { ist = sichtbar(fn(bau(), stufe)); }
    catch (e) { ist = `WURF: ${e instanceof Error ? e.message : e}`; }
    if (ist !== erwartet[stufe])
      klage(`${name} / ${stufe}: sichtbar=${ist}, erwartet ${erwartet[stufe]}`);
  }
}

// ⚠ Die Form muss erhalten bleiben, sonst stuerzt die Oberflaeche statt zu teasern:
// FirmaProfil.tsx liest data.signale.bietergemeinschaften und t(data.signale.netzwerk) direkt.
const red = R.redactFirma(firma(), "free");
if (typeof red.signale !== "object" || red.signale === null) klage("signale ist kein Objekt mehr");
if (typeof red.signale?.netzwerk !== "string") klage("signale.netzwerk ist kein String mehr");
if (!Array.isArray(red.sits) || !Array.isArray(red.expiring)) klage("sits/expiring sind keine Listen mehr");

// ⚠ SELBSTPROBE — GENAU DIE ZWEI BEFUNDE muessen auffallen.
const alsPro = (fn) => (d) => fn(d, "strategie");                   // Befund 1: eine Schwelle
const g1 = (() => {
  const d = alsPro(R.redactStrategie)(strategie());
  return d.bau.faehigkeiten.a === 1;      // „analyse sieht ++" waere genau das
})();
if (!g1) klage("SELBSTPROBE 1 kann nicht greifen — strategie sieht die ++-Inhalte nicht");
const nurExpiring = (p) => { const d = structuredClone(p); d.expiring = []; return d; };  // Befund 2
if (nurExpiring(firma()).sits.length !== 1) {
  klage("SELBSTPROBE 2 kann nicht greifen — die alte Fassung haette sits nicht durchgelassen");
}

await rm(verz, { recursive: true, force: true });
console.log(`  ${FAELLE.length} Abschnitte × 3 Stufen = ${FAELLE.length * 3} Pruefungen, echte redact.ts gefahren`);
console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Redaktion trifft die Stufen aus §3");
process.exit(fehler ? 1 : 0);

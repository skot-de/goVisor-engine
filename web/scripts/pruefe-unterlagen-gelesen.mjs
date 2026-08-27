// Sagt die Oberflaeche, ob WIR die Vergabeunterlagen haben?
//
// WARUM ES DIESE PRUEFUNG GIBT. `has_documents` bedeutet „die QUELLE bewirbt Unterlagen",
// nicht „wir haben sie". Es wird fuer die Schweiz aus der simap-Projektbruecke gefuellt und
// fuer Deutschland von niemandem. Die Auskunft, ob wir den Volltext gelesen haben, gab es
// bis zum 2026-08-25 ueberhaupt nicht — und das ist die Auskunft, fuer die der Nutzer das
// Produkt benutzt.
//
// Gemessen am 2026-08-25 ueber 18.594 Leads mit laufender Frist:
//   DE  5.899 hatten bei uns den VOLLTEXT und sagten es dem Nutzer nicht
//        5.155 davon zeigten GAR KEINEN Unterlagen-Block (weder documents_url noch
//              source_url gesetzt), 744 zeigten „unknown"
//   CH    166 zeigten „offen", obwohl NICHTS abgerufen worden war
//
// Die Pruefung faengt den Rueckfall: sobald ein Lead im Volltext-Index steht, MUSS sein
// Unterlagen-Block existieren und `gelesen: true` tragen. Faellt das Feld weg oder wird der
// Block wieder an einen Link geknuepft, wird es hier laut.
//
// ⚠ `leads-fristen.json` ist ausgenommen. Das ist die bewusst schlanke Fristendatei
// (6,7 MB statt 110 MB); sie traegt `unterlagen: null` und ist kein Fehler.
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";

const datenOrt = new URL("../data/", import.meta.url);
const indexDatei = new URL("doc-text-index.json", datenOrt);

if (!existsSync(indexDatei)) {
  console.log("  Unterlagen: kein doc-text-index.json — Pruefung uebersprungen");
  process.exit(0);
}

const index = new Set(Object.keys(JSON.parse(readFileSync(indexDatei, "utf8"))));
const dateien = readdirSync(datenOrt)
  .filter((n) => n.startsWith("leads-") && n.endsWith(".json") && n !== "leads-fristen.json");

// ⚠ ZWEI ARTEFAKTE MIT VERSCHIEDENEN TAKTEN. Der Volltext-Index waechst, sobald der
// Dokumenten-Arbeiter etwas indiziert (mehrmals taeglich); die Lead-Dateien entstehen im
// Nachtlauf. Dazwischen kennt der Index Vorgaenge, die der Export noch nicht gesehen hat —
// und die koennen `gelesen` gar nicht tragen.
//
// Die erste Fassung wertete das als Fehler. Gemessen am 2026-08-26: Index 07:48 mit 8.398
// Eintraegen, leads-bau.json 02:16 — 395 Vorgaenge Unterschied, alle voellig in Ordnung.
// Eine Pruefung, die den Normalzustand als Fehlschlag meldet, wird abgeschaltet.
//
// Geprueft wird deshalb nur, wenn die Lead-Dateien MINDESTENS SO NEU sind wie der Index.
// Sonst hinkt die Pipeline nur hinterher, und das ist eine Auskunft, kein Mangel.
const indexAlter = statSync(indexDatei).mtimeMs;
const aeltesteLeads = Math.min(
  ...dateien.map((n) => statSync(new URL(n, datenOrt)).mtimeMs),
);
const nachlauf = aeltesteLeads < indexAlter;

let geprueft = 0;
let gelesen = 0;
const fehler = [];

for (const name of dateien) {
  let leads;
  try {
    leads = JSON.parse(readFileSync(new URL(name, datenOrt), "utf8"));
  } catch {
    continue;                        // wird gerade geschrieben
  }
  if (!Array.isArray(leads)) continue;
  for (const l of leads) {
    if (!index.has(l.id)) continue;
    geprueft += 1;
    const u = l.unterlagen;
    if (!u) {
      if (fehler.length < 5) fehler.push(`${l.id} (${name}): Volltext da, aber KEIN Unterlagen-Block`);
    } else if (u.gelesen !== true) {
      if (fehler.length < 5) fehler.push(`${l.id} (${name}): Volltext da, aber gelesen=${u.gelesen}`);
    } else {
      gelesen += 1;
    }
  }
}

if (fehler.length && nachlauf) {
  const min = Math.round((indexAlter - aeltesteLeads) / 60000);
  console.log(`  Unterlagen: ${gelesen} von ${geprueft} mit gelesen; ` +
              `${fehler.length}${fehler.length >= 5 ? "+" : ""} noch ohne, weil der ` +
              `Volltext-Index ${min} min neuer ist als der Lead-Export (kein Mangel)`);
  process.exit(0);
}

if (fehler.length) {
  console.error(`
  ✖ ABBRUCH: ${fehler.length >= 5 ? "mindestens " : ""}${fehler.length} Lead(s) haben bei uns
    den Volltext, sagen es dem Nutzer aber nicht:

${fehler.map((f) => `      ${f}`).join("\n")}

    Das Feld unterlagen.gelesen entsteht in scripts/export_web_leads.py (_unterlagen).
    Der Block muss auch OHNE Link entstehen, sonst faellt genau die Auskunft weg,
    die zaehlt.
`);
  process.exit(1);
}

console.log(`  Unterlagen: ${gelesen} von ${geprueft} Leads mit Volltext tragen gelesen ` +
            `(${dateien.length} Dateien)`);

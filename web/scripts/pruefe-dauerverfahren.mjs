// Dauerverfahren zeigen keine Frist — GERECHNET mit dem echten `fristCell`.
//
// ⚠ DER BEFUND. Open-House- und Qualifizierungsverfahren stehen dauerhaft offen; die
// Quellen tragen dafuer ein Platzhalterdatum (01.01.2100 in AT, 31.12.2099 in DE). Die
// Oberflaeche rechnete daraus eine Frist und zeigte noch 26.761 Tage in der Liste und
// in -24307 Mon. im Detail — zwei verschiedene Unsinnszahlen aus derselben Quelle.
// Gemessen am 2026-09-25 bei 390 Vorgaengen. Aufgefallen ist es Sven beim Nachsehen zu
// einem Drahthersteller, nicht einer Pruefung.
//
// ⚠ DIE GEGENRICHTUNG IST DIE WICHTIGERE. Von 2.522 Open-House-Vorgaengen tragen nur
// diese 390 ein Platzhalterdatum; die uebrigen 2.132 haben eine ECHTE Frist und muessen
// ihren Countdown behalten. Eine Regel open_house-zeigt-nie-eine-Frist waere bequem und
// falsch — sie wuerde 2.132 Vorgaengen die Frist nehmen, die sie wirklich haben.
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
let fehler = 0;
const sage = (ok, t) => { if (!ok) fehler++; console.log(`  ${ok ? "✓" : "✗"} ${t}`); };

const i = core.indexOf("function fristCell(l){");
const ende = core.indexOf("\n}", core.indexOf('return `<span class="cd">${val(endetText(l)'));
if (i < 0 || ende < 0) { console.log("  ✗ fristCell nicht gefunden"); process.exit(1); }

const T = mkdtempSync(join(tmpdir(), "gv-dauer-"));
try {
  writeFileSync(join(T, "m.mjs"), `
    const tk = (s, v) => v ? Object.entries(v).reduce((a,[k,x]) => a.replace('{'+k+'}', x), s) : s;
    const esc = s => String(s ?? "");
    const val = (t) => '<span class="val">' + t + '</span>';
    const endetText = l => (l && l.endetMonate != null) ? tk('in {n} Mon.', {n: l.endetMonate}) : (l && l.endet) || '';
    ${core.slice(i, ende + 2)}
    export { fristCell };
  `);
  const { fristCell } = await import(join(T, "m.mjs"));
  const text = (l) => fristCell(l).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  const timing = { src: "echt", hint: "" };

  // Platzhalterdatum: keine Frist, sondern der Zustand.
  sage(text({ verfahren: "open_house", tage: 26761, timing }) === "laufend dauerhaft offen",
       "AT-Platzhalter (01.01.2100) zeigt laufend statt 26.761 Tage");
  sage(text({ verfahren: "open_house", tage: 26756, timing }) === "laufend dauerhaft offen",
       "DE-Platzhalter (31.12.2099) ebenso");
  // ⚠ Auch ohne jede Zahl: das Detail rechnete daraus in -24307 Mon.
  sage(text({ verfahren: "open_house", tage: null, endetMonate: -24307, timing, src: "f02" })
       === "laufend dauerhaft offen",
       "ohne Frist kein negativer Monatswert");

  // DIE GEGENRICHTUNG: echte Fristen bleiben.
  sage(text({ verfahren: "open_house", tage: 36, timing }) === "36 Tage bis Schluss",
       "Dauerverfahren MIT echter Frist behaelt seinen Countdown");
  sage(text({ verfahren: "open_house", tage: 3650, timing }) === "3650 Tage bis Schluss",
       "zehn Jahre sind noch eine Frist, keine Dauerhaftigkeit");
  sage(text({ verfahren: "wettbewerb", tage: 4, timing }) === "4 Tage bis Schluss",
       "gewoehnliche Vergabe unveraendert");
  sage(text({ verfahren: "wettbewerb", tage: 26761, timing }) === "26761 Tage bis Schluss",
       "ohne open_house wird NICHT umgedeutet — die Kennzeichnung entscheidet, nicht das Datum");

  // Und im Detailblock dieselbe Regel, sonst steht die Haelfte weiter falsch da.
  sage(core.includes("l.verfahren === 'open_house' && (l.tage == null || l.tage > 3650)")
       && core.split("l.verfahren === 'open_house'").length - 1 >= 2,
       "Liste UND Detail pruefen beide auf das Dauerverfahren");
} finally {
  rmSync(T, { recursive: true, force: true });
}
console.log(fehler ? `  ${fehler} Abweichung(en)` : "  Dauerverfahren zeigen keine erfundene Frist");
process.exit(fehler ? 1 : 0);

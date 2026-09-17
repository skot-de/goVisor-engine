// Filtert der Zeithorizont nach dem, was die Liste ANZEIGT?
//
// WARUM ES DIESE PRUEFUNG GIBT. Ein Lead traegt bis zu zwei Daten: `tage` (Angebotsfrist,
// „wann muss ich abgeben") und `endTage` (Vertragsende, „wann wird neu vergeben"). Bis zum
// 2026-09-17 ordneten drei Stellen sie verschieden:
//
//   fristCell            `tage` zuerst   → zeigt „4 Tage bis Schluss"
//   Sortierung 'frist'   `tage` zuerst
//   Zeithorizont-Filter  `endTage` ZUERST
//
// Ein Lead mit `tage: 4` und `endTage: 800` stand also sichtbar mit „4 Tage" in der Liste
// und fiel aus dem Ein-Monats-Filter, weil der 800 mass. Der Nutzer sah: „wenn ich nach
// Vertragsende 1 Monat filtere, zeigt er mir nur zwei Leads mit 8 Tagen Frist, geh ich auf
// egal sind da noch viele andere mit 4 Tagen."
//
// ⚠ DIE EIGENSCHAFT, DIE HIER GEPRUEFT WIRD, ist nicht „die Reihenfolge ist tage-zuerst" —
// das waere eine Abschrift der Regel. Geprueft wird: WAS DIE SPALTE ZEIGT, DANACH SIEBT DER
// FILTER. Diese Aussage bleibt richtig, auch wenn jemand die Regel spaeter bewusst umdreht;
// sie zwingt nur, beide Stellen gemeinsam zu drehen.
import { readFileSync, readdirSync } from "node:fs";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
const shell = readFileSync(new URL("../components/explorer/ExplorerShell.tsx", import.meta.url), "utf8");
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

function schnitt(name) {
  const a = core.indexOf(`function ${name}(`);
  if (a < 0) throw new Error(`${name} fehlt in explorerCore.js`);
  return core.slice(a, core.indexOf("\n}", a) + 3);
}

const tk = (k, v) => String(k).replace(/\{(\w+)\}/g, (_, n) => (v && v[n] != null ? v[n] : ""));
const esc = (s) => String(s);
const val = (t) => t;
const endetText = (l) => `Ende in ${l.endTage} Tagen`;
const { handlungsFrist, fristCell } = new Function(
  "tk", "esc", "val", "endetText",
  `${schnitt("handlungsFrist")}\n${schnitt("fristCell")}\nreturn { handlungsFrist, fristCell };`,
)(tk, esc, val, endetText);

/* ── 1. Der Filter benutzt die gemeinsame Regel, keine eigene Fassung ─────────────── */
// Eine handgeschriebene `??`-Kette neben `handlungsFrist` ist genau der Zustand, aus dem
// der Fehler entstanden ist: zwei Kopien einer Reihenfolge, eine davon verkehrt.
const horizonBlock = shell.slice(shell.indexOf("if (a.horizon != null)"),
                                 shell.indexOf("if (a.regions.length || a.nationwide)"));
if (!horizonBlock.includes("handlungsFrist(")) {
  klage("Der Zeithorizont-Filter ruft `handlungsFrist` nicht auf — er hat wieder eine "
      + "eigene Fassung der Reihenfolge.");
}
// ⚠ Auf einen echten FELDZUGRIFF pruefen (`l.endTage`), nicht auf das blosse Wort. Eine
// TypeScript-Annotation wie `l as { tage?: number; endTage?: number }` enthaelt beide
// Namen, ist aber keine Rechnung — die erste Fassung dieser Pruefung schlug daran an.
if (/l\.(endTage|tage)\b[^;]*(\?\?|\|\|)[^;]*l\.(tage|endTage)\b/.test(horizonBlock)) {
  klage("Im Zeithorizont-Filter steht wieder eine eigene `endTage`/`tage`-Kette.");
}

/* ── 2. Was die Spalte zeigt, danach siebt der Filter ─────────────────────────────── */
const faelle = [
  ["Frist kurz, Ende weit", { tage: 4, endTage: 800, src: "f02", timing: {} }, 4],
  ["nur Frist",             { tage: 12, endTage: null, src: "f02", timing: {} }, 12],
  ["nur Vertragsende",      { tage: null, endTage: 45, src: "auslauf", timing: {} }, 45],
  ["weder noch",            { tage: null, endTage: null, src: "f01", timing: {} }, null],
];
for (const [name, lead, erwartet] of faelle) {
  const h = handlungsFrist(lead);
  if (h !== erwartet) klage(`\`${name}\`: handlungsFrist = ${h}, erwartet ${erwartet}.`);
  // Zeigt die Spalte einen Countdown, MUSS es dieselbe Zahl sein.
  const zelle = fristCell(lead);
  const m = zelle.match(/(\d+) Tage/);
  if (m && Number(m[1]) !== h) {
    klage(`\`${name}\`: die Spalte zeigt ${m[1]} Tage, der Filter misst ${h}. `
        + "Genau diese Luecke war der Fehler.");
  }
}

/* ── 3. Gegen die echten Daten: der Lead, den man sieht, ist auch filterbar ───────── */
const daten = new URL("../data/", import.meta.url);
const LEADS = [];
for (const f of readdirSync(daten).filter((x) => /^leads-(?!fristen).*\.json$/.test(x))) {
  const roh = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
  for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) LEADS.push(l);
}
if (LEADS.length) {
  const sichtbar = (l, h) => { const d = handlungsFrist(l); return !(d == null || d < 0 || d / 30 > h); };
  // Jeder Lead, dessen ANGEZEIGTE Frist in den Horizont faellt, muss ihn auch passieren.
  const widerspruch = LEADS.filter((l) => l.tage != null && l.tage >= 0 && l.tage <= 30
                                          && !sichtbar(l, 1));
  if (widerspruch.length) {
    const b = widerspruch[0];
    klage(`${widerspruch.length} Leads zeigen eine Frist von <= 30 Tagen und fallen trotzdem `
        + `aus dem Ein-Monats-Horizont. Beispiel ${b.id}: Frist ${b.tage}, Ende ${b.endTage}.`);
  }
  const eng = LEADS.filter((l) => sichtbar(l, 1)).length;
  console.log(`  ${LEADS.length.toLocaleString("de")} Leads, `
            + `${eng.toLocaleString("de")} im Ein-Monats-Horizont`);
}

console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Der Filter siebt nach dem, was die Liste zeigt");
process.exit(fehler ? 1 : 0);

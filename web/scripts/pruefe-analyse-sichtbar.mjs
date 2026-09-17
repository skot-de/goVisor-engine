// Sieht der Nutzer, welche Vorgaenge ausgewertete Vergabeunterlagen haben?
//
// WARUM ES DIESE PRUEFUNG GIBT. `scripts/export_doc_analysis.py` wertet Vergabeunterlagen
// aus und schreibt seit Ticket 23 einen Index ueber alle Auswertungen. Am 2026-09-17 ergab
// ein grep ueber `web/` (ohne node_modules, .next) NULL Treffer fuer „doc-analysis-index":
// die Datei wurde jede Nacht geschrieben und von niemandem gelesen. 10.951 Auswertungen,
// unsichtbar. Die Frage in der Vorfuehrung lautete „wo sehe ich, welche Ausschreibungen
// analysierte Unterlagen haben?" — und die Antwort war: nirgends.
//
// ⚠ DIESE PRUEFUNG IST BEWUSST VERHALTENSBASIERT. Eine Wortpruefung („kommt `docAn` im
// Quelltext vor?") waere wertlos: genau so ein Waechter stand hier schon einmal fuer die
// Cron-Sperre und blieb gruen, nachdem Aufruf UND Import entfernt worden waren. Deshalb
// wird `applyAnalyse` aus der Quelle geschnitten und gegen die ECHTEN Daten gefahren.
//
// Gemessen am 2026-09-17 ueber 43.676 Leads:
//   ausgewertet            4.122 (9,4 %)   ← das Merkmal, das trennt
//   Link auf Unterlagen   42.494 (97,3 %)  ← der bestehende Filter, der nichts siebt
import { readFileSync, readdirSync, existsSync } from "node:fs";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
const daten = new URL("../data/", import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

/* ── 1. Der Index traegt die Dichte, nicht nur die Ampel ──────────────────────────── */
const idxDatei = new URL("doc-analysis-index.json", daten);
if (!existsSync(idxDatei)) {
  console.log("  … doc-analysis-index.json fehlt — export_doc_analysis.py nicht gelaufen. Uebersprungen.");
  process.exit(0);
}
const idx = JSON.parse(readFileSync(idxDatei, "utf8"));
const eintraege = Object.entries(idx);
const mitDichte = eintraege.filter(([, v]) => typeof v?.pruef === "number" && v.pruef > 0).length;
if (!mitDichte) {
  klage("kein einziger Eintrag traegt `pruef` — der Export schreibt wieder nur die Ampel. "
      + "Damit faellt jede Sortierung nach Informationsdichte auf 0 zusammen.");
}

/* ── 2. Die Ampel allein traegt nichts — falls jemand auf die Idee kommt, sie zu nutzen ─ */
const ampeln = {};
for (const [, v] of eintraege) ampeln[v?.ampel ?? "null"] = (ampeln[v?.ampel ?? "null"] || 0) + 1;
const groesste = Math.max(...Object.values(ampeln));
const ampelAnteil = groesste / eintraege.length;

/* ── 3. `applyAnalyse` laeuft gegen echte Daten ───────────────────────────────────── */
const a = core.indexOf("function applyAnalyse(");
if (a < 0) {
  klage("`applyAnalyse` fehlt in explorerCore.js — der Index wird nicht mehr an die Leads geheftet.");
} else {
  const quelle = core.slice(a, core.indexOf("\n}", a) + 3);
  const LEADS = [];
  for (const f of readdirSync(daten).filter((x) => /^leads-(?!fristen).*\.json$/.test(x))) {
    const roh = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
    for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) LEADS.push(l);
  }
  const fn = new Function("LEADS", `${quelle}\nreturn applyAnalyse;`)(LEADS);
  fn(idx);

  const markiert = LEADS.filter((l) => l.docAn).length;
  const mitZahl = LEADS.filter((l) => l.docAn && l.docAn.pruef > 0).length;
  if (!markiert) {
    klage(`${LEADS.length.toLocaleString("de")} Leads, aber KEIN einziger traegt eine Auswertung. `
        + `Der Index kennt ${eintraege.length.toLocaleString("de")} Vorgaenge — die Kennungen passen nicht zusammen.`);
  } else if (!mitZahl) {
    klage(`${markiert} Leads sind markiert, aber keiner traegt eine Pruefpunktzahl.`);
  }

  /* ⚠ Ein Lead OHNE Auswertung muss `docAn === null` bekommen, nicht `undefined`. Die
     Spalte unterscheidet drei Zustaende: ausgewertet, ausgewertet-ohne-Fund, und gar
     nicht ausgewertet. `undefined` liefe in denselben Zweig wie `null`, aber nur solange
     niemand `in`-Pruefungen oder `Object.keys` benutzt — das ist zu fein, um sich darauf
     zu verlassen. */
  const ohne = LEADS.find((l) => !l.docAn);
  if (ohne && ohne.docAn !== null) {
    klage("Leads ohne Auswertung tragen nicht `null`, sondern " + String(ohne.docAn) + ".");
  }
  console.log(`  ${markiert.toLocaleString("de")} von ${LEADS.length.toLocaleString("de")} Leads `
            + `(${(100 * markiert / LEADS.length).toFixed(1)} %) tragen eine Auswertung`);
}

/* ── 4. Die Spalte ist registriert UND standardmaessig sichtbar ───────────────────── */
// Ohne `on:true` waere die Arbeit wieder unsichtbar — nur eben eine Ebene tiefer versteckt.
if (!/\{\s*key:\s*'doks'[^}]*on:\s*true/.test(core)) {
  klage("Spalte 'doks' fehlt in COLS oder steht nicht auf `on:true` — "
      + "die Auswertungen waeren wieder unsichtbar.");
}
if (core.indexOf("case 'doks':") < 0) {
  klage("`cellHTML` hat keinen Zweig fuer 'doks' — die Spalte bliebe leer.");
}

/* ── 5. Irgendetwas unter `app/` muss den Index tatsaechlich lesen ────────────────── */
// Das ist die Pruefung gegen den Rueckfall in genau den Zustand, der diese Datei ausgeloest
// hat: Datei geschrieben, niemand liest sie.
function suchen(ordner, treffer = []) {
  for (const e of readdirSync(ordner, { withFileTypes: true })) {
    const p = new URL(e.name + (e.isDirectory() ? "/" : ""), ordner);
    if (e.isDirectory()) { if (e.name !== "node_modules") suchen(p, treffer); }
    else if (/\.(ts|tsx|js|mjs)$/.test(e.name) &&
             readFileSync(p, "utf8").includes("docAnalysis")) treffer.push(e.name);
  }
  return treffer;
}
const leser = suchen(new URL("../app/", import.meta.url));
if (!leser.length) {
  klage("Keine Datei unter `app/` importiert `lib/docAnalysis` — der Index wird wieder "
      + "geschrieben und von niemandem gelesen. Genau dafuer gibt es diese Pruefung.");
}

console.log(`  Index: ${eintraege.length.toLocaleString("de")} Auswertungen, `
          + `${mitDichte.toLocaleString("de")} mit Dichte, `
          + `haeufigste Ampel ${(100 * ampelAnteil).toFixed(1)} % `
          + `(${ampelAnteil > 0.8 ? "⚠ taugt nicht zum Filtern" : "brauchbar"})`);
console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Auswertungen sind sichtbar");
process.exit(fehler ? 1 : 0);

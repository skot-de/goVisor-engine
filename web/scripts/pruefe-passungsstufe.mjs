// Behauptet die Passung eine Feinheit, die sie nicht hat?
//
// WARUM ES DIESE PRUEFUNG GIBT. `passung` wird aus vier Zuschlaegen in Halbschritten
// gebaut und kann deshalb nur ACHT Werte annehmen:
//
//     s      2,0  2,5  3,0  3,5  4,0  4,5  5,0  5,5
//     Zahl     0   14   29   43   57   71   86  100
//
// Angezeigt wurde „86/100". Das sieht aus wie ein Prozentsatz mit hundert Abstufungen —
// und 86 ist die haeufigste der acht: Feld, Region und Volumen passen, kein
// Zielrichtungsbonus. Also der Normalfall eines gut passenden Leads.
//
// Gemeldet am 2026-09-17: „alle leads haben relevanz 86, kann auch nicht sein oder?"
// Die Rechnung war richtig. Die DARSTELLUNG hat etwas behauptet, das es nicht gibt — und
// der Kopf von `passungsZahl` sagte seit jeher das Gegenteil: „die STUFE bleibt die
// Aussage; die Zahl dient dem Sortieren."
//
// ⚠ WAS HIER GEPRUEFT WIRD, ist nicht „es sind genau acht Stufen" — das waere eine
// Abschrift der Rechnung. Geprueft wird: die ANZEIGE verspricht nicht mehr Abstufungen,
// als die Rechnung hergibt. Wer die Rechnung verfeinert, darf die Anzeige mitverfeinern;
// wer nur die Anzeige aufblaest, wird rot.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const web = new URL("../", import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

const { passungsZahl, passungsStufe, PASSUNG_STUFEN, matchLead, buildProfile } =
  await import(pathToFileURL(new URL("lib/profileEngine.js", web).pathname).href);

/* ── 1. Wie viele Werte kann die Rechnung ueberhaupt erzeugen? ────────────────────── */
// `s` laeuft von 2 bis 5,5 in Halbschritten — das sind die einzig moeglichen Eingaben.
const werte = new Set(), stufen = new Set();
for (let s = 2; s <= 5.5001; s += 0.5) { werte.add(passungsZahl(s)); stufen.add(passungsStufe(s)); }
console.log(`  Rechnung liefert ${werte.size} verschiedene Zahlen und ${stufen.size} Stufen`);
if (stufen.size !== werte.size) {
  klage(`${werte.size} moegliche Zahlen, aber ${stufen.size} Stufen — die Stufe verliert `
      + "oder erfindet eine Unterscheidung.");
}
if (Math.max(...stufen) !== PASSUNG_STUFEN) {
  klage(`Hoechste Stufe ist ${Math.max(...stufen)}, PASSUNG_STUFEN sagt ${PASSUNG_STUFEN}.`);
}

/* ── 2. Die Anzeige verspricht nicht mehr, als die Rechnung hergibt ───────────────── */
const core = readFileSync(new URL("lib/explorerCore.js", web), "utf8");
const a = core.indexOf("function passungAchse(");
if (a < 0) {
  klage("`passungAchse` fehlt.");
} else {
  /* ⚠ KOMMENTARE RAUS. Die erste Fassung dieser Pruefung schlug an der ERKLAERUNG im Kopf
     von `passungAchse` an — dort steht die alte Darstellung als Zitat („hier stand 86/100").
     Sie mass Prosa statt Code. Dieselbe Falle steckte heute schon in `pruefe_verdrahtung.py`
     und im Ladezustand-Test; sie ist offenbar die haeufigste in dieser Art Waechter. */
  const block = core.slice(a, core.indexOf("\n}", a) + 3)
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  // Die alte Behauptung: „/100" oder „von 100".
  if (/\/100|von 100/.test(block)) {
    klage("Die Anzeige nennt wieder \u201e100\u201c als Bezugsgroesse. Die Rechnung kennt "
        + `${werte.size} Werte, \u201evon 100\u201c behauptet hundert.`);
  }
  // Die Zahl der gezeichneten Segmente muss aus der Rechnung stammen, nicht fest stehen.
  const feste = [...block.matchAll(/length:\s*(\d+)/g)].map((m) => Number(m[1]));
  for (const n of feste) {
    if (n !== PASSUNG_STUFEN) {
      klage(`Die Anzeige zeichnet ${n} Segmente, die Rechnung kennt ${PASSUNG_STUFEN} Stufen.`);
    }
  }
  if (!/\bstufe\b/.test(block)) klage("`passungAchse` benutzt die Stufe nicht mehr.");
  // Ohne Begruendung ist eine Stufe so undurchsichtig wie eine Zahl.
  if (!/teile/.test(block)) {
    klage("Der Tooltip nennt die Gruende nicht mehr (`match.teile`). Eine Stufe ohne "
        + "Begruendung erklaert so wenig wie \u201e86\u201c.");
  }
}

/* ── 3. Die Stufe stimmt mit dem ueberein, was `matchLead` wirklich rechnet ───────── */
const profil = buildProfile({ cpvFields: ["4521"], cpvFields6: [], nachbarFields: ["4523"],
  regions: ["DEA"], regionTyp: "bundesland", volMin: null, volMax: 10000000 });
const FAELLE = [
  ["voller Treffer",   { cpv: "45211000", nuts: "DEA12", volumen: { wert: "5.000.000", src: "belegt" } }],
  ["Nachbarfeld",      { cpv: "45231000", nuts: "DEA12", volumen: { wert: "5.000.000", src: "belegt" } }],
  ["ausserhalb",       { cpv: "72000000", nuts: "DEA12", volumen: { wert: "5.000.000", src: "belegt" } }],
];
for (const [name, lead] of FAELLE) {
  const m = matchLead({ ...lead, anf: null, lose: null }, profil);
  if (m.passung == null) continue;
  if (m.stufe == null) { klage(`\`${name}\`: \`matchLead\` liefert keine Stufe.`); continue; }
  // Stufe und Zahl muessen dieselbe Reihenfolge ergeben — sonst sortiert die Liste anders,
  // als die Anzeige nahelegt. Genau dieser Bruch war der Zeitfilter-Fehler von heute frueh.
  const erwartet = [...werte].sort((x, y) => x - y).indexOf(m.passung);
  if (m.stufe !== erwartet) {
    klage(`\`${name}\`: Stufe ${m.stufe}, aber die Zahl ${m.passung} ist die `
        + `${erwartet}. von ${werte.size}. Anzeige und Sortierung fielen auseinander.`);
  }
}

console.log(fehler ? `\n✗ ${fehler} Befund(e)`
                   : "\n✓ Die Anzeige verspricht genau so viele Abstufungen, wie es gibt");
process.exit(fehler ? 1 : 0);

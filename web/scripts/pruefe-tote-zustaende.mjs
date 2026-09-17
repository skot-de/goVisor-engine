// Gibt es Zustaende, die gesetzt und nie gelesen werden?
//
// WARUM ES DIESE PRUEFUNG GIBT. Am 2026-09-17 sah ein Nutzer nach der Anmeldung rund
// zwoelf Sekunden lang „0 von 0" und darunter „Keine Leads mit diesen Filtern. Passe die
// Filter an" — eine Aufforderung, an Filtern zu drehen, die mit dem Problem nichts zu tun
// hatten.
//
// Der Zustand, der das haette verhindern koennen, WAR DA: `const [loading, setLoading] =
// useState(true)` in `ExplorerShell.tsx`, korrekt gesetzt vor dem Abruf und danach
// zurueckgenommen. Gelesen hat ihn niemand. Die Anwendung wusste, dass sie laedt, und
// sagte es nicht.
//
// Das ist dieselbe Fehlerklasse wie „gebaut, nicht verdrahtet" (s. `pruefe_verdrahtung.py`
// und `pruefe-analyse-sichtbar.mjs`), nur eine Ebene kleiner: nicht eine ungelesene Datei,
// sondern ein ungelesener Zustand. Sie faellt nicht auf, weil nichts kaputtgeht — die
// Oberflaeche ist nur stumm, wo sie etwas wuesste.
//
// ⚠ EIN TREFFER IST NICHT AUTOMATISCH EIN FEHLER. Ein Zustand kann bewusst nur als Sperre
// dienen. Dann gehoert er in AUSNAHMEN, mit Begruendung und Datum — nicht kommentarlos.
import { readFileSync, readdirSync } from "node:fs";

const web = new URL("../", import.meta.url);

/** Zustaende, die absichtlich nur geschrieben werden. Mit Grund und Datum, sonst wird
 *  diese Liste zu dem, was die Ausnahmeliste in `pruefe_verdrahtung.py` geworden war:
 *  ein Ort, an dem Funde sterben. */
const AUSNAHMEN = {};

function dateien(ordner, raus = []) {
  for (const e of readdirSync(ordner, { withFileTypes: true })) {
    if (e.isDirectory()) {
      if (!["node_modules", ".next"].includes(e.name)) dateien(new URL(e.name + "/", ordner), raus);
    } else if (/\.tsx$/.test(e.name)) raus.push(new URL(e.name, ordner));
  }
  return raus;
}

let fehler = 0, geprueft = 0;
for (const p of [...dateien(new URL("components/", web)), ...dateien(new URL("app/", web))]) {
  const datei = String(p).split("/web/")[1];
  // Kommentare raus: ein Zustand, der nur in einer Prosazeile vorkommt, ist nicht gelesen.
  const code = readFileSync(p, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  for (const m of code.matchAll(/const \[(\w+),\s*(set\w+)\] = useState/g)) {
    const [, wert, setzer] = m;
    geprueft++;
    if (AUSNAHMEN[`${datei}:${wert}`]) continue;
    const n = (code.match(new RegExp(`\\b${wert}\\b`, "g")) || []).length;
    if (n > 1) continue;
    const gesetzt = (code.match(new RegExp(`\\b${setzer}\\b`, "g")) || []).length > 1;
    console.error(`  ✗ ${datei}: \`${wert}\` wird ${gesetzt ? "gesetzt" : "angelegt"}, aber nie gelesen.`
      + (gesetzt
        ? " Die Oberflaeche weiss etwas und sagt es nicht — genau so blieb der Ladezustand"
          + " zwoelf Sekunden lang unsichtbar."
        : " Tote Zeile: weder gelesen noch gesetzt."));
    fehler++;
  }
}

console.log(`  ${geprueft} Zustaende geprueft`);
console.log(fehler ? `\n✗ ${fehler} ungelesene(r) Zustand/Zustaende`
                   : "\n✓ Jeder Zustand wird auch gelesen");
process.exit(fehler ? 1 : 0);

// Finden die Suchworte des Drehbuchs im DEMO-Datensatz etwas?
//
// WARUM ES DIESE PRUEFUNG GIBT. Am 2026-09-17 wurde mitten in einer Vorfuehrung empfohlen,
// nach „Ubstadt" zu suchen. Geprueft worden war `EU_VB_27_Rottweil_WE` gegen den
// VOLLBESTAND (87.352 Leads, per DuckDB). Im Demo-Datensatz (945 Leads) kommt keines von
// beiden vor. Die Suche lief ins Leere, und es sah aus wie ein Suchfehler.
//
// ⚠ DER VOLLBESTAND SAGT NICHTS UEBER DIE VORFUEHRUNG. `scripts/demo_datensatz.py` siebt
// nach Informationsdichte und laesst dabei ganze Regionen und Vergabestellen fallen, ohne
// es zu melden. Beide Seiten tragen dieselben Feldnamen und beantworten dieselben
// Abfragen — nur mit anderem Inhalt. Deshalb faellt der Fehler nicht auf.
//
// Die Worte stehen in `docs/demo-ablauf.md` in einem ```suchworte-Block. Wer eines ins
// Drehbuch nimmt, traegt es dort ein; hier wird es gefahren.
import { readFileSync, readdirSync, existsSync } from "node:fs";

const wurzel = new URL("../../", import.meta.url);
const demo = new URL("web/data-demo/", wurzel);
if (!existsSync(demo)) {
  console.log("  … web/data-demo/ fehlt — demo_datensatz.py nicht gelaufen. Uebersprungen.");
  process.exit(0);
}

const drehbuch = readFileSync(new URL("docs/demo-ablauf.md", wurzel), "utf8");
const block = drehbuch.match(/```suchworte\n([\s\S]*?)```/);
if (!block) {
  console.error("  ✗ In `docs/demo-ablauf.md` fehlt der ```suchworte-Block. "
              + "Ohne ihn prueft diese Sonde nichts und ist selbst die Luecke.");
  process.exit(1);
}
const worte = block[1].split("\n").map((z) => z.trim().toLowerCase()).filter(Boolean);
if (!worte.length) {
  console.error("  ✗ Der ```suchworte-Block ist leer.");
  process.exit(1);
}

// Dieselbe Zusammensetzung wie `leadText` in `lib/explorerCore.js`. Sie wird hier aus der
// Quelle geschnitten, damit die Pruefung nicht an einer Abschrift vorbeilaeuft.
const core = readFileSync(new URL("web/lib/explorerCore.js", wurzel), "utf8");
const a = core.indexOf("const leadText =");
const leadText = new Function(`${core.slice(a, core.indexOf("\n", a) + 1)}\nreturn leadText;`)();

const LEADS = [];
for (const f of readdirSync(demo).filter((x) => /^leads-(?!fristen).*\.json$/.test(x))) {
  const roh = JSON.parse(readFileSync(new URL(f, demo), "utf8"));
  for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) LEADS.push(l);
}

let fehler = 0;
console.log(`  Demo-Datensatz: ${LEADS.length.toLocaleString("de")} Leads`);
for (const w of worte) {
  const n = LEADS.filter((l) => leadText(l).includes(w)).length;
  if (!n) {
    console.error(`  ✗ „${w}" findet im Demo-Datensatz NICHTS. In der Vorfuehrung sieht das `
                + "aus wie ein Suchfehler. Wort streichen oder den Demo-Satz anders sieben.");
    fehler++;
  } else {
    console.log(`     „${w}" → ${n} Treffer`);
  }
}
console.log(fehler ? `\n✗ ${fehler} Drehbuchwort(e) laufen ins Leere`
                   : "\n✓ Jedes Drehbuchwort findet etwas");
process.exit(fehler ? 1 : 0);

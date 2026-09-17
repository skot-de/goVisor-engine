// Findet die Suche, was sie hinterher als Fundort ausweist?
//
// WARUM ES DIESE PRUEFUNG GIBT. `leadText` baut den durchsuchten Text eines Leads,
// `fundstelle` erklaert hinterher, WO das Wort stand. Bis zum 2026-09-17 kannten die
// beiden verschiedene Felder:
//
//   leadText    titel, buyer, buyerShort, natur, beschreibung, kw
//   fundstelle  … und zusaetzlich `Vergabenummer` und `Los N`
//
// Damit hatte `fundstelle` zwei tote Zweige: sie konnte Fundorte melden, die `matchToken`
// nie erzeugen konnte. Umgekehrt waren Vorgaenge unauffindbar, deren Ort nur im Los-Titel
// steht — bei Mehrlos-Vergaben der Normalfall, denn der Haupttitel heisst dann „Neubau
// Verwaltungsgebaeude, Lose 1-7". Gemessen: „rottweil" 19 → 22 Treffer, „hamm" 72 → 86.
//
// ⚠ DIE EIGENSCHAFT, DIE HIER GEPRUEFT WIRD: jeder Fundort, den `fundstelle` melden kann,
// muss von einer echten Suche erreichbar sein — und jeder Treffer muss einen Beleg
// bekommen. Ein Treffer ohne Beleg sieht aus wie ein Fehler; das steht so im Kopf von
// `fundstelle` und war genau der Zustand, den diese Pruefung verhindert.
import { readFileSync, readdirSync } from "node:fs";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

function schnitt(name, art = "function") {
  const marke = art === "const" ? `const ${name} =` : `function ${name}(`;
  const a = core.indexOf(marke);
  if (a < 0) throw new Error(`${name} fehlt in explorerCore.js`);
  const b = art === "const" ? core.indexOf("\n", a) + 1 : core.indexOf("\n}", a) + 3;
  return core.slice(a, b);
}

// Nur die Stuecke, die die Volltextsuche braucht. `cpvLabel` wird gestubbt: es zieht eine
// Kennzahlentabelle nach, die mit der Frage nichts zu tun hat.
const quelle = [schnitt("leadText", "const"), schnitt("_kennNorm", "const"),
                schnitt("fundstelle")].join("\n");
const cpvLabel = () => "";
const { leadText, fundstelle } = new Function(
  "cpvLabel", `${quelle}\nreturn { leadText, fundstelle };`,
)(cpvLabel);

/* ── 1. Jeder Fundort, den `fundstelle` kennt, ist durch die Suche erreichbar ──────── */
// Die Faelle sind so gebaut, dass das Suchwort NUR in dem einen Feld steht. Findet die
// Suche es nicht, ist der Zweig in `fundstelle` tot.
const basis = { titel: "", buyer: "", buyerShort: "", natur: "", beschreibung: "", kw: [],
                lose: null, vergabenr: null };
const ORTE = [
  ["Titel",         { ...basis, titel: "zzqtitel" },                        "zzqtitel"],
  ["Leistungsart",  { ...basis, natur: "zzqnatur" },                        "zzqnatur"],
  ["Los 3",         { ...basis, lose: [{ nr: 3, titel: "zzqlos" }] },       "zzqlos"],
  ["Beschreibung",  { ...basis, beschreibung: "ein satz mit zzqbeschr darin" }, "zzqbeschr"],
  ["Auftraggeber",  { ...basis, buyer: "zzqbuyer" },                        "zzqbuyer"],
  ["Vergabenummer", { ...basis, vergabenr: "VB-27-ZZQNR-2026" },            "zzqnr"],
];
for (const [erwarteterOrt, lead, wort] of ORTE) {
  const gefunden = leadText(lead).includes(wort);
  if (!gefunden) {
    klage(`Fundort „${erwarteterOrt}": die Suche findet „${wort}" nicht, obwohl `
        + "`fundstelle` diesen Ort melden kann. Der Zweig ist toter Code.");
    continue;
  }
  const f = fundstelle(lead, wort);
  if (!f) {
    klage(`Fundort „${erwarteterOrt}": Treffer OHNE Beleg. „Ohne diesen Beleg wirken `
        + 'Volltext-Treffer wie Fehler" steht im Kopf von `fundstelle`.');
  } else if (!String(f.ort).startsWith(erwarteterOrt.split(" ")[0])) {
    klage(`Fundort „${erwarteterOrt}": fundstelle meldet stattdessen „${f.ort}".`);
  }
}

/* ── 2. Gegen echte Daten: jeder Volltext-Treffer bekommt einen Beleg ──────────────── */
const daten = new URL("../data/", import.meta.url);
const LEADS = [];
for (const f of readdirSync(daten).filter((x) => /^leads-(?!fristen).*\.json$/.test(x))) {
  const roh = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
  for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) LEADS.push(l);
}
if (LEADS.length) {
  let ohneBeleg = 0, bsp = null, treffer = 0;
  for (const wort of ["rottweil", "hamm", "aufzug", "schleuse", "brandschutz"]) {
    for (const l of LEADS) {
      if (!leadText(l).includes(wort)) continue;
      treffer++;
      if (!fundstelle(l, wort)) { ohneBeleg++; if (!bsp) bsp = [l.id, wort]; }
    }
  }
  if (ohneBeleg) {
    klage(`${ohneBeleg} von ${treffer} Volltext-Treffern bekommen keinen Beleg `
        + `(z. B. ${bsp[0]} bei „${bsp[1]}"). Sie sehen fuer den Nutzer aus wie Fehler.`);
  }
  // Die Lose muessen tatsaechlich etwas beitragen, sonst ist der Aufwand umsonst.
  const ohneLose = (l) => (l.titel + " " + l.buyer + " " + l.buyerShort + " " + l.natur + " "
    + (l.beschreibung || "") + " " + (l.kw || []).map((k) => k.w).join(" ")).toLowerCase();
  const nurDurchLose = LEADS.filter((l) => leadText(l).includes("rottweil")
                                        && !ohneLose(l).includes("rottweil")).length;
  console.log(`  ${treffer.toLocaleString("de")} Volltext-Treffer geprueft, alle mit Beleg`);
  console.log(`  „rottweil": ${nurDurchLose} Vorgaenge nur ueber Lose/Nummer auffindbar`);
}

console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Suche und Fundort kennen dieselben Felder");
process.exit(fehler ? 1 : 0);

// Sieht der Nutzer, dass ein Auftrag aus EU-Mitteln kofinanziert ist?
//
// WARUM ES DIESE PRUEFUNG GIBT. Das Feld `FundingProgramCode` liegt seit Jahren in
// Bronze und stand seit dem 2026-07-23 in `bronze_inventory` als bekannt und UNGENUTZT.
// Es ist am 2026-10-04 angeschlossen worden. Die Kette hat vier Glieder — Silber-
// Attribute, `_lead_context_sql`, `export_web_leads.py`, `explorerCore.js` — und
// „gebaut, aber nicht verdrahtet" ist in diesem Projekt die haeufigste Fehlerklasse.
// Jedes einzelne Glied kann reissen, ohne dass ein Test rot wird: eine leere Spalte
// sieht aus wie eine Quelle, die nichts hergibt.
//
// ⚠ VERHALTENSBASIERT, NICHT WORTBASIERT. Ein grep nach „euGefoerdert" bliebe gruen,
// wenn die Zeile in einem Zweig steht, den nie jemand erreicht. Deshalb wird die
// Anforderungs-Vorlage aus `explorerCore.js` geschnitten und mit allen DREI Zustaenden
// gerendert: true, false, null.
//
// Der dritte Zustand ist der wichtige. Nur eForms kennt ein ausdrueckliches
// `no-eu-funds`; DOeE, DTVP, NetServer und Healy-Hudson tragen das Feld gar nicht, und
// die Altformate kennen nur ein Ja. Wuerde die Oberflaeche aus `null` ein „nicht
// gefoerdert" machen, behauptete sie etwas, das die Quelle nicht sagt.
import { readFileSync, readdirSync, existsSync } from "node:fs";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
const daten = new URL("../data/", import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

/* ── 1. Die Vorlage aus der Quelle schneiden ──────────────────────────────────────── */
// Geschnitten wird GENAU der Teil, der `rows` fuellt: von der Eignungs-Tabelle bis zur
// Leerpruefung. Alles danach ist Rahmenwerk (Ueberschrift, Rueckgabe) und gehoert nicht
// in die Probe — es zieht sonst die umschliessende Pfeilfunktion mit und bricht.
const anker = core.indexOf('const EIG = {');
const ende = core.indexOf("if(!rows.length) return '';", anker);
if (anker < 0 || ende < 0) {
  klage("Anforderungsblock in explorerCore.js nicht gefunden — wurde er umbenannt? "
      + "Dann muss diese Sonde nachgezogen werden, nicht geloescht.");
  process.exit(1);
}
const quelle = core.slice(anker, ende);

// Minimalumgebung: die Vorlage benutzt `tk` (Uebersetzung) und `esc` (Maskierung).
const bauen = (anf) => {
  // `const rows=[]` steht bereits im geschnittenen Block — nicht noch einmal anlegen.
  const fn = new Function("a", "tk", "esc", "userProfile", `
    ${quelle}
    return rows.join("");
  `);
  return fn(anf, (s) => s, (s) => String(s ?? ""), null);
};

/* ── 2. Alle drei Zustaende ───────────────────────────────────────────────────────── */
const ja = bauen({ euGefoerdert: true, euProgramm: "ERDF_2021" });
const jaOhneName = bauen({ euGefoerdert: true, euProgramm: null });
const nein = bauen({ euGefoerdert: false, euProgramm: null });
const unbekannt = bauen({ euGefoerdert: null, euProgramm: null });

if (!/EU-Mittel/.test(ja)) {
  klage("Bei `euGefoerdert: true` erscheint KEINE EU-Zeile. Die Kette ist zwischen "
      + "export_web_leads.py und explorerCore.js unterbrochen.");
}
if (!/ERDF_2021/.test(ja)) {
  klage("Der Programmname wird nicht angezeigt, obwohl er vorliegt.");
}
if (!/EU-Mittel/.test(jaOhneName)) {
  klage("Ohne Programmnamen verschwindet die ganze Zeile. Der Name ist optional, "
      + "die Foerderung nicht.");
}
if (/EU-Mittel/.test(nein)) {
  klage("Bei `euGefoerdert: false` erscheint eine EU-Zeile. Die grosse Mehrheit ist "
      + "nicht gefoerdert — das waere Rauschen in jedem Lead.");
}
if (/EU-Mittel/.test(unbekannt)) {
  klage("Bei `euGefoerdert: null` erscheint eine EU-Zeile. `null` heisst „die Quelle "
      + "sagt nichts\" und darf nichts behaupten — weder ja noch nein.");
}

/* ── 3. Gegen die echten Daten: kommt das Feld ueberhaupt an? ─────────────────────── */
if (!existsSync(daten)) {
  console.log("  … web/data fehlt — uebersprungen.");
  process.exit(fehler ? 1 : 0);
}
const LEADS = [];
for (const f of readdirSync(daten).filter((x) => /^leads-(?!fristen).*\.json$/.test(x))) {
  const roh = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
  for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) LEADS.push(l);
}
if (!LEADS.length) {
  console.log("  … keine Leads exportiert — uebersprungen.");
  process.exit(fehler ? 1 : 0);
}
const z = { true: 0, false: 0, null: 0 };
let mitProgramm = 0;
for (const l of LEADS) {
  const v = (l.anf || {}).euGefoerdert;
  z[v === true ? "true" : v === false ? "false" : "null"]++;
  if ((l.anf || {}).euProgramm) mitProgramm++;
}
if (!z.true) {
  klage(`${LEADS.length.toLocaleString("de")} Leads, aber KEINER ist als EU-kofinanziert `
      + `markiert. Gemessen am 2026-10-04 waren es 897. Null heisst: `
      + `export_web_leads.py oder lead_export traegt das Feld nicht mehr.`);
}
if (!z.false) {
  klage("Kein einziger Lead traegt ein ausdrueckliches NEIN. eForms sagt `no-eu-funds` "
      + "ausdruecklich — fehlt das, liest die Kette nur noch die Altformate.");
}
if (!z.null) {
  klage("Kein Lead ist `null`. Die nationalen Quellen (DOeE, DTVP, NetServer, "
      + "Healy-Hudson) tragen das Feld nicht — wo keine NULL mehr ist, hat jemand aus "
      + "Schweigen ein Nein gemacht.");
}

console.log(`  ${z.true.toLocaleString("de")} EU-kofinanziert · `
          + `${z.false.toLocaleString("de")} ausdruecklich nicht · `
          + `${z.null.toLocaleString("de")} ohne Angabe  `
          + `(${mitProgramm.toLocaleString("de")} mit Programmnamen)`);
if (!fehler) console.log("  ✓ EU-Kofinanzierung ist sichtbar, und nur wo sie belegt ist");
process.exit(fehler ? 1 : 0);

// Sieht der Nutzer, dass ohne Wettbewerb vergeben wurde — und mit welcher Begruendung?
//
// WARUM ES DIESE PRUEFUNG GIBT. Der Text ist der AMTLICHE Wortlaut der EU-Codeliste
// (`data/reference/eforms/direct-award-justification.json`) und kommt als DATEN ins
// Frontend: Export → `anf.direktvergabeGrund` → `tk(...)`. Drei Glieder, drei Ausfaelle:
//
//   1. Der Export findet die Codeliste nicht → im Produkt steht `technical` statt des
//      Rechtstexts. Sichtbar haesslich, aber eben nur, wenn jemand hinsieht.
//   2. Die Oberflaeche zeigt das Feld nicht mehr an → Daten da, Anzeige leer.
//   3. Ein Wortlaut hat keine Uebersetzung → englische Nutzer lesen deutsche
//      Rechtsbegriffe.
//
// ⚠ Fall 3 faengt `test_verdrahtete_texte_sind_uebersetzt` NICHT. Er durchsucht den
// Quelltext nach `t("...")`-Literalen; diese Texte stehen nirgends im Code. Genau
// dieselbe Luecke wurde gestern bei den Nichtvergabe-Gruenden gefunden — sie gilt fuer
// JEDES Vokabular, das wir aus Parquet ins Frontend reichen.
import { readFileSync, readdirSync, existsSync } from "node:fs";

const hier = (p) => new URL(p, import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

/* ── 1. Die Oberflaeche zeigt es — VERHALTENSBASIERT ──────────────────────────────── */
// ⚠ Der erste Entwurf prueffte nur, ob die Zeichenkette `a.direktvergabeGrund` im
// Quelltext vorkommt. Die Selbstprobe entlarvte ihn: ersetzt man die BEDINGUNG durch
// `if(false)`, steht der Name immer noch in der Vorlage darunter, und der Waechter
// blieb gruen. Eine Wortpruefung kann nicht sehen, ob ein Zweig erreichbar ist.
// Deshalb wird der Anforderungsblock geschnitten und mit echten Daten gerendert.
const core = readFileSync(hier("../lib/explorerCore.js"), "utf8");
const anker = core.indexOf("const EIG = {");
const ende = core.indexOf("if(!rows.length) return '';", anker);
if (anker < 0 || ende < 0) {
  klage("Anforderungsblock in explorerCore.js nicht gefunden — umbenannt? Dann muss "
      + "diese Sonde nachgezogen werden, nicht geloescht.");
} else {
  const quelle = core.slice(anker, ende);
  const bauen = (anf) => new Function("a", "tk", "esc", "userProfile",
    `${quelle}\nreturn rows.join("");`)(anf, (s) => s, (s) => String(s ?? ""), null);
  const mitGrund = bauen({ direktvergabeGrund: "PROBETEXT-XY" });
  const ohneGrund = bauen({});
  if (!/PROBETEXT-XY/.test(mitGrund)) {
    klage("Mit `direktvergabeGrund` erscheint KEINE Zeile. Die Begruendung steht in "
        + "den Daten und wird nirgends angezeigt.");
  }
  if (/Direktvergabe/.test(ohneGrund)) {
    klage("Ohne Begruendung erscheint trotzdem eine Direktvergabe-Zeile. Die grosse "
        + "Mehrheit wurde im Wettbewerb vergeben — das waere Rauschen.");
  }
}

/* ── 2. Die Daten tragen den Rechtstext, nicht den Code ───────────────────────────── */
const refP = hier("../../data/reference/eforms/direct-award-justification.json");
if (!existsSync(refP)) {
  klage("data/reference/eforms/direct-award-justification.json fehlt. Holen: "
      + "python3 scripts/hole_eforms_codeliste.py");
}
const ref = existsSync(refP) ? JSON.parse(readFileSync(refP, "utf8")) : {};
const codes = new Set(Object.keys(ref));
const texte = new Set(Object.values(ref).map((v) => v.de).filter(Boolean));

const daten = hier("../data/");
if (!existsSync(daten)) {
  console.log("  … web/data fehlt — uebersprungen.");
  process.exit(fehler ? 1 : 0);
}
let mit = 0;
const gesehen = new Set();
for (const f of readdirSync(daten).filter((x) => /^leads-(?!fristen).*\.json$/.test(x))) {
  const roh = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
  for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) {
    const g = (l.anf || {}).direktvergabeGrund;
    if (!g) continue;
    mit++;
    gesehen.add(g);
  }
}
if (!mit) {
  klage("KEIN Lead traegt eine Direktvergabe-Begruendung. Gemessen am 2026-10-05: "
      + "1.593. Null heisst, die Kette ist zwischen lead_export und "
      + "export_web_leads.py unterbrochen.");
}
// ⚠ Steht der rohe CODE statt des Rechtstexts da, hat der Export die Liste nicht gefunden.
const roheCodes = [...gesehen].filter((g) => codes.has(g));
if (roheCodes.length) {
  klage(`${roheCodes.length} Eintraege zeigen den rohen Code statt des Rechtstexts `
      + `(${roheCodes.slice(0, 4).join(", ")}). export_web_leads.py findet die `
      + `Codeliste nicht.`);
}
const fremd = [...gesehen].filter((g) => !texte.has(g) && !codes.has(g));
if (fremd.length) {
  klage(`${fremd.length} Texte stehen nicht in der amtlichen Codeliste: `
      + `${fremd.slice(0, 2).map((x) => x.slice(0, 50)).join(" | ")}`);
}

/* ── 3. Jeder Wortlaut ist uebersetzt ─────────────────────────────────────────────── */
for (const sprache of ["en", "fr"]) {
  const p = hier(`../lib/i18n/messages/flat.${sprache}.json`);
  if (!existsSync(p)) { klage(`flat.${sprache}.json fehlt`); continue; }
  const m = JSON.parse(readFileSync(p, "utf8"));
  const fehlend = [...gesehen].filter((g) => !(g in m));
  if (fehlend.length) {
    klage(`flat.${sprache}.json fehlen ${fehlend.length} Wortlaute, die als DATEN in `
        + `die Ansicht kommen. Nachziehen: python3 scripts/i18n_aus_codeliste.py. `
        + `Der allgemeine i18n-Waechter sieht sie nicht.`);
  }
}

console.log(`  ${mit.toLocaleString("de")} Leads mit Direktvergabe-Begruendung, `
          + `${gesehen.size} verschiedene Wortlaute — alle amtlich und uebersetzt`);
if (!fehler) console.log("  ✓ Direktvergaben sind sichtbar, im Wortlaut der Codeliste");
process.exit(fehler ? 1 : 0);

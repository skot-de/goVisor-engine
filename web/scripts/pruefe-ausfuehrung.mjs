// Sieht der Nutzer die Ausfuehrungsbedingungen — und wird die VORBEHALTENE als
// Ausschluss gezeigt, nicht als Hinweis?
//
// WARUM ES DIESE PRUEFUNG GIBT. Die Bedingungen kommen seit der Parser-Aenderung vom
// 2026-10-05 aus `requirements` (vorher waren sie in `attributes` nicht zuzuordnen).
// Die Kette hat vier Glieder: Parser → Silber → `_execution_terms_sql` →
// `export_web_leads.py` → `explorerCore.js`.
//
// ⚠ DER WICHTIGSTE FALL IST NICHT „wird angezeigt", SONDERN „wie". Bei
// `reserved-execution=yes` ist der Auftrag geschuetzten Werkstaetten oder
// Sozialunternehmen vorbehalten — ein gewoehnlicher Bieter kann gar nicht mitbieten.
// Das neben einer E-Rechnungspflicht mit demselben freundlichen „i" zu zeigen, waere
// eine Verharmlosung, die jemanden Arbeit an einem Angebot kostet, das er nie abgeben
// durfte. Es muss das Ausschlusszeichen tragen.
//
// ⚠ Und: nur FORDERNDE Auspraegungen gehoeren angezeigt. „E-Rechnung erlaubt" oder
// „nicht vorbehalten" ist die Abwesenheit einer Bedingung und stuende bei fast jedem
// Lead als Rauschen.
import { readFileSync, readdirSync, existsSync } from "node:fs";

const hier = (p) => new URL(p, import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

/* ── 1. Verhaltensbasiert: den Block schneiden und rendern ────────────────────────── */
const core = readFileSync(hier("../lib/explorerCore.js"), "utf8");
const anker = core.indexOf("const EIG = {");
const ende = core.indexOf("if(!rows.length) return '';", anker);
if (anker < 0 || ende < 0) {
  klage("Anforderungsblock in explorerCore.js nicht gefunden.");
} else {
  const quelle = core.slice(anker, ende);
  const bauen = (anf) => new Function("a", "tk", "esc", "userProfile",
    `${quelle}\nreturn rows.join("");`)(anf, (s) => s, (s) => String(s ?? ""), null);

  const vorbehalten = bauen({ ausfuehrung: [
    { was: "vorbehalten", text: "Nur für Werkstätten oder Sozialunternehmen" }] });
  const rechnung = bauen({ ausfuehrung: [
    { was: "E-Rechnung Pflicht", text: "Elektronische Rechnungsstellung ist verlangt" }] });
  const leer = bauen({});

  if (!/vorbehalten/.test(vorbehalten)) {
    klage("Eine vorbehaltene Ausfuehrung erscheint gar nicht. Das ist der Fall, der "
        + "einen Bieter von vornherein ausschliesst.");
  }
  // Das Ausschlusszeichen ist `mk n` mit &#10007;, das Hinweiszeichen `mk i`.
  const istSperre = /class="mk n"/.test(vorbehalten);
  if (!istSperre) {
    klage("Die vorbehaltene Ausfuehrung traegt NICHT das Ausschlusszeichen (`mk n`). "
        + "Sie sieht damit aus wie ein Hinweis, obwohl der Bieter nicht mitbieten "
        + "darf — das kostet ihn die Arbeit an einem unmoeglichen Angebot.");
  }
  if (/class="mk n"/.test(rechnung)) {
    klage("Die E-Rechnungspflicht traegt das AUSSCHLUSSzeichen. Sie ist eine Auflage, "
        + "kein Ausschluss — so verliert das Zeichen seine Bedeutung.");
  }
  if (/Ausführung/.test(leer)) {
    klage("Ohne Bedingungen erscheint trotzdem eine Zeile.");
  }
}

/* ── 2. Die Daten tragen es, und nur das Fordernde ────────────────────────────────── */
const daten = hier("../data/");
if (!existsSync(daten)) {
  console.log("  … web/data fehlt — uebersprungen.");
  process.exit(fehler ? 1 : 0);
}
//: Diese Auspraegungen sind ANFORDERUNGEN. Alles andere ist deren Abwesenheit.
const ERWARTET = new Set(["vorbehalten", "E-Rechnung Pflicht", "Geheimhaltung",
                          "E-Katalog Pflicht", "E-Signatur Pflicht"]);
let mit = 0, sperren = 0;
const arten = new Map();
for (const f of readdirSync(daten).filter((x) => /^leads-(?!fristen).*\.json$/.test(x))) {
  const roh = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
  for (const l of (Array.isArray(roh) ? roh : roh.leads || [])) {
    const xs = (l.anf || {}).ausfuehrung;
    if (!xs || !xs.length) continue;
    mit++;
    for (const x of xs) {
      arten.set(x.was, (arten.get(x.was) || 0) + 1);
      if (x.was === "vorbehalten") sperren++;
    }
  }
}
if (!mit) {
  klage("KEIN Lead traegt eine Ausfuehrungsbedingung. Entweder ist das Silber noch "
      + "nicht mit dem neuen Parser gebaut, oder die Kette ist unterbrochen.");
} else {
  const fremd = [...arten.keys()].filter((k) => !ERWARTET.has(k));
  if (fremd.length) {
    klage(`Unerwartete Auspraegungen: ${fremd.join(", ")}. Entweder traegt die Quelle `
        + `ein neues Vokabular — dann gehoert es in _AUSFUEHRUNG und hierher — oder `
        + `es wird etwas angezeigt, das keine Anforderung ist.`);
  }
  /* ── 3. Uebersetzt? Diese Texte kommen als DATEN, der i18n-Waechter sieht sie nicht. */
  for (const sprache of ["en", "fr"]) {
    const p = hier(`../lib/i18n/messages/flat.${sprache}.json`);
    if (!existsSync(p)) { klage(`flat.${sprache}.json fehlt`); continue; }
    const m = JSON.parse(readFileSync(p, "utf8"));
    const fehlend = [...arten.keys()].filter((k) => !(k in m));
    if (fehlend.length) {
      klage(`flat.${sprache}.json fehlen: ${fehlend.join(", ")}`);
    }
  }
}

console.log(`  ${mit.toLocaleString("de")} Leads mit Ausfuehrungsbedingungen, `
          + `${sperren.toLocaleString("de")} davon vorbehalten, `
          + `${arten.size} Auspraegungen`);
if (!fehler) console.log("  ✓ Bedingungen sichtbar, Vorbehalt als Ausschluss markiert");
process.exit(fehler ? 1 : 0);

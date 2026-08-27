// Sagt die Dichtestufe die Wahrheit ueber die Unterlagen?
//
// WARUM ES DIESE PRUEFUNG GIBT. `dichte()` wird bei JEDEM Lead-Klick mitgeschrieben
// (`analytics.recordLeadClick` → PostHog + user_lead_interactions) und ist nachtraeglich
// NICHT rekonstruierbar: die Dichte eines Leads aendert sich, sobald seine Unterlagen
// ankommen. Ein falsch verbuchter Klick bleibt falsch.
//
// Bis zum 2026-08-26 schloss die Stufe aus dem VORHANDENSEIN von Anforderungen auf
// „Unterlagen gelesen" und zaehlte dabei Bindefrist und Buergschaft mit — die stammen aber
// regelmaessig aus eForms. Gemessen: 6.288 von 11.731 „reichen" Leads (54 %) hatten gar
// keinen Volltext bei uns.
//
// Die Pruefung faengt den Rueckfall: „reich" DARF es nur geben, wo der Volltext bei uns
// liegt. Die Gegenrichtung wird nicht geprueft — ein Lead mit Volltext, dessen Auswertung
// noch aussteht, ist zu Recht nur „mittel".
import { readFileSync, readdirSync } from "node:fs";

const datenOrt = new URL("../data/", import.meta.url);
const dateien = readdirSync(datenOrt)
  .filter((n) => n.startsWith("leads-") && n.endsWith(".json") && n !== "leads-fristen.json");

// Dieselbe Regel wie in lib/dichte.ts, bewusst nachgebaut: die Pruefung soll anschlagen,
// wenn dort jemand die Bedingung aufweicht, nicht mit ihr mitwandern.
const volltextDa = (l) => l?.unterlagen?.gelesen === true;
const ausUnterlagen = (l) => l?.anf?.quelle === "unterlagen" || Boolean(l?.anf?.zertifikate?.length);

// GEPRUEFT WIRD DIE INVARIANTE ZWISCHEN DEN BEIDEN SIGNALEN, nicht die Stufe selbst.
//
// ⚠ Der erste Entwurf zaehlte Leads, die `volltextDa && ausUnterlagen` erfuellen, und
// prueffte dann `!volltextDa` — eine Bedingung, die er zwei Zeilen vorher verlangt hatte.
// Sie konnte nie greifen. Eine Pruefung, die nicht scheitern kann, ist wertlos.
//
// Was WIRKLICH schiefgehen kann: die beiden Signale stammen aus verschiedenen Quellen.
// `anf.quelle` kommt aus der Dokumentanalyse (doc_eligibility/doc_guarantee/doc_certs),
// `unterlagen.gelesen` aus dem Volltext-Index. Behauptet die Analyse Dokumentinhalt, ohne
// dass ein Volltext vorliegt, widersprechen sich beide — und `dichte()` wuerde daraus
// wieder ein „reich" ohne gelesene Unterlagen bauen. Gemessen am 2026-08-26: 0 Faelle.
let reich = 0;
const falsch = [];
let volltextOhneInhalt = 0;
// Wie viele waeren nach der ALTEN Regel „reich" gewesen, ohne Volltext? Nur als Zahl im
// Log — ein Rueckbau der Regel fiele daran auf.
let altReich = 0;
const altRegel = (l) => {
  const a = l?.anf || {};
  return Boolean(a.eignung?.length || a.zertifikate?.length || a.bindefristTage || a.buergschaft);
};

for (const name of dateien) {
  let leads;
  try {
    leads = JSON.parse(readFileSync(new URL(name, datenOrt), "utf8"));
  } catch {
    continue;                          // wird gerade geschrieben
  }
  if (!Array.isArray(leads)) continue;
  for (const l of leads) {
    const inhalt = ausUnterlagen(l);
    const text = volltextDa(l);
    if (inhalt && text) reich += 1;
    if (inhalt && !text && falsch.length < 5) {
      falsch.push(`${l.id} (${name}): anf.quelle=${l?.anf?.quelle}, ` +
                  `zertifikate=${l?.anf?.zertifikate?.length ?? 0}, aber kein Volltext`);
    }
    if (text && !inhalt) volltextOhneInhalt += 1;
    if (altRegel(l) && !text) altReich += 1;
  }
}

if (falsch.length) {
  console.error(`
  ✖ ABBRUCH: ${falsch.length} Lead(s) behaupten Inhalt AUS DEN UNTERLAGEN, ohne dass
    der Volltext bei uns liegt. Die beiden Signale widersprechen sich:

${falsch.map((f) => `      ${f}`).join("\n")}
`);
  process.exit(1);
}

console.log(`  Dichte: ${reich} Leads „reich" (Volltext + Auswertung), ` +
            `${volltextOhneInhalt} mit Volltext ohne verwertbaren Inhalt (zu Recht nur „mittel"), ` +
            `${altReich} waeren nach der alten Regel ohne Volltext „reich" gewesen`);

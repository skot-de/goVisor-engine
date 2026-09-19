/* Eine Marke je Zeile, und nur wenn sie neuer ist als der letzte Besuch.
 *
 * ⚠ WARUM DIESE SONDE DEN ECHTEN CODE FAEHRT. Die Regel hat vier Eingaenge (Ereignisart,
 * Ereignisdatum, Veroeffentlichungsdatum, Stichtag) und genau einen Ausgang. Eine
 * Wortpruefung koennte nur sehen, DASS die Bedingungen dastehen, nicht ob sie zusammen das
 * Richtige ergeben — und der gefaehrlichste Fall ist der, in dem ZWEI Marken erscheinen
 * oder gar keine.
 */
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const T = mkdtempSync(join(tmpdir(), "gv-frische-"));
let fehler = 0;
const sage = (ok, t) => { if (!ok) fehler++; console.log(`  ${ok ? "✓" : "✗"} ${t}`); };

try {
  /* explorerCore importiert `./i18n` (ein Verzeichnis) — unter node nicht aufloesbar.
     Deshalb die Marke samt ihrer Abhaengigkeiten herausschneiden statt das Modul zu laden;
     dieselbe Technik benutzen die uebrigen Sonden fuer diese Datei. */
  const src = readFileSync(join(WEB, "lib", "explorerCore.js"), "utf8");
  const i = src.indexOf("const AKT_WORT");
  const j = src.indexOf("\n}", src.indexOf("function frischeMarke"));
  if (i < 0 || j < 0) { console.log("  ✗ frischeMarke() gibt es nicht mehr"); process.exit(1); }
  const teil = src.slice(i, j + 2);

  const js = `
    const tk = (s, v) => v ? Object.entries(v).reduce((a,[k,x]) => a.replace('{'+k+'}', x), s) : s;
    const esc = (s) => String(s ?? "");
    let stichtagBesuch = null;
    export function setStichtag(t){ stichtagBesuch = t || null; }
    ${teil}
    export { frischeMarke };
  `;
  writeFileSync(join(T, "m.js"), js);
  const m = await import(join(T, "m.js"));

  const marken = (h) => (h.match(/class="akttag/g) || []).length;
  m.setStichtag("2026-09-10");

  // 1 ── Nichts passiert, nichts steht da.
  sage(m.frischeMarke({ pub: "2026-09-01" }) === "",
       "ein alter Vorgang ohne Ereignis traegt keine Marke");

  // 2 ── Neu seit dem Besuch.
  const neu = m.frischeMarke({ pub: "2026-09-15" });
  sage(neu.includes("akt-neu") && marken(neu) === 1, "juenger als der Besuch → genau eine Marke „neu\"");

  // 3 ── Ereignis schlaegt Veroeffentlichung, und es bleibt EINE Marke.
  const beides = m.frischeMarke({ pub: "2026-09-15", aktualitaet: { art: "frist", am: "2026-09-17", fristNeu: "2026-10-06" } });
  sage(marken(beides) === 1, `Ereignis UND neu ergeben eine Marke, nicht zwei (waren ${marken(beides)})`);
  sage(beides.includes("06.10."), "die Fristmarke traegt das neue Datum, nicht nur das Wort");

  // 4 ── Nachricht verfaellt, Zustand nicht.
  //
  // ⚠ DIESER FALL HAT DIE REGEL KORRIGIERT. Die erste Fassung liess jedes Ereignis vor dem
  // letzten Besuch verfallen — auch die Aufhebung. Dann steht „neu" ueber einer
  // Ausschreibung, auf die niemand mehr bieten kann. Eine Fristaenderung ist eine
  // Nachricht und irgendwann gelesen; eine Aufhebung ist ein Zustand und bleibt.
  sage(m.frischeMarke({ pub: "2026-09-15", aktualitaet: { art: "frist", am: "2026-09-02", fristNeu: "2026-09-30" } })
         .includes("akt-neu"),
       "eine Fristmeldung VOR dem letzten Besuch ist gelesen");
  const altAuf = m.frischeMarke({ pub: "2026-09-15", aktualitaet: { art: "aufgehoben", am: "2026-09-02" } });
  sage(altAuf.includes("akt-aufgehoben") && marken(altAuf) === 1,
       "eine Aufhebung bleibt sichtbar, auch wenn sie vor dem letzten Besuch war");

  // 5 ── Aufhebung wird als solche benannt.
  const auf = m.frischeMarke({ aktualitaet: { art: "aufgehoben", am: "2026-09-18", text: "Aufhebung" } });
  sage(auf.includes("akt-aufgehoben") && auf.includes("aufgehoben"), "eine Aufhebung heisst aufgehoben");

  // 6 ── Unbekannte Art faellt auf „geaendert", nicht auf eine tote CSS-Klasse.
  const wirr = m.frischeMarke({ aktualitaet: { art: "voellig-neue-art", am: "2026-09-18" } });
  sage(wirr.includes("akt-geaendert"),
       "eine unbekannte Ereignisart wird zu „geaendert\" statt zu einer Klasse ohne Stil");

  // 7 ── Erster Besuch: kein Stichtag, dann darf nur ein EREIGNIS sprechen.
  m.setStichtag(null);
  sage(m.frischeMarke({ pub: "2026-09-18" }) === "",
       "ohne Stichtag wird nicht jede frische Zeile markiert (das waere wieder ein Teppich)");
  sage(marken(m.frischeMarke({ aktualitaet: { art: "frist", am: "2026-09-18", fristNeu: "2026-10-01" } })) === 1,
       "ohne Stichtag zeigt ein Ereignis trotzdem seine Marke");
} finally {
  rmSync(T, { recursive: true, force: true });
}

if (fehler) { console.log(`\n⛔ ${fehler} Befund(e)`); process.exit(1); }
console.log("\n✓ Eine Marke je Zeile, und nur was seit dem letzten Besuch passiert ist");

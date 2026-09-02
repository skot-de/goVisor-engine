/* Sonde: was rendert der Bieterfragen-Block wirklich, auf allen echten Daten?
 *
 * ⚠ SIE SCHNEIDET DIE ECHTE FUNKTION AUS, statt sie abzuschreiben. Die Nachbarsonde
 * `pruefe-marktwert.mjs` warnt selbst davor („eine Abschrift der Rechnung geht gruen, waehrend
 * die benutzte Fassung falsch ist") — und ist dann doch eine Abschrift. Hier wird
 * `renderBieterfragen` aus `lib/explorerCore.js` gelesen und ausgefuehrt; faellt die Funktion
 * weg oder aendert sie ihren Namen, schlaegt die Sonde fehl statt still weiterzulaufen.
 *
 * ⚠ UND SIE PRUEFT DIE ESCAPUNG AUF ECHTEM TEXT. Die Abschnitte stammen aus fremden
 * Vergabeunterlagen; ein „<" oder „&" darin ist keine Theorie. Der Browser-Durchgang war an
 * diesem Tag nicht moeglich (die Anmeldung ging beim Neustart des Dev-Servers verloren), also
 * traegt diese Sonde die Last.
 *
 *     node web/scripts/pruefe-bieterfragen.mjs
 */
import { readFileSync } from "node:fs";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
const start = core.indexOf("function renderBieterfragen(");
if (start < 0) throw new Error("renderBieterfragen fehlt in explorerCore.js");
const ende = core.indexOf("\n}", start) + 2;
const quelle = core.slice(start, ende);

const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const tk = (k, v) => String(k).replace(/\{(\w+)\}/g, (_, n) => (v && v[n] != null ? v[n] : "{" + n + "}"));
const render = new Function("esc", "tk", quelle + "; return renderBieterfragen;")(esc, tk);

const daten = JSON.parse(readFileSync(new URL("../data/bieterfragen.json", import.meta.url), "utf8"));
let geprueft = 0, mitMehr = 0;
const roh = [], leer = [];
for (const [id, b] of Object.entries(daten)) {
  const html = render({ lbFragen: b });
  geprueft++;
  if (!html) { leer.push(id); continue; }
  if (html.includes("Auszug,")) mitMehr++;
  // ⚠ Alles zwischen den Tags muss escaped sein. Ein rohes „<" im Text kaeme hier durch.
  const innen = html.replace(/<[^>]*>/g, " ");
  if (/[<>]/.test(innen)) roh.push(id);
  const m = html.match(/Auszug, (\d+) von (\d+)/);
  if (m && (Number(m[1]) !== b.auszug.length || Number(m[2]) !== b.n))
    throw new Error(id + ": Auszug-Zahlen stimmen nicht");
}
if (roh.length) throw new Error("ungeschuetzte Zeichen im Markup bei: " + roh.slice(0, 5).join(", "));
if (leer.length) throw new Error("kein Markup trotz Daten bei: " + leer.slice(0, 5).join(", "));
console.log("  " + geprueft + " Vorgaenge gerendert · " + mitMehr + " mit Auszug-Hinweis · 0 ungeschuetzte Zeichen");
console.log("  leerer Fall: " + (render({}) === "" ? "gibt nichts aus ✓" : "⛔ rendert trotz fehlender Daten"));

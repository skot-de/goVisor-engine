/* Sonde: was meldet der Fassungs-Block wirklich, auf allen echten Daten?
 *
 * ⚠ Sie schneidet `renderUnterlagenstand` aus `lib/explorerCore.js` heraus und fuehrt es aus,
 * statt die Logik abzuschreiben — dieselbe Regel wie bei `pruefe-bieterfragen.mjs`.
 *
 *     node web/scripts/pruefe-unterlagenstand.mjs
 */
import { readFileSync } from "node:fs";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
const start = core.indexOf("function renderUnterlagenstand(");
if (start < 0) throw new Error("renderUnterlagenstand fehlt in explorerCore.js");
const quelle = core.slice(start, core.indexOf("\n}", start) + 2);

const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const tk = (k, v) => String(k).replace(/\{(\w+)\}/g, (_, n) => (v && v[n] != null ? v[n] : "{" + n + "}"));
const render = new Function("esc", "tk", quelle + "; return renderUnterlagenstand;")(esc, tk);

const daten = JSON.parse(readFileSync(new URL("../data/unterlagenstand.json", import.meta.url), "utf8"));
let n = 0, mitNamen = 0;
const roh = [], stumm = [];
for (const [id, u] of Object.entries(daten)) {
  const html = render({ lbStand: u });
  n++;
  if (!html) { stumm.push(id); continue; }
  if (u.geaendert.length) mitNamen++;
  const innen = html.replace(/<[^>]*>/g, " ");
  if (/[<>]/.test(innen)) roh.push(id);
  // ⚠ Die Fassungsnummern muessen im Text stehen, sonst ist die Meldung nicht pruefbar.
  if (!innen.includes(String(u.version)) || !innen.includes(String(u.vorige)))
    throw new Error(id + ": Fassungsnummern fehlen im Text");
}
if (roh.length) throw new Error("ungeschuetzte Zeichen bei: " + roh.slice(0, 5).join(", "));
if (stumm.length) throw new Error("kein Markup trotz Aenderung bei: " + stumm.slice(0, 5).join(", "));
console.log("  " + n + " Vorgaenge gerendert · " + mitNamen + " mit Dateinamen · 0 ungeschuetzte Zeichen");
console.log("  ohne Aenderung: " + (render({ lbStand: { nGeaendert: 0, nNeu: 0, nWeg: 0 } }) === ""
  ? "schweigt ✓" : "⛔ meldet trotzdem"));

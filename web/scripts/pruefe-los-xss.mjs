// Los-Titel dürfen kein HTML ins Dokument tragen — GERECHNET mit dem echten Renderer.
//
// ⚠ DER BEFUND (2026-09-28, Pentest). Der Los-Abschnitt in `renderUebersicht` setzt denselben
// Los-Titel dreimal in HTML, das per `dangerouslySetInnerHTML` in die Seite geht. An einer
// Stelle war er escaped (`esc(x.titel)` in der Tabellenzeile), an zwei nicht:
//   · der „Für euch relevant ist"-Hinweis  (l.bestLot.titel / l.bestLot.region)
//   · die Einstiegsschwelle                 (l.lose[minI].titel)
// Los-Titel sind auftraggeberseitig geschriebene Ausschreibungsdaten (eForms `lot_title`,
// Portal-Trefferlisten); der Export bereinigt kein HTML. Ein Titel `<img src=x onerror=…>`
// wäre also im Kontext jedes angemeldeten Nutzers gelaufen, der den Lead öffnet.
//
// ⚠ WARUM AUS DER ECHTEN QUELLE GESCHNITTEN. Der Renderer UND das echte `esc` werden aus
// `explorerCore.js` extrahiert, nicht abgeschrieben. Nimmt jemand das `esc(` an einer der
// Stellen wieder heraus — oder schwächt er `esc` selbst ab — liefert der extrahierte Code
// das rohe `<img` und dieser Test fällt. Ein Test gegen eine Abschrift bewiese nichts (s.
// die Herkunfts-/Ratenbremse-Sonden, die aus demselben Grund die echte Fassung laden).
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const core = readFileSync(new URL("../lib/explorerCore.js", import.meta.url), "utf8");
let fehler = 0;
const sage = (ok, t) => { if (!ok) fehler++; console.log(`  ${ok ? "✓" : "✗"} ${t}`); };

// 1) Das echte `esc` herausschneiden.
const iEsc = core.indexOf("const esc = s => String(s == null");
const eEsc = core.indexOf("&#39;');", iEsc);
if (iEsc < 0 || eEsc < 0) { console.log("  ✗ esc-Definition nicht gefunden"); process.exit(1); }
const escQuelle = core.slice(iEsc, eEsc + "&#39;');".length);

// 2) Die Los-IIFE herausschneiden (die (()=>{ … })-Arrow, ohne den sofortigen Aufruf).
const iLose = core.indexOf("l.lose && l.lose.length>1 ? (()=>{");
const iFn = core.indexOf("(()=>{", iLose);
const iEnd = core.indexOf("})() : ''}", iFn);
if (iLose < 0 || iFn < 0 || iEnd < 0) { console.log("  ✗ Los-Abschnitt nicht gefunden"); process.exit(1); }
// Die Arrow schliesst im Original `l` aus `renderUebersicht(l)` ein und nimmt kein Argument
// (`(()=>{…})()`). Für den isolierten Aufruf machen wir `l` zum Parameter: `((l)=>{…})`.
const fnQuelle = "((l)=>{" + core.slice(iFn + "(()=>{".length, iEnd) + "})";

const T = mkdtempSync(join(tmpdir(), "gv-losxss-"));
try {
  writeFileSync(join(T, "m.mjs"), `
    const tk = (s, v) => v ? Object.entries(v).reduce((a,[k,x]) => a.replaceAll('{'+k+'}', String(x)), s) : s;
    ${escQuelle}
    const renderLose = ${fnQuelle};
    export { renderLose };
  `);
  const { renderLose } = await import(join(T, "m.mjs"));

  // Jedes datengetragene Feld des Los-Abschnitts bekommt eine eigene Nutzlast, damit der
  // Test nicht nur den Titel sieht: Titel, Region, Wert und Dauer stammen alle aus den
  // Vergabedaten und wurden alle einmal roh gerendert.
  const TITEL = '<img src=x onerror=alert(document.cookie)>';
  const REGION = '<svg onload=alert(1)>';
  const WERT = '<b onmouseover=alert(2)>100</b>';
  const DAUER = '<i onclick=alert(3)>12 Mon.</i>';
  // ⚠ Das kleinste Los MUSS deterministisch der TITEL-Träger sein: die Einstiegsschwelle
  // zeigt `l.lose[minI].titel`, und `minI` kommt aus den Ziffern von `wert`. Eine HTML-
  // Nutzlast im `wert` des min-Loses würde über ihre Ziffern (`alert(2)` → „2") den Index
  // verschieben — deshalb trägt Los 1 einen sauber kleinsten Zahlwert, die `wert`-Nutzlast
  // sitzt in Los 2.
  const l = {
    bestLot: { nr: 1, titel: TITEL, region: REGION },
    lose: [
      { nr: 1, titel: TITEL, wert: '100 €', dauer: DAUER, region: REGION },
      { nr: 2, titel: 'harmlos', wert: WERT, dauer: '12 Mon.', region: 'Berlin' },
    ],
  };
  const html = renderLose(l);

  // KEIN gefährliches Roh-Tag darf im Ergebnis stehen — egal aus welchem Feld.
  // (Der escapte Text `&lt;img … onerror=…&gt;` ist harmlos und DARF `onerror=` als
  // Zeichenkette enthalten; geprüft wird deshalb das TAG `<img `, nicht die Teilzeichenkette.)
  for (const tag of ['<img ', '<svg ', '<b ', '<i ', '<script']) {
    sage(!html.includes(tag), `kein rohes ${tag}… aus einem Los-Feld im HTML`);
  }
  // Der Inhalt ist noch DA, nur escaped — sonst hätten wir ihn bloss verschluckt.
  sage(html.includes('&lt;img src=x onerror=alert(document.cookie)&gt;'),
       "der Titel steht escaped im HTML (Einstiegsschwelle + relevantes Los + Zeile)");
  sage(html.includes('&lt;svg onload=alert(1)&gt;'), "die Region steht escaped im HTML");
  // Der Titel taucht an drei Stellen auf (relevantes Los, Einstiegsschwelle, Zeile) —
  // roh 0×, escaped ≥3×.
  const roh = (html.match(/<img /g) || []).length;
  const escapt = (html.match(/&lt;img /g) || []).length;
  sage(roh === 0 && escapt >= 3, `Titel 0× roh, ${escapt}× escaped (erwartet ≥3)`);

  console.log(fehler ? `\n✗ ${fehler} Fehler` : "\n✓ Los-Titel tragen kein HTML ins Dokument.");
  process.exit(fehler ? 1 : 0);
} finally {
  rmSync(T, { recursive: true, force: true });
}

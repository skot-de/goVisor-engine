// Kein rohes Datenfeld direkt im HTML — der dauerhafte Nachfolger des XSS-Audits.
//
// ⚠ WARUM. `explorerCore.js` (und die eine innerHTML-Stelle in ExplorerShell) bauen HTML als
// Zeichenkette, die per `dangerouslySetInnerHTML` in die Seite geht. Die Datenfelder darin
// stammen aus TED/Portalen — nicht vertrauenswuerdig. Beim Pentest 2026-09-28 war `esc()`
// ueber die Datei inkonsistent gesetzt; ein Vollaudit hat die Luecken geschlossen. Diese
// Sonde haelt den Stand: sie parst den ECHTEN Quelltext (TypeScript-AST) und meldet, sobald
// ein Datenfeld OHNE Umschliessung in HTML landet.
//
// WAS SIE PRUEFT: jede `${…}`-Interpolation innerhalb eines HTML-Template-Literals (oder
// eines darin geschachtelten). Ein DIREKTER Zugriff `x.feld` / `x[e]` auf ein Datenobjekt
// gilt als Verstoss — es sei denn, das Feld steht in `SICHERE_FELDER` (nachweislich Zahl,
// Enum, ID, Code oder Datum, kein Freitext).
//
// ⚠ WAS SIE BEWUSST NICHT LEISTET (ehrliche Grenze):
//   · Funktionsaufrufe gelten als sicher. `esc(x)`, `iv(x)`, `b(x)` usw. escapen (geprueft),
//     und ein Helfer ist auditierter Code. Ein NEUER Helfer, der roh rendert, wird hier
//     NICHT gefangen — die Helfer b/n/na/bnum escapen deshalb seit dem Audit intern.
//   · Nur Template-Literale werden gesehen, keine `+`-Verkettung zu HAND-HTML.
//   · Nur explorerCore.js + ExplorerShell.tsx. DetailPanel/LeadTable/StrategieView speisen
//     sich aus explorerCore oder React-JSX (das escaped selbst).
//
// EINEN VERSTOSS BEHEBEN: das Feld mit `esc(...)` umschliessen. Ist es nachweislich eine
// Zahl/ein Enum/eine ID/ein Datum (kein Freitext), stattdessen unten in `SICHERE_FELDER`
// eintragen — mit dem Wissen, dass damit AUCH jedes kuenftige Feld gleichen Namens
// ungeprueft durchginge. Deshalb stehen dort nur eindeutige, beschreibende Namen.
import ts from "typescript";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const DATEIEN = ["lib/explorerCore.js", "components/explorer/ExplorerShell.tsx"];

// Nachweislich kein Freitext: Zahl, Zaehler, Prozent, Enum, ID, Code, Datum. Jeder Eintrag
// ist eine bewusste Entscheidung (s. Kopf). Freitext-Namen (titel, name, text, label,
// beschreibung, region, ort, portal, grund, wert, zeitraum, laufzeit, n, w …) stehen hier
// NICHT — die gehoeren durch esc().
const SICHERE_FELDER = new Set([
  // IDs / Index
  "id", "merk", "_i",
  // Codes
  "cpv", "cpv4",
  // Enums / Slugs
  "access", "cls", "kind", "land", "naturKat", "rahmen", "relevanz", "src",
  "struktur", "stufe", "trend", "wechsel",
  // Zahlen / Zaehler / Prozent
  "bekannt", "below", "bieter", "bindefristTage", "categories", "coverage", "deckung",
  "firmen", "gewonnen", "kunden", "lbFiles", "loseMaxAngebot", "loseMaxZuschlag",
  "marktanteil", "netzDeckung", "netzSuchend", "nr", "offen", "pct", "rang", "share",
  "siege", "subQuote", "top3", "total", "vergaben", "wins", "wins36",
  // Datum / Zeitstempel
  "seit", "ts",
]);

const KONST = (t) => !!t && (/^[A-Z][A-Z0-9_]*$/.test(t)
  || ["Math", "Number", "JSON", "Date", "Object", "Array"].includes(t));

function wurzel(n) {
  let c = n;
  while (c) {
    if (ts.isPropertyAccessExpression(c) || ts.isElementAccessExpression(c) || ts.isCallExpression(c)) c = c.expression;
    else if (ts.isParenthesizedExpression(c) || ts.isNonNullExpression(c)) c = c.expression;
    else break;
  }
  return ts.isIdentifier(c) ? c.text : null;
}

const benutzteFelder = new Set();

/** Ist dieser Ausgabe-Ausdruck sicher (kein rohes Datenfeld)? */
function sicher(n) {
  if (!n) return true;
  if (ts.isParenthesizedExpression(n) || ts.isNonNullExpression(n)) return sicher(n.expression);
  if (ts.isTemplateExpression(n)) return true;   // eigene Spans werden separat geprueft
  if (ts.isCallExpression(n)) return true;        // Funktion = auditierter Code (s. Grenze oben)
  if (ts.isIdentifier(n)) return true;            // lokale Variablen sind abgeleitet
  if (ts.isConditionalExpression(n)) return sicher(n.whenTrue) && sicher(n.whenFalse);
  if (ts.isPrefixUnaryExpression(n)) return true; // !x, -x → bool/Zahl
  if (ts.isBinaryExpression(n)) {
    const op = n.operatorToken.kind;
    if (op === ts.SyntaxKind.AmpersandAmpersandToken) return sicher(n.right);
    if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken)
      return sicher(n.left) && sicher(n.right);
    const cmp = [ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken,
      ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
      ts.SyntaxKind.LessThanToken, ts.SyntaxKind.LessThanEqualsToken,
      ts.SyntaxKind.GreaterThanToken, ts.SyntaxKind.GreaterThanEqualsToken];
    if (cmp.includes(op)) return true;            // Vergleich → bool
    return sicher(n.left) && sicher(n.right);     // Arithmetik u. a.
  }
  if (ts.isPropertyAccessExpression(n)) {
    if (n.name.text === "length") return true;
    if (KONST(wurzel(n))) return true;            // Konstanten-Map / Math etc.
    if (SICHERE_FELDER.has(n.name.text)) { benutzteFelder.add(n.name.text); return true; }
    return false;
  }
  if (ts.isElementAccessExpression(n)) return KONST(wurzel(n));
  if (ts.isArrayLiteralExpression(n)) return n.elements.every(sicher);
  return true;                                     // Literale, Keywords etc.
}

const verstoesse = [];
for (const rel of DATEIEN) {
  const src = readFileSync(join(WEB, rel), "utf8");
  const sf = ts.createSourceFile(rel, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const walk = (n, inHtml) => {
    let html = inHtml;
    if (ts.isTemplateExpression(n)) {
      if (inHtml || n.getText(sf).includes("<")) {
        html = true;
        for (const span of n.templateSpans) {
          if (!sicher(span.expression)) {
            const { line } = sf.getLineAndCharacterOfPosition(span.expression.getStart(sf));
            verstoesse.push(`${rel}:${line + 1}  ${span.expression.getText(sf).replace(/\s+/g, " ").slice(0, 80)}`);
          }
        }
      }
    }
    ts.forEachChild(n, (c) => walk(c, html));
  };
  walk(sf, false);
}

const stale = [...SICHERE_FELDER].filter((f) => !benutzteFelder.has(f));
if (stale.length) {
  console.log(`  Hinweis: ${stale.length} SICHERE_FELDER kommen nicht mehr vor (kein Fehler): ${stale.join(", ")}`);
}
if (verstoesse.length) {
  console.log(`✗ ${verstoesse.length} rohe(s) Datenfeld(er) im HTML — mit esc() umschliessen (oder als Zahl/Enum/ID in SICHERE_FELDER eintragen):`);
  for (const v of verstoesse) console.log("  " + v);
  process.exit(1);
}
console.log("✓ Kein rohes Datenfeld direkt im HTML.");

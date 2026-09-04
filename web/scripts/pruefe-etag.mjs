/* Die ETag-Regel des Listenabrufs.
 *
 *     node web/scripts/pruefe-etag.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/etag.js`, keine Abschrift.
 *
 * Warum überhaupt ein Test: ein ETag ist ein Versprechen. Sagt er „unverändert", zeigt der
 * Browser, was er hat — und fragt nicht nach. Ein ETag, der stehen bleibt, während sich die
 * Daten bewegen, ist deshalb schlimmer als gar keiner: er ersetzt eine langsame Antwort
 * durch eine falsche. Bei einem Produkt, das mit Fristen wirbt, ist das die teuerste Ecke.
 */
import { etagAus, unveraendert } from "../lib/etag.js";

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

// ── Die Grundform ──────────────────────────────────────────────────────────────
pruefe("beide Marken stehen im ETag", etagAus("bau", ["abc", "def"]) === '"bau-abc-def"');
pruefe("der Grundraum steht mit drin — sonst teilen sich zwei Branchen einen ETag",
  etagAus("bau", ["abc", "def"]) !== etagAus("it", ["abc", "def"]));

// ── ⚠ DIE FALLE ────────────────────────────────────────────────────────────────
// Fehlt die FUEHRENDE Quelle, darf kein ETag entstehen. Ein fester Ersatzwert erzeugte
// eine Kennung, die stehen bleibt, waehrend sich die Daten bewegen — der Browser bekaeme
// dauerhaft 304 und zeigte Altes als frisch.
pruefe("ohne fuehrende Marke gibt es keinen ETag", etagAus("bau", [null, "def"]) === null);
pruefe("auch bei leerer Zeichenkette nicht", etagAus("bau", ["", "def"]) === null);
pruefe("und ohne Marken ueberhaupt nicht", etagAus("bau", []) === null);

// Eine fehlende NEBEN-Quelle ist dagegen ein normaler Zustand (nicht jeder Grundraum hat
// Zuschlaege) — sie muss aber mitgefuehrt werden, damit der ERSTE Zuschlag den
// Zwischenspeicher bricht.
pruefe("fehlende Nebenquelle wird als 0 mitgefuehrt",
  etagAus("bau", ["abc", null]) === '"bau-abc-0"');
pruefe("der erste Zuschlag aendert den ETag",
  etagAus("bau", ["abc", null]) !== etagAus("bau", ["abc", "x"]));

// ── Der Vergleich ──────────────────────────────────────────────────────────────
pruefe("gleicher ETag → unveraendert", unveraendert('"a-b-c"', '"a-b-c"'));
pruefe("anderer ETag → veraendert", !unveraendert('"a-b-c"', '"a-b-d"'));
pruefe("ohne ETag nie unveraendert", !unveraendert(null, '"a-b-c"'));
pruefe("ohne Anfrage-Kopfzeile nie unveraendert", !unveraendert('"a-b-c"', null));
// Ein Proxy darf `W/` voranstellen, ein Client mehrere senden. Beides zu ignorieren waere
// ein stiller Verlust: der Browser haette die Daten und bekaeme sie trotzdem noch einmal.
pruefe("schwache Kennzeichnung wird erkannt", unveraendert('"a-b-c"', 'W/"a-b-c"'));
pruefe("mehrere Kennungen werden durchsucht",
  unveraendert('"a-b-c"', '"x", W/"a-b-c", "y"'));

console.log(fehler ? `\n${fehler} Pruefung(en) fehlgeschlagen` : "\nalle Pruefungen bestanden");
process.exit(fehler ? 1 : 0);

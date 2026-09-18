/* Waechter: faehrt `mischen` aus `lib/filterMischen.js` gegen die DREI Faelle, die ein
 * gespeicherter Filter in sechs Monaten erlebt. Kein Wortabgleich — die echte Funktion.
 *
 * Warum das ein eigener Waechter ist: der Schaden ist LAUTLOS. Ein alter Filter laedt
 * scheinbar sauber und filtert anders; niemand sieht einen Fehler, alle sehen eine falsche
 * Liste. */
import { mischen } from "../lib/filterMischen.js";

let fehler = 0;
function pruefe(name, ist, soll) {
  const a = JSON.stringify(ist), b = JSON.stringify(soll);
  if (a === b) { console.log(`  ✓ ${name}`); return; }
  console.log(`  ✗ ${name}\n      ist:  ${a}\n      soll: ${b}`);
  fehler++;
}

const VORGABE = { staaten: [], horizon: null, buyer: "", nationwide: false, phases: [] };

pruefe("nimmt, was passt",
  mischen(VORGABE, { staaten: ["DE"], buyer: "Stadt", nationwide: true }),
  { staaten: ["DE"], horizon: null, buyer: "Stadt", nationwide: true, phases: [] });

pruefe("neue Facette behaelt ihren Vorgabewert",
  mischen(VORGABE, { staaten: ["AT"] }).phases, []);

pruefe("entfernte Facette fliegt raus",
  Object.keys(mischen(VORGABE, { staaten: [], gibtsNichtMehr: 42 })).includes("gibtsNichtMehr"), false);

pruefe("umgebaute Facette wird verworfen, nicht uebernommen",
  mischen(VORGABE, { buyer: ["war", "mal", "string"] }).buyer, "");

pruefe("Array gegen Nicht-Array wird verworfen",
  mischen(VORGABE, { staaten: "DE" }).staaten, []);

pruefe("null bleibt erlaubt",
  mischen(VORGABE, { horizon: 12 }).horizon, 12);

pruefe("Unsinn statt Objekt ergibt die reine Vorgabe",
  mischen(VORGABE, "kaputt"), VORGABE);

pruefe("die Vorgabe wird nicht veraendert",
  (() => { const v = { a: [] }; mischen(v, { a: [1] }); return v.a.length; })(), 0);

console.log(fehler ? `\n${fehler} Fehler` : "\nMischung haelt alle Faelle");
process.exit(fehler ? 1 : 0);

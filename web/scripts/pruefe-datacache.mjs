/* Den Zwischenspeicher der Datendateien durchspielen. Läuft mit blossem `node`:
 *     node web/scripts/pruefe-datacache.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/dataCache.js`. Die Uhr wird hereingereicht, damit
 * der Verfall ohne Warten prüfbar ist — ein Test, der `sleep` braucht, wird entweder langsam
 * oder flatterhaft, und wir haben heute schon einen flatterhaften Test im Bestand.
 */
import { erstelleCache } from "../lib/dataCache.js";

let fehler = 0;
const pruefe = (name, ok) => { if (!ok) fehler++; console.log(`${ok ? "ok  " : "FEHL"}  ${name}`); };

let uhr = 1000;
const c = erstelleCache({ maxBytes: 100, ttlMs: 500, jetzt: () => uhr });

c.setze("a", "A", 40);
pruefe("Abgelegtes kommt zurück", c.hole("a") === "A");
pruefe("Unbekanntes ist undefined", c.hole("gibtsnicht") === undefined);

uhr += 499;
pruefe("kurz vor Ablauf noch da", c.hole("a") === "A");
uhr += 2;
pruefe("nach Ablauf weg", c.hole("a") === undefined);
pruefe("Abgelaufenes belegt keinen Platz mehr", c.stand().belegt === 0);

uhr = 1000;
c.leere();
c.setze("a", "A", 40); c.setze("b", "B", 40);
c.hole("a");                       // „a" frisch benutzt → „b" ist der Ältere
c.setze("d", "D", 40);             // 120 > 100 → einer muss weichen
pruefe("das am längsten Ungenutzte weicht (b)", c.hole("b") === undefined);
pruefe("das zuletzt Benutzte bleibt (a)", c.hole("a") === "A");
pruefe("das Neue liegt drin (d)", c.hole("d") === "D");
pruefe("Budget wird eingehalten", c.stand().belegt <= 100);

c.leere();
c.setze("riesig", "X", 5000);
pruefe("was allein zu gross ist, wird gar nicht erst aufgenommen", c.hole("riesig") === undefined);
c.setze("a", "A", 40);
pruefe("und räumt dabei nichts weg", c.hole("a") === "A");

c.leere();
c.setze("a", "A", 40); c.setze("a", "A2", 40);
pruefe("Überschreiben zählt die Bytes nicht doppelt", c.stand().belegt === 40 && c.hole("a") === "A2");

console.log(fehler ? `\n${fehler} Prüfung(en) fehlgeschlagen.` : "\nDer Zwischenspeicher hält sich an seine Regeln.");
process.exit(fehler ? 1 : 0);

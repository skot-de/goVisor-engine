/* Die Herkunftsbestimmung, auf die jede Ratenbremse ihren Zähler stellt.
 *
 *     node web/scripts/pruefe-herkunft.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/clientIp.js`, keine Abschrift.
 *
 * Warum überhaupt ein Test: `x-forwarded-for` ist eine LISTE, an die jeder Proxy hinten
 * anhängt. Wer den linkesten Wert liest, liest den, den der Aufrufer selbst geschickt hat —
 * und ein neuer Wert je Anfrage ist ein neuer Zähler. Der Fehler sieht nicht wie ein Fehler
 * aus: die Bremse antwortet weiter brav mit 200, sie bremst nur niemanden mehr.
 */
import { clientIp } from "../lib/clientIp.js";

const req = (h) => ({ headers: { get: (n) => h[n] ?? null } });

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

const ECHT = "203.0.113.77";

// 1) Der Normalfall hinter einem Proxy: unsere Gegenstelle steht hinten.
pruefe("einzelner Wert wird genommen",
  clientIp(req({ "x-forwarded-for": ECHT })) === ECHT);

// 2) ⚠ DER KERN. Der Client stellt einen eigenen Wert voran, der Proxy hängt unsere echte
//    Gegenstelle an. Wer vorne liest, bekommt bei jeder Anfrage einen neuen Zähler.
for (const gefaelscht of ["10.0.0.1", "10.0.0.2", "::1", "irgendwas"]) {
  pruefe(`vorangestelltes "${gefaelscht}" aendert die Herkunft nicht`,
    clientIp(req({ "x-forwarded-for": `${gefaelscht}, ${ECHT}` })) === ECHT);
}

// 3) Mehrere Proxys: es zaehlt, was der NAECHSTE gesehen hat.
pruefe("bei mehreren Eintraegen zaehlt der letzte",
  clientIp(req({ "x-forwarded-for": `1.1.1.1, 2.2.2.2, ${ECHT}` })) === ECHT);

// 4) Plattform-Kopfzeilen haben Vorrang — sie kann der Aufrufer nicht setzen.
pruefe("x-vercel-forwarded-for schlaegt x-forwarded-for",
  clientIp(req({ "x-vercel-forwarded-for": ECHT, "x-forwarded-for": "10.0.0.1" })) === ECHT);
pruefe("x-real-ip wird genutzt, wenn sonst nichts da ist",
  clientIp(req({ "x-real-ip": ECHT })) === ECHT);

// 5) Nichts da → ein STABILER Schluessel. „unknown" bremst alle Namenlosen gemeinsam; das
//    ist streng, aber es ist eine Bremse. Ein zufaelliger Wert waere gar keine.
pruefe("ohne Kopfzeilen ein fester Schluessel", clientIp(req({})) === "unknown");
pruefe("leere Kopfzeile faellt auf den festen Schluessel zurueck",
  clientIp(req({ "x-forwarded-for": "  ,  " })) === "unknown");

console.log(fehler ? `\n${fehler} Pruefung(en) fehlgeschlagen` : "\nalle Pruefungen bestanden");
process.exit(fehler ? 1 : 0);

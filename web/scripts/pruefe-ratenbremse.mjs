/* Der Zähler hinter jeder Ratenbremse — und die Trennung von Nachsehen und Verbrauchen.
 *
 *     node web/scripts/pruefe-ratenbremse.mjs
 *
 * Geprüft wird die ECHTE Fassung aus `lib/rateLimitCore.js`, keine Abschrift.
 *
 * Warum überhaupt ein Test: `/api/lead-docs` zählte ganz am Anfang mit, vor jeder
 * Gültigkeitsprüfung. Eine Anfrage ohne Datei bekam ihr 400 und hatte die Quote trotzdem
 * verbraucht — und weil dort ein GLOBALER Deckel steht, sperrte das die Dokumentanalyse
 * für alle anderen. Der Fehler sieht nicht wie ein Fehler aus: die Route antwortet korrekt
 * mit 400, sie nimmt nur nebenbei allen anderen das Kontingent weg.
 */
import { darfNoch, rateLimit, _leeren } from "../lib/rateLimitCore.js";

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

const FENSTER = 60_000;

// 1) Nachsehen verbraucht NICHT — beliebig oft.
_leeren();
for (let i = 0; i < 100; i++) darfNoch("a", 3);
pruefe("100-mal nachsehen verbraucht nichts", rateLimit("a", 3, FENSTER).ok);

// 2) Verbrauchen verbraucht.
_leeren();
pruefe("erster Verbrauch geht durch", rateLimit("b", 2, FENSTER).ok);
pruefe("zweiter Verbrauch geht durch", rateLimit("b", 2, FENSTER).ok);
pruefe("dritter Verbrauch wird abgewiesen", !rateLimit("b", 2, FENSTER).ok);

// 3) Nachsehen SIEHT den verbrauchten Stand — sonst waere es nutzlos.
pruefe("nachsehen meldet die erschoepfte Quote", !darfNoch("b", 2).ok);
pruefe("nachsehen liefert eine Wartezeit", darfNoch("b", 2).retryAfter > 0);

// 4) ⚠ DER EIGENTLICHE FALL. 40 ungueltige Anfragen (nur nachsehen) duerfen die Quote
//    nicht anruehren; die 41., gueltige, muss noch laufen duerfen.
_leeren();
for (let i = 0; i < 40; i++) darfNoch("leaddocs:global", 40);
pruefe("nach 40 abgewiesenen Anfragen ist die Quote unberuehrt",
  rateLimit("leaddocs:global", 40, FENSTER).ok);

// 5) Und die Quote greift trotzdem, wenn wirklich gearbeitet wurde.
_leeren();
for (let i = 0; i < 40; i++) rateLimit("leaddocs:global", 40, FENSTER);
pruefe("nach 40 echten Laeufen ist Schluss", !rateLimit("leaddocs:global", 40, FENSTER).ok);
pruefe("und das Nachsehen sagt es auch", !darfNoch("leaddocs:global", 40).ok);

// 6) Getrennte Schluessel stoeren einander nicht.
_leeren();
for (let i = 0; i < 5; i++) rateLimit("ip:1", 5, FENSTER);
pruefe("ein anderer Schluessel hat seine eigene Quote", rateLimit("ip:2", 5, FENSTER).ok);

console.log(fehler ? `\n${fehler} Pruefung(en) fehlgeschlagen` : "\nalle Pruefungen bestanden");
process.exit(fehler ? 1 : 0);

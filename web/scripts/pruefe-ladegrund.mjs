/* Die Regel, die „gibt es nicht" von „ich komme nicht dran" trennt.
 *
 *     node web/scripts/pruefe-ladegrund.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/ladegrund.js`, keine Abschrift.
 *
 * Warum überhaupt ein Test: ein leeres Ergebnis ist eine AUSSAGE. Sagt die Oberfläche „keine
 * Fristen", richtet sich jemand danach. Kommt dieselbe Antwort auch dann, wenn der Speicher
 * nicht erreichbar ist, hat das Produkt einen Ausfall in eine Auskunft verwandelt — genau
 * die Verwechslung, gegen die sein ganzes Versprechen steht.
 */
import { grundAus, darfLeerAntworten, OK, FEHLT, STOERUNG } from "../lib/ladegrund.js";

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

// ── Der Normalfall ─────────────────────────────────────────────────────────────
pruefe("200 vom Speicher ist ok", grundAus({ ferngriff: true, status: 200 }) === OK);
pruefe("Plattenbetrieb ohne Datei ist `fehlt`", grundAus({ ferngriff: false }) === FEHLT);
pruefe("gar kein Protokoll ist `fehlt`", grundAus() === FEHLT);

// ── ⚠ FALLE 1: 404 IST KEINE STOERUNG ──────────────────────────────────────────
// Der Speicher hat geantwortet, die Datei gibt es dort nicht. Wer daraus einen Ausfall
// macht, meldet fuer JEDEN Lead ohne Kalenderdatei eine Stoerung — und eine Fehlermeldung,
// die immer kommt, liest bald niemand mehr.
pruefe("404 ist `fehlt`, nicht `stoerung`",
  grundAus({ ferngriff: true, status: 404 }) === FEHLT);

// ── ⚠ FALLE 2: EIN TREFFER AUF DER PLATTE LOESCHT DIE STOERUNG ─────────────────
// Der Rueckfall auf die lokale Platte ist der Sinn der Kette. Liegt die Datei am Ende vor,
// war der entfernte Fehlschlag folgenlos.
pruefe("500 + Plattentreffer ist ok",
  grundAus({ ferngriff: true, status: 500, platte: true }) === OK);
pruefe("Netzausfall + Plattentreffer ist ok",
  grundAus({ ferngriff: true, ausnahme: true, platte: true }) === OK);

// ── Die Stoerungen ─────────────────────────────────────────────────────────────
pruefe("500 ohne Plattentreffer ist `stoerung`",
  grundAus({ ferngriff: true, status: 500 }) === STOERUNG);
pruefe("403 (Signatur abgelehnt) ist `stoerung`",
  grundAus({ ferngriff: true, status: 403 }) === STOERUNG);
pruefe("geworfenes fetch (Netz, DNS, Zeitgrenze) ist `stoerung`",
  grundAus({ ferngriff: true, ausnahme: true }) === STOERUNG);
pruefe("Ferngriff ohne Status und ohne Ausnahme bleibt `stoerung` — unerklaert ist nicht ok",
  grundAus({ ferngriff: true }) === STOERUNG);

// ── Was der Aufrufer daraus machen darf ────────────────────────────────────────
pruefe("`fehlt` darf leer beantwortet werden", darfLeerAntworten(FEHLT));
pruefe("`ok` darf leer beantwortet werden", darfLeerAntworten(OK));
pruefe("`stoerung` NICHT — sonst wird ein Ausfall zur Auskunft",
  !darfLeerAntworten(STOERUNG));

console.log(fehler ? `\n${fehler} Pruefung(en) fehlgeschlagen` : "\nalle Pruefungen bestanden");
process.exit(fehler ? 1 : 0);

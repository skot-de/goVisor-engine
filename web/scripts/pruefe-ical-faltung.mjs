/* Die iCal-Textregeln des Frontends gegen RFC 5545 §3.1 und §3.3.11.
 *
 *     node web/scripts/pruefe-ical-faltung.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/ical.js`, die der Feed benutzt — keine Abschrift.
 *
 * Warum überhaupt ein Test: die Faltung ist von Hand gebaut und rechnet in OKTETT, während
 * JavaScript in Code-Units denkt. Ein Fehler darin sieht nicht wie ein Fehler aus, sondern
 * wie ein Umlaut, der im Kalender eines einzelnen Nutzers zu zwei Fragezeichen wird. Von
 * aussen sieht man davon nichts.
 */
import { esc, falte, entfalte } from "../lib/ical.js";

const oktett = (s) => new TextEncoder().encode(s).length;

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

// 1) Kurze Zeilen bleiben unangetastet — Faltung ist kein Selbstzweck.
const kurz = "SUMMARY:Angebotsfrist";
pruefe("kurze Zeile bleibt unveraendert", falte(kurz) === kurz);

// 2) Eine echte lange Zeile aus dem Bestand (198 Oktett war der gemessene Maximalwert).
const lang = "DESCRIPTION:" + "Termine für eine Ortsbesichtigung können mit DWS Architekten "
  + "PartGmbB Dollmann Wagner Schmidt vereinbart werden, bitte melden Sie sich rechtzeitig.";
const gefaltet = falte(lang);
const zeilen = gefaltet.split("\r\n");
pruefe("lange Zeile wird ueberhaupt gefaltet", zeilen.length > 1);
pruefe("keine Zeile ueber 75 Oktett", zeilen.every((z) => oktett(z) <= 75));
pruefe("Fortsetzungen beginnen mit einem Leerzeichen",
  zeilen.slice(1).every((z) => z.startsWith(" ")));
pruefe("Entfalten stellt das Original her", entfalte(gefaltet) === lang);

// 3) ⚠ DER EIGENTLICHE GRUND FUER DEN TEST: mehrbytige Zeichen duerfen nicht zerschnitten
//    werden. Ein „ä" genau an der Grenze wuerde bei byteweisem Schnitt zu Datenmuell.
for (const fuellung of ["ä".repeat(80), "€".repeat(60), "🏗".repeat(40), "Łódź ".repeat(20)]) {
  const z = falte("DESCRIPTION:" + fuellung);
  const teile = z.split("\r\n");
  pruefe(`mehrbytig unversehrt (${[...fuellung][0]})`,
    entfalte(z) === "DESCRIPTION:" + fuellung
    && teile.every((t) => oktett(t) <= 75)
    && !z.includes("�"));
}

// 4) Maskierung nach §3.3.11. Der Backslash muss ZUERST verdoppelt werden, sonst maskiert
//    man die eigene Maskierung ein zweites Mal.
pruefe("Komma und Semikolon werden maskiert", esc("a,b;c") === "a\\,b\\;c");
pruefe("Backslash wird verdoppelt", esc("a\\b") === "a\\\\b");
pruefe("Zeilenumbruch wird zu \\n", esc("a\r\nb") === "a\\nb");

// 5) Grenzfall: genau 75 und genau 76 Oktett.
pruefe("genau 75 Oktett bleibt eine Zeile", falte("A".repeat(75)).split("\r\n").length === 1);
pruefe("76 Oktett werden zwei Zeilen", falte("A".repeat(76)).split("\r\n").length === 2);

console.log(fehler ? `\n${fehler} Pruefung(en) fehlgeschlagen` : "\nalle Pruefungen bestanden");
process.exit(fehler ? 1 : 0);

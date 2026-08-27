/* Textregeln des iCal-Formats (RFC 5545) — Maskieren und Falten.
 *
 * WARUM EINE EIGENE DATEI, UND WARUM PLAIN JS. Beides sind kleine, aber fehleranfällige
 * Textregeln, und ein Fehler darin sieht nicht wie ein Fehler aus: der Feed wird abonniert,
 * bleibt aber bei einzelnen Nutzern leer oder zeigt zerhackte Umlaute. Hier liegend, kann
 * `node` sie laden und `web/scripts/pruefe-ical-faltung.mjs` die ECHTE Fassung prüfen — ein
 * Test gegen eine Abschrift geht grün, während die benutzte Version falsch ist.
 *
 * ⚠ ES GIBT EINE ZWEITE UMSETZUNG in `govisor/kalender.py` (`_escape`, `_falte`) für den
 * CLI-Weg `export_kalender.py --ical`. Die beiden sind schon einmal auseinandergelaufen:
 * die Python-Seite schreibt `DTEND` und kürzt den Titel, diese hier nicht. Wer eine Regel
 * ändert, ändert beide — ausgeliefert wird DIESE.
 */

/**
 * RFC 5545 §3.3.11: Komma, Semikolon, Backslash und Zeilenumbruch maskieren.
 *
 * ⚠ EIN EINZELNES CR IST AUCH EIN ZEILENUMBRUCH. Die vorige Fassung suchte `\r?\n` — ein
 * `\r` OHNE folgendes `\n` lief damit ungefiltert in die Ausgabe. In iCal trennt CRLF die
 * Zeilen, und nachsichtige Kalenderprogramme brechen schon am blossen CR um: der Rest des
 * Titels stuende dann als EIGENE Eigenschaft im Termin. Wer einen Text in unsere Daten
 * bekommt — und die Titel und Belege stammen aus fremden Ausschreibungsunterlagen —, kann
 * so eigene iCal-Felder in den Kalender eines Nutzers schreiben.
 *
 * Im Bestand kommt es heute NICHT vor (2026-08-27 ueber alle Kalender- und Lead-Dateien
 * geprueft: 0 Treffer). Das ist der Grund, es jetzt zu schliessen und nicht spaeter: es
 * gibt nichts zu reparieren, nur etwas zu verhindern.
 *
 * Dazu fallen Steuerzeichen weg. Der TEXT-Typ des Standards laesst ausser HTAB keine zu,
 * und aus PDF-Extraktion kommen sie regelmaessig mit (das Projekt hatte schon einmal
 * literale 0x08-Bytes im Quelltext).
 */
export function esc(s) {
  return String(s)
    .replace(/([,;\\])/g, "\\$1")
    .replace(/\r\n|\r|\n/g, "\\n")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");
}

/**
 * Lange Zeile nach RFC 5545 §3.1 umbrechen: CRLF und ein führendes Leerzeichen.
 *
 * Der Standard sagt SHOULD, nicht MUST — die meisten Kalenderprogramme lesen auch lange
 * Zeilen. „Die meisten" ist bei einem Feed, den man einmal abonniert und dann vergisst, aber
 * die falsche Wette: der Ausfall träfe einzelne Nutzer, und von aussen sähe niemand etwas.
 * Gemessen am 2026-08-25 über den ganzen Bestand: **37 % der erzeugten Inhaltszeilen** liegen
 * darüber, die längste bei 198 Oktett — die DESCRIPTION trägt ein wörtliches Zitat aus den
 * Vergabeunterlagen.
 *
 * ⚠ GEZÄHLT WIRD IN OKTETT, NICHT IN ZEICHEN. „ä" ist zwei Oktett; ein Schnitt mitten im
 * Zeichen macht aus dem Umlaut Datenmüll. `for…of` läuft über Code-Punkte, nicht über
 * Code-Units — deshalb überleben auch Zeichen ausserhalb der BMP (Emoji, seltene Schriften).
 * Fortsetzungszeilen tragen nur 74 Oktett, weil das führende Leerzeichen mitzählt.
 *
 * @param {string} zeile eine vollständige Inhaltszeile, z. B. `DESCRIPTION:…`
 * @returns {string} dieselbe Zeile, bei Bedarf gefaltet
 */
export function falte(zeile) {
  const enc = new TextEncoder();
  if (enc.encode(zeile).length <= 75) return zeile;
  const teile = [];
  let akt = "", oktett = 0, grenze = 75;
  for (const zeichen of zeile) {
    const n = enc.encode(zeichen).length;
    if (oktett + n > grenze) { teile.push(akt); akt = ""; oktett = 0; grenze = 74; }
    akt += zeichen;
    oktett += n;
  }
  if (akt) teile.push(akt);
  return teile.join("\r\n ");
}

/** Faltung rückgängig machen. Nur für Tests — ein Client tut genau das beim Lesen. */
export function entfalte(text) {
  return text.replace(/\r\n /g, "");
}

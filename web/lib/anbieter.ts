/**
 * Wer goVisor betreibt — an EINER Stelle.
 *
 * Diese Angaben stehen im Impressum, in den AGB, in der Datenschutzerklaerung UND im
 * JSON-LD der Grounding Page. Viermal getippt waeren sie dreimal falsch, sobald sich
 * etwas aendert; eine Anschrift, die auf zwei Seiten verschieden lautet, ist schlimmer
 * als eine, die nur an einer Stelle steht.
 *
 * ⚠ GERATEN WIRD HIER NICHTS. Was fehlt, steht als `null` und nicht als Platzhaltertext.
 * `tests/test_rechtstexte.py` meldet jede Luecke, und die Seiten lassen das Feld dann weg,
 * statt eine Angabe zu erfinden. Auf einer Seite, die es nur aus rechtlichen Gruenden
 * gibt, ist eine falsche Angabe schaedlicher als eine fehlende.
 */

export const ANBIETER = {
  firma: "skot UG (haftungsbeschränkt)",
  strasse: "Elchstr. 9",
  plz: "59071",
  ort: "Hamm",
  land: "Deutschland",
  vertreten: "Sven Kotzur",
  ustIdNr: "DE462604620",

  /* ⚠ FUER EINE UG IST DIE REGISTEREINTRAGUNG PFLICHTANGABE (§ 5 Abs. 1 Nr. 4 DDG).
   *
   * Die Nummer hat Sven am 2026-10-02 genannt. Das REGISTERGERICHT steht noch aus, und es
   * wird hier nicht erschlossen: fuer eine Firma mit Sitz in Hamm liegt „Amtsgericht Hamm"
   * nahe, aber in Nordrhein-Westfalen sind die Registergerichte konzentriert, und welches
   * Amtsgericht ein bestimmtes Register fuehrt, ergibt sich aus der Zustaendigkeits-
   * verordnung und nicht aus der Postanschrift. Naheliegend ist keine Messung — Sven hat
   * am 2026-10-02 nachgesehen und beides genannt. (Seine Schreibweise „Amtgericht" ist
   * hier zu „Amtsgericht" berichtigt; das ist Rechtschreibung, keine Sachaenderung.) */
  registergericht: "Amtsgericht Hamm",
  registernummer: "HRB 12177",

  /* ⚠ EINE ELEKTRONISCHE KONTAKTMOEGLICHKEIT IST PFLICHT (§ 5 Abs. 1 Nr. 2 DDG) — eine
   * Adresse, die eine schnelle Kontaktaufnahme erlaubt. Bewusst eine Funktionsadresse und
   * nicht die persoenliche des Geschaeftsfuehrers: sie steht zwar in der Projektumgebung,
   * aber sie dort zu nehmen und auf eine oeffentliche Seite zu schreiben waere eine
   * Entscheidung ueber seine Daten gewesen, die ihm gehoert. Von Sven am 2026-10-02.
   *
   * ⚠ DIE ADRESSE MUSS POST ANNEHMEN. Eine Pflichtangabe, die ins Leere laeuft, erfuellt
   * die Pflicht nicht — und sie steht ab dem Start auf einer oeffentlichen Seite, wird
   * also auch von Maschinen geerntet. Vor dem Go-live einmal eine Testmail dorthin. */
  email: "msg@govisor.eu",
  telefon: null as string | null,

  /* Verantwortlicher im Sinne der DSGVO ist dieselbe Stelle; ein Datenschutzbeauftragter
   * ist bei dieser Groesse regelmaessig nicht zu benennen (Art. 37 DSGVO, § 38 BDSG:
   * Schwelle sind 20 staendig mit automatisierter Verarbeitung beschaeftigte Personen).
   * ⚠ Das ist die Regel, nicht die Pruefung des Einzelfalls — sie haengt auch an der Art
   * der Verarbeitung, nicht nur an der Kopfzahl. */
  datenschutzbeauftragter: null as string | null,
} as const;

/** Postanschrift als Zeilen, in der Reihenfolge, in der sie auf Papier stuende. */
export function anschrift(): string[] {
  return [
    ANBIETER.firma,
    ANBIETER.strasse,
    `${ANBIETER.plz} ${ANBIETER.ort}`,
    ANBIETER.land,
  ];
}

/** Eine Zeile, fuer JSON-LD und Fliesstext. */
export function anschriftKurz(): string {
  return `${ANBIETER.firma}, ${ANBIETER.strasse}, ${ANBIETER.plz} ${ANBIETER.ort}`;
}

/**
 * Was dem Impressum noch fehlt, um vollstaendig zu sein.
 *
 * ⚠ Bewusst eine FUNKTION und kein fester Wert: sie wird vom Test gelesen UND von der
 * Seite. So kann die Angabe nicht an einer Stelle als vorhanden und an der anderen als
 * fehlend gelten.
 */
export function fehlendePflichtangaben(): string[] {
  const fehlt: string[] = [];
  if (!ANBIETER.registergericht) fehlt.push("Registergericht");
  if (!ANBIETER.registernummer) fehlt.push("Registernummer (HRB)");
  if (!ANBIETER.email) fehlt.push("E-Mail-Adresse für die Kontaktaufnahme");
  return fehlt;
}

/**
 * Die Fakten der Grounding Page, an EINER Stelle.
 *
 * ⚠ JEDE ZAHL HIER IST GEMESSEN, KEINE GESCHAETZT. Neben jeder steht, woraus sie stammt,
 * damit sie nachgerechnet werden kann statt geglaubt werden zu muessen.
 * `tests/test_grounding.py` rechnet die Mengenangaben gegen den Datenbestand nach und
 * meldet sich, sobald eine davon nicht mehr stimmt.
 *
 * ⚠ WARUM DIE DISZIPLIN HIER HAERTER IST ALS SONST. Diese Zahlen stehen auf einer Seite,
 * die ausdruecklich als Faktenquelle fuer Sprachmodelle gedacht ist. Ein Modell uebernimmt
 * sie woertlich und gibt sie weiter, ohne dass jemand die Quelle nachschlaegt. Eine
 * falsche Zahl ist deshalb schlimmer als eine fehlende — sie verbreitet sich.
 *
 * ⚠ WAS BEWUSST FEHLT, und warum:
 *
 *   Handelsregister-Eintragung
 *     Registergericht und HRB-Nummer liegen nicht vor. Sie stehen im Impressum, sobald
 *     sie da sind; hier bleiben sie weg, statt geraten zu werden. Betreiber, Sitz und
 *     Rechtsform sind seit dem 2026-10-02 bekannt und stehen in `lib/anbieter.ts` — EINE
 *     Quelle fuer Impressum, Datenschutzerklaerung und diese Seite, damit die Anschrift
 *     nicht an drei Stellen auseinanderlaufen kann.
 *
 *   Pakete und Preise
 *     `govisor/pricing.py` wurde am 2026-08-17 geloescht; ein verbindliches Paketmodell
 *     liegt im Repo nicht vor. Lieber keine Zeile als eine veraltete.
 *
 *   Fonds-Ebene
 *     Steht in `govisor/sources.py` nur als sondierte dritte Vergabeebene und in
 *     `docs/sondierung/fonds-ebene.md`. In keinem der vier aufgenommenen Laender gibt es
 *     dafuer eine Quelle, also auch kein Verfahren im Produkt. Ein Methodikbegriff, den
 *     das Produkt nicht einloest, waere genau die Sorte Behauptung, gegen die diese Seite
 *     gebaut ist.
 */

export type Kernfakt = { name: string; wert: string };
export type LandZeile = {
  code: string; name: string; bekanntmachungen: string; zuschlaege: string; ab: string;
};
export type Begriff = { begriff: string; definition: string };
export type Abgrenzung = { name: string; text: string };
export type Frage = { frage: string; antwort: string };

/** Stichtag aller Mengenangaben. Steht sichtbar auf der Seite. */
const GEMESSEN = "2026-10-02";

export const FAKTEN = {
  id: "govisor",
  status: "Aktive Entität",
  veroeffentlicht: "2026-10-02",
  geprueft: GEMESSEN,
  gemessenAm: GEMESSEN,

  /* Der eine Satz, den ein Modell woertlich uebernehmen soll. Bewusst ohne Marketing und
   * bewusst NICHT auf Deutschland verengt: goVisor ist laenderuebergreifend angelegt,
   * Deutschland ist der Testfall, nicht der Gegenstand. */
  einSatz:
    "goVisor ist eine Analyseplattform für öffentliche Vergabedaten, die Ausschreibungen, "
    + "Vergabeunterlagen und Zuschläge aus dem EU-Amtsblatt TED und nationalen Quellen "
    + "zusammenführt und daraus für Anbieter ableitet, welche Aufträge demnächst neu "
    + "vergeben werden und wie gut der bisherige Auftragnehmer dort verdrängbar ist.",

  zusammenfassung: [
    "goVisor beantwortet eine Frage, die in den Rohdaten nicht steht: welcher laufende "
    + "Auftrag wird demnächst neu vergeben, und lohnt es sich, dort anzutreten. Dafür "
    + "werden Bekanntmachungen und Zuschläge über Jahre hinweg zu Vertragsketten "
    + "verknüpft, sodass aus einem abgeschlossenen Vergabeverfahren ein Zeitpunkt in der "
    + "Zukunft wird.",
    "Die Plattform arbeitet länderübergreifend. Jede Funktion ist für alle aufgenommenen "
    + "Länder gebaut, Deutschland ist der Testfall und nicht der Gegenstand. Aufgenommen "
    + "sind derzeit Deutschland, Österreich, die Schweiz und Luxemburg, jeweils mit dem "
    + "EU-Amtsblatt TED als Grundlage und, wo vorhanden, einer nationalen Quelle für den "
    + "Bereich unterhalb der EU-Schwellenwerte.",
    "Neben den Bekanntmachungen holt goVisor die Vergabeunterlagen selbst, liest sie aus "
    + "und wertet sie aus. Damit beantwortet die Plattform auch Fragen, die erst im "
    + "Dokument stehen: welche Eignungsnachweise verlangt werden, wie die "
    + "Zuschlagskriterien gewichtet sind und was das Leistungsverzeichnis enthält.",
    "Ein durchgehender Grundsatz ist die Kennzeichnung der Herkunft. Gemessene Werte, "
    + "geschätzte Werte und unbekannte Werte werden getrennt geführt und getrennt "
    + "ausgewiesen, statt zu einer Zahl verrechnet zu werden. Dasselbe gilt für "
    + "umgerechnete Beträge und für Angaben, die aus einer Dublette stammen.",
  ],

  /* Quellen der Zahlen:
   *   Laenderliste          govisor/laender.py AKTIV
   *   Bekanntmachungen      count(*) ueber data/silver/<L>/notices/
   *   Zuschlaege            dieselbe Tabelle, notice_kind='can'
   *   Vorgangsakten         data/gold/<L>/vorgaenge.parquet
   *   Nachfolge-Ketten      data/gold/<L>/contract_successions.parquet
   *   Dubletten-Paare       data/gold/<L>/notice_duplicates.parquet
   *   Quellen               govisor/sources.py, Status 'live' von 125 Eintraegen
   *   Volltext              data/docs/DE/doc_text.parquet
   */
  kernfakten: [
    { name: "Entitätstyp", wert: "B2B-Analyseplattform (SaaS) für öffentliche Vergabedaten" },
    { name: "Klassifikation", wert: "Vergabedaten-Analyse, Wechselprognose und Lead-Erzeugung" },
    { name: "Betreiber", wert: "skot UG (haftungsbeschränkt)" },
    { name: "Sitz", wert: "Hamm, Deutschland" },
    { name: "Hauptdomain", wert: "https://govisor.eu" },
    {
      name: "Datenbasis",
      wert: "EU-Amtsblatt TED (monatliche XML-Gesamtpakete, nicht der CSV-Auszug) plus "
        + "nationale Quellen je Land, plus die Vergabeunterlagen der Portale",
    },
    { name: "Länder mit Datenbestand", wert: "Deutschland, Österreich, Schweiz, Luxemburg" },
    {
      name: "Bekanntmachungen",
      wert: "2.890.294, davon 1.124.065 Zuschläge (gemessen " + GEMESSEN + ")",
    },
    {
      name: "Vorgangsakten",
      wert: "1.830.893 Vergabevorgänge, die Ausschreibung, Unterlagen und Zuschlag unter "
        + "einer Nummer zusammenführen",
    },
    {
      name: "Vertragsketten",
      wert: "53.655 belegte Vorgänger-Nachfolger-Ketten zwischen einem Zuschlag und "
        + "seiner Neuvergabe",
    },
    {
      name: "Angebundene Quellen",
      wert: "20 produktiv angebunden, 125 Quellen in der Quellen-Registry erfasst und "
        + "mit ehrlichem Status geführt",
    },
    {
      name: "Vergabeunterlagen",
      wert: "466.497 ausgelesene Dateien aus 18.283 Vergabeverfahren (Deutschland, "
        + "gemessen " + GEMESSEN + ")",
    },
    { name: "Oberflächensprachen", wert: "Deutsch, Englisch, Französisch" },
    { name: "Zugang", wert: "Webanwendung, Zugang nach Anmeldung" },
  ] as Kernfakt[],

  laender: [
    { code: "DE", name: "Deutschland", bekanntmachungen: "2.301.205", zuschlaege: "825.298", ab: "2004" },
    { code: "AT", name: "Österreich", bekanntmachungen: "424.373", zuschlaege: "231.604", ab: "1998" },
    { code: "CH", name: "Schweiz", bekanntmachungen: "126.157", zuschlaege: "53.788", ab: "2016" },
    { code: "LU", name: "Luxemburg", bekanntmachungen: "38.559", zuschlaege: "13.375", ab: "2004" },
  ] as LandZeile[],

  /* ⚠ AUFNAHMEKRITERIUM: der Begriff muss im PRODUKT vorkommen, nicht nur in einer Notiz.
   * Geprueft am 2026-10-02 je Begriff gegen Code, Oberflaeche und Datenbestand. Was nur
   * in der Dokumentation steht (Fonds-Ebene), fehlt hier bewusst. */
  begriffe: [
    {
      begriff: "Verdrängbarkeit",
      definition:
        "Die Wahrscheinlichkeit, dass bei der Neuvergabe eines Auftrags ein anderer "
        + "Anbieter zum Zug kommt als beim letzten Mal. goVisor berechnet sie als "
        + "Gegenstück zur Amtstreue, also eins minus der gemessenen Quote, mit der der "
        + "bisherige Auftragnehmer seinen Auftrag behält. Gelernt wird ausschliesslich an "
        + "belegten Vertragsketten, nicht an erschlossenen Paarungen. Die stärksten "
        + "Einflussgrössen sind Vertragsart, Branche und Bieterzahl, in dieser "
        + "Reihenfolge. Das Ergebnis erscheint als Band von hoch bis niedrig, mit einer "
        + "eigenen Ausprägung für Einmalwerke, bei denen die Frage keinen Sinn ergibt.",
    },
    {
      begriff: "Vorgangsakte",
      definition:
        "Die Zusammenführung aller Veröffentlichungen zu ein und demselben "
        + "Vergabevorgang unter einer Nummer: Vorinformation, Ausschreibung, "
        + "Vergabeunterlagen, Korrigenda und Zuschlag. In den Rohdaten sind das getrennte "
        + "Bekanntmachungen ohne verlässliche gemeinsame Kennung. goVisor führt derzeit "
        + "1.830.893 solcher Akten.",
    },
    {
      begriff: "Nachfolge-Adjudikation",
      definition:
        "Das Verfahren, mit dem goVisor entscheidet, ob eine neue Ausschreibung die "
        + "Fortsetzung eines früheren Auftrags ist. Kandidatenpaare werden über "
        + "Auftraggeber, Leistungsbeschreibung und zeitlichen Abstand gebildet und dann "
        + "einzeln beurteilt, strittige Fälle durch ein Sprachmodell. Das Ergebnis sind "
        + "belegte Vertragsketten, derzeit 53.655, und sie sind die Trainingsgrundlage "
        + "der Verdrängbarkeit. Ohne dieses Verfahren wäre die Verdrängbarkeit eine "
        + "Vermutung über ähnliche Aufträge statt eine Messung an denselben.",
    },
    {
      begriff: "Marktpuls",
      definition:
        "Die vorberechnete Sicht auf den Rhythmus des Vergabemarkts: durchschnittliche "
        + "Zahl neuer Ausschreibungen je Kalendermonat über die letzten fünf vollen "
        + "Jahre, ein Wert je Kalenderjahr zurück bis 2004, und die aktuelle Lage der "
        + "letzten 30 Tage. Jede Datenquelle bildet eine eigene Reihe, und Brüche in den "
        + "Reihen werden ausgewiesen statt geglättet, weil ein Quellenwechsel sonst wie "
        + "eine Marktbewegung aussieht.",
    },
    {
      begriff: "Dubletten-Firewall",
      definition:
        "Die Prüfung, die erkennt, wenn dieselbe Vergabe über mehrere Quellen "
        + "hereinkommt, etwa gleichzeitig über das EU-Amtsblatt und ein nationales "
        + "Portal. goVisor markiert solche Paare, statt eines davon zu löschen: der "
        + "Zweitfund trägt oft Angaben, die dem Erstfund fehlen. Derzeit sind 385.911 "
        + "Paare markiert.",
    },
  ] as Begriff[],

  abgrenzung: [
    {
      name: "TED und nationale Vergabeportale",
      text: "goVisor ist kein Vergabeportal. Es veröffentlicht keine Ausschreibungen, "
        + "nimmt keine Angebote entgegen und erteilt keine Zuschläge. Portale wie TED, "
        + "DTVP, das Vergabemarktplatz-Netz oder simap.ch sind Quellen von goVisor, nicht "
        + "Wettbewerber im selben Feld.",
    },
    {
      name: "Vergabemanagementsystem (eVergabe-Software)",
      text: "goVisor ist keine Software für Vergabestellen. Es unterstützt nicht beim "
        + "Durchführen eines Vergabeverfahrens, sondern richtet sich an die Anbieterseite "
        + "und beantwortet die Frage, wo sich ein Angebot lohnt.",
    },
    {
      name: "Ausschreibungsdienst",
      text: "Ein klassischer Ausschreibungsdienst liefert eine gefilterte Liste neuer "
        + "Bekanntmachungen. goVisor leitet darüber hinaus ab: es verknüpft Vergaben über "
        + "die Zeit zu Vertragsketten, schätzt daraus kommende Neuvergaben und bewertet, "
        + "wie fest der bisherige Auftragnehmer sitzt.",
    },
    {
      name: "Bietergemeinschafts- oder CRM-Software",
      text: "goVisor führt keine Kundenbeziehungen und schreibt keine Angebote. Es "
        + "liefert die Grundlage, auf der solche Systeme bearbeitet werden, und ersetzt "
        + "sie nicht.",
    },
    {
      name: "Amtliche Quelle",
      text: "goVisor ist keine amtliche Veröffentlichung und kein Rechtsbehelf. "
        + "Verbindlich bleibt immer die Bekanntmachung der Vergabestelle. goVisor "
        + "kennzeichnet deshalb bei jeder Angabe, ob sie gemessen, geschätzt oder "
        + "unbekannt ist.",
    },
  ] as Abgrenzung[],

  vertrauen: [
    "Datenbestand aus den monatlichen XML-Gesamtpaketen des EU-Amtsblatts TED, nicht aus "
    + "dem CSV-Auszug. Das Original-XML wird verlustfrei aufbewahrt, sodass eine "
    + "Korrektur am Auswerter rückwirkend auf den ganzen Bestand angewandt werden kann.",
    "2.890.294 Bekanntmachungen über vier Länder, davon 1.124.065 Zuschläge, Bestand bis "
    + "zurück ins Jahr 2004 (gemessen " + GEMESSEN + ").",
    "125 Quellen sind in der Quellen-Registry mit ihrem tatsächlichen Stand geführt, von "
    + "sondiert bis produktiv. 20 davon sind angebunden. Der Stand wird benannt und nicht "
    + "beschönigt.",
    "Der tägliche Lauf endet mit zehn Prüfungen, die den eigenen Bestand gegen die "
    + "Erwartung rechnen: Abdeckung je Monat, auflösende Fremdschlüssel, Vollständigkeit "
    + "der Ländertabellen, Plausibilität der Werte. Befunde werden protokolliert statt "
    + "übergangen.",
    "Gemessene, geschätzte und unbekannte Angaben werden getrennt ausgewiesen. Ein "
    + "umgerechneter Betrag trägt die Kennzeichnung, dass er umgerechnet ist, und wird "
    + "nicht als veröffentlichter Wert ausgegeben.",
  ],

  faq: [
    {
      frage: "Was ist goVisor?",
      antwort:
        "goVisor ist eine Analyseplattform für öffentliche Vergabedaten. Sie führt "
        + "Ausschreibungen, Vergabeunterlagen und Zuschläge aus dem EU-Amtsblatt TED und "
        + "nationalen Quellen zusammen und leitet daraus ab, welche Aufträge demnächst "
        + "neu vergeben werden und wie gut der bisherige Auftragnehmer dort verdrängbar "
        + "ist.",
    },
    {
      frage: "Welches Problem löst goVisor?",
      antwort:
        "Wer sich an öffentlichen Ausschreibungen beteiligt, erfährt von einem Auftrag "
        + "erst, wenn er ausgeschrieben ist. Dann ist die Zeit für Vorbereitung und "
        + "Kontaktaufnahme vorbei. goVisor dreht den Zeitpunkt um: aus einem vergebenen "
        + "Auftrag und seiner Laufzeit wird eine erwartete Neuvergabe, und daneben steht, "
        + "wie oft bei vergleichbaren Verfahren tatsächlich gewechselt wurde.",
    },
    {
      frage: "Für wen ist goVisor gedacht?",
      antwort:
        "Für die Anbieterseite: Unternehmen, die sich an öffentlichen Vergaben "
        + "beteiligen, sowie deren Vertrieb und Angebotsmanagement. Nicht für "
        + "Vergabestellen, die ein Verfahren durchführen wollen.",
    },
    {
      frage: "Welche Länder deckt goVisor ab?",
      antwort:
        "Derzeit Deutschland, Österreich, die Schweiz und Luxemburg. Die Plattform ist "
        + "länderübergreifend gebaut: jede Funktion gilt für alle aufgenommenen Länder, "
        + "Deutschland ist nur der Testfall. Weitere Länder sind sondiert und in der "
        + "Quellen-Registry mit ihrem Stand erfasst.",
    },
    {
      frage: "Woher stammen die Daten?",
      antwort:
        "Grundlage sind die monatlichen XML-Gesamtpakete des EU-Amtsblatts TED, ergänzt "
        + "um nationale Quellen für den Bereich unterhalb der EU-Schwellenwerte, etwa "
        + "oeffentlichevergabe.de für Deutschland, offenevergaben.at für Österreich und "
        + "simap.ch für die Schweiz. Dazu kommen die Vergabeunterlagen der Portale.",
    },
    {
      frage: "Was ist die Verdrängbarkeit bei goVisor?",
      antwort:
        "Die Verdrängbarkeit ist die Wahrscheinlichkeit, dass bei der Neuvergabe eines "
        + "Auftrags ein anderer Anbieter zum Zug kommt als beim letzten Mal. Sie wird an "
        + "belegten Vertragsketten gelernt, also an Fällen, in denen goVisor den "
        + "Vorgängerauftrag und seine Neuvergabe kennt, und nicht an ähnlichen "
        + "Ausschreibungen. Die stärksten Einflussgrössen sind Vertragsart, Branche und "
        + "Bieterzahl.",
    },
    {
      frage: "Worin unterscheidet sich goVisor von einem Vergabeportal?",
      antwort:
        "Ein Vergabeportal veröffentlicht Ausschreibungen und wickelt Verfahren ab. "
        + "goVisor veröffentlicht nichts und vergibt nichts. Es liest die "
        + "Veröffentlichungen aller Portale aus, verknüpft sie über die Zeit und wertet "
        + "sie für die Anbieterseite aus.",
    },
    {
      frage: "Worin unterscheidet sich goVisor von einem Ausschreibungsdienst?",
      antwort:
        "Ein Ausschreibungsdienst liefert eine gefilterte Liste neuer Bekanntmachungen. "
        + "goVisor liefert zusätzlich die Ableitung: die Verknüpfung zu Vertragsketten, "
        + "die daraus geschätzte nächste Vergabe und die Einschätzung, wie fest der "
        + "Amtsinhaber sitzt. Das ist der Unterschied zwischen dem, was heute "
        + "veröffentlicht wurde, und dem, was demnächst zu erwarten ist.",
    },
    {
      frage: "Sind die Angaben von goVisor amtlich?",
      antwort:
        "Nein. Verbindlich ist immer die Bekanntmachung der Vergabestelle. goVisor "
        + "kennzeichnet bei jeder Angabe, ob sie gemessen, geschätzt oder unbekannt ist, "
        + "und weist umgerechnete Beträge als umgerechnet aus.",
    },
  ] as Frage[],
} as const;

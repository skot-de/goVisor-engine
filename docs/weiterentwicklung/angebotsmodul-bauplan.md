# Angebotsmodul: die Akte als Anker

**Stand 2026-09-15.** Wie aus der Verfahrensakte ein Angebotsmodul wird, ohne dass etwas
Neues danebengestellt werden muss. Alle Zahlen an diesem Tag am laufenden Bestand gemessen,
Land DE, sofern nicht anders genannt.

Gerendert auch als Blatt: `claude.ai/code/artifact/35410140-a396-4fcf-8b59-1bdda7a62a69`
(Begleitkonzept „Mappe an der Kette": `.../03b4e11f-8014-4ed5-8aa0-2633160bda24`).
⚠ Diese Datei ist die Quelle, nicht das Blatt.

## Die eine Entscheidung: `(nutzer, land, vorgang_id)`

Jede Zeile, die ein Kunde erzeugt, haengt an dieser Kombination: Kalkulation, Bausteine,
Nachweise, Ausgang. **Nicht am Lead, nicht an der Bekanntmachung, nicht am Datum.**

Warum das die Mechanik freischaltet: Vorgaenge sind bereits verkettet (`vorgang_kette`,
148.745 Glieder in 47.475 Ketten, Stand 2026-09-15). Wer seine Arbeit an den Vorgang haengt,
haengt sie damit an den Faden durch die Zeit. Die Wiederkehr braucht keine eigene Logik,
sie ist ein Join.

### ⚠ Der Anker bewegt sich

Eine Vorgangskennung ist nicht fuer die Ewigkeit. `build_vorgaenge._anwenden` bildet beim
Andocken und Verschmelzen „alte Nummer → Zielnummer" ab, und die alte verschwindet. Am
2026-09-15 aus `vorgaenge.n_verschmolzen` gemessen: **4.809 Kennungen sind bei einem einzigen
Neuaufbau untergegangen**, aufgegangen in 4.322 Zielen. Das sind 0,3 %, aber es trifft die
Mappe eines Kunden voll, und lautlos.

**Reparatur, klein weil die Karte schon existiert:** `_anwenden` haelt sie im Speicher und
wirft sie weg. Sie muss als `vorgang_umzug.parquet` je Lauf geschrieben werden; die Mappe
zieht beim Lesen mit. Zusaetzlich speichert die Mappe die `notice_id`, aus der sie entstand,
als zweiten Anker.

Stabilitaet je Schluesselquelle (2026-09-15): `allein` 784.666 (stabil, die Bekanntmachung
IST der Vorgang) · `folder` 282.690 (stabil, ContractFolderID) · `rueckref` 352.825
(**wandert**, wenn eine aeltere Bekanntmachung die Wurzel der Verweiskette verschiebt).

### ⚠ Das Land gehoert in den Schluessel

48 Vorgangsnummern kommen in mehr als einem Land vor (AT∩DE 31, CH∩DE 9, DE∩PL 4). Beim
Buendelpfad hat genau das schon zugeschlagen. Ein Fremdschluessel ohne `land` ist hier kein
Schoenheitsfehler, sondern stiller Datenverlust.

## Fuenf Stufen

Die Reihenfolge ist nicht beliebig; jede Stufe macht die naechste moeglich.

### 1. Die Mappe als Behaelter
Eine Zeile je Kunde und Vorgang: Status, Notiz, Zustaendigkeit. Die Akte liefert Unterlagen,
Anforderungen, Fristen und Vorgeschichte bereits.

⚠ **Kein Neubau, sondern ein Umzug.** `user_watchlist` existiert und haengt an `lead_id`,
nicht am Vorgang; sie fuehrt schon Melde-Buchhaltung (`deadline_14d_sent`,
`expiry_warn_sent`). Es steht also ein Anker in Produktion, der dem Anker dieses Plans
widerspricht. Der Weg fuehrt ueber `vorgang_notice`, weil `lead_id` eine `notice_id` ist.
Dabei fallen mehrere gemerkte Bekanntmachungen desselben Vorgangs zu EINER Mappe zusammen:
gewollt, aber eine Verschmelzung fremder Daten, die man einmal richtig macht.

### 2. Vollstaendigkeit gegen die Akte pruefen
`doc_checklist` (571.677 Zeilen, 2026-09-15) weiss, was verlangt wird: 134.350 einzureichende
Dokumente, 56.009 Formalien, 43.979 Fristen, 7.243 Ausschlussgruende im Klartext (⚠ nur
7.243 von 30.904 Zeilen tragen einen Text). Die Mappe weiss, was der Kunde hat. Die Differenz
ist die Antwort.

⚠ **Bauen ja, bewerben nein.** Unterlagen liegen fuer 32 % der offenen Verfahren vor (4.719
von 14.923). Auf diesen 32 % hilft der Abgleich sofort, und „liegen uns nicht vor" ist eine
ehrliche Antwort. Was nicht geht: die Pruefung zum Aushaengeschild eines Pakets machen, das
bei zwei von drei Verfahren schweigt.

### 3. Nachweise mit Ablaufdatum
Praequalifikation, Unbedenklichkeitsbescheinigungen, Versicherungen, Referenzen. Der Punkt
ist das Datum, nicht die Ablage: Ein abgelaufener Nachweis fuehrt zum Ausschluss.

⚠ **Haengt am Mailversand.** `web/lib/email.ts` meldet heute Erfolg, ohne zu senden. Eine
Warnung, die nicht ankommt, ist schlimmer als keine.

### 4. Wiederkehr: die Kette zieht die alte Mappe herbei
Hat der Vorgang einen Vorgaenger mit einer Mappe desselben Kunden, oeffnet sich die neue mit
dessen Inhalt, daneben der Anlaufvergleich (`anlauf_vergleich.parquet`, s. u.). Dazu die
Vorwarnung: **4.834 Ketten sind 2026/27 rechnerisch faellig** (Takt = Median der eigenen
Abstaende, mindestens 3 Glieder). Nachgeprueft: 98 % dieser Ketten haben ihr letztes Glied
ab 2022, 85 % ab 2024, Median-Takt 2 Jahre.

⚠ **Kettenguete muss mitlaufen.** Von 148.745 Gliedern sind 73.421 inhaltlich eindeutig
(`content_unique`), 27.849 maschinell entschieden (`llm_adjudicated`). Eine falsch angebotene
alte Mappe ist schlimmer als keine: bei schwacher Kette bestaetigt der Kunde die Zuordnung.

### 5. Ausgang erfassen, dann aufhoeren
Gewonnen oder verloren, und gegen wen. Das ist die Grenze. **79 % aller Gebote stammen von
Bietern, die nie genannt werden** (248.526 Gebote in 52.971 Verfahren mit bekannter
Bieterzahl, nur die 52.971 Gewinner sind namentlich bekannt). Diese Luecke fuellt nur, wer
sie selbst meldet.

⚠ **Kartellrecht gehoert in die Bauweise, nicht in die Fussnote.** Teilnahme und Ausgang zu
melden ist unproblematisch; Angebotspreise zwischen Wettbewerbern sichtbar zu machen kann
eine abgestimmte Verhaltensweise begruenden. Preise nur aggregiert, nie einem Einzelnen
zuordenbar, keine Auswertung auf weniger als eine Handvoll Melder. Mit den AGB klaeren.

## Wo das Modul aufhoert

| Schritt | Im Modul? | Begruendung |
|---|---|---|
| Finden und beurteilen | ja | das heutige Produkt |
| Vorbereiten | ja | Stufen 1 bis 4 |
| Exportieren | ja | fertige Mappe als Paket, der Kunde reicht selbst ein |
| Einreichen aus der Plattform | nur mit Partner | der rechtliche Akt gehoert cosinex, DTVP, e-Vergabe des Bundes. Eine verpasste Frist kostet den Auftrag des Kunden, nicht ein Abo. Vereinbarung, kein Bauvorhaben. |
| Ausgang erfassen | ja | Stufe 5, die Schleife |
| Vertrag durchfuehren | nein | anderes Produkt, anderer Kaeufer, besetzter Markt |

## Reihenfolge

- **Stufe 1, dann 4.** Der Behaelter allein ist wenig wert; mit der Kette entsteht sofort
  etwas, das kein Wettbewerber zeigen kann. Beide Datenteile stehen bereits.
- **Stufe 5 frueh, nicht spaet.** Eine Frage im Formular, und der Anfang des Datennetzeffekts.
  Wer sie ans Ende schiebt, sammelt ein Jahr lang nichts.
- **Stufe 2 nach der Abdeckung**, Stufe 3 **nach dem Mailversand**.

## Was danach anders ist

| Heute | Danach |
|---|---|
| Kuendigen kostet nichts | Kuendigen kostet das Gedaechtnis des Betriebs. Nach dem dritten Angebot ist der Wechsel keine Abo-Frage mehr. |
| Wir melden, was veroeffentlicht ist | Wir melden, was kommt (4.834 faellige Ketten). |
| 79 % aller Gebote sind anonym | Jede abgeschlossene Mappe fuellt eine Zelle, die niemand abgreifen kann. |
| Eine Ausschreibung steht fuer sich | Sie steht neben ihrem Vorgaenger, mit dem Unterschied daneben (9.972 Paare nach erfolglosem Anlauf). |
| Jede Ansicht ist in zwei Wochen nachgebaut | Nachbaubar bleibt die Software, nicht die Arbeit des Kunden darin. |

**Was es NICHT loest:** Dokumentenabdeckung bleibt 32 %. Preis der oberen Pakete bleibt ohne
beobachteten Vergleichswert. Das Produkt haengt weiter an einer Person. Und es entsteht kein
Kunde dadurch, dass das Modul existiert.

**⚠ Die eine Annahme, die keine Messung pruefen kann:** Der Plan setzt voraus, dass ein Bieter
eine Mappe tatsaechlich pflegt. Alles Weitere folgt daraus. Ob mittelstaendische Betriebe das
tun, steht in keinem Datensatz. Zehn Kundengespraeche beantworten das besser als jede weitere
Auswertung.

## Zuarbeit, die schon steht

- `scripts/build_anlaufvergleich.py` → `data/gold/<L>/anlauf_vergleich.parquet`: ein Vergleich
  je Kettenpaar. 101.270 Paare, davon **9.972 nach einem erfolglosen Anlauf**. Wert, Frist,
  Verfahrensart, Lose, CPV mit Wechselkennzeichen. Die Dokumentenspalten
  (`unterlagen_beide`, `anf_entfallen`, `anf_neu`) stehen im Schema und werden in DERSELBEN
  Abfrage befuellt, sobald beide Seiten Anforderungen tragen: erneut laufen lassen genuegt.
  ⚠ Am 2026-09-15 hat **kein einziges** Paar Unterlagen auf beiden Seiten; erste Paare
  entstehen von selbst, geschaetzt rund 400 binnen zwoelf Monaten (8,3 % der Verfahren
  scheitern, 4.719 offene sind dokumentiert, 11.861 Wiederholungen im selben Jahr).
  ⚠ `verfahren_status='erfolglos'` haengt zu 100 % am Zuschlag (`can`), nie an der
  Ausschreibung. Wer auf die Leitbekanntmachung verbindet, bekommt eine stille Null.
- `vorgang_kette`, `vorgaenge`, `vorgang_notice`, `doc_checklist`, `doc_positions`
  (1.243.063 LV-Positionen, 93 % mit Menge), Bausteinbibliothek: gebaut.
- `user_contracts`, `user_outcomes`, `user_declarations`, `user_watchlist`: Tabellen in
  Supabase, ohne Erfassungsoberflaeche.

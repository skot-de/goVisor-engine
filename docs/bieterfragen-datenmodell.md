# Bieterfragen: Datenmodell

**Stand:** 2026-09-01. Antwort auf die Rückfrage aus der Frontend-Sitzung
(„das ist kein Textwechsel, sondern ein neues Datenmodell").

Ergänzt `bieterfragen-feasibility.md` (27.07.), widerspricht ihr in **einem** Punkt.

---

## 0. Der Befund, der die Lage ändert

Die Studie schloss: Q&A-Inhalte stehen zu **0 %** in unseren Daten. Das galt für
**TED/eForms** und gilt dort unverändert. Als Aussage über den heutigen Korpus ist es
überholt, weil wir seither Portal-ZIPs herunterladen und in denen liegen die
Bieterinformationen mit drin.

Gemessen an `doc_text` (211.297 Dokumente mit Volltext), Doktyp `fragenantworten`:

| | Dokumente | Vorgänge |
|---|---:|---:|
| als `fragenantworten` erkannt | 2.217 | 1.034 |
| **davon mit Frage UND Antwort im Text** | **707** | **257** |
| ohne Antwort (Leerformular „FB6 Bieterfrage" u. ä.) | 1.510 | |
| **davon heute noch offen** | | **109** |

Der Doktyp-Erkenner steht bereits, in fünf Sprachräumen, mit Dateinamensregeln **und**
Inhaltsproben (`frage \d+:`, `^antwort:`, „beantwortung der bieterfragen").
`govisor/doctypes.py`, Eintrag `fragenantworten`.

**Folge für die Reihenfolge:** Der erste Schritt ist nicht die Beschaffung, sondern das
Modellieren dessen, was schon daliegt. Das kostet keine Aktivierung, keinen Crawler und
keine Nutzerhandlung — und beweist den Wert, bevor irgendjemand um einen Upload gebeten wird.

## 0.1 Warum die Aktivierung die Absage der Studie nicht bricht

Die Studie hat **Crawling** abgelehnt, mit vier Gründen: Login, robots, das Verbot
Konten anzulegen, und 8 bis 12 Engines Dauerpflege. Alle vier sitzen in der
**Beschaffung**. Die Aktivierung berührt keinen davon: der Bieter ist für genau dieses
Verfahren bereits registriert, hat die Bieterinformation bereits rechtmäßig erhalten und
gibt sie freiwillig weiter. Kein Crawler, kein Login, kein Engine-Parser, keine Pflege.

Was aus der Studie **stehen bleibt**: jedes inhaltliche Signal braucht LLM-Extraktion je
Verfahren. Diese Kosten sind seit dem 01.09. gedeckelt (`llm.UPLOAD_TAG_USD`, eigener
Tagestopf mit Vorrang, Commit `41cab60`).

---

## 1. Warum Q&A nicht in `doc_checklist` passt

Eine Vergabeunterlage ist ein **Zustand**. Ein Fragenkatalog ist ein **Verlauf**: er hat
eine Nummer, ein Datum, mehrere Fassungen, und er **ändert** die Unterlage rückwirkend.
Rechtlich wird die Antwort Bestandteil der Vergabeunterlagen.

Der Wert liegt deshalb nicht im Dialog, sondern im **Unterschied**. Ein Bieter, der die
Unterlagen an Tag 1 heruntergeladen hat, weiß nicht, was an Tag 12 geändert wurde. Genau
das ist die Lücke, die sonst niemand füllt — und sie verlangt eine eigene Tabelle mit
einem Verweis zurück auf die Anforderung, die sich geändert hat.

Beleg aus dem Bestand: ein Verfahren führt `Vergabeunterlagen/Version 13/
26_Bieterfragen-Antworten_...` mit **190.647 Zeichen**. Dreizehn Fortschreibungen.

---

## 2. `doc_qa` — eine Zeile je Frage/Antwort-Paar

| Feld | Inhalt |
|---|---|
| `notice_id` | Vorgang |
| `nr` | laufend im Vorgang, sortiert nach Bulletin und Fragennummer |
| `bulletin` | „Bieterinformation Nr. 3", „Version 13" — die Fassung, in der es kam |
| `frage_nr` | Nummer wie im Dokument angegeben |
| `frage` | Fragetext, geschwärzt (s. § 4) |
| `antwort` | Antworttext, wörtlich |
| `datum` | Datum der Antwort, wenn angegeben |
| `wirkung` | `praezisierung` · `aenderung` · `frist` · `verweis` · `keine` |
| `betrifft_req` | Verweis auf `doc_checklist.nr`, wenn die Antwort eine Anforderung ändert |
| `quote`, `source_file`, `source_page` | Beleg, gleiche Disziplin wie `doc_checklist` |
| `marking`, `parser` | `Zitat`/`Extrahiert`/`Abgeleitet`, `LLM`/`pdf_fields` |
| `beleg_stufe` | `korpus` (aus dem Portal-ZIP) · `nutzer` (hochgeladen) · `unbestaetigt` |

`wirkung` und `betrifft_req` sind die beiden Felder, die den Unterschied tragen. Ohne sie
ist die Tabelle ein Textarchiv; mit ihnen ist sie eine Änderungsverfolgung.

## 3. `doc_qa_stand` — eine Zeile je Vorgang, ohne LLM

Die billige Schicht, rein aus Zählen und Datumsvergleich:

| Feld | Warum |
|---|---|
| `n_bulletins` | Fortschreibungen. 13 ist ein Warnzeichen |
| `n_fragen` | der Frühindikator für Bieterinteresse, den die Studie wollte |
| `letztes_bulletin` | wie frisch der Stand ist |
| `tage_vor_frist` bei letzter Antwort | Fairnessmaß. ⚠ **Gemessen am 01.09.: Median 29 Tage, nur 2 von 82 unter 7 Tagen.** Die Vermutung, die Stellen antworteten zu spät, trägt nicht. Brauchbar als seltener Ausreißer-Hinweis, nicht als Regel |
| `frist_verschoben` | mit eForms `Change`/F14 abgleichbar, teils schon vorhanden |

Diese Tabelle braucht **kein** LLM und lässt sich auf die 707 Dokumente sofort rechnen.

---

## 4. Die zwei harten Punkte

### Der Fragesteller ist erkennbar, auch ohne personenbezogene Daten

„Wir sind Hersteller von X und verfügen über Referenz Y" ist kein Name und keine
Anschrift, aber es identifiziert. Die bestehende Schwärzung greift auf
personenbezogene Daten, nicht auf **wettbewerbliche Erkennbarkeit**.

Rechtlich ist das Bulletin an alle Interessenten verteilt. Unsere Leserschaft ist aber
nicht dieselbe Menge. Wer nie am Verfahren teilgenommen hat, erführe bei uns, was ein
Wettbewerber gefragt hat.

**Regel:** Die **Antwort** wörtlich zeigen, sie stammt von der Vergabestelle und ist die
verbindliche Aussage. Die **Frage** nur als normalisiertes Thema, es sei denn, die
Vergabestelle hat sie selbst schon anonymisiert veröffentlicht. Das ist eine
Entwurfsbedingung, kein Nachtrag.

### Ein gefälschtes Bulletin wäre eine neue Angriffsfläche

Bei Vergabeunterlagen fängt der Käufer-Abgleich (§5-4) das meiste ab. Bei Q&A wiegt es
schwerer, weil eine erfundene Antwort Wettbewerber gezielt in die Irre führen kann.

Drei Prüfungen, alle billig: nennt das Dokument die **Vergabenummer**, nennt es die
**Vergabestelle**, ist die **Bulletin-Nummer** lückenlos zur bekannten Reihe. Fällt eine
durch → `beleg_stufe='unbestaetigt'`, und eine unbestätigte Zeile darf **niemals still
eine angezeigte Anforderung überschreiben**. Sie steht daneben, gekennzeichnet.

---

## 5. Was daraus an einzigartigen Kennzahlen fällt

Ergänzt die Sammlung in `uebergabe-kennzahlen-aktivierung.md`:

1. **Antwortzeitpunkt gegen Frist** — beantwortet die Stelle so spät, dass niemand mehr
   reagieren kann? Braucht beides: die öffentliche Frist und das Bulletin-Datum.
2. **Fortschreibungsdichte** — wie oft wurden die Unterlagen geändert. „Version 13" ist
   ein Risikosignal, das im Bekanntmachungstext nirgends steht.
3. **Antwort ändert Anforderung** — die Delta-Kennzahl. Ohne die ursprünglichen
   Anforderungen *und* den Fragenkatalog nicht rechenbar. Das ist die schärfste.
4. **Fragenlast als Interessensvorlauf** — die Studie nannte sie „mittel belastbar";
   das bleibt richtig, Fragenzahl ist nicht Bieterzahl. Als weiches Signal brauchbar.

---

## 6. Vorschlag zur Reihenfolge

1. **`doc_qa_stand` auf den vorhandenen 707 Dokumenten.** Kein LLM, keine Aktivierung,
   keine Kosten. Liefert sofort Fortschreibungsdichte und Antwortzeitpunkt.
2. **`doc_qa` auf denselben 707.** Rund **34 $** einmalig bei 0,048 $ je Vorgang.
   ⚠ Das 190.647-Zeichen-Dokument liegt über dem Fenster und braucht den Strom-Pfad.
   Als eigener Stapel fahren, nicht über den Tagesdeckel.
3. **Erst dann die Aktivierung.** Wenn 109 offene Vorgänge zeigen, was ein Fragenkatalog
   hergibt, ist die Bitte „laden Sie die Bieterinformation hoch" belegt statt behauptet.

Schritt 1 und 2 hängen an keiner Nutzerhandlung. Das ist der Grund, sie zuerst zu machen.

---

## 7. Schritt 1 ist gebaut — was dabei herauskam

`scripts/build_doc_qa_stand.py`, Tabelle `data/gold/DE/doc_qa_stand.parquet` (257 Zeilen).
Vier Prüfungen in `tests/test_doc_qa_stand.py`, alle gegengeprobt.

**Zwei Messfehler, die beim Bauen aufgefallen sind:**

1. Die naheliegende Fassungsregel `Bieterinformation Nr. N` war mit **102 von 257**
   Vorgängen die größte Gruppe und in fast jedem nachgesehenen Fall falsch:
   `Bieterfragen Nr. 82-87` ist eine **Fragennummer**, `Bieterfragen_Stand_30.07.2026`
   ein **Kalendertag**, `ENSPE_50_Bieterfragen` ein **Projektkürzel**. Regel entfernt,
   nicht verschärft. Es bleibt `Version N` aus dem Portal-Pfad: 65 belegte Vorgänge,
   die übrigen 192 tragen `fassung_quelle='dokumentzahl'` und sind als Schätzung erkennbar.
2. Die Datumsermittlung lieferte 656 Tage vor der Frist und 114 Tage danach, aus
   Vertragsdaten im Fließtext. Plausibilitätsfenster 0 bis 180 Tage, Unplausibles wird
   NULL und im Bericht gezählt.

**Ergebnis:**

| | |
|---|---:|
| Vorgänge mit verwertbarem Fragenkatalog | 257 |
| Dokumente | 707 |
| verworfen als Leerformular | 1.510 |
| belegte Fassungszahl (Portal-Pfad) | 65 |
| Fortschreibungen, Spanne | 3 bis 13 |
| Antwortabstand zur Frist, Median | **29 Tage** |
| davon 7 Tage oder knapper | **2 von 82** |

⚠ **Beim Anzeigen entdoppeln.** Die zehn Vorgänge mit 13 Fassungen sind **eine**
Beschaffung, die als zehn Bekanntmachungen erscheint. Ungefiltert sieht das aus wie zehn
Befunde.

AT und CH laufen sauber durch und melden „nichts zu tun", sie haben kein `doc_text`.

**Noch offen und bewusst nicht von mir gemacht:** die Einhängung in `govisor/schema.py`,
`scripts/daily_leads.sh`, `govisor/verify.py` (FK) und `govisor/kennzahlen.py`. In den
ersten beiden Dateien liegen gerade uncommittete Änderungen der Frontend-Sitzung.

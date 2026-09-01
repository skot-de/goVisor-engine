# Übergabe: einzigartige Kennzahlen + Aktivierung

**Stand:** 2026-09-01. Alle Zahlen an den echten Dateien gemessen, nicht geschätzt.
Grundlage: `lead_export.parquet` (Bekanntmachung), `doc_signals.parquet` (Regex-Signale),
`doc_checklist.parquet` / `doc_analysis.parquet` (LLM, zitatgeprüft), `doc_text.parquet`,
`document_duplicates.parquet`.

**Wichtig:** `doc_analysis` / `doc_checklist` / `doc_verworfen` sind seit Commit `07bbd26`
(01.09., 14:45) in `scripts/daily_leads.sh` verdrahtet, aber **noch nie im Nachtlauf gebaut**
(letzter Lauf war 01:23). Erste echte Fassung entsteht in der Nacht auf den 02.09.
Bis dahin liegen sie nur als Probefassung im Sitzungs-Scratch.

---

## Teil 1 — Kennzahlen, die nur wir bilden können

Gemeinsames Merkmal: jede braucht **beide** Seiten, die öffentliche Bekanntmachung
*und* die aus den Unterlagen gewonnenen Werte. Wer nur eine Seite hat, kann sie nicht rechnen.

### Rechenfertig, Daten vollständig

| # | Kennzahl | Gemessen | Basis |
|---|---|---|---|
| 1 | **Aufwand gegen Zeitfenster** | Median 34 Tage, **unabhängig vom Aufwand** (9 bis 109 Anforderungen). Härtester Fall: 120 Anforderungen in 12 Tagen | 3.096 Vorgänge |
| 2 | **Strenge als Perzentil je Bereich** | Median / 90. Perzentil: Leistung 26/39, Formalitäten 19/39, Vertrag 6/18, Ausschluss 5, Eignung 3, Zuschlag 3 | alle analysierten |
| 3 | **Fingerabdruck der Vergabestelle** | z. B. BARMER verlangt Referenz-Mindestwert in 9 von 9 Verfahren, marktweit 6 % | 415 Stellen mit ≥3 Verfahren |
| 4 | **Formularaufwand** | Median 22 Pflichtfelder, Maximum 192 | 93.938 Dokumentforderungen |
| 5 | **Mengengerüst** | 495.891 LV-Positionen mit Menge und Einheit | 2.228 offene Leads |
| 6 | **Bezifferte Schwellen als Vergleichsgruppe** | 198.584 Zahlen, einordenbar gegen Median und Quartil | `wert_num` |
| 7 | **Vertragsstrafe beziffert** | fast alle bei 5 %, Ausreißer nach unten (Fraunhofer 2,2 %) | 13.370, davon 10.106 beziffert |
| 8 | **Standardtext-Anteil** | Median **≥10 %**, oberes Viertel **≥27 %**, **13 %** der Vorgänge sind zu über der Hälfte Kopie | Stichprobe 517 Vorgänge |
| 9 | **Widerspruch bei der Angebotsfrist** | **26 von 1.653 (1,6 %)** nennen in den Unterlagen eine **spätere** Frist als die Bekanntmachung; 70 (4,2 %) eine frühere | belegte Fristen beidseitig |

**Zu 8:** gemessen innerhalb von 600 Vorgängen, Absätze ab 120 Zeichen, Standardtext =
wortgleich in ≥3 Vorgängen. Im vollen Bestand finden mehr Absätze Partner, die Werte sind
also eine **Untergrenze**. Dateiprüfsummen allein ergeben nur 2,1 % und taugen nicht.

**Zu 9:** nur mit dem scharfen Filter belastbar. Das Datum muss **im Zitat selbst** stehen,
und Binde-, Zuschlags- und Auskunftsfristen müssen ausgeschlossen werden. Ohne diesen Filter
kommen 598 Scheintreffer heraus. Kein Breitenmaß, sondern ein **seltener Warnhinweis mit
hohem Einsatz**: zwei der Fälle liegen exakt 365 Tage auseinander, also Jahreszahl-Tippfehler
in den Unterlagen. Die 70 Fälle „Unterlagen früher" sind der zweite Hinweis: veraltete Fassung.

### Gebaut, aber nicht verdrahtet

| # | Kennzahl | Zustand |
|---|---|---|
| 10 | **`evidence`** | 35,6 % Abdeckung, höchster Wert aller Signale, kommt im Frontend nie an |
| 11 | **Verlässlichkeit je Auswertung** | aus `rejected_items` und `doc_verworfen` ableitbar |

### Braucht Zeit

| # | Kennzahl | Frühestens |
|---|---|---|
| 12 | **Anforderungs-Drift** (dieselbe Stelle, zwei Runden: verschärft?) | Historie beginnt mit dem Lauf 02.09. |
| 13 | **Wirkung von Hürden auf die Bieterzahl** | heute 987 verbindbar, wächst mit jedem Zuschlag |

### Geprüft und verworfen

- **Die Ampel.** Rot (4,7 K.-o.-Kriterien) liegt praktisch auf gelb (4,7). Trennt nur grün vom Rest.
- **Anforderungen sagen sich gegenseitig vorher.** Eine brauchbare Regel von allen:
  Mindestumsatz → Referenzanzahl, 83 % gegen 26 % Grundrate. Zu dünn für ein Produkt,
  brauchbar als Vorbefüllung im Formular.
- **Bürgschafts-Widerspruch.** 598 vermeintliche Treffer sind fast alle Standardtext:
  VHB-Überschriften, der VOB/B-Gesetzestext selbst, ein Inhaltsverzeichnis und ein
  Wortgleichnis („Entgelttarifvertrag für Sicherheitsleistungen" meint das Wachgewerbe).
  Der Anker-Regex taugt für die Trefferlücke, **nicht** für eine Aussage.

### Nebenbefund, eigener Fehler

`gold.py:3392` wertet das eForms-Feld `RequiredFinancialGuarantee.GuaranteeTypeCode` nur auf
`true`/`false` aus. Das Feld trägt aber vier Werte: `false` (211.682), `true` (50.888),
**`none` (16.888)** und **`provisional` (16.101)**. Die letzten beiden fallen still auf NULL,
obwohl sie eindeutig sind: `none` = keine Sicherheit, `provisional` = vorläufige Sicherheit.
**33.000 Bekanntmachungen verlieren die Angabe grundlos.**

---

## Teil 2 — Aktivierung

Grundgedanke: jede Lücke, jeder Zweifel und jedes Ergebnis ist eine Einladung an den Nutzer.
Wir zeigen die Lücke nicht als Mangel, sondern als Tür. Der Nutzer gewinnt einen besseren
Datensatz, wir gewinnen Daten, an die niemand sonst kommt.

### Vier Regeln für jede Aktivierung

1. **Nur an der Fundstelle.** Die Bitte steht dort, wo die Lücke sichtbar wird, nie in einem eigenen Menü.
2. **Nie mehr versprechen als wir halten.** Kein „wir rechnen sofort", wenn der Tageslauf dazwischenliegt.
   Hochgeladene Unterlagen laufen mit Vorrang, aber unter eigenem Tagesdeckel; ist er erreicht,
   sagen wir ehrlich, wann es weitergeht.
3. **Ein Klick, nicht ein Formular.** Bestätigen, ankreuzen, Datei ziehen. Freitext ist immer freiwillig.
4. **Der Beitrag bleibt sichtbar.** Wer etwas beisteuert, sieht danach, was sich dadurch geändert hat.

### A — Aktivierung, die uns Dokumente bringt (der Moat)

| Auslöser | Text an der Fundstelle | Was wir gewinnen |
|---|---|---|
| `missing_expected`: Zuschlagskriterien fehlen (**4.747**) | „Die Zuschlagskriterien stehen nicht in den Unterlagen, die wir haben. Ladet die Wertungsmatrix hoch, dann ergänzen wir die Auswertung." | die häufigste Einzellücke |
| Eignung fehlt (**1.710**), Aufforderung fehlt (**1.107**) | analog | zweit- und dritthäufigste |
| Vorgang ganz ohne Unterlagen | „Zu dieser Ausschreibung liegen uns keine Unterlagen vor. Habt ihr Zugang zum Portal?" | Portale, an die wir nicht kommen (vergabe24) |
| Land AT oder CH | dieselbe Bitte, doppelt gewichtet | **0 % Dokumentenabdeckung** in AT und CH |
| **Bieterfragen und Antworten** | „Habt ihr Antworten der Vergabestelle erhalten? Die helfen allen Bietern." | existieren in unseren Daten **nicht** und sind **nicht abgreifbar** (siehe `bieterfragen-feasibility.md`). Stärkstes Ziel überhaupt |

### B — Aktivierung, die die Passung schärft

| Auslöser | Text | Was wir gewinnen |
|---|---|---|
| Passungszahl unvollständig | „Wir kennen eure Referenzen noch nicht. Zwei Angaben genügen für eine belastbare Zahl." | schließt die Lücke aus `govisor-userflow-befunde`: der Eignungs-Check **sammelt** Haftpflicht, Präqualifikation und ISO und **wirft sie weg**. Genau hier andocken |
| Kennzahl 9 feuert (Fristwiderspruch) | „Die Unterlagen nennen den 21.10., die Bekanntmachung den 16.09. Welche Frist gilt?" | Nutzer prüft für uns, wir lernen die Trefferquote des Filters |
| Eintrag in `doc_verworfen` | „Hier waren wir uns nicht sicher. Stimmt das so?" | schließt die Lernschleife mit dem Nutzer im Kreis |
| Kennzahl 8 hoch (viel Standardtext) | „Rund 60 % dieser Unterlagen sind Standardtext, den ihr kennt. Sollen wir nur das Abweichende zeigen?" | Nutzung als Signal, dass unsere Erkennung stimmt |
| **Pflicht-Ortstermin außerhalb der Regionen** (**108**) | „Dieser Vorgang verlangt einen Ortstermin, an dem ihr teilnehmen müsst, und er liegt außerhalb eures Gebiets. Fahrt ihr trotzdem hin?" | prüft die **Regionsgrenze**, die wir aus der Historie ableiten und nie gegenmessen |

**Zum Ortstermin.** Der Blocker steht seit dem 01.09. in `matchLead` und speist sich aus
`site_visit_mandatory` (bis dahin eines der sechs Signale, die erhoben und nie gezeigt
wurden). Er ist der einzige Auslöser in dieser Liste, der eine **eigene Annahme** prüft statt
einer Lücke in den Daten: die Regionsgrenze eines Nutzers leiten wir aus seiner Historie ab
und messen nie nach, ob sie stimmt. Wer „ja, wir fahren hin" antwortet, sagt uns, dass sie zu
eng ist — und das wirkt auf **jeden** seiner Leads, nicht nur auf diesen.

Die Zahl ist klein und das ist hier ein Vorteil: 108 von 3.723 erkannten Ortsterminen sind
verpflichtend. Der Auslöser feuert also selten genug, um nicht zur Tapete zu werden, und der
Einsatz ist im Einzelfall hoch (wer nicht erscheint, darf nicht bieten).

⚠ **Anrede: durchgehend „ihr/euch", entschieden am 01.09.** Die Texte in diesem Papier
siezten zunächst. Gemessen: die Anbieter-Seite des Produkts benutzt durchweg „ihr/euch"
(`profileEngine`, `DetailPanel`, Anmeldung, Onboarding), gesiezt wird ausschließlich die
**Käufersicht** (`VergabeblickView`: „Wie steht Ihre Stelle da?"). Aktivierung sitzt auf der
Anbieter-Seite, also Du. **Zehn Textstellen** in Teil 2 sind umgestellt.

⚠ Wer hier Texte ergänzt: das Zitat aus der Käufersicht bleibt gesiezt. Es ist kein
vergessener Rest, sondern die zweite Zielgruppe. Ein Suchen-und-Ersetzen über das ganze
Papier zerstört genau diese Unterscheidung.

### C — Aktivierung, die uns Marktdaten bringt

| Auslöser | Text | Was wir gewinnen |
|---|---|---|
| Frist abgelaufen, Nutzer hatte den Lead offen | „Habt ihr mitgeboten?" | **Bieterzahl**, die sonst nirgends steht |
| Antwort „nein" | „Woran lag es?" mit vier Ankreuzgründen | die wertvollsten Produktdaten überhaupt: **welche Hürde schreckt tatsächlich ab**. Speist Kennzahl 13 |
| Zuschlag an einen Dritten | „Kennt ihr das Unternehmen?" | Entity-Resolution bei den Gewinnern |
| Rahmenvertrag läuft aus | „Seid ihr heute Auftragnehmer?" | Amtsinhaber-Erkennung ohne Zuschlagsdaten |

### D — Aktivierung ohne Datengewinn, rein Bindung

- **Frist merken.** Ein Klick, Erinnerung vor Ablauf.
- **Vergabestelle beobachten.** „Diese Stelle schreibt etwa alle vier Jahre aus. Sollen wir euch erinnern?"
  Speist sich aus `buyer_loyalty` und `retender_signal`.
- **Partner suchen.** „Ihr erfüllt 8 von 10 Anforderungen. Für die restlichen zwei einen Partner suchen?"
  Der Unterbau steht bereits (siehe `govisor-partnersuche`), wartet nur auf das Dashboard.

### Kosten

Nur **A** kostet Geld, weil Unterlagen durch das LLM müssen. Deshalb der eigene Tagesdeckel
neben `TAG_USD`, mit gemeinsamer Reserve. **B, C und D kosten nichts** und brauchen keinen Deckel,
nur ein Feld in der Datenbank. Das ist der Grund, sie zuerst zu bauen: der größte Teil der
Aktivierung ist umsonst zu haben.

---

## Nachtrag 01.09., zweite Runde

### 14 — Gewichtung der Zuschlagskriterien aus den Unterlagen *(stärkster Neuzugang)*

Kein Widerspruchsmaß, sondern ein Vervollständigungsmaß. Die Bekanntmachung trägt nur
**Namen** („Technik · Preis"), nie Prozente. Gemessen an offenen Vorgängen mit mehreren
Zuschlagskriterien:

- **2.283** offene Vorgänge haben mehrere Zuschlagskriterien
- **1.829 davon (80 %)** nennen in der Bekanntmachung **keine einzige Gewichtung**
- für **205** liefern die Unterlagen sie heute schon

Beispiel: Bekanntmachung „Technik · Preis", Unterlagen „Optik/Gesamteindruck 70 %, Preis 30 %".
Das ändert eine Bietentscheidung. Die Deckung ist allein durch die Dokumentenabdeckung begrenzt,
sie wächst also mit jeder Aktivierung aus Teil 2 A.

### 15 — Aufwand je Euro Auftragswert *(brauchbar als Filter, nicht als Schlagzeile)*

- Median **0,15** Anforderungen je 1.000 EUR, Viertel bei 0,085 und 0,24
- Spreizung nur **3-fach**, damit als Kennzahl unauffällig
- Interessant sind die Ränder: 38 Anforderungen für **3.218 EUR** gegen 38 Anforderungen für
  **54,6 Mio EUR**. Gleicher Aufwand, siebzehntausendfacher Auftrag
- Basis 3.463 Vorgänge mit Wert und Anforderungszahl

Einsatz: als Ausschlussfilter für kleine Bieter („unverhältnismäßiger Aufwand ausblenden"),
nicht als angezeigte Zahl.

### Zusätzlich geprüft und verworfen

- **Widerspruch bei den Zuschlagskriterien.** Nicht rechenbar. Die Bekanntmachung führt
  ausschließlich Kriteriennamen, keine Gewichte. Es gibt keine zwei Zahlen zum Vergleichen.
  Genau daraus wurde Kennzahl 14.
- **Vergabedienstleister aus Dokumentdubletten.** Idee: dieselbe nicht-amtliche Datei bei
  vielen Vergabestellen verrät das betreuende Büro. Gemessen: 670 Dublettengruppen, 277
  angeblich außerhalb der Standardformulare. Die Spitzenreiter sind aber erneut Vordrucke,
  die der Filter nicht erwischt hat (513 EU 10-2018, 511 EU 02-2024, VOL-B, Allgemeine
  Vertragsbedingungen), der Rest sind namenlose Dateien wie `3939281.pdf`. **Kein Signal.**

### Woran alles hängt

Der Vorrat an *neuen* Kennzahlen aus dem heutigen Datenbestand ist damit erschöpft. Die
verbleibende Steigerung liegt nicht in weiteren Kennzahlen, sondern in der **Abdeckung**:
fast jede Zahl oben steht auf nur rund 2.000 bis 3.500 Vorgängen, weil nur so viele offene
Leads Unterlagen haben. Kennzahl 14 kann für 1.829 Vorgänge etwas sagen und tut es für 205.

Das ist der eigentliche Grund für Teil 2. Aktivierung ist keine Nebensache neben den
Kennzahlen, sie ist der Multiplikator für jede einzelne davon.

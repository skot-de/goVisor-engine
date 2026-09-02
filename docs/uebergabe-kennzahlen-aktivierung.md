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
| 4 | ~~**Formularaufwand**~~ → **Umfang der Formulare** | ⚠ **korrigiert, siehe unten** — gebaut als „grösstes einzelnes Formular", Median 23 Felder je Formular, 12 % der Vorgänge über 400 | 31.799 Formulare in 5.469 Vorgängen |
| 5 | ~~**Mengengerüst**~~ → **Umfang des Leistungsverzeichnisses** | ⚠ **korrigiert, siehe unten** — gebaut als Gewerksvergleich zur bereits angezeigten Positionszahl | 1.382 Vorgänge in 12 Gewerken |
| 6 | **Bezifferte Schwelle gegen ihre Gruppe** | ⚠ **stark eingeschränkt, siehe unten** — von 223.570 Zahlen sind 2.208 einordenbar (1 %) | 10 Gruppen |
| 7 | **Vertragsstrafe beziffert** | ⚠ **zwei Zahlen, nicht eine, siehe unten** — 5 % ist die Obergrenze, 0,20 % der Tagessatz | 4.796 zugeordnet von 11.182 |
| 8 | **Standardtext-Anteil** | am vollen Bestand **29 % / 51 %**, 26 % über der Hälfte Kopie — gut das Dreifache der Stichprobe | 9.246 Vorgänge, 1,32 Mio. Absätze |
| 9 | **Widerspruch bei der Angebotsfrist** | bestätigt: 1,4 % später, 4,1 % früher — gemeldet werden 97 Vorgänge nach vier Filtern | 1.958 Vorgänge mit beiden Seiten |

**Zu 7 (aufgeteilt am 2026-09-02, beim Bauen):** „fast alle bei 5 %" stimmt — für die
**Obergrenze**. Vertragsstrafen gibt es als zwei verschiedene Zahlen, und sie stehen im
Verhältnis **1:25**:

| | n | Median | oberes Viertel |
|---|---|---|---|
| Obergrenze („insgesamt höchstens") | 3.958 | **5,00 %** | 5,00 % |
| Tagessatz („je Werktag") | 838 | **0,20 %** | 0,20 % |

⚠ **Die Kennzahl galt als fertig und war es nicht.** Das Verzeichnis führte sie als `penaltyPct`
mit Bezug „markt"; angezeigt wurde `${s.penaltyPct} %` — ohne jeden Vergleichswert. Schlimmer:
die Zahl war **zweideutig**. „Vertragsstrafe 0,3 %" konnte eine sehr milde Obergrenze oder ein
harter Tagessatz sein, und die Anzeige sagte nicht welches. Von den 4.114 Werten in
`penalty_pct` lassen sich 67 % ohne Beleg keiner der beiden zuordnen.

**Drei Funde beim Bauen, alle drei erst in den Daten sichtbar:**

1. **Das Einheitenfeld ist Fliesstext, kein Symbol.** „der Auftragssumme je angefangenen
   Werktag", „€ je Vorfall", „pro Woche", „maximal" — 2.123 Zeilen tragen so etwas. Die erste
   Fassung verwarf sie alle, weil sie keine bekannte Einheit fand. Der Text ist aber der beste
   Beleg, den es gibt: er sagt Geld oder Prozent **und** die Ausprägung.
2. ⚠ **Geschwisterzeilen teilen sich das Zitat.** Ein Vorgang mit „0,1 % je angefangenen
   Werktag" und „10 % insgesamt" hat für **beide** Zeilen denselben Belegsatz; nur das
   Einheitenfeld ist zeilengenau. Wer den gemeinsamen Text zuerst liest, bekommt bei genau den
   Vorgängen keine Zuordnung, die beide Zahlen nennen — also bei den interessanten. Das
   Einheitenfeld hat deshalb Vorrang; es entscheidet in 442 Fällen, das Zitat in 5.799.
3. **„Pro Woche" ist kein Tagessatz.** 134 Zeilen sagen „pro Woche", 44 „pro
   Überschreitungsfall": eigene Bezugsgrössen. Ein Wochensatz von 0,5 % neben Tagessätzen von
   0,20 % wäre ein Fehlalarm. Sie fallen heraus.

Angezeigt wird jetzt die Ausprägung („0,3 % je Werktag") und, wo der Wert über dem oberen
Viertel seiner eigenen Gruppe liegt, der Vergleich. Ein Beleg, der weder Tagessatz noch
Obergrenze hergibt, bekommt beides nicht — die Zahl bleibt nackt statt falsch beschriftet.

**Zu 6 (eingeschränkt am 2026-09-02, beim Bauen):** Zahlen gibt es sogar mehr als versprochen
(223.570 statt 198.584), einordenbar ist rund **ein Prozent**. Drei Filter liegen dazwischen, und
jeder steht für eine eigene Fehlerart:

1. **Ohne Einheit kein Vergleich.** Bei `technische_mindestanforderung` fehlt sie in 66 % der
   Fälle, bei `vertragsstrafe` in 81 %, bei `zertifikat` in 97 %. „Median 20" ist 20 mm oder 20
   Jahre. ⚠ Und eine Einheit kann einen **Faktor** tragen: „1,5 Mio. EUR" gegen „1.500.000 EUR"
   verglichen wäre ein Fehler um das Millionenfache. Solche Schreibweisen werden verworfen, nicht
   geraten.
2. **Die Gruppe muss eine Grösse benennen.** Ein Urteil, kein Rechenschritt. Draussen sind unter
   anderem `technische_mindestanforderung` („mindestens 20 %" — wovon? Steigung, Recyclinganteil,
   Rabatt), `frist` (Bindefrist und Ausführungsfrist im selben Topf) und `leistung_menge`
   (mischt Türen und Schrauben, und ist Kennzahl 5). ⚠ **Stabilität allein reicht nicht:**
   `technische_mindestanforderung / Prozent` besteht die Driftprüfung mühelos und ist trotzdem
   unvergleichbar.
3. ⚠ **Misst die Zahl den Vorgang oder misst sie uns?** Diese Prüfung rechnet der Export bei
   **jedem Lauf** neu, statt das Urteil von heute einzufrieren. Durchgefallen sind unter anderem:

   | Gruppe | flach gelesen | tief gelesen | |
   |---|---|---|---|
   | Mindestumsatz / EUR | 400.000 | 1.000.000 | 2,5× |
   | Referenz-Mindestwert / EUR | 500.000 | 300.000 | 1,7× |
   | Vertragsstrafe / EUR | 1.250 | 75 | 16,7× (gemischte Skala) |

   ⚠ **Beim Mindestumsatz war die naheliegende Erklärung falsch.** „Tief gelesene Vorgänge sind
   grosse Vergaben, die verlangen eben mehr" klingt zwingend: nachgemessen korreliert die
   Schwelle **nicht** mit dem Auftragswert (0,24; bei der Berufshaftpflicht sogar −0,09), und der
   Anstieg bleibt **innerhalb jedes Regelwerks** bestehen (VgV 480.000 → 1.500.000). Es ist
   unsere Lesetiefe.

**Und ein Fund, der erst im Beleg auffiel:** die Deckungssummen sind nach **Schadensart**
gestaffelt und spreizen dabei um das Sechsfache. Schlimmer noch, **28 % aller Belege nennen eine
kombinierte Deckung** („Mindestdeckungssumme von 3 Mio. EUR für Personen-, Sach- und
Vermögensschäden") — eine Summe für alles. Die abgekürzten Glieder tragen das Wort „schäden"
nicht, deshalb traf die Schlagwortsuche nur das letzte und verglich eine kombinierte Deckung
gegen reine Vermögensschaden-Summen. Sie hat jetzt eine eigene Gruppe, und ein Fehlalarm ist
dadurch zu Recht verschwunden.

**Sie hat keine eigene Anzeige.** Die Zahl stand seit jeher in der Checklistenzeile; ergänzt ist
nur die Einordnung daneben, und nur nach oben: eine niedrigere Deckungssumme ändert keine
Entscheidung. Bei zwei Gruppen fällt das obere Viertel mit dem Median zusammen (Vertragsstrafe
5 %, Referenzen 3), deshalb greift der Vergleich nur bei **echt darüber**.

**Zu 5 (korrigiert am 2026-09-02, beim Bauen):** die „495.891 LV-Positionen" **liegen
nirgends**. Sie wurden beim Parsen gezählt und nie gespeichert: `docpipe.py` macht aus
GAEB-Positionen Text, damit sie durchsuchbar sind. Zwei weitere Befunde beim Nachbauen, und
beide sind Lehren für die nächste Kennzahl:

1. ⚠ **Die Zahl stand längst in der App.** Der Block „Leistungsumfang" zeigt `nPositionen` aus
   `doc-struktur.json` seit jeher, samt Mengen je Einheit und Positionstabelle. Eine zweite
   Kachel mit derselben Zahl wäre Doppelung gewesen. Gebaut ist deshalb **nur der Vergleich**,
   und er hängt an der vorhandenen Zeile. *Wer eine Kennzahl baut, sucht zuerst, ob ihre Zahl
   schon irgendwo steht.*
2. ⚠ **Die erste Quelle war die falsche.** Der erste Versuch zählte `leistung_menge`-Zeilen aus
   `doc_checklist` statt der geparsten Positionen. Er sah weniger Vorgänge, und an seiner Spitze
   standen **Lastgänge**: Viertelstundenwerte eines Jahres in einer Tabelle, bis 200.010 Zeilen.
   „200.010 Positionen zu bepreisen" wäre bei jeder Stromausschreibung falsch gewesen.

   | | Vorgänge | Median | Maximum |
   |---|---|---|---|
   | `doc_positions` (geparst, benutzt) | 3.770 | 96 | 9.411 |
   | `doc_checklist` (abgeleitet, verworfen) | 2.812 | 83 | **200.010** |

**Verglichen wird je Gewerk (CPV 4-stellig), nicht global.** Innerhalb von CPV 45 spreizen die
Mediane **5,4-fach**: Installationsarbeiten (4533) 292 Positionen, Anstricharbeiten (4544) 54.
Ein Median über alle Bauarbeiten markierte jedes normale Installations-LV als gross. Ein
verkürzter CPV („45" ohne Gewerk, 239 Vorgänge) bekommt **keinen** Vergleich: „neun von zehn
Verzeichnissen dieses Gewerks" über einen Topf, in dem jedes Gewerk liegt, wäre eine Behauptung,
die das Wort nicht deckt.

**Und sie darf vergleichen, wo Kennzahl 4 es nicht darf** — gemessen, nicht gesetzt: das grösste
LV je Vorgang ist über die Lesetiefe stabil (69 → 96 → 78), die Formularsummen wachsen monoton
mit. Angezeigt wird der Vergleich nur am oberen Rand: „üblich sind 292" bei einem LV im
Mittelfeld ist keine Nachricht, sondern eine Zeile mehr.

**Zu 4 (korrigiert am 2026-09-02, beim Bauen):** von „Median 22 Pflichtfelder, Maximum
192" hält nichts, und die drei Gründe sind drei verschiedene Fehlerarten. Es lohnt sich, sie
auseinanderzuhalten, weil die dritte in jeder weiteren Kennzahl aus Dokumenten wieder auftauchen
kann.

1. **Falsche Grösse.** „Pflicht" ist ein Kennzeichen im PDF, das kaum jemand setzt: **93 %**
   aller 31.799 Formulare tragen null Pflichtfelder, auch **92 %** derjenigen mit über 50
   Feldern. Ein 95-Felder-Vergabeformular ohne ein einziges Pflichtfeld gibt es nicht. Die Zahl
   misst die Formularsoftware, nicht die Vergabe.
2. **Falsche Ebene.** Die „22" stimmt sogar fast (gemessen 23), aber je **Formular**, nicht je
   Vorgang. Je Vorgang liegt der Median der Pflichtfelder bei **0**, drei Viertel haben gar keine.
3. ⚠ **Falscher Messgegenstand, und das ist die teure.** Summen je Vorgang wachsen mit der Zahl
   gelesener Dateien: **2 → 7 → 16** Formulare bei 1-5 / 6-15 / 16-40 gelesenen Dateien, Felder
   **60 → 327 → 606**. Ein Plateau gibt es bei keiner Lesetiefe, und auch keins in den 165
   Vorgängen, deren Unterlagen vollständig aus **einem** ZIP kamen. Wer diese Summe anzeigt,
   zeigt unsere Abrufquote als Eigenschaft der Ausschreibung.

Gebaut ist deshalb nur, was von der Lesetiefe unabhängig ist: **Anwesenheit**. Ein Formular, das
wir gesehen haben, ist da; seine Abwesenheit dürfen wir nicht behaupten. Die Kennzahl sagt nie
„wenig Aufwand" und hat **keinen Marktvergleich** — ein marktweiter Median stammt aus derselben
Untererfassung, und dagegen verglichen sähe jeder tief gelesene Vorgang extremer aus als er ist.

Angezeigt wird ab 100 Feldern (47 % der Vorgänge mit Formularen) eine graue Notiz, ab 400 (12 %)
ein Warnhinweis. Von den 636 Vorgängen über 400 Feldern sind 472 VHB-Formblätter, also
Preisblätter: das ist Kalkulationsarbeit von Tagen, und sie steht nirgends in der Bekanntmachung.

**Zu 13 (Negativbefund, gemessen am 2026-09-02):** die Datenlage ist besser als beim Nachbarn —
**1.114** offene Vorgänge haben Unterlagen *und* eine Bieterzahl. ⚠ Aber die Bieterzahl gehört
zum **Vorgänger**, die Anforderungen zum aktuellen Verfahren; die Verbindung ist der Käufer,
nicht der Vorgang. Und der Effekt ist nicht da:

1. **Über die Hürdenzahl: kein Signal.** Median 4,0 / 3,0 / 4,0 / 4,0 bei 0 / 1–2 / 3–5 / 6+
   Hürden; Einzelbieteranteil 19 / 16 / 18 / 21 %.
2. **Je Anforderungsart sah es nach etwas aus** — und war der Lesetiefe-Effekt eine Ebene höher.
   Die scheinbar wirksamen Arten kommen in 70–90 % der Vorgänge vor, die „ohne"-Gruppe sind dünn
   gelesene Fälle. Die echten Hürden standen bei **4,0 gegen 4,0**.
3. ⚠ **Innerhalb einer Wertklasse erschien der Effekt dann doch** — und die **Replikation** hat
   ihn zerlegt:

| Hürde | <250k | 250k–1M | >1M |
|---|---|---|---|
| Referenz-Mindestwert | — | **2,0 / 4,0** | — |
| Berufshaftpflicht | 3,5 / 1,0 | 3,0 / 4,0 | — |
| Eignung Personal | 3,0 / 1,0 | 3,0 / 4,0 | 5,0 / 3,0 |
| Zertifikat | 3,0 / 1,0 | 4,0 / 4,0 | 5,0 / 3,0 |

Keine einzige Hürde zeigt in allen drei Klassen dieselbe Richtung. **Hätte ich nur die mittlere
Klasse gemessen, stünde jetzt „Referenz-Mindestwert halbiert das Bieterfeld" in der App.**

⚠ **Warum die kleine Klasse alles umdreht:** 1.486 ihrer 1.694 Vorgänge haben weniger als fünf
extrahierte Anforderungen, und deren Median-Bieterzahl ist **1,0** (der Rest: 4,0). Es ist immer
dieselbe Menge kaum gelesener Vorgänge, die als „ohne Hürde" gilt.

Der gemeinsame Treiber ist die **Grösse**: die Bieterzahl steigt mit der Lesetiefe (3 → 4 → 5 → 5)
und mit dem Auftragswert (3 → 4 → 5) in derselben Form.

⚠ **Die Bieterzahl selbst ist nicht das Problem** — 1/2/3/4/5 mit natürlichem Abfall, die 999
kommt genau einmal vor. Der Befund steht auf sauberen Daten.

**Was es bräuchte:** Bieterzahlen am *selben* Vorgang, dessen Unterlagen wir gelesen haben — also
die Aufbewahrung von Dokumenten über den Zuschlag hinaus. Dieselbe Voraussetzung wie bei der
Anforderungs-Drift.

**Zu 12 (nicht rechenbar, geprüft am 2026-09-02):** die Anforderungs-Drift zwischen zwei
Runden derselben Stelle lässt sich mit den heutigen Daten nicht bilden, und zwar **strukturell**,
nicht wegen einer Lücke:

    contract_succession × doc_checklist  =  0 Paare
    Nachfolger mit Unterlagen: 0  ·  Vorgänger mit Unterlagen: 0

Vergabeunterlagen existieren nur **während laufender Angebotsfrist**; ein Vorgänger ist per
Definition abgeschlossen. Die beiden Bestände sind disjunkt und bleiben es, solange wir Dokumente
nach dem Zuschlag nicht aufbewahren. Der Eintrag bleibt deshalb offen — mit dem Blocker
daneben, damit die nächste Sitzung nicht dieselbe Sackgasse ausmisst.

**Gebaut ist stattdessen die Drift INNERHALB des Verfahrens**, und sie ist näher an der
Entscheidung: eine Verschärfung zwei Runden zurück ist Marktkunde, eine geänderte Datei seit
gestern kostet Geld. **209 Vorgänge tragen mehrere Fassungen, 93 davon noch offen — und alle 93
haben im letzten Schritt eine Änderung** (Median 3 Dateien). Betroffen sind genau die Dateien,
auf die es ankommt: `Leistungsverzeichnis`, `Anlage 201 Eignungskriterien`, `Anlage 100
Bewerbungsbedingungen`.

⚠ **Verglichen wird der letzte Schritt**, nicht Fassung 1 gegen die neueste: wer die Unterlagen
gestern gezogen hat, will wissen, was seitdem passiert ist.

⚠ **„Geändert" ist der gefährliche Fall, nicht „neu"** — gleicher Dateiname, anderer Inhalt. Wer
die Datei schon hat, sieht keinen Anlass, sie noch einmal zu ziehen. Die geänderten werden
deshalb namentlich genannt, Neuzugänge nur gezählt.

**Zu den Bieterfragen (widerlegt am 2026-09-02):** das Papier führt sie als stärkstes Ziel
überhaupt und behauptet zugleich, sie existierten in unseren Daten **nicht** und seien **nicht
abgreifbar**. Die erste Hälfte stimmt, die zweite nicht mehr.

⚠ **Die zitierte Machbarkeitsstudie ist nicht falsch, sondern überholt.** Sie hat am 27.07. die
**eForms-Attribute der Bekanntmachungen** durchsucht (475,3 Mio. Zeilen) und dort zu Recht nichts
gefunden. Die Q&A stecken in den **Vergabeunterlagen** — als Bieterinformation,
Bieterfragenkatalog, Bieterrundschreiben. Gemessen:

| | |
|---|---|
| Vorgänge mit Fragerunde (`doc_qa_stand`) | **257** |
| davon mit lesbarem Text | **172** |
| verschiedene Abschnitte | **1.336** (Median 4 je Vorgang) |
| noch offene Vergaben | **71** |

*Wer eine Machbarkeitsstudie zitiert, prüft, welche Quelle sie untersucht hat.*

**Was gebaut ist:** ein Block im Lead-Detail, der die Abschnitte zeigt, jeden mit seinem
Dokument, und die Rechtslage nennt — § 20 Abs. 3 EU-VgV: die Auskünfte müssen allen Bietern
zugänglich sein, gelten also auch für den, der nicht gefragt hat.

⚠ **Es sind Abschnitte, keine Frage-Antwort-Paare.** Die Marke im Dokument trennt, sie ordnet
nicht: nur **35 %** der Abschnitte enthalten überhaupt ein Fragezeichen. Zwei Spalten Frage und
Antwort behaupteten eine Zuordnung, die die Daten nicht hergeben.

⚠ **Entdubliert wird über den Text, nicht über den Dateinamen.** Derselbe Bieterfragenkatalog
liegt als Stand 10.08., 13.08. und 20.08. im Paket; ohne diese Regel zählte er viermal
(gemessen 264 Marken statt 66).

**Die Aktivierung aus dem Papier bleibt sinnvoll** — für die Vorgänge ohne Fragerunde in unseren
Daten. Sie ist nicht gebaut.

**Zu 11 (gebaut am 2026-09-02, in meiner Reihe die zehnte):** sie ist die einzige, die nicht
die Vergabe misst, sondern **uns**. Jede Aussage des Modells muss sich mit einem Zitat belegen
lassen; was das nicht schafft, wird verworfen.

⚠ **Sie brauchte keinen Export.** `rejected_items` lag längst im Lead-Detail, und im
Haftungshinweis stand sogar die Zahl („12 unbelegte Aussagen wurden verworfen"). Was fehlte, war
nicht die Zahl, sondern ihre Bedeutung. Der Halbsatz weicht jetzt, wenn die Zeile steht — zwei
Stellen mit derselben Zahl wären Doppelung.

**Und die Bedeutung ist nicht die naheliegende:** ein hoher Verwurfsanteil heisst **lückenhaft,
nicht falsch**. Angezeigt wird nur, was die Belegprüfung bestanden hat. Gemessen über 8.104
Auswertungen: ab 50 % Verwurf fallen die behaltenen Punkte von 59 auf 20, die fehlenden
Doktypen steigen von 1 auf 2. Verteilung: Median 8 %, p75 17 %, p90 30 %, über 50 % nur 2,4 %.

⚠ **Fast alles sind Belegfehler:** 3.967 von 4.006 aufgeschlüsselten Verwürfen (99 %) scheiterten
an der Zitatprüfung, 39 am Schema, 0 am Typ. Die Aufschlüsselung `rej_schema`/`rej_typ`/`rej_beleg`
gibt es aber **erst seit dem 02.09.** — 916 von 8.104 Auswertungen. Wer sie auswertet, misst den
neuen Bestand, nicht den ganzen.

⚠ **Absichtlich nicht nach Modell gerahmt**, obwohl die Quote 3,2-fach spreizt (gpt-5.6-luna 4 %,
gemini-2.5-flash 8 %, Llama-3.3-70B 11 %). Das ist der Punkt, an dem die sonst richtige Regel
„vergleiche im richtigen Rahmen" kippt — Begründung in der Bibel.

**Zu 9 (gebaut am 2026-09-02):** die Zahlen des Papiers sind bestätigt — von 1.958 Vorgängen
mit beiden Seiten stimmen 94,5 % überein, 4,1 % nennen in den Unterlagen eine **frühere** Frist,
1,4 % eine **spätere** (Papier: 4,2 % und 1,6 %).

⚠ **Ein Fehlalarm kostet hier eine Angebotsabgabe.** Deshalb vier Filter, und jeder stammt aus
den Belegen, nicht aus einer Schätzung:

1. **Nur die Angebotsfrist.** `req_type='frist'` mischt Binde-, Zuschlags-, Ausführungs-,
   Rückfrage- und Lieferfristen. Von 33.399 Fristzeilen benennen 4.586 eindeutig die
   Angebotsfrist (13,7 %).
2. **Höchstens 30 Tage Abweichung.** Innerhalb davon lauten die Zitate durchweg „Ablauf der
   Angebotsfrist Datum … Uhrzeit …". Darüber steht anderes: `-66 Tage` ein Seitenkopf
   („VERGABEUNTERLAGE · Seite 26 von 653"), `+435` eine Lieferfrist aus der Vertragsphase,
   `-1268` ein Rückblick auf 2023.
   ⚠ Die **±365-Tage-Fälle** („Die Angebotsfrist endet am 10.09.2027") bleiben bewusst stumm:
   das *kann* ein echter Jahresdreher des Auftraggebers sein — und genau deshalb wird er nicht
   gemeldet. Ohne das Dokument zu öffnen lässt sich sein Tippfehler nicht von unserem Lesefehler
   unterscheiden. Bei einer Frist ist Schweigen billiger als Raten.
3. **Keine Seitenköpfe.**
4. **Der Beleg muss das Datum tragen**, das er belegen soll. 93 % tun das ohnehin, **0 % nennen
   ein anderes** (das wäre das Alarmzeichen), 7 % gar keines — dort stammt der Wert aus einem
   Formularfeld und das Zitat ist nur dessen Etikett. Kostet 3 von 100 Fällen.

⚠ **Und ein Befund, der die Kennzahl entlastet hat.** Fünf Fälle mit genau −1 Tag hintereinander
sahen zuerst nach einem Datumsfehler von uns aus. Die Verteilung spitzt aber auf **Vielfachen
von sieben** (−14: 18 Fälle, −7: 17, +14: 5; **51 von 100 sind exakte Wochenvielfache**, zufällig
wären es 14 %) — das ist die Signatur verlängerter Fristen. Bei einem Off-by-one wäre der Gipfel
bei ±1; dort liegen 6 %.

**Die Anzeige urteilt deshalb nicht, welche Seite recht hat.** Mal bleibt das alte Dokument nach
einer Verlängerung liegen, mal trägt das Dokument die Verlängerung und die Bekanntmachung nicht
(„Ablauf der Angebotsfrist nach Verlängerung: 23.09.2026" steht so in den Unterlagen). Genannt
werden beide Daten, der Beleg mit Dateiname — und der eine Satz, der immer stimmt: **die frühere
Angabe ist die sichere.** Als einzige Kennzahl dieser Reihe in Warnrot.

**Zu 8 (gebaut am 2026-09-02):** die Untergrenzen-Warnung des Papiers stimmt, und zwar
deutlich. Am vollen Bestand (9.690 Vorgänge, 1,32 Mio. verschiedene Absätze, 4,2 Mrd. Zeichen,
rund 90 Sekunden Rechenzeit):

| | Papier (600 Vorgänge) | voller Bestand |
|---|---|---|
| Median | ≥10 % | **29 %** |
| oberes Viertel | ≥27 % | **51 %** |
| über die Hälfte Kopie | 13 % | **26 %** |

⚠ **Die Vergleichsgruppe ist die TEXTMENGE, nicht das Regelwerk** — das war nicht die erste
Vermutung. Das Regelwerk trennt sichtbar, die Textmenge doppelt so stark, und ihr Muster
wiederholt sich *innerhalb* jedes Regelwerks:

| | 50–200 Tsd. | 200–800 Tsd. | über 800 Tsd. |
|---|---|---|---|
| VOB | 41 % | 23 % | 10 % |
| VgV | 37 % | 26 % | 5 % |
| UVgO | 46 % | 36 % | zu dünn |
| sonst | 42 % | 25 % | 12 % |

Spreizung: **Textmenge 4,1×**, Regelwerk 1,8×. Der Grund ist inhaltlich, nicht statistisch:
grosse Pakete tragen ein eigenes Leistungsverzeichnis und eigene technische Anlagen, und die
stehen nirgends sonst. Wer global vergleicht, nennt jede kleine Vergabe „viel Kopie" und jede
grosse „ungewöhnlich eigen".

⚠ **Unter 50 Tsd. Zeichen ist die Zahl Rauschen:** dort landen 35 % der Vorgänge bei genau 0 %
(darüber 3 %) — zu wenige Absätze, um überhaupt Partner finden zu können. Sie bekommen keinen
Wert statt eines schlechten. Das kostet 444 von 9.690 Vorgängen.

**Negativbefund, geprüft und verworfen:** Geschwistervergaben (ein Projekt in mehreren Losen,
gleiche Dateien) blähen die Zahl **nicht** auf. Nur 5,6 % der Standardabsätze erreichen die
Dreier-Schwelle ausschliesslich über Geschwister; Median und Anteil der 100-Prozent-Fälle sind
identisch, ob man je Vorgang oder je Projekt zählt.

**Angezeigt** wird sie im Kopf des Volltext-Blocks, direkt neben „1.152 Tsd. Zeichen" — dort
entscheidet jemand, ob er das liest. **Ohne Warnfarbe:** ein hoher Anteil ist keine schlechte
Nachricht, sondern weniger Arbeit.

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
| 11 | **Verlässlichkeit je Auswertung** | ✅ gebaut 02.09. — ohne Export, s. unten |

### Braucht Zeit

| # | Kennzahl | Frühestens |
|---|---|---|
| 12 | **Anforderungs-Drift** (dieselbe Stelle, zwei Runden: verschärft?) | ⚠ **nicht rechenbar, siehe unten** — stattdessen die Drift im laufenden Verfahren gebaut |
| 13 | **Wirkung von Hürden auf die Bieterzahl** | ⚠ **nachgemessen, Effekt nicht vorhanden** — siehe unten. 1.114 verbindbar, aber die Bieterzahl gehört zum Vorgänger |

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
| **Bieterfragen und Antworten** | wir haben sie | ⚠ **Annahme widerlegt, siehe unten.** 257 Vorgänge mit Fragerunde, 172 mit lesbarem Text, 71 noch offen. Seit 02.09. im Lead-Detail |

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

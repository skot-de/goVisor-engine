# Wettbewerb und Positionierung

**Zweck:** Gesprächsvorbereitung für den Vertrieb, nicht Eigenlob. Enthält bewusst auch,
**wo wir schwächer sind** — wer das im Gespräch zum ersten Mal hört, hat schon verloren.

**Stand:** 2026-10-05, abends. ⚠ Jede Zahl hier trägt dieses Datum. Wer sie ändert, zieht das
Datum mit. Zusammengetragen aus drei parallel arbeitenden Sitzungen; wer was beigetragen hat,
steht am Ende.

---

## ⛔ Was der Vertrieb NICHT sagen darf

**Dieser Abschnitt steht vorn, weil er im Gespräch zuerst gebraucht wird.** Jeder Punkt ist ein
Satz, der sich gut anhört und an einer Messung gescheitert ist. Wer ihn trotzdem sagt, verliert
das Gespräch beim ersten Nachfragen — und zwar bei einem Kunden, der es prüfen kann.

| ⛔ nicht sagen | warum nicht, gemessen |
|---|---|
| „Wir zeigen Ihnen Ihre Position im Markt." | An sieben Firmen durchgerechnet: **0,8 % bis 8,6 %** der Vergabestellen sind welche, bei denen sie je gewonnen haben — auch mit der richtigen Grundgesamtheit (Feld × Region statt nationaler Top-60). 57 von 60 Kacheln wären grau. Das ist die Form des Marktes, kein Darstellungsproblem: viele öffentliche Käufer, jede Firma bedient wenige. |
| „Wir sagen Ihnen, wann die Nachfolge kommt." | Vorlauf vor Vertragsende, 8.521 echte Paare: **Median 232 Tage, Quartile −13 bis 632.** Je CPV-Klasse schwanken die Mediane zwischen 168 und 722 Tagen, und **in Österreich ist der Median negativ** (−83 Tage): die Nachfolge erscheint typischerweise NACH dem Vertragsende. Ein berechnetes Handlungsdatum wäre erfundene Genauigkeit. |
| „Wir garantieren Vollständigkeit." | An der Messung gescheitert: **11,0 % Fehlstellen** gegen ein einziges nicht angebundenes Portal. Tragbar wäre nur eine Zusage auf ausgewiesene Quellen — und die ist nicht gebaut. |
| „Wir haben 125 Quellen." | Doppelzählung. Die 125 sind **drei verschiedene Dinge** (s. u.), und die Zahl der „live"-Quellen hängt an der Maschine, nicht am Code. Belegbar ist: *drei Konnektoren ≈ 36 Portale*, und **in Deutschland sind auf der Bekanntmachungs-Ebene 15 von 15 Quellen angeschlossen**. |
| „Unsere Dokumentenanalyse ist aktuell." | ⚠ **Sie steht seit dem 24.09.** 3.946 Dokumente warten, weil das LLM-Guthaben leer ist. Ausgerechnet unser einziger gemessener Vorsprung — und solange nicht aufgeladen ist, ist der Satz falsch. |
| „govisor.eu ist live." | Bewusst noch nicht online. |
| „Wir erkennen den Bedarf, bevor er ausgeschrieben wird." | ⛔ **Vier Quellen gemessen, vier gefallen.** Ratsdokumente (das BidFix-Modell): Median **29 Tage** Vorlauf, nicht Monate — die Papiere begleiten das Verfahren, sie gehen ihm nicht voraus. Vorinformation: **53 %** führen zu einer Ausschreibung, Grundrauschen **55 %** — sie sagt nichts voraus. Haushaltspläne: Jahre im Voraus, aber nur **~3 %** einer Bekanntmachung zuordenbar, weil der Haushalt intern schreibt und die Bekanntmachung öffentlich. EU-Fördervorhaben: **2 %** gegen 1 % Grundrauschen. |
| „Das Feld sagt uns, dass sich eine Beschaffung wiederholt." | ⛔ `RecurringProcurementIndicator` steht zu **97,8 % auf „false"** — die Käufer kreuzen es praktisch nie an. Ausgerechnet unsere Produktthese wörtlich im Datenfeld, und als Beleg unbrauchbar. Wer es nennt, wird widerlegt. |
| „Die neuen Merkmale gelten DACH-weit." | ⛔ **Die Schweiz bekommt davon nichts.** 1 von 8.549 CH-Leads trägt EU-Kofinanzierung; Direktvergabe-Grund und Ausführungsbedingungen stehen bei **0**. Das ist richtig so — die Schweiz fällt nicht unter die EU-Richtlinien — aber „gilt EU-weit" darf im DACH-Gespräch nicht als „gilt auch in der Schweiz" gelesen werden. |
| „Tausende zusätzliche Leads durch die neuen Merkmale." | ⚠ **Die absoluten Zahlen sind klein**: 921 EU-kofinanzierte und 1.601 mit Direktvergabe-Grund unter 43.027 Leads im Frontend. Als Merkmal, das sonst niemand hat, ist das stark; als Mengenaussage wäre es falsch. |
| „Impressum, Datenschutz und AGB stehen." | ⚠ Impressum ja. Die Datenschutzerklärung hat **offene Stellen** (Auftragsverarbeitung bei zwei Dienstleistern, eine Serverregion ungeprüft), die AGB sind ein **Entwurf mit acht offenen Geschäftsentscheidungen**, und **eine Rechtsprüfung hat nicht stattgefunden.** |
| „34,1 % der Ausschreibungen haben ausgewertete Unterlagen." | Nur **mit Nenner** zitieren: 34,1 % gilt für *laufende* Ausschreibungen. Gegen alle Akten gerechnet sind es 1,6 %, weil 69 % der Akten vor dem Abrufstart am 01.08.2026 liegen und kein Portal rückwirkend herausgibt. ⚠ An diesem Nenner ist heute schon einmal fast eine gute Idee gekippt. |

---

## Die Lage in einem Satz

**goVisor hat kein Alleinstellungsmerkmal auf Funktionsebene.** Acht Kandidaten geprüft, acht
gefallen. Das ist kein Mangel am Produkt, sondern die Lage des Marktes: Das LLM hat
Dokumentenanalyse innerhalb von achtzehn Monaten für alle gleichzeitig billig gemacht. Eine
Ein-Personen-Firma, fünf Monate alt, hat unsere Funktionsliste.

Wer in so einem Markt nach dem besseren Merkmal sucht, sucht am falschen Ort.

---

## Die drei Wettbewerber, gemessen

### aufträge.io / publicdeals.io — RFXSearch FlexCo, Wien
Eine Person (Ing. Martin Ha), eingetragen **18.03.2026**. Supabase + Northflank + Hetzner +
Weaviate + Gemini — derselbe Grundriss wie unserer.

**Funktionsliste deckungsgleich mit unserer:** Single-Bid, Repeat-Award, Saisonalität,
Incumbent (3–5 J.), Restlaufzeit, Wettbewerbsdichte, Match-Score, Rahmenvertrags-Frühwarnung.
**Was sie haben und wir nicht: ein MCP-Server mit 28 Werkzeugen.**

⚠ **Ihre Zahlen widersprechen sich im eigenen Material** — Portale „über 200" (/facts/) vs.
„300+" (Blog) vs. „hunderte" (Startseite); Auftraggeber 40.000 vs. 30.000. Ein einziges,
anonymes Testimonial. Das entwertet auch ihre „3,1 Mio analysierte Vergaben".

**Materialunterschied, nachgerechnet mit SEINEN eigenen Filtern im identischen Monat:**
8.423 gegen 1.448 Vergaben = **Faktor 5,8**. Seine Methodik ist dabei sauber — bei der
Single-Bid-Quote kommen wir auf dasselbe Ergebnis (26,2 % gegen seine 27,9 %, Konfidenz-
intervalle überlappen). Er misst richtig, er sieht nur weniger.

**Kein Selbstregistrieren, kein öffentlicher Preis** — jeder Kunde läuft durch einen
15-Minuten-Termin. Bei einer Ein-Personen-Firma ist das ihre Decke.

### BidFix — Fix Solutions GmbH
Vier Stufen: Pre-Tender, Such-, Qualifizierungs-, Bid-Agent. Eigenangaben: 2.000+ Unternehmen,
ISO 27001, **„100 % Abdeckung in DE & EU"**, **„+82 % Win-Rate"**.

**Ihr strategischer Zug: sie sitzen eine Stufe früher.** Ratsdokumente und Haushaltspläne,
bevor ein Verfahren läuft.

⚠ **Nachgemessen, und es trägt nicht so weit wie behauptet.** An Dresden (1.199 Vorlagen aus
2025) gegen 43.850 Dresdner Bekanntmachungen: Von 119 Vorlagen mit Vergabenummer führten 12 zu
einer späteren Bekanntmachung, **Median 29 Tage**. Der Vorlauf ist ein Monat, nicht Monate.
Beim Haushaltsplan (ihr eigenes Beispiel) lassen sich nur **~3 %** der Posten einer
Bekanntmachung zuordnen, weil der Haushalt intern schreibt und die Bekanntmachung öffentlich.
Und „10.000 Kommunen" geht nicht über OParl: das offizielle Verzeichnis führt **25 Endpunkte**.

**Von ihren 35 offengelegten Portalen haben wir 30 im Code**, eines geprüft und verworfen,
vier nicht erwähnt (metropoleruhr, niedersachsen, westfalen, vmp-rheinland).

### DTAD
Der Platzhirsch. **„Frank"**, chat-basierter KI-Assistent: „Er liest Dokumente, extrahiert
Eignungs- und Zuschlagskriterien."

---

## Die acht gefallenen USP-Kandidaten

Jeder wurde gegen vier Bedingungen geprüft: **heute wahr · belegbar · kaufentscheidend ·
vom Wettbewerb nicht besetzt.**

| # | Kandidat | woran er gescheitert ist |
|---|---|---|
| 1 | Die Akte / Vorgeschichte | aufträge.io hat Incumbent-Historie über 3–5 Jahre |
| 2 | Dokumente in der Akte | **1,6 %** der Akten tragen eine Dateiliste (⚠ s. u., falscher Nenner) |
| 3 | „sucht seit Jahren erfolglos" | **80 Fälle** mit ≥3 Fehljahren. Anekdote, keine Säule |
| 4 | prospektive Wettbewerbsdichte | **0.** Offene Ausschreibungen tragen weder Bieterzahl noch Verdrängbarkeit |
| 5 | „wir lesen die Unterlagen mit KI" | BidFix wörtlich, DTAD „Frank", aufträge.io implizit |
| 6 | Bieten-oder-nicht-Empfehlung | BidFix Qualifizierungs-Agent, ~4 Minuten je Vergabe |
| 7 | Abdeckung (43,2 % nicht in TED) | BidFix behauptet „100 %". Als *Behauptung* wertlos |
| 8 | Akte als wachsender Bestand | Zahlt 2028. Kein USP, eine Wette |

⚠ **Zu #2 — ein Messfehler, der fast eine gute Idee gekippt hätte.** Die 1,6 % waren gegen
**alle** Akten gerechnet, also gegen 22 Jahre Geschichte, für die es nie Unterlagen geben kann
(69 % der Akten liegen vor dem Abrufstart am 01.08.2026, und kein Portal gibt rückwirkend
heraus). Für einen Bieter zählt, worauf er **heute bieten kann**, und dort sind es **34,1 %**.
**Lehre: bei jeder Abdeckungszahl zuerst den Nenner prüfen.**

---

## Was gemessen für uns spricht

| | gemessen |
|---|---|
| Materialvorsprung | **Faktor 5,8** gegen aufträge.io, identischer Monat, seine Filter |
| Neuzugang je Werktag | **1.300–1.480** gegen „über 500" |
| Nicht über TED erreichbar | **rund 42 bis 43 %** der offenen deutschen Ausschreibungen — ⭐ **zweimal unabhängig gemessen** (s. u.) |
| Unterlagen ausgewertet | **34,1 %** der laufenden Ausschreibungen |
| Anforderungen aus Unterlagen | 31,8 % — darunter **Zertifikate, Pflicht-Ortstermin, Präsentation: in eForms zu 0 % vorhanden** |
| Käufer-Lieferanten-Beziehungen | **273.425** über 22 Jahre |
| Quellenregister | **125 Quellen mit ausdrücklichem Status** — in DE **15 von 15 live** ⚠ s. Warnung oben |
| Was jede Quelle NEU beiträgt | Dublettenquote je Quelle: **DTVP 66,6 %, Healy-Hudson 62,0 %, NetServer 29,8 %** |

### ⭐ Die Kernzahl ist zweimal unabhängig gemessen worden

Am selben Tag, von zwei Sitzungen, ohne voneinander zu wissen:

| | DÖE | DTVP | NetServer | Healy | Summe |
|---|---:|---:|---:|---:|---:|
| 11:40 Uhr | 23,1 % | 10,6 % | 6,0 % | 3,4 % | **43,2 %** |
| 16:30 Uhr | 22,5 % | 10,3 % | 5,8 % | 3,3 % | **41,9 %** |

**Identische Reihenfolge, jeder Einzelwert leicht niedriger** — was zu einem Stichtag ein paar
Stunden später passt, weil Fristen ablaufen. Für ein Gespräch ist das stärker als ein
Punktwert: die Zahl ist nicht aus einer günstigen Abfrage entstanden. **Im Gespräch deshalb als
Spanne nennen, und die 41,9 % als untere Kante.**

### Was jede Quelle wirklich beiträgt — und warum das niemand sonst sagen kann

Die Dublettenquote sagt, wie viel eine Quelle liefert, das wir nicht ohnehin schon haben:

| Quelle | geholte Sätze | davon schon bekannt | wirklich neu |
|---|---:|---:|---:|
| DTVP | 15.577 | 66,6 % | 5.208 |
| NetServer | 6.284 | 29,8 % | 4.409 |
| Healy-Hudson | 2.971 | 62,0 % | 1.129 |

⚠ **Und hier steckt die Falle, die fast jede Diskussion über Quellen kaputtmacht.** Dieselben
drei Quellen sind

- **im Bestand** (20 Jahre, 2,3 Mio. Bekanntmachungen): 10.746 neue Sätze = **0,47 %**
- **bei den heute offenen Leads**: 2.868 von 14.775 = **19,4 %**

**Faktor 40, und beide Zahlen stimmen.** Der Bestand ist 20 Jahre TED-Historie; die offenen
Leads sind der heutige Markt — und unterschwellige kommunale Vergaben sind kurzlebig: sie
erscheinen, laufen vier Wochen, verschwinden. Wer den Wert einer Quelle am Bestand misst,
misst die falsche Zahl, und der Fehler lässt **jede** unterschwellige Quelle wertlos aussehen.

⚠ **DÖE, NetServer und Healy-Hudson stehen nicht in aufträge.ios eigener Quellenliste** —
zusammen 4.674 offene Ausschreibungen, 32,5 %. „Nicht in ihrer Liste" ist allerdings kein
Beweis für „haben sie nicht"; Bund.de und DTAD aggregieren teilweise mit.

---

## Was am 2026-10-05 dazugekommen ist

Drei Sitzungen parallel. **Gemessen, nicht behauptet** — jede Zeile hat eine Zahl oder sagt
ausdrücklich, dass sie noch keine hat.

### Fertig und belegt

| | Zahl |
|---|---|
| **cosinex-Landesportale live** (NRW/RLP) | lag 7 Wochen auf „vorbereitet". Gegenprobe vor dem Einschalten: 966 neue Bekanntmachungen aus zwei Seiten je Division, nur NRW. Ertrag gemessen: **23,5 % neu** |
| **CH-KMU-Kennzahl repariert** | stand bei **einem** Wert (100 %) an 61 Vergabestellen — rechnerisch korrekt, als Marktaussage wertlos. Jetzt **53 verschiedene Werte an 159 Stellen**. (DE 74/237 · AT 31/43 · LU 18/30) |
| **CHF-Kurs 2026** | fiel durch einen Netzfehler lautlos aus; 11.739 Schweizer Vergaben waren um **537,6 Mio € = 1,46 %** zu niedrig bewertet. Behoben, mit Wiederholung und Rückfallebene |
| **Dateigrenze im Frontend** | 151.769 → **63.133** Dateien, Bau 18 s statt ~5 min. Vorher waren es 4.231 Dateien bis zum Abbruch, jetzt 92.867 |
| **Los-Zuordnung in Anforderungen** | ein Parserfehler liess **5,6 Mio.** Zeilen ohne Los-Bezug. Behoben: Ausführungsbedingungen **97 %**, technische **80 %**, Ausschlussgründe **23 %** mit Los |
| **`erfolglos`-Signal zurückgeholt** | war mit der eForms-Umstellung von 13,0 % (2019) auf **0,9 %** gefallen und damit drei Jahre blind — nicht kaputt, sondern taub. Jetzt **4,2 bis 5,3 %** in 2024–2026. ⚠ Das ist NICHT „wieder normal": 4–5 % gegen 10–13 % der Altjahre bleibt ein Unterschied, und beides stimmt |
| **Neue Merkmale auf offenen Ausschreibungen** | EU-Kofinanzierung **2.631** · Direktvergabe-Grund **4.872** · Ausführungsbedingungen **8.077** (DE-Leads). Im Frontend angekommen: 921 · 1.601 · 2.080 |
| **Grund der Nichtvergabe** | **11.512 von 79.075** erfolglosen Verfahren tragen einen (15 %) — im amtlichen Wortlaut |
| **Vorlauf der Nachfolge, erstmals richtig gemessen** | DE 8.521 Paare, Median +232 Tage · AT 8.050 Paare, Median **−83** Tage · CH 49 und LU 2 Paare: zu dünn |
| **Betriebsfestigkeit** | der Nachtlauf fährt seit heute einen eigenen, festen Stand. Vorher lief, was zufällig ausgecheckt war — ein Fix vom 01.09. war dadurch **fünf Wochen** nie gelaufen |
| **Vier neue Prüfungen** | u. a. eine, die meldet, wenn eine Warteschlange Arbeit trägt und sich seit Tagen nichts bewegt |

### Angefangen, noch nicht belastbar — ⛔ gehört in kein Angebot

- **Beobachtungsliste im Strategiebereich** (statt eines Terminplans, weil ein Termin nicht
  berechenbar ist): Export fertig, Ansicht fehlt. Abdeckung **34 von 185 Posten = 18 %** mit
  belegtem Fenster, und **sie trägt nur in Deutschland.**
- **Dokumentenanalyse steht seit dem 24.09.** — 3.946 Dokumente warten auf LLM-Guthaben.

## Wo wir schwächer sind — vor dem Gespräch lesen

1. ⚠ **Vergabestellen.** Sie nennen 40.000, wir haben **7.783 mit Profil**, bei 123.428 rohen
   Käufernamen allein für DE. **39 % der Beziehungszeilen tragen einen unaufgelösten Käufer.**
   Das ist die bekannte schwache Entity-Resolution auf Käuferseite.
2. **Kein MCP-Server.** Sie haben 28 Werkzeuge; wer sein LLM direkt auf Vergabedaten setzen
   will, findet das bei ihnen und nicht bei uns.
3. **Dokumente erst ab 01.08.2026.** Rückwirkend nicht beschaffbar.
4. **Vier Portale**, die BidFix nennt und wir nicht anfassen.
5. **Kein öffentlicher Preis, kein Selbstregistrieren** — gilt für sie und noch für uns.

---

## Wie der Markt mit Lücken umgeht — der verwertbare Befund

**Alle vier großen deutschen Anbieter schließen Vollständigkeit im Vertrag aus**, während sie
im Marketing Abdeckung behaupten:

> **DTAD:** „weder für die Vollständigkeit oder Richtigkeit der Auftragsinformationen verantwortlich"
> **Deutsches Ausschreibungsblatt**, **Vergabe24**, **evergabe.de**: „keine Gewähr für die
> Richtigkeit und Vollständigkeit"

aufträge.io macht es eleganter: **nie Vollständigkeit behaupten**, nur „über 200", „über 3,1 Mio".
Wer nichts verspricht, muss nichts halten.

**Damit beantwortet niemand die Frage, die der Kunde wirklich hat: „Was habe ich verpasst?"**
Die Antwort der ganzen Branche darauf steht in §12 der AGB.

Wir könnten sie im Produkt beantworten — 125 Quellen mit Status, drei getrennte Gründe für
fehlende Unterlagen, `amtlich` vs. `erschlossen` bei der Vollständigkeit. ⚠ **Und es ist für
jeden Etablierten teuer, das zu kopieren:** BidFix kann keine Lücken listen, ohne die eigene
Startseite zu widerlegen.

⚠ Gegenargument, das ehrlich dazugehört: Lücken zu zeigen kostet Gespräche („ihr habt es also
*nicht*?"). Sven hat es als **„im Ansatz gut, schwer zu verkaufen"** eingeordnet. Es taugt als
Haltung und als Antwort auf einen Einwand, nicht als Überschrift.

---

## Die drei Einwände, die im Gespräch kommen werden

| Einwand | belegte Antwort |
|---|---|
| „DTAD hat auch eine KI, die Unterlagen liest." | Stimmt. Frank analysiert auf Zuruf, eine Vergabe nach der anderen. Wir haben **16.250 vorab** ausgewertet — deshalb kann man bei uns **danach filtern** (keine Bürgschaft, kein Pflicht-Ortstermin, passende Zertifikate). Ein Assistent auf Zuruf kann das strukturell nicht. |
| „BidFix sagt 100 % Abdeckung." | Jeder behauptet das, und alle schließen es in den AGB aus. Prüfbar ist es nur an Ihren eigenen Daten: **nennen Sie mir Ihre letzten zehn Ausschreibungen.** |
| „Wir haben schon ein Tool." | Dann ist die Frage nicht Funktionen, sondern was es **nicht** zeigt. 43,2 % der offenen deutschen Vergaben stehen nicht in TED. |

---

## ⭐ Was seit heute neu verkaufbar ist: warum ein Verfahren gescheitert ist

Beide anderen Sitzungen halten unabhängig voneinander dasselbe für den stärksten neuen Punkt,
und er ist seit gestern messbar: **wir können sagen, WARUM ein Verfahren gescheitert ist — im
amtlichen Wortlaut, nicht geraten.**

Für einen Bieter sind die Gründe **gegensätzlich**:

| amtlicher Code | heisst | für den Bieter |
|---|---|---|
| `no-rece` | es sind keine Angebote eingegangen | ⭐ **eine Chance** — der Käufer sucht und findet niemanden |
| `chan-need` | der Bedarf hat sich geändert | nichts zu holen |

**Bis gestern lief beides ununterschieden durch.** 11.512 von 79.075 erfolglosen Verfahren
tragen einen Grund (15 %).

Dasselbe bei der Direktvergabe: *„nur ein Anbieter aus technischen Gründen"* ist angreifbar,
wenn man es selbst kann — und es steht bei **4.872** deutschen Leads im Wortlaut da.

Und ein Merkmal, das einem Bieter unmittelbar Arbeit erspart: `reserved-execution=yes` — der
Auftrag ist Werkstätten vorbehalten, er kann gar nicht mitbieten. **8 Leads im Frontend**, und
jeder davon hätte jemanden ein vergebliches Angebot gekostet.

⚠ **Mengenmässig ist das klein** (s. Verbotstabelle oben). Es ist ein Merkmal, kein Volumen.

---

## Was tatsächlich trägt: Zielkundenqualifizierung

Kein Produktmerkmal, sondern ein Vertriebsvorteil — und der einzige Punkt, der acht
Prüfungen überlebt hat.

**Wir können über jedes deutsche Unternehmen eine belastbare Vertriebsaussage treffen,
bevor wir es ansprechen.** Aus öffentlichen Daten, ohne dass es Kunde ist.

Gemessen an einer geschichteten Stichprobe (30 Firmen) und am Gesamtbestand:

| Schicht | Median Käufer | Median Top1-Anteil |
|---|---|---|
| klein (5–20 Zuschläge) | 5 | 38,8 % |
| mittel (21–100) | 22 | 14,9 % |
| groß (>100) | 84,5 | 5,4 % |

⚠ **Klumpenrisiko ist NICHT die Regel** — Top1 ≥ 50 % bei 6 von 30 in der Stichprobe, 23,0 %
im Gesamtbestand (3.135 von 13.638 aktiven Firmen). Wer „Sie hängen an einem Kunden" als Pitch
baut, liegt bei vier von fünf Gesprächen daneben.

**Aber wir wissen vorher, welches Fünftel es ist.** Daraus entstand
[`docs/zielliste-dome.csv`](zielliste-dome.csv) — 78 Firmen, bei denen die Zahlen die
Geschichte selbst erzählen. Siehe [`zielliste-dome.md`](zielliste-dome.md).

---

## Offene Fragen

- Will ein Mittelständler diese Aussage hören? **Annahme, nicht gemessen** — in drei
  Gesprächen prüfbar.
- Lohnt ein MCP-Server? Billig zu bauen, und es ist ihr einziges echtes Merkmal.
- ✅ **Beantwortet:** die vier nicht angefassten Portale. `vergabe-westfalen.de` und
  `vmp-rheinland.de` laufen auf derselben cosinex-Familie, nur unter einem anderen Pfad;
  `metropoleruhr` teilt die IP mit Westfalen; `niedersachsen` ist eine andere Plattform.
  cosinex ist seit heute live. Gemessener Ertrag: **11,0 % echte Fehlstellen** von 91
  laufenden Vergaben — 89 % hatten wir schon.
- **Neu offen:** Lohnt die Beobachtungsliste, wenn sie nur in Deutschland trägt (18 %
  Abdeckung, in AT ist der Vorlauf negativ)? Entscheidung liegt bei Sven.
- **Neu offen und dringend:** LLM-Guthaben. Solange es leer ist, steht die
  Dokumentenanalyse — und das ist der einzige gemessene Vorsprung, den wir haben.

---

## Wer was beigetragen hat

Drei Sitzungen, am 2026-10-05 parallel. Die Zahlen stammen jeweils von der Sitzung, die sie
gemessen hat; ⭐ **die Abdeckungszahl (42–43 % nicht über TED) ist die einzige, die zwei
Sitzungen unabhängig voneinander gemessen haben** — und sie hielt.

- **Wettbewerbsanalyse, Zielliste, cosinex, Bündelung, Vorlaufmessung, Beobachtungsliste** —
  die Sitzung, die dieses Papier angelegt hat.
- **`erfolglos`/BT-144, EU-Kofinanzierung, Direktvergabe-Wortlaut, Ausführungsbedingungen und
  Los-IDs, Grounding-Seite, Rechtstexte** — die Sitzung am Frontend und Parser.
- **Quellenanalyse, Dublettenquoten, KMU-Reparatur, CHF-Kurs, Betriebsfestigkeit des
  Nachtlaufs, Wächter** — die Sitzung an Pipeline und Skripten.

⚠ **Was keine Sitzung behauptet:** dass irgendetwas davon beim Kunden erprobt wäre. Alle
Zahlen sind aus dem Bestand gemessen, keine aus einem Gespräch.

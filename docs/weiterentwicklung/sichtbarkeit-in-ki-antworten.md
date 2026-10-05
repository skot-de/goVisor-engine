# Sichtbarkeit in KI-Antworten: Marktanalyse und Index-Bauplan

**Stand:** 2026-10-01 · **Anlass:** Sven: „wie können wir gewährleisten, dass wenn jemand bei
ChatGPT und co nach öffentlichen Ausschreibungen sucht, uns findet?"
**Art:** Messung + Strategie. Alle Fremdzahlen sind als **Behauptung** gekennzeichnet, alle
eigenen Zahlen sind gemessen und mit Messweg benannt.

> ⚠ **Die eigenen Zahlen in §3 werden ERZEUGT**, von `scripts/zahlen_nachziehen.py` im
> Nachtlauf. Prosa und Strategie bleiben Handarbeit und werden nie überschrieben — ersetzt
> wird nur, was zwischen den `<!-- ZAHLEN:… -->`-Markierungen steht. Die **Fremdzahlen
> bleiben bewusst Handarbeit** mit Prüfdatum: sie stammen aus einer Websuche, nicht aus
> unseren Daten, und sollen sichtbar veralten statt nächtlich frisch zu erscheinen.

---

## 1. Ausgangslage, gemessen

| | |
|---|---|
| `govisor.eu` | **HTTP 404** — „The deployment could not be found on Vercel" |
| `govisor.de` | 301 → `govisor.eu` → 404 |
| `www.govisor.eu` | nicht erreichbar |
| `robots.txt`, `sitemap.xml`, `llms.txt` | 404 |
| goVisor in Suchergebnissen | **null Treffer** |

Geprüft am 2026-10-01 mit den echten Crawler-Kennungen `OAI-SearchBot`, `PerplexityBot`,
`ClaudeBot` und `Googlebot`. Alle vier bekommen dieselben 107 Bytes.

⛔ **Keine KI kann eine 404 nennen.** Jeder Punkt unten setzt ein Deployment voraus.

Und eine zweite Schicht danach: `web/middleware.ts` setzt an drei Stellen
`x-robots-tag: noindex, nofollow`, solange die Coming-Soon-Sperre läuft. Ein Crawler dürfte
die Seite dann lesen und **darf sie nicht indizieren**.

---

## 2. Das Wettbewerbsfeld

Die Kategorie ist **nicht dünn**. Elf Anbieter, die alle dieselbe Frage besetzen:

| Anbieter | Behauptung (deren Angabe) | Preis (deren Angabe) |
|---|---|---|
| **DTAD** | 12.000 Quellen · 99,99 % Abdeckung DE · „Platzhirsch" | nicht öffentlich, Schätzung ~200 €/Mon |
| **aufträge.io** (RFXSearch, Wien) | 3,1 Mio. analysierte Vergaben · 260.000 Firmen · 500+ Ausschreibungen/Tag · Incumbent-Tracking · Vertragsende-Prognose · ARGE-Partner · „Win-Rate über 35 %" | nicht gefunden |
| **Patterno** | 1.000+ Vergabeportale europaweit | 99 / 499 / 2.499 €/Mon, 10 % Jahresrabatt |
| **Vergabepilot** | 300+ Portale · Relevanzscore | **kostenlos** / 60 / 125 €/Mon |
| **VergabeRadar** | Passungs-Score · geschätzter Auftragswert | nicht gefunden |
| **Tendit** | semantisches Firmenprofil, IT-Fokus | nicht gefunden |
| **BidFix** | voller Lebenszyklus · dauerhaft kostenlose Stufe | kostenlose Stufe |
| DTVP, Vergabe24, Ausschreibungen.de, Deutsches Ausschreibungsblatt | Portale, keine Analysewerkzeuge | teils kostenlos |

### ⚠ Drei unbequeme Folgerungen

**Der Relevanzscore ist kein Unterscheidungsmerkmal.** Vergabepilot, VergabeRadar, Tendit und
Patterno beanspruchen ihn alle. Wer damit wirbt, sagt nichts.

**Die Nachfolge ist besetzt.** Ich hatte Sven zuerst gesagt, niemand bewerbe Vertragsende und
Amtsinhaber. **Das war falsch** — aufträge.io bewirbt genau das, inklusive Frühwarnsystem für
auslaufende Rahmenverträge und automatisch berechneter ARGE-Partner. Der Fehler entstand, weil
aufträge.io in keinem der gefundenen Vergleichsartikel vorkommt und deshalb nicht in meiner
ersten Messung auftauchte.

**Bei der Quellenzahl verliert goVisor.** Unsere Registry (die Zahl steht in §3) liegt gegen DTADs
behauptete 12.000 und Patternos 1.000 zwei Größenordnungen zurück. Diese Achse ist nicht gewinnbar und sollte nicht
beworben werden — siehe auch den ehrlichen Konter in `docs/` zur „200 Quellen"-Frage.

---

## 3. Wo goVisor wirklich steht

Gemessen über Silber und Gold, nicht behauptet. **Dieser Block wird erzeugt** — von
`scripts/zahlen_nachziehen.py`, jede Nacht im Tageslauf. Er ist die einzige Stelle im Dokument,
an der diese Zahlen stehen; wer sie anderswo wiederholt, erzeugt eine zweite Wahrheit, und der
Erzeuger meldet das.

<!-- ZAHLEN:bestand -->
| | DE | AT | CH | LU | gesamt |
|---|---:|---:|---:|---:|---:|
| Bekanntmachungen | 2.302.157 | 424.349 | 126.339 | 38.568 | **2.891.413** |
| Zuschläge | 825.285 | 231.593 | 53.848 | 13.383 | **1.124.109** |
| Vorgangsakten | 1.433.279 | 298.267 | 75.318 | 25.226 | **1.832.090** |
| Bestand ab | 2004-01-02 | ⚠ Datenfehler | 2016-08-09 | 2004-01-02 | |

⚠ AT trägt als frühestes `publication_date` einen Wert vor 1993. Das ist ein Parserfehler, kein Bestand — er ist zu klären, bevor diese Tabelle öffentlich wird.

Quellen-Registry (`govisor/sources.py`): **125** Einträge.

*Gemessen am 2026-10-05 von `scripts/zahlen_nachziehen.py`. Nicht von Hand ändern — der nächste Lauf überschreibt es.*
<!-- /ZAHLEN:bestand -->


**Damit liegt goVisor bei der Menge auf Augenhöhe mit aufträge.io** (2,89 Mio. gemessen gegen
3,1 Mio. behauptet), nicht darunter. Die Behauptung „wir haben weniger Daten" wäre falsch; die
Behauptung „wir haben mehr Quellen" wäre es auch.

### Was wirklich keiner bewirbt

Die **Vorgangsakte als Objekt**: Bekanntmachung, Vergabeunterlagen und Zuschlag unter EINER
Nummer, 1,83 Mio. davon, zurück bis 2004. Dazu die **Herkunftskennzeichnung je Wert** und die
**Zitatverifikation**, die jede Aussage an ihre Belegstelle im Dokument bindet (Ticket 23).

⚠ **Hier stand bis zum 2026-10-04: „Kein Anbieter im Feld verspricht, die Vergabeunterlagen
selbst auszuwerten — alle hören bei ‚diese Ausschreibung passt zu dir' auf."** Der Satz war
drei Tage alt und falsch. Gemessen an den Herstellerseiten am 2026-10-04 werben **DTAD**
(Assistent „Frank"), **Patterno** (100 Seiten in 30 s) und **Vergabepilot** (Chat über die
Unterlagen) alle drei mit genau dieser Auswertung. Die **Dokumentenanalyse** gehört deshalb
nicht mehr unter diese Überschrift; nur ihre Tiefe tut es.

⚠ **Und die Fehlerursache gehört dazu, weil sie wiederkommt:** §2 entstand aus einer Websuche,
und Websuchen finden Vergleichsartikel statt Herstellerseiten. Patterno stand dort mit 1.000
Portalen und wirbt auf der eigenen Seite mit **4.500** — drei Tage später. Fremdzahlen altern
in Tagen, eigene Zahlen in Nächten. Vor jeder Verwendung dieses Kapitels im Vertrieb gehört
ein Blick auf die Seite des genannten Anbieters.

---

## 4. Wie Anbieter überhaupt in KI-Antworten kommen

Drei Wege, und sie werden gern verwechselt:

**Trainingsdaten.** Nicht steuerbar, Jahre Verzögerung, für ein neues Produkt praktisch null.
Darauf lässt sich nicht planen.

**Abruf zur Laufzeit.** Der Weg, der zählt. ChatGPT Search, Perplexity, Gemini und Claude mit
Websuche stellen eine Suchanfrage und lesen die Treffer. Es entscheidet, was auffindbar und
maschinenlesbar klar ist.

**Quellen, die Modelle überproportional zitieren.** Wikipedia, Wikidata, Fachverzeichnisse.

### ⚠ Der eigentliche Fund: die Vergleiche schreiben die Anbieter selbst

`tenderautomation.de`, `produktneutral.de`, `bidfix.ai`, `patterno.de`, `usetendit.com`,
`ki-syndikat.de`, `tenderzen.de` und `auftraege.io` betreiben alle Blogs mit Titeln wie
„Ausschreibungssoftware Vergleich 2026: 7 Tools im Test" und „DTAD-Alternativen 2026".
**Das ist die Fläche, die ein Modell liest, wenn es nach einem Tool gefragt wird** — nicht die
Herstellerseiten, die Vergleiche.

aufträge.io geht dabei am weitesten: ihre Vergleichskriterien lauten „Ausschreibungsabdeckung,
Incumbent-Analyse, Zukunftssignale, Qualifizierungshilfe und Partnerstrategie" — also genau
ihre eigenen Stärken, und sie sind dort Testsieger. goVisor kommt nicht vor.

Patterno fährt zusätzlich ein **programmatisches Muster**: eine Seite je Wettbewerber
(`/resources/blog/dtad-alternativen`) und eine je Portal (`/de/vergabe-portale/vergabe24`).

---

## 5. Die Suchlandkarte: wer besitzt welche Frage

| Fragetyp | Beispiel | Wer antwortet heute | Für goVisor |
|---|---|---|---|
| **Fundort** | „wo finde ich öffentliche Ausschreibungen" | TED, bund.de, Landesportale | ⛔ nicht gewinnbar, und das ist richtig so |
| **Produktkategorie** | „Tool um Ausschreibungen zu finden" | 7+ Anbieter-Vergleichsblogs | ⚠ besetzt, Einstieg nur über eine eigene Achse |
| **Abdeckung** | „die meisten Quellen" | DTAD | ⛔ nicht gewinnbar |
| **Rechtsfrage** | „Laufzeit von Rahmenvereinbarungen" | Kanzleien, Vergaberechtsblogs, Bundestag-WD | ⛔ nicht unser Feld |
| **Datenfrage** | „wann läuft der Vertrag von Behörde X aus" · „wer ist Amtsinhaber bei Y" | **niemand** | ✅ **hier liegt der Platz** |

### Der Befund, auf dem der Index aufbauen sollte

Die Suche nach „wann läuft ein Rahmenvertrag aus / Nachfolgeausschreibung" liefert heute
ausschließlich **Rechtstheorie**: Rahmenverträge laufen zwei bis vier Jahre, schauen Sie in die
Vergabeunterlagen, Kündigungsfrist meist drei Monate. Kein Werkzeug antwortet mit Daten —
auch aufträge.io nicht, obwohl es die Funktion bewirbt.

goVisor hat über eine Million Zuschläge mit Nachfolge-Adjudikation (genaue Zahl in §3). Es
kann diese Frage als einziges
**mit einer Zahl** beantworten statt mit einer Rechtsregel.

---

## 6. Index-Bauplan

Reihenfolge nach Wirkung je Aufwand. Schritt 0 ist nicht verhandelbar.

**0. Deployen und `noindex` für die öffentlichen Seiten aufheben.** Alles darunter ist ohne das
wirkungslos. Heute hat die Sitemap drei Einträge (`/`, `/start`, `/login`) — nichts davon ist
zitierfähig, weil keine davon eine Frage beantwortet.

**1. Datenseiten, die eine Frage mit einer Zahl beantworten.** Das ist der Teil, den kein
Wettbewerber kopieren kann, weil ihm die Daten fehlen. Kandidaten aus dem vorhandenen Bestand:

* Je Vergabestelle: welche Verträge laufen aus, wer ist Amtsinhaber, seit wann
* Je Branche/CPV: Marktgröße, Bieterdichte, Verteidigungsquote
* Der EU-Marktbericht: 844.602 Bekanntmachungen über 31 Länder, bereits gemessen
* Bietende Einheiten je Konzern (§9.2 Preismodell), bereits gemessen

**2. In die Vergleiche kommen.** Zwei Wege, beide legitim:
* Eigener Vergleich mit **offengelegter Absenderschaft** („wir sind Anbieter"), auf den
  Kriterien, auf denen goVisor nicht verliert: Aktentiefe, Archiv ab 2004, Dokumentenanalyse.
* Eintrag in die Verzeichnisse, die Modelle zitieren: OMR Reviews, Capterra DE, G2.
  ⚠ Diese verlangen in der Regel Kundenbewertungen — mit heute **null zahlenden Kunden**
  (gemessen: 13 Organisationen, alle `tier='free'`) ist das eine Henne-Ei-Frage.

**3. `llms.txt` anlegen** (existiert nicht) und das vorhandene JSON-LD korrigieren: es
deklariert `offers: { price: "0" }`, obwohl v1.9 die Preise festlegt. Falsche Fakten in
strukturierten Daten sind schlimmer als keine, weil ein Modell sie übernimmt.

**4. Wikidata-Eintrag.** Billigster Hebel je Aufwand.

**5. Preisseite mit Zahlen.** v1.9 ist entschieden (99 / 349 €, Erweiterung 29 €). Patterno und
Vergabepilot veröffentlichen ihre Preise, DTAD nicht — und genau das wird in Vergleichen als
Nachteil notiert. Einordnung: goVisors 99 € = Patternos Starter, 349 € liegt unter Patternos
Scale (499 €); Vergabepilot unterbietet mit 60/125 €. Der Jahresrabatt (14,2 %) ist höher als
Patternos 10 %.

---

## 7. Was ich nicht empfehle

* **Platzierung kaufen.** Wer „garantierte Nennung in ChatGPT" verkauft, verkauft nichts.
* **Anweisungen an das Modell im Seitentext.** Wird gefiltert, und wenn es auffällt, kostet es
  mehr als es bringt.
* **Neutral aussehende Vergleichsseiten ohne Absenderangabe** oder erfundene Bewertungen.
* **Mit der Quellenzahl werben.** Das ist ein Vergleich, den man nicht sucht.
* **Mit „Relevanzscore" werben.** Vier Wettbewerber behaupten dasselbe.

---

## 8. Abgleich mit Ticket 17 (Ausschreibungs-Landingpages)

Gelesen am 2026-10-01: `INPUT/govisor-ticket-17-ausschreibungs-landingpages_v1.3`. Das Ticket
ist in der Ausführung strenger als dieser Bauplan und kommt **unabhängig zum selben Kernschluss**.

**Was sich deckt, und das ist die starke Nachricht.** §11 macht die Exklusivschicht zur
**Bedingung für Indexierung**: verifizierter Vorgängervertrag, oder Auftraggeber-Historie mit
n ≥ 6 in der CPV-Gruppe, oder Zyklushistorie. Ausdrücklich zählen *Segmentzahlen, Anbieterzahlen
je Region und allgemeine Texte nicht*. Genau das ist der Befund aus §5 dieses Dokuments: die
Datenfrage ist die einzige Achse, auf der goVisor nicht verliert. Und §5 des Tickets nennt als
dritte Suchintention „Bisheriger Auftragnehmer → *Wird mein Vertrag neu vergeben?*" — die Frage,
die heute messbar **niemand mit Daten beantwortet**.

Zwei Wege, ein Ergebnis. Das ist Bestätigung, nicht Doppelarbeit.

### ⚠ Eine echte Lücke: das Ticket gewinnt den langen Schwanz, nicht die Kategoriefrage

Alle vier Suchintentionen in §5 des Tickets sind **vorgangsbezogen** — Vergabenummer, Titel,
Leistung plus Stadt, eigener Vertragstitel. Keine davon ist „Tool um Ausschreibungen zu finden",
und genau dort sitzt die Kaufabsicht und teilen sich heute acht Anbieter-Vergleichsblogs den
Verkehr (§4).

Eine Seite je Ausschreibung kann diese Frage nicht einfangen. Dafür braucht es den **zweiten
Seitentyp**, den die Wettbewerber längst bauen: eine Seite je Portal und eine je Wettbewerber.
Ticket 17 und dieser Bauplan sind damit nicht Alternativen, sondern zwei Hälften.

### ⚠ Eine Prämisse, die geprüft werden muss statt angenommen

§1 des Tickets: die Seite „weiß **mehr als jede andere Quelle**". Gegen TED und die Portale
stimmt das. Gegen **aufträge.io** ist es eine offene Frage: sie bewerben Incumbent-Tracking UND
Vertragsende-Prognose, also genau das, was §11 als Exklusivschicht definiert. Ist ihre Prognose
echt, macht die Schwelle goVisor nicht einzigartig, sondern **Zweiten**.

Das ist prüfbar und sollte geprüft werden, bevor diese Prämisse einen ganzen Akquisekanal trägt
(§9, erster Punkt).

### ⚠ Gemessen: was die §11-Schwelle wirklich durchlässt

Die Prämisse oben ist geprüft, und das Ergebnis dreht die Frage. aufträge.io **benennt** die
Vertragsende-Prognose auf der Startseite („Wann Verträge enden und neu vergeben werden"), aber:
kein Verfahren, keine Datengrundlage, kein einziges Beispiel mit einem vorhergesagten Datum,
auch nicht auf tieferen Seiten der Domain. Belegt werden nur Erfahrungswerte (25 Jahre
Vergabepraxis, 100 Mio. € gewonnene Aufträge, 3,1 Mio. analysierte Vergaben).

**Die Exklusivität liegt damit nicht im Besitz der Funktion, sondern in ihrer Belegbarkeit.**
Wir können Zahlen nennen, sie nennen keine. Nur sind unsere Zahlen kleiner als das Ticket
voraussetzt:

| §11-Tor | trifft zu auf | Bewertung |
|---|---|---|
| verifizierter Vorgängervertrag | **4.275 von 90.979 Leads (4,7 %)** | das starke Tor, aber ein schmaler Schwanz |
| davon mit belegter Amtszeit | 421 | |
| davon mit Zyklus (Kettentiefe ≥ 2) | **47** | als Alleinstellung zu wenig für einen Kanal |
| Auftraggeber-Historie n ≥ 6 (CPV-gruppengenau) | **71.053 von 90.979 Leads (78,1 %)** | kein Tor, sondern eine Tür |

Belegqualität der Nachfolge, gemessen: Ø `confidence` **0,76** bei `content_unique` (79.591
Kanten) und **0,70** bei `llm_adjudicated` (35.675). Das ist mehr, als irgendein Wettbewerber
über seine Prognose veröffentlicht — und es ist eine Zahl, die man hinschreiben kann.

**Folgerungen für Ticket 17:**

1. Das starke Tor trägt rund **4.300 indexierbare Seiten**. Das ist ein brauchbarer langer
   Schwanz, aber kein „eine Seite je Ausschreibung".
2. ⚠ **Das breite Tor ist keine Schwelle.** Nachgerechnet: „Auftraggeber hat n ≥ 6 Zuschläge in
   der CPV-Gruppe dieser Ausschreibung" lässt **78,1 % aller Leads** durch. Eine Bedingung, die
   vier von fünf Seiten erfüllen, gatet nicht — sie öffnet. Dazu ist sie inhaltlich genau das,
   was §11 selbst ausschliesst („Segmentzahlen … zählen nicht"): dass eine Vergabestelle in
   einer Division schon sechsmal vergeben hat, ist eine Segmentzahl, keine seitenspezifische
   Erkenntnis.

   ⚠ **Und sie ist herleitbar, anders als zunächst angenommen.** Die Nachbarsitzung hat das Tor
   entfernt mit der Begründung, die Daten trügen keine CPV-gruppengenaue Zahl — ihr Code prüfte
   `buyerProfile.total`. Die Zahl ist aber aus `party_entity` (role=buyer) und
   `notices.cpv_main` berechenbar: 118.419 Paare Käufer × CPV-Division, davon 20.850 mit n ≥ 6.
   Die Entscheidung bleibt richtig, der Grund war falsch — und das ist wichtig, weil sonst
   jemand das Tor wieder einbaut, sobald er merkt, dass die Zahl doch zu haben ist.
3. Die ehrliche Begründung der Schwelle ist nicht „das hat sonst keiner", sondern **„unsere
   steht mit einer gemessenen Konfidenz da, die anderen nennen keine"**. Diese Begründung hält
   auch, wenn aufträge.io die Funktion wirklich liefert.

### Zwei Kleinigkeiten

**§7.2 trägt veraltete Stufennamen.** Dort steht „Pro/Premium: direkt in die Analyse". Seit dem
2026-10-01 heißen die bezahlten Stufen **Analyse** und **Strategie** (Commit 5cb7f36). Inhaltlich
stimmt es weiter, weil beide unbegrenzt sind (`darfAnalyse`), aber die Worte stammen von vor der
Trennung. Die Free-Regel (3 Analysen je 30 Tage) deckt sich mit `web/lib/kontingent.ts`.

**§11 setzt Crawler und tägliche Neubauten voraus.** Solange `govisor.eu` 404 liefert und die
Coming-Soon-Sperre `noindex` setzt (§1), kann weder Search Console noch IndexNow beginnen. Das
Ticket behandelt Deploy und Vorhang-Ausnahme zu Recht als eigene Entscheidung — es ist aber die
Abhängigkeit, an der alles andere hängt.

---

## 9. Offene Prüfungen

Zahlen, die eine Gegenprobe verdienen, bevor sie in einen eigenen Vergleich gehen:

* DTADs „12.000 Quellen" und „99,99 % Abdeckung" — gegen TEDs eigene Zahlen prüfbar
* aufträge.ios „3,1 Mio. analysierte Vergaben" — ist das derselbe Gegenstand wie unsere
  2,89 Mio. Bekanntmachungen, oder zählt es Lose?
* aufträge.ios „Win-Rate über 35 %" — gegen welche Grundgesamtheit?
* Patternos „1.000+ Vergabeportale europaweit" — gegen unsere Registry (§3)

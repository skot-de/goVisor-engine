# goVisor — Preismodell & Feature-Zuordnung

**Version:** 1.9
**Stand:** 2026-09-30
**Zweck:** Zuordnung aller Features zu den Stufen · Grundlage für Preisseite, Gating und Abrechnung
**Grundlage:** Feature-Matrix v2.0, Marktpreis-Recherche 07/2026, Preisstufen-Analyse Gold Layer 09/2026, Tickets #1–#28
**Geltungsbereich:** **V1 = Anbieterseite.** Die Vergabestellenseite (§12) ist dokumentiert, aber **nicht Teil von V1** — sie kommt in V2 und wird nicht gebaut.

**Changelog:**
1.0 Erstfassung nach Features · 1.1 Zuordnung auf Bereiche und Tabs umgestellt; Firmenprofil in zwei Tabs geteilt · 1.2 Netzwerk-Grenze definiert (Free passiv, Pro aktiv) · 1.3 Prämien-Auslöser um die Unterlagen-Analyse erweitert · 1.4 Preistafeln festgehalten (Rabattmechanik 10,25 Monate, Vergabestellen-Preise, Zahlungsarten) · 1.5 Erfolgsprämie gestrichen; Testphase ergänzt; Free-Kontingent vereinheitlicht · 1.6 Stufen umbenannt (Analyse / Strategie); Strategie auf 349 €; drei getrennte Preisachsen; Kontingenteinheit „Vorgang"; Account-Sharing; Konzernfähigkeit · 1.7 Profilpauschale durch Profilpakete ersetzt; Hochrechnung der Achsenanteile ergänzt (§9); Vergabestellenseite als V2 markiert; Bau-Checkliste (§13) · 1.8 Profilverteilung gemessen (§9.2); §7.3 gegen die Messung korrigiert (zwei widerlegte Aussagen); Datengrenze „TED kennt keine unterlegenen Bieter" festgehalten · **1.9 Profilstaffel S/M/L/XL gestrichen; stattdessen eine Erweiterung zu 29 € für Nutzer wie Unternehmensprofil — zwei Preisachsen statt drei; „Paket" bezeichnet nur noch die Stufe**

---

## 1. Die Leitregel

> **Was pro Ausschreibung passiert, ist unbegrenzt. Was über Ausschreibungen hinweg geht, staffelt.**

Begründung: Wer an einem konkreten Verfahren arbeitet, darf darin nicht auf ein Zählwerk stoßen — ein
halb aufgeschlossener Vorgang ist für den Nutzer wertlos und für goVisor kein Umsatz, sondern eine
Kündigung in Zeitlupe. Die Staffel greift dort, wo Funktionen **erst ab einer bestimmten
Marktaktivität Sinn ergeben**: Wer fünf Ausschreibungen im Jahr macht, braucht keine
24-Monats-Pipeline und keine Wettbewerbslandschaft.

Die Trennlinie ist **operativ gegen strategisch**, nicht „viel gegen wenig".

---

## 2. Die Stufen

| Stufe | Wofür | Wer |
|---|---|---|
| **Testphase** | 4 Wochen kompletter Zugang, ohne Zahlungsmittel. → §3a | jeder neue Account |
| **Free** | Dauerzustand nach der Testphase. Alles sichtbar, 3 Vorgänge im Monat. | Nichtnutzer, Gelegenheitsbieter |
| **Analyse (+)** | Der komplette Vorgang je Ausschreibung — unbegrenzt. | Regelmäßige Bieter |
| **Strategie (++)** | Marktbearbeitung über Ausschreibungen hinweg. | Systematische Marktbearbeiter, Bid-Teams |

**Zu den Namen:** Beide Stufen tragen die Arbeit des Kunden im Namen — erst ein Verfahren durchdringen,
dann den Markt bearbeiten. Die Zuordnung ist eins zu eins: Das Paket *Strategie* schaltet den Bereich
*Strategie* frei. „Pro" und „Premium" sagten nur „teurer", nicht „anders", und ließen den Kunden über
Geld statt über Zweck verhandeln.

**Founding ist ein Preisattribut, kein Stufenname** — „Founding-Preis", nicht „Founding Analyse".

---

## 2a. Die drei Preisachsen

Paket und Erweiterung sind **unabhängig voneinander**. In v1.5 hingen Sitzplätze noch
am Funktionsumfang — wer einen zweiten Nutzer brauchte, musste die strategische Ebene mitkaufen, die er
nicht wollte. Das ist keine Staffel, das ist eine Zwangsbündelung.

| Achse | Was sie bepreist | Preis |
|---|---|---|
| **Paket** | die Leistung | Analyse 99 € · Strategie 349 €, je 1 Nutzer und 1 Unternehmensprofil |
| **Erweiterung** | jede weitere Einheit — Nutzer **oder** Unternehmensprofil | 29 €/Mon · 299 €/Jahr, in **beiden** Paketen gleich |

**Ein Satz für die Preisseite:** Das Paket ist die Leistung, die Erweiterung ist alles Weitere — ein
Nutzer oder eine bietende Einheit, beides zum gleichen Preis.

> **Eine Erweiterung ist entweder ein weiterer Nutzer oder ein weiteres Unternehmensprofil.**
> Gleicher Preis, gleiche Mechanik. Auf der Rechnung erscheinen beide als eigene Zeile mit demselben
> Einzelpreis, damit erkennbar ist, was freigegeben wird; technisch ist es ein Preisobjekt mit Menge.

**Warum nur eine Zusatzachse** (v1.9 hat die frühere Profilstaffel S/M/L/XL gestrichen):

1. **Eine Mengenstaffel hätte kaum mehr eingebracht.** Gegen die gemessenen Konzerne gerechnet (§9.2)
   liegt der flache Preis über die ganze Spanne innerhalb von 20 % der Staffel: Bechtle mit 35 Profilen
   zahlt flach 986 €, gestaffelt hätte es 999 € gekostet. Der Unterschied ist mechanisch — eine Staffel
   kassiert die Bandobergrenze, flach kassiert genau.
2. **Der Preis der Komplexität war höher als der Ertrag.** Vier Stufen, eine zweite Bedeutung des Worts
   „Paket" und eine Rechenaufgabe auf der Preisseite für 6 % Umsatz (§9.1). Ein Solo-Vertrieb kann sich
   keine Preisseite leisten, die erklärt werden muss.
3. **Mehrere Unternehmensprofile bleiben eine Korrektheitsanforderung, keine Preisfrage.** Ein Konzern
   mit acht bietenden Einheiten *braucht* acht Profile, sonst behauptet die Handlungsempfehlung
   Fähigkeiten, die die bietende Einheit nicht hat (§7). Gebaut wird das unabhängig davon, wie
   abgerechnet wird.

**Warum der Erweiterungspreis in beiden Paketen gleich ist:** Die Differenz zwischen den Stufen bleibt
dadurch bei jeder Konstellation konstant **250 €**. Kein Kunde muss rechnen, ab welcher Kopf- oder
Einheitenzahl sich ein Wechsel lohnt — die Frage lautet nur noch, ob er die strategische Ebene will.

**Bekannte Unschärfe, bewusst in Kauf genommen:** Ein gleicher Preis behauptet, ein Profil sei so viel
wert wie ein Sitzplatz. Ist es nicht — ein Sitzplatz ist Zugang zu dem, was schon da ist, ein Profil ist
ein zusätzlicher Markt mit eigenen CPVs, eigener Region, eigenen Wettbewerbern, und auf der Stufe
Strategie vervielfacht es die Auswertung. Das Niveau trifft dennoch: Ein Konzern wie Bechtle landet bei
rund 12.000 €/Jahr, im Zielkorridor. Offener Punkt für den ersten Konzern-Abschluss auf Strategie
(§10).

**Kein gebauter Umstiegspunkt.** Es wäre möglich, den Sitzplatz so zu bepreisen, dass Analyse mit fünf
Nutzern genau so viel kostet wie Strategie (nötig wären 62,50 € je Sitzplatz). Das wird **nicht**
gemacht:

1. **Der Sitzplatzpreis ist nach unten gedeckelt.** Er muss niedrig genug bleiben, dass niemand den
   Login teilt. Bei 62,50 € spart ein Fünf-Personen-Team 3.000 € im Jahr durch einen geteilten Zugang —
   und die personengebundenen Funktionen (§7) verlieren ihren Sinn.
2. **Teamgröße und strategischer Bedarf korrelieren nicht.** Ein sechsköpfiges Bau-Bieterteam arbeitet
   rein operativ, ein Einzelberater braucht Marktintelligenz dringender als jedes Systemhaus.
3. **Die Zielgruppe erkennt es.** Menschen, die beruflich Preisblätter auf versteckte Mechanik prüfen,
   sehen einen konstruierten Indifferenzpunkt sofort. Das beschädigt das Ehrlichkeitsversprechen an
   genau der Stelle, an der der Kunde bewertet.

**Ergebnisdaten-Reziprozität** bleibt eine vierte, unbepreiste Achse: wer meldet, sieht die
Wettbewerbsmenge — stufenunabhängig, **nie bepreisen**.

**Keine Erfolgsprämie.** Gestrichen mit v1.5. Der Business Case liegt ohne Prämie höher und ist
planbarer; die Prämie hätte Attribution, Rechnungslauf und einen menschlichen Prüfschritt je Fall
verlangt und nur auf den ~65 % der Vergaben mit echtem Auftragswert abgerechnet werden können. Was
verloren geht, ist die Erzählung („wir verdienen, wenn ihr gewinnt"), nicht der Umsatz.

---

## 3. Zuordnung nach Navigation

Die Stufe hängt am **Bereich beziehungsweise Tab**, nicht am einzelnen Feature. Das ist im Interface
eindeutig kennzeichenbar und für den Nutzer nachvollziehbar.

**Grundsatz: eine Stufe je Tab.** Wo ein Tab gemischt wäre, wird er geteilt (§3.5). Ein Tab, in dem
manches nutzbar und manches gesperrt ist, ist weder erklärbar noch verkaufbar.

### 3.1 Bereiche (Navigationsleiste)

| Bereich | Stufe | Begründung |
|---|:---:|---|
| **Akquise** (Liste + Lead-Detail) | gemischt je Tab → §3.2 | Kern des Produkts |
| **Merkliste / Cockpit** (#17) | **+** | Arbeitswerkzeug, setzt regelmäßige Teilnahme voraus |
| **Netzwerk** (Partnersuche, Freigaben) | gemischt → §3.8 | Free passiv, Analyse aktiv |
| **Strategie** (8 Sektionen) | **++** | über Ausschreibungen hinweg |
| **Unser Unternehmen** (#27, #28) | **Free** | Voraussetzung, nicht Leistung — erstes Profil frei, weitere nach §8 |
| **Profil** (Bausteine, Import, Einstellungen) | **Free** | Bausteine kosten nichts und binden |

### 3.2 Lead-Detail — Tabs

| Tab | Stufe | Inhalt |
|---|:---:|---|
| Übersicht | **Free** | Eckdaten, Lose, Wettbewerbslage, Leistungsort |
| Teilnahme | **Free** | Fristen, Link zu den Vergabeunterlagen (#13, #16) |
| **Unterlagen** | **+** *(Free: zählt als Vorgang)* | Upload, Checkliste, Textbausteine (#23) |
| **Bewertung** | **+** *(Free: zählt als Vorgang)* | Direktvergleich, Wechselwahrscheinlichkeit, Anforderungen, Aufwand, Bid/No-Bid (#3/#15/#18/#19/#26) |
| Vergabestelle | **+** | Vergabeverhalten dieser Stelle |
| Markt | **+** | Wettbewerbsumfeld dieser Ausschreibung |
| Team | **+** | interne Zuordnung |

> **Unterlagen und Bewertung sind zusammen der Aufschluss eines Vorgangs.** Wer einen der beiden Tabs
> öffnet, hat den Vorgang aufgeschlossen — und damit alle Tabs dieses Leads frei, dauerhaft.
> Zählweise: §4.3.

### 3.3 Zuschlag-Detail — Tabs (#24)

| Tab | Stufe |
|---|:---:|
| gesamter Bereich inkl. Liste, Detail, Alert | **++** |
| Spiegelseite „Ihr habt gewonnen" | **+** |

> Die Spiegelseite gehört in Analyse: Wer selbst gewinnt, soll Partner finden können — das füttert das
> Netzwerk und ist kein strategisches Werkzeug.

### 3.4 Cockpit — Bereiche (#17)

| Bereich | Stufe |
|---|:---:|
| Beobachtet (Merkliste) | **Free** |
| Aktiv (Pipeline) | **+** |
| Historie | **+** |

> Die Merkliste bleibt frei, damit Free-Nutzer Leads sammeln können — das erzeugt Bindung und später
> Ergebnisdaten.

### 3.5 Firmenprofil — muss geteilt werden (#25)

Heute eine durchgehende Seite mit gemischtem Wert. Für die Stufenlogik wird sie in **zwei Tabs**
geschnitten:

| Tab | Stufe | Inhalt |
|---|:---:|---|
| **Übersicht** | **+** *(zählt auf das Free-Kontingent, §4.3)* | Identität, Zuordnungsgüte, Kennzahlen, Leistungsfelder, Regionen |
| **Angriffspunkte** | **++** | Wo das Unternehmen festsitzt · Was dort ausläuft · Kopf an Kopf · weitere Signale · Beobachten |

**Bau-Konsequenz für #25:** Die Seite erhält eine Tab-Leiste. §5.1 bis §5.5 des Tickets wandern in
„Angriffspunkte", §4 bleibt in „Übersicht".

### 3.6 Strategie — Sektionen (#10)

| Sektion | Stufe |
|---|:---:|
| Pipeline · Felder · Vergabestellen · Wettbewerb | **++** |
| Position · Fähigkeiten · Bindung · Profil | **++** |

Der gesamte Bereich liegt auf der Stufe Strategie. Keine Ausnahme, kein Free-Kontingent.

### 3.7 Querschnitt: was überall frei ist

| Element | Stufe | Begründung |
|---|:---:|---|
| Herkunfts-Flags (gemessen/geschätzt/unbekannt) | **Free** | Ehrlichkeitsprinzip gilt in jeder Stufe |
| Suche, Filter, Lead-Liste | **Free** | kostet nichts, schafft Reichweite |
| Bausteinbibliothek + Import (#23) | **Free** | Speicher kostet nichts, bindet stark |
| Eignungsprofil, Bilanz (#27, #28) — erstes Profil | **Free** | Voraussetzung für jede Bewertung |
| Netzwerk: Freigabe, Interesse bekunden, antworten | **Free** | Beiträge nie bepreisen — Dichte (§3.8) |
| Eigene Teilnahmen privat tracken | **Free** | Kaltstart-Löser für die Ergebnisdaten (#11) |

### 3.8 Netzwerk — Free ist passiv, Analyse ist aktiv

Das Netzwerk lebt von Dichte. Beiträge dürfen deshalb nie hinter eine Bezahlschranke — wer etwas
**gibt**, darf das in jeder Stufe. Bezahlt wird das **aktive Suchen und Ansprechen**.

| Handlung | Free | + | ++ |
|---|:---:|:---:|:---:|
| Unternehmensprofil im Netzwerk anlegen, Freigabe setzen | ○ | ○ | ○ |
| **Interesse an einem Los bekunden** | ○ | ○ | ○ |
| Von anderen gefunden und angesprochen werden | ○ | ○ | ○ |
| Auf eine Anfrage antworten | ○ | ○ | ○ |
| Eigene Bekundungen verwalten und zurückziehen | ○ | ○ | ○ |
| **Sehen, wer sonst Interesse an dieser Vergabe hat** | — | ○ | ○ |
| **Partner aktiv suchen und filtern** | — | ○ | ○ |
| Andere von sich aus ansprechen | — | ○ | ○ |
| Zuschlagsgewinner kontaktieren (#24) | — | — | ○ |

**Begründung der Grenze:** Die interessantesten Partner bei Mehr-Los-Vergaben sind oft kleine,
regionale Anbieter, die genau ein Los abdecken — typische Free-Nutzer. Dürften nur Zahlende bekunden,
suchte ein Analyse-Kunde in einem leeren Pool und zahlte für ein Feature ohne Gegenüber. Und wer
angesprochen wird, muss antworten können, sonst ist die Kette einseitig.

**Verifizierung statt Bezahlung:** Interesse bekunden darf, wer ein bestätigtes Unternehmensprofil hat
(`entity_confidence` = confirmed). Das filtert Wegwerf-Accounts, ohne Dichte zu kosten.

**Free-Erlebnis:** Der Free-Nutzer sieht, dass es Interessenten gibt („4 Unternehmen haben Interesse an
Los 2 bekundet"), aber nicht wer — Blur mit Upgrade-CTA.

**Konzerne:** Im Netzwerk erscheint **jedes Unternehmensprofil einzeln**, nie der Konzern als Ganzes —
sonst stimmen CPV- und Regionsangaben für keine der Einheiten (§8.2).

---

## 3a. Testphase — vier Wochen Vollzugang

**Jeder neue Account startet mit vier Wochen komplettem Zugang** — alle Funktionen beider Stufen,
unbegrenzt, ohne Zahlungsmittel bei der Registrierung. Ein Nutzer, ein Unternehmensprofil.

**Nach vier Wochen fällt der Account automatisch auf Free.** Keine Sperre, keine Zwangsentscheidung,
kein Wiedereinlogg-Hindernis. Was aus Free heraus nicht mehr geht, bleibt sichtbar und benannt (§4.1).

**Warum ein Abfall auf Free und kein harter Stopp:**

1. **Das Verfahren ist länger als der Test.** Vom Ausschreibungsstart bis zum Zuschlag vergehen im
   Median 87 Tage. Vier Wochen zeigen keinen abgeschlossenen Vorgang — wer danach aussperrt, sperrt
   mitten im Prozess aus.
2. **Free-Nutzer produzieren, was das Produkt besser macht:** Ergebnisdaten (#11), Korpus-Beiträge
   (#23), Netzwerkdichte (§3.8). Ein stillgelegter Account produziert nichts.
3. **Ein gesperrter Account kommt nie zurück.** Ein Free-Account kommt wieder, wenn die nächste
   passende Ausschreibung erscheint — und genau dann ist die Zahlungsbereitschaft da.

**Ankündigung:** eine Woche vor Ablauf, mit konkretem Bezug auf die tatsächliche Nutzung („Sie haben in
den letzten Wochen 9 Ausschreibungen bewertet — ab dem 14. sind es drei im Monat"). Kein generisches
„Ihr Testzeitraum endet bald".

**Kein Trial-Abuse-Schutz über Karte.** Die Registrierung bleibt ohne Zahlungsmittel. Missbrauch wird
über das bestätigte Unternehmensprofil begrenzt (`entity_confidence`), nicht über eine Hürde, die echte
Interessenten kostet.

> **Widerspruch zum Gesamtflow-Dokument:** `govisor-v1-gesamtflow_v2.md` nennt „Kein Trial (kein
> Trial-Abuse)" als bewusste Entscheidung. Diese Entscheidung ist mit v1.5 aufgehoben — das Dokument
> ist nachzuziehen (§11).

---

## 4. Free: alles sichtbar, drei Vorgänge im Monat

Kein verstecktes Produkt. Jede Funktion ist **im Interface vorhanden** — aber in zwei Zuständen:

- **Funktionen der Stufe Analyse:** in drei Vorgängen im Monat echt nutzbar, danach gesperrt.
- **Funktionen der Stufe Strategie:** dauerhaft nur sichtbar, nie nutzbar — auch nicht einmal.

### 4.1 Die drei Darstellungsformen

| Form | Wo | Warum |
|---|---|---|
| **Echte Nutzung** | Analyse-Funktionen, innerhalb der drei Vorgänge | Der Nutzer erlebt den vollen Wert an seinen eigenen Daten |
| **Demowerte** | Strategie-Funktionen + verbrauchte Analyse-Funktionen, wo die Struktur den Wert zeigt | Strategie-Sektionen, Firmenprofil-Kennzahlen — die Form ist die Botschaft |
| **Blur** | Strategie-Funktionen + verbrauchte Analyse-Funktionen, wo der Einzelwert die Botschaft ist | Auslaufliste, Kopf-an-Kopf, Wechselwahrscheinlichkeit |

**Regel für die Wahl:** Ist die *Struktur* aussagekräftig (eine Pipeline-Kurve, eine
Wettbewerbstabelle), zeigen Demowerte den Nutzen besser als ein Weichzeichner. Ist der *konkrete Wert*
die Botschaft („dieser Vertrag läuft im März 2027 aus"), ist Blur ehrlicher — Demowerte wären dort
irreführend.

**Pflicht bei Demowerten:** deutlich als Beispiel gekennzeichnet, niemals mit echten Daten verwechselbar.

### 4.2 CTA-Regeln

| Situation | CTA |
|---|---|
| Testphase läuft | Restlaufzeit sichtbar, kein Upgrade-Druck |
| Testphase endet in ≤ 7 Tagen | Hinweis mit Bezug auf die tatsächliche Nutzung (§3a) |
| Vor Verbrauch (noch Vorgänge übrig) | Zähler sichtbar: „2 von 3 Vorgängen diesen Monat" |
| Nach Verbrauch, Analyse-Funktion | „Unbegrenzt mit Analyse" + was konkret freigeschaltet wird |
| Strategie-Funktion (in Free wie in Analyse) | CTA mit Nutzenbezug auf **diese** Ansicht — kein Zähler, da nie nutzbar |

**Nie:** generisches „Jetzt upgraden". Der CTA benennt immer, was diese eine Ansicht liefert.

### 4.3 Zählweise — eine Zahl, eine Einheit

> **Drei Vorgänge im Monat.**

Ein Vorgang ist:

- **ein Lead mit allem, was daran hängt** — Bewertung, Unterlagen, Empfehlung und die Firmenprofile
  der an diesem Lead beteiligten Unternehmen (Vergabestelle, Auftragnehmer, Wettbewerber), **oder**
- **ein einzeln aufgerufenes Firmenprofil**, also eines, das nicht über einen aufgeschlossenen Lead
  erreicht wurde.

**Ein aufgeschlossener Vorgang bleibt offen** — dauerhaft, auch über den Monatswechsel hinaus. Ein
Verfahren zieht sich über Monate; ein Lead, für den man erneut zahlen müsste, wäre absurd.

**Kein Kontingent** haben: Strategie-Bereich, Zuschlagsphase und der Firmenprofil-Tab
„Angriffspunkte". Sie liegen auf der Stufe Strategie und sind in Free nie nutzbar.

**Warum die Einheit „Vorgang" heißt und nicht „Analyse":** Der Stufenname *Analyse* ist ab v1.6
vergeben. Hieße das Free-Kontingent weiter „3 Analysen", hätte Free Analysen, während das Paket
*Analyse* kostenpflichtig ist — unerklärbar. „Vorgang" ist zudem das Wort, das diese Zielgruppe ohnehin
benutzt.

**Warum eine Zahl statt zwei Kontingente:** Zwei Zähler sind auf der Preisseite nicht erklärbar und im
Interface nicht anzeigbar, ohne dass der Nutzer rechnet. Und wer einen Lead bewertet, will das
Firmenprofil des Auftragnehmers ohnehin sehen — es getrennt zu zählen bestrafte genau den Weg, den das
Produkt nahelegt.

**Bau-Konsequenz:** ein Zählwerk (`vorgang_credits`), ein Auslöser je Lead (erstes Öffnen von
Unterlagen *oder* Bewertung), Firmenprofile im Lead-Kontext zählen nicht mit.

---

## 5. Preistafel

### 5.1 Pakete

| Stufe | Monatszahlung | Jahreszahlung | rechnerisch 12× | Rabatt | enthalten |
|---|---|---|---|---|---|
| **Analyse (+)** | 99 €/Mon | **1.019 €/Jahr** | 1.188 € | 14,2 % | 1 Nutzer, 1 Profil |
| **Strategie (++)** | 349 €/Mon | **3.579 €/Jahr** | 4.188 € | 14,5 % | 1 Nutzer, 1 Profil |

### 5.2 Erweiterungen

| Position | Monatszahlung | Jahreszahlung |
|---|---|---|
| **Erweiterung** — weiterer Nutzer **oder** weiteres Unternehmensprofil | **29 €** | **299 €** |

Gleicher Preis in beiden Paketstufen, linear, keine Staffel, keine Obergrenze.

**Auf der Rechnung zwei Zeilen, technisch eine Position.** Der Kunde sieht „3 × weiterer Nutzer" und
„2 × weiteres Unternehmensprofil" mit demselben Einzelpreis, damit erkennbar ist, was er freigibt.
Abrechnungsseitig ist es ein Preisobjekt mit Menge.

**Keine Mengenstaffel.** Gegen die gemessenen Konzerne (§9.2) gerechnet hätte eine Staffel kaum mehr
eingebracht:

| Konzern | Profile | flach 29 € | Staffel (verworfen) |
|---|---:|---:|---:|
| Bechtle | 35 | 986 € | 999 € |
| STRABAG | 34 | 957 € | 999 € |
| Median-Konzern | 8 | 203 € | 249 € |

Über die ganze gemessene Spanne liegt der flache Preis innerhalb von 20 % der Staffel. Der Unterschied
ist mechanisch: Eine Staffel kassiert die Bandobergrenze — wer vier Profile hat, zahlt den „bis
acht"-Preis —, flach kassiert genau. Der Ertrag der Staffel lag bei rund 6 % Gesamtumsatz (§9.1) und
kostete vier Preisstufen, eine zweite Bedeutung des Worts „Paket" und eine Rechenaufgabe auf der
Preisseite. Ein Solo-Vertrieb kann sich keine Preisseite leisten, die erklärt werden muss.

**Obergrenze und Erweiterbarkeit:** Die Abrechnungslogik ist so zu bauen, dass eine Mengenstaffel
später ohne Schemaänderung nachgezogen werden kann — Preis je Einheit konfigurierbar, Menge als eigenes
Feld. Eingeführt wird sie erst, wenn drei Konzern-Abschlüsse zeigen, dass sie nötig ist.

### 5.3 Rechenbeispiele

Erweiterungen = (Nutzer − 1) + (Unternehmensprofile − 1).

| Konstellation | Erweiterungen | Analyse | Strategie |
|---|:---:|---|---|
| 1 Nutzer, 1 Profil | 0 | 99 € | 349 € |
| 3 Nutzer, 1 Profil | 2 | 157 € | 407 € |
| 5 Nutzer, 1 Profil | 4 | 215 € | 465 € |
| 5 Nutzer, 3 Profile | 6 | 273 € | 523 € |
| 20 Nutzer, 8 Profile | 26 | 853 € | 1.103 € |
| 40 Nutzer, 35 Profile | 73 | 2.216 € | 2.466 € |

Die Differenz zwischen den Stufen beträgt bei **jeder** Konstellation 250 €.

**Referenzfall Konzern** (Strategie, 20 Nutzer, 8 Profile): 1.103 €/Mon bei Monatszahlung,
**11.353 €/Jahr** bei Jahreszahlung. Zur Einordnung: Patterno ruft für seine Spitzenstufe 2.499 €/Monat
*je Nutzer* auf.

### 5.4 Founding-Preis

| Stufe | Monatszahlung | Jahreszahlung |
|---|---|---|
| Analyse | 49 €/Mon | 509 €/Jahr |
| Strategie | 149 €/Mon | 1.529 €/Jahr |

Die ersten **50 Kunden**, **unbegrenzt gültig**, solange das Abo läuft. Gilt für alle Founding-Kunden
gleich — persönliche Kontakte zahlen nicht mehr und nicht weniger als spätere.

**Der Founding-Preis gilt nur für das Paket.** Erweiterungen werden zum Listenpreis abgerechnet. Sonst skaliert ein einzelner Founding-Kunde den Rabatt unbegrenzt.

### 5.5 Rabatt- und Zahlungsmechanik

**Rabattmechanik:** Der Jahrespreis entspricht **10,25 Monatspreisen** (12 minus 1,75 Monate),
kaufmännisch aufgerundet auf eine 9er-Endung. Kein Monatsaufschlag — der Monatspreis ist der
Listenpreis, der Jahrespreis der Vorteil. Gilt für beide Achsen.

**Zahlungsart:** SEPA-Lastschrift als Voreinstellung, Karte als Alternative. SEPA kostet pauschal
0,35 € statt 1,5 % + 0,25 €.

**Zur Einordnung:** Der Jahresrabatt ist ein **Cashflow- und Bindungsinstrument**, kein
Kostenoptimierer. Die Gebührenersparnis durch eine statt zwölf Buchungen liegt bei 4–10 € je Kunde und
Jahr und steht in keinem Verhältnis zum Rabatt.

### 5.6 Einordnung im Markt

Recherchestand 07/2026:

| Anbieter | Preis/Monat | Leistung |
|---|---|---|
| Vergabe24 | 18 € | reine Suche |
| AusschreibungsRadar | 9 / 29 / 79 / 149 € | Watchlist bis Bid/No-Bid + CRM |
| Vergabepilot | 0 / 60 / 125 € | KI-Suche 300+ Portale — Preis gilt für alle Nutzer |
| BidFix | 0 / ab 79 € | Suche bis Angebotserstellung |
| Patterno | 99 / 499 / 2.499 € | KI-Suche, Branchenmodule, Marktintelligenz — je Nutzer |
| DTAD | auf Anfrage | größte Quellenabdeckung |

**Begründung für 99 €:** Der Vergleichsrahmen des Käufers ist Vergabepilot (60–125 €) und
AusschreibungsRadar (79 €). 99 € sitzt mittig und ist ohne Rechtfertigungsaufwand verkäuflich.

**Begründung für 349 €:** Über Vergabepilot (125 €) endet der Wettbewerb, Patterno springt auf 499 €.
Zwischen 250 und 500 € steht niemand. Diese Stufe kauft ein Bid-Team, für das 4.188 € im Jahr weniger
sind als zwei Personentage an einer einzigen Ausschreibung. Zusätzlich: Der Founding-Preis von 149 €
gilt unbegrenzt — je höher die Liste, desto stärker der Grund, zu den ersten 50 zu gehören.

**Marktdurchdringung:** DTAD nennt >5.500 Kunden — bei rund 150.000 bietenden Unternehmen liegt die
Durchdringung im niedrigen einstelligen Prozentbereich. **Der Hauptwettbewerber ist „kein Tool".**

---

## 6. Sitzplätze — was ein Nutzer bekommt

Die Abgrenzung entscheidet, ob der Sitzplatzpreis gerechtfertigt wirkt. Sie ist zugleich der stärkste
Schutz gegen geteilte Zugänge (§9).

| Nutzergebunden (je Sitzplatz) | Kontogebunden (einmal je Unternehmensprofil) |
|---|---|
| eigener Login | Vorgangs-Kontingent |
| eigene Merkliste und Pipeline-Sicht | Unternehmensprofil (#27), Bilanz (#28) |
| eigene Alerts (#9) und Zustellung | Bausteinbibliothek (#23, Ebene B) |
| Zuordnung im Team-Tab | Checkliste auf Ebene A |
| Autorschaft an Textbausteinen, „zuletzt geändert von" | Netzwerk-Freigaben und Bekundungen |
| eigene Kommentare und Notizen | Abrechnung |

**Bau-Konsequenz:** Alles in der linken Spalte braucht `user_id` als Fremdschlüssel, alles in der
rechten `profile_id`. Diese Trennung ist die Voraussetzung für §8 und §9.

---

## 7. Mehrere Unternehmensprofile (Konzerne)

**Ein Konto kann mehrere Unternehmensprofile führen. Das ist nicht optional.**

Ein Konzern bietet über rechtlich getrennte Einheiten mit eigenen HRB-Nummern, eigenen Zertifikaten,
eigenen Regionen. Ein zusammengeführtes Eignungsprofil (#27) würde bei jedem Lead Fähigkeiten
behaupten, die die bietende Einheit nicht hat — und die Handlungsempfehlung (#26) wäre systematisch
falsch. Direktvergleich, Verteidigungsquote (#25) und Ergebnisdaten (#11) hängen ebenfalls an der
einzelnen Entity, weil TED-Zuschläge an der einzelnen Entity hängen.

**Die Architektur trägt das bereits.** `relevance(entity, tender)` statt `relevance(lead, current_user)`
aus dem Architekturprinzip heißt genau das: Das Profil ist das erste Objekt, nicht der Nutzer.

### 7.1 Modell

```
Konto (Abrechnung, Paketstufe, Zahl der Erweiterungen)
 ├── Unternehmensprofil A (entity-gebunden, eigenes Eignungsprofil)
 ├── Unternehmensprofil B
 └── Nutzer 1..n — je Nutzer einem oder mehreren Profilen zugeordnet
```

Die Paketstufe gilt für das Konto, nicht je Profil. Ein Nutzer kann zwischen den ihm zugeordneten
Profilen wechseln; die aktive Profilauswahl bestimmt Bewertung, Empfehlung und Direktvergleich.

### 7.2 Zwei harte Regeln

> **Einheiten desselben Konzerns bieten gegeneinander.** Das ist in Systemhaus- und Bau-Gruppen
> Alltag. Textbausteine und Unterlagen auf **Ebene B dürfen standardmäßig nicht über Profilgrenzen
> hinweg sichtbar sein** — Freigabe nur explizit, je Profilpaar, protokolliert. Technisch dieselbe
> RLS-Trennung wie gegenüber Fremdfirmen, nur innerhalb des Kontos. Ohne das fällt goVisor in jeder
> Konzern-Compliance-Prüfung durch.

> **Im Netzwerk erscheint jedes Profil einzeln**, nie der Konzern als Ganzes. Sonst stimmen CPV- und
> Regionsangaben für keine der Einheiten, und Partneranfragen laufen an die falsche Einheit.

### 7.3 Grenzen je Stufe

| | Profile |
|---|---|
| Testphase | genau **1** |
| Free | genau **1** |
| Analyse / Strategie | 1 enthalten, jedes weitere ist eine Erweiterung zu 29 € (§5.2) |

**Nur bietende Einheiten sind zählbar.** Ein Unternehmensprofil ist „unsere bietende Einheit" (#27).
Einheiten ohne Zuschlagshistorie erhalten kein Profil, weil es nichts anzeigen würde.

**Gemessen (§9.2) — zwei frühere Annahmen dieses Abschnitts sind widerlegt:**

| Frühere Annahme (bis v1.7) | Messung |
|---|---|
| „Ein Konzern mit 30 Gesellschaften bietet häufig über drei bis fünf." | **Falsch.** Median **11** bietende Einheiten je Gruppe, p75 22, Max 35. Selbst bei strenger Aktivitätsschwelle (≥ 5 Zuschläge / 3 Jahre) sind es 5. |
| „Holdings, Besitz- und Servicegesellschaften tauchen in TED nie als Bieter auf." | **Nur für Holdings richtig.** 28 Einheiten mit Zuschlag tragen ein Servicewort im Namen, angeführt von „SPIE Information & Communication Services GmbH" mit 45 Zuschlägen. Service-GmbHs bieten. |

Richtig bleibt die Grundaussage: **Bietende Einheiten liegen weit unter der Zahl der Gesellschaften** —
STRABAG 34 von 123. 253 Gesellschaften der fünfzehn gemessenen Gruppen haben im Dreijahresfenster keinen
einzigen Zuschlag, davon 89 allein bei STRABAG.

**Zwei Datengrenzen, die für #11 und #27 gelten:**

> **TED kennt keine unterlegenen Bieter.** `party_entity.role` hat genau vier Werte: `buyer`, `winner`,
> `review`, `mediation`. Eine Einheit, die bietet und nie gewinnt, ist in TED unsichtbar. Alle
> Einheitenzahlen sind deshalb **Untergrenzen** — und es ist der eigentliche Grund für die
> Ergebnisdaten-Achse (#11) und den Unterlagen-Import (#23).

> **Die Konzernzuordnung ist markengenau, nicht mutterkonzerngenau.** Sie läuft zu 98,3 % über
> `auto_domain` (E-Mail-Domain bestätigt den Namen). Eine Tochter mit eigenem Namen und eigener Domain
> fällt heraus: ZÜBLIN erscheint als eigene Gruppe, obwohl es zu STRABAG gehört; EUROVIA und AXIANS
> gehören beide zu VINCI. Für die Profilzählung heißt das: Ein Kunde kann mehr Einheiten zusammenfassen
> wollen, als die Messung je Marke zeigt.

---

## 8. Account-Sharing

Technisch verhindern lässt es sich nicht, ohne echte Nutzer zu treffen. Drei Hebel, nach Wirkung:

### 8.1 Produktgestaltung — der stärkste Hebel

Alles Personengebundene bleibt personengebunden (§6). Teilen sich vier Leute einen Login, laufen alle
Alerts in ein Postfach, die Merkliste wird unbrauchbar und im Team-Tab steht bei jedem Eignungsnachweis
derselbe Name. Das zerstört genau die Funktion, für die ein Bid-Team zahlt. Sharing wird dadurch nicht
verboten, sondern wertlos.

**Dazu gehört der niedrige Sitzplatzpreis.** 29 € liegen unter einer Arbeitsstunde eines
Bid-Managers — darunter lohnt das Teilen nicht mehr. Das ist der Grund, warum der Sitzplatzpreis nach
unten gedeckelt ist (§2a).

### 8.2 Sitzungsbegrenzung mit Verdrängung

Maximal **zwei gleichzeitige Sitzungen je Sitzplatz**, die neueste verdrängt die älteste. Legitime
Nutzung (Laptop plus Handy) bleibt unberührt, vier geteilte Nutzer werfen sich permanent gegenseitig
heraus. Wirksamste Einzelmaßnahme bei geringstem Supportaufwand.

### 8.3 Stille Erkennung, abgestufte Reaktion

| Signal | Aussagekraft |
|---|---|
| Unmögliche Ortswechsel (Sitzung Hamm → 20 Min später München) | hoch |
| Parallele Arbeit an verschiedenen Leads in derselben Minute | hoch — eine Person analysiert nicht zwei Verfahren gleichzeitig |
| Anzahl unterschiedlicher Geräte je 30 Tage (> 8) | mittel |
| Zeitgleiche Sitzungen aus verschiedenen Netzen | mittel — VPN und Homeoffice erzeugen Fehlalarme |

**Reaktionsleiter:**

1. nur werten, keine Anzeige
2. Hinweis im Interface mit Ein-Klick-Button „weiteren Nutzer hinzufügen"
3. persönlicher Kontakt

**Nie automatisch sperren.** Ein Fehlalarm gegen einen zahlenden Kunden kostet mehr als das geteilte
Konto.

### 8.4 Vertrag und Grenzen

AGB: Der Sitzplatz ist namensgebunden. Schafft die Handhabe, ersetzt keine Maßnahme.

**Nicht bauen:** Geräte-Registrierung, IP-Freigaben, MFA als Strafmaßnahme. Alle drei treffen
Außendienst und Homeoffice, erzeugen Supportlast, die neben einem Hauptjob nicht tragbar ist, und lösen
das Problem nicht.

**Nebenbefund:** Auf Free ist Sharing selbstlimitierend — drei Vorgänge im Monat, geteilt durch fünf
Personen, sind wertlos. Das Problem existiert praktisch nur auf der Stufe Analyse.

---

## 9. Hochrechnung: was die Achsen tragen

⚠ **Die Verteilung in §9.1 ist ungemessen** — sie beschreibt die erwartete Kundenbasis. Gemessen ist
dagegen die Einheitenzahl je Konzerngruppe (§9.2); sie betrifft nur den rechten Rand dieser Verteilung.

### 9.1 Anteile je 100 zahlende Kunden

Annahme Profilverteilung — daraus die Erweiterungen aus Profilen:

| Profile | Anteil | Kunden | Erweiterungen | Summe/Mon |
|---|---:|---:|---:|---:|
| 1 | 80 % | 80 | 0 | 0 € |
| 2–3 | 13 % | 13 | 20 | 580 € |
| 4–8 | 6 % | 6 | 30 | 870 € |
| 9 und mehr | 1 % | 1 | 10 | 290 € |
| | | | **60** | **1.740 €** |

Gegengerechnet mit Paketen (Annahme 70 % Analyse, 30 % Strategie) und Nutzer-Erweiterungen (Ø 2,5
Nutzer → 150 Erweiterungen):

| Position | Umsatz/Mon je 100 Kunden | Anteil |
|---|---:|---:|
| Pakete | 17.400 € | 74 % |
| Erweiterungen · Nutzer | 4.350 € | 19 % |
| Erweiterungen · Profile | 1.740 € | 7 % |
| **gesamt** | **23.490 €** | |

**Die Erweiterungsachse bringt +35 % gegenüber reinem Paketumsatz** — wirtschaftlich dasselbe wie 35
zusätzliche Kunden, ohne einen davon zu gewinnen. 210 Erweiterungen auf 100 Kunden, davon rund 70 % für
Nutzer.

**Konsequenz für die Priorisierung:** Die Erweiterung ist ein Beitrag, kein Geschäftsmodell — und
innerhalb der Achse tragen Nutzer fast dreimal so viel wie Profile. Der Aufwand für Profil-spezifische
Preismechanik sollte 7 % nicht übersteigen; das ist der Grund, warum die Mengenstaffel gestrichen wurde
(§5.2). Die Kundenzahl verdient alles andere.

### 9.2 Messergebnis — bietende Einheiten je Konzerngruppe

**Gemessen 09/2026** über den Gold Layer, 15 Gruppen (5 IT-Systemhäuser, 10 Bau), Fenster 36 Monate.
Konzernzuordnung zu 98,3 % über `auto_domain`; Einheiten nur dort getrennt, wo zwei verschiedene
deutsche USt-IDs vorliegen.

| Gruppe | Art | Einheiten | ≥ 2 Zuschläge | ≥ 5 Zuschläge | Zuschläge | NUTS-1 |
|---|---|---:|---:|---:|---:|---:|
| BECHTLE | IT | 35 | 21 | 14 | 579 | 17 |
| STRABAG | Bau | 34 | 17 | 7 | 203 | 15 |
| APLEONA | Bau | 24 | 18 | 10 | 217 | 14 |
| SPIE | Bau | 22 | 17 | 11 | 300 | 15 |
| JAEGER-AUSBAU | Bau | 21 | 15 | 10 | 123 | 14 |
| SCHMITT-AUFZUEGE | Bau | 14 | 11 | 8 | 123 | 11 |
| GOLDBECK | Bau | 14 | 10 | 8 | 118 | 15 |
| DATAGROUP | IT | 11 | 8 | 4 | 42 | 9 |
| EUROVIA | Bau | 10 | 7 | 3 | 118 | 13 |
| AXIANS | IT | 10 | 4 | 2 | 35 | 11 |
| ZUEBLIN | Bau | 8 | 2 | 2 | 21 | 8 |
| KAEFER | Bau | 8 | 7 | 5 | 120 | 14 |
| CANCOM | IT | 7 | 5 | 2 | 224 | 15 |
| COMPUTACENTER | IT | 4 | 2 | 2 | 253 | 14 |
| FLIESEN-ROEHLICH | Bau | 1 | 1 | 1 | 214 | 10 |

| Verteilung (n=15) | Median | p75 | Max | Min |
|---|---:|---:|---:|---:|
| aufgelöste Einheiten | **11** | 22 | 35 | 1 |
| davon ≥ 2 Zuschläge / 3 J. | **8** | 17 | 21 | 1 |
| davon ≥ 5 Zuschläge / 3 J. | **5** | 10 | 14 | 1 |
| IT-Systemhäuser (n=5) | 10 | 11 | 35 | 4 |
| Bau-Gruppen (n=10) | 14 | 22 | 34 | 1 |

**Was daraus folgt:**

1. **Grenzen 3 / 8 / 20 bleiben.** Maßgeblich ist nicht die Zahl bietender Einheiten, sondern die Zahl
   der Einheiten, für die ein Kunde ein Eignungsprofil pflegt — realistisch die Spalte „≥ 2 Zuschläge",
   Median 8. M = 8 liegt damit auf dem Median.
2. **XL bis 40 ist neu** (§5.2): fünf von fünfzehn Gruppen sprengen die 20, auf Markenebene.
3. **§7.3 war an zwei Stellen falsch** — korrigiert, mit den Zahlen im Abschnitt selbst.
4. **§9.1 bleibt gültig.** Die Hochrechnung beschreibt die Kundenbasis, nicht Großkonzerne; die Messung
   korrigiert den rechten Rand der Verteilung, nicht die Annahme, dass 80 % der Kunden ein Profil führen.

**Grenzen der Messung — beim Lesen mitführen:** Untergrenzen, weil TED keine unterlegenen Bieter kennt
(§7.3). Markenebene, nicht Mutterkonzern (§7.3). Und es sind fünfzehn handverlesene Großgruppen — über
den typischen Mehr-Einheiten-Kunden mit zwei bis vier bietenden GmbHs sagt die Messung nichts.

---

## 10. Offene Entscheidungen

| # | Punkt | Anmerkung |
|---|---|---|
| 1 | ~~Profilstaffel~~ | **erledigt mit v1.9** — gestrichen; ein Erweiterungspreis für Nutzer und Profile (§5.2). Preisseite ist freigegeben. |
| 2 | Erweiterungspreis 29 € | zwei Wirkungen gleichzeitig: Sharing-Schwelle (§8.1) und Profilpreis. Gegen die Sharing-Telemetrie (§8.3) und die ersten Konzern-Abschlüsse justieren. |
| 2a | Profilverteilung im Mittelstand | Die Messung (§9.2) deckt nur Großgruppen ab. Sobald 20 Kunden da sind: tatsächliche Profilzahl je Konto auswerten. |
| 3 | Profil auf Strategie teurer als auf Analyse? | Ökonomisch ja — Strategie × n Profile ist n Märkte strategischer Intelligenz. Bleibt einheitlich, weil eine Zahl die Preisseite trägt. **Beim ersten Konzern-Abschluss auf Strategie prüfen** — dort auch die Frage, ob eine Mengenstaffel nötig wird. |
| 5 | Free-Kontingent (3 Vorgänge/Monat) | an realen LLM-Kosten und Konversion justieren; §4.3 ist die Definition |
| 6 | Testphase-Länge (4 Wochen) | gegen Konversion messen, sobald 50 Accounts durchgelaufen sind |
| 7 | Stripe-Konditionen im eigenen Konto gegenprüfen | Quellen nennen 1,4–1,5 % für EWR-Karten; SEPA-Deckelung prüfen |

---

## 11. Nachzuziehende Dokumente

| Dokument | Was |
|---|---|
| **#6b (Billing/Auth)** | Erfolgsprämie entfernen · Zählwerk `vorgang_credits` nach §4.3 · Testphase als Account-Zustand mit automatischem Übergang auf Free · **Sitzplatzverwaltung**: Anlegen, Entziehen, Proration  · **Erweiterungen** als Menge je Konto, Einzelpreis konfigurierbar · **Sitzungsbegrenzung** nach §8.2 · **Sharing-Telemetrie** nach §8.3 |
| **#27 (Eignungsprofil)** | mehrere Profile je Konto · Profilwechsel im Interface · aktive Profilauswahl steuert Bewertung und Empfehlung  · jedes Profil ab dem zweiten ist eine Erweiterung (§5.2) |
| **#23 (Dokumentenanalyse)** | Prämien-Bezüge entfernen · Unterlagen-Tab als Auslöser des Vorgangs-Aufschlusses · **Ebene-B-Trennung zwischen Unternehmensprofilen desselben Kontos** (§7.2) |
| **#25 (Firmenprofil)** | Tab-Leiste Übersicht / Angriffspunkte (§3.5) |
| **#9 (Alerts)** | Alerts sind nutzergebunden, nicht kontogebunden (§6) |
| **#17 (Cockpit)** | Merkliste und Pipeline-Sicht nutzergebunden (§6) |
| **`govisor-v1-gesamtflow_v2.md`** | „Basis-Fee + Success-Fee" streichen · „Kein Trial" ist aufgehoben (§3a) · Metrik `win_reported` verliert den Prämienzweck, bleibt als Ergebnisdatum (#11) |
| **Alle Dokumente und Prototypen** | Stufennamen „Pro" und „Premium" → „Analyse" und „Strategie" · Kontingenteinheit „Analyse" → „Vorgang" · Prämien-Banner entfernen |

---

## 12. Vergabestellenseite — V2, nicht bauen

> **Vermerk: Die Vergabestellenseite (Vergabeblick) ist nicht Teil von V1.** Sie ist hier vollständig
> dokumentiert, damit die Entscheidungen nicht verloren gehen — **implementiert wird sie in V2.** Für
> V1 gilt: kein Vergabestellen-Onboarding, kein Ausschreibungscheck, kein zweiter Kontotyp im
> Produktiv-Flow.
>
> **Ausnahme, die trotzdem in V1 gehört:** die Spalte `profile_type` mit Default `bidder` und Check auf
> `('bidder','contracting_authority')`. Heute eine Zeile, nach dem Deployment mit Nutzern eine
> Migration plus Änderung am Auth-Flow. Das ist die einzige V1-Konsequenz aus diesem Abschnitt.

Eigene Logik — die Stelle gewinnt nichts, plant nur.

| Feature | Erst-Einblick | Check | Abo |
|---|:---:|:---:|:---:|
| Dashboard (Bieterzahl, Aufhebungsquote, KMU-Anteil) | ○ | ○ | ○ |
| Eine Markterkundungs-Kennzahl | ○ | ○ | ○ |
| Ausschreibungscheck (ein Entwurf) | — | ○ | ○ |
| Analysedokument zum Entwurf | — | ○ | ○ |
| Markterkundung, Wettbewerbsdichte, Anbieter-Verfügbarkeit | — | — | ○ |
| Zuschnitt-Optimierung / Bieterzahl-Prognose | — | — | ○ |
| Vergleichbare Vergaben (Comps) | — | — | ○ |
| Vergabe-Güte, Auftragnehmer-Beobachtung ⚖️ | — | — | ○ |
| Eigene Vergabe-Vorschau | — | — | ○ |
| KMU-Förderung, Preis-vs-Qualität-Benchmark | — | — | ○ |

| Angebot | Preis | Logik |
|---|---|---|
| Erst-Einblick | **0 €** | einmalig, Türöffner — kein Dauer-Freemium |
| Einzel-Ausschreibungscheck | **490 €** | ein Verfahren, ein Gutachten |
| **Jahresabo** | **3.900 €** | entspricht 8 Checks — lohnt ab regelmäßiger Nutzung |

**Kein Dauer-Freemium und keine Testphase:** Behörden kaufen vorgangsgebunden; ein dauerhafter
Gratis-Tier erzeugt hier keinen Netzwerkwert (anders als bei Bietern, die Dichte und Ergebnisdaten
liefern), und eine Vier-Wochen-Testphase passt nicht zum Haushaltsrhythmus.

**Nur Jahresabo, kein Monatspreis.** Behörden budgetieren im Haushaltsjahr; ein Monatsabo erzeugt zwölf
Rechnungen statt einer.

**Vergaberechtliche Einordnung (entscheidend):** Direktaufträge für Liefer- und Dienstleistungen sind
auf Bundesebene bis **15.000 € netto** zulässig (UVgO, befristete Regelung; geplante dauerhafte
Anhebung auf 50.000 €), Länder oft darüber. Alle drei Preise liegen deutlich darunter — eine
Vergabestelle kann **formlos beauftragen**, ohne eigenes Vergabeverfahren. Das ist ein wesentlicher
Vertriebsvorteil und begrenzt zugleich den Preisspielraum nach oben: Ab 15.000 € kippt der Kauf in ein
Verfahren und der Verkaufszyklus verlängert sich massiv.

**Rechnungsstellung:** Kauf auf Rechnung mit XRechnung und Leitweg-ID über die OZG-Rechnungs­
eingangsplattform ist Pflicht für diese Zielgruppe. Am Anfang manuell (kostenloser Generator +
OZG-RE-Upload), Automatisierung erst ab Volumen.

**Offen für V2:** landesspezifische Direktauftragsgrenzen je Bundesland für den Vertrieb dokumentieren.

---

## 13. Bau-Checkliste V1

Datenmodell:

- [ ] `accounts`: `tier` ∈ (`trial`,`free`,`analyse`,`strategie`), `trial_ends_at`, `seat_count`, `company_profile_count` — Erweiterungen = (seat_count − 1) + (company_profile_count − 1); Einzelpreis konfigurierbar
- [ ] `user_profiles.profile_type` mit Default `bidder`, Check auf (`bidder`,`contracting_authority`) — **jetzt einziehen** (§12)
- [ ] `company_profiles`: n je Konto, entity-gebunden, `entity_confidence`
- [ ] `user_profile_assignments`: Nutzer × Unternehmensprofil
- [ ] `vorgang_credits`: Konto, Monat, Verbrauch; `unlocked_leads` dauerhaft
- [ ] RLS: Ebene-B-Tabellen auf `profile_id`, **keine** kontoweite Sichtbarkeit (§7.2)
- [ ] `user_id` auf allen nutzergebundenen Tabellen (§6, linke Spalte)

Logik:

- [ ] Vorgangs-Auslöser: erstes Öffnen von Unterlagen **oder** Bewertung je Lead, einmalig
- [ ] Firmenprofile im Lead-Kontext verbrauchen kein Kontingent; einzeln aufgerufene schon
- [ ] Testphase-Ablauf → automatischer Übergang auf Free, Ankündigung bei T−7
- [ ] Gating je Bereich/Tab nach §3, Darstellung nach §4.1
- [ ] Sitzungsbegrenzung: 2 je Sitzplatz, Verdrängung ältester Sitzung
- [ ] Sharing-Signale nach §8.3 erfassen, **keine** automatische Sperre
- [ ] Keine Profilobergrenze auf bezahlten Stufen; Free und Testphase auf 1 Profil begrenzen

Abrechnung:

- [ ] Zwei Achsen, drei Rechnungszeilen: Paket · weitere Nutzer · weitere Unternehmensprofile — die beiden Erweiterungszeilen mit demselben Einzelpreis, technisch ein Preisobjekt mit Menge
- [ ] Jahrespreis = 10,25 × Monatspreis, aufgerundet auf 9er-Endung
- [ ] Founding-Preis nur auf die Paketposition
- [ ] SEPA als Voreinstellung, Karte als Alternative
- [ ] Proration bei jeder Erweiterungsänderung unterjährig, gleiche Logik für Nutzer und Profile

Nicht bauen in V1:

- [ ] Vergabestellenseite (§12) — außer `profile_type`
- [ ] Erfolgsprämie, Prämien-Auslöser, `win_reported` als Abrechnungsereignis
- [ ] Geräte-Registrierung, IP-Freigaben, MFA als Strafmaßnahme (§8.4)

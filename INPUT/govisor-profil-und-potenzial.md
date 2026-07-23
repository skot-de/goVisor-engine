# goVisor — Bereich „Profil & Potenzial"

**Zweck des Dokuments:** Fachliche Skizze für einen neuen Produktbereich, zur Prüfung der
Umsetzbarkeit durch Claude Code. Enthält alle Kennzahlen, die aus den bisherigen Design-Runden
bekannt sind, jeweils mit vermuteter Quelle, bekannter Abdeckung und Ehrlichkeits-Vorbehalt.

**Status:** Entwurf. Noch nicht gebaut. Kennzahlen mit ⚠️ brauchen eine Machbarkeits-Antwort,
bevor sie ins Design gehen.

---

## 1 · Warum dieser Bereich

Bisher beantwortet goVisor: *Was passiert im Markt?* — Leads, Vergabestellen, Regionen.

Was fehlt: *Wer sind wir in diesem Markt?* Das ist die Frage, die ein Kunde **nicht selbst
beantworten kann**, weil ihm die Vergleichsgröße fehlt. Sein eigener Umsatz steht im CRM.
Sein Anteil am ausgeschriebenen Volumen steht nirgends.

**Der Kern des Mehrwerts** ist der Potenzial-Teil (Abschnitt 4): Welche Vergaben haben unsere
**bestehenden Kunden** in **unserem Feld** ausgeschrieben, bei denen wir nicht dabei waren?
Das ist Cross-Selling in bestehende Beziehungen — und die eine Auswertung, die kein CRM liefert.

**Wichtig:** Diese Auswertung braucht **keine Vertragskette** (die ist nur zu ~35 % sicher).
Sie braucht nur: Auftraggeber × CPV × „haben wir gewonnen oder nicht". Das ist belastbar.

### Nebeneffekt: Bestand-Pflege bekommt einen echten Grund
Bisher war die Aufforderung „bestätige deine Verträge" faktisch eine Bitte, die Entity-Resolution
zu reparieren. Neuer Handel: **Je vollständiger euer Bestand, desto genauer euer Profil und desto
mehr ungenutztes Potenzial finden wir bei euren eigenen Kunden.** Zwei Minuten Pflege gegen eine
Liste verpasster Gelegenheiten.

---

## 2 · Teil 1 — Fußabdruck („Wer bin ich?")

Beschreibt das Unternehmen aus TED-Sicht. Rein deskriptiv, keine Wertung.

| Kennzahl | Quelle (vermutet) | Abdeckung | Vorbehalt |
|---|---|---|---|
| Firmenname + Auflösungsweg | `entity_identity`, Onboarding-Match | 81 % belegt (HR/nationalId), 19 % nur Name | Match-Weg steuert die Verlässlichkeit des **ganzen Bereichs** |
| Gewonnene Vergaben gesamt | eigene Siege via Entity-ID | — | bei Namens-Match als Vorschlag kennzeichnen |
| Aktiv seit / letzte Vergabe | min/max Zuschlagsdatum | — | — |
| Laufende Verträge | kuratierter Bestand (Nutzer-bestätigt) | — | Nutzer-Eingabe, nicht Messung → eigene Herkunfts-Kategorie |
| Verschiedene Auftraggeber | distinct buyer über eigene Siege | — | Konzern-Töchter über `entity_identity` zusammenfassen (19 % der Entitäten gruppiert) |
| Bespielte CPV-Bereiche | Branchen-Bündel aus Gold Layer | — | dieselbe Bündelung wie beim Käufer-Profil verwenden |
| Bespielte Regionen | `market_nuts3` der eigenen Siege | 91 % NUTS-3-genau | **Leistungsort**, nicht Firmensitz — sonst 18,3 % falsch |
| Vertragsarten-Mix | Rahmen / Einmal / wiederkehrend | — | — |
| Typischer Auftragswert (Median) | `median_award_eur` analog | ~65 % mit Wert | Median statt Summe — robuster gegen fehlende Werte |
| Bekanntes eigenes Volumen | Σ eigener Siege mit Wert | ~65 % | ⚠️ **immer als Untergrenze** mit Coverage-Flag |
| Fragmentierungs-Warnung | `entity_identity` Fragmentierung 4,9 % | — | „bei etwa jedem 20. Namen verteilen sich Siege auf mehrere Entitäten" |

### Darstellung
- Ein Vergabe-Profil-Ring wie beim Käufer (CPV-Mix nach **Anzahl**, nicht Wert)
- Karte: Regionen, in denen wir gewonnen haben
- Zeitverlauf: Siege pro Jahr

### Ehrlichkeit
Der **Umsatz gehört nicht groß herausgestellt** — den kennt der Kunde besser als wir, und unsere
Zahl ist wegen der Wert-Lücke sogar schlechter. Wertvoll wird er erst als Verhältnis (Teil 2).

---

## 3 · Teil 2 — Position („Wie stehe ich da?")

Setzt den Fußabdruck ins Verhältnis zum Markt. Hier entsteht der Erkenntniswert.

| Kennzahl | Rechenweg | Vorbehalt |
|---|---|---|
| **Marktanteil je CPV-Bereich (nach Anzahl)** | eigene Siege ÷ alle Vergaben im CPV × Region | ✅ belastbar — Anzahl ist vollständig |
| Marktanteil je CPV (nach Wert) | eigenes Volumen ÷ ausgeschriebenes Volumen | ⚠️ beide Seiten unvollständig (65 % / 12–37 %) → **eher weglassen oder stark flaggen** |
| Rang unter den Anbietern im Bereich | Position in der Siegerliste je CPV | ✅ analog `n_distinct_winners` / `top3_share` |
| Konzentration in meinem Bereich | `top3_share`, `concentration` je CPV+Region | ✅ vorhanden |
| Wettbewerber-Überschneidung | wer gewinnt bei **meinen** Kunden sonst | ✅ `buyer_contractor_history` (266k) |
| Regionale Über-/Unterrepräsentation | eigener Anteil je Region vs. Marktanteil gesamt | ✅ mit `auftraege_je_1000_ew` normalisierbar |
| Ø Bieterzahl bei meinen Siegen | `num_tenders` bei eigenen Zuschlägen | ⚠️ bei f02 zu 0 % gefüllt (7.962 Leads) |
| **Gewinnquote (Win-Rate)** | Siege ÷ Teilnahmen | ❌ **nicht berechenbar** — siehe unten |

### ❌ Kritische Lücke: Gewinnquote
TED veröffentlicht **Gewinner, nicht Verlierer**. Wir wissen bei jeder Vergabe, *wie viele* geboten
haben (`num_tenders`), aber nicht *wer*. Damit ist die naheliegendste Profil-Kennzahl —
„ihr gewinnt 1 von 4 Ausschreibungen" — **strukturell nicht ableitbar**.

Optionen:
1. **Weglassen** und ehrlich benennen, warum (bevorzugt)
2. Nutzer trägt eigene Teilnahmen nach → wird zum CRM, hoher Pflegeaufwand
3. Proxy „Anteil an allen Vergaben im Feld" statt Gewinnquote — misst etwas anderes, ist aber ehrlich

**Frage an Claude Code:** Gibt es *irgendeine* Spur eingereichter, aber verlorener Angebote?
(Rügen, Nachprüfungsverfahren, Vergabekammer-Entscheidungen, `award_criteria`-Details?)

---

## 4 · Teil 3 — Potenzial („Wo ist ungenutzter Raum?") — **Kernstück**

### 4A · Bestandskunden-Potenzial ⭐ höchster Wert
> „Bei Landkreis X habt ihr 1 von 7 Vergaben in eurem Feld gewonnen — hier sind die anderen 6."

| Feld | Rechenweg | Machbarkeit |
|---|---|---|
| Kunden-Durchdringung | je (buyer × CPV-Bündel): eigene Siege ÷ alle Vergaben | ✅ keine Vertragskette nötig |
| Verpasste Vergaben (historisch) | Vergaben des Kunden im Feld ohne eigenen Sieg | ✅ |
| **Aktuell offen beim Bestandskunden** | offene Ausschreibungen, buyer ∈ meine Kunden, CPV ∈ mein Feld | ✅ reiner Filter — **das ist die Handlungsliste** |
| Vorinformationen beim Bestandskunden | Phase = Ankündigung, gleicher Filter | ✅ Frühindikator |
| Wer stattdessen gewonnen hat | `buyer_contractor_history` | ✅ |
| Kunden-Aktivität / Trend | `total_awards`, `awards_per_year_recent` | ✅ |

**Ansprache-Argument fürs UI:** „Diese Vergabestelle kennt euch bereits — ihr habt dort seit
2021 einen laufenden Vertrag."

### 4B · Benachbarte CPV-Bereiche
> „Eure Kunden schreiben auch X aus — dort habt ihr noch nie geboten."

| Feld | Rechenweg | Machbarkeit |
|---|---|---|
| CPV-Bereiche meiner Kunden, in denen ich nie gewonnen habe | Differenzmenge über buyer × CPV | ✅ |
| Volumen/Anzahl in diesen Bereichen | Aggregation | ✅ (Anzahl), ⚠️ (Wert) |
| Wettbewerbslage dort | `single_bidder_rate`, `top3_share`, `concentration` | ✅ |
| CPV-Nachbarschaft (fachliche Nähe) | ⚠️ **offen** — siehe Fragen | ⚠️ |

**Frage an Claude Code:** Gibt es eine Ähnlichkeits-Struktur zwischen CPV-Bündeln? Ohne sie
ist „benachbart" nur „derselbe Kunde, anderes Feld" — was als erste Stufe reicht, aber die
Empfehlung „passt fachlich zu euch" nicht trägt.

### 4C · Geografische Ausdehnung
> „In Region Y wird viel in eurem Feld ausgeschrieben, ihr seid dort nicht aktiv."

| Feld | Quelle | Abdeckung |
|---|---|---|
| Nachfrage je Region in meinem CPV | `region_kpi` × CPV-Filter, über `market_nuts3` | 91 % |
| Eigene Präsenz je Region | eigene Siege je NUTS-3 | — |
| Normalisierung | `auftraege_je_1000_ew` (Median 0,40) | — |
| Wettbewerbslage der Region | `single_bidder_rate` (regional) | — |
| Fiskalische Lage | `investition_je_kopf_eur` (Median 642 €), `schulden_je_kopf_eur` (Median 1.276 €) | ~320/422, **Stand 2023** |
| Vorlaufindikator | `genehmigungen_gesamt` (Median 135) | 422/422 ✅ vollständig |

⚠️ **Anbieterdichte (`auftraege_je_betrieb`) nicht als Chancen-Argument verwenden.** Gemessen:
Korrelation zur Single-Bieter-Quote r = 0,099, über alle Quartile flach. Begründung: Baufirmen
arbeiten überregional. Außerdem nur für **Baugewerbe** vorhanden (322/422) — für IT-Kunden leer.

⚠️ ~100 der 422 Regionen ohne Kontext (gleichnamige Stadt/Landkreis) → sichtbarer Leerzustand.

### 4D · Ähnliche Auftraggeber
> „Vergabestellen wie eure bestehenden Kunden, bei denen ihr noch nicht seid."

| Feld | Rechenweg | Machbarkeit |
|---|---|---|
| Ähnlichkeit von Vergabestellen | über CPV-Mix, Größe, Typ, Region | ⚠️ **offen** |
| Erreichbarkeit | `concentration` — oligopol = schwer, fragmentiert = offen | ✅ vorhanden |
| Aktivität | `total_awards`, `awards_per_year_recent` | ✅ |
| Einstiegs-Chance | `single_bidder_rate`, `avg_bidders`, `retention_rate` | ✅ |

**Frage an Claude Code:** Ist ein Käufer-Ähnlichkeitsmaß aus `buyer_profile` bildbar
(CPV-Mix-Vektor + Größenklasse + Typ)? Wenn ja, wäre 4D die stärkste Akquise-Empfehlung im Produkt.

---

## 5 · Bekannte Datenlage (Stand aus den Design-Runden)

### Entity-Resolution
| Weg | Firmen | Siege | Verlässlichkeit |
|---|---|---|---|
| Handelsregister exakt | 40.868 | 238.562 | belegt |
| TED-nationalId | 30.759 | 65.713 | belegt |
| nur Name | 26.171 | 53.122 | ⚠️ geraten |
| nicht aufgelöst | 10.034 | 17.301 | ⚠️ |

- **81 %** aller Siege an belegter Firmen-ID · Fragmentierung **4,9 %**
- `entity_identity`: 19 % der Entitäten einer Konzerngruppe zugeordnet

### Vergabe-Grunddaten
- ~96 % der Vergaben mit publiziertem Gewinner
- ~65 % mit echtem Auftragswert · ~35 % ohne
- Wert-Schätzung trifft Band ~42 % → **nicht abrechnungstauglich**
- Ausschreibung → Zuschlag verknüpfbar ~51 % · Median 87 Tage
- Vertragskette sicher verkettbar ~35 % → **kein Nachfolge-Versprechen**

### Leistungsort (Fix)
- `market_nuts3`, `market_region_name`, `market_region_ok`
- 73.733 Leads mit Leistungsort (94 %), NUTS-3-genau 70.837 (**91 %**)
- 13.481 (18,3 %) hätten über den Käufersitz die falsche Region bekommen

### Score
- `displaceability`: empirische Raten-Tabelle (Vertragsart × Branche × Bieterzahl, mit Backoff)
- Backtest 5-fach CV, 17.934 Zeilen: **AUC 0,767** (Stand 2026-07-23; vorher 0,806 — Drift durch
  neue Datenbasis), Brier-Lift +19,1 %, ECE 0,016
- ⚠️ bei offenen Ausschreibungen (f02) ist `num_tenders` zu **0 %** gefüllt → 7.962 Leads mit
  blinder Bieterzahl-Achse, Backoff auf „unbekannt"

### Datenstände
| Block | Stand |
|---|---|
| Leads / Fristen | tagesaktuell |
| Wikidata (Website, Einwohner) | live |
| **Destatis-Kontextzahlen** | **2023** — Label am Feld Pflicht |
| Handelsregister-Firmografie | 2017–2019 — mit Warnhinweis |

---

## 6 · Durchgängige Ehrlichkeits-Regeln

1. **Volumen immer als Untergrenze**, mit Coverage-Prozent direkt an der Zahl — nie in einer Fußnote.
2. **Anteile nach Anzahl, nicht nach Wert.** Bei 12–65 % Wert-Abdeckung wäre eine Euro-Quote erfunden.
3. **Gewinnquote existiert nicht** — nicht durch einen Proxy ersetzen, der so aussieht.
4. **Jede Kennzahl braucht eine Bezugsgröße** (Median über alle Regionen/Käufer). Ohne Vergleich
   ist eine Regionszahl bedeutungslos.
5. **Fünf Herkunfts-Kategorien** statt vier: gemessen · geschätzt · unsicher · unbekannt ·
   **amtlich mit Stichtag** (Destatis).
6. **Nutzer-Eingaben sind eine eigene Kategorie** — der kuratierte Bestand ist bestätigt, nicht gemessen.
7. **Entity-Match-Weg gated den ganzen Bereich:** bei Namens-Match (19 %) alles als Vorschlag
   kennzeichnen, nicht als Fakt.
8. **Leere Zustände begründen**, nicht verschweigen — „kein Kontext, weil Stadt und Landkreis
   gleichnamig" statt stiller Lücke.

---

## 7 · Verortung im Produkt

**Eigener Bereich in der Modus-Leiste links**, nicht als Tab im Lead-Detail — denn er ist an das
**Unternehmen** gebunden, nicht an eine Ausschreibung. Kein Kaltstart-Problem: Das Profil ist
immer das eigene.

Vorschlag Struktur:
```
Profil
├── Fußabdruck      (wer sind wir)
├── Position        (wie stehen wir da)
└── Potenzial       (wo ist Raum)  ← Einstieg, weil handlungsnah
```

**Einstiegspunkt sollte „Potenzial" sein**, nicht „Fußabdruck" — der Kunde will nicht sein
Spiegelbild, er will die Liste verpasster Gelegenheiten.

### Querverweise
- Potenzial-Eintrag → Lead-Detail (der offenen Ausschreibung)
- Kunde im Potenzial → Vergabestellen-Tab
- Region im Potenzial → Markt-Tab
- Bestand-Pflege → begründet aus dem Profil heraus

### Preismodell
- **Pro**, wie Vergabestelle und Markt: eigene Daten, kein Abruf-Kostenfaktor, unbegrenzt
- **Kein eigenes Kontingent** — es ist eine Unternehmens-Sicht, nicht pro Lead
- Free-Zustand: Struktur sichtbar, konkrete Werte verwischt (wie Vergabestelle/Markt)
- Potenzial-Liste ist ein **starkes Upgrade-Argument**: Anzahl sichtbar
  („7 verpasste Vergaben bei euren Kunden"), Inhalte verwischt

---

## 8 · Offene Fragen an Claude Code

1. **Eigene Siege zuverlässig ermittelbar?** Entity-ID → alle Zuschläge, inkl. Konzern-Töchter
   über `entity_identity`. Wie hoch ist die Trefferquote in der Praxis?
2. **Gibt es irgendeine Spur verlorener Angebote?** (Nachprüfungsverfahren, Rügen,
   Vergabekammer, Zuschlagskriterien-Details) — entscheidet über die Gewinnquote.
3. **CPV-Nachbarschaft:** existiert oder bildbar? Ohne sie ist 4B nur „gleicher Kunde,
   anderes Feld".
4. **Käufer-Ähnlichkeitsmaß** aus `buyer_profile` bildbar? Entscheidet über 4D.
5. **Kunden-Durchdringung** (4A): Ist `buyer × CPV-Bündel × eigene Siege` performant über
   den ganzen Bestand rechenbar, oder braucht es eine vorberechnete Tabelle?
6. **Offene Ausschreibungen bei Bestandskunden:** Wie viele Leads betrifft das typischerweise
   pro Kunde? (Relevanz-Check: lohnt die Liste?)
7. **Marktanteil je CPV:** Ist die Grundgesamtheit „alle Vergaben im CPV × Region" sauber
   abgrenzbar, oder verzerren Rahmenverträge/Lose die Zählung?
8. **Zeitliche Abgrenzung:** Welcher Zeitraum ist für „unsere Kunden" sinnvoll — letzte 3 Jahre,
   5 Jahre, laufende Verträge? Beeinflusst alle Potenzial-Rechnungen.

---

## 9 · Was ich bewusst weglassen würde

| Kandidat | Grund |
|---|---|
| Absoluter Eigenumsatz groß dargestellt | kennt der Kunde besser; unsere Zahl ist schlechter |
| Gewinnquote | strukturell nicht ableitbar (keine Verliererdaten) |
| Marktanteil nach Wert | beide Seiten zu lückenhaft |
| `intensitaet_pct` | 132/422 Abdeckung, Werte >100 % erklärungsbedürftig |
| Anbieterdichte als Chancen-Argument | gemessen widerlegt (r = 0,099) |
| Handelsregister-Firmografie | Stand 2018 neben tagesaktuellen Leads |
| Nachfolge-Vorhersage („das ist die Neuausschreibung eures Vertrags") | Kette nur 35 % sicher — stattdessen: „diese Stelle hat etwas Neues in eurem Feld" |

---

## 10 · Wunschliste — Kennzahlen, die wir (noch) nicht haben

Sortiert nach vermuteter Machbarkeit. Die ersten beiden Gruppen sind realistisch genug,
dass sie die Roadmap verschieben könnten.

### 10.1 · Vermutlich schon in TED — bitte prüfen ⭐

Diese Felder werden in EU-Bekanntmachungen häufig mitgeliefert. Wenn sie da sind, sind sie
der billigste große Sprung im Produkt.

| Wunsch | Was es ermöglicht | Vermutete Quelle |
|---|---|---|
| **Zuschlagskriterien mit Gewichtung** | „Diese Stelle gewichtet Preis zu 70 %, Qualität zu 30 %" → sagt einem Bieter, **ob er über Preis oder Konzept gewinnen muss**. Das ist die praktischste Einzelinformation für die Angebotsstrategie überhaupt. | `award_criteria` in F02/F03 |
| **Losaufteilung** | Anzahl Lose, Losgrößen, ob Mehrfachvergabe zulässig. Kleine Lose = für Mittelständler zugänglich; ein Großlos = nur für Konzerne. Ändert die Relevanz-Bewertung erheblich. | Lot-Struktur in TED |
| **Schätzwert vs. Zuschlagswert** | Delta zwischen veröffentlichtem Schätzwert und tatsächlichem Zuschlag → **Preisniveau je Vergabestelle**: „hier gewinnt man typisch 8 % unter Schätzwert". Wäre die erste echte Preisintelligenz. | beide Felder existieren teilweise |
| **Vertragslaufzeit + Optionsjahre** | Präzises Auslaufdatum statt Schätzung, und ob Verlängerungsoptionen bestehen — die erklären, warum eine erwartete Neuausschreibung ausbleibt. | `duration`, `renewal` |
| **Angebotsfrist-Länge** | Tage zwischen Veröffentlichung und Frist. Kurze Fristen bevorzugen strukturell den Amtsinhaber → eigenständiges Chancen-Signal. | berechenbar aus vorhandenen Daten |
| **Verfahrensart im Detail** | Offen / nicht-offen / Verhandlung / wettbewerblicher Dialog / Direktvergabe. Verhandlungsverfahren = Beziehung zählt mehr als Preis. | vorhanden? |
| **Bietergemeinschaften** | Wer bietet mit wem? Zeigt Partner-Netzwerke — und wer sich zusammentut, um an große Lose zu kommen. | Gewinner-Feld nennt teils Konsortien |
| **Vergabeplattform der Stelle** | Auf welcher Plattform wird abgewickelt. Registrierung dauert — wer das vorher weiß, verliert keine Frist. | Bekanntmachungs-Metadaten |

### 10.2 · Externe Quellen, realistisch beschaffbar

| Wunsch | Was es ermöglicht | Quelle |
|---|---|---|
| **Präqualifikationsverzeichnisse** | CPV-genauer Anbieterpool statt „alle Baubetriebe im Kreis". Genau der Ex-ante-Prädiktor, der bei offenen Ausschreibungen fehlt (7.962 Leads mit blinder Bieterzahl). | PQ-VOB, amtliche Verzeichnisse |
| **Haushaltspläne der Vergabestelle** | Echtes Budget **dieser Behörde** statt Kreis-Investitionen — behebt die Einschränkung, die wir aktuell umgehen müssen. | kommunale Haushaltspläne (PDF, offen) |
| **Ratsbeschlüsse / Beschlussvorlagen** | Investitionsentscheidungen **bevor** ausgeschrieben wird. Der früheste denkbare Indikator — Monate vor jeder Vorinformation. | kommunale Ratsinformationssysteme |
| **Förderprogramme** | Programme lösen Ausschreibungswellen aus (DigitalPakt → IT, Konjunkturpakete → Bau). „In eurem Feld läuft ein Förderprogramm mit Mittelabruf bis 2027." | Bund/EU-Förderdatenbanken |
| **Jahresabschlüsse der Wettbewerber** | Umsatz und Mitarbeiterzahl → Kapazitätseinschätzung: „Dieser Wettbewerber ist zu klein für dieses Volumen." Auch Bonität. | Bundesanzeiger |
| **Nachprüfungsverfahren / Rügen** | Welche Stellen werden häufig angegriffen → Verfahrensqualität und Risiko. **Und:** Nachprüfungsakten nennen teils unterlegene Bieter — der einzige mir denkbare Weg zu Verliererdaten. | Vergabekammern |
| **Personelle Kontinuität** | Gleiche Ansprechpartner über Jahre → Beziehungswert. Wechsel im Vergabereferat = Chance für Neue. | Kontaktfelder über Zeit |

### 10.3 · Abgeleitet — clever, aber Eigenleistung

| Wunsch | Was es ermöglicht | Ansatz |
|---|---|---|
| **Textähnlichkeit alte ↔ neue Ausschreibung** ⭐ | **Löst das Vertragsketten-Problem eleganter als die Kette.** Behörden kopieren Leistungsbeschreibungen. Hohe Textähnlichkeit zwischen einer neuen Ausschreibung und einer alten desselben Käufers ist ein starkes Nachfolge-Signal — ohne auf Titel-Rekonstruktion angewiesen zu sein. Könnte die 35 % deutlich heben. | Embedding/Shingling über Leistungsbeschreibungen |
| **Zuschnitt auf den Amtsinhaber** ⭐ | Erkennen, ob Anforderungen so eng gefasst sind, dass praktisch nur der Bestandslieferant passt — ungewöhnliche Zertifikatskombinationen, sehr spezifische Referenzanforderungen, Produktnennungen. Ergebnis: **„Diese Ausschreibung ist auf den Amtsinhaber zugeschnitten — Chance gering."** Das wäre eine der ehrlichsten und wertvollsten Warnungen im Produkt: Sie rät vom Bieten ab. | NLP auf Anforderungstexten + Vergleich mit Branchenüblichkeit |
| **Wiederkehr-Rhythmus je Käufer** | Manche Stellen schreiben in festen Zyklen aus. Aus der Historie ableitbar: „Diese Stelle vergibt Rahmenverträge alle 4 Jahre, das nächste Fenster ist Q2/2027." | Zeitreihenanalyse je buyer × CPV |
| **Anforderungs-Profil des Kunden** | Welche Zertifikate/Referenzen fordert unser Kunde typischerweise → Lückenanalyse gegen das eigene Portfolio, über den Einzelfall hinaus. | Aggregation der Anforderungs-Extraktion (F02, V2-Ticket) |
| **Verdrängungs-Bilanz** | Wen haben wir verdrängt, wer hat uns verdrängt — über alle Verträge. Braucht die Kette, wäre aber mit Textähnlichkeit erreichbar. | abhängig von Textähnlichkeit |
| **Saisonalität** | Wann im Jahr wird in unserem Feld ausgeschrieben → Kapazitätsplanung im Bid-Team. | einfache Aggregation |

### 10.4 · Schön, aber unrealistisch

| Wunsch | Warum schwierig |
|---|---|
| Vollständige Bieterlisten | Wird systematisch nicht veröffentlicht. Nur Bruchstücke über Nachprüfungsverfahren. |
| Angebotspreise der Unterlegenen | Faktisch nie öffentlich. |
| Interne Bewertungsmatrizen | Nicht veröffentlichungspflichtig. |
| Unterschwellige Vergaben vollständig | DÖE deckt einen Teil; unterhalb der Schwellen gilt keine EU-Publizität. |
| Subunternehmer-Ketten | Nur vereinzelt in Bekanntmachungen. |
| Zufriedenheit des Auftraggebers | Existiert nirgends öffentlich — wäre aber der beste Prädiktor für Vertragstreue. |

### Meine drei Favoriten, wenn nur wenig geht

1. **Zuschlagskriterien-Gewichtung** — vermutlich schon vorhanden, sofort handlungsrelevant,
   verändert die Angebotsstrategie jedes Kunden.
2. **Textähnlichkeit für Nachfolge-Erkennung** — hebt eine bekannte Schwäche (35 %) mit
   Eigenleistung statt Datenzukauf.
3. **Zuschnitt-Erkennung auf den Amtsinhaber** — das stärkste denkbare Vertrauens-Signal,
   weil das Produkt damit auch mal sagt: *hier lohnt sich der Aufwand nicht.*

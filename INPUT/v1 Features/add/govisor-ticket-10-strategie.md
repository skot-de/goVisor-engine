# Feature #10: Strategie

**Produkt:** goVisor
**Version:** V1.5
**Status:** Draft
**Erstellt:** 2026-07-26
**Gate:** Pro (sektionsweise, nicht bereichsweise)

---

## 1. Kontext

Der Lead Explorer beantwortet die operative Frage: *Welche Ausschreibung gewinne ich?*
Der Strategie-Bereich beantwortet die unternehmerische: *Wo investiere ich, worauf verzichte ich, was ist mir verschlossen?*

Zielperson ist nicht der Bid Manager, sondern die Geschäftsführung. Nutzungsfrequenz ist quartalsweise, nicht täglich. Das prägt jede Designentscheidung: keine Handlungsaufforderungen pro Lead, sondern Aggregate mit Zeitachse.

### 1.1 Abgrenzung zum bestehenden Bereich „Potenzial"

**Entscheidung: „Potenzial" wird umbenannt zu „Strategie" und ausgebaut.** Kein zweiter Rail-Eintrag.

Begründung: `Chancen` ist bereits heute strategisch (verpasste Vergaben bei Bestandskunden, Nachbarfelder, einstiegsfreundliche Lose), `Position` ohnehin. Ein paralleler Bereich würde diese Inhalte duplizieren.

Der bestehende Tab `Chancen` wird aufgelöst:

| Bisheriger Block in `Chancen` | Neues Zuhause |
|---|---|
| Bei euren Kunden | Vergabestellen |
| In eurem Markt | Vergabestellen |
| In benachbarten Feldern | Felder |
| Einstiegsfreundlich | Felder |

`Position` und `Profil` bleiben inhaltlich unverändert bestehen.

### 1.2 Voraussetzung: Entity-Auflösung

**Der gesamte Bereich Wettbewerb steht und fällt mit `entity_identity`.** Wenn „Bechtle AG", „Bechtle GmbH & Co. KG Regensburg" und „BECHTLE AG" als drei Anbieter in der Datenbank liegen, sind alle Marktanteils-, Konzentrations- und Zuschlagsanteilszahlen falsch — nicht ungenau, sondern falsch.

Vor Implementierung der Sektionen `Wettbewerb`, `Vergabestellen` und `Position` ist zu klären:

1. Wie hoch ist die aktuelle Auflösungsquote auf `winner_entity_id`?
2. Werden Konzernstrukturen (Mutter/Tochter) zusammengefasst oder getrennt geführt?
3. Wie werden Bietergemeinschaften behandelt — als eigene Entität oder auf die Mitglieder aufgeteilt?

Zu 3 ist die Entscheidung produktseitig zu treffen. Empfehlung: Bietergemeinschaft zählt für **jedes** Mitglied als Zuschlag, wird aber als solche gekennzeichnet. Sonst verschwinden KMU aus der Statistik, die genau über diesen Weg an große Aufträge kommen.

---

## 2. Sektionsstruktur

Acht Sektionen in zwei Gruppen. Darstellung als vertikale Abschnittsnavigation (bestehende `.ananav`), **nicht** als weitere Tab-Ebene.

| Gruppe | Sektion | Kernfrage |
|---|---|---|
| **Markt** | Pipeline | Was kommt in 12/24/36 Monaten? |
| | Felder | Wo ist Platz, wo ist es eng? |
| | Vergabestellen | Wo lohnt Beziehungsaufbau? |
| | Wettbewerb | Wer holt was, wer hält was? |
| **Wir** | Position | Wo stehen wir? |
| | Fähigkeiten | Was blockiert uns? |
| | Bindung | Was ist uns verschlossen? |
| | Profil | Wer sind wir? |

---

## 3. Provenance-Regeln

Die Regel „lieber unbekannt zeigen als falsch" gilt hier verschärft, weil Aggregate ihre Unsicherheit verstecken. Eine Wechselquote aus zwei Fällen als „50 %" auszuweisen ist die exakte Form von Falschpräzision, die das Produkt vermeidet.

### 3.1 Fallzahl-Schwellen

Gilt für **jeden** quotenbasierten KPI (Wechselquote, KMU-Anteil, Preisentscheidungen, Neuzugänge, Aufhebungen, Zuschlagsanteil).

| Fallzahl `n` | Darstellung | Herkunft |
|---|---|---|
| `n >= 8` | Prozentwert | `echt` — unmarkiert |
| `3 <= n <= 7` | Prozentwert + „aus n Vergaben" | `duenn` — Punkt |
| `1 <= n <= 2` | Absolutwert („2 von 3"), **keine Prozentzahl** | `duenn` — Punkt |
| `n = 0` | „—" in `--ink-300` | `unbekannt` |

### 3.2 Neuer Herkunfts-Zustand `duenn`

Die bestehende Grammatik kennt `echt`, `schaetz`, `unsicher`, `unbekannt`, `na`. Für Aggregate fehlt ein Zustand: *gemessen, aber auf zu wenigen Fällen*. Das ist weder geschätzt (nichts wurde abgeleitet) noch unsicher (die Daten widersprechen sich nicht).

Vorschlag zur Ergänzung von `SRC_TEXT`:

```javascript
duenn: 'Dünn · gemessen, aber wenige Fälle'
```

Punktfarbe: `--ink-300` wie `schaetz`, aber eigener Tooltip. **Offene Entscheidung** — siehe Abschnitt 9.

### 3.3 Volumen

Der bestehende Split gilt unverändert und wird in der Pipeline **explizit ausgewiesen**, nicht nur im Tooltip:

| Anteil | Bedeutung |
|---|---|
| ~65 % | Auftragswert publiziert → `echt` |
| ~35 % | kein Wert publiziert → `unbekannt`, **nicht** schätzen |

Für die Pipeline-Summe heißt das: es gibt keine Gesamtsumme, sondern drei Summen. Ein Balken pro Quartal wird gestapelt dargestellt, nicht addiert.

### 3.4 Vertragsende

| Quelle | Anteil | Herkunft |
|---|---|---|
| `PlannedPeriod.EndDate` | ~33 % | `echt` |
| Startdatum + Median-Laufzeit des CPV-Bündels | Rest | `schaetz` |
| weder noch | — | `unbekannt`, fällt aus der Pipeline |

---

## 4. Aggregat-Tabellen

Alle Sektionen lesen aus vorberechneten Aggregaten, nicht aus Live-Queries auf die Rohdaten. Nächtlicher Rebuild.

### 4.1 `agg_buyer_profile`

Pro Vergabestelle, rollierend 36 Monate.

| Feld | Typ | Quelle / Formel |
|---|---|---|
| `buyer_entity_id` | uuid | PK |
| `authority_type` | string | `AA_AUTHORITY_TYPE` (100 %) |
| `main_activity` | string | `MA_MAIN_ACTIVITIES` (99,3 %) / eForms `ActivityTypeCode` |
| `vergaben_36m` | int | Anzahl Zuschläge |
| `volumen_echt_36m` | numeric | Summe publizierter Werte |
| `volumen_unbekannt_anzahl` | int | Vergaben ohne Wert |
| `preisquote` | numeric | `AC_AWARD_CRIT = 'lowest price'` / total |
| `preisquote_n` | int | Nenner für Schwellenregel |
| `bieter_median` | numeric | Median `ReceivedSubmissionsStatistics` je Los |
| `bieter_n` | int | Lose mit Bieterangabe |
| `kmu_anteil` | numeric | `CompanySizeCode IN (micro,small,medium)` / Zuschläge mit Angabe |
| `kmu_n` | int | Zuschläge mit Größenangabe |
| `wechselquote` | numeric | siehe 4.5 |
| `wechsel_n` | int | verkettete Nachfolgepaare |
| `neuzugang_pro_jahr` | numeric | Anbieter mit Erstzuschlag / Beobachtungsjahre |
| `aufhebungsquote` | numeric | `TenderResultCode = 'clos-nw'` / Lose |
| `konzentration_top1` | numeric | Zuschläge des stärksten Anbieters / total |
| `buergschaft_quote` | numeric | Verfahren mit `RequiredFinancialGuarantee` |
| `lose_median` | numeric | Median Lose je Vergabe |
| `rahmen_anteil` | numeric | `ContractingSystemTypeCode` gesetzt / total |
| `regulatory_mix` | jsonb | Verteilung VOB/VgV/UVgO/SektVO |

### 4.2 `agg_supplier_profile`

Pro Anbieter, rollierend 36 Monate. Struktur analog, zusätzlich:

| Feld | Typ | Bedeutung |
|---|---|---|
| `supplier_entity_id` | uuid | PK |
| `zuschlaege_12m` / `_24m` / `_36m` | int | Zeitfenster für Trend |
| `trend_yoy` | numeric | Zuschläge 12M vs. Vorjahreszeitraum |
| `volumen_echt_24m` | numeric | |
| `stellen_anzahl` | int | distinct Vergabestellen |
| `laufende_vertraege` | int | Vertragsende in der Zukunft |
| `laufendes_volumen` | numeric | nur `echt` |
| `cpv_mix` | jsonb | Verteilung über CPV-Bündel |
| `region_mix` | jsonb | Verteilung über NUTS |
| `groesse` | string | `CompanySizeCode`, häufigster Wert |
| `sub_nutzung` | numeric | `SubcontractingTerm` gesetzt / Zuschläge |
| `erstzuschlag_datum` | date | für „Neuzugang" |

### 4.3 `agg_buyer_supplier` (die Matrix)

Die bipartite Kante. Trägt beide Sichten.

| Feld | Typ | Bedeutung |
|---|---|---|
| `buyer_entity_id` | uuid | PK-Teil |
| `supplier_entity_id` | uuid | PK-Teil |
| `zuschlaege` | int | Zuschläge dieses Anbieters bei dieser Stelle |
| `volumen_echt` | numeric | |
| `anteil_bei_stelle` | numeric | `zuschlaege` / `agg_buyer_profile.vergaben_36m` |
| `anteil_marktdurchschnitt` | numeric | 1 / Anzahl aktiver Anbieter bei der Stelle |
| `ueberperformance` | numeric | `anteil_bei_stelle` − `anteil_marktdurchschnitt` |
| `erster_zuschlag` | date | |
| `letzter_zuschlag` | date | |
| `laufende_vertraege` | int | |
| `naechstes_ende` | date | Grundlage für „angreifbar" |

**Wichtig zur Formulierung:** Das Feld heißt `ueberperformance`, nicht `beziehung`. Ein hoher Zuschlagsanteil kann Beziehung, fachliche Passung oder einen Rahmenvertrag bedeuten. Das Produkt weist die Zahl aus und überlässt die Deutung dem Nutzer. „Gute Beziehung zur Vergabestelle" darf im UI nicht als Aussage stehen.

### 4.4 `agg_field`

CPV-Bündel × NUTS-Ebene (1 und 3), rollierend 36 Monate.

| Feld | Typ | Bedeutung |
|---|---|---|
| `cpv_bundle` | string | PK-Teil |
| `nuts_code` | string | PK-Teil |
| `vergaben_12m` / `_24m` / `_36m` | int | Trendbasis |
| `volumen_echt_24m` | numeric | |
| `anbieter_aktiv` | int | distinct Anbieter |
| `bieter_median` | numeric | Wettbewerbsdichte |
| `kmu_anteil` | numeric | |
| `kleinstes_los_median` | numeric | Einstiegshürde |
| `buergschaft_quote` | numeric | Kapitalhürde |
| `nebenangebote_quote` | numeric | `VariantConstraintCode` |
| `bietergemeinschaft_erlaubt_quote` | numeric | `CompanyLegalFormCode` |
| `bindefrist_median` | numeric | `TenderValidityPeriod` — gebundene Kapazität |

### 4.5 Wechselquote — Ableitung

Der einzige nicht-triviale KPI. Basis ist die Nachfolge-Verkettung.

```sql
-- Nachfolgepaare: Vergabe B ist Nachfolger von Vergabe A
-- wenn B via ref_publication_number auf A verweist ODER
-- (gleiche Stelle) AND (gleiches CPV-Bündel) AND
-- (B.start innerhalb ±180 Tage nach A.ende)

WITH paare AS (
  SELECT
    a.buyer_entity_id,
    a.winner_entity_id AS vorher,
    b.winner_entity_id AS nachher
  FROM awards a
  JOIN awards b
    ON b.ref_publication_number = a.publication_number
  WHERE a.winner_entity_id IS NOT NULL
    AND b.winner_entity_id IS NOT NULL
)
SELECT
  buyer_entity_id,
  COUNT(*) AS wechsel_n,
  COUNT(*) FILTER (WHERE vorher <> nachher)::numeric / COUNT(*) AS wechselquote
FROM paare
GROUP BY buyer_entity_id;
```

**Realismus:** Ausschreibung → Zuschlag ist nur zu ~51 % verknüpfbar. Ein Nachfolgepaar braucht zwei intakte Verkettungen. Rechne mit **wenigen belastbaren Fällen pro Stelle** — genau dafür existiert die Schwellenregel aus 3.1.

Die heuristische Verkettung (gleiche Stelle + CPV + Zeitfenster) ist als **Fallback** implementierbar, muss dann aber als `schaetz` markiert werden und darf nicht mit der harten Verkettung in einen Topf.

### 4.6 `agg_pipeline`

Materialisiert je User berechenbar, aber besser generisch: Vertragsenden je CPV-Bündel × NUTS × Quartal, mit Herkunfts-Split.

| Feld | Typ |
|---|---|
| `quartal` | date (Quartalsbeginn) |
| `cpv_bundle` | string |
| `nuts_code` | string |
| `volumen_echt` | numeric |
| `volumen_geschaetzt` | numeric |
| `anzahl_unbekannt` | int |
| `anzahl_gesamt` | int |
| `davon_rahmen_ohne_wettbewerb` | int |

Die User-Sicht ist dann ein Filter über `cpv_bundle IN (profil.schwerpunkte)` und `nuts_code LIKE ANY (profil.regionen)`.

---

## 5. Sektions-Spezifikationen

### 5.1 Pipeline

**Frage:** Was kommt in 12/24/36 Monaten auf uns zu?

**Inhalt**

- Gestapeltes Balkendiagramm je Quartal, drei Segmente: `echt` / `geschätzt` / `unbekannt (Anzahl)`
- Umschalter 12 / 24 / 36 Monate
- Darunter: Tabelle der größten Einzelposten mit Sprung in den Lead Explorer
- Kennzahl „davon in Rahmenvereinbarungen ohne erneuten Wettbewerb" — das ist Volumen, das zwar ausläuft, aber nur für Gelistete abrufbar ist

**Regeln**

- Keine Gesamtsumme über die drei Herkunftsklassen
- Vorinformationen (PIN) werden separat gekennzeichnet, nicht mit Vertragsenden vermischt
- Quartale ohne Datenlage werden leer dargestellt, nicht interpoliert

**Gate:** Free sieht Achse und Balkenform ohne Werte. Pro sieht Zahlen.

---

### 5.2 Felder

**Frage:** Wo ist Platz, wo ist es eng?

**Inhalt**

- Tabelle CPV-Bündel × Region, sortierbar
- Spalten: Volumen 24M, Vergaben/Jahr, Trend 3 Jahre, Ø Bieter, KMU-Anteil, kleinstes Los (Median), Bürgschaftsquote
- Block „Benachbarte Felder" (übernommen aus `Chancen`): Bereiche, die dieselben Anbieter zusätzlich bedienen — abgeleitet aus Ko-Vorkommen im `cpv_mix` der Anbieterprofile
- Block „Einstiegsfreundlich" (übernommen aus `Chancen`): offene Lose mit kleinem Volumen und historisch geringer Bieterzahl

**Regeln**

- Bieterzahl stammt aus entschiedenen Vergaben derselben Stelle — bei laufenden Ausschreibungen hat noch niemand geboten. Dieser Hinweis steht bereits im bestehenden Prototyp und ist zu übernehmen.
- Trend nur bei durchgehender Datenlage über alle drei Jahre, sonst `unbekannt`

**Gate:** Pro.

---

### 5.3 Vergabestellen

**Frage:** Wo lohnt Beziehungsaufbau?

**Inhalt** — Tabelle, eine Zeile je Stelle:

| Spalte | Quelle |
|---|---|
| Vergabestelle | `buyer_entity_id` |
| Typ | `authority_type` |
| Volumen 24M | `volumen_echt_24m` |
| Vergaben/Jahr | `vergaben_36m / 3` |
| Preisentscheidungen | `preisquote` |
| Ø Bieter | `bieter_median` |
| KMU-Anteil | `kmu_anteil` |
| **Wechselquote** | `wechselquote` |
| **Neuzugänge/Jahr** | `neuzugang_pro_jahr` |
| Ihr dort | `agg_buyer_supplier` für eigene Entity |

**Detailansicht je Stelle** — Sicht Vergabestelle:

```
Lieferantenbild        Top-Anbieter mit Anteil, Zeitraum, laufende Verträge
Konzentration          Anteil des stärksten Anbieters
Neuzugänge pro Jahr    Firmen mit Erstzuschlag
Wechselquote           bei Nachfolgevergaben
KMU-Anteil             der Zuschläge
Preisentscheidungen    rein über Preis
Ø Lose je Vergabe      Teilbarkeit
Bürgschaftspflicht     Kapitalhürde
Rechtsrahmen-Mix       VOB / VgV / UVgO / SektVO
```

**Kernaussage der Sektion:** Die Neuzugangsquote ist die eigentliche Antwort auf „komme ich da rein?". Sie braucht im Gegensatz zur Wechselquote keine Verkettung und ist damit deutlich belastbarer. Eine Stelle mit 0,2 Neuzugängen pro Jahr ist geschlossen, unabhängig vom Volumen.

**Gate:** Free sieht die ersten 3 Zeilen. Pro sieht alles.

---

### 5.4 Wettbewerb

**Frage:** Wer holt was, wer hält was?

Zwei Sichten auf dieselbe Datenstruktur (`agg_buyer_supplier`). Der bestehende Inside/Outside-Umschalter trägt die Logik konzeptionell bereits.

#### Ebene 1 — Übersicht Anbieter

Tabelle: Anbieter, Zuschläge 24M, Volumen, Trend YoY, Anzahl Stellen, Überschneidung mit euch (geteilte Stellen + geteilte CPV-Bündel, als Stufe hoch/mittel/niedrig). Eigene Zeile am Ende hervorgehoben.

#### Ebene 2 — Anbieterprofil

| Block | Inhalt |
|---|---|
| Geholt (12M) | Zuschläge mit Stelle, Volumen, Datum, Kennzeichnung Neuzugang/verteidigt |
| Gehalten | laufende Verträge mit Ende, Kennzeichnung „ohne erneuten Wettbewerb" |
| Zuschlagsanteil je Stelle | `anteil_bei_stelle` gegen `anteil_marktdurchschnitt`, absteigend nach `ueberperformance` |
| Angreifbar | laufende Verträge mit nahem Ende, angereichert um die Wechselquote der Stelle |

#### Ebene 3 — Vergabestellen-Sicht

Identisch zu 5.3 Detailansicht. Von jeder Matrixzelle aus in beide Richtungen navigierbar.

#### Matrix

Vergabestellen (Zeilen) × Anbieter (Spalten), Zellintensität = Zuschlagsanteil. Leere Zellen bei hohem Zeilenvolumen sind das Signal: dort dominiert niemand.

**Regeln**

- Überall `entity_confidence` mitführen. Anbieter mit `confidence = none` werden aus Aggregaten ausgeschlossen, nicht als „Sonstige" gebündelt — sonst entsteht ein Phantom-Marktführer.
- Keine Wertung im Text. Nicht „starke Beziehung", sondern „12 von 19 Vergaben, Marktdurchschnitt 14 %".

**Gate:** Pro vollständig. Free sieht Ebene 1 mit den ersten 3 Zeilen ohne Zahlen.

---

### 5.5 Position

Unverändert aus dem bestehenden Prototyp übernehmen. Inklusive des Absatzes zur nicht ausweisbaren Gewinnquote — der bleibt wörtlich stehen.

---

### 5.6 Fähigkeiten

**Frage:** Was blockiert uns?

**Inhalt:** Geforderte Nachweise, Zertifikate und Bürgschaften im Zielmarkt, gegen das eigene Profil geprüft. Je Anforderung: Häufigkeit, betroffenes Volumen, vorhanden ja/nein.

**Regel — und das ist die wichtigste dieser Sektion:** Eignungsanforderungen liegen überwiegend im Freitext (`T_CAPACITY_INFORMATION.P`, `ECONOMIC_OPERATORS_PERSONAL_SITUATION.P`, jeweils ~37 % Abdeckung). Jede Aussage ist deshalb als **Untergrenze** zu formulieren:

> „Mindestens €28M der Ausschreibungen in eurem Feld fordern C5."

Nicht: „€28M fordern C5."

**Hinweis zur Datenbasis:** `ExternalReference.URI` (Direktlink zu den Vergabeunterlagen) hat 83 % Abdeckung bei offenen Leads, das aktuell genutzte `portal_url` nur 44,5 %. Ein Wechsel auf das bessere Feld hebt die Anforderungs-Extraktion deutlich. Das ist unabhängig von diesem Ticket umsetzbar und sollte vorgezogen werden.

**Gate:** Pro.

---

### 5.7 Bindung

**Frage:** Was ist uns verschlossen?

Die Sektion mit dem höchsten Differenzierungswert. Grundlage ist `ContractingSystemTypeCode = 'fa-wo-rc'` (Rahmenvereinbarung ohne erneuten Wettbewerb, 46,5 % Abdeckung, davon 9–11 % dieser Typ).

**Blöcke**

| Block | Inhalt |
|---|---|
| Gesperrtes Volumen | Rahmen ohne erneuten Wettbewerb im Zielmarkt, bei denen die eigene Entity nicht unter den Gelisteten ist. Volumen, Laufzeitende, gelistete Anbieter. |
| Nächste Einstiegsfenster | Enddaten dieser Rahmen minus üblicher Vorlauf (Median Ausschreibung→Zuschlag: 87 Tage, plus Positionierungsvorlauf) |
| Eigene auslaufende Verträge | Verteidigungsbedarf, sortiert nach Ende |
| Konzentrationsrisiko | Anteil des bekannten eigenen Volumens, der an der stärksten Stelle hängt |
| Gebundene Kapazität | Summe der Bindefristen (`TenderValidityPeriod`) laufender eigener Angebote |

**Regel:** „Gesperrt" nur behaupten, wenn die Gelisteten-Liste tatsächlich vorliegt. Wo nur bekannt ist, dass es ein Rahmen ohne Wettbewerb ist, aber nicht wer gelistet ist: als `unbekannt` ausweisen, nicht als gesperrt annehmen.

**Gate:** Free sieht die Anzahl gesperrter Rahmen ohne Volumen. Pro sieht alles.

---

### 5.8 Profil

Unverändert aus dem bestehenden Prototyp übernehmen.

---

## 6. Free / Pro Gates

Gating erfolgt **pro Sektion**, nicht pro Bereich. Grund: der Bereich soll später als eigener Tarif abtrennbar sein, ohne die Gate-Logik neu zu bauen.

| Sektion | Free | Pro |
|---|---|---|
| Pipeline | Achse + Balkenform, Werte verdeckt | voll |
| Felder | gesperrt | voll |
| Vergabestellen | Top 3 Zeilen, Zahlen verdeckt | voll |
| Wettbewerb | Ebene 1, Top 3, Zahlen verdeckt | voll |
| Position | gesperrt (wie heute) | voll |
| Fähigkeiten | gesperrt | voll |
| Bindung | Anzahl gesperrter Rahmen, kein Volumen | voll |
| Profil | ∞ | ∞ |

**Blur statt Leere.** Die bestehende Mechanik (`sec-lock`, `pb-lock`, `probadge-lock`) wird übernommen: Struktur sichtbar, Zahlen verdeckt. Ein Free-User, der „38 % eures Marktes ist gesperrt — Details in Pro" sieht, hat einen konkreten Grund zum Upgrade.

**Analyse-Limit:** Der Strategie-Bereich verbraucht **keine** der 3 Analysen pro 30 Tage. Das Limit gilt weiterhin nur für den Bewertungs-Tab im Lead-Detail. Strategie ist reines Pro-Gating.

**Erfolgsprämie:** Der Strategie-Bereich löst **keine** Attribution aus. Auslöser bleibt ausschließlich der Klick auf den Bewertungs-Tab eines konkreten Leads. Ein Aufruf von „Vergabestellen" ist keine Lead-Analyse.

---

## 7. Analytics-Events

Ergänzend zu Ticket #8.

| Event | Properties |
|---|---|
| `strategy_opened` | `section` |
| `strategy_section_changed` | `from`, `to` |
| `strategy_horizon_changed` | `months` (12/24/36) |
| `strategy_buyer_opened` | `buyer_id` |
| `strategy_supplier_opened` | `supplier_id` |
| `strategy_matrix_cell_clicked` | `buyer_id`, `supplier_id` |
| `strategy_leadjump` | `section`, `lead_id` — Sprung in den Explorer |
| `strategy_upgrade_prompt_shown` | `section` |
| `strategy_thin_data_shown` | `kpi`, `n` — wie oft greift die Schwellenregel |

Das letzte Event ist wichtig: Wenn `strategy_thin_data_shown` sehr häufig feuert, ist die Sektion für die Mehrheit der Nutzer wertlos und muss überarbeitet werden.

---

## 8. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Rail-Eintrag „Potenzial" heißt „Strategie" |
| 2 | Acht Sektionen in zwei Gruppen, vertikale Abschnittsnavigation |
| 3 | Keine zweite Tab-Ebene innerhalb einer Sektion |
| 4 | `Chancen` existiert nicht mehr, Inhalte sind in Felder/Vergabestellen aufgegangen |
| 5 | Jeder Quoten-KPI respektiert die Fallzahl-Schwellen aus 3.1 |
| 6 | Bei `n <= 2` wird nie ein Prozentwert angezeigt |
| 7 | Pipeline zeigt drei getrennte Herkunftsklassen, keine Gesamtsumme |
| 8 | Anbieter mit `entity_confidence = none` sind aus allen Aggregaten ausgeschlossen |
| 9 | Kein UI-Text behauptet „Beziehung"; ausgewiesen wird Zuschlagsanteil gegen Marktdurchschnitt |
| 10 | Fähigkeiten-Aussagen sind als Untergrenze formuliert |
| 11 | „Gesperrt" nur bei bekannter Gelisteten-Liste |
| 12 | Gating je Sektion konfigurierbar, nicht hart verdrahtet |
| 13 | Strategie verbraucht keine Analysen und löst keine Attribution aus |
| 14 | Aggregate werden nächtlich neu gebaut, Ladezeit je Sektion < 800 ms |
| 15 | Jede Sektion hat einen definierten Leerzustand für Firmen ohne Historie |
| 16 | Bietergemeinschaften zählen für jedes Mitglied und sind gekennzeichnet |

---

## 9. Offene Fragen

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Herkunfts-Zustand `duenn` einführen? | Ja — sonst wird „gemessen aus 3 Fällen" mit „gemessen aus 300" gleich dargestellt |
| 2 | Konzernstrukturen zusammenfassen? | Ja, aber umschaltbar. Ein Systemhaus will je nach Frage beides sehen |
| 3 | Bietergemeinschaften: je Mitglied zählen? | Ja, gekennzeichnet — sonst verschwinden KMU aus der Statistik |
| 4 | Heuristische Nachfolge-Verkettung als Fallback? | Ja, aber strikt als `schaetz` getrennt von der harten Verkettung |
| 5 | Eigener Tarif für Strategie? | Nicht in V1.5. Sektionsweises Gating jetzt bauen, Preisfrage nach Design-Partner-Feedback |
| 6 | Zeithorizont über 36 Monate? | Nein. Vertragsenden jenseits davon sind zu ~70 % geschätzt |
| 7 | Wettbewerbs-Matrix bei > 30 Stellen? | Top 15 × Top 10, Rest über Suche |

---

## 10. Out of Scope

| Was | Warum |
|---|---|
| Szenario-Simulator mit Ertragsprognose | Braucht eine Gewinnquote, die aus den Daten nicht ableitbar ist |
| Erwartete Wins in Euro | Dieselbe Begründung |
| Haushaltsdaten-Prognose | Nicht in TED/DÖE, Aufwand hoch, Aussage schwammig |
| Finanzkennzahlen der Wettbewerber | Kostenpflichtig, kein Bezug zur Vergabeentscheidung |
| LLM-generierte Handlungsempfehlungen | Ohne Belegkette nicht mit der Provenance-Regel vereinbar |
| Personalwechsel bei Vergabestellen | Nicht sauber verfügbar |
| Export des Strategie-Bereichs | V2 — erst Struktur validieren |

---

## 11. Abhängigkeiten

| Abhängigkeit | Status |
|---|---|
| `entity_identity` mit belastbarer Auflösungsquote | **Voraussetzung, offen** |
| `ref_publication_number` Verkettung | vorhanden, ~51 % |
| DÖE als Datenquelle | in Arbeit |
| NUTS-3 Granularität | separates Ticket |
| `ExternalReference.URI` statt `portal_url` | vorgezogen empfohlen |
| Ticket #2 User-Profil (Schwerpunkte, Regionen) | vorhanden |
| Ticket #6 Auth (Pro-Status) | vorhanden |

---

## 12. Vorgeschlagene Reihenfolge

| Schritt | Inhalt |
|---|---|
| 1 | Entity-Auflösung prüfen und, falls nötig, härten |
| 2 | Aggregat-Tabellen 4.1–4.4 bauen, nächtlicher Rebuild |
| 3 | Sektion Pipeline — einfachste Aggregation, sofort sichtbarer Wert |
| 4 | Sektion Vergabestellen inkl. Wechsel- und Neuzugangsquote |
| 5 | Sektion Wettbewerb (Ebene 1 + 2), danach Matrix |
| 6 | Sektion Bindung |
| 7 | Sektionen Felder und Fähigkeiten |
| 8 | Position und Profil aus dem Bestand migrieren |

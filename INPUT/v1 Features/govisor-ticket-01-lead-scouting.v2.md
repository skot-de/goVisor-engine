# Feature #1: Lead Scouting — v2 (engine-verdrahtet)

**Produkt:** goVisor
**Version:** V1
**Status:** Draft (Neufassung von v1, korrigiert gegen den realen Gold-Layer)
**Erstellt:** 2026-07-18

> **Warum diese Fassung?** Die erste Fassung war handwerklich gut, aber greenfield gedacht:
> sie erfand `leads`, `lead_scores` und einen Wechsel-Score neu, obwohl der Gold-Layer das
> bereits berechnet — inklusive Konfidenz und Quellenkennzeichnung, die v1 weggelassen hat.
> Diese Fassung zeigt auf die bestehenden Gold-Tabellen und macht die gemessene Datenrealität
> zum Teil der Spezifikation. Leitprinzipien der Engine gelten auch hier:
> **kein Datenverlust, markieren statt wegwerfen** und **messen statt annehmen**.

---

## Reality-Check (gemessen, DE-Gold, 70.271 Leads, Stand 2026-07-18)

Diese Zahlen sind **Vorgaben**, keine Randnotiz — die AC und das UI müssen sie tragen.

| Signal | Verteilung | Bedeutung fürs Feature |
|--------|-----------|------------------------|
| Auslauf-Basis (`faellig_basis`) | 77,0 % echtes Vertragsende · **23,0 % aus Laufzeit geschätzt** | Auslauf-Radar trägt, aber „geschätzt" ist ein sichtbarer Zustand |
| Termin-Plausibilität (`termin_plausibel`) | 98,5 % plausibel · 1,5 % markiert unplausibel | unplausible Termine werden **angezeigt + markiert**, nicht gedroppt |
| Volumen (`value_source`) | **55,8 % unbekannt** · 39,9 % final · 4,4 % geschätzt | Volumen-Match darf einen Lead nicht wegen fehlendem Volumen verwerfen |
| Wechsel-Score (`displaceability`) | **31,4 % NULL** (Einmal-Werk, nicht kettenrelevant) | kein erfundener Score für Nicht-Ketten — NULL ist eine Aussage |
| Vertragsart (`contract_kind`) | sonstiges 45,3 · werk_sonstig 18,0 · wiederkehrend 16,0 · einmal_werk 13,4 · rahmenvertrag 7,2 % | **5 Klassen**, nicht 2 — die Achse trägt das Displaceability-Modell |
| Incumbent-Konfidenz (`incumbent_conf`) | 89,7 % ≥ 0.90 · **10,3 % < 0.50** (bimodal) | 10 %-Keil unsicherer Incumbents: sichtbar als unsicher, nicht als Fakt |
| Notice-Quellen (Silber) | cn/F02 46,6 % · can/F03 39,8 % · **pin/F01 2,1 %** | alle drei Quellen vorhanden; F01 ist dünn und muss so kommuniziert werden |

---

## Kontext

Anbieter im Public-Sector-Markt erfahren zu spät von relevanten Deals — oder gar nicht.
Wenn eine Ausschreibung live ist, hat der Incumbent oft schon Monate Vorsprung durch
Beziehungsaufbau. Lead Scouting bringt drei Signale in eine Master-Liste, nach Timing gestaffelt:

| Quelle | notice_kind | Timing | Signal | Datenstatus |
|--------|-------------|--------|--------|-------------|
| Auslauf-Radar | `can` (F03) | 6–24 Mo vorher | Vertrag läuft aus (Vergabe + Laufzeit) | **existiert im Gold** (`leads`) |
| F01 Vorinformation | `pin` (F01) | 3–12 Mo vorher | Buyer kündigt offiziell an | in Silber, **noch nicht als Lead** (dünn: 2,1 %) |
| F02 Ausschreibung | `cn` (F02) | jetzt | Ausschreibung ist live | in Silber, **noch nicht als Lead** (46,6 %) |

**Wichtig:** Heute speist **nur der Auslauf-Radar** die `leads`-Tabelle. F01/F02 als Lead-Quellen
sind der eigentliche Neubau dieses Tickets (siehe Abschnitt „Neubau vs. Bestand").

---

## User Story

> **Als** Anbieter
> **will ich** relevante Leads sehen (passend zu meinem Profil), mit ehrlicher Kennzeichnung
> wie sicher jedes Signal ist,
> **um** früher als der Wettbewerb aktiv zu werden — sei es beim **Angriff** auf einen fremden
> Vertrag oder bei der **Verteidigung** eines eigenen auslaufenden Vertrags.

---

## Angriff / Verteidigung (die „View")

Der Toggle aus dem Mockup wird hier definiert. Er hängt daran, ob der eingeloggte User
**selbst der Incumbent** eines Leads ist. Das wird bestimmt, indem die eigene Firma des Users
(aus `user_profiles`, aufgelöst über dieselbe Entity-Resolution wie alle Suppliers) gegen
`leads.incumbent_entity` gematcht wird.

| View | Definition | Leads |
|------|-----------|-------|
| 🎯 **Angriff** | User ist **nicht** Incumbent | fremde auslaufende/ausgeschriebene Verträge, die zum Profil passen |
| 🛡️ **Verteidigung** | User **ist** Incumbent (`incumbent_entity` = eigene Entity, mit `incumbent_conf`) | eigene auslaufende Verträge — Frühwarnung, bevor die Neuausschreibung kommt |

- Der Match User-Firma ↔ Incumbent trägt **selbst eine Konfidenz** (`incumbent_conf`). Bei
  `< 0.75` gilt ein Verteidigungs-Lead als **„mutmaßlich eigener Vertrag"** und wird als solcher
  markiert — nie stillschweigend als sicher eigener Vertrag geführt.
- In der Verteidigung invertiert sich die Lesart des Wechsel-Scores: hoher `displaceability`
  = **hohes eigenes Verlustrisiko** (nicht Chance). Gleiche Zahl, andere Farbe/Label je View.

---

## Akzeptanzkriterien

| # | Kriterium |
|---|-----------|
| 1 | Leads erscheinen in der Master-Liste (linke Spalte), gefiltert nach aktivem View (Angriff/Verteidigung) |
| 2 | Default-Sortierung nach kombiniertem Ranking (Definition unten, **nicht** Produkt zweier Scores); umschaltbar auf Relevanz, Wechsel-W., Timing |
| 3 | Jeder Lead zeigt: **🎯 Relevanz**, **⚡ Wechsel** (aus `displaceability`), Timing, Buyer, Volumen, Incumbent |
| 4 | Jeder Score/Wert trägt eine **sichtbare Vertrauens-/Quellen-Kennzeichnung**: Volumen (`value_source`), Auslauf (`faellig_basis`, `termin_plausibel`), Incumbent (`incumbent_conf`) |
| 5 | Leads mit `displaceability = NULL` (Einmal-Werk) zeigen **„n/a"** beim Wechsel-Score, **keinen erfundenen Wert** |
| 6 | Quellen-Filter (Auslauf/F01/F02) und Icons machen die Herkunft jedes Leads erkennbar |
| 7 | Klick auf Lead → Detail rechts (Ticket #3) |
| 8 | Nur Leads passend zum User-Profil (CPV inkl. Hierarchie, Region, Volumen — mit Sonderbehandlung „Volumen unbekannt", siehe Scoring) |
| 9 | Alert bei neuen passenden Leads über konfigurierbarer Schwelle (E-Mail) |
| 10 | Volumen-Vergleiche laufen über **`value_real_2020`** (deflationiert), nicht über Nominalwerte |

---

## Neubau vs. Bestand (der eigentliche Scope)

| Baustein | Status | Quelle |
|----------|--------|--------|
| Auslauf-Leads inkl. Auslauf-Datum, Wechsel-Score, Incumbent+Konfidenz, Volumen+Quelle, Kontakt | **existiert** | `data/gold/DE/leads.parquet` |
| Wechsel-Score-Modell (kalibriert, AUC 0.806) | **existiert** | `dim_displaceability` + `build_displaceability` |
| Entity-Resolution mit Konfidenz | **existiert** | `entities` / `build_entities` |
| Deflator für reale Volumen | **existiert** | `dim_deflator` |
| **F02 (cn) und F01 (pin) als Lead-Quellen** materialisieren | **Neubau** | Silber `notices` (kind in {cn,pin}) → neue Lead-Zeilen |
| **Relevanz-Score** (per User-Profil) | **Neubau** | User-Profil × Lead (CPV/Region/Volumen) |
| **user_profiles / Auth** | **Neubau** | — |
| **Angriff/Verteidigung-View** (User-Firma ↔ incumbent_entity) | **Neubau** | Match User-Entity gegen `leads.incumbent_entity` |
| **Alert-/E-Mail-System** | **Neubau** | — |

---

## F01/F02 als Lead-Quellen (Materialisierung)

**Kein eigenes Produkt-Ticket**, sondern ein Gold-Builder-Sub-Task dieses Tickets: eine Funktion
(`build_prospective_leads`, analog zu `build_leads`) liest Silber-`notices` mit
`notice_kind ∈ {cn, pin}` und schreibt **zusätzliche Zeilen** ins bestehende `leads`-Parquet mit
demselben Schema. Ein `can`/Auslauf-Lead bleibt unverändert.

```
Silber notices (notice_kind = cn/pin)
        │  join lots (Laufzeit/Optionen), Buyer-Entity, CPV→branche
        ▼
Gold leads (neue Zeilen, gleiches Schema, source ∈ {f01,f02})
```

**Feld-Mapping** (was gefüllt wird, was bewusst NULL bleibt):

| Gold-Feld | F02 (`cn`) | F01 (`pin`) | Begründung |
|-----------|-----------|-------------|------------|
| `source` | `'f02'` | `'f01'` | aus `notice_kind` abgeleitet |
| `buyer_entity` / `buyer_name` / `buyer_nuts` / `buyer_email` / `buyer_url` | ✅ | ✅ | Buyer ist da (Entity-aufgelöst) |
| `titel` / `beschreibung` / `cpv_main` / `cpv_class` / `branche` / `sector` | ✅ | ✅ | Inhalt + CPV-Hierarchie vorhanden |
| `contract_kind` | ✅ (`classify_contract` aus Titel/CPV) | ✅ | Klassifikation braucht keine Vergabe |
| `value_used` / `value_source` / `value_real_2020` / `value_band` | ✅ (meist `geschaetzt`) | ⚠️ oft NULL | F02 hat `estimated_value`; F01 selten |
| `has_renewal` / `max_renewals` | ✅ (aus lots, falls vorhanden) | ⚠️ selten | Optionen/Verlängerung teils schon im cn |
| **Timing** | `submission_deadline` (Frist) | `publication_date` (Ankündigung) | **andere Timing-Semantik** als Auslauf, siehe unten |
| `incumbent_entity` / `incumbent_name` / `incumbent_conf` / `in_consortium` | **NULL** | **NULL** | noch nicht vergeben — kein Incumbent |
| `displaceability` / `displ_band` / `score_*` / `bidder_bucket` | **NULL** | **NULL** | Wechsel-Modell greift nur bei Vergabe-Historie; `displ_band = 'n/a (nicht vergeben)'` |
| `num_tenders` / `single_bidder` | **NULL** | **NULL** | Ergebnis-Kennzahlen existieren erst nach Vergabe |
| `contract_end` / `months_to_expiry` / `faellig_basis` / `termin_plausibel` | **NULL** | **NULL** | kein Auslauf-Datum — Timing kommt aus Frist/Ankündigung |
| `reachable` | ✅ | ✅ | Buyer-Kontakt vorhanden |

**Timing-Vereinheitlichung:** die Master-Liste braucht ein sortierbares Timing über alle drei
Quellen. Regel:
- `auslauf` → `months_to_expiry` (bis Vertragsende)
- `f02` → Monate bis `submission_deadline` (bis Angebotsfrist)
- `f01` → Monate seit `publication_date` bzw. erwarteter Vorlauf (Signal „kommt bald")

Diese drei speisen ein gemeinsames Sort-Feld `timing_sort` (kleiner = dringender). Die
Quellen-Semantik bleibt im UI über das Quell-Icon (🔵/🟢/🟡) sichtbar, damit „4 Monate" bei
Auslauf und „4 Monate" bei F02 nicht verwechselt werden.

---

## Datenmodell

Die Lead-Grunddaten kommen aus dem Gold-`leads`-Parquet. Persistente App-Tabellen kommen
**nur** dort hinzu, wo etwas User-spezifisch ist (Profil, Relevanz, Alerts). Der Lead selbst
wird **nicht** in eine App-DB kopiert und dabei seiner Konfidenzfelder beraubt.

### Bestehend: Gold `leads` (Auszug der relevanten Spalten — nicht neu anlegen)

| Feld | Bedeutung |
|------|-----------|
| `lead_id` | Schlüssel |
| `buyer_entity`, `buyer_name`, `buyer_nuts`, `buyer_email`, `buyer_url` | Käufer (Entity-aufgelöst) |
| `incumbent_entity`, `incumbent_name`, **`incumbent_conf`**, `in_consortium` | Incumbent **mit Konfidenz** |
| `titel`, `beschreibung`, `cpv_main`, `cpv_class`, `branche`, `sector` | Inhalt + CPV-Hierarchie |
| `vergabe_datum`, `contract_end`, `months_to_expiry`, **`faellig_basis`**, **`termin_plausibel`** | Auslauf-Radar |
| `contract_kind` | 5 Klassen |
| `value_clean`, `value_used`, **`value_source`**, **`value_real_2020`**, `value_band` | Volumen **ehrlich** |
| `num_tenders`, `single_bidder`, `has_renewal`, `max_renewals` | Verfahrensmerkmale |
| `reachable`, `source_confidence` | Kontakt / Quellen-Vertrauen |
| **`displaceability`**, `displ_band`, `score_basis`, `score_support`, `bidder_bucket`, `score_driver` | **Wechsel-Score** inkl. Trainings-Support & Treiber |

> Für F01/F02-Leads werden dieselben Spalten befüllt, soweit die Quelle sie hergibt; fehlende
> Felder bleiben NULL und werden im UI als „—" mit passendem Grund gezeigt (nicht geraten).
> Insbesondere hat ein F02-Lead **keinen** Incumbent (noch nicht vergeben) und i. d. R. keinen
> Wechsel-Score — das ist korrekt und wird so dargestellt.

### Neu: `user_profiles`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | uuid | PK |
| `user_id` | uuid | FK → auth.users |
| `company_name` | string | Firmenname |
| `company_entity_id` | string | **aufgelöste eigene Entity** (für Verteidigungs-View); gesetzt per Onboarding-Regel unten |
| `company_entity_conf` | decimal | Konfidenz dieser Zuordnung |
| `cpv_codes` | string[] | relevante CPVs |
| `nuts_regions` | string[] | aktive Regionen |
| `volume_min`, `volume_max` | decimal | Volumen-Range (real, Basis 2020) |

#### Onboarding: wie `company_entity_id` gesetzt wird

**Auto-Vorschlag, manuelle Bestätigung** — nie stilles Binden. Die Verteidigungs-View hängt
direkt daran (falsche Eigen-Entity ⇒ falsche „eigene Verträge"), deshalb ist eine Bestätigung Pflicht.

1. Aus `company_name` (+ optional USt-IdNr./HRB) wird über die **bestehende** Entity-Resolution
   (`normalize_company` → `blocking_key` → `entities`) ein Kandidat mit Konfidenz gezogen.
2. Dem User werden die Top-Kandidaten mit ihrem kanonischen Namen und einer Konfidenz gezeigt.
   Er bestätigt einen (oder „keiner davon").
3. `company_entity_id` + `company_entity_conf` werden gesetzt. Liegt die Konfidenz `< 0.75`,
   bleibt der Status **„unbestätigt"**; die Verteidigungs-View markiert ihre Leads dann als
   „mutmaßlich eigener Vertrag" (konsistent mit Edge Case #7).
4. Findet sich **kein** Match (neuer Marktteilnehmer ohne TED-Historie), ist `company_entity_id`
   NULL — die Angriffs-View funktioniert voll, die Verteidigungs-View ist leer mit Hinweis.

### Neu: `lead_relevance` (User-spezifisch, ersetzt „lead_scores")

Nur **passende** (User, Lead)-Paare werden persistiert (offene Frage #6), nicht das
Kreuzprodukt. Die Teil-Scores sind eigene Spalten (nicht in ein jsonb-Blob versteckt), damit
sie sortier-/filterbar und im UI erklärbar sind.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | uuid | PK |
| `lead_id` | string | FK → gold `leads.lead_id` |
| `user_id` | uuid | FK → auth.users |
| `relevance_score` | int | 0–100 (gewichtete Summe der drei Teil-Scores) |
| `cpv_match_score` | int | 0–100, CPV-Hierarchie-Match (Gewicht 40 %) |
| `region_match_score` | int | 0–100, NUTS-Match (Gewicht 30 %) |
| `volume_match_score` | int | 0–100, Volumen-Range-Match; 50 bei `value_source='unbekannt'` (Gewicht 30 %) |
| `is_incumbent_self` | boolean | User ist Incumbent dieses Leads → Verteidigungs-Lead |
| `incumbent_self_conf` | decimal | Konfidenz des Matches User-Entity ↔ `incumbent_entity` (nullable) |
| `calculated_at` | timestamp | |

Uniqueness: `(lead_id, user_id)`. Index auf `(user_id, relevance_score DESC)` für die Master-Liste.

> **Kein** eigenes `switch_probability_score`-Feld: der Wechsel-Score ist `leads.displaceability`
> und wird nicht dupliziert/neu berechnet. Das kombinierte Ranking entsteht **zur Laufzeit** aus
> `lead_relevance.relevance_score` × `leads.displaceability` (siehe „Berechnungsstrategie").

### Neu: `lead_alerts`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | uuid | PK |
| `user_id` | uuid | FK |
| `lead_id` | string | FK → `leads.lead_id` |
| `first_matched_at` | timestamp | wann der Lead **erstmals** ins Profil passte (Alert-Trigger, siehe unten) |
| `notified_at` | timestamp | nullable |

---

## API / Logik

### Endpunkte

| Methode | Endpoint | Beschreibung |
|---------|----------|--------------|
| GET | /api/leads | Leads für User (View, gefiltert, sortiert, paginiert) |
| GET | /api/leads/:id | Lead-Detail (Ticket #3) |
| GET | /api/leads/count | Anzahl neuer passender Leads (Badge) |

### Query-Parameter (GET /api/leads)

| Param | Typ | Default | Werte |
|-------|-----|---------|-------|
| view | string | 'attack' | 'attack', 'defense' |
| sort | string | 'combined' | 'combined', 'relevance', 'switch', 'timing' |
| source | string | 'all' | 'all', 'auslauf', 'f01', 'f02' |
| contract_kind | string | 'all' | 'all', 'rahmenvertrag', 'wiederkehrend', 'einmal_werk', 'werk_sonstig', 'sonstiges' |
| page | int | 1 | |
| limit | int | 50 | |

### Response (GET /api/leads) — Konfidenz ist Teil des Vertrags

```json
{
  "view": "attack",
  "leads": [
    {
      "lead_id": "…",
      "source": "auslauf",
      "buyer": { "entity": "…", "name": "BMI", "nuts": "DE3" },
      "incumbent": { "entity": "…", "name": "Bechtle", "confidence": 0.97, "in_consortium": false },
      "volume": { "used": 12000000, "real_2020": 10800000, "source": "final", "band": "1-5M" },
      "timing": {
        "months_to_expiry": 4,
        "contract_end": "2026-11-01",
        "basis": "Vertragsende",          // oder "aus Laufzeit geschätzt"
        "plausible": true,
        "deadline": null
      },
      "contract_kind": "rahmenvertrag",
      "scores": {
        "relevance": 92,
        "switch": { "value": 74, "band": "hoch", "support": 128, "driver": "…" }
      },
      "flags": { "has_contact": true, "single_bidder": false, "has_renewal": true }
    }
  ],
  "total": 47, "page": 1, "limit": 50
}
```

- `scores.switch.value` ist **null** bei Einmal-Werken; das UI zeigt „n/a".
- `incumbent` ist **null** bei F02-Leads (noch nicht vergeben).

### Relevanz-Score 🎯 (Neubau — korrigiert)

Basis 0–100. Region und Volumen sind **nicht** binär 0/100.

| Faktor | Gewicht | Berechnung |
|--------|---------|------------|
| CPV-Match | 40 % | über CPV-**Hierarchie**: exakt = 1.0, gleiche 4-Steller-Klasse (`cpv_class`) = 0.6, gleiche `branche` = 0.3, sonst 0. Max über alle User-CPVs |
| Region-Match | 30 % | exakte NUTS-Region = 1.0, gleiche NUTS-1 = 0.5, sonst 0 (nicht hart 0/100) |
| Volumen-Match | 30 % | in Range = 1.0, ±1 Band daneben = 0.5, außerhalb = 0. **Bei `value_source='unbekannt'` (55,8 %): neutraler Beitrag = 0.5, Lead nicht verwerfen**, und im UI als „Volumen unbekannt" markiert |

### Wechsel-Score ⚡ (Bestand — nicht neu erfinden)

= `leads.displaceability` (kalibriertes Modell, AUC 0.806, trainiert auf echten
`contract_successions`). Mitgeliefert: `displ_band`, `score_support` (n Trainingsfälle),
`score_driver`.

- `displaceability = NULL` (Einmal-Werk, 31,4 %) → **„n/a", kein Ersatzwert**.
- In der **Verteidigung** invertiert das Label (hoch = eigenes Verlustrisiko), der Zahlenwert bleibt.

### Kombiniertes Ranking (Skala fixiert)

Nicht das Produkt zweier 0–100-Werte (das ergäbe 0–10 000 und macht die Alert-Schwelle „> 70"
bedeutungslos). Stattdessen **gewichtetes Mittel auf 0–100**:

```
combined = round(0.5 * relevance + 0.5 * switch)          # wenn switch != null
combined = relevance                                       # wenn switch == null (Einmal-Werk)
```

Gewichte konfigurierbar. Alert-Schwelle bezieht sich eindeutig auf `combined` (0–100).

### Berechnungsstrategie (Performance)

70k+ Leads × N User. **Hybrid**, weil Lese-Frische und Alert-Dedup unterschiedliche Dinge brauchen:

| Zweck | Strategie | Warum |
|-------|-----------|-------|
| **Master-Liste (Lesen)** | **on-the-fly** in DuckDB gegen das `leads`-Parquet, gefiltert aufs User-Profil | Relevanz ist billige Arithmetik; 70k Zeilen scoren + sortieren + paginieren sind Millisekunden. Immer frisch, keine Staleness. |
| **Alerts + Count-Badge** | **materialisiert** in `lead_relevance` / `lead_alerts`, aktualisiert per Async-Job | Für „Lead passt **erstmals**" braucht es einen persistenten Vorher-Zustand — on-the-fly kann „neu" nicht von „schon gesehen" unterscheiden. |

- **Async-Job-Trigger**: (a) neuer/aktualisierter Lead im Gold (nach Gold-Rebuild), (b) User
  ändert Profil. Der Job rechnet nur die betroffenen (User, Lead)-Paare neu, nicht das Kreuzprodukt.
- Nur **passende** Paare landen in `lead_relevance` (offene Frage #6) — das begrenzt die Zeilen
  auf tatsächliche Matches statt 70k × N.
- Die Master-Liste liest die frischen on-the-fly-Werte; `lead_relevance` ist die Konsistenzbasis
  für Alerts. Bei Bedarf (sehr große Profile) kann die Liste später auf die materialisierten
  Werte umschwenken — Schnittstelle bleibt gleich.

**Zielwert:** Liste (500 Leads, gefiltert + sortiert) < 2 s (Testfall #12).

### Alert-Logik

| Trigger | Aktion |
|---------|--------|
| Lead passt **erstmals** ins Profil (`lead_alerts.first_matched_at` neu gesetzt) **und** `combined > Schwelle` | E-Mail |
| „Erstmals passt" | definiert als: es existierte noch kein `lead_alerts`-Eintrag (User, Lead). Verhindert Doppel-Alerts bei Neuberechnung |
| Profiländerung erzeugt neue Matches | zählt als „neu" nur, wenn vorher kein Eintrag bestand |
| Frequenz | konfigurierbar: sofort / täglicher Digest (Default: täglich) |
| Schwelle | konfigurierbar, Default `combined > 70` |

---

## Edge Cases

| # | Case | Verhalten |
|---|------|-----------|
| 1 | Keine passenden Leads | Leere Liste + „Keine Leads gefunden. Profil erweitern?" |
| 2 | User ohne Profil | Redirect zu Profil-Setup |
| 3 | Volumen unbekannt (55,8 %) | „€ —" + Badge „Volumen unbekannt"; Relevanz-Volumenfaktor neutral (0.5), Lead bleibt |
| 4 | Auslauf nur geschätzt (`faellig_basis='aus Laufzeit geschätzt'`, 23 %) | anzeigen **mit** Badge „geschätzt" |
| 5 | Termin unplausibel (`termin_plausibel=false`, 1,5 %) | anzeigen **mit** Warnmarkierung, nicht droppen |
| 6 | Wechsel-Score NULL (Einmal-Werk, 31,4 %) | „n/a"; kombiniertes Ranking fällt auf reine Relevanz zurück |
| 7 | Incumbent unsicher (`incumbent_conf < 0.5`, 10,3 %) | Name mit „unsicher"-Kennzeichen; in Verteidigung: „mutmaßlich eigener Vertrag" |
| 8 | F02-Lead ohne Incumbent | „— (noch nicht vergeben)", kein Wechsel-Score |
| 9 | Erstausschreibung ohne Incumbent-Historie | „— (Erstausschreibung)" |
| 10 | Kontakt fehlt | kein 📇, sonst normal |
| 11 | Profiländerung | Relevanz neu berechnen (async), Alert-Dedup beachten |
| 12 | Sehr viele Leads | Pagination + Query auf Parquet/DuckDB optimiert |

---

## Icons

| Icon | Bedeutung | Quelle |
|------|-----------|--------|
| 🔵 | Auslauf-Radar | `source='auslauf'` |
| 🟢 | F01 Vorinformation | `source='f01'` |
| 🟡 | F02 aktive Ausschreibung | `source='f02'` |
| 📋 | Rahmen-/wiederkehrender Vertrag | `contract_kind in {rahmenvertrag, wiederkehrend}` |
| 📇 | Kontaktdaten vorhanden | `reachable=true` |
| ⚠️ | geschätztes/unplausibles Datum oder unsicherer Incumbent | `faellig_basis`/`termin_plausibel`/`incumbent_conf` |

---

## Out of Scope

| Was | Wo stattdessen |
|-----|----------------|
| Lead-Detail-Ansicht | Ticket #3 / #8 Auto-Dossier |
| Filter-UI (Feinbau) | Ticket #2 Personal Fit |
| **Score-Modell-Interna** (Displaceability-Training) | bereits gebaut (`build_displaceability`); hier nur konsumiert |
| Export | Ticket #9 |
| Alert-Einstellungen-UI | Ticket #10 |

> Klarstellung ggü. v1: Die **Anwendung** der Scores (Relevanz-Formel, Ranking, NULL-Handling)
> gehört in dieses Ticket. Nur das **Training** des Wechsel-Modells ist außerhalb.

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| Gold `leads` (Auslauf-Radar) | ✅ existiert |
| `dim_displaceability`, `dim_deflator`, `entities` | ✅ existiert |
| F02/F01 → Lead-Materialisierung (cn/pin aus Silber) | ⬜ Neubau (dieses Ticket) |
| Relevanz-Scoring + `lead_relevance` | ⬜ Neubau (dieses Ticket) |
| User-Profil + eigene Entity-Auflösung | ⬜ vorher nötig |
| Auth-System | ⬜ vorher nötig |
| Alert-/E-Mail-System | ⬜ Neubau |

---

## Testfälle

| # | Test | Erwartetes Ergebnis |
|---|------|---------------------|
| 1 | User mit Profil öffnet Liste (Angriff) | fremde passende Leads, nach `combined` sortiert |
| 2 | View auf Verteidigung | nur Leads, wo User = Incumbent; hoher Wechsel-Score als **Risiko** gelabelt |
| 3 | Lead mit Volumen unbekannt | „€ —" + Badge; Lead bleibt in Liste |
| 4 | Lead mit geschätztem Auslauf | Badge „geschätzt" sichtbar |
| 5 | Einmal-Werk-Lead | Wechsel-Score „n/a"; Ranking = Relevanz |
| 6 | Incumbent `conf < 0.5` | „unsicher"-Kennzeichen |
| 7 | F02-Lead | 🟡, kein Incumbent, kein Wechsel-Score |
| 8 | Sortierung Relevanz / Timing / Wechsel | jeweils korrekt geordnet; NULL-Wechsel ans Ende bei sort=switch |
| 9 | Neuer passender Lead, `combined > 70` | genau eine Alert-Mail (kein Doppel bei Neuberechnung) |
| 10 | Profil ändern | Relevanz async neu, keine Alert-Flut |
| 11 | Volumen-Match Basis | vergleicht `value_real_2020`, nicht Nominalwert |
| 12 | 500 Leads laden | Liste < 2 s |

---

## Offene Fragen

| # | Frage | Entscheidung |
|---|-------|--------------|
| 1 | Gewichte im kombinierten Score? | konfigurierbar, Default 0.5/0.5 |
| 2 | F01 (pin) nur 2,1 % — eigene Quelle oder erst v2? | aufnehmen, im UI als „dünn" kommunizieren |
| 3 | Verteidigungs-View: ab welcher Konfidenz „eigener Vertrag" sicher? | ✅ ≥ 0.75 sicher, darunter „mutmaßlich" (in Onboarding-Regel verankert) |
| 4 | Relevanz-Volumenfaktor bei unbekanntem Volumen? | ✅ neutral 50, Lead bleibt (in Scoring/Edge Case #3 verankert) |
| 5 | Alert-Schwelle auf `combined` (0–100)? | ✅ ja, Default > 70 |
| 6 | Leads ohne Profil-Match speichern? | ✅ nein, nur passende (User, Lead) in `lead_relevance` |
| 7 | `company_entity_id` beim Onboarding automatisch oder bestätigt? | ✅ Auto-Vorschlag + manuelle Bestätigung (Abschnitt Onboarding) |
| 8 | Relevanz pre-computed oder on-the-fly? | ✅ Hybrid: Liste on-the-fly, Alerts materialisiert (Abschnitt Berechnungsstrategie) |
| 9 | F01/F02-Materialisierung eigenes Ticket? | ✅ nein, Gold-Builder-Sub-Task hier (`build_prospective_leads`) |

---

## Anhang: TED-Datenquellen (Schema-Generationen)

TED liegt in vier Generationen vor; die Formularnummern F01/F02/F03 gelten für **2016–2023**.
Für **2024+** gilt **eForms/UBL** (keine F0x-Nummern), für **2004–2015** ältere XML/Textformate.
Das Feature liest **`notice_kind`** (`pin`/`cn`/`can`), nicht die Formularnummer — dadurch
generationsübergreifend robust.

| Datenpunkt | Silber-Feld |
|------------|-------------|
| Quelle/Art | `notice_kind` (pin/cn/can) |
| CPV | `cpv_main` (+ Gold `cpv_class`, `branche`) |
| Region | `performance_nuts` / Buyer-NUTS |
| Volumen | `estimated_value` / `final_value` → Gold `value_used` + `value_source` |
| Buyer | Entity-aufgelöst → `buyer_entity` |
| Incumbent | nur bei `can` → `incumbent_entity` + `incumbent_conf` |
| Laufzeit | `lots.duration_months` / `start_date` / `end_date` → Gold `contract_end` + `faellig_basis` |
| Frist | `submission_deadline` |
| Kontakt | Buyer-Mail/URL → `reachable` |

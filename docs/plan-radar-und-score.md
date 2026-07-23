# Bauplan: #1 Auslauf-Radar & #2 Wechsel-Score

**Stand:** 2026-07-17. Ziel: den Pivot von *Engine* (rückblickend) zu *Produkt*
(Blick nach vorn). #1 ist der Liefergegenstand (kommende Re-Vergaben mit Kontakt),
#2 macht das Ranking gemessen statt geraten. #3 (klickbares lokales Frontend) folgt
danach.

> **Gate — GEMESSEN 2026-07-17, NICHT bestanden:** Incumbent-Rate bleibt bei **7 %**
> (2.156/30.509). Diagnose (scripts/feature_checks.py + Ad-hoc):
> - Entity-IDs sind **stabil** — nur 49/28.353 Wechsel haben gleichen Namen/andere ID
>   (0 %). Fragmentierung ist NICHT die Ursache; die frühere Erwartung „stabile IDs →
>   40–60 %" war falsch.
> - Konfidenz-Kontrolle (beide conf≥0,9): weiterhin 7 %. Kein Auflösungs-Rauschen.
> - **Die Ketten-Paarung ist das Problem:** eindeutige Zellen (1 Vorgänger/Nachfolger)
>   nur 12 %, große Zellen 5 %. 48 % aller Ketten aus Top-100 (Käufer×CPV)-Zellen,
>   dominiert von EINEM Käufer (DB) im Bahnbau. Heuristik (Käufer + 4-stellig CPV +
>   Zeitfenster) paart bei Großkäufern sachlich unabhängige Verträge → `incumbent_retained`
>   misst Zufall, keine echte Nachfolge.
>
> **Folge:** `contract_chains` bildet keine echte Vertragsnachfolge ab. **#2 ist
> blockiert**, bis die Nachfolge-Erkennung neu gebaut ist (s. u.). #1 ist unberührt
> (nutzt pro CAN das eigene end_date + eigenen Gewinner, keine Paarung).

---

## #1 — Auslauf-Radar (Gold-Tabelle `leads`)

**Idee:** Jeder abgeschlossene Auftrag (CAN) mit bekanntem Vertragsende erzeugt eine
künftige Re-Vergabe. Der Radar listet diese Auslauftermine *vor* der Neuausschreibung,
mit Amtsinhaber, Angreifbarkeit, Wert-Band und Kontakt. Das ist der verkaufbare Lead.

### Quelle & Vertragsende
- Basis: `notices` mit `notice_kind='can'`.
- Vertragsende `contract_end`:
  1. `notices.end_date`, sonst
  2. `award_date + duration_months` (aus `lots`, größte Los-Laufzeit der Notice), sonst
  3. NULL → Lead ohne Termin (niedrigere Priorität, trotzdem gelistet — kein Verlust).
- Lead nur, wenn `contract_end >= reference_date` (Zukunft). Vergangene Enden sind
  Historie → die füttern #2, nicht den Radar.
- `reference_date` wird als Parameter übergeben (kein `now()` im Buildcode).

### Spalten (`data/gold/DE/leads.parquet`)
| Spalte | Herkunft |
|---|---|
| `lead_id` | = `notice_id` (bzw. `notice_id`+`lot_id` bei Los-Granularität, v2) |
| `procedure_id` | join `procedures` |
| `buyer_entity`, `buyer_name` | `party_entity`(role=buyer) → `entities` |
| `buyer_town`, `buyer_nuts`, `buyer_email`, `buyer_url` | `notice_parties`(role=buyer) |
| `incumbent_entity`, `incumbent_name`, `incumbent_confidence` | winner-Entität + `entities.confidence` |
| `in_consortium` | `notice_parties`(role=winner).in_consortium |
| `cpv_main`, `cpv_class` (4-stellig), `branche`, `sector` | `notice_cpv`/`cpv_main` → `dim_cpv` (Division) |
| `contract_end`, `months_to_expiry` | berechnet ggü. `reference_date` |
| `value_clean`, `value_real_2020` | `quality.final_value_clean` × `dim_deflator` |
| `value_band` | Band aus `value_clean` (s. u.), sonst „unbekannt" |
| `num_tenders`, `single_bidder` | `awards` (max je Notice) |
| `has_renewal`, `max_renewals` | `lots` (bindet Amtsinhaber → senkt Wechselchance) |
| `reachable` | `buyer_email IS NOT NULL OR buyer_url IS NOT NULL` |
| `source_confidence` | min(incumbent_confidence, buyer_confidence); Wert-Flag mit ausweisen |

### Wert-Band (weil ~50 % keinen Wert haben)
Bänder aus `value_clean` (real, 2020): `<50k`, `50–200k`, `200k–1M`, `1–5M`, `>5M`,
plus `unbekannt`. Band statt exaktem € ist die ehrliche Darstellung; nie eine Zahl
erfinden. Für „unbekannt" später Schätz-Band aus mehreren Signalen (CPV+Laufzeit+
Käufer+Bieterzahl) — als *geschätzt* markiert, nicht fürs Billing.

### Priorität (Ranking-Vorstufe, ohne #2)
Heuristik v1: bald auslaufend + angreifbar (hohe historische Bieterzahl / kein
Renewal) + hohes Band + erreichbar. Ab #2 ersetzt der gemessene Wechsel-Score die
Heuristik-Komponente „angreifbar".

### Umsetzung
`gold.py::build_leads(cfg, country, reference_date)` — reine DuckDB-Query über die
oben genannten Silber/Gold-Parquets, ein `COPY … TO leads.parquet`. Kein neues
Ingest, keine externen Daten.

---

## #2 — Wechsel-Score (backgetestet, erklärbar)

**Idee:** `contract_chains` trägt mit `incumbent_retained` die Ground Truth „Amtsinhaber
blieb / wurde verdrängt". Daraus lernen wir gemessene Wechsel-Raten je Merkmal —
transparent, nicht als Black Box.

### Trainingsdaten
Ein Sample je Kette (`contract_chains`, n ≈ 30–35k). Ziel: `switched = NOT incumbent_retained`.
Merkmale (alle aus vorhandenen Tabellen, join über `predecessor`-notice_id):
| Merkmal | Herkunft | Hypothese |
|---|---|---|
| `num_tenders` (Vorgänger) | `awards` | mehr Bieter → mehr Wechsel |
| `single_bidder` | `awards` | Einzelbieter → Amtsinhaber bleibt |
| `has_renewal` | `lots` | Verlängerungsoption → bleibt |
| `value_band` | `quality`+`deflator` | Bandeffekt |
| `branche` | `dim_cpv` | Branchen-Grundraten unterscheiden sich |
| `gap_days` | `contract_chains` | lange Lücke → Neuausschreibung → Wechsel |
| `incumbent_confidence` | `entities` | **Kontrolle**: niedrige Konfidenz erzeugt Schein-Wechsel |

### Methode v1 — stratifizierte Raten (erklärbar zuerst)
1. Basis-Wechselrate gesamt.
2. Wechselrate je Merkmal-Bin (z. B. Einzelbieter vs. ≥3 Bieter; je Branche; je Band;
   Renewal ja/nein). Das ist das interpretierbare Rückgrat — jede Aussage rückführbar
   auf „X von Y Verträgen".
3. Kombinierter Score optional per simpler logistischer Regression, aber die
   stratifizierten Raten bleiben die vorzeigbare Erklärung („warum 70 %? → Einzelbieter
   + Bausektor + Renewal-Option").
4. **Kontroll-Schnitt:** Raten zusätzlich nur auf `incumbent_confidence >= 0.75`
   rechnen — zeigt, ob niedrige Konfidenz die Wechselrate künstlich hebt.

### Backtest (Kalibrierung statt Bauchgefühl)
Temporaler Holdout: Raten auf Ketten mit `successor.award_date < cutoff` lernen, auf
späteren testen. Prüfen: vorhergesagte vs. tatsächliche Wechselrate je Score-Dezil
(Kalibrierungskurve). Ergebnis dokumentieren — das ist die verteidigbare Zahl fürs
Kundengespräch.

### Ausgabe & Kopplung an #1
`gold.py::build_switch_score(cfg, country)` schreibt entweder eine Modell-Tabelle
(Merkmal-Bin → Rate) oder wendet den Score direkt auf `leads` an: jeder Lead bekommt
`wechsel_wahrscheinlichkeit` + `top_treiber` (das stärkste Merkmal). Damit ist der
Radar aus #1 **gerankt** — kommende Re-Vergaben, sortiert nach gemessener
Verdrängbarkeit, mit Kontakt.

### Ehrliche Grenzen (müssen kundensichtbar bleiben)
- Nur Gewinner bekannt → Score sagt „Amtsinhaber wechselt", NICHT „du gewinnst".
- Ketten sind erschlossen (`match_confidence` 0.6) → Score erbt diese Unsicherheit.
- n ≈ 30k trägt stratifizierte Raten gut, viel-Merkmal-Logit nur begrenzt → v1 bewusst
  schlank.

---

## Reihenfolge
1. `build_leads` (#1) — hängt nicht am Incumbent-Gate, sofort baubar.
2. Incumbent-Check bestätigen (final5).
3. `build_switch_score` (#2) + Backtest.
4. Score an `leads` koppeln → gerankter Radar.
5. Danach #3: rudimentäres lokales Frontend auf `leads` (etwas zum Klicken).

---

## Umgesetzt (2026-07-17)

**#1 `gold.build_leads`** → `leads.parquet`, 70.432 Leads (Stichtag heute). Pro Lead:
Amtsinhaber+Konfidenz, Käufer+Kontakt, Branche, Vertragsende, `months_to_expiry`,
`value_band` (40 % haben einen Wert), Bieterzahl, Renewal, `source_confidence`.
Hinweis: `reachable` ≈ 100 % (nur Käufer-Kontakt) — als Filter wertlos, später ersetzen.

**Spike-Verdict (#2 machbar?):** JA. Saubere Paarung (voll-CPV, kleine Zelle, conf≥0,75)
hebt die Incumbent-Rate 6 %→18 %, und das Signal **trennt sich**: Einzelbieter 29 % vs.
≥4 Bieter 10 %; IT 38 % vs. Bau 13 %. Absolut niedrig (Re-Wins unter Tochter/ARGE nicht
verknüpfbar) → als *relatives* Signal nutzbar. Umdeutung: **Verdrängbarkeit statt Amtstreue.**

**#2 `gold.build_displaceability`** (Ansatz B) → `dim_displaceability.parquet` (Modell:
Verdrängbarkeit je Branche×Bieter-Bucket, gelernt auf sauberem Subset) + Score-Spalten auf
`leads`: `displaceability` (0–1), `displ_band`, `score_driver`, `score_basis` (Backoff
Branche×Bieter → Branche → global, min_support 25), `score_support`. Monoton & trennscharf
(IT: Einzel 0,50 → viel 0,86; IT-Einzel 0,50 vs Bau-Einzel 0,81). **Relatives Ranking, keine
kalibrierte Gewinn-Wahrscheinlichkeit.**

**Kalibrierungs-Backtest (2026-07-18, `scripts/score_backtest.py`):**
- **Temporaler Holdout unmöglich** — nur 6 saubere Paare vor 2023 (verlässliche Entity-IDs
  sind eForms-Ära). „Vergangenheit sagt Zukunft" ist damit NICHT prüfbar.
- **5-fach Kreuzvalidierung (out-of-sample):** ECE **0,019** (sehr gut kalibriert — Score 0,72
  → real ~72 % verdrängt), Brier 0,1443 vs. Baseline 0,1519 (**+5 %** besser als raten),
  **AUC 0,659** (trennt richtig, aber moderat). Terzile monoton & kalibriert.
- **Fazit:** Die Score-Zahlen SIND belastbar (kalibriert), Trennschärfe moderat. Vorbehalt:
  Labels aus derselben erschlossenen Nachfolge (Zirkularität); n=4.144 klein; kein Zeit-Test.
  → Prognose-Signal C → B−: als kalibriertes Priorisierungs-Ranking nutzbar, nicht als
  starkes Einzelfall-Orakel.

## Echte Vergabeketten (`contract_successions`, 2026-07-18)

Die alten `contract_chains` (Käufer×CPV) sind KEINE echten Ketten (Katalog einer
Kategorie). **`build_contract_successions`** baut sie richtig: gleicher Käufer,
**Titel-/Scope-Ähnlichkeit** (Jaccard≥0,7, Käufername entfernt), >300 Tage Abstand,
geblockt nach (Käufer, CPV-4). **Vertragsart als Faktor** (`classify_contract`):
Einmal-Werke (Hausbau) sind ausgeschlossen (`chain_worthy=false`); Rahmenverträge/
Dienstleistungen sind die Kette. 15.137 echte Kanten mit `contract_kind`, `recurring`,
`incumbent_retained`, `similarity`, beiden Gewinnernamen.

**Befund — Vertragsart moduliert Amtstreue stark** (robust gegen Tochter-Fragmentierung,
+1pp gruppen-bewusst): Rahmenvertrag **10 %** gehalten (am angreifbarsten!), wiederkehrend
30 %, sonstiges 36 %. Zwei unabhängige Methoden (buyer×CPV-Subset 18 %, Titel-Match 19 %,
successions 27 % nach Werk-Ausschluss) bestätigen: echte sichtbare Amtstreue ist niedrig.

**Score neu basiert (2026-07-18):** `build_displaceability` trainiert jetzt auf
`contract_successions` (echte Labels), Achsen **Vertragsart × Branche × Bieter**, 4-stufiger
Backoff. Modell je Vertragsart: Rahmenvertrag **0,90** verdrängbar, wiederkehrend 0,70,
sonstiges 0,64. **Kreuzvalidierter Backtest deutlich besser:** AUC 0,659 → **0,806** (gut),
Brier-Lift +5 % → **+23,5 %**, ECE 0,016 (weiter sehr gut kalibriert). Die Vertragsart war der
fehlende Hebel. Vorbehalt bleibt: Kreuzvalidierung (nicht temporal), Labels aus der Titel-
Rekonstruktion (eigenes Rauschen) → Prognose-Signal **B− → B/B+**.

**RE-MESSUNG 2026-07-23:** Nach Voll-Reparse, DÖE-Ingest und Parser-Fixes reproduziert der
Backtest **AUC 0,767** (statt 0,806), Brier-Lift **+19,1 %** (statt +23,5 %), ECE 0,016
(unverändert gut). Die Methodik ist identisch — die Datenbasis hat sich geändert. **Für Pitch/
Doku ab jetzt 0,767 verwenden**, nicht 0,806. Reproduzieren: `python scripts/score_backtest.py`.
Merke: Jede Score-Zahl gehört mit Datum + Reproduktionsbefehl zitiert, sonst driftet sie unbemerkt.

**Nächster Hebel:** Dashboard „Vorgänger/Nachfolge" je Lead auf `contract_successions`.

**Weiter offen:** `reachable` sinnvoll machen; externe Quellen zur Wert-Abdeckung (~44 %);
temporaler Score-Test, sobald genug post-eForms-Historie vorliegt (~2–3 Jahre).

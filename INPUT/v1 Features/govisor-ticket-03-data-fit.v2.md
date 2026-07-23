# Feature #3: Data Fit — v2 (engine-verdrahtet)

**Produkt:** goVisor
**Version:** V1
**Status:** Draft (Neufassung von v1, korrigiert gegen den realen Gold-Layer + gemessene Nachfolge-Machbarkeit)
**Erstellt:** 2026-07-19

> **Warum diese Fassung?** Die erste Fassung hatte die beste UX der drei Tickets (Outside/Inside +
> Red-Team-Toggle), war aber greenfield gedacht: Sie versprach reiche Wettbewerbs-Intelligenz
> (Verlust-Raten, Verdrängungs-Bilanzen, Incumbent-Schwächen, saubere mehrjährige Vertragsketten) —
> und stützte fast alles davon auf **`contract_successions`/`contract_chains`** und entity-level
> Aggregation. Beides ist gemessen unzuverlässig: die Ketten-Paarung verbindet bei Großkäufern
> unabhängige Verträge (Incumbent-Rate 7 % = Artefakt), die Entity-Auflösung ist zu 68 % ohne
> verifizierte national_id. Diese Fassung macht die gemessene Datenrealität zur Vorgabe, teilt jede
> KPI nach Machbarkeit ein und erfindet den Wechsel-Score **nicht** neu. Prinzipien wie #1/#2:
> **kein Datenverlust, markieren statt wegwerfen, messen statt annehmen.**

---

## Reality-Check (gemessen, DE-Gold, Stand 2026-07-19)

Verbindliche Vorgaben, keine Randnotiz. Jede KPI in Ticket 3 fällt in eine von drei Ampeln —
**an EINER Bruchlinie: braucht sie eine verlässliche Vertrags-Nachfolge?**

| Ampel | Bedeutung | KPIs |
|-------|-----------|------|
| 🟢 **tragfähig heute** | reine Aggregation über Notices/Entitäten, keine Nachfolge | Buyer-Profil+Adresse+Kontakt, `total_awards`, `top_contractors`, `top_cpvs`, eigene Wins/Track-Record, Incumbent-**Identität** (mit `incumbent_conf`), `active_contractors`, Markt-Aktivität, `market_rank`/`market_share` **nach Win-Zahl**, `trend_yoy` |
| 🟡 **mit Coverage-Flag** | Quelldaten lückenhaft — bauen, aber % mitführen | alles Volumen-basierte (`value_source`-Coverage **55,8 % unbekannt**), `avg_decision_days` (cn→can-Link **58,4 %**, award_date **48 %**), `avg_contract_duration_months` (Laufzeit partiell) |
| 🔴 **erst mit Nachfolge-Modell** | braucht verlässliche Vorgänger-Kette | `loss_rate`, `top_displacers`, `head_to_head`, `user_loss_history`, `incumbent_loyalty`, `market.switch_rate`, `contract_history`-Kette, alle Inside-Risk-Faktoren |

**Nachfolge-Machbarkeit (gemessen an 5.066 Rahmenvertrags-Ankern, gestufter Scorer):**
- **46 %** haben keinen TED-Vorgänger → ehrlich „Erstvergabe / kein Vorgänger".
- **~15 %** sofort eindeutig aus Eckdaten+Titel (CPV+Zeit+Titel-Ähnlichkeit), hohe Präzision, **kein LLM**.
- **~33 %** mehrdeutig → LLM-Adjudikation (≈1.680 Anker) → hebt echte Abdeckung auf **~35 %**.
- Ergebnis: von **7 % Artefakt** auf **~35 % verifizierte Nachfolge** — und jede behauptete stimmt.

> **Konsequenz für 🔴:** Diese KPIs erscheinen **erst mit dem Nachfolge-Modell** und **nur konfidenz-
> gegatet** — hoch = Fakt, niedrig = „geschätzt", nie als blanker Wert. Bis dahin: Sektion mit Hinweis
> „Wettbewerbs-Historie in Aufbau", nicht mit Fiktion füllen.

**Entity-Realität (aus #2, gemessen):** Statistiken aggregieren über `entity_id`. 68 % ohne verifizierte
national_id, Fragmentierung (CANCOM 4×). → Jede Aggregat-KPI trägt **`n` (Fallzahl) + Auflösungs-
Konfidenz**; eine fragmentierte Firma unterzählt Wins. Nach der Entity-Härtung (Stufe 1 committed:
−6.279 Dubletten) auf den **neuen** Stand zeigen.

---

## Kontext

Data Fit ist die **rechte Spalte** im Master-Detail-Layout — alle Infos zu einem Lead auf einen Blick,
aus fünf Perspektiven: **Lead · User · Buyer · Incumbent · Markt**. Zwei Views, automatisch nach
User-Profil gewählt:

| View | Wann | Bedeutung |
|------|------|-----------|
| **Outside** | User ≠ Incumbent | Du willst rein |
| **Inside** | User = Incumbent | Du bist drin |

Toggle nur in Inside → „Wie sehen mich andere?" (Red Team). *(View-Logik unverändert aus v1 — gut.)*

> **Ehrlichkeits-Regel für beide Views:** Der Rahmen (Lead + Buyer + eigene Erfahrung) ist 🟢 und immer
> gefüllt. Die Wettbewerbs-Sektionen (Incumbent-Schwächen, Bedrohungen, Historie) sind 🔴/🟡 und
> erscheinen nur, soweit die Daten sie tragen — sonst mit ehrlichem Platzhalter, nicht geraten.

---

## User Story

> **Als** Anbieter **will ich** alle relevanten Infos zu einem Lead — aus meiner, der Buyer-, der
> Incumbent- und der Markt-Perspektive, **mit ehrlicher Kennzeichnung, wie belastbar jede Zahl ist**,
> **um** fundiert zu entscheiden, ob und wie ich aktiv werde.

---

## View-Logik (unverändert aus v1)

```python
def get_default_view(lead, user_profile):
    return "inside" if lead.incumbent_entity in user_profile.selected_entity_ids else "outside"

def is_toggle_available(lead, user_profile):
    return lead.incumbent_entity in user_profile.selected_entity_ids
```

---

## Akzeptanzkriterien (korrigiert)

| # | Kriterium |
|---|-----------|
| 1 | Lead-Detail erscheint rechts bei Klick |
| 2 | View automatisch: Outside wenn User ≠ Incumbent, Inside wenn User = Incumbent |
| 3 | Toggle (Outside↔Inside) nur in Inside |
| 4 | **Lead-Basis** (🟢): Titel, CPV, Region, Volumen **mit `value_source`+`value_band`** (nicht erfundene Punkt-Konfidenz), Timing **mit `faellig_basis`+`termin_plausibel`**, Vertragsart, Quelle |
| 5 | **Scores**: Relevanz 🎯 + **`leads.displaceability`** ⚡ (Outside) bzw. **dieselbe Zahl, Label „Verlustrisiko"** (Inside). `displaceability = NULL` (31,4 % Einmal-Werk) → **„n/a", kein Ersatzwert** |
| 6 | **User-Perspektive** (🟢): ähnliche Wins, Track Record beim Buyer, regionale Stärke — aus eigenen Wins (#2), Volumen-Angaben mit Coverage-Hinweis |
| 7 | **Buyer-Perspektive**: Profil+Kontakt (🟢), Vergabe-Statistik (🟢 Zählungen / 🟡 `avg_decision_days` mit Coverage), Top-Contractors (🟢, **mit `n`+Konfidenz**) |
| 8 | **Incumbent-Perspektive**: Identität+Profil (🟢, mit `incumbent_conf`), **Verlust-Rate/Schwächen/Head-to-Head nur wenn Nachfolge-Modell aktiv (🔴, konfidenz-gegatet)** |
| 9 | **Bedrohungen (Inside)** (🔴): erst mit Nachfolge-Modell; sonst „Wettbewerbs-Historie in Aufbau" |
| 10 | **Vertragshistorie** (🔴): nur verifizierte Nachfolgen (Konfidenz je Glied aus dem Modell, **nicht** erfunden); unsichere Glieder als „geschätzt" |
| 11 | **Markt**: `active_contractors`/`total_awards` (🟢), `switch_rate` (🔴, erst mit Modell), Marktanteil **nach Win-Zahl** (🟢) — nach Volumen nur mit Coverage (🟡) |
| 12 | Fehlende Daten als „—"/„unbekannt", nie weglassen |
| 13 | **Jede Aggregat-KPI trägt sichtbar Konfidenz/Coverage/`n`** |
| 14 | Link zur Original-Ausschreibung (TED) |

---

## UI/UX

Die Mockups aus v1 (Outside/Inside) bleiben als Layout-Vorlage gültig — **mit diesen Ehrlichkeits-Deltas:**

| v1-Element | Korrektur |
|------------|-----------|
| „Volumen €12M (geschätzt · Konfidenz 0.72)" | **`value_confidence` gibt es nicht.** → „€12M · geschätzt" (`value_source`) + `value_band`; keine erfundene Punkt-Konfidenz |
| „⚡ Wechsel-W. 74 %" immer sichtbar | bei `displaceability=NULL` → **„n/a"**; Zahl = `leads.displaceability`, dazu `score_driver`/`score_support` (nicht ein neues 4-Faktoren-Breakdown) |
| „Schwach in: Bayern, **SAP-Projekte**" | SAP ist **kein CPV** (#2). Schwächen nur über CPV-Klasse/NUTS, und nur 🔴-gegatet |
| „Verliert 28 % seiner Verträge" / Head-to-Head „2:1" | 🔴 — nur mit Nachfolge-Modell, mit Konfidenz; sonst nicht anzeigen |
| Vertragshistorie „2020←2016←2012" mit Konfidenz 0.89/0.92 | Konfidenz kommt **aus dem Nachfolge-Modell**, nicht aus der Luft; nur verifizierte Glieder als Fakt |
| Incumbent „Seit 2020 · Konfidenz 0.89" | ✅ beibehalten — das ist `incumbent_conf`, echtes Feld |

---

## Scores — nicht neu erfinden (Korrektur der Kern-Regression)

**Wechsel-Score ⚡** = `leads.displaceability` (kalibriertes Modell, AUC 0.806, `score_driver`, `score_support`).
- Outside: „Wechsel-Wahrscheinlichkeit". Inside: **dieselbe Zahl, Label „Verlustrisiko"** (hoch = eigenes Risiko).
- `NULL` (Einmal-Werk, 31,4 %) → **„n/a"**; kombiniertes Ranking fällt auf Relevanz (wie #1).
- **Gestrichen ggü. v1:** das eigene `score_breakdown` (incumbent_duration/buyer_loyalty/…) und die separate
  `calculate_risk_score`-Funktion. Beide erfinden ein zweites Modell neben dem kalibrierten — das
  widerspricht #1 („nicht neu erfinden") und produziert den Mockup↔Code-Widerspruch (74 % vs. 26 %).
  Der Inside-„Risiko"-Wert **ist** die invertierte Lesart derselben `displaceability`, kein neues Modell.

**Relevanz 🎯** = identisch zu #1 (CPV-Hierarchie 40 / Region 30 / Volumen 30, unbekanntes Volumen → 50).

---

## Datenmodell

### Bestehend: Gold (darauf zeigen)
`leads`, `entities` (mit `method`/`confidence`), `party_entity` (role=buyer/winner), `dim_cpv`, `notices`.

### Neu: Aggregat-Views — **nach Machbarkeit gegated**

Täglich materialisiert. Jede Kennzahl trägt `n`/Coverage/Konfidenz. Ampel = wann baubar.

#### 🟢 `buyer_stats` (jetzt)
`buyer_entity_id` · `total_awards` · `top_cpvs` · `top_contractors [{entity_id,name,wins,conf}]` ·
🟡 `avg_decision_days` (**+ `decision_days_coverage`**, braucht cn→can-Link) · 🔴 `incumbent_loyalty`
(**erst Nachfolge-Modell** — das ist die Artefakt-Kennzahl selbst) · `calculated_at`.

#### 🟢/🔴 `contractor_stats` (teilweise jetzt)
`entity_id` · `cpv_class` · `total_wins` (🟢) · `total_volume` (🟡 **+ `volume_coverage`**) ·
`market_rank`/`market_share` **nach Win-Zahl** (🟢) · `trend_yoy` (🟢) · 🔴 `loss_rate` · 🔴 `top_displacers`
· `weak_regions`/`weak_cpvs` (🔴 — Underperformance braucht Verlust-Baseline) · `calculated_at`.

#### 🟢/🔴 `market_stats` (teilweise jetzt)
`cpv_class` · `nuts_1` · `active_contractors` (🟢) · `total_awards` (🟢) · `avg_contract_duration_months`
(🟡) · 🔴 `switch_rate` · `calculated_at`.

#### 🔴 `head_to_head`, `user_loss_history`, `buyer_contractor_history.total_losses`
Alle reine Verdrängungs-/Verlust-Kennzahlen → **erst mit Nachfolge-Modell, konfidenz-gegatet.**
`buyer_contractor_history.total_wins`/`last_win_year`/`total_renewals` (🟢) sind sofort baubar.

#### 🔴 `contract_history` (Kette)
Aus dem **Nachfolge-Modell** (Stufe B eindeutig + LLM-adjudiziert), nicht aus `contract_chains`.
`confidence` je Glied = Modell-Konfidenz. **Fix:** `lead_id` ist **VARCHAR** (wie `leads.lead_id`), nicht uuid.
Nur verifizierte Glieder als Fakt; Rest „geschätzt" oder weglassen.

---

## API / Logik

Endpunkte + Response-Struktur wie v1, mit diesen Vertrags-Änderungen:
- `lead.value_source`/`value_band` statt `value_confidence` (Feld gestrichen).
- `scores.switch` = `displaceability` (+ `driver`, `support`); **`null` bei Einmal-Werk**. Kein `score_breakdown`.
- `scores.risk` entfällt als eigenes Feld — Inside rendert `switch` mit invertiertem Label.
- Jede `stats`-Sektion bekommt `coverage`/`n`/`confidence`-Felder.
- `threats`, `incumbent.weaknesses`, `contract_history`, `head_to_head` = **`null`, solange Nachfolge-Modell
  inaktiv** (Client zeigt „in Aufbau"), danach konfidenz-gegatet.

---

## Edge Cases (ergänzt)

| # | Case | Verhalten |
|---|------|-----------|
| 1–14 | *(wie v1: User=Incumbent, Erstausschreibung, Konfidenz<0.5, dünner Buyer, keine Wins, kein H2H …)* | *unverändert* |
| 15 | **`displaceability = NULL`** (Einmal-Werk, 31,4 %) | Score „n/a"; Inside-Risiko „n/a"; kein Ersatzwert |
| 16 | **Volumen unbekannt** (55,8 %) | „€ —" + Badge; Deal-Listen mit „nur X % mit Volumen" |
| 17 | **Nachfolge-Modell inaktiv / unter Schwelle** | Wettbewerbs-Sektion „Historie in Aufbau", keine Fiktion |
| 18 | **Buyer/Incumbent-Entity fragmentiert** (niedrige Konfidenz) | Statistik mit „Auflösung unsicher — Wins evtl. unterzählt" |
| 19 | **`avg_decision_days` unter Coverage** | „Vergabedauer: begrenzte Daten (X %)" |

---

## Out of Scope

Handlungsempfehlungen · Partner-Empfehlung · Ähnliche-Leads-Cluster · Wettbewerber-Deep-Dive ·
externe Buyer-Anreicherung → **V2**. Briefing-Export → **#8 Auto-Dossier**.
Nachfolge-**Modelltraining** (Scorer + LLM-Stufe) → eigener Gold-Builder-Task (siehe Abhängigkeiten);
hier nur **konsumiert**.

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| Gold `leads`, `entities`, `party_entity`, `dim_cpv` | ✅ existiert |
| User-Profil mit `selected_entity_ids` | #2 |
| Entity-Härtung (Stufe 1: −6.279 Dubletten) | ✅ committed |
| 🟢 `buyer_stats`/`contractor_stats`/`market_stats` (Nicht-🔴-Felder) | ⬜ Neubau (jetzt baubar) |
| **Nachfolge-Modell** (Eckdaten-Filter → Titel-Score → LLM-Adjudikation, konfidenz-tragend) | ⬜ **Blocker für alle 🔴-KPIs** |
| `head_to_head`/`user_loss_history`/`contract_history`/`switch_rate`/`loss_rate` | ⬜ nach Nachfolge-Modell |
| Auth | ⬜ vorher nötig |

---

## Testfälle (ergänzt)

v1-Testfälle 1–16 bleiben. Neu:
| # | Test | Erwartung |
|---|------|-----------|
| 17 | Einmal-Werk-Lead | Wechsel-Score „n/a", kein Breakdown |
| 18 | Volumen unbekannt | „€ —" + Coverage-Badge |
| 19 | Nachfolge-Modell inaktiv | Wettbewerbs-Sektion „in Aufbau", keine Kette gezeigt |
| 20 | Fragmentierter Incumbent | „Auflösung unsicher" + `n` sichtbar |
| 21 | Inside-Risiko | = invertierte `displaceability`, gleiche Zahl wie Outside |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | Zeitraum Statistiken | 5 Jahre |
| 2 | Vertragshistorie-Tiefe | 5 Vorgänger, aber nur verifizierte |
| 3 | Marktanteil ab wie vielen Wins | ab 3 |
| 4 | Materialisierung | täglich |
| 5 | Nachfolge-Schwelle: ab welcher Modell-Konfidenz „Fakt"? | zu kalibrieren an der LLM-Stichprobe (vor Gold-Festschreibung) |
| 6 | 🔴-KPIs vor Nachfolge-Modell zeigen? | **nein** — „in Aufbau" statt Fiktion |
| 7 | Risiko-Score-Schwellen (Farbe) | <20 grün / 20–40 gelb / >40 rot — auf `displaceability` |

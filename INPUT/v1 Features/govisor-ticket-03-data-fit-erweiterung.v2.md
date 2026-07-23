# Feature #3: Data Fit — Erweiterung (Potential Fit Integration) — v2 (engine-verdrahtet)

**Bezug:** govisor-ticket-03-data-fit.v2.md  
**Status:** Draft (Neufassung, korrigiert gegen den realen Gold-Layer)  
**Erstellt:** 2026-07-19

> **Warum diese Erweiterung?** Ticket #3 v2 deckt die fünf Perspektiven ab (Lead, User, Buyer, 
> Incumbent, Markt), aber es fehlt der **direkte Vergleich** zwischen User und Incumbent sowie
> der **Anforderungs-Match** gegen das User-Profil. Diese Erweiterung integriert "Potential Fit"
> in das bestehende Lead-Detail, statt ein separates Ticket zu erstellen.

---

## Korrekturen gegen den realen Gold-Layer (gemessen 2026-07-19)

Verbindlich. Die Erweiterung ist gut ampel-verdrahtet; diese fünf Punkte müssen aber sitzen,
sonst zeigen 🟢-Sektionen Zahlen, die die Tabellen nicht hergeben.

| # | Befund (gemessen) | Konsequenz |
|---|-------------------|------------|
| K1 | **KORRIGIERT (2026-07-19):** `leads`/`notices` haben nur `cpv_main` — **ABER** die volle Mehr-CPV-Liste liegt bereits typisiert in **`silver/notice_cpv`** (3,5 M Zeilen: `notice_id, cpv_code, is_main`; Ø 1,92 CPVs/Notice). | Anforderungs-Match nutzt **`notice_cpv` join auf `lead_id`** (= `notice_id`) für ALLE Lead-CPVs. Kein Pipeline-Task nötig. „2 von 3 CPVs" ist **sofort möglich**. |
| K2 | **`party_entity` hat kein `lead_id`** (nur `notice_id, role, seq, entity_id`); `leads.lead_id` **ist** eine `notice_id`. | Der Join `party_entity pe ON l.lead_id = pe.lead_id` ist kaputt. Und **unnötig**: `leads.incumbent_entity` trägt den Gewinner direkt → `leads WHERE incumbent_entity IN user_entities AND contract_end > :as_of`. |
| K3 | `contractor_stats` ist **pro (entity_id, cpv_class)** + 5-Jahres-Fenster. Ein User hat u. U. **mehrere** Entitäten (Gruppe, #2). | market_share/trend über mehrere User-Entitäten = **Wins erst summieren, dann Anteil** — nicht Shares mitteln. |
| K4 | Region-Wins brauchen winner→notice→`performance_nuts` (**65 % befüllt**); `party_entity` trägt **kein NUTS**. | `wins_in_region` mit **Coverage-Flag**; fehlendes NUTS ≠ 0 Wins. |
| K5 | Cert-Anforderungen stehen im **CN (F02)**, nicht im Win (CAN). Link via `ref_publication_number` (**58,4 %**, #2). | `get_implied_certifications` muss den **cn→can-Link** fahren, nicht `get_f02_requirements(win.notice_id)` direkt. |

**Durchgängig (wie #1/#2):** Jede Vergleichs-Statistik trägt **`n` + Auflösungs-Konfidenz**. Bei
fragmentiertem Incumbent (z. B. DB Netz ↔ DB InfraGO) ist „5 Wins" ein **Floor** — das gehört sichtbar
gemacht, nicht nur als Edge Case.

---

## Neue Sektionen im Lead-Detail

| Sektion | Frage | Ampel |
|---------|-------|-------|
| **Direktvergleich** | Wie stehe ich vs. Incumbent? | 🟢 |
| **Anforderungs-Match** | Erfülle ich die Anforderungen? | 🟢 |
| **Lücken-Analyse** | Was fehlt mir? | 🟢 |
| **Laufende Verträge** | Bin ich schon beim Buyer aktiv? | 🟢 |
| **Zertifizierungs-Vergleich** | Wer hat welche Qualifikationen? | 🟡 |

---

## 1. Direktvergleich: User vs. Incumbent

### Kontext

Der User will wissen: **Bin ich besser aufgestellt als der Incumbent?**

### Datenquellen

| Metrik | Quelle | Ampel |
|--------|--------|-------|
| Wins bei diesem Buyer | `party_entity` (role=winner) × Buyer | 🟢 |
| Wins in diesem CPV-Segment | `party_entity` × CPV-Klasse | 🟢 |
| Wins in dieser Region | `party_entity` × NUTS | 🟢 |
| Marktanteil (nach Wins) | `contractor_stats.market_share` | 🟢 |
| Trend YoY | `contractor_stats.trend_yoy` | 🟢 |
| Laufende Verträge beim Buyer | `leads` mit `contract_end > heute` | 🟢 |
| Head-to-Head Bilanz | Verdrängungen | 🔴 (Nachfolge-Modell) |

### UI

```
DIREKTVERGLEICH
─────────────────────────────────────────────────────────────

                        DU          BECHTLE      
                        
Wins bei BMI            2           5            ⬅
Wins in Cloud (72212)   34          47           ⬅
Wins bei Bund           12          23           ⬅
Marktanteil             8%          12%          ⬅
Trend                   ↗ +15%      ↘ -3%        ➡
Laufende bei BMI        1           2            ⬅

─────────────────────────────────────────────────────────────
Legende: ➡ Vorteil Du · ⬅ Vorteil Incumbent · — Gleich
```

### Logik

```python
def side(entities, lead):
    # K3: über mehrere Entitäten Wins ERST summieren, dann Anteil — nie Shares mitteln.
    # market_share = Σ wins(entities, cpv_class) / Σ wins(alle, cpv_class) aus contractor_stats-Basis.
    # wins_in_region: winner→notice→performance_nuts (K4, 65 % Coverage) → region_coverage mitgeben.
    return {
        "wins_at_buyer": count_wins(entities, buyer=lead.buyer_entity),
        "wins_in_cpv": count_wins(entities, cpv_class=lead.cpv_class),
        "wins_in_region": count_wins(entities, nuts_prefix=nuts1(lead.buyer_nuts)),
        "region_coverage": region_nuts_coverage(lead.cpv_class),      # K4
        "market_share": aggregate_market_share(entities, lead.cpv_class),  # K3: wins-first
        "trend_yoy": aggregate_trend(entities, lead.cpv_class),
        "active_contracts_at_buyer": active_contracts(entities, lead.buyer_entity),  # leads.incumbent_entity, K2
        "resolution_conf": min_resolution_conf(entities),            # Konfidenz/Floor sichtbar
    }

def build_comparison(lead, user_entities, incumbent_entity):
    return {
        "user": side(user_entities, lead),
        # Incumbent evtl. fragmentiert → Wins sind ein FLOOR; resolution_conf macht das sichtbar.
        "incumbent": side([incumbent_entity], lead) | {"conf": lead.incumbent_conf},
        # Head-to-Head nur wenn Nachfolge-Modell aktiv (jetzt: contract_succession vorhanden),
        # und nur konfidenz-gegatet.
        "head_to_head": get_head_to_head(user_entities, incumbent_entity) if succession_model_active() else None
    }
```

### Edge Cases

| Case | Verhalten |
|------|-----------|
| Kein Incumbent (Erstausschreibung) | Sektion "Direktvergleich" ausblenden, stattdessen "Offenes Feld" |
| User = Incumbent | Sektion ausblenden (Inside View zeigt andere Infos) |
| Incumbent-Entity fragmentiert | "Daten unvollständig – Incumbent evtl. unterzählt" |
| User hat 0 Wins in Kategorie | "0" anzeigen, nicht verstecken |

---

## 2. Anforderungs-Match

### Kontext

Der User will wissen: **Erfülle ich die Anforderungen dieser Ausschreibung?**

### Match-Dimensionen

| Dimension | Lead-Feld | Profil-Feld | Match-Logik |
|-----------|-----------|-------------|-------------|
| CPV | **`silver/notice_cpv`** (alle CPVs des Leads, join auf `notice_id`) | `cpv_codes[]`, `cpv_classes[]` | Exakt oder Klassen-Match |
| Region | `buyer_nuts` | `nuts_regions[]` | Exakt oder Parent-Match |
| Volumen | `value_real_2020`, `value_band` | `volume_min`, `volume_max` | In Range oder ±1 Band |
| Vertragsart | `contract_kind` | — | Info, kein Match |

> **K1 (korrigiert):** Alle Lead-CPVs kommen aus `notice_cpv` (join `notice_id`=`lead_id`) — die
> Mehr-CPV-Ansicht („2 von 3 CPVs") ist **sofort** möglich. Labels aus `dim_cpv_label` (9.454 Codes, 97 % Coverage).

### UI

```
ANFORDERUNGS-CHECK
─────────────────────────────────────────────────────────────

CPV-Match
✓ 72212 Cloud & Managed Services      In deinem Profil
✓ 72310 Datenverarbeitung            In deinem Profil
✗ 48440 SAP                          NICHT in deinem Profil

Region-Match
✓ Bund                               In deinem Profil

Volumen-Match
✓ €12M                               In deiner Range (€2M – €50M)

Ergebnis: 2 von 3 CPVs · Region ✓ · Volumen ✓
```

### Logik

```python
def check_requirements(lead, user_profile):
    # CPV-Match — alle Lead-CPVs aus notice_cpv (K1 korrigiert: sofort verfügbar)
    cpv_results = []
    all_lead_cpvs = get_notice_cpvs(lead.lead_id)   # SELECT cpv_code FROM notice_cpv WHERE notice_id=lead_id
    
    for cpv in all_lead_cpvs:
        match_type = None
        if cpv in user_profile.cpv_codes:
            match_type = "exact"
        elif cpv_class(cpv) in user_profile.cpv_classes:
            match_type = "class"
        
        cpv_results.append({
            "cpv": cpv,
            "label": get_cpv_label(cpv),
            "match": match_type is not None,
            "match_type": match_type
        })
    
    # Region-Match
    region_match = (
        lead.buyer_nuts in user_profile.nuts_regions or
        (user_profile.is_federal and is_federal_buyer(lead)) or
        nuts_parent(lead.buyer_nuts) in user_profile.nuts_regions
    )
    
    # Volumen-Match
    if lead.value_source == 'unbekannt':
        volume_match = None  # Unbekannt
    elif user_profile.volume_min <= lead.value_real_2020 <= user_profile.volume_max:
        volume_match = True
    elif within_one_band(lead.value_band, user_profile):
        volume_match = "partial"
    else:
        volume_match = False
    
    return {
        "cpv": cpv_results,
        "cpv_match_count": sum(1 for c in cpv_results if c["match"]),
        "cpv_total": len(cpv_results),
        "region": {
            "lead_region": lead.buyer_nuts,
            "match": region_match
        },
        "volume": {
            "lead_value": lead.value_real_2020,
            "lead_band": lead.value_band,
            "lead_source": lead.value_source,
            "match": volume_match
        }
    }
```

---

## 3. Lücken-Analyse

### Kontext

Aus dem Anforderungs-Match ergeben sich **Lücken** – was der User nicht abdeckt.

### UI

```
LÜCKEN
─────────────────────────────────────────────────────────────

⚠️ CPV 48440 (SAP) wird gefordert, fehlt in deinem Profil.

Optionen:
• Profil erweitern (wenn du SAP kannst)
• Partner suchen (V2)
```

### Logik

```python
def identify_gaps(requirements_check, user_profile):
    gaps = []
    
    # CPV-Lücken
    for cpv in requirements_check["cpv"]:
        if not cpv["match"]:
            gaps.append({
                "type": "cpv",
                "cpv": cpv["cpv"],
                "label": cpv["label"],
                "suggestion": "Profil erweitern oder Partner suchen"
            })
    
    # Region-Lücke
    if not requirements_check["region"]["match"]:
        gaps.append({
            "type": "region",
            "region": requirements_check["region"]["lead_region"],
            "suggestion": "Neue Region für dich"
        })
    
    # Volumen-Lücke
    if requirements_check["volume"]["match"] == False:
        gaps.append({
            "type": "volume",
            "lead_value": requirements_check["volume"]["lead_value"],
            "suggestion": "Außerhalb deiner typischen Deal-Größe"
        })
    
    return gaps
```

---

## 4. Laufende Verträge beim Buyer

### Kontext

Der User will wissen: **Bin ich schon bei diesem Buyer aktiv?**

Das ist ein starkes Signal:
- Beziehung existiert bereits
- Kenntnis der internen Prozesse
- Mögliche Cross-Selling-Chance

### Datenquelle

```sql
-- KORRIGIERT (K2): kein party_entity-Join nötig — leads.incumbent_entity IST der Gewinner.
-- as_of = derselbe Stichtag wie build_leads (nicht CURRENT_DATE), sonst inkonsistent.
SELECT *
FROM leads l
WHERE l.incumbent_entity IN (user_selected_entities)
  AND l.buyer_entity = :current_lead_buyer
  AND l.contract_end > :as_of
ORDER BY l.contract_end ASC
```

### UI

```
LAUFENDE VERTRÄGE BEI BMI
─────────────────────────────────────────────────────────────

Du bist bereits aktiv bei diesem Buyer:

• IT-Beratung         €2M    läuft bis 2025    
• Netzwerk-Betrieb    €4M    läuft bis 2026    

→ 2 aktive Verträge – du kennst den Buyer ✓
```

Wenn keine:

```
LAUFENDE VERTRÄGE BEI BMI
─────────────────────────────────────────────────────────────

Keine laufenden Verträge bei diesem Buyer.

Aber: 4 abgeschlossene Verträge in der Vergangenheit.
      Letzter: 2022 (IT-Beratung)
```

### Logik

```python
def get_active_contracts_at_buyer(user_entities, buyer_entity):
    active = query_active_contracts(user_entities, buyer_entity)
    past = query_past_contracts(user_entities, buyer_entity) if not active else None
    
    return {
        "active": [
            {
                "title": c.title,
                "volume": c.value_real_2020,
                "volume_source": c.value_source,
                "ends": c.contract_end,
            }
            for c in active
        ],
        "past_count": len(past) if past else 0,
        "last_past": past[0] if past else None,
        "relationship_exists": len(active) > 0 or (past and len(past) > 0)
    }
```

---

## 5. Zertifizierungs-Vergleich

### Kontext

Der User will wissen: **Habe ich die nötigen Qualifikationen? Hat der Incumbent mehr?**

### Datenquellen

| Wer | Quelle | Logik |
|-----|--------|-------|
| User | `user_certifications` (manuell) | Direkt aus Profil |
| User | Wins (impliziert) | "Du hast X gewonnen, das Y forderte → du hast Y" |
| Incumbent | Wins (impliziert) | Dieselbe Logik |
| Lead-Anforderung | F02 Eignungskriterien | ⚠️ Freitext, Extraktion nötig |

### Ampel

| Teil | Ampel | Grund |
|------|-------|-------|
| User-Zertifizierungen (manuell) | 🟢 | Aus Profil |
| User-Zertifizierungen (impliziert) | 🟡 | Braucht Aggregation über Wins |
| Incumbent-Zertifizierungen (impliziert) | 🟡 | Dieselbe Logik |
| Lead-Anforderungen | 🟡 | F02-Extraktion nötig (NLP/LLM auf Freitext) |

### Implikations-Logik

```python
def get_implied_certifications(entity_ids):
    """
    Für jede gewonnene Ausschreibung (CAN):
    - Verlinke sie mit IHRER Bekanntmachung (CN/F02) via ref_publication_number (58,4 %, #2)
    - Die Eignungskriterien stehen im CN, NICHT im CAN (K5)
    - Der Gewinner erfüllt sie implizit — konfidenzbehaftet (Link × Extraktion)
    """
    implied = {}                                   # cert -> max Konfidenz
    for win in get_wins_as_can(entity_ids):
        cn = link_cn(win.ref_publication_number)   # 58,4 % verknüpfbar; sonst kein Signal
        if not cn:
            continue
        for req in extract_cert_reqs(cn):          # F02-LEFTI/SelectionCriteria-Extraktion
            conf = req.extract_conf * cn.link_conf * win.winner_conf
            implied[req.cert] = max(implied.get(req.cert, 0), conf)
    return implied                                 # je Cert höchste Konfidenz (recall-first, #2)
```

### UI

```
ZERTIFIZIERUNGEN
─────────────────────────────────────────────────────────────

                        DU          BECHTLE      GEFORDERT
                        
ISO 27001               ✓ (Profil)  ✓ (Win)     ✓
BSI C5                  ✓ (Win)     ✓ (Win)     ✓
ISO 9001                ✓ (Profil)  —           —
SAP-Zertifiziert        —           ✓ (Win)     ✓

─────────────────────────────────────────────────────────────
⚠️ Dir fehlt: SAP-Zertifizierung (vom Lead gefordert)
```

### Abhängigkeit

Diese Sektion braucht:
1. **F02-Eignungskriterien-Extraktion** (Freitext → strukturiert)
2. **Zertifizierungs-Taxonomie** (ISO 27001, BSI C5, etc.)

**Vorschlag:** V1 nur mit manuellen User-Zertifizierungen. V2 mit Implikation + F02-Extraktion.

---

## Datenmodell-Ergänzungen

### `active_contracts` (View, nicht materialisiert)

```sql
-- KORRIGIERT (K2): incumbent_entity ist der Gewinner; kein party_entity-Join.
CREATE VIEW active_contracts AS
SELECT
    l.lead_id,
    l.titel AS title,
    l.buyer_entity,
    l.value_real_2020,
    l.value_source,
    l.contract_end,
    l.incumbent_entity AS contractor_entity,
    l.incumbent_conf   AS contractor_conf   -- Auflösungs-Konfidenz mitführen
FROM leads l
WHERE l.contract_end > :as_of;
```

### `implied_certifications` (materialisiert, täglich) — V2

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `entity_id` | string | PK |
| `certification_type` | string | ISO_27001, BSI_C5, etc. |
| `source` | enum | 'manual', 'implied_from_win' |
| `win_notice_id` | string | Bei implied: welcher Win |
| `confidence` | decimal | Bei implied: Extraktions-Konfidenz |

### `f02_requirements` (materialisiert) — V2

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `notice_id` | string | PK |
| `certifications_required` | string[] | Extrahierte Zertifizierungen |
| `min_revenue` | decimal | Mindest-Umsatz (nullable) |
| `min_employees` | int | Mindest-Mitarbeiter (nullable) |
| `reference_requirements` | text | Referenz-Anforderungen |
| `extraction_confidence` | decimal | NLP/LLM Konfidenz |

---

## API-Ergänzungen

### Response-Erweiterung (GET /api/leads/:id)

```json
{
  "lead": { ... },
  "scores": { ... },
  "user_perspective": { ... },
  "buyer": { ... },
  "incumbent": { ... },
  "market": { ... },
  
  "comparison": {
    "user": {
      "wins_at_buyer": 2,
      "wins_in_cpv": 34,
      "wins_in_region": 12,
      "market_share": 0.08,
      "trend_yoy": 0.15,
      "active_contracts_at_buyer": 1
    },
    "incumbent": {
      "wins_at_buyer": 5,
      "wins_in_cpv": 47,
      "wins_in_region": 23,
      "market_share": 0.12,
      "trend_yoy": -0.03,
      "active_contracts_at_buyer": 2
    },
    "head_to_head": null
  },
  
  "requirements_check": {
    "cpv": [
      {"cpv": "72212", "label": "Cloud", "match": true},
      {"cpv": "72310", "label": "Datenverarbeitung", "match": true},
      {"cpv": "48440", "label": "SAP", "match": false}
    ],
    "cpv_match_count": 2,
    "cpv_total": 3,
    "region": {"lead_region": "DE", "match": true},
    "volume": {"lead_value": 12000000, "match": true}
  },
  
  "gaps": [
    {"type": "cpv", "cpv": "48440", "label": "SAP"}
  ],
  
  "active_contracts_at_buyer": {
    "active": [
      {"title": "IT-Beratung", "volume": 2000000, "ends": "2025-06-30"}
    ],
    "past_count": 3,
    "relationship_exists": true
  },
  
  "certifications": null
}
```

---

## Akzeptanzkriterien (Ergänzung zu #3 v2)

| # | Kriterium |
|---|-----------|
| 15 | **Direktvergleich** (🟢): Tabelle User vs. Incumbent mit Wins, Marktanteil, Trend |
| 16 | **Anforderungs-Match** (🟢): CPV/Region/Volumen Check gegen User-Profil |
| 17 | **Lücken** (🟢): Fehlende CPVs/Regionen hervorheben |
| 18 | **Laufende Verträge** (🟢): Aktive Contracts beim Buyer anzeigen |
| 19 | **Zertifizierungen** (🟡): V1 nur manuell; V2 mit Implikation + F02-Extraktion |
| 20 | Direktvergleich nur in Outside View (nicht bei Erstausschreibung, nicht in Inside) |
| 21 | Laufende Verträge in beiden Views (Outside + Inside) |

---

## Edge Cases (Ergänzung)

| # | Case | Verhalten |
|---|------|-----------|
| 22 | Erstausschreibung (kein Incumbent) | Direktvergleich ausblenden, "Offenes Feld – kein Incumbent" |
| 23 | User = Incumbent (Inside View) | Direktvergleich ausblenden |
| 24 | Alle CPVs matchen | "Vollständiger CPV-Match ✓" |
| 25 | Keine CPVs matchen | "⚠️ Kein CPV-Match – neues Segment" |
| 26 | Volumen unbekannt | "Volumen-Match: nicht prüfbar (Volumen unbekannt)" |
| 27 | Keine laufenden Verträge, aber vergangene | Vergangene anzeigen mit "Letzter: [Jahr]" |
| 28 | Keine Verträge bei Buyer (nie) | "Neuer Buyer für dich" |
| 29 | Lead hat keine zusätzlichen CPVs | Nur `cpv_main` prüfen |

---

## Testfälle (Ergänzung)

| # | Test | Erwartung |
|---|------|-----------|
| 22 | Lead mit Incumbent, Outside View | Direktvergleich-Tabelle sichtbar |
| 23 | Lead ohne Incumbent | Direktvergleich ausgeblendet, "Offenes Feld" |
| 24 | User = Incumbent (Inside View) | Direktvergleich ausgeblendet |
| 25 | Alle CPVs im Profil | Alle grün, "Vollständiger Match" |
| 26 | CPV fehlt im Profil | Rot markiert, in Lücken-Sektion |
| 27 | User hat laufenden Vertrag beim Buyer | Sektion zeigt aktive Verträge |
| 28 | User hat keinen Vertrag beim Buyer | "Neuer Buyer" oder vergangene anzeigen |
| 29 | Volumen unbekannt | "Nicht prüfbar" statt Match/Mismatch |

---

## Offene Fragen (Ergänzung)

| # | Frage | Vorschlag |
|---|-------|-----------|
| 8 | F02-Extraktion: V1 oder V2? | V2 (Aufwand NLP/LLM) |
| 9 | Zertifizierungs-Implikation: V1 oder V2? | V2 (braucht F02-Extraktion) |
| 10 | Lücken: Partner-Empfehlung zeigen? | V2 (Partner Fit Feature) |
| 11 | Direktvergleich: Head-to-Head zeigen wenn verfügbar? | Ja, aber 🔴-gegatet (Nachfolge-Modell) |

---

## Zusammenfassung

| Sektion | V1 | V2 |
|---------|----|----|
| Direktvergleich (Wins, Marktanteil, Trend) | ✅ | + Head-to-Head |
| Anforderungs-Match (CPV, Region, Volumen) | ✅ | — |
| Lücken-Analyse | ✅ | + Partner-Empfehlung |
| Laufende Verträge beim Buyer | ✅ | — |
| Zertifizierungs-Vergleich | ◐ (nur manuell) | ✅ (Implikation + F02) |

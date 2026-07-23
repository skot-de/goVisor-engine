# goVisor Data Engine – Konzeptdokument v2.0

**Ziel:** Aufbau einer Analyse-Engine, die 20+ Jahre öffentliche Vergabedaten (TED) lädt, strukturiert, anreichert, qualitätsbewertet und Muster extrahiert – als Grundlage für validierte Wechsel-Prognosen.

**Datum:** Januar 2026  
**Autor:** Sven / Claude  
**Für:** Claude Code Implementation

---

## Inhaltsverzeichnis

1. [Übersicht & Architektur](#1-übersicht--architektur)
2. [Datenquellen](#2-datenquellen)
3. [Drei-Schichten-Modell](#3-drei-schichten-modell)
4. [Schicht 1: Raw Import](#4-schicht-1-raw-import)
5. [Schicht 2: LLM Extraction](#5-schicht-2-llm-extraction)
6. [Schicht 3: Normalized Data](#6-schicht-3-normalized-data)
7. [Quality Scoring System](#7-quality-scoring-system)
8. [Contract Chain Building](#8-contract-chain-building)
9. [Analyse-Queries](#9-analyse-queries)
10. [Human-in-the-Loop Workflow](#10-human-in-the-loop-workflow)
11. [Technische Anforderungen](#11-technische-anforderungen)
12. [Implementierungs-Phasen](#12-implementierungs-phasen)

---

## 1. Übersicht & Architektur

### Das Problem

TED-Daten sind:
- Über 20 Jahre gewachsen (verschiedene Schema-Versionen)
- Inkonsistent befüllt (gleiche Felder, andere Nutzung)
- Kritische Infos im Freitext versteckt
- Ohne Qualitätskontrolle

### Die Lösung

```
┌─────────────────────────────────────────────────────────────┐
│  SCHICHT 1: RAW                                             │
│  raw_notices_cn, raw_notices_can                            │
│  → 1:1 aus TED CSV                                          │
│  → Alle ~80 Felder                                          │
│  → Quality Score: Completeness                              │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SCHICHT 2: EXTRACTED                                       │
│  extracted_notices                                          │
│  → LLM liest Freitext                                       │
│  → Strukturiert: Duration, Tech, Extensions                 │
│  → Quality Score: Extraction Confidence                     │
│  → Human Review für unsichere Fälle                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SCHICHT 3: NORMALIZED                                      │
│  buyers, suppliers, contracts, contract_chains              │
│  → Merge aus RAW + EXTRACTED                                │
│  → Quality Score: Comprehensive (5 Dimensionen)             │
│  → Analysefähig                                             │
└─────────────────────────────────────────────────────────────┘
```

### Warum drei Schichten?

| Vorteil | Erklärung |
|---------|-----------|
| **Debugging** | Bei Fehlern: Zurück zu Raw |
| **Reproduzierbarkeit** | Raw unverändert, Transformationen dokumentiert |
| **Qualitätskontrolle** | Quality Score auf jeder Ebene |
| **Human Review** | Extraction separat prüfbar |
| **Flexibilität** | Verschiedene Normalisierungen möglich |

---

## 2. Datenquellen

### 2.1 Primär: TED (Tenders Electronic Daily)

| Parameter | Wert |
|-----------|------|
| Zeitraum | 2004-01-01 bis heute |
| Länder | Deutschland (DE) – erweiterbar auf EU |
| Notice Types | Contract Notices (CN), Contract Award Notices (CAN), VEAT |
| Format | CSV (strukturiert) + Freitext-Felder |
| Geschätztes Volumen | 2-3 Millionen Records (DE) |
| Quelle | https://data.europa.eu/euodp/en/data/dataset/ted-csv |

### 2.2 Schema-Evolution beachten

| Zeitraum | XSD Version | Besonderheiten |
|----------|-------------|----------------|
| 2004-2008 | 2.0.5 | Niedrige Qualität, wenige Felder |
| 2009-2015 | 2.0.8 | Besser, aber viele Lücken |
| 2016-2022 | 2.0.9 | Lot-Level Daten, mehr Felder |
| 2022+ | eForms | Komplett neues Schema |

### 2.3 Sekundär (Phase 2)

| Quelle | Daten | Zweck |
|--------|-------|-------|
| Destatis | BIP, Inflation | Wirtschafts-Kontext |
| Bundesregierung.de | Kabinette, Minister | Politik-Kontext |
| Wikipedia | Wahlen, Regierungen | Zyklen |
| BSI | Security-Vorfälle | Event-Trigger |

---

## 3. Drei-Schichten-Modell

### Datenfluss

```
TED CSV Files (2006-2025)
         │
         ▼
┌─────────────────────────────────────┐
│  Step 1: Raw Import                 │
│  CSV → raw_notices_cn               │
│  CSV → raw_notices_can              │
│  + quality_score_raw berechnen      │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Step 2: LLM Extraction             │
│  Freitext → extracted_notices       │
│  + quality_score_extracted          │
│  + Human Review Queue               │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Step 3: Entity Resolution          │
│  raw + extracted → buyers           │
│  raw + extracted → suppliers        │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Step 4: Normalization + Merge      │
│  raw + extracted → contracts        │
│  + quality_score_final (5 Dim.)     │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Step 5: Chain Building             │
│  contracts → contract_chains        │
│  + Incumbent Analysis               │
└─────────────────────────────────────┘
```

---

## 4. Schicht 1: Raw Import

### 4.1 Alle TED CSV-Felder (vollständig)

**WICHTIG: Alle Felder 1:1 importieren, nichts weglassen.**

#### Notice Metadata

```sql
id_notice_cn TEXT,                    -- Unique ID Contract Notice
id_notice_can TEXT,                   -- Unique ID Contract Award Notice
ted_notice_url TEXT,                  -- URL zur Notice
year INT,                             -- Publikationsjahr
id_type TEXT,                         -- Standard Form Nummer
directive TEXT,                       -- Directive (bei VEAT)
dt_dispatch DATE,                     -- Versanddatum
xsd_version TEXT,                     -- Schema Version (2.0.5-2.0.9)
cancelled BOOLEAN,                    -- Storniert?
corrections INT,                      -- Anzahl Korrekturen
future_can_id TEXT,                   -- Link zum folgenden CAN ← GOLD!
future_can_id_estimated BOOLEAN,      -- ID korrigiert?
```

#### Contracting Authority / Entity

```sql
b_multiple_cae BOOLEAN,               -- Mehrere Auftraggeber?
cae_name TEXT,                        -- Offizieller Name
cae_nationalid TEXT,                  -- VAT/Registernummer
cae_address TEXT,                     -- Adresse
cae_town TEXT,                        -- Stadt
cae_postal_code TEXT,                 -- PLZ
iso_country_code TEXT,                -- Land
b_multiple_country BOOLEAN,           -- Mehrere Länder?
iso_country_code_all TEXT,            -- Alle Länder
cae_type TEXT,                        -- Typ (1,3,4,5,6,8,N,R,Z)
eu_inst_code TEXT,                    -- EU Institution Code
main_activity TEXT,                   -- COFOG Haupttätigkeit
```

#### Procedure & Contract Info

```sql
b_on_behalf BOOLEAN,                  -- Zentrale Beschaffung?
b_involves_joint_procurement BOOLEAN, -- Gemeinsame Beschaffung?
b_awarded_by_central_body BOOLEAN,    -- Zentrale Vergabestelle?
type_of_contract TEXT,                -- W/U/S (Works/Supplies/Services)
tal_location_nuts TEXT,               -- NUTS Code Ort
b_fra_agreement BOOLEAN,              -- Framework Agreement?
fra_estimated TEXT,                   -- Framework Hinweise (K/C/A)
b_fra_single_operator BOOLEAN,        -- Single Operator Framework?
fra_number_operators INT,             -- Anzahl Framework-Teilnehmer
fra_number_max_operators INT,         -- Max Teilnehmer
b_dyn_purch_syst BOOLEAN,             -- Dynamic Purchasing System?
cpv TEXT,                             -- Haupt-CPV Code
additional_cpv TEXT,                  -- Weitere CPV Codes
b_gpa BOOLEAN,                        -- GPA covered?
lots_number INT,                      -- Anzahl Lose
lots_submission TEXT,                 -- A/O/M (All/One/Multiple)
top_type TEXT,                        -- Verfahrensart
b_accelerated BOOLEAN,                -- Beschleunigt?
out_of_directives TEXT,               -- Außerhalb Directive?
```

#### Values & Duration

```sql
value_euro NUMERIC,                   -- Wert EUR
value_euro_fin_1 NUMERIC,             -- Bereinigter Wert
value_euro_fin_2 NUMERIC,             -- Manuell korrigiert
b_options BOOLEAN,                    -- Optionen?
b_eu_funds BOOLEAN,                   -- EU-Finanzierung?
b_renewals BOOLEAN,                   -- Verlängerbar?
duration TEXT,                        -- Laufzeit (RAW, nicht interpretiert!)
contract_start DATE,                  -- Start
contract_completion DATE,             -- Ende
```

#### Award Criteria

```sql
crit_code TEXT,                       -- L/M (Lowest/MEAT)
crit_price_weight TEXT,               -- Preis-Gewichtung
crit_criteria TEXT,                   -- Kriterien-Text
crit_weights TEXT,                    -- Gewichtungs-Text
b_electronic_auction BOOLEAN,         -- E-Auktion?
b_variants BOOLEAN,                   -- Varianten?
```

#### Submission Details

```sql
env_operators INT,                    -- Geplante Anbieter
env_min_operators INT,                -- Minimum
env_max_operators INT,                -- Maximum
number_awards INT,                    -- Anzahl Awards
dt_applications DATE,                 -- Einreichungsfrist
b_language_any_ec BOOLEAN,            -- Alle EU-Sprachen?
admin_languages_tender TEXT,          -- Erlaubte Sprachen
b_recurrent_procurement BOOLEAN,      -- Wiederkehrend?
```

#### Award Metadata (nur CAN)

```sql
id_award TEXT,                        -- Unique Award ID
id_lot_awarded TEXT,                  -- Los-Nummer
info_on_non_award TEXT,               -- Keine Vergabe (Grund)
contract_number TEXT,                 -- Vertragsnummer
title TEXT,                           -- Titel
dt_award DATE,                        -- Vergabedatum
```

#### Winner Info (nur CAN)

```sql
b_awarded_to_a_group BOOLEAN,         -- Vergabe an Gruppe?
win_name TEXT,                        -- Gewinner Name
win_nationalid TEXT,                  -- Gewinner VAT/ID
win_address TEXT,                     -- Adresse
win_town TEXT,                        -- Stadt
win_postal_code TEXT,                 -- PLZ
win_country_code TEXT,                -- Land
b_contractor_sme BOOLEAN,             -- SME?
```

#### Competition Details (nur CAN)

```sql
number_offers INT,                    -- Anzahl Angebote
number_tenders_sme INT,               -- Davon SME
number_tenders_other_eu INT,          -- Aus anderen EU-Ländern
number_tenders_non_eu INT,            -- Aus Nicht-EU
number_offers_electr INT,             -- Elektronisch
award_est_value_euro NUMERIC,         -- Geschätzter Wert
award_value_euro NUMERIC,             -- Finaler Wert
award_value_euro_fin_1 NUMERIC,       -- Bereinigt
b_subcontracted BOOLEAN,              -- Subunternehmer?
```

### 4.2 Raw Tables Schema

```sql
-- Contract Notices (Ausschreibungen)
CREATE TABLE raw_notices_cn (
    -- Primary Key
    id_notice_cn TEXT PRIMARY KEY,
    
    -- === NOTICE METADATA ===
    ted_notice_url TEXT,
    year INT,
    id_type TEXT,
    directive TEXT,
    dt_dispatch DATE,
    xsd_version TEXT,
    cancelled BOOLEAN,
    corrections INT,
    future_can_id TEXT,
    future_can_id_estimated BOOLEAN,
    
    -- === CONTRACTING AUTHORITY ===
    b_multiple_cae BOOLEAN,
    cae_name TEXT,
    cae_nationalid TEXT,
    cae_address TEXT,
    cae_town TEXT,
    cae_postal_code TEXT,
    iso_country_code TEXT,
    b_multiple_country BOOLEAN,
    iso_country_code_all TEXT,
    cae_type TEXT,
    eu_inst_code TEXT,
    main_activity TEXT,
    
    -- === PROCEDURE ===
    b_on_behalf BOOLEAN,
    b_involves_joint_procurement BOOLEAN,
    b_awarded_by_central_body BOOLEAN,
    type_of_contract TEXT,
    tal_location_nuts TEXT,
    b_fra_agreement BOOLEAN,
    fra_estimated TEXT,
    b_fra_single_operator BOOLEAN,
    fra_number_operators INT,
    fra_number_max_operators INT,
    b_dyn_purch_syst BOOLEAN,
    cpv TEXT,
    additional_cpv TEXT,
    b_gpa BOOLEAN,
    lots_number INT,
    lots_submission TEXT,
    top_type TEXT,
    b_accelerated BOOLEAN,
    
    -- === VALUES & DURATION ===
    value_euro NUMERIC,
    value_euro_fin_1 NUMERIC,
    value_euro_fin_2 NUMERIC,
    b_options BOOLEAN,
    b_eu_funds BOOLEAN,
    b_renewals BOOLEAN,
    duration TEXT,
    contract_start DATE,
    contract_completion DATE,
    
    -- === CRITERIA ===
    crit_code TEXT,
    crit_price_weight TEXT,
    crit_criteria TEXT,
    crit_weights TEXT,
    b_electronic_auction BOOLEAN,
    b_variants BOOLEAN,
    
    -- === SUBMISSION ===
    env_operators INT,
    env_min_operators INT,
    env_max_operators INT,
    dt_applications DATE,
    b_language_any_ec BOOLEAN,
    admin_languages_tender TEXT,
    b_recurrent_procurement BOOLEAN,
    
    -- === LOT LEVEL (XSD 2.0.9+) ===
    id_lot TEXT,
    
    -- === RAW QUALITY SCORE ===
    quality_score_raw FLOAT,
    fields_filled INT,
    fields_total INT,
    critical_fields_missing TEXT[],
    
    -- === IMPORT META ===
    raw_row JSONB,
    imported_at TIMESTAMP DEFAULT NOW(),
    source_file TEXT
);

-- Contract Award Notices (Vergaben)
CREATE TABLE raw_notices_can (
    -- Composite Primary Key (Notice + Award)
    id_notice_can TEXT,
    id_award TEXT,
    
    -- === NOTICE METADATA ===
    ted_notice_url TEXT,
    year INT,
    id_type TEXT,
    directive TEXT,
    dt_dispatch DATE,
    xsd_version TEXT,
    cancelled BOOLEAN,
    corrections INT,
    
    -- === CONTRACTING AUTHORITY ===
    b_multiple_cae BOOLEAN,
    cae_name TEXT,
    cae_nationalid TEXT,
    cae_address TEXT,
    cae_town TEXT,
    cae_postal_code TEXT,
    iso_country_code TEXT,
    cae_type TEXT,
    main_activity TEXT,
    
    -- === CONTRACT ===
    type_of_contract TEXT,
    tal_location_nuts TEXT,
    b_fra_agreement BOOLEAN,
    fra_estimated TEXT,
    b_dyn_purch_syst BOOLEAN,
    cpv TEXT,
    additional_cpv TEXT,
    b_gpa BOOLEAN,
    lots_number INT,
    top_type TEXT,
    out_of_directives TEXT,
    number_awards INT,
    
    -- === AWARD DETAILS ===
    id_lot_awarded TEXT,
    info_on_non_award TEXT,
    contract_number TEXT,
    title TEXT,
    dt_award DATE,
    
    -- === WINNER ===
    b_awarded_to_a_group BOOLEAN,
    win_name TEXT,
    win_nationalid TEXT,
    win_address TEXT,
    win_town TEXT,
    win_postal_code TEXT,
    win_country_code TEXT,
    b_contractor_sme BOOLEAN,
    
    -- === COMPETITION ===
    number_offers INT,
    number_tenders_sme INT,
    number_tenders_other_eu INT,
    number_tenders_non_eu INT,
    number_offers_electr INT,
    
    -- === VALUES ===
    award_est_value_euro NUMERIC,
    award_value_euro NUMERIC,
    award_value_euro_fin_1 NUMERIC,
    b_subcontracted BOOLEAN,
    
    -- === NOTICE LEVEL VALUES ===
    value_euro NUMERIC,
    value_euro_fin_1 NUMERIC,
    value_euro_fin_2 NUMERIC,
    duration TEXT,
    contract_start DATE,
    contract_completion DATE,
    
    -- === CRITERIA ===
    crit_code TEXT,
    b_options BOOLEAN,
    b_eu_funds BOOLEAN,
    
    -- === RAW QUALITY SCORE ===
    quality_score_raw FLOAT,
    fields_filled INT,
    fields_total INT,
    critical_fields_missing TEXT[],
    
    -- === IMPORT META ===
    raw_row JSONB,
    imported_at TIMESTAMP DEFAULT NOW(),
    source_file TEXT,
    
    PRIMARY KEY (id_notice_can, id_award)
);

-- Indexes für Performance
CREATE INDEX idx_cn_future_can ON raw_notices_cn(future_can_id);
CREATE INDEX idx_cn_buyer ON raw_notices_cn(cae_name);
CREATE INDEX idx_cn_cpv ON raw_notices_cn(cpv);
CREATE INDEX idx_cn_year ON raw_notices_cn(year);
CREATE INDEX idx_cn_quality ON raw_notices_cn(quality_score_raw);

CREATE INDEX idx_can_buyer ON raw_notices_can(cae_name);
CREATE INDEX idx_can_supplier ON raw_notices_can(win_name);
CREATE INDEX idx_can_cpv ON raw_notices_can(cpv);
CREATE INDEX idx_can_year ON raw_notices_can(year);
CREATE INDEX idx_can_award_date ON raw_notices_can(dt_award);
CREATE INDEX idx_can_quality ON raw_notices_can(quality_score_raw);
```

### 4.3 Raw Quality Score Berechnung

```python
# Feld-Gewichtungen für Quality Score
FIELD_WEIGHTS = {
    # Kritisch (Gewicht 3) - Ohne diese ist der Record nutzlos
    'id_notice_can': 3,
    'cae_name': 3,
    'win_name': 3,
    'cpv': 3,
    'dt_award': 3,
    'value_euro_fin_1': 3,
    
    # Wichtig (Gewicht 2) - Für Analyse sehr relevant
    'duration': 2,
    'contract_start': 2,
    'contract_completion': 2,
    'top_type': 2,
    'b_fra_agreement': 2,
    'number_offers': 2,
    'future_can_id': 2,
    'cae_type': 2,
    'type_of_contract': 2,
    'cae_nationalid': 2,
    'win_nationalid': 2,
    
    # Nice-to-have (Gewicht 1)
    'cae_address': 1,
    'cae_town': 1,
    'cae_postal_code': 1,
    'win_address': 1,
    'win_town': 1,
    'win_postal_code': 1,
    'tal_location_nuts': 1,
    'b_options': 1,
    'b_eu_funds': 1,
    'crit_code': 1,
    'b_contractor_sme': 1,
    'number_tenders_sme': 1,
    'b_subcontracted': 1,
}


def calculate_raw_quality_score(notice: dict) -> dict:
    """
    Berechnet gewichteten Quality Score für Raw Notice.
    
    Returns:
        {
            'quality_score_raw': 67.5,
            'fields_total': 35,
            'fields_filled': 24,
            'critical_fields_missing': ['duration', 'contract_start'],
            'field_scores': {'cae_name': 1.0, 'duration': 0.0, ...}
        }
    """
    
    total_weight = 0
    filled_weight = 0
    field_scores = {}
    critical_missing = []
    
    for field, weight in FIELD_WEIGHTS.items():
        total_weight += weight
        value = notice.get(field)
        
        # Prüfe ob Feld wirklich gefüllt ist
        is_filled = (
            value is not None 
            and value != '' 
            and str(value).strip() != ''
            and str(value).upper() != 'NULL'
            and str(value).upper() != 'N/A'
        )
        
        if is_filled:
            filled_weight += weight
            field_scores[field] = 1.0
        else:
            field_scores[field] = 0.0
            if weight == 3:  # Kritisches Feld
                critical_missing.append(field)
    
    return {
        'quality_score_raw': round((filled_weight / total_weight) * 100, 1),
        'fields_total': len(FIELD_WEIGHTS),
        'fields_filled': sum(1 for v in field_scores.values() if v > 0),
        'critical_fields_missing': critical_missing,
        'field_scores': field_scores
    }
```

---

## 5. Schicht 2: LLM Extraction

### 5.1 Warum LLM vor Normalisierung?

```
Beispiel aus der Realität:

Raw Notice:
  DURATION: NULL (Feld leer!)
  DESCRIPTION: "Rahmenvertrag über IT-Dienstleistungen 
                für 48 Monate mit Option auf zweimalige 
                Verlängerung um jeweils 12 Monate. 
                Technologien: Microsoft Azure, SAP S/4HANA"

Ohne LLM: duration_months = NULL
Mit LLM:  duration_months = 48, extension_months = 24, 
          tech_keywords = ["Azure", "SAP S/4HANA"]
```

**Der Freitext enthält oft die ECHTEN Werte.**

### 5.2 Extracted Data Schema

```sql
CREATE TABLE extracted_notices (
    -- Primary Key
    notice_id TEXT PRIMARY KEY,
    notice_type TEXT,                     -- 'CN' oder 'CAN'
    
    -- === EXTRAHIERTE FELDER ===
    
    -- Duration
    duration_months INT,
    duration_text TEXT,                   -- Original-Formulierung
    extension_options TEXT,               -- "2x12 Monate optional"
    extension_months INT,                 -- Max Verlängerung
    
    -- Tech Stack
    tech_keywords TEXT[],                 -- ["Azure", "SAP", "Cisco"]
    tech_category TEXT,                   -- "Cloud", "On-Prem", "Hybrid"
    
    -- Predecessor/Successor Hints
    mentions_predecessor BOOLEAN,
    predecessor_supplier TEXT,            -- "Ablösung des Vertrags mit T-Systems"
    mentions_renewal BOOLEAN,
    
    -- Contract Type Clarification
    is_framework_mentioned BOOLEAN,
    framework_type TEXT,                  -- "single", "multi", "dps"
    
    -- Value Clarification
    value_mentioned NUMERIC,
    value_is_annual BOOLEAN,
    value_is_total BOOLEAN,
    
    -- === EXTRACTION QUALITY ===
    extraction_confidence FLOAT,          -- 0.0 - 1.0
    extraction_model TEXT,                -- "claude-3-haiku"
    extracted_at TIMESTAMP,
    
    -- Quality Scores
    quality_score_extracted FLOAT,
    completeness_score FLOAT,
    plausibility_score FLOAT,
    text_coverage_score FLOAT,
    
    -- === HUMAN REVIEW ===
    review_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'auto_approved'
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    
    -- Corrections (falls Human korrigiert)
    corrected_duration_months INT,
    corrected_extension_months INT,
    corrected_tech_keywords TEXT[],
    
    -- === LLM QUALITY CHECK ===
    llm_cpv_match_score FLOAT,            -- 1-10
    llm_cpv_match_reason TEXT,
    llm_value_plausibility_score FLOAT,
    llm_value_plausibility_reason TEXT,
    llm_duration_plausibility_score FLOAT,
    llm_duration_plausibility_reason TEXT,
    llm_contradictions_found BOOLEAN,
    llm_contradictions_details TEXT,
    llm_missing_critical_info BOOLEAN,
    llm_missing_info_details TEXT,
    llm_overall_quality_score FLOAT
);

CREATE INDEX idx_extracted_review ON extracted_notices(review_status);
CREATE INDEX idx_extracted_confidence ON extracted_notices(extraction_confidence);
CREATE INDEX idx_extracted_quality ON extracted_notices(quality_score_extracted);
```

### 5.3 LLM Extraction Prompt

```python
EXTRACTION_PROMPT = """
Analysiere diese öffentliche Vergabebekanntmachung.

=== STRUKTURIERTE FELDER (bereits vorhanden) ===
- CPV Code: {cpv}
- Vertragstyp: {type_of_contract}
- Duration Feld: {duration}
- Start: {contract_start}
- Ende: {contract_completion}
- Framework: {b_fra_agreement}
- Optionen: {b_options}
- Wert: {value_euro}

=== FREITEXT ===
TITEL: {title}

BESCHREIBUNG:
{description}

KRITERIEN:
{crit_criteria}

=== AUFGABE ===
Extrahiere Informationen, die in den strukturierten Feldern FEHLEN oder UNGENAU sind.

Antworte NUR mit validem JSON:
{{
  "duration_months": 48,
  "duration_text": "48 Monate",
  "extension_options": "2x12 Monate optional",
  "extension_months": 24,
  
  "tech_keywords": ["Azure", "SAP", "Cisco"],
  "tech_category": "Cloud",
  
  "mentions_predecessor": true,
  "predecessor_supplier": "T-Systems",
  "mentions_renewal": false,
  
  "is_framework_mentioned": true,
  "framework_type": "multi",
  
  "value_mentioned": 5000000,
  "value_is_annual": false,
  "value_is_total": true,
  
  "extraction_confidence": 0.85
}}

REGELN:
- Wenn ein Feld nicht aus dem Text extrahierbar ist, setze null
- duration_months: Nur wenn explizit genannt (1-120 plausibel)
- tech_keywords: Nur echte Technologie-Begriffe, max 15
- predecessor_supplier: Nur wenn namentlich genannt
- extraction_confidence: 0.0-1.0, basierend auf Klarheit des Textes
"""
```

### 5.4 LLM Quality Check Prompt

```python
LLM_QUALITY_CHECK_PROMPT = """
Analysiere diese Vergabebekanntmachung auf DATENQUALITÄT.

=== STRUKTURIERTE DATEN ===
- CPV Code: {cpv} ({cpv_description})
- Vertragstyp: {type_of_contract}
- Wert: {value_eur} EUR
- Laufzeit: {duration_months} Monate
- Auftraggeber: {buyer_name}
- Auftragnehmer: {supplier_name}

=== FREITEXT ===
{description}

=== PRÜFE ===
1. Passt der CPV-Code zum Beschreibungstext? (1-10)
2. Ist der Wert plausibel für diese Leistung? (1-10)
3. Ist die Laufzeit plausibel für diese Leistung? (1-10)
4. Gibt es Widersprüche zwischen Feldern und Text?
5. Fehlen kritische Informationen?

Antworte NUR mit JSON:
{{
  "cpv_match_score": 8,
  "cpv_match_reason": "CPV 72000000 passt zu Softwareentwicklung",
  
  "value_plausibility_score": 6,
  "value_plausibility_reason": "2.5M für 48 Monate IT-Rahmenvertrag scheint niedrig",
  
  "duration_plausibility_score": 9,
  "duration_plausibility_reason": "48 Monate ist Standard für Rahmenverträge",
  
  "contradictions_found": false,
  "contradictions_details": null,
  
  "missing_critical_info": true,
  "missing_info_details": "Keine Angabe zu Verlängerungsoptionen",
  
  "overall_quality_score": 7.5,
  "confidence": 0.85
}}
"""
```

### 5.5 Extraction Quality Score Berechnung

```python
EXTRACTION_FIELDS = {
    # Feld: (Gewicht, Validator)
    'duration_months': (3, lambda x: x is None or (1 <= x <= 120)),
    'extension_months': (2, lambda x: x is None or (0 <= x <= 60)),
    'tech_keywords': (2, lambda x: x is None or (isinstance(x, list) and len(x) <= 15)),
    'mentions_predecessor': (2, lambda x: x is None or isinstance(x, bool)),
    'predecessor_supplier': (1, lambda x: x is None or len(str(x)) < 200),
    'value_mentioned': (2, lambda x: x is None or x > 0),
    'is_framework_mentioned': (1, lambda x: x is None or isinstance(x, bool)),
}


def calculate_extraction_quality(extracted: dict, raw_text_length: int) -> dict:
    """
    Qualität der LLM-Extraktion bewerten.
    
    Returns:
        {
            'quality_score_extracted': 78.5,
            'completeness_score': 85.0,
            'plausibility_score': 90.0,
            'text_coverage_score': 75.0,
            'needs_review': False
        }
    """
    
    # 1. Completeness: Wie viele Felder wurden extrahiert?
    total_weight = sum(w for w, _ in EXTRACTION_FIELDS.values())
    extracted_weight = 0
    
    for field, (weight, validator) in EXTRACTION_FIELDS.items():
        value = extracted.get(field)
        if value is not None:
            try:
                if validator(value):
                    extracted_weight += weight
                else:
                    extracted_weight += weight * 0.5  # Invalid but present
            except:
                pass
    
    completeness = (extracted_weight / total_weight) * 100
    
    # 2. Plausibility: Machen die Werte Sinn?
    plausibility_checks = []
    
    if extracted.get('duration_months'):
        plausibility_checks.append(1 <= extracted['duration_months'] <= 120)
    
    if extracted.get('tech_keywords'):
        known_tech = ['sap', 'microsoft', 'azure', 'aws', 'oracle', 'cisco', 
                      'ibm', 'linux', 'windows', 'java', 'python', 'cloud',
                      'vmware', 'kubernetes', 'docker', 'salesforce']
        matches = sum(1 for kw in extracted['tech_keywords'] 
                     if any(t in kw.lower() for t in known_tech))
        if extracted['tech_keywords']:
            plausibility_checks.append(matches / len(extracted['tech_keywords']) > 0.3)
    
    plausibility = (sum(plausibility_checks) / max(len(plausibility_checks), 1)) * 100
    
    # 3. Confidence vom LLM
    confidence = (extracted.get('extraction_confidence') or 0.5) * 100
    
    # 4. Text Coverage
    text_coverage = min(raw_text_length / 500, 1.0) * 100
    
    # Gesamtscore
    quality_score = (
        completeness * 0.35 +
        plausibility * 0.30 +
        confidence * 0.20 +
        text_coverage * 0.15
    )
    
    return {
        'quality_score_extracted': round(quality_score, 1),
        'completeness_score': round(completeness, 1),
        'plausibility_score': round(plausibility, 1),
        'text_coverage_score': round(text_coverage, 1),
        'needs_review': quality_score < 70 or confidence < 70
    }
```

---

## 6. Schicht 3: Normalized Data

### 6.1 Entity Tables

```sql
-- Auftraggeber (dedupliziert)
CREATE TABLE buyers (
    buyer_id TEXT PRIMARY KEY,
    
    -- Identifikation
    name TEXT,
    name_normalized TEXT,
    national_id TEXT,
    
    -- Location
    address TEXT,
    town TEXT,
    postal_code TEXT,
    country_code TEXT,
    nuts_code TEXT,
    
    -- Klassifikation
    buyer_type TEXT,                      -- ministry, regional, utility, eu, body, other
    main_activity TEXT,
    is_central_purchasing_body BOOLEAN,
    
    -- Stats (berechnet)
    first_notice_date DATE,
    last_notice_date DATE,
    total_notices INT,
    total_value_eur NUMERIC,
    
    -- Matching
    name_variants TEXT[],
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Lieferanten (dedupliziert)
CREATE TABLE suppliers (
    supplier_id TEXT PRIMARY KEY,
    
    -- Identifikation
    name TEXT,
    name_normalized TEXT,
    national_id TEXT,
    
    -- Location
    address TEXT,
    town TEXT,
    postal_code TEXT,
    country_code TEXT,
    
    -- Klassifikation
    is_sme BOOLEAN,
    
    -- Stats
    first_win_date DATE,
    last_win_date DATE,
    total_wins INT,
    total_value_eur NUMERIC,
    
    -- Matching
    name_variants TEXT[],
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 6.2 Contracts Table (Merged)

```sql
CREATE TABLE contracts (
    contract_id TEXT PRIMARY KEY,
    
    -- === REFERENZEN ===
    source_notice_cn TEXT,
    source_notice_can TEXT,
    buyer_id TEXT REFERENCES buyers(buyer_id),
    supplier_id TEXT REFERENCES suppliers(supplier_id),
    
    -- === CORE FACTS ===
    contract_type TEXT,                   -- works, supplies, services
    cpv_main TEXT,
    cpv_division TEXT,                    -- Erste 2 Stellen
    cpv_group TEXT,                       -- Erste 3 Stellen
    cpv_all TEXT[],
    
    -- === PROCEDURE ===
    procedure_type TEXT,
    is_framework BOOLEAN,
    is_dps BOOLEAN,
    framework_type TEXT,
    
    -- === DATES ===
    notice_date DATE,
    submission_deadline DATE,
    award_date DATE,
    contract_start DATE,
    contract_end DATE,
    
    -- === DURATION (normalisiert auf Monate) ===
    duration_months INT,
    duration_source TEXT,                 -- 'structured', 'extracted', 'calculated', 'estimated'
    duration_confidence TEXT,             -- 'high', 'medium', 'low'
    has_extension_option BOOLEAN,
    extension_months INT,
    predicted_end_date DATE,
    
    -- === VALUES (normalisiert auf EUR) ===
    estimated_value_eur NUMERIC,
    final_value_eur NUMERIC,
    value_source TEXT,
    value_confidence TEXT,
    
    -- === TECH (aus Extraction) ===
    tech_keywords TEXT[],
    tech_category TEXT,
    
    -- === COMPETITION ===
    num_bidders INT,
    num_bidders_sme INT,
    num_bidders_foreign INT,
    
    -- === FLAGS ===
    is_cancelled BOOLEAN,
    is_eu_funded BOOLEAN,
    is_gpa_covered BOOLEAN,
    has_subcontracting BOOLEAN,
    
    -- === PREDECESSOR HINTS ===
    mentions_predecessor BOOLEAN,
    predecessor_supplier_hint TEXT,
    
    -- === FIELD SOURCES ===
    field_sources JSONB,                  -- {"duration": "extracted", "value": "structured", ...}
    
    -- === QUALITY SCORES ===
    quality_score_raw FLOAT,
    quality_score_extracted FLOAT,
    quality_score_final FLOAT,
    quality_improvement FLOAT,
    
    -- === META ===
    xsd_version TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_contracts_buyer ON contracts(buyer_id);
CREATE INDEX idx_contracts_supplier ON contracts(supplier_id);
CREATE INDEX idx_contracts_cpv ON contracts(cpv_main);
CREATE INDEX idx_contracts_cpv_div ON contracts(cpv_division);
CREATE INDEX idx_contracts_award_date ON contracts(award_date);
CREATE INDEX idx_contracts_end_date ON contracts(predicted_end_date);
CREATE INDEX idx_contracts_quality ON contracts(quality_score_final);
```

### 6.3 Merge-Logik

```python
def merge_raw_and_extracted(raw: dict, extracted: dict) -> dict:
    """
    Merged Raw + Extracted mit Qualitäts-Tracking.
    
    Prioritäten:
    1. Extracted (wenn confident)
    2. Structured (wenn vorhanden)
    3. Calculated (wenn berechenbar)
    4. Estimated (als Fallback)
    """
    
    merged = {}
    field_sources = {}
    
    # Duration
    duration, source, confidence = merge_duration(raw, extracted)
    merged['duration_months'] = duration
    merged['duration_source'] = source
    merged['duration_confidence'] = confidence
    field_sources['duration'] = source
    
    # Extension
    if extracted and extracted.get('extension_months'):
        merged['extension_months'] = extracted['extension_months']
        merged['has_extension_option'] = True
        field_sources['extension'] = 'extracted'
    elif raw.get('b_options'):
        merged['has_extension_option'] = True
        field_sources['extension'] = 'structured_flag_only'
    
    # Tech Stack (nur aus Extraction)
    if extracted and extracted.get('tech_keywords'):
        merged['tech_keywords'] = extracted['tech_keywords']
        merged['tech_category'] = extracted.get('tech_category')
        field_sources['tech'] = 'extracted'
    
    # Value
    merged['final_value_eur'] = (
        raw.get('award_value_euro_fin_1') or
        raw.get('value_euro_fin_1') or
        (extracted.get('value_mentioned') if extracted else None)
    )
    field_sources['value'] = 'structured' if raw.get('award_value_euro_fin_1') else 'extracted'
    
    # Predecessor Hints
    if extracted:
        merged['mentions_predecessor'] = extracted.get('mentions_predecessor', False)
        merged['predecessor_supplier_hint'] = extracted.get('predecessor_supplier')
    
    # Field Sources speichern
    merged['field_sources'] = field_sources
    
    return merged


def merge_duration(raw: dict, extracted: dict) -> tuple:
    """
    Merged Duration aus Raw + Extracted.
    
    Returns: (duration_months, source, confidence)
    """
    
    # Priorität 1: LLM-extrahiert (wenn confident)
    if extracted and extracted.get('duration_months'):
        confidence = extracted.get('extraction_confidence', 0.5)
        if confidence > 0.7:
            return extracted['duration_months'], 'extracted', 'high'
    
    # Priorität 2: Strukturiertes Feld
    if raw.get('duration'):
        months = parse_duration_field(raw['duration'])
        if months:
            return months, 'structured', 'high'
    
    # Priorität 3: Aus Dates berechnen
    if raw.get('contract_start') and raw.get('contract_completion'):
        start = parse_date(raw['contract_start'])
        end = parse_date(raw['contract_completion'])
        if start and end:
            delta = (end - start).days
            months = round(delta / 30.4)
            if 1 <= months <= 120:
                return months, 'calculated', 'medium'
    
    # Priorität 4: LLM mit niedriger Confidence
    if extracted and extracted.get('duration_months'):
        return extracted['duration_months'], 'extracted', 'low'
    
    # Priorität 5: Framework Default
    if raw.get('b_fra_agreement'):
        return 48, 'estimated_framework', 'low'
    
    return None, None, None


def parse_duration_field(duration_str: str) -> int:
    """
    Parsed das TED Duration Feld.
    Kann sein: "48", "48 months", "4 years", etc.
    """
    if not duration_str:
        return None
    
    import re
    
    # Nur Zahl
    if duration_str.isdigit():
        months = int(duration_str)
        if 1 <= months <= 120:
            return months
    
    # "X months" oder "X Monate"
    match = re.search(r'(\d+)\s*(month|monat)', duration_str.lower())
    if match:
        return int(match.group(1))
    
    # "X years" oder "X Jahre"
    match = re.search(r'(\d+)\s*(year|jahr)', duration_str.lower())
    if match:
        return int(match.group(1)) * 12
    
    # "X days" oder "X Tage"
    match = re.search(r'(\d+)\s*(day|tag)', duration_str.lower())
    if match:
        return round(int(match.group(1)) / 30.4)
    
    return None
```

---

## 7. Quality Scoring System

### 7.1 Fünf Qualitätsdimensionen

| Dimension | Was wird geprüft | Gewicht |
|-----------|------------------|---------|
| **Completeness** | Sind die Felder gefüllt? | 15% |
| **Plausibility** | Machen Einzelwerte Sinn? | 25% |
| **Consistency** | Passen Felder zusammen? | 25% |
| **Temporal** | Historisch erklärbar? | 15% |
| **LLM Quality** | Passt zum Freitext? | 20% |

### 7.2 Quality Tables

```sql
CREATE TABLE contract_quality (
    contract_id TEXT PRIMARY KEY REFERENCES contracts(contract_id),
    
    -- === DIMENSION SCORES (0-100) ===
    score_completeness FLOAT,
    score_plausibility FLOAT,
    score_consistency FLOAT,
    score_temporal FLOAT,
    score_llm_quality FLOAT,
    
    -- === FINAL SCORE ===
    score_final FLOAT,
    
    -- === FLAGS ===
    plausibility_flags JSONB,
    consistency_flags JSONB,
    temporal_flags JSONB,
    
    -- === LLM DETAILS ===
    llm_cpv_match FLOAT,
    llm_value_plausibility FLOAT,
    llm_contradictions TEXT,
    llm_missing_info TEXT,
    
    -- === REVIEW ===
    needs_review BOOLEAN,
    review_priority INT,                  -- 1=urgent, 2=normal, 3=low
    
    -- === META ===
    calculated_at TIMESTAMP DEFAULT NOW()
);
```

### 7.3 Plausibility Rules

```python
PLAUSIBILITY_RULES = {
    'duration_months': {
        'min': 1,
        'max': 120,
        'typical_range': (12, 48),
        'flag_if_outside': True
    },
    'final_value_eur': {
        'min': 100,
        'max': 10_000_000_000,
        'flag_if_zero': True,
        'flag_if_round': True
    },
    'num_bidders': {
        'min': 1,
        'max': 100,
        'typical_range': (1, 15)
    },
    'award_date': {
        'min': '2004-01-01',
        'max': 'today',
        'must_be_after': 'notice_date'
    },
    'cpv_main': {
        'pattern': r'^\d{8}$',
        'valid_prefixes': ['03', '09', '14', '15', '16', '18', '19', '22', 
                           '24', '30', '31', '32', '33', '34', '35', '37', 
                           '38', '39', '41', '42', '43', '44', '45', '48', 
                           '50', '51', '55', '60', '63', '64', '65', '66', 
                           '70', '71', '72', '73', '75', '76', '77', '79', 
                           '80', '85', '90', '92', '98']
    }
}


def check_plausibility(contract: dict) -> dict:
    """
    Prüft Plausibilität aller Felder.
    """
    
    flags = []
    scores = {}
    
    for field, rules in PLAUSIBILITY_RULES.items():
        value = contract.get(field)
        if value is None:
            continue
        
        score = 1.0
        
        # Min/Max Check
        if 'min' in rules:
            min_val = rules['min']
            if isinstance(min_val, str) and min_val == 'today':
                min_val = datetime.now()
            if value < min_val:
                flags.append({
                    'field': field,
                    'issue': f'below minimum ({value} < {rules["min"]})',
                    'severity': 'error'
                })
                score *= 0.3
        
        if 'max' in rules:
            max_val = rules['max']
            if isinstance(max_val, str) and max_val == 'today':
                max_val = datetime.now()
            if value > max_val:
                flags.append({
                    'field': field,
                    'issue': f'above maximum ({value} > {rules["max"]})',
                    'severity': 'error'
                })
                score *= 0.3
        
        # Typical Range (soft)
        if 'typical_range' in rules:
            low, high = rules['typical_range']
            if not (low <= value <= high):
                flags.append({
                    'field': field,
                    'issue': f'outside typical range ({low}-{high})',
                    'severity': 'warning'
                })
                score *= 0.8
        
        # Round Number Check
        if rules.get('flag_if_round') and isinstance(value, (int, float)):
            if value > 10000 and value % 10000 == 0:
                flags.append({
                    'field': field,
                    'issue': 'suspiciously round number',
                    'severity': 'info'
                })
                score *= 0.95
        
        # Pattern Check
        if 'pattern' in rules:
            import re
            if not re.match(rules['pattern'], str(value)):
                flags.append({
                    'field': field,
                    'issue': 'invalid format',
                    'severity': 'error'
                })
                score *= 0.2
        
        scores[field] = score
    
    avg_score = sum(scores.values()) / max(len(scores), 1)
    
    return {
        'score': avg_score * 100,
        'flags': flags
    }
```

### 7.4 Consistency Rules

```python
CONSISTENCY_RULES = [
    {
        'name': 'date_order',
        'check': lambda c: c.get('contract_start') <= c.get('contract_end') 
                          if c.get('contract_start') and c.get('contract_end') else True,
        'severity': 'error',
        'message': 'Start date after end date'
    },
    {
        'name': 'duration_matches_dates',
        'check': lambda c: abs(c.get('duration_months', 0) - 
                              ((c.get('contract_end') - c.get('contract_start')).days / 30.4)) < 3
                          if c.get('duration_months') and c.get('contract_start') and c.get('contract_end') else True,
        'severity': 'warning',
        'message': 'Duration does not match start/end dates'
    },
    {
        'name': 'award_after_notice',
        'check': lambda c: c.get('award_date') >= c.get('notice_date')
                          if c.get('award_date') and c.get('notice_date') else True,
        'severity': 'error',
        'message': 'Award date before notice date'
    },
    {
        'name': 'value_vs_estimate',
        'check': lambda c: c.get('final_value_eur') <= c.get('estimated_value_eur') * 3
                          if c.get('final_value_eur') and c.get('estimated_value_eur') else True,
        'severity': 'warning',
        'message': 'Final value >3x estimated value'
    },
    {
        'name': 'framework_multiple_awards',
        'check': lambda c: c.get('is_framework') if c.get('num_awards', 1) > 1 else True,
        'severity': 'warning',
        'message': 'Multiple awards but not marked as framework'
    },
    {
        'name': 'open_procedure_single_bid',
        'check': lambda c: c.get('num_bidders', 1) > 1 
                          if c.get('procedure_type') == 'open' else True,
        'severity': 'info',
        'message': 'Open procedure with only 1 bidder'
    }
]


def check_consistency(contract: dict) -> dict:
    """
    Prüft interne Konsistenz.
    """
    
    flags = []
    score = 1.0
    
    for rule in CONSISTENCY_RULES:
        try:
            passed = rule['check'](contract)
        except:
            passed = True
        
        if not passed:
            flags.append({
                'rule': rule['name'],
                'severity': rule['severity'],
                'message': rule['message']
            })
            
            if rule['severity'] == 'error':
                score *= 0.5
            elif rule['severity'] == 'warning':
                score *= 0.8
            else:
                score *= 0.95
    
    return {
        'score': score * 100,
        'flags': flags
    }
```

### 7.5 Temporal Consistency

```python
def check_temporal_consistency(contract: dict, history: list) -> dict:
    """
    Vergleicht mit historischen Daten.
    """
    
    if len(history) < 3:
        return {'score': 100, 'flags': [], 'reason': 'Not enough history'}
    
    flags = []
    score = 1.0
    
    # Value Anomaly
    values = [h['final_value_eur'] for h in history if h.get('final_value_eur')]
    if values and contract.get('final_value_eur'):
        avg_value = sum(values) / len(values)
        ratio = contract['final_value_eur'] / avg_value
        if ratio > 5 or ratio < 0.2:
            flags.append({
                'type': 'value_anomaly',
                'message': f"Value {ratio:.1f}x historical average",
                'severity': 'warning'
            })
            score *= 0.7
    
    # Duration Anomaly
    durations = [h['duration_months'] for h in history if h.get('duration_months')]
    if durations and contract.get('duration_months'):
        from statistics import mode
        try:
            typical = mode(durations)
            if contract['duration_months'] != typical:
                flags.append({
                    'type': 'duration_change',
                    'message': f"Duration {contract['duration_months']}m vs typical {typical}m",
                    'severity': 'info'
                })
                score *= 0.9
        except:
            pass
    
    return {
        'score': score * 100,
        'flags': flags
    }
```

### 7.6 Comprehensive Quality Calculation

```python
def calculate_comprehensive_quality(
    contract: dict, 
    extracted: dict, 
    history: list
) -> dict:
    """
    Kombiniert alle Qualitätsdimensionen.
    """
    
    # 1. Completeness
    completeness = calculate_completeness(contract)
    
    # 2. Plausibility
    plausibility = check_plausibility(contract)
    
    # 3. Consistency
    consistency = check_consistency(contract)
    
    # 4. Temporal
    temporal = check_temporal_consistency(contract, history)
    
    # 5. LLM Quality
    llm_quality = extracted.get('llm_overall_quality_score', 7.5) * 10 if extracted else None
    
    # Gewichteter Score
    scores = {
        'completeness': completeness['score'],
        'plausibility': plausibility['score'],
        'consistency': consistency['score'],
        'temporal': temporal['score'],
    }
    
    weights = {
        'completeness': 0.15,
        'plausibility': 0.25,
        'consistency': 0.25,
        'temporal': 0.15,
    }
    
    if llm_quality is not None:
        scores['llm_quality'] = llm_quality
        weights['llm_quality'] = 0.20
    else:
        # Normalisiere ohne LLM
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
    
    final_score = sum(scores[k] * weights[k] for k in scores)
    
    # Alle Flags sammeln
    all_flags = (
        plausibility['flags'] + 
        consistency['flags'] + 
        temporal['flags']
    )
    
    # Review nötig?
    has_errors = any(f.get('severity') == 'error' for f in all_flags)
    needs_review = final_score < 60 or has_errors
    
    return {
        'score_completeness': scores['completeness'],
        'score_plausibility': scores['plausibility'],
        'score_consistency': scores['consistency'],
        'score_temporal': scores['temporal'],
        'score_llm_quality': scores.get('llm_quality'),
        'score_final': round(final_score, 1),
        'plausibility_flags': plausibility['flags'],
        'consistency_flags': consistency['flags'],
        'temporal_flags': temporal['flags'],
        'needs_review': needs_review,
        'review_priority': 1 if has_errors else (2 if needs_review else 3)
    }
```

---

## 8. Contract Chain Building

### 8.1 Chain Table

```sql
CREATE TABLE contract_chains (
    chain_id SERIAL PRIMARY KEY,
    
    -- === DIE KETTE ===
    original_contract_id TEXT REFERENCES contracts(contract_id),
    renewal_contract_id TEXT REFERENCES contracts(contract_id),
    
    -- === GEMEINSAMER KONTEXT ===
    buyer_id TEXT REFERENCES buyers(buyer_id),
    cpv_division TEXT,
    
    -- === ERGEBNIS ===
    incumbent_supplier_id TEXT REFERENCES suppliers(supplier_id),
    new_supplier_id TEXT REFERENCES suppliers(supplier_id),
    incumbent_retained BOOLEAN,
    
    -- === DELTAS ===
    value_change_pct FLOAT,
    duration_change_months INT,
    gap_days INT,
    
    -- === CHAIN METADATA ===
    chain_position INT,
    total_chain_length INT,
    
    -- === MATCHING ===
    match_method TEXT,                    -- 'future_can_id', 'buyer_cpv_time', 'predecessor_hint'
    match_confidence FLOAT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(original_contract_id, renewal_contract_id)
);

CREATE INDEX idx_chains_buyer ON contract_chains(buyer_id);
CREATE INDEX idx_chains_incumbent ON contract_chains(incumbent_retained);
CREATE INDEX idx_chains_cpv ON contract_chains(cpv_division);
```

### 8.2 Chain Building Logic

```python
def build_contract_chains():
    """
    Baut Vertragsverkettungen aus:
    1. FUTURE_CAN_ID (direkte Links)
    2. Buyer + CPV + Zeit Matching
    3. Predecessor Hints aus LLM Extraction
    """
    
    # Methode 1: FUTURE_CAN_ID (höchste Confidence)
    chains_from_future_id = db.query("""
        INSERT INTO contract_chains (
            original_contract_id, renewal_contract_id,
            buyer_id, cpv_division,
            incumbent_supplier_id, new_supplier_id, incumbent_retained,
            value_change_pct, gap_days,
            match_method, match_confidence
        )
        SELECT 
            cn.contract_id,
            can.contract_id,
            cn.buyer_id,
            cn.cpv_division,
            cn.supplier_id,
            can.supplier_id,
            cn.supplier_id = can.supplier_id,
            (can.final_value_eur - cn.final_value_eur) / NULLIF(cn.final_value_eur, 0) * 100,
            can.award_date - cn.predicted_end_date,
            'future_can_id',
            0.95
        FROM contracts cn
        JOIN raw_notices_cn raw ON cn.source_notice_cn = raw.id_notice_cn
        JOIN contracts can ON can.source_notice_can = raw.future_can_id
        WHERE raw.future_can_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    
    # Methode 2: Buyer + CPV + Zeit (mittlere Confidence)
    chains_from_matching = db.query("""
        INSERT INTO contract_chains (
            original_contract_id, renewal_contract_id,
            buyer_id, cpv_division,
            incumbent_supplier_id, new_supplier_id, incumbent_retained,
            value_change_pct, gap_days,
            match_method, match_confidence
        )
        SELECT DISTINCT ON (c1.contract_id)
            c1.contract_id,
            c2.contract_id,
            c1.buyer_id,
            c1.cpv_division,
            c1.supplier_id,
            c2.supplier_id,
            c1.supplier_id = c2.supplier_id,
            (c2.final_value_eur - c1.final_value_eur) / NULLIF(c1.final_value_eur, 0) * 100,
            c2.award_date - c1.predicted_end_date,
            'buyer_cpv_time',
            0.7
        FROM contracts c1
        JOIN contracts c2 ON 
            c1.buyer_id = c2.buyer_id
            AND c1.cpv_division = c2.cpv_division
            AND c2.award_date BETWEEN c1.predicted_end_date - INTERVAL '6 months'
                                  AND c1.predicted_end_date + INTERVAL '18 months'
            AND c1.contract_id != c2.contract_id
        WHERE c1.contract_id NOT IN (SELECT original_contract_id FROM contract_chains)
        ORDER BY c1.contract_id, ABS(c2.award_date - c1.predicted_end_date)
        ON CONFLICT DO NOTHING
    """)
    
    # Methode 3: Predecessor Hints (niedrigere Confidence, aber wertvoll)
    # ...
```

---

## 9. Analyse-Queries

### 9.1 Basis-Statistiken

```sql
-- Gesamtüberblick
SELECT 
    COUNT(*) as total_contracts,
    COUNT(DISTINCT buyer_id) as unique_buyers,
    COUNT(DISTINCT supplier_id) as unique_suppliers,
    SUM(final_value_eur) as total_value,
    ROUND(AVG(quality_score_final), 1) as avg_quality
FROM contracts;

-- Quality Distribution
SELECT 
    CASE 
        WHEN quality_score_final >= 90 THEN '90-100 (Excellent)'
        WHEN quality_score_final >= 70 THEN '70-89 (Good)'
        WHEN quality_score_final >= 50 THEN '50-69 (Fair)'
        ELSE '<50 (Poor)'
    END as quality_bucket,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct
FROM contracts
GROUP BY 1
ORDER BY 1 DESC;
```

### 9.2 Incumbent Analysis

```sql
-- Incumbent-Rate gesamt
SELECT 
    COUNT(*) as total_chains,
    SUM(incumbent_retained::int) as incumbent_wins,
    ROUND(AVG(incumbent_retained::int) * 100, 1) as incumbent_rate_pct
FROM contract_chains
WHERE match_confidence > 0.6;

-- Incumbent-Rate nach CPV Division
SELECT 
    cpv_division,
    COUNT(*) as chains,
    ROUND(AVG(incumbent_retained::int) * 100, 1) as incumbent_rate
FROM contract_chains
WHERE match_confidence > 0.6
GROUP BY cpv_division
HAVING COUNT(*) > 50
ORDER BY incumbent_rate DESC;

-- Incumbent-Rate nach Vertragsgröße
SELECT 
    CASE 
        WHEN c.final_value_eur < 100000 THEN '<100k'
        WHEN c.final_value_eur < 1000000 THEN '100k-1M'
        WHEN c.final_value_eur < 10000000 THEN '1M-10M'
        ELSE '>10M'
    END as value_bucket,
    COUNT(*) as chains,
    ROUND(AVG(cc.incumbent_retained::int) * 100, 1) as incumbent_rate
FROM contract_chains cc
JOIN contracts c ON cc.original_contract_id = c.contract_id
WHERE cc.match_confidence > 0.6
GROUP BY 1
ORDER BY 1;
```

### 9.3 Temporal Patterns

```sql
-- Vergaben nach Jahr
SELECT 
    EXTRACT(YEAR FROM award_date) as year,
    COUNT(*) as contracts,
    SUM(final_value_eur) as total_value,
    ROUND(AVG(quality_score_final), 1) as avg_quality
FROM contracts
GROUP BY 1
ORDER BY 1;

-- Saisonalität
SELECT 
    EXTRACT(QUARTER FROM award_date) as quarter,
    COUNT(*) as contracts,
    SUM(final_value_eur) as volume
FROM contracts
GROUP BY 1
ORDER BY 1;
```

---

## 10. Human-in-the-Loop Workflow

### 10.1 Auto-Approve Rules

```python
def should_auto_approve(extracted: dict) -> bool:
    """
    Wann ist Human Review nicht nötig?
    """
    
    confidence = extracted.get('extraction_confidence', 0)
    
    # Hohe Confidence
    if confidence < 0.90:
        return False
    
    # Plausible Duration
    duration = extracted.get('duration_months')
    if duration and not (1 <= duration <= 120):
        return False
    
    # Nicht zu viele Keywords
    keywords = extracted.get('tech_keywords', [])
    if len(keywords) > 10:
        return False
    
    # Keine Widersprüche gefunden
    if extracted.get('llm_contradictions_found'):
        return False
    
    return True
```

### 10.2 Review Queue Priority

```python
def get_review_queue(limit: int = 100) -> list:
    """
    Priorisierte Review-Queue:
    1. Hoher Wert + mittlere Confidence
    2. Errors gefunden
    3. Rest
    """
    
    return db.query("""
        SELECT 
            e.*,
            c.final_value_eur,
            cq.needs_review,
            cq.review_priority
        FROM extracted_notices e
        JOIN contracts c ON e.notice_id = c.source_notice_can
        JOIN contract_quality cq ON c.contract_id = cq.contract_id
        WHERE e.review_status = 'pending'
        ORDER BY 
            cq.review_priority ASC,
            c.final_value_eur DESC
        LIMIT :limit
    """, limit=limit)
```

### 10.3 Review Statistics

```python
def get_review_stats() -> dict:
    """
    Übersicht für Human Reviewer.
    """
    
    return db.query("""
        SELECT 
            review_status,
            COUNT(*) as count,
            ROUND(AVG(extraction_confidence) * 100, 1) as avg_confidence
        FROM extracted_notices
        GROUP BY review_status
    """)
```

---

## 11. Technische Anforderungen

### 11.1 Stack

| Komponente | Empfehlung |
|------------|------------|
| Datenbank | PostgreSQL (Supabase) |
| Sprache | Python 3.11+ |
| LLM | Claude Haiku (Extraktion), Claude Sonnet (Quality Check) |
| Scheduling | Supabase Cron oder GitHub Actions |

### 11.2 Ressourcen

| Ressource | Schätzung |
|-----------|-----------|
| Storage | 20-50 GB |
| LLM Kosten (Extraktion) | ~$300-500 einmalig (Haiku) |
| LLM Kosten (Quality) | ~$500-800 einmalig (Sonnet) |
| Import-Zeit | 1-2 Tage |
| Extraction-Zeit | 2-3 Tage |

---

## 12. Implementierungs-Phasen

### Phase 1: Raw Import (Woche 1-2)

- [ ] TED CSV Download (2006-2025)
- [ ] Raw Tables erstellen
- [ ] Import-Script
- [ ] Raw Quality Score berechnen
- [ ] Basis-Statistiken

### Phase 2: LLM Extraction (Woche 2-4)

- [ ] Extraction Prompt finalisieren
- [ ] Batch-Processing Pipeline
- [ ] Quality Check Prompt
- [ ] Review Queue aufsetzen
- [ ] Auto-Approve Logic

### Phase 3: Normalization (Woche 4-5)

- [ ] Entity Resolution (Buyers, Suppliers)
- [ ] Merge-Logic implementieren
- [ ] Contracts Table befüllen
- [ ] Comprehensive Quality Score

### Phase 4: Chain Building (Woche 5-6)

- [ ] FUTURE_CAN_ID Chains
- [ ] Fuzzy Matching Chains
- [ ] Incumbent-Rate Berechnung
- [ ] Chain Analytics

### Phase 5: X-RAY v2 (Woche 6-7)

- [ ] Deine 80 Verträge anreichern
- [ ] Wechsel-Score berechnen
- [ ] Export-Format
- [ ] Report generieren

---

## Anhang: CPV Divisions Reference

| Code | Kategorie | Wiederkehrend? |
|------|-----------|----------------|
| 03 | Landwirtschaft | Mittel |
| 09 | Energie | Hoch |
| 15 | Lebensmittel | Hoch |
| 30 | IT Hardware | Hoch |
| 32 | Telekommunikation | Hoch |
| 33 | Medizintechnik | Sehr hoch |
| 34 | Transport | Hoch |
| 45 | Bau | Mittel |
| 48 | Software | Sehr hoch |
| 50 | Wartung | Sehr hoch |
| 60 | Transportdienste | Sehr hoch |
| 64 | Post/Telko | Sehr hoch |
| 65 | Versorgung | Sehr hoch |
| 72 | IT-Services | Sehr hoch |
| 79 | Beratung | Hoch |
| 85 | Gesundheit | Sehr hoch |
| 90 | Reinigung/Umwelt | Sehr hoch |

---

**Ende des Konzeptdokuments**

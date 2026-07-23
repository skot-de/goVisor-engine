# goVisor: NUTS-3 Regionale Granularität – Backend

## Kontext

Wettbewerber (aufträge.io) bietet Filter bis Landkreis-Ebene. Wir aktuell nur Bundesland (NUTS-1). Das ist ein Gap für regionale Anbieter (Handwerker, lokale IT-Dienstleister).

**Ziel:** Filter bis NUTS-3 (Landkreis) ermöglichen.

---

## NUTS-Hierarchie

| Ebene | Code-Beispiel | Beschreibung | Anzahl DE |
|-------|---------------|--------------|-----------|
| NUTS-0 | DE | Deutschland | 1 |
| NUTS-1 | DE2 | Bayern | 16 |
| NUTS-2 | DE21 | Oberbayern | 38 |
| NUTS-3 | DE212 | München, Landkreis | 401 |

---

## 1. Prüfen: Was haben wir?

```sql
-- Prüfen welche NUTS-Codes in den Daten sind
SELECT 
  LENGTH(nuts_code) as code_length,
  LEFT(nuts_code, 3) as nuts1_prefix,
  COUNT(*) as count
FROM leads
WHERE country = 'DE'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Beispiel-Werte
SELECT DISTINCT nuts_code 
FROM leads 
WHERE country = 'DE' 
LIMIT 100;
```

**Erwartung:** TED liefert NUTS-3 Codes. Falls nur NUTS-1/2: Mapping-Tabelle von TED oder EU nötig.

---

## 2. Dimensionstabelle: `dim_nuts`

Falls nicht vorhanden, anlegen:

```sql
CREATE TABLE dim_nuts (
  nuts_code VARCHAR(5) PRIMARY KEY,
  nuts_level INT NOT NULL,  -- 0, 1, 2, 3
  name_de VARCHAR(255) NOT NULL,
  name_en VARCHAR(255),
  parent_code VARCHAR(5),
  
  -- Für schnelle Hierarchie-Abfragen
  nuts0_code VARCHAR(2) GENERATED ALWAYS AS (LEFT(nuts_code, 2)) STORED,
  nuts1_code VARCHAR(3) GENERATED ALWAYS AS (LEFT(nuts_code, 3)) STORED,
  nuts2_code VARCHAR(4) GENERATED ALWAYS AS (LEFT(nuts_code, 4)) STORED,
  
  FOREIGN KEY (parent_code) REFERENCES dim_nuts(nuts_code)
);

-- Index für Autocomplete
CREATE INDEX idx_dim_nuts_name ON dim_nuts(name_de);
CREATE INDEX idx_dim_nuts_parent ON dim_nuts(parent_code);
CREATE INDEX idx_dim_nuts_level ON dim_nuts(nuts_level);
```

**Datenquelle:** https://ec.europa.eu/eurostat/web/nuts/correspondence-tables/

---

## 3. Leads-Tabelle: NUTS-Felder

Falls `leads.nuts_code` nur NUTS-1 enthält, erweitern:

```sql
-- Prüfen ob wir das rohe NUTS-3 haben
SELECT nuts_code, LENGTH(nuts_code) as len
FROM leads 
WHERE country = 'DE'
LIMIT 10;

-- Falls nötig: Felder für jede Ebene (für schnelle Filter)
ALTER TABLE leads ADD COLUMN nuts1_code VARCHAR(3);
ALTER TABLE leads ADD COLUMN nuts2_code VARCHAR(4);
ALTER TABLE leads ADD COLUMN nuts3_code VARCHAR(5);

-- Update aus bestehendem nuts_code
UPDATE leads SET
  nuts1_code = LEFT(nuts_code, 3),
  nuts2_code = CASE WHEN LENGTH(nuts_code) >= 4 THEN LEFT(nuts_code, 4) END,
  nuts3_code = CASE WHEN LENGTH(nuts_code) >= 5 THEN LEFT(nuts_code, 5) END
WHERE country = 'DE';

-- Indizes
CREATE INDEX idx_leads_nuts1 ON leads(nuts1_code);
CREATE INDEX idx_leads_nuts2 ON leads(nuts2_code);
CREATE INDEX idx_leads_nuts3 ON leads(nuts3_code);
```

---

## 4. User-Profil: NUTS erweitern

Aktuell in `user_profiles.regions` (NUTS-1 Array). Erweitern für beliebige NUTS-Ebenen:

```sql
-- Bestehend
-- regions: ['DE2', 'DE7']  -- Bayern, Hessen

-- Neu: beliebige NUTS-Codes erlauben
-- regions: ['DE2', 'DE712', 'DE212']  -- ganz Bayern + Frankfurt + München LK

-- Keine Schema-Änderung nötig, nur Interpretation:
-- Frontend/Backend erkennt an Code-Länge die Ebene
```

**Logik im Backend:**

```python
def matches_region_filter(lead_nuts: str, user_regions: list[str]) -> bool:
    """
    Prüft ob Lead in einer der User-Regionen liegt.
    User kann NUTS-1, NUTS-2 oder NUTS-3 wählen.
    Lead matcht wenn sein NUTS-Code mit einem User-Code BEGINNT.
    
    Beispiele:
    - Lead: DE212 (München LK), User: ['DE2'] → True (Bayern)
    - Lead: DE212 (München LK), User: ['DE21'] → True (Oberbayern)
    - Lead: DE212 (München LK), User: ['DE711'] → False (Frankfurt)
    """
    for region in user_regions:
        if lead_nuts.startswith(region):
            return True
    return False
```

---

## 5. API Endpoints

### 5.1 NUTS Autocomplete

```
GET /api/nuts/search?q=münch&level=3

Response:
{
  "results": [
    { "code": "DE212", "name": "München, Landkreis", "level": 3, "parent": "DE21" },
    { "code": "DE21H", "name": "München, Stadt", "level": 3, "parent": "DE21" }
  ]
}
```

### 5.2 NUTS Hierarchie (für Drill-down)

```
GET /api/nuts/children?parent=DE2

Response:
{
  "parent": { "code": "DE2", "name": "Bayern", "level": 1 },
  "children": [
    { "code": "DE21", "name": "Oberbayern", "level": 2, "lead_count": 1234 },
    { "code": "DE22", "name": "Niederbayern", "level": 2, "lead_count": 456 },
    ...
  ]
}
```

### 5.3 Leads Filter (erweitert)

```
GET /api/leads?regions=DE212,DE711&...

-- Backend SQL
SELECT * FROM leads
WHERE (
  nuts3_code IN ('DE212', 'DE711')
  OR nuts2_code IN ('DE212', 'DE711')
  OR nuts1_code IN ('DE212', 'DE711')
)
-- Oder mit startswith:
WHERE (
  nuts_code LIKE 'DE212%' 
  OR nuts_code LIKE 'DE711%'
)
```

---

## 6. Relevanz-Score Anpassung

Der Relevanz-Score (Region-Komponente 30%) muss NUTS-3 berücksichtigen:

```python
def region_score(lead_nuts: str, user_regions: list[str]) -> float:
    """
    Exakter Match auf tiefster Ebene = 100%
    Match auf höherer Ebene = anteilig
    """
    for region in user_regions:
        if lead_nuts == region:
            return 1.0  # Exakt
        if lead_nuts.startswith(region):
            # Lead ist spezifischer als User-Auswahl
            # z.B. User: DE2 (Bayern), Lead: DE212 (München LK)
            return 0.9
        if region.startswith(lead_nuts):
            # User ist spezifischer als Lead
            # z.B. User: DE212 (München LK), Lead: DE2 (Bayern-weit)
            return 0.7
    return 0.0  # Kein Match
```

---

## 7. Migration / Backfill

```sql
-- 1. dim_nuts befüllen (einmalig, aus EU-Datenquelle)
COPY dim_nuts FROM '/path/to/nuts_2024.csv' WITH CSV HEADER;

-- 2. Leads: NUTS-Felder befüllen
UPDATE leads SET
  nuts1_code = LEFT(nuts_code, 3),
  nuts2_code = CASE WHEN LENGTH(nuts_code) >= 4 THEN LEFT(nuts_code, 4) END,
  nuts3_code = CASE WHEN LENGTH(nuts_code) >= 5 THEN LEFT(nuts_code, 5) END
WHERE nuts1_code IS NULL AND country = 'DE';

-- 3. User-Profile: keine Migration nötig (bestehende NUTS-1 Codes bleiben gültig)
```

---

## 8. Tests

```python
def test_nuts_hierarchy():
    assert get_parent("DE212") == "DE21"
    assert get_parent("DE21") == "DE2"
    assert get_parent("DE2") == "DE"
    
def test_region_filter():
    # User wählt Bayern
    assert matches_region_filter("DE212", ["DE2"]) == True
    # User wählt München LK
    assert matches_region_filter("DE212", ["DE212"]) == True
    # User wählt Frankfurt
    assert matches_region_filter("DE212", ["DE711"]) == False
    
def test_region_score():
    assert region_score("DE212", ["DE212"]) == 1.0  # Exakt
    assert region_score("DE212", ["DE2"]) == 0.9    # Lead spezifischer
    assert region_score("DE2", ["DE212"]) == 0.7    # User spezifischer
```

---

## 9. Offene Fragen

| Frage | Empfehlung |
|-------|------------|
| Haben wir NUTS-3 in den TED-Rohdaten? | Prüfen mit Query oben |
| Falls nicht: woher? | EU Eurostat Mapping-Tabelle |
| Performance bei 401 NUTS-3 Codes? | Index sollte reichen |
| Supabase RLS anpassen? | Ja, falls region-basierte Policies |

---

## Zusammenfassung

| Komponente | Änderung |
|------------|----------|
| `dim_nuts` | Neue Tabelle (falls nicht da) |
| `leads` | 3 neue Spalten (nuts1/2/3_code) + Indizes |
| `user_profiles` | Keine Änderung (regions[] akzeptiert alle NUTS-Ebenen) |
| API | 2 neue Endpoints (search, children) + Filter erweitern |
| Relevanz-Score | Region-Komponente anpassen |

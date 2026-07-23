# Radius-Suche (Stadt + Umkreis)

**Status:** Backend implementiert (2026-07-22)
**Frage:** „Ich suche München und will alle Aufträge im Umkreis von 5/10/25/50/100 km."

---

## Abgrenzung zum NUTS-3-Filter

Das [`govisor-nuts3-backend.md`](../INPUT/v1%20Features/govisor-nuts3-backend.md)-Ticket
baut ein **hierarchisches** Filter (Landkreis-Präfix). Die Radius-Suche ist **geometrisch**
(Distanz von einem Punkt) und braucht **Koordinaten pro Lead**. Beide koexistieren:
NUTS-3 = „Regionen, die ich dauerhaft bediene" (Profil); Radius = „ad hoc um *diese* Stadt".

---

## Datengrundlage (gemessen)

| Signal | Abdeckung |
|---|---|
| Buyer-PLZ (aus `notice_parties`) | 85 % |
| `buyer_town` (Ort-Fallback) | 100 % |
| **Geo-Abdeckung je Lead (kombiniert)** | **99,8 %** |

## Bausteine

- **Geo-Referenz:** `data/reference/geonames/DE.txt` — GeoNames-PLZ-Datensatz (CC-BY,
  `download.geonames.org/export/zip/DE.zip`, ~23k Zeilen).
- **`dim_plz` (`gold.build_dim_plz`):** PLZ → Zentroid (lat/lon, Ort, Bundesland),
  10.813 PLZ. Dient doppelt: Lead-Geokoder **und** City-Such-Geokoder.
- **`lead_geo` (`gold.build_lead_geo`):** Koordinate je Lead. Waterfall: Buyer-PLZ
  (normalisiert auf 5 Ziffern) → `dim_plz`; sonst `buyer_town` → Ort-Zentroid; sonst
  keine. `geo_source` ∈ {`plz`, `ort`, `none`} flaggt die Präzision ehrlich. 1:1 zu `leads`.
- **`govisor/geo.py`:** `geocode_city(city)` → (lat, lon); `radius_search(lat, lon, km)`
  und `radius_count(...)` — Haversine-Distanzfilter über `lead_geo`.

## Nutzung

```python
from govisor import geo
from govisor.config import Config
cfg = Config(countries=("DE",), data_dir="data")

lat, lon = geo.geocode_city(cfg, "DE", "München")     # → (48.14, 11.56)
geo.radius_count(cfg, "DE", lat, lon, 25)              # Anzahl im 25-km-Umkreis
geo.radius_search(cfg, "DE", lat, lon, 10, limit=20)  # Leads, nach Distanz sortiert
```

**Beispiel München** (verifiziert): 5 km → 3.376 · 10 km → 4.076 · 25 km → 4.561 ·
50 km → 4.999 · 100 km → 6.616 Leads (monoton wachsend).

## Kombination mit NUTS-3-Filter

`lead_geo` trägt zusätzlich `nuts` (= `buyer_nuts`, **99,8 % NUTS-3**). `geo.search(...)`
verknüpft **Radius UND NUTS-Präfix** (beide optional, UND-verknüpft):

```python
geo.search(cfg, "DE", city="München", radius_km=25)                 # nur Radius
geo.search(cfg, "DE", nuts=["DE21"])                                # nur Region (Oberbayern)
geo.search(cfg, "DE", city="München", radius_km=25, nuts=["DE21"])  # BEIDES (Schnittmenge)
geo.search(cfg, "DE", nuts=["DE212", "DE21H"])                      # mehrere Landkreise
```

NUTS-Codes sind Präfix-Match (beliebige Ebene: `DE2`=Bayern, `DE21`=Oberbayern,
`DE212`=München LK) und werden gegen `^[A-Z]{2}[A-Z0-9]{0,3}$` validiert (kein Injection).
Verifiziert: 25 km + DE21 = 4.527 < 4.561 (Radius allein) — echte Schnittmenge.

### Namens-Autocomplete (`dim_nuts`) — gebaut

`dim_nuts` (`gold.build_dim_nuts`): NUTS-Code → Name/Ebene/Parent aus den **autoritativen
EU-GISCO-Attributtabellen** (`data/reference/nuts/NUTS_AT_{2021,2024}.csv`, Union beider
Versionen). 462 DE-Codes (1 Land / 16 Bundesländer / 38 RB / 407 Kreise), deckt **97 %**
der in Leads vorkommenden NUTS-Codes ab.

```python
geo.nuts_autocomplete(cfg, "DE", "münch")        # → DE212 (München, Kreisfreie Stadt), DE21H (…Landkreis)
geo.nuts_autocomplete(cfg, "DE", "bayern", level=1)  # → DE2 (Bayern)
geo.nuts_children(cfg, "DE", "DE21")             # Drill-down: Landkreise Oberbayerns + Lead-Anzahl
```

UI-Flow: Nutzer tippt Region → `nuts_autocomplete` liefert Code → `search(..., nuts=[code])`
(optional mit Radius kombiniert). `nuts_children` liefert den Drill-down mit Lead-Zahlen
(§5.1/§5.2 des NUTS-Tickets, jetzt implementiert).

## Zwei Achsen: Buyer vs. Leistungsort

`lead_geo` trägt **beide** Standort-Achsen; `geo.search(..., axis=...)` wählt sie:

| `axis` | Bedeutung | Koordinate | NUTS |
|---|---|---|---|
| **`buyer`** (Default) | *Auftraggeber* — wo sitzt die Behörde | Buyer-PLZ (**fein**) | `nuts` (=buyer_nuts) |
| **`performance`** | *Leistungsort* — wo wird gearbeitet | NUTS-3-Zentroid (**grob**, 95 %) | `perf_nuts` (=performance_nuts) |

Die NUTS-3-Zentroide für die Performance-Achse sind **selbst-abgeleitet** (Mittel der
Buyer-Koordinaten je Region) — kein externer Download. Verifiziert: **1.579 Leads haben
Buyer-NUTS ≠ Performance-NUTS** (Auftraggeber außerhalb der Region, Leistung darin oder
umgekehrt) — die Achsen sind echt unterschiedliche Signale. Für den lokalen Anbieter ist
`performance` semantisch korrekt („wo ist die Arbeit"); `buyer` ist feiner (PLZ). Im UI
beide anbieten, Default `buyer`.

## Ehrliche Grenzen

- **Präzision:** `geo_source='plz'` ist fein (~PLZ-Gebiet), `'ort'` ist grob (Stadt-Zentroid,
  alle Leads einer Stadt am selben Punkt). Die Performance-Achse ist NUTS-3-grob
  (Landkreis-Zentroid) — 5/10 km sinnvoll nur auf der Buyer-Achse. Im UI als Präzisions-
  Hinweis anzeigen.
- **PLZ-Lücken:** einzelne (Großkunden-)PLZ fehlen in GeoNames → Ort-Fallback greift.

## Performance / Skalierung

Bei ~74k Leads ist der Haversine-Scan trivial (<10 ms). Für viel größere Bestände:
Bounding-Box-Vorfilterung (`lat/lon ± r/111 km`) oder PostGIS + GiST-Index.

## Verdrahtung

In der Gold-Pipeline (`cli.py`: `dim-plz`, `lead-geo`), FK-geprüft (`lead_geo.lead_id →
leads`), Tests in `tests/test_geo.py` (Geokoder, 1:1, Monotonie, Haversine-Plausibilität).

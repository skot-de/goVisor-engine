# Externe APIs für die aufgebohrten Lead-Details

Kontext: Lead-Detail bekommt Tabs **Übersicht · Ausschreibung · Vergabestelle · Team** (Notizen/Log).
Frage: welche externen APIs werten bestehende/neue Detailfelder auf? Alles gemessen/verifiziert (Juli 2026).

## Grundprinzip
Unsere Daten sagen *welche Chance* + *wer der Käufer/Gewinner ist* (als **Name**). Extern fehlt:
*wer ist diese Firma/Behörde wirklich* (Firmografie), *ist sie solide* (Distress), *wie groß ist der €-Markt*
(Wert), *wo genau* (Geo). Genau das füllen externe Quellen — je Tab unterschiedlich.

## Zuordnung API → Tab

### Tab „Vergabestelle" (größter Hebel)
| Quelle | Feld | Auth/Kosten | Status |
|---|---|---|---|
| **Wikidata** (SPARQL) | offizielle Website, Einwohnerzahl, Koordinaten, Typ, Logo | **frei, kein Auth** | ✅ getestet — greift für ~7 % (saubere Kommunal-Käufer), Disambiguierung via Geo nötig |
| **Handelsregister / OffeneRegister** | Rechtsform, Sitz, HRB, Geschäftsführer, Konzern | frei (Bulk) / komm. (API) | Fundament auch für Entity-Resolution |
| **Destatis GENESIS** (Regionaldaten) | Einwohner/BIP/Bau-Aktivität der Region | frei, **aber Registrierung/Token** | ⚠️ 307-Redirect ohne Creds |

### Tab „Ausschreibung"
| Quelle | Feld | Auth/Kosten | Status |
|---|---|---|---|
| **Destatis Baupreisindex** | Wert real/deflationiert, Bau-Preistrend-Kontext | frei, Token | ⚠️ Registrierung |
| **Nominatim/OSM** | präzise Leistungsort-Koordinate + Kartenpin | frei, Fair-Use | wir haben Koordinaten schon (dim_plz/lead_geo) |
| Vergabeplattform-Dokumente | Vergabeunterlagen (Formblätter, Preisblatt) | Login/AGB | v3-Tool, gegated (§ getrennt) |

### Tab „Übersicht" (verdichtet aus obigen)
- €-Kontext (Destatis-Marktgröße neben unserem Floor-Wert)
- Incumbent-Firmografie (Handelsregister) + Distress-Flag (Insolvenz)

### Tab „Team" (Notizen/Log)
- Rein intern, **keine externe API** — nur unser Backend (User, Timestamp, Kommentar, Status-Log).

## Firmen-Anreicherung (Gewinner/Incumbent) — quer über Tabs
| Quelle | Feld | Auth/Kosten |
|---|---|---|
| **Insolvenzbekanntmachungen** (via handelsregister.ai/Insolvenz-Radar/Bundesanzeiger) | Insolvenz-Flag → **Displacement-Trigger** | komm. API / Scraping-Grauzone |
| **Bundesanzeiger / North Data** | Umsatz, Mitarbeiter, Bilanz des Gewinners | komm. |
| **Creditreform / D&B** | Bonität | komm., teuer |
| **VIES** (EU) | USt-IdNr.-Validierung | frei |

## Priorisierung (Wert × autonom-machbar)
1. **Wikidata Käufer-Anreicherung** — ✅ **UMGESETZT** (`scripts/enrich_wikidata.py` →
   `data/reference/buyer_external.parquet`, optional in `build_buyer_profile` gejoint).
   **709 Käufer** angereichert (552 Website, 668 Einwohner), **geo-disambiguiert** (nächster
   Kandidat < 25 km) → in der Stichprobe 0 Fehltreffer. Neue Felder: `website`, `population`,
   `wikidata_id`, `is_enriched`. Deckt die sauberen Kommunal-Käufer; große/fragmentierte
   Vergabestellen brauchen Handelsregister (#2).
2. **OffeneRegister/Handelsregister** — hebt Entity-Resolution (Fundament) + Firmografie. Größere
   Integration; Matching ist die Arbeit.
3. **Insolvenz-API** — der Novum-Trigger (Displacement), aber braucht gute Entities (nach #2) und
   i. d. R. kommerzielle API.
4. **Destatis** — €-Marktgröße/Baupreis, braucht (kostenlose) Registrierung → ein Token vom Nutzer.

## Bewusst NICHT autonom heute
- Destatis (Token nötig), Insolvenz/North Data/Creditreform (kommerziell/Auth), Plattform-Dokumente (AGB).
- Wikidata **nur mit Geo-Disambiguierung** (naives Label-Matching liefert falsche Orte — gemessen:
  25 Namen → 128 rohe Kandidaten).

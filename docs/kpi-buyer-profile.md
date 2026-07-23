# Vergabestelle-Analyse — KPI-Liste fürs Design

Quelle: `buyer_profile.parquet` (8.821 Käufer) + `buyer_recent_awards.parquet` (Feed, ≤20/Käufer).
Zwei Beispiel-Käufer als Bandbreite: **DB Netz AG** (groß, fragmentiert) · **LK Bad Tölz** (klein, captured).

## Kopf / Identität
| Feld | Bedeutung | DB Netz | Bad Tölz | UI |
|---|---|---|---|---|
| `buyer_name` | Name der Vergabestelle | DB Netz Aktiengesellschaft | Landkreis Bad Tölz-Wolfratshausen | Titel |
| `main_nuts` | Haupt-Region (NUTS) | DE7 (Hessen*) | DE2 (Bayern) | Region-Badge |
| `also_below_threshold` | auch unterschwellig aktiv? | ✅ (592 Tender) | – | Icon |

### Regions-Kontext (Destatis, `kreis_investitionen_eur`) — ⚠️ NICHT als Käufer-Budget zeigen
| Feld | Bedeutung | Beispiel |
|---|---|---|
| `main_nuts3` | Haupt-Kreis des Käufers (NUTS-3) | DE712 |
| `kreis_investitionen_eur` | **Investitionsauszahlungen des gesamten Kreises** (alle Kommunen) | 462 Mio € |
| `kreis_finanzen_jahr` | Datenjahr | 2023 |

> **Wichtig fürs Design:** Das ist das Budget **aller Kommunen im Kreis**, nicht das dieser
> Vergabestelle. Für **kommunale** Käufer (Stadt/Landkreis) ist es sinnvoller Kontext; für
> Bundes-/Unternehmens-Käufer (DB Netz, Autobahn GmbH, BImA) ist es **bedeutungslos** —
> dort besser ausblenden. **Keine Quote „Käufer-Volumen ÷ Kreisbudget"** bilden. Coverage: 72 %.

### Externe Anreicherung (Wikidata, nur Kommunal-Käufer — `is_enriched=true`)
| Feld | Bedeutung | Beispiel | UI |
|---|---|---|---|
| `website` | offizielle Website | https://www.kreis-lup.de/ | klickbarer Link |
| `population` | Einwohnerzahl (Regionsgröße) | 212.373 | Kontext-Zahl |
| `wikidata_id` | Wikidata-Referenz | Q5674 | Deep-Link (optional) |
| `is_enriched` | angereichert? (689 Käufer) | true | Icon/Fallback |

> Nur ~7 % der Käufer (saubere Kommunal-Namen) sind angereichert; große/fragmentierte Vergabe­stellen
> zeigen `is_enriched=false`. Fürs Design: Website/Einwohner nur rendern, wenn `is_enriched`.

## Aktivität
| Feld | Bedeutung | DB Netz | Bad Tölz | UI |
|---|---|---|---|---|
| `total_awards` | vergebene Aufträge (gesamt) | 8.559 | 25 | große Zahl |
| `first_year`–`last_year` | aktiver Zeitraum | 2017–2026 | – | Zeitspanne |
| `active_years` | Jahre mit Aktivität | 10 | – | – |
| `awards_per_year_recent` | Ø Aufträge/Jahr (letzte 2 J) | 1.803 | – | Kadenz |

## Volumen (ehrlich als Floor)
| Feld | Bedeutung | DB Netz | UI |
|---|---|---|---|
| `volume_known_eur` | Σ bekannter Auftragswerte (real-2020) | 4,02 Mrd € | KPI-Kachel |
| `median_award_eur` | Median-Auftragswert | 28.158 € | – |
| `value_coverage` | **% Aufträge mit echtem Wert** | 12 % | ⚠️ „Floor, X % gedeckt" |

> Wichtig: `volume_known_eur` ist **untertrieben** (nur `value_coverage` % der Aufträge tragen einen echten Wert). Immer mit dem Coverage-Flag zeigen — nie als Gesamtvolumen behaupten.

## Themen
| Feld | Bedeutung | DB Netz | Bad Tölz | UI |
|---|---|---|---|---|
| `top_division_label` | Haupt-Themenbereich (CPV-Division) | Bauarbeiten | Transport-/Beförderungsdienstl. | Kategorie-Chip |
| `n_categories` | Themen-Breite (distinkte CPV-Klassen) | 82 | – | „breit/fokussiert" |

## Lieferanten & Konzentration
> ⚠️ **Zwei verschiedene Grundgesamtheiten — nicht mischen!**
> `total_awards` (8.559) kommt aus dem **Auslauf-Radar** (gefilterte Teilmenge).
> Alle Gewinner-Zahlen kommen aus der **vollen Vergabe-Historie** — Basis ist **`wins_total`** (22.654).
> Gewinner-Anteil also **immer durch `wins_total` teilen**, nie durch `total_awards`.
> Beispiel korrekt: Leonhard Weiss 1.321 / 22.654 = **5,8 %** (nicht 15 %).

| Feld | Bedeutung | DB Netz | Bad Tölz | UI |
|---|---|---|---|---|
| **`wins_total`** | **Basis** aller Gewinner-Anteile | 22.654 | – | Nenner |
| `n_contractors` | verschiedene Auftragnehmer (Historie) | 2.231 | – | – |
| `n_distinct_winners` | Gewinner im Auslauf-Radar (andere Basis!) | 805 | – | eher nicht zeigen |
| `top3_share` | Top-3-Anteil an `wins_total` | 14 % | 72 % | Balken |
| `concentration` | Label: `fragmentiert`/`moderat`/`oligopol` | fragmentiert | oligopol | farbiges Badge |
| `top_winners` | Top-3-Gewinner (Namen) | Leonhard Weiss, DB Engineering, DB Bahnbau | Regionalverkehr Oberbayern, … | Liste |

## Wettbewerb
| Feld | Bedeutung | DB Netz | Bad Tölz | UI |
|---|---|---|---|---|
| `single_bidder_rate` | % Aufträge mit nur 1 Bieter | 35 % | – | Prozent |
| `competition_flag` | **Ampel** (s. u.) | 🟡 gelb | – | Ampel-Badge |
| `avg_bidders` | Ø Bieterzahl | 3,1 | – | – |

**Ampel-Schwellen** (`competition_flag`, an der Verteilung aktiver Käufer geeicht: Median 15, Q3 26, P90 43 — EU-Red-Flag-Zone):
- 🟢 **gruen** — `single_bidder_rate` < 15 % (kompetitiv)
- 🟡 **gelb** — 15–34 % (auffällig)
- 🔴 **rot** — ≥ 35 % (unkompetitiv, Warnsignal)
- `NULL` — zu wenige Aufträge für ein Urteil

Verteilung: 🟢 4.245 · 🟡 810 · 🔴 1.661 · (k.A. 2.105)

## Verhalten
| Feld | Bedeutung | DB Netz | Bad Tölz | UI |
|---|---|---|---|---|
| `retention_rate` | % Fälle, in denen der Amtsinhaber gehalten wird | 19 % (wechselfreudig) | 80 % (treu) | Skala treu↔offen |
| `avg_decision_days` | Ø Tage cn→Zuschlag | 103 | – | – |

## Feed: `buyer_recent_awards` (letzte 20/Käufer)
| Feld | Bedeutung | Beispiel (DB Netz) |
|---|---|---|
| `vergabe_datum` | Zuschlagsdatum | 2026-06-24 |
| `titel` | Auftragstitel | „SOC-Anbindung SIDIS-RBC …" |
| `winner` | Gewinnerfirma | Siemens Mobility GmbH |
| `value_eur` + `value_known` | Wert + ob echt | – (known=false) |
| `single_bidder` | nur 1 Bieter? | true |
| `cpv_class` + `cpv_class_label` | Thema (Code + Klartext, 99 % gedeckt) | 3463 → „Teile für Eisenbahn-… / rollendes Material" |

## Design-Skalen (Verteilungen über alle Käufer)
- `single_bidder_rate`: 0 … median 0 … 100 % (die *aktiven* Käufer tragen das Signal)
- `retention_rate`: 0 … **median 26 %** … 100 %
- `value_coverage`: 0 … **median 50 %** … 100 %
- `concentration`: oligopol 4.153 · fragmentiert 3.268 · moderat 1.400

\* Käufer-NUTS teils grob/fragmentiert (bekannte Entity-Schwäche); große Käufer sauber.

# KPIs: Regionen & externer Kontext — Design-Referenz

Alles, was nach den Vergabestellen-KPIs dazugekommen ist. Quellen: `region_kpi.parquet`
(422 NUTS-3-Regionen), `buyer_profile.parquet` (Anreicherung), Destatis + Wikidata.

**Beispielregionen:** Frankfurt a. M. (Großstadt, Bundes-Hub) · Bonn (Bundes-Hub).
⚠️ Beide sind **Ausreißer** — für Default-Ansichten die Mediane als Normalfall nehmen.

---

## 1 · Vergabestelle: externe Anreicherung (Wikidata)
| Feld | Bedeutung | Beispiel | Coverage |
|---|---|---|---|
| `website` | offizielle Website (klickbar) | https://www.kreis-lup.de/ | 535 Käufer |
| `population` | Einwohner der Gebietskörperschaft | 212.373 | 649 Käufer |
| `wikidata_id` | Referenz (optionaler Deep-Link) | Q5674 | 689 |
| `is_enriched` | angereichert? → **Gate fürs Rendern** | true | 689 / 8.821 |

> Nur kommunale Käufer (Stadt/Landkreis/Gemeinde). Bei `is_enriched=false` Block ausblenden.

## 2 · Vergabestelle: Regions-Kontext (Destatis)
| Feld | Bedeutung | Beispiel | Coverage |
|---|---|---|---|
| `main_nuts3` | Haupt-Kreis des Käufers | DE712 | — |
| `kreis_investitionen_eur` | Investitionsbudget **des ganzen Kreises** | 462 Mio € | 6.334 |
| `kreis_finanzen_jahr` | Datenstand | 2023 | — |

> ⚠️ **Nicht** als Budget dieser Behörde zeigen und **keine Quote** daraus bilden. Bei Bundes-/
> Konzern-Käufern (DB Netz, BImA, Autobahn GmbH) sinnvollerweise ausblenden.

---

## 2b · Lead → Markt-Region (⚠️ Kernregel)
| Feld | Bedeutung | Beispiel |
|---|---|---|
| `market_nuts3` | **Leistungsort** (NUTS-3) — die Region des Marktes | DE251 |
| `market_region_name` | Klartext | Ansbach, Landkreis |
| **`market_region_ok`** | Markt-Kontext zeigbar? (91 % der Leads) | true |

> **Regionalen Marktkontext NUR bei `market_region_ok = true` zeigen.** Die Region kommt aus dem
> **Leistungsort**, nicht aus dem Käufersitz — DB Netz sitzt in Frankfurt und baut Gleise in
> 17 Bundesländern. Bei Käufersitz-Logik bekämen **13.481 Leads (18,3 %) den falschen Markt**.
> Ist der Leistungsort unbekannt oder zu grob (9 %), lieber **nichts** zeigen als den falschen Markt.

## 3 · Region: Nachfrage (unsere Daten)
| Feld | Frankfurt | Bonn | Median | UI |
|---|---|---|---|---|
| `n_vergeben` | 9.571 | 2.391 | — | große Zahl |
| `n_offen` | 107 | 557 | — | „aktuell offen" |
| `n_vergabestellen` | 128 | 196 | — | — |
| `volumen_2023_eur` | 2.093 Mio € | 1.019 Mio € | — | mit Coverage! |
| `volumen_coverage` | 13 % | 33 % | — | ⚠️ „Untergrenze" |
| `single_bidder_rate` | 32 % | 33 % | — | Ampel wie Käufer |

## 4 · Region: Angebotsseite (A) — **neu**
| Feld | Frankfurt | Bonn | Median | p90 | Coverage |
|---|---|---|---|---|---|
| `baubetriebe` | 591 | 129 | **172** | 376 | 322/422 |
| `bau_beschaeftigte` | 8.333 | 1.056 | — | — | 322/422 |
| `bau_umsatz_eur` | — | — | — | — | 322/422 |
| **`auftraege_je_betrieb`** | 16,19 | 18,53 | **0,34** | 1,63 | 322/422 |

> ⚠️ **Nur deskriptiver Kontext — KEINE Erklärgröße.** `auftraege_je_betrieb` beschreibt das
> Verhältnis Nachfrage/Baubetriebe einer Region. Die naheliegende These „erklärt hohe
> Single-Bieter-Quoten" wurde **geprüft und widerlegt**: Single-Bieter-Quote je Dichte-Quartil
> = 21 % / 21 % / 19 % / 22 % (flach), Korrelation **0,099** (n=322 Regionen).
>
> Wahrscheinlicher Grund: **Baufirmen sind mobil** — eine bayerische Firma bietet in Sachsen.
> „Betriebe in diesem Kreis" ist deshalb nicht der relevante Anbieterpool; Wettbewerb entsteht
> pro **Gewerk/CPV**, nicht pro Landkreis. Für einen echten Ex-ante-Wettbewerbsindikator bräuchte
> es einen CPV-genauen Anbieterpool (z. B. Präqualifikationsverzeichnisse).
>
> **Fürs UI:** als Strukturzahl der Region zeigen, nicht als Chancen-/Erklärsignal formulieren.

## 5 · Region: Vorlaufindikator (B) — **neu**
| Feld | Frankfurt | Bonn | Median | p90 | Coverage |
|---|---|---|---|---|---|
| `genehmigungen_gesamt` | 347 | 158 | **135** | 383 | **422/422** |

> Baugenehmigungen laufen Bau-Ausschreibungen zeitlich voraus → Frühindikator für kommendes
> Volumen. Einzige vollständig gedeckte Kontext-Kennzahl.

## 6 · Region: Fiskalische Lage (C) — **neu**
| Feld | Frankfurt | Bonn | Median | p90 | Coverage |
|---|---|---|---|---|---|
| `investitionen_eur` | 462 Mio € | 174 Mio € | — | — | 320/422 |
| `investition_je_kopf_eur` | 616 € | 540 € | **642 €** | 1.004 € | 319/422 |
| `schulden_je_kopf_eur` | 3.543 € | 6.384 € | **1.276 €** | 3.304 € | 315/422 |

> Hohe Schulden/Kopf → sinkende Investitionsfähigkeit → schrumpfende Nachfrage.

## 7 · Region: Normalisierung (D) — **neu**
| Feld | Frankfurt | Bonn | Median | p90 |
|---|---|---|---|---|
| `bevoelkerung` | 749.596 | 321.680 | — | — |
| `sv_beschaeftigte` | — | — | — | — |
| `auftraege_je_1000_ew` | 12,77 | 7,43 | **0,40** | 1,11 |

> Macht Regionen fair vergleichbar (statt „groß gewinnt immer").

## 8 · Marktabdeckung — mit Vorsicht
| Feld | Frankfurt | Bonn | Median | p90 | Coverage |
|---|---|---|---|---|---|
| `intensitaet_pct` | 453 % | 587 % | **1,6 %** | 31 % | **132/422** |

> Sichtbares Auftragsvolumen 2023 ÷ Investitionsbudget 2023. **Als Signal lesen, nicht als Quote:**
> - **~2 % (Median)** = normal: der Großteil kommunaler Investitionen wird nicht als
>   Ausschreibung sichtbar (unterschwellig/Direktvergabe/fehlende Werte) → **die Marktlücken-Story**
> - **>100 %** = in dieser Region dominieren Bundes-/Konzern-Käufer, deren Aufträge nicht aus dem
>   Kommunalhaushalt stammen → **Hub-Signal**, kein Fehler
> - Nur 31 % der Regionen befüllt (braucht Volumen **und** Budget)

---

## 9 · Datenstand (Pflicht-Labels)
| Datenblock | Stand | Anzeige |
|---|---|---|
| Leads / Ausschreibungen / Fristen | tagesaktuell (DÖE 2026-07, TED 2026-06) | — |
| Käufer-Website/Einwohner (Wikidata) | live | — |
| **Alle Destatis-Kontextzahlen** | **2023** | „Stand 2023" ans Feld |
| Handelsregister-Firmografie | 2017–2019 | „Stand 2018" + Warnhinweis |

## Bekannte Lücken (ehrlich)
- **Gleichnamige Kreise** (z. B. München Stadt/Landkreis) werden bewusst **nicht** zugeordnet →
  Kontext dort NULL statt falsch. Betrifft ~100 der 422 Regionen.
- ~~DÖE-Leads fehlen in `region_kpi`~~ — **behoben**: `region_kpi` aggregiert jetzt über den
  Leistungsort, damit sind die DÖE-Leads drin (422 → 436 Regionen).

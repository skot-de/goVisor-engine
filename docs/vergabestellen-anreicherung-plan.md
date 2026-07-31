# Vergabestellen-Anreicherung — Plan & Messung

**Ziel:** die verbleibende Schwäche bei den Vergabestellen (18,4 % register-belegt, viele
nur-Name-Fragmente) mit externen/autoritativen Quellen angehen. **Grundsatz: messen statt
annehmen** — jede der drei angedachten Quellen ist unten an echten Daten geprüft. Ergebnis:
**zwei Fallen entschärft, ein sauberer in-house-Hebel gefunden, eine Quelle auf „Validierung
statt Merge" zurechtgerückt.**

Stand: 2026-07-31. Basis: Käufer-Entitäten nach dem Leitweg-Rebuild (75.363, davon 18,4 %
national_id). Vorläufer: [[govisor-datenqualitaet]], Leitweg-Arbeit in `gold.py`.

---

## Übersicht (gemessen)

| Hebel | sauberes Potenzial | sauber? | Download nötig? | Aufwand |
|---|---:|:--:|:--:|---|
| Leitweg-Anker | −704 (erledigt) | ✓ | nein | ✅ gebaut |
| **USt-IdNr-Anker (guarded)** | **~584 Merges** | ✓ mit Token-Guard | **nein (in-house)** | 1 Pass (wie Leitweg) |
| Destatis-AGS als *Merge*-Schlüssel | ~412 roh | ✗ **über-mergt** | ja | verworfen |
| Destatis Gemeindeverzeichnis als *Label/Validierung* | Qualität, nicht Menge | ✓ | ja | mittel |
| Offizielles Leitweg-ID-Verzeichnis (KoSIT) | autoritative Namen je Leitweg | ✓ (falls offen) | ja | zu prüfen |

**Kernaussage:** Der größte *saubere automatische* Rest-Hebel ist der **USt-IdNr-Anker in-house**
(kein Download). Die extern gehoffte AGS-Gruppierung ist bei Messung **kein sauberer Merge**;
Destatis liefert **Qualität (Namen/Validierung), nicht Masse**.

---

## 1. USt-IdNr-Anker (in-house, empfohlen zuerst)

**Lücke:** `resolve_supplier` verwirft die USt-IdNr für öffentliche Stellen genau wie die
Leitweg-ID (PUBLIC/Person/Konsortium kehren vor dem `national_id`-Zweig zurück). 5.056 distinkte
Käufer tragen eine USt-IdNr — toter Anker.

**Gemessen:**
- Käufer-Instanzen mit USt-IdNr: **92.197** (4.008 eindeutige Keys nach Entität).
- VAT-Cluster mit ≥2 Ist-Entitäten: **646**.
- **Falle:** manche USt-IdNr sind über Verwaltungsgemeinschaften **geteilt** — `DE309506861`
  hängt an „Gemeinde Bous / Eurasburg / Langerringen" (drei verschiedene Gemeinden!). Ein naiver
  VAT-Merge wäre falsch.
- **Guard = gemeinsamer signifikanter Namens-Token** (Heidelberg-Varianten mergen, Bous≠Eurasburg
  nicht): davon **447 Cluster sicher → 584 Merges**; 199 riskante Cluster (kein gemeinsamer Token)
  fallen raus.

**Umsetzung:** `_consolidate_by_vat` analog zu `_consolidate_by_leitweg`, plus **Token-Guard**
(Cluster nur mergen, wenn alle Entitäten ≥1 signifikanten Namens-Token teilen). Gleiche
Ketten-Kompression, gleicher Test-Aufbau. **Kein Download, ~584 saubere Merges, ein Rebuild.**

## 2. Destatis Gemeindeverzeichnis — Validierung & Labels (nicht Merge)

**Warum NICHT als Merge-Schlüssel:** Die Leitweg-Grobadressierung *ist* der AGS
(09162000 = München). Naiv nach AGS zu gruppieren wäre verlockend, aber gemessen **über-mergt** es:
- Kurze Codes sind Routing-Präfixe, keine Behörden: `991` (797 Entitäten = Bund-Platzhalter),
  2-stellig `08/09/11/12` = ganzes Bundesland. → nur volle 8/12-stellige Codes taugen.
- Aber selbst voller Gemeinde-AGS fasst ein **Territorium**, keinen Rechtsträger: AGS 09162000
  zieht „München Klinik gGmbH" + Stadtbibliothek zusammen, AGS 05334002 „Aachener Parkhaus GmbH"
  + STAWAG. Das sind **eigene** Vergabestellen. Der bestehende `_consolidate_by_municipality`
  ist konservativer (fasst nur namensmatchende Kommunal-Stellen) und bleibt die richtige Ebene.

**Was Destatis sauber liefert:**
1. **Validierung**: welche Leitweg-Grobcodes echte Gemeinden sind → Junk (991/Bundesland) sicher
   ausschließen statt per Heuristik-Schwelle.
2. **Kanonische Namen**: AGS → offizieller Gemeindename für schöne Labels der leitweg-/muni-
   gemergten Entitäten.
3. **Ebenen-Klassifikation**: Gemeinde vs. Kreis vs. Land — verbessert die Disambiguierung im
   Municipality-Pass (heute geonames-Kreis-Rateschritt).

**Quelle (für Freigabe):** Destatis GV-ISys „Gemeindeverzeichnis" (AGS + Name + Fläche/Einwohner),
offen lizenziert (dl-de/by-2-0), CSV/XLSX, ~12.000 Gemeinden, wenige MB.
→ *Download braucht deine Freigabe* (Dateiname/Quelle/Größe nenne ich beim Ziehen).

## 3. Offizielles Leitweg-ID-Verzeichnis (KoSIT) — prüfen

Falls es ein offenes Verzeichnis Leitweg-ID → Behördenname gibt (KoSIT/Leitweg-ID-Vergabestellen),
wäre das der **ideale** Label-Layer: autoritativer Name für alle 3.749 leitweg-getragenen Entitäten.
Existenz/Lizenz noch zu prüfen (kein Blindflug — erst recherchieren, dann ziehen).

---

## Empfohlene Reihenfolge

1. **USt-IdNr-Anker (guarded)** — in-house, ~584 saubere Merges, kein Download. Sofort baubar,
   ein Rebuild. *Größter sauberer automatischer Rest-Hebel.*
2. **Destatis Gemeindeverzeichnis** ziehen (nach Freigabe) → als **Validierungs-/Label-Layer**:
   Junk-Leitweg-Codes ausschließen, kanonische Gemeindenamen, Municipality-Disambiguierung härten.
3. **Leitweg-ID-Verzeichnis** (KoSIT) recherchieren; falls offen → autoritative Labels.

**Bewusst NICHT:** AGS-Gruppierung als Automatik-Merge (über-mergt Kommunal-GmbHs);
naiver VAT-Merge ohne Token-Guard (geteilte Verwaltungsgemeinschafts-VATs).

---

## Messskripte (Reproduzierbarkeit)
Die Zahlen oben stammen aus Ad-hoc-Messungen gegen `data/silver/DE/notice_parties` +
`data/gold/DE/{entities,party_entity}.parquet` (Leitweg-/VAT-Normalisierung via
`gold.normalize_national_id`). Für die Umsetzung wandern sie in `_consolidate_by_vat` + Test
analog zu `test_consolidate_by_leitweg`.

# v1-Ticket: DÖE-Unterschwellen-Ingest (zweite Lead-Quelle) — ✅ UMGESETZT

**Ergebnis (2026-07):** 384.034 DÖE-Notices (2023-01…2026-07) im Silber, **3.864 aktuell
offene Unterschwellen-Leads** (Slug-Prefix `d`, Phase f02) zusätzlich → 78.201 Leads gesamt.
Käufer + Leistungsart 100 %, FK sauber, 124 Tests grün. Module: `govisor/doe.py` (Fetch),
`silver.build_month_doe`+`consolidate_doe`, `cli ingest-doe`, `refresh_doe` (aktiv).

**Zwei nicht-offensichtliche Fixes (gemessen, nicht angenommen):**
1. **Cross-Monat-Dubletten:** DÖE re-exportiert offene Notices in MEHREREN Monatspaketen
   (TED nie). → Staging außerhalb des Globs + `consolidate_doe` (späterster Monat gewinnt je notice_id).
2. **hive-Layout:** Gold liest Silber mit `hive_partitioning=1` → Konsolidat MUSS unter
   `year=YYYY/` liegen (nicht `doe/`), sonst Partition-Mismatch → verfälschte Reads/Fan-out.

**Offene Qualitäts-Punkte (kein Blocker):** DÖE-Lean-Notices tragen nur 2-stelliges CPV →
`cpv_label` nur 34 % (natur_kat trotzdem 100 % via Division); Käufer-NUTS 0 % → Region 12 %
(Leistungsort-Fallback greift teils). Beides Datenrealität der Unterschwellen-eForms.

---


**Ziel:** Unterschwellige DE-Vergaben aus dem Datenservice Öffentlicher Einkauf (DÖE) in die
Pipeline ziehen → ~+84 % laufender Lead-Zufluss (~6.200/Monat), die TED strukturell nie enthält.
Grundlage: [`docs/spike-doe-datenquelle.md`] (alles gemessen). CC0-Lizenz, kein Rechtsrisiko.

## Kernentscheidungen (aus dem Spike)
1. **Nur das `de-*`-Subset ingesten** (procedureLegalBasis `de-vob`/`de-vol`/`de-uvgo`/`de-hhr`).
   Oberschwellige DÖE-Notices SIND TED-Dubletten (UUID ≠ TED-Nummer, kein sauberer Join) → durch
   den `de-*`-Filter **kein Dedup-Problem**. Oberschwellig kommt weiter aus TED.
2. **Format `eforms.zip`, NICHT csv.zip.** DÖE liefert UBL-eForms (`eforms-de-2.1`) — **dasselbe
   Format, das `schema._parse_eforms` bereits parst.** Parser wiederverwenden statt das 12-Tabellen-
   CSV-Schema neu zu mappen. (CSV war nur fürs Spike-Messen praktisch.)
3. **Quelle flaggen** `source='doe_unter'` (bzw. `schema_gen='doe'`), damit Herkunft im Lead sichtbar
   ist und wir DÖE vs. TED getrennt auswerten können.
4. **Zeitraum:** Backfill ab **2023-01** (Unterschwelliges ist ab da voll da, ~3,5 J Historie) +
   laufend inkrementell. DÖE geht nicht vor 2023 → TED bleibt das historische Rückgrat.

## Architektur (Medallion, analog TED)
- **Bronze:** DÖE-ZIPs roh ablegen (`data/raw_doe/DE/<YYYY-MM>.eforms.zip`), verlustfrei. Pull über
  `GET https://oeffentlichevergabe.de/api/notice-exports?pubMonth=YYYY-MM&format=eforms.zip`
  (auch `pubDay=`). Keine Auth.
- **Silber:** neuer `silver.build_month_doe()` (oder Erweiterung): eForms-XML aus dem ZIP durch
  `schema._parse_eforms` → auf die **bestehende `notices`/`notice_parties`/`notice_cpv`…-Schema**
  schreiben, `schema_gen='doe'`, Filter `RegulatoryDomain LIKE 'de-%'`. Dedup je
  `noticeIdentifier` (letzte `VersionID` gewinnt).
- **Gold:** unverändert — `build_leads`, `build_lead_geo`, `build_lead_detail`, `build_lead_export`
  laufen über die vereinigten Silber-Notices. Neue DÖE-Leads erscheinen automatisch (Phase `f02`,
  offene Ausschreibung).

## Bekannte Anpassungen (GEMESSEN an 800 echten DÖE-`de-*`-Notices, 2026-05)
`schema.parse` läuft **fehlerfrei** (0 Crashes), aber mit zwei Lücken — Feldabdeckung gemessen:

| Feld | Coverage | Status |
|---|---|---|
| title | 100 % | ✅ |
| cpv_main | 95 % | ✅ |
| performance_nuts | 77 % | ✅ |
| submission_deadline | 75 % | ✅ |
| **buyer_name** | **0 %** | 🔴 **Fix nötig** |
| contract_nature (BT-23) | 7 % | 🟡 fällt auf CPV-Heuristik zurück (ok) |

- **🔴 buyer_name = 0 %:** DÖE-Unterschwellen-eForms tragen **keinen `efac:Organizations`-Block** —
  unser `_parse_eforms` liest den Käufer aber genau daraus. Der Name steht inline unter
  `cac:ContractingParty/cac:Party/cac:PartyName/cbc:Name` (verifiziert, z. B. „Generalzolldirektion
  Zentrale Beschaffungsstelle…"), teils in anderen Varianten. **Fix:** Fallback-Kette im eForms-Parser
  (inline ContractingParty-PartyName, dann weitere Encodings). **Pflicht** — Käufer ist das #1-Lead-Feld.
- **🟡 contract_nature 7 %:** unterschwellig ist BT-23 meist nicht gesetzt → `natur_kat` via
  CPV-Fallback, `natur_src='geschaetzt'`. Kein Blocker, ehrlich geflaggt.
- **Bronze-Prep läuft:** eForms-ZIPs 2023-01…2026-07 werden nach `data/raw_doe/DE/` vorgeladen
  (idempotent), damit der Ingest direkt darauf aufsetzen kann.
- **Käufer-NUTS fehlt (0 %):** bei Unterschwellen-Notices ist die Käufer-Region unbefüllt (nur
  Leistungsort-NUTS 75 %). Für die Käufer-Achse der Radius-/Regionssuche → Käufer-Region aus PLZ
  (via `dim_plz`) oder Name ableiten; sonst auf Leistungsort-NUTS zurückfallen. In `build_lead_geo`
  behandeln.
- **Historie flach für Nachfolge:** DÖE-Unterschwelliges hat wenig Award-Historie (~3,5 J) → DÖE-Leads
  zunächst v. a. „offene Ausschreibung" (f02), kaum Auslauf-Radar/Incumbent. Ehrlich flaggen, keine
  erfundene Wechsel-Historie.

## Aufgaben
1. `bulk`-Analogon für DÖE: `fetch_doe(month|day, fmt='eforms.zip')` + Fingerprint-Cache (HEAD/Größe).
2. `silver.build_month_doe()` — ZIP → `_parse_eforms` → Silber, `de-*`-Filter, `schema_gen='doe'`.
3. `_parse_eforms` an DÖE-Notices validieren + härten (Feldabdeckung messen wie beim TED-Parser).
4. `build_lead_geo`: Käufer-Region-Fallback (PLZ→dim_plz, sonst Leistungsort-NUTS).
5. `verify.gold_integrity`: DÖE-Leads mit in die FK-Checks.
6. CLI: `python -m govisor.cli ingest-doe --start 2023-01` (Backfill) + in `refresh.py` einhängen.
7. Backfill 2023-01…heute fahren, Volumen/Coverage gegen Spike-Zahlen prüfen (Regression).
8. Tests: Parser-Fixture (eForms-DE), `source='doe_unter'`-Vokabular, FK.

## Täglicher Runner (s. eigene Frage)
- **TED: steht** — `scripts/refresh.py` (laufendes + voriges Monatspaket, Silber→Gold→FK), launchd
  `de.govisor.refresh.plist` (06:00, **nicht aktiviert**).
- **DÖE: Verdrahtung steht schon** — `refresh.py` ist mehrquellen-/mehrländerfähig (Source-Registry
  + Länder-Loop + geteilter Gold/Verify-Tail je Land). DÖE ist als `refresh_doe`-**Stub** registriert
  (`enabled=False`). Zu tun: den Stub implementieren (laufenden `pubMonth` als `eforms.zip` ziehen,
  idempotent/versioniert, `de-*`-Silber bauen, fresh zurückmelden) und in `SOURCES` `enabled=True`
  setzen. Der gemeinsame Gold-Rebuild + FK deckt dann beide Quellen ab → **ein** täglicher Job hält
  TED **und** DÖE frisch. Erst nach Go-Live via launchd aktivieren.

## Aufwand (grob)
~2–3 Tage: Tag 1 Bulk+Silber+Parser-Validierung, Tag 2 Geo-Fallback+CLI+Backfill, Tag 3 refresh-
Integration+Tests. Risiko niedrig (Parser existiert, Format bekannt, CC0).

## Definition of Done
- Backfill 2023-01…heute in Silber (`schema_gen='doe'`, nur `de-*`), Gold-Rebuild FK-sauber.
- DÖE-Leads in `lead_export` mit `source='doe_unter'`, Geo befüllt (Käufer-Fallback greift).
- `refresh.py` zieht TED **und** DÖE; ein Trockenlauf grün. Tests grün.

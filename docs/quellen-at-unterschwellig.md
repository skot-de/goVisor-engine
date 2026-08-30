# Quelle AT unterschwellig — OffeneVergaben.at (data.gv.at / BVergG2018)

**Stand 2026-07-29.** Discovery/Kontrakt für die vierte technische Basis (`offeneverg-csv`).
Schließt die letzte echte DACH-Lücke: **Österreich unterschwellig**. Registry-Eintrag
`offeneverg-at` in `govisor/sources.py`.

## Warum diese Quelle (und nicht ANKÖ)

AT oberschwellig ist über TED gelöst (`build_at_gold`-Brücke steht). Darunter fehlt alles.
Zwei Wege:

| | OffeneVergaben.at | ANKÖ / vergabeportal.at |
|---|---|---|
| Zugang | **offen** (Open Data, Open Source) | kommerziell, Login, kein offener Feed |
| Quelle | data.gv.at, BVergG2018-Pflichtdaten | Amtsblätter + Amtlicher Lieferanzeiger |
| Format | CSV-Bulk, täglich | Portal/Abo |
| Volumen | Pflichtpublikation **>50k €** | ~3.000/Tag (inkl. <50k) |

**Entscheidung: OffeneVergaben.at.** Offen, offiziell fundiert, sofort integrierbar.

> ⚠ **Berichtigung 2026-08-30 an der Tabelle darüber.** Die Zeile „ANKÖ: kein offener Feed"
> ist falsch. ANKÖ betreibt eine **offene, per BVergG 2018 verpflichtende Kerndatenquelle**
> unter **CC BY 4.0**: `http://ogd.ankoe.at/api/v1/notices`, XML im `kdq`-Schema des BRZ,
> **41.709 Bekanntmachungen seit März 2019**, ohne Anmeldung abrufbar. Kommerziell ist das
> PORTAL, nicht die Pflichtpublikation — und die beiden wurden hier in einen Topf geworfen.
>
> **An der Entscheidung ändert das nichts, aber ihre Begründung war die falsche.** Der
> tragfähige Grund ist eine Messung: ANKÖ veröffentlicht die Kerndaten SEINER Auftraggeber,
> OffeneVergaben.at bündelt die aller Publizierenden — **238.979 Sätze gegen 41.709**,
> dasselbe Recht, dieselbe Lizenz, das Fünfeinhalbfache. Dazu sind **96 % der ANKÖ-Sätze
> Zuschläge** (Stichprobe 89 aus 2026: 85× `KD_8_2_Z1`, 4× `KD_8_1_Z2` mit Frist), also
> genau die Schicht, die atverg ohnehin führt.
>
> Nicht bauen, solange atverg läuft. Registry-Eintrag `ankoe-at` = `research`.

> ⚠ **Und das Unternehmensserviceportal (USP) ist keine Quelle.** Am 2026-08-30 geprüft, weil
> es auf der Portalliste stand: das USP ist das **Meldeformular**, mit dem Auftraggeber ihre
> Kerndaten-Metadaten auf data.gv.at eintragen — mit Anmeldung und dem Rollenrecht
> „eProcurement Metadaten-Ersteller". Die Ausschreibungssuche darauf
> (`ausschreibungen.usp.gv.at`) bündelt genau die Kerndatenquellen, die dort registriert
> wurden, und hat keine öffentliche Schnittstelle (`/api/*`, `/v3/api-docs`, `/swagger-ui`,
> `/actuator` → 404 bzw. 403). Wer die Daten will, liest die Quellen selbst — und das tut
> `offeneverg-at` bereits. Registry-Eintrag `usp-at` = `research`.

## Rechtsgrundlage / Abdeckung

Seit **März 2019** müssen österreichische Auftraggeber Ausschreibungen **und** Zuschläge über
**50.000 €** gemäß BVergG 2018 als **Open Data** auf `data.gv.at` publizieren (die „Kerndaten").
Ausnahmen für Bekanntmachungen unter 50k. Das ist die Pflicht-Untergrenze — vergleichbar mit
DÖE in DE, nur über einen anderen Kanal (Open-Data-Metadaten statt eForms-API).

## Technischer Zugang (verifiziert)

- **BULK-Kerndaten CSV**, UTF-8, Trennzeichen `,`, **täglich** aktualisiert (~32 MB).
- Download: `https://offenevergaben.at/downloads/kerndaten_dump_daily?format=csv`
- Kein JSON/XML, keine dokumentierte REST-API — der Tages-Bulk genügt (wie unsere anderen
  Bulk-Quellen). Projekt ist **Open Source** (GitHub-Scraper + App), gefördert über netidee.
- Lizenz: Open Data (data.gv.at, i. d. R. CC-BY 4.0 — beim Bau final prüfen).

## Connector GEBAUT (`govisor/atverg.py`, 2026-07-29)

Bronze + Silber fertig und smoke-getestet gegen den echten Tages-Dump (236.118 Records).

> **Stand 2026-08-30: läuft.** Der Voll-Ingest wartete auf den externen Speicher — den es seit
> dem 2026-07-29 gibt. Gemessen: Bronze lädt täglich (34 MB, zuletzt 28./29./30.08.), Silber
> führt **238.979 atverg-Sätze** (158.945 `can` / 80.034 `cn`), und **10.947 der 18.284
> AT-Gold-Leads** tragen die `atv-`-Kennung. Von den `cn`-Sätzen haben 995 eine Frist in der
> Zukunft. Der Registry-Eintrag stand bis heute auf `prepared` und beschrieb damit den
> Bauzustand von Ende Juli, nicht den Betrieb.

1. **Bronze:** `atverg.download()` — GET der Downloads-Seite, ZIP-URL aus dem HTML parsen
   (`_ZIP_RE`, da Zeitstempel+Hash pro Aufruf), ZIP nach `data/raw_atverg/AT/<stamp>.zip`.
2. **Silber:** `atverg.build_silver()` — DuckDB liest die CSV aus der ZIP (robuste RFC4180-Quotes),
   mappt auf `notices`/`notice_parties`/`notice_cpv`/`awards`/`attributes` (schema-treu via
   `model.TABLES`), `schema_gen='atverg'`, `country='AT'`. notice_id = `atv-<id>` (eigener
   Namensraum, keine Kollision mit TED-AT). Hive-Partition nach Jahr.
3. **Gold:** **kein eigener Builder** — `build_at_gold` liest `silver/AT` und zieht die
   atverg-`cn`-Leads automatisch (verifiziert: 1.020 Leads aus dem Sample). **OSB-Dedup gebaut**:
   `build_at_gold` schließt atverg-Notices mit `attributes.atverg/schwelle='OSB'` aus (TED-AT ist
   die oberschwellige Autorität). Da TED nur oberschwellig und atverg-USB nur unterschwellig führt,
   sind beide danach disjunkt — kein Content-Matching nötig. No-op, solange keine atverg-attributes
   existieren (reiner TED-AT-Bestand). Regressions-Test `test_plumbing.py::test_at_gold_osb_dedup`.
4. **CLI:** `ingest-atverg [--silver] [--skip-download] [--force]`.
5. **Registry:** `offeneverg-at` = `prepared`. Web-Export unioniert `gold/AT/…` automatisch.

### Gemessenes Mapping (236.118 Records, 2026-07-28)

| CSV-Spalte | → Silber | Wert/Format |
|---|---|---|
| `art` | `notice_kind` | `KD_x_1_*`→cn (79k), `KD_x_2_*`→can (157k) |
| `auftragsart` | `contract_nature` | Bau/Dienstleistung/Liefer + Konzessionen |
| `cpv` | `cpv_main` | `"72000000 IT-Dienste…"` → 8-Stellen-Code (99,9 %) |
| `wert` | `estimated_value` | EUR-Zahl (65 % gesamt, aber v. a. bei Zuschlägen) |
| `schlusstermin für den eingang` | `submission_deadline` | DD.MM.YYYY (24 %, cn-lastig) |
| `auftraggeber` (+ `stammzahl`) | party buyer (+ national_id) | 100 % / **97,6 % ID** |
| `lieferant` (+ `stammzahl`) | party winner + award | 67 % (Zuschläge) |
| `anzahl eingegangener angebote` | `awards.num_tenders` | Bieterzahl |
| `oberschwellenbereich/…` | `attributes.atverg/schwelle` | OSB 82k / USB 72k |

## Fallstricke (gemessen / recherchiert)

- **Nur >50k €** — die kleinsten Direktvergaben fehlen. Ehrlich flaggen.
- **Wert bei offenen Ausschreibungen (cn) meist NULL** — der Auftragswert steht vor Zuschlag oft
  nicht in den Kerndaten (im Sample 0/1020 cn-Leads mit Wert). Gebühren-Band läuft dann auf CPV-
  Median-Imputation (wie bei anderen wertlosen Leads).
- **Geo schwach:** kein `postal_code`, `nuts_code` nur 33 % gefüllt und oft nur „AT" → Umkreis-
  suche für AT-unterschwellig kaum bedienbar. `geo_source='none'` ehrlich setzen.
- **OSB-Overlap (~36 %)** mit TED-AT — vor dem Live-Schalten in Gold ausschließen/deduplizieren.
- **Datums-Sentinels:** vereinzelt Fristen wie `31.12.2038` (Platzhalter „offen") — beim Lead-
  Filter beachten.
- CSV-Schema kann sich ändern (Scraper-Projekt) — defensiv mappen, Unbekanntes → `attributes`.
- **ZIP-URL flüchtig:** `/tmp/…_<hash>.zip` wird pro Aufruf frisch generiert — immer erst die
  Downloads-Seite parsen, nie eine alte URL cachen.

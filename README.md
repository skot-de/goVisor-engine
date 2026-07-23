# goVisor Data Engine

Analyse-Engine für 20+ Jahre öffentliche Vergabedaten (TED) als Grundlage für validierte Wechsel-Prognosen.

Startscope ist **Deutschland**, die Pipeline ist aber durchgehend länder-parametrisiert — kein Modul unterhalb von `config.py` kennt „DE".

## Stand

Schicht 1 (Raw Import) läuft. Schicht 2 (LLM Extraction) und 3 (Normalisierung) sind noch nicht gebaut.

Das Konzept in [`INPUT/govisor-data-engine-concept.md`](INPUT/govisor-data-engine-concept.md) ist die inhaltliche Grundlage, seine Quellenwahl ist jedoch überholt: es baut auf dem CSV-Export, der keinen Freitext enthält und 2023 endet. Die Begründung und alle Messwerte stehen in **[`docs/data-sources.md`](docs/data-sources.md)** — vor Änderungen an der Ingest-Logik dort nachlesen.

## Schnellstart

```bash
python -m pip install -r requirements.txt

# Bronze: ein Monat Deutschland
python -m govisor.cli ingest --from 2023-06 --country DE

# Bronze: Vollimport. --evict löscht Pakete nach der Verarbeitung
# (25 GB Download, aber nur ~2 GB DE bleiben liegen), --resume setzt fort.
python -m govisor.cli ingest --from 2016-01 --to 2026-06 --country DE --evict --resume

# Silber: Bronze → Parquet, verlustfrei
python -m govisor.cli silver --country DE

pytest tests/ -q
```

## Datenablage

```
data/
  cache/            heruntergeladene Monatspakete (wegwerfbar, mit --evict sofort gelöscht)
  raw/<Land>/       BRONZE — gefiltertes Original-XML, nach dem Ingest unverändert
  silver/<Land>/    SILBER — Parquet, 1 Zeile/Notice, ganzes Dokument als JSON
  index/<Land>/     schlanke Zusammenfassungen (jsonl.gz), Altlast aus der Bauphase
```

Bronze ist die einzige Schicht, die Wahrheit enthält — Silber und alles darüber ist jederzeit daraus neu berechenbar. Ein Parser-Bug kostet damit einen Re-Run über lokale Dateien statt eines 25-GB-Downloads. Das ist keine Theorie: der Parser hat auf dem Weg dreimal Felder verloren (siehe `docs/data-sources.md`).

## Silber abfragen

Die Silber-Schicht braucht keinen Server:

```python
import duckdb
duckdb.sql("SELECT count(*) FROM 'data/silver/DE/*/*.parquet'")
```

Typisierte Spalten (`cpv_main`, `description`, `lot_count`, `text_chars` …) decken den Alltag ab. Alles andere steht in `doc` — dem vollständigen Dokument als JSON:

```sql
SELECT json_extract_string(doc,
  '$.TED_EXPORT.FORM_SECTION.*.CONTRACTING_BODY.ADDRESS_CONTRACTING_BODY.E_MAIL')[1]
FROM 'data/silver/DE/*/*.parquet'
```

Kein Feld geht verloren, nur weil heute niemand daran gedacht hat.

## Module

| Datei | Zweck |
|---|---|
| `govisor/bulk.py` | Monatspakete finden, laden, streamen |
| `govisor/schema.py` | Parser für die TED-Schema-Generationen |
| `govisor/flatten.py` | XML → verlustfreies dict/JSON |
| `govisor/countries.py` | Ländercode-Registry (alpha-2 ↔ alpha-3) |
| `govisor/ingest.py` | Bronze: filtern, ablegen, indizieren |
| `govisor/silver.py` | Silber: Bronze → Parquet |
| `govisor/config.py` | Pfade und Länderauswahl |
| `govisor/cli.py` | Kommandozeile |

## Gemessene Kennzahlen (Paket `2023-06`)

- 69.655 Notices/Monat EU-weit, davon **13.716 DE** (19,7 %)
- Scan **~37.600 Dateien/s** — ein Monat in ~8 s inkl. Parsing und Ablage
- **99,9 %** der DE-Notices haben Freitext
- DE-Ablage: 38 MB/Monat → **~10 GB für 22 Jahre**

## Neues Land aufnehmen

Ist es in `govisor/countries.py` gelistet, genügt `--country XX`. Sonst dort eine Zeile ergänzen. Zu prüfen bleibt pro Land, ob die Käufer-Nationalität sauber erkannt wird — `probe_countries()` ist überinklusiv, `parse()` entscheidet.

# 15 · Eintragungsliste — wo ein Land überall bekannt gemacht wird

> **Es gibt keine zentrale Länderliste.** `("DE", "AT", "CH")` steht an über einem Dutzend
> Stellen. Diese Liste ist der Ersatz dafür; sie wird beim Aufnehmen eines Landes
> abgearbeitet und beim Abschluss noch einmal gegengelesen.

Sortiert nach dem Zeitpunkt, zu dem man sie braucht.

## Vor dem ersten Ingest

| Datei | Was einzutragen ist |
|-------|---------------------|
| `govisor/sources.py` | Eintrag je Quelle mit ehrlichem Status (`research`/`candidate`/`prepared`/`live`) |
| `govisor/locales.py` | `Locale`-Profil: Rechtsformen, Vertretungsklauseln, Abteilungen, Klassifikation. **Ohne dieses Profil läuft alles mit dem DE-Default.** |
| `govisor/languages.py` | Sprachcodes, falls die Quelle exotische Kürzel liefert |
| `govisor/model.py` | nur, wenn die Quelle Felder bringt, die es noch nicht gibt |
| `data/reference/geonames/XX.txt` | Ortsverzeichnis herunterladen |
| `data/reference/nuts/` | NUTS-Katalog des Landes (speist `dim_nuts`) |

## Parser und Ingest

| Datei | Was |
|-------|-----|
| neues Modul `govisor/<quelle>.py` | Parser Bronze→Silber, ein `schema_gen`-Wert |
| `govisor/cli.py` | Unterbefehl `ingest-<quelle>` |
| `scripts/fetch_ted_live.py` | Land in den Live-Abruf aufnehmen |

⚠ Der Parser muss `notice_text` schreiben, wenn die Quelle mehrsprachig ist
([Kapitel 02](02-input-ausschreibungen.md)).

## Dubletten und Entitäten

| Datei | Was |
|-------|-----|
| `govisor/dedupe.py` | nichts — **wenn** `locales.use(country)` bereits greift. Prüfen. |
| `data/curated/XX_entity_aliases.csv` | optional, kuratierte Umbenennungen |

## Gold

| Datei | Was |
|-------|-----|
| `govisor/gold.py` → `_REGION_STELLEN` | **NUTS-Stelle der Verwaltungseinheit** ([Kapitel 07](07-geo-und-regionen.md)) |
| `scripts/build_dach_gold.py` | Land in den Lauf; `KETTE` prüfen, ob alle Schritte country-fähig sind |
| `scripts/pruefe_verdrahtung.py` → `LAENDER` | Land aufnehmen, sonst prüft die Sonde es nicht |

## Regionen und Geo

| Datei | Was |
|-------|-----|
| `scripts/region_ableiten.py` → `LAENDER`, `REGION_STELLEN` | **muss zu `_REGION_STELLEN` passen** (Test hält das zusammen) |
| `scripts/region_ableiten.py` → `_KEINE_ORTE` | Behördenvokabular des Landes ([Kapitel 07](07-geo-und-regionen.md)) |
| `scripts/region_ableiten.py` → `_worte` | Buchstaben des Landes ([Kapitel 14](14-zeichen-und-schrift.md)) |
| `scripts/region_ableiten.py` → `LAND_NUTS1` | nur, wenn das Land keine `dim_nuts`-Namen hat |

## Export und Aggregate

| Datei | Was |
|-------|-----|
| `scripts/export_web_leads.py` | prüfen: liest **jede** Faktentabelle über `_union` bzw. `_silber_union`? |
| `scripts/export_strategie.py` → `LAENDER` | Land aufnehmen |
| `scripts/export_landing.py` | bewusst DE-only — **entscheiden und begründen**, ob das so bleibt |
| `scripts/build_marktpuls.py` | Serien-Regel je Quelle (`_serien_regel`): zu welcher Linie gehört die neue Quelle, wo bricht die Reihe? |
| `scripts/export_web_awards.py` | Zuschlagsphase; prüfen, ob das Land Zuschläge liefert |
| `scripts/export_regionen.py` | nimmt `--country`; entscheiden, ob eine eigene Regionsansicht entsteht |

## Frontend

| Datei | Was |
|-------|-----|
| `web/lib/explorerCore.js` → `LAND_LABEL` | Klartextname des Landes |
| `web/lib/explorerCore.js` → `LAND_AUS_NUTS` / `nutzerLand()` | sonst bekommt der Nutzer DE-Aggregate |
| `web/lib/explorerCore.js` | Länder-Kennzeichnung („🇨🇭 nur Schweiz") erweitern |
| `web/app/api/strategie/route.ts` → `LAENDER` | erlaubte Werte für `?land=` |
| `web/components/Marktpuls.tsx` | Länderwissen prüfen |

## Betrieb

| Datei | Was |
|-------|-----|
| `scripts/daily_leads.sh` | Ingest-Schritt, `--laender`-Listen, Firewall-Schleife |
| `docs/quellen-landkarte.md` | Status ehrlich setzen |
| Auto-Memory | was gemessen wurde, was offen blieb, mit absolutem Datum |

## Migrations- und Wartungsskripte

Diese laufen selten, kennen aber Länder. Wer sie später braucht und das Land fehlt, sucht
lange:

`scripts/backfill_notice_text.py` · `scripts/migrate_fremde_notices.py` ·
`scripts/rename_notice_text_columns.py` · `scripts/normalize_languages.py` ·
`scripts/preisstufen_analyse.py`

## Gegenprobe zum Schluss

```bash
grep -rn "'DE', *'AT', *'CH'\|\"DE\", *\"AT\", *\"CH\"\|DE,AT,CH" \
  govisor scripts web/lib web/app web/components | grep -v node_modules
```

Jede Trefferzeile durchgehen: **gehört das neue Land dazu?** Wenn nein, warum nicht — und
steht die Begründung irgendwo?

Dazu die Sonde, die den Gold-Teil automatisch prüft:

```bash
python3 scripts/pruefe_verdrahtung.py --offen
```

# 15 · Eintragungsliste — wo ein Land überall bekannt gemacht wird

> **Es gibt DREI Ebenen. Zwei haben seit dem 2026-09-04 eine Registry, die dritte nicht —
> und das ist der Kern dieses Kapitels.**
>
> 1. **Ländercodes** — `govisor/countries.py`: Alpha-2, Alpha-3, Name, plus die Aliase, die
>    TED über zwanzig Jahre gesammelt hat (`GR`→`EL`, `GB`→`UK`). Das *Vokabular*. Sie kennt
>    Bulgarien; gebaut wird es deshalb noch lange nicht.
> 2. **Welche Länder die Pipeline BAUT** — `govisor/laender.py:AKTIV`. ⚠ Hier standen bis
>    zum 2026-09-04 eigene `LAENDER`-Tupel in einem Dutzend Dateien, und Luxemburg fehlte in
>    der Hälfte. Neun Dateien leiten jetzt ab; `tests/test_laender.py` hält sie davon ab,
>    wieder eine eigene Liste zu schreiben.
> 3. **Wertetabellen** — `gold._REGION_STELLEN`, `_PLZ_STELLEN`, `locales.LOCALES`,
>    `LAND_LABEL` … ⚠ **Für die kann es keine Registry geben**: eine Liste erfindet `DE=5,
>    AT=4` nicht, das ist Länderwissen, das jemand messen muss. Sie bleiben von Hand gepflegt
>    — aber ein *fehlender* Eintrag ist seitdem laut:
>
> ```bash
> python3 scripts/pruefe_laender_tabellen.py --alle
> ```
>
> ⚠ **Warum dieser Wächter der wichtigere Teil ist.** Die Tabellen scheitern lautlos. Als LU
> dazukam: `_PLZ_STELLEN` fehlte → der Lead fiel auf den Ortsnamen zurück, die Abdeckung
> blieb 279/279, nur die Genauigkeit war weg (0 statt 127 Leads über die PLZ).
> `export_suppliers._STELLEN` fehlte → jede LU-Region verworfen. `locales` fehlte → alles
> lief mit dem DE-Default. Kein Fehler, keine leere Tabelle, keine Ausnahme.
>
> Diese Liste unten bleibt trotzdem: sie sagt, was man beim Aufnehmen ABARBEITET. Der
> Wächter sagt, was man dabei VERGESSEN hat.

Sortiert nach dem Zeitpunkt, zu dem man sie braucht.

## Vor dem ersten Ingest

| Datei | Was einzutragen ist |
|-------|---------------------|
| `govisor/countries.py` | Alpha-2/Alpha-3 und Name — **prüfen, ob das Land schon drinsteht** (EU-27 plus EWR/Beitrittskandidaten sind vorhanden) |
| `govisor/sources.py` | Eintrag je Quelle mit ehrlichem Status (`research`/`candidate`/`prepared`/`live`) |
| `govisor/locales.py` | `Locale`-Profil: Rechtsformen, Vertretungsklauseln, Abteilungen, Klassifikation. **Ohne dieses Profil läuft alles mit dem DE-Default.** |
| `govisor/languages.py` | Sprachcodes, falls die Quelle exotische Kürzel liefert |
| `govisor/model.py` | nur, wenn die Quelle Felder bringt, die es noch nicht gibt |
| `data/reference/geonames/<LAND>.txt` | Ortsverzeichnis herunterladen |
| `data/reference/nuts/` | ⚠ **schon EU-weit vorhanden.** `NUTS_AT_2024.csv` heisst NUTS-**Attributes**, nicht Austria: 1.971 Codes über 39 Länder (FR 143, PL 98). Nichts herunterzuladen. |

## Parser und Ingest

| Datei | Was |
|-------|-----|
| neues Modul `govisor/<quelle>.py` | Parser Bronze→Silber, ein `schema_gen`-Wert |
| ⚠ dort: **Regionskennung normalisieren** | Liefert die Quelle **NUTS** oder ein nationales Kürzel? simap liefert Kantonscodes (`ZH`, `VD`, `BE`); ohne Zuordnung fielen 4.850 Zuschläge aus jeder Regionsanzeige, und `BE` wäre im NUTS-Raum Belgien statt Bern. Vorbild: `_KANTON_NUTS` in `govisor/simap.py` — vollständig, gegen `dim_nuts` geprüft, Unbekanntes bleibt stehen. Siehe [Kapitel 07](07-geo-und-regionen.md). |
| `govisor/cli.py` | Unterbefehl `ingest-<quelle>` |
| `scripts/fetch_ted_live.py` | Land in den Live-Abruf aufnehmen |

⚠ Der Parser muss `notice_text` schreiben, wenn die Quelle mehrsprachig ist
([Kapitel 02](02-input-ausschreibungen.md)).

## Dubletten und Entitäten

| Datei | Was |
|-------|-----|
| `govisor/dedupe.py` | nichts — **wenn** `locales.use(country)` bereits greift. Prüfen. |
| `data/curated/<LAND>_entity_aliases.csv` | optional, kuratierte Umbenennungen |

## Dokumente

⚠ **Diesen Abschnitt gab es bis zum 2026-09-03 nicht** — und genau deshalb blieb die
Dokumentenkette bei Deutschland stehen, während drei Länder daneben lagen. Der Abrufer stand
in der Liste, alles dahinter nicht.

| Datei | Was |
|-------|-----|
| `scripts/daily_leads.sh` → `_IXLAENDER` | **die eine Liste** für `index-docs` UND `signals-docs`. Beide laufen darüber, damit sie nicht auseinanderlaufen |
| `scripts/analyze_docs.py` | nichts eintragen — vereinigt `data/docs/*/`. Prüfen, dass das so bleibt |
| `scripts/export_doc_text.py`, `export_doc_signals.py` | dito, vereinigen `data/docs/*/` |
| `scripts/build_doc_analysis.py`, `export_doc_struktur.py` | nehmen `--land`/`--country` — im Aufrufer setzen |
| `scripts/export_doc_listing.py` | Portal-Dateiliste je Land; nur eintragen, wenn das Land ein Listenportal hat |
| `web/app/api/lead-docs/route.ts` → `LAENDER` | erlaubte Werte für den Upload-Pfad |
| `scripts/process_upload.py` → `_ERLAUBT` | dieselbe Liste eine Ebene tiefer |
| `scripts/export_anforderungsprofil.py`, `export_stellenprofil.py`, `export_fenster.py` | lesen `doc_checklist`/`doc_analysis` je Land |

⚠ **Ein Land hier zu vergessen wirft keinen Fehler.** Die Schleifen prüfen je Land auf die
Datei und überspringen, was fehlt — das ist richtig, macht das Vergessen aber unsichtbar.
Die Gegenprobe unten ist deshalb nicht optional.

⚠ **Und was NICHT einzutragen ist:** ein Länderrang für Uploads. Hochgeladene Unterlagen gehen
synchron durch (`llm.VORRANG`) und sehen die Warteschlange nie — s. [Kapitel 03](03-input-dokumente.md).

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
| `scripts/export_web_awards.py` | Zuschlagsphase. ⚠ Deckel gilt je Branche **und Land** (`CAP`), und das Feld `land` kommt aus der Quelle — nicht hartkodieren |
| `scripts/export_suppliers.py` | Onboarding-Firmenindex. ⚠ Zwei Dinge: `clean_nuts` braucht die Regionslänge des Landes, und Grenzgänger müssen zusammengelegt werden (gleicher Name **und** gemeinsames CPV-4-Feld) |
| `scripts/export_firma_profiles.py` | `/firma`-Profile. ⚠ Regionsnamen aus `dim_nuts` je Land, kein `nuts1 LIKE 'DE_'` |
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

Und für die Frage „was hängt eigentlich an dieser Tabelle" — die Karte, die den Quelltext
liest statt ein getipptes Verzeichnis:

```bash
python3 scripts/verdrahtungskarte.py --waisen
```

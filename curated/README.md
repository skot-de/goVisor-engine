# Kuratierte Dateien — was hier liegt und warum

`data/` ist ein Symlink auf die externe SSD; **git fasst nichts darunter an**. Alles, was
menschliche Arbeit enthält und nicht aus den Daten ableitbar ist, gehört deshalb HIERHER.

## Was hier liegt

| Datei | Inhalt | ersetzbar? |
|---|---|---|
| `DE_entity_aliases.csv` | belegte Umbenennungen (DB InfraGO ↔ DB Netz, gleiche HRB) | **nein** — recherchiert |
| `vergabestellen_kuratierung_worklist.csv` | Arbeitsliste fragmentierter Vergabestellen | halb — Analyse-Ausgabe, aber Einstiegspunkt |
| `DE_kategorie_korrektur.csv` | Kategorie-Korrekturen; speisen auch den Prompt (Lernschleife) | **nein** |
| `<L>_region_korrektur.csv` | geprüfte Regions-Urteile je (Käufername, PLZ, alte Kennung) — DE/AT/CH | **nein** — Fall für Fall belegt |

## Was NICHT hierher gehört

`data/curated/DE_company_groups.csv` (407.794 Zeilen, 41 MB) bleibt, wo sie ist. Gemessen
2026-08-14: **0 Zeilen mit `source=manual`** — sie besteht vollständig aus `seed`,
`auto_domain` und `auto_muni` und ist damit aus den Daten reproduzierbar.

⚠ **Das kann sich ändern.** `build_company_groups` überschreibt bestehende Zeilen nie, damit
Handkorrekturen den Rebuild überleben. Sobald dort `source=manual`-Zeilen entstehen, sind sie
unersetzlich und müssen mitgesichert werden — sinnvollerweise als Auszug nur dieser Zeilen,
nicht die ganze Datei.

Prüfen:

    python3 -c "import csv;print(sum(1 for r in csv.DictReader(open('data/curated/DE_company_groups.csv')) if r['source']=='manual'))"

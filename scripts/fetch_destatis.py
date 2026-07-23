"""Destatis/Regionalstatistik → Kreis-Finanzen (Investitionsbudget je Kreis).

Holt Tabelle **71717-Z-03** („Auszahlungen (Übersicht)", Rechnungsergebnisse der kommunalen
Kernhaushalte, 2018–2025) auf Ebene **FKREISE** und cached sie als
``data/reference/kreis_finanzen.parquet``. Damit bekommt jede Vergabestelle-Region ein echtes
**Investitionsbudget** — die €-Achse, die uns bei DÖE fehlt (Beschaffungsintensität).

**API-Eigenheiten (teuer herausgefunden, bitte beibehalten):**
- Base ``https://www.regionalstatistik.de/genesisws/rest/2020``; **POST** (GET ist seit
  27.11.2025 abgeschaltet), Body ``x-www-form-urlencoded`` (JSON → HTTP 415).
- **Zugangsdaten gehören in die HTTP-HEADER** ``username``/``password`` — im Body ergibt das
  Fehler-Code 15. ``helloworld/logincheck`` meldet immer „GAST", taugt NICHT als Auth-Test.
- Große Tabellen: ``job=true`` → Job-Name merken → ``catalogue/jobs`` bis ``State='Fertig'``
  → ``data/resultfile`` mit **``area=Benutzer``** → Antwort ist ein **ZIP** mit Flat-CSV.
- Credentials: ``.secrets/destatis.txt`` (Zeile 1 = Kennung, Zeile 2 = Passwort), chmod 600.

Aufruf:  python scripts/fetch_destatis.py [--year 2023]
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

BASE = "https://www.regionalstatistik.de/genesisws/rest/2020"
TABLE = "71717-Z-03"
MEASURES = {"AINVD78": "investitionen_eur", "AUSZ001": "auszahlungen_eur"}
SECRETS = ROOT / ".secrets" / "destatis.txt"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def _creds():
    if not SECRETS.exists():
        sys.exit(f"Zugangsdaten fehlen: {SECRETS} (Zeile 1 Kennung, Zeile 2 Passwort). "
                 f"Kostenlos registrieren: https://www.regionalstatistik.de/genesis/online")
    lines = [l.strip() for l in SECRETS.read_text().splitlines() if l.strip()]
    return lines[0], lines[1]


def _post(path, params, raw=False):
    """POST mit Header-Auth (curl — urllib scheitert am python.org-Zertifikat)."""
    user, pw = _creds()
    cmd = ["curl", "-sS", "--max-time", "180", "-X", "POST", f"{BASE}/{path}",
           "-H", f"username: {user}", "-H", f"password: {pw}",
           "-H", "Content-Type: application/x-www-form-urlencoded"]
    for k, v in params.items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    if raw:
        cmd += ["--output", "-"]
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"curl {path}: {out.stderr.decode()[:200]}")
    return out.stdout if raw else json.loads(out.stdout.decode("utf-8", "replace"))


def _unzip_csv(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        return zf.read(name).decode("utf-8", "replace")


def fetch_flat_csv(year: int, table: str = TABLE) -> str:
    """Flat-CSV einer Tabelle holen.

    **Primär ``data/tablefile``** — liefert zuverlässig ein ZIP mit ``*_flat.csv``.
    (``data/table`` gibt kleine Tabellen im KLASSISCHEN CSV mit Titel-Präambel zurück,
    ignoriert also ``format=ffcsv`` — deshalb nicht als Primärweg nutzen.)
    Fallback für zu große Tabellen: Job-Modus.
    """
    common = {"name": table, "area": "all", "format": "ffcsv", "language": "de",
              "startyear": str(year), "endyear": str(year)}
    blob = _post("data/tablefile", common, raw=True)
    if blob[:2] == b"PK":                       # ZIP → direkter Treffer
        return _unzip_csv(blob)
    d = _post("data/table", {**common, "job": "true"})
    status = (d.get("Status") or {}).get("Content", "")
    m = re.search(r"([0-9A-Za-z\-]+_\d+)", status)
    if not m:                                   # klein genug → direkt geliefert
        content = ((d.get("Object") or {}).get("Content") or "")
        if content:
            return content
        raise RuntimeError(f"unerwartete Antwort: {status[:160]}")
    job = m.group(1)
    log(f"  Job {job} gestartet, warte …")
    for attempt in range(30):
        time.sleep(8)
        # WICHTIG: nach dem Job-Namen zu selektieren matcht NICHT — alles listen und
        # per Code finden.
        jl = _post("catalogue/jobs", {"selection": "*", "area": "Benutzer", "language": "de"})
        state = next((j.get("State") for j in (jl.get("List") or [])
                      if j.get("Code") == job), None)
        if state == "Fertig":
            break
        log(f"    Status: {state or '…'}")
    else:
        raise RuntimeError("Job wurde nicht rechtzeitig fertig")
    blob = _post("data/resultfile", {"name": job, "area": "Benutzer",
                                     "format": "ffcsv", "language": "de"}, raw=True)
    return _unzip_csv(blob)


def build(year: int) -> int:
    import duckdb

    log(f"Destatis {TABLE} — Jahr {year}")
    csv_text = fetch_flat_csv(year)
    tmp = ROOT / "data" / "cache" / f"destatis_{TABLE}_{year}.csv"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(csv_text)
    log(f"  Rohdaten: {len(csv_text.splitlines()):,} Zeilen → {tmp.name}")

    # Kreis-Ebene (FKREISE), Kennzahlen pivotieren, Kreis-Schlüssel = 'F' + AGS.
    # NUTS-3-Zuordnung über NORMALISIERTEN Namen — nur EINDEUTIGE Treffer (Rest bleibt
    # ohne nuts_code; Destatis führt auch Nicht-Kreise wie Bezirksverwaltungen).
    norm = (r"lower(trim(regexp_replace(regexp_replace({c},"
            r"'(,\s*)?(Landkreis|Kreisfreie Stadt|Stadtkreis|Kreis|Landeshauptstadt)\s*$','','gi'),"
            r"'^(Landkreis|Kreis|Stadtkreis)\s+','','gi')))")
    out = ROOT / "data" / "reference" / "kreis_finanzen.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    R = f"read_csv('{tmp.as_posix()}', delim=';', header=true, auto_detect=true, ignore_errors=true)"
    con.execute(f"""
        CREATE TEMP TABLE k AS
        SELECT replace("1_variable_attribute_code", 'F', '') AS ags,
               "1_variable_attribute_label" AS kreis_name,
               {norm.format(c='"1_variable_attribute_label"')} AS nkey,
               CAST(time AS INT) AS year,
               max(CASE WHEN value_variable_code='AINVD78' THEN TRY_CAST(value AS BIGINT) END) AS investitionen_eur,
               max(CASE WHEN value_variable_code='AUSZ001' THEN TRY_CAST(value AS BIGINT) END) AS auszahlungen_eur
        FROM {R} WHERE "1_variable_code"='FKREISE' GROUP BY 1,2,3,4""")
    con.execute(f"""
        CREATE TEMP TABLE nuts AS
        SELECT {norm.format(c='name')} AS nkey, any_value(nuts_code) AS nuts_code, count(*) AS n
        FROM read_parquet('data/gold/DE/dim_nuts.parquet') WHERE level=3 GROUP BY 1""")
    con.execute(f"""
        COPY (SELECT k.ags, k.kreis_name, k.year, k.investitionen_eur, k.auszahlungen_eur,
                     CASE WHEN nuts.n = 1 THEN nuts.nuts_code END AS nuts_code
              FROM k LEFT JOIN nuts ON nuts.nkey = k.nkey)
        TO '{out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    n, mapped = con.execute(
        f"SELECT count(*), count(nuts_code) FROM read_parquet('{out.as_posix()}')").fetchone()
    con.close()
    log(f"FERTIG: {n} Kreise → {out}  (davon {mapped} mit NUTS-3-Zuordnung)")
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2023)
    build(ap.parse_args().year)

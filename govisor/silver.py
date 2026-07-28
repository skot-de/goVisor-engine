"""Silber: bronze XML → normalisierte Parquet-Tabellen. Kein JSON.

Jede Notice zerfällt in Zeilen über mehrere Tabellen (notices, notice_parties,
lots, notice_cpv, lot_cpv, award_criteria), je eine Parquet-Datei pro
Tabelle/Land/Monat, verknüpft über ``notice_id``. Abgefragt wird mit ganz
normalem SQL über Joins — kein ``json_extract``, kein Blob.

Verlustfreiheit liegt in **Bronze**. Ein seltenes, hier nicht gemapptes Feld
ist aus dem Original-XML nachziehbar; deshalb braucht Silber keinen JSON-Blob.

Reads only from ``raw/`` — ein Parser-Fix kostet einen Re-Run über lokale
Dateien, keinen 25-GB-Download.
"""

from __future__ import annotations

import re
import tarfile
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import model, normalize, schema
from .config import Config

_DOE_VERSION = re.compile(rb"VersionID>(\d+)<")


def build_month(cfg: Config, country: str, key: str, force: bool = False) -> int:
    """Ein Bronze-Monat → alle Tabellen als Parquet. Gibt die Notice-Zahl zurück."""
    src = cfg.raw_path(country, key)
    if not src.exists():
        return 0
    marker = cfg.silver_table_path("notices", country, key)
    if marker.exists() and not force:
        return -1

    year, month = (int(p) for p in key.split("-"))
    buckets: dict[str, list[dict]] = {name: [] for name in model.TABLES}
    # Alt-Pakete (2004–2007) liefern JEDE Notice mehrfach: eine ISO- und eine UTF8-
    # Edition (beide mit Präfix DE_, beide passieren den Länderfilter). Nach dem Parsen
    # sind das identische Zeilen → bis zu 50 % Dubletten. Deduplizieren nach notice_id;
    # die sauber als UTF-8 dekodierende Edition gewinnt (die ISO-Variante hätte Mojibake).
    # Für Jahre ohne Dubletten (2010+) erscheint jede notice_id genau einmal → unverändert.
    by_id: dict[str, tuple[int, dict]] = {}
    with tarfile.open(src, "r:gz") as tf:
        for member in tf:
            if not member.isfile():
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            notice_id = schema.normalize_notice_id(Path(member.name).stem)
            raw = fh.read()
            try:
                raw.decode("utf-8")
                clean = 1
            except UnicodeDecodeError:
                clean = 0
            prev = by_id.get(notice_id)
            if prev is not None and prev[0] >= clean:
                continue                       # schon eine mind. so saubere Edition dieser Notice
            try:
                notice = schema.parse(raw, notice_id)
            except Exception:
                continue
            by_id[notice_id] = (clean, normalize.rows(notice, raw, country, year, month))

    count = len(by_id)
    if count == 0:
        return 0
    for _, table_map in by_id.values():
        for table, table_rows in table_map.items():
            buckets[table].extend(table_rows)
    for table, table_schema in model.TABLES.items():
        out = cfg.silver_table_path(table, country, key)
        out.parent.mkdir(parents=True, exist_ok=True)
        arrow = pa.Table.from_pylist(buckets[table], schema=table_schema)
        tmp = out.with_suffix(".part")
        pq.write_table(arrow, tmp, compression="zstd")
        tmp.rename(out)
        # Das Monatspaket ist die vollständige Wahrheit — eine vorab per TED-Search-API
        # geholte `-live`-Datei desselben Monats wäre jetzt eine Dublette.
        live = out.with_name(f"{key}-live.parquet")
        if live.exists():
            live.unlink()
    return count


def _doe_stage_path(cfg: Config, table: str, country: str, key: str) -> Path:
    """DÖE-**Staging** je Monat, BEWUSST außerhalb des Silber-Globs (``data/doe_stage/``).

    DÖE re-exportiert offene/aktualisierte Notices über MEHRERE Monatspakete — schriebe
    man die direkt ins Silber, gäbe es Cross-Monat-Dubletten (→ Join-Fan-out im Gold).
    Deshalb: pro Monat ins Staging, dann ``consolidate_doe`` dedupliziert je notice_id
    (spätester Monat gewinnt) in EIN File je Tabelle unter ``<table>/doe/``.
    """
    return cfg.data_dir / "doe_stage" / country / table / f"{key}.parquet"


def build_month_doe(cfg: Config, key: str, force: bool = False, country: str = "DE") -> int:
    """Ein DÖE-Monat (``raw_doe/<country>/<key>.eforms.zip``) → Silber, nur unterschwellig.

    Nur das **``de-*``-Subset** (nationale Rechtsgrundlage) wird übernommen — oberschwellig
    ist TED-Dublette. Dedup je Notice über die höchste ``VersionID``. Schreibt in dasselbe
    Silber-Schema wie TED, aber mit ``schema_gen='doe'`` und ``-doe``-Dateinamen. Gibt die
    Notice-Zahl zurück (0 = kein/leeres Paket, -1 = schon gebaut ohne ``force``).
    """
    src = cfg.data_dir / "raw_doe" / country / f"{key}.eforms.zip"
    if not src.exists():
        return 0
    marker = _doe_stage_path(cfg, "notices", country, key)
    if marker.exists() and not force:
        return -1

    year, month = (int(p) for p in key.split("-"))
    buckets: dict[str, list[dict]] = {name: [] for name in model.TABLES}
    by_id: dict[str, tuple[int, dict]] = {}       # notice_id -> (version, table_map)
    with zipfile.ZipFile(src) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            raw = zf.read(name)
            if b"RegulatoryDomain>de-" not in raw:     # nur unterschwellig (kein TED-Overlap)
                continue
            notice_id = schema.normalize_notice_id(re.sub(r"-\d+$", "", Path(name).stem))  # Versions-Suffix ab, dann kanonisch
            vm = _DOE_VERSION.search(raw)
            version = int(vm.group(1)) if vm else 0
            prev = by_id.get(notice_id)
            if prev is not None and prev[0] >= version:
                continue                              # neuere/gleiche Version schon gesehen
            try:
                notice = schema.parse(raw, notice_id)
            except Exception:
                continue
            table_map = normalize.rows(notice, raw, country, year, month)
            for row in table_map.get("notices", []):
                row["schema_gen"] = "doe"             # Quelle markieren (t/d im Slug etc.)
            by_id[notice_id] = (version, table_map)

    count = len(by_id)
    if count == 0:
        return 0
    for _, table_map in by_id.values():
        for table, table_rows in table_map.items():
            buckets[table].extend(table_rows)
    for table, table_schema in model.TABLES.items():
        out = _doe_stage_path(cfg, table, country, key)
        out.parent.mkdir(parents=True, exist_ok=True)
        arrow = pa.Table.from_pylist(buckets[table], schema=table_schema)
        tmp = out.with_suffix(".part")
        pq.write_table(arrow, tmp, compression="zstd")
        tmp.rename(out)
    return count


def consolidate_doe(cfg: Config, country: str = "DE") -> int:
    """DÖE-Staging (per Monat) → dedupliziertes Silber, **pro Jahr** unter ``year=YYYY/``.

    Cross-Monat-Dedup: je ``notice_id`` gewinnt der **späteste Monat** (aktuellster Stand;
    Version innerhalb eines Monats hat ``build_month_doe`` schon dedupliziert). Für jede
    Tabelle werden nur die Zeilen aus dem kanonischen Monat der jeweiligen Notice behalten
    (Mehrfach-Zeilen wie Lose/CPV EINES Monats bleiben, ohne Cross-Monat-Vervielfachung).

    **Wichtig — hive-Layout:** die Gold-Builder lesen Silber mit ``hive_partitioning=1``;
    darum MUSS die Ausgabe unter ``year=YYYY/`` liegen (nicht ``doe/``), sonst Partition-
    Mismatch → verfälschte Reads. Je Notice ins File ihres kanonischen Jahres. Gibt die
    deduplizierte Notice-Zahl zurück.
    """
    import glob as _glob
    import os

    import duckdb

    stage = cfg.data_dir / "doe_stage" / country
    nstage = str(stage / "notices" / "*.parquet")
    if not _glob.glob(nstage):
        return 0
    con = duckdb.connect(); con.execute("SET threads=4")
    MON = "([0-9]{4}-[0-9]{2})"
    # kanonischer Monat (+ Jahr) je notice_id
    con.execute(f"""CREATE TEMP TABLE _canon AS
        SELECT notice_id, max(regexp_extract(filename, '{MON}', 1)) AS cm,
               CAST(substr(max(regexp_extract(filename, '{MON}', 1)), 1, 4) AS INT) AS cy
        FROM read_parquet('{nstage}', filename=true) GROUP BY 1""")
    years = [r[0] for r in con.execute("SELECT DISTINCT cy FROM _canon ORDER BY 1").fetchall()]

    # Reste alter Konsolidate entfernen (früheres doe/-Layout und je-Jahr-Dateien).
    for old in _glob.glob(str(cfg.silver_dir / country / "*" / "doe" / "all-doe.parquet")):
        os.remove(old)
    for old in _glob.glob(str(cfg.silver_dir / country / "*" / "year=*" / "*-doe.parquet")):
        os.remove(old)

    n_out = 0
    for table in model.TABLES:
        files = str(stage / table / "*.parquet")
        if not _glob.glob(files):
            continue
        con.execute(f"""CREATE OR REPLACE TEMP TABLE _t AS
            SELECT s.* EXCLUDE(filename), c.cy
            FROM (SELECT *, regexp_extract(filename, '{MON}', 1) AS _mon
                  FROM read_parquet('{files}', filename=true)) s
            JOIN _canon c ON c.notice_id = s.notice_id AND c.cm = s._mon""")
        for y in years:
            cnt = con.execute(f"SELECT count(*) FROM _t WHERE cy={y}").fetchone()[0]
            if not cnt:
                continue
            out = cfg.silver_dir / country / table / f"year={y}" / f"{y}-doe.parquet"
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".part")
            con.execute(f"COPY (SELECT * EXCLUDE(cy, _mon) FROM _t WHERE cy={y}) "
                        f"TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            tmp.replace(out)
            if table == "notices":
                n_out += cnt
    con.close()
    return n_out


def available_months_doe(cfg: Config, country: str = "DE") -> list[str]:
    d = cfg.data_dir / "raw_doe" / country
    return sorted(p.name[:-len(".eforms.zip")] for p in d.glob("*.eforms.zip")) if d.exists() else []


def available_months(cfg: Config, country: str) -> list[str]:
    return sorted(p.stem.replace(".tar", "") for p in cfg.raw_dir.joinpath(country).glob("*.tar.gz"))

"""`notice_text` für den Altbestand nachziehen — Sprachfassungen aus den Rohdaten.

Die Tabelle entsteht seit 8272804 bei jedem neuen Ingest. Der Altbestand (2,2 Mio. Notices)
hat sie nicht: dort wurde beim Parsen nur die ERSTE Titelfassung behalten. Dieses Skript
liest die Rohdaten erneut und schreibt ausschließlich `notice_text` — alle anderen
Silber-Tabellen bleiben unberührt.

**Kein Download nötig.** Die Rohdaten liegen vollständig lokal:
  · `data/raw/<Land>/<Monat>.tar.gz` — länder-gefilterte Monatspakete (DE 270, AT 269)
  · `data/raw_live/<Land>/<Monat>/*.xml` — der Live-Cache (CH, EU und die jüngsten Monate)
`data/cache/ted_<Monat>.tar.gz` sind die ungefilterten Originalpakete (161 GB); die
länder-gefilterten in `data/raw` sind für diesen Zweck die schnellere Quelle.

**Warum das billiger ist, als es klingt.** Gemessen 629 Notices/s einkernig → rund 48 min
für DE, ~5 min für AT. Der teure Teil eines Silber-Rebuilds ist nicht das Parsen, sondern
das Schreiben aller neun Tabellen; hier fällt eine an.

**Partitionierung** folgt exakt `silver.build_month`: Archiv-Notices landen unter dem
Schlüssel ihres Monatspakets, Live-Notices unter ihrem `publication_date`. Nur so liegen
die neuen Dateien deckungsgleich zu den bestehenden.

**Wiederaufnahme:** ein Monat, dessen `notice_text`-Datei schon existiert, wird
übersprungen (`--neu` erzwingt ihn). Der Lauf lässt sich also jederzeit abbrechen.

Aufruf:  python scripts/backfill_notice_text.py [--laender DE,AT,CH,EU] [--neu] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import bulk, model, schema  # noqa: E402  (Pfad muss zuerst stehen)
from govisor.config import Config  # noqa: E402

SCHEMA = model.TABLES["notice_text"]


def _zeilen(notice) -> list[dict]:
    nid = notice.notice_id
    return [{"notice_id": nid, "lot_id": lot_id, "feld": feld,
             "language": lang, "wert": wert}
            for lot_id, feld, lang, wert in (getattr(notice, "texts", None) or [])]


def _pfad(cfg, land: str, key: str) -> Path:
    """Zielpfad — auch für Pseudo-Töpfe wie ``EU``.

    `Config` validiert den Ländercode und lehnt `EU` ab (zu Recht: es ist kein Land,
    sondern der Auffangtopf für Notices, deren Käufer ausserhalb der gepflegten Länder
    sitzt). Ohne diesen Ausweg bricht der Lauf am Ende ab — nach DE, AT und CH, also
    nachdem die teure Arbeit schon getan ist.
    """
    if cfg is None:
        return ROOT / "data" / "silver" / land / "notice_text" / f"year={key[:4]}" / f"{key}.parquet"
    return cfg.silver_table_path("notice_text", land, key)


def _schreibe(cfg, land: str, key: str, zeilen: list[dict]) -> Path:
    ziel = _pfad(cfg, land, key)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = ziel.with_suffix(".part")
    pq.write_table(pa.Table.from_pylist(zeilen, schema=SCHEMA), tmp, compression="zstd")
    tmp.replace(ziel)          # atomar — ein Abbruch hinterlässt keine halbe Datei
    return ziel


def aus_archiv(cfg: Config, land: str, neu: bool, limit: int | None) -> tuple[int, int]:
    """Monatspakete aus ``data/raw/<land>`` durchgehen."""
    pakete = sorted((ROOT / "data" / "raw" / land).glob("*.tar.gz"))
    notices = fassungen = 0
    for i, paket in enumerate(pakete, 1):
        key = paket.stem.replace(".tar", "")
        ziel = _pfad(cfg, land, key)
        if ziel.exists() and not neu:
            continue
        t0 = time.time()
        zeilen: list[dict] = []
        n = 0
        for name, raw in bulk.iter_notices(paket, land):
            nid = schema.normalize_notice_id(Path(name).stem)
            try:
                notice = schema.parse(raw, nid)
            except Exception:
                continue                    # kaputte Notice überspringen, nicht abbrechen
            n += 1
            zeilen.extend(_zeilen(notice))
        _schreibe(cfg, land, key, zeilen)
        notices += n
        fassungen += len(zeilen)
        print(f"  [{i:3}/{len(pakete)}] {land} {key}: {n:6,} Notices → {len(zeilen):7,} "
              f"Fassungen ({time.time()-t0:.0f}s)", flush=True)
        if limit and notices >= limit:
            break
    return notices, fassungen


def aus_live(cfg: Config, land: str, neu: bool, limit: int | None) -> tuple[int, int]:
    """Einzel-XML aus dem Live-Cache. Partition nach `publication_date`, wie im Live-Ingest."""
    wurzel = ROOT / "data" / "raw_live" / land
    if not wurzel.exists():
        return 0, 0
    nach_monat: dict[str, list[dict]] = defaultdict(list)
    notices = 0
    gesehen: set[str] = set()
    for datei in sorted(wurzel.glob("*/*.xml")):
        pub = datei.stem
        # Kanonisieren wie im Archiv-Zweig: der Dateiname traegt `370795-2024`, das Silber
        # fuehrt `370795_2024`. Ohne diesen Schritt sind ALLE Zeilen Waisen — beim ersten
        # Lauf waren das 88.486 von 88.486 CH-Notices.
        nid = schema.normalize_notice_id(pub)
        # Dieselbe Notice liegt oft in mehreren Cache-Monaten (der Ordner folgt dem
        # Suchfenster, nicht dem Publikationsdatum) — sonst entstehen Dubletten.
        if nid in gesehen:
            continue
        gesehen.add(nid)
        try:
            notice = schema.parse(datei.read_bytes(), nid)
        except Exception:
            continue
        notices += 1
        pd = notice.publication_date
        if not pd:
            continue                        # ohne Datum keine Partition — bewusst überspringen
        nach_monat[f"{pd[:4]}-{pd[5:7]}"].extend(_zeilen(notice))
        if limit and notices >= limit:
            break
    fassungen = 0
    for key, zeilen in sorted(nach_monat.items()):
        ziel = _pfad(cfg, land, key)
        if ziel.exists() and not neu:
            continue
        _schreibe(cfg, land, key, zeilen)
        fassungen += len(zeilen)
        print(f"  {land} {key}: {len(zeilen):7,} Fassungen", flush=True)
    return notices, fassungen


def main(laender: list[str], neu: bool, limit: int | None) -> int:
    gesamt_n = gesamt_f = 0
    t0 = time.time()
    for land in laender:
        try:
            cfg = Config(countries=(land,), data_dir="data")
        except KeyError:
            cfg = None          # Pseudo-Topf (EU) — Pfade direkt bauen
        archiv = (ROOT / "data" / "raw" / land)
        if archiv.exists() and any(archiv.glob("*.tar.gz")):
            n, f = aus_archiv(cfg, land, neu, limit)
        else:
            # CH und EU haben keine Monatspakete — sie kommen über den Live-Abruf.
            n, f = aus_live(cfg, land, neu, limit)
        print(f"{land}: {n:,} Notices, {f:,} Sprachfassungen")
        gesamt_n += n
        gesamt_f += f
    print(f"\nSumme: {gesamt_n:,} Notices, {gesamt_f:,} Sprachfassungen "
          f"in {(time.time()-t0)/60:.0f} min")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--laender", default="DE,AT,CH,EU")
    ap.add_argument("--neu", action="store_true", help="auch fertige Monate neu bauen")
    ap.add_argument("--limit", type=int, help="nur N Notices je Land (zum Testen)")
    a = ap.parse_args()
    sys.exit(main([x.strip() for x in a.laender.split(",") if x.strip()], a.neu, a.limit))

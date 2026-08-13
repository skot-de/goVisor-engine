"""Leistungsverzeichnisse aus den Vergabeunterlagen → ``doc_positions.parquet``.

**Die Lücke.** `docpipe` zieht aus den Archiven nur TEXT. Ein GAEB-Leistungsverzeichnis ist
aber bereits strukturiert — Ordnungszahl, Menge, Einheit, Kurztext je Position. Diese Struktur
als Fließtext zu behandeln, wirft genau das weg, was den Wert ausmacht: „wie viel wovon".
`govisor.docparse.parse_gaeb` kann das seit Ticket 23, wurde aber nur beim EINZEL-UPLOAD
aufgerufen. Über den Korpus lief es nie.

**Was hier herauskommt** (je Position eine Zeile):
``notice_id, quelle, datei, rno, menge, einheit, text`` — plus eine Aggregatzeile je Vorgang
in ``doc_lv.parquet`` (Positionszahl, Summe der Mengen je Einheit als JSON).

**Grenzen, ehrlich.** GAEB DA XML (X8x) wird geparst; die alten Flat-Formate D8x nicht — die
sind ein Zeilenformat mit fester Spaltenbreite und brauchen einen eigenen Leser. XLSX liefert
nur Struktur (Blätter, Spaltenüberschriften, Zeilenzahl), bewusst KEINE Zellwerte: ein
Excel-LV hat kein festes Schema, und geratene Spaltenzuordnungen erzeugen falsche Mengen —
schlimmer als keine.

Aufruf:  python3 scripts/extract_positions.py [--country DE] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import docparse  # noqa: E402

_MAX_ENTPACKT = 60 * 1024 * 1024      # je Datei — Zip-Bomben-Schutz (wie docpipe)


def _archive(vorgang: Path):
    """Alle ZIPs eines Vorgangs (in der Regel genau eines)."""
    return sorted(vorgang.glob("*.zip"))


def sammle(country: str, limit: int | None) -> tuple[list[dict], list[dict]]:
    root = ROOT / "data" / "docs" / country
    vorgaenge = sorted(p for p in root.iterdir() if p.is_dir())
    if limit:
        vorgaenge = vorgaenge[:limit]
    positionen: list[dict] = []
    lv: list[dict] = []
    for v in vorgaenge:
        nid = v.name
        n_pos = 0
        mengen: Counter = Counter()
        blaetter: list[dict] = []
        for z in _archive(v):
            try:
                zf = zipfile.ZipFile(z)
            except Exception:
                continue
            with zf:
                for info in zf.infolist():
                    if info.is_dir() or info.file_size > _MAX_ENTPACKT:
                        continue
                    endung = Path(info.filename).suffix.lower()
                    if endung not in docparse.GAEB_EXTS and endung not in (".xlsx", ".xlsm"):
                        continue
                    try:
                        daten = zf.read(info)
                    except Exception:
                        continue
                    if endung in docparse.GAEB_EXTS:
                        res = docparse.parse_gaeb(daten)
                        if not res:
                            continue          # D8x-Flatformat o. Ä. — ehrlich uebersprungen
                        for p in res["positions"]:
                            positionen.append({
                                "notice_id": nid, "quelle": "gaeb", "datei": info.filename,
                                "rno": p.get("rno") or None,
                                "menge": _zahl(p.get("qty")),
                                "einheit": (p.get("unit") or None),
                                "text": (p.get("text") or None),
                            })
                            n_pos += 1
                            if p.get("unit") and _zahl(p.get("qty")) is not None:
                                mengen[p["unit"]] += _zahl(p["qty"])
                    else:
                        res = docparse.parse_xlsx(daten)
                        if not res:
                            continue
                        for sh in res.get("sheets", []):
                            blaetter.append({"datei": info.filename, **sh})
                            n_pos += sh.get("n_positions", 0)
        if n_pos or blaetter:
            lv.append({
                "notice_id": nid,
                "n_positionen": n_pos,
                "mengen_je_einheit": json.dumps({k: round(v, 2) for k, v in mengen.most_common(12)},
                                                ensure_ascii=False) if mengen else None,
                "xlsx_blaetter": json.dumps(blaetter[:20], ensure_ascii=False) if blaetter else None,
            })
    return positionen, lv


def _zahl(s) -> float | None:
    if s in (None, ""):
        return None
    try:
        return float(str(s).replace(".", "").replace(",", ".")) if "," in str(s) else float(s)
    except ValueError:
        return None


def main(country: str, limit: int | None) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq

    positionen, lv = sammle(country, limit)
    root = ROOT / "data" / "docs" / country
    if positionen:
        pq.write_table(pa.Table.from_pylist(positionen, schema=pa.schema([
            ("notice_id", pa.string()), ("quelle", pa.string()), ("datei", pa.string()),
            ("rno", pa.string()), ("menge", pa.float64()), ("einheit", pa.string()),
            ("text", pa.string())])), root / "doc_positions.parquet", compression="zstd")
    if lv:
        pq.write_table(pa.Table.from_pylist(lv, schema=pa.schema([
            ("notice_id", pa.string()), ("n_positionen", pa.int64()),
            ("mengen_je_einheit", pa.string()), ("xlsx_blaetter", pa.string())])),
            root / "doc_lv.parquet", compression="zstd")
    mit_gaeb = len({p["notice_id"] for p in positionen})
    print(f"Leistungsverzeichnisse {country}: {len(positionen):,} Positionen aus {mit_gaeb} Vorgängen "
          f"(GAEB), {len(lv)} Vorgänge mit LV insgesamt")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    sys.exit(main(a.country, a.limit))

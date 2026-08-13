"""Kriterien-Matrizen (UfAB/EVB-IT) aus XLSX → ``doc_criteria.parquet``.

**Warum das der wichtigste noch fehlende Baustein war.** Die Parser-Selbstdiagnose wies für
``award_weights`` eine Lücke von 102 aus, und die häufigste unerkannte Textform lautete
*„Mehrere Zuschlagskriterien gemäß Formblatt"* — die Gewichte stehen also nicht im Fließtext,
sondern in einem separaten Formblatt. Das Formblatt liegt den Unterlagen bei: als Excel mit
stabilem Spaltenschema (Kriterienhauptgruppe / Kriteriengruppe / Kriterium / Gewichtung).

Und es trägt mehr als Gewichte: die Spalte hinter dem Kriteriums-Code führt **A oder B** —
``A = Ausschlusskriterium`` (nicht erfüllt ⇒ Angebot fliegt raus), ``B = Bewertungskriterium``
(bringt Punkte). Das ist die K.o.-Liste, also die erste Frage jedes Bieters.

**Warum hier Zellwerte gelesen werden.** ``docparse.parse_xlsx`` liest bewusst keine Werte
(§6.2). Diese Regel stammt aus dem Upload-Pfad, wo Nutzer eigene Dokumente hochladen. Hier
geht es um veröffentlichte Vergabeunterlagen von öffentlichen Portalen — von Sven ausdrücklich
freigegeben (2026-08-13). Der Upload-Pfad bleibt unverändert.

**Robustheit.** Spalten werden über die ÜBERSCHRIFT gefunden, nie über einen festen Index:
die Matrizen nutzen verbundene Zellen, dieselbe Spalte liegt je Formular woanders. Was nicht
erkannt wird, wird übersprungen — lieber ein Vorgang weniger als eine falsche Zuordnung.

Aufruf:  python3 scripts/extract_criteria.py [--country DE]
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.filterwarnings("ignore", module="openpyxl")

# Überschriften, an denen die Matrix erkannt wird. Der Kern ist „Kriterienhauptgruppe" —
# ohne den ist es eine andere Tabelle und wird nicht angefasst.
_MARKER = "kriterienhauptgruppe"
_SPALTEN = {
    "khg":        r"kriterienhauptgruppe",
    "kg":         r"kriteriengruppe",
    "k":          r"^kriterium",
    "gewichtung": r"^gewichtung",
    "prozent":    r"^prozent",
}
# Kriteriums-Code wie „A.1.1.4" / „B.2.3" — der Buchstabe davor ist die Art.
_CODE = re.compile(r"^([AB])\.((?:\d+\.)*\d+)$", re.I)
_MAX_ZEILEN = 4000


def _kopfzeile(ws) -> tuple[int, dict[str, int]] | None:
    """Kopfzeile suchen und Spaltenüberschrift → Index abbilden (nicht über feste Positionen)."""
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i > 25:
            return None
        zellen = [str(c).strip().lower() if c is not None else "" for c in row]
        if not any(_MARKER in c for c in zellen):
            continue
        idx: dict[str, int] = {}
        for name, muster in _SPALTEN.items():
            for j, c in enumerate(zellen):
                if c and re.search(muster, c):
                    idx.setdefault(name, j)
        # „Gewichtung" ist eine VERBUNDENE Zelle ueber drei Unterspalten. Die Werte stehen
        # nicht darunter, sondern in den Unterspalten, die erst die naechste Zeile benennt:
        #   Zeile 0:  … | Gewichtung |    |    | Prozent | …
        #   Zeile 1:  … |    KHG     | KG | K  |         | …
        # Ohne diesen Schritt las ich die verbundene Kopfspalte und bekam ueberall None —
        # gemessen 0 von 6.832 Kriterien mit Gewichtung.
        if "gewichtung" in idx:
            unter = next(ws.iter_rows(min_row=i + 2, max_row=i + 2, values_only=True), ())
            unter = [str(c).strip().lower() if c is not None else "" for c in unter]
            j0 = idx["gewichtung"]
            for j in range(j0, min(j0 + 4, len(unter))):
                if unter[j] == "khg":
                    idx["gew_khg"] = j
                elif unter[j] == "kg":
                    idx["gew_kg"] = j
                elif unter[j] == "k":
                    idx["gew_k"] = j
        return i, idx
    return None


def _zahl(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def lies_matrix(daten: bytes, blatt: str) -> list[dict]:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(daten), read_only=False, data_only=True)
    except Exception:
        return []
    if blatt not in wb.sheetnames:
        wb.close()
        return []
    ws = wb[blatt]
    kopf = _kopfzeile(ws)
    if not kopf:
        wb.close()
        return []
    start, idx = kopf
    aus: list[dict] = []
    khg = kg = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i <= start + 1 or i > _MAX_ZEILEN:
            continue
        z = [str(c).strip() if c is not None else "" for c in row]

        def feld(name: str) -> str:
            j = idx.get(name)
            return z[j] if j is not None and j < len(z) else ""

        # Ebene 1/2: Hauptgruppe bzw. Gruppe merken — sie stehen einmal und gelten fuer die
        # darunter liegenden Kriterien weiter (typische Excel-Gliederung ohne Wiederholung).
        if feld("khg"):
            khg = feld("khg")
            kg = None
        if feld("kg"):
            # In der Gruppenzeile steht links die Nummer, rechts daneben der Name.
            j = idx["kg"]
            name = next((x for x in z[j + 1:j + 4] if x), "")
            kg = f"{feld('kg')} {name}".strip()

        # Ebene 3: das eigentliche Kriterium — erkennbar am Code „A.1.1.4".
        code = txt = art = ""
        for j, c in enumerate(z):
            m = _CODE.match(c)
            if m:
                code, art = c, m.group(1).upper()
                txt = next((x for x in z[j + 1:j + 3] if len(x) > 3), "")
                break
        if not code:
            continue
        aus.append({
            "khg": khg or None, "kg": kg or None, "code": code,
            "art": "ausschluss" if art == "A" else "bewertung",
            "text": txt[:400] or None,
            # Gewicht auf Kriteriumsebene; die Gruppen-Gewichte stehen in den
            # Gruppenzeilen und gelten fuer alle Kriterien darunter.
            "gewichtung": _zahl(feld("gew_k")) or _zahl(feld("gewichtung")),
            "gew_gruppe": _zahl(feld("gew_kg")),
            "gew_hauptgruppe": _zahl(feld("gew_khg")),
            "prozent": _zahl(feld("prozent")),
        })
    wb.close()
    return aus


def main(country: str) -> int:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = ROOT / "data" / "docs" / country
    lv = root / "doc_lv.parquet"
    if not lv.exists():
        print("kein doc_lv.parquet — erst `extract_positions.py` laufen lassen.")
        return 1
    con = duckdb.connect()
    kandidaten = con.execute(
        f"""SELECT notice_id, xlsx_blaetter FROM read_parquet('{lv.as_posix()}')
            WHERE lower(xlsx_blaetter) LIKE '%{_MARKER}%'""").fetchall()

    zeilen: list[dict] = []
    ohne = 0
    for nid, js in kandidaten:
        treffer = [b for b in json.loads(js)
                   if any(_MARKER in (c or "").lower() for c in b.get("columns", []))]
        vorher = len(zeilen)
        for b in treffer:
            pfad = next((root / nid).glob("*.zip"), None)
            if not pfad:
                continue
            try:
                with zipfile.ZipFile(pfad) as zf:
                    daten = zf.read(b["datei"])
            except Exception:
                continue
            for k in lies_matrix(daten, b["name"]):
                zeilen.append({"notice_id": nid, "datei": b["datei"], **k})
        if len(zeilen) == vorher:
            ohne += 1

    if zeilen:
        pq.write_table(pa.Table.from_pylist(zeilen, schema=pa.schema([
            ("notice_id", pa.string()), ("datei", pa.string()), ("khg", pa.string()),
            ("kg", pa.string()), ("code", pa.string()), ("art", pa.string()),
            ("text", pa.string()), ("gewichtung", pa.float64()),
            ("gew_gruppe", pa.float64()), ("gew_hauptgruppe", pa.float64()),
            ("prozent", pa.float64())])),
            root / "doc_criteria.parquet", compression="zstd")
    n_vorgang = len({z["notice_id"] for z in zeilen})
    n_aus = sum(1 for z in zeilen if z["art"] == "ausschluss")
    print(f"Kriterien-Matrizen {country}: {len(zeilen):,} Kriterien aus {n_vorgang} Vorgängen "
          f"({n_aus:,} Ausschluss-, {len(zeilen)-n_aus:,} Bewertungskriterien)")
    if ohne:
        print(f"  {ohne} Vorgänge mit Matrix-Überschrift, aber ohne lesbare Zeilen — "
              f"abweichendes Layout, bewusst übersprungen statt geraten.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    sys.exit(main(ap.parse_args().country))

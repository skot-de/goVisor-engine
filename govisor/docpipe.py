"""Dokument-Pipeline — Vergabeunterlagen-ZIPs → Volltext-Index.

**Engine-unabhängig:** verarbeitet die ZIPs, die ``docfetch`` (cosinex) auf die SSD legt, GENAUSO
wie Dateien, die anderswoher kommen (Bund/AI per Login, manuell geliefert). Einziges Contract: die
ZIPs liegen unter ``<data>/docs/<country>/<notice_id>/*.zip``.

Extrahiert Text je Datei (PDF/DOCX/XLSX/TXT/HTML), **rekursiv durch verschachtelte ZIPs** (Vergabe-
unterlagen packen oft ZIP-in-ZIP). Schreibt einen Volltext-Index ``doc_text.parquet``
(notice_id, file, filetype, n_chars, text) — die Basis für Suche + Analyse (Leistungsverzeichnis,
Eignungskriterien …). Scan-PDFs ohne Textebene ergeben ``n_chars=0`` und werden ehrlich als
``image_only`` geflaggt (OCR wäre ein eigener Schritt).

Robust: Fehler je Datei werden gefangen (eine kaputte PDF kippt nicht den Lauf). Idempotent über
``--force`` steuerbar (sonst wird ein vorhandener Index neu gebaut, das ist billig).
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from .config import Config

_MAX_TEXT = 2_000_000   # pro Datei kappen (Index soll durchsuchbar bleiben, nicht Bücher speichern)


def _pdf_text(data: bytes) -> str:
    """PDF-Text: pypdf (schnell) zuerst, pdfplumber als Fallback (robuster bei Layout)."""
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        t = "\n".join((p.extract_text() or "") for p in r.pages)
        if t.strip():
            return t
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except Exception:
        return ""


def _docx_text(data: bytes) -> str:
    """DOCX = ZIP mit word/document.xml — Tags grob strippen (kein python-docx nötig)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        xml = re.sub(r"</w:p>", "\n", xml)          # Absätze erhalten
        return re.sub(r"\s+\n", "\n", re.sub(r"<[^>]+>", " ", xml)).strip()
    except Exception:
        return ""


def _xlsx_text(data: bytes) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    out.append("\t".join(cells))
        return "\n".join(out)
    except Exception:
        return ""


def _html_text(data: bytes) -> str:
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(data, "html.parser").get_text(" ", strip=True)
    except Exception:
        return ""


def _txt(data: bytes) -> str:
    for enc in ("utf-8", "cp1252", "iso-8859-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


_EXTRACT = {
    ".pdf": _pdf_text, ".docx": _docx_text, ".xlsx": _xlsx_text,
    ".htm": _html_text, ".html": _html_text, ".xml": _html_text,
    ".txt": _txt, ".csv": _txt,
}
# bekannt, aber ohne einfachen Extraktor (Alt-Office/Binär) → geflaggt, nicht ignoriert
_KNOWN_NOEXTRACT = {".doc", ".xls", ".ppt", ".rtf", ".odt", ".p7s", ".zip"}


def iter_docs(zip_bytes: bytes, prefix: str = "", depth: int = 0):
    """(pfad, ext, bytes) je Datei — rekursiv durch verschachtelte ZIPs (max. 5 Ebenen)."""
    if depth > 5:
        return
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            ext = Path(name).suffix.lower()
            try:
                data = zf.read(info)
            except Exception:
                continue
            if ext == ".zip":
                yield from iter_docs(data, prefix + name + "::", depth + 1)
            else:
                yield prefix + name, ext, data


def process_zip(path: Path) -> list[dict]:
    """Ein Vergabeunterlagen-ZIP → Zeilen [{file, filetype, n_chars, text, status}]."""
    rows = []
    try:
        blob = Path(path).read_bytes()
    except Exception:
        return rows
    for name, ext, data in iter_docs(blob):
        fn = _EXTRACT.get(ext)
        if fn:
            text = (fn(data) or "")[:_MAX_TEXT]
            status = "ok" if text.strip() else ("image_only" if ext == ".pdf" else "empty")
        else:
            text = ""
            status = "unsupported" if ext in _KNOWN_NOEXTRACT else "unknown_type"
        rows.append({"file": name, "filetype": ext, "n_chars": len(text),
                     "text": text, "status": status})
    return rows


def build_index(cfg: Config, country: str = "DE") -> dict:
    """Alle ``docs/<country>/<notice_id>/*.zip`` → ``docs/<country>/doc_text.parquet``.

    Gibt eine Zusammenfassung zurück (Vorgänge, Dateien, Zeichen, Status-Verteilung).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = cfg.data_dir / "docs" / country
    if not root.exists():
        print(f"docpipe: keine Dokumente unter {root} — erst `fetch-docs` laufen lassen.")
        return {}
    rows = []
    status_counts: dict[str, int] = {}
    n_notices = 0
    for notice_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        zips = list(notice_dir.glob("*.zip"))
        if not zips:
            continue
        n_notices += 1
        for zp in zips:
            for r in process_zip(zp):
                r = {"notice_id": notice_dir.name, "archive": zp.name, **r}
                status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
                rows.append(r)
    if not rows:
        print("docpipe: keine Dateien in den ZIPs gefunden.")
        return {}
    schema = pa.schema([("notice_id", pa.string()), ("archive", pa.string()),
                        ("file", pa.string()), ("filetype", pa.string()),
                        ("n_chars", pa.int64()), ("status", pa.string()), ("text", pa.string())])
    out = root / "doc_text.parquet"
    pq.write_table(pa.Table.from_pylist([{k: r[k] for k in schema.names} for r in rows], schema=schema),
                   out, compression="zstd")
    total_chars = sum(r["n_chars"] for r in rows)
    print(f"docpipe {country}: {n_notices} Vorgänge, {len(rows)} Dateien, {total_chars/1e6:.1f} Mio. Zeichen "
          f"→ {out.name}")
    print("  Status: " + " | ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    return {"notices": n_notices, "files": len(rows), "chars": total_chars, "status": status_counts}

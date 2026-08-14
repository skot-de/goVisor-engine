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
from .docupload import MAX_PACKAGE_BYTES, MAX_ZIP_DEPTH, check_zip_bomb

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


def iter_docs(zip_bytes: bytes, prefix: str = "", depth: int = 0, _budget: list | None = None):
    """(pfad, ext, bytes) je Datei — rekursiv durch verschachtelte ZIPs.

    ZIP-Bomben-Schutz (§4.2, Sicherheits-Härtung): pro Eintrag wird die DEKLARIERTE unkomprimierte
    Größe (`ZipInfo.file_size`) GEGEN die komprimierte geprüft, BEVOR entpackt wird — ein verdächtiges
    Verhältnis (`check_zip_bomb`, 100:1) wird übersprungen. Zusätzlich ein laufendes Gesamt-Budget
    an unkomprimierten Bytes (`MAX_PACKAGE_BYTES`), damit auch viele mittelgroße Einträge nicht in
    Summe den Speicher sprengen. Tiefe an `MAX_ZIP_DEPTH` gebunden.
    """
    if depth > MAX_ZIP_DEPTH:
        return
    if _budget is None:
        _budget = [MAX_PACKAGE_BYTES]        # verbleibendes unkomprimiertes Byte-Budget (mutierbar über die Rekursion)
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # Vor dem Entpacken: Kompressionsverhältnis + Gesamt-Budget prüfen (Zip-Bombe).
            if check_zip_bomb(info.compress_size, info.file_size):
                continue                     # verdächtiges Verhältnis → Eintrag überspringen
            if info.file_size > _budget[0]:
                return                       # Budget erschöpft → Extraktion abbrechen
            name = info.filename
            ext = Path(name).suffix.lower()
            try:
                data = zf.read(info)
            except Exception:
                continue
            _budget[0] -= len(data)
            if ext == ".zip":
                yield from iter_docs(data, prefix + name + "::", depth + 1, _budget)
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


# Zeitlimit JE ARCHIV. Am 2026-08-14 lief `index-docs` 106 Minuten an einem einzelnen
# Dokument fest (der Stack zeigte reine String-Arbeit, kein Fortschritt) und blockierte die
# restlichen fuenf Schritte des Tageslaufs.
#
# Der Wecker steht bewusst IM Arbeiter und nicht beim Verteiler: ein Pool kann eine bereits
# laufende Aufgabe nicht abbrechen — `future.cancel()` greift nur, solange sie wartet. Nur
# der Arbeiter selbst kann sich unterbrechen.
ZEIT_JE_ARCHIV = 120


def _verarbeite_archiv(auftrag):
    """Ein Archiv → Zeilen. Muss auf Modulebene stehen, damit der Pool sie versenden kann.

    Ein Fehlschlag ist eine ZEILE, kein Abbruch: die Projektregel „markieren statt filtern"
    gilt auch hier. Ein Archiv, das in die Zeitgrenze laeuft, verschwindet nicht stillschweigend
    aus dem Index — es steht mit `status='zeitlimit'` drin und ist damit zaehlbar.
    """
    import signal
    notice_id, pfad = auftrag
    zp = Path(pfad)

    def _wecker(signum, frame):
        raise TimeoutError(f"{ZEIT_JE_ARCHIV}s ueberschritten")

    alt = None
    try:
        alt = signal.signal(signal.SIGALRM, _wecker)
        signal.alarm(ZEIT_JE_ARCHIV)
    except (AttributeError, ValueError):
        alt = None                      # kein SIGALRM (Windows) — dann eben ohne Limit
    try:
        return [{"notice_id": notice_id, "archive": zp.name, **r} for r in process_zip(zp)]
    except Exception as e:
        return [{"notice_id": notice_id, "archive": zp.name, "file": "", "filetype": "",
                 "n_chars": 0, "status": "zeitlimit" if isinstance(e, TimeoutError) else "fehler",
                 "text": ""}]
    finally:
        try:
            signal.alarm(0)
            if alt is not None:
                signal.signal(signal.SIGALRM, alt)
        except (AttributeError, ValueError):
            pass


def _dringlichkeit(cfg: Config, country: str) -> dict[str, int]:
    """notice_id → Tage bis zur Angebotsfrist. Kleiner = dringender.

    Sortierschluessel fuer die Abarbeitung. Ohne Frist (abgelaufen, Zuschlag, unbekannt)
    landet ein Vorgang hinten — nicht weil er wertlos waere, sondern weil niemand mehr auf
    ihn bietet.
    """
    import duckdb
    p = cfg.gold_dir / country / "lead_deadline.parquet"
    if not p.exists():
        return {}
    return {r[0]: int(r[1]) for r in duckdb.connect().execute(
        f"SELECT notice_id, datediff('day', current_date, deadline_date) "
        f"FROM read_parquet('{p.as_posix()}') WHERE deadline_date IS NOT NULL").fetchall()}


def build_index(cfg: Config, country: str = "DE", neu_aufbauen: bool = False,
                zeit_budget: int | None = None) -> dict:
    """Alle ``docs/<country>/<notice_id>/*.zip`` → ``docs/<country>/doc_text.parquet``.

    Gibt eine Zusammenfassung zurück (Vorgänge, Dateien, Zeichen, Status-Verteilung).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = cfg.data_dir / "docs" / country
    if not root.exists():
        print(f"docpipe: keine Dokumente unter {root} — erst `fetch-docs` laufen lassen.")
        return {}
    # VIELE LESER, EIN SCHREIBER.
    #
    # Die Extraktion ist rein lokal und CPU-gebunden; am 2026-08-14 lief sie einkernig auf
    # einer 10-Kern-Maschine ueber 3.243 Vorgaenge. Der Abruf davor wird bewusst NICHT
    # parallelisiert — der ist netzgebunden und absichtlich langsam, aus Ruecksicht auf
    # fremde Portale.
    #
    # ⚠ Die Arbeiter schreiben NICHTS. Genau daran ist es heute schiefgegangen: zwei
    # Prozesse schrieben gleichzeitig `doc_text.parquet`. Sie liefern Zeilen zurueck, und
    # geschrieben wird EINMAL, unten, von diesem Prozess.
    import multiprocessing as mp

    # INKREMENTELL. Der eigentliche Hebel — groesser als die Parallelisierung.
    #
    # Gemessen 2026-08-14: der Bestand ist **89 GB** in 3.241 Archiven, 484 davon ueber
    # 50 MB. `build_index` entpackte bisher JEDES MAL alles. Bei taeglich einigen Dutzend
    # neuen Vorgaengen heisst das, 89 GB zu verarbeiten, um 1,5 GB Neues zu erfassen.
    #
    # Ein Archiv aendert sich nicht: der Abruf ist idempotent und ueberspringt, was schon
    # liegt („exists … vorhanden"). Der Schluessel (notice_id, archive) genuegt deshalb.
    #
    # ⚠ NACH EINER PARSER-AENDERUNG MUSS `neu_aufbauen=True` GESETZT WERDEN. Sonst traegt
    # der Index halb altes, halb neues Verhalten — und das faellt niemandem auf. Genau
    # diese Sorte stiller Altlast hat heute zugeschlagen: zwei Wochen lang entstanden
    # Anforderungs-Signale aus einem Textbestand vom 31. Juli, weil der Index nie neu
    # geschrieben wurde und niemand die Datei-Zeitstempel ansah.
    out = root / "doc_text.parquet"
    bekannt: set[tuple[str, str]] = set()
    if out.exists() and not neu_aufbauen:
        # NUR DIE SCHLUESSEL, nicht der Text.
        #
        # Erster Entwurf las den kompletten Bestand nach Python — und machte damit den
        # Speicherbedarf GROESSER statt kleiner, obwohl die Inkrementalitaet ihn senken
        # sollte. Bei 16 GB RAM, 2 GB Swap und 89 GB Archiven fuehrte das zu einer vollen
        # Platte (der Rechner musste am 2026-08-14 deshalb neu gestartet werden).
        #
        # Der Bestand wird unten STROMWEISE uebernommen, Zeilengruppe fuer Zeilengruppe —
        # er muss nie ganz im Speicher liegen.
        import duckdb
        bekannt = {(r[0], r[1]) for r in duckdb.connect().execute(
            f"SELECT DISTINCT notice_id, archive FROM read_parquet('{out.as_posix()}')"
        ).fetchall()}

    auftraege = []
    n_notices = 0
    uebersprungen = 0
    for notice_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        zips = list(notice_dir.glob("*.zip"))
        if not zips:
            continue
        n_notices += 1
        for zp in zips:
            if (notice_dir.name, zp.name) in bekannt:
                uebersprungen += 1
                continue
            auftraege.append((notice_dir.name, str(zp)))
    if uebersprungen:
        print(f"docpipe {country}: {uebersprungen} Archive bereits im Index — uebersprungen "
              f"(`neu_aufbauen=True` erzwingt alles)", flush=True)
    if not auftraege:
        print(f"docpipe {country}: nichts Neues zu indizieren.")
        return {"notices": n_notices, "uebersprungen": uebersprungen}

    # DRINGENDES ZUERST. Nicht „neu vor alt" — ein heute geladenes Dokument fuer einen Lead
    # mit 90 Tagen Restfrist ist weniger wert als eines von letzter Woche fuer einen mit
    # drei. Der Bieter braucht das Leistungsverzeichnis, wenn er BIETET.
    #
    # Erst diese Reihenfolge macht das Zeitbudget unten vertretbar: schneidet man eine
    # unsortierte Liste ab, bleibt womoeglich genau das Dringende liegen.
    #
    # Gemessen 2026-08-14: 22,4 % der offenen DE-Leads haben unter sieben Tagen Restfrist.
    tage = _dringlichkeit(cfg, country)
    auftraege.sort(key=lambda a: (tage.get(a[0], 10**6), a[0]))

    rows = []
    status_counts: dict[str, int] = {}
    arbeiter = max(1, min(mp.cpu_count() - 2, 8))
    print(f"docpipe {country}: {len(auftraege)} Archive aus {n_notices} Vorgaengen, "
          f"{arbeiter} Arbeiter, {ZEIT_JE_ARCHIV}s je Archiv", flush=True)
    fertig = 0
    # ZEITBUDGET. Was nicht mehr reinpasst, macht der naechste Lauf — dank Inkrementalitaet
    # ohne Doppelarbeit. Der Rueckstand laeuft so ueber mehrere Naechte ab, ohne je das
    # Frische zu blockieren. Am 2026-08-14 kamen 76 GB auf einmal herein (zwei Wochen
    # Abruf-Ausfall); mit Budget waere das kein Notfall gewesen, sondern ein paar Naechte.
    #
    # KEIN STILLES ABSCHNEIDEN: was liegenbleibt, wird unten gezaehlt und gemeldet.
    import time as _t
    start = _t.monotonic()
    abgeschnitten = 0
    # chunksize=1, damit das Budget zeitnah greift — bei 4 laeuft ein Arbeiter noch drei
    # Archive weiter, und bei 50-MB-Archiven ist das viel.
    with mp.Pool(arbeiter) as pool:
        for teil in pool.imap_unordered(_verarbeite_archiv, auftraege, chunksize=1):
            # ERST einsammeln, DANN die Zeit pruefen. Andersherum wuerde das gerade fertig
            # gewordene Archiv verworfen — die Arbeit war getan und landete im Muell.
            for r in teil:
                status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
                rows.append(r)
            fertig += 1
            # Fortschritt ins Log. Ohne ihn war heute „haengt" von „arbeitet" nur ueber
            # `sample` auf die Prozess-ID zu unterscheiden.
            if fertig % 200 == 0 or fertig == len(auftraege):
                print(f"  {fertig}/{len(auftraege)} Archive", flush=True)
            if zeit_budget is not None and _t.monotonic() - start > zeit_budget:
                abgeschnitten = len(auftraege) - fertig
                pool.terminate()
                break
    if abgeschnitten:
        print(f"  ⏳ Zeitbudget ({zeit_budget}s) erreicht — {abgeschnitten} Archive bleiben "
              f"fuer den naechsten Lauf (dringendste zuerst abgearbeitet)", flush=True)
    if not rows and not bekannt:
        print("docpipe: keine Dateien in den ZIPs gefunden.")
        return {}
    schema = pa.schema([("notice_id", pa.string()), ("archive", pa.string()),
                        ("file", pa.string()), ("filetype", pa.string()),
                        ("n_chars", pa.int64()), ("status", pa.string()), ("text", pa.string())])

    # STROMWEISE SCHREIBEN, nicht als eine grosse Tabelle.
    #
    # `pa.Table.from_pylist` ueber alles haette den gesamten Volltext auf einmal im Speicher
    # — genau der Fehler, der die Platte gefuellt hat. Stattdessen: erst den Bestand
    # Zeilengruppe fuer Zeilengruppe durchreichen, dann das Neue in Bloecken anhaengen.
    # Der Spitzenbedarf ist damit eine Zeilengruppe, nicht der ganze Index.
    #
    # Erst in eine Nebendatei, dann umbenennen: ein Abbruch mittendrin (Strom, Speicher,
    # Neustart) darf den vorhandenen Index nicht zerstoeren. Am 2026-08-14 ging genau so
    # eine Stunde Arbeit verloren, weil erst ganz am Ende geschrieben wurde.
    tmp = out.with_suffix(".parquet.neu")
    schreiber = pq.ParquetWriter(tmp, schema, compression="zstd")
    try:
        if bekannt and out.exists():
            alt = pq.ParquetFile(out)
            for i in range(alt.num_row_groups):
                schreiber.write_table(alt.read_row_group(i).select(schema.names))
        BLOCK = 2000
        for i in range(0, len(rows), BLOCK):
            teil = rows[i:i + BLOCK]
            schreiber.write_table(pa.Table.from_pylist(
                [{k: r[k] for k in schema.names} for r in teil], schema=schema))
    finally:
        schreiber.close()
    tmp.replace(out)
    total_chars = sum(r["n_chars"] for r in rows)   # nur die NEUEN, der Bestand ist durchgereicht
    print(f"docpipe {country}: {n_notices} Vorgänge, {len(rows)} Dateien, {total_chars/1e6:.1f} Mio. Zeichen "
          f"→ {out.name}")
    print("  Status: " + " | ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    return {"notices": n_notices, "files": len(rows), "chars": total_chars, "status": status_counts}

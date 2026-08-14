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
import os
import re
import zipfile
from pathlib import Path

from .config import Config
from . import db as _db
from .docupload import MAX_PACKAGE_BYTES, MAX_ZIP_DEPTH, check_zip_bomb

_MAX_TEXT = 2_000_000   # pro Datei kappen (Index soll durchsuchbar bleiben, nicht Bücher speichern)
_MAX_TEXT_ARCHIV = 30_000_000   # und pro ARCHIV, s. Begründung in `process_zip`


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


# GROESSEN-SPERRE JE DATEI. Gemessen 2026-08-14 an echten Paketen (je 6 Proben):
#
#   PDF-Groesse   Zeichen/MB   bildrein   Ø Sekunden
#   0–1 MB            34.246      0/6            0,1
#   1–5 MB           150.970      0/6            4,3     ← hier steckt der Inhalt
#   5–20 MB              447      1/6           35,3
#   20–60 MB          12.916      0/6          182,0
#   >60 MB             2.196      3/6          600,3     ← zehn Minuten je Datei
#
# Die grossen Dateien heissen „Fotodokumentation_Drohnenbefliegung", „Fotoduku_Drohne",
# „Parkflaechen Fotos". Sie sind Bilderstrecken: die HAELFTE liefert gar keinen Text, und
# die Textdichte ist 69× schlechter als bei 1–5-MB-Dateien.
#
# Der Zeitanteil ist der eigentliche Schaden. `ZEIT_JE_ARCHIV` steht auf 120 Sekunden —
# EINE grosse PDF sprengt das um das Fuenffache, und dann liefert das GANZE Archiv nichts
# (`status='zeitlimit'`). Genau so entstand der 106-Minuten-Haenger, der den Tageslauf
# blockierte. Eine Sperre je ARCHIV bestraft die 507 anderen Dateien mit; eine Sperre je
# DATEI holt aus demselben Archiv alles Brauchbare und laesst nur den Brocken liegen.
#
# WO DIE GRENZE LIEGT — nachgemessen, weil 40 MB ein Bauchwert war. Jedes Archiv in einem
# EIGENEN Prozess (`ru_maxrss` ist ein Hochwasserstand und sinkt nie; mehrere Archive in
# einem Prozess ergeben eine Zahl, die alle vermischt — der Fehler kostete den ersten Anlauf):
#
#   Archiv   Grenze     Sek.       RSS      Zeichen
#   636 MB     5 MB       11     333 MB      958.936
#   636 MB    10 MB       22     752 MB    1.127.833
#   636 MB    20 MB      100   3.013 MB    1.692.555
#   636 MB    40 MB      173   6.370 MB    2.293.333
#   495 MB    10 MB      265   1.162 MB    3.461.594
#   495 MB    20 MB      359   3.254 MB    3.562.982
#   495 MB    40 MB      486   8.639 MB    3.633.037
#
# Beim 495-MB-Paket kostet der Sprung von 10 auf 40 MB das SIEBENFACHE an Speicher fuer
# 5 % mehr Text. Bei acht Arbeitern waeren 40 MB im schlechtesten Fall ueber 50 GB auf einer
# 16-GB-Maschine — schlimmer als der Zustand, der heute zweimal zum Absturz fuehrte.
#
# 10 MB haelt einen Arbeiter unter ~1,2 GB und holt trotzdem den Grossteil des Textes. Der
# Speicher ist dabei NICHT streng monoton (495 MB: 5er-Grenze 1.512 MB, 10er 1.162 MB) — die
# PDF-Bibliothek alloziert je Dokument sehr unterschiedlich. Die Zahlen sind Groessen-
# ordnungen, keine Praezisionswerte.
#
# ⚠ MARKIERT, NICHT VERWORFEN: uebersprungene Dateien bekommen `status='datei_zu_gross'`.
MAX_DATEI_MB = int(os.environ.get("GOVISOR_MAX_DATEI_MB", "10"))


def iter_docs(quelle, prefix: str = "", depth: int = 0, _budget: list | None = None):
    """(pfad, ext, bytes) je Datei — rekursiv durch verschachtelte ZIPs.

    `quelle` ist ein PFAD oder ein Byte-Blob. Der Pfad ist der Normalfall und der Grund
    fuer diese Unterscheidung: `zipfile` liest dann direkt von der Platte und braucht nur
    den jeweils entpackten Eintrag im Speicher. Vorher wurde das Archiv erst komplett
    gelesen (636 MB) und dann fuer `io.BytesIO` noch einmal kopiert — 1,3 GB, bevor die
    erste Datei entpackt war. Bytes bleiben moeglich, weil verschachtelte ZIPs nur so
    vorliegen.

    Zu grosse EINZELDATEIEN werden uebersprungen und als solche gemeldet (s. `MAX_DATEI_MB`
    oben) — nicht stillschweigend, sondern als eigener Eintrag mit `ext=None`.

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
        zf = zipfile.ZipFile(quelle if isinstance(quelle, (str, Path))
                             else io.BytesIO(quelle))
    except (zipfile.BadZipFile, OSError):
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
            # Der Brocken wird gar nicht erst entpackt — das spart Speicher UND die
            # Minuten, die seine Text-Extraktion kosten wuerde.
            if MAX_DATEI_MB and info.file_size > MAX_DATEI_MB * 1e6:
                yield prefix + name, None, info.file_size
                continue
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
    # TEXT-BUDGET JE ARCHIV. `_MAX_TEXT` deckelt die EINZELNE Datei auf 2 MB — ein Archiv
    # mit 196 Dateien darf daraus trotzdem 392 MB machen, und die reist als Pickle zurueck
    # zum Elternprozess. Genau diese Summe war der Rest des 1,95-GB-Arbeiters.
    #
    # 30 MB reichen fuer eine durchsuchbare Ausschreibung um Groessenordnungen; wer mehr
    # braucht, liest das Original. Was nicht mehr hineinpasst, wird GEMELDET, nicht
    # verschwiegen (`status='budget'`).
    rest = _MAX_TEXT_ARCHIV
    for name, ext, data in iter_docs(Path(path)):
        if ext is None:                       # zu grosse Einzeldatei, nicht entpackt
            rows.append({"file": name, "filetype": Path(name).suffix.lower(),
                         "n_chars": 0, "text": "", "status": "datei_zu_gross"})
            continue
        fn = _EXTRACT.get(ext)
        if fn:
            text = (fn(data) or "")[:_MAX_TEXT]
            status = "ok" if text.strip() else ("image_only" if ext == ".pdf" else "empty")
            if len(text) > rest:
                text, status = text[:max(rest, 0)], "budget"
            rest -= len(text)
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
# Angehoben von 120 s (2026-08-14), nachdem die Ursache vermessen war: die 120 s waren die
# Notbremse gegen den 106-Minuten-Haenger, und dafuer taugten sie. Sie trafen aber auch jedes
# ehrlich grosse Archiv — eine PDF von 20–60 MB braucht gemessen 182 s, ein Archiv mit dreien
# davon lief also ins Limit und lieferte NICHTS, obwohl jede einzelne Datei brauchbar war.
#
# Der eigentliche Zeitfresser (>60-MB-Dateien, Ø 600 s) faellt jetzt schon vorher unter
# `MAX_DATEI_MB`. Das Limit bleibt als Notbremse gegen Endlosschleifen, aber grosszuegig.
ZEIT_JE_ARCHIV = int(os.environ.get("GOVISOR_ZEIT_JE_ARCHIV", "900"))

# GROESSEN-SPERRE. `process_zip` liest das Archiv KOMPLETT in den Speicher und entpackt
# verschachtelte ZIPs mit hinein — aus 200 MB auf der Platte wird ein Vielfaches im RAM.
#
# Gemessen 2026-08-14, nachdem der Rechner ZWEIMAL abgestuerzt war: ein einzelner Arbeiter
# hielt 1,95 GB; das groesste Archiv (636 MB) lief mit EINEM Arbeiter ueber zehn Minuten
# ohne Ergebnis. Bei vier Arbeitern sind das im schlechtesten Fall acht GB gleichzeitig auf
# einer 16-GB-Maschine — der Weg in den Swap und in den Absturz.
#
# Die Verteilung macht die Entscheidung leicht:
#   bis  50 MB   2.743 Archive (84,5 %) =  28,6 GB
#   darueber       504 Archive (15,5 %) =  67,5 GB   ← 70 % des Volumens
# Fuenf von sechs Ausschreibungen fuer weniger als ein Drittel des Aufwands.
#
# ⚠ MARKIERT, NICHT VERWORFEN. Ein zu grosses Archiv bekommt eine Zeile mit
# `status='zu_gross'` und ist damit zaehlbar — die Projektregel „markieren statt filtern".
# Wer die 504 will, hebt die Schwelle oder baut `process_zip` auf stroemendes Entpacken um
# (eigenes Ticket; das ist der saubere Weg, aber der teure).
# ABGESCHALTET (Vorgabe 0) am 2026-08-14. Die Sperre war richtig, solange `process_zip` das
# ganze Archiv in den Speicher las — das tut sie nicht mehr (`iter_docs` liest vom Pfad).
# Speicher und Zeit werden jetzt dort begrenzt, wo sie entstehen: je Datei (`MAX_DATEI_MB`)
# und je Archiv-Textmenge (`_MAX_TEXT_ARCHIV`). Eine Grenze auf die ARCHIV-Groesse bestrafte
# 507 brauchbare Dateien fuer den einen Brocken, der neben ihnen lag.
#
# Wieder einschalten: `GOVISOR_MAX_ARCHIV_MB=50`.
MAX_ARCHIV_MB = int(os.environ.get("GOVISOR_MAX_ARCHIV_MB", "0"))


# ═══ SPEICHER: ZWEI SICHERUNGEN GEBAUT, BEIDE GEMESSEN WIRKUNGSLOS (2026-08-14) ═══
#
# Der Neuaufbau lief mit `MAX_DATEI_MB=10` — und ein EINZELNER Arbeiter stand bei 6,5 GB,
# bei 1,3 GB freiem RAM. Abgebrochen, sonst der dritte Rechnerabsturz des Tages.
#
# Versuch 1 — `RLIMIT_AS`: auf macOS wirkungslos. Gemessen lief eine 900-MB-Allokation
#   unter einer 500-MB-Grenze anstandslos durch; der Kernel setzt es dort nicht durch.
# Versuch 2 — Wachthread + SIGALRM (derselbe Mechanismus, der das ZEITlimit traegt):
#   loest aus, aber die `MemoryError` wird tief in der PDF-Bibliothek von einem internen
#   `except Exception` geschluckt. Gemessen: 2,15 GB bei 0,35 GB Grenze, Status `ok`.
#
# Beide wurden wieder ENTFERNT. Eine Sicherung, die nicht ausloest, ist schlimmer als keine:
# sie stiftet falsches Vertrauen und man faehrt mit acht Arbeitern los.
#
# WAS DARAUS FOLGT — und das ist die eigentliche Erkenntnis: Speicher laesst sich IN diesem
# Prozess nicht begrenzen. Wer ihn wirklich begrenzen will, muss jedes Archiv in einem
# EIGENEN kurzlebigen Prozess verarbeiten, den der Elternprozess ueberwacht und notfalls
# hart beendet — das Betriebssystem ist die einzige Instanz, die die Grenze durchsetzen
# kann. Das ist ein eigener Umbau (der Pool haelt langlebige Arbeiter; ein getoeteter
# Arbeiter bringt `mp.Pool` zum Haengen), kein Nebenbei.
#
# BIS DAHIN gilt: `MAX_DATEI_MB` klein halten und die Arbeiterzahl niedrig. Das ist eine
# Wette auf die Verteilung, keine Garantie — und sie ist hier ausdruecklich als solche
# benannt, damit niemand sie fuer eine Sicherung haelt.


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

    try:
        mb = zp.stat().st_size / 1e6
    except OSError:
        mb = 0
    if MAX_ARCHIV_MB and mb > MAX_ARCHIV_MB:
        return [{"notice_id": notice_id, "archive": zp.name, "file": "", "filetype": "",
                 "n_chars": 0, "status": "zu_gross", "text": ""}]

    alt = None
    try:
        alt = signal.signal(signal.SIGALRM, _wecker)
        signal.alarm(ZEIT_JE_ARCHIV)
    except (AttributeError, ValueError):
        alt = None                      # kein SIGALRM (Windows) — dann eben ohne Limit
    try:
        return [{"notice_id": notice_id, "archive": zp.name, **r} for r in process_zip(zp)]
    except (Exception, MemoryError) as e:
        if isinstance(e, TimeoutError):
            grund = "zeitlimit"
        elif isinstance(e, MemoryError):
            grund = "speicher"      # Grenze gegriffen — gezaehlt, nicht verschwiegen
        else:
            grund = "fehler"
        return [{"notice_id": notice_id, "archive": zp.name, "file": "", "filetype": "",
                 "n_chars": 0, "status": grund, "text": ""}]
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
    return {r[0]: int(r[1]) for r in _db.connect().execute(
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
        bekannt = {(r[0], r[1]) for r in _db.connect().execute(
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

    # ── SCHREIBEN WÄHREND DER ARBEIT, nicht danach ────────────────────────────────────────
    #
    # ⚠ DIE WICHTIGSTE ZEILE IN DIESER FUNKTION. Zwei Anlaeufe sind hier gescheitert, beide
    # am selben Denkfehler: die Ergebniszeilen wurden in einer Liste gesammelt und erst am
    # Ende geschrieben. Jede Zeile traegt den VOLLTEXT des Dokuments — bei 2.938 Archiven
    # sind das mehrere GB im Arbeitsspeicher.
    #
    # Gemessen 2026-08-14, zweiter Anlauf: nach 200 von 2.938 Archiven war der Swap zu 90 %
    # voll (9,3 von 10,2 GB), die interne Platte verlor 8 GB, und der Durchsatz brach von
    # 2,5 Archiven/s auf 0,3 ein — FUENFZEHNMAL langsamer. Die Maschine lagerte aus, statt
    # zu rechnen. Beim ersten Anlauf endete derselbe Fehler in einem erzwungenen Neustart.
    #
    # Jetzt: Schreiber VOR der Schleife oeffnen, jeden Block sofort wegschreiben, Puffer
    # leeren. Der Spitzenbedarf ist damit EIN Block statt des gesamten Index.
    #
    # Nebeneffekt, der genauso zaehlt: ein Abbruch kostet hoechstens den letzten Block. Der
    # erste Anlauf hatte ueber eine Stunde gearbeitet und hinterliess NICHTS.
    schema = pa.schema([("notice_id", pa.string()), ("archive", pa.string()),
                        ("file", pa.string()), ("filetype", pa.string()),
                        ("n_chars", pa.int64()), ("status", pa.string()), ("text", pa.string())])
    BLOCK = 200
    tmp = out.with_suffix(".parquet.neu")
    schreiber = pq.ParquetWriter(tmp, schema, compression="zstd")

    def _wegschreiben(puffer):
        if puffer:
            schreiber.write_table(pa.Table.from_pylist(
                [{k: r[k] for k in schema.names} for r in puffer], schema=schema))
            puffer.clear()

    status_counts: dict[str, int] = {}
    # ARBEITERZAHL. Jeder Arbeiter haelt EIN entpacktes Archiv im Speicher — bei den 484
    # Brocken ueber 50 MB sind acht davon mehrere GB gleichzeitig. Auf einer 16-GB-Maschine
    # koennen VIER Arbeiter schneller sein als acht, weil sie nicht in den Swap laufen.
    # Deshalb einstellbar statt fest verdrahtet.
    arbeiter = int(os.environ.get("GOVISOR_INDEX_ARBEITER", "0")) or max(
        1, min(mp.cpu_count() - 2, 8))
    print(f"docpipe {country}: {len(auftraege)} Archive aus {n_notices} Vorgaengen, "
          f"{arbeiter} Arbeiter, {ZEIT_JE_ARCHIV}s je Archiv", flush=True)

    import time as _t
    start = _t.monotonic()
    fertig = abgeschnitten = n_zeilen = total_chars = 0
    puffer: list[dict] = []
    try:
        # Bestand zuerst durchreichen — Zeilengruppe fuer Zeilengruppe, nie ganz im Speicher.
        if bekannt and out.exists():
            alt = pq.ParquetFile(out)
            for i in range(alt.num_row_groups):
                t = alt.read_row_group(i).select(schema.names)
                schreiber.write_table(t)
                n_zeilen += t.num_rows
        with mp.Pool(arbeiter) as pool:
            for teil in pool.imap_unordered(_verarbeite_archiv, auftraege, chunksize=1):
                for r in teil:
                    status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
                    total_chars += r["n_chars"]
                puffer.extend(teil)
                n_zeilen += len(teil)
                fertig += 1
                if len(puffer) >= BLOCK:
                    _wegschreiben(puffer)
                if fertig % 200 == 0 or fertig == len(auftraege):
                    print(f"  {fertig}/{len(auftraege)} Archive", flush=True)
                if zeit_budget is not None and _t.monotonic() - start > zeit_budget:
                    abgeschnitten = len(auftraege) - fertig
                    pool.terminate()
                    break
        _wegschreiben(puffer)
    finally:
        schreiber.close()
    tmp.replace(out)

    if abgeschnitten:
        print(f"  ⏳ Zeitbudget ({zeit_budget}s) erreicht — {abgeschnitten} Archive bleiben "
              f"fuer den naechsten Lauf (dringendste zuerst abgearbeitet)", flush=True)
    print(f"docpipe {country}: {n_notices} Vorgänge, {n_zeilen} Zeilen im Index, "
          f"{total_chars/1e6:.1f} Mio. Zeichen neu → {out.name}")
    print("  Status: " + " | ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    return {"notices": n_notices, "files": n_zeilen, "chars": total_chars,
            "status": status_counts, "offen": abgeschnitten}

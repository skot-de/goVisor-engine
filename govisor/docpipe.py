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
import datetime as _dt
import os
import re
import zipfile
from pathlib import Path

from .config import Config
from . import db as _db

ROOT = Path(__file__).resolve().parent.parent
from .docupload import MAX_PACKAGE_BYTES, MAX_ZIP_DEPTH, check_zip_bomb

# EINE Definition, von `build_index` UND `docworker` benutzt. Lagen sie doppelt vor, fiele
# eine Abweichung erst beim Zusammenfuehren auf — also nach der ganzen Arbeit.
def _schema():
    import pyarrow as pa
    return pa.schema([("notice_id", pa.string()), ("archive", pa.string()),
                      ("file", pa.string()), ("filetype", pa.string()),
                      ("n_chars", pa.int64()), ("status", pa.string()),
                      ("text", pa.string())])


# BEWUSST KEIN Lazy-Wrapper. Der erste Entwurf war einer (ein Objekt, das `_schema()` erst
# beim ersten Attributzugriff baut), und er ging schief: `pa.Table.from_pylist(schema=...)`
# verlangt eine ECHTE `pyarrow.Schema`, kein Objekt, das sich wie eine verhaelt. Der Fehler
# trat erst im Arbeiter-Prozess auf, dessen Ausgabe unterdrueckt ist — sichtbar war nur
# „Arbeiter endete mit 1". Wer Attribute durchreicht, hat den Typ nicht ersetzt.
#
# Wer `_schema()` braucht, ruft die Funktion. Das ist ein Zeichen mehr und keine Falle.

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


# ── OCR FUER BILDREINE PDFs ───────────────────────────────────────────────────────────
#
# Gemessen 2026-08-15 an je fuenf Proben aus drei Gruppen:
#
#   Gruppe                  Ø Zeichen   Ø Sek.   fachlich brauchbar
#   Leistungsverzeichnis        1.734      2,6              3 von 5
#   Plan / Bild                 1.283      2,1              0 von 5
#   nicht erkannt               1.579      1,8              1 von 5
#
# ZWEI ERKENNTNISSE, beide gegen meine eigene Erwartung:
#
#  (1) OCR ist BILLIG. 1,8–2,6 s fuer drei Seiten — ich hatte „teuer, Rechenzeit" gesagt.
#      Alle 2.267 bildreinen PDFs sind einkernig in gut einer Stunde durch.
#
#  (2) DIE ZEICHENZAHL SAGT NICHTS. Ein Luftbild liefert 1.283 Zeichen und sieht damit wie
#      ein Erfolg aus — es sind Kartenbeschriftungen mit Erkennungsfehlern
#      („Böschunaskörper", „Hemuonıg"). Haette ich nur gezaehlt, waere der Index mit 741
#      Plaenen voller Rauschen geflutet worden.
#
# Deshalb wird NACH dem Erkennen gefiltert, nicht davor: vorher zu entscheiden ginge ueber
# den Dateinamen, und der hat mich am selben Tag zweimal in die Irre gefuehrt (erst Ordner-
# statt Dateiname, dann 229 statt 23 Leistungsverzeichnisse). 57 % der Dateien heissen so,
# dass man ihnen nichts ansieht.
#
# Was NICHT durchkommt, wird MARKIERT (`ocr_ohne_inhalt`), nicht verworfen — und die Plaene
# sind ohnehin ueber die Unterlagen-Anzeige sichtbar. OCR und Anzeige loesen zwei
# verschiedene Haelften desselben Problems.
_OCR_AN = os.environ.get("GOVISOR_OCR", "1") == "1"
_OCR_SEITEN = int(os.environ.get("GOVISOR_OCR_SEITEN", "3"))
_OCR_MAX_MB = 25          # groessere Scans kosten Minuten und bringen selten mehr
_OCR_ZEIT = 120           # Notbremse je Datei

# Woran man eine Vergabeunterlage erkennt — NICHT am Vorhandensein von Buchstaben.
_FACH = re.compile(
    r"leistung|position|menge|einheit|angebot|bieter|vergabe|frist|eignung|nachweis|"
    r"vertrag|zuschlag|pauschal|einheitspreis|gesamtpreis|umsatzsteuer|nebenangebot",
    re.I)
_OCR_MINDEST = 3          # so viele Fachtreffer, sonst gilt es als Rauschen


def _ocr_verfuegbar() -> bool:
    """Einmal pruefen, dann merken. Fehlt tesseract, ist das kein Fehler — der Index laeuft
    weiter wie bisher und die Datei bleibt `image_only`."""
    if not hasattr(_ocr_verfuegbar, "_ja"):
        import shutil
        _ocr_verfuegbar._ja = bool(shutil.which("tesseract") and shutil.which("pdftoppm"))
    return _ocr_verfuegbar._ja


def _ocr_pdf(data: bytes) -> str:
    """Erste Seiten rastern und durch tesseract schicken. Leerer String bei jedem Problem."""
    import subprocess
    import tempfile
    if not _OCR_AN or not _ocr_verfuegbar() or len(data) > _OCR_MAX_MB * 1024 ** 2:
        return ""
    try:
        with tempfile.TemporaryDirectory() as d:
            quelle = Path(d) / "s.pdf"
            quelle.write_bytes(data)
            # 200 dpi: darunter leidet die Erkennung, darueber explodiert die Zeit.
            subprocess.run(["pdftoppm", "-r", "200", "-l", str(_OCR_SEITEN), "-png",
                            str(quelle), str(Path(d) / "b")],
                           capture_output=True, timeout=_OCR_ZEIT)
            teile = []
            for bild in sorted(Path(d).glob("b-*.png")):
                r = subprocess.run(["tesseract", str(bild), "stdout", "-l", "deu"],
                                   capture_output=True, text=True, timeout=_OCR_ZEIT)
                teile.append(r.stdout)
            return "\n".join(teile)
    except Exception:                                     # noqa: BLE001
        return ""


def _gaeb_text(data: bytes) -> str:
    """GAEB → durchsuchbarer Text der Leistungsverzeichnis-Positionen.

    **Der Parser lag fertig daneben und wurde nie gerufen.** `govisor/docparse.py` kann GAEB
    seit Ticket 23 (`parse_gaeb`, `parse_gaeb_flat`), aber `_EXTRACT` kannte die Endungen
    nicht — 2.082 Dateien (.x83 1.392 · .d83 557 · .p83 133) liefen deshalb als
    `unknown_type` durch, gemessen 2026-08-15.

    Das ist der teuerste Posten im ganzen Index gewesen: ein GAEB ist das
    LEISTUNGSVERZEICHNIS — Position, Menge, Einheit, Text. Genau das, wonach ein Bieter
    sucht, und genau das, was wir als „unbekanntes Format" verworfen haben.
    """
    from .docparse import parse_gaeb, parse_gaeb_flat
    d = None
    try:
        d = parse_gaeb(data) or parse_gaeb_flat(data)
    except Exception:                                     # noqa: BLE001
        return ""
    if not d:
        # RUECKFALLEBENE FUER DEN T-DIALEKT. Gemessen 2026-08-15: die `.d83`/`.p83` in
        # unseren Archiven beginnen mit `T0`/`T1`, nicht mit `00` — `parse_gaeb_flat`
        # lehnt sie deshalb korrekt ab (es ist nicht DA 90). Die `T1`-Saetze tragen aber
        # lesbaren Beschreibungstext ab Spalte 3.
        #
        # Wir holen ihn als TEXT, nicht als Positionen: die Satzstruktur dieses Dialekts
        # kennen wir nicht, und geratene Mengen waeren schlimmer als keine. 690 Dateien
        # (.d83 557 · .p83 133), die bisher gar nichts lieferten.
        try:
            roh = data.decode("cp850", "replace")
        except Exception:                                 # noqa: BLE001
            return ""
        # GAEB-KLAMMERFORMAT (`.p83`): `#begin[GAEB]` mit `[Tag]Wert[end]`. Wieder nur
        # TEXT, keine Positionen — die Tag-Bedeutungen kennen wir nicht, und geratene
        # Mengen waeren schlimmer als keine. 133 Dateien.
        if roh.lstrip().startswith("#begin"):
            import re as _re2
            werte = _re2.findall(r"\]([^\[\]]{3,})\[end\]", roh)
            return "\n".join(w.strip() for w in werte if any(c.isalpha() for c in w))
        if not roh.lstrip().startswith("T"):
            return ""
        zeilen = [z[2:].rstrip() for z in roh.splitlines()
                  if len(z) > 2 and z[0] == "T"]
        return "\n".join(z for z in zeilen if z.strip())
    zeilen = []
    for pos in (d.get("positions") or []):
        # Menge und Einheit gehoeren dazu: „4 St Hausnummernschild" ist suchbar,
        # „Hausnummernschild" allein verliert die Groessenordnung.
        teile = [pos.get("rno"), pos.get("qty"), pos.get("unit"), pos.get("text")]
        zeilen.append(" ".join(str(t) for t in teile if t))
    return "\n".join(zeilen)


def _odt_text(data: bytes) -> str:
    """ODT ist ein ZIP mit `content.xml` — braucht keine Bibliothek, nur zwei Zeilen."""
    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            roh = zf.read("content.xml")
    except Exception:                                     # noqa: BLE001
        return ""
    return _html_text(roh)


def _rtf_text(data: bytes) -> str:
    """RTF -> Text, ohne Abhaengigkeit.

    561 Dateien und damit der groesste Posten unter `unsupported` (gemessen 2026-08-15) —
    mehr als `.doc` (205) und `.xls` (86) zusammen. RTF ist im Kern lesbarer Text mit
    Steuerworten; ein Stripper reicht und spart eine Bibliothek, die sonst nur hierfuer
    im Projekt laege.

    DIE KOPFTABELLEN BRAUCHEN EINEN KLAMMERZAEHLER, kein Muster. Der erste Versuch war ein
    Regex auf `{\\fonttbl...}` — der scheitert, weil RTF-Tabellen VERSCHACHTELTE Klammern
    enthalten (`{\\f0\\froman Times New Roman;}`): das nicht-gierige Ende trifft die erste
    INNERE Klammer, der Rest der Tabelle bleibt stehen. Gemessen begann der Text danach mit
    „Symbol; Times New Roman; sans-serif; Courier;" — nicht suchbar, und jede Zeichenzahl
    verfaelscht. Verschachtelte Klammern sind mit regulaeren Ausdruecken grundsaetzlich
    nicht zu fassen; der Zaehler ist hier kein Luxus, sondern die einzige richtige Loesung.
    """
    import re as _re
    try:
        t = data.decode("cp1252", "replace")
    except Exception:                                     # noqa: BLE001
        return ""

    for gruppe in ("fonttbl", "colortbl", "stylesheet", "info", "listtable",
                   "listoverridetable", "generator", "pict", "themedata", "rsidtbl"):
        marke = "{" + chr(92) + gruppe
        i = t.find(marke)
        while i != -1:
            tiefe, j = 0, i
            while j < len(t):
                if t[j] == "{":
                    tiefe += 1
                elif t[j] == "}":
                    tiefe -= 1
                    if tiefe == 0:
                        break
                j += 1
            t = t[:i] + " " + t[j + 1:]
            i = t.find(marke)

    t = _re.sub(r"\{\\\*.*?\}", " ", t, flags=_re.S)       # Steuergruppen ganz weg
    t = _re.sub(r"\\'([0-9a-fA-F]{2})",
                lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), t)
    t = _re.sub(r"\\par[d]?\b", "\n", t)                   # Absaetze erhalten
    t = _re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", t)              # uebrige Steuerworte
    t = t.replace("{", " ").replace("}", " ")
    return _re.sub(r"[ \t]{2,}", " ", t).strip()


_STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _doc_text(data: bytes) -> str:
    """Word 97-2003 (.doc) → Text. OLE2-Container, Stueckliste, keine Bibliothek von der Stange.

    **Warum ueberhaupt.** `.doc` und `.xls` standen als „Binaerformat ohne sinnvolle Loesung"
    in `_KNOWN_NOEXTRACT`. Gemessen 2026-08-18 sind das 394 Dateien in 213 Vorgaengen, und
    die Stichprobe zeigt, was drinsteckt: „Stadtverwaltung Idar-Oberstein, Tiefbauamt,
    Leistungsbeschreibung, Baubeschreibung". Also nicht Beiwerk, sondern der Kern.

    **Warum von Hand und nicht mit einer Konvertierung.** LibreOffice oder antiword waeren
    ein Fremdprozess je Datei und auf dieser Maschine gar nicht vorhanden. `olefile` liest
    den Container, den Rest macht das Format selbst: Word legt den Text nicht am Stueck ab,
    sondern in einer **Stueckliste** (piece table) im Table-Stream. Jedes Stueck sagt, wo
    seine Zeichen liegen und ob sie als CP1252 (Bit 0x40000000 im `fc`) oder als UTF-16
    stehen. Wer das ignoriert und einfach im Datenstrom nach Text sucht, bekommt bei
    schnellgespeicherten Dokumenten die alten Fassungen mit dazu — und ein falsches Zitat
    ist schlimmer als ein fehlendes (Belegpflicht, s. `govisor/docextract.py`).
    """
    import io
    try:
        import olefile
    except ImportError:                                   # noqa: BLE001
        return ""
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
        if not ole.exists("WordDocument"):
            return ""
        wd = ole.openstream("WordDocument").read()
        # Bit 0x0200 der FIB-Flags sagt, WELCHER der beiden Table-Streams gilt. Den falschen
        # zu nehmen liefert Muell, der wie Text aussieht.
        tabelle = "1Table" if int.from_bytes(wd[0x0A:0x0C], "little") & 0x0200 else "0Table"
        if not ole.exists(tabelle):
            return ""
        tb = ole.openstream(tabelle).read()
        fc = int.from_bytes(wd[0x01A2:0x01A6], "little")
        lcb = int.from_bytes(wd[0x01A6:0x01AA], "little")
        clx = tb[fc:fc + lcb]
        i = 0
        while i < len(clx) and clx[i] == 0x01:             # optionale Prc-Bloecke ueberspringen
            i += 3 + int.from_bytes(clx[i+1:i+3], "little")
        if i >= len(clx) or clx[i] != 0x02:
            return ""
        pcdt = clx[i+5:i+5 + int.from_bytes(clx[i+1:i+5], "little")]
        n = (len(pcdt) - 4) // 12                          # (n+1) CPs a 4 B + n PCDs a 8 B
        cps = [int.from_bytes(pcdt[4*k:4*k+4], "little") for k in range(n + 1)]
        teile = []
        for k in range(n):
            pcd = pcdt[4*(n+1) + 8*k: 4*(n+1) + 8*k + 8]
            f = int.from_bytes(pcd[2:6], "little")
            zeichen = cps[k+1] - cps[k]
            if f & 0x40000000:
                start = (f & 0x3FFFFFFF) >> 1
                teile.append(wd[start:start + zeichen].decode("cp1252", "replace"))
            else:
                teile.append(wd[f:f + zeichen * 2].decode("utf-16-le", "replace"))
        # \x07 ist das Zellen-/Zeilenende in Word-Tabellen, \r der Absatz.
        t = "".join(teile).replace("\r", "\n").replace("\x07", "\n")
        return _STEUERZEICHEN.sub("", t)
    except Exception:                                      # noqa: BLE001
        return ""


def _xls_text(data: bytes) -> str:
    """Excel 95-2003 (.xls) → Zeilen als Text. In der Stichprobe: Leistungsverzeichnisse.

    Dasselbe Muster wie `_xlsx_text`: eine Zeile je Tabellenzeile, Zellen mit `|` getrennt,
    leere Zellen weg. Die Blattnamen bleiben als Ueberschrift stehen, weil sie in
    Vergabeunterlagen die Gliederung tragen („Leistungsverzeichnis", „Preisblatt").

    `xlrd` ab 2.0 kann kein `.xls` mehr (nur noch `.xlsx`), deshalb steht in
    `requirements.txt` ausdruecklich `xlrd<2`. Wer das beim naechsten Aufraeumen anhebt,
    schaltet 394 Dateien still wieder ab.
    """
    try:
        import xlrd
    except ImportError:                                    # noqa: BLE001
        return ""
    try:
        wb = xlrd.open_workbook(file_contents=data)
    except Exception:                                      # noqa: BLE001
        return ""
    aus = []
    for sh in wb.sheets():
        aus.append(f"\u2500\u2500 {sh.name} \u2500\u2500")
        for r in range(sh.nrows):
            zeile = [str(c.value).strip() for c in sh.row(r) if str(c.value).strip()]
            if zeile:
                aus.append(" | ".join(zeile))
    return "\n".join(aus)


def _aidf_text(data: bytes) -> str:
    """`.aidf` → das Leistungsverzeichnis darin. Ein ZIP, das sich als Einzeldatei ausgibt.

    Gemessen 2026-08-18 an einer Probe: die Datei ist ein ZIP mit vier Eintraegen, und
    ``data.lv`` ist ein XML-Leistungsverzeichnis des AI-AG-Formats (`<ai:lv …>`). 391 Dateien
    liefen als `unknown_type` durch, obwohl genau das drinsteht, wonach ein Bieter sucht.

    Bewusst NUR ``data.lv`` und ``metadata.xml``: ``lvm.aicatalog`` ist mit 415 KB der
    Abgleichkatalog des Programms (Standardtexte, nicht die Ausschreibung) und ``stylesheet.xsl``
    die Darstellung. Beide wuerden den Index aufblaehen und nichts beitragen.
    """
    import io
    import zipfile
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:                                      # noqa: BLE001
        return ""
    teile = []
    for name in z.namelist():
        if name.rsplit("/", 1)[-1] in ("data.lv", "metadata.xml"):
            try:
                teile.append(_html_text(z.read(name)))
            except Exception:                              # noqa: BLE001
                continue
    return "\n".join(t for t in teile if t)


_EXTRACT = {
    ".pdf": _pdf_text, ".docx": _docx_text, ".xlsx": _xlsx_text,
    ".htm": _html_text, ".html": _html_text, ".xml": _html_text,
    ".txt": _txt, ".csv": _txt,
    # `.docm` ist DOCX mit Makros — dieselbe Struktur, derselbe Extraktor (83 Dateien).
    ".docm": _docx_text, ".xlsm": _xlsx_text,
    ".rtf": _rtf_text, ".odt": _odt_text,
    # GAEB — der Parser lag seit Ticket 23 ungenutzt daneben, s. `_gaeb_text`.
    ".x83": _gaeb_text, ".x81": _gaeb_text, ".x86": _gaeb_text,
    ".d83": _gaeb_text, ".d81": _gaeb_text, ".p83": _gaeb_text, ".gaeb": _gaeb_text,
    # Alt-Office. Bis 2026-08-18 als „unsupported" gefuehrt: 394 Dateien in 213 Vorgaengen.
    ".doc": _doc_text, ".xls": _xls_text,
    # AI-AG-Vergabemanager (verbreitet auf den Landesportalen). Was Inhalt traegt, gemessen:
    #   .aidf   391 Dateien  ZIP mit dem XML-Leistungsverzeichnis      → eigener Leser
    #   .aiform 194 Dateien  das VHB-Angebotsschreiben mit Bindefrist  → XML-Text
    #   .aidoc  194 Dateien  Vergabenummer, Titel, Leistung            → XML-Text
    # Was KEINEN Inhalt traegt, steht in `_KNOWN_NOEXTRACT` — mit Beleg, warum.
    ".aidf": _aidf_text, ".aiform": _html_text, ".aidoc": _html_text,
}
# bekannt, aber ohne einfachen Extraktor → geflaggt, nicht ignoriert.
#
# `.doc`/`.xls` standen hier bis 2026-08-18 mit der Begruendung „Binaerformat, keine sinnvolle
# Loesung ohne Fremdprozess". Das stimmte fuer LibreOffice und antiword, nicht fuer den Weg,
# den `_doc_text`/`_xls_text` jetzt gehen: zwei kleine reine Python-Pakete (olefile, xlrd<2).
# Geblieben ist, was wirklich nichts hergibt: `.ppt` (Folien, im Vergabekontext Beiwerk),
# `.p7s` (Signatur, kein Inhalt), `.zip` (wird eine Ebene hoeher ausgepackt).
#
# DAZU, seit 2026-08-18, die grossen Posten aus `unknown_type` — jeder mit Blick in die Bytes
# entschieden, nicht nach der Endung geraten:
#
#   .asc   725  PGP-Schluesselbloecke („-----BEGIN PGP PUBLIC KEY BLOCK-----"). Der groesste
#               Einzelposten im ganzen `unknown_type` und der irrefuehrendste: er sieht nach
#               einem Austauschformat aus und ist die Verschluesselung des Portals.
#   .dwg   384  CAD-Zeichnung, .jpg 291 Foto: Bilder, kein Text.
#   .aidocdef 582  Formulardefinition des AI-AG-Systems. Ihr Text sind Pruefmeldungen
#               („Nicht alle Zeichen sind erlaubt"), nicht die Ausschreibung.
#   .xsl   194  Stylesheet zur Darstellung des LV, nicht das LV (das liegt im `.aidf`).
#   .din   106  39-Byte-Kopfzeile („VERSION$CHARACTER_SET 1$WE8MSWIN1252"), sonst nichts.
#   .db    100  `Thumbs.db` aus Windows-Ordnern.
#
# Der Unterschied ist keine Wortklauberei: `unknown_type` heisst „hier fehlt uns ein Parser"
# und ist eine Aufgabe, `unsupported` heisst „hier ist nichts zu holen" und ist erledigt.
_KNOWN_NOEXTRACT = {".ppt", ".p7s", ".zip", ".asc", ".dwg", ".jpg", ".jpeg",
                    ".aidocdef", ".xsl", ".din", ".db"}


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
            # BILDREINE PDF → OCR, und danach der Vokabeltest. Die Reihenfolge ist der
            # ganze Trick: die Zeichenzahl unterscheidet einen Lageplan nicht von einem
            # Leistungsverzeichnis (beide ~1.300–1.700), das Fachvokabular schon
            # (Plaene 0 von 5, Leistungsverzeichnisse 3 von 5 — gemessen 2026-08-15).
            if status == "image_only":
                erkannt = _ocr_pdf(data)
                if len(_FACH.findall(erkannt)) >= _OCR_MINDEST:
                    text, status = erkannt[:_MAX_TEXT], "ocr"
                elif erkannt.strip():
                    # Text da, aber ohne Substanz: Kartenbeschriftungen, Stempel,
                    # Erkennungsfehler. Gezaehlt statt verworfen — sonst sieht ein Plan
                    # aus wie eine Datei, die OCR gar nicht erreicht hat.
                    status = "ocr_ohne_inhalt"
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


# SPEICHERGRENZE JE ARBEITER — die einzige, die wirklich greift.
#
# Sie wird NICHT im Arbeiter gesetzt, sondern vom Elternprozess DURCHGESETZT: er misst den
# RSS jedes Arbeiterprozesses und beendet ihn mit SIGKILL, wenn er sie reisst. Das Archiv
# bekommt dann `status='speicher'` und ist gezaehlt.
#
# 2 GB × 4 Arbeiter = 8 GB Obergrenze auf einer 16-GB-Maschine, mit Reserve fuer den
# Elternprozess und das System. Wer die Arbeiterzahl hochsetzt, muss das mitrechnen — die
# beiden Zahlen gehoeren zusammen und sind einzeln sinnlos.
SPEICHER_JE_ARBEITER_GB = float(os.environ.get("GOVISOR_ARBEITER_GB", "2"))

# ═══ WARUM NICHT IM ARBEITER: ZWEI SICHERUNGEN GEBAUT, BEIDE GEMESSEN WIRKUNGSLOS ═══
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


# `_verarbeite_archiv` (Pool-Arbeiter) wurde am 2026-08-14 ersatzlos entfernt. Seine
# Aufgabe macht jetzt `govisor/docworker.py` als eigener Prozess — der Grund steht dort.
# Er hierzulassen hiesse, zwei Wege zur selben Sache zu haben, von denen einer den Rechner
# abstuerzen laesst.


def _rss_gb(pids) -> dict[int, float]:
    """RSS mehrerer Prozesse in GB — in EINEM `ps`-Aufruf, nicht einem je Prozess.

    Bei vier Arbeitern und zwei Messungen je Sekunde waeren das sonst acht Prozessstarts
    pro Sekunde, nur um Zahlen abzulesen. `ps` liefert Kilobytes.
    """
    if not pids:
        return {}
    import subprocess
    try:
        aus = subprocess.run(["ps", "-o", "pid=,rss=", "-p", ",".join(str(x) for x in pids)],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:                                     # noqa: BLE001
        return {}                 # keine Messung ist kein Grund, den Lauf abzubrechen
    raus: dict[int, float] = {}
    for zeile in aus.splitlines():
        teile = zeile.split()
        if len(teile) == 2:
            try:
                raus[int(teile[0])] = int(teile[1]) / 1024 ** 2
            except ValueError:
                pass
    return raus


def _fehlzeile(notice_id: str, archiv: str, status: str, hinweis: str = "") -> dict:
    """Ein gescheitertes Archiv wird MARKIERT, nicht verschwiegen — sonst sieht ein Lauf,
    der die Haelfte abgeschossen hat, genauso aus wie einer, der alles geschafft hat."""
    return {"notice_id": notice_id, "archive": archiv, "file": "", "filetype": "",
            "n_chars": 0, "status": status, "text": hinweis}


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
    # DASSELBE Schema wie der Arbeiter (`_schema()` oben). Nicht hier neu aufschreiben:
    # eine Abweichung faellt erst beim Zusammenfuehren auf, also nach der ganzen Arbeit.
    schema = _schema()
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
        # ── EIN PROZESS JE ARCHIV, vom Elternprozess beaufsichtigt ────────────────────
        #
        # Ersetzt am 2026-08-14 einen `mp.Pool`. Der Grund steht ausfuehrlich in
        # `govisor/docworker.py`; kurz: Speicher laesst sich INNERHALB eines Prozesses nicht
        # verlaesslich begrenzen (drei Versuche, alle gemessen wirkungslos), und die einzige
        # Instanz, die eine Grenze durchsetzen kann, ist das Betriebssystem.
        #
        # Ein Pool taugt dafuer nicht: seine Arbeiter sind langlebig, und einen davon hart
        # zu beenden bringt `mp.Pool` zum Haengen. Eigene kurzlebige Prozesse darf man
        # toeten — der Verlust ist EIN Archiv, und das wird als Zeile vermerkt.
        #
        # Der zweite Gewinn ist genauso wichtig: der Arbeiter schreibt sein Ergebnis SELBST
        # als Parquet-Bruchstueck. Der Elternprozess reicht es als Arrow-Tabelle durch, ohne
        # den Volltext je als Python-Objekt zu halten. Vorher pufferte er 200 Archive à bis
        # zu 30 MB Text — bis zu 6 GB, die niemand mitgerechnet hatte.
        import itertools
        import subprocess
        import sys as _sys

        bruch_dir = _db.temp_verzeichnis() / "docidx"
        bruch_dir.mkdir(parents=True, exist_ok=True)
        for rest in bruch_dir.glob("*.parquet"):
            rest.unlink()                 # Reste eines abgebrochenen Laufs
        zaehler = itertools.count()
        warteschlange = list(auftraege)
        laufend: dict[int, list] = {}     # pid → [proc, (notice_id, pfad), bruchstueck, t0]
        getoetet: dict[str, int] = {}

        def _uebernehmen(zeilen_tabelle=None, zeilen=None):
            """Ergebnis eines Arbeiters in den Schreiber — Tabelle direkt, Zeilen gepuffert."""
            nonlocal n_zeilen
            if zeilen_tabelle is not None:
                schreiber.write_table(zeilen_tabelle)
                n_zeilen += zeilen_tabelle.num_rows
            if zeilen:
                puffer.extend(zeilen)
                n_zeilen += len(zeilen)

        while warteschlange or laufend:
            while warteschlange and len(laufend) < arbeiter:
                notice_id, pfad = warteschlange.pop(0)
                bruch = bruch_dir / f"t{next(zaehler)}.parquet"
                proc = subprocess.Popen(
                    [_sys.executable, "-m", "govisor.docworker", notice_id, pfad, str(bruch)],
                    cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                laufend[proc.pid] = [proc, (notice_id, pfad), bruch, _t.monotonic()]

            _t.sleep(0.4)
            speicher = _rss_gb(list(laufend))

            for pid in list(laufend):
                proc, (nid, pfad), bruch, t0 = laufend[pid]
                lebt = proc.poll() is None
                if lebt:
                    # DIE GRENZE, DIE WIRKLICH GREIFT. Kein Signal, kein rlimit — SIGKILL.
                    grund = None
                    if speicher.get(pid, 0) > SPEICHER_JE_ARBEITER_GB:
                        grund = "speicher"
                    elif _t.monotonic() - t0 > ZEIT_JE_ARCHIV:
                        grund = "zeitlimit"
                    if not grund:
                        continue
                    proc.kill()
                    try:
                        proc.wait(timeout=10)
                    except Exception:                     # noqa: BLE001
                        pass
                    getoetet[grund] = getoetet.get(grund, 0) + 1
                    zeile = _fehlzeile(nid, Path(pfad).name, grund,
                                       f"{speicher.get(pid, 0):.1f} GB" if grund == "speicher"
                                       else f"{ZEIT_JE_ARCHIV}s")
                    status_counts[grund] = status_counts.get(grund, 0) + 1
                    _uebernehmen(zeilen=[zeile])
                    bruch.unlink(missing_ok=True)
                    del laufend[pid]
                    fertig += 1
                    continue

                # Fertig — Bruchstueck einsammeln.
                del laufend[pid]
                fertig += 1
                if bruch.exists():
                    try:
                        t = pq.read_table(bruch).select(schema.names)
                        for st, n in zip(t.column("status").to_pylist(),
                                         t.column("n_chars").to_pylist()):
                            status_counts[st] = status_counts.get(st, 0) + 1
                            total_chars += n or 0
                        _uebernehmen(zeilen_tabelle=t)
                    except Exception:                     # noqa: BLE001
                        status_counts["fehler"] = status_counts.get("fehler", 0) + 1
                        _uebernehmen(zeilen=[_fehlzeile(nid, Path(pfad).name, "fehler",
                                                        "Bruchstueck unlesbar")])
                    bruch.unlink(missing_ok=True)
                else:
                    # Kein Bruchstueck und nicht getoetet: der Arbeiter ist selbst gestorben
                    # (z. B. vom System wegen Speichers). Auch das wird vermerkt.
                    status_counts["fehler"] = status_counts.get("fehler", 0) + 1
                    _uebernehmen(zeilen=[_fehlzeile(nid, Path(pfad).name, "fehler",
                                                    f"Arbeiter endete mit {proc.returncode}")])

                if len(puffer) >= BLOCK:
                    _wegschreiben(puffer)
                if fertig % 100 == 0 or fertig == len(auftraege):
                    print(f"  {fertig}/{len(auftraege)} Archive"
                          + (f"  (getoetet: {getoetet})" if getoetet else ""), flush=True)

            if zeit_budget is not None and _t.monotonic() - start > zeit_budget:
                abgeschnitten = len(warteschlange) + len(laufend)
                for pid in list(laufend):
                    laufend[pid][0].kill()
                    laufend[pid][2].unlink(missing_ok=True)
                laufend.clear()
                warteschlange.clear()
                break

        _wegschreiben(puffer)
    finally:
        schreiber.close()
    tmp.replace(out)

    if abgeschnitten:
        print(f"  ⏳ Zeitbudget ({zeit_budget}s) erreicht — {abgeschnitten} Archive bleiben "
              f"fuer den naechsten Lauf (dringendste zuerst abgearbeitet)", flush=True)
    # STAND HINTERLASSEN. Ohne diese Datei ist „wie gross ist der Rueckstand?" nur ueber
    # eine Parquet-Abfrage zu beantworten — und damit nicht aus dem Frontend heraus, das
    # kein DuckDB hat. Die Datei ist klein, wird bei jedem Lauf neu geschrieben und ist die
    # einzige Stelle, an der steht, was der Index WIRKLICH geschafft hat.
    try:
        import json as _json
        (root / "_index_stand.json").write_text(_json.dumps({
            "stand": _dt.datetime.now().isoformat(timespec="seconds"),
            "vorgaenge": n_notices,
            "archive_bearbeitet": fertig,
            "archive_uebersprungen": uebersprungen,
            "zeilen": n_zeilen,
            "zeichen": total_chars,
            "status": status_counts,
            "offen": abgeschnitten,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass          # ein fehlender Stand ist ein blindes Dashboard, kein kaputter Index

    print(f"docpipe {country}: {n_notices} Vorgänge, {n_zeilen} Zeilen im Index, "
          f"{total_chars/1e6:.1f} Mio. Zeichen neu → {out.name}")
    print("  Status: " + " | ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    return {"notices": n_notices, "files": n_zeilen, "chars": total_chars,
            "status": status_counts, "offen": abgeschnitten}

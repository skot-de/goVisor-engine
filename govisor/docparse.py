"""Parser-Schiene für strukturierte Vergabeunterlagen (Ticket #23, §6.2).

Wo ein Format strukturiert vorliegt, ist der LLM überflüssig (und teuer): GAEB-LV (84 % im
Bau!), ausfüllbare PDF-Formulare und Excel-Preisblätter werden **regelbasiert** geparst.
Ausgabe ist strukturierte Fakten (Positionen/Felder/Tabellenstruktur) — bei Preisblättern
bewusst **ohne Werte** (§6.2: „keine Werte eintragen"). Wo ein Parser greift, entfällt die
LLM-Extraktion für dieses Dokument.

Zusätzlich der **Inhalts-Klassifikator** (§6.1, Schritt 2) für die 31 % Dateien, die der
Dateiname nicht trifft.
"""
from __future__ import annotations

import io
import re

# Endungen, für die ein Parser existiert (→ keine LLM-Extraktion).
GAEB_EXTS = frozenset({".x83", ".x81", ".x86", ".d83", ".d81", ".p83", ".gaeb"})
XLSX_EXTS = frozenset({".xlsx", ".xlsm"})


def _localname(tag) -> str:
    """XML-Tag ohne Namensraum. Nimmt AUCH Nicht-Strings entgegen.

    lxml liefert fuer Kommentare und Processing-Instructions als `.tag` eine FUNKTION,
    keinen String — `root.iter()` gibt diese Knoten mit aus. Ohne diesen Guard warf der
    GAEB-Parser dort `TypeError: argument of type 'cython_function_or_method' is not a
    container`. Aufgefallen erst beim Lauf ueber echte Leistungsverzeichnisse; beim
    Einzel-Upload hatte es nie jemanden getroffen.
    """
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_gaeb(data: bytes) -> dict | None:
    """GAEB DA XML (X8x) → Positionen (Ordnungszahl, Menge, Einheit, Kurztext).

    Namespace-agnostisch über local-name (deckt DA83 3.2/3.3 ab). Gibt None bei nicht-XML
    (alte D8x-Flat-Formate werden hier nicht geparst → fallen auf die LLM-/Text-Schiene zurück).
    """
    try:
        from lxml import etree
        root = etree.fromstring(data)
    except Exception:
        return None
    positions = []
    for el in root.iter():
        if _localname(el.tag) != "Item":
            continue
        rno = el.get("RNoPart") or el.get("RNo") or ""
        qty = qu = short = ""
        for ch in el.iter():
            ln = _localname(ch.tag)
            t = (ch.text or "").strip()
            if ln == "Qty" and not qty:
                qty = t
            elif ln == "QU" and not qu:
                qu = t
            elif ln in ("OutlineText", "TextOutlTxt", "span") and t and not short:
                short = t
        if not short:                       # Fallback: erster Text unter Description
            desc = next((c for c in el.iter() if _localname(c.tag) == "Description"), None)
            if desc is not None:
                short = " ".join(x.strip() for x in desc.itertext() if x.strip())[:200]
        if rno or qty or short:
            positions.append({"rno": rno, "qty": qty, "unit": qu, "text": short[:300]})
    if not positions:
        return None
    return {"parser": "gaeb", "positions": positions, "n_positions": len(positions)}


def parse_pdf_fields(data: bytes) -> dict | None:
    """Ausfüllbares PDF → Formularfelder (Name, Typ, Pflichtkennzeichen). None ohne Felder."""
    try:
        import pypdf
        r = pypdf.PdfReader(io.BytesIO(data))
        fields = r.get_fields()
    except Exception:
        return None
    if not fields:
        return None
    out = []
    for name, f in fields.items():
        try:
            ff = f.get("/Ff")
            required = bool(int(ff) & 2) if ff is not None else False   # Bit 2 = Required
        except Exception:
            required = False
        out.append({"name": str(name), "type": str(f.get("/FT", "")).lstrip("/") or "text",
                    "required": required})
    return {"parser": "pdf_fields", "fields": out, "n_fields": len(out)}


def parse_xlsx(data: bytes) -> dict | None:
    """XLSX → Tabellenstruktur (Blätter, Spaltenüberschriften, Positionszahl). KEINE Werte (§6.2)."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        return None
    sheets = []
    for ws in wb.worksheets:
        # ws.max_row ist im read_only-Modus unzuverlässig (deklarierte Dimension, oft 1.048.576).
        # Echte Positionszahl = nicht-leere Datenzeilen, gezählt beim Iterieren (gedeckelt).
        header, n_rows = [], 0
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            cells = [c for c in row if c is not None and str(c).strip()]
            if i == 0:
                header = [str(c).strip() for c in cells][:30]
                continue
            if cells:
                n_rows += 1
            if i > 20000:                                # Deckel gegen pathologische Blätter
                break
        sheets.append({"name": ws.title, "columns": header, "n_positions": n_rows})
    wb.close()
    if not sheets:
        return None
    return {"parser": "xlsx", "sheets": sheets}


def parse(name: str, ext: str, data: bytes) -> dict | None:
    """Dispatcher: strukturierte Ausgabe je Format, sonst None (→ LLM-/Text-Schiene)."""
    e = (ext or "").lower()
    if e in GAEB_EXTS:
        return parse_gaeb(data)
    if e in XLSX_EXTS:
        return parse_xlsx(data)
    if e == ".pdf":
        return parse_pdf_fields(data)
    return None


# ── Inhalts-Klassifikator (§6.1, Schritt 2) — für die 31 %, die der Dateiname nicht trifft ──
# Reihenfolge = Vorrang; auf die Extraktions-Doktypen abgebildet. Sucht in den ersten Zeichen.
_CONTENT_RULES: tuple[tuple[str, str], ...] = (
    ("zuschlagskriterien",    r"zuschlagskriterien|wertungskriterien|bewertungsmatrix|"
                              r"wertung.{0,20}(erfolgt|nach)|gewichtung.{0,20}%"),
    ("eignung",               r"eignungskriterien|eignungsnachweise|mindestumsatz|"
                              r"vergleichbare referenzen|präqualifikation|ausschlussgründe"),
    ("aufforderung",          r"aufforderung zur angebotsabgabe|angebotsfrist|"
                              r"angebote sind bis|einzureichen bis"),
    ("vertrag",               r"vertragsbedingungen|vertragsstrafe|gewährleistung|"
                              r"§\s*\d+\s+(haftung|kündigung|laufzeit)"),
    ("leistungsbeschreibung", r"leistungsbeschreibung|leistungsverzeichnis|"
                              r"technische anforderungen|leistungsumfang"),
)
_CONTENT_COMPILED = tuple((dt, re.compile(pat, re.I)) for dt, pat in _CONTENT_RULES)


def classify_content(text: str, sample: int = 4000) -> str:
    """Doktyp aus einer Inhaltsprobe (§6.1, Schritt 2). ``sonstiges`` wenn nichts greift."""
    head = (text or "")[:sample]
    for doctype, rx in _CONTENT_COMPILED:
        if rx.search(head):
            return doctype
    return "sonstiges"

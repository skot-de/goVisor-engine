"""Ticket #23 Phase 2 — Parser-Schiene (§6.2): GAEB / XLSX / PDF-Formfelder + Inhalts-Klassifikator.

Synthetische Eingaben (korpus-unabhängig). Belegt: wo ein Parser greift, gibt es strukturierte
Fakten ohne LLM; Preisblätter tragen KEINE Werte (nur Struktur).
"""
import io

from govisor import docparse


_X83 = """<?xml version="1.0" encoding="UTF-8"?>
<GAEB xmlns="http://www.gaeb.de/GAEB_DA_XML/DA83/3.3">
 <Award><BoQ><BoQBody><Itemlist>
  <Item ID="I1" RNoPart="1">
    <Qty>4.000</Qty><QU>St</QU>
    <Description><CompleteText><OutlineText><OutlTxt><TextOutlTxt>
      <span>Brandschutztür T30</span></TextOutlTxt></OutlTxt></OutlineText></CompleteText></Description>
  </Item>
  <Item ID="I2" RNoPart="2">
    <Qty>120.500</Qty><QU>m2</QU>
    <Description><CompleteText><OutlineText><OutlTxt><TextOutlTxt>
      <span>Trockenbauwand einlagig</span></TextOutlTxt></OutlTxt></OutlineText></CompleteText></Description>
  </Item>
 </Itemlist></BoQBody></BoQ></Award>
</GAEB>""".encode("utf-8")


def test_parse_gaeb_x83():
    r = docparse.parse("LV.x83", ".x83", _X83)
    assert r and r["parser"] == "gaeb" and r["n_positions"] == 2
    p0 = r["positions"][0]
    assert p0["rno"] == "1" and p0["qty"] == "4.000" and p0["unit"] == "St"
    assert "Brandschutztür" in p0["text"]


def test_parse_gaeb_rejects_nonxml():
    assert docparse.parse_gaeb(b"das ist kein xml") is None


def test_parse_xlsx_structure_no_values():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Preisblatt"
    ws.append(["Pos", "Bezeichnung", "Menge", "EP", "GP"])
    for i in range(1, 6):
        ws.append([i, f"Leistung {i}", 10 * i, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    r = docparse.parse("Preisblatt.xlsx", ".xlsx", buf.getvalue())
    assert r and r["parser"] == "xlsx"
    sh = r["sheets"][0]
    assert sh["name"] == "Preisblatt"
    assert sh["columns"][:3] == ["Pos", "Bezeichnung", "Menge"]
    assert sh["n_positions"] == 5                       # 5 Datenzeilen, NICHT die 1.048.576-Dimension
    # keine Werte im Ergebnis (nur Struktur)
    assert "10" not in str(sh) and "Leistung 1" not in str(sh)


def test_parse_pdf_fields_none_on_garbage():
    assert docparse.parse_pdf_fields(b"%PDF-1.4 kaputt") is None
    assert docparse.parse("x.pdf", ".pdf", b"nope") is None


def test_dispatcher_routes_by_ext():
    assert docparse.parse("a.docx", ".docx", b"x") is None      # kein Parser → LLM/Text-Schiene
    assert docparse.parse("lv.x83", ".x83", _X83)["parser"] == "gaeb"


def test_classify_content():
    """Die Inhaltsprobe wertet nach Punkten und schweigt im Zweifel.

    ⚠ Bis 2026-08-21 nahm sie die erste passende Regel — ein einziges Stichwort genuegte.
    Gegen eine Rueckhaltestichprobe gehalten lag sie damit in ueber der Haelfte der Faelle
    daneben (46,1 %). Ein EINZELNER Satz reicht seither nicht mehr: die Schwelle verlangt
    mehrere zusammenpassende Merkmale. Das ist der Preis fuer 86 % Genauigkeit und
    beabsichtigt — ein falscher Doktyp schickt den Text an die falsche Extraktionsaufgabe
    und meldet einen priorisierten Typ als vorhanden, wo eine echte Luecke ist.
    """
    zuschlag = ("Zuschlagskriterien und ihre Gewichtung 40 %. Die Bewertung erfolgt nach "
                "Bewertungsmatrix; die Hoechstpunktzahl erhaelt das Angebot mit dem "
                "niedrigsten Angebotspreis, dazwischen lineare Interpolation.")
    assert docparse.classify_content(zuschlag) == "zuschlagskriterien"

    eignung = ("Bewerbungsbedingungen. Nachzuweisen sind vergleichbare Referenzen der "
               "letzten drei Jahre sowie ein Mindestumsatz. Die Eignungsnachweise sind mit "
               "den Vordrucken der Vergabestelle einzureichen.")
    assert docparse.classify_content(eignung) == "eignung"

    preis = ("Aufgliederung der Einheitspreise. Mittellohn einschliesslich Lohnzulagen, "
             "Soziallöhne und Lohnnebenkosten ergeben den Verrechnungslohn.")
    assert docparse.classify_content(preis) == "preisblatt"

    assert docparse.classify_content("Allgemeines Blabla ohne Merkmale") == "sonstiges"
    # Ein einzelnes Stichwort ist kein Urteil.
    assert docparse.classify_content("Angebote sind bis 15.08.2026 einzureichen") == "sonstiges"


def test_inhaltsprobe_greift_erst_wenn_der_name_schweigt():
    """Der Name entscheidet, solange er etwas hergibt — er ist genauer und kostet nichts."""
    from govisor import doctypes
    lb = "Leistungsverzeichnis, Ordnungszahl und Langtext je Position, Menge Einheit."
    assert doctypes.classify("Vertragsbedingungen.pdf", lb) == "vertrag"
    assert doctypes.classify("Anlage 3.pdf", lb) == "leistungsbeschreibung"
    assert doctypes.classify("Anlage 3.pdf") == "sonstiges"


def test_nachweis_count():
    """Ticket #23 §B.2 — Nachweisdichte: distinkte Nachweis-Arten + Formblätter, Wiederholung zählt 1×."""
    from govisor import docsignals
    t = ("Einzureichen: Eigenerklärung zur Eignung, Nachweis der Berufshaftpflicht, Referenzen der "
         "letzten Jahre, Formblatt 124, Formblatt 234, Zertifikat ISO 9001, Erklärung Art. 5k. "
         "Nochmals: Eigenerklärung beifügen.")  # 'Eigenerklärung' 2× → zählt 1×
    n = docsignals.nachweis_count(t)
    assert n >= 6, n                                   # eigenerkl+haftpflicht+referenz+iso+5k + 2 Formblätter
    assert docsignals.nachweis_count("") == 0
    assert docsignals.nachweis_count("Allgemeiner Text ohne Nachweise.") == 0

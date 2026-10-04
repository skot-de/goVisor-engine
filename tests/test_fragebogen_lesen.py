"""Fragebogen aus XLSX und PDF lesen — an echten Dateien geprueft.

⚠ **Warum diese Suite Node startet.** Der Leser liegt in TypeScript
(`web/lib/fragebogenLesen.ts`), weil er in der Next-Route laeuft. Ihn in Python nachzubilden,
um ihn zu testen, haette eine zweite Fassung erzeugt — und damit genau das Problem, das bei
`blockcrypto` schon besteht. Stattdessen erzeugt dieser Test **echte Dateien** (openpyxl,
reportlab) und laesst den **echten Leser** in Node darauf los (Node 23+ laedt TypeScript direkt).

Damit ist belegt, was sonst Behauptung bliebe: dass eine von Excel geschriebene Datei mit
`sharedStrings` ankommt, dass eine Tabellenzeile zu EINER Textzeile wird (sonst trennt sich die
Fragennummer von ihrer Frage), und dass ein Scan-PDF eine verstaendliche Absage bekommt statt
eines leeren Ergebnisses.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"

node_fehlt = pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")
openpyxl = pytest.importorskip("openpyxl") if shutil.which("node") else None


def _lesen(pfad: pathlib.Path) -> dict:
    """Laesst `textAusDatei` in Node auf die Datei los und gibt das Ergebnis zurueck."""
    skript = (
        "const {readFileSync} = await import('node:fs');"
        "const {textAusDatei, NichtLesbar} = await import('./lib/fragebogenLesen.ts');"
        "const p = process.argv[process.argv.length - 1];"
        "const b = new Uint8Array(readFileSync(p));"
        "try { process.stdout.write(JSON.stringify(await textAusDatei(b, p))); }"
        "catch (e) { process.stdout.write(JSON.stringify("
        "  {fehler: e.message, art: e instanceof NichtLesbar ? 'nicht_lesbar' : 'anders'})); }"
    )
    p = subprocess.run(["node", "--input-type=module", "-e", skript, "--", str(pfad)],
                       cwd=WEB, capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"node brach ab: {p.stderr.strip()[-500:]}")
    return json.loads(p.stdout.strip())


# ── XLSX ─────────────────────────────────────────────────────────────────────────────────────

def _xlsx(tmp_path, zeilen) -> pathlib.Path:
    import openpyxl as ox
    wb = ox.Workbook()
    ws = wb.active
    for z in zeilen:
        ws.append(z)
    ziel = tmp_path / "fragebogen.xlsx"
    wb.save(ziel)
    return ziel


@node_fehlt
def test_xlsx_zeile_bleibt_eine_zeile(tmp_path):
    """Die Nummer steht in einer Spalte, die Frage in der naechsten. Beides muss zusammenbleiben.

    Wuerde je Zelle eine Textzeile entstehen, trennte sich "1." von seiner Frage, und aus einer
    Frage wuerden zwei Fragmente.
    """
    datei = _xlsx(tmp_path, [
        ["Nr.", "Frage", "Antwort"],
        ["1.", "Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.", ""],
        ["2.3", "Welche Referenzen koennen Sie vorweisen?", ""],
    ])
    d = _lesen(datei)
    assert d.get("art") == "xlsx", d
    zeilen = d["text"].splitlines()
    assert "1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem." in zeilen, zeilen
    assert "2.3 Welche Referenzen koennen Sie vorweisen?" in zeilen, zeilen


@node_fehlt
def test_xlsx_umlaute_und_zahlen(tmp_path):
    datei = _xlsx(tmp_path, [["1.", "Verfügen Sie über eine Bürgschaft über 100000 €?"],
                             ["2.", "Mindestumsatz", 250000]])
    d = _lesen(datei)
    assert "Verfügen Sie über eine Bürgschaft über 100000 €?" in d["text"], d["text"]
    assert "250000" in d["text"], d["text"]


@node_fehlt
def test_xlsx_ohne_text_wird_benannt(tmp_path):
    import openpyxl as ox
    wb = ox.Workbook()
    ziel = tmp_path / "leer.xlsx"
    wb.save(ziel)
    d = _lesen(ziel)
    assert d.get("art") == "nicht_lesbar", d
    assert "kein Text" in d["fehler"], d


@node_fehlt
def test_altes_excel_format_wird_ehrlich_abgewiesen(tmp_path):
    """Eine .xls ist kein ZIP. Die Absage muss das sagen, nicht 'konnte nicht geoeffnet werden'."""
    ziel = tmp_path / "alt.xls"
    ziel.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 200)       # OLE2-Kennung
    d = _lesen(ziel)
    assert d.get("art") == "nicht_lesbar", d
    assert ".xlsx" in d["fehler"], d


# ── PDF ──────────────────────────────────────────────────────────────────────────────────────

def _pdf(tmp_path, zeilen) -> pathlib.Path:
    reportlab = pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    ziel = tmp_path / "fragebogen.pdf"
    c = canvas.Canvas(str(ziel), pagesize=A4)
    y = 780
    for z in zeilen:
        c.drawString(60, y, z)
        y -= 24
    c.save()
    return ziel


@node_fehlt
def test_pdf_zeilen_bleiben_zeilen(tmp_path):
    """pdf.js liefert Textstuecke, keine Zeilen. Ohne Zeilenbildung steht der Bogen in einer Zeile."""
    datei = _pdf(tmp_path, [
        "1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.",
        "2. Welche Referenzen koennen Sie vorweisen?",
        "3. Verfuegen Sie ueber eine Berufshaftpflichtversicherung?",
    ])
    d = _lesen(datei)
    assert d.get("art") == "pdf", d
    zeilen = [z for z in d["text"].splitlines() if z.strip()]
    assert len(zeilen) >= 3, zeilen
    assert zeilen[0].startswith("1. Bitte beschreiben"), zeilen
    assert any("Referenzen" in z for z in zeilen), zeilen


@node_fehlt
def test_scan_pdf_bekommt_eine_verstaendliche_absage(tmp_path):
    """Ein Bild-PDF ohne Text ist der haeufige Fall und darf nicht wie ein Nutzerfehler klingen."""
    reportlab = pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    ziel = tmp_path / "scan.pdf"
    c = canvas.Canvas(str(ziel), pagesize=A4)
    c.rect(60, 600, 400, 160, fill=1)        # eine Flaeche, kein Text
    c.save()
    d = _lesen(ziel)
    assert d.get("art") == "nicht_lesbar", d
    assert "Scan" in d["fehler"], d


# ── Rahmenbedingungen ────────────────────────────────────────────────────────────────────────

@node_fehlt
def test_leere_datei(tmp_path):
    ziel = tmp_path / "leer.txt"
    ziel.write_bytes(b"")
    d = _lesen(ziel)
    assert d.get("art") == "nicht_lesbar" and "leer" in d["fehler"], d


@node_fehlt
def test_unbekannte_endung_wird_benannt(tmp_path):
    ziel = tmp_path / "bogen.rtf"
    ziel.write_text("1. Bitte beschreiben Sie etwas.")
    d = _lesen(ziel)
    assert d.get("art") == "nicht_lesbar" and ".rtf" in d["fehler"], d


@node_fehlt
def test_text_wird_durchgereicht(tmp_path):
    ziel = tmp_path / "bogen.txt"
    ziel.write_text("1. Bitte beschreiben Sie Ihr Qualitaetsmanagement.\n", encoding="utf-8")
    d = _lesen(ziel)
    assert d.get("art") == "text" and "Qualitaetsmanagement" in d["text"], d


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

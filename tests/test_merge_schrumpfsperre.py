"""Wache: `entity_merge_anwenden.py` darf die Karte nicht stillschweigend schrumpfen.

Der Lauf ist NICHT wiederholbar: `paare_fuer` joint die Kandidaten gegen `entities.parquet`,
und dort stehen die Entitaeten NACH Anwendung der bestehenden Karte. Was eine fruehere Karte
verschmolzen hat, existiert als `entity_b` nicht mehr. Gemessen 2026-10-02: 10.847 Kandidaten,
davon 4.750 mit noch existierendem `entity_b`. Ein zweiter Lauf schreibt deshalb eine kleinere
Karte, und `to_parquet` ueberschreibt — am 2026-10-02 waeren das 9.991 geloeschte
Verschmelzungen gewesen.

⚠ Geprueft wird der RUMPF OHNE Kommentare und Docstrings. Sonst schlaegt die Pruefung an der
Begruendung an, die dieselben Woerter nennt (s. memory waechter-messen-prosa-statt-code).
"""
import ast
import pathlib

SKRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "entity_merge_anwenden.py"


def _rumpf_ohne_doku(pfad: pathlib.Path) -> str:
    """Quelltext ohne Kommentare und ohne Docstrings."""
    quelle = pfad.read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(
        zeile.split("#", 1)[0] if "#" in zeile and not _in_zeichenkette(zeile) else zeile
        for zeile in quelle.splitlines()
    )
    baum = ast.parse(quelle)
    doks = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(knoten, clean=False)
            if d:
                doks.add(d)
    for d in doks:
        ohne_kommentar = ohne_kommentar.replace(d, "")
    return ohne_kommentar


def _in_zeichenkette(zeile: str) -> bool:
    """Grobe Sicherung: '#' innerhalb von Anfuehrungszeichen nicht als Kommentar lesen."""
    vor = zeile.split("#", 1)[0]
    return vor.count('"') % 2 == 1 or vor.count("'") % 2 == 1


def test_schrumpfsperre_sitzt_vor_dem_schreiben():
    rumpf = _rumpf_ohne_doku(SKRIPT)
    assert "to_parquet(ZIEL" in rumpf, "Schreibstelle nicht gefunden — Skript umgebaut?"
    schreiben = rumpf.index("to_parquet(ZIEL")
    davor = rumpf[:schreiben]
    assert "len(karte) < _vorher" in davor, \
        "kein Groessenvergleich vor dem Schreiben — die Karte kann stillschweigend schrumpfen"
    assert "return 1" in davor, \
        "der Vergleich bricht nicht ab (kein `return 1` vor dem Schreiben)"


def test_sperre_hat_einen_bewussten_ausweg():
    rumpf = _rumpf_ohne_doku(SKRIPT)
    assert "schrumpfen_erlauben" in rumpf, \
        "kein Schalter, um die Sperre bewusst zu uebergehen"


def test_selbstprobe_die_pruefung_faellt_ohne_die_sperre():
    """Erzwingt den Fund: ohne den Vergleich MUSS die erste Pruefung rot werden."""
    rumpf = _rumpf_ohne_doku(SKRIPT)
    verstuemmelt = rumpf.replace("len(karte) < _vorher", "False")
    schreiben = verstuemmelt.index("to_parquet(ZIEL")
    assert "len(karte) < _vorher" not in verstuemmelt[:schreiben], \
        "SELBSTPROBE: die Pruefung bemerkt das Entfernen des Vergleichs nicht — sie ist ein No-op"

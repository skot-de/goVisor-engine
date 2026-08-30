"""Der Volltext-Export — der Lauf, der am 2026-08-29 den Rechner lahmgelegt hat.

Der Dokument-Arbeiter ruft ihn alle zehn Minuten auf. Gemessen an dem Tag:

    `SELECT … FROM read_parquet(…)` + `.fetchall()`  →  **14 GB** Speicher
    817 MB Parquet, 16 GB Maschine, alle zehn Minuten
    geschriebene Dateien in einer ganzen Stunde: 0

Zwei Dinge waren falsch, und beide sind hier festgehalten: er lief, obwohl es nichts zu
tun gab, und er las alles auf einmal, obwohl die Zeilen eines Vorgangs beieinanderliegen.
"""
import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _modul(tmp_path, monkeypatch):
    """`scripts/export_doc_text.py` laden und auf ein Spielzeug-Verzeichnis umbiegen."""
    spec = importlib.util.spec_from_file_location(
        "edt", ROOT / "scripts" / "export_doc_text.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "SRC", tmp_path / "doc_text.parquet")
    monkeypatch.setattr(m, "JE_VORGANG", tmp_path / "doc-text")
    monkeypatch.setattr(m, "INDEX", tmp_path / "doc-text-index.json")
    monkeypatch.setattr(m, "ALT", tmp_path / "doc-text.json")
    monkeypatch.setattr(m, "STAND", tmp_path / ".stand.json")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    return m


def _quelle(pfad: Path, zeilen):
    """Eine Parquet-Datei im Format von `index-docs` — so, wie sie wirklich aussieht."""
    con = duckdb.connect()
    con.execute("CREATE TABLE t (notice_id VARCHAR, file VARCHAR, filetype VARCHAR, "
                "text VARCHAR, status VARCHAR)")
    for z in zeilen:
        con.execute("INSERT INTO t VALUES (?, ?, ?, ?, ?)", list(z))
    con.execute(f"COPY t TO '{pfad.as_posix()}' (FORMAT PARQUET)")


def test_unveraenderte_quelle_wird_uebersprungen(tmp_path, monkeypatch, capsys):
    """Der teure Lauf darf nur laufen, wenn es etwas zu tun gibt.

    Die Quelle schreibt ausschliesslich `index-docs`. Ändert sie sich nicht, kann sich das
    Ergebnis nicht ändern — dann genügt ein Blick auf Zeitstempel und Größe. Vorher lief
    jedes Mal der volle Durchgang: gemessen 81 Sekunden und Gigabytes, für null
    geschriebene Dateien.
    """
    m = _modul(tmp_path, monkeypatch)
    _quelle(m.SRC, [("a_2026", "lv.pdf", "pdf", "Leistungsverzeichnis Text", "ok")])

    assert m.main([]) == 0
    erst = capsys.readouterr().out
    assert "1 Vorgänge" in erst, erst

    # Zweiter Lauf, nichts geändert → gar nicht erst anfangen.
    assert m.main([]) == 0
    zweit = capsys.readouterr().out
    assert "unveraendert" in zweit, zweit

    # ⚠ Aber `--erzwingen` muss trotzdem durchlaufen — sonst gäbe es keinen Weg zurück,
    # wenn jemand die Scherben von Hand löscht.
    assert m.main(["--erzwingen"]) == 0
    assert "1 Vorgänge" in capsys.readouterr().out


def test_geaenderte_quelle_laeuft_wieder(tmp_path, monkeypatch, capsys):
    """Und die Sperre darf nicht kleben: neue Quelle, neuer Lauf."""
    m = _modul(tmp_path, monkeypatch)
    _quelle(m.SRC, [("a_2026", "lv.pdf", "pdf", "Erster Text", "ok")])
    m.main([])
    capsys.readouterr()

    m.SRC.unlink()
    _quelle(m.SRC, [("a_2026", "lv.pdf", "pdf", "Erster Text", "ok"),
                    ("b_2026", "lb.pdf", "pdf", "Zweiter Text", "ok")])
    assert m.main([]) == 0
    aus = capsys.readouterr().out
    assert "2 Vorgänge" in aus, aus
    assert (m.JE_VORGANG / "b_2026.json").exists()


def test_dateien_eines_vorgangs_kommen_zusammen_und_in_ordnung(tmp_path, monkeypatch):
    """Die Gruppierung ohne `ORDER BY` — der eigentliche Umbau.

    Das teure `ORDER BY notice_id, file` sortierte 817 MB samt Volltext-Spalten; genau das
    war der Speicherfresser. Gebraucht wird es nicht: `index-docs` schreibt vorgangsweise
    (gemessen über 223.747 Zeilen: kein einziger Vorgang ist in der Dateireihenfolge
    zerrissen). Die Reihenfolge INNERHALB eines Vorgangs stellt der Export selbst her.

    ⚠ Der Test prüft beides — dass alle Dateien eines Vorgangs ankommen UND in welcher
    Reihenfolge. Ohne die zweite Hälfte wäre eine zufällige Reihenfolge bestanden, und der
    Nutzer bekäme die Abschnitte seiner Unterlagen durcheinander.
    """
    m = _modul(tmp_path, monkeypatch)
    _quelle(m.SRC, [
        ("a_2026", "c.pdf", "pdf", "Drittes", "ok"),
        ("a_2026", "a.pdf", "pdf", "Erstes", "ok"),
        ("a_2026", "b.pdf", "pdf", "Zweites", "ok"),
        ("b_2026", "x.pdf", "pdf", "Fremdes", "ok"),
    ])
    assert m.main([]) == 0

    a = json.loads((m.JE_VORGANG / "a_2026.json").read_text(encoding="utf-8"))
    assert a["files"] == 3, "nicht alle Dateien des Vorgangs sind angekommen"
    assert a["text"].index("Erstes") < a["text"].index("Zweites") < a["text"].index("Drittes"), \
        "die Dateien stehen nicht in Namensreihenfolge"
    assert "Fremdes" not in a["text"], "der Text eines anderen Vorgangs ist mit hineingeraten"


def test_kein_direktes_schreiben_der_grossen_datei():
    """Die 355-MB-Datei wird über eine temporäre Datei geschrieben, nicht direkt.

    `analyze_docs.py` sicherte den Zwischenstand mit `OUT.write_text(...)`. Das Schreiben
    dauert Sekunden; wer den Lauf in diesem Fenster abbricht — `launchctl bootout`, ein
    Neustart, eine volle Platte — bekommt eine abgeschnittene Datei, und zwar ohne
    Fehlermeldung. Sie ist einfach kürzer und nicht mehr lesbar. Darin stecken Analysen für
    rund 94 $ bezahlte Modell-Zeit.

    ⚠ Kommentare und Docstrings werden vorher entfernt: die Datei ERKLÄRT den alten Fehler,
    und ein Test, der Prosa mitzählt, zwingt einen dazu, die Begründung zu löschen.
    """
    import ast

    quelle = (ROOT / "scripts" / "analyze_docs.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    for knoten in ast.walk(baum):
        if not (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute)):
            continue
        if knoten.func.attr != "write_text":
            continue
        ziel = knoten.func.value
        assert not (isinstance(ziel, ast.Name) and ziel.id == "OUT"), (
            f"Zeile {knoten.lineno}: die grosse Ergebnisdatei wird wieder direkt "
            f"geschrieben — ein Abbruch mittendrin kappt sie")


def _analyse_modul():
    """`scripts/analyze_docs.py` laden. Der Import ist billig (gemessen 0,11 s / 57 MB) —
    die teure Arbeit steckt erst in `_lauf()`."""
    import sys

    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("ad", ROOT / "scripts" / "analyze_docs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("guthaben,erwartet_uebersprungen", [
    (1.41, True),    # der reale Fall vom 30.08.: 0,41 $ frei
    (1.00, True),    # genau auf der Reserve
    (0.20, True),    # darunter
    (5.00, False),   # genug fuer rund 160 Vorgaenge
    (1.55, False),   # knapp ueber der Schwelle (0,55 $ frei)
])
def test_leere_runde_faengt_gar_nicht_erst_an(monkeypatch, guthaben, erwartet_uebersprungen):
    """Die Geldwache sitzt im einzelnen Aufruf — sie verhindert Ausgaben, nicht Arbeit.

    Eine Runde ohne Guthaben lud trotzdem erst die Volltexte aus 817 MB Parquet und dann
    den Bestand (`doc-analysis.json`, 355 MB → rund 1,7 GB Python-Objekte), stellte fest,
    dass sie nichts tun darf, und schrieb alles zurück. Am 29.08. lief das im
    Viertelstundentakt: drei Runden hintereinander meldeten unverändert „1379 warten noch",
    während der Rechner unbedienbar war. Bezahlt hat es niemand — es hat nur die Maschine
    gekostet.

    ⚠ Beide Richtungen. Ein Test, der nur „springt über" prüft, wäre auch dann grün, wenn
    der Lauf NIE mehr anliefe — und das wäre die stillere, teurere Fehlerart.
    """
    m = _analyse_modul()
    monkeypatch.setattr(m, "_restguthaben", lambda: guthaben)
    grund = m._lohnt_sich()
    assert (grund is not None) is erwartet_uebersprungen, \
        f"bei {guthaben} $ Guthaben: {grund!r}"
    if grund:
        assert "Reserve" in grund and "Aufladen" in grund, \
            "die Meldung sagt nicht, was zu tun ist"


def test_unbekanntes_guthaben_haelt_den_lauf_nicht_auf(monkeypatch):
    """„Ich weiss es nicht" ist kein „kein Geld".

    Ist der Kontostand nicht abrufbar — Netz weg, Anbieter zickt —, darf die Analyse nicht
    stillstehen. Eine Bremse, die bei jeder Stoerung zumacht, legt den Betrieb lahm statt
    ihn zu schuetzen.
    """
    m = _analyse_modul()
    monkeypatch.setattr(m, "_restguthaben", lambda: None)
    assert m._lohnt_sich() is None

    def kaputt():
        raise RuntimeError("Anbieter antwortet nicht")

    monkeypatch.setattr(m, "_restguthaben", kaputt)
    assert m._lohnt_sich() is None

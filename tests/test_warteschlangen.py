"""Die Sonde gegen stillstehende Warteschlangen — an gebauten Fällen, nicht an der Tageslage.

⚠ WARUM SIE GEBAUT WURDE. Am 2026-10-05 lief der Analyse-Arbeiter seit dem 11. September
ununterbrochen, protokollierte alle 30 Minuten seinen Stand — und hatte seit dem 24. September
nichts mehr analysiert. 3.946 Dokumente lagen unbearbeitet, das Guthaben war seit dem 21.09.
leer. Elf Tage, zwölf Sonden, keine schlug an: der Dienst lief, die Daten waren vollständig,
kein Feld war NULL. Ein Arbeiter, der läuft und nichts bewegt, sieht in jeder Prozessliste
gesund aus.

⚠ UND DIE TAGESLAGE ZU PRÜFEN REICHT NICHT. Ein Test, der nur sagt „heute steht nichts still",
wäre an dem Tag, an dem etwas stillsteht, einfach rot — und an allen anderen grün, ohne je
belegt zu haben, dass der Detektor etwas SIEHT. Deshalb hier gebaute Fälle in beide
Richtungen: er muss den Stillstand finden UND bei einer abgearbeiteten Schlange schweigen.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "scripts"))

import pruefe_warteschlangen as pw      # noqa: E402


def _nur_code(pfad: pathlib.Path) -> str:
    """Python-Quelle ohne Kommentare UND ohne Docstrings.

    ⚠ DIESER HELFER IST SELBST EIN BEFUND. Die Prüfung unten („die Sonde darf keine
    Protokolle lesen") schlug beim ersten Lauf an — an der BEGRÜNDUNG im Docstring der
    Sonde, die das Wort „Kein Guthaben" zitiert. Genau die Falle, vor der
    `waechter-messen-prosa-statt-code` warnt, und ein Zeilenfilter auf `#` sieht sie nicht:
    ein Docstring ist Code, kein Kommentar.

    Deshalb über `ast` statt über Textregeln — ein Dreifachanführungszeichen mitten in einem
    Ausdruck oder ein `#` in einer Zeichenkette bringt jeden Regex durcheinander.
    """
    import ast
    quelle = pfad.read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    # ⚠ Einfach ueber ALLE Knoten, nicht ueber `body`/`orelse` der Eltern: dort liegt bei
    # einem f-String ein `FormattedValue` statt einer Liste, und das warf beim ersten Anlauf
    # `TypeError: 'JoinedStr' object is not iterable`. Ein Docstring IST nichts anderes als
    # eine Anweisung, die nur aus einer Zeichenkette besteht — genau das wird hier gesucht.
    weg: set[int] = set()
    for k in ast.walk(baum):
        if (isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant)
                and isinstance(k.value.value, str)):
            weg.update(range(k.lineno, (k.end_lineno or k.lineno) + 1))
    zeilen = [z for i, z in enumerate(quelle.splitlines(), 1)
              if i not in weg and not z.lstrip().startswith("#")]
    return "\n".join(zeilen)


def test_der_stripper_entfernt_docstrings_UND_kommentare():
    """Selbstprobe des Helfers: ohne sie misst die Prüfung darunter womöglich Prosa."""
    probe = '"""Doku mit VERBOTEN drin."""\n# auch VERBOTEN\nx = "ECHT"\n'
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "m.py"
        p.write_text(probe, encoding="utf-8")
        raus = _nur_code(p)
    assert "VERBOTEN" not in raus, f"Prosa nicht entfernt: {raus!r}"
    assert "ECHT" in raus, "echter Code wurde mit entfernt"


def _schlange(name, wartend, tage_her):
    wann = dt.date.today() - dt.timedelta(days=tage_her)
    return {"name": name, "wartend": wartend, "bewegung": wann.isoformat(), "tage": tage_her}


def test_arbeit_und_stillstand_ist_ein_befund():
    """Der echte Fall vom 2026-10-05: 3.946 wartend, 11 Tage keine Bewegung."""
    b = pw.befunde_aus([_schlange("Analyse DE", 3946, 11)])
    assert [x["name"] for x in b] == ["Analyse DE"]


def test_eine_leere_schlange_steht_zu_recht_still():
    """⚠ DIE WICHTIGERE RICHTUNG. Eine abgearbeitete Schlange bewegt sich nie wieder — sie
    hier zu melden hiesse, sie für immer anzuzeigen. Ein Wächter, der dauernd grundlos
    schreit, wird übergangen, und dann ist auch der echte Befund verloren."""
    assert pw.befunde_aus([_schlange("Analyse DE", 0, 400)]) == []


def test_arbeit_die_sich_bewegt_ist_kein_befund():
    assert pw.befunde_aus([_schlange("Analyse DE", 3946, 1)]) == []


def test_unbekannter_stand_wird_nicht_geraten():
    """`wartend is None` heisst „wir wissen es nicht" — das ist kein Befund. Für die
    Abruf-Schlangen ist das der Regelfall, weil der Rückstau bei 3 von 13 Abrufern
    nachweislich nicht filtert (`govisor-rueckstau-steuerzahl`)."""
    assert pw.befunde_aus([_schlange("Abruf DE/simap", None, 99)]) == []


def test_die_schwelle_liegt_zwischen_normalbetrieb_und_ausfall():
    """⚠ Sie ist GEMESSEN, nicht gefühlt — und dieser Test hält die Messung fest.

    Die Analyse lieferte zwischen dem 2026-08-22 und dem 2026-09-24 an 23 Tagen Ergebnisse;
    die Lücken dazwischen waren 1, 2, 3 und 5 Tage. Grösste Lücke im Normalbetrieb: 5.
    Der Ausfall: 11. Eine Schwelle unter 6 schriee an einem ruhigen Wochenende, eine über
    10 verschliefe genau den Fall, für den die Sonde gebaut ist.
    """
    groesste_normale_luecke, ausfall = 5, 11
    assert groesste_normale_luecke < pw.SCHWELLE_TAGE < ausfall, (
        f"Schwelle {pw.SCHWELLE_TAGE} liegt nicht zwischen Normalbetrieb "
        f"({groesste_normale_luecke}) und Ausfall ({ausfall})")
    assert pw.befunde_aus([_schlange("x", 10, groesste_normale_luecke)]) == [], \
        "die grösste normale Lücke darf nicht melden"
    assert pw.befunde_aus([_schlange("x", 10, ausfall)]), "der Ausfall muss melden"


def test_der_grund_kommt_aus_den_daten_und_nicht_aus_dem_protokoll():
    """⚠ Eine Sonde, die Protokolltexte liest, zerbricht beim ersten umformulierten Satz.
    Der Arbeiter schreibt seinen Haltegrund nach `data/.llm_stand.json` — genau dort wird
    er geholt, und das ist auch die Stelle, an der die Auskunft am 2026-10-05 bereits lag,
    ohne dass sie jemand las."""
    ohne_text = _nur_code(WURZEL / "scripts" / "pruefe_warteschlangen.py")
    for verboten in ("Library/Logs", "govisor-analyse.out.log", "Kein Guthaben"):
        assert verboten not in ohne_text, (
            f"die Sonde liest {verboten!r} — Protokolltexte altern, Datenspalten nicht")
    assert ".llm_stand.json" in ohne_text


def test_an_den_echten_daten_laeuft_sie_durch():
    """Kein Urteil über die Tageslage — nur, dass die Messung auf diesem Bestand nicht
    abstürzt und jede Schlange die Felder trägt, auf denen die Regel oben arbeitet."""
    if not (WURZEL / "data").exists():
        pytest.skip("keine Datenebene auf dieser Maschine")
    alle, befunde = pw.pruefe()
    assert alle, "keine einzige Warteschlange gefunden — die Pfade stimmen nicht mehr"
    for s in alle:
        if "fehler" in s:
            continue
        assert "name" in s and "tage" in s and "wartend" in s, f"unvollständig: {s}"
    assert all(b in alle for b in befunde)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

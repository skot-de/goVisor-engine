"""cosinex — „kein ZIP" ist drei verschiedene Dinge.

Ohne Netz. Geprüft wird die Einordnung der Antwort, nicht der Abruf.
"""
from __future__ import annotations

from govisor import docfetch
from govisor import docfetch_queue as q


def test_skript_und_stil_zaehlen_nicht_zum_sichtbaren_text():
    """⚠ Eine erste Fassung suchte im Roh-HTML nach „anmelden" und fand es überall — in
    CSS-Regeln und im Kopfmenü, das auf JEDER cosinex-Seite einen Login-Link trägt.
    Dieselbe Falle wie die had.de-Brotkrume."""
    html = ('<style>img.lazy{min-height:1px} .anmelden{color:red}</style>'
            '<script>var login="anmelden";</script>'
            '<div>Um Zugriff auf dieses Modul zu erhalten müssen Sie am '
            'Vergabeverfahren teilnehmen.</div>')
    t = docfetch._sichtbarer_text(html)
    assert "img.lazy" not in t and "var login" not in t
    assert "am Vergabeverfahren teilnehmen" in t


def test_teilnahme_wird_erkannt():
    assert docfetch._TEILNAHME.search(
        "Um Zugriff auf dieses Modul zu erhalten müssen Sie am Vergabeverfahren teilnehmen.")
    assert not docfetch._TEILNAHME.search("Bitte melden Sie sich an Startseite Login")


def test_die_drei_ausgaenge_liegen_in_verschiedenen_klassen():
    """Der Unterschied ist nicht kosmetisch: `gated` wartet auf einen Zugang, `weg` ist
    endgültig, und `kein_zip` sagt ehrlich „ungeklärt"."""
    assert q.BLOCKIERT.get("gated") == "konto"
    assert "weg" in q.DAUERHAFT
    # Ungeklaertes gehoert in KEINE der Mengen — es soll nach der Sperrfrist wiederkommen.
    assert "kein_zip" not in q.DAUERHAFT
    assert "kein_zip" not in q.BLOCKIERT
    assert "kein_zip" not in q.KEIN_FEHLSCHLAG


def test_keine_pauschale_gated_einstufung_mehr():
    """⚠ Bis 2026-08-31 stand hier `gated` für JEDE Antwort ohne ZIP — der Kommentar nannte
    die Zweideutigkeit sogar („oder nicht (mehr) verfügbar") und entschied trotzdem für die
    blockierende Deutung."""
    quelle = docfetch.__file__
    with open(quelle, encoding="utf-8") as f:
        code = "\n".join(z for z in f if not z.lstrip().startswith("#"))
    i = code.index('"zip" not in ctype')
    block = code[i:i + 1400]
    assert '"weg"' in block and '"kein_zip"' in block and '"gated"' in block


def test_notiz_sagt_den_grund_nicht_den_inhaltstyp():
    """Die alte Notiz lautete „http 200, text/html;charset=iso-8859-1" — technisch wahr und
    für die Frage „warum kam nichts?" wertlos."""
    with open(docfetch.__file__, encoding="utf-8") as f:
        code = f.read()
    assert "Teilnahme am Verfahren nötig" in code
    assert "Vorgang nicht mehr auf dem Portal (404)" in code

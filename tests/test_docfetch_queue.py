"""Die Warteschlange muss vorankommen — sonst holt ein Fetcher jeden Tag dieselbe Niete.

Der Fehler, den diese Tests festnageln, hat drei Fetcher gleichzeitig lahmgelegt und sah
dabei aus wie drei verschiedene Fehler: `aumass` 0 von 2, `staatsanzeiger` 0 von 3,
`docfetch_healyhudson` 0 von 40. Die Ursache war eine einzige — ein Vorgang ohne Unterlagen
hinterlässt keine ZIP-Datei, und die Kandidatenwahl prüfte nur, ob eine Datei da ist. Der
Fehlschlag wurde sauber gemeldet, aber nirgends behalten.

Nach dem Fix: `aumass --limit 2` ging von 0 geladen auf 2 geladen (27 Dateien, 21,3 MB).
Es war nie ein Fetcher-Problem.
"""
from __future__ import annotations

import datetime as dt

from govisor import docfetch_queue as q

HEUTE = dt.date(2026, 8, 14)


def test_dauerhaftes_wird_nie_wieder_versucht():
    """Eine Ex-Ante-Bekanntmachung kündigt eine beabsichtigte Direktvergabe an. Es GIBT
    keine Unterlagen — nicht heute und nicht in drei Wochen."""
    for status in ("ohne_unterlagen", "kein_downloadbereich", "frameset"):
        vorher = {"status": status, "wann": dt.date(2020, 1, 1)}
        assert q.ueberspringen(vorher, HEUTE) == status, status


def test_voruebergehendes_bekommt_eine_sperrfrist_keinen_ausschluss():
    """Eine Vorgangsseite ohne Dateien kann morgen welche haben — Unterlagen werden oft
    nach der Bekanntmachung nachgereicht. „Nie wieder" wäre hier echter Datenverlust."""
    frisch = {"status": "leer", "wann": HEUTE - dt.timedelta(days=2)}
    assert q.ueberspringen(frisch, HEUTE), "innerhalb der Sperre: überspringen"

    alt = {"status": "leer", "wann": HEUTE - dt.timedelta(days=q.SPERRE_TAGE + 1)}
    assert q.ueberspringen(alt, HEUTE) is None, "nach der Sperre: wieder versuchen"

    netz = {"status": "fehler", "wann": HEUTE - dt.timedelta(days=q.SPERRE_TAGE)}
    assert q.ueberspringen(netz, HEUTE) is None, "ein Netzfehler ist kein Urteil"


def test_erfolg_und_trockenlauf_sind_kein_fehlschlag():
    """`probe` ist der Trockenlauf-Vermerk. Ihn als Fehlschlag zu werten hiesse, dass ein
    einziger `--dry-run` den Kandidaten für eine Woche sperrt."""
    for status in ("downloaded", "probe"):
        assert q.ueberspringen({"status": status, "wann": HEUTE}, HEUTE) is None


def test_unbekannter_kandidat_wird_versucht():
    """Kein Gedächtnis heisst „noch nie probiert", nicht „gescheitert"."""
    assert q.ueberspringen({}, HEUTE) is None
    assert q.ueberspringen({"status": None, "wann": None}, HEUTE) is None


def test_filtere_zaehlt_die_gruende_statt_still_zu_kappen():
    """Ein Lauf, der 200 Kandidaten still auslässt und „3 versucht" meldet, führt in die
    Irre. Was übersprungen wird, muss gezählt und benannt werden."""
    offen = [("a", "u"), ("b", "u"), ("c", "u"), ("d", "u")]
    vorher = {
        "a": {"status": "ohne_unterlagen", "wann": HEUTE},
        "b": {"status": "frameset", "wann": HEUTE},
        "c": {"status": "downloaded", "wann": HEUTE},
    }
    bleibt, gruende = q.filtere(offen, vorher)
    assert [x[0] for x in bleibt] == ["c", "d"]
    assert gruende == {"ohne_unterlagen": 1, "frameset": 1}
    assert "ohne_unterlagen=1" in q.bericht(gruende)
    assert q.bericht({}) == "", "nichts übersprungen → keine Zeile"


def test_manifest_wird_fortgeschrieben_nicht_ueberschrieben(tmp_path):
    """Das alte Verhalten warf mit jedem Lauf die gesamte Vorgeschichte weg. Damit war
    nicht nur die Warteschlange blind, sondern auch jede Frage nach dem Verlauf
    unbeantwortbar."""
    q.schreibe(tmp_path, "test", [
        {"lead_id": "a", "status": "ohne_unterlagen", "bytes": 0},
        {"lead_id": "b", "status": "downloaded", "bytes": 100},
    ])
    q.schreibe(tmp_path, "test", [{"lead_id": "c", "status": "leer", "bytes": 0}])

    bekannt = q.frueher(tmp_path, "test")
    assert set(bekannt) == {"a", "b", "c"}, "der erste Lauf darf nicht verschwinden"
    assert bekannt["a"]["status"] == "ohne_unterlagen"


def test_juengster_satz_gewinnt_je_lead():
    """Sonst wüchse die Datei mit jedem Lauf, und ein alter Fehlschlag könnte einen
    späteren Erfolg überstimmen."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        q.schreibe(p, "t", [{"lead_id": "a", "status": "leer",
                             "versucht_am": dt.date(2026, 8, 1)}])
        q.schreibe(p, "t", [{"lead_id": "a", "status": "downloaded",
                             "versucht_am": dt.date(2026, 8, 10)}])
        bekannt = q.frueher(p, "t")
        assert len(bekannt) == 1
        assert bekannt["a"]["status"] == "downloaded"


def test_kaputtes_manifest_kostet_historie_nicht_den_lauf(tmp_path):
    """Der schlimmste Fall darf sein, dass wieder von vorn probiert wird — das ist der
    Zustand von gestern, kein Ausfall."""
    (tmp_path / "_manifest_kaputt.parquet").write_bytes(b"kein parquet")
    assert q.frueher(tmp_path, "kaputt") == {}


def test_alle_vier_fetcher_nutzen_das_gedaechtnis():
    """Der Fehler war viermal derselbe. Die Lösung darf nicht bei dreien hängenbleiben."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for name in ("netserver", "aumass", "healyhudson", "staatsanzeiger"):
        text = (root / "govisor" / f"docfetch_{name}.py").read_text(encoding="utf-8")
        assert "docfetch_queue" in text, f"{name} liest das Gedächtnis nicht"
        assert "_queue.filtere" in text, f"{name} filtert nicht"
        assert "_queue.schreibe" in text, f"{name} schreibt das Manifest noch selbst"
        # Der Filter MUSS vor dem Limit stehen, sonst kappt das Limit auf Kandidaten,
        # die gleich wieder aussortiert werden — und der Lauf holt wieder nichts.
        assert text.index("_queue.filtere") < text.index("offen = offen[:limit]"), (
            f"{name}: gefiltert wird nach dem Kappen — dann bleibt nichts übrig")

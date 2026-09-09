"""Zwei Abrufer, die an einem langsamen Moment die Arbeit eines ganzen Schritts verloren.

⚠ WARUM ES DIESE DATEI GIBT — beide Ausfaelle sind gemessen, nicht ausgedacht:

  · **Healy-Hudson**, 2026-09-07 und 2026-09-09. Ein `Page.goto`-Zeitablauf (45 s) flog
    ungeschuetzt aus der Runden-Schleife durch die Laender-Schleife nach oben. Bronze wird
    erst HINTER der Schleife geschrieben — also war auch alles Eingesammelte weg. Am 09.09.
    riss `BL=01`, das erste Bundesland: 0 statt 16 Laender, 873 s Laufzeit, keine Zeile.
  · **OffeneVergaben.at**, 2026-09-09. Ein `urlopen`-Zeitablauf ohne zweiten Versuch. Die
    Quelle kriecht gelegentlich (974 s gingen am 05.09. noch durch, 1352 s am 09.09. nicht).

Beide Male sah das Protokoll fast normal aus. Die Tests halten fest, was die Reparatur
koennen muss — und ebenso, was sie NICHT tun darf: einen Programmfehler wegschlucken.
"""
from __future__ import annotations

import urllib.error

import pytest

from govisor import atverg, healyhudson


# ─────────────────────────────────────────────────── Healy-Hudson

class FakeSeite:
    """Ein Playwright-`page`, das in bestimmten Runden ausfaellt."""

    def __init__(self, fehler_in: set[int], zeilen_je_runde: int = 2):
        self.fehler_in = fehler_in
        self.zeilen_je_runde = zeilen_je_runde
        self.runde = 0

    def goto(self, url, **kw):
        self.runde += 1
        if self.runde in self.fehler_in:
            raise TimeoutError(f"Page.goto: Timeout 45000ms exceeded (Runde {self.runde})")

    def wait_for_timeout(self, ms):        # kein Schlaf im Test
        pass

    def set_default_timeout(self, ms):
        pass

    def evaluate(self, js):
        if "body.innerText" in js:
            return "Anzahl: 9"
        # Sechs Zellen im Spaltenschnitt der echten Liste (`_SPALTE`/`_MIN_ZELLEN`);
        # je Runde andere Titel, weil die echte Liste je Abruf neu wuerfelt.
        return [["", "VOB", f"Bauvorhaben {self.runde}-{i}", "Stadt Musterhausen",
                 "01.09.2026", "30.09.2026"]
                for i in range(self.zeilen_je_runde)]


def test_eine_gescheiterte_runde_verliert_das_land_nicht():
    """⚠ Der Kern: Runde 2 faellt aus, die Saetze aus Runde 1 und 3 muessen bleiben."""
    pg = FakeSeite(fehler_in={2})
    r = healyhudson.hole_land("SH", pg, runden=3)
    assert r["fehler"] == 1
    assert r["geholt"] > 0, "die Saetze der gelungenen Runden gingen verloren"


def test_drei_aussetzer_am_stueck_geben_das_land_auf():
    """Ein totes Portal soll nicht zwoelf Runden lang angeklopft werden."""
    pg = FakeSeite(fehler_in={1, 2, 3, 4, 5, 6})
    r = healyhudson.hole_land("SH", pg, runden=12)
    assert r["fehler"] == healyhudson._AUSSETZER, r
    assert pg.runde == healyhudson._AUSSETZER, "nach der Grenze wurde weiter angeklopft"


def test_ein_treffer_setzt_die_aussetzer_zurueck():
    """Aussetzer zaehlen AM STUECK. Sonst gibt eine wacklige Leitung das Land auf,
    obwohl jede zweite Runde liefert."""
    pg = FakeSeite(fehler_in={1, 3, 5})
    r = healyhudson.hole_land("SH", pg, runden=6)
    assert r["fehler"] == 3
    assert r["geholt"] > 0
    assert pg.runde == 6, "der Lauf wurde vorzeitig abgebrochen"


def test_ein_ausgefallenes_land_beendet_nicht_die_uebrigen(monkeypatch, capsys):
    """Der 09.09.-Fall: das ERSTE Land stirbt, die anderen muessen trotzdem geholt werden."""
    gesehen = []

    def stub(kuerzel, pg, runden):
        gesehen.append(kuerzel)
        if kuerzel == "SH":
            raise RuntimeError("Browser weg")
        return {"land": kuerzel, "name": healyhudson.LAENDER[kuerzel][1], "gemeldet": 2,
                "geholt": 2, "runden": 1, "fehler": 0,
                "saetze": [{"schluessel": f"{kuerzel}-1"}, {"schluessel": f"{kuerzel}-2"}]}

    monkeypatch.setattr(healyhudson, "hole_land", stub)
    monkeypatch.setattr(healyhudson, "sync_playwright", _fake_playwright(), raising=False)
    r = healyhudson.lauf(["SH", "HH", "NI"], runden=3, dry_run=True)
    assert gesehen == ["SH", "HH", "NI"], "nach dem Ausfall wurde abgebrochen"
    assert r["ausgefallen"] == ["SH"]
    assert r["laender"] == 2
    assert r["geholt"] == 4, "die Saetze der ueberlebenden Laender fehlen"
    assert "⛔ ausgefallen: SH" in capsys.readouterr().out


def test_fehlercode_nur_wenn_kein_land_durchkam(monkeypatch):
    """⚠ Sonst faerbt die unzuverlaessigste Landesseite den ganzen Schritt rot — und der
    Nachtlauf meldet dasselbe, ob ein Land fehlt oder alle sechzehn."""
    monkeypatch.setattr(healyhudson, "sync_playwright", _fake_playwright(), raising=False)

    monkeypatch.setattr(healyhudson, "hole_land",
                        lambda k, pg, r: (_ for _ in ()).throw(TimeoutError("tot")))
    assert healyhudson.main(["--laender", "SH,HH", "--dry-run"]) == 1

    monkeypatch.setattr(healyhudson, "hole_land", lambda k, pg, r: {
        "land": k, "name": k, "gemeldet": 1, "geholt": 1, "runden": 1, "fehler": 0,
        "saetze": [{"schluessel": f"{k}-1"}]})
    assert healyhudson.main(["--laender", "SH,HH", "--dry-run"]) == 0


def _fake_playwright():
    """`lauf` holt sich Playwright erst im Funktionsrumpf — hier ein Ersatz ohne Browser."""
    class Ctx:
        def new_page(self):
            return FakeSeite(set())

        def close(self):
            pass

    class Browser:
        def new_context(self):
            return Ctx()

        def close(self):
            pass

    class Chromium:
        def launch(self, **kw):
            return Browser()

    class P:
        chromium = Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return lambda: P()


# ─────────────────────────────────────────────────── OffeneVergaben.at

class _Cfg:
    def __init__(self, tmp):
        self.data_dir = tmp


def _antworten(folge):
    """`_get`-Ersatz: arbeitet `folge` ab (Ausnahme = werfen, sonst zurueckgeben)."""
    rest = list(folge)
    aufrufe = []

    def stub(url):
        aufrufe.append(url)
        x = rest.pop(0)
        if isinstance(x, Exception):
            raise x
        return x

    return stub, aufrufe


_SEITE = ('<a href="https://offenevergaben.at/tmp/'
          'kerndaten_dailydump_1757000000_a1b2c3.zip">CSV</a>').encode()


def test_ein_zeitablauf_wird_wiederholt(tmp_path, monkeypatch, capsys):
    """Der 09.09.-Fall: erster Anlauf laeuft in den Zeitablauf, der zweite traegt."""
    stub, aufrufe = _antworten([_SEITE, TimeoutError("read operation timed out"),
                                _SEITE, b"ZIP-Inhalt"])
    monkeypatch.setattr(atverg, "_get", stub)
    monkeypatch.setattr(atverg.time, "sleep", lambda s: None)
    out = atverg.download(_Cfg(tmp_path), stamp="2026-09-09")
    assert out.read_bytes() == b"ZIP-Inhalt"
    assert len(aufrufe) == 4
    # ⚠ Der zweite Anlauf muss die SEITE neu holen: die ZIP-Adresse traegt Zeitstempel und
    # Hash und wird je Aufruf frisch erzeugt.
    assert aufrufe[2] == atverg._PAGE, aufrufe
    assert "Versuch 1/3" in capsys.readouterr().out


def test_nach_drei_versuchen_wird_durchgereicht(tmp_path, monkeypatch):
    """Eine dauerhaft tote Quelle darf nicht endlos angeklopft werden."""
    stub, aufrufe = _antworten([urllib.error.URLError("weg")] * atverg._VERSUCHE)
    monkeypatch.setattr(atverg, "_get", stub)
    monkeypatch.setattr(atverg.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.URLError):
        atverg.download(_Cfg(tmp_path), stamp="2026-09-09")
    assert len(aufrufe) == atverg._VERSUCHE


def test_ein_geaenderter_seitenaufbau_wird_nicht_wiederholt(tmp_path, monkeypatch):
    """⚠ Die wichtigste Grenze: fehlt der ZIP-Link, ist die Seite umgebaut worden. Dreimal
    dasselbe zu holen verdeckt den Befund nur — und kostet zwei Pausen dazu."""
    stub, aufrufe = _antworten([b"<html>ganz anders</html>"])
    monkeypatch.setattr(atverg, "_get", stub)
    monkeypatch.setattr(atverg.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="ZIP-Link"):
        atverg.download(_Cfg(tmp_path), stamp="2026-09-09")
    assert len(aufrufe) == 1, "ein Programmbefund wurde als Netzfehler wiederholt"

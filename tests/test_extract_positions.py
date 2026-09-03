"""Leistungsverzeichnisse: was der Merker überspringen darf und was nicht.

Bis zum 2026-09-03 entpackte dieser Schritt jede Nacht alle Archive neu. Der Merker spart
das — und genau daran hängt jetzt die Richtigkeit der Ausgabe: was übersprungen wird, muss
aus dem letzten Lauf übernommen werden, und was sich geändert hat, muss auffallen.
"""
from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "extract_positions.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")


def _modul():
    spec = importlib.util.spec_from_file_location("_ep", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _modul()


def _vorgang(basis: Path, name: str, inhalt: bytes = b"x") -> Path:
    v = basis / name
    v.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(v / "unterlagen.zip", "w") as z:
        z.writestr("egal.txt", inhalt)
    return v


# ── Fingerabdruck ───────────────────────────────────────────────────────────────────

def test_gleicher_vorgang_gleicher_abdruck(tmp_path):
    v = _vorgang(tmp_path, "a")
    assert M._fingerabdruck(v) == M._fingerabdruck(v)


def test_neues_archiv_aendert_den_abdruck(tmp_path):
    v = _vorgang(tmp_path, "a")
    vorher = M._fingerabdruck(v)
    with zipfile.ZipFile(v / "nachtrag.zip", "w") as z:
        z.writestr("mehr.txt", b"y")
    assert M._fingerabdruck(v) != vorher


def test_geaenderter_inhalt_aendert_den_abdruck(tmp_path):
    v = _vorgang(tmp_path, "a", b"kurz")
    vorher = M._fingerabdruck(v)
    with zipfile.ZipFile(v / "unterlagen.zip", "w") as z:
        z.writestr("egal.txt", b"deutlich laenger als vorher")
    assert M._fingerabdruck(v) != vorher, "Groesse fliesst nicht in den Abdruck ein"


def test_vorgang_ohne_archiv_hat_einen_abdruck(tmp_path):
    """Ein leeres Verzeichnis ist ein gültiger Zustand — und darf nicht jede Nacht neu
    'geprüft' werden, nur weil es nichts enthält."""
    (tmp_path / "leer").mkdir()
    assert M._fingerabdruck(tmp_path / "leer").startswith("v")


def test_parser_stand_entwertet_den_merker(tmp_path):
    """⚠ Der Merker kennt die ARCHIVE, nicht den Code. Ein verbesserter GAEB-Leser würde
    sonst lautlos nie angewandt: die alten Ergebnisse blieben stehen und sähen frisch aus."""
    v = _vorgang(tmp_path, "a")
    vorher = M._fingerabdruck(v)
    alt = M.PARSER_STAND
    try:
        M.PARSER_STAND = alt + 1
        assert M._fingerabdruck(v) != vorher
    finally:
        M.PARSER_STAND = alt


# ── Merker lesen ────────────────────────────────────────────────────────────────────

def test_fehlender_merker_ist_kein_fehler(tmp_path):
    """Der erste Lauf hat keinen — er muss alles lesen, nicht abbrechen."""
    assert M._stand_lesen(tmp_path) == {}


def test_alte_zeilen_melden_ob_die_dateien_da_sind(tmp_path):
    """Der dritte Rückgabewert entscheidet, ob überhaupt übersprungen werden darf."""
    assert M._alte_zeilen(tmp_path)[2] is False


def test_kaputter_merker_ist_kein_fehler(tmp_path):
    """Lieber einmal zu viel lesen als abbrechen: das kostet Zeit, nicht Daten."""
    (tmp_path / "doc_positions_stand.parquet").write_bytes(b"kein parquet")
    assert M._stand_lesen(tmp_path) == {}


# ── Die Regeln, die im Code stehen muessen ──────────────────────────────────────────

def test_ohne_die_alten_dateien_wird_nicht_uebersprungen():
    """⚠ Der Merker sagt nur „unverändert". Fehlen die Ausgabedateien, gibt es nichts zu
    übernehmen — dann muss trotz passendem Fingerabdruck gelesen werden, sonst schrumpft
    die Ausgabe bei jedem Lauf um alles, was gerade nicht neu gerechnet wurde."""
    kern = QUELLE.split("def sammle(")[1].split("\ndef ")[0]
    assert "if alt_da and stand.get(nid) == fa:" in kern


def test_geprueft_und_nichts_gefunden_wird_uebersprungen():
    """⚠ DER ERSTE ENTWURF HAETTE FAST NICHTS GESPART. Seine Bedingung verlangte, dass der
    Vorgang in der alten AUSGABE steht — aber nur 4.011 von 10.216 haben überhaupt ein
    Leistungsverzeichnis. Die anderen 6.200 wären jede Nacht erneut entpackt worden, also
    genau die Mehrheit, um die es geht."""
    kern = QUELLE.split("def sammle(")[1].split("\ndef ")[0]
    assert "nid in alt_pos" not in kern, "die Bedingung haengt wieder an der alten Ausgabe"


def test_nichts_gefunden_wird_auch_gemerkt():
    """⚠ Nur 4.011 von 10.216 Vorgängen haben überhaupt ein Leistungsverzeichnis. Kennte
    der Merker nur die Treffer, liefe der Schritt für die anderen 6.200 jede Nacht erneut,
    also für die Mehrheit — und spart hätte er fast nichts."""
    kern = QUELLE.split("def sammle(")[1].split("\ndef ")[0]
    i_stand = kern.index("neuer_stand[nid] = fa")
    i_skip = kern.index("uebernommen += 1")
    assert i_stand < i_skip, "der Fingerabdruck wird erst nach dem Ueberspringen gesetzt"


def test_merker_wird_nach_den_ergebnissen_geschrieben():
    """⚠ Stirbt der Lauf dazwischen, ist der Merker älter als die Daten — dann wird zu viel
    gelesen, was Zeit kostet, aber nichts kaputt macht. Andersherum wäre es Datenverlust:
    ein Merker ohne die zugehörigen Zeilen lässt sie für immer überspringen."""
    kern = QUELLE.split("def main(")[1]
    assert kern.index("doc_positions.parquet") < kern.index("doc_positions_stand.parquet")
    assert kern.index("doc_lv.parquet") < kern.index("doc_positions_stand.parquet")


def test_limit_schreibt_keinen_merker():
    """Bei `--limit` sieht der Lauf nur einen Ausschnitt. Einen Merker daraus zu schreiben
    hiesse, den Rest als geprüft zu markieren, ohne ihn angesehen zu haben."""
    kern = QUELLE.split("def main(")[1]
    assert "if stand and limit is None:" in kern


def test_voll_umgeht_den_merker():
    """Nach einer Parser-Aenderung, die `PARSER_STAND` nicht erfasst, braucht es einen Weg
    zurueck zur vollen Berechnung."""
    assert '--voll' in QUELLE
    kern = QUELLE.split("def sammle(")[1].split("\ndef ")[0]
    assert "{} if voll else _stand_lesen(root)" in kern


def test_der_wochenlauf_faehrt_voll():
    """⚠ Der Merker erkennt geänderte ARCHIVE zuverlässig, aber nicht jede denkbare Änderung
    am Leser. `PARSER_STAND` deckt die bewussten ab, der Sonntagslauf die unbewussten —
    dasselbe Muster, das die Dubletten-Firewall schon fährt."""
    lauf = (WURZEL / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    block = lauf.split('step "Leistungsverzeichnisse')[0][-700:] + \
        lauf.split('step "Leistungsverzeichnisse')[1][:400]
    assert '_LV_ARGS="--voll"' in block
    assert 'date +%u' in block

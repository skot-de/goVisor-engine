"""Hält die Ausnahmeliste der Quellen-Sonde ehrlich.

⚠ **WARUM DIESER TEST WICHTIGER IST ALS DIE SONDE SELBST.** `RUHT_BEWUSST` schaltet
Meldungen ab. Genau so ist `cosinex-de` sieben Wochen unsichtbar geblieben — nicht durch
eine Ausnahme, sondern durch das Fehlen jeder Prüfung; eine gepflegte Ausnahmeliste ist der
nächstliegende Weg, denselben Zustand noch einmal herzustellen, nur mit gutem Gewissen.

Deshalb: ein Eintrag muss auf eine Quelle zeigen, die es GIBT, die wirklich ruht, und er
braucht eine Begründung, die etwas sagt. Dieselbe Bauart wie `tests/test_verdrahtung.py`.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from govisor import sources                      # noqa: E402
import pruefe_quellen_register as sonde          # noqa: E402


def _ids() -> set[str]:
    return {s.id for s in sources.REGISTRY}


def test_jede_ausnahme_zeigt_auf_eine_existierende_quelle():
    unbekannt = sorted(set(sonde.RUHT_BEWUSST) - _ids())
    assert not unbekannt, (
        "Diese Quellen stehen in RUHT_BEWUSST, existieren aber nicht (mehr) im Register. "
        f"Eine Ausnahme für etwas Gelöschtes verdeckt nichts, sie verwirrt nur: {unbekannt}")


def test_keine_ausnahme_fuer_eine_laengst_laufende_quelle():
    """Eine Ausnahme, die nicht mehr nötig ist, gehört weg — sonst bleibt sie stehen und
    deckt irgendwann einen echten Rückfall zu."""
    je_id = {s.id: s for s in sources.REGISTRY}
    unnoetig = sorted(i for i in sonde.RUHT_BEWUSST
                      if i in je_id and je_id[i].status == "live")
    assert not unnoetig, (
        "Diese Quellen laufen inzwischen, tragen aber noch eine Ruhe-Begründung. "
        f"Eintrag aus RUHT_BEWUSST entfernen: {unnoetig}")


@pytest.mark.parametrize("qid", sorted(sonde.RUHT_BEWUSST))
def test_jede_ausnahme_traegt_eine_echte_begruendung(qid: str):
    grund = sonde.RUHT_BEWUSST[qid]
    assert len(grund) >= 60, (
        f"Die Begründung für {qid} ist zu kurz, um eine zu sein. Wer eine Meldung abschaltet, "
        f"schreibt hin, WARUM und was das Einschalten verlangen würde: {grund!r}")


def test_die_sonde_faellt_bei_einer_ruhenden_quelle_wirklich_um():
    """⚠ Selbstprobe auf Testebene: ohne sie könnte die Sonde stumm grün bleiben.

    Gepflanzt wird eine Quelle, die `live` ist und deren Connector garantiert in keinem
    Lauf steht — genau die Lage, in der `cosinex-de` umgekehrt war.
    """
    text = sonde._lauftext().lower()
    erfunden = sources.Source("probe-test", "Testquelle", "existiertnirgends-html", "DE",
                              "beides", "live")
    assert sonde._stamm(erfunden.connector) not in text, (
        "Der erfundene Connector steht doch im Tageslauf — die Selbstprobe ist wertlos "
        "geworden, such einen anderen Namen.")


def test_kommentare_werden_vor_der_suche_entfernt():
    """⚠ Die Falle aus `waechter-messen-prosa-statt-code`: `cosinex` stand im Tageslauf in
    einem KOMMENTAR (Unterlagen-Abschnitt), während der Aufruf fehlte. Wer den rohen Text
    durchsucht, meldet die Quelle als verdrahtet."""
    roh = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    ohne = sonde._lauftext()
    assert "#" in roh, "Der Tageslauf hat keine Kommentare? Dann stimmt die Annahme nicht."
    assert len(ohne) < len(roh), "Es wurde kein einziger Kommentar entfernt"
    kommentarzeilen = [z for z in ohne.splitlines() if z.lstrip().startswith("#")]
    assert not kommentarzeilen, f"Kommentare überlebt: {kommentarzeilen[:3]}"

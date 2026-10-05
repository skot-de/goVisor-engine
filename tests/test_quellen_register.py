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


# ───────────────────────────────────────────────────────────────────────────────────────
# Das Prüfdatum (`Source.geprueft`, seit 2026-10-05)
#
# ⚠ WARUM DIESE DREI TESTS EXISTIEREN. Die Alters-Zusicherung war im ersten Entwurf BLIND:
# sie prüfte das Datumsformat erst NACH der Fristabfrage und sprang bei Status ohne Frist
# vorher ab. Eine kaputte Datumsangabe auf einer `live`-Quelle fiel damit nie auf. Gemerkt
# nur, weil eine Probe ein Unsinns-Datum pflanzte und die Sonde dazu schwieg. Eine Zusicherung,
# die man nicht zum Anschlagen gebracht hat, ist eine Vermutung.
# ───────────────────────────────────────────────────────────────────────────────────────


def _fahre(registry):
    """Laesst die Sonde gegen eine ERSETZTE Registry laufen und gibt (Rueckgabe, Funde)."""
    import contextlib
    import io
    echt = sources.REGISTRY
    sources.REGISTRY = registry
    sonde.fehler, sonde.hinweise = 0, 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = sonde.main([])
    finally:
        sources.REGISTRY = echt
    return rc, [z.strip() for z in buf.getvalue().splitlines() if z.strip().startswith("\u2717")]


def test_ein_zu_altes_pruefdatum_schlaegt_an():
    import dataclasses
    import datetime as dt
    R = list(sources.REGISTRY)
    s = next((x for x in R if x.status == "sondiert"), None)
    if s is None:
        pytest.skip("keine sondierte Quelle im Register")
    alt = (dt.date.today() - dt.timedelta(days=400)).isoformat()   # Frist fuer sondiert: 365
    rc, funde = _fahre([dataclasses.replace(x, geprueft=alt) if x.id == s.id else x for x in R])
    assert rc == 1 and any(s.id in f for f in funde), (
        f"Ein 400 Tage altes Pruefdatum wurde nicht gemeldet. Funde: {funde}")


def test_ein_unlesbares_pruefdatum_schlaegt_an_AUCH_OHNE_FRIST():
    """⚠ Der eigentliche Fehler des ersten Entwurfs: `live` hat keine Frist, und genau
    deshalb wurde das Format dort nie geprueft."""
    import dataclasses
    R = list(sources.REGISTRY)
    l = next(x for x in R if x.status == "live")
    rc, funde = _fahre([dataclasses.replace(x, geprueft="letzten Dienstag") if x.id == l.id else x
                        for x in R])
    assert rc == 1 and any("ISO" in f for f in funde), (
        f"Ein unlesbares Datum auf einer live-Quelle wurde nicht gemeldet. Funde: {funde}")


def test_ein_pruefdatum_in_der_zukunft_schlaegt_an():
    """Ein Datum von morgen ist keine Pflege, sondern ein Tippfehler oder eine Behauptung."""
    import dataclasses
    R = list(sources.REGISTRY)
    l = next(x for x in R if x.status == "live")
    rc, funde = _fahre([dataclasses.replace(x, geprueft="2099-01-01") if x.id == l.id else x
                        for x in R])
    assert rc == 1 and any("ZUKUNFT" in f for f in funde), (
        f"Ein Datum in der Zukunft wurde nicht gemeldet. Funde: {funde}")


def test_die_unveraenderte_registry_bleibt_gruen():
    """Gegenrichtung: ohne gepflanzten Fehler darf die Sonde NICHT anschlagen — sonst waere
    sie eine Funktion, die immer meldet, und die drei Tests darueber waeren wertlos."""
    rc, funde = _fahre(list(sources.REGISTRY))
    assert rc == 0 and not funde, f"Die Sonde meldet ohne gepflanzten Fehler: {funde}"

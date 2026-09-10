"""Welche drei Dokument-Abrufer je Runde drankommen (`scripts/waehle_abrufer.sh`).

⚠ WARUM ES DIESE DATEI GIBT. Die Regel stand dreimal geändert im Arbeiter-Skript und war
nie geprüft. Am 2026-09-10 ist sie eingefroren, ohne dass irgendetwas rot wurde: es lagen
exakt drei Abrufer über der Untergrenze, und `2 + (RUNDE-1) % (3-2)` ist **immer 2**. Der
dritte Platz stand damit fest auf `netserver`. An einem Tag gemessen: 143 Runden, davon
netserver 140, evergabe 3, die übrigen acht **null** — während die drei oben in fast jeder
Runde „0 offen" meldeten und ihre 182 erreichbaren Vorgänge liegen blieben.

Eine Rotation, die nicht rotiert, sieht im Protokoll aus wie eine, die rotiert. Nur die
Namen wiederholen sich.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WAEHLE = ROOT / "scripts" / "waehle_abrufer.sh"

# Die echte Lage vom 2026-09-10: Name, erwartete Ausbeute, roher Rückstau.
LAGE = """cosinex\t1485\t2007
subreport\t594\t812
netserver\t348\t461
evergabe_online\t43\t44
evergabe\t37\t40
ausschreibungsblatt\t33\t35
staatsanzeiger\t23\t46
bimedien\t20\t40
aumass\t14\t32
healyhudson\t10\t40
simap_docs\t2\t3
lu\t0\t0
vergabeportal_at\t0\t0
"""


def waehle(runde: int, tabelle: str = LAGE, **umgebung) -> list[str]:
    r = subprocess.run([str(WAEHLE), str(runde)], input=tabelle, capture_output=True,
                       text=True, env={"PATH": "/usr/bin:/bin", **umgebung})
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def test_die_zwei_grossen_stehen_fest():
    """Platz 1 und 2 gehen an den Rückstau — das war und bleibt die Regel."""
    for runde in range(1, 12):
        assert waehle(runde)[:2] == ["cosinex", "subreport"]


def test_der_dritte_platz_rotiert_wirklich():
    """⚠ Der Fall vom 2026-09-10: hier stand achtmal hintereinander `netserver`."""
    dritte = [waehle(r)[2] for r in range(1, 9)]
    assert len(set(dritte)) == 8, f"Der dritte Platz wiederholt sich: {dritte}"


def test_jeder_mit_lohnendem_rueckstau_kommt_dran():
    """Nach einem vollen Umlauf darf keiner fehlen, bei dem sich eine Stunde lohnt."""
    gesehen = {waehle(r)[2] for r in range(1, 20)}
    erwartet = {"netserver", "evergabe_online", "evergabe", "ausschreibungsblatt",
                "staatsanzeiger", "bimedien", "aumass", "healyhudson"}
    assert gesehen == erwartet, f"fehlt: {erwartet - gesehen}, zuviel: {gesehen - erwartet}"


def test_wer_zu_wenig_hat_bleibt_draussen():
    """⚠ Die Lehre vom 2026-08-22, die nicht verloren gehen darf: der dritte Platz ging an
    `aumass` mit EINEM offenen Vorgang, und vier von sechs Runden verschenkten ihre Stunde.
    `simap_docs` (3) und die Nuller dürfen nicht in die Rotation."""
    gesehen = {n for r in range(1, 20) for n in waehle(r)}
    for klein in ("simap_docs", "lu", "vergabeportal_at"):
        assert klein not in gesehen, f"{klein} bekommt eine Stunde für fast nichts."


def test_der_zweite_platz_wird_nicht_doppelt_vergeben():
    """Ohne Ausschluss stünde derselbe Name zweimal in der Runde — und ein Abrufer liefe
    zweimal gleichzeitig gegen dasselbe Portal."""
    for runde in range(1, 20):
        d = waehle(runde)
        assert len(d) == len(set(d)), f"Runde {runde}: {d}"


def test_reicht_es_nicht_fuer_zwei_grosse_ruecken_die_kleinen_nach():
    """Sonst steht der Schritt still, sobald der Rückstau abgearbeitet ist."""
    schmal = "evergabe\t37\t40\nausschreibungsblatt\t33\t35\nstaatsanzeiger\t23\t46\n"
    d = waehle(1, schmal)
    assert len(d) == 3 and set(d) == {"evergabe", "ausschreibungsblatt", "staatsanzeiger"}


def test_ohne_messung_bleibt_der_arbeiter_nicht_stehen():
    """Fehlt die Tabelle ganz (Abfrage kaputt), muss trotzdem etwas drankommen."""
    d = waehle(1, "")
    assert len(d) == 3, d


def test_die_untergrenzen_sind_stellbar():
    """Beide Schwellen gehören in die Umgebung, nicht in den Quelltext — sie sind an
    Messungen gebunden, und Messungen ändern sich."""
    d = waehle(1, LAGE, ABRUF_MINDEST="2000", ABRUF_MINDEST_KLEIN="800")
    # Nur cosinex liegt über 2000 → die Kleinen rücken nach, Rotation über >= 800.
    assert d[:2] == ["cosinex", "subreport"], d


def test_der_arbeiter_benutzt_die_ausgelagerte_regel():
    """Die Regel darf nicht an zwei Stellen leben — genau so ist sie eingefroren."""
    arbeiter = (ROOT / "scripts" / "dokumente_arbeiter.sh").read_text(encoding="utf-8")
    assert "waehle_abrufer.sh" in arbeiter
    assert "% (${#SORTIERT[@]} - 2)" not in arbeiter, "Die alte Rechnung steht noch da."

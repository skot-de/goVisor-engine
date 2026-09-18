"""Gespeicherte Filter (`web/lib/filterMischen.js`, `supabase/0022`).

Der gefaehrlichste Teil am Speichern ist nicht das Speichern, sondern das LADEN eines alten
Filters. `Adv` waechst; ein Zustand von heute muss in sechs Monaten noch aufgehen. Ohne
Mischung laedt er SCHEINBAR sauber und filtert anders: kein Fehler, keine Meldung, nur eine
falsche Liste.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-filtermischen.mjs"


def test_die_mischung_haelt_alle_faelle():
    """Faehrt die ECHTE `mischen`-Funktion, nicht ihren Quelltext.

    ⚠ Eine Wortpruefung waere hier wertlos, aus demselben Grund, der im Kopf von
    `filterMarken.js` steht: sie bleibt gruen, wenn die Logik daneben kaputtgeht. Deshalb
    liegt `mischen` in reinem JS und wird hier ausgefuehrt.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Mischung haelt alle Faelle" in r.stdout


def test_die_sonde_wird_rot_wenn_die_mischung_faellt():
    """Gegenprobe: ein Waechter, der nie rot werden kann, ist keiner.

    Genau diese Falle steht in `test_analyse_sichtbar.py` beschrieben — ein Waechter blieb
    gruen, nachdem Aufruf UND Import entfernt worden waren.
    """
    if not shutil.which("node"):
        return
    quelle = (WURZEL / "web" / "lib" / "filterMischen.js").read_text(encoding="utf-8")
    kaputt = quelle.replace(
        "if (Array.isArray(alt) !== Array.isArray(neu)) continue;", "")
    assert kaputt != quelle, "die Typpruefung steht nicht mehr da, wo der Test sie sucht"
    sicherung = WURZEL / "web" / "lib" / "filterMischen.js"
    original = sicherung.read_text(encoding="utf-8")
    try:
        sicherung.write_text(kaputt, encoding="utf-8")
        r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
        assert r.returncode != 0, "die Sonde blieb gruen, obwohl die Typpruefung fehlt"
    finally:
        sicherung.write_text(original, encoding="utf-8")


def test_die_migration_legt_die_schlafende_spalte_an():
    """`benachrichtigen` ist absichtlich tot und muss trotzdem existieren.

    Ein gespeicherter Filter ist der natuerliche Traeger fuer „sag mir Bescheid";
    `user_alert_settings` kann das nicht, sie ist EINE Zeile je Nutzer. Die Spalte steht
    jetzt da, damit die spaetere Verdrahtung keine Bestandsdaten anfassen muss.
    """
    sql = (WURZEL / "supabase" / "0022_gespeicherte_filter.sql").read_text(encoding="utf-8")
    assert "benachrichtigen" in sql
    assert "fassung" in sql, "ohne Fassung laesst sich ein alter Zustand nicht einordnen"
    assert "row level security" in sql.lower()

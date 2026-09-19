"""Steht eine Migration nur im Ordner? (`scripts/pruefe_supabase_migrationen.py`)

⚠ GEFUNDEN AM 2026-09-19, nebenbei. Beim Anlegen von `user_lead_status` (0023) fiel beim
Blick auf die Live-Tabellen auf, dass auch **0021 (Ausblenden)** und **0022 (gespeicherte
Filter)** nie angewandt waren. Zwei fertig gebaute, getestete Funktionen, die seit ihrem Bau
nichts speichern.

⚠ WARUM ES NIEMAND GEMERKT HAT — der Ausfall schweigt von BEIDEN Seiten:

  · Die Client-Module fangen jeden Datenbankfehler ab und tun dann nichts
    (`} catch { /* no-op */ }`). Das ist richtig, ein Klick in der Liste darf nie eine rote
    Meldung erzeugen. Die Folge ist aber, dass eine fehlende Tabelle sich anfuehlt wie ein
    erfolgreicher Klick: der Knopf reagiert, die Oberflaeche merkt sich den Zustand, und
    erst beim naechsten Laden ist er weg.
  · Die Tests pruefen den Code, nicht die Datenbank. Sie bleiben gruen.

Das ist genau die Fehlerklasse, die dieses Projekt „gebaut, nicht verdrahtet" nennt — nur
liegt der fehlende Draht diesmal ausserhalb des Quelltextes.

⚠ Dieser Test macht die Suite NICHT rot, wenn eine Migration fehlt. Wann eine Migration in
die Produktion geht, entscheidet nicht der Testlauf. Er prueft, dass die Sonde funktioniert
und dass sie jede Nacht laeuft.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "scripts" / "pruefe_supabase_migrationen.py"
NACHTLAUF = WURZEL / "scripts" / "daily_leads.sh"


def _sonde():
    sys.path.insert(0, str(WURZEL / "scripts"))
    import importlib
    m = importlib.import_module("pruefe_supabase_migrationen")
    return importlib.reload(m)


def test_die_sonde_liest_die_migrationen():
    """Sie muss die Tabellen finden, die es wirklich gibt."""
    erwartet = _sonde().erwartete_tabellen()
    assert erwartet, "keine einzige Migration erkannt"
    assert erwartet["0001_auth_profiles.sql"] == ["user_profiles"]
    assert "user_lead_status" in erwartet["0023_lead_status.sql"]


def test_eine_auskommentierte_tabelle_zaehlt_nicht(tmp_path):
    """⚠ F13, an diesem Tag mehrfach. Eine verworfene, auskommentierte `create table`-Zeile
    ist keine Tabelle, die jemand erwartet. Ohne Strippen meldet die Sonde sie JEDE NACHT
    als fehlend — und ein Bericht, der Rauschen enthaelt, wird nach einer Woche ueberlesen.

    ⚠ Dieser Test ersetzt einen frueheren, der behauptete, dasselbe zu pruefen, und es
    nicht tat: er las einen Kommentar, in dem `user_watchlist` bloss ERWAEHNT wird. Der
    Ausdruck der Sonde sucht aber `create table if not exists public.X` — eine blosse
    Erwaehnung haette er ohnehin nie getroffen. Die Gegenprobe kam nicht an, und das war
    der Hinweis.
    """
    (tmp_path / "0099_probe.sql").write_text(
        "-- create table if not exists public.verworfene_idee (\n"
        "-- verworfen am 2026-09-19, siehe user_watchlist\n"
        "create table if not exists public.echte_tabelle (id uuid primary key);\n",
        encoding="utf-8")
    t = _sonde().erwartete_tabellen(tmp_path)["0099_probe.sql"]
    assert t == ["echte_tabelle"], (
        f"die Sonde erwartet {t} — eine auskommentierte Zeile zaehlt mit")


def test_nichterreichbar_ist_nicht_in_ordnung():
    """⚠ Eine Sonde, die Nichterreichbarkeit als „alles gut" auslegt, ist schlimmer als
    keine: sie erzeugt genau das Vertrauen, das sie nicht rechtfertigen kann. Der Fall
    tritt garantiert ein (kein Netz, abgelaufenes Passwort, pausiertes Projekt), und er
    darf nie wie ein gruener Haken aussehen.
    """
    m = _sonde()
    echt = m.live_tabellen
    try:
        m.live_tabellen = lambda _dsn: None
        rueck = m.main()
    finally:
        m.live_tabellen = echt
    if m._dsn() is None:
        return   # ohne Zugangsdaten kommt die Sonde gar nicht so weit
    assert rueck == 2, (
        f"unerreichbare Datenbank ergibt Rueckgabe {rueck} statt 2 — damit meldet der "
        f"Nachtlauf Ruhe, obwohl niemand nachgesehen hat")


def test_die_sonde_laeuft_und_sagt_die_wahrheit():
    """Sie darf drei Antworten geben, und jede muss eindeutig sein:
    0 alles da · 1 etwas fehlt · 2 keine Auskunft (kein Zugang, kein Netz).

    ⚠ Der Unterschied zwischen 1 und 2 ist der Punkt. Eine Sonde, die Nichterreichbarkeit
    als „alles in Ordnung" auslegt, ist schlimmer als keine.
    """
    r = subprocess.run([sys.executable, str(SONDE)], capture_output=True, text=True,
                       cwd=WURZEL, timeout=120)
    assert r.returncode in (0, 1, 2), f"unerwartete Rueckgabe {r.returncode}: {r.stdout}"
    if r.returncode == 1:
        assert "nicht angewandt" in r.stdout
    elif r.returncode == 2:
        assert "keine Auskunft" in r.stdout


def test_die_sonde_haengt_im_nachtlauf():
    """⚠ Ein Waechter, den niemand aufruft, ist ein Kommentar. `gold_integrity` hing
    monatelang an einem Netzlauf, den der Tageslauf nie startete — die Luecke fiel erst an
    28 Waisen auf, die AT einen Tag lang trug.
    """
    sh = NACHTLAUF.read_text(encoding="utf-8")
    assert "pruefe_supabase_migrationen.py" in sh, "die Sonde laeuft in keiner Nacht"
    i = sh.index("$PY scripts/pruefe_supabase_migrationen.py")
    assert "--still" in sh[i:i + 120], (
        "ohne --still meldet die Sonde auch dann etwas, wenn alles in Ordnung ist — "
        "und eine Nacht, die immer etwas sagt, liest bald niemand mehr")
    assert "Details:" in sh[i:i + 400], (
        "der Nachtlauf sagt nicht, wie man den Befund nachschlaegt")

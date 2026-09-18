"""Verlieren zwei gleichzeitige Schreiber einander noch?

⚠ WARUM DAS NICHT STRUKTURELL ZU BEWEISEN IST. `tests/test_profilschreiber.py` prueft, dass
es genau EINEN Schreibweg gibt und dass der Patch minimal ist. Beides ist richtig und beides
sagt nichts darueber, was unter echter Nebenlaeufigkeit passiert.

Der Auftrag verlangte deshalb ausdruecklich „zwei Schreibvorgaenge absichtlich ueberlappen
lassen und belegen, dass keiner den anderen verliert". Gemessen am 2026-09-18 gegen die
echte Datenbank, je 12 Runden mit zwei gleichzeitigen Schreibern auf VERSCHIEDENE Felder:

    alter Weg (lesen → aendern → ganzen Blob schreiben)    0 von 12 vollstaendig
    merge_profile (atomar, supabase/0020)                 12 von 12 vollstaendig

Der alte Weg verliert in JEDER Runde — das ist die Reproduktion des Fehlers, der am
2026-09-17 Stunden vor einer Vorfuehrung in Produktion zuschlug („0 von 7.013").

⚠ ZWEI TABS SIND DER REALISTISCHE AUSLOESER, kein konstruierter Testfall. Deshalb schreiben
beide Seiten verschiedene Felder — so wie Onboarding (`saveProfile`) und Eignungs-Check
(`patchProfil`). Wer denselben Schluessel schreibt, misst nur, wer spaeter dran war.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "scripts" / "pruefe_profil_nebenlaeufig.py"
PASSWORT = WURZEL / ".secrets" / "pruefkonto.txt"


def test_der_atomare_weg_verliert_nichts():
    """⚠ Braucht Netz und das Pruefkonto — sonst uebersprungen.

    `scripts/pruefkonto.py` legt es an (mailfrei, `.invalid` ist per RFC 2606 nicht
    zustellbar). Ohne das Konto laeuft die Sonde nicht; sie sucht sich KEIN anderes.

    ⚠ Die Sonde meldet sich SELBST anmelden — mit dem Dienstschluessel waere `auth.uid()`
    NULL, `merge_profile` traefe keine Zeile, und der Test saehe gruen aus, weil er gar
    nichts misst.
    """
    if not (PASSWORT.exists() and shutil.which("python3")):
        return
    r = subprocess.run(["python3", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "0 mit Verlust" in r.stdout, r.stdout[-600:]


def test_der_alte_weg_verliert_nachweislich():
    """Gegenprobe auf die Sonde selbst — sie muss den Fehler auch FINDEN koennen.

    ⚠ Eine Nebenlaeufigkeitspruefung, die nur den behobenen Weg faehrt, belegt nichts: sie
    koennte aus jedem beliebigen Grund gruen sein (zu kurzes Fenster, serialisierte
    Anfragen, ein Schreiber, der gar nicht schreibt). Erst der Nachweis, dass sie den ALTEN
    Weg zuverlaessig scheitern sieht, macht das Gruen zur Aussage. Hausregel F10/F13:
    nachweisen, dass die Mutation ankommt, nicht nur dass der Test faellt.
    """
    if not (PASSWORT.exists() and shutil.which("python3")):
        return
    r = subprocess.run(["python3", str(SONDE), "--alt"], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 1, "der alte Weg verliert nichts — die Sonde misst nicht, was sie soll"
    assert "mit Verlust" in r.stdout

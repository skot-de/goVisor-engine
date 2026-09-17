"""Behauptet die Passung eine Feinheit, die sie nicht hat?

⚠ WARUM DIESE DATEI EXISTIERT. `passung` wird aus vier Zuschlaegen in Halbschritten
gebaut und kann deshalb nur ACHT Werte annehmen:

    s      2,0  2,5  3,0  3,5  4,0  4,5  5,0  5,5
    Zahl     0   14   29   43   57   71   86  100

Angezeigt wurde „86/100" — das sieht aus wie ein Prozentsatz mit hundert Abstufungen.
86 ist die haeufigste der acht: Feld, Region und Volumen passen, kein Zielrichtungsbonus,
also der Normalfall eines gut passenden Leads.

Gemeldet am 2026-09-17: „alle leads haben relevanz 86, kann auch nicht sein oder?"

⚠ DER KOMMENTAR IM CODE WUSSTE ES BEREITS. Ueber `passungAchse` stand seit jeher: „Sie
kennt genau acht Werte … eine feinere Darstellung wuerde Genauigkeit behaupten, die es
nicht gibt." Darunter wurde `86/100` gezeichnet. Die Begruendung daneben wehrte nur das
Prozentzeichen ab, nicht die Skala — ein Nenner von 100 behauptet hundert Abstufungen,
ob ein % danebensteht oder nicht. Wissen im Kommentar ersetzt keine Pruefung.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-passungsstufe.mjs"


def test_die_sonde_laeuft_gruen():
    """Faehrt die ECHTE Rechnung (`passungsZahl`, `passungsStufe`, `matchLead`).

    ⚠ Geprueft wird NICHT „es sind genau acht Stufen" — das waere eine Abschrift der
    Rechnung. Geprueft wird: die ANZEIGE verspricht nicht mehr Abstufungen, als die
    Rechnung hergibt. Wer die Rechnung verfeinert, darf die Anzeige mitverfeinern; wer
    nur die Anzeige aufblaest, wird rot.

    Gegengeprueft am 2026-09-17: rot, wenn (a) „/100" in die Anzeige zurueckkehrt,
    (b) mehr Segmente gezeichnet werden als es Stufen gibt, (c) Stufe und Zahl eine
    andere Reihenfolge ergeben — dann fielen Anzeige und Sortierung auseinander.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "verspricht genau so viele Abstufungen" in r.stdout


def test_die_zahl_bleibt_fuer_die_sortierung():
    """Die Stufe ist die Aussage, die Zahl sortiert — beides muss bleiben.

    ⚠ Waere `passung` entfernt worden, sortierte die Spalte „Relevanz" nach nichts mehr:
    `case 'relevanz'` in `explorerCore.js` liest genau dieses Feld. Der Kopf von
    `passungsZahl` sagt es seit jeher: „die STUFE bleibt die Aussage; die Zahl dient dem
    Sortieren und einem Mindestwert."
    """
    core = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
    assert "l.passung = m.passung" in core, "die Rangzahl wird nicht mehr gesetzt"
    assert "l.passungStufe = m.stufe" in core, "die Stufe wird nicht mehr gesetzt"
    i = core.index("case 'relevanz':")
    assert "passung" in core[i:i + 120], "die Sortierung liest die Rangzahl nicht mehr"

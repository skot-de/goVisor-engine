"""Filtert der Zeithorizont nach dem, was die Liste ANZEIGT?

⚠ WARUM DIESE DATEI EXISTIERT. Ein Lead traegt bis zu zwei Daten — `tage`
(Angebotsfrist) und `endTage` (Vertragsende) — und drei Stellen ordneten sie bis zum
2026-09-17 verschieden: die Spalte und die Sortierung nahmen `tage` zuerst, der
Zeithorizont-Filter `endTage`. Ein Lead mit `tage: 4` und `endTage: 800` stand sichtbar
mit „4 Tage" in der Liste und fiel aus dem Ein-Monats-Filter.

Gemessen: 6.041 Leads (13,8 %) tragen diese Kombination; der Ein-Monats-Filter zeigte
8.214 statt 15.092.

Aufgefallen ist es nicht durch einen Test, sondern durch einen Nutzer: „wenn ich nach
Vertragsende 1 Monat filtere, zeigt er mir nur zwei Leads mit 8 Tagen Frist, geh ich auf
egal sind da noch viele andere mit 4 Tagen."
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-zeithorizont.mjs"


def test_die_sonde_laeuft_gruen():
    """Faehrt `handlungsFrist` und `fristCell` aus `explorerCore.js` gegen echte Leads.

    ⚠ Geprueft wird NICHT „die Reihenfolge ist tage-zuerst" — das waere eine Abschrift
    der Regel und ginge gruen, sobald jemand sie an EINER Stelle dreht. Geprueft wird die
    Eigenschaft: was die Spalte zeigt, danach siebt der Filter. Wer die Regel bewusst
    umdreht, muss beide Stellen gemeinsam drehen.

    Gegengeprueft am 2026-09-17: rot, wenn (a) `handlungsFrist` umgedreht wird (meldet
    dann die 6.955 betroffenen Leads namentlich), (b) der Filter wieder eine eigene
    `endTage`/`tage`-Kette baut.
    """
    if not shutil.which("node") or not list((WURZEL / "web" / "data").glob("leads-*.json")):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Der Filter siebt nach dem, was die Liste zeigt" in r.stdout

"""Findet die Suche, was sie hinterher als Fundort ausweist?

⚠ WARUM DIESE DATEI EXISTIERT. `leadText` baut den durchsuchten Text, `fundstelle`
erklaert hinterher, WO das Wort stand. Bis zum 2026-09-17 kannten beide verschiedene
Felder: `fundstelle` konnte „Vergabenummer" und „Los N" melden, `leadText` durchsuchte
weder das eine noch das andere. Zwei tote Zweige — und Vorgaenge, deren Ort nur im
Los-Titel steht, waren unauffindbar. Bei Mehrlos-Vergaben ist das der Normalfall: der
Haupttitel heisst dann „Neubau Verwaltungsgebaeude, Lose 1-7".

Gemessen: „rottweil" 19 → 22 Treffer, „hamm" 72 → 86. 68 % der Bau-Leads tragen Lose.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-suchfelder.mjs"
DEMO = WURZEL / "web" / "scripts" / "pruefe-demoworte.mjs"


def test_suche_und_fundort_kennen_dieselben_felder():
    """Jeder Fundort, den `fundstelle` melden kann, muss durch eine Suche erreichbar sein —
    und jeder Volltext-Treffer muss einen Beleg bekommen.

    „Ohne diesen Beleg wirken Volltext-Treffer wie Fehler" steht im Kopf von `fundstelle`;
    genau dieser Zustand entstuende, wenn die Nummer im Heuhaufen liegt, der Beleg aber
    nur exakt vergleicht.

    Gegengeprueft am 2026-09-17: rot, wenn (a) die Lose aus `leadText` fallen, (b) der
    Beleg fuer Nummern-Teiltreffer entfernt wird.
    """
    if not shutil.which("node") or not list((WURZEL / "web" / "data").glob("leads-*.json")):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Suche und Fundort kennen dieselben Felder" in r.stdout


def test_drehbuchworte_finden_im_demosatz_etwas():
    """⚠ Der Vollbestand sagt nichts ueber das, was in einer Vorfuehrung sichtbar ist.

    Am 2026-09-17 wurde mitten in einer Vorfuehrung „such nach Ubstadt" empfohlen —
    geprueft war der Vollbestand, im geduennten Demo-Satz kommt das Wort nicht vor. Die
    Suche lief ins Leere und sah aus wie ein Suchfehler.

    Beim ersten Lauf meldete diese Pruefung sofort einen zweiten Fall: `klostermann` stand
    im Drehbuch, liegt aber in `suppliers.json` und nicht in den Leads.
    """
    if not shutil.which("node") or not (WURZEL / "web" / "data-demo").exists():
        return
    r = subprocess.run(["node", str(DEMO)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Jedes Drehbuchwort findet etwas" in r.stdout

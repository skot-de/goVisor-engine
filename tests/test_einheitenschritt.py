"""Stellt der Einheiten-Schritt eine Frage, wo es nichts zu fragen gibt?

⚠ WARUM DIESE DATEI EXISTIERT. Schritt 3 des Onboardings fragt „Gehoeren diese Einheiten
zu euch?". Bei EINER Einheit ist das keine Frage, sondern eine Liste mit einem Eintrag,
ueber den in Schritt 2 gerade entschieden wurde.

⚠ DER SCHRITT WIRD NICHT UEBERSPRUNGEN, und das ist der Kern. Eine erste Fassung vom
2026-09-17 sprang bei einer belegten Einheit direkt zu „fertig" — die falsche Loesung. Der
Schritt traegt die Zusage „Mit der Bestaetigung merken wir uns diese Einheiten als eure
Identitaet. {n} Siege fliessen in euer Profil."; das ist die Stelle, an der aus „wir kennen
euch" ein Profil wird. Sie wegzulassen waere schlechter als eine unpassende Ueberschrift.

Gemessen am 2026-09-18, zwei Grundmengen — beide richtig, verschiedene Fragen:

    alle DE-Identitaeten (entity_identity.parquet)  304.994 · 96,9 % mit EINER Einheit
    Firmen, die das Onboarding findet (suppliers)    37.948 · 79,5 % mit EINER Einheit

Die zweite ist die einschlaegige: Schritt 3 erreicht nur, wer in Schritt 2 einen Treffer
aus `suppliers.json` bestaetigt hat. ⚠ Ich hatte die erste Zahl als falsch bezeichnet —
sie war es nicht, ich hatte eine andere Grundmenge gemessen.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-einheitenschritt.mjs"


def test_die_sonde_laeuft_gruen():
    """Faehrt die ECHTE Regel `hatEtwasZuEntscheiden` gegen fuenf Faelle.

    ⚠ ZWEI DINGE, DIE SIE FESTHAELT. Erstens: uebersprungen wird nur bei einer BELEGTEN
    Einheit. Ist sie blosse Selbstauskunft, traegt der Schritt eine Warnung („diese
    Zuschlaege zaehlen als eure Historie"), und sie stillschweigend zu uebergehen hiesse,
    eine Zustimmung anzunehmen, die niemand gegeben hat. Zweitens: BEIDE Wege in den
    Bildschirm (normaler Pfad und Token-Pfad) benutzen dieselbe Regel — auf dem
    Token-Pfad stand `anzahl > 1` ohne Belegpruefung, die zwei Regeln waren bereits
    auseinandergelaufen.

    Gegengeprueft am 2026-09-18: rot, wenn (a) der Schritt wieder uebersprungen wird,
    (b) die Scheinfrage zurueckkehrt, (c) der Text verspricht, eine Einheit spaeter zu
    ERGAENZEN — das kann das Produkt nicht, `EntityKorrektur` ersetzt nur die Zuordnung.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Der Schritt bleibt, und er fragt nur, wo es etwas zu fragen gibt" in r.stdout


def test_die_beleglage_wandert_weiter_ins_profil():
    """Uebersprungen wird die FRAGE, nicht die Erfassung.

    ⚠ `confirmedEntities` muss auch im uebersprungenen Fall gefuellt werden, und zwar mit
    der richtigen Beleglage. Die Plausibilitaetsbremse vom 2026-08-21 haelt fest: der
    BELEG wandert mit ins Profil, nicht nur der Name — sonst ist nach dem Speichern nicht
    mehr unterscheidbar, welcher Teil des Bestands belegt ist und welcher blosse
    Selbstauskunft.
    """
    seite = (WURZEL / "web" / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    i = seite.index("confirmedEntities:")
    block = seite[i:i + 400]
    assert "beleg:" in block, "confirmedEntities traegt die Beleglage nicht mehr"
    assert "kennung" in block and "selbstauskunft" in block, (
        "die beiden Beleg-Auspraegungen fehlen — der Unterschied waere nach dem Speichern weg")
    # `aktiv` wird in `ladeMitglieder` gesetzt, also VOR dem Sprung — auch im
    # uebersprungenen Fall steht die Auswahl bereit.
    lade = seite[seite.index("const ladeMitglieder"):]
    assert "setAktiv(" in lade[:lade.index("\n  }, [")], (
        "`aktiv` wird nicht mehr beim Laden gesetzt — im uebersprungenen Fall waere es leer")

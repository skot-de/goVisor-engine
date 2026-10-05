"""Fremdzitate im Wettbewerbspapier tragen Quelle und Lesedatum — oder sind als offen geführt.

⚠ WARUM. Das Papier zitiert vier fremde Firmen wörtlich (AGB-Passagen, Werbeaussagen,
Produktbeschreibungen), und bei keinem Zitat stand, wann und woher es stammt. In diesem Haus
ist dafür eine Falle dokumentiert: **Abruf-Werkzeuge erfinden Zitate**, weshalb bei jeder
Recherche festgehalten wird, ob der ROHTEXT gesehen wurde.

⛔ Das Risiko ist nicht Ungenauigkeit. Auf einem AGB-Zitat ruht ein ganzer Abschnitt des
Papiers. Liegt es daneben, steht eine falsche Tatsachenbehauptung über einen Wettbewerber in
einem Papier, das an Vertrieb und Kunden geht.

Diese Prüfung hält zwei Dinge:

1. Solange die Prüfliste Lücken hat, muss die Warnung oben stehen.
2. Sobald sie vollständig ist, muss die Warnung WEG — sonst steht dort dauerhaft „ungeprüft"
   über einem geprüften Papier, und niemand glaubt der Warnung noch.

⚠ Die zweite Richtung ist die wichtigere: ein Hinweis, der immer dasteht, wird genauso
überlesen wie ein Wächter, der immer rot ist.
"""
from __future__ import annotations

import pathlib
import re

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
PAPIER = WURZEL / "docs" / "wettbewerb-und-positionierung.md"

WARNUNG = "UNGEPRÜFT: alle wörtlichen Zitate vom Wettbewerb"
UEBERSCHRIFT = "## Zu prüfende Zitate"


def _liste() -> list[list[str]]:
    """Die Zeilen der Prüftabelle, in Spalten zerlegt."""
    text = PAPIER.read_text(encoding="utf-8")
    teil = text.split(UEBERSCHRIFT, 1)[1]
    zeilen = []
    for z in teil.splitlines():
        z = z.strip()
        if not z.startswith("|") or set(z) <= set("|- "):
            continue
        spalten = [s.strip() for s in z.strip("|").split("|")]
        if spalten and spalten[0].isdigit():
            zeilen.append(spalten)
    return zeilen


def test_die_liste_gibt_es_und_sie_ist_nicht_leer():
    assert PAPIER.exists(), "das Papier fehlt"
    assert UEBERSCHRIFT in PAPIER.read_text(encoding="utf-8"), "die Prüfliste fehlt"
    assert _liste(), "die Prüfliste hat keine Zeilen"


def test_jede_zeile_nennt_zitat_und_zuschreibung():
    """Ein Zitat ohne Zuschreibung ist nicht prüfbar — niemand weiss, wo er nachsehen soll."""
    for z in _liste():
        nr, zitat, wem = z[0], z[1], z[2]
        assert len(zitat) > 10, f"Zeile {nr}: kein Zitat"
        assert len(wem) > 3, f"Zeile {nr}: keine Zuschreibung"


def test_warnung_steht_solange_etwas_offen_ist():
    """⚠ Die eigentliche Zusage: offen und still gibt es nicht zusammen."""
    text = PAPIER.read_text(encoding="utf-8")
    offen = [z for z in _liste() if not (z[4].strip() and z[5].strip())]
    if offen:
        assert WARNUNG in text, (
            f"{len(offen)} Zitat(e) ohne Quelle oder Lesedatum, aber die Warnung oben fehlt — "
            "dann liest jemand das Papier als geprüft. Offen: "
            + ", ".join(z[0] for z in offen))
    else:
        assert WARNUNG not in text, (
            "alle Zitate sind belegt, aber die Warnung steht noch. Ein Hinweis, der immer "
            "dasteht, wird überlesen wie ein dauerrot stehender Wächter — bitte entfernen.")


def test_das_schwerste_zitat_ist_als_solches_markiert():
    """Die AGB-Zitate tragen einen ganzen Abschnitt. Wer die Liste kürzt, soll sehen, was
    daran hängt, bevor er eine Zeile streicht."""
    schwer = [z for z in _liste() if "⛔" in z[3]]
    assert schwer, "kein Zitat ist als tragend markiert — die Spalte „trägt\" ist dann Zierde"
    assert any("AGB" in z[2] for z in schwer), (
        "die AGB-Zitate sind nicht als tragend geführt, obwohl ein ganzer Abschnitt auf ihnen "
        "ruht")


def test_kein_fremdzitat_ausserhalb_der_liste_ohne_beleg():
    """⚠ SELBSTPROBE DER VOLLSTAENDIGKEIT, und sie ist absichtlich grob.

    Geprüft wird: trägt das Papier ungefähr so viele Zitate, wie die Liste führt? Eine exakte
    Zuordnung wäre eine zweite Regex-Wache mit allen Fallen, die dieses Haus schon kennt
    (Prosa statt Code, eigene Formulierungen in Anführungszeichen). Die grobe Zahl fängt den
    Fall, der zählt: jemand fügt ein neues Fremdzitat ein und trägt es nicht nach.
    """
    text = PAPIER.read_text(encoding="utf-8")
    vor_liste = text.split(UEBERSCHRIFT, 1)[0]
    zitate = re.findall(r"[„\"]([^„\"“”]{12,200})[\"“”]", vor_liste)
    assert zitate, "keine Zitate gefunden — die Suche greift nicht mehr"
    # Deutlich mehr Zitate im Text als Zeilen in der Liste? Dann ist etwas dazugekommen.
    assert len(zitate) < len(_liste()) * 5, (
        f"{len(zitate)} Zitate im Text gegen {len(_liste())} Zeilen in der Liste — "
        "wurde ein Fremdzitat eingefügt, ohne es einzutragen?")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

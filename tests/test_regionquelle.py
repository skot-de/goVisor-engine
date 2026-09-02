"""Die Herkunft der Region gehört an den Wert.

⚠ `regionQuelle` lag seit jeher an 42.660 Leads und wurde im Frontend NIRGENDS gelesen.
Gemessen am 2026-09-02: 69,3 % amtlich, **25,6 % von uns abgeleitet**, 0,4 % widersprüchlich,
4,8 % ohne Angabe. Ein Viertel aller Bundesländer in der Liste hat also niemand
veröffentlicht, sondern wir haben es aus dem Namen der Vergabestelle erschlossen.

Die Begründung stand die ganze Zeit im Export selbst: „Ein stillschweigend ergänzter Wert
sieht aus wie eine Quelle — und danach wird gefiltert."
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")


def test_die_spalte_liest_die_herkunft():
    block = CORE[CORE.index("case 'region':"):CORE.index("case 'inc':")]
    assert "l.regionQuelle" in block, "die Spalte zeigt den Wert ohne seine Herkunft"


def test_abgeleitet_und_widerspruechlich_sehen_verschieden_aus():
    """⚠ Abgeleitet heisst NICHT falsch: wir haben es erschlossen, und meistens stimmt es.
    Widersprüchlich heisst, dass eine andere Angabe derselben Quelle dagegen spricht. Beides
    gleich zu markieren wäre eine Vermischung, die dem Nutzer nicht hilft."""
    block = CORE[CORE.index("case 'region':"):CORE.index("case 'inc':")]
    assert "rq-abl" in block and "rq-wid" in block
    css = (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    assert ".rq-wid" in css and "flag" in css[css.index(".rq-wid"):css.index(".rq-wid") + 160]


def test_amtlich_bekommt_kein_etikett():
    """Ein Marker an jedem Wert ist kein Marker mehr. 69 % sind amtlich, die bleiben schlicht."""
    block = CORE[CORE.index("case 'region':"):CORE.index("case 'inc':")]
    assert "'amtlich'" not in block


def test_die_werte_sind_die_der_daten():
    """⚠ Ein vierter Wert im Export, den die Anzeige nicht kennt, verschwände lautlos."""
    bekannt = {"amtlich", "abgeleitet", "widerspruechlich"}
    gefunden = set()
    for f in glob.glob(str(WURZEL / "web" / "data" / "leads-*.json")):
        if "fristen" in f or "ohne" in f:
            continue
        d = json.load(open(f, encoding="utf-8"))
        d = d if isinstance(d, list) else list(d.values())
        for x in d:
            if x.get("regionQuelle"):
                gefunden.add(x["regionQuelle"])
    assert gefunden <= bekannt, f"unbekannte Herkunft im Bestand: {gefunden - bekannt}"

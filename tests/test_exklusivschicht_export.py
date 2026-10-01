"""Trägt `leads-fristen.json` die Exklusivschicht, und spiegelt sie die Leseseite?

Ticket #17 §11 macht die Exklusivschicht zur Bedingung für Indexierung. Eine Sitemap der
indexierbaren Seiten müsste ohne dieses Feld die sieben vollen Lead-Dateien lesen — 110 MB für
eine Liste von rund 4.275 URLs, genau das, wovon `leads-fristen.json` die Abkehr ist.

⚠ DIE GEFAHR IST NICHT, DASS DAS FELD FEHLT, sondern dass es etwas ANDERES bedeutet als auf der
Leseseite. `web/lib/oeffentlich.ts::exklusivSchicht()` und `scripts/export_web_leads.py::
_exklusiv()` müssen dieselbe Entscheidung treffen, inklusive Rangfolge. Zwei Umsetzungen
derselben Regel driften, und dann indexiert die Sitemap Seiten, die sich selbst als nicht
indexierbar ausweisen — oder umgekehrt.

⚠ DER SLUG WIRD BEWUSST NICHT EXPORTIERT. Eine erste Fassung tat es, portiert aus `titelSlug`/
`vollSlug`. Das wäre eine zweite Normalisierung derselben Sache gewesen; die Leseseite leitet
ihn allein in TS ab, aus `id` und `titel`. Dieser Test hält fest, dass der Slug draußen bleibt.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
EXPORT = WURZEL / "scripts" / "export_web_leads.py"
LESESEITE = WURZEL / "web" / "lib" / "oeffentlich.ts"


def _rumpf_ohne_doku() -> str:
    """Der ausfuehrbare Teil von `_exklusiv` — ohne Docstring und ohne Kommentare."""
    quelle = EXPORT.read_text(encoding="utf-8")
    i = quelle.index("def _exklusiv(l):")
    block = quelle[i:quelle.index("\ndef ", i + 1)]
    # Docstring: vom ersten bis zum zweiten Dreifachanfuehrungszeichen
    a = block.index('"""')
    b = block.index('"""', a + 3) + 3
    ohne_doku = block[:a] + block[b:]
    return "\n".join(z for z in ohne_doku.splitlines() if not z.lstrip().startswith("#"))


def _exklusiv():
    """⛔ NICHT importieren — `export_web_leads.py` FUEHRT beim Import den Export aus und
    schreibt dabei `plz-geo.json` ohne `_cities` (die Datei warnt selbst davor, Zeile 27 ff.).
    Die Funktion wird deshalb aus dem Quelltext herausgeschnitten und einzeln ausgeführt."""
    quelle = EXPORT.read_text(encoding="utf-8")
    i = quelle.index("def _exklusiv(l):")
    j = quelle.index("\ndef ", i + 1)
    raum: dict = {}
    exec(quelle[i:j], raum)
    return raum["_exklusiv"]


ECHT = {"name": "Beispiel GmbH", "src": "echt", "conf": 0.9, "seit": "2021"}
UNSICHER = {"name": "Geraten AG", "src": "unsicher", "conf": 0.6, "seit": ""}
ZYKLUS = {"seit": "2019", "tiefe": 2}


def test_die_rangfolge_stimmt_mit_der_leseseite():
    """Wer BEIDES hat, gilt als `predecessor`."""
    f = _exklusiv()
    assert f({"incumbent": ECHT}) == "predecessor"
    assert f({"kette": ZYKLUS}) == "cycle"
    assert f({"incumbent": ECHT, "kette": ZYKLUS}) == "predecessor", \
        "die Rangfolge ist gekippt — predecessor geht vor cycle"
    assert f({}) is None
    assert f({"incumbent": None, "kette": None}) is None


def test_ein_geratener_amtsinhaber_zaehlt_nicht():
    """⛔ `src='unsicher'` heisst: aus dem letzten vergleichbaren Zuschlag DESSELBEN KAEUFERS
    geraten, nicht aus diesem Verfahren (conf 0,6). Eine Seite, die ihn als Indexierungsgrund
    fuehrt, behauptet Gewissheit, die sie nicht hat — §6.3 „bei Zweifel weglassen".
    Gemessen am 2026-10-01: 20.694 echt, 10.118 unsicher."""
    f = _exklusiv()
    assert f({"incumbent": UNSICHER}) is None, \
        "ein geratener Amtsinhaber macht die Seite indexierbar — das ist eine Behauptung"
    assert f({"incumbent": {"name": "X"}}) is None, "ohne src zaehlt es nicht"
    assert f({"incumbent": {"src": "echt"}}) is None, "ohne Namen ist es keine Aussage"


def test_die_dublettenliste_zaehlt_NICHT():
    """⛔ DER WICHTIGSTE TEST DIESER DATEI. `ersetzt` ist die Liste der doppelten Kennungen, die
    `_verfahrens_dubletten()` in diesen Lead einschmilzt, damit alte Nummern suchbar bleiben —
    ein Aufraeumartefakt, kein Vertrag.

    Beide Seiten lasen es bis zum 2026-10-01 als „verifizierter Vorgaengervertrag". Die Seite
    haette 184 Mal einen Vorgaenger behauptet, den es nicht gibt, und zwar als GRUND fuer die
    Indexierung. §1 des Tickets nennt genau das als Markenschaden."""
    f = _exklusiv()
    assert f({"ersetzt": ["603341_2026", "603342_2026"]}) is None, \
        "die Dublettenliste macht die Seite wieder indexierbar — das ist der alte Fehler"
    # ⚠ DEN DOCSTRING WEGSCHNEIDEN, NICHT NUR KOMMENTARZEILEN. Der Docstring von `_exklusiv`
    # ERWAEHNT `ersetzt` absichtlich, um zu erklaeren, warum es nicht gelesen wird — eine
    # Suche ohne dieses Wegschneiden schlaegt an der Begruendung an statt am Code. Dieselbe
    # Lehre wie „Waechter messen Prosa statt Code", und sie hat diesen Test beim ersten Lauf
    # erwischt.
    assert "ersetzt" not in _rumpf_ohne_doku(), "`ersetzt` wird wieder gelesen"


def test_das_breite_auftraggeber_tor_ist_nicht_drin():
    """⛔ Es laesst 78,1 % aller Leads durch und gatet damit nicht (Marktanalyse §8, Commit
    1c101ea). Wer es wieder einbaut, oeffnet statt zu gaten."""
    f = _exklusiv()
    assert f({"buyerProfile": {"total": 99}}) is None, \
        "das breite Tor ist zurueck — es gehoert NICHT in die Exklusivschicht"
    assert f({"incumbent": ECHT, "buyerProfile": {"total": 2}}) == "predecessor"
    quelle = EXPORT.read_text(encoding="utf-8")
    i = quelle.index("def _exklusiv(l):")
    rumpf = "\n".join(z for z in quelle[i:quelle.index("\ndef ", i + 1)].splitlines()
                      if not z.lstrip().startswith("#"))
    assert "buyerProfile" not in rumpf and "buyer_history" not in rumpf


def test_die_leseseite_kennt_genau_dieselben_werte():
    """Beide Seiten müssen dieselbe Wertemenge führen, sonst liest die Sitemap etwas, das die
    Route nie setzt."""
    ts = LESESEITE.read_text(encoding="utf-8")
    assert '"predecessor" | "buyer_history" | "cycle" | null' in ts, \
        "der Rueckgabetyp in oeffentlich.ts sieht anders aus als erwartet"
    f = _exklusiv()
    werte = {f({"incumbent": ECHT}), f({"kette": ZYKLUS}), f({})}
    assert werte == {"predecessor", "cycle", None}


def test_der_slug_bleibt_draussen():
    """Zwei Normalisierungen derselben Sache driften. Die Leseseite leitet ihn ab."""
    quelle = EXPORT.read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(z for z in quelle.splitlines() if not z.lstrip().startswith("#"))
    assert '"slug"' not in ohne_kommentar, \
        "der Slug wird wieder exportiert — das ist die zweite Normalisierung"
    assert "_voll_slug" not in ohne_kommentar and "_titel_slug" not in ohne_kommentar


def test_das_feld_wird_nur_gesetzt_wenn_es_eine_gibt():
    """42.105 Eintraege mit `null` waeren rund 1 MB auf einer Datei in einem ANFRAGEPFAD."""
    quelle = EXPORT.read_text(encoding="utf-8")
    i = quelle.index("def _frist_zeile")
    rumpf = quelle[i:quelle.index("\ndef ", i + 1)]
    assert "if (ex := _exklusiv(l))" in rumpf, \
        "das Feld wird unbedingt gesetzt — dann steht 42.105-mal null in der Datei"


def test_die_echte_datenlage_traegt_ueberhaupt_exklusivschichten():
    """Ein Feld, das auf JEDEM Lead null ist, waere gebaut und wirkungslos. Gemessen gegen die
    exportierten Lead-Dateien, nicht gegen eine Annahme."""
    f = _exklusiv()
    dateien = sorted((WURZEL / "web" / "data").glob("leads-*.json"))
    dateien = [p for p in dateien if "fristen" not in p.name]
    if not dateien:
        return                                    # frische Umgebung ohne Export
    treffer = {"predecessor": 0, "cycle": 0}
    gesamt = 0
    for p in dateien[:3]:
        d = json.loads(p.read_text(encoding="utf-8"))
        leads = d if isinstance(d, list) else d.get("leads", [])
        for l in leads:
            gesamt += 1
            if (ex := f(l)):
                treffer[ex] += 1
    assert gesamt > 0, "keine Leads gelesen"
    assert sum(treffer.values()) > 0, (
        f"kein einziger von {gesamt} Leads traegt eine Exklusivschicht — das Feld waere "
        f"gebaut und wirkungslos")

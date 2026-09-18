"""Sagt die Oberflaeche, dass sie laedt — oder behauptet sie, es gaebe nichts?

⚠ WARUM DIESE DATEI EXISTIERT. Nach der Anmeldung stand rund zwoelf Sekunden lang
„0 von 0" auf dem Schirm, darunter „Keine Leads mit diesen Filtern. Passe die Filter an
oder wechsle den Grundraum." Beides sind Aussagen ueber die DATEN; waehrend des Ladens
sind beide falsch, und die zweite schickt den Nutzer aktiv in die Irre.

Der Zustand war da: `const [loading, setLoading] = useState(true)`, korrekt gesetzt vor
dem Abruf und danach zurueckgenommen. Gelesen hat ihn niemand. Die Anwendung wusste, dass
sie laedt, und sagte es nicht.

Gemeldet in einer Vorfuehrung: „hab mich durchgeklickt, nun sind noch weniger infos da."
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-tote-zustaende.mjs"


def test_kein_zustand_bleibt_ungelesen():
    """Die Sonde prueft die KLASSE, nicht den Einzelfall.

    „Gesetzt, nie gelesen" ist dieselbe Fehlerklasse wie „gebaut, nicht verdrahtet", nur
    eine Ebene kleiner: nicht eine ungelesene Datei, sondern ein ungelesener Zustand. Sie
    faellt nicht auf, weil nichts kaputtgeht — die Oberflaeche ist nur stumm, wo sie etwas
    wuesste.

    Gegengeprueft am 2026-09-17: rot, sobald der Ladezustand wieder aus der Anzeige
    genommen wird. Beim ersten Lauf fand die Sonde ausserdem `planOpen` — eine tote Zeile,
    weder gelesen noch gesetzt.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Jeder Zustand wird auch gelesen" in r.stdout


def test_die_liste_kennt_den_dritten_zustand():
    """„leer" und „gefuellt" reichen nicht — „laedt noch" ist ein eigener Zustand.

    ⚠ Ohne ihn zeigt die Tabelle waehrend des Ladens ihren Leer-Text, und der nennt eine
    Ursache („diese Filter"), die nicht stimmt.
    """
    import re
    roh = (WURZEL / "web" / "components" / "explorer" / "LeadTable.tsx").read_text(encoding="utf-8")
    # ⚠ KOMMENTARE RAUS. Die erste Fassung dieses Tests schlug an der ERKLAERUNG im
    # JSDoc von `laedt` an, die den Leer-Text zitiert — sie mass Prosa statt Code.
    # Dieselbe Falle steckte am selben Tag in `pruefe_verdrahtung.py`.
    tabelle = re.sub(r"(?m)(^|[^:])//.*$", r"\1", re.sub(r"/\*.*?\*/", "", roh, flags=re.S))
    assert "laedt" in tabelle, "LeadTable kennt keinen Ladezustand"
    # Der Leer-Text darf nur im NICHT-ladenden Zweig stehen.
    i = tabelle.index("Keine Leads mit diesen Filtern")
    davor = tabelle[max(0, i - 600):i]
    assert "laedt ?" in davor, ("Der Leer-Text haengt nicht am Ladezustand — er erscheint "
                                "wieder waehrend des Ladens und nennt eine falsche Ursache")


def test_die_liste_kennt_vier_zustaende():
    """laedt · Stoerung · gefiltert-leer · leer — nur die letzten beiden sind Aussagen.

    ⚠ FALLENKATALOG A16: „Ein leeres Ergebnis ist eine AUSSAGE. Kommt sie auch dann, wenn
    niemand nachgesehen hat, ist ein Ausfall zur Auskunft geworden." Dieselbe
    Unterscheidung steht seit dem 2026-09-04 in `lib/ladegrund.js` („gibt es nicht" gegen
    „komme nicht dran") — an dieser Stelle war sie nur nie angeschlossen.

    Bis zum 2026-09-18 setzte der Fehlerzweig schlicht `setLoading(false)`, und die Liste
    sagte „Keine Leads mit diesen Filtern": ein Ausfall als Auskunft, samt Rat an den
    Falschen. Der dritte Zustand fehlte ebenso — ohne gesetzte Filter ist „mit diesen
    Filtern" schlicht unwahr.
    """
    import re
    roh = (WURZEL / "web" / "components" / "explorer" / "LeadTable.tsx").read_text(encoding="utf-8")
    tab = re.sub(r"(?m)(^|[^:])//.*$", r"\1", re.sub(r"/\*.*?\*/", "", roh, flags=re.S))
    for zustand in ("stoerung ?", "laedt ?", "gefiltert ?"):
        assert zustand in tab, f"Zustand `{zustand}` fehlt — vier Zustaende, nicht zwei"
    # Die Reihenfolge ist Teil der Aussage: eine Stoerung WAEHREND des Ladens ist eine
    # Stoerung, keine Ladeanzeige, die nie endet.
    assert tab.index("stoerung ?") < tab.index("laedt ?") < tab.index("gefiltert ?"), (
        "die Zustaende stehen in falscher Reihenfolge — eine Stoerung waehrend des Ladens "
        "wuerde als Ladeanzeige erscheinen und nie enden")


def test_der_fehlerzweig_meldet_die_stoerung():
    """Ein gescheiterter Abruf darf nicht als leere Liste enden.

    ⚠ Und der STATUS zaehlt, nicht nur der Rumpf: `/api/leads` antwortet bei fehlenden
    Daten mit 503. `r.json()` machte daraus ein Objekt, `Array.isArray` war falsch, und
    uebrig blieb eine leere Liste ohne Begruendung.
    """
    import re
    roh = (WURZEL / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    quelle = re.sub(r"(?m)(^|[^:])//.*$", r"\1", re.sub(r"/\*.*?\*/", "", roh, flags=re.S))
    i = quelle.index("fetch(`/api/leads")
    block = quelle[i:quelle.index("}, [aktiveBranche", i)]
    assert "r.ok" in block, "der HTTP-Status wird nicht geprueft — 503 saehe aus wie leere Daten"
    assert "setStoerung(true)" in block, "der Fehlerzweig meldet die Stoerung nicht"

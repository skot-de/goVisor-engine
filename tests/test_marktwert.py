"""Marktüblich in der Anbieter-Sicht: der Bezug, der in der Käufersicht seit jeher steht.

⚠ Diese Datei prüft vor allem, dass die Zeile SCHWEIGT, wo sie nichts sagen kann. Ein
Marktwert aus drei Vergabestellen sieht genauso aus wie einer aus sechzig, und das ist die
teuerste Sorte Fehler in einem Produkt, dessen Verkaufsargument Belegbarkeit ist.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
SV = (WEB / "components" / "explorer" / "StrategieView.tsx").read_text(encoding="utf-8")
STRATEGIE = WEB / "data" / "strategie.json"

MIND_STELLEN = 10
MIND_FAELLE = 8


def _code() -> str:
    """Quelltext ohne Kommentare. ⚠ Die Begründungen nennen genau die Begriffe, gegen die
    hier geprüft wird; ein Test über den Rohtext hinge an der eigenen Erklärung."""
    raus, im_block = [], False
    for z in SV.splitlines():
        t = z.strip()
        if t.startswith("/*"): im_block = True
        if im_block:
            if "*/" in t: im_block = False
            continue
        if t.startswith("//") or t.startswith("*"): continue
        raus.append(z)
    return "\n".join(raus)


def test_die_schwellen_stehen_im_code():
    c = _code()
    assert f"MIND_STELLEN = {MIND_STELLEN}" in c
    assert f"MIND_FAELLE = {MIND_FAELLE}" in c


def test_ohne_streuung_kein_viertel():
    """⚠ Der Fehler, der fast live gegangen wäre: liegen oberes und unteres Viertel auf
    demselben Wert, ist `eigen >= oben` für JEDE Stelle wahr. In der Schweiz hätte damit
    jede einzelne Vergabestelle „oberes Viertel" beim KMU-Anteil getragen."""
    c = _code()
    assert "gleich" in c and "streuung" in c.lower()
    assert re.search(r"lage\.oben\s*>\s*lage\.unten", c), "die Streuung wird nicht geprüft"


def test_keine_wertung_in_der_anbieter_sicht():
    """Die Käufersicht färbt „schlechter als der Markt" rot, weil eine Vergabestelle ein
    normatives Ziel hat. Ein Anbieter hat keins: eine Stelle mit wenigen Bietern ist für ihn
    attraktiv. Wer hier eine Ampel setzt, behauptet eine Richtung, die es nicht gibt."""
    block = SV[SV.index("function Marktzeile"):]
    block = block[:block.index("\n}")]
    for verboten in ("warn", "risk", "goodHigh", "worse"):
        assert verboten not in block, f"{verboten} bringt eine Wertung in die Anbieter-Sicht"


def test_die_zeile_schweigt_wo_die_daten_duenn_sind():
    """Gegen die ECHTEN Daten, nicht gegen eine Nachbildung. In der Schweiz tragen bei der
    Wechselquote nur 1 bis 6 Stellen einen belastbaren Wert."""
    if not STRATEGIE.exists():
        return  # ohne Datei nichts zu prüfen; die Verdrahtungssonde meldet das getrennt
    d = json.loads(STRATEGIE.read_text(encoding="utf-8"))
    ch = d.get("CH") or {}
    assert ch, "CH fehlt in strategie.json"
    for branche, s in ch.items():
        stellen = s.get("stellen") or []
        belastbar = [x["wechsel"]["pct"] for x in stellen
                     if isinstance(x.get("wechsel"), dict) and (x["wechsel"].get("n") or 0) >= MIND_FAELLE]
        assert len(belastbar) < MIND_STELLEN, (
            f"CH/{branche}: die Wechselquote trägt jetzt {len(belastbar)} Stellen. "
            "Wenn das echt ist, ist es eine gute Nachricht und dieser Test gehört angepasst.")


def _quoten_je_stelle(land: str, feld: str) -> dict:
    """Ein Wert je Vergabestelle — dieselbe Stelle steht in mehreren Branchen."""
    d = json.loads(STRATEGIE.read_text(encoding="utf-8"))
    return {x["id"]: x[feld] for s in (d.get(land) or {}).values()
            for x in (s.get("stellen") or [])
            if isinstance(x.get(feld), dict) and (x[feld].get("n") or 0) >= MIND_FAELLE}


def test_die_kmu_kennzeichnung_unterscheidet_wieder():
    """⚠ DIESER TEST STAND BIS ZUM 2026-09-01 AUF DEM KOPF.

    Er hielt fest, dass in der Schweiz ALLE 104 ausgewerteten Stellen denselben KMU-Anteil
    von 100 % trugen — als Zustandsbeschreibung eines bekannten Defekts, damit die Anzeige
    daraus kein Viertel-Etikett macht.

    Die Ursache ist gefunden und behoben (`scripts/export_strategie.py`, `kmu`-Bauschritt):
    die Quote wurde auf `v36` gemessen, und `v36` haelt nur Vergaben mit registerbelegtem
    Gewinner. In CH liess dieser Filter exakt das Melder-Lager uebrig, das die Sammelstufe
    `sme` verwendet und `large` nie — 100 % waren keine Messung, sondern eine Vokabel.
    Gemessen auf allen Zuschlaegen: 1 → 45 verschiedene Werte, Median 89 %.

    Was der Test jetzt haelt, ist die Reparatur. Er faellt zurueck in einen Fehlschlag,
    sobald die Kennzahl wieder zur Konstanten wird."""
    if not STRATEGIE.exists():
        return
    werte = set(q["pct"] for q in _quoten_je_stelle("CH", "kmu").values())
    assert len(werte) > 1, (
        "CH-KMU traegt wieder EINEN einzigen Wert. Das ist der Zustand vom 2026-09-01: "
        "die Kennzahl unterscheidet nichts und liest sich trotzdem als Marktaussage. "
        "Ursache pruefen — `python3 scripts/pruefe_streuung.py`.")


def test_keine_kennzahl_ohne_streuung_bleibt_unmarkiert():
    """Der Waechter selbst, gegen die echte Datei. Eine Kennzahl ohne Streuung ueber ein
    ganzes Land darf existieren — aber nur markiert (`konstant`), nie als blanker Messwert.

    ⚠ Warum ueberhaupt als Test und nicht nur als Skript: der Defekt macht kein Geraeusch.
    Kein Feld ist NULL, kein Fremdschluessel bricht, keine Zahl sieht falsch aus. Er faellt
    nur auf, wenn jemand zwei Laender nebeneinanderlegt — und genau das tut hier niemand
    von selbst."""
    if not STRATEGIE.exists():
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pruefe_streuung

    d = json.loads(STRATEGIE.read_text(encoding="utf-8"))
    offen = [b for b in pruefe_streuung.pruefe(d) if not b["markiert"]]
    assert not offen, "unmarkierte Kennzahl(en) ohne Streuung: " + ", ".join(
        f"{b['land']}/{b['kennzahl']} ({b['stellen']} Stellen, Wert {b['wert']})" for b in offen)


def test_der_waechter_findet_eine_konstante():
    """Der Detektor selbst — an einem gebauten Fall, nicht an der Tageslage. Ohne das
    prueft der Test oben nur, dass heute nichts entartet ist; ob der Waechter ueberhaupt
    etwas SIEHT, bliebe offen. Genau diese Sorte Luecke hat den KMU-Fall drei Wochen
    getragen."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pruefe_streuung

    def land(werte, n=12):
        return {"bau": {"stellen": [
            {"id": f"s{i}", "kmu": {"pct": w, "n": n, "treffer": 0}} for i, w in enumerate(werte)]}}

    # 12 Stellen, EIN Wert → Befund, unmarkiert
    b = pruefe_streuung.pruefe({"XX": land([100] * 12)})
    assert len(b) == 1 and b[0]["kennzahl"] == "kmu" and not b[0]["markiert"]

    # markiert → kein offener Befund mehr (markieren statt wegwerfen)
    mit_mark = land([100] * 12)
    for st in mit_mark["bau"]["stellen"]:
        st["kmu"]["konstant"] = True
    assert pruefe_streuung.pruefe({"XX": mit_mark})[0]["markiert"]

    # Streuung vorhanden → kein Befund
    assert not pruefe_streuung.pruefe({"XX": land([100] * 11 + [50])})

    # zu wenige Stellen → Gleichheit ist Zufall, kein Befund
    assert not pruefe_streuung.pruefe({"XX": land([100] * 9)})

    # duenne Quoten (n < 8) zaehlen gar nicht erst mit
    assert not pruefe_streuung.pruefe({"XX": land([100] * 12, n=4)})


def test_die_markierung_landet_in_der_datei():
    """Der Bauschritt ruft `markieren` — und `markieren` stempelt wirklich.

    ⚠ Warum das einen eigenen Test braucht: seit der Reparatur entartet nichts mehr, also
    laeuft dieser Pfad im Tagesbetrieb NIE. Genau so entsteht die haeufigste Fehlerklasse
    des Projekts — ein korrekter Baustein, den niemand mehr ausloest, und der beim naechsten
    echten Fall stumm bleibt."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pruefe_streuung

    block = {"bau": {"stellen": [
        {"id": f"s{i}", "kmu": {"pct": 100, "n": 20, "treffer": 20}} for i in range(14)]}}
    # eine duenne Stelle dazu — sie zaehlt nicht mit und darf auch nicht markiert werden
    block["bau"]["stellen"].append({"id": "duenn", "kmu": {"pct": 0, "n": 3, "treffer": 0}})

    getroffen = pruefe_streuung.markieren(block, "XX", sagen=lambda *_: None)
    assert getroffen == ["kmu"]
    stellen = block["bau"]["stellen"]
    assert all(st["kmu"]["konstant"] for st in stellen if st["id"] != "duenn")
    assert "konstant" not in stellen[-1]["kmu"], "duenne Quote faelschlich markiert"
    # Rohwert bleibt — markieren statt wegwerfen
    assert stellen[0]["kmu"]["pct"] == 100 and stellen[0]["kmu"]["n"] == 20
    # und danach gilt die Entartung als versorgt
    assert pruefe_streuung.pruefe({"XX": block})[0]["markiert"]


def test_bauschritt_und_waechter_teilen_eine_quelle():
    """Die zwei Schwellen duerfen nicht doppelt gepflegt sein. Der Bauschritt importiert
    den Waechter, statt die Rechnung nachzubauen."""
    quelle = (Path(__file__).resolve().parent.parent / "scripts" / "export_strategie.py")\
        .read_text(encoding="utf-8")
    assert "from pruefe_streuung import markieren" in quelle
    assert "streuung_markieren(out[land], land)" in quelle


def test_der_waechter_gilt_fuer_jedes_land():
    """EU-weit-Grundsatz: der Detektor darf keine Laenderliste kennen. Er prueft, was in
    der Datei steht — auch ein Land, das es heute noch nicht gibt."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pruefe_streuung

    # ⚠ NICHT ueber den Rohtext pruefen: `BEKANNT` nennt Laender voellig zu Recht (eine
    # abgehakte Ausnahme gilt fuer ein bestimmtes Land). Geprueft gehoert der DETEKTOR —
    # ob er eine feste Laenderliste kennt oder das nimmt, was da ist.
    import inspect
    for fn in (pruefe_streuung.pruefe, pruefe_streuung.spalten_scan, pruefe_streuung.markieren):
        code = inspect.getsource(fn)
        for land in ("DE", "AT", "CH"):
            assert f'"{land}"' not in code, f"{fn.__name__} nennt {land} fest"
    # Spur 2 holt die Laender aus dem Verzeichnis, nicht aus einer Liste.
    assert "GOLD.glob" in inspect.getsource(pruefe_streuung.spalten_scan)

    # Ein frei erfundenes Land wird genauso geprueft wie DE.
    b = pruefe_streuung.pruefe({"PL": {"bau": {"stellen": [
        {"id": f"s{i}", "preis": {"pct": 0, "n": 30, "treffer": 0}} for i in range(15)]}}})
    assert len(b) == 1 and b[0]["land"] == "PL" and b[0]["kennzahl"] == "preis"


def test_die_spaltenspur_findet_die_asymmetrie():
    """Spur 2 an gebauten Faellen — sie darf nicht davon abhaengen, was heute in Gold liegt.

    Geprueft werden beide Klassen: die Laender-Asymmetrie (irgendwo unterscheidet die
    Spalte etwas, hier nicht) und das nur-positive Vokabular (nirgends etwas, aber
    irgendwo gefuellt). Die zweite ist die, an der der KMU-Wert haengt."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pruefe_streuung

    quelle = (Path(__file__).resolve().parent.parent / "scripts" / "pruefe_streuung.py")\
        .read_text(encoding="utf-8")
    # Beide Klassen muessen benannt sein — sonst faellt eine still weg.
    assert '"laendervergleich"' in quelle and '"nur_positiv"' in quelle
    # Eine ueberall-NULL-Spalte behauptet nichts und gehoert NICHT hierher.
    assert "irgendwo_gefuellt" in quelle


def test_die_ausnahmen_bleiben_ehrlich():
    """⚠ Eine Ausnahmeliste ist eine Textdatei mit Zugriffsrechten: sie verrottet.

    Dieselbe Lehre wie bei `pruefe_verdrahtung.py`. Ein Eintrag ohne Grund, fuer eine
    Spalte, die es nicht mehr gibt, oder fuer eine Luecke, die laengst geschlossen ist,
    macht die Sonde blind — und zwar leise. Hier wird jeder Eintrag gegen die WIRKLICHKEIT
    geprueft, nicht gegen sich selbst."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pruefe_streuung

    # 1 · Jeder Eintrag traegt einen Grund, und der Grund ist kein Platzhalter.
    for schluessel, grund in pruefe_streuung.BEKANNT.items():
        assert isinstance(grund, str) and len(grund) > 20, f"{schluessel}: Grund zu duenn"

    # 2 · Kein Eintrag fuer etwas, das gar nicht (mehr) auffaellt. Braucht gebaute Gold-
    #     Ebenen — ohne sie ist die Pruefung nicht moeglich, nicht bestanden.
    befunde = pruefe_streuung.spalten_scan()
    if not befunde:
        return
    gefunden = {(b["land"], b["spalte"]) for b in befunde}
    veraltet = sorted(set(pruefe_streuung.BEKANNT) - gefunden)
    assert not veraltet, (
        "Eintraege in BEKANNT, die keinem Befund mehr entsprechen — Luecke geschlossen "
        "oder Spalte weg, Eintrag gehoert raus: " + ", ".join(f"{l}/{s}" for l, s in veraltet))


def test_der_unterlagen_block_bleibt_als_offener_punkt_stehen():
    """⚠ DER GROESSTE FUND NEBEN KMU, und er zeigt in die andere Richtung.

    Der Unterlagen-Block (`has_documents`, `documents_paid`, `documents_source`,
    `documents_languages`) ist fuer die SCHWEIZ gebaut und fuer DE/AT nie verdrahtet
    worden — gemessen am 2026-09-01. In DE stehen 90.969 Leads auf `has_documents=False`,
    obwohl unter `data/docs/DE` ein grosser Bestand liegt.

    Das ist dieselbe Krankheit wie beim KMU-Wert, nur mit umgekehrtem Vorzeichen: statt
    „alles erfuellt" behauptet die Datei „nichts vorhanden". Beide Male steht ein nicht
    erhobenes Merkmal als entschiedener Wert da.

    Dieser Test haelt den offenen Punkt fest. Wird der Block verdrahtet, schlaegt er an
    und gehoert angepasst — so wie dieser hier den KMU-Test abgeloest hat."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pruefe_streuung

    for land in ("DE", "AT"):
        assert ("has_documents" in
                [s for (l, s) in pruefe_streuung.BEKANNT if l == land]), \
            f"{land}/has_documents nicht mehr als offener Punkt gefuehrt"


def test_die_anzeige_kennt_die_markierung():
    """Markieren statt wegwerfen: die Anzeige muss `konstant` lesen — sonst steht die
    Kennzeichnung in der Datei und die 100 % trotzdem im Bild."""
    c = _code()
    assert "konstant" in c, "StrategieView liest die Markierung nicht"
    assert "q.konstant" in c and "data-src=\"konstant\"" in c
    # und sie darf keinen Marktwert mehr speisen
    assert "if (q?.konstant) return null;" in c


def test_die_sonde_gibt_es():
    """Die Rechnung wird unter `node` gegen die echte Datei gefahren, nicht in einer
    Abschrift geprüft. Dieselbe Lehre wie bei netzMatch und der Passwortregel."""
    sonde = WEB / "scripts" / "pruefe-marktwert.mjs"
    assert sonde.exists()
    txt = sonde.read_text(encoding="utf-8")
    assert "strategie.json" in txt and "MIND_STELLEN" in txt


def test_alle_sechs_kacheln_tragen_den_bezug():
    c = _code()
    assert c.count("<Marktzeile") == 6, "nicht jede Kachel hat ihre Bezugsgrösse"
    for feld in ("vergabenJahr", "neuAnteil", "bieterMedian", "kmu", "preis", "wechsel"):
        assert f"marktLage(alle" in c and feld in c

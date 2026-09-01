"""Marktüblich in der Anbieter-Sicht: der Bezug, der in der Käufersicht seit jeher steht.

⚠ Diese Datei prüft vor allem, dass die Zeile SCHWEIGT, wo sie nichts sagen kann. Ein
Marktwert aus drei Vergabestellen sieht genauso aus wie einer aus sechzig, und das ist die
teuerste Sorte Fehler in einem Produkt, dessen Verkaufsargument Belegbarkeit ist.
"""
from __future__ import annotations

import json
import re
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


def test_der_entartete_kmu_wert_ist_erkannt():
    """⚠ In der Schweiz tragen ALLE ausgewerteten Stellen denselben KMU-Anteil von 100 %.
    Die Kennzeichnung unterscheidet dort nichts. Solange das so ist, darf daraus kein
    Viertel-Etikett werden."""
    if not STRATEGIE.exists():
        return
    d = json.loads(STRATEGIE.read_text(encoding="utf-8"))
    werte = {x["kmu"]["pct"] for s in (d.get("CH") or {}).values()
             for x in (s.get("stellen") or [])
             if isinstance(x.get("kmu"), dict) and (x["kmu"].get("n") or 0) >= MIND_FAELLE}
    assert len(werte) <= 1, (
        f"CH-KMU trägt jetzt {len(werte)} verschiedene Werte. Wenn die Kennzeichnung "
        "repariert wurde, ist das gut und dieser Test gehört angepasst.")


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

"""Jeder Wert mit seiner Herkunft — die Kernaussage der Marke, als Prüfung.

„Gemessenes ist gemessen, Geschätztes ist markiert, Unbekanntes bleibt sichtbar." Das ist
kein Werbesatz, sondern eine Behauptung über die Oberfläche. Sie hält nur, solange jeder
ausgelieferte Herkunftswert einer ist, den die Anzeige KENNT.

⚠ Am 2026-08-31 hielt sie für 5.683 Leads nicht. Ein Zweig in `export_web_leads.py` schrieb
den englischen Rohwert `uncertain` statt des Oberflächen-Vokabulars `unsicher` — fünf Zeilen
über der Abbildungstabelle, die genau das übersetzt. Folge:

    Tooltip:  „undefined"        (SRC_TEXT kennt den Schlüssel nicht)
    Punkt:    durchsichtig       (keine CSS-Regel greift)

Der Amtsinhaber sah damit aus wie gemessen, obwohl er aus einem VERGLEICHBAREN Zuschlag
desselben Käufers abgeleitet ist. Das ist die eine Verwechslung, die das Produkt nicht
machen darf.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
KERN = WEB / "lib" / "explorerCore.js"
DATEN = WEB / "data"

# Felder der ausgelieferten Leads, die eine Herkunft tragen.
HERKUNFTSFELDER = ("volumen", "timing", "incumbent", "konk", "relevanz", "anf")


def _bekannte_herkuenfte() -> set[str]:
    """Was die Anzeige übersetzen kann — aus `SRC_TEXT` gelesen, nicht abgeschrieben."""
    quelle = KERN.read_text(encoding="utf-8")
    block = quelle[quelle.index("const SRC_TEXT = {"):]
    block = block[: block.index("};")]
    return set(re.findall(r"^\s*([a-zA-Z_]+)\s*:", block, re.M))


def _ausgelieferte_herkuenfte() -> dict[str, int]:
    zahl: dict[str, int] = {}
    for datei in sorted(DATEN.glob("leads-*.json")):
        try:
            leads = json.loads(datei.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        for lead in leads:
            for feld in HERKUNFTSFELDER:
                wert = lead.get(feld)
                if isinstance(wert, dict) and wert.get("src"):
                    zahl[wert["src"]] = zahl.get(wert["src"], 0) + 1
    return zahl


def test_die_anzeige_kennt_jede_ausgelieferte_herkunft():
    """Ein Herkunftswert, den die Anzeige nicht kennt, ist schlimmer als keiner.

    Er verschwindet nicht sichtbar, sondern lautlos: der Tooltip zeigt „undefined", der
    Punkt bleibt durchsichtig — und der Wert sieht damit aus wie gemessen. Genau in die
    Richtung, in die er nicht irren darf.
    """
    bekannt = _bekannte_herkuenfte()
    assert len(bekannt) >= 4, f"SRC_TEXT nicht erkannt: {bekannt}"

    geliefert = _ausgelieferte_herkuenfte()
    if not geliefert:
        pytest.skip("keine Lead-Dateien vorhanden (frische Arbeitskopie)")

    fremd = {s: n for s, n in geliefert.items() if s not in bekannt}
    assert not fremd, (
        "Herkunftswerte, die die Anzeige nicht kennt:\n  "
        + "\n  ".join(f"{s!r}: {n:,} Leads" for s, n in sorted(fremd.items()))
        + "\nDie Pipeline spricht Englisch, die Oberflaeche Deutsch — die Abbildung steht "
          "in `scripts/export_web_leads.py` (VAL_SRC / TIM_SRC / INC_SRC / KONK_SRC).")


def test_kein_englischer_rohwert_rutscht_durch():
    """Die Vertragssprache der Pipeline darf die Oberflaeche nicht erreichen.

    `lead_export` ist durchgehend englisch (`actual`/`estimated`/`uncertain`/`unknown`) —
    so steht es in `docs/laender/09-frontend-und-i18n.md`. Genau diese vier Woerter duerfen
    in den ausgelieferten Dateien nicht vorkommen; wo sie auftauchen, ist eine Abbildung
    uebersprungen worden.
    """
    roh = {"actual", "estimated", "uncertain", "unknown"}
    geliefert = _ausgelieferte_herkuenfte()
    if not geliefert:
        pytest.skip("keine Lead-Dateien vorhanden")
    treffer = {s: n for s, n in geliefert.items() if s in roh}
    assert not treffer, (
        "Englische Rohwerte im Ausliefergut:\n  "
        + "\n  ".join(f"{s!r}: {n:,} Leads" for s, n in sorted(treffer.items())))


def test_was_nicht_gemessen_ist_traegt_ein_sichtbares_zeichen():
    """Die zweite Haelfte der Aussage: markiert heisst SICHTBAR, nicht nur beschriftet.

    Das Zeichensystem ist bewusst asymmetrisch (`globals.css`: „Belegtes trägt KEIN Zeichen,
    nur Abweichungen werden markiert"). Es gibt es zweimal — `.val[data-src=…]::before` für
    die Tabelle und `.pdot-…` für die Detailansicht. Beide Wege muessen jeden Wert kennen,
    der nicht `echt` ist; sonst ist der Punkt zwar da, aber durchsichtig.
    """
    css = ((WEB / "app" / "globals.css").read_text(encoding="utf-8")
           + (WEB / "app" / "explorer.css").read_text(encoding="utf-8"))
    geliefert = _ausgelieferte_herkuenfte()
    if not geliefert:
        pytest.skip("keine Lead-Dateien vorhanden")

    ohne_zeichen = []
    for src, n in geliefert.items():
        if src in ("echt", "na"):          # gemessen: kein Zeichen; n/a: eigener Kursivstil
            continue
        hat_val = f'.val[data-src="{src}"]' in css
        hat_pdot = f".pdot-{src}" in css
        if not (hat_val and hat_pdot):
            ohne_zeichen.append(
                f"{src!r} ({n:,} Leads): "
                f"{'Tabelle ok' if hat_val else 'TABELLE fehlt'}, "
                f"{'Detail ok' if hat_pdot else 'DETAIL fehlt'}")
    assert not ohne_zeichen, (
        "Herkuenfte ohne sichtbares Zeichen:\n  " + "\n  ".join(ohne_zeichen))

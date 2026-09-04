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


# ---- Die Richtung der Abbildungstabellen ---------------------------------------
EXPORT = ROOT / "scripts" / "export_web_leads.py"


def _herkunftstabellen() -> dict[str, str]:
    """Die `*_SRC`-Tabellen als Rohtext — gelesen, nicht importiert.

    Importieren hiesse duckdb und die halbe Pipeline zu laden, nur um vier Zeilen zu lesen.
    Dieselbe Entscheidung wie bei `_bekannte_herkuenfte()` eine Datei weiter oben.
    """
    quelle = EXPORT.read_text(encoding="utf-8")
    return dict(re.findall(r"^([A-Z_]+_SRC)\s*=\s*(\{[^}]*\})", quelle, re.M))


def test_keine_herkunftstabelle_haelt_unbekanntes_fuer_gemessen():
    """Wo nichts angegeben ist, darf nicht „gemessen" herauskommen.

    ⚠ DIE ASYMMETRIE IST DER GRUND. Belegte Werte tragen KEINE Markierung — das ist bewusst
    so, sonst wäre die Oberfläche ein Punktefeld. Genau deshalb ist „echt" der einzige Wert,
    zu dem man nicht raten darf: er ist die stille Vorgabe, und eine stille Vorgabe für
    „ich weiss es nicht" verwandelt eine Wissenslücke in eine Behauptung.

    `INC_SRC` war am 2026-09-04 die einzige der vier Tabellen, die das tat (`None: "echt"`,
    dazu `.get(..., "echt")`), während VAL_SRC/TIM_SRC auf „unbekannt" und KONK_SRC auf „na"
    abbildeten. Gemessen betraf es 0 Leads — der Weg dorthin war zugewachsen, nicht zu. Der
    Test hält die Richtung fest, damit der nächste neue Wert von oben nicht durchrutscht.
    """
    tabellen = _herkunftstabellen()
    assert len(tabellen) >= 4, f"Herkunftstabellen nicht erkannt: {sorted(tabellen)}"

    falsch = [n for n, block in tabellen.items()
              if re.search(r"None\s*:\s*[\"']echt[\"']", block)]
    assert not falsch, (
        f"Diese Tabellen bilden „nichts angegeben\" auf „echt\" ab: {falsch}. "
        "Richtig ist „unsicher\" oder „unbekannt\" — je nachdem, was die Anzeige kennt.")


def test_kein_rueckfall_auf_echt_bei_unbekanntem_schluessel():
    """`.get(x, "echt")` ist derselbe Fehler, nur eine Zeile später.

    Die Tabelle kann noch so sauber sein: ein Vorgabewert „echt" beim Nachschlagen macht
    jeden Wert, den `govisor/gold.py` neu erfindet, zur unmarkierten Behauptung. Und Gold
    erfindet welche — `lead_predecessor` trägt heute `'content'` (Konfidenz 0,6), das keine
    der vier Tabellen kennt.
    """
    quelle = EXPORT.read_text(encoding="utf-8")
    # ⚠ EINE KLAMMERSTUFE MUSS DAS MUSTER AUSHALTEN. Der erste Entwurf stand auf `[^)]*?`
    # und war damit blind: der echte Aufruf lautet `INC_SRC.get(g("incumbent_source"), "echt")`
    # — die innere Klammer beendete die Zeichenklasse, das Muster traf nichts, und die
    # Gegenprobe mit zurueckgebautem Fehler lief gruen durch.
    treffer = re.findall(
        r"([A-Z_]+_SRC)\.get\((?:[^()]|\([^()]*\))*,\s*[\"']echt[\"']\s*\)", quelle)
    assert not treffer, (
        f"Rückfall auf „echt\" bei unbekanntem Schlüssel: {sorted(set(treffer))}")

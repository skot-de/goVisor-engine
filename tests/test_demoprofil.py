"""Baut das Vorfuehr-Skript dasselbe Profil wie das echte Onboarding?

⚠ WARUM ES DIESE PRUEFUNG GIBT. `scripts/demo_konto.py` legt das Konto an, das
Aussenstehenden vorgefuehrt wird. Bis zum 2026-09-17 baute es das Profil von Hand und
nahm dabei nur `fields` (CPV-4) mit. `fields6` fiel weg — und damit fiel die Passung auf
CPV-4-Verhalten zurueck. `profileEngine.js` sagt das ausdruecklich an: „Alt-Profile ohne
cpvFields6 → CPV-4-Verhalten". Aufzug (453131) und Elektro (453112) waren dann dasselbe
Gewerk.

Gemessen fuer H. Klostermann: mit den zwoelf Sechsteller-Codes 598 Volltreffer gegen
1.170 Nachbarfeld. Ohne sie war beides eine Menge, und die Vorfuehrung zeigte das Produkt
unter Wert.

⚠ DAS IST MEHR ALS EIN DEMO-FEHLER. Ein Skript, das ein schwaecheres Profil baut als der
echte Weg, verdeckt auch Regressionen: waere der Onboarding-Pfad kaputt, wuerde der
Demolauf es nicht bemerken, weil er ihn nicht benutzt.

⚠ WARUM NICHT EINFACH DIE WERTE VERGLEICHEN. Der eine Weg ist Python, der andere
TypeScript im Browser; beide zusammen laufen zu lassen hiesse, eine Anmeldung zu
simulieren. Verglichen wird deshalb, WELCHE FELDER jede Seite schreibt. Genau das ist
auseinandergelaufen: nicht die Werte waren falsch, es fehlten Felder.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SKRIPT = WURZEL / "scripts" / "demo_konto.py"
ONBOARDING = WURZEL / "web" / "app" / "onboarding" / "page.tsx"

# Felder, die das Onboarding aus dem Treffer ableitet, der Demoweg aber nicht ableiten
# KANN — mit Grund. Wer hier etwas eintraegt, setzt ein Datum dazu.
NUR_ONBOARDING = {
    # Kommen aus dem Eignungs-Check, den es im Skript nicht gibt (keine Nutzereingabe).
    "checkAngaben",
    # Die Beleglage entsteht aus Domain/Impressum-Pruefung; das Demokonto bleibt bewusst
    # „unbestaetigt" (s. Kommentar in demo_konto.py, §3).
    "entityConfidence",
}


def _felder_onboarding() -> set[str]:
    """Die Schluessel, die `buildProfile(...)` im Onboarding gesetzt bekommt."""
    text = ONBOARDING.read_text(encoding="utf-8")
    i = text.index("profile = {")
    j = text.index("...(ausCheck ?? {}),", i)
    block = text[i:j]
    # Kommentare raus — sonst zaehlen zitierte Feldnamen aus der Prosa mit. Genau diese
    # Falle hat am selben Tag drei Waechter getroffen.
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    block = re.sub(r"(?m)(^|[^:])//.*$", r"\1", block)
    # ⚠ EIGENSCHAFTEN AN IHRER POSITION FANGEN, nicht am Zeilenanfang. JavaScript erlaubt
    # die Kurzform (`cpvFields,` statt `cpvFields: cpvFields`), und im Onboarding stehen
    # beide auf EINER Zeile: `cpvFields, cpvLabels: matched.fields.map(...)`. Die erste
    # Fassung dieser Pruefung suchte am Zeilenanfang und fand sieben statt neun Feldern —
    # ein Waechter, der zwei Felder nicht sieht, meldet auch ihr Fehlen nicht.
    # ⚠ NACHSCHAU STATT VERBRAUCH beim Trennzeichen: `cpvFields, cpvLabels:` steht auf
    # einer Zeile, und ein verbrauchtes Komma verschluckt den naechsten Treffer. Dritter
    # Fall dieser Art an einem Tag — verbrauchende Regex-Fenster sind offenbar die
    # haeufigste Falle in dieser Art Pruefung.
    return set(re.findall(r"(?:^|[{,])\s*(\w+)\s*(?=[,:])", block, re.M))


def _felder_demo() -> set[str]:
    """Die Schluessel, die `demo_konto.py` in den `profile`-Blob schreibt."""
    text = SKRIPT.read_text(encoding="utf-8")
    i = text.index('"profile": {')
    # Bis zur schliessenden Klammer des Blobs.
    j = text.index('"quelle"', i)
    block = text[i:j]
    block = re.sub(r"(?m)^\s*#.*$", "", block)
    return set(re.findall(r'"(\w+)"\s*:', block))


def test_der_demoweg_laesst_kein_feld_fallen():
    """Jedes Feld, das das Onboarding ableitet, muss auch das Demokonto tragen.

    ⚠ Die Richtung ist bewusst einseitig: das Skript DARF mehr setzen (etwa `quelle`),
    aber nichts weglassen. Ein fehlendes Feld faellt sonst erst auf, wenn jemand vor der
    Vorfuehrung sitzt und sich wundert, warum die Ausschreibungen nicht passen.
    """
    fehlt = _felder_onboarding() - _felder_demo() - NUR_ONBOARDING
    assert not fehlt, (
        "demo_konto.py laesst Felder fallen, die das Onboarding setzt: "
        + ", ".join(sorted(fehlt))
        + ". Die Vorfuehrung zeigt damit ein schwaecheres Profil als das echte Produkt.")


def test_die_gewerkscharfen_codes_sind_dabei():
    """`cpvFields6` ist der Grund, warum es diese Pruefung gibt.

    Ohne die Sechsteller faellt die Passung auf CPV-4 zurueck, und zwar STILL: es gibt
    keine Fehlermeldung, nur schlechtere Treffer. Gemessen fuer H. Klostermann: 598
    Volltreffer gegen 1.170 Nachbarfeld.
    """
    demo = _felder_demo()
    assert "cpvFields6" in demo, "die gewerkscharfen Sechsteller fehlen wieder"
    assert "cpvWins" in demo, (
        "`cpvWins` fehlt — ohne sie feuert der Bestands-Bonus nie, und die Passung "
        "erreicht nur vier der acht Stufen statt sieben")


def test_der_waechter_sieht_ueberhaupt_etwas():
    """Gegenprobe auf die Pruefung selbst.

    ⚠ Findet der Ausschnitt nichts, waeren beide Mengen leer und der Vergleich immer
    gruen — ein Waechter, der schweigt, weil er blind ist. Dieselbe Klasse wie die
    Wortpruefungen, die an diesem Tag mehrfach aufgefallen sind.
    """
    ob, demo = _felder_onboarding(), _felder_demo()
    assert len(ob) >= 8, f"nur {len(ob)} Felder im Onboarding gefunden — Ausschnitt kaputt?"
    assert len(demo) >= 8, f"nur {len(demo)} Felder im Demoweg gefunden — Ausschnitt kaputt?"

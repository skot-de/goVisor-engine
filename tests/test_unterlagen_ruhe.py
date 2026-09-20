"""Die Unterlagen-Seite bleibt ueberschaubar — GEMESSEN mit echten Analysedaten.

⚠ DER ANLASS. Sven am 2026-09-20: „ich will mit dir an der unterlagen seite arbeiten, die
ist total unuebersichtlich, aber die wichtigste seite die wir haben." Nachgemessen an einem
Median-Fall (58 Pruefpunkte, echtes Stylesheet, echter Renderer):

    Knoepfe                          239
    Textfelder                        58
    Hoehe wie ausgeliefert         5.473 px
    Hoehe ganz aufgeklappt        19.837 px   (22 Bildschirme)

Die Ursache lag nicht bei der Zahl der Abschnitte — die ist hoechstens vier —, sondern bei
der Bauform EINES Pruefpunkts: ein aufgeklappter Kasten mit Zitat, Textfeld und zwei
Knoepfen, 58 mal untereinander.

⚠ UND DER GRUND, WARUM MAN NICHTS FAND: gemessen ueber 392 Analysen tragen **87 % der
Pruefpunkte eine Ueberschrift, die in derselben Liste mehrfach vorkommt** (38 mal
„Technische Mindestanforderung"). Die unterscheidende Aussage stand klein darunter im
Zitat — und das ist im Median nur 89 Zeichen lang. Seit dem Umbau ist das Zitat die Zeile.

⚠ WAS DIESE DATEI NICHT PRUEFT: ob die Auswertung inhaltlich stimmt. Sie prueft, dass die
Seite benutzbar bleibt — und zwar in BEIDE Richtungen: Ruhe darf nicht dadurch entstehen,
dass Fundstelle oder Textbaustein verschwinden.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "scripts" / "pruefe_unterlagen.py"
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
CSS = WURZEL / "web" / "app" / "explorer.css"


def _lauf():
    return subprocess.run([sys.executable, str(SONDE)], capture_output=True, text=True,
                          cwd=WURZEL, timeout=300)


def _mit_mutation(datei: Path, alt: str, neu: str):
    echt = datei.read_text(encoding="utf-8")
    assert echt.count(alt) == 1, f"Anker nicht eindeutig ({echt.count(alt)}x): {alt[:70]}"
    try:
        datei.write_text(echt.replace(alt, neu, 1), encoding="utf-8")
        return _lauf()
    finally:
        datei.write_text(echt, encoding="utf-8")


def test_die_unterlagen_seite_ist_ueberschaubar():
    """Ohne Playwright oder ohne Analysedaten gibt die Sonde keine Auskunft."""
    r = _lauf()
    if r.returncode == 2:
        return
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]
    assert "Pruefpunkte" in r.stdout


def test_die_sonde_sieht_die_alte_bauform_wieder():
    """Gegenprobe mit GENAU DEM ZUSTAND, der da war: jeder Punkt immer aufgeklappt.

    ⚠ Eine Textpruefung sieht hier nichts. Das Markup bleibt Zeichen fuer Zeichen gleich;
    nur eine CSS-Regel entscheidet, ob 58 Textfelder auf dem Schirm stehen oder keines.
    """
    r = _mit_mutation(CSS, ".va-checklist .item .ibody{display:none}",
                      ".va-checklist .item .ibody{display:block}")
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl wieder alles offen steht"
    assert "Textfelder" in r.stdout or "px" in r.stdout, r.stdout


def test_die_sonde_sieht_wenn_die_ruhe_mit_der_funktion_erkauft_ist():
    """⚠ DIE WICHTIGERE RICHTUNG. Eine Seite ohne Inhalt ist immer ruhig. Wer den
    Textbaustein streicht, gewinnt jede Messung dieser Sonde — bis auf diese."""
    r = _mit_mutation(CSS, ".va-checklist .item.auf .ibody{display:block;padding-bottom:9px}",
                      ".va-checklist .item.auf .ibody{display:none}")
    if r.returncode == 2:
        return
    assert r.returncode == 1, (
        "die Sonde meldet Ruhe, obwohl ein aufgeklappter Punkt nichts mehr zeigt")
    assert "erkauft" in r.stdout, r.stdout


def test_die_zeile_traegt_das_zitat_und_nicht_die_art():
    """⚠ Textpruefung, und sie weiss das: sie haelt eine ENTSCHEIDUNG fest. 87 % der
    Ueberschriften wiederholen sich in derselben Liste; das Zitat unterscheidet."""
    q = CORE.read_text(encoding="utf-8")
    i = q.index('data-clopen="${it._i}"')
    zeile = q[i:i + 200]
    assert "${esc(satz)}" in zeile, "die Zeile traegt nicht mehr das Zitat"
    art = q[q.index('class="cl-art"'):q.index('class="cl-art"') + 120]
    assert "it.label" in art, "die Art ist nicht mehr die kleine Marke"


def test_der_wert_steht_nur_da_wenn_er_einer_ist():
    """59 % der `value` sind laenger als 18 Zeichen (also Text), 52 % stehen woertlich schon
    im Zitat. ⚠ Und `String(null)` ist „null" — genau das stand am 2026-09-20 in den
    Zeilen."""
    q = CORE.read_text(encoding="utf-8")
    b = q[q.index("const wert = ("):q.index("const wert = (") + 320]
    assert "it.value != null" in b, "die Pruefung auf den leeren Wert fehlt wieder"
    assert "length <= 18" in b, "auch langer Text landet wieder in der Zeile"
    assert "satz.includes" in b, "der Wert wird wieder doppelt gezeigt"


def test_die_sonde_sieht_die_zusammenfassung_wieder_offen():
    """Gegenprobe zum zweiten Absatz Prosa. ⚠ Beide Absaetze gibt es bei 100 % der
    Auswertungen; der Ampel-Grund bleibt offen, die Zusammenfassung klappt."""
    r = _mit_mutation(
        CORE,
        '<details class="va-worum"><summary>${tk("Worum es geht")}</summary><p class="va-sum">${esc(a.zusammenfassung)}</p></details>',
        '<p class="va-sum">${esc(a.zusammenfassung)}</p>')
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl die Zusammenfassung wieder offen steht"
    assert "Woerter" in r.stdout or "Vorspann" in r.stdout, r.stdout


def test_die_sonde_sieht_einen_ungekuerzten_ampelgrund():
    """Der Grund ist im Median 163 Zeichen lang, im Einzelfall 298. Zwei Zeilen zeigen."""
    r = _mit_mutation(
        CSS,
        ".va-grund{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;",
        ".va-grund{display:block;overflow:visible;")
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl der Ampel-Grund ungekuerzt steht"
    # ⚠ Der Deckel kostet im Medianfall nur EINE Zeile (19 px) und liegt damit unter jeder
    # brauchbaren Pixelschwelle. Gemeldet wird deshalb die Zeilenzahl, nicht der Vorspann.
    assert "Zeilen" in r.stdout, r.stdout

"""„Euer Ueberblick" steht in einer Reihe, und die Leitzahl meint diese Woche — GEMESSEN.

⚠ WARUM ES DIESEN TEST GIBT. Der Block war als `repeat(4,minmax(0,1fr))` geschrieben, also
sichtbar als eine Reihe gemeint, und war auf keinem gemessenen Arbeitsbildschirm eine: bei
1512 und 1440 px blieben drei Spalten uebrig und „Markt & Netzwerk" rutschte unter „Jetzt
bewerben". Eine Textpruefung haette die vier Spalten bestaetigt. Nur eine Messung sieht,
dass `1fr` unter Platzmangel umbricht.

Dazu die zweite Haelfte desselben Befunds: vier gleich laute 30-px-Zahlen mit voellig
verschiedener Bedeutung, die lauteste davon 10.018 Fristen binnen drei Wochen — eine Zahl,
die niemand heute anfassen kann.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "scripts" / "pruefe_ueberblick.py"
CSS = WURZEL / "web" / "app" / "explorer.css"
TSX = WURZEL / "web" / "components" / "explorer" / "DetailPanel.tsx"


def _lauf():
    return subprocess.run([sys.executable, str(SONDE)],
                          capture_output=True, text=True, cwd=WURZEL, timeout=180)


def _mit_mutation(*tausche: tuple[Path, str, str]):
    """Tauscht Anker und gibt den Lauf zurueck — Dateien danach wieder wie vorher."""
    echt = {d: d.read_text(encoding="utf-8") for d, _, _ in tausche}
    try:
        for datei, alt, neu in tausche:
            jetzt = datei.read_text(encoding="utf-8")
            assert jetzt.count(alt) == 1, (
                f"Anker nicht eindeutig ({jetzt.count(alt)}x) in {datei.name}: {alt[:70]}")
            datei.write_text(jetzt.replace(alt, neu, 1), encoding="utf-8")
        return _lauf()
    finally:
        for datei, inhalt in echt.items():
            datei.write_text(inhalt, encoding="utf-8")


def test_der_ueberblick_steht_in_einer_reihe():
    """Ohne Playwright/Chromium gibt die Sonde keine Auskunft — das ist kein Befund."""
    r = _lauf()
    if r.returncode == 2:
        return
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]
    assert "eine Reihe" in r.stdout


def test_die_sonde_sieht_den_umbruch_der_vier_gleichen_spalten():
    """Gegenprobe mit GENAU DEM ZUSTAND, der da war: vier Spalten `minmax(0,1fr)`."""
    r = _mit_mutation(
        (CSS,
         ".lb-zwei{display:grid;grid-template-columns:1.6fr 1fr;gap:var(--s6);align-items:start}",
         ".lb-zwei{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));"
         "gap:var(--s6);align-items:start}"),
        # ⚠ Die vier Spalten allein stellen den alten Zustand NICHT wieder her: im Raster
        # stehen heute zwei Kinder, vier Spalten bleiben dann drei leer und brechen nie um.
        # Erst `display:contents` loest den Rahmen auf und macht die drei Kontextbloecke
        # wieder zu eigenen Rasterfeldern — genau die Anordnung vom 2026-09-20.
        (CSS, ".lb-kontext{display:flex;flex-direction:column;gap:var(--s5);min-width:0}",
         ".lb-kontext{display:contents}"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl die Abschnitte wieder umbrechen"
    assert "Reihen" in r.stdout, r.stdout


def test_die_sonde_sieht_gleich_breite_spalten():
    """⚠ Gleicher Rang ist kein Layoutfehler, den ein Umbruchzaehler sieht: zwei gleiche
    Spalten stehen sauber in EINER Reihe. Nur die Breitenmessung merkt, dass die
    Arbeitsspalte ihren Vorrang verloren hat."""
    r = _mit_mutation((CSS, "grid-template-columns:1.6fr 1fr;gap:var(--s6)",
                       "grid-template-columns:1fr 1fr;gap:var(--s6)"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl beide Spalten gleich breit sind"
    assert "nicht breiter als der Kontext" in r.stdout, r.stdout


def test_die_sonde_sieht_wenn_auf_schmalen_schirmen_nicht_gestapelt_wird():
    r = _mit_mutation((CSS, "@media (max-width:1100px){.lb-zwei{grid-template-columns:1fr}}",
                       "@media (max-width:600px){.lb-zwei{grid-template-columns:1fr}}"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl 1100 px zweispaltig bleiben"
    assert "gestapelt" in r.stdout, r.stdout


def test_die_sonde_sieht_die_alte_leitzahl():
    """Die drei Wochen als Leitzahl — der Zustand vor dem 2026-09-20.

    ⚠ Diese Gegenprobe braucht kein Playwright: sie greift die Verdrahtung an, nicht das
    Raster. Sie darf deshalb auch dann rot werden, wenn die Messung schweigt.
    """
    r = _mit_mutation(
        (TSX,
         '<p className="lb-n2">{b.dieseWoche.length.toLocaleString("de-DE")}'
         '<em>{t("mit Frist in dieser Woche")}</em></p>',
         '<p className="lb-n2">{b.heiss.length.toLocaleString("de-DE")}'
         '<em>{t("mit Frist in dieser Woche")}</em></p>'))
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl wieder die drei Wochen fuehren"
    assert "statt aus `dieseWoche`" in r.stdout, r.stdout


def test_die_sonde_sieht_die_doppelte_grosse_zahl():
    """Die Zahl ueber den Kacheln wiederholte die erste Kachel: zweimal 1.204."""
    r = _mit_mutation(
        (TSX,
         '<h4><span className="lb-dot luecke" />{t("Was euch bremst")}</h4>',
         '<h4><span className="lb-dot luecke" />{t("Was euch bremst")}</h4>\n'
         '            <p className="lb-n2">{b.luecken[0].n.toLocaleString("de-DE")}'
         '<em>{t("Luecken")}</em></p>'))
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl dieselbe Zahl zweimal dasteht"
    assert "grosse Zahlen" in r.stdout, r.stdout


def test_die_sonde_sieht_eine_veraenderte_sieben_tage_grenze():
    r = _mit_mutation((TSX, "const dieseWoche = heiss.filter((l) => (tageOf(l) ?? 99) <= 7);",
                       "const dieseWoche = heiss.filter((l) => (tageOf(l) ?? 99) <= 21);"))
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl diese Woche drei Wochen meint"
    assert "sieben Tagen" in r.stdout, r.stdout

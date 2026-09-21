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
    """Gegenprobe mit GENAU DEM ZUSTAND, der da war: vier Spalten `minmax(0,1fr)`.

    ⚠ Drei Mutationen, nicht eine, und das ist der Lerneffekt: im Raster stehen heute zwei
    Kinder. Vier Spalten allein lassen drei davon leer und brechen nie um. Erst wenn Rahmen
    UND Kachelraster aufgeloest sind, stehen wieder sechs Felder nebeneinander.
    """
    r = _mit_mutation(
        (CSS,
         ".lb-zwei{display:grid;grid-template-columns:640px minmax(0,1fr);gap:var(--s6);align-items:start}",
         ".lb-zwei{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));"
         "gap:var(--s6);align-items:start}"),
        # ⚠ Die vier Spalten allein stellen den alten Zustand NICHT wieder her: im Raster
        # stehen heute zwei Kinder, vier Spalten bleiben dann drei leer und brechen nie um.
        # Erst `display:contents` loest den Rahmen auf und macht die drei Kontextbloecke
        # wieder zu eigenen Rasterfeldern — genau die Anordnung vom 2026-09-20.
        (CSS, ".lb-kontext{display:flex;flex-direction:column;gap:var(--s5);min-width:0}",
         ".lb-kontext{display:contents}"),
        (CSS, ".lb-kx{display:grid;grid-template-columns:1fr 1fr;gap:8px}",
         ".lb-kx{display:contents}"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl die Abschnitte wieder umbrechen"
    assert "Reihen" in r.stdout, r.stdout


def test_die_sonde_sieht_gleich_breite_spalten():
    """⚠ Gleicher Rang ist kein Layoutfehler, den ein Umbruchzaehler sieht: zwei gleiche
    Spalten stehen sauber in EINER Reihe. Nur die Breitenmessung merkt, dass die
    Arbeitsspalte ihren Vorrang verloren hat."""
    # ⚠ Der Anker traegt seit dem 2026-09-21 eine feste Breite; der Anspruch ist
    # derselbe geblieben: die Arbeitsspalte muss breiter sein als der Kontext.
    r = _mit_mutation((CSS, "grid-template-columns:640px minmax(0,1fr);gap:var(--s6)",
                       "grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--s6)"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl beide Spalten gleich breit sind"
    assert "nicht breiter als der Kontext" in r.stdout, r.stdout


def test_die_sonde_sieht_wenn_auf_schmalen_schirmen_nicht_gestapelt_wird():
    r = _mit_mutation((CSS, "@media (max-width:1150px){.lb-zwei{grid-template-columns:1fr}}",
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


def test_die_sonde_sieht_eine_zweite_grosse_zahl():
    """Die Zahl ueber den Kacheln wiederholte die erste Kachel: zweimal 1.204 untereinander.

    ⚠ Die Gegenprobe setzt sie woanders wieder ein als damals, und das ist Absicht: geprueft
    wird die REGEL (eine einzige Leitzahl), nicht die Stelle, an der sie einmal verletzt war.
    """
    r = _mit_mutation((
        TSX, '          <div className="lb-kx">',
        '          <p className="lb-n2">{b.netz.length}<em>{t("Lose")}</em></p>\n'
        '          <div className="lb-kx">'))
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl zwei Zahlen gleich laut sprechen"
    assert "grosse Zahlen" in r.stdout, r.stdout


def test_die_sonde_sieht_eine_veraenderte_sieben_tage_grenze():
    r = _mit_mutation((TSX, "const dieseWoche = heiss.filter((l) => (tageOf(l) ?? 99) <= 7);",
                       "const dieseWoche = heiss.filter((l) => (tageOf(l) ?? 99) <= 21);"))
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl diese Woche drei Wochen meint"
    assert "sieben Tagen" in r.stdout, r.stdout


def test_die_sonde_sieht_eine_zweite_gleich_laute_zahl():
    """Der Befund, mit dem der Umbau anfing: vier gleich laute 30-px-Zahlen nebeneinander.

    ⚠ Kein Umbruch, keine falsche Breite, kein fehlender Text — die Anordnung bleibt exakt
    dieselbe. Nur die BERECHNETE Schriftgroesse verraet es. Eine Textpruefung haette hier
    nichts zu lesen.
    """
    r = _mit_mutation((CSS, ".kx-n{font-size:19px;", ".kx-n{font-size:30px;"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl vier Zahlen gleich laut sind"
    assert "gleich laute Zahlen" in r.stdout, r.stdout


def test_die_sonde_sieht_eine_kachel_mehr():
    """Die Decke gegen das Zuwachsen. ⚠ Beweist zugleich, dass das Blatt seine Fuellung aus
    dem Bauteil zieht: eine Kachel im TSX muss in der MESSUNG ankommen."""
    r = _mit_mutation((
        TSX,
        '          {/* Die Strategie ist keine Zahl',
        '            <Kachel n={"7"} label={t("Testkachel")} sub={t("dazugebaut")}\n'
        '              ziel={() => onGoto?.("award")} />\n'
        '          {/* Die Strategie ist keine Zahl'))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl eine Kachel dazugekommen ist"
    assert "klickbare Flaechen" in r.stdout, r.stdout


def test_die_sonde_sieht_mehr_zeilen_in_der_arbeitsspalte():
    """Zweiter Beweis fuer dieselbe Ableitung, von der anderen Seite."""
    r = _mit_mutation((TSX, "b.heiss.slice(0, 5)", "b.heiss.slice(0, 9)"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl vier Zeilen dazugekommen sind"
    assert "klickbare Flaechen" in r.stdout, r.stdout


def test_die_sonde_merkt_wenn_sie_an_der_wirklichkeit_vorbei_misst():
    """⚠ Die gefaehrlichste Luege dieser Sonde: sie misst ein NACHGEBAUTES Blatt. Benennt
    jemand im Bauteil eine Klasse um, misst sie weiter eine Anordnung, die niemand mehr
    ausliefert. Genau dieser Fall muss auffallen, und zwar ohne Playwright."""
    r = _mit_mutation((TSX, 'className="lb-kx"', 'className="lb-kacheln"'))
    assert r.returncode == 1, "die Sonde misst weiter, obwohl das Bauteil die Klasse nicht mehr kennt"
    assert "nicht mehr gibt" in r.stdout, r.stdout


def test_die_arbeitsspalte_hat_auf_allen_breiten_dieselbe_breite():
    """Sven am 2026-09-21: „kannst du dem linken bereich eine feste breite geben?"

    ⚠ Mit `1.6fr 1fr` schwankte sie gemessen zwischen 649 px (1150er Fenster) und 901 px
    (1728er). Die Titel sind ohnehin auf 58 Zeichen beschnitten; mehr Breite bringt keinen
    Text mehr, sie verteilt nur Luft — und dieselbe Liste liest sich auf jedem Rechner
    anders.
    """
    r = _lauf()
    if r.returncode == 2:
        return
    assert r.returncode == 0, r.stdout[-1200:]


def test_die_sonde_sieht_eine_wieder_mitwachsende_spalte():
    r = _mit_mutation((CSS, "grid-template-columns:640px minmax(0,1fr);gap:var(--s6)",
                       "grid-template-columns:1.6fr 1fr;gap:var(--s6)"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl die Spalte wieder mitwaechst"
    assert "nicht ueberall gleich breit" in r.stdout, r.stdout


def test_die_sonde_sieht_wenn_die_feste_breite_auf_schmalen_fenstern_gewinnt():
    """⚠ DER FALL, DER IM ENTWURF PASSIERT IST. Die Media-Query muss dieselbe Spezifitaet
    haben und danach stehen; sonst bleibt die feste Breite auch bei 820 px stehen und die
    Seite laeuft quer. Genau das hat mein Prototyp mit `.b .lb-zwei` getan."""
    r = _mit_mutation((CSS, "@media (max-width:1150px){.lb-zwei{grid-template-columns:1fr}}",
                       "@media (max-width:1150px){.lb-zwei.eng{grid-template-columns:1fr}}"))
    if r.returncode == 2:
        return
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl die feste Breite nicht weicht"
    assert "quer" in r.stdout or "gestapelt" in r.stdout, r.stdout


def test_die_arbeitsspalte_traegt_einen_rahmen():
    """Rechts stehen vier gerahmte Kacheln; links stand der Inhalt frei auf der Flaeche."""
    css = CSS.read_text(encoding="utf-8")
    assert ".lb-zwei > .lb-sp{border:1px solid var(--line)" in css, (
        "die Arbeitsspalte hat ihren Rahmen verloren")

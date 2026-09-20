#!/usr/bin/env python3
"""Bleibt die Unterlagen-Seite ueberschaubar? GEMESSEN mit echten Analysedaten.

⚠ WARUM DIESE SONDE EXISTIERT. Sven am 2026-09-20: „ich will mit dir an der unterlagen
seite arbeiten, die ist total unuebersichtlich, aber die wichtigste seite die wir haben."
Nachgemessen an einem Median-Fall (58 Pruefpunkte) stimmte das in einer Groessenordnung,
die niemand geschaetzt haette:

    Knoepfe auf der Seite            239
    Textfelder                        58
    Hoehe wie ausgeliefert         5.473 px   (6 Bildschirme)
    Hoehe ganz aufgeklappt        19.837 px   (22 Bildschirme)

Ursache war nicht die Zahl der Abschnitte — die liegt bei hoechstens vier —, sondern die
Bauform EINES Pruefpunkts: jeder war ein aufgeklappter Kasten mit Zitatblock, Textfeld und
zwei Knoepfen, 58 mal untereinander. Geschrieben wird in eine Handvoll davon.

⚠ DIESE SONDE FAEHRT DEN ECHTEN CODE. `renderChecklistBlock` wird aus `explorerCore.js`
ausgeschnitten und mit einer echten Analyse aus `web/data/doc-analysis/` gerendert; das
Ergebnis misst ein Browser mit dem echten Stylesheet. Ein nachgebautes Blatt wuerde genau
die Unruhe verschweigen, um die es geht.

Aufruf:  python3 scripts/pruefe_unterlagen.py [--still] [--id <notice-id>]
Rueckgabe: 0 in Ordnung · 1 Befund · 2 keine Auskunft (kein Playwright, keine Daten)
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

WURZEL = pathlib.Path(__file__).resolve().parent.parent
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
ANALYSEN = WURZEL / "web" / "data" / "doc-analysis"

# ⚠ DECKEL, KEINE MESSWERTE. Sie halten den Zustand vom 2026-09-20 fest; wer sie hebt,
# hebt sie bewusst. Gemessen wurde damals: 1.466 px geliefert, 3.444 px mit allen Gruppen
# offen, 122 sichtbare Knoepfe (je Punkt ein Haken und die Zeile selbst).
MAX_HOEHE_GELIEFERT = 2_000
MAX_HOEHE_GRUPPEN_OFFEN = 4_500
# Sichtbare Knoepfe je Pruefpunkt: der Haken und die Zeile. Ein dritter waere ein Rueckfall
# in die alte Bauform, in der jeder Punkt seine zwei Baustein-Knoepfe offen trug.
MAX_KNOEPFE_JE_PUNKT = 2
# Sichtbare Textfelder, solange kein Punkt aufgeklappt ist. 58 waren es vorher.
MAX_TEXTFELDER_ZU = 0
# ⚠ DER VORSPANN. Sven am 2026-09-20: „mir ist das zu viel text wenn man auf die seite
# kommt." Gemessen waren es 533 px und 110 Woerter bis zum ersten Pruefpunkt — zwei
# Absaetze Prosa (beide bei 100 % der Auswertungen vorhanden), drei Kaesten uebereinander.
# Danach: 308 px und 59 Woerter. Die Woerter zaehlen mit, weil Pixel sich durch kleinere
# Schrift schoenrechnen lassen.
MAX_VORSPANN_PX = 370
MAX_VORSPANN_WORTE = 70
# Der Ampel-Grund BLEIBT — er sagt, warum die Ampel so steht, und das ist die eine Aussage,
# wegen der man herkommt. Gekuerzt wird nur die Ansicht: zwei Zeilen, der Rest auf Klick.
MAX_GRUND_ZEILEN = 2


def _median_fall() -> pathlib.Path | None:
    """Eine Analyse mit ungefaehr der mittleren Zahl an Pruefpunkten (58)."""
    idx = WURZEL / "web" / "data" / "doc-analysis-index.json"
    if not idx.exists() or not ANALYSEN.is_dir():
        return None
    try:
        ana = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:
        return None
    kand = sorted(ana.items(), key=lambda kv: abs((kv[1].get("pruef") or 0) - 58))
    for k, _ in kand[:40]:
        f = ANALYSEN / f"{k}.json"
        if f.exists():
            return f
    return None


def _schnitt(src: str, start: str, ende: str) -> str:
    i = src.index(start)
    return src[i:src.index(ende, i)]


def _rendern(analyse: pathlib.Path, ziel: pathlib.Path) -> bool:
    """Die echte Checkliste bauen. Die drei Zusatzbloecke (Fenster/Profil/Umfang) sind
    gestubbt — sie kaemen NOCH dazu, jede Messung hier ist also eine Untergrenze."""
    src = CORE.read_text(encoding="utf-8")
    try:
        teile = "\n".join((
            _schnitt(src, "function zitat(roh){", "\nfunction renderChecklistBlock"),
            _schnitt(src, "const _CL_GROUPS = [", "function _clDone"),
            _schnitt(src, "function renderChecklistBlock(a, l){", "\n// Download-Knopf"),
            # ⚠ DER AMPEL-KOPF GEHOERT DAZU. Er steht in `renderDocs` und traegt die zwei
            # Absaetze Prosa, um die es Sven ging („mir ist das zu viel text wenn man auf
            # die seite kommt"). Eine Messung, die nur die Checkliste kennt, misst den
            # Vorspann nicht — und genau der war der Befund.
            # ⚠ Der Schnitt endet MITTEN in der Funktion: im Original laeuft sie hinter
            # dem Checklisten-Zweig weiter in den Alt-Format-Fall. Deshalb wird sie hier
            # geschlossen — ohne das meldet node nur „Unexpected token 'export'".
            _schnitt(src, "const head = l.lbAnalyse ? (()=>{", "    // Legacy-Fallback")
              .replace("const head = l.lbAnalyse ? (()=>{", "function kopf(l){", 1)
              + "\n  return '';\n}\n",
        ))
    except ValueError:
        return False
    js = """
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const tk = (s, v) => v ? Object.entries(v).reduce((a,[k,x]) => a.replace('{'+k+'}', x), s) : s;
  const aktuelleSprache = () => 'de';
  const _clDone = () => ({}); const _clHasBlocks = () => false; const _markBadge = () => '';
  const schwellenVergleich = () => ''; const schwellenEinheit = () => '';
  const renderFensterBlock = () => ''; const renderProfilBlock = () => '';
  const renderUmfangBlock = () => ''; const renderUnterlagenstand = () => '';
  const verlaesslichkeit = () => '';
  const dropFeld = () => ''; const istOffen = false;
""" + teile + "\n  export { kopf };\n"
    css = (WURZEL / "web" / "app" / "globals.css").read_text(encoding="utf-8")
    css += "\n" + (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as t:
        mod = pathlib.Path(WURZEL / "web" / f".pruefe-unterlagen-{pathlib.Path(t).name}.mjs")
        treiber = pathlib.Path(t) / "treiber.mjs"
        mod.write_text(js, encoding="utf-8")
        treiber.write_text(f"""
import {{ readFileSync, writeFileSync }} from "node:fs";
const {{ kopf }} = await import({json.dumps(str(mod))});
const a = JSON.parse(readFileSync({json.dumps(str(analyse))}, "utf8"));
const l = {{ id: "x", lbFiles: 5, lbAnalyse: a, unterlagen: {{ url: "https://x" }} }};
const html = kopf(l);
writeFileSync({json.dumps(str(ziel))},
  '<meta charset="utf-8"><style>' + {json.dumps(css)}
  + "\\nbody{{margin:0;font-family:system-ui;background:var(--surface)}}</style>"
  + '<div class="dbody dbody-ov">' + html + '</div>');
""", encoding="utf-8")
        try:
            r = subprocess.run(["node", str(treiber)], capture_output=True, text=True,
                               cwd=WURZEL / "web", timeout=120)
            return r.returncode == 0 and ziel.exists()
        except Exception:
            return False
        finally:
            mod.unlink(missing_ok=True)


def messen(blatt: pathlib.Path) -> dict | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 760, "height": 900})
            pg.goto(blatt.as_uri())
            raus = pg.evaluate("""() => {
                const sicht = s => [...document.querySelectorAll(s)].filter(e => e.offsetParent).length;
                const erst = document.querySelector('article.item');
                const kopf = document.querySelector('.va-sec') || document.body;
                /* ⚠ AM ELEMENT SCHNEIDEN, NICHT AM WORT. Der erste Anlauf trennte den
                   Vorspann am Text „K.-o.-Kriterien" — der stand aber AUCH in den
                   Sprungmarken daruber, also mitten im Vorspann. Gezaehlt wurden dann 62
                   statt 69 Woerter: die Messung log zugunsten des gemessenen Zustands. */
                /* ⚠ ZWEIMAL DANEBEN, BEVOR ES STIMMTE. Erst schnitt ich am Text
                   „K.-o.-Kriterien" — der stand auch in den Sprungmarken, also mitten im
                   Vorspann (gezaehlt: 62 statt 69, die Messung log zu meinen Gunsten).
                   Dann schnitt ich am Element, per Range — die liest aber auch den TEXT
                   IN ZUGEKLAPPTEN `<details>` mit (112 statt 69), also log sie in die
                   andere Richtung. Gezaehlt wird, was ein Mensch SIEHT: `innerText` je
                   Block, und der laesst zugeklappte Inhalte weg. */
                const g1 = document.querySelector('details.grp');
                const bloecke = [];
                for (const wurzel of [kopf, kopf.querySelector('.va-checklist')]) {
                    if (!wurzel) continue;
                    for (const kind of wurzel.children) {
                        if (kind === g1 || kind.contains(g1)) break;
                        if (kind.matches('details.grp')) break;
                        bloecke.push(kind.innerText || '');
                    }
                }
                const vor = bloecke.join(' ');
                const a = { punkte: document.querySelectorAll('article.item').length,
                            ta_zu: sicht('textarea'),
                            vorspann: erst ? Math.round(erst.getBoundingClientRect().top) : 0,
                            vorworte: vor.trim().split(/[ \\n\\t]+/).filter(Boolean).length,
                            h_zu: Math.round(document.body.scrollHeight) };
                document.querySelectorAll('details.grp').forEach(d => d.open = true);
                a.knoepfe = sicht('button');
                /* ⚠ DEN DECKEL DIREKT MESSEN, NICHT UEBER DIE GESAMTHOEHE. Ein
                   ungekuerzter Ampel-Grund kostet im Medianfall nur EINE Zeile (19 px) —
                   unter jeder brauchbaren Pixelschwelle. Im schlechtesten Fall (298
                   Zeichen) sind es drei. Gezaehlt werden deshalb die Zeilen. */
                const g = document.querySelector('.va-grund');
                if (g) {
                    const lh = parseFloat(getComputedStyle(g).lineHeight) || 20;
                    a.grund_zeilen = Math.round(g.getBoundingClientRect().height / lh);
                }
                a.h_offen = Math.round(document.body.scrollHeight);
                // Ein aufgeklappter Punkt MUSS Fundstelle und Baustein zeigen — sonst ist
                // die Ruhe damit erkauft, dass die Funktion verschwunden ist.
                const eins = document.querySelector('article.item');
                if (eins) eins.classList.add('auf');
                a.ta_auf = sicht('textarea');
                a.zitat_auf = sicht('.quote');
                return a;
            }""")
            b.close()
            return raus
    except Exception:
        return None


def main() -> int:
    still = "--still" in sys.argv
    if "--id" in sys.argv:
        analyse = ANALYSEN / (sys.argv[sys.argv.index("--id") + 1] + ".json")
    else:
        analyse = _median_fall()
    if analyse is None or not analyse.exists():
        if not still:
            print("  (keine Analysedaten unter web/data/doc-analysis — keine Auskunft)")
        return 2

    with tempfile.TemporaryDirectory() as t:
        blatt = pathlib.Path(t) / "checkliste.html"
        if not _rendern(analyse, blatt):
            if not still:
                print("  (die Checkliste liess sich nicht rendern — keine Auskunft)")
            return 2
        m = messen(blatt)
    if m is None:
        if not still:
            print("  (kein Playwright/Chromium — keine Auskunft)")
        return 2

    befunde = []
    n = max(1, m["punkte"])
    if m["h_zu"] > MAX_HOEHE_GELIEFERT:
        befunde.append(f"die Seite ist beim Oeffnen {m['h_zu']:,} px hoch "
                       f"(hoechstens {MAX_HOEHE_GELIEFERT:,})")
    if m["h_offen"] > MAX_HOEHE_GRUPPEN_OFFEN:
        befunde.append(f"mit allen Gruppen offen sind es {m['h_offen']:,} px "
                       f"(hoechstens {MAX_HOEHE_GRUPPEN_OFFEN:,})")
    if m["knoepfe"] > n * MAX_KNOEPFE_JE_PUNKT + 20:
        befunde.append(f"{m['knoepfe']} sichtbare Knoepfe bei {n} Pruefpunkten "
                       f"(hoechstens {MAX_KNOEPFE_JE_PUNKT} je Punkt)")
    if m["ta_zu"] > MAX_TEXTFELDER_ZU:
        befunde.append(f"{m['ta_zu']} Textfelder stehen offen, ohne dass jemand einen Punkt "
                       "aufgeklappt hat")
    if m.get("grund_zeilen", 0) > MAX_GRUND_ZEILEN:
        befunde.append(f"der Ampel-Grund steht in {m['grund_zeilen']} Zeilen "
                       f"(hoechstens {MAX_GRUND_ZEILEN}, der Rest auf Klick)")
    if m["vorspann"] > MAX_VORSPANN_PX:
        befunde.append(f"bis zum ersten Pruefpunkt stehen {m['vorspann']} px Vorspann "
                       f"(hoechstens {MAX_VORSPANN_PX})")
    if m["vorworte"] > MAX_VORSPANN_WORTE:
        befunde.append(f"{m['vorworte']} Woerter stehen vor dem ersten Pruefpunkt "
                       f"(hoechstens {MAX_VORSPANN_WORTE})")
    # ⚠ Die Gegenrichtung: Ruhe darf nicht durch Verlust entstehen.
    if m["ta_auf"] < 1 or m["zitat_auf"] < 1:
        befunde.append("ein aufgeklappter Pruefpunkt zeigt keine Fundstelle oder kein "
                       "Textfeld mehr — die Ruhe waere mit der Funktion erkauft")

    if befunde:
        if not still:
            print("  " + "\n  ".join(befunde))
        return 1
    if not still:
        print(f"  Unterlagen: {n} Pruefpunkte · {m['h_zu']:,} px beim Oeffnen · "
              f"{m['h_offen']:,} px mit allen Gruppen · {m['knoepfe']} sichtbare Knoepfe · "
              f"Vorspann {m['vorspann']} px / {m['vorworte']} Woerter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

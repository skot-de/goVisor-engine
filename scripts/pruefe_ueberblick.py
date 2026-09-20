#!/usr/bin/env python3
"""Bleibt „Euer Ueberblick" auf uebliche Bildschirmen in EINER Reihe, und zeigt die
Leitzahl etwas, das man heute anfassen kann? GEMESSEN, nicht gelesen.

⚠ WARUM DIESE SONDE EXISTIERT. Bis zum 2026-09-20 standen die vier Abschnitte in

    .lb-drei{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}

Das sah im Quelltext nach einer Reihe aus und war auf **keinem der gemessenen
Arbeitsbildschirme** eine: bei 1512 und 1440 px blieben nur drei Spalten uebrig, „Markt &
Netzwerk" rutschte unter „Jetzt bewerben", und der Block wurde 603 px hoch mit einem
weissen Loch neben sich. Erst ab 1728 px passte die Reihe. Die Zahl `repeat(4, …)` war
richtig geschrieben und galt trotzdem nicht, weil `minmax(0,1fr)` unter dem Gesamtplatz
umbricht. Wieder ein Fall fuer: **wo das Ergebnis aus einer Kaskade entsteht, muss man das
Ergebnis messen** (s. `pruefe_marken_optik.py`).

Zweiter Befund derselben Sitzung: die Leitzahl war „10.018 offene Fristen" (drei Wochen).
Eine Zahl, die niemand heute anfassen kann, und daneben drei weitere gleich laute Zahlen
mit voellig anderer Bedeutung. Die Leitzahl ist jetzt die Frist DIESER WOCHE; die drei
Wochen stehen klein darunter. Diese Sonde haelt beides fest: die Reihe UND die Herkunft
der Leitzahl.

Aufruf:  python3 scripts/pruefe_ueberblick.py [--still]
Rueckgabe: 0 in Ordnung · 1 Befund · 2 keine Auskunft (kein Playwright/Chromium)
"""
from __future__ import annotations

import pathlib
import re
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
TSX = WURZEL / "web" / "components" / "explorer" / "DetailPanel.tsx"

# Breiten, die auf diesem Schreibtisch und bei Sven vorkommen. ⚠ 1728 ist ein MacBook Pro
# 16" im Standard, 1512 das 14", 1440 ein gaengiger externer Schirm, 1280 ein kleines
# Fenster. Faellt die Reihe bei einer davon auseinander, ist es kein Randfall.
BREITEN = (1728, 1512, 1440, 1280)

# Unter dieser Breite DARF gestapelt werden — ein Telefon oder ein halbes Fenster kann
# keine zwei Spalten tragen, und das Stapeln ist dort die richtige Antwort, kein Fehler.
STAPELN_ERLAUBT_UNTER = 1100


def _blatt(ziel: pathlib.Path) -> None:
    css = (WURZEL / "web" / "app" / "globals.css").read_text(encoding="utf-8")
    css += "\n" + (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    # Fuellung in der Groessenordnung des echten Bestands: fuenf Zeilen links, drei
    # Kacheln in der Mitte, drei Kacheln unten. Weniger wuerde die Reihe leichter
    # aussehen lassen, als sie ist.
    zeilen = "".join(
        '<button class="lb-z"><span class="lb-zt">Ausschreibung Rahmenvertrag '
        'Bauherrenvertretung und Projektsteuerung</span>'
        '<span class="lb-zs">Bundesamt fuer Bauten und Logistik · noch 1 Tage</span></button>'
        for _ in range(5))
    kacheln = "".join(
        f'<button class="lb-kachel"><b>{n}</b><span><i>{ti}</i>. {tx}</span></button>'
        for n, ti, tx in (
            ("1.204", "Ohne Bundesland", "Ergaenzt eure Region, dann filtert der Umkreis."),
            ("311", "Ohne Eignungsnachweis", "Hinterlegt Zertifikate, dann fallen K.-o.-Kriterien weg."),
            ("88", "Ohne Referenzen", "Mit Referenzen steigt die Trefferquote.")))
    markt = "".join(
        f'<button class="lb-kachel"><b>{n}</b><span>{tx}</span></button>'
        for n, tx in (
            ("37", "Mehrlos-Vergaben, u.a. bei DB Netz und Stadt Koeln, hier lohnt ein Partner"),
            ("12", "frische Zuschlaege, u.a. an Strabag und Zueblin"),
            ("→", "Strategie: wohin sich euer Markt bewegt")))
    ziel.write_text(
        '<meta charset="utf-8"><style>' + css + """
body{margin:0;font-family:system-ui}
.lb-z{display:flex;flex-direction:column;align-items:flex-start;gap:2px;background:none;
  border:0;text-align:left;padding:5px 0;max-width:100%}
.lb-zt{font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;max-width:100%}
.lb-zs{font-size:11.5px}</style>"""
        '<div class="lb"><div class="lb-zwei">'
        '<section class="lb-sp" data-a="jetzt"><h4><span class="lb-dot heiss"></span>'
        '<button class="lb-h4btn">Jetzt bewerben</button></h4>'
        '<p class="lb-n2">1.148<em>mit Frist in dieser Woche</em></p>'
        '<p class="lb-rahmen">6.501 innerhalb von drei Wochen</p>' + zeilen + '</section>'
        '<div class="lb-kontext">'
        '<section class="lb-sp" data-a="bald"><h4><span class="lb-dot bald"></span>Bahnt sich an</h4>'
        '<p class="lb-n2">14<em>Ankuendigungen und auslaufende Vertraege</em></p></section>'
        '<section class="lb-sp" data-a="bremst"><h4><span class="lb-dot luecke"></span>'
        'Was euch bremst</h4>' + kacheln + '</section>'
        '<section class="lb-sp" data-a="markt"><h4>Markt &amp; Netzwerk</h4>' + markt + '</section>'
        '</div></div></div>',
        encoding="utf-8")


def messen() -> dict | None:
    """Je Breite: wie viele Reihen bilden die Abschnitte, und wie breit ist welcher?"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        blatt = pathlib.Path(t) / "ueberblick.html"
        _blatt(blatt)
        try:
            with sync_playwright() as p:
                b = p.chromium.launch()
                raus = {}
                for br in (*BREITEN, STAPELN_ERLAUBT_UNTER):
                    pg = b.new_page(viewport={"width": br, "height": 900})
                    pg.goto(blatt.as_uri())
                    raus[br] = pg.evaluate("""() => {
                        const g = document.querySelector('.lb-zwei');
                        // ⚠ Die Reihen des RASTERS, nicht die der Abschnitte: die drei
                        // Kontextabschnitte stehen absichtlich uebereinander. Ein Zaehler
                        // ueber alle `.lb-sp` meldet deshalb immer drei Reihen und haette
                        // jede Anordnung fuer kaputt erklaert.
                        const kind = [...g.children].map(e => e.getBoundingClientRect());
                        const s = [...g.querySelectorAll('.lb-sp')];
                        return { reihen: new Set(kind.map(x => Math.round(x.top))).size,
                                 hoehe: Math.round(g.getBoundingClientRect().height),
                                 breiten: Object.fromEntries(s.map(e =>
                                          [e.dataset.a, Math.round(e.getBoundingClientRect().width)])) };
                    }""")
                    pg.close()
                b.close()
                return raus
        except Exception:
            return None


def _ohne_kommentar(s: str) -> str:
    """⚠ Sonst prueft diese Sonde die Prosa in DetailPanel.tsx statt den Code. Genau das
    ist am 2026-09-19 fuenfmal an einem Tag passiert."""
    s = re.sub(r"\{/\*.*?\*/\}", " ", s, flags=re.S)
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"(?m)//.*$", " ", s)
    return re.sub(r"\s+", " ", s)


def leitzahl() -> list[str]:
    """Woher kommt die grosse Zahl unter „Jetzt bewerben"?

    ⚠ Die Grenze dieser Pruefung: sie liest, WELCHE Groesse gedruckt wird, nicht, ob die
    Groesse stimmt. Dass `dieseWoche` wirklich sieben Tage meint, haelt die dritte
    Zusicherung fest — mehr kann Text nicht.
    """
    q = _ohne_kommentar(TSX.read_text(encoding="utf-8"))
    befunde = []
    if not re.search(r'const dieseWoche = heiss\.filter\(\(l\) => \(tageOf\(l\) \?\? \d+\) <= 7\)', q):
        befunde.append("`dieseWoche` wird nicht mehr als Frist binnen sieben Tagen aus "
                       "`heiss` gebildet")
    m = re.search(r'className="lb-n2">\{b\.(\w+)\.length', q)
    if not m or m.group(1) != "dieseWoche":
        woher = m.group(1) if m else "?"
        befunde.append(f"die Leitzahl im Ueberblick kommt aus `{woher}` statt aus `dieseWoche`")
    if not re.search(r'className="lb-rahmen">\{t\("\{n\} innerhalb von drei Wochen", \{ n: b\.heiss\.length', q):
        befunde.append("die drei Wochen stehen nicht mehr klein unter der Leitzahl")
    # ⚠ Die zweite grosse Zahl ueber den Luecken-Kacheln wiederholte die erste Kachel:
    # zweimal „1.204" untereinander liest sich wie zwei Befunde und ist einer.
    if q.count('className="lb-n2"') > 2:
        befunde.append(f"es stehen {q.count(chr(34) + 'lb-n2' + chr(34))} grosse Zahlen im "
                       "Ueberblick statt zwei")
    return befunde


def main() -> int:
    still = "--still" in sys.argv
    befunde = leitzahl()

    gemessen = messen()
    if gemessen is None:
        if befunde:
            if not still:
                print("  " + "\n  ".join(befunde))
                print("  (kein Playwright/Chromium — die Reihe wurde NICHT gemessen)")
            return 1
        if not still:
            print("  (kein Playwright/Chromium — keine Auskunft)")
        return 2

    for br in BREITEN:
        m = gemessen[br]
        if m["reihen"] != 1:
            befunde.append(f"bei {br} px stehen die Abschnitte in {m['reihen']} Reihen "
                           f"({m['hoehe']} px hoch) statt in einer")
        # „Jetzt bewerben" ist die einzige Spalte mit Arbeit fuer heute. Sie muss die
        # breiteste sein, sonst behauptet das Raster wieder Gleichrang.
        b = m["breiten"]
        if b.get("jetzt", 0) <= b.get("bremst", 0):
            befunde.append(f"bei {br} px ist „Jetzt bewerben\" {b.get('jetzt')} px breit und "
                           f"damit nicht breiter als der Kontext ({b.get('bremst')} px)")
    eng = gemessen[STAPELN_ERLAUBT_UNTER]
    if eng["reihen"] == 1:
        befunde.append(f"bei {STAPELN_ERLAUBT_UNTER} px steht alles noch nebeneinander — "
                       "so schmal gehoert es gestapelt")

    if befunde:
        if not still:
            print("  " + "\n  ".join(befunde))
        return 1
    if not still:
        h = gemessen[min(BREITEN)]["hoehe"]
        print(f"  Ueberblick: eine Reihe von {max(BREITEN)} bis {min(BREITEN)} px "
              f"({h} px hoch), Leitzahl ist die Frist dieser Woche")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
# ⚠ 1200 GEHOERT DAZU, UND ZWAR WEGEN DES DECKELS. `.lb` ist auf 1240 px begrenzt; oberhalb
# davon ist die Arbeitsspalte auch mit `1.6fr 1fr` ueberall gleich breit, weil der Deckel die
# Schwankung schluckt. Ohne einen Messpunkt UNTERHALB blieb die Gegenprobe gruen, obwohl die
# Spalte wieder mitwuchs — die Sonde mass eine Eigenschaft des Deckels, nicht der Spalte.
BREITEN = (1728, 1512, 1440, 1280, 1200)

# Unter dieser Breite DARF gestapelt werden — ein Telefon oder ein halbes Fenster kann
# keine zwei Spalten tragen, und das Stapeln ist dort die richtige Antwort, kein Fehler.
STAPELN_ERLAUBT_UNTER = 1150

# ⚠ EINE DECKE, KEIN MESSWERT. Der Block ist zweimal zugewachsen, beide Male in kleinen
# Schritten: erst fuenf Vorschau-Zeilen, dann drei Luecken- und drei Markt-Kacheln. Am
# 2026-09-20 waren es 18 Flaechen und 821 px bei rund 800 px sichtbarer Hoehe. Wer die
# naechste Zeile einbaut, soll diese Zahl bewusst heben muessen.
HOECHSTENS_FLAECHEN = 11


def _fuellung() -> tuple[int, int, bool]:
    """Wie viele Zeilen und Kacheln baut das ECHTE Bauteil? Aus dem Quelltext gelesen.

    ⚠ OHNE DIESE ABLEITUNG MISST DIE SONDE NUR SICH SELBST. Zaehlt das Blatt eine feste
    Zahl Kacheln, bleibt sie gruen, waehrend im Bauteil eine fuenfte und sechste stehen —
    und genau so ist der Block zweimal zugewachsen. Jetzt traegt das Blatt so viel, wie
    `DetailPanel.tsx` wirklich rendert.
    """
    q = _ohne_kommentar(TSX.read_text(encoding="utf-8"))
    m = re.search(r"b\.heiss\.slice\(0, (\d+)\)", q)
    return (int(m.group(1)) if m else 5, q.count("<Kachel"), "lb-strat" in q)


def _blatt(ziel: pathlib.Path) -> None:
    zeilen_n, kacheln_n, mit_strat = _fuellung()
    css = (WURZEL / "web" / "app" / "globals.css").read_text(encoding="utf-8")
    css += "\n" + (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    # Fuellung in der Groessenordnung des echten Bestands: fuenf Zeilen links, vier
    # Kacheln rechts. Weniger wuerde den Block leichter aussehen lassen, als er ist.
    zeilen = "".join(
        '<button class="lb-row"><span class="lb-row-t">Ausschreibung Rahmenvertrag '
        'Bauherrenvertretung und Projektsteuerung</span>'
        '<span class="lb-row-s">noch 1 Tage</span></button>'
        for _ in range(zeilen_n))
    muster = (
            ("4 von 6", "Angaben im Profil", "1.204 liegen ausserhalb eurer Regionen"),
            ("1.180", "bahnen sich an", "Ankuendigungen und auslaufende Vertraege"),
            ("37", "Mehrlos-Vergaben", "u.a. bei DB Netz und Stadt Koeln, hier lohnt ein Partner"),
            ("12", "frische Zuschlaege", "u.a. an Strabag und Zueblin, wer gewonnen hat, kauft jetzt ein"))
    kacheln = "".join(
        '<button class="kx"><span class="kx-n">{}</span>'
        '<span class="kx-l">{}</span><span class="kx-s">{}</span></button>'.format(*muster[i % len(muster)])
        for i in range(kacheln_n))
    ziel.write_text(
        '<meta charset="utf-8"><style>' + css + "\nbody{margin:0;font-family:system-ui}</style>"
        '<div class="lb"><div class="lb-zwei">'
        '<section class="lb-sp" data-a="jetzt"><h4><span class="lb-dot heiss"></span>'
        '<button class="lb-h4btn">Jetzt bewerben</button></h4>'
        '<p class="lb-n2">1.148<em>mit Frist in dieser Woche</em></p>'
        '<p class="lb-rahmen">6.501 innerhalb von drei Wochen</p>' + zeilen + '</section>'
        '<div class="lb-kontext" data-a="kontext"><div class="lb-kx">' + kacheln + '</div>'
        + ('<button class="lb-strat">Strategie: wohin sich euer Markt bewegt'
           '<span>&rarr;</span></button>' if mit_strat else "")
        + '</div></div></div>',
        encoding="utf-8")


# ⚠ DIE GRENZE DIESER SONDE: das Blatt oben ist NACHGEBAUT, nicht das echte Bauteil. Zieht
# jemand in `DetailPanel.tsx` andere Klassen ein, misst die Sonde weiter eine Anordnung,
# die niemand mehr ausliefert — und meldet gruen. Genau diese Luecke hat `pruefe_marken_optik`
# einmal eine ganze Spalte uebersehen lassen. Deshalb wird hier geprueft, dass jede Klasse,
# die das Blatt benutzt, im echten Bauteil ueberhaupt vorkommt.
KLASSEN = ("lb-zwei", "lb-kontext", "lb-kx", "kx-n", "kx-l", "kx-s", "lb-strat",
           "lb-n2", "lb-rahmen", "lb-row")


def klassen_pruefen() -> list[str]:
    q = _ohne_kommentar(TSX.read_text(encoding="utf-8"))
    fehlen = [k for k in KLASSEN if f'"{k}' not in q and f' {k}' not in q]
    return ([f"die Sonde misst Klassen, die es im Bauteil nicht mehr gibt: "
             + ", ".join(fehlen)] if fehlen else [])


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
                        const s = [...g.querySelectorAll('[data-a]')];
                        // ⚠ „Laut" heisst: so gross, dass es den Blick zuerst zieht. Genau
                        // EIN Element darf das sein. Vier gleich laute Zahlen waren der
                        // Befund, mit dem dieser Umbau angefangen hat.
                        // ⚠ Nicht „Element ohne Kinder": die Leitzahl `.lb-n2` traegt ein
                        // <em> mit der Beschriftung und waere damit durchgerutscht. Zaehlt
                        // wird der EIGENE Text eines Elements.
                        const eigen = e => [...e.childNodes]
                            .filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
                        const laut = [...g.querySelectorAll('*')].filter(e =>
                            eigen(e) && parseFloat(getComputedStyle(e).fontSize) >= 20).length;
                        return { reihen: new Set(kind.map(x => Math.round(x.top))).size,
                                 quer: document.documentElement.scrollWidth > window.innerWidth,
                                 hoehe: Math.round(g.getBoundingClientRect().height),
                                 laut, flaechen: g.querySelectorAll('button, a').length,
                                 kacheln: new Set([...g.querySelectorAll('.kx')].map(e =>
                                          Math.round(e.getBoundingClientRect().width))).size,
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
    # ⚠ GENAU EINE grosse Zahl. Die zweite stand ueber den Luecken-Kacheln und wiederholte
    # die erste Kachel: zweimal „1.204" untereinander liest sich wie zwei Befunde und ist
    # einer. Seit die Kacheln ihre eigene, kleinere Zahl tragen, ist jede weitere `lb-n2`
    # eine zweite Stimme, die genauso laut spricht wie die Leitzahl.
    n2 = q.count('className="lb-n2"')
    if n2 != 1:
        befunde.append(f"es stehen {n2} grosse Zahlen im Ueberblick statt einer einzigen")
    return befunde


def main() -> int:
    still = "--still" in sys.argv
    befunde = leitzahl() + klassen_pruefen()

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

    # ⚠ DIE ARBEITSSPALTE MUSS AUF ALLEN BREITEN GLEICH BREIT SEIN. Mit `1.6fr 1fr` schwankte
    # sie zwischen 649 und 901 px; Zeilenlaengen, die sich mit dem Fenster aendern, lesen
    # sich auf jedem Rechner anders. Gemessen wird die Gleichheit, nicht die Zahl — wer sie
    # bewusst aendert, soll das an EINER Stelle tun koennen.
    breiten = {gemessen[br]["breiten"].get("jetzt") for br in BREITEN}
    if len(breiten) > 1:
        befunde.append("die Arbeitsspalte ist nicht ueberall gleich breit: "
                       + ", ".join(f"{br} px -> {gemessen[br]['breiten'].get('jetzt')}"
                                   for br in BREITEN))
    for br in BREITEN:
        m = gemessen[br]
        if m.get("quer"):
            befunde.append(f"bei {br} px laeuft die Seite quer")
        if m["reihen"] != 1:
            befunde.append(f"bei {br} px stehen die Abschnitte in {m['reihen']} Reihen "
                           f"({m['hoehe']} px hoch) statt in einer")
        # „Jetzt bewerben" ist die einzige Spalte mit Arbeit fuer heute. Sie muss die
        # breiteste sein, sonst behauptet das Raster wieder Gleichrang.
        b = m["breiten"]
        if b.get("jetzt", 0) <= b.get("kontext", 0):
            befunde.append(f"bei {br} px ist die Arbeitsspalte {b.get('jetzt')} px breit und "
                           f"damit nicht breiter als der Kontext ({b.get('kontext')} px)")
        if m["laut"] != 1:
            befunde.append(f"bei {br} px stehen {m['laut']} gleich laute Zahlen im Block "
                           "statt einer einzigen Leitzahl")
        if m["kacheln"] != 1:
            befunde.append(f"bei {br} px sind die Kacheln unterschiedlich breit "
                           f"({m['kacheln']} Breiten)")
        if m["flaechen"] > HOECHSTENS_FLAECHEN:
            befunde.append(f"bei {br} px stehen {m['flaechen']} klickbare Flaechen im Block "
                           f"(hoechstens {HOECHSTENS_FLAECHEN})")
    eng = gemessen[STAPELN_ERLAUBT_UNTER]
    # ⚠ Auf schmalen Fenstern MUSS die feste Breite weichen. Sie tut es nur, wenn die
    # Media-Query dieselbe Spezifitaet hat und danach steht — im Entwurf mit `.b .lb-zwei`
    # (zwei Klassen) gewann die feste Breite, und bei 820 px lief die Seite quer.
    if eng.get("quer"):
        befunde.append(f"bei {STAPELN_ERLAUBT_UNTER} px laeuft die Seite quer; die feste "
                       "Breite weicht nicht")
    if eng["reihen"] == 1:
        befunde.append(f"bei {STAPELN_ERLAUBT_UNTER} px steht alles noch nebeneinander — "
                       "so schmal gehoert es gestapelt")

    if befunde:
        if not still:
            print("  " + "\n  ".join(befunde))
        return 1
    if not still:
        h = gemessen[min(BREITEN)]["hoehe"]
        f = gemessen[min(BREITEN)]["flaechen"]
        print(f"  Ueberblick: eine Reihe von {max(BREITEN)} bis {min(BREITEN)} px "
              f"({h} px hoch), {f} klickbare Flaechen, eine Leitzahl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

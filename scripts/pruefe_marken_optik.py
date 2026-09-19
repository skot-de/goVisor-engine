#!/usr/bin/env python3
"""Tragen alle Marken einer Tabellenzeile dieselbe Bauform? GEMESSEN, nicht gelesen.

⚠ WARUM DIESE SONDE EXISTIERT. Am 2026-09-19 stand in `explorer.css`:

    .dokpill{font-size:11.5px;font-weight:500; …}

und die Unterlagen-Label standen trotzdem in **13 px** in einer Zeile mit lauter
11,5-px-Marken. Ursache war eine Zeile weiter unten:

    td.c-doks button{font:inherit; …}

`td.c-doks button` ist spezifischer als `.dokpill`, und das `font`-Kuerzel setzt Groesse,
Gewicht, Familie und Zeilenhoehe auf geerbt. Der Wert stand also da, galt aber nicht.

⚠ DER WAECHTER, DEN ES SCHON GAB, WAR GRUEN. `test_tabelle_ruhe.py` prueft, dass
`.dokpill` die richtigen Eigenschaften DEKLARIERT — und genau das tat sie ja. Eine
Textpruefung kann Kaskade und Spezifitaet nicht sehen; sie liest, was jemand geschrieben
hat, nicht, was der Browser daraus macht. Sven hat den Fehler mit blossem Auge gefunden,
nachdem die Suite gruen gemeldet hatte.

Deshalb rendert diese Sonde die Marken mit dem ECHTEN Stylesheet und liest die BERECHNETEN
Werte. Ohne Playwright/Chromium gibt sie keine Auskunft (Rueckgabe 2) statt zu behaupten,
alles sei in Ordnung.

Aufruf:  python3 scripts/pruefe_marken_optik.py [--still]
Rueckgabe: 0 einheitlich · 1 Abweichung · 2 keine Auskunft
"""
from __future__ import annotations

import pathlib
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent

# Marke → (Zelle, HTML des Labels). Die Liste ist der Vertrag: wer eine Marken-Spalte
# hinzufuegt, traegt sie hier ein, sonst prueft die Sonde sie nie.
MARKEN = [
    ("Phase",            "c-src",   '<span class="srcpill src-auslauf">Auslauf</span>'),
    ("Phase Zuschlag",   "c-src",   '<span class="srcpill src-award">Zuschlag</span>'),
    ("Leistung",         "c-natur", '<span class="nat nat-bau">Bauleistung</span>'),
    ("Status gesetzt",   "c-wf",    '<button class="wf-btn"><span class="wf wf-int filled">Interessant</span></button>'),
    ("Status leer",      "c-wf",    '<button class="wf-btn"><span class="wf wf-none">Setzen</span></button>'),
    ("Unterlagen Ja",    "c-doks",  '<button class="dokpill dok-ja dok-ausgewertet">Ja</button>'),
    ("Unterlagen Ja2",   "c-doks",  '<button class="dokpill dok-ja">Ja</button>'),
    ("Unterlagen Link",  "c-doks",  '<button class="dokpill dok-link2">Link</button>'),
    ("Unterlagen Nein",  "c-doks",  '<span class="dokpill dok-nein">Nein</span>'),
]


# ⚠ AUSNAHMEN STEHEN HIER ALS CODE, nicht in einer Textdatei und nicht als Schweigen —
# dieselbe Regel wie in `pruefe_verdrahtung.py`. Wer eine Ausnahme braucht, schreibt den
# Grund daneben; wer keinen hinschreiben kann, hat keine.
OHNE_GRUND_ERLAUBT = {
    # Der leere Status ist KEINE Marke, sondern ein leeres Feld. Ein getoenter Grund wuerde
    # ihn wie einen GESETZTEN Status aussehen lassen — genau die Verwechslung, gegen die
    # die gestrichelte Kontur gebaut ist. Er ist die einzige Kapsel in der Zeile, die eine
    # Aufforderung ist statt einer Auskunft.
    "Status leer",
}


def _blatt(ziel: pathlib.Path) -> None:
    css = (WURZEL / "web" / "app" / "globals.css").read_text(encoding="utf-8")
    css += "\n" + (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    zellen = "".join(
        f'<td class="{z}"><i data-m="{n}">{h}</i></td>' for n, z, h in MARKEN)
    ziel.write_text(
        '<meta charset="utf-8"><style>' + css
        + "\nbody{font-family:system-ui}table.leads{border-collapse:collapse}"
          ".leads td{padding:9px 10px;font-size:13px}i{font-style:normal}</style>"
          f'<table class="leads"><tr>{zellen}</tr></table>',
        encoding="utf-8")


def messen() -> list[dict] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        blatt = pathlib.Path(t) / "marken.html"
        _blatt(blatt)
        try:
            with sync_playwright() as p:
                b = p.chromium.launch()
                pg = b.new_page()
                pg.goto(blatt.as_uri())
                raus = pg.evaluate("""() => [...document.querySelectorAll('[data-m]')].map(i => {
                    const el = i.firstElementChild.classList.contains('wf-btn')
                             ? i.firstElementChild.firstElementChild : i.firstElementChild;
                    const s = getComputedStyle(el);
                    return { name: i.dataset.m, size: s.fontSize, radius: s.borderRadius,
                             pad: s.padding, grund: s.backgroundColor };
                })""")
                b.close()
                return raus
        except Exception:
            return None


def main() -> int:
    still = "--still" in sys.argv
    gemessen = messen()
    if gemessen is None:
        if not still:
            print("  (kein Playwright/Chromium — keine Auskunft)")
        return 2

    befunde = []
    groessen = {m["size"] for m in gemessen}
    if len(groessen) > 1:
        gruppen = {}
        for m in gemessen:
            gruppen.setdefault(m["size"], []).append(m["name"])
        befunde.append("Schriftgroessen laufen auseinander: "
                       + " · ".join(f"{k} → {', '.join(v)}" for k, v in sorted(gruppen.items())))
    if len({m["radius"] for m in gemessen}) > 1:
        befunde.append("die Kapselform ist nicht ueberall dieselbe: "
                       + ", ".join(f"{m['name']} {m['radius']}" for m in gemessen))
    if len({m["pad"] for m in gemessen}) > 1:
        befunde.append("das Polster ist nicht ueberall dasselbe: "
                       + ", ".join(f"{m['name']} {m['pad']}" for m in gemessen))
    # ⚠ Eine Marke ohne Grund liest sich in einer Zeile voller getoenter Kapseln nicht als
    # Zurueckhaltung, sondern als fehlende Farbe. Sven am 2026-09-19: „die farben kommen
    # nicht rueber".
    ohne = [m["name"] for m in gemessen
            if m["grund"] in ("rgba(0, 0, 0, 0)", "transparent")
            and m["name"] not in OHNE_GRUND_ERLAUBT]
    if ohne:
        befunde.append("ohne getoenten Grund: " + ", ".join(ohne))

    if not befunde:
        if not still:
            print(f"  ✓ {len(gemessen)} Marken, eine Bauform "
                  f"({groessen.pop()}, {gemessen[0]['radius']}, {gemessen[0]['pad']})")
        return 0
    print("  ⛔ Die Marken einer Zeile sehen nicht gleich aus:\n")
    for b in befunde:
        print(f"     · {b}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Wächter über die Wertetabellen: trägt JEDE von ihnen jedes aktive Land?

⚠ **WARUM ES DAS BRAUCHT — und warum eine zentrale Länderliste allein NICHT reicht.**
Eine Liste kann `DE=5, AT=4` nicht erfinden; das ist Länderwissen, das jemand messen muss.
Was sie kann, ist einen fehlenden Eintrag LAUT machen. Denn genau diese Tabellen scheitern
lautlos — gemessen am 2026-09-03, als Luxemburg dazukam:

    gold._PLZ_STELLEN        fehlte → `[0-9]{5}` trifft keine vierstellige PLZ, der Lead
                                      fällt auf den ORTSNAMEN zurück. Abdeckung blieb
                                      279/279, nur die Genauigkeit war weg: 0 statt 127
                                      Leads über die PLZ.
    export_suppliers._STELLEN fehlte → `soll` ist None, `if soll and …` verwirft JEDE
                                      luxemburgische Region. Firmen auffindbar, aber ohne
                                      Einsatzgebiet.
    locales.LOCALES          fehlte → alles läuft mit dem DE-Default weiter.

Kein Fehler, keine leere Tabelle, keine Ausnahme. Nur ein schlechteres Ergebnis, das
niemandem auffällt. Diese Prüfung hätte alle drei am selben Tag gemeldet, statt sie über
Stunden einzeln finden zu lassen.

⚠ **Das ist die Umkehrung von Kapitel 15 der Länder-Bibel.** Dort steht eine Textliste, die
man abarbeitet; hier ein Wächter, der sich meldet.

Aufruf:  python3 scripts/pruefe_laender_tabellen.py [--alle]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── Welche Länder gelten als aktiv ──────────────────────────────────────────────────────
def aktive_laender() -> list[str]:
    """Aus dem BESTAND, nicht aus einer Liste im Code.

    ⚠ `lead_export.parquet` ist der Marker, nicht das blosse Verzeichnis. `data/gold/` führt
    auch `EU` (Sammelablage ohne eindeutiges Land) und `PL` (angefangen, liegengeblieben —
    326.485 Sätze in Silber, kein Gold). Beide haben je drei Tabellen und wären als 'aktiv"
    eine Falschaussage: für sie ist ein fehlender Locale-Eintrag KEIN Defekt.
    """
    g = ROOT / "data" / "gold"
    if not g.exists():
        return []
    return sorted(d.name for d in g.iterdir()
                  if d.is_dir() and (d / "lead_export.parquet").exists())


# ── Die Wertetabellen ───────────────────────────────────────────────────────────────────
#
# Je Eintrag: wo sie steht, wie man die abgedeckten Länder herausliest, und — das Wichtigste —
# WAS PASSIERT, WENN EIN LAND FEHLT. Ohne diesen Satz ist ein Befund nur ein Hinweis; mit ihm
# ist er eine Entscheidung.
#
# `muster` fängt den Block, `codes` liest die Ländercodes daraus. Beides getrennt, damit ein
# nicht mehr greifendes Muster als FEHLER auffällt und nicht als 'alle Länder fehlen".
# ⚠ SCHLUESSEL STEHEN MAL MIT, MAL OHNE ANFUEHRUNGSZEICHEN. Python schreibt {"DE": 3},
# JavaScript {DE:'Deutschland'}, und `locales.LOCALES` fuehrt sogar blanke Bezeichner
# (DE, FR, CH, AT, LU). Ein Muster, das Anfuehrungszeichen verlangt, findet dort NICHTS —
# und meldete beim ersten Lauf vier Tabellen als komplett leer. Deshalb: alle
# Zweibuchstaben-Woerter nehmen und gegen die Laender-Registry sieben. Das filtert
# zuverlaessiger als jede Klammer-Akrobatik.
_ZWEI = re.compile(r"\b([A-Z]{2})\b")

sys.path.insert(0, str(ROOT))
from govisor import countries as _c            # noqa: E402
_ECHTE = {x.alpha2 for x in _c.all_countries()}


def _codes(block: str) -> set[str]:
    return {x for x in _ZWEI.findall(block) if x in _ECHTE}


class Tabelle:
    def __init__(self, name: str, datei: str, muster: str, folge: str, *, flags=0):
        self.name, self.datei, self.folge = name, datei, folge
        self.muster = re.compile(muster, re.S | flags)

    def laender(self) -> tuple[set[str] | None, str]:
        p = ROOT / self.datei
        if not p.exists():
            return None, f"Datei fehlt: {self.datei}"
        m = self.muster.search(p.read_text(encoding="utf-8"))
        if not m:
            # ⚠ NICHT als 'alle Länder fehlen" melden. Ein Muster, das nicht mehr greift,
            # ist ein Defekt DIESER Prüfung — und würde sonst 4 Fehlalarme werfen, in denen
            # der echte Befund untergeht. Genau die Falle A10: Statusmeldung als Befund.
            return None, "Muster greift nicht mehr — Prüfung anpassen, nicht die Tabelle"
        gefunden = _codes(m.group(1))
        if not gefunden:
            # ⚠ DASSELBE WIE „Muster greift nicht": das Muster passt, liefert aber keinen
            # einzigen Code. Ohne diesen Zweig meldet die Pruefung „alle Laender fehlen" —
            # und ein Befund, der ALLES anzeigt, zeigt nichts. Beim ersten Lauf am
            # 2026-09-03 traf es vier Tabellen, weil ihre Schluessel ohne Anfuehrungszeichen
            # stehen. Vier Fehlalarme, in denen ein echter Befund untergegangen waere.
            return None, "Muster passt, findet aber keinen Laendercode — Pruefung anpassen"
        return gefunden, ""


TABELLEN: list[Tabelle] = [
    Tabelle("gold._REGION_STELLEN", "govisor/gold.py",
            r"_REGION_STELLEN\s*=\s*\{([^}]*)\}",
            "ohne Eintrag bekommt das Land keine Regionsableitung"),
    Tabelle("gold._PLZ_STELLEN", "govisor/gold.py",
            r"_PLZ_STELLEN\s*=\s*\{([^}]*)\}",
            "der Lead faellt vom PLZ- auf den ORTS-Zentroid zurueck — die Abdeckung bleibt "
            "voll, die Genauigkeit ist weg (LU: 0 statt 127 Leads)"),
    Tabelle("region_ableiten.REGION_STELLEN", "scripts/region_ableiten.py",
            r"REGION_STELLEN\s*=\s*\{([^}]*)\}",
            "muss zu gold._REGION_STELLEN passen, sonst driften beide auseinander"),
    Tabelle("export_suppliers._STELLEN", "scripts/export_suppliers.py",
            r"_STELLEN\s*=\s*\{([^}]*)\}",
            "`clean_nuts` verwirft JEDE Region des Landes — Firmen ohne Einsatzgebiet"),
    Tabelle("locales.LOCALES", "govisor/locales.py",
            r"LOCALES\s*=\s*\{loc\.code: loc for loc in \(([^)]*)\)\}",
            "alles laeuft mit dem DE-Default: Rechtsformen, Behoerden, Klassifikation",
            flags=0),
    Tabelle("fetch_ted_live.LAND3", "scripts/fetch_ted_live.py",
            r"LAND3\s*=\s*\{([^}]*)\}",
            "der Live-Abruf kennt den TED-Alpha-3-Code nicht"),
    Tabelle("fetch_ted_live --country", "scripts/fetch_ted_live.py",
            r'add_argument\("--country".*?choices=\(([^)]*)\)',
            "argparse weist `--country <LAND>` ab, obwohl der Code laengst dafuer gebaut ist"),
    Tabelle("process_upload._ERLAUBT", "scripts/process_upload.py",
            r"_ERLAUBT\s*=\s*\(([^)]*)\)",
            "der Upload faellt auf DE zurueck und wird im falschen Land abgelegt"),
    Tabelle("lead-docs route LAENDER", "web/app/api/lead-docs/route.ts",
            r"LAENDER = new Set\(\[([^\]]*)\]",
            'der Upload-Endpunkt weist das Land mit 400 ab'),
    Tabelle("strategie route LAENDER", "web/app/api/strategie/route.ts",
            r"LAENDER = new Set\(\[([^\]]*)\]",
            "`?land=<LAND>` wird abgewiesen, obwohl der Export das Land baut"),
    Tabelle("explorerCore.LAND_LABEL", "web/lib/explorerCore.js",
            r"const LAND_LABEL = \{([^}]*)\}",
            "im Detail steht der rohe Laendercode statt des Namens"),
    Tabelle("explorerCore.LAND_AUS_NUTS", "web/lib/explorerCore.js",
            r"const LAND_AUS_NUTS = \{([^}]*)\}",
            "der Nutzer bekommt DE-Aggregate statt seiner eigenen"),
    Tabelle("Landing.LAND_NAME", "web/components/Landing.tsx",
            r"const LAND_NAME: Record<string, string> = \{([^}]*)\}",
            'auf der Landing-Zaehlung steht der rohe Code statt des Namens'),
    Tabelle("Marktpuls.LAND_LABEL", "web/components/Marktpuls.tsx",
            r"const LAND_LABEL: Record<string, string> = \{([^}]*)\}",
            'das Land faellt in den Sammeltopf der uebrigen EU-Laender'),
    Tabelle("export_strategie.LAENDER", "scripts/export_strategie.py",
            r"^LAENDER\s*=\s*\[([^\]]*)\]",
            "die Strategie-Ansicht wird fuer das Land nicht gebaut", flags=re.M),
    Tabelle("export_web_leads.LAENDER", "scripts/export_web_leads.py",
            r"^LAENDER\s*=\s*\(([^)]*)\)",
            "Dubletten-, Frist- und Unterlagen-Kennzahlen zaehlen das Land nicht mit",
            flags=re.M),
    Tabelle("pruefe_verdrahtung.LAENDER", "scripts/pruefe_verdrahtung.py",
            r"^LAENDER\s*=\s*\(([^)]*)\)",
            "die Verdrahtungssonde prueft das Land ueberhaupt nicht", flags=re.M),
]


# ── Bewusst NICHT geprüft ───────────────────────────────────────────────────────────────
#
# Drei Listen enthalten absichtlich nicht alle aktiven Länder. Sie hier nur wegzulassen wäre
# eine stille Ausnahme — deshalb stehen sie MIT Begründung da, und `tests/` hält sie ehrlich.
BEWUSST_UNVOLLSTAENDIG: dict[str, str] = {
    "web/lib/staaten.ts:STAATEN":
        'das oeffentliche VERSPRECHEN (jede Vergabe in ...). Es hinkt absichtlich hinterher: '
        "LU liefert noch keine Leads. Die Datei sagt selbst, ein viertes Land sei 'eine Zeile, "
        "und das Versprechen wandert von allein mit - genau deshalb darf sie NICHT automatisch "
        "mitwandern, sonst veroeffentlicht ein Ingest eine Zusage.",
    "scripts/analyze_docs.py:LAND_PRIO":
        "eine REIHENFOLGE, keine Zugehoerigkeit. LU fehlt bewusst und faellt damit hinten an "
        "(Sven 2026-09-03: LU ist erst einmal nur zum Material sammeln).",
    "scripts/daily_leads.sh:_IXLAENDER":
        "welche Laender DOKUMENTE haben, nicht welche aktiv sind. AT und CH stehen bei den "
        "Portalen auf 0 % Abdeckung — ein Indexlauf dort waere Leerlauf.",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--alle", action="store_true", help="auch die vollstaendigen zeigen")
    a = ap.parse_args()

    aktiv = set(aktive_laender())
    if not aktiv:
        print("  keine aktiven Laender gefunden (data/gold fehlt?) — nichts zu pruefen.")
        return 0
    print(f"── Aktive Laender (aus data/gold/*/lead_export.parquet): {', '.join(sorted(aktiv))} ──\n")

    befunde: list[str] = []
    kaputt: list[str] = []
    for t in TABELLEN:
        hat, fehler = t.laender()
        if hat is None:
            kaputt.append(f"    ⚠ {t.name}: {fehler}")
            continue
        fehlt = aktiv - hat
        if fehlt:
            befunde.append(f"    ✖ {t.name}  fehlt: {', '.join(sorted(fehlt))}\n"
                           f"        Folge: {t.folge}\n"
                           f"        Datei: {t.datei}")
        elif a.alle:
            print(f"    ✓ {t.name}")

    if kaputt:
        print("── Pruefung selbst defekt ──")
        print("\n".join(kaputt))
        print()
    if befunde:
        print("── Luecken ──")
        print("\n\n".join(befunde))
        print(f"\n  {len(befunde)} Wertetabelle(n) unvollstaendig.")
    else:
        print("  ✓ alle Wertetabellen tragen jedes aktive Land.")

    if a.alle:
        print("\n── Bewusst unvollstaendig ──")
        for k, v in BEWUSST_UNVOLLSTAENDIG.items():
            print(f"    · {k}\n      {v}")
    return 1 if (befunde or kaputt) else 0


if __name__ == "__main__":
    raise SystemExit(main())

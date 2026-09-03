#!/usr/bin/env python3
"""Wie viele Unterlagen-Links nennen ueberhaupt ein Verfahren? — EINE Regel fuer alle Laender.

⚠ WARUM ES DIESES SKRIPT GIBT. Die Tiefenpruefung entstand im griechischen Kapitel (dort
nannten 43 % der Links nur eine Startseite) und wurde danach je Land NEU HINGESCHRIEBEN.
Zwischen Bulgarien und Kroatien aenderte sich dabei die Regel: die bulgarische Fassung
verlangte sechs Hexzeichen (fuer GUIDs), und daran scheiterte Kroatiens `/tender-eo/84749`
— eine fuenfstellige Nummer in zwei Pfadstuecken.

Ergebnis: Kroatien wurde als „0 % tief" gemessen und ist in Wahrheit 100 %. Die Antwort
kippte vollstaendig, ohne dass an den Daten etwas anders war.

**Eine von Hand nachgezogene Heuristik ist keine Messung.** Deshalb steht sie jetzt hier,
einmal, und jedes Land bekommt dieselbe.

Aufruf:  python3 scripts/miss_linktiefe.py [--monate 3]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import tarfile
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import bulk, flatten                                    # noqa: E402

AUSSCHREIBUNG = re.compile(rb'<(ContractNotice)[ >]')
LAND = re.compile(rb'listName="country"[^>]*>([A-Z]{3})<')
A3 = {"DEU": "DE", "FRA": "FR", "POL": "PL", "ESP": "ES", "ITA": "IT", "CZE": "CZ",
      "BEL": "BE", "NLD": "NL", "SWE": "SE", "LTU": "LT", "BGR": "BG", "NOR": "NO",
      "PRT": "PT", "HRV": "HR", "FIN": "FI", "SVN": "SI", "CHE": "CH", "LVA": "LV",
      "IRL": "IE", "GRC": "GR", "SVK": "SK", "HUN": "HU", "DNK": "DK", "EST": "EE",
      "AUT": "AT", "ROU": "RO", "LUX": "LU", "CYP": "CY", "MLT": "MT", "ISL": "IS",
      "LIE": "LI"}

# DIE Regel. Ein Link ist "tief", wenn irgendwo eine Verfahrenskennung steht.
#
# ⚠ SIE MUSSTE DREIMAL REPARIERT WERDEN, und jedes Mal zeigte ein Land, was fehlte:
#   · HR  /tender-eo/84749          — vier Ziffern muessen reichen (nicht erst sechs Hex)
#   · EE  #/procurement/9490004/…   — die Kennung steht in der RAUTE, die urlsplit weder
#                                     in Pfad noch Abfrage legt. Ohne fragment: 99,8 %
#                                     „ohne Verfahren" statt fast null.
#   · CH  ?context=eyJwYWdlIjoi…    — Base64 ohne Ziffernfolge; ein langes undurchsichtiges
#                                     Zeichenband IST eine Kennung.
# Gegenprobe, die tief bleiben muss: CZ nen.nipez.cz/profil/MVCR nennt den KAEUFER, nicht
# das Verfahren — das ist zu Recht flach.
KENNUNG = re.compile(r'\d{4,}|[0-9a-f]{8,}', re.I)
# ⚠ Ein langes undurchsichtiges Zeichenband gilt NUR in Abfrage und Raute als Kennung,
# nie im Pfad: `sicpportal/mtoAnunciosLicitacion.aspx` (ES) ist ein LESBARES WORT von
# 21 Zeichen und keine Kennung. Im Pfad stehen Seitennamen, in der Abfrage stehen Werte.
UNDURCHSICHTIG = re.compile(r'[A-Za-z0-9+/%_-]{16,}')


def ist_tief(w: str) -> bool:
    u = urlsplit(w)
    # ⚠ fragment MUSS mit — SPA-Portale routen ueber die Raute.
    rest = u.path.strip("/") + "?" + (u.query or "") + "#" + (u.fragment or "")
    if KENNUNG.search(rest):
        return True
    if UNDURCHSICHTIG.search((u.query or "") + "#" + (u.fragment or "")):
        return True
    tiefe = len([x for x in (u.path.strip("/") + "/" + (u.fragment or "")).split("/") if x])
    return tiefe >= 3


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monate", type=int, default=3)
    p.add_argument("--ziel", default="data/sondierung/linktiefe.json")
    a = p.parse_args()

    pakete = sorted((ROOT / "data" / "cache").glob("ted_*.tar.gz"))[-a.monate:]
    if not pakete:
        print("  keine Pakete im Cache."); return 1

    tief: dict = collections.Counter()
    flach: dict = collections.Counter()
    for paket in pakete:
        with tarfile.open(paket) as t:
            for m in t:
                if not m.name.endswith(".tar.gz"):
                    continue
                for _x, roh in bulk._walk(m.name, t.extractfile(m).read(), None):
                    if not AUSSCHREIBUNG.search(roh[:4000]):
                        continue
                    c = LAND.search(roh[:120000])
                    land = A3.get(c.group(1).decode()) if c else None
                    if not land:
                        continue
                    try:
                        paare = flatten.leaves(roh)
                    except Exception:                                # noqa: BLE001
                        continue
                    gesehen = set()
                    for pfad, wert in paare:
                        if "CallForTendersDocumentReference" not in pfad:
                            continue
                        if not wert.startswith("http"):
                            continue
                        t_ = ist_tief(wert)
                        if (land, t_) in gesehen:
                            continue
                        gesehen.add((land, t_))
                        (tief if t_ else flach)[land] += 1
        print(f"  {paket.stem[4:]} gelesen", flush=True)

    laender = sorted(set(tief) | set(flach), key=lambda l: -(tief[l] + flach[l]))
    print(f"\n  {'Land':<6} {'tief':>7} {'Startseite':>11} {'Anteil ohne Verfahren':>22}")
    aus = {}
    for l in laender:
        a_, b_ = tief[l], flach[l]
        anteil = b_ / (a_ + b_) * 100
        aus[l] = {"tief": a_, "flach": b_, "ohne_verfahren_prozent": round(anteil, 1)}
        marke = "  ⚠" if anteil >= 20 else ""
        print(f"  {l:<6} {a_:>7,} {b_:>11,} {anteil:>20.1f} %{marke}")
    ziel = ROOT / a.ziel
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps({"monate": [x.stem[4:] for x in pakete], "laender": aus},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  → {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

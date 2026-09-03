#!/usr/bin/env python3
"""Tiefe Portal-Sondierung: zwölf Monate, alle Länder, ALLE URL-Felder.

⚠ WARUM ES DIESES ZWEITE SKRIPT GIBT. `sondiere_portale.py` liest EINEN Monat und EIN
Feld (`CallForTendersDocumentReference`). Beides ist zu eng, und beides ist beim
Nachprüfen aufgefallen:

  · EIN MONAT übersieht jedes Portal, das seltener als monatlich auftaucht. Bei 538 Domains
    in Italien ist der Schwanz genau dort, wo die Einzelmessung blind wird.
  · EIN FELD übersieht Portale, die anders verlinkt sind. `ContractingParty.BuyerProfileURI`
    trägt allein im Juni 2026 rund 1.454 Adressen — ausgeschlossen mit der Begründung
    „Beschafferprofil, nicht das Verfahren". Das stimmt für die Zuordnung, aber NICHT für
    die Frage, welche Portale es gibt: wo TED keinen Unterlagen-Link führt, ist das
    Käuferprofil oft der einzige Zeiger.

Dieses Skript zählt deshalb JEDES Feld getrennt, statt vorab auszuwählen. Die Auswahl
kommt danach, an den Zahlen.

Ausgabe: data/sondierung/_tief/<land>.json — Domains je Feld, über alle gelesenen Monate.

Aufruf:  python3 scripts/sondiere_tief.py [--monate 12] [--laender DE,FR,...]
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

# ⚠ Der Namensraum-Praefix MUSS optional sein. Ohne ihn fehlten ContractNotices aus
# RO (1.252), AT (816), ES (523), SE (513) und DE (260) in EINEM Monat.
AUSSCHREIBUNG = re.compile(rb'<(?:[A-Za-z0-9]+:)?(ContractNotice)[ >]')
# ⚠ BEIDE Codelisten-Namen. Rumaenien schreibt AUSSCHLIESSLICH listName="eforms-country";
# mit dem alten Muster war es in der ganzen Sondierung unsichtbar (64 statt 3.866 im Juni).
# govisor/schema.py:1799 kennt beide seit laengerem — die Skripte hier hatten es nicht.
LAND = re.compile(rb'listName="(?:eforms-)?country"[^>]*>([A-Z]{3})<')

# ISO-3 → ISO-2, damit die Ausgabe die üblichen Kürzel trägt.
A3 = {
    "DEU": "DE", "FRA": "FR", "POL": "PL", "ESP": "ES", "ITA": "IT", "CZE": "CZ",
    "BEL": "BE", "NLD": "NL", "SWE": "SE", "LTU": "LT", "BGR": "BG", "NOR": "NO",
    "PRT": "PT", "HRV": "HR", "FIN": "FI", "SVN": "SI", "CHE": "CH", "LVA": "LV",
    "IRL": "IE", "GRC": "GR", "SVK": "SK", "HUN": "HU", "DNK": "DK", "EST": "EE",
    "AUT": "AT", "ROU": "RO", "LUX": "LU", "CYP": "CY", "MLT": "MT", "ISL": "IS",
    "LIE": "LI",
}

# Feldgruppen — bewusst NICHT vorab gefiltert, sondern benannt und getrennt gezählt.
# Die Entscheidung, welche zählen, gehört hinter die Messung, nicht davor.
def gruppe(pfad: str) -> str:
    if "CallForTendersDocumentReference" in pfad:
        return "unterlagen_link"        # der Deeplink zu den Unterlagen
    if "AccessToolsURI" in pfad:
        return "kommunikationskanal"    # das Portal, über das das Verfahren läuft
    if "TenderRecipientParty" in pfad:
        return "abgabeort"              # wohin das Angebot geht
    if "BuyerProfileURI" in pfad:
        return "kaeuferprofil"          # ⚠ die Gruppe, die zuerst fehlte
    if "LegislationDocumentReference" in pfad:
        return "gesetzestext"           # kein Portal
    if "Organizations.Organization" in pfad:
        return "organisation"           # Kontaktdaten — hier steckt die Nachprüfungsstelle
    return "sonstiges"


def lies_monat(paket: pathlib.Path, treffer: dict) -> int:
    n = 0
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
                n += 1
                try:
                    paare = flatten.leaves(roh)
                except Exception:                                    # noqa: BLE001
                    continue
                gesehen = set()
                for pfad, wert in paare:
                    if not wert.startswith("http"):
                        continue
                    host = urlsplit(wert).netloc.lower().removeprefix("www.")
                    if not host or "." not in host:
                        continue
                    schluessel = (land, gruppe(pfad), host)
                    if schluessel in gesehen:      # je Bekanntmachung nur einmal zählen
                        continue
                    gesehen.add(schluessel)
                    treffer[schluessel] += 1
    return n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monate", type=int, default=12)
    p.add_argument("--ziel", default="data/sondierung/_tief")
    a = p.parse_args()

    pakete = sorted((ROOT / "data" / "cache").glob("ted_*.tar.gz"))[-a.monate:]
    if not pakete:
        print("  keine Pakete im Cache."); return 1

    treffer: dict = collections.Counter()
    gesamt = 0
    for i, paket in enumerate(pakete, 1):
        n = lies_monat(paket, treffer)
        gesamt += n
        print(f"  [{i:>2}/{len(pakete)}] {paket.stem[4:]}  {n:>7,} Ausschreibungen", flush=True)

    ziel = ROOT / a.ziel
    ziel.mkdir(parents=True, exist_ok=True)
    je_land: dict = collections.defaultdict(lambda: collections.defaultdict(dict))
    for (land, grp, host), c in treffer.items():
        je_land[land][grp][host] = c
    for land, gruppen in je_land.items():
        (ziel / f"{land}.json").write_text(json.dumps({
            "land": land,
            "monate": [x.stem[4:] for x in pakete],
            "gruppen": {g: dict(sorted(d.items(), key=lambda kv: -kv[1]))
                        for g, d in gruppen.items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n  {gesamt:,} Ausschreibungen über {len(pakete)} Monate, "
          f"{len(je_land)} Länder nach {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

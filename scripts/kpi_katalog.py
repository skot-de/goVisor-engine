#!/usr/bin/env python3
"""Der Kennzahlen-Katalog — ERZEUGT, nicht getippt.

    python3 scripts/kpi_katalog.py            # nach docs/kpi-katalog.md
    python3 scripts/kpi_katalog.py --zaehlen  # nur die Zahl, fuer Skripte

DIE FRAGE. „Wie viele Kennzahlen habt ihr?" war bis zum 2026-09-16 nicht beantwortbar: Es gab
vier Teillisten (`docs/cross-kpis.md`, `kpi-buyer-profile.md`, `kpi-region-und-kontext.md`,
`feature-inventory-vergabestelle.md`), keine Gesamtzahl und keinen gemeinsamen Begriff. In
einer Unterlage stand „125", und die Zahl liess sich nirgends herleiten.

⚠ GETIPPT WAERE SIE SOFORT VERALTET. Der Bestand waechst, Tabellen bekommen Spalten. Deshalb
dieselbe Bauweise wie bei der Verdrahtungskarte: aus dem Bestand erzeugt, jederzeit neu
rechenbar, mit dem Datum im Kopf.

DIE REGEL, und sie ist Auslegung, nicht Wahrheit:

    Eine Kennzahl ist ein abgeleiteter Wert, der eine Entscheidung stuetzt.
    KEINE Kennung, kein Name, kein Link, kein Herkunftskennzeichen, kein rohes Stammdatum.

`AUSSCHLUSS` macht sie pruefbar. Wer die Regel aendert, aendert die Zahl — dann gehoert die
neue Regel hierher und nicht in eine Fussnote der Unterlage.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Was KEINE Kennzahl ist. Absichtlich streng: im Zweifel draussen, damit die Zahl haelt.
AUSSCHLUSS = re.compile(
    r"(_id$|^id$|_ids$|name|titel|title|url|email|phone|^land$|country|"
    r"_source$|_quelle$|quelle$|beschreibung|description|text$|^cpv|"
    r"nuts|plz|ort|town|postal|_conf$|confidence|stand$|provider|model)", re.I)

# Produktflaechen: was der Nutzer sieht, nicht was im Lager liegt.
FLAECHEN: dict[str, str] = {
    "Lead (Auslauf-Radar)": "leads",
    "Lead-Detail": "lead_detail",
    "Marktchancen": "market_opportunity",
    "Anbieterprofil": "contractor_stats",
    "Vergabestelle": "buyer_stats",
    "Vorgangsakte": "vorgaenge",
    "Vergabekette": "vorgang_kette",
    "Dokumentenanalyse": "doc_analysis",
    "Anlaufvergleich": "anlauf_vergleich",
}
# Handgepflegte Listen, die Felder ausserhalb der Gold-Tabellen beschreiben.
DOKUMENTE = ("kpi-buyer-profile", "kpi-region-und-kontext")


def _spalten(tabelle: str, land: str = "DE") -> list[str]:
    import duckdb
    pfad = ROOT / "data" / "gold" / land / f"{tabelle}.parquet"
    if not pfad.exists():
        return []
    con = duckdb.connect()
    return [c[0] for c in con.execute(
        f"describe select * from read_parquet('{pfad.as_posix()}')").fetchall()]


def _aus_dokument(name: str) -> set[str]:
    pfad = ROOT / "docs" / f"{name}.md"
    if not pfad.exists():
        return set()
    raus = set()
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        treffer = re.match(r"\|\s*`([a-z0-9_]+)`", zeile)
        if treffer and not AUSSCHLUSS.search(treffer.group(1)):
            raus.add(treffer.group(1))
    return raus


def sammle() -> tuple[dict[str, set[str]], dict[str, set[str]], set[str]]:
    je_flaeche: dict[str, set[str]] = {}
    for label, tabelle in FLAECHEN.items():
        spalten = _spalten(tabelle)
        if spalten:
            je_flaeche[label] = {s for s in spalten if not AUSSCHLUSS.search(s)}
    je_dokument = {d: _aus_dokument(d) for d in DOKUMENTE}
    alle: set[str] = set()
    for menge in list(je_flaeche.values()) + list(je_dokument.values()):
        alle |= menge
    return je_flaeche, je_dokument, alle


def schreibe(je_flaeche, je_dokument, alle) -> Path:
    aus_flaechen: set[str] = set()
    for m in je_flaeche.values():
        aus_flaechen |= m
    aus_dok: set[str] = set()
    for m in je_dokument.values():
        aus_dok |= m
    z = [f"# Kennzahlen-Katalog\n",
         f"> ⚠ **ERZEUGT, NICHT GETIPPT.** `python3 scripts/kpi_katalog.py`. Wer hier von Hand",
         f"> schreibt, verliert es beim naechsten Lauf. Stand {date.today().isoformat()}.\n",
         "## Die Regel\n",
         "Eine Kennzahl ist ein **abgeleiteter Wert, der eine Entscheidung stuetzt**. Keine",
         "Kennung, kein Name, kein Link, kein Herkunftskennzeichen, kein rohes Stammdatum.",
         "Die Ausschlussliste steht als Regex im Skript und ist damit pruefbar.\n",
         "⚠ Das ist **Auslegung, nicht Wahrheit**. Eine andere Regel ergibt eine andere Zahl;",
         "dann gehoert die neue Regel ins Skript und nicht in eine Fussnote.\n",
         f"## Die Zahl\n",
         f"**{len(alle)} verschiedene Kennzahlen.** Davon {len(aus_flaechen)} in den",
         f"Produktflaechen und {len(aus_dok)} aus den handgepflegten Listen fuer Vergabestelle",
         f"und Region; {len(aus_flaechen & aus_dok)} kommen in beidem vor.\n",
         "## Je Produktflaeche\n",
         "| Flaeche | Kennzahlen | Tabelle |", "|---|---:|---|"]
    for label in FLAECHEN:
        if label in je_flaeche:
            z.append(f"| {label} | {len(je_flaeche[label])} | `{FLAECHEN[label]}.parquet` |")
        else:
            z.append(f"| {label} | — | `{FLAECHEN[label]}.parquet` (noch nicht gebaut) |")
    z += ["", "## Je handgepflegter Liste", "",
          "| Liste | Kennzahlen |", "|---|---:|"]
    for d, m in je_dokument.items():
        z.append(f"| [{d}.md]({d}.md) | {len(m)} |")
    z += ["", "## Alle Kennzahlen, alphabetisch", ""]
    for i in range(0, len(sorted(alle)), 4):
        z.append("- " + " · ".join(f"`{k}`" for k in sorted(alle)[i:i + 4]))
    ziel = ROOT / "docs" / "kpi-katalog.md"
    ziel.write_text("\n".join(z) + "\n", encoding="utf-8")
    return ziel


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zaehlen", action="store_true", help="nur die Gesamtzahl ausgeben")
    a = p.parse_args()
    je_flaeche, je_dokument, alle = sammle()
    if a.zaehlen:
        print(len(alle))
        return 0
    ziel = schreibe(je_flaeche, je_dokument, alle)
    print(f"  {len(alle)} Kennzahlen → {ziel.relative_to(ROOT)}")
    for label, menge in je_flaeche.items():
        print(f"    {label:<24} {len(menge):>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

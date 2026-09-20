#!/usr/bin/env python3
"""Wiederholt sich etwas an dem, was weggeklickt wird? (`user_lead_hidden`)

⚠ Sven am 2026-09-20: „idealerweise haben wir eine automatische analyse die nach mustern
schaut und bei vielen gleichen gründen dem nachgeht."

⛔ DIE FALLE IST DIE BASISRATE, UND SIE HAT DIESES PROJEKT SCHON MEHRFACH ERWISCHT.
Fuenf weggeklickte Vorgaenge derselben CPV-Klasse sind KEIN Muster, wenn diese Klasse
ohnehin 80 % der Liste stellt — dann ist es der Zufall der Mengenverhaeltnisse. Dieselbe
Sorte Fehler steckte in der Entity-Zusammenfuehrung (die Ausgangszahl war eine
Doppelzaehlung) und im Volumenband (CPV-Mediane sahen aus wie veroeffentlichte Werte).

Deshalb wird JEDER Befund gegen den Grundraum desselben Nutzers gerechnet:

    Auffaelligkeit = Anteil in der Ausblendmenge / Anteil im Grundraum

Gemeldet wird nur, was sowohl absolut (>= `--mindestens`) als auch relativ (>= `--lift`)
heraussticht. Ohne den zweiten Teil waere der Bericht eine Liste der haeufigsten
CPV-Klassen, und die kennt man auch ohne Ausblendungen.

⚠ ZWEI ADRESSATEN, UND SIE MUESSEN GETRENNT BLEIBEN:

  · **Produktfehler** — „Fehlerhafte Zuordnung" haeuft sich auf einer CPV-Klasse. Das ist
    ein Befund ueber UNS: unsere Kategorisierung trifft dort daneben. Daraus darf niemals
    ein Nutzer-Ausschluss werden; es muss die Zuordnung geprueft werden.
  · **Profilvorschlag** — „Entfernung" haeuft sich auf einer Region, „Zu umfangreich"
    oberhalb eines Wertbands. Das ist ein Befund ueber den NUTZER, und dafuer liegt
    `profileEngine.exclusions` bereit (regionen_aus, wert_max).

Die uebrigen drei Gruende (Kein Interesse, Zu kurzfristig, Keine Chance) liegen auf keiner
Achse, die das Profil kennt. Sie werden gezaehlt und gemeldet, aber ohne Vorschlag — ein
Vorschlag, den niemand umsetzen kann, ist schlimmer als keiner.

Aufruf:  python3 scripts/muster_ausgeblendet.py [--mindestens 4] [--lift 3.0] [--json]
Rueckgabe: 0 immer (kein Muster ist kein Fehler)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from collections import Counter, defaultdict

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

# Grund → (Merkmal, das gepruefte wird, Adressat, Konsequenz)
#
# ⚠ Je Grund genau EIN Merkmal. Wer alle Merkmale gegen alle Gruende prueft, bekommt bei
# vier Merkmalen und sechs Gruenden 24 Zahlen, von denen ein paar immer heraussstechen —
# das ist Rauschen mit Nachkommastellen, kein Befund.
_ACHSE = {
    "Fehlerhafte Zuordnung": ("cpv4",  "produkt", "Kategorisierung dieser CPV-Klasse pruefen"),
    "Entfernung":            ("nuts2", "profil",  "exclusions.regionen_aus vorschlagen"),
    "Zu umfangreich":        ("band",  "profil",  "exclusions.wert_max vorschlagen"),
    "Kein Interesse":        (None,    "offen",   None),
    "Zu kurzfristig":        (None,    "offen",   None),
    "Keine Chance":          (None,    "offen",   None),
}


def _dsn() -> str | None:
    a, b = WURZEL / ".secrets" / "supabase.txt", WURZEL / ".secrets" / "supabase_db.txt"
    if not (a.exists() and b.exists()):
        return None
    try:
        ref = a.read_text(encoding="utf-8").splitlines()[0].split("//")[1].split(".")[0]
        return (f"postgresql://postgres:{b.read_text(encoding='utf-8').strip()}"
                f"@db.{ref}.supabase.co:5432/postgres")
    except (IndexError, OSError):
        return None


def hole() -> list[dict] | None:
    dsn = _dsn()
    if not dsn:
        return None
    try:
        from govisor.psql import psql_oder_fehler
        r = subprocess.run(
            [psql_oder_fehler(), dsn, "-At", "-F", "\x1f", "-c",
             "select user_id::text, lead_id, coalesce(grund,'') from public.user_lead_hidden"],
            capture_output=True, text=True, timeout=90)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    raus = []
    for z in r.stdout.splitlines():
        t = z.split("\x1f")
        if len(t) >= 3 and t[2]:
            raus.append({"user": t[0], "lead_id": t[1], "grund": t[2]})
    return raus


def merkmale(lead_ids: set[str]) -> dict:
    """Je Lead die vier Merkmale, an denen ein Muster haengen kann."""
    if not lead_ids:
        return {}
    try:
        import duckdb
        import glob as _g
        dateien = sorted(_g.glob("data/gold/*/lead_export*.parquet"))
        if not dateien:
            return {}
        con = duckdb.connect()
        lst = ",".join("'" + i.replace("'", "") + "'" for i in lead_ids)
        return {r[0]: {"cpv4": r[1], "nuts2": r[2], "band": r[3], "buyer": r[4]}
                for r in con.execute(
                    f"SELECT lead_id, substr(cpv_main,1,4), substr(buyer_nuts,1,4),"
                    f" value_band, buyer_name FROM read_parquet({dateien!r}, union_by_name=true)"
                    f" WHERE lead_id IN ({lst})").fetchall()}
    except Exception:
        return {}


def grundraum(spalte: str) -> Counter:
    """Die Verteilung IM BESTAND — der Nenner, ohne den jede Haeufung nur Groesse misst."""
    try:
        import duckdb
        import glob as _g
        dateien = sorted(_g.glob("data/gold/*/lead_export*.parquet"))
        if not dateien:
            return Counter()
        sql = {"cpv4": "substr(cpv_main,1,4)", "nuts2": "substr(buyer_nuts,1,4)",
               "band": "value_band", "buyer": "buyer_name"}[spalte]
        con = duckdb.connect()
        return Counter({r[0]: r[1] for r in con.execute(
            f"SELECT {sql}, count(*) FROM read_parquet({dateien!r}, union_by_name=true)"
            f" WHERE phase='open' AND {sql} IS NOT NULL GROUP BY 1").fetchall()})
    except Exception:
        return Counter()


def suche(zeilen: list[dict], mindestens: int, lift: float) -> list[dict]:
    m = merkmale({z["lead_id"] for z in zeilen})
    basis_cache: dict[str, Counter] = {}
    befunde: list[dict] = []
    # je (Nutzer, Grund) getrennt: ein Muster ist eine Gewohnheit EINES Nutzers, nicht die
    # Summe verschiedener Leute mit verschiedenen Profilen.
    gruppen: dict[tuple, list[str]] = defaultdict(list)
    for z in zeilen:
        gruppen[(z["user"], z["grund"])].append(z["lead_id"])
    for (nutzer, grund), ids in gruppen.items():
        achse, adressat, konsequenz = _ACHSE.get(grund, (None, "offen", None))
        if len(ids) < mindestens:
            continue
        if achse is None:
            befunde.append({"grund": grund, "n": len(ids), "adressat": adressat,
                            "merkmal": None, "wert": None, "lift": None,
                            "konsequenz": None, "nutzer": nutzer[:8]})
            continue
        werte = Counter(m[i][achse] for i in ids if i in m and m[i].get(achse))
        if not werte:
            continue
        if achse not in basis_cache:
            basis_cache[achse] = grundraum(achse)
        basis = basis_cache[achse]
        gesamt = sum(basis.values()) or 1
        for wert, n in werte.most_common(3):
            if n < mindestens:
                continue
            anteil_aus = n / len(ids)
            anteil_basis = basis.get(wert, 0) / gesamt
            if anteil_basis <= 0:
                continue
            q = anteil_aus / anteil_basis
            if q >= lift:
                befunde.append({"grund": grund, "n": n, "von": len(ids), "adressat": adressat,
                                "merkmal": achse, "wert": wert, "lift": round(q, 1),
                                "konsequenz": konsequenz, "nutzer": nutzer[:8]})
    return sorted(befunde, key=lambda b: (-(b["lift"] or 0), -b["n"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mindestens", type=int, default=4)
    ap.add_argument("--lift", type=float, default=3.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    zeilen = hole()
    if zeilen is None:
        print("  (kein Zugang zur Datenbank — keine Auskunft)")
        return 0
    befunde = suche(zeilen, a.mindestens, a.lift)
    if a.json:
        print(json.dumps(befunde, ensure_ascii=False, indent=2))
        return 0
    print(f"  {len(zeilen):,} Ausblendungen MIT Grund · Schwelle n>={a.mindestens}, "
          f"Auffaelligkeit >={a.lift}x\n")
    if not befunde:
        print("  Kein Muster. Das ist die Regel, nicht die Ausnahme — ein Bericht, der")
        print("  immer etwas findet, findet nichts.")
        return 0
    for b in befunde:
        kopf = {"produkt": "⛔ PRODUKTFEHLER", "profil": "→ Profilvorschlag",
                "offen": "·  ohne Achse"}[b["adressat"]]
        if b["merkmal"]:
            print(f"  {kopf}  {b['grund']}: {b['n']} von {b['von']} auf "
                  f"{b['merkmal']}={b['wert']} ({b['lift']}x haeufiger als im Bestand)")
            print(f"       → {b['konsequenz']}   [Nutzer {b['nutzer']}]")
        else:
            print(f"  {kopf}  {b['grund']}: {b['n']}x   [Nutzer {b['nutzer']}]")
            print(f"       → keine Profilachse; nur zaehlen, nicht vorschlagen")
    return 0


if __name__ == "__main__":
    sys.exit(main())

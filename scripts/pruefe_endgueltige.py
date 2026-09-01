#!/usr/bin/env python3
"""Sonde 5: hält ein endgültiges Urteil noch?

WARUM ES DIESE DATEI GIBT. Zwischen dem 2026-08-20 und dem 2026-08-31 sind elf
Dokument-Abrufer von Hand nachgeprüft worden — netserver, subreport, evergabe-online,
healyhudson, staatsanzeiger, aumass, evergabe, cosinex, rib und die Landesportale. **Neun
der geprüften Vermerke haben nicht gehalten**, und jedes Mal war es derselbe Satzbau: ein
Status behauptet Endgültigkeit, die er aus dem Verhalten des Portals nur geraten hat.

  netserver   „kein Unterlagen-Abschnitt"   → der Abschnitt war eingeklappt
  subreport   „kein Grund genannt"          → der Aufklapper kam vor der Begründung
  rib         „leitet auf /unavailable"     → eine Umleitung ist ein Zustand, kein Merkmal

Elfmal dieselbe Klasse von Hand zu suchen ist der Kreis, in dem wir uns gedreht haben. Ein
endgültiges Urteil ist eine **prüfbare Behauptung** — also gehört es geprüft wie jede andere
Zahl in diesem Projekt, regelmäßig und ohne dass jemand daran denken muss.

WAS SIE TUT. Für jede Gruppe (Portal × Status), deren Status in DAUERHAFT oder
KEIN_FEHLSCHLAG liegt und damit **nie wieder angefasst wird**, zieht sie eine Stichprobe und
lässt den echten Abrufer erneut laufen. Kommen zu viele Sätze plötzlich durch, hält das
Urteil nicht.

⚠ SIE SCHREIBT NICHTS. Weder ins Manifest noch nach `data/`; die Downloads landen in einem
Temp-Verzeichnis und werden verworfen. Damit ist sie neben einem laufenden Abrufer sicher —
anders als alles andere, was `data/docs` anfasst. Das ist der Grund, warum sie die Sperre
aus `laeuft_was.sh` nicht braucht.

⚠ SIE MISST DEN ECHTEN WEG. Nicht eine nachgebaute URL, sondern `documents_url` aus dem
Bestand durch den Connector, den auch der Nachtlauf wählt. Am 2026-08-30 hat eine Sonde mit
selbstgebautem Pfad („/VMPSatellite/" statt „/Satellite/") gemeldet, 82 % der cosinex-Fälle
seien weg — sie hatte nur die falsche Adresse geprüft.

    python3 scripts/pruefe_endgueltige.py [--stichprobe N] [--status S] [--offen]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ab wie vielen zurückgekehrten Sätzen ein Urteil als gefallen gilt. Ein einzelner Treffer
# ist Rauschen (ein Portal kann einen Vorgang wieder veröffentlichen); ein Drittel ist keins.
# Gemessen zur Eichung: rib `abgelaufen` 72 % (gefallen), rib `nur_bekanntmachung` 17 %
# (hält), `weg` 3 % (hält).
SCHWELLE = 0.30
MIN_TREFFER = 3

# Diese Stati sind kein Urteil über den Vorgang, sondern der Erfolgsfall selbst.
ERFOLG = {"exists", "downloaded"}


def gruppen(con, land: str):
    from govisor import docfetch_queue as q
    M = f"read_parquet('data/docs/{land}/_manifest.parquet')"
    L = f"read_parquet('data/gold/{land}/lead_export.parquet')"
    zeilen = con.execute(f"""
        select m.portal, m.status, m.notice_id, l.documents_url
        from {M} m join {L} l on l.lead_id = m.notice_id
        where l.documents_url is not null""").fetchall()
    raus = defaultdict(list)
    for portal, status, nid, url in zeilen:
        if status in ERFOLG:
            continue
        if status in q.DAUERHAFT or status in q.KEIN_FEHLSCHLAG:
            raus[(portal, status)].append((nid, url))
    return raus


def pruefe(paare, n: int) -> tuple[int, int]:
    """Stichprobe erneut abrufen. Rückgabe: (geprüft, wieder erfolgreich)."""
    from govisor.docfetch import _waehle_connector
    # Ohne Zufall, damit zwei Läufe vergleichbar sind: gleichmäßig über die Gruppe verteilt.
    schritt = max(1, len(paare) // n)
    probe = paare[::schritt][:n]
    zurueck = 0
    with tempfile.TemporaryDirectory() as d:
        for nid, url in probe:
            try:
                r = _waehle_connector(url)(url, nid, Path(d))
                if r.status in ERFOLG:
                    zurueck += 1
            except Exception:
                pass  # Ein Absturz ist kein zurückgekehrter Satz — und nicht die Frage hier.
    return len(probe), zurueck


def main() -> int:
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stichprobe", type=int, default=12)
    ap.add_argument("--status", help="nur diesen Status prüfen")
    ap.add_argument("--land", default="DE")
    ap.add_argument("--offen", action="store_true", help="nur die gefallenen Urteile zeigen")
    a = ap.parse_args()

    con = duckdb.connect()
    g = gruppen(con, a.land)
    if a.status:
        g = {k: v for k, v in g.items() if k[1] == a.status}
    if not g:
        print("  nichts endgültig abgelegt — nichts zu prüfen")
        return 0

    print(f"── Sonde 5: endgültige Urteile ({a.land}) ──")
    gefallen = []
    for (portal, status), paare in sorted(g.items(), key=lambda x: -len(x[1])):
        n, zurueck = pruefe(paare, a.stichprobe)
        if not n:
            continue
        quote = zurueck / n
        faellt = quote >= SCHWELLE and zurueck >= MIN_TREFFER
        if faellt:
            gefallen.append((portal, status, len(paare), zurueck, n))
        elif a.offen:
            continue
        zeichen = "⚠" if faellt else "✓"
        print(f"  {zeichen} {portal:<34} {status:<20} {len(paare):>5} abgelegt · "
              f"{zurueck}/{n} kehren zurück")

    if gefallen:
        print("\n⚠ Diese Urteile halten nicht — die Sätze warten auf nichts, sie sind holbar:")
        for portal, status, ges, zurueck, n in gefallen:
            print(f"   {portal} · {status}: {zurueck} von {n} kamen durch, "
                  f"{ges} Sätze liegen so ab")
        print("\n   Der Status gehört aus DAUERHAFT/KEIN_FEHLSCHLAG heraus (oder seine")
        print("   Herleitung repariert), danach die betroffenen Sätze freigeben.")
        return 1
    print("\n✓ jedes endgültige Urteil hält")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

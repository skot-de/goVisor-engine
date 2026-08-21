#!/usr/bin/env python3
"""Rückstau abarbeiten — EINEN Dokument-Abrufer bis zum Ende durchziehen.

**Warum es das gibt.** Der Tageslauf holt je Abrufer 60 Vorgänge pro Nacht. Gemessen am
2026-08-17 liegen aber **7.649 Vorgänge** im Rückstau, bei einem Zulauf von rund 796 neuen
Bekanntmachungen am Tag. Die Nacht arbeitet damit nicht das Tagesdelta ab, sondern greift
sich eine Scheibe aus einem Berg — und welche 60 das sind, entscheidet die Sortierung.

Genau daher kommt die Unberechenbarkeit: ein Vorgang ist gemessen alles zwischen 0 und
636 MB (Median 8,1), 60 Stück sind je nach Zusammensetzung 0,6 bis 3,3 GB. Der Tageslauf
schwankte deshalb zwischen 55 und 719 Minuten, obwohl Quelle und Verfahren gleich blieben.

Sven am 2026-08-17: „dann müssen wir läufe manuell anstoßen und am besten connector für
connector isoliert, bis das backlog abgearbeitet ist und dann haben wir bei den tagesläufen
nur noch das delta von gestern zu heute."

**Was dieses Werkzeug NICHT tut: selbst herunterladen.** Es ruft in Runden den vorhandenen
Abrufer auf. Der kennt sein Portal, seine Höflichkeitspausen, seine Deckel und seine
Warteschlange — das hier noch einmal zu bauen hiesse, dreizehn Sonderfälle zu verdoppeln
und beim nächsten Portalwechsel zwei Stellen zu pflegen.

**Wiederaufnahme ist geschenkt.** Die Abrufer sind idempotent: bereits geholte Vorgänge
stehen als ``exists`` im Manifest und werden übersprungen. Ein Abbruch kostet also nur die
angefangene Runde. Aus demselben Grund braucht es keinen eigenen Fortschrittsspeicher —
der Reststand steht in den Daten, nicht in einer Datei daneben.

Aufruf::

    scripts/rueckstau.py --zeigen
    scripts/rueckstau.py --connector netserver --stunden 4
    scripts/rueckstau.py --connector evergabe --stunden 2 --limit 40
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import sources as S  # noqa: E402

LOCK = ROOT / "data" / ".daily_leads.lock"

# Die Abrufer melden ihren Reststand selbst, in einer über alle dreizehn einheitlichen
# Zeile: „<Portal>: N Vergaben zu holen (von M offenen Leads)". Das ist der Stand NACH
# ihrem eigenen Warteschlangen-Filter, also genau die Zahl, die zählt. Sie hier neu
# auszurechnen hiesse, ihre Filterlogik ein zweites Mal zu schreiben.
_REST = re.compile(r"(\d[\d.,]*)\s+Vergaben zu holen")


def _zahl(s: str) -> int:
    return int(s.replace(".", "").replace(",", ""))


# Zwei Registry-Eintraege sind KEINE eigenstaendigen Programme, und das steht der Registry
# nicht an: `govisor.docfetch` (cosinex) laeuft ueber die CLI, und `govisor.docfetch_rib`
# ist ueberhaupt kein Abrufer, sondern ein Einschub von `docfetch` — `docfetch.py:122`
# reicht RIB-URLs dorthin weiter. Wer das Modul startet, bekommt Stille und Exit 0.
#
# Genau darauf ist dieses Werkzeug am 2026-08-17 hereingefallen: es hat der Registry
# geglaubt, `python -m govisor.docfetch_rib` gestartet und nach einer Runde ohne
# Reststand aufgegeben. Deshalb steht die Ausnahme jetzt HIER, sichtbar, statt als
# stille Fehlannahme.
UEBER_CLI = {
    "govisor.docfetch": ["-m", "govisor.cli", "fetch-docs", "--country", "DE"],
}
NICHT_EINZELN = {
    "govisor.docfetch_rib": "wird von `fetch-docs` mitbedient (docfetch.py:122)",
}


def abrufer() -> dict[str, str]:
    """Kurzname → Python-Modul, aus der Registry statt aus einer zweiten Liste."""
    out = {}
    for q in S.DOC_REGISTRY:
        if not q.modul or q.modul in NICHT_EINZELN:
            continue
        out[q.modul.rsplit(".", 1)[-1].replace("docfetch_", "").replace("docfetch", "cosinex")] = q.modul
    return out


# ⚠ ERFOLG HEISST NICHT ÜBERALL `downloaded`. `subreport` und `vergabeportal_at` liefern
# konstruktionsbedingt nur DATEILISTEN und schreiben `nur_liste` — gemessen 467 von 560 in
# sieben Tagen. Wer nur `downloaded` zaehlt, haelt sie fuer kaputt (0 %) statt fuer
# erfolgreich (83 %) und sortiert sie aus, obwohl ihre Liste die Frage „gibt es ein
# Leistungsverzeichnis" beantwortet.
_ERFOLG = ("downloaded", "nur_liste")

# ⚠ `exists` IST KEIN VERSUCH. cosinex schreibt fuer jede Vergabe, deren ZIP schon auf der
# Platte liegt, einen Satz mit diesem Status — die anderen Abrufer sortieren solche Faelle
# vorher aus und schreiben gar nichts. Zaehlt man `exists` in den Nenner, sieht cosinex nach
# 2 % aus (74 von 3.296), waehrend es unter den echten Versuchen **79 %** holt (74 von 94).
# Genau diese Fehldeutung hat am 21.08. dazu gefuehrt, den groessten deutschen Abrufer ans
# Ende der Reihenfolge zu sortieren.
_KEIN_VERSUCH = ("exists",)


def _ausbeute(kurz: str, tage: int = 7) -> float | None:
    """Anteil erfolgreicher Abrufe der letzten Tage. ``None``, wenn es keine Historie gibt."""
    import duckdb

    verz = ROOT / "data" / "docs" / "DE"
    # cosinex schreibt in `_manifest.parquet` ohne Namenszusatz — historisch der erste.
    pfad = verz / (f"_manifest_{kurz}.parquet" if kurz != "cosinex" else "_manifest.parquet")
    if not pfad.exists():
        return None
    try:
        v, g = duckdb.sql(
            f"""SELECT count(*), sum(CASE WHEN status IN {_ERFOLG!r} THEN 1 ELSE 0 END)
                FROM read_parquet('{pfad.as_posix()}')
                WHERE versucht_am >= current_date - {tage}
                  AND status NOT IN {_KEIN_VERSUCH!r}""").fetchone()
    except Exception:                                         # noqa: BLE001
        return None
    return (g or 0) / v if v else None


def rueckstand() -> list[tuple[str, int]]:
    """Kurzname → ERWARTETE Ausbeute (Rückstau × Trefferquote), absteigend.

    ⚠ Der rohe Rueckstau ist zu 88 % ehrlich: von 8.029 offenen Vergaben ohne Unterlagen
    wurden 7.107 noch NIE versucht. Die restlichen 922 tragen schon einen Manifest-Eintrag
    (405 `nur_liste`, 112 `leer`, 136 `fehler`) und schrumpfen den Rueckstau nie — dafuer
    eine Sonderbehandlung zu bauen, waere Aufwand fuer 11 %.

    ⚠ **Nach Rückstau allein zu sortieren waere falsch.** `subreport` steht bei 979 offenen
    Vergaben und liefert konstruktionsbedingt nur Dateilisten, nie ZIPs — sein Rueckstau
    schrumpft nie. Ohne Gewichtung hielte es einen Spitzenplatz auf Dauer besetzt.

    ⚠ **Das Manifest ist ein ZUSTAND je Vergabe, kein Protokoll der Versuche** (`schreibe`
    behaelt je Kennung nur den juengsten Satz). Die Quote hier misst also „von den zuletzt
    beruehrten Vergaben — wie viele haben einen Erfolgsstatus", nicht „von N Anfragen".
    #
    Ohne Historie gilt 0,5 — ein neuer Abrufer soll seine Chance bekommen, aber keinen Vorrang.

    Warum das hier steht und nicht im Arbeiter-Skript: die Zuordnung Portal → Abrufer lebt
    in den Modulen selbst (`ist_bimedien`, `is_cosinex`, …). Eine zweite Liste in Bash waere
    die Kopie, die als erste veraltet — und sie waere still falsch, nicht laut.

    ⚠ Die Prädikate heissen NICHT einheitlich: zehn Module schreiben `ist_*`, `docfetch`
    (cosinex) und `docfetch_rib` schreiben `is_*`. Ausgerechnet cosinex traegt den groessten
    Rueckstau — wer nur `ist_*` sucht, uebersieht ihn und haelt die Liste trotzdem fuer
    vollstaendig.
    """
    import importlib

    import duckdb

    from govisor.docfetch_queue import filtere, frueher

    L = (ROOT / "data" / "gold" / "DE" / "lead_export.parquet").as_posix()
    T = (ROOT / "data" / "docs" / "DE" / "doc_text.parquet").as_posix()
    con = duckdb.connect()
    schon = {n for (n,) in con.execute(
        f"SELECT DISTINCT notice_id FROM read_parquet('{T}')").fetchall()} \
        if (ROOT / "data" / "docs" / "DE" / "doc_text.parquet").exists() else set()
    # ⚠ OPEN HOUSE GEHOERT NICHT IN DEN RUECKSTAU. Dort tritt man einem Rabattvertrag BEI,
    # statt zu bieten; die Unterlagen liegen systematisch hinter der Teilnahme, und die
    # Abrufer schliessen sie deshalb schon in ihrer eigenen Auswahl aus. Zaehlt man sie mit,
    # sieht ein Abrufer riesig aus und ist es nicht: von cosinex' scheinbaren 1.751 offenen
    # Vergaben sind **1.172 Open House** (67 %) und weitere 253 als `gated` bereits gelernt —
    # wirklich holbar sind 307. Ueber alle Abrufer: 1.953 der 7.936 sind Open House (25 %).
    offen = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L}')
        WHERE phase='open' AND deadline_date > current_date AND documents_url IS NOT NULL
          AND coalesce(procedure_kind, '') <> 'open_house'
    """).fetchall()
    con.close()
    offen = [(lid, url) for lid, url in offen if lid not in schon]

    zahlen: dict[str, int] = {}
    for kurz, modul in abrufer().items():
        try:
            m = importlib.import_module(modul)
        except Exception:                                     # noqa: BLE001
            continue
        pruefer = next((getattr(m, n) for n in dir(m)
                        if n.startswith(("ist_", "is_")) and callable(getattr(m, n))), None)
        if pruefer is None:
            continue
        try:
            treffer = [(lid, url) for lid, url in offen if pruefer(url)]
        except Exception:                                     # noqa: BLE001
            continue
        # Frueher Gescheitertes zaehlt ebenfalls nicht: der Abrufer wuerde es gar nicht
        # erst anfassen (`filtere`), es blaeht nur die Zahl auf, nach der wir sortieren.
        try:
            treffer, _ = filtere(treffer, frueher(ROOT / "data" / "docs" / "DE", kurz),
                                 lead_id=lambda x: x[0])
        except Exception:                                     # noqa: BLE001
            pass
        zahlen[kurz] = len(treffer)
    gewichtet = []
    for kurz, n in zahlen.items():
        quote = _ausbeute(kurz)
        quote = 0.5 if quote is None else quote
        gewichtet.append((kurz, n, round(n * quote)))
    # Ausgabe traegt BEIDE Zahlen: die Erwartung steuert, der rohe Rueckstau erklaert sie.
    gewichtet.sort(key=lambda x: (-x[2], -x[1]))
    return [(kurz, erwartet, roh) for kurz, roh, erwartet in gewichtet]


def frei() -> tuple[bool, str]:
    """Läuft der Tageslauf? Dann NICHT starten.

    Beide würden in dieselben Manifeste und denselben Dokumentenbaum schreiben. Der
    Tageslauf schützt sich per Lock; Aufrufe von Hand tun das nicht, und genau die sind
    im Projekt schon einmal kollidiert.
    """
    if LOCK.exists():
        return False, f"Tageslauf aktiv ({LOCK.name})"
    return True, ""


def eine_runde(modul: str, limit: int) -> tuple[int, str]:
    """Ein Abrufer-Aufruf. Gibt (Reststand vor der Runde, Rohausgabe) zurück."""
    befehl = ([sys.executable] + UEBER_CLI[modul] + ["--limit", str(limit)]
              if modul in UEBER_CLI else
              [sys.executable, "-m", modul, "--limit", str(limit)])
    p = subprocess.run(befehl, cwd=ROOT, capture_output=True, text=True)
    aus = (p.stdout or "") + (p.stderr or "")
    m = _REST.search(aus)
    return (_zahl(m.group(1)) if m else -1), aus


def abarbeiten(name: str, modul: str, stunden: float, limit: int) -> int:
    ende = time.time() + stunden * 3600
    runde, vorher = 0, None
    print(f"\n══ {name} ({modul}) — bis zu {stunden:g} h, {limit} je Runde")
    while time.time() < ende:
        runde += 1
        t0 = time.time()
        rest, aus = eine_runde(modul, limit)
        dauer = time.time() - t0

        if rest < 0:
            print(f"  Runde {runde}: kein Reststand gemeldet — Abrufer sagt:")
            for z in [z for z in aus.splitlines() if z.strip()][-4:]:
                print(f"      {z[:96]}")
            return 1

        geholt = (vorher - rest) if vorher is not None else 0
        tempo = geholt / (dauer / 60) if dauer > 30 else 0
        rest_h = (rest / tempo / 60) if tempo > 0 else None
        print(f"  Runde {runde:>3}: noch {rest:>6,} offen"
              + (f" · {geholt:>4} geschafft in {dauer/60:>5.1f} min" if vorher is not None else "")
              + (f" · {tempo:>5.1f}/min · Rest ~{rest_h:.1f} h" if rest_h else ""), flush=True)

        if rest == 0:
            print(f"  ✓ {name} ist leer.")
            return 0
        # KEIN FORTSCHRITT heisst aufhoeren, nicht weiterprobieren. Wenn eine Runde nichts
        # bewegt, liegt es am Portal (Sperre, Konto, alles dauerhaft aussichtslos) und
        # nicht daran, dass zu wenig Runden gelaufen sind. Weiterlaufen hiesse, dieselbe
        # Absage stundenlang zu wiederholen.
        if vorher is not None and rest >= vorher:
            print(f"  ⏹ keine Bewegung ({vorher:,} → {rest:,}) — hier ist Schluss.")
            for z in [z for z in aus.splitlines() if z.strip()][-3:]:
                print(f"      {z[:96]}")
            return 2
        vorher = rest
    print(f"  ⏱ Zeitgrenze von {stunden:g} h erreicht, noch {vorher or '?'} offen. "
          f"Erneut aufrufen setzt fort.")
    return 3


def main(argv=None) -> int:
    reg = abrufer()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zeigen", action="store_true", help="verfügbare Abrufer auflisten")
    ap.add_argument("--rueckstand", action="store_true",
                    help="Abrufer nach offenem Rückstau sortiert (Name<TAB>Zahl)")
    ap.add_argument("--connector", help=f"einer von: {', '.join(sorted(reg))}")
    ap.add_argument("--stunden", type=float, default=4.0)
    ap.add_argument("--limit", type=int, default=60, help="Vorgänge je Runde")
    ap.add_argument("--trotzdem", action="store_true",
                    help="auch bei laufendem Tageslauf starten (nur wenn man weiss, warum)")
    a = ap.parse_args(argv)

    if a.rueckstand:
        for kurz, erwartet, roh in rueckstand():
            print(f"{kurz}\t{erwartet}\t{roh}")
        return 0
    if a.zeigen or not a.connector:
        print("Dokument-Abrufer:")
        for k, m in sorted(reg.items()):
            print(f"  {k:<20} {m}")
        print("\n  scripts/rueckstau.py --connector <name> [--stunden 4] [--limit 60]")
        return 0

    if a.connector not in reg:
        print(f"Unbekannt: {a.connector}. Bekannt: {', '.join(sorted(reg))}", file=sys.stderr)
        return 1

    ok, grund = frei()
    if not ok and not a.trotzdem:
        print(f"⛔ {grund} — nicht gestartet. Mit --trotzdem erzwingen.", file=sys.stderr)
        return 75

    os.environ.setdefault("GOVISOR_VORGANG_FRIST", "480")
    return abarbeiten(a.connector, reg[a.connector], a.stunden, a.limit)


if __name__ == "__main__":
    raise SystemExit(main())

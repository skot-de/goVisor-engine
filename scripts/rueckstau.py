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


def _land_von(kurz: str) -> str:
    """Zu welchem Land gehoert dieser Abrufer? Aus der Registry, nicht geraten.

    ⚠ Bis zum 2026-09-15 stand ueberall fest `data/docs/DE`. Fuer `docfetch_lu`,
    `vergabeportal_at` und `simap_docs` ist das schlicht das falsche Verzeichnis: ihre
    Manifeste und ihre Dokumente liegen unter LU, AT und CH. Die Folge war kein Fehler,
    sondern Stille — ein Abrufer ohne Rueckstau kommt nie dran.
    """
    for q in S.DOC_REGISTRY:
        if q.modul and q.modul.rsplit(".", 1)[-1].replace("docfetch_", "").replace("docfetch", "cosinex") == kurz:
            return getattr(q, "country", "DE") or "DE"
    return "DE"


def _manifest_ort(kurz: str):
    return ROOT / "data" / "docs" / _land_von(kurz)


def _ausbeute(kurz: str, tage: int = 7) -> float | None:
    """Anteil erfolgreicher Abrufe der letzten Tage. ``None``, wenn es keine Historie gibt."""
    import duckdb

    verz = _manifest_ort(kurz)
    # ⚠ DERSELBE DREHER WIE IN `rueckstand()`, nur leiser. Hier stand der Kurzname direkt im
    # Dateinamen; fuer `simap_docs` und `vergabeportal_at` heisst die Datei aber
    # `_manifest_simap.parquet` bzw. `_manifest_vergabeportal.parquet`. Ergebnis war kein
    # Fehler, sondern `None` — und damit die Vorgabequote 0,5 statt der gemessenen. Die
    # Zuordnung steht jetzt an einer Stelle: `docfetch_queue.KENNUNG`.
    from govisor.docfetch_queue import _pfad, kennung
    name, _ = kennung(kurz)
    pfad = _pfad(verz, name)
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


# Nebenausgabe von `rueckstand()`: {abrufer: {grund: anzahl}}. Modulweit statt im
# Rueckgabewert, damit die Signatur ihrer 13 Aufrufer sich nicht aendert.
LETZTE_LAGEN: dict[str, dict[str, int]] = {}


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

    from govisor.docfetch_queue import ManifestFehler, filtere, frueher, kennung

    # ⚠ ALLE AKTIVEN LAENDER, NICHT NUR DE — seit 2026-09-15.
    #
    # Hier stand `data/gold/DE/lead_export.parquet`, fest. Diese Funktion entscheidet, WER
    # drankommt: der Dauerarbeiter waehlt seine Abrufer nach dem Rueckstau, den sie hier
    # bekommen. Und weil luxemburgische, oesterreichische und schweizerische Adressen in
    # DEUTSCHEN Leads nicht vorkommen, stand ihr Rueckstau dauerhaft auf 0 — sie wurden
    # nie gewaehlt.
    #
    # Seit dem 2026-08-18 holt der Tageslauf keine Unterlagen mehr („das macht der
    # Dauerarbeiter"). Vier Wochen lang hat damit NIEMAND die Unterlagen von LU, AT und CH
    # geholt. Gemessen am 2026-09-15, als es auffiel:
    #
    #     LU    169 abrufbare Vorgaenge  (Manifest kannte 3)
    #     AT    254
    #     CH  1.599
    #
    # ⚠ Bei Luxemburg ist das nicht nachholbar: dort verschwinden die Unterlagen nach
    # Fristende. Ein Abrufer, der nicht auf der Liste steht, sieht aus wie einer, der
    # nichts zu tun hat — und ein leerer Rueckstau wie erledigte Arbeit.
    #
    # Die Laenderliste kommt aus `govisor/laender.py`, nicht aus einer zweiten Aufzaehlung.
    from govisor.laender import AKTIV

    def _vorhanden(unter: str, datei: str) -> list[str]:
        return [q.as_posix() for l in AKTIV
                if (q := ROOT / "data" / unter / l / datei).exists()]

    leads = _vorhanden("gold", "lead_export.parquet")
    texte = _vorhanden("docs", "doc_text.parquet")
    if not leads:
        return []
    con = duckdb.connect()
    L = "[" + ", ".join(f"'{x}'" for x in leads) + "], union_by_name=true"
    schon = {n for (n,) in con.execute(
        "SELECT DISTINCT notice_id FROM read_parquet(["
        + ", ".join(f"'{x}'" for x in texte) + "], union_by_name=true)").fetchall()} \
        if texte else set()
    # ⚠ OPEN HOUSE GEHOERT NICHT IN DEN RUECKSTAU. Dort tritt man einem Rabattvertrag BEI,
    # statt zu bieten; die Unterlagen liegen systematisch hinter der Teilnahme, und die
    # Abrufer schliessen sie deshalb schon in ihrer eigenen Auswahl aus. Zaehlt man sie mit,
    # sieht ein Abrufer riesig aus und ist es nicht: von cosinex' scheinbaren 1.751 offenen
    # Vergaben sind **1.172 Open House** (67 %) und weitere 253 als `gated` bereits gelernt —
    # wirklich holbar sind 307. Ueber alle Abrufer: 1.953 der 7.936 sind Open House (25 %).
    offen = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet({L})
        WHERE phase='open' AND deadline_date > current_date AND documents_url IS NOT NULL
          AND coalesce(procedure_kind, '') <> 'open_house'
    """).fetchall()
    con.close()
    offen = [(lid, url) for lid, url in offen if lid not in schon]

    zahlen: dict[str, int] = {}
    # Warum ein Kandidat NICHT geholt wird, je Abrufer — die zweite Liste, die bis
    # zum 2026-09-20 fehlte. Der Trichter zeigte 15.972 Leads mit Link und 6.399
    # geholte; warum die uebrigen 9.573 fehlen, sagte niemand.
    lagen: dict[str, dict[str, int]] = {}
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
        #
        # ⚠ HIER STAND `frueher(_manifest_ort(kurz), kurz)` — mit dem KURZNAMEN als
        # Manifest-Namen und ohne Schluesselfeld. Bei drei von dreizehn Abrufern ging das
        # daneben (Namensdreher bzw. `notice_id` statt `lead_id`), und `frueher` antwortete
        # mit einem leeren Ergebnis, das aussieht wie „noch nichts versucht". Folge: jeder
        # laengst gelernte Ausgang zaehlte weiter mit. Gemessen am 2026-09-20 —
        # simap_docs 1.566 gemeldet / 3 echt, cosinex 318 / 0.
        #
        # ⚠ UND DAS `except Exception: pass` DARUM HAT ES ZUGEDECKT. Ein Defekt im Aufruf
        # darf nicht in denselben Topf wie ein unlesbares Manifest. `ManifestFehler` faellt
        # deshalb bewusst durch.
        name, id_feld = kennung(kurz)
        try:
            # ⚠ Das Manifest liegt beim Land des Abrufers, nicht bei DE.
            treffer, gruende = filtere(
                treffer, frueher(_manifest_ort(kurz), name, id_feld=id_feld, streng=True),
                lead_id=lambda x: x[0])
            lagen[kurz] = gruende
        except ManifestFehler:
            raise
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
    global LETZTE_LAGEN
    LETZTE_LAGEN = lagen
    return [(kurz, erwartet, roh) for kurz, roh, erwartet in gewichtet]


# ── DIE ZWEITE LISTE: warum ein Kandidat NICHT geholt wird ───────────────────────────────
#
# WARUM (Sven, 2026-09-20): „macht es nicht sinn die eintraege zu flaggen und je nach flag
# werden sie uebersprungen bzw in eine andere liste uebertragen?"
#
# Die Flags gibt es laengst — `docfetch_queue` fuehrt sie in DAUERHAFT, BLOCKIERT, WARTET
# und KEIN_FEHLSCHLAG, und jeder Abrufer schreibt sie sauber ins Manifest. Was fehlte, war
# die zweite Liste: `--rueckstand` zaehlt nur, was zu HOLEN ist, und alles andere fiel
# stumm heraus. `scripts/dokumente_stand.py` zeigte 15.972 Leads mit Link und 6.399 geholte
# — und ueber die uebrigen 9.573 sagte niemand ein Wort.
#
# ⚠ DER UNTERSCHIED IST NICHT KOSMETISCH. `blockiert:konto` ist eine Geschaeftsfrage (lohnt
# ein Zugang?), `blockiert:parser` eine Arbeitsliste fuer uns, `dauerhaft` ein Schlussstrich
# und `Sperre` nur Geduld. Zusammengeworfen sehen alle vier aus wie „geht halt nicht".
_KLASSE = {
    "dauerhaft": "endgueltig — nichts mehr zu holen",
    "konto":     "braucht einen Zugang        (Geschaeftsfrage)",
    "passwort":  "nur fuer eingeladene Bieter (nicht loesbar)",
    "interesse": "braucht Interessensbekundung (Geschaeftsfrage)",
    "parser":    "unsere Baustelle            (Arbeitsliste)",
    "portal":    "Portal gibt es anonym nicht her",
    "groesse":   "ueber der Groessengrenze dieses Laufs",
    "sperre":    "Sperrfrist laeuft noch      (kommt von selbst wieder)",
}


def _klasse_von(grund: str) -> str:
    """Manifest-Status → Klasse. Die Zuordnung steht in `docfetch_queue`, nicht hier."""
    from govisor.docfetch_queue import BLOCKIERT, DAUERHAFT, normalisiere
    st = normalisiere(grund)
    if st in DAUERHAFT:
        return "dauerhaft"
    b = BLOCKIERT.get(st)
    if b:
        return b
    return "sperre"


def zeige_lage() -> int:
    """Warum die Kandidaten nicht geholt werden — je Klasse, ueber alle Abrufer."""
    import collections

    reihen = rueckstand()
    offen_gesamt = sum(roh for _, _, roh in reihen)
    je_klasse: dict[str, int] = collections.Counter()
    je_klasse_abrufer: dict[str, dict[str, int]] = collections.defaultdict(collections.Counter)
    for kurz, gruende in LETZTE_LAGEN.items():
        for grund, n in gruende.items():
            k = _klasse_von(grund)
            je_klasse[k] += n
            je_klasse_abrufer[k][kurz] += n

    print(f"  Zu holen (Rueckstau ueber alle Abrufer): {offen_gesamt:,}")
    print()
    print("  NICHT zu holen, und warum:")
    for k, n in sorted(je_klasse.items(), key=lambda x: -x[1]):
        wer = ", ".join(f"{a} {v:,}" for a, v in
                        sorted(je_klasse_abrufer[k].items(), key=lambda x: -x[1])[:3])
        print(f"    {n:>7,}  {_KLASSE.get(k, k):<44} {wer}")
    summe = sum(je_klasse.values())
    print(f"    {summe:>7,}  zusammen")
    print()
    print("  Die zwei Geschaeftsfragen stehen oben: ein Zugang bzw. eine Interessens-")
    print("  bekundung wuerde genau diese Vorgaenge freischalten. `parser` ist unsere")
    print("  Arbeit, `dauerhaft` ist erledigt, `Sperre` kommt von selbst wieder.")
    return 0


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
    ap.add_argument("--lage", action="store_true",
                    help="warum die uebrigen Kandidaten NICHT geholt werden (nach Klasse)")
    ap.add_argument("--connector", help=f"einer von: {', '.join(sorted(reg))}")
    ap.add_argument("--stunden", type=float, default=4.0)
    ap.add_argument("--limit", type=int, default=60, help="Vorgänge je Runde")
    ap.add_argument("--trotzdem", action="store_true",
                    help="auch bei laufendem Tageslauf starten (nur wenn man weiss, warum)")
    a = ap.parse_args(argv)

    if a.lage:
        return zeige_lage()
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

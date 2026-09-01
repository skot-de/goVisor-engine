#!/usr/bin/env python3
"""Fragenkataloge im Bestand → `doc_qa_stand`: eine Zeile je Vorgang, ohne LLM.

Die billige Schicht aus `docs/bieterfragen-datenmodell.md`, Schritt 1. Sie zaehlt und
vergleicht Daten — mehr nicht. Kein Modellaufruf, keine Kosten, keine Nutzerhandlung.

WOFUER: Aus einem Fragenkatalog fallen drei Zahlen, die in keiner Bekanntmachung stehen:
wie oft die Unterlagen fortgeschrieben wurden, wie viele Fragen gestellt wurden, und wie
kurz vor Fristende die Vergabestelle geantwortet hat. Die letzte ist die schaerfste: wer
drei Tage vor Abgabe erfaehrt, dass sich eine Anforderung geaendert hat, kann nicht mehr
reagieren.

⚠ WAS DIESE TABELLE NICHT IST: der Inhalt. Frage- und Antworttexte, ihre Wirkung auf die
Anforderungen und die Verweise gehoeren nach `doc_qa` und brauchen das LLM (Schritt 2).
Hier steht nur, WIEVIEL und WANN — nie, WAS.

Aufruf:  python3 scripts/build_doc_qa_stand.py [--land DE] [--ziel data/gold]
"""
import argparse
import datetime as _dt
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import doctypes as dt                                   # noqa: E402

# ── ERKENNUNG ────────────────────────────────────────────────────────────────────────
#
# ⚠ Der Doktyp allein genuegt NICHT. 1.510 der 2.217 als `fragenantworten` erkannten
# Dokumente sind LEERFORMULARE („FB6_Bieterfrage" — der Vordruck, auf dem der Bieter
# seine Frage stellt), nicht Antworten. Wer nur den Doktyp zaehlt, meldet dreimal so
# viele Fragenkataloge wie es gibt. Deshalb muss BEIDES im Text stehen: eine Frage und
# eine Antwort.
FRAGE = re.compile(r'frage\s*(?:nr\.?)?\s*(\d{1,3})|^\s*frage\s*:', re.I | re.M)
ANTWORT = re.compile(r'^\s*antwort\s*:|antwort\s*(?:nr\.?)?\s*\d{1,3}|beantwortung der', re.I | re.M)

# Fassungskennung, in der Reihenfolge ihrer Verlaesslichkeit. `Version` steht bei 320 von
# 707 Dokumenten im PFAD (`Vergabeunterlagen/Version 3/...`) — das ist der versionierte
# Unterlagensatz des Portals und damit die belastbarste Quelle. Die Textfunde bestaetigen
# die Bedeutung („es wurde eine neue Version der Vergabeunterlagen erzeugt (Version 2)").
#
# ⚠ ES BLIEB EINE EINZIGE REGEL UEBRIG, und das ist das Ergebnis einer Messung, nicht
# der Bequemlichkeit. Die naheliegende Regel „Bieterinformation Nr. N" war mit 102 von
# 257 Vorgaengen die groesste Gruppe und in fast jedem nachgesehenen Fall FALSCH:
#   · `Beantwortete Bieterfragen Nr. 82-87.pdf`  → 82 ist eine FRAGENNUMMER, keine Fassung
#   · `Bieterfragen_Stand_30.07.2026.pdf`        → 30 ist der TAG eines Datums
#   · `Bieterfragen29.07.2027.pdf`               → dito
#   · `260811_ENSPE_50_Bieterfragen.pdf`         → 50 ist ein Projektkuerzel
# Das `\D{0,12}` sprang ueber jeden Trenner und griff die naechstbeste Zahl. Eine Regel,
# die in der Mehrzahl der Faelle etwas anderes misst, als ihr Name sagt, gehoert nicht
# verschaerft, sondern entfernt — sonst steht im Produkt „82 Fortschreibungen" an einem
# Verfahren, das zwei hatte.
#
# `Version N` bleibt, weil es im PFAD steht (`Vergabeunterlagen/Version 3/...`): das ist
# der versionierte Unterlagensatz des Portals selbst, keine Zahl aus einem Fliesstext.
FASSUNG = [
    ("version", re.compile(r'\bversion\s*(\d{1,2})\b', re.I)),
]
DATUM = [re.compile(r'(20\d{2})-(\d{2})-(\d{2})'),
         re.compile(r'(?:^|\D)(\d{1,2})\.(\d{1,2})\.(20\d{2})')]

SPALTEN = ("notice_id VARCHAR, land VARCHAR, n_dokumente INTEGER, n_fassungen INTEGER, "
           "fassung_quelle VARCHAR, n_fragen INTEGER, n_antwortmarken INTEGER, "
           "letztes_datum DATE, datum_quelle VARCHAR, deadline DATE, tage_vor_frist INTEGER, "
           "beleg_stufe VARCHAR")


def _datum(text: str):
    """Erstes plausibles Datum. ⚠ Nur Jahre 20xx und Monate 1-12 — sonst liest die
    Punktform jede Gliederungsnummer („3.12.2026" als Absatz) als Datum."""
    for rx in DATUM:
        for m in rx.finditer(text):
            g = m.groups()
            j, mo, t = (int(g[0]), int(g[1]), int(g[2])) if len(g[0]) == 4 \
                else (int(g[2]), int(g[1]), int(g[0]))
            if 1 <= mo <= 12 and 1 <= t <= 31 and 2020 <= j <= 2035:
                try:
                    return _dt.date(j, mo, t)
                except ValueError:
                    continue
    return None


def sammle(land: str) -> tuple[dict, int, int]:
    """Alle verwertbaren Fragenkataloge je Vorgang. Gibt auch die Verwerfungszahlen
    zurueck, damit im Bericht steht, was NICHT gezaehlt wurde."""
    import duckdb
    quelle = ROOT / "data" / "docs" / land / "doc_text.parquet"
    if not quelle.exists():
        return {}, 0, 0
    con = duckdb.connect()
    rows = con.execute(
        f"select notice_id, file, text from read_parquet('{quelle}') "
        "where status='ok' and n_chars > 200").fetchall()
    con.close()

    je: dict = {}
    leerformulare = 0
    doppelt = 0
    gesehen: set = set()
    for nid, datei, text in rows:
        if dt.classify(datei) != "fragenantworten":
            continue
        t = str(text)
        if not (FRAGE.search(t) and ANTWORT.search(t)):
            leerformulare += 1
            continue
        # ⚠ Entdoppeln. Dasselbe Bulletin liegt oft in mehreren Archiven eines Vorgangs
        # (`Nachschreiben I.zip` enthaelt, was auch lose danebenliegt). Ohne diesen
        # Schritt zaehlt ein Vorgang fuenf Fassungen, wo eine ist — gemessen an der
        # 190.647-Zeichen-Datei, die fuenfmal auftauchte.
        schluessel = (nid, len(t), t[:200])
        if schluessel in gesehen:
            doppelt += 1
            continue
        gesehen.add(schluessel)
        je.setdefault(nid, []).append((str(datei), t))
    return je, leerformulare, doppelt


def zeile(nid: str, land: str, dokumente: list, frist) -> tuple:
    fassungen: list[int] = []
    quellen: list[str] = []
    fragen: set = set()
    marken = 0
    datteln: list = []
    for datei, t in dokumente:
        probe = datei + "\n" + t[:3000]
        for name, rx in FASSUNG:
            if m := rx.search(probe):
                fassungen.append(int(m.group(1)))
                quellen.append(name)
                break
        fragen |= {g for g in FRAGE.findall(t) if g}
        marken += len(ANTWORT.findall(t))
        # Der Dateiname ist die verlaesslichere Quelle: er traegt fast immer den Stand
        # („Bieterfragen_Stand_30.07.2026"), waehrend im Text jedes Vertragsdatum steht.
        if d := _datum(datei):
            datteln.append((d, "dateiname"))
        elif d := _datum(t[:2000]):
            datteln.append((d, "text"))

    # ⚠ Ohne Fassungskennung ist die Zahl der Dokumente die ehrlichere Schaetzung — und
    # `fassung_quelle` sagt, welche der beiden es war. Eine Zahl ohne ihre Herkunft ist
    # in dieser Tabelle wertlos, weil beide Wege verschieden verlaesslich sind.
    if fassungen:
        n_fassungen, quelle = max(fassungen), max(set(quellen), key=quellen.count)
    else:
        n_fassungen, quelle = len(dokumente), "dokumentzahl"

    letztes, dquelle = (max(datteln, key=lambda x: x[0])[0],
                        max(datteln, key=lambda x: x[0])[1]) if datteln else (None, None)
    # ⚠ Plausibilitaetsfenster. Ohne es steht in der Tabelle „Antwort 656 Tage vor der
    # Frist" (ein Vertragsbeginn im Text) und „114 Tage danach". Beides ist kein
    # Antwortdatum, sondern ein falsch gegriffenes. Unplausibles wird NULL und im
    # Bericht gezaehlt — nicht stillschweigend mitgerechnet.
    tage = (frist - letztes).days if (frist and letztes) else None
    if tage is not None and not (0 <= tage <= 180):
        tage = None
    return (nid, land, len(dokumente), n_fassungen, quelle, len(fragen), marken,
            letztes, dquelle, frist, tage, "korpus")


def schreibe(con, pfad: pathlib.Path, zeilen: list, spalten: str) -> None:
    """Wie `build_doc_analysis.schreibe` — ueber Arrow statt executemany."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"CREATE OR REPLACE TABLE _t ({spalten})")
    if zeilen:
        import pyarrow as pa
        namen = [s.strip().split()[0] for s in spalten.split(",")]
        spaltenweise = list(zip(*zeilen))
        con.register("_arrow", pa.table({namen[i]: pa.array(spaltenweise[i])
                                         for i in range(len(namen))}))
        con.execute("INSERT INTO _t SELECT * FROM _arrow")
        con.unregister("_arrow")
    con.execute(f"COPY (SELECT * FROM _t) TO '{pfad}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute("DROP TABLE _t")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--land", default="DE")
    p.add_argument("--ziel", default="data/gold")
    a = p.parse_args()

    je, leerformulare, doppelt = sammle(a.land)
    if not je:
        # ⚠ Kein Fehler. AT und CH haben heute kein `doc_text` — die Funktion gilt fuer
        # alle Laender, die Daten fehlen nur. Ein Abbruch waere hier eine Falschmeldung.
        print(f"  {a.land}: keine Fragenkataloge im Bestand — nichts zu tun.")
        return 0

    import duckdb
    con = duckdb.connect()
    fristen: dict = {}
    lead = ROOT / "data" / "gold" / a.land / "lead_export.parquet"
    if lead.exists():
        fristen = dict(con.execute(
            f"select lead_id, deadline_date from read_parquet('{lead}') "
            "where deadline_date is not null").fetchall())

    zeilen = [zeile(nid, a.land, dok, fristen.get(nid)) for nid, dok in sorted(je.items())]
    ziel = (ROOT / a.ziel) if not pathlib.Path(a.ziel).is_absolute() else pathlib.Path(a.ziel)
    schreibe(con, ziel / a.land / "doc_qa_stand.parquet", zeilen, SPALTEN)
    con.close()

    mit_frist = [z for z in zeilen if z[10] is not None]
    knapp = [z for z in mit_frist if z[10] <= 7]
    print(f"  doc_qa_stand ({a.land}): {len(zeilen):,} Vorgaenge, "
          f"{sum(z[2] for z in zeilen):,} Dokumente")
    print(f"    verworfen: {leerformulare:,} Leerformulare, {doppelt:,} Dubletten")
    print(f"    Fassungsquelle: " + ", ".join(
        f"{q} {sum(1 for z in zeilen if z[4] == q)}"
        for q in dict.fromkeys(z[4] for z in zeilen)))
    if mit_frist:
        tage = sorted(z[10] for z in mit_frist)
        print(f"    Antwort vor Fristende: Median {tage[len(tage)//2]} Tage "
              f"({len(mit_frist)} Vorgaenge mit bekannter Frist)")
        print(f"    davon 7 Tage oder knapper: {len(knapp)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

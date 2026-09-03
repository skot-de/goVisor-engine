#!/usr/bin/env python3
"""LB-Volltext je Vorgang → web/data/doc-text.json für die Lead-Detail-Anzeige.

Quelle: data/docs/<country>/doc_text.parquet (aus `index-docs`). Ein Vorgang (notice_id) hat
mehrere Dateien; hier je notice_id zusammengefügt (status='ok' und 'ocr'), mit Dateiüberschriften.
Ausgabe: {notice_id: {chars, files, text}}. Pro Vorgang auf CAP Zeichen gekürzt (Payload zähmen —
für den Volltext-Download gibt es später die echte Datei/Objektspeicher).

Aufruf: python3 scripts/export_doc_text.py
"""
import argparse
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
# ⚠ ERST den Projektpfad, DANN `govisor` importieren. Unter launchd gibt es kein
# PYTHONPATH; ein Import davor bricht stumm ab (s. test_skripte_finden_govisor_ohne_pythonpath).
sys.path.insert(0, str(ROOT))
from govisor.docpipe import SQL_BRAUCHBAR, ueberholte  # noqa: E402
SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
# Eine Datei je Vorgang — der einzige Weg, auf dem der Volltext ausgeliefert wird.
JE_VORGANG = ROOT / "web" / "data" / "doc-text"
# Verzeichnis OHNE Text: wer da ist, wie viele Zeichen, aus wie vielen Dateien. Rund 200 KB
# statt 294 MB. Es beantwortet alle Fragen, die nicht den Text selbst brauchen (Trichter im
# Lauf-Monitor, `scripts/dokumente_stand.py`).
INDEX = ROOT / "web" / "data" / "doc-text-index.json"
# Der alte Sammelblock. Wird nur noch geloescht, nie geschrieben.
ALT = ROOT / "web" / "data" / "doc-text.json"
CAP = 60_000  # Zeichen je Vorgang im JSON
# ⚠ WANN DER LAUF UEBERHAUPT ETWAS ZU TUN HAT. Der Dokument-Arbeiter ruft dieses Skript alle
# zehn Minuten auf. Am 29.08. hat es dabei in einer ganzen Stunde NULL von 9.128 Dateien
# geschrieben — es gab schlicht nichts Neues. Bezahlt wurde der Lauf trotzdem: die ganze
# Parquet-Datei durch den Speicher, gemessen 14 GB auf einer 16-GB-Maschine. Der Rechner war
# dadurch waehrend der Laufzeit praktisch unbedienbar.
#
# Die Quelle wird ausschliesslich von `index-docs` geschrieben. Aendert sie sich nicht, kann
# sich das Ergebnis nicht aendern — dann genuegt ein Blick auf Zeitstempel und Groesse.
STAND = ROOT / "data" / ".doc_text_export.json"
# ⚠ EIN ZWEITER MERKER, EINE EBENE FEINER. `STAND` oben beantwortet „hat sich die Quelle
# ueberhaupt geruehrt" — und im Nachtlauf lautet die Antwort IMMER ja, weil die
# Dokument-Arbeiter rund um die Uhr in dieselbe Datei schreiben. Der grobe Waechter greift
# damit nie, und der Lauf verarbeitete alle 243.478 Zeilen neu, um am Ende festzustellen,
# dass sich an fast keinem Vorgang etwas geaendert hat.
#
# Dieser hier haelt je VORGANG einen Fingerabdruck. Er kostet 1,6 s (eine Aggregation ohne
# die Textspalte, `n_chars` steht ohnehin in der Quelle) und erspart das Lesen des Textes
# fuer alles Unveraenderte.
JE_VORGANG_STAND = ROOT / "data" / ".doc_text_je_vorgang.json"

_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{3,}")


def _sicher(nid: str) -> str:
    """Kennung → Dateiname. Der Name wird zum URL-Pfad; ein `../` waere ein Pfadwechsel."""
    return "".join(c for c in nid if c.isalnum() or c in "-_")


def _abdruecke(con) -> dict[str, str]:
    """Je Vorgang ein Fingerabdruck, ohne die Textspalte anzufassen.

    Dateinamen gehoeren hinein, nicht nur Zahlen: `ueberholte()` entscheidet ANHAND DER
    NAMEN, welche Fassung ausgeliefert wird. Ein Nachtrag, der eine Datei ersetzt, kann
    Zeilenzahl und Zeichensumme unveraendert lassen und trotzdem ein anderes Ergebnis
    erzeugen.
    """
    zeilen = con.execute(
        f"""SELECT notice_id,
                   count(*) || ':' || coalesce(sum(n_chars), 0) || ':'
                   || md5(string_agg(file || '\x1f' || status, '\x1e' ORDER BY file, status))
            FROM read_parquet('{SRC.as_posix()}')
            WHERE {SQL_BRAUCHBAR} AND text IS NOT NULL AND length(text) > 0
            GROUP BY 1""").fetchall()
    return {str(a): str(b) for a, b in zeilen}


def _alter_index() -> dict[str, dict]:
    """Der Index des letzten Laufs — die Quelle fuer alles, was uebernommen wird."""
    if not INDEX.exists():
        return {}
    try:
        roh = json.loads(INDEX.read_text(encoding="utf-8"))
        return roh if isinstance(roh, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _alte_abdruecke() -> dict[str, str]:
    if not JE_VORGANG_STAND.exists():
        return {}
    try:
        roh = json.loads(JE_VORGANG_STAND.read_text(encoding="utf-8"))
        return roh if isinstance(roh, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def clean(t: str) -> str:
    t = t.replace("\x00", " ").replace("\r", "\n")
    t = _WS.sub(" ", t)
    t = _NL.sub("\n\n", t)
    return t.strip()


def _quelle_stand() -> dict:
    """Fingerabdruck der Quelle: Zeitstempel und Groesse. Beides billig, beides genug."""
    st = SRC.stat()
    return {"mtime": int(st.st_mtime), "groesse": st.st_size}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--erzwingen", action="store_true",
                    help="auch laufen, wenn die Quelle unveraendert ist")
    ap.add_argument("--sortieren", action="store_true",
                    help="Quelle vor dem Lesen sortieren (teuer; nur noetig, wenn der Lauf "
                         "zerrissene Vorgaenge meldet)")
    a = ap.parse_args(argv)

    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst `index-docs` laufen lassen.")
        return 1

    stand = _quelle_stand()
    if not a.erzwingen and INDEX.exists() and STAND.exists():
        try:
            if json.loads(STAND.read_text(encoding="utf-8")) == stand:
                print("LB-Volltext: Quelle unveraendert — nichts zu tun. (--erzwingen laeuft trotzdem)")
                return 0
        except Exception:                       # noqa: BLE001
            pass                                # kaputter Stand → lieber einmal zu viel laufen

    con = duckdb.connect()
    # ⚠ NICHT SORTIEREN. Hier stand `ORDER BY notice_id, file` — und genau das war das
    # Speicherproblem: DuckDB muss dafuer 817 MB Parquet MIT den Volltext-Spalten
    # materialisieren. Mit einer Grenze von 1 GB oder 2 GB steigt es mit
    # OutOfMemoryException aus, ohne Grenze nimmt es sich, was da ist.
    #
    # Gebraucht wird die Sortierung ohnehin nicht. `index-docs` schreibt vorgangsweise;
    # gemessen am 2026-08-30 ueber 223.747 Zeilen und 9.336 Vorgaenge: **kein einziger**
    # Vorgang ist in der Dateireihenfolge zerrissen. Die Reihenfolge der Dateien INNERHALB
    # eines Vorgangs stellt `verarbeite()` selbst her — das sind eine Handvoll Eintraege.
    #
    # ⚠ Verlassen wird sich darauf nicht: taucht eine Kennung doch ein zweites Mal auf,
    # zaehlt der Lauf das und sagt es laut. `--sortieren` erzwingt dann den alten Weg mit
    # genug Speicher. Eine stillschweigende Annahme waere hier ein halber Volltext.
    con.execute(f"SET memory_limit='{'6GB' if a.sortieren else '1GB'}'")
    # ⚠ `preserve_insertion_order=false` DARF HIER NICHT STEHEN. Ich hatte es gesetzt, weil
    # DuckDB es bei Speichernot selbst vorschlaegt — es erlaubt aber ausdruecklich, Zeilen
    # umzuordnen, und genau darauf beruht die Gruppierung ohne ORDER BY. Die Folge war
    # nicht ein Fehler, sondern ein WACKELN: derselbe Lauf schrieb mal 50, mal 62 Dateien,
    # und die Zeichensumme wanderte. Ein Ergebnis, das sich bei gleicher Eingabe aendert,
    # ist schlimmer als ein langsames.
    # ── Was hat sich ueberhaupt geruehrt? ───────────────────────────────────────────
    abdruecke = _abdruecke(con)
    alt_abdruck = {} if a.erzwingen else _alte_abdruecke()
    alt_index = {} if a.erzwingen else _alter_index()
    # ⚠ „GEPRUEFT UND NICHTS AUSZULIEFERN" IST AUCH EIN ERGEBNIS. Ein Vorgang, dessen
    # Dateien alle als ueberholt gelten, steht in KEINEM Index — er darf trotzdem als
    # erledigt gelten, sonst wird er jede Nacht erneut gelesen. Es entscheidet allein der
    # Fingerabdruck, nicht die Anwesenheit im Index. Genau diesen Fehler hatte ich am
    # selben Tag in `extract_positions.py` schon einmal gebaut.
    unveraendert = {n for n, fa in abdruecke.items() if alt_abdruck.get(n) == fa}
    zu_lesen = [n for n in abdruecke if n not in unveraendert]
    con.execute("create or replace temp table _zu (notice_id varchar)")
    if zu_lesen:
        con.executemany("insert into _zu values (?)", [(n,) for n in zu_lesen])

    ordnung = "ORDER BY notice_id, file" if a.sortieren else ""
    con.execute(
        f"""SELECT notice_id, file, filetype, text
            FROM read_parquet('{SRC.as_posix()}')
            SEMI JOIN _zu USING (notice_id)
            -- `ocr` wie `ok` — s. govisor/docpipe.py: der Zustand entsteht nur, wenn die
            -- Texterkennung Fachvokabular fand (>= 3 Begriffe der Vergabesprache).
            -- Gemessen 2026-08-18: 404 Vorgaenge bekommen dadurch zusaetzlichen Text,
            -- 3,23 Mio. Zeichen. KEIN Vorgang haengt allein daran — wer nur OCR-Text hat,
            -- existiert nicht (0 von 404). Es ist Tiefe, nicht Abdeckung.
            WHERE {SQL_BRAUCHBAR} AND text IS NOT NULL AND length(text) > 0
            {ordnung}"""
    )

    JE_VORGANG.mkdir(parents=True, exist_ok=True)
    vorhanden = {f.stem for f in JE_VORGANG.glob("*.json")}
    index: dict[str, dict] = {}
    # Unveraenderte uebernehmen: ihr Eintrag kommt aus dem alten Index, ihre Datei liegt
    # schon da und wird unten NICHT als verwaist geloescht.
    uebernommen = 0
    for nid in unveraendert:
        uebernommen += 1
        vorhanden.discard(_sicher(nid))
        if nid in alt_index:
            index[nid] = alt_index[nid]
    zerrissen: list[str] = []
    geschrieben = 0
    zeichen_gesamt = 0
    ueberholt_gesamt = 0

    def verarbeite(nid: str, dateien: list[tuple[str, str]]) -> None:
        """Ein Vorgang, fertig zusammengesetzt und geschrieben."""
        nonlocal geschrieben, zeichen_gesamt, ueberholt_gesamt
        # ── Nachtraege: ueberholte Fassungen nicht ausliefern ──────────────────────────
        # `docpipe` markiert sie seit dem 21.08. beim Indizieren (`status='ueberholt'`);
        # dieser Filter gilt dem, was VORHER indiziert wurde. Ohne ihn stuenden in der
        # Anzeige zwei Angebotsfristen untereinander, mit „── Datei ──"-Trenner dazwischen
        # und ohne Hinweis, welche gilt. Je DATEI, nicht je Fassung — s. `docpipe.ueberholte`.
        dateien = sorted(dateien, key=lambda x: x[0])   # ersetzt das teure ORDER BY … , file
        raus = ueberholte([f for f, _ in dateien])
        ueberholt_gesamt += len(raus)
        teile = [f"── {f} ──\n{clean(t)}" for f, t in dateien if f not in raus]
        if not teile:
            return
        full = "\n\n".join(teile)
        v = {"chars": len(full), "files": len(teile), "text": full[:CAP],
             "truncated": len(full) > CAP}
        index[nid] = {"chars": v["chars"], "files": v["files"], "truncated": v["truncated"]}
        zeichen_gesamt += v["chars"]
        # Der Dateiname wird zum URL-Pfad. Alles, was dort nichts zu suchen hat, faellt weg —
        # ein `../` in einer notice_id waere sonst ein Pfadwechsel beim Ausliefern.
        sicher = _sicher(nid)
        if not sicher:
            return
        ziel = JE_VORGANG / f"{sicher}.json"
        inhalt = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        vorhanden.discard(sicher)
        if ziel.exists() and ziel.read_text(encoding="utf-8") == inhalt:
            return
        ziel.write_text(inhalt, encoding="utf-8")
        geschrieben += 1

    # ⚠ IN STAPELN, NICHT AUF EINMAL. Hier stand `.fetchall()` — die ganze Tabelle samt
    # Volltexten in einem Rutsch. 817 MB Parquet werden dabei zu **14 GB** Python-Objekten,
    # und danach hielt der Code dieselben Texte in `docs` ein zweites Mal.
    #
    # Weil die Abfrage `ORDER BY notice_id, file` sortiert, liegen die Dateien eines
    # Vorgangs beieinander: es genuegt, sie zu sammeln, bis die naechste Kennung anfaengt.
    # Im Speicher steht damit EIN Vorgang statt neuntausend.
    BATCH = 500
    aktuelle_nid: str | None = None
    puffer: list[tuple[str, str]] = []
    while True:
        teil = con.fetchmany(BATCH)
        if not teil:
            break
        for nid, datei, _ftype, text in teil:
            if aktuelle_nid is not None and nid != aktuelle_nid:
                verarbeite(aktuelle_nid, puffer)
                puffer = []
                if nid in index:                  # Kennung kommt ein zweites Mal
                    zerrissen.append(nid)
            aktuelle_nid = nid
            puffer.append((datei, text))
    if aktuelle_nid is not None and puffer:
        verarbeite(aktuelle_nid, puffer)

    # Was der Lauf nicht mehr kennt, fliegt raus: eine alte Einzeldatei wuerde sonst ewig
    # weiter ausgeliefert, obwohl der Vorgang laengst aus dem Bestand ist.
    for verwaist in vorhanden:
        (JE_VORGANG / f"{verwaist}.json").unlink(missing_ok=True)

    # ⚠ KEIN SAMMELBLOCK MEHR. `doc-text.json` lag zuletzt bei 294 MB und stand neben den
    # Einzeldateien — dieselbe Menge zweimal, jede Nacht neu hochzuladen. Wer zaehlen will,
    # nimmt den Index; wer Text will, die Einzeldatei. Die alte Datei wird aktiv entfernt,
    # damit nicht irgendwo ein Monat alter Stand weiterlebt und wie aktuell aussieht.
    ALT.unlink(missing_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
    # Erst NACH dem Schreiben vermerken: bricht der Lauf vorher ab, laeuft der naechste
    # wieder an, statt eine halbe Ausgabe fuer fertig zu halten.
    STAND.write_text(json.dumps(stand), encoding="utf-8")
    # ⚠ ZULETZT, aus demselben Grund wie der grobe Stand darueber: bricht der Lauf vorher
    # ab, wird beim naechsten Mal zu viel gelesen. Das kostet Zeit. Andersherum gaelten
    # Vorgaenge als fertig, deren Zeilen nie geschrieben wurden.
    JE_VORGANG_STAND.write_text(json.dumps(abdruecke, separators=(",", ":")), encoding="utf-8")

    if zerrissen:
        print(f"  ⚠ {len(zerrissen):,} Vorgaenge liegen NICHT am Stueck in der Quelle "
              f"(z. B. {zerrissen[0]}). Ihr Volltext ist unvollstaendig. "
              f"Lauf mit --sortieren wiederholen.")
    if ueberholt_gesamt:
        print(f"  {ueberholt_gesamt:,} überholte Dateien aus Nachträgen übersprungen")
    # ⚠ AUS DEM INDEX, NICHT AUS DEM ZAEHLER. `zeichen_gesamt` zaehlt nur, was dieser Lauf
    # verarbeitet hat — seit unveraenderte Vorgaenge uebernommen werden, meldete die Zeile
    # „0 Zeichen gesamt" neben einem Index mit vier Milliarden. Eine Zahl, die bei gesunder
    # Lage Null sagt, laesst einen kaputten Lauf wie einen gesunden aussehen.
    gesamt = sum(int(v.get("chars") or 0) for v in index.values())
    print(f"LB-Volltext: {len(index)} Vorgänge ({gesamt:,} Zeichen gesamt)")
    print(f"  je Vorgang: {geschrieben:,} geschrieben, {uebernommen:,} unveraendert "
          f"uebernommen, {len(vorhanden):,} verwaiste entfernt "
          f"→ {JE_VORGANG.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

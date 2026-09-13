"""cosinex — „kein ZIP" ist drei verschiedene Dinge.

Ohne Netz. Geprüft wird die Einordnung der Antwort, nicht der Abruf.
"""
from __future__ import annotations

import pathlib

from govisor import docfetch
from govisor import docfetch_queue as q


def test_skript_und_stil_zaehlen_nicht_zum_sichtbaren_text():
    """⚠ Eine erste Fassung suchte im Roh-HTML nach „anmelden" und fand es überall — in
    CSS-Regeln und im Kopfmenü, das auf JEDER cosinex-Seite einen Login-Link trägt.
    Dieselbe Falle wie die had.de-Brotkrume."""
    html = ('<style>img.lazy{min-height:1px} .anmelden{color:red}</style>'
            '<script>var login="anmelden";</script>'
            '<div>Um Zugriff auf dieses Modul zu erhalten müssen Sie am '
            'Vergabeverfahren teilnehmen.</div>')
    t = docfetch._sichtbarer_text(html)
    assert "img.lazy" not in t and "var login" not in t
    assert "am Vergabeverfahren teilnehmen" in t


def test_teilnahme_wird_erkannt():
    assert docfetch._TEILNAHME.search(
        "Um Zugriff auf dieses Modul zu erhalten müssen Sie am Vergabeverfahren teilnehmen.")
    assert not docfetch._TEILNAHME.search("Bitte melden Sie sich an Startseite Login")


def test_die_drei_ausgaenge_liegen_in_verschiedenen_klassen():
    """Der Unterschied ist nicht kosmetisch: `gated` wartet auf einen Zugang, `weg` ist
    endgültig, und `kein_zip` sagt ehrlich „ungeklärt"."""
    assert q.BLOCKIERT.get("gated") == "konto"
    assert "weg" in q.DAUERHAFT
    # Ungeklaertes gehoert in KEINE der Mengen — es soll nach der Sperrfrist wiederkommen.
    assert "kein_zip" not in q.DAUERHAFT
    assert "kein_zip" not in q.BLOCKIERT
    assert "kein_zip" not in q.KEIN_FEHLSCHLAG


def test_keine_pauschale_gated_einstufung_mehr():
    """⚠ Bis 2026-08-31 stand hier `gated` für JEDE Antwort ohne ZIP — der Kommentar nannte
    die Zweideutigkeit sogar („oder nicht (mehr) verfügbar") und entschied trotzdem für die
    blockierende Deutung."""
    quelle = docfetch.__file__
    with open(quelle, encoding="utf-8") as f:
        code = "\n".join(z for z in f if not z.lstrip().startswith("#"))
    i = code.index('"zip" not in ctype')
    block = code[i:i + 1400]
    assert '"weg"' in block and '"kein_zip"' in block and '"gated"' in block


def test_notiz_sagt_den_grund_nicht_den_inhaltstyp():
    """Die alte Notiz lautete „http 200, text/html;charset=iso-8859-1" — technisch wahr und
    für die Frage „warum kam nichts?" wertlos."""
    with open(docfetch.__file__, encoding="utf-8") as f:
        code = f.read()
    assert "Teilnahme am Verfahren nötig" in code
    assert "Vorgang nicht mehr auf dem Portal (404)" in code


# ───────────────────────── Das Muster muss auch in SQL treffen (seit 2026-09-13)

# Echte Adressen aus `lead_export`, die drei Bauformen, die cosinex kennt.
_ECHTE_URLS = (
    "https://www.dtvp.de/Satellite/notice/CXS0YHFDYD5DTW42",
    "https://vergabe.hilgmbh.de/VMPSatellite/notice/CXT6YYDYTV749DQ2/documents",
    "https://evergabe.blb.nrw.de/Vergabe/notice/CXS7YYXYTTTY2T2E",
    "https://ausschreibungen.giz.de/Satellite/notice/CXTRYY6DYDCW3WA2/documents",
)


def test_das_sql_muster_trifft_dieselben_adressen_wie_das_python_muster():
    """⚠ DER GROESSTE STILLE AUSFALL DIESES ABRUFERS, 22 Tage lang.

    Am 2026-08-22 kam das cosinex-Muster in die SQL-Abfrage von `fetch_batch` — direkt als
    Literal in einen f-String. Python liest `{2,20}` dort als Platzhalter:

        Quelltext:   '/[A-Za-z0-9_-]{2,20}/…/CX[A-Z0-9]{6,}'
        ausgefuehrt: '/[A-Za-z0-9_-](2, 20)/…/CX[A-Z0-9](6,)'

    Das Muster traf danach **null** Zeilen. Uebrig blieb der zweite Zweig
    (`meinauftrag.rib.de`, 718 Vorgaenge, alle laengst geholt) — der Abrufer meldete Runde
    fuer Runde „0 Vorgaenge" und sah dabei gesund aus.

    ⚠ Und die Kennzahl, die es haette zeigen muessen, kam aus einer ANDEREN Rechnung:
    `rueckstau.py` ordnet ueber `is_cosinex()` zu, also ueber das heile Python-Muster. Der
    Rueckstau stieg taeglich (2.007 → 2.227), waehrend der Abrufer nichts tat — zusammen
    las sich das wie „grosser Rueckstand, wird langsam abgearbeitet".

    Der Test faehrt das Muster deshalb **durch DuckDB**, nicht durch den Quelltext.
    """
    import duckdb

    from govisor import docfetch

    con = duckdb.connect()
    for url in _ECHTE_URLS:
        assert docfetch.is_cosinex(url), f"das Python-Muster verfehlt {url}"
        assert con.execute("SELECT regexp_matches(?, ?)",
                           [url, docfetch._SQL_COSINEX]).fetchone()[0], (
            f"das SQL-Muster verfehlt {url} — dann waehlt `fetch_batch` diese Vergaben "
            f"nicht aus, obwohl `rueckstau.py` sie als Rueckstand zaehlt. Genau so lief "
            f"cosinex 22 Tage leer.")


def test_beide_muster_decken_sich_auf_dem_echten_bestand():
    """Die schaerfere Fassung: nicht vier Adressen, sondern alle.

    ⚠ Vier feste Beispiele haetten den Ausfall zwar gefunden, aber sie altern — die naechste
    cosinex-Instanz benennt ihren Basispfad wieder anders (`Satellite`, `VMPSatellite`,
    `Vergabe`, `VMPCenter` sind schon vier). Gegen den ganzen Bestand gemessen faellt jede
    Abweichung auf, auch eine, an die niemand gedacht hat. Gemessen 2026-09-13: 3.663
    Adressen, beide Muster identisch.
    """
    import duckdb
    import pytest

    from govisor import docfetch

    L = (pathlib.Path(__file__).resolve().parent.parent
         / "data" / "gold" / "DE" / "lead_export.parquet")
    if not L.exists():
        pytest.skip("kein lead_export — frische Arbeitskopie")
    con = duckdb.connect()
    alle = [u for (u,) in con.execute(
        f"SELECT DISTINCT documents_url FROM read_parquet('{L.as_posix()}') "
        f"WHERE documents_url IS NOT NULL").fetchall()]
    py = {u for u in alle if docfetch.is_cosinex(u)}
    sql = {u for (u,) in con.execute(
        f"SELECT DISTINCT documents_url FROM read_parquet('{L.as_posix()}') "
        f"WHERE documents_url IS NOT NULL AND regexp_matches(documents_url, ?)",
        [docfetch._SQL_COSINEX]).fetchall()}
    assert py, "das Python-Muster trifft gar nichts mehr"
    assert py == sql, (
        f"Python und SQL waehlen Verschiedenes: nur Python {len(py - sql)}, "
        f"nur SQL {len(sql - py)}. Beispiel: {sorted(py ^ sql)[:1]}")


def test_das_muster_steht_nicht_als_literal_im_f_string():
    """Die Bauform ist die Ursache, nicht der Tippfehler: ein Regex mit `{n,m}` gehoert nie
    in einen f-String. Als Konstante interpoliert kann dasselbe nicht wieder passieren."""
    quelle = (pathlib.Path(__file__).resolve().parent.parent
              / "govisor" / "docfetch.py").read_text(encoding="utf-8")
    sql = quelle.split("rows = con.execute(")[1].split(").fetchall()")[0]
    assert "{_SQL_COSINEX}" in sql, "das Muster wird nicht mehr als Konstante eingesetzt"
    assert "CX[A-Z0-9]" not in sql, \
        "das Muster steht wieder als Literal in der Abfrage — dort frisst der f-String die "\
        "geschweiften Klammern"

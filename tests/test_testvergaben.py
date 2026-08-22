"""Testausschreibungen: Übungsvorgänge, die keine echte Vergabe sind.

Portale legen Vorgänge an, damit Bieter die elektronische Angebotsabgabe üben können, und
Behörden testen ihre Anbindung. Sie standen im Bestand wie jede echte Ausschreibung —
„TESTDL2025" der Bundesrechenzentrum GmbH sogar mit 524 Mio € Auftragswert, was die
Werte-Statistik der Startseite verzerrt hat.
"""
import pathlib

from govisor.testvergaben import ist_testvergabe, sql_bedingung

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_erkennt_die_uebungsvorgaenge():
    for titel in ("TESTDL2025", "TESTAUSSCHREIBUNG", "testausschreibung",
                  "Testvergabe für Bieter zur Übung der Angebotsabgabe",
                  "Testvergabe für die elektronische Angebotsabgabe (2025_Testvergabe)",
                  "Test / Schulungsverfahren für elektronische Angebotsabgabe: 10 Paletten",
                  "  TESTAUSSCHREIBUNG  ", "Dies ist eine Testausschreibung"):
        assert ist_testvergabe(titel), f"nicht erkannt: {titel!r}"


def test_laesst_echte_vergaben_in_ruhe():
    """⚠ DIE EIGENTLICHE GEFAHR. „test" ist im Vergabewesen ein normales Wort: gemessen am
    2026-08-22 tragen 203 von 43.642 Einträgen es im Titel. Ein Muster auf den Wortbestandteil
    würde 196 echte Vergaben mitreissen — Prüfmaschinen, Wafer-Tests, Testautomation.
    """
    for titel in ("Dienstleistungen TCK Testautomation",
                  "Eine Universalprüfmaschine für Zug- und Druckbelastungstests",
                  "Testcrowd-Anbieter für BVG eCommerce (ITD1-0275-2026)",
                  "Weiterentwicklung - eID Testbed",
                  "200 mm Wafer Prober incl. Temperature Testing (IIS-05.1)",
                  "SOC-Testsystem - PR1251693-2270-W",
                  "Lieferung von Corona-Schnelltests", "Materialtestung Beton"):
        assert not ist_testvergabe(titel), f"faelschlich erkannt: {titel!r}"
    assert not ist_testvergabe(None) and not ist_testvergabe("")


def test_dieselbe_regel_gilt_in_duckdb():
    """Python und SQL müssen dasselbe sagen — sonst markiert Gold etwas anderes, als der
    Export herausnimmt, und der Unterschied fällt niemandem auf."""
    import duckdb
    con = duckdb.connect()
    proben = ["TESTDL2025", "Testvergabe für Bieter", "Dienstleistungen TCK Testautomation",
              "SOC-Testsystem", "TESTAUSSCHREIBUNG", "eID Testbed"]
    con.execute("CREATE TEMP TABLE p(t VARCHAR)")
    con.executemany("INSERT INTO p VALUES (?)", [(x,) for x in proben])
    aus_sql = {t for (t,) in con.execute(f"SELECT t FROM p WHERE {sql_bedingung('t')}").fetchall()}
    aus_py = {t for t in proben if ist_testvergabe(t)}
    assert aus_sql == aus_py, f"SQL {aus_sql} != Python {aus_py}"


def test_beide_exporte_und_gold_nutzen_die_regel():
    """Eine Marke, drei Verwender — und keiner davon mit eigener Kopie des Musters."""
    gold = (ROOT / "govisor" / "gold.py").read_text(encoding="utf-8")
    assert "'testvergabe'" in gold and "_testvergabe_sql" in gold, \
        "Gold markiert Übungsvorgänge nicht mehr"
    for skript in ("export_web_leads.py", "export_web_awards.py"):
        text = (ROOT / "scripts" / skript).read_text(encoding="utf-8")
        assert "_testvergabe_sql" in text, f"{skript} nimmt Übungsvorgänge nicht heraus"

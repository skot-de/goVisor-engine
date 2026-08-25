"""Werte-Normalisierung — aus Zeichenketten wird etwas, mit dem man filtern kann."""
from govisor import normwerte as nw


def test_deutsche_tausendertrennung_wird_nicht_zum_dezimalpunkt():
    """⚠ Der teuerste Einzelfehler in dieser Datei waere `3.000.000` → 3,0.

    Aus einer Haftpflicht ueber drei Millionen wuerde eine ueber drei Euro, und ein
    Filter „Haftpflicht bis 3 Mio" liesse plötzlich alles durch.
    """
    assert nw.zahl("3.000.000") == 3_000_000
    assert nw.zahl("3.000") == 3_000
    assert nw.zahl("1.250.000,50") == 1_250_000.50
    # Ein Punkt mit ein bis zwei Ziffern dahinter ist dagegen ein Dezimalpunkt.
    assert nw.zahl("3.00") == 3.0
    assert nw.zahl("1,5") == 1.5


def test_vielfache_wie_sie_in_unterlagen_stehen():
    assert nw.zahl("1,5 Mio") == 1_500_000
    assert nw.zahl("3 Millionen") == 3_000_000
    assert nw.zahl("500 TEUR") == 500_000
    assert nw.zahl("keine Angabe") is None
    assert nw.zahl(None) is None
    assert nw.zahl(True) is None          # bool ist kein Betrag


def test_datum_nur_wenn_es_eines_ist():
    assert nw.datum("16.07.2026") == "2026-07-16"
    assert nw.datum("2026-08-13 11:00") == "2026-08-13"
    assert nw.datum("31.02.2026") is None, "der 31. Februar ist kein Datum"
    assert nw.datum("4") is None, "eine Dauer ist kein Datum"


def test_aus_einem_datum_wird_keine_zahl():
    """⚠ `2026-08-13 11:00` ergab in der ersten Fassung die Zahl 2026, `31.02.2026`
    die Zahl 31,02. Ein Feld, das wie ein Datum aussieht, gibt keinen Betrag her."""
    assert "wert_num" not in nw.normalisiere({"value": "2026-08-13 11:00", "unit": None})
    assert "wert_num" not in nw.normalisiere({"value": "31.02.2026", "unit": None})
    assert nw.normalisiere({"value": "16.07.2026"})["wert_datum"] == "2026-07-16"


def test_die_zahl_steht_mal_im_wert_mal_in_der_einheit():
    """`zuschlagskriterium` traegt den Namen im Wert und die Gewichtung in der Einheit —
    zu 76 % im Bestand gemessen."""
    r = nw.normalisiere({"value": "Entgelte ohne Kraftstoff", "unit": "75 %"})
    assert r["wert_num"] == 75.0 and r["wert_einheit"] == "%"
    r = nw.normalisiere({"value": "3000000", "unit": "EUR"})
    assert r["wert_num"] == 3_000_000 and r["wert_einheit"] == "EUR"


def test_dauern_werden_in_tage_umgerechnet():
    assert nw.normalisiere({"value": "4", "unit": "Wochen"})["wert_tage"] == 28
    assert nw.normalisiere({"value": "24", "unit": "Monate"})["wert_tage"] == 720
    # Ein Datum ist keine Dauer — dann gibt es keine Tageszahl.
    assert "wert_tage" not in nw.normalisiere({"value": "16.07.2026", "unit": "Tage"})


def test_nichts_wird_ueberschrieben():
    """Die Rohwerte tragen die Belegpflicht (§6a.2) — ein normalisierter Wert ist eine
    Auslegung, kein Zitat."""
    item = {"value": "600000", "unit": "EUR", "quote": "… mindestens 600.000 EUR …"}
    kopie = dict(item)
    nw.normalisiere(item)
    assert item == kopie, "normalisiere() darf den Eintrag nicht veraendern"


def test_unauslegbares_bleibt_leer_statt_zu_raten():
    assert nw.normalisiere({"value": "nach Absprache", "unit": None}) == {}
    assert nw.normalisiere({"value": None, "unit": None}) == {}


def test_beide_wege_sind_verdrahtet():
    """Neue Auswertungen ueber `docextract`, der Bestand ueber den Export — sonst
    braeuchte man einen Modelllauf, um an eine Zahl zu kommen, die schon dasteht."""
    import pathlib

    w = pathlib.Path(__file__).resolve().parent.parent
    assert "normwerte.normalisiere" in (w / "govisor" / "docextract.py").read_text(encoding="utf-8")
    assert "normwerte.normalisiere" in (w / "scripts" / "export_doc_analysis.py").read_text(encoding="utf-8")

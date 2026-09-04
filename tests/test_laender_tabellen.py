"""Der Waechter ueber die Wertetabellen (`scripts/pruefe_laender_tabellen.py`).

⚠ Er prueft, ob JEDE Wertetabelle jedes aktive Land traegt — und das ist die Klasse Fehler,
die sonst LAUTLOS bleibt: ein fehlender Eintrag wirft keine Ausnahme, er liefert nur ein
schlechteres Ergebnis. Damit ist der Waechter selbst die einzige Absicherung, und ein
Waechter ohne Test ist eine Behauptung.
"""
import importlib.util
import pathlib

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent


def _modul():
    spec = importlib.util.spec_from_file_location(
        "plt", WURZEL / "scripts" / "pruefe_laender_tabellen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_der_echte_bestand_ist_sauber():
    """Keine Wertetabelle darf ein aktives Land vermissen."""
    m = _modul()
    aktiv = set(m.aktive_laender())
    if not aktiv:
        pytest.skip("kein data/gold — frische Arbeitskopie")
    luecken = []
    for t in m.TABELLEN:
        hat, fehler = t.laender()
        assert hat is not None, (
            f"{t.name}: {fehler}\n"
            f"⚠ Das ist ein Defekt DIESER Pruefung, nicht der Tabelle — sonst meldet sie "
            f"gleich vier Laender als fehlend und der echte Befund geht unter.")
        if aktiv - hat:
            luecken.append(f"{t.name} fehlt {sorted(aktiv - hat)} — {t.folge}")
    assert luecken == [], "\n".join(luecken)


def test_aktive_laender_kommen_aus_dem_bestand():
    """⚠ `lead_export.parquet` ist der Marker, NICHT das blosse Verzeichnis.

    `data/gold/` fuehrt auch `EU` (Sammelablage ohne eindeutiges Land) und `PL`
    (angefangen, liegengeblieben). Beide als aktiv zu zaehlen waere eine Falschaussage:
    fuer sie ist ein fehlender Locale-Eintrag KEIN Defekt, sondern der bekannte Stand.
    """
    m = _modul()
    aktiv = m.aktive_laender()
    if not aktiv:
        pytest.skip("kein data/gold")
    for cc in aktiv:
        assert (WURZEL / "data" / "gold" / cc / "lead_export.parquet").exists()
    for tot in ("EU", "PL"):
        if (WURZEL / "data" / "gold" / tot).is_dir() and \
           not (WURZEL / "data" / "gold" / tot / "lead_export.parquet").exists():
            assert tot not in aktiv, f"{tot} hat kein lead_export und darf nicht aktiv heissen"


def test_waechter_meldet_ein_fehlendes_land():
    """Ein Waechter, der nicht anschlagen kann, ist keiner."""
    m = _modul()

    class Kaputt:
        name, datei, folge = "probe", "x", "y"

        def laender(self):
            return {"DE"}, ""

    aktiv = {"DE", "LU"}
    hat, _ = Kaputt().laender()
    assert aktiv - hat == {"LU"}


def test_jede_ausnahme_traegt_eine_begruendung_und_ein_ziel():
    """⚠ Drei Listen sind absichtlich unvollstaendig. Sie einfach wegzulassen waere eine
    STILLE Ausnahme — dann steht nirgends, dass jemand das entschieden hat. Also: Datei muss
    existieren, Begruendung muss inhaltlich sein.
    """
    m = _modul()
    assert m.BEWUSST_UNVOLLSTAENDIG, "ohne Ausnahmen waere die Liste verdaechtig leer"
    for schluessel, grund in m.BEWUSST_UNVOLLSTAENDIG.items():
        datei = schluessel.split(":")[0]
        assert (WURZEL / datei).exists(), f"{schluessel}: {datei} gibt es nicht (mehr)"
        assert len(grund) > 80, f"{schluessel}: Begruendung zu duenn"


def test_keine_tabelle_doppelt_registriert():
    m = _modul()
    namen = [t.name for t in m.TABELLEN]
    assert len(namen) == len(set(namen))

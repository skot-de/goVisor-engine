"""Haelt `scripts/pruefe_verdrahtung.py` und seine Ausnahmelisten ehrlich.

Zwei Sorten Test, und die zweite ist die wichtigere:

1. **Die Sonden schlagen wirklich an.** Eine Pruefung, die man nur gegen die echte
   Datenlage laufen lassen kann, ist unbewiesen — und eine unbewiesene Pruefung ist
   genau das Problem, das sie loesen soll. Deshalb bauen die Tests eine kuenstliche
   Gold-Ebene und pruefen beide Richtungen: schlaegt an / bleibt still.

2. **Die Ausnahmelisten verrotten nicht.** Eine Ausnahme ohne Begruendung, eine
   Ausnahme fuer etwas, das es nicht mehr gibt, oder ein `OFFEN`-Eintrag, der laengst
   erledigt ist — alles drei laesst die Suite rot werden. Ohne das waechst so eine
   Liste stillschweigend, bis sie alles enthaelt.
"""
import importlib.util
import os
import pathlib
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "pruefe_verdrahtung", ROOT / "scripts" / "pruefe_verdrahtung.py")
pv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pv)

TAG = 86400


def _gold(tmp_path, dateien: dict[str, dict[str, float]]) -> pathlib.Path:
    """Kuenstliche Gold-Ebene: {land: {tabelle: alter_in_tagen}}.

    Die Dateien sind leer — die Sonden lesen nur `mtime`, kein Parquet.
    """
    jetzt = time.time()
    wurzel = tmp_path / "gold"
    for land, tabellen in dateien.items():
        (wurzel / land).mkdir(parents=True, exist_ok=True)
        for name, alter in tabellen.items():
            p = wurzel / land / f"{name}.parquet"
            p.write_bytes(b"")
            os.utime(p, (jetzt - alter * TAG, jetzt - alter * TAG))
    return wurzel


# ── Sonde 1 schlaegt an ─────────────────────────────────────────────────────

def test_frische_findet_die_stehengebliebene_datei(tmp_path):
    """Der Fall lead_lot/lead_text: alles taeglich, einer haengt zehn Tage zurueck."""
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "lead_lot": 10}})
    fehler = pv.sonde_frische(wurzel=w)
    assert len(fehler) == 1 and "lead_lot" in fehler[0]


def test_frische_schweigt_bei_taeglichem_bestand(tmp_path):
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "lead_lot": 0.5}})
    assert pv.sonde_frische(wurzel=w) == []


def test_frische_akzeptiert_eine_begruendete_ausnahme(tmp_path):
    """`succession_llm_edges` laeuft von Hand — 25 Tage sind dort kein Befund."""
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "succession_llm_edges": 25}})
    assert pv.sonde_frische(wurzel=w) == []


def test_frische_findet_ein_ganz_stehengebliebenes_land(tmp_path):
    """Ohne diese Pruefung wandert der Bezugspunkt mit: baut AT gar nichts mehr,
    ist AT trotzdem in sich konsistent und faellt nicht auf."""
    w = _gold(tmp_path, {"DE": {"lead_export": 0}, "AT": {"lead_export": 9, "lead_lot": 9}})
    fehler = pv.sonde_frische(wurzel=w)
    assert any("Land AT" in f for f in fehler)


# ── Sonde 2 schlaegt an ─────────────────────────────────────────────────────

def test_paritaet_findet_die_unbekannte_nur_de_tabelle(tmp_path):
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "irgendwas_neues": 0},
                         "AT": {"lead_export": 0}, "CH": {"lead_export": 0}})
    fehler = pv.sonde_paritaet(wurzel=w)
    assert len(fehler) == 1 and "irgendwas_neues" in fehler[0]


def test_paritaet_schweigt_bei_begruendeter_luecke(tmp_path):
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "doe_demand": 0},
                         "AT": {"lead_export": 0}, "CH": {"lead_export": 0}})
    assert pv.sonde_paritaet(wurzel=w) == []


def test_paritaet_meldet_bekannte_luecken_nicht_als_fehler(tmp_path):
    """`OFFEN` ist eine Arbeitsliste, kein Fehlschlag — sonst waere die Suite
    dauerhaft rot und niemand schaut mehr hin."""
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "lead_criteria": 0},
                         "AT": {"lead_export": 0}, "CH": {"lead_export": 0}})
    assert pv.sonde_paritaet(wurzel=w) == []


# ── Die Listen verrotten nicht ──────────────────────────────────────────────

ALLE_LISTEN = {
    "AUSNAHMEN_FRISCHE": pv.AUSNAHMEN_FRISCHE,
    "LEICHEN": pv.LEICHEN,
    "BEWUSST_NUR_DE": pv.BEWUSST_NUR_DE,
    "OFFEN_NUR_DE": pv.OFFEN_NUR_DE,
}


@pytest.mark.parametrize("name", sorted(ALLE_LISTEN))
def test_jeder_eintrag_hat_eine_begruendung(name):
    """Ohne Grund ist es keine Ausnahme, sondern ein Persilschein."""
    for tabelle, grund in ALLE_LISTEN[name].items():
        assert grund and len(grund) > 15, f"{name}[{tabelle}] ist nicht begruendet"


def test_keine_tabelle_steht_in_zwei_widerspruechlichen_listen():
    """`BEWUSST_NUR_DE` und `OFFEN_NUR_DE` schliessen sich aus: entweder eine
    Entscheidung oder eine Baustelle, nicht beides."""
    doppelt = set(pv.BEWUSST_NUR_DE) & set(pv.OFFEN_NUR_DE)
    assert not doppelt, f"widerspruechlich eingeordnet: {sorted(doppelt)}"


def _gold_da() -> bool:
    return (ROOT / "data" / "gold").is_dir() and any(
        (ROOT / "data" / "gold").glob("*/*.parquet"))


@pytest.mark.skipif(not _gold_da(), reason="keine Gold-Ebene (frische CI ohne Ingest)")
def test_kein_offen_eintrag_ist_laengst_erledigt():
    """Wer eine Tabelle fuer AT/CH verdrahtet, muss die Zeile streichen.

    Ohne diesen Test bleibt der Eintrag stehen und die Sonde schweigt kuenftig
    auch dann, wenn die Tabelle wieder ausfaellt.
    """
    import collections
    da = collections.defaultdict(set)
    for p in (ROOT / "data" / "gold").glob("*/*.parquet"):
        da[p.stem].add(p.parent.name)
    erledigt = [t for t in pv.OFFEN_NUR_DE if {"AT", "CH"} <= da.get(t, set())]
    assert not erledigt, (
        f"steht noch als offene Luecke, ist aber gebaut: {sorted(erledigt)} — "
        f"Zeile aus OFFEN_NUR_DE streichen")


@pytest.mark.skipif(not _gold_da(), reason="keine Gold-Ebene (frische CI ohne Ingest)")
@pytest.mark.parametrize("name", sorted(ALLE_LISTEN))
def test_keine_ausnahme_fuer_etwas_das_es_nicht_mehr_gibt(name):
    """Eine Ausnahme fuer eine geloeschte Tabelle ist toter Ballast — und sie
    verdeckt, dass die Liste seit Jahren niemand gelesen hat."""
    vorhanden = {p.stem for p in (ROOT / "data" / "gold").glob("*/*.parquet")}
    tot = [t for t in ALLE_LISTEN[name] if t not in vorhanden]
    assert not tot, f"{name} nennt Tabellen, die es nicht mehr gibt: {sorted(tot)}"


@pytest.mark.skipif(not _gold_da(), reason="keine Gold-Ebene (frische CI ohne Ingest)")
def test_die_echte_datenlage_ist_sauber():
    """Der eigentliche Waechter: neue Verdrahtungsfehler lassen ab sofort die
    Suite fallen, nicht erst den Zufall."""
    assert pv.sonde_frische() == []
    assert pv.sonde_paritaet() == []


def test_die_sonde_laeuft_im_nachtlauf_mit():
    """Eine Verdrahtungspruefung, die selbst nicht verdrahtet ist, waere die
    Pointe des ganzen Vorhabens."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text()
    ohne_kommentar = "\n".join(z for z in lauf.splitlines() if not z.lstrip().startswith("#"))
    assert "scripts/pruefe_verdrahtung.py" in ohne_kommentar

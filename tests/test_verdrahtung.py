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


def test_paritaet_meldet_bekannte_luecken_nicht_als_fehler(tmp_path, monkeypatch):
    """`OFFEN` ist eine Arbeitsliste, kein Fehlschlag — sonst waere die Suite
    dauerhaft rot und niemand schaut mehr hin.

    Der Eintrag wird hier GESETZT statt aus der echten Liste geliehen: sobald
    jemand die geliehene Zeile streicht (weil er die Tabelle verdrahtet hat),
    faellt sonst dieser Test — und zwar mit einer Meldung, die vom Falschen
    handelt. Genau das ist beim Leeren der Liste am 2026-08-23 passiert.
    """
    monkeypatch.setitem(pv.OFFEN_NUR_DE, "beispiel_luecke",
                        "nur fuer den Test gesetzt, steht fuer eine bekannte Baustelle")
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "beispiel_luecke": 0},
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


# ── Sonde 3: DE-feste Pfade ─────────────────────────────────────────────────
# Sonde 1 und 2 sehen die Gold-Ebene. Die Haelfte aller Funde sass aber im
# VERBRAUCHER: Tabelle sauber je Land gebaut, Exporter liest nur DE.

def test_pfade_findet_das_de_feste_skript(tmp_path, monkeypatch):
    lauf = tmp_path / "daily_leads.sh"
    lauf.write_text("$PY scripts/beispiel_export.py\n")
    skripte = tmp_path / "scripts"
    skripte.mkdir()
    (skripte / "beispiel_export.py").write_text('G = "data/gold/DE"\n')
    monkeypatch.setattr(pv, "NACHTLAUF", lauf)
    monkeypatch.setattr(pv, "ROOT", tmp_path)
    fehler = pv.sonde_pfade()
    assert len(fehler) == 1 and "beispiel_export.py" in fehler[0]


def test_pfade_zaehlt_docstrings_und_kommentare_nicht_mit(tmp_path, monkeypatch):
    """Der erste Versuch meldete drei Fehlalarme — einen Docstring, der ERKLAERT,
    warum dort nicht gelesen wird, und die Begruendungstexte der Sonde selbst.
    Wer Prosa mitzaehlt, zwingt dazu, die Begruendung zu loeschen."""
    lauf = tmp_path / "daily_leads.sh"
    lauf.write_text("$PY scripts/nur_prosa.py\n")
    skripte = tmp_path / "scripts"
    skripte.mkdir()
    (skripte / "nur_prosa.py").write_text(
        '"""Hier wird bewusst NICHT data/gold/DE gelesen."""\n'
        "# auch data/silver/DE im Kommentar zaehlt nicht\n"
        "x = 1\n")
    monkeypatch.setattr(pv, "NACHTLAUF", lauf)
    monkeypatch.setattr(pv, "ROOT", tmp_path)
    assert pv.sonde_pfade() == []


def test_sonde_1_sieht_auch_die_frontend_daten(tmp_path, monkeypatch):
    """`firma-profiles.json` war 23 Tage alt und von keiner Sonde gedeckt."""
    gold = _gold(tmp_path, {"DE": {"lead_export": 0}})
    web = tmp_path / "web" / "data"
    web.mkdir(parents=True)
    jetzt = time.time()
    for name, alter in (("frisch.json", 0), ("vergessen.json", 20)):
        f = web / name
        f.write_text("{}")
        os.utime(f, (jetzt - alter * TAG, jetzt - alter * TAG))
    monkeypatch.setattr(pv, "WEB", web)
    fehler = pv.sonde_frische(wurzel=gold)
    assert any("vergessen.json" in f for f in fehler)


def test_skript_listen_haben_begruendungen():
    for name, liste in (("BEWUSST_NUR_DE_SKRIPTE", pv.BEWUSST_NUR_DE_SKRIPTE),
                        ("OFFEN_NUR_DE_SKRIPTE", pv.OFFEN_NUR_DE_SKRIPTE),
                        ("AUSNAHMEN_WEB", pv.AUSNAHMEN_WEB)):
        for schluessel, grund in liste.items():
            assert grund and len(grund) > 25, f"{name}[{schluessel}] ist nicht begruendet"


def test_pfade_erlaubt_die_union_basis(tmp_path, monkeypatch):
    """`G = "data/gold/DE"` ist in einem Skript mit `_union` die BASIS, der die
    uebrigen Laender angehaengt werden — kein Befund. Zwei Nennungen schon."""
    lauf = tmp_path / "daily_leads.sh"
    lauf.write_text("$PY scripts/mit_union.py\n$PY scripts/zwei_mal.py\n")
    skripte = tmp_path / "scripts"
    skripte.mkdir()
    (skripte / "mit_union.py").write_text(
        'G = "data/gold/DE"\n'
        "def _union(t):\n    return G + t\n")
    (skripte / "zwei_mal.py").write_text(
        'G = "data/gold/DE"\n'
        'X = "data/silver/DE/notices"\n'
        "def _union(t):\n    return G + t\n")
    monkeypatch.setattr(pv, "NACHTLAUF", lauf)
    monkeypatch.setattr(pv, "ROOT", tmp_path)
    fehler = pv.sonde_pfade()
    assert len(fehler) == 1 and "zwei_mal.py" in fehler[0]


def test_die_drei_produktwege_laufen_im_nachtlauf_mit():
    """Onboarding-Index, Zuschlagsphase und Firmenprofile. Zwei davon standen bis
    2026-08-23 in KEINEM Lauf und schrieben trotzdem nach web/data."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text()
    ohne_kommentar = "\n".join(z for z in lauf.splitlines() if not z.lstrip().startswith("#"))
    for skript in ("export_suppliers.py", "export_web_awards.py", "export_firma_profiles.py"):
        assert skript in ohne_kommentar, f"{skript} laeuft nicht im Nachtlauf"


# ── Sonde 4: halb aufgenommene Laender ──────────────────────────────────────
# Die Fehlerklasse dieses Skripts auf der obersten Ebene: 326.485 polnische
# Bekanntmachungen lagen in Silber, seit zwei Monaten ohne Gold, und KEINE
# Sonde meldete es — Sonde 1 und 2 sehen nur, was in `data/gold` steht.

def test_laender_findet_silber_ohne_gold(tmp_path, monkeypatch):
    silber = tmp_path / "silver" / "XX" / "notices" / "year=2026"
    silber.mkdir(parents=True)
    (silber / "a.parquet").write_bytes(b"")
    monkeypatch.setattr(pv, "SILBER", tmp_path / "silver")
    monkeypatch.setattr(pv, "GOLD", tmp_path / "gold")
    fehler = pv.sonde_laender()
    assert len(fehler) == 1 and "XX" in fehler[0]


def test_laender_schweigt_bei_begruendetem_land(tmp_path, monkeypatch):
    silber = tmp_path / "silver" / "EU" / "notices" / "year=2026"
    silber.mkdir(parents=True)
    (silber / "a.parquet").write_bytes(b"")
    monkeypatch.setattr(pv, "SILBER", tmp_path / "silver")
    monkeypatch.setattr(pv, "GOLD", tmp_path / "gold")
    assert pv.sonde_laender() == []


def test_laender_schweigt_wenn_gold_da_ist(tmp_path, monkeypatch):
    silber = tmp_path / "silver" / "XX" / "notices" / "year=2026"
    silber.mkdir(parents=True)
    (silber / "a.parquet").write_bytes(b"")
    (tmp_path / "gold" / "XX").mkdir(parents=True)
    monkeypatch.setattr(pv, "SILBER", tmp_path / "silver")
    monkeypatch.setattr(pv, "GOLD", tmp_path / "gold")
    assert pv.sonde_laender() == []


def test_bewusst_ohne_gold_ist_begruendet():
    for land, grund in pv.BEWUSST_OHNE_GOLD.items():
        assert grund and len(grund) > 25, f"BEWUSST_OHNE_GOLD[{land}] ist nicht begruendet"


# ── Verdrahtungskarte ───────────────────────────────────────────────────────
# Die Bibel nennt die REGELN. Was ihr fehlte, ist die KARTE: welche Tabelle kommt
# aus welchem Builder, und wer haengt daran. Sie wird ERZEUGT, nicht getippt —
# eine getippte Karte verrottet mit dem ersten Umbau.

def _karte():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "verdrahtungskarte", ROOT / "scripts" / "verdrahtungskarte.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_karte_findet_erzeuger_und_verbraucher():
    """Drei Tabellen, an denen diese Sitzung Fehler hatte — jede muss beide Seiten
    zeigen, sonst haette die Karte den Fund nicht geliefert."""
    k = _karte().karte()
    for tabelle, builder in (("lead_lot", "build_lead_lot"),
                             ("lead_text", "build_lead_text"),
                             ("buyer_stats", "build_market_intelligence")):
        assert tabelle in k, f"{tabelle} fehlt in der Karte"
        assert builder in k[tabelle]["erzeuger"], \
            f"{tabelle}: {builder} nicht als Erzeuger erkannt"
        assert k[tabelle]["verbraucher"], f"{tabelle} hat keinen Verbraucher"


def test_karte_haelt_erzeuger_und_leser_auseinander():
    """In `COPY (… JOIN read_parquet('a') …) TO 'b'` stehen beide in EINER Anweisung.
    Wer die ganze Anweisung durchsucht, macht jede gelesene Tabelle zum Erzeuger —
    gemessen bekam `dim_cpv_label` so fuenf angebliche Erzeuger statt einem."""
    k = _karte().karte()
    assert k["dim_cpv_label"]["erzeuger"] == {"build_dim_cpv_label"}


def test_karte_sieht_die_union_leser():
    """Der wichtigste Leser nennt die Endung gar nicht: `_union("lead_lot")` baut den
    Dateinamen zur Laufzeit. Ohne diesen Zweig waeren genau die laenderfaehigen
    Verbraucher unsichtbar — also die, um die es geht."""
    k = _karte().karte()
    assert "scripts/export_web_leads.py" in k["lead_lot"]["verbraucher"]

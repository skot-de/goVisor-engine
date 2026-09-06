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


def _leeres_web(tmp_path):
    """Ein leeres `web/data` fuer die Gold-Tests.

    ⚠ Ohne das scannt `sonde_frische` zusaetzlich das ECHTE `web/data` — und dann haengt
    ein synthetischer Test an der Datenlage der Maschine. Am 2026-08-29 wurden drei Tests
    rot, weil die Dokumentanalyse seit vier Tagen stillstand: der Befund stimmte, die
    Tests hatten damit nur nichts zu tun.
    """
    d = tmp_path / "leeres-web"
    d.mkdir(exist_ok=True)
    return d


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
    fehler = pv.sonde_frische(wurzel=w, web_wurzel=_leeres_web(tmp_path))
    assert len(fehler) == 1 and "lead_lot" in fehler[0]


def test_frische_schweigt_bei_taeglichem_bestand(tmp_path):
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "lead_lot": 0.5}})
    assert pv.sonde_frische(wurzel=w, web_wurzel=_leeres_web(tmp_path)) == []


def test_frische_akzeptiert_eine_begruendete_ausnahme(tmp_path):
    """`succession_llm_edges` laeuft von Hand — 25 Tage sind dort kein Befund."""
    w = _gold(tmp_path, {"DE": {"lead_export": 0, "succession_llm_edges": 25}})
    assert pv.sonde_frische(wurzel=w, web_wurzel=_leeres_web(tmp_path)) == []


def test_frische_findet_ein_ganz_stehengebliebenes_land(tmp_path):
    """Ohne diese Pruefung wandert der Bezugspunkt mit: baut AT gar nichts mehr,
    ist AT trotzdem in sich konsistent und faellt nicht auf."""
    w = _gold(tmp_path, {"DE": {"lead_export": 0}, "AT": {"lead_export": 9, "lead_lot": 9}})
    fehler = pv.sonde_frische(wurzel=w, web_wurzel=_leeres_web(tmp_path))
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
    verdeckt, dass die Liste seit Jahren niemand gelesen hat.

    ⚠ ZWEI SCHLUESSELFORMEN seit dem 2026-09-06. Eine Ausnahme galt bisher fuer ALLE
    Laender (`bronze_inventory`) — damit haette eine Ausnahme fuer LU auch den taeglich
    gebauten DE-Rueckstand entschuldigt. Die Form `LAND/tabelle` grenzt sie ein. Dieser Test
    muss beide kennen, sonst meldet er die praezisere Ausnahme als tot.
    """
    gold = ROOT / "data" / "gold"
    vorhanden = {p.stem for p in gold.glob("*/*.parquet")}
    vorhanden |= {f"{p.parent.name}/{p.stem}" for p in gold.glob("*/*.parquet")}
    tot = [t for t in ALLE_LISTEN[name] if t not in vorhanden]
    assert not tot, f"{name} nennt Tabellen, die es nicht mehr gibt: {sorted(tot)}"


@pytest.mark.skipif(not _gold_da(), reason="keine Gold-Ebene (frische CI ohne Ingest)")
def _pv():
    """Das Pruefskript als Modul. Es liegt in `scripts/`, nicht im Paket."""
    import importlib.util
    import pathlib as _p
    pfad = _p.Path(__file__).resolve().parent.parent / "scripts" / "pruefe_verdrahtung.py"
    spec = importlib.util.spec_from_file_location("pv", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_die_sonde_kennt_ihre_laender_nicht_auswendig(tmp_path):
    """⚠ Die Fehlerklasse dieses Skripts, eine Ebene hoeher: im Pruefwerkzeug selbst.

    Bis zum 2026-09-02 stand `LAENDER = ("DE","AT","CH")` fest. Ein viertes Land haette die
    Sonde damit stillschweigend ausgehebelt — seine Tabellen waeren in keiner Pruefung
    vorgekommen, weil das Land nicht in der Liste stand. Genau so ist Polen zwei Monate lang
    mit 326.485 Bekanntmachungen in Silber gelegen, ohne dass eine Sonde etwas meldete.
    """
    for land in ("DE", "AT", "PL"):
        (tmp_path / land).mkdir()
        (tmp_path / land / "leads.parquet").write_bytes(b"x")
    # ⚠ NACHGESCHAERFT AM 2026-09-02. Bis dahin galt: jedes Land mit Gold zaehlt mit. Dann
    # schrieb `build_vorgaenge.py` als erster laenderagnostischer Schritt auch fuer PL und EU
    # — beide dokumentierte Baustellen — und die Paritaetspruefung meldete 40 bestehende
    # Tabellen als Luecke. Die Regel lautet jetzt: ein Land mit Gold zaehlt mit, ES SEI DENN
    # es steht als Baustelle in `BEWUSST_OHNE_GOLD`. Der Kern bleibt: KEINE fest eingetippte
    # Laenderliste — faellt der Eintrag, zaehlt das Land ab dem naechsten Lauf voll mit.
    pv = _pv()
    assert pv._laender(tmp_path) == ("AT", "DE"), "die Baustelle PL zaehlt weiter mit"
    assert "PL" in pv.BEWUSST_OHNE_GOLD, "PL muesste als Baustelle eingetragen sein"
    ohne_pl = {k: v for k, v in pv.BEWUSST_OHNE_GOLD.items() if k != "PL"}
    alt_liste, pv.BEWUSST_OHNE_GOLD = pv.BEWUSST_OHNE_GOLD, ohne_pl
    try:
        assert pv._laender(tmp_path) == ("AT", "DE", "PL"), \
            "ohne Baustellen-Eintrag muss Polen sofort mitzaehlen — sonst steht die Liste doch im Code"
    finally:
        pv.BEWUSST_OHNE_GOLD = alt_liste


def test_eine_tabelle_ohne_DE_faellt_nicht_durch(tmp_path):
    """⚠ Frueher stand in der Bedingung `"DE" not in laender: continue`. Eine Tabelle, die es
    in AT und CH gibt und in DE nicht, galt damit als „kein Paritaetsfall" und fiel durch —
    obwohl das genauso eine Luecke ist."""
    for land in ("DE", "AT", "PL"):
        (tmp_path / land).mkdir()
        (tmp_path / land / "leads.parquet").write_bytes(b"x")
    (tmp_path / "PL" / "nur_polen.parquet").write_bytes(b"x")
    befunde = _pv().sonde_paritaet(wurzel=tmp_path)
    assert any("nur_polen" in b for b in befunde), "eine Tabelle ohne DE wird uebersehen"
    # ⚠ Und die Meldung sagt, WO sie liegt. „gibt es nur in DE" waere hier schlicht falsch
    # gewesen und haette jeden an den falschen Ort geschickt.
    assert any("gibt es in PL" in b for b in befunde)


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


def test_sonde_1_sieht_auch_die_frontend_daten(tmp_path):
    """`firma-profiles.json` war 23 Tage alt und von keiner Sonde gedeckt."""
    gold = _gold(tmp_path, {"DE": {"lead_export": 0}})
    web = tmp_path / "web" / "data"
    web.mkdir(parents=True)
    jetzt = time.time()
    for name, alter in (("frisch.json", 0), ("vergessen.json", 20)):
        f = web / name
        f.write_text("{}")
        os.utime(f, (jetzt - alter * TAG, jetzt - alter * TAG))
    fehler = pv.sonde_frische(wurzel=gold, web_wurzel=web)
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


# ── Bibel-Pruefung ──────────────────────────────────────────────────────────
# Eine Anleitung faellt nicht um, sie wird nur langsam falsch. Was dagegen hilft,
# sind Pruefungen die LAUT scheitern — nicht Vorsaetze.

def _bibel():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pruefe_bibel", ROOT / "scripts" / "pruefe_bibel.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_bibel_behauptungen_stimmen_noch():
    """Das Behauptungs-Register gegen die LIVE-Daten. Faellt eine Zeile, weiss man
    sofort, welches Kapitel ab sofort luegt."""
    assert _bibel().pruefung_behauptungen() == []


def test_bibel_zahlen_tragen_ein_datum():
    """Eine Messung ohne Datum liest sich als Gegenwart und ist morgen falsch —
    gemessen drifteten sechs undatierte Zahlen binnen Stunden."""
    assert _bibel().pruefung_datierung() == []


def test_bibel_und_claude_md_pflegen_keine_zahl_doppelt():
    """CLAUDE.md fasst die Bibel zusammen. Wer dieselbe Zahl an zwei Stellen fuehrt,
    pflegt sie an einer nicht — genau so stand dort „16 Tabellen nur fuer DE",
    Stunden nachdem sie verdrahtet waren."""
    assert _bibel().pruefung_doppelpflege() == []


def test_bibel_pruefung_laeuft_im_nachtlauf_mit():
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text()
    ohne_kommentar = "\n".join(z for z in lauf.splitlines() if not z.lstrip().startswith("#"))
    assert "scripts/pruefe_bibel.py" in ohne_kommentar


def test_nachlauf_eskaliert_nach_der_frist(monkeypatch):
    """Eine Warnung ohne Frist ist folgenlos — man kann sie beliebig lange
    ignorieren, und genau das passiert mit jeder Meldung, die nie eskaliert.
    Unter der Frist ein Anstoss, darueber ein Fehlschlag."""
    b = _bibel()
    monkeypatch.setattr(b, "NACHLAUF_FRIST_TAGE", 10_000)
    assert b.pruefung_nachlauf() == [], "so lange darf nichts eskalieren"
    monkeypatch.setattr(b, "NACHLAUF_FRIST_TAGE", -1)
    assert b.pruefung_nachlauf(), "jenseits der Frist MUSS es fehlschlagen"


def test_claude_md_kennt_beide_pruefungen():
    """Was eine neue Sitzung beim Start liest, entscheidet, was sie benutzt.

    ⚠ `pruefe_bibel.py` war gebaut, im Nachtlauf verankert und in zwei Kapiteln
    beschrieben — und stand trotzdem NICHT in CLAUDE.md. Dieselbe Fehlerklasse wie
    „gebaut, aber nicht verdrahtet", eine Ebene weiter aussen: das Werkzeug lief,
    aber niemand wusste davon.
    """
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for werkzeug in ("scripts/pruefe_verdrahtung.py", "scripts/verdrahtungskarte.py",
                     "scripts/pruefe_bibel.py", "docs/land-onboarding.md"):
        assert werkzeug in claude, f"CLAUDE.md nennt {werkzeug} nicht"


# ── Sonde 5: Nutzlast ───────────────────────────────────────────────────────
# Sonde 1 fragt, ob eine Datei in `web/data` FRISCH ist. Ob sie ueberhaupt jemand
# holt, fragte bis zum 2026-08-25 niemand — und `web/data` geht taeglich als Ganzes
# in den Objektspeicher (1,4 GB gemessen). An einem einzigen Tag entstand dort
# `kalender-index.json`, das keine vier Stunden spaeter als ungelesen aufflog.

def test_nutzlast_findet_die_ungelesene_datei(tmp_path, monkeypatch):
    """Was ausgeliefert und von niemandem geholt wird, muss auffallen."""
    (tmp_path / "leads-bau.json").write_text("[]")          # wird geladen
    (tmp_path / "geisterdatei.json").write_text("{}")       # holt niemand
    assert any("geisterdatei.json" in b for b in pv.sonde_nutzlast(wurzel=tmp_path))
    assert not any("leads-bau.json" in b for b in pv.sonde_nutzlast(wurzel=tmp_path))


def test_nutzlast_schweigt_bei_begruendeter_ausnahme(tmp_path, monkeypatch):
    """Eine benannte Ausnahme ist kein Befund — eine unbenannte schon."""
    (tmp_path / "doc-analysis.json").write_text("{}")
    assert pv.sonde_nutzlast(wurzel=tmp_path) == []


def test_nutzlast_erkennt_verzeichnisse_ueber_ein_beispiel(tmp_path):
    """Bei `kalender/<id>.json` sagt der Verzeichnisname allein nichts — geprüft wird
    eine Beispieldatei darin, sonst gälte jedes Scherbenverzeichnis als tot."""
    (tmp_path / "kalender").mkdir()
    (tmp_path / "kalender" / "491665_2026.json").write_text("{}")
    (tmp_path / "muell").mkdir()
    (tmp_path / "muell" / "x.json").write_text("{}")
    befunde = pv.sonde_nutzlast(wurzel=tmp_path)
    assert not any("kalender" in b for b in befunde), "ein echtes Scherbenverzeichnis gilt als tot"
    assert any("muell" in b for b in befunde)


def test_jede_nutzlast_ausnahme_hat_eine_begruendung():
    """Eine Ausnahme ohne Grund ist ein Schweigen, kein Befund."""
    for name, grund in pv.AUSNAHMEN_NUTZLAST.items():
        assert len(grund) > 20, f"{name} steht ohne belastbare Begruendung in der Liste"


@pytest.mark.skipif(not (ROOT / "web" / "data").exists(), reason="kein Export vorhanden")
def test_die_echte_nutzlast_ist_sauber():
    """Der eigentliche Waechter: eine NEUE ungelesene Datei laesst ab sofort die Suite
    fallen. Die drei bekannten stehen als offener Punkt in `AUSNAHMEN_NUTZLAST`."""
    assert pv.sonde_nutzlast() == []


def test_jedes_pruefskript_wird_auch_aufgerufen():
    """Eine Pruefung, die niemand startet, ist eine Datei — keine Pruefung.

    Unter `web/scripts/` liegen Skripte, die die ECHTEN Frontend-Bausteine gegen `node`
    fahren (Signatur, Herkunft, iCal-Faltung, Ratenbremse …). Sie sind genau deshalb dort,
    weil ein Test gegen eine Abschrift gruen geht, waehrend die benutzte Fassung falsch ist.
    Damit teilen sie aber die Schwaeche jedes Bausteins: gebaut heisst nicht aufgerufen.

    Am 2026-08-27 lag `pruefe-unterlagen-gelesen.mjs` genau so da — geschrieben, lauffaehig,
    von niemandem gestartet. Aufgefallen ist es nur, weil ich beim Anlegen des dritten
    eigenen Skripts nachgesehen habe, ob meine ueberhaupt laufen.

    Zaehlt als Aufruf: eine Datei unter `tests/` oder ein npm-Skript in `web/package.json`.
    """
    import json

    skripte = sorted((ROOT / "web" / "scripts").glob("pruefe-*.mjs"))
    assert len(skripte) >= 5, f"nur {len(skripte)} Pruefskripte gefunden — stimmt der Pfad noch?"

    rufer = [p.read_text(encoding="utf-8") for p in sorted((ROOT / "tests").glob("*.py"))]
    rufer.append(json.dumps(json.loads(
        (ROOT / "web" / "package.json").read_text(encoding="utf-8"))))
    alles = "\n".join(rufer)

    verwaist = [p.name for p in skripte if p.name not in alles]
    assert not verwaist, (
        "Pruefskripte, die niemand startet:\n  " + "\n  ".join(verwaist)
        + "\n(ein Test unter tests/ oder ein npm-Skript in web/package.json)")


def test_unterlagen_gelesen_sagt_die_wahrheit():
    """`has_documents` heisst „die QUELLE bewirbt Unterlagen", nicht „wir haben sie".

    Die Auskunft, ob wir den Volltext gelesen haben, ist die, fuer die ein Bieter das
    Produkt benutzt. Das Skript prueft sie gegen den echten Bestand.

    ⚠ Es traegt eine bewusste Nachlauf-Toleranz: ist der Volltext-Index juenger als der
    Lead-Export, sind einzelne Leads noch ohne Kennzeichnung, und das ist kein Mangel,
    sondern die Reihenfolge des Nachtlaufs. Ohne diese Toleranz waere der Test jede Nacht
    einmal rot und damit wertlos.
    """
    import subprocess

    skript = ROOT / "web" / "scripts" / "pruefe-unterlagen-gelesen.mjs"
    p = subprocess.run(["node", str(skript)], capture_output=True, text=True)
    assert p.returncode == 0, f"die Oberflaeche behauptet Unterlagen, die wir nicht haben:\n{p.stdout}{p.stderr}"


def test_passungszahl_widerspricht_nie_ihrer_stufe():
    """Die Zahl und das Wort daneben stammen aus derselben Groesse. Sie koennen auseinanderlaufen.

    `profileEngine.matchLead` rechnet einen Punktwert `s` und leitet daraus BEIDES ab: die
    Stufe (hoch/mittel/niedrig) ueber die Schwellen 4,5 und 3, und die Passungszahl ueber die
    Spanne S_MIN..S_MAX. Verschiebt jemand nur eine der beiden Seiten, zeigt die Oberflaeche
    „niedrig · 86" oder „hoch · 12".

    Das ist die unangenehme Sorte Fehler: beide Angaben sehen fuer sich plausibel aus, und
    niemand meldet sie. Darum faehrt `pruefe-passung.mjs` den ECHTEN Baustein unter `node`
    ueber alle erreichbaren Kombinationen und vergleicht Wort gegen Zahl.
    """
    import subprocess

    skript = ROOT / "web" / "scripts" / "pruefe-passung.mjs"
    p = subprocess.run(["node", str(skript)], capture_output=True, text=True)
    assert p.returncode == 0, f"Passungszahl und Relevanz-Stufe widersprechen sich:\n{p.stdout}{p.stderr}"


def test_jede_gold_tabelle_mit_fk_wird_geprueft():
    """Eine handgepflegte Liste hoert irgendwann auf zu wachsen. Diese hier merkt es selbst.

    `verify.gold_integrity` fuehrt die Fremdschluessel-Pruefungen als Liste von Hand. Am
    2026-08-25 stand sie bei 22 Pruefungen, waehrend `data/gold/<L>` auf 64 Tabellen
    gewachsen war — 44 kamen nicht vor, darunter die ganze Los-, CPV- und Kriterien-Ebene.
    Der Kommentar im Code nennt es die Krankheit: eine Liste, die aufgehoert hat zu wachsen,
    waehrend nebenan behauptet wurde, alle neuen Tabellen seien erfasst.

    Dagegen hilft kein Vorsatz, sondern nur eine Pruefung, die NEUE Tabellen von selbst
    findet. Diese hier scannt die Gold-Ebene nach Spalten, die erkennbar ein Fremdschluessel
    sind, und verlangt fuer jede entweder eine Pruefung oder einen begruendeten Eintrag in
    `verify.FK_AUSNAHMEN`. Wer eine Tabelle hinzufuegt, muss sich also entscheiden — und
    kann sie nicht mehr stillschweigend uebergehen.

    ⚠ Sie prueft die LISTE, nicht die Daten. Ob die Pruefung dann 0 Waisen findet, ist
    `gold_integrity` selbst; ob die Tabelle in allen Laendern existiert, ist
    `pruefe_verdrahtung.sonde_paritaet`. Drei verschiedene Fragen, drei Stellen.

    ⚠ UND SIE SIEHT NUR, WAS AUF DER PLATTE LIEGT. Eine gerade hinzugefuegte Tabelle ist
    unsichtbar, bis sie einmal gebaut wurde — der Wachhund greift also erst nach dem ersten
    Lauf. Gegengeprueft am 2026-08-31: nimmt man `buyer_loyalty` oder `retender_signal` aus
    der Liste, meldet sie beide; nimmt man `verify.FK_AUSNAHMEN` weg, meldet sie
    `entity_merge_map` und `entity_group`.
    """
    import ast
    import duckdb
    from govisor import verify

    gold = ROOT / "data" / "gold" / "DE"
    if not gold.is_dir():
        pytest.skip("keine Gold-Ebene vorhanden")

    # ⚠ NICHT per Regex ueber die ganze Datei. Der erste Anlauf tat das und war damit
    # wirkungslos: `FK_AUSNAHMEN` nennt die ausgenommenen Tabellen selbst beim Namen, also
    # galten sie als geprueft — und jede beliebige Erwaehnung im Quelltext haette die
    # Pruefung ebenso stillgelegt. Eine Pruefung, die sich vom eigenen Kommentar besaenftigen
    # laesst, prueft nichts.
    #
    # Stattdessen der Syntaxbaum: nur die Tupel aus den `checks`-Listen in `gold_integrity`
    # zaehlen, und dort nur das zweite Feld (die Kind-Tabelle).
    baum = ast.parse((ROOT / "govisor" / "verify.py").read_text(encoding="utf-8"))
    geprueft: set[str] = set()
    for knoten in ast.walk(baum):
        if not (isinstance(knoten, ast.Assign) and isinstance(knoten.value, ast.List)):
            continue
        namen = [z.id for z in knoten.targets if isinstance(z, ast.Name)]
        if not any(n.endswith("checks") for n in namen):
            continue
        for eintrag in knoten.value.elts:
            if not isinstance(eintrag, ast.Tuple):
                continue
            # Feld 1 = Kind-Tabelle (die geprueft wird), Feld 3 = Eltern-Tabelle (das ZIEL).
            # Die Eltern zaehlen ebenfalls als abgedeckt: `entities.entity_id` ist ein
            # Primaerschluessel, kein Fremdschluessel. Ohne diese Zeile meldet die Pruefung
            # `entities` und `quality` als ungeprueft — formal richtig erkannt, fachlich
            # Unsinn, und ein Fehlalarm in einer Waechter-Pruefung ist toedlich: er kostet
            # sie beim zweiten Mal das Vertrauen und beim dritten die Existenz.
            for i in (1, 3):
                if len(eintrag.elts) > i:
                    feld = eintrag.elts[i]
                    if isinstance(feld, ast.Constant) and str(feld.value).endswith(".parquet"):
                        geprueft.add(feld.value)
    assert geprueft, "keine Pruefliste gefunden — der Syntaxbaum-Zugriff ist gebrochen"

    # Spalten, die ohne Zweifel auf eine andere Tabelle zeigen.
    FK_SPALTEN = {"entity_id", "lead_id", "notice_id", "buyer_entity", "incumbent_entity"}

    con = duckdb.connect()
    offen = []
    for datei in sorted(gold.glob("*.parquet")):
        if datei.name in geprueft or datei.name in verify.FK_AUSNAHMEN:
            continue
        try:
            spalten = {c[0] for c in con.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{datei.as_posix()}')").fetchall()}
        except Exception:                                  # noqa: BLE001
            continue                                       # unlesbar ist Sache anderer Sonden
        treffer = spalten & FK_SPALTEN
        if treffer:
            offen.append(f"{datei.name} ({', '.join(sorted(treffer))})")
    con.close()

    assert not offen, (
        "Gold-Tabellen mit Fremdschluessel-Spalte, die weder in `gold_integrity` geprueft "
        "noch in `verify.FK_AUSNAHMEN` begruendet sind:\n  " + "\n  ".join(offen))


def test_eignungscheck_gibt_seine_antworten_weiter():
    """Der Check sammelt sechs Angaben. Bis zum 2026-08-31 warf er sie danach weg.

    Gemessen: der Aufruf „N passende offene Vergaben ansehen" war ein blankes
    `<a href="/onboarding">`, `localStorage` und `sessionStorage` blieben leer, und
    `app/onboarding/page.tsx` hatte NULL Treffer fuer `buergschaft`, `iso_9001`,
    `praequalifikation`, `referenz`. Der Nutzer beantwortete dieselben Fragen zweimal —
    beim zweiten Mal, weil `matchLead` mangels `buergschaft` sagte „hinterlegt euren Rahmen".

    Das ist die Sorte Fehler, die keine Ausnahme wirft und keinen Test rot macht: beide
    Seiten funktionieren fuer sich. Nur die Leitung dazwischen fehlt. Deshalb wird hier die
    LEITUNG geprueft, nicht das Verhalten der Enden.

    ⚠ Bewusst eine Quelltext-Pruefung, mit der bekannten Schwaeche: sie sieht, dass die
    Aufrufe dastehen, nicht dass sie zur Laufzeit greifen. Das Verhalten selbst wurde am
    2026-08-31 von Hand durchgespielt (Check → Onboarding → Profil traegt volMin/volMax
    100.000/500.000 und `capabilities: ["berufshaftpflicht"]`). Eine bessere Pruefung
    braeuchte einen Browser im Testlauf; die gibt es hier nicht.
    """
    web = ROOT / "web"
    check = (web / "components" / "EignungsCheck.tsx").read_text(encoding="utf-8")
    onb = (web / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    modul = (web / "lib" / "checkUebergabe.ts").read_text(encoding="utf-8")

    assert "checkUebergabe" in check and "speichern(" in check, \
        "der Eignungs-Check gibt seine Antworten nicht mehr weiter"
    assert "onClick={angabenMitgeben}" in check, \
        "der Aufruf ins Onboarding traegt die Angaben nicht mehr mit"
    assert "checkUebergabe" in onb and "alsProfilfelder" in onb, \
        "das Onboarding liest die Angaben aus dem Check nicht mehr"
    assert "uebernimmCheck" in onb, \
        "die Nachweise landen nicht mehr im Firmenprofil — nur dort liest recommendation.js sie"
    assert "Aus eurem Check" in onb, \
        "die Uebernahme muss SICHTBAR sein; still vorbelegte Zahlen kann niemand korrigieren"

    # Beide Seiten muessen denselben Schluessel benutzen. Er steht genau einmal, im Modul.
    assert modul.count('const SCHLUESSEL') == 1
    assert "gv_check_v1" not in check and "gv_check_v1" not in onb, \
        "der Speicherschluessel gehoert ins Modul, nicht in die Enden — sonst laeuft er auseinander"


def test_passwortregel_haelt_was_der_hinweis_verspricht():
    """Hinweis und Regel standen uebereinander und widersprachen sich.

    Unter dem Feld: „Länge zählt mehr als Sonderzeichen, eine Passphrase aus vier Wörtern ist
    sicherer als P@ssw0rt!" Darunter eine Bedingung, die drei Zeichenklassen verlangte. Eine
    29 Zeichen lange Passphrase fiel durch, `Abcdefgh123!` kam durch.

    Beide Seiten waren fuer sich vertretbar, und genau deshalb schlug nichts an. Dazu kam,
    dass DREI verschiedene Regeln nebeneinander standen — Onboarding 12 Zeichen plus Klassen,
    Zuruecksetzen 8, Einstellungen 8. Man konnte spaeter ein Passwort setzen, mit dem man
    sich nicht haette registrieren duerfen: die schwaechste Regel gewann, weil sie erreichbar
    blieb.

    `pruefe-passwort.mjs` faehrt die EINE Regel unter `node` mit echten Passwoertern.
    """
    import subprocess

    skript = ROOT / "web" / "scripts" / "pruefe-passwort.mjs"
    p = subprocess.run(["node", str(skript)], capture_output=True, text=True)
    assert p.returncode == 0, f"Passwortregel und Hinweis widersprechen sich:\n{p.stdout}{p.stderr}"

    # Und die Regel darf nicht wieder auseinanderlaufen: keine eigene Laengenpruefung mehr
    # neben der gemeinsamen.
    web = ROOT / "web"
    for datei in ("app/onboarding/page.tsx", "app/auth/passwort/page.tsx", "app/settings/page.tsx"):
        quelle = (web / datei).read_text(encoding="utf-8")
        assert "pwPruefung" in quelle, f"{datei} benutzt die gemeinsame Passwortregel nicht"
    einstellungen = (web / "app" / "settings" / "page.tsx").read_text(encoding="utf-8")
    assert "pw.length < 8" not in einstellungen, "die alte 8-Zeichen-Regel ist zurueck"


def test_bereiche_decken_alle_req_types():
    """Eine neue Anforderungsart darf nicht stillschweigend in einer falschen Gruppe landen.

    `theme` aus der LLM-Auswertung war eine verlustbehaftete Umkodierung von `req_type`:
    gemessen am 2026-09-01 bildete jeder der 18 Typen auf genau ein Thema ab, 70,5 % landeten
    auf „sonstiges". Nicht weil die Zuordnung scheiterte, sondern weil das Vokabular
    eignungs-zentriert war und die Haelfte des Materials Vertrags- und Formalienfragen sind.

    `BEREICH` ordnet stattdessen nach der Frage, die ein Bieter stellt. Der Preis dafuer ist
    eine Pflegestelle: kommt ein neuer `req_type` dazu, muss er eingetragen werden. Genau
    deshalb gibt es keinen stillen Sammeltopf — Unbekanntes wird `unbekannt` und faellt hier
    auf. Ein Default haette den Fehler unsichtbar gemacht, und das ist die Sorte Fehler, die
    Monate ueberlebt.
    """
    import json
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("bda", ROOT / "scripts" / "build_doc_analysis.py")
    bda = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bda)

    erlaubt = {"eignung", "leistung", "vertrag", "formalitaet", "termin", "ausschluss", "zuschlag"}
    assert set(bda.BEREICH.values()) <= erlaubt, \
        f"unbekannter Bereich in der Zuordnung: {set(bda.BEREICH.values()) - erlaubt}"

    quelle = ROOT / "web" / "data" / "doc-analysis"
    if not quelle.is_dir():
        pytest.skip("keine Auswertung vorhanden")

    # Gegen die ECHTEN Daten, nicht gegen eine Liste im Test: eine Stichprobe reicht, um
    # einen neu auftauchenden Typ zu bemerken, und haelt den Lauf kurz.
    fehlend = set()
    for i, pfad in enumerate(sorted(quelle.glob("*.json"))):
        if i >= 400:
            break
        try:
            d = json.loads(pfad.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            continue
        for it in d.get("checklist") or []:
            rt = it.get("req_type")
            if rt and rt not in bda.BEREICH:
                fehlend.add(rt)
    assert not fehlend, (
        "req_type ohne Bereich — in `BEREICH` eintragen, nicht in einen Sammeltopf schieben:\n  "
        + "\n  ".join(sorted(fehlend)))


def test_verwerfungsgruende_summieren_sich():
    """Drei Zaehler, eine Summe — sonst verschwindet eine Ursache unbemerkt.

    Bis zum 2026-09-01 zaehlte `verarbeite` alle Verwerfungen in EINE Zahl. Damit war die
    entscheidende Frage nicht beantwortbar: von 4.747 Vorgaengen ohne
    Zuschlagskriterien-Dokument tragen 82,8 % das Wort trotzdem im Volltext, und bei 91,1 %
    lagen ausschliesslich Doktypen vor, die `zuschlagskriterium` gar nicht melden DUERFEN.
    Findet das Modell die Kriterien und wir werfen sie weg — oder findet es sie nicht? Eine
    einzelne Zahl kann das nicht sagen.

    Jetzt: `beleg` = Modellqualitaet, `typ` = unsere Regel, `schema` = Formatproblem. Der
    Test haelt fest, dass die drei zusammen `rejected` ergeben. Kommt eine vierte Ursache
    dazu, ohne einen eigenen Zaehler zu bekommen, faellt sie hier auf statt still in einer
    der drei zu verschwinden.
    """
    from govisor import docextract

    doctype = "aufforderung"
    text = "Die Angebotsfrist endet am 30.09.2026 um 10:00 Uhr."
    roh = [
        # gueltig und belegt
        {"req_type": "frist", "value": "30.09.2026", "unit": None,
         "quote": "Die Angebotsfrist endet am 30.09.2026", "marking": "Zitat"},
        # richtiger Typ, aber fuer diesen Doktyp nicht erlaubt → `typ`
        {"req_type": "zuschlagskriterium", "value": "50", "unit": "%",
         "quote": "Die Angebotsfrist endet am 30.09.2026", "marking": "Zitat"},
        # Zitat steht nicht im Text → `beleg`
        {"req_type": "frist", "value": "1", "unit": None,
         "quote": "Ein Satz, der im Dokument nirgends vorkommt und lang genug ist",
         "marking": "Zitat"},
        # kaputt → `schema`
        {"req_type": "gibtesnicht", "marking": "Zitat", "quote": "x"},
    ]
    res = docextract.verarbeite(doctype, text, "datei.pdf", roh)
    g = res["rejected_gruende"]

    assert sum(g.values()) == res["rejected"], \
        f"Gruende {g} ergeben nicht die Summe {res['rejected']}"
    assert g["typ"] == 1, f"der nicht erlaubte Typ muss als `typ` zaehlen, nicht anders: {g}"
    assert g["beleg"] == 1, f"das unbelegte Zitat muss als `beleg` zaehlen: {g}"
    assert g["schema"] == 1, f"der kaputte Eintrag muss als `schema` zaehlen: {g}"
    assert len(res["items"]) == 1, "der gueltige Eintrag muss durchkommen"


def test_kurzes_zitat_gilt_nur_wenn_eindeutig():
    """Die Belegpflicht wurde gelockert — aber genau so weit, dass keine Erfindung durchkommt.

    Gemessen am 2026-09-01 an 920 abgelehnten Zitaten: 536 (58,3 %) scheiterten allein an der
    Laengenschwelle von 16 Zeichen. Der naheliegende Schluss „die Schwelle ist zu hoch" war
    falsch — von den Verworfenen kommen 350 (38,0 %) im Volltext GAR NICHT vor. Ein blosses
    Absenken haette 350 Erfindungen hereingelassen.

    Der tragfaehige Unterschied ist die EINDEUTIGKEIT: 268 (29,1 %) treffen genau einmal, und
    das sind die Belege, die uns fehlen — Formularankreuzungen, Fristen, LV-Positionen.
    147 (16,0 %) treffen mehrfach und bleiben draussen.

    Der Test haelt beide Seiten fest. Faellt eine, ist die Regel entweder wieder zu streng
    (die kurzen Belege fehlen) oder zu lax (Erfindungen kommen durch).
    """
    from govisor.docextract import verify_quote

    text = ("Der Bieter reicht X Urkalkulation ein. Menge: 165 Meter. "
            "Zone 9: Mo.-Sa. 9-22 Uhr. psch psch psch. Angebot in Textform.")

    # kurz, aber genau einmal → gilt
    assert verify_quote("X Urkalkulation", text)
    assert verify_quote("Menge: 165 Meter", text)

    # kurz und MEHRFACH → gilt nicht, sonst waere jeder Zufallstreffer ein Beleg
    assert not verify_quote("psch", text)

    # unter dem Boden → gilt nicht, auch wenn eindeutig: „X nein" zeigt zwar auf eine
    # Stelle, sagt einem Menschen aber nicht, worauf es sich bezieht.
    assert not verify_quote("in Textform"[:6], text)

    # gar nicht vorhanden → gilt nicht, egal wie lang
    assert not verify_quote("Ein Satz, der in diesem Dokument nirgends steht", text)

    # der lange Normalfall bleibt unveraendert
    assert verify_quote("Der Bieter reicht X Urkalkulation ein", text)


# ── UPLOAD-DECKEL: VORRANG MIT EIGENER OBERGRENZE ────────────────────────────────────
#
# Der Vorrang fuer hochgeladene Unterlagen ist genau die Sorte Aenderung, die still kaputt
# geht: faellt der Zweck weg, laeuft der Upload einfach gegen den allgemeinen Deckel und
# wartet bis 00:30 — das Ergebnis sieht nicht falsch aus, es kommt nur spaeter. Und faellt
# der eigene Deckel weg, merkt es niemand, bis die Rechnung kommt. Deshalb wird hier das
# VERHALTEN geprueft, nicht die Anwesenheit der Konstanten.

def _wache_stellen(monkeypatch, *, stand, tag_allgemein, tag_upload):
    """Geldwache mit gestellten Zahlen, damit die Entscheidung pruefbar wird."""
    from govisor import llm
    monkeypatch.setattr(llm, "kontostand", lambda frisch=False: stand)
    monkeypatch.setattr(llm, "_tagesbuch", lambda s: tag_allgemein)
    monkeypatch.setattr(llm, "_tagesbuch_zweck", lambda z: tag_upload if z == "upload" else 0.0)
    llm._geld.update(start=stand, start_verbrauch=0.0, verbrauch=0.0,
                     n=0, naechste=0, gewarnt=False, stopp=None)
    return llm


def _laeuft(llm, zweck):
    """True, wenn die Wache diesen Zweck durchlaesst."""
    llm._geld["stopp"] = None
    llm._geld["n"] = 0
    llm._geld["naechste"] = 0
    with llm.kontext(zweck=zweck):
        try:
            llm._geldwache()
            return True, ""
        except llm.BudgetErschoepft as e:
            return False, str(e)


def test_upload_laeuft_weiter_wenn_der_tagesdeckel_gerissen_ist(monkeypatch):
    """Der allgemeine Deckel ist voll, der Upload-Topf leer → Analyse ja, Upload ja."""
    llm = _wache_stellen(monkeypatch, stand=50.0,
                         tag_allgemein=llm_tag() + 1.0, tag_upload=0.0)
    ok_analyse, grund = _laeuft(llm, "analyse")
    assert not ok_analyse, "Der allgemeine Tagesdeckel haette greifen muessen"
    assert "Tagesdeckel" in grund
    ok_upload, _ = _laeuft(llm, "upload")
    assert ok_upload, ("Hochgeladene Unterlagen muessen am allgemeinen Tagesdeckel vorbei — "
                       "sonst wartet der Nutzer bis zum naechsten Tageslauf, obwohl ihm "
                       "sofortige Auswertung zugesagt wurde.")


def test_upload_hat_eine_eigene_obergrenze(monkeypatch):
    """Vorrang ohne eigenen Deckel waere die Abschaffung des Deckels."""
    from govisor import llm as _l
    llm = _wache_stellen(monkeypatch, stand=50.0, tag_allgemein=0.0,
                         tag_upload=_l.UPLOAD_TAG_USD + 0.01)
    ok, grund = _laeuft(llm, "upload")
    assert not ok, "Der eigene Upload-Tagesdeckel hat nicht gegriffen"
    assert "hochgeladene" in grund.lower() and "GOVISOR_UPLOAD_TAG_USD" in grund, grund


def test_upload_haelt_die_reserve_trotzdem_ein(monkeypatch):
    """Vorrang heisst Vorrang vor dem Tagesdeckel, nicht vor dem leeren Konto."""
    from govisor import llm as _l
    llm = _wache_stellen(monkeypatch, stand=_l.RESERVE_USD - 0.01,
                         tag_allgemein=0.0, tag_upload=0.0)
    ok, grund = _laeuft(llm, "upload")
    assert not ok, "Die Reserve muss auch fuer hochgeladene Unterlagen gelten"
    assert "Reserve" in grund, grund


def test_upload_frisst_dem_arbeiter_sein_budget_nicht(monkeypatch):
    """Zwei Toepfe in BEIDE Richtungen: was der Upload verbraucht, zaehlt dem Tageslauf nicht."""
    from govisor import llm as _l
    # Der Tag hat insgesamt so viel gekostet wie der Deckel erlaubt — aber alles davon
    # ging auf Uploads. Der Arbeiter muss trotzdem laufen duerfen.
    voll = _l.TAG_USD - _l.SCHONUNG_USD
    llm = _wache_stellen(monkeypatch, stand=50.0, tag_allgemein=voll + 0.5, tag_upload=voll + 0.5)
    ok, grund = _laeuft(llm, "analyse")
    assert ok, ("Upload-Ausgaben duerfen dem allgemeinen Tagesdeckel nicht angerechnet "
                f"werden, sonst nimmt wer zuerst da ist alles. Grund: {grund}")


def test_upload_setzt_seinen_zweck_und_meldet_ehrlich():
    """Ohne `zweck='upload'` gibt es keinen Vorrang — und ohne Anzeige keine Ehrlichkeit."""
    from govisor import llm as _l
    quelle = (ROOT / "scripts" / "process_upload.py").read_text(encoding="utf-8")
    assert 'zweck="upload"' in quelle, "process_upload.py setzt den Zweck nicht"
    assert "upload" in _l.VORRANG, "llm.VORRANG kennt den Upload nicht"
    assert "BudgetErschoepft" in quelle, "der Deckel wird im Upload nicht abgefangen"
    assert "lbAnalyseWartet" in quelle, "der Upload meldet das Warten nicht zurueck"
    schale = (ROOT / "web" / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    assert "lbAnalyseWartet" in schale, (
        "Der Client zeigt die Wartemeldung nicht an — der Nutzer saehe einen "
        "erfolgreichen Upload ohne Auswertung und ohne Grund.")


def llm_tag() -> float:
    from govisor import llm as _l
    return _l.TAG_USD - _l.SCHONUNG_USD


# ---- Sonde 6: Baugrenze --------------------------------------------------------
def _baugrenze():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_pv", ROOT / "scripts" / "pruefe_verdrahtung.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _baum(wurzel, verteilung: dict[str, int]):
    for name, n in verteilung.items():
        d = wurzel / name
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"{i}.json").write_text("{}", encoding="utf-8")


def test_baugrenze_schweigt_unter_der_warnschwelle(tmp_path):
    m = _baugrenze()
    _baum(tmp_path, {"firma": 20, "doc-text": 5})
    assert m.sonde_baugrenze(wurzel=tmp_path) == []


def test_baugrenze_meldet_ueber_der_warnschwelle(tmp_path, monkeypatch):
    """Die eigentliche Gegenprobe: schlaegt sie an, wenn es eng wird?

    ⚠ WARUM DIESE SONDE UEBERHAUPT GEBRAUCHT WIRD. `next build` stirbt bei rund 156.000
    Dateien unter `web/data` reproduzierbar im Node-Heap. Das steht seit Wochen an zwei
    Stellen im Code — und NICHTS zaehlte die Dateien. Der Deckel schlaegt erst beim Bauen
    ein, und kein Alltagslauf faehrt `next build`; genau so blieb der `/login`-Fehler
    vierzehn Tage unsichtbar. Ein SIGABRT im Node-Heap sieht dazu nach zu wenig Speicher
    aus, nicht nach zu vielen Dateien.
    """
    m = _baugrenze()
    monkeypatch.setattr(m, "BAUWARNUNG", 30)
    monkeypatch.setattr(m, "BAUGRENZE", 40)
    _baum(tmp_path, {"firma": 25, "suppliers": 10})
    befunde = m.sonde_baugrenze(wurzel=tmp_path)
    assert len(befunde) == 1, befunde
    assert "35" in befunde[0], befunde[0]           # gezaehlt
    assert "firma 25" in befunde[0], befunde[0]     # und benannt, wo man buendeln muesste


def test_baugrenze_haelt_stand_und_grenze_beieinander():
    """Die Zahl darf nicht an drei Orten auseinanderlaufen.

    Sie steht im Exporteur, im Frontend-Lader und jetzt in der Sonde. Laufen sie
    auseinander, buendelt jemand gegen eine Grenze, die es nicht gibt.
    """
    m = _baugrenze()
    for datei in ("scripts/export_vorgaenge.py", "web/lib/vorgangsakte.ts"):
        text = (ROOT / datei).read_text(encoding="utf-8")
        assert "156.000" in text or str(m.BAUGRENZE) in text, (
            f"{datei} nennt die Baugrenze nicht mehr — oder anders als die Sonde "
            f"({m.BAUGRENZE:,}).")


def test_baugrenze_ohne_verzeichnis_ist_kein_befund(tmp_path):
    """Frische Arbeitskopie ohne Export: kein Befund, kein Absturz."""
    m = _baugrenze()
    assert m.sonde_baugrenze(wurzel=tmp_path / "gibtsnicht") == []


# ---- Sonde 7: Module ----------------------------------------------------------
def _webbaum(wurzel, dateien: dict[str, str]):
    for pfad, inhalt in dateien.items():
        z = wurzel / pfad
        z.parent.mkdir(parents=True, exist_ok=True)
        z.write_text(inhalt, encoding="utf-8")
    return wurzel


def test_module_findet_eine_datei_die_niemand_importiert(tmp_path):
    """⚠ DER FUND, DER DIESE SONDE AUSGELOEST HAT. `web/lib/identityGate.ts` ist ein
    fail-closed gebautes Sicherheitstor mit eigenem Sperrtext („Diese Funktion ist gesperrt,
    bis eure Zugehoerigkeit zur Firma bestaetigt ist") — und KEINE Stelle importiert es. Wer
    die Datei liest, haelt die Zugaenge fuer geschuetzt. Die Fehlerklasse ist die des Hauses:
    gebaut, nicht verdrahtet — nur eben im Frontend, wo bis dahin keine Sonde hinsah.
    """
    m = _baugrenze()
    w = _webbaum(tmp_path, {
        "lib/genutzt.ts": "export const a = 1;",
        "lib/tot.ts": "export const b = 2;",
        "app/seite.tsx": 'import { a } from "@/lib/genutzt";',
    })
    befunde = m.sonde_module(wurzel=w)
    assert len(befunde) == 1, befunde
    assert "lib/tot.ts" in befunde[0]


def test_module_kennt_den_import_ueber_das_verzeichnis(tmp_path):
    """Ein `index` wird ueber SEIN VERZEICHNIS importiert.

    ⚠ `lib/i18n/index.tsx` heisst im Import `@/lib/i18n`. Ohne diese Regel meldete die Sonde
    jedes Index-Modul als Leiche — beim Bauen genau hier passiert.
    """
    m = _baugrenze()
    w = _webbaum(tmp_path, {
        "lib/i18n/index.tsx": "export const t = 1;",
        "app/seite.tsx": 'import { t } from "@/lib/i18n";',
    })
    assert m.sonde_module(wurzel=w) == []


def test_module_schweigt_bei_begruendeter_ausnahme(tmp_path, monkeypatch):
    """Eine benannte Ausnahme ist kein Befund — eine unbenannte schon."""
    m = _baugrenze()
    monkeypatch.setitem(m.AUSNAHMEN_MODULE, "lib/tot.ts", "steht als Stub bis zum Start")
    w = _webbaum(tmp_path, {"lib/tot.ts": "export const b = 2;"})
    assert m.sonde_module(wurzel=w) == []


def test_jede_modul_ausnahme_hat_eine_begruendung():
    """Eine Ausnahme ohne Grund ist ein Schweigen, kein Befund."""
    m = _baugrenze()
    for name, grund in m.AUSNAHMEN_MODULE.items():
        assert len(grund) > 20, f"{name} steht ohne belastbare Begruendung in der Liste"


def test_keine_modul_ausnahme_fuer_etwas_das_es_nicht_mehr_gibt():
    """Eine Ausnahme fuer eine geloeschte Datei ist toter Ballast — und sie verdeckt, dass
    die Liste seit Monaten niemand gelesen hat."""
    m = _baugrenze()
    fehlt = [n for n in m.AUSNAHMEN_MODULE if not (ROOT / "web" / n).exists()]
    assert not fehlt, f"AUSNAHMEN_MODULE nennt Dateien, die es nicht mehr gibt: {fehlt}"


# ---- Wer ein Skript LAEDT, fuehrt es aus --------------------------------------
def _ohne_main_schutz() -> set[str]:
    """Skripte, bei denen ein blosser Import die ganze Arbeit erledigt."""
    return {p.stem for p in (ROOT / "scripts").glob("*.py")
            if "__main__" not in p.read_text(encoding="utf-8", errors="replace")}


def test_keine_pruefung_fuehrt_einen_export_aus():
    """Ein Werkzeug, das nachsehen soll, darf nichts schreiben.

    ⚠ DER FUND, GEMESSEN AM 2026-09-04. `pruefe_bibel.py` lud `scripts/export_suppliers.py`
    ueber `exec_module`, um EINE Konstante zu lesen. Das Skript hat keinen `__main__`-Schutz:
    der gesamte Export laeuft auf Modulebene. Jeder Import fuehrte damit die vollstaendige
    Lieferanten-Ausgabe aus — DuckDB ueber Gold, 46 MB `suppliers.json` schreiben, 37.930
    Einzeldateien anfassen und verwaiste LOESCHEN. Im Nachtlauf stand derselbe Export
    zweimal im Protokoll:

        daily-2026-09-04-0031.log:899   37930 Lieferanten → web/data/suppliers.json
        daily-2026-09-04-0031.log:1061  37930 Lieferanten → web/data/suppliers.json

    Die zweite Zeile war die Pruefung. Wer sie von Hand aufrief, waehrend ein Export lief,
    schrieb mitten hinein. Behoben, indem der Wert jetzt mit `ast` aus dem Quelltext GELESEN
    wird — ohne eine einzige Anweisung auszufuehren.

    Diese Regel haelt es allgemein: kein `spec_from_file_location` auf ein Skript, das beim
    Import arbeitet. Entweder man liest den Quelltext, oder das Skript bekommt einen
    `__main__`-Schutz.
    """
    import ast
    ungeschuetzt = _ohne_main_schutz()
    assert "export_suppliers" in ungeschuetzt, (
        "export_suppliers.py hat jetzt einen __main__-Schutz — dann darf diese Ausnahme weg "
        "und der Test kann strenger werden.")

    befunde: list[str] = []
    for p in sorted(list((ROOT / "tests").glob("*.py")) + list((ROOT / "scripts").glob("*.py"))):
        try:
            baum = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for k in ast.walk(baum):
            if not (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                    and k.func.attr == "spec_from_file_location" and len(k.args) >= 2):
                continue
            ziel = ast.unparse(k.args[1])
            for name in ungeschuetzt:
                if f'"{name}.py"' in ziel or f"'{name}.py'" in ziel:
                    befunde.append(f"{p.relative_to(ROOT)}:{k.lineno} laedt {name}.py")
    assert not befunde, (
        "Diese Stellen fuehren beim Laden ein ganzes Skript aus:\n  " + "\n  ".join(befunde)
        + "\nEntweder den Quelltext lesen (ast) oder dem Skript einen __main__-Schutz geben.")


def test_module_erkennt_einen_import_mit_endung(tmp_path):
    """⚠ DER FEHLALARM AUS DER ERSTEN NACHT.

    Das Muster verlangte das schliessende Anfuehrungszeichen unmittelbar nach dem
    Modulnamen. Ein Import der Form `from "@/lib/ladegrund.js"` fiel damit durch, und die
    Sonde meldete im Nachtlauf vom 2026-09-05 ein Modul als Leiche, das an fuenf Stellen
    importiert wird. Ein Fehlalarm wiegt hier schwerer als ein uebersehener Fund: eine
    Sonde, die grundlos anschlaegt, liest nach zwei Wochen niemand mehr.
    """
    m = _baugrenze()
    w = _webbaum(tmp_path, {
        "lib/mitEndung.js": "export const a = 1;",
        "lib/ohneEndung.ts": "export const b = 2;",
        "app/seite.tsx": ('import { a } from "@/lib/mitEndung.js";\n'
                          'import { b } from "@/lib/ohneEndung";\n'),
    })
    assert m.sonde_module(wurzel=w) == []

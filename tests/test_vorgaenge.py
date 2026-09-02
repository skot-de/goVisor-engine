"""Vorgänge — Ausschreibung, Dokumente und Zuschlag unter einer Kennung.

Der Schlüssel ist ein Wasserfall mit drei verschieden guten Stufen, und die entscheidende
Eigenschaft ist, dass jede Zeile sagt, welche gegriffen hat. Eine über Käufer und Titel
zusammengesetzte Akte darf nicht aussehen wie eine amtlich verknüpfte.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "build_vorgaenge.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")


def _modul():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_vg", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _koerper(name: str) -> str:
    fn = next(n for n in ast.walk(ast.parse(QUELLE))
              if isinstance(n, ast.FunctionDef) and n.name == name)
    rumpf = fn.body[1:] if ast.get_docstring(fn) else fn.body
    return "\n".join(ast.get_source_segment(QUELLE, k) or "" for k in rumpf)


def _gold(land: str = "DE"):
    p = WURZEL / "data" / "gold" / land / "vorgaenge.parquet"
    if not p.exists():
        return None
    import duckdb
    return duckdb.connect(), f"read_parquet('{p.as_posix()}')"


# ── der Wasserfall ──────────────────────────────────────────────────────────────────────

def test_die_reihenfolge_der_stufen():
    """⚠ `ContractFolderID` zuerst, weil sie als einzige die eForms-Jahre trägt: der
    Rückverweis ist ab 2024 praktisch leer (2023: 44.470 verknüpfte Zuschläge, 2024: 507)."""
    m = _modul()
    assert m.RANG == {"folder": 0, "rueckref": 1, "allein": 2}
    k = _koerper("baue")
    assert k.index("ContractFolderID") < k.index("ref_publication_number"), \
        "der Rückverweis steht vor der Verfahrenskennung"


def test_die_staerkste_regel_der_gruppe_gewinnt():
    """⚠ Bei einer Rückverweis-Kette trägt nur das KIND einen Verweis; die Wurzel fällt für
    sich auf `allein` und gruppiert trotzdem richtig. Wer das Erstbeste nimmt, meldet je nach
    Lesereihenfolge mal `rueckref`, mal `allein` für denselben Vorgang — die Zahl in der
    Auswertung schwankte dadurch um das Fünfzigfache (7.612 gegen 352.954)."""
    k = _koerper("baue")
    assert "min((t[0] for t in teile), key=lambda q: RANG[q])" in k
    assert "teile[0][0]" not in k


def test_zyklusschutz_in_der_kette():
    """Eine Korrektur, die auf sich selbst zeigt, hängt sonst den ganzen Lauf auf."""
    m = _modul()
    assert m._wurzel({"a": "b", "b": "a"}, "a") in ("a", "b")
    assert m._wurzel({"c": "b", "b": "a"}, "c") == "a"
    assert m._wurzel({}, "x") == "x"


# ── die Entscheidung, die den Anwendungsfall rettet ─────────────────────────────────────

def test_grosse_vorgaenge_werden_gezaehlt_nicht_gekappt():
    """⚠ 304 Kennungen tragen über 20 Bekanntmachungen. Das ist ENTWEDER ein Rahmenvertrag mit
    vielen Abrufen — „DBS über den Bezug von Schulungsleistungen": 1 Ausschreibung, 789
    Zuschläge, 0 Korrekturen — ODER eine nachlässig vergebene Kennung. Der Unterschied steht in
    den Zählspalten. Wer kappt, wirft den Fall weg, wegen dem man das Ganze baut."""
    k = _koerper("baue")
    assert not re.search(r"if len\(teile\) [<>]", k), "die Gruppengrösse wird beschnitten"
    for spalte in ("n_bekanntmachungen", "n_ausschreibung", "n_zuschlag", "n_korrektur"):
        assert spalte in QUELLE, f"{spalte} fehlt — ohne sie ist Rahmenvertrag nicht von Müll zu trennen"
    d = _gold()
    if d:
        con, V = d
        n = con.execute(f"select count(*) from {V} where n_zuschlag >= 5 and n_korrektur < n_zuschlag").fetchone()[0]
        assert n > 100, f"nur {n} Rahmenvertrags-Kandidaten — die Gruppierung greift nicht"


def test_titel_kommt_aus_der_ausschreibung():
    """Der Zuschlag trägt oft nur „Vergabe von …" oder den Losnamen."""
    k = _koerper("baue")
    assert '[t for t in teile if t[1] == "cn"] or teile' in k


# ── EU-weit ─────────────────────────────────────────────────────────────────────────────

def test_laender_kommen_vom_bestand():
    fn = next(n for n in ast.walk(ast.parse(QUELLE))
              if isinstance(n, ast.FunctionDef) and n.name == "_laender")
    text = ast.get_source_segment(QUELLE, fn)
    assert "iterdir()" in text
    assert not re.search(r'"(DE|AT|CH|PL)"', text), "harte Länderliste"


def test_kein_de_fester_pfad():
    """⚠ Die häufigste Altlast des Projekts: für DE gebaut, für den Rest vergessen."""
    assert "gold/DE" not in QUELLE and "silver/DE" not in QUELLE
    assert 'land' in _koerper("baue")


def test_alle_laender_haben_die_tabelle():
    silber = WURZEL / "data" / "silver"
    if not silber.is_dir():
        return
    laender = [p.name for p in silber.iterdir() if p.is_dir() and (p / "notices").is_dir()]
    fehlen = [l for l in laender
              if not (WURZEL / "data" / "gold" / l / "vorgaenge.parquet").exists()]
    assert not fehlen, f"ohne Vorgänge: {fehlen}"


# ── die Ketten ──────────────────────────────────────────────────────────────────────────

def _kette(land: str = "DE"):
    q = WURZEL / "data" / "gold" / land / "vorgang_kette.parquet"
    if not q.exists():
        return None
    import duckdb
    return duckdb.connect(), f"read_parquet('{q.as_posix()}')"


def test_kanten_im_selben_vorgang_fallen_weg():
    """⚠ 10.935 der 114.402 Nachfolge-Kanten verbinden zwei Bekanntmachungen DESSELBEN
    Vorgangs — die Abrufe unter einem Rahmenvertrag. Auf Vorgangsebene ist das keine
    Nachfolge, sondern Innenleben; ohne diesen Filter wäre jeder Rahmenvertrag eine Kette
    mit sich selbst."""
    k = _koerper("baue_ketten")
    assert "a.vorgang_id <> b.vorgang_id" in k


def test_bester_vorgaenger_statt_erstbester():
    """99 % der Vorgänge haben ohnehin genau einen Vorgänger — die Auswahl korrigiert 1 %.
    Sie folgt der Vorgänger-Richtung, weil Nachfolger verzweigen (ein alter Auftrag wird in
    mehrere neue zerlegt)."""
    k = _koerper("baue_ketten")
    assert "rang > bester[nach][0]" in k
    assert "float(konf or 0)" in k, "die Konfidenz entscheidet nicht"


def test_zyklusschutz_auch_in_der_kette():
    """⚠ `contract_succession` ist eine SCHÄTZUNG und kann im Kreis zeigen."""
    k = _koerper("baue_ketten")
    stelle = k[k.index("def wurzel"):]
    assert "gesehen" in stelle and "v not in gesehen" in stelle


def test_dauerangebot_haengt_am_takt_nicht_am_titel():
    """⚠ DIE ZWEITE FASSUNG. Zuerst markierte ich Ketten mit nur EINEM Titel — und traf
    daneben: die längste Kette (435 Glieder, „Abschluss einer nicht-exklusiven
    Rabattvereinbarung") trägt mehrere Titelvarianten und wäre durchgerutscht. Ein
    Rahmenvertrag wird alle zwei bis vier Jahre neu vergeben; ein Open-House-Vertrag nach
    §130a SGB V nimmt laufend Beitritte auf."""
    m = _modul()
    assert m.DAUERANGEBOT_TAKT == 4.0
    k = _koerper("baue_ketten")
    assert "takt > DAUERANGEBOT_TAKT" in k
    assert "len(titel) > 1" not in k, "die verworfene Titel-Regel ist zurück"
    d = _kette()
    if d:
        con, K = d
        r = con.execute(f"""select
            count(distinct kette_id) filter (where dauerangebot) markiert,
            max(n_glieder) filter (where dauerangebot) laengste_markiert,
            max(n_glieder) filter (where not dauerangebot) laengste_normal from {K}""").fetchone()
        assert 50 < r[0] < 2000, f"{r[0]} markierte Ketten — die Schwelle trifft nicht mehr"
        assert r[1] > r[2], "die längste Kette gilt als normale Neuausschreibung"


def test_die_kette_traegt_ihre_schwaechste_konfidenz():
    """`contract_succession` ist Inhaltsvergleich (0,76) und LLM-Adjudikation (0,70), keine
    amtliche Verknüpfung. Eine Kette ist so belastbar wie ihr schwächstes Glied."""
    d = _kette()
    if not d:
        return
    con, K = d
    falsch = con.execute(f"""select count(*) from (
        select kette_id, min(min_konfidenz) a, min(konfidenz_zum_vorgaenger) b
        from {K} group by 1) where a is not null and b is not null and abs(a-b) > 0.001""").fetchone()[0]
    assert falsch == 0, f"{falsch} Ketten melden ein anderes Minimum als ihr schwächstes Glied"


def test_ketten_haben_mindestens_zwei_glieder():
    d = _kette()
    if not d:
        return
    con, K = d
    assert con.execute(f"select count(*) from {K} where n_glieder < 2").fetchone()[0] == 0
    luecken = con.execute(f"""select count(*) from (
        select kette_id, count(*) n, max(position) p from {K} group by 1) where n <> p""").fetchone()[0]
    assert luecken == 0, f"{luecken} Ketten haben Lücken in der Positionsfolge"


# ── Ausliefergut ────────────────────────────────────────────────────────────────────────

def test_die_zahlen_stimmen_mit_der_gegenprobe():
    """⚠ Gegen die unabhängig gemessenen Werte gehalten: 2022 (Rückverweis-Ära) ≈ 43.113
    vollständige Vorgänge, 2024 (eForms-Ära) ≈ 48.926. Bricht der Schlüssel an einer der
    beiden Stellen, fällt eine der Zahlen ein."""
    d = _gold()
    if not d:
        return
    con, V = d
    for jahr, erwartet in ((2022, 43113), (2024, 48926), (2025, 48839)):
        n = con.execute(f"""select count(*) from {V}
            where vollstaendig and year(erste_veroeffentlichung) = {jahr}""").fetchone()[0]
        assert 0.85 * erwartet <= n <= 1.15 * erwartet, \
            f"{jahr}: {n:,} vollständige Vorgänge, erwartet ~{erwartet:,}"


def test_unterlagen_haengen_am_vorgang():
    """Ohne diese Spalten sagt die Akte nicht, ob sie ihre dritte Schicht hat."""
    d = _gold()
    if not d:
        return
    con, V = d
    r = con.execute(f"""select count(*) filter (where hat_unterlagen) mit,
        sum(n_dokumente) dok, sum(n_anforderungen) anf from {V}""").fetchone()
    assert r[0] > 0 and r[1] > 0 and r[2] > 0, "keine Unterlagen an Vorgängen"
    leer = con.execute(f"select count(*) from {V} where hat_unterlagen and n_dokumente = 0").fetchone()[0]
    assert leer == 0, f"{leer} Vorgänge melden Unterlagen ohne Dokumente"


def test_vollstaendig_heisst_beides():
    d = _gold()
    if not d:
        return
    con, V = d
    falsch = con.execute(f"""select count(*) from {V}
        where vollstaendig and (n_ausschreibung = 0 or n_zuschlag = 0)""").fetchone()[0]
    assert falsch == 0

"""Vorgangsakten — was der Export in eine Akte legt und was er bewusst weglässt.

Drei Eigenschaften sind teuer erkauft und dürfen nicht still zurückfallen:
der Verlauf fasst gleiche Ereignisse eines Tages zusammen, das Kettenfenster hält die
Dateigrösse linear statt quadratisch, und die Ereignisarten sind die ECHTEN Werte aus
`vorgang_notice.notice_kind` und nicht die Namen der Zählspalten.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import date
import re
from pathlib import Path

import pytest


def _ohne_kommentare_py(quelle: str) -> str:
    """Python-Quelltext ohne Docstrings — dieselbe Falle wie unten, andere Sprache."""
    import ast
    baum = ast.parse(quelle)
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef, ast.Module)) and ast.get_docstring(knoten):
            knoten.body = knoten.body[1:]
    return ast.unparse(baum)


def _ohne_kommentare(quelle: str) -> str:
    """TS-Quelltext ohne Kommentare.

    ⚠ SONST PRUEFT DER TEST DIE BEGRUENDUNG STATT DES CODES. Genau hier stand
    `// ⚠ NICHT 404. Ein Lead ohne Akte ist der Normalfall …` — der Kommentar, der die
    geforderte Eigenschaft ERKLAERT, liess den Test fallen, der sie sichert. Dieselbe Falle
    hat am 2026-09-02 vier Tests erwischt.
    """
    quelle = re.sub(r"/\*.*?\*/", "", quelle, flags=re.S)
    return re.sub(r"//[^\n]*", "", quelle)

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_vorgaenge.py"


def _modul():
    spec = importlib.util.spec_from_file_location("_va", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _modul()


# ── Ereignisarten ───────────────────────────────────────────────────────────────────

def test_arten_decken_das_echte_vokabular():
    """Der erste Lauf setzte hier die Namen der Zählspalten (`ausschreibung`, `zuschlag`).

    `notice_kind` führt aber `cn`, `can`, `corrigendum`, `pin`, `other` — die Ansicht hätte
    also „cn" angezeigt. Der Test hält beide Vokabulare auseinander.
    """
    assert set(M.ARTEN) == {"cn", "can", "corrigendum", "pin", "other"}
    assert M.ARTEN["cn"] == "Ausschreibung"
    assert M.ARTEN["can"] == "Zuschlag"
    for spaltenname in ("ausschreibung", "zuschlag", "korrektur", "vorinfo"):
        assert spaltenname not in M.ARTEN


def test_unbekannte_art_faellt_nicht_weg():
    """Eine neue Art aus einer neuen Quelle darf im Verlauf stehen, roh statt gar nicht."""
    v = M._verlauf([{"notice_id": "a", "notice_kind": "wasneues",
                     "veroeffentlicht": date(2025, 1, 1), "hat_unterlagen": False}])
    assert len(v) == 1 and v[0]["label"] == "wasneues"


# ── Verlauf ─────────────────────────────────────────────────────────────────────────

def _bm(nid, kind, tag, unterlagen=False, dublette=False):
    return {"notice_id": nid, "notice_kind": kind, "dublette": dublette,
            "veroeffentlicht": date(2025, 1, tag), "hat_unterlagen": unterlagen}


def test_gleiche_art_am_gleichen_tag_wird_ein_eintrag():
    v = M._verlauf([_bm("k1", "corrigendum", 5), _bm("k2", "corrigendum", 5),
                    _bm("k3", "corrigendum", 9)])
    assert [e["n"] for e in v] == [2, 1]
    assert v[0]["ids"] == ["k1", "k2"]


def test_verschiedene_arten_am_gleichen_tag_bleiben_getrennt():
    """Sonst verschwindet die eine Ausschreibung unter den Korrekturen desselben Tages."""
    v = M._verlauf([_bm("a", "cn", 5), _bm("k", "corrigendum", 5)])
    assert {e["art"] for e in v} == {"cn", "corrigendum"}


def test_verlauf_ist_zeitlich_geordnet():
    v = M._verlauf([_bm("z", "can", 20), _bm("a", "cn", 3), _bm("k", "corrigendum", 11)])
    assert [e["datum"] for e in v] == ["2025-01-03", "2025-01-11", "2025-01-20"]


def test_unterlagen_stehen_am_eintrag_nicht_nur_oben():
    """Eine Akte von 2015 hat Bekanntmachungen, aber fast nie Dateien. Die Ansicht muss
    sehen können, an WELCHEM Ereignis Unterlagen hängen, nicht nur dass es welche gibt."""
    v = M._verlauf([_bm("a", "cn", 5, unterlagen=True), _bm("z", "can", 20)])
    assert v[0]["unterlagen"] is True and v[1]["unterlagen"] is False


def test_ohne_datum_stuerzt_nicht_ab():
    v = M._verlauf([{"notice_id": "x", "notice_kind": "cn",
                     "veroeffentlicht": None, "hat_unterlagen": False}])
    assert v[0]["datum"] is None


# ── Kettenfenster ───────────────────────────────────────────────────────────────────

def _kette(n):
    return [{"vorgang": f"v{i}", "position": i, "jahr": 2000 + i, "konfidenz": 0.8}
            for i in range(1, n + 1)]


def test_kurze_kette_bleibt_vollstaendig():
    assert len(M._fenster(_kette(5), 3)) == 5


def test_lange_kette_wird_gefenstert():
    """Die längste echte Kette hat 435 Glieder. Ohne Fenster schreibt der Export 435 Titel
    in 435 Dateien — 189.225 Kopien für EINE Kette, und der erste Lauf kam so auf 153 MB."""
    f = M._fenster(_kette(435), 200)
    assert len(f) == M.KETTE_FENSTER


def test_fenster_enthaelt_die_eigene_position():
    for pos in (1, 2, 50, 200, 434, 435):
        f = M._fenster(_kette(435), pos)
        assert any(g["position"] == pos for g in f), f"Position {pos} fehlt im eigenen Fenster"


def test_fenster_wandert_am_rand_nach_innen():
    """Wer an Position 1 steht, will die Nachfolger sehen, nicht leere Plätze davor."""
    f = M._fenster(_kette(435), 1)
    assert len(f) == M.KETTE_FENSTER
    assert f[0]["position"] == 1
    f = M._fenster(_kette(435), 435)
    assert len(f) == M.KETTE_FENSTER and f[-1]["position"] == 435


def test_fenster_haelt_die_reihenfolge():
    f = M._fenster(_kette(100), 50)
    assert [g["position"] for g in f] == sorted(g["position"] for g in f)


def test_fenster_kopiert_statt_zu_verbiegen():
    """Die Glieder werden nachträglich um `titel` ergänzt. Ohne Kopie schreibt die Akte an
    Position 2 ihre Titel in dieselben Objekte, die die Akte an Position 3 gleich nutzt."""
    quelle = _kette(5)
    f = M._fenster(quelle, 2)
    f[0]["titel"] = "angefasst"
    assert "titel" not in quelle[0]


# ── Datumsformat ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("roh,erwartet", [
    (date(2025, 8, 8), "2025-08-08"),
    ("2025-08-08 00:00:00", "2025-08-08"),   # so kommt es über .df() zurück
    ("2025-08-08", "2025-08-08"),
    (None, None),
])
def test_tag_vereinheitlicht(roh, erwartet):
    """Dieselbe Spalte kam über `.df()` als Timestamp und über `fetchall()` als `date` —
    der erste Lauf hatte beide Formen in EINER Akte."""
    assert M._tag(roh) == erwartet


# ── Dateiname ───────────────────────────────────────────────────────────────────────

def test_dateiname_trennt_was_eine_saeuberung_verschmelzen_wuerde():
    """`folder:ab-1` und `folder:ab1` wären nach `[^A-Za-z0-9_-]` → "" derselbe Dateiname,
    und die eine Akte überschriebe die andere lautlos."""
    assert M.dateiname("DE", "folder:ab-1") != M.dateiname("DE", "folder:ab1")


def test_dateiname_trennt_die_laender():
    """⚠ Die Vorgangsnummer allein ist NICHT weltweit eindeutig: 48 Nummern kommen in mehr
    als einem Land vor (AT∩DE 31, CH∩DE 9, DE∩PL 4). Ohne das Land im Schlüssel überschreibt
    die österreichische Akte die deutsche, lautlos."""
    assert M.dateiname("AT", "pub:12345-2020") != M.dateiname("DE", "pub:12345-2020")


def test_dateiname_stimmt_mit_dem_frontend_ueberein():
    """Muss identisch zu `web/lib/vorgangsakte.ts` sein — sonst sucht die Route Dateien,
    die der Export nie geschrieben hat."""
    ts = (WURZEL / "web" / "lib" / "vorgangsakte.ts").read_text(encoding="utf-8")
    assert "`${land}:${id}`" in ts, "Frontend hasht ohne Land"
    assert f"BUENDEL_STELLEN = {M.BUENDEL_STELLEN};" in ts, \
        "Buendelbreite laeuft zwischen Export und Frontend auseinander"
    assert M.dateiname("DE", "folder:x") == \
        __import__("hashlib").sha1(b"DE:folder:x").hexdigest()


def test_alle_laender_mit_vorgaengen_werden_gebaut():
    """⚠ Der erste Entwurf hatte `--land DE` als Vorgabe und der Tageslauf rief ihn ohne
    Argument. AT (14.245) und CH (3.533) wären nie exportiert worden, ohne dass irgendetwas
    rot geworden wäre. Deutschland ist der Testfall, nicht der Geltungsbereich."""
    quelle = SKRIPT.read_text(encoding="utf-8")
    kern = quelle.split("def _laender(")[1].split("def main(")[0]
    assert "vorgaenge.parquet" in kern and "iterdir()" in kern
    assert 'ap.add_argument("--land", default=None' in quelle


def test_ein_land_ohne_treffer_bricht_den_lauf_nicht_ab():
    """PL hat Vorgänge in Gold, aber keinen sichtbaren Lead. Der erste Lauf starb dort —
    NACHDEM er DE fertig hatte, und hinterliess die Akten aller Länder ungeschrieben."""
    con = __import__("duckdb").connect()
    assert M._menge(con, "DE", set()) == set()


def test_alle_laender_erst_sammeln_dann_schreiben():
    """`schreibe` räumt weg, was nicht in der übergebenen Menge steht. Je Land zu schreiben
    hiesse, dass das zweite Land die Akten des ersten löscht — und der Lauf sähe dabei
    erfolgreich aus."""
    quelle = _ohne_kommentare_py(SKRIPT.read_text(encoding="utf-8"))
    kern = quelle.split("def main(")[1]
    schleife = kern.split("for land in _laender(")[1].split("mit_dok")[0]
    assert "schreibe(" not in schleife, "schreibe() steht in der Laenderschleife"


# ── Was der Export ueber sich selbst sagen muss ─────────────────────────────────────

def test_export_nennt_die_duenne_dokumentendeckung():
    """Der Dokumentenschenkel liegt bei 0,6 % und wird nur nach vorn dichter. Ein Skript,
    das das nicht sagt, lädt zur Fehldeutung ein, die Akte sei kaputt."""
    quelle = SKRIPT.read_text(encoding="utf-8")
    assert "0,6 %" in quelle and "August 2026" in quelle


def test_produktmenge_kommt_nicht_aus_lead_export():
    """`lead_export.parquet` führt 90.272 Leads, der Explorer zeigt 42.678. Der erste Lauf
    baute Akten für 48.000 Vergaben, die im Produkt niemand aufrufen kann."""
    quelle = SKRIPT.read_text(encoding="utf-8")
    kern = quelle.split("def _menge(")[1].split("def ")[0]
    assert "lead_export" not in kern
    assert "_sichtbare_leads()" in quelle.split("def main(")[1]


# ── Die Schranke ────────────────────────────────────────────────────────────────────

def test_vorgang_bleibt_hinter_der_anmeldung():
    """Die Akte ist ein Pro-Merkmal und darf nicht in `OFFEN` stehen.

    ⚠ WARUM ALS TEST UND NICHT ALS VORSATZ. Diese Ansicht laesst sich ohne Anmeldung nicht
    pruefen; beim Bauen am 2026-09-02 stand `/vorgang` deshalb zeitweise in `OFFEN`, damit
    der Browser sie zeigt. So eine Zeile zurueckzunehmen ist eine Gedaechtnisleistung, und
    genau die faellt aus, wenn dazwischen etwas anderes passiert. Der Test erledigt es.
    """
    mw = (WURZEL / "web" / "middleware.ts").read_text(encoding="utf-8")
    offen = mw.split("const OFFEN = [")[1].split("];")[0]
    assert '"/vorgang"' not in offen
    assert '"/api/vorgang"' not in offen


def test_route_trennt_fehlend_von_nicht_geladen():
    """Ohne die Trennung sieht ein fehlender Datenspeicher aus wie ein leeres Ergebnis —
    derselbe Vorfall, nach dem `/api/firma` seine 503 bekommen hat."""
    route = (WURZEL / "web" / "app" / "api" / "vorgang" / "route.ts").read_text(encoding="utf-8")
    assert "503" in route and "vorgangBestand" in route


def test_lead_ohne_akte_ist_kein_fehler():
    """Aufbereitet sind 36.000 von 1,47 Mio. Vorgaengen. Ein Lead ohne Akte ist damit der
    Normalfall ausserhalb der Menge; eine 404 daraus zu machen, faerbt die Detailansicht
    bei jedem zweiten Klick rot."""
    route = (WURZEL / "web" / "app" / "api" / "vorgang" / "route.ts").read_text(encoding="utf-8")
    kern = _ohne_kommentare(route).split("if (!id && lead) {")[1].split("if (!ID_RE")[0]
    assert "vorhanden: false" in kern and "404" not in kern


def test_buendel_statt_einzeldateien():
    """⚠ 53.872 Einzeldateien liessen `next build` im Node-Heap sterben (SIGABRT, Stapel in
    `node::fs::AfterStat`): Next geht beim Bauen den Projektbaum ab, und mit `firma/` und
    `doc-analysis/` zusammen standen rund 156.000 Dateien unter `web/data`.

    Eine Sammeldatei ist aber genauso falsch — daran ist `firma-profiles.json` gescheitert
    (67 MB laden, um 1,6 KB zu liefern). 256 Bündel liegen dazwischen.
    """
    quelle = SKRIPT.read_text(encoding="utf-8")
    kern = quelle.split("def schreibe(")[1]
    assert "buendel" in kern.lower()
    assert 16 ** M.BUENDEL_STELLEN == 256


def test_geschriebenes_json_ist_gueltiges_json():
    """⚠ `json.dumps` schreibt für `float('nan')` das nackte `NaN` — gültiges Python,
    ungültiges JSON. Am 2026-09-02 standen so 256 gültig aussehende Bündel auf der Platte,
    die der Browser nicht lesen konnte (`"cpv": NaN`). Der Export meldete Erfolg, die Tests
    waren grün, und der Fehler tauchte erst beim Lesen auf, weit weg von seiner Ursache.

    `allow_nan=False` verschiebt ihn dorthin, wo der Wert entsteht.
    """
    quelle = SKRIPT.read_text(encoding="utf-8")
    assert "allow_nan=False" in quelle
    # Ohne das Strippen prueft der Test die WARNUNG vor `.df()` statt ihrer Abwesenheit —
    # dieselbe Falle, die heute schon fuenf Tests erwischt hat.
    assert ".df()" not in _ohne_kommentare_py(quelle), \
        "pandas macht aus fehlenden Werten wieder NaN"


def test_buendel_auf_der_platte_sind_lesbar():
    """Prüft die tatsächliche Ausgabe, nicht die Absicht. `NaN` und `Infinity` kommen durch
    `json.loads` normalerweise unbeanstandet durch — `parse_constant` fängt sie ab."""
    import glob
    import json as _json
    dateien = sorted(glob.glob(str(WURZEL / "web" / "data" / "vorgang" / "*.json")))
    if not dateien:
        pytest.skip("noch kein Export gelaufen")
    def _knall(c):
        raise ValueError(f"{c} ist kein JSON")
    for weg in dateien[:24]:
        with open(weg, encoding="utf-8") as f:
            _json.loads(f.read(), parse_constant=_knall)


# ── Güte der Kette ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mk,erwartet", [
    (0.95, "belastbar"), (0.80, "belastbar"),
    (0.79, "plausibel"), (0.70, "plausibel"),
    (0.69, "schwach"), (0.55, "schwach"), (0.0, "schwach"),
    (None, None),
])
def test_guete_baender(mk, erwartet):
    assert M._guete(mk) == erwartet


def test_guete_folgt_dem_schwaechsten_glied():
    """Eine Kette ist so belastbar wie ihr schwächstes Glied, deshalb entscheidet das
    Minimum. Ein Durchschnitt verwischt genau den Fall, um den es geht: vier gute
    Verknüpfungen und eine geratene sähen darin aus wie fünf mittelmässige."""
    quelle = _ohne_kommentare_py(SKRIPT.read_text(encoding="utf-8"))
    assert "min_konfidenz" in quelle.split("def _guete(")[1].split("def ")[0] \
        or 'kk["min_konfidenz"]' in quelle


def test_baender_stehen_in_den_daten_nicht_im_renderer():
    """Sonst kennt die Anzeige eine Schwelle, die der Export nicht kennt, und beide laufen
    beim nächsten Anfassen auseinander. Dieselbe Regel wie bei `export_schwellen.py`."""
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    kern = _ohne_kommentare(tsx)
    for zahl in ("0.8", "0.80", "0.7", "0.70", "0.55"):
        assert f"guete >= {zahl}" not in kern and f"konfidenz < {zahl}" not in kern, \
            f"Schwelle {zahl} steht in der Anzeige statt im Export"
    assert 'a.kette?.guete ? GUETE[a.kette.guete]' in kern


def test_jedes_band_hat_einen_eigenen_satz():
    """Drei Bänder und ein Satz für alle wären dasselbe Problem in neu."""
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    block = tsx.split("const GUETE:")[1].split("};")[0]
    # `satz: "` mit Anfuehrungszeichen — sonst zaehlt die Typzeile `satz: string` mit.
    saetze = [z.strip() for z in block.splitlines() if 'satz: "' in z]
    assert len(saetze) == 3 and len(set(saetze)) == 3


def test_duennes_glied_wird_am_glied_markiert():
    """Die Kette kann an genau EINER Stelle dünn sein, und dann will man wissen, an welcher."""
    quelle = SKRIPT.read_text(encoding="utf-8")
    assert "GLIED_DUENN" in quelle
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    assert "g.duenn" in tsx


def test_schwache_kette_ohne_sichtbares_glied_sagt_es():
    """⚠ Das schwächste Glied kann ausserhalb des Kettenfensters liegen: gemessen 271 Fälle.
    Ohne diesen Hinweis widerspricht sich die Seite, oben „schwach" und unten kein einziges
    markiertes Glied."""
    quelle = SKRIPT.read_text(encoding="utf-8")
    assert "duennes_glied_sichtbar" in quelle
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    assert "duennes_glied_sichtbar" in tsx


# ── Der Vorgaenger ist nicht die Zeile darueber ─────────────────────────────────────

def test_kette_traegt_ihren_vorgaenger():
    """⚠ `vorgang_kette` speicherte bis zum 2026-09-02 NICHT, wer der Vorgänger ist. Die
    Anzeige musste ihn also raten, und sie riet die Zeile darüber. Gemessen: 70.521 der
    120.737 angezeigten Glieder (58 %) folgen NICHT auf die Zeile darüber, weil Nachfolger
    verzweigen und mehrere Vergaben denselben Vorgänger haben können."""
    bau = (WURZEL / "scripts" / "build_vorgaenge.py").read_text(encoding="utf-8")
    assert "vorgaenger VARCHAR" in bau
    quelle = SKRIPT.read_text(encoding="utf-8")
    assert "anschluss_direkt" in quelle and "vorgaenger_jahr" in quelle


def test_anzeige_behauptet_keine_nachbarschaft():
    """Ein Vermerk, der stillschweigend die Zeile darüber meint, sagt in der Mehrzahl der
    Fälle etwas Falsches. Er muss den Vorgänger benennen oder schweigen."""
    tsx = _ohne_kommentare(
        (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8"))
    assert "g.anschluss_direkt" in tsx and "g.wurzel" in tsx
    assert "hier dünn" not in tsx, "alter Wortlaut behauptet Nachbarschaft"


def test_position_ist_ein_zeitrang_kein_kettenrang():
    """Die Sortierung nach Jahr ist Absicht (eine Ansicht will einen Zeitstrahl), aber sie
    darf nicht als Kettenreihenfolge gelesen werden. In 3.189 Fällen sitzt die Wurzel
    mitten in der Kette, weil die erschlossene Nachfolge rückwärts in der Zeit zeigt."""
    bau = (WURZEL / "scripts" / "build_vorgaenge.py").read_text(encoding="utf-8")
    assert "position` IST EIN ZEITRANG" in bau


def test_herkunft_widerspricht_der_kette_nicht():
    """⚠ „einzeln, keine Verknüpfung gefunden" stand bei 6.048 Akten direkt über einer
    Vorgeschichte mit mehreren Gliedern. Der Vermerk meint die Bekanntmachungen DIESES
    Vorgangs, die Kette die Nachfolge zwischen Vorgängen."""
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    block = tsx.split("const HERKUNFT:")[1].split("};")[0]
    assert "keine Verknüpfung gefunden" not in block
    assert "nur eine Bekanntmachung" in block


# ── Warum keine Unterlagen da sind ──────────────────────────────────────────────────

def _akte(dokumente=(), unterlagen=False, bis="2026-08-26"):
    return {"dokumente": list(dokumente), "bis": bis,
            "verlauf": [{"unterlagen": unterlagen}]}


def test_grund_entfaellt_wenn_dateien_da_sind():
    assert M._unterlagen_grund(_akte(dokumente=[{"n": 3}])) is None


def test_angekuendigt_schlaegt_das_datum():
    """Wenn die Vergabe Unterlagen ausweist, ist das der Grund, egal wie alt sie ist."""
    assert M._unterlagen_grund(_akte(unterlagen=True, bis="2015-01-01")) == "angekuendigt"


def test_alt_bekommt_die_alterserklaerung():
    assert M._unterlagen_grund(_akte(bis="2015-01-01")) == "vor_abrufstart"


def test_neu_bekommt_NICHT_die_alterserklaerung():
    """⚠ Der erste Entwurf schob eine fehlende Dateiliste IMMER aufs Alter und sagte einer
    Vergabe vom 26.08.2026, ältere Vorgänge trügen deshalb selten Dateien. Gemessen am
    2026-09-02: 7.453 Akten bekamen so eine Erklärung, die auf sie nicht zutrifft."""
    assert M._unterlagen_grund(_akte(bis="2026-08-26")) == "kein_abruf"
    assert M._unterlagen_grund(_akte(bis="2026-12-01")) == "kein_abruf"


def test_grenze_ist_der_abrufstart():
    assert M._unterlagen_grund(_akte(bis=M.ABRUF_START)) == "kein_abruf"
    assert M._unterlagen_grund(_akte(bis="2026-07-31")) == "vor_abrufstart"


def test_anzeige_raet_den_grund_nicht():
    """Der Grund kommt aus dem Export. Eine Anzeige, die ihn selbst herleitet, kennt eine
    Regel, die der Export nicht kennt."""
    tsx = _ohne_kommentare(
        (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8"))
    assert "a.unterlagen_grund" in tsx
    assert "verlauf.some" not in tsx, "Anzeige leitet den Grund wieder selbst her"


def test_jeder_grund_hat_einen_eigenen_satz():
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    for satz in ("Unterlagen holen wir erst seit August 2026 ein",
                 "Nicht jedes Portal gibt eine Liste der Unterlagen ohne Anmeldung heraus",
                 "Diese Vergabe weist Unterlagen aus"):
        assert satz in tsx


# ── Vierte Stufe: heimatlose Zuschlaege ─────────────────────────────────────────────

BAU = (WURZEL / "scripts" / "build_vorgaenge.py").read_text(encoding="utf-8")


def test_andocken_ist_nicht_transitiv():
    """⚠ „gleicher Käufer + gleicher Titel + Zeitfenster" als Verschmelzung wird TRANSITIV:
    A passt zu B, B zu C, C zu D. Über ein gleitendes Halbjahresfenster entstanden dabei
    Gruppen von 630, 533 und 462 Vorgängen — ein Jahrzehnt „d-münchen: gebäudereinigung" in
    einer Akte. Kandidaten hängen sich an Ziele, Ziele nie aneinander."""
    kern = _ohne_kommentare_py(BAU).split("def _andocken(")[1].split("\ndef ")[0]
    assert "union" not in kern.lower() and "find(" not in kern


def test_eigene_folderid_ist_ein_veto():
    """Trägt der Kandidat eine amtliche Verfahrenskennung, hat der Auftraggeber selbst
    gesagt, dass es ein anderes Verfahren ist. Eine Schätzung darf das nicht überstimmen."""
    kern = _ohne_kommentare_py(BAU).split("def _andocken(")[1].split("\ndef ")[0]
    # ast.unparse normalisiert Anfuehrungszeichen — beide Formen zulassen.
    assert 'beste == "folder"' in kern or "beste == 'folder'" in kern


def test_mehrdeutiges_bleibt_liegen():
    """Ein falsches Zusammenlegen behauptet eine Einheit, die es nicht gibt, und ist teurer
    als ein verpasstes. 47.546 Kandidaten bleiben deshalb bewusst liegen."""
    kern = _ohne_kommentare_py(BAU).split("def _andocken(")[1].split("\ndef ")[0]
    assert "len(passend) == 1" in kern


def test_kandidat_hat_keine_eigene_ausschreibung():
    """Zwei Vorgänge mit je eigener Ausschreibung sind zwei Vergaben. Genau daran hängt die
    Unterscheidung zwischen Bruchstück und jährlicher Wiederausschreibung: „D-Dresden:
    Auftausalz" laeuft 2004 bis 2008 jedes Jahr mit eigener Ausschreibung UND eigenem
    Zuschlag und darf NICHT zusammenfallen."""
    kern = _ohne_kommentare_py(BAU).split("def _andocken(")[1].split("\ndef ")[0]
    assert "cn > 0 or n != 1" in kern


def test_kaeufer_kommt_aus_dem_laufenden_durchgang():
    """⚠ Der erste Entwurf las den Käufer über `vorgang_notice.parquet` — die AUSGABE des
    vorherigen Laufs. Nach jeder Änderung am Schlüssel hätte die Stufe stumm ins Leere
    gegriffen."""
    kern = _ohne_kommentare_py(BAU).split("def _andocken(")[1].split("\ndef ")[0]
    assert "vorgang_notice" not in kern
    assert "zeilen_n" in kern


def test_angedocktes_wird_ausgewiesen():
    """Über Käufer und Titel zugeordnet ist erschlossen, nicht amtlich. Wie bei der Kette
    gehört das an die Oberfläche und nicht nur in die Tabelle."""
    assert "n_angedockt BIGINT" in BAU
    assert '"angedockt"' in SKRIPT.read_text(encoding="utf-8")
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    assert "z.angedockt" in tsx


def test_laender_ohne_party_entity_werden_benannt():
    """PL und EU führen keine `party_entity` — dort greift die Stufe nicht. Das ist eine
    Lücke, keine Eigenschaft, und muss im Lauf sichtbar sein statt still zu bleiben."""
    kern = BAU.split("def _andocken(")[1].split("\ndef ")[0]
    assert "Andocken uebersprungen" in kern


def test_kein_gezaehlter_satz_ohne_einzahlfassung():
    """⚠ ZWEIMAL DERSELBE FEHLER AN EINEM TAG: erst „1 Bekanntmachungen", dann
    „1 Zuschläge". Jeder Satz mit einem gezählten Platzhalter braucht eine Einzahlfassung,
    sonst schreibt die Seite bei genau einem Element falsches Deutsch.

    Geprüft werden Sätze, die mit `{n} ` beginnen und auf ein Mehrzahl-Wort enden — die
    Form, in der der Fehler beide Male auftrat."""
    import re
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    gezaehlt = re.findall(r't\("(\{n\} [^"]+)"', tsx)
    # Zulaessig ist eine Einzahlfassung (`=== 1 ?`) ODER ein Waechter, der die Eins gar
    # nicht erst durchlaesst (`> 1 ?`) — beides verhindert „1 Zuschläge".
    ohne = [k for k in gezaehlt
            if "=== 1" not in (v := tsx.split(f't("{k}"')[0][-300:]) and "> 1" not in v]
    assert not ohne, "gezählte Sätze ohne Einzahlfassung: " + repr(ohne)


# ── Worauf die Vollstaendigkeit ruht ────────────────────────────────────────────────

def test_vollstaendigkeit_sagt_worauf_sie_ruht():
    """⚠ 62.795 Akten (9,7 % aller vollständigen) sind es NUR, weil `_andocken` ihren
    Zuschlag über Käufer und Titel zugeordnet hat. Eine grüne Plakette „Ausschreibung und
    Zuschlag vorhanden" behauptet dort eine Tatsache, wo eine Schätzung steht — derselbe
    Fehler, den die Kette und die Unterlagen schon hinter sich haben, eine Ebene höher."""
    quelle = SKRIPT.read_text(encoding="utf-8")
    assert '"vollstaendig_beleg"' in quelle
    tsx = _ohne_kommentare(
        (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8"))
    assert 'a.vollstaendig_beleg === "erschlossen"' in tsx
    # Die gruene Plakette darf NUR am amtlich belegten Zweig haengen.
    gruen = tsx.split('vg-tag ok">{t("Ausschreibung und Zuschlag vorhanden")')[0][-400:]
    assert "erschlossen" in gruen, "gruene Plakette haengt nicht hinter der Belegpruefung"


def test_beleg_ist_null_wenn_unvollstaendig():
    """Ein Beleg für etwas, das nicht behauptet wird, waere ein Widerspruch in der Akte."""
    quelle = SKRIPT.read_text(encoding="utf-8")
    kern = quelle.split('"vollstaendig_beleg": (')[1].split("),")[0]
    assert 'None if not k.get("vollstaendig")' in kern


# ── Zweitmeldungen derselben Vergabe ────────────────────────────────────────────────

def test_nur_der_starke_beleg_zaehlt():
    """`nur_titel`, `nur_titel_kurz` und `geschwister` sind schwächere Indizien.
    `export_web_leads.py` traut aus demselben Grund nur `kaeufer_und_titel`."""
    assert 'DUBLETTEN_BELEG = "kaeufer_und_titel"' in BAU
    kern = _ohne_kommentare_py(BAU).split("def _dubletten(")[1].split("\ndef ")[0]
    assert "DUBLETTEN_BELEG" in kern


def test_nur_wenn_der_master_in_derselben_akte_liegt():
    """⚠ Gemessen am 2026-09-02: von den belegten Dubletten hat nur ein Teil den Master in
    derselben Akte (DE 1.545 von 20.786, AT 404 von 50.481, CH 5.930 von 10.800). Bei allen
    übrigen steht der Master in einem ANDEREN Vorgang; dort ist die Zweitmeldung das
    einzige, was diese Vergabe in dieser Akte belegt. Sie zu entwerten liesse eine
    Bekanntmachung verschwinden, die nichts ersetzt."""
    kern = _ohne_kommentare_py(BAU).split("def _dubletten(")[1].split("\ndef ")[0]
    assert "vorgang_von.get(x) == vorgang_von.get(m)" in kern


def test_wer_selbst_master_ist_wird_nicht_entwertet():
    """456 Bekanntmachungen in DE stehen in der einen Zeile als Duplikat und in der
    nächsten als Master. Ohne die Sperre könnte eine Akte beide Seiten verlieren."""
    kern = _ohne_kommentare_py(BAU).split("def _dubletten(")[1].split("\ndef ")[0]
    assert "if x in master:" in kern


def test_markiert_statt_geloescht():
    """Die Regel der Firewall selbst. Wer die Zweitmeldung wegwirft, verliert die Spur zur
    zweiten Quelle — und genau die belegt, dass wir beide Portale gelesen haben."""
    assert "dublette BOOLEAN" in BAU
    quelle = SKRIPT.read_text(encoding="utf-8")
    # Sie bleibt in den sichtbaren Kennungen des Verlaufseintrags stehen.
    kern = quelle.split("def _verlauf(")[1].split("\ndef ")[0]
    assert '"ids": sorted(t["notice_id"] for t in gruppe)' in kern
    assert '"dubletten": sum(' in kern


def test_verlaufseintrag_zaehlt_ohne_zweitmeldungen():
    """Daran hingen im Zürcher Beispiel sieben Zuschläge für sechs Lose."""
    kern = SKRIPT.read_text(encoding="utf-8").split("def _verlauf(")[1].split("\ndef ")[0]
    assert 'sum(1 for t in gruppe if not t.get("dublette"))' in kern


def test_dubletten_stehen_in_der_akte():
    tsx = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    assert "e.dubletten" in tsx


def test_fehlendes_dublettenkennzeichen_haelt_den_export_nicht_an():
    """Ein Verlaufseintrag ohne das Feld ist keine Zweitmeldung, kein Absturz."""
    v = M._verlauf([{"notice_id": "x", "notice_kind": "cn",
                     "veroeffentlicht": date(2025, 1, 5), "hat_unterlagen": False}])
    assert v[0]["n"] == 1 and v[0]["dubletten"] == 0


def test_zweitmeldung_zaehlt_nicht_als_ereignis():
    v = M._verlauf([_bm("a", "can", 5), _bm("b", "can", 5), _bm("c", "can", 5, dublette=True)])
    assert v[0]["n"] == 2 and v[0]["dubletten"] == 1
    assert "c" in v[0]["ids"], "die Zweitmeldung muss sichtbar bleiben"

"""cosinex-VMP-Connector: Trefferzeilen-Parser und Bronze→Silber-Mapping.

Die HTML-Ausschnitte sind aus den echten Seiten von vergabe.rlp.de und
vergabemarktplatz.brandenburg.de gekürzt — nicht nachgebaut. Nachgebaute Fixtures
prüfen die eigene Vorstellung vom Markup, nicht das Markup.
"""

import json

import pandas as pd
import pytest

from govisor import cosinex

# Eine echte Trefferzeile (RLP, gekürzt). Sie enthält die vier Fallen auf einmal:
#   * das Datum steht nur im sichtbaren Text, der ZEITPUNKT im ``abbr title``
#   * Vergabeordnung und Typ teilen sich EINE Zelle, getrennt durch <br>
#   * der Typ steht als Kürzel im Text und ausgeschrieben im ``abbr title``
#   * die pid hängt am Link der letzten Zelle, nicht am Titel
_ZEILE_RLP = """
<tr class="odd">
 <td style="text-align: center;"><abbr title='26.07.2026 um 10:50 Uhr'>26.07.2026 </abbr></td>
 <td style="text-align: center;"><abbr title='25.08.2026 um 10:00 Uhr'>25.08.2026 </abbr></td>
 <td class="word-break">Munitionsdepot Kriegsfeld - Baustromversorgung</td>
 <td>VSVgV<br /><abbr title="Teilnahmewettbewerb">TNW</abbr></td>
 <td>Landesbetrieb Liegenschafts- u. Baubetreuung</td>
 <td><a href="https://www.vergabe.rlp.de/VMPCenter/public/company/projectForwarding.do?pid=59717"
        target="_blank"><img src="/VMPCenter/images/icons/action_to_projectroom.gif"></a></td>
</tr>
"""

# Ein vergebener Auftrag ohne Frist. ``nv`` heisst „nicht vorhanden" und darf kein Datum
# werden — bei NetServer hat genau so ein Rückfall einmal die Frist als Veröffentlichung
# gesetzt und Jahr/Monat der Notice verschoben.
_ZEILE_OHNE_FRIST = """
<tr>
 <td style="text-align: center;"><abbr title='13.08.2026 um 09:12 Uhr'>13.08.2026 </abbr></td>
 <td style="text-align: center;">nv</td>
 <td class="word-break">Rueckbau Betonplatte Denkmal Freiherr vom Stein</td>
 <td>VOB/A<br /><abbr title="Vergebener Auftrag">Vergebener Auftrag</abbr></td>
 <td>LBB NL Koblenz</td>
 <td><a href="/VMPCenter/public/company/projectForwarding.do?pid=60001"></a></td>
</tr>
"""

# Layout-Zeile ohne pid — darf NICHT als Vorgang zählen.
_ZEILE_LAYOUT = """
<tr><td>Veröffentlicht</td><td>Frist</td><td>Kurzbezeichnung</td><td>Typ</td><td>Stelle</td></tr>
"""

_UEBERBLICK = """
<table><tbody>
 <tr><td><a href="/VMPCenter/company/announcements/categoryOverview.do?method=showTable&amp;cpvCode=45000000-7">
     <span aria-hidden="true">Bauarbeiten</span></a></td>
     <td style="text-align: right;"><span> 929</span></td></tr>
 <tr><td><a href="/VMPCenter/company/announcements/categoryOverview.do?method=showTable&amp;cpvCode=72000000-5">
     <span aria-hidden="true">IT-Dienste</span></a></td>
     <td style="text-align: right;"><span> 1.234</span></td></tr>
 <tr><td>kein CPV-Link</td><td>7</td></tr>
</tbody></table>
"""


# ── Trefferzeilen-Parser ──────────────────────────────────────────────────────────────────
def test_zeile_traegt_alle_felder_getrennt():
    (z,) = cosinex.zeilen_lesen(_ZEILE_RLP)
    assert z["pid"] == "59717"
    assert z["titel"] == "Munitionsdepot Kriegsfeld - Baustromversorgung"
    assert z["stelle"] == "Landesbetrieb Liegenschafts- u. Baubetreuung"
    # Vergabeordnung und Typ dürfen NICHT zu „VSVgVTNW" verschmelzen.
    assert z["vo"] == "VSVgV"
    assert z["typ"] == "TNW"


def test_uhrzeit_kommt_aus_dem_abbr_nicht_aus_dem_sichtbaren_text():
    """Der sichtbare Text trägt nur das Datum. Bei einer Angebotsfrist ist die Uhrzeit
    der Unterschied zwischen „heute noch" und „vorbei"."""
    (z,) = cosinex.zeilen_lesen(_ZEILE_RLP)
    assert z["pub"] == "2026-07-26T10:50:00"
    assert z["frist"] == "2026-08-25T10:00:00"


def test_nv_frist_wird_kein_datum():
    (z,) = cosinex.zeilen_lesen(_ZEILE_OHNE_FRIST)
    assert z["frist"] is None
    assert z["pub"] == "2026-08-13T09:12:00"
    assert z["typ"] == "Vergebener Auftrag"


def test_zeile_ohne_pid_ist_kein_vorgang():
    assert cosinex.zeilen_lesen(_ZEILE_LAYOUT) == []


def test_seitenzahl_aus_der_blaetter_zeile():
    assert cosinex.seitenzahl("<p>Seite: 3 von 47 - Gesamteinträge: 929</p>") == 47
    assert cosinex.seitenzahl("<p>ohne Blätterzeile</p>") == 1


def test_divisionen_liest_code_label_und_anzahl():
    class _Antwort:
        text = _UEBERBLICK
        status_code = 200

        def raise_for_status(self):
            pass

    class _Sess:
        def get(self, url, timeout=None):
            assert "showCategoryOverview" in url
            return _Antwort()

    divs = cosinex.divisionen(_Sess(), "https://example.invalid/VMPCenter")
    assert divs == [("45000000-7", "Bauarbeiten", 929), ("72000000-5", "IT-Dienste", 1234)]


# ── robots.txt-Sperre ─────────────────────────────────────────────────────────────────────
def test_gesperrtes_portal_wird_ohne_flag_nicht_abgerufen(capsys):
    """Brandenburg sendet ``User-agent: * / Disallow: /``. Der Abruf funktioniert technisch —
    ob er stattfindet, ist eine Entscheidung und gehört einem Menschen. Ohne das Flag darf
    hier KEIN Netzverkehr entstehen (der Test hat keinen Netzzugang nötig, um das zu zeigen).
    """
    assert cosinex.PORTALE["bb"][2] == "disallow"
    assert cosinex.hole(["bb"], ab_jahr=2026, bekannt=set(), stop_nach=0) == []
    assert "robots.txt" in capsys.readouterr().out


# ── Bronze → Silber ───────────────────────────────────────────────────────────────────────
@pytest.fixture()
def _bronze(tmp_path, monkeypatch):
    monkeypatch.setattr(cosinex, "ROOT", tmp_path)
    d = tmp_path / "data" / "raw_cosinex" / "DE"
    d.mkdir(parents=True)

    def schreibe(saetze):
        (d / "2026-07.jsonl").write_text(
            "\n".join(json.dumps(s, ensure_ascii=False) for s in saetze) + "\n",
            encoding="utf-8")
    return tmp_path, schreibe


def _satz(**kw):
    basis = {"pid": "59717", "key": "rp:59717", "portal": "rp", "land": "Rheinland-Pfalz",
             "pub": "2026-07-26T10:50:00", "frist": "2026-08-25T10:00:00",
             "titel": "Munitionsdepot Kriegsfeld", "vo": "VOB/A", "typ": "Ausschreibung",
             "stelle": "LBB Kaiserslautern", "cpv_divs": ["45000000-7"],
             "erfasst_am": "2026-08-14"}
    basis.update(kw)
    return basis


def _lies(tmp_path, tabelle):
    import duckdb
    g = str(tmp_path / "data" / "silver" / "DE" / tabelle / "*" / "*.parquet")
    return duckdb.connect().execute(f"SELECT * FROM read_parquet('{g}')").fetchdf()


def test_silber_mapping_kern(_bronze):
    tmp_path, schreibe = _bronze
    schreibe([_satz()])
    cosinex.nach_silber("DE")
    n = _lies(tmp_path, "notices")
    assert len(n) == 1
    r = n.iloc[0]
    # Namensraum getrennt von TED — sonst kollidieren reine Zahlen (Lehre aus DÖE).
    assert r.notice_id == "cx:rp:59717"
    assert r.schema_gen == "cosinex"
    assert r.language == "de"            # kleingeschrieben, sonst schlägt der Sprach-Guard an
    assert r.notice_kind == "cn"
    assert r.contract_nature == "works"  # VOB/A ist per Definition Bauleistung
    assert str(r.publication_date)[:10] == "2026-07-26"
    assert r.year == 2026 and r.month == 7
    # Die Uhrzeit der Frist überlebt bis Silber.
    assert str(r.submission_deadline).startswith("2026-08-25 10:00")


def test_cpv_kommt_aus_der_portalangabe_nicht_aus_dem_regelwerk(_bronze):
    """Der eigentliche Mehrwert gegenüber DTVP/NetServer: dort ist `cpv_main` nur für VOB/A
    herleitbar und für VOL/UVgO NULL — womit diese Leads aus `build_prospective_leads`
    fallen. Hier liefert das Portal die Division für JEDE Vergabeordnung."""
    tmp_path, schreibe = _bronze
    schreibe([_satz(pid="1", key="rp:1", vo="UVgO", cpv_divs=["72000000-5"]),
              _satz(pid="2", key="rp:2", vo="VOL/A", cpv_divs=["33000000-0"])])
    cosinex.nach_silber("DE")
    n = _lies(tmp_path, "notices").set_index("publication_number")
    assert n.loc["1"].cpv_main == "72000000-5"
    assert n.loc["2"].cpv_main == "33000000-0"
    assert pd.isna(n.loc["1"].contract_nature)  # keine Herleitung, wo keine Regel gilt


def test_mehrere_divisionen_gehen_nicht_verloren(_bronze):
    tmp_path, schreibe = _bronze
    schreibe([_satz(cpv_divs=["45000000-7", "71000000-8"])])
    cosinex.nach_silber("DE")
    a = _lies(tmp_path, "attributes")
    divs = sorted(a[a.path == "cosinex/cpv_division"].value)
    assert divs == ["45000000-7", "71000000-8"]
    # Die Grobheit steht ausdrücklich daneben.
    assert (a.path == "cosinex/cpv_ebene").any()


def test_ohne_vergabestelle_entsteht_trotzdem_eine_partei(_bronze):
    """Ohne Partei fällt der Vorgang am ``JOIN buyer`` von `build_prospective_leads`
    lautlos aus der Lead-Schicht — die Falle, die bei Bremen alle 41 Ausschreibungen
    gekostet hätte. Der Ersatzname ist als Nicht-Stelle lesbar, nicht plausibel."""
    tmp_path, schreibe = _bronze
    schreibe([_satz(stelle=None)])
    cosinex.nach_silber("DE")
    p = _lies(tmp_path, "notice_parties")
    assert len(p) == 1
    assert "nicht ausgewiesen" in p.iloc[0]["name"]
    a = _lies(tmp_path, "attributes")
    assert (a.path == "cosinex/stelle_unbekannt").any()


def test_ohne_veroeffentlichungsdatum_kein_erfundenes_datum(_bronze):
    """`publication_date` bleibt NULL — aber year/month kommen aus dem Erfassungsdatum,
    sonst landet der Satz in ``year=0`` und fällt aus jeder Zeitreihe."""
    tmp_path, schreibe = _bronze
    schreibe([_satz(pub=None)])
    cosinex.nach_silber("DE")
    r = _lies(tmp_path, "notices").iloc[0]
    assert pd.isna(r.publication_date)
    assert r.year == 2026 and r.month == 8
    a = _lies(tmp_path, "attributes")
    assert (a.path == "cosinex/zeitpunkt_aus_erfassung").any()


def test_notice_kind_deckt_alle_typen_der_trefferliste(_bronze):
    tmp_path, schreibe = _bronze
    typen = {"Ausschreibung": "cn", "TNW": "cn",
             "Beabsichtigte Ausschreibung": "pin", "Vergebener Auftrag": "can"}
    schreibe([_satz(pid=str(i), key=f"rp:{i}", typ=t)
              for i, t in enumerate(typen, start=10)])
    cosinex.nach_silber("DE")
    n = _lies(tmp_path, "notices")
    assert sorted(n.notice_kind) == sorted(typen.values())


def test_bronze_ist_idempotent(_bronze):
    tmp_path, _ = _bronze
    s = _satz()
    cosinex.schreibe_bronze([s])
    cosinex.schreibe_bronze([s])
    zeilen = (tmp_path / "data" / "raw_cosinex" / "DE" / "2026-07.jsonl").read_text().strip()
    assert len(zeilen.splitlines()) == 1
    assert cosinex.bekannte_keys("DE") == {"rp:59717"}

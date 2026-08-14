"""Marktpuls — Regressions-Guards für die Regeln, die man am Bildschirm nicht sieht.

Bewusst OHNE Voll-Lauf: `scripts/build_marktpuls.py` scannt den ganzen Bestand (~40 s).
Geprüft wird deshalb die reine Logik plus der Vertrag der erzeugten Datei, wenn sie da ist.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _modul():
    spec = importlib.util.spec_from_file_location(
        "build_marktpuls", ROOT / "scripts" / "build_marktpuls.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _modul()


def _monate(pcts):
    return [{"m": i + 1, "avg": 100.0, "pct": p} for i, p in enumerate(pcts)]


def _stab(monate, *welche, jahre=22):
    """Stabilitäts-Tabelle, in der genau `welche` Monate als verlässlich gelten.

    Die Richtung wird aus dem Fensterwert abgeleitet — genau wie in echten Daten, wo eine
    verlässliche Abweichung nach unten auch im Fenster unten liegt. Ein Helfer, der die
    Richtung starr setzt, würde den Abgleich zwischen Beleg und Anzeige gar nicht prüfen.
    """
    nach_m = {m["m"]: m["pct"] for m in monate}
    out = {}
    for m in welche:
        hoch = nach_m[m] > 0
        out[m] = {"jahre": jahre, "gleiche_richtung": jahre,
                  "richtung": "ueber" if hoch else "unter",
                  "lo": 10.0 if hoch else -30.0, "hi": 30.0 if hoch else -10.0,
                  "mittel": 20.0 if hoch else -20.0, "pro_monat": 500.0, "stabil": True}
    return out


def test_befund_benennt_nur_verlaessliche_ausschlaege():
    """Der Ein-Satz-Befund darf keinen Effekt erfinden (Briefing §3.2/§7).

    Ohne einen über die Jahre verlässlichen Ausschlag ist die ehrliche Aussage
    „gleichmässiger als vermutet" — auch dann, wenn im angezeigten Fenster ein Monat weit
    ausschlägt. Gemessen AT/Sicherheit: Juli +53 %, Juni −56 % im Fenster, aber keiner der
    beiden hält über die Jahre die Richtung. Ein Satz darüber wäre erfundene Bedeutung.
    """
    stark = _monate([5, -4, 3, 0, 2, -1, 53, -56, 1, 0, -2, 3])
    assert M.befund(stark, {})["typ"] == "flach", "ohne Verlässlichkeit kein benannter Effekt"

    assert M.befund([], {})["typ"] == "keine_daten"

    tief = M.befund(stark, _stab(stark, 8))
    assert tief["typ"] == "tief" and tief["monat"] == 8
    assert tief["jahre"] == 22 and tief["jahre_gleich"] == 22, "Beleg muss mitkommen"

    spitze = M.befund(stark, _stab(stark, 7))
    assert spitze["typ"] == "spitze" and spitze["monat"] == 7


def test_befund_nennt_den_staerksten_und_nicht_den_erstbesten():
    """Der Fehler, der das ausgelöst hat: `befund()` prüfte erst auf Hoch, dann auf Tief.

    Sobald irgendein Monat über der Schwelle lag, wurde er gemeldet — auch wenn das Tief
    deutlich stärker war. Gemessen DE/Energie: der Satz meldete „Juli +31 %", während der
    Januar bei −39 % lag. Die Zahlen im Diagramm stimmten, nur der Satz benannte den
    schwächeren Effekt. Auf einer öffentlichen Seite IST der Satz die Aussage.
    """
    monate = _monate([-39, 0, 0, 0, 0, 0, 31, 0, 0, 0, 0, 0])
    b = M.befund(monate, _stab(monate, 1, 7))
    assert b["typ"] == "tief" and b["monat"] == 1, "muss den stärkeren Ausschlag nennen"

    # Und andersherum, damit der Test nicht nur eine Richtung absichert.
    zwei = _monate([-20, 0, 0, 0, 0, 0, 44, 0, 0, 0, 0, 0])
    b2 = M.befund(zwei, _stab(zwei, 1, 7))
    assert b2["typ"] == "spitze" and b2["monat"] == 7


def test_stabilitaet_braucht_richtung_UND_ausmass():
    """Beide Hürden, sonst rutscht Bedeutungsloses in den Satz.

    Gemessen: der Dezember hält die Richtung in 82 % der Jahre — aber im Mittel nur mit
    +3,9 %. Verlässlich und trotzdem ohne Aussage. Umgekehrt hebt ein einzelnes
    Ausreisserjahr den Schnitt, ohne dass ein Muster dahintersteht.
    """
    assert M.STABIL_ANTEIL <= 1.0 and M.STABIL_MIN_PCT > 0
    treu_aber_klein = {1: {"jahre": 22, "gleiche_richtung": 18, "richtung": "ueber",
                           "lo": -11.0, "hi": 36.0, "mittel": 3.9, "stabil": False}}
    assert M.befund(_monate([4] + [0] * 11), treu_aber_klein)["typ"] == "flach"


def test_quellenfamilien_decken_alle_schema_generationen():
    """Ein neuer Connector bringt eine neue `schema_gen`. Fehlt sie in `QUELLE`, fällt sie
    auf 'sonstige' und würde als eigene Quelle behandelt — ein stiller Fehler, der erst als
    Sprung in der Kurve auffällt. Die Liste muss zu `govisor/schema.py` passen."""
    erwartet = {"legacy", "eforms", "text", "ojs", "doe", "simap", "atverg"}
    assert erwartet <= set(M.QUELLE), f"nicht abgebildet: {erwartet - set(M.QUELLE)}"
    assert set(M.QUELLE.values()) == {"ted", "doe", "simap", "atverg"}


def test_in_list_verdoppelt_hochkommata():
    assert M._in_list("x", []) == "FALSE"
    assert M._in_list("x", ["a'b"]) == "x IN ('a''b')"


def _regel(zahl, achse, quellen):
    """`_serien_regel` mit einer Mini-Zähltabelle statt einem Bestand.

    `zahl` kommt als {quelle: {jahr: n}} — die echte Struktur ist ein Tupel-Schlüssel,
    aber die Regel liest daraus nur (land, ALLE, quelle, jahr).
    """
    flach = {("X", M.ALLE, q, j): n for q, jj in zahl.items() for j, n in jj.items()}
    return M._serien_regel(flach, {}, "X", quellen, achse)


def test_nationale_quelle_wird_nur_bei_durchgehender_lieferung_zusammengefuehrt():
    """Die Regel aus Entscheidung 5 — der Kern des Jahres-Layers.

    Sie ist absichtlich achsenabhängig: dieselbe Quelle gehört über ein kurzes Fenster zu
    TED und über die Historie in eine eigene Reihe. Wer das „vereinheitlicht", baut genau
    den Fehler wieder ein, den der Marktpuls vermeiden soll — eine Summenkurve, in der ein
    Quellen-Start wie Marktwachstum aussieht.
    """
    betrieb = M.MIN_JAHR_VERFAHREN * 10

    # Kurzes Fenster: beide liefern durchgehend → eine Linie (gemessen AT/atverg 2021–2025).
    kurz = list(range(2021, 2026))
    r = _regel({"ted": {j: betrieb for j in kurz}, "atverg": {j: betrieb for j in kurz}},
               kurz, ["atverg", "ted"])
    assert r["atverg"]["serie"] == "ted" and r["atverg"]["grund"] == "durchgehend"

    # Lange Achse: dieselbe Quelle beginnt später → eigene Linie ab ihrem Beginn.
    lang = list(range(2004, 2026))
    r = _regel({"ted": {j: betrieb for j in lang},
                "atverg": {j: betrieb for j in lang if j >= 2019}},
               lang, ["atverg", "ted"])
    assert r["atverg"]["serie"] == "atverg" and r["atverg"]["von"] == 2019
    assert r["ted"]["serie"] == "ted" and r["ted"]["grund"] == "basis"


def test_streuzeilen_begruenden_keinen_serienbeginn():
    """AT/atverg führt 2009–2018 ein bis zwanzig Verfahren je Jahr — Nachtrags-Rauschen.

    Ohne Betriebsschwelle stünde der Serienbeginn auf 2009 und die Linie bestünde zehn
    Jahre lang aus einer Nulllinie mit Zacken. Weggeworfen wird trotzdem nichts: die
    Quelle bleibt als `vorlauf` ausgewiesen.
    """
    achse = list(range(2004, 2026))
    r = _regel({"ted": {j: 5000 for j in achse},
                "atverg": {**{j: 12 for j in range(2009, 2019)},
                           **{j: 6000 for j in range(2019, 2026)}}},
               achse, ["atverg", "ted"])
    assert r["atverg"]["von"] == 2019, "Streujahre dürfen den Beginn nicht vorziehen"

    nur_streu = _regel({"ted": {j: 5000 for j in achse}, "atverg": {2014: 12}},
                       achse, ["atverg", "ted"])
    assert nur_streu["atverg"]["serie"] is None
    assert nur_streu["atverg"]["grund"] == "vorlauf"
    assert nur_streu["atverg"]["verfahren"] == 12, "Vorlauf wird ausgewiesen, nicht gelöscht"


def test_luecke_nach_dem_start_verhindert_die_zusammenfuehrung():
    """Eine Quelle, die mittendrin ein Jahr aussetzt, ist nicht „durchgehend" — sonst
    würde eine Ingest-Lücke als Markteinbruch in die TED-Linie gerechnet."""
    achse = list(range(2021, 2026))
    r = _regel({"ted": {j: 5000 for j in achse},
                "doe": {2021: 5000, 2022: 5000, 2024: 5000, 2025: 5000}},   # 2023 fehlt
               achse, ["doe", "ted"])
    assert r["doe"]["serie"] == "doe"


def test_fehlendes_publication_date_wirft_kein_verfahren_weg():
    """Der teuerste Fund dieser Runde, als Guard.

    `verfahren_tabelle` verlangte ein `publication_date`. Gemessen tragen aber nur 8.875
    von 102.043 DÖE-`cn` aus 2023 eines — die Forderung warf **93 % der Quelle** weg, ohne
    eine Zeile Fehlermeldung. Aufgefallen ist es erst, als der Jahres-Layer DÖE als eigene
    Reihe zeichnete und die Linie eine Grössenordnung zu niedrig lag.

    `year`/`month` sind der belastbare Ersatz (natürliche Verteilung über zwölf Monate;
    98,3 % Übereinstimmung, wo beide Angaben vorliegen). Geprüft wird hier das SQL, nicht
    der Bestand: die Bedingung darf nie wieder auf ein hartes `publication_date IS NOT NULL`
    zurückfallen, und das Ersatzdatum muss in der Herkunfts-Kennzeichnung landen.
    """
    quelle = (ROOT / "scripts" / "build_marktpuls.py").read_text(encoding="utf-8")
    kern = quelle[quelle.index("def verfahren_tabelle"):quelle.index("def quellen_im_fenster")]
    assert "n.publication_date IS NOT NULL\n" not in kern, \
        "harte Datumspflicht wieder da — sie verwirft ganze Quellen lautlos"
    assert "make_date(n.year, n.month, 1)" in kern, "Ersatzdatum aus year/month fehlt"
    assert "datum_aus_jahr_monat" in kern, "Herkunft des Zeitpunkts wird nicht mitgeführt"


def test_kuratierte_brueche_tragen_immer_einen_beleg():
    """`art: kuratiert` heisst: steht in keinem unserer Daten. Ein solcher Eintrag ohne
    Quellenangabe wäre eine Behauptung — und in einer Anzeige, die sonst nur Gemessenes
    zeigt, die einzige Stelle, an der niemand nachprüfen kann."""
    assert M.REGEL_BRUECHE, "Tabelle darf leer sein, aber dann bewusst"
    for r in M.REGEL_BRUECHE:
        assert r["beleg"].strip(), r
        assert r["laender"] == "*" or isinstance(r["laender"], list), r
        assert M.FRUEHESTES_JAHR <= r["jahr"] <= 2100, r
        assert r["code"] and " " not in r["code"], r


def test_branchen_decken_das_ui_vokabular():
    """Dieselben sechs Grundräume wie die Lead-Liste (Briefing §9-4) — sonst zeigt der
    Marktpuls andere Zahlen als die Liste, auf die er verweist."""
    assert set(M.BRANCHEN) == {"bau", "it", "beratung", "medizin", "sicherheit", "energie"}
    for b in M.BRANCHEN:
        assert f"'{b}'" in M.BRANCHE_SQL


def test_belege_stehen_in_den_sprachkatalogen():
    """Die `beleg`-Sätze laufen über `t(variable)` — die bekannte Lücke der i18n-Guards.

    `test_verdrahtete_texte_sind_uebersetzt` sieht nur `t("literal")`,
    `test_texttabellen_hinter_t_sind_uebersetzt` nur `t(KONSTANTE.feld)`. Ein Beleg kommt
    dagegen als deutscher Satz aus dem JSON und wird erst im Frontend übersetzt: kein
    bestehender Test kann ihn finden. Wer `REGEL_BRUECHE` erweitert und die Kataloge
    vergisst, bekäme in EN/FR mitten im englischen Absatz einen deutschen Rechtsverweis.
    """
    import json as _json
    m = ROOT / "web" / "lib" / "i18n" / "messages"
    en = _json.loads((m / "flat.en.json").read_text(encoding="utf-8"))
    fr = _json.loads((m / "flat.fr.json").read_text(encoding="utf-8"))
    fehlend = [r["beleg"] for r in M.REGEL_BRUECHE if r["beleg"] not in en or r["beleg"] not in fr]
    assert not fehlend, "Beleg ohne Übersetzung:\n  " + "\n  ".join(fehlend)


@pytest.mark.skipif(not (ROOT / "web" / "data" / "marktpuls.json").exists(),
                    reason="marktpuls.json noch nicht gebaut")
def test_erzeugte_datei_haelt_den_vertrag():
    p = ROOT / "web" / "data" / "marktpuls.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert p.stat().st_size < 50 * 1024, "Briefing §5: JSON unter 50 KB"
    for feld in ("schema", "erzeugt", "stand", "laender", "fenster", "coverage", "saison", "lage"):
        assert feld in d, feld
    assert d["fenster"]["jahre"] == M.FENSTER_JAHRE
    assert d["gesamt_key"] in d["coverage"] and d["gesamt_key"] in d["lage"]["je_land"]
    # Jede Land×Branche-Kombination muss existieren — die Anzeige greift blind darauf zu.
    for land in [d["gesamt_key"], *d["laender"]]:
        for br in ["alle", *d["branchen"]]:
            block = d["saison"].get(f"{land}|{br}")
            assert block is not None, f"{land}|{br} fehlt"
            assert len(block["monate"]) == 12
            assert block["genug"] == (block["verfahren_gesamt"] >= d["min_faelle"])
    # Herkunfts-Kennzeichnung darf nie verschwinden (Projekt-Konvention).
    for land, lg in d["lage"]["je_land"].items():
        assert lg["frist_basis"] == "echt", land
        assert "frist_abdeckung" in lg, land

    # Der Befundsatz ist auf einer öffentlichen Seite DIE Aussage — Diagramm, Satz und Beleg
    # müssen dasselbe sagen. Jede dieser vier Bedingungen hat schon einmal nicht gehalten.
    for key, b in d["saison"].items():
        if not b["genug"]:
            continue
        f = b["befund"]
        if f["typ"] in ("flach", "keine_daten"):
            continue
        sp = f["spanne"]
        # STRADDLE, nicht Beruehrung. Die Bedingung soll verhindern, dass der Satz „Januar
        # liegt tief" ueber einer Spanne steht, die von −20 % bis +30 % reicht. Ein Endpunkt
        # von exakt 0,0 ist aber kein Vorzeichenwechsel: DE|medizin lag in 21 von 22 Jahren
        # im Januar unter dem Schnitt, Spanne −56,5 % bis 0,0 % — ein Jahr traf die Null
        # (auf eine Stelle gerundet). Mit `> 0` schlug der Test genau dort fehl, wo der
        # Befund am stabilsten ist.
        assert sp[0] * sp[1] >= 0, (key, "Spanne wechselt das Vorzeichen, der Satz behauptet "
                                         "aber dieselbe Seite")
        assert (f["pct"] > 0) == (sp[0] > 0), (key, "Befund zeigt in die andere Richtung als "
                                                    "sein eigener Beleg")
        assert (f["typ"] == "tief") == (f["pct"] < 0), (key, "typ passt nicht zum Wert")
        assert f["jahre_gleich"] <= f["jahre"]
        staerkster = max(b["monate"], key=lambda m: abs(m["pct"]))
        if staerkster.get("stabil"):
            assert f["monat"] == staerkster["m"], (
                key, "nennt nicht den stärksten verlässlichen Monat — genau der Fehler, mit "
                     "dem DE/Energie „Juli +31 %\" meldete, während der Januar bei −39 % lag")

    if d["schema"] < 2:
        return
    j = d["jahre"]
    assert j["achse"] == list(range(j["von"], j["bis"] + 1))
    # Das laufende Jahr ist per Definition ein Teiljahr — steht es in der Achse, zeichnet
    # die Anzeige einen Einbruch, der nur „das Jahr ist noch nicht um" bedeutet.
    assert j["bis"] < j["laufendes_jahr"], "laufendes Jahr gehört nicht auf die Achse"
    for key, reihen in j["reihen"].items():
        for r in reihen:
            assert j["von"] <= r["von"] <= j["bis"], (key, r["quelle"])
            assert len(r["werte"]) == j["bis"] - r["von"] + 1, (key, r["quelle"])
            # `serie` gruppiert, `quelle` bleibt einzeln — genau dadurch ist die
            # Quellen-Zusammensetzung je Jahr in den Daten und braucht keinen zweiten Block.
            assert r["serie"] in (r["quelle"], "ted"), (key, r)
            for t in r.get("teiljahre", []):
                assert 0 < t["monate"] < 12, (key, r["quelle"], t)
                assert r["von"] <= t["jahr"] <= j["bis"]
    for land, bs in j["brueche"].items():
        for b in bs:
            assert b["art"] in ("gemessen", "kuratiert"), (land, b)
            # Kein kuratierter Bruch ohne Beleg — dieselbe Regel wie im Skript, hier
            # noch einmal an der ausgelieferten Datei.
            assert b["art"] != "kuratiert" or b.get("beleg"), (land, b)
            assert j["von"] < b["jahr"] <= j["bis"], (land, b)


# ── NetServer-Quelle ─────────────────────────────────────────────────────────
# (hier statt in einer eigenen Datei, weil die Guards dieselbe Sorte Fehler treffen:
#  stille Verluste beim Weg einer Quelle in die Lead-Schicht)

def _ns():
    spec = importlib.util.spec_from_file_location(
        "netserver", ROOT / "govisor" / "netserver.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


NS = _ns()


def test_netserver_zeitstempel_ist_kein_titel():
    """Die Verdopplungs-Falle: NetServer rendert jeden Vorgang ZWEIMAL — einmal vollstaendig,
    einmal als reine Fristzeile. Nimmt der Parser den Zeitstempel als Titel, verdoppelt sich
    der Bestand (Bremen meldete 82 statt 41 Vorgaengen) und die Phantomsaetze zaehlen bei
    jedem Bestandsabgleich als „neu" — genau so kam eine 92-%-Neuquote zustande, die es
    nicht gab.
    """
    seite = """<table><tr><th>Ausschreibung</th><th>Verfahrensart</th><th>Rechtsrahmen</th>
      <th>Abgabefrist</th></tr>
      <tr><td>13.08.2026</td><td>Lueftungstechnik und Gebaeudeautomation (V0471/2026)</td>
          <td>Offenes Verfahren</td><td>VOB</td><td>11.09.2026 10:00</td></tr>
      <tr><td>11.09.2026 10:00</td></tr></table>"""
    z = NS.zeilen_lesen(seite)
    assert len(z) == 1, "die reine Fristzeile darf kein Vorgang sein"
    assert z[0]["titel"].startswith("Lueftungstechnik")


def test_netserver_erfindet_kein_veroeffentlichungsdatum():
    """Sachsen fuehrt in der Trefferliste NUR die Abgabefrist. Ein Rueckfall auf „irgendein
    Datum" setzte die Frist als Veroeffentlichung — gemessen an allen 50 Saetzen — und
    verschoebe damit Jahr/Monat der Notice und den Marktpuls."""
    seite = """<table><tr><th>Ausschreibung</th><th>Vergabestelle</th></tr>
      <tr><td>Reinigung Smart Mobility Lab (2A032785)</td><td>SIB Bautzen</td>
          <td>VOL/VgV, Offenes Verfahren</td><td>15.09.2026 09:00</td></tr></table>"""
    z = NS.zeilen_lesen(seite)
    assert len(z) == 1
    assert z[0]["pub"] is None, "ohne Quellenangabe kein erfundenes Veroeffentlichungsdatum"
    assert z[0]["frist"].startswith("2026-09-15")


def test_netserver_liest_die_vergabestelle_aus_der_spalte():
    """MV und Baden-Wuerttemberg fuehren eine SPALTE „Vergabestelle", Sachsen ein Feld
    „Auftraggeber:". Ein rein musterbasierter Parser fand nur Sachsen und liess 68 Stellen
    liegen — die dann am `JOIN buyer` des Lead-Baus lautlos ausgefallen waeren."""
    seite = """<table><tr><th>Ausschreibung</th><th>Vergabestelle</th><th>Verfahrensart</th>
      <th>Rechtsrahmen</th><th>Abgabefrist</th></tr>
      <tr><td>Neubau Feuerwache Los 3</td><td>Landesforst Mecklenburg Vorpommern</td>
          <td>Offenes Verfahren</td><td>VOB</td><td>20.09.2026 10:00</td></tr></table>"""
    z = NS.zeilen_lesen(seite)
    assert len(z) == 1
    assert z[0]["auftraggeber"] == "Landesforst Mecklenburg Vorpommern"


def test_netserver_schluessel_ueberlebt_fristverlaengerung():
    """Der Schluessel steht auf Portal + Veroeffentlichung + Titel, NICHT auf der Frist.
    Sonst erzeugt jede Fristverlaengerung einen zweiten Satz derselben Vergabe."""
    a = {"pub": "2026-08-13", "titel": "Neubau Feuerwache", "frist": "2026-09-11T10:00:00"}
    b = {"pub": "2026-08-13", "titel": "Neubau Feuerwache", "frist": "2026-09-25T10:00:00"}
    assert NS.schluessel("hb", a) == NS.schluessel("hb", b)
    assert NS.schluessel("hb", a) != NS.schluessel("sn", a), "Portale bleiben getrennt"


def test_netserver_ist_in_der_dubletten_firewall_bekannt():
    """Eine Quelle, die die Firewall nicht kennt, laeuft an ihr vorbei — genau das, wogegen
    sie gebaut wurde."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import dedupe as ded          # Paketmodul: dedupe nutzt relative Importe
    assert "netserver" in ded.QUELLEN_RANG
    # Aermstes Satzbild im Bestand → darf niemandem als Anreicherungsquelle vorgezogen werden.
    assert ded.QUELLEN_RANG["netserver"] == max(ded.QUELLEN_RANG.values())


def test_lead_bau_verlangt_keinen_cpv():
    """Die CPV-Pflicht im Lead-Bau warf gemessen 307 laufende Ausschreibungen weg.

    Sie stand in `build_prospective_leads` als `AND n.cpv_main IS NOT NULL` und traf
    ausgerechnet die Quellen, die den unterschwelligen Markt tragen: DOeE 239, NetServer 68.
    Der CPV fehlt dabei nicht der VERGABE — dieselben UVgO-Vergaben tragen bei DOeE zu
    100 % einen echten Code —, sondern der Trefferliste des Portals.

    Ein Lead ohne Branche ist unvollstaendig; ein fehlender Lead ist im Vergleich zweier
    Werkzeuge eine sichtbare Luecke. Deshalb darf die Bedingung nicht zurueckkommen.
    """
    quelle = (ROOT / "govisor" / "gold.py").read_text(encoding="utf-8")
    i = quelle.index("def build_prospective_leads")
    kern = quelle[i:i + 12000]
    assert "n.cpv_main IS NOT NULL" not in kern, (
        "CPV-Pflicht im Lead-Bau wieder da — sie verwirft laufende Ausschreibungen lautlos")


def test_grundraum_ohne_ist_ueberall_verdrahtet():
    """Ein Grundraum ist erst durchgaengig, wenn Export, ROUTE und Anzeige ihn kennen.

    Gemessen beim Einbau: der Export schrieb `leads-ohne.json` mit 306 Vergaben, und
    `/api/leads?branche=ohne` antwortete trotzdem mit HTTP 400 — die Route trug eine eigene
    Allow-Liste. Die Leads waren also exportiert und fuer die App unerreichbar. Dieselbe
    Liste steht an vier Stellen; drei davon aggregieren still ueber alle Grundraeume, dort
    faellt ein fehlender Eintrag nicht einmal als Fehler auf.
    """
    from pathlib import Path
    web = Path(__file__).resolve().parent.parent / "web"
    pflicht = [
        "app/api/leads/route.ts",          # Liste je Grundraum
        "app/api/lead-detail/route.ts",    # Detailseite
        "app/api/branchen/route.ts",       # Zaehler + Geo-Aggregation
        "app/api/calendar/[token]/route.ts",  # Fristen-Feed
        "lib/explorerCore.js",             # Anzeige-Label
    ]
    fehlend = [f for f in pflicht if '"ohne"' not in (web / f).read_text(encoding="utf-8")
               and "ohne:" not in (web / f).read_text(encoding="utf-8")]
    assert not fehlend, "Grundraum 'ohne' fehlt in: " + ", ".join(fehlend)

    # Und die Gegenprobe: in der PROFIL-Auswahl hat er nichts verloren — niemandes
    # Geschaeft ist „ohne Kategorie". Er ist ein Anzeigefach, kein Gewerk.
    for f in ("app/settings/page.tsx", "app/onboarding/page.tsx"):
        assert '"ohne"' not in (web / f).read_text(encoding="utf-8"), (
            f"{f}: 'ohne' ist keine waehlbare Branche")


def test_hessen_laeuft_ueber_den_eigenen_suchweg():
    """HAD ist keine gewoehnliche NetServer-Instanz und darf nicht so behandelt werden.

    Unter `/NetServer/` liegen dort nur die DETAILseiten; die Suche ist eine eigene
    Oberflaeche mit POST-Formular. Der generische Servlet-Weg antwortet mit 404 — deshalb
    steht die Basis-URL bewusst auf None, damit er gar nicht erst versucht wird, und der
    Abruf laeuft ueber `hole_had`.
    """
    assert "he" in NS.PORTALE, "Hessen fehlt in der Portal-Tabelle"
    assert NS.PORTALE["he"][1] is None, (
        "Hessen darf keine Servlet-Basis-URL tragen — der generische Weg gibt dort 404")
    assert hasattr(NS, "hole_had"), "eigener Suchweg fuer Hessen fehlt"

    quelle = (ROOT / "govisor" / "netserver.py").read_text(encoding="utf-8")
    kern = quelle[quelle.index("def hole_had"):quelle.index("def hole(")]
    # Zwei Fallen, beide beim Bauen zugeschlagen — als Guard festgehalten:
    assert "document.forms[2]" in kern, (
        "falsches Formular: forms[0] ist der Sprachumschalter, forms[1] das kleine Suchfeld")
    assert "f.submit()" in kern, (
        "CMD ist ein RADIO, kein Absende-Knopf — ein Klick darauf schickt nichts ab")
    assert "replace(/\\\\s+/g" not in kern, (
        "Zeilenumbrueche sind bei HAD die Struktur: sie trennen Verfahrensart, Leistungsart "
        "und Titel. Werden sie plattgemacht, beginnt jeder Titel mit demselben Formularsatz")


def test_docfetch_ueberspringt_fristtag_und_open_house():
    """Zwei Filter im Unterlagen-Abruf, beide aus einer Messung, nicht aus einer Vermutung.

    Vorher galten 1.439 Versuche als `gated` — der Name legt „braucht Anmeldung" nahe, also
    gibt man auf. Gemessen war es etwas anderes:

    * **Fristtag.** Eine Frist traegt eine UHRZEIT (08:00/10:00/12:00). Laeuft der Fetch
      nachmittags, hat cosinex die Unterlagen laengst abgehaengt. DTVP, je 10 Vorgaenge:
      Frist heute 70 % erreichbar, ab +1 Tag 90–100 %. Die Klippe ist EIN Tag breit —
      ein groesserer Vorlauf haette erreichbare Vorgaenge mit weggeworfen.
    * **Open House.** Dort tritt man bei, statt zu bieten; die Unterlagen liegen hinter der
      Teilnahme. `vergabe.tk.de`: 197 von 202 Versuchen `gated`, alle Stichproben
      Open-House-Rabattvertraege. Keine schliessbare Luecke, sondern die Bauart.

    Zusammen 1.357 verschenkte Abrufe je Lauf.
    """
    quelle = (ROOT / "govisor" / "docfetch.py").read_text(encoding="utf-8")
    i = quelle.index("def fetch_batch")
    kern = quelle[i:i + 4000]
    assert "deadline_date > current_date" in kern, (
        "Fristtag wieder drin — die Unterlagen sind dort meist schon abgehaengt")
    assert "deadline_date >= current_date" not in kern, (
        "`>=` laesst den Fristtag wieder zu")
    assert "open_house" in kern, (
        "Open-House-Verfahren wieder im Abruf — dort gibt es die Unterlagen nur mit Teilnahme")


def _sub():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import subreport
    return subreport


def test_subreport_leitet_die_vergabeseite_aus_beiden_url_formen_ab():
    """985 offene subreport-Leads liegen in ZWEI URL-Formen vor.

    673 zeigen auf die Vergabeseite, 312 direkt auf die Bekanntmachungs-PDF. Ein Aufruf der
    zweiten startet einen Download statt eine Seite („Download is starting") — daran
    scheiterte der erste Lauf. Die ELVIS-Kennung steht aber in der URL. Es sind exakt die
    312, die in der Portal-Landkarte als „subreport-elvis, Bot-Sperre" gefuehrt wurden:
    keine Sperre, eine zweite URL-Form.
    """
    S = _sub()
    assert S.vergabeseite("https://www.subreport.de/E74857938") == \
        "https://www.subreport.de/E74857938"
    assert S.vergabeseite(
        "https://www.subreport-elvis.de/download/bund/E63477415/1785907953466/bekanntmachung.pdf"
    ) == "https://www.subreport.de/E63477415"
    assert S.vergabeseite("https://www.subreport.de/ohne-kennung") is None
    assert S.vergabeseite(None) is None


def test_subreport_holt_listen_und_gibt_das_auch_so_an():
    """Der Connector laedt KEINE Vergabeunterlagen — der Download reagiert ohne Anmeldung
    nicht (drei Vergaben, alle Knopfpositionen geprueft). Genau ein Knopf liefert, und der
    traegt die Bekanntmachung („unverbindliche Darstellung der eForms-formatierten
    Bekanntmachung"), die wir laengst ueber TED haben.

    Der Status muss das sagen. Ein `downloaded` hier waere die dritte Fehldeutung derselben
    Sorte an einem Tag — nach „gated", „503" und „Bot-Sperre".
    """
    quelle = (ROOT / "govisor" / "subreport.py").read_text(encoding="utf-8")
    assert '"nur_liste"' in quelle, "Status muss ausweisen, dass nur die LISTE vorliegt"
    assert "accept_downloads" not in quelle, (
        "der Connector darf keine Downloads annehmen — er liest die oeffentliche Liste")
    assert "doctypes" in quelle, "ohne Typ-Klassifikation ist die Liste nur ein Haufen Namen"


def _eg():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import docfetch_evergabe
    return docfetch_evergabe


def test_evergabe_verwechselt_die_gleichnamigen_nachbarn_nicht():
    """Fünf Hosts tragen „evergabe" im Namen und sind völlig verschiedene Systeme.

    evergabe-online.de ist der Bund (1.027 Leads, eigene Wartungsfenster), deutsche-evergabe,
    evergabe.nrw, evergabe.blb.nrw und bieter.ehealth-evergabe sind je eigene Plattformen.
    Ein `'evergabe.de' in url` fängt mehrere davon mit ein und würde sie diesem Connector
    zuschieben, der ihre Oberfläche nicht kennt.
    """
    E = _eg()
    assert E.ist_evergabe("https://www.evergabe.de/unterlagen/3423114")
    for fremd in ("https://www.evergabe-online.de/x", "https://www.deutsche-evergabe.de/x",
                  "https://www.evergabe.nrw.de/x", "https://evergabe.blb.nrw.de/x",
                  "https://bieter.ehealth-evergabe.de/x"):
        assert not E.ist_evergabe(fremd), fremd


def test_evergabe_fuehrt_alle_vier_url_formen_auf_die_dateiliste():
    """Vier Formen im Bestand, alle führen auf `/unterlagen/<kennung>`.

    Die Suchform trägt die Kennung im LETZTEN Pfadsegment — ein einzelner Regex auf
    `/unterlagen/` greift dort nicht und hätte ~150 Leads verworfen.
    """
    E = _eg()
    U = "https://www.evergabe.de/unterlagen/"
    assert E.unterlagen_url(U + "3423114/zustellweg-auswaehlen") == U + "3423114"
    assert E.unterlagen_url(U + "019f6b47-3646-4d51-82f8-8f2231a58038/zustellweg-auswaehlen") \
        == U + "019f6b47-3646-4d51-82f8-8f2231a58038"
    assert E.unterlagen_url(U + "54321-Tender-19f8e1fc48b-5e119e0005bf8de6") \
        == U + "54321-Tender-19f8e1fc48b-5e119e0005bf8de6"
    assert E.unterlagen_url(
        "https://www.evergabe.de/auftraege/suche-ueber-vergabestellen/Stadt%2520Leipzig/3434706"
    ) == U + "3434706"
    assert E.unterlagen_url("https://www.evergabe.de/auftraege") is None
    assert E.unterlagen_url(None) is None


def test_evergabe_unterscheidet_leer_von_abgewiesen_von_gesperrt():
    """Der teuerste Fehler dieses Connectors war eine zu grobe Meldung.

    Erste Fassung: „keine Dateien" — egal ob die Vergabe leer war, die Dateien abgewiesen
    wurden oder die WAF schon die SEITE gesperrt hatte. Gemessen meldeten fünf von zehn
    Vorgängen „keine Dateien"; alle fünf trugen Dateien, alle fünf waren HTTP 418. Ohne die
    Trennung hätte der Lauf hunderte Vergaben still als unergiebig abgehakt.
    """
    quelle = (ROOT / "govisor" / "docfetch_evergabe.py").read_text(encoding="utf-8")
    for status in ('"leer"', '"abgewiesen"', '"gesperrt"', '"downloaded"'):
        assert status in quelle, f"Status {status} fehlt"
    assert "r.status in _GESPERRT" in quelle, "der HTTP-Status der Seite muss geprüft werden"


def test_evergabe_pausiert_statt_abzubrechen():
    """Die WAF-Sperre ist flüchtig — gemessen 418 bei 0/2/4 min, 200 bei 6 min.

    Ein Abbruch nach der ersten Sperre hätte jeden Lauf nach ~10 Vorgängen beendet und die
    845 offenen Vergaben nie eingeholt. Und was während einer Sperre übersprungen wird, muss
    nachgeholt werden: die Reihenfolge ist stabil, sonst fällt bei JEDEM Lauf genau der
    Vorgang durch, an dem die Drosselung zuschlägt.
    """
    E = _eg()
    assert E._ABKUEHLUNG_S >= 360, "unter den gemessenen 6 Minuten hilft die Pause nicht"
    quelle = (ROOT / "govisor" / "docfetch_evergabe.py").read_text(encoding="utf-8")
    assert "nachzuholen" in quelle, "pausierte Vorgänge müssen nachgeholt werden"


def test_evergabe_schreibt_dorthin_wo_docpipe_sucht():
    """Ein ZIP je Vergabe unter `docs/<country>/<lead_id>/` — genau das Layout, das
    `docpipe.index` per `notice_dir.glob('*.zip')` liest. Damit laufen Volltext-Index,
    Signale, LV- und Kriterien-Extraktion ohne eine Zeile Änderung mit. Ein eigener Pfad
    hätte vier nachgelagerte Schritte gekostet."""
    quelle = (ROOT / "govisor" / "docfetch_evergabe.py").read_text(encoding="utf-8")
    assert '"docs" / country' in quelle
    assert 'out_root / lead_id' in quelle
    pipe = (ROOT / "govisor" / "docpipe.py").read_text(encoding="utf-8")
    assert 'glob("*.zip")' in pipe, "Layout-Annahme geprüft — docpipe liest weiterhin *.zip"


def _hh():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import healyhudson
    return healyhudson


def test_healyhudson_kennt_alle_sechzehn_laender():
    """Der amtliche Bundesland-Schlüssel ist der einzige Parameter, den die Liste kennt.

    Er wurde nicht geraten: `auftraege.bayern.de` verlinkt „Zu den Ausschreibungen" selbst
    auf `/Dashboards/Dashboard_off?BL=09`. Fehlt ein Land in der Tabelle, fehlt es lautlos
    im Lauf — deshalb hier festgenagelt.
    """
    H = _hh()
    assert len(H.LAENDER) == 16
    assert H.LAENDER["BY"][0] == "09" and H.LAENDER["HH"][0] == "02"
    assert sorted(k for k, _ in H.LAENDER.values()) == [f"{i:02d}" for i in range(1, 17)]


def test_healyhudson_zerlegt_eine_trefferzeile_und_raet_nichts():
    """Titel, Verfahrensart und Vergabestelle stehen in der Zeile nur durch Leerraum
    getrennt — eine sichere Aufteilung ist daraus NICHT möglich. Sie bleibt deshalb
    ungetrennt in `beschreibung`. Ein falsch aufgeteilter Titel wäre schlimmer als ein
    ungeteilter: die Dubletten-Firewall vergleicht Titel."""
    H = _hh()
    s = H.zerlege("VOB Erweiterung Grundschule Simbach - Estrich Offenes Verfahren "
                  "Stadt Simbach a. Inn 21.07.2026 25.08.2026", "BY")
    assert s["vergabeart"] == "VOB"
    assert s["pub"] == "21.07.2026" and s["frist"] == "25.08.2026"
    assert "Simbach" in s["beschreibung"]
    assert "titel" not in s, "die Zeile gibt keinen sauberen Titel her — nicht so tun als ob"
    assert H.zerlege("Anzahl: 395", "BY") is None
    assert H.zerlege("VORDN. TITEL VERGABESTELLE PUBLIKATION FRIST", "BY") is None


def test_healyhudson_meldet_unvollstaendigkeit_statt_sie_zu_verschweigen():
    """Die Liste gibt je Abruf eine ZUFALLSAUSWAHL von ~25 Zeilen zurück, egal ob 2 oder
    395 Vorgänge gemeldet sind — sechs Abrufe auf Bayern ergaben kumuliert 91 von 395.
    Ein Lauf, der 60 % holt und „fertig" meldet, wäre schlimmer als gar keiner."""
    quelle = (ROOT / "govisor" / "healyhudson.py").read_text(encoding="utf-8")
    assert "unvollständig" in quelle
    assert "gemeldet" in quelle, "die Soll-Zahl der Seite muss mitgeführt werden"
    H = _hh()
    assert H._TROCKEN >= 3, "zu früh aufzuhören verwechselt Pech mit Vollständigkeit"


def _nsdoc():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import docfetch_netserver
    return docfetch_netserver


def test_netserver_unterlagen_gehen_ueber_publications_nicht_ueber_die_bekanntmachung():
    """Der eine Schritt, ohne den nichts geht.

    Die `documents_url` zeigt auf die BEKANNTMACHUNG — dort steht keine einzige Datei, und
    genau deshalb meldete die erste Stichprobe „keine Dateien, keine Knöpfe" und NetServer
    galt als gegated. Der Unterlagen-Bereich hängt am selben `TenderOID` mit
    `&thContext=publications`.
    """
    N = _nsdoc()
    roh = ("https://vergabe.landbw.de/NetServer/TenderingProcedureDetails"
           "?function=_Details&TenderOID=54321-NetTender-19f4ad487ff-1e39c6b0bec9148f")
    z = N.unterlagen_url(roh)
    assert z is not None and z.endswith("&thContext=publications")
    assert "54321-NetTender-19f4ad487ff-1e39c6b0bec9148f" in z
    assert N.unterlagen_url("https://example.org/x") is None
    assert N.unterlagen_url(None) is None


def test_netserver_nimmt_nur_die_neueste_version():
    """Die Tabelle führt ALLE Versionen; die Seite sagt selbst „Es gilt immer nur die
    aktuellste Version der Unterlagen." Gemessen lag Version 2 (11.08.) über Version 1
    (10.07.). Eine ältere zu ziehen wäre kein Teilerfolg, sondern eine falsche
    Leistungsbeschreibung im Produkt."""
    quelle = (ROOT / "govisor" / "docfetch_netserver.py").read_text(encoding="utf-8")
    assert "knoepfe[0]" in quelle, "die oberste Zeile ist die neueste Version"
    assert "aktuellste Version" in quelle, "die Begründung muss am Code stehen"


def test_netserver_wirft_grosse_pakete_nicht_weg():
    """Eine Autobahn-Vergabe mit 335 MB fiel durch die erste Grenze von 200 MB.

    Eine ganze Vergabeunterlage wegzuwerfen, weil sie groß ist, widerspricht dem Grundsatz,
    dass jede Vergabe zählt — und Platz ist da (1,6 TB frei bei 89 GB Bestand).
    """
    N = _nsdoc()
    assert N._MAX_ZIP >= 400 * 1024**2
    assert N._LAUF_BUDGET_MB > 0, "ohne Lauf-Budget zieht ein Lauf 30 GB am Stück"


def _hhdoc():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import docfetch_healyhudson
    return docfetch_healyhudson


def test_healyhudson_dateiname_ist_keine_mailadresse():
    """`kundendienst@deutsche-evergabe.de` endet auf `.de` und lief durch eine generische
    `\\.\\w{2,5}$`-Regel als Datei durch — gemessen bei drei von vier Vorgängen im ersten
    Probelauf. Geprüft wird deshalb gegen echte Dokumentendungen."""
    H = _hhdoc()
    assert H._MIT_ENDUNG.search("Vergabeunterlagen.pdf")
    assert H._MIT_ENDUNG.search("Leistungsverzeichnis.X83")
    assert not H._MIT_ENDUNG.search("kundendienst@deutsche-evergabe.de")
    assert not H._MIT_ENDUNG.search("www.beispiel.de")


def test_healyhudson_trennt_umleitung_von_leerer_vergabe():
    """Die Instanzen verhalten sich verschieden: Bahn und Hamburg geben Unterlagen heraus,
    `bieterzugang.deutsche-evergabe.de` leitet auf ein zentrales Dashboard ohne Dateien.
    Beides als „leer" zu melden würde eine PLATTFORM-Eigenschaft wie eine Eigenschaft der
    einzelnen Vergabe aussehen lassen — und niemand käme je auf die Idee nachzusehen."""
    quelle = (ROOT / "govisor" / "docfetch_healyhudson.py").read_text(encoding="utf-8")
    assert '"kein_downloadbereich"' in quelle
    assert '"leer"' in quelle
    assert "je_host" in quelle, "das Manifest muss nach Host aufschlüsseln"


def test_neue_quellen_sind_im_tageslauf_aber_inert():
    """Vorbereitet heißt verdrahtet, nicht scharf. Die drei neuen Schritte stehen im
    Tageslauf, laufen aber nur mit `GOVISOR_NEUE_QUELLEN=1` — `healyhudson` schreibt bisher
    nur Bronze, und die zwei Fetcher bringen mehrere Gigabyte je Lauf."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    # Geprüft wird der SCHALTER, nicht sein Vorgabewert. Der stand zuerst auf 0 (inert) und
    # wurde von der zweiten Sitzung auf 1 gestellt, nachdem die Quellen sich bewährt hatten —
    # eine bewusste Entscheidung, kein Regressionsfall. Ein Test, der den Vorgabewert
    # festnagelt, hätte diese Entscheidung als Fehler gemeldet.
    assert "GOVISOR_NEUE_QUELLEN:-" in lauf, "der Schalter muss existieren"
    for m in ("govisor.healyhudson", "govisor.docfetch_netserver",
              "govisor.docfetch_healyhudson", "govisor.docfetch_aumass",
              "govisor.docfetch_staatsanzeiger"):
        assert m in lauf, f"{m} fehlt im Tageslauf"
    # Berlin und Saarland laufen dagegen SOFORT mit — derselbe erprobte NetServer-Pfad.
    assert "hb,sn,mv,bw,he,be,sl" in lauf


def _au():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import docfetch_aumass
    return docfetch_aumass


def test_aumass_nummer_wird_grossgeschrieben():
    """Der Endpunkt erwartet GROSSBUCHSTABEN und liefert sonst nichts — ohne Fehlermeldung.

    Die URLs tragen die Nummer aber gemischt: 60 Leads als `av281953-eu`, 35 als
    `AV281953-A`. Wer sie durchreicht wie vorgefunden, verliert rund ein Drittel der
    Vorgänge lautlos.
    """
    A = _au()
    assert A.aumass_id("https://plattform.aumass.de/Veroeffentlichung/av281953-eu") == "AV281953-EU"
    assert A.aumass_id("https://plattform.aumass.de/Veroeffentlichung/AV281953-A") == "AV281953-A"
    assert A.aumass_id("https://example.org/x") is None
    assert A.aumass_id(None) is None


def test_aumass_unterscheidet_ex_ante_von_ausfall():
    """Eine „EX ANTE BEKANNTMACHUNG" kündigt eine geplante Direktvergabe an — es gibt nichts
    zu bieten und entsprechend nichts herunterzuladen. Gemessen an AV281974-A.

    Das als `fehler` zu führen würde eine korrekte Seite wie einen Ausfall aussehen lassen
    und jeden Lauf mit falschen Warnungen belasten — bis niemand mehr hinsieht.
    """
    quelle = (ROOT / "govisor" / "docfetch_aumass.py").read_text(encoding="utf-8")
    assert '"ohne_unterlagen"' in quelle
    assert "EX ANTE BEKANNTMACHUNG" in quelle


def test_aumass_geschwister_teilen_den_abruf():
    """288 Leads zeigen auf nur 269 Vergaben. Bei 24–188 MB je Paket ist ein doppelter
    Abruf nicht nur Verschwendung, sondern unnötige Last auf einem fremden System."""
    quelle = (ROOT / "govisor" / "docfetch_aumass.py").read_text(encoding="utf-8")
    assert "geschwister" in quelle and "kein zweiter Abruf" in quelle


def test_netserver_erkennt_am_pfad_nicht_am_hostnamen():
    """Sven fragte nach den zwei fehlenden BW-Portalen — die Antwort waren 26 fehlende Hosts.

    Gemessen 2026-08-14:  Hostliste 1.055 Leads · Pfad `/NetServer/` 1.524 · Vereinigung
    1.698. Die Liste übersah tender24, vmstart, Fraunhofer, Deutsche Rentenversicherung, die
    Städte München/Köln/Düsseldorf/Frankfurt, LVR, LWL … Der Pfad allein reicht aber auch
    nicht: 174 Leads liegen auf Hosts, die NetServer fahren, ohne den Pfad zu tragen
    (evergabe-mv 72, had.de 59, ausschreibungen.landbw 43). Deshalb BEIDES.
    """
    N = _nsdoc()
    assert N.ist_netserver("https://www.tender24.de/NetServer/TenderingProcedureDetails?x=1")
    assert N.ist_netserver("https://vergabe.vmstart.de/NetServer/x")
    assert N.ist_netserver("https://evergabe-mv.de/irgendwas")      # nur über die Liste
    assert not N.ist_netserver("https://example.org/NetServerFake")


def test_netserver_tauscht_das_servlet_nicht_nur_den_parameter():
    """Der Fehler, der drei HTTP 404 erzeugte, bevor er auffiel.

    Die Roh-URL kommt in zwei Formen — 803× `TenderingProcedureDetails?…&TenderOID=` und
    718× `PublicationControllerServlet?…&TWOID=`. Der TWOID-Wert funktioniert unverändert
    als TenderOID, aber das zweite Servlet kennt `function=_Details` nicht. Wer nur den
    Parameter ersetzt und den Pfad stehen lässt, baut eine 404-URL, die gültig aussieht.
    """
    N = _nsdoc()
    z = N.unterlagen_url("https://www.evergabe.sachsen.de/NetServer/"
                         "PublicationControllerServlet?function=Detail&TWOID=54321-Tender-abc")
    assert "TenderingProcedureDetails" in z and "PublicationControllerServlet" not in z
    assert "TenderOID=54321-Tender-abc" in z and z.endswith("&thContext=publications")


def _stanz():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import docfetch_staatsanzeiger
    return docfetch_staatsanzeiger


def test_staatsanzeiger_knopf_navigiert_und_laedt_nicht():
    """Der Fehler, der diese Quelle einen halben Tag als „unbaubar" dastehen liess.

    „Anonym als Zip" sieht aus wie ein Download-Knopf, ist aber eine Navigation auf
    `/aJs/DownlAsAnonym`. Ein `expect_download` läuft in den Timeout, obwohl alles
    funktioniert — der ZIP-Link steht erst auf der Folgeseite, auf einem ANDEREN Host
    (`…-eservices.eu` statt `.de`). Dazu kam ein zu enger XPath, der den Knopf beim zweiten
    Aufruf nicht fand; daraus wurde die Fehldiagnose „die Seite rendert inkonsistent".
    Beides war falsch.
    """
    S = _stanz()
    quelle = (ROOT / "govisor" / "docfetch_staatsanzeiger.py").read_text(encoding="utf-8")
    assert "KEIN `expect_download`" in quelle, "die Begründung muss am Code stehen"
    assert S._ANONYM == "input[type=submit][value='Anonym als Zip']"
    assert S._ZIP.search('<a href="https://www.staatsanzeiger-eservices.eu/L_1_NC-1_TVZ-2.zip">')


def test_staatsanzeiger_frameset_ist_kein_fehler():
    """56 der 211 Leads tragen die zweite URL-Form `besuJs/BekLanding4Bund` — ein FRAMESET.
    `document.body.innerText` ist dort naturgemäß leer. Das als `fehler` zu führen belastet
    jeden Lauf mit 56 falschen Warnungen, bis niemand mehr hinsieht."""
    quelle = (ROOT / "govisor" / "docfetch_staatsanzeiger.py").read_text(encoding="utf-8")
    assert '"frameset"' in quelle and "len(pg.frames) > 1" in quelle

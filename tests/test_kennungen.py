"""Die Kennungs-Streuung: wann ist eine ``national_id`` keine Kennung?

⚠ DIE WICHTIGSTEN TESTS HIER SIND DIE GEGENPROBEN, nicht die Treffer. Die erste Regel-
variante am 2026-10-06 zählte den Beleg nur über die NAMEN und hätte damit echte Auftraggeber
zerschlagen: ``9110002556748`` (Land Niederösterreich mit zehn Strassenbauabteilungen, 7.189
Zeilen) fiel auf 48 %, ``9110015233841`` (Bundesimmobiliengesellschaft, 12.736 Zeilen) auf
28 %, weil hundert seltene Schreibvarianten dort so viel wiegen wie die dominanten Namen.
``test_dominante_zeilen_retten_dachkennung`` und ``test_variantenschwanz_kippt_nicht`` halten
diesen Fehler fest; wer die Zeilen-Zählung wieder ausbaut, sieht hier rot.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from govisor import kennungen, entities                      # noqa: E402
from govisor.gold import normalize_national_id, resolve_supplier, Method   # noqa: E402


def _streu(saetze, **kw):
    return kennungen.streuung(saetze, schluessel=normalize_national_id, **kw)


def _fuell(n, praefix="Fuellfirma"):
    """Grundrauschen: n Kennungen mit je einem Namen — setzt p99 auf 1, damit der
    Entartungsschutz die Schwelle bestimmt und die Fälle unten darüber liegen."""
    return [(f"HRB{i:05d}", f"{praefix} {i} GmbH", 1) for i in range(n)]


# ── 1. Der Befund selbst ─────────────────────────────────────────────────────────────────

def test_platzhalter_mit_fremden_namen_wird_verworfen():
    """„keine Angabe" von vielen fremden Stellen geteilt → keine Kennung."""
    fremde = ["Universitaetsklinikum Aachen", "Bremer Baeder GmbH", "Deutscher Bundestag",
              "Muenchen Klinik gGmbH", "Alfred-Wegener-Institut", "Handelskammer Hamburg",
              "Amt Siek Der Amtsvorsteher", "Stadtwerke Flensburg"]
    s = _streu([("keine Angabe", n, 1) for n in fremde] + _fuell(300))
    assert "keineAngabe" in s.platzhalter
    b = next(b for b in s.befunde if b.kennung == "keineAngabe")
    assert b.namen == len(fremde)
    assert b.beleg < kennungen.BELEG_MINDEST


def test_echte_registernummer_bleibt_trotz_streuung():
    """Form wie Müll, Inhalt echt: 'Fraunhofer …'-Varianten teilen einen Token.

    Gemessen ist das `00002636` bzw. `DE129515865` — genau die Fälle, an denen eine
    Positivliste verbotener Zeichenketten scheitert.
    """
    namen = ["Fraunhofer-Gesellschaft Einkauf B12",
             "Fraunhofer-Gesellschaft zur Foerderung der angewandten Forschung e.V.",
             "Fraunhofer-Gesellschaft Einkauf und Geraetewirtschaft C2",
             "Fraunhofer-Institut fuer Angewandte und Integrierte Sicherheit AISEC",
             "Fraunhofer-Institut fuer Bauphysik",
             "Fraunhofer-Institut fuer Lasertechnik",
             "Fraunhofer IZM Berlin", "Fraunhofer ISE Freiburg"]
    s = _streu([("00002636", n, 1) for n in namen] + _fuell(300))
    assert "00002636" not in s.platzhalter
    b = next(b for b in s.befunde if b.kennung == "00002636")
    assert b.urteil == "traegt" and b.token == "fraunhofer"
    assert b.beleg >= kennungen.BELEG_SICHER


def test_drei_urteile_nicht_zwei():
    """Starker Beleg → ``traegt``, kein Beleg → ``platzhalter``, Mitte → ``verdacht``.

    ⚠ GEGENPROBE GEGEN EINEN ECHTEN FEHLER. Der erste Entwurf kannte nur „fällt" und „fällt
    nicht"; der Wächter meldete daraufhin 66 Kennungen als unentschieden, darunter ÖBB,
    Fraunhofer und die Autobahn GmbH mit 97–100 % Beleg. Wer die Grenze ``BELEG_SICHER``
    wieder ausbaut, macht aus der Sonde einen Arbeitsvorrat voller richtiger Treffer.
    """
    rausch = _fuell(300)
    stark = _streu([("A1", f"Oebb Infrastruktur Bereich {i}", 1) for i in range(8)] + rausch)
    mitte = _streu([("A2", f"Oebb Infrastruktur Bereich {i}", 1) for i in range(4)]
                   + [(f"A2", f"Quasselbude{i} Zwirbel{i}weg", 1) for i in range(4)] + rausch)
    keiner = _streu([("A3", f"Quasselbude{i} Zwirbel{i}weg Behelf{i}", 1) for i in range(8)] + rausch)
    assert next(b for b in stark.befunde if b.kennung == "A1").urteil == "traegt"
    assert next(b for b in mitte.befunde if b.kennung == "A2").urteil == "verdacht"
    assert next(b for b in keiner.befunde if b.kennung == "A3").urteil == "platzhalter"
    # Nur das verworfene Urteil wirkt auf die Auflösung — die anderen zwei lassen sie in Ruhe.
    assert stark.platzhalter == frozenset() and mitte.platzhalter == frozenset()
    assert keiner.platzhalter == frozenset({"A3"})


def test_grenzen_fassen_die_senke_ein():
    """Die Begründung der beiden Grenzen: das gemessene Tal liegt zwischen ihnen."""
    assert kennungen.BELEG_MINDEST < kennungen.BELEG_SICHER
    # Zweigipfelige Lage nachgebaut: viele mit starkem Beleg, viele ohne, wenige dazwischen.
    saetze = _fuell(400)
    for i in range(20):
        saetze += [(f"S{i}", f"Sammelstelle{i} Werk {j} Abteilung", 1) for j in range(8)]
    for i in range(20):
        saetze += [(f"M{i}", f"Quasselbude{i}{j} Zwirbel{i}{j}weg Behelf{i}{j}", 1)
                   for j in range(8)]
    s = _streu(saetze)
    tal = kennungen.senke(s)
    assert tal == -1.0 or kennungen.BELEG_MINDEST < tal < kennungen.BELEG_SICHER


# ── 2. Die Gegenproben gegen die erste, falsche Regelvariante ────────────────────────────

def test_dominante_zeilen_retten_dachkennung():
    """Land Niederösterreich: wenige dominante Namen, langer Variantenschwanz.

    Nach NAMEN gezählt liegt der Beleg unter der Grenze, nach ZEILEN weit darüber. Die
    Kennung darf NICHT fallen — sonst zerfällt ein echter Auftraggeber in zehn Abteilungen.
    """
    kern = [("Land Niederoesterreich, p.A. Amt der NOE-Landesregierung", 862),
            ("Land Niederoesterreich, p.A. NOE Strassenbauabteilung 7", 682),
            ("Land Niederoesterreich, p.A. NOE Strassenbauabteilung 8", 563),
            ("Land Niederoesterreich, p.A. NOE Strassenbauabteilung 6", 473)]
    # ⚠ Der Schwanz muss UNTEREINANDER verschieden sein. Ein erster Entwurf nannte ihn
    # „Sonderfall Vergabestelle Variante i" — dann teilte der Schwanz selbst einen Token und
    # der Namens-Anteil stand bei 91 %, womit der Test nichts mehr prüfte.
    schwanz = [(f"Quasselbude{i} Zwirbel{i}strasse Behelf{i}", 1) for i in range(40)]
    saetze = [("9110002556748", n, z) for n, z in kern + schwanz] + _fuell(300)
    s = _streu(saetze)
    b = next(b for b in s.befunde if b.kennung == "9110002556748")
    assert b.anteil_namen < kennungen.BELEG_MINDEST, "Namens-Zählung allein würde hier irren"
    assert b.anteil_zeilen >= kennungen.BELEG_MINDEST, "Zeilen-Zählung muss sie retten"
    assert "9110002556748" not in s.platzhalter


def test_variantenschwanz_kippt_nicht():
    """Bundesimmobiliengesellschaft: ein Name, hundert Schreibweisen, ein Auftraggeber."""
    kern = [("Bundesimmobiliengesellschaft m.b.H.", 1025),
            ("Bundesimmobiliengesellschaft m.b.H. Unternehmensbereich Schulen", 268)]
    schwanz = [(f"Bundesimmobiliengesellschaft m.b.H. Bereich {i}", 1) for i in range(30)]
    fremd = [(f"Ganz fremde Stelle {i}", 1) for i in range(20)]
    s = _streu([("9110015233841", n, z) for n, z in kern + schwanz + fremd] + _fuell(300))
    assert "9110015233841" not in s.platzhalter


def test_streuender_platzhalter_ohne_dominanz_faellt():
    """Gegenstück: viele fremde Namen, keiner dominiert — das ist der echte Befund.

    Gemessen `13754`: 103 Namen in 102 Orten, lauter fremde Gemeinden.
    """
    namen = ["Landratsamt Straubing-Bogen", "Gemeinde Wehrheim", "Stadt Schriesheim",
             "Kreisstadt St. Wendel", "Markt Dinkelscherben", "Markt Bad Steben",
             "Stadt Forchheim", "Stadtverwaltung Lorch", "Gemeinde Hohenstein"]
    s = _streu([("13754", n, 8) for n in namen] + _fuell(300))
    assert "13754" in s.platzhalter, "Stadt/Gemeinde/Markt sind Stoppwörter, kein Beleg"


# ── 3. Die Schwelle wird gemessen, nicht getippt ─────────────────────────────────────────

def test_schwelle_folgt_der_streuung_der_quelle():
    """Eine Quelle mit breiter Streuung bekommt eine höhere Schwelle als eine schmale."""
    schmal = _streu(_fuell(300))
    breit = _streu(_fuell(300) + [(f"HRB9{i:04d}", f"Firma {i} Zweig {j} GmbH", 1)
                                  for i in range(60) for j in range(12)])
    assert breit.rohe_schwelle > schmal.rohe_schwelle
    assert breit.schwelle > schmal.schwelle


def test_entartungsschutz_bei_winziger_quelle():
    """p99 kann bei einer kleinen Quelle auf 1 fallen — dann darf die Regel nicht
    behaupten, zwei Schreibweisen eines Namens seien ein Platzhalter."""
    s = _streu([("HRB1", "Alpha GmbH", 1), ("HRB2", "Beta GmbH", 1),
                ("HRB3", "Gamma Bau GmbH", 1), ("HRB3", "Gamma Bau Gesellschaft", 1)])
    assert s.rohe_schwelle < kennungen.MINDEST_SCHWELLE
    assert s.schwelle == kennungen.MINDEST_SCHWELLE and s.schwelle_gegriffen
    assert not s.platzhalter


def test_schwelle_steht_im_ergebnis():
    """Die Schwelle muss mitgeliefert werden, sonst ist sie nicht nachrechenbar."""
    s = _streu(_fuell(300))
    assert s.schwelle >= 1 and s.perzentil == kennungen.SCHWELLEN_PERZENTIL
    assert s.beleg_mindest == kennungen.BELEG_MINDEST


# ── 4. Kein Datenverlust ─────────────────────────────────────────────────────────────────

def test_verworfene_kennung_faellt_auf_namen_zurueck():
    """Der Satz verschwindet nicht — er wird über den Namen aufgelöst."""
    ohne = resolve_supplier("Bremer Baeder GmbH", national_id="keine Angabe")
    assert ohne.entity_id == "id:keineAngabe" and ohne.method is Method.TED_NATIONAL_ID
    mit = resolve_supplier("Bremer Baeder GmbH", national_id="keine Angabe",
                           platzhalter=frozenset({"keineAngabe"}))
    assert mit.entity_id == "name:bremer baeder"
    assert mit.method is Method.NAME_ONLY and mit.entity_id


def test_zwei_fremde_namen_trennen_sich_wieder():
    """Der eigentliche Zweck: zwei fremde Stellen mit demselben Platzhalter werden zwei."""
    p = frozenset({"keineAngabe"})
    a = resolve_supplier("Universitaetsklinikum Aachen", national_id="keine Angabe", platzhalter=p)
    b = resolve_supplier("Bremer Baeder GmbH", national_id="keine Angabe", platzhalter=p)
    assert a.entity_id != b.entity_id


def test_nicht_betroffene_kennung_bleibt_schluessel():
    r = resolve_supplier("Irgendeine Firma GmbH", national_id="HRB 12345 XY",
                         platzhalter=frozenset({"keineAngabe"}))
    assert r.entity_id == "id:HRB12345XY" and r.method is Method.TED_NATIONAL_ID


# ── 5. Handentscheidungen haben Vorrang, in beide Richtungen ─────────────────────────────

def test_handurteil_lesen(tmp_path):
    p = tmp_path / "DE_kennung_entscheidung.csv"
    p.write_text("kennung,urteil,grund\nabc,traegt,belegt\nxyz,PLATZHALTER,Portalmuell\n",
                 encoding="utf-8")
    u = kennungen.entscheidungen_lesen([p])
    assert u == {"abc": "traegt", "xyz": "platzhalter"}


def test_erster_pfad_gewinnt(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("kennung,urteil\nabc,traegt\n", encoding="utf-8")
    b.write_text("kennung,urteil\nabc,platzhalter\n", encoding="utf-8")
    assert kennungen.entscheidungen_lesen([a, b])["abc"] == "traegt"


def test_fehlende_datei_ist_kein_fehler(tmp_path):
    assert kennungen.entscheidungen_lesen([tmp_path / "gibtsnicht.csv"]) == {}


# ── 6. Die Senke, die die 30 % begründet ─────────────────────────────────────────────────

def test_senke_schweigt_bei_zu_wenig_befunden():
    """Ohne genug Befunde ist ein „Tal" Rauschen — dann darf sie nichts behaupten."""
    s = _streu([("keine Angabe", f"Fremde Stelle {i}", 1) for i in range(9)] + _fuell(300))
    assert kennungen.senke(s) == -1.0


# ── 7. Der verschobene Token-Helfer verhält sich unverändert ─────────────────────────────

def test_signifikante_token_unveraendert():
    from govisor import gold
    assert gold._vat_tokens is entities.signifikante_token
    assert gold._VAT_STOP is entities.STOPP_TOKEN
    assert entities.signifikante_token("stadt koeln abfallwirtschaft") == {"koeln", "abfallwirtschaft"}
    assert entities.signifikante_token("") == set()

"""Haelt `scripts/pruefe_entity_dubletten.py` ehrlich.

Die Tests pruefen WIRKUNG, nicht Vokabeln (Fallenkatalog F10). Jeder Fall unten ist ein
Paar aus dem echten DE-Bestand vom 2026-09-11, mit seinem gemessenen Urteil daneben — wer
eine Schranke verschiebt, sieht sofort, welcher Fall kippt.

⚠ Zwei Tests sind Zeugen fuer einen FUND, nicht fuer eine Vorliebe:

  · `test_umlaut_wird_gefaltet_nicht_geloescht` haelt fest, dass die naheliegende Fassung
    `[^[:alnum:]]` Müller und Möller verschmilzt (150 Paare im Bestand). Er prueft BEIDE
    Fassungen, damit der Unterschied belegt bleibt und nicht zur Folklore wird.
  · `test_grenzverschiebung_*` haelt fest, dass `ASE GmbH` und `ASEG mbH` denselben
    strengen Schluessel tragen und trotzdem zwei Firmen sind (HRB232448 Bruchsal gegen
    HRB27950 Jena).
"""
import importlib.util
import pathlib
import collections

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "pruefe_entity_dubletten", ROOT / "scripts" / "pruefe_entity_dubletten.py")
ped = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ped)


def mitglied(name, *, plz=(), ort=(), identity_id=None, entity_id=None, nid=(), land="DE"):
    """Ein Kandidat, so wie `sammle()` ihn aufbaut — nur von Hand."""
    iid = identity_id or f"solo:name:{name.lower()}"
    eid = entity_id or iid.split("solo:", 1)[-1]
    return dict(
        identity_id=iid,
        entity_ids={eid},
        namen=collections.Counter({name: 1}),
        plz=set(plz), ort=set(ort), nid=set(nid),
        jahre={2024}, notices={"x"},
        stamm=ped.stamm(name, land),
        hr=ped._hr_schluessel(iid, eid),
        vat=ped._vats(set(nid)),
    )


def urteile(a, b, regionen=None):
    if regionen is None:
        regionen = {p[:2] for m in (a, b) for p in m["plz"]}
    return ped.beurteile("egal", a, b, regionen)


# ── Der strenge Schluessel ───────────────────────────────────────────────────────────

def test_leerzeichen_verschwindet():
    """Der einzige Gewinn der Regel: `H. Klostermann` und `H.Klostermann` werden gleich."""
    assert (ped.streng("H. Klostermann Baugesellschaft mbH")
            == ped.streng("H.Klostermann Baugesellschaft mbH"))


def test_umlaut_wird_gefaltet_nicht_geloescht():
    """F2 — gemessen: die naive Fassung erzeugt 150 Paare, die es sonst nicht gibt.

    Der Test prueft BEIDE Fassungen. Ohne die zweite Haelfte waere er nur eine Meinung:
    man saehe nicht, dass die naheliegende Schreibweise den Fehler wirklich macht.
    """
    assert ped.streng("Müller") == "mueller"
    assert ped.streng("Müller") != ped.streng("Möller")
    # ... und so sieht der Fehler aus, den wir vermeiden:
    assert ped.streng_naiv("Müller") == ped.streng_naiv("Möller") == "mller"


def test_stamm_trennt_die_rechtsform_ab():
    assert ped.stamm("ASE GmbH", "DE") == "ase"
    assert ped.stamm("ASEG mbH", "DE") == "aseg"


def test_stamm_ist_laenderfaehig():
    """Die Rechtsformen kommen aus dem Laenderprofil, nicht aus einer DE-Liste."""
    assert ped.stamm("Beispiel SARL", "LU") == "beispiel"
    assert ped.stamm("Beispiel GmbH", "AT") == "beispiel"


# ── Die drei Fallen ──────────────────────────────────────────────────────────────────

def test_grenzverschiebung_traegt_denselben_schluessel():
    """Die Voraussetzung des Fundes: ohne sie waere der Fall gar kein Kandidat."""
    assert ped.streng("ASE GmbH") == ped.streng("ASEG mbH") == "asegmbh"


def test_grenzverschiebung_wird_zurueckgestellt():
    """F1 — echte Paarung: HRB232448 Bruchsal gegen HRB27950 Jena."""
    a = mitglied("Ase GmbH", plz={"76646"}, ort={"bruchsal"},
                 identity_id="solo:hr:B8535_HRB232448")
    b = mitglied("ASEG mbH", plz={"07747"}, ort={"jena"},
                 identity_id="solo:hr:R1202_HRB27950")
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("namensfalle", "grenzverschiebung")


def test_kontaktfragment_ist_kein_firmenname():
    """F3 — 1.065 Paare im DE-Bestand sind Telefon-/Adressblöcke, keine Firmen."""
    a = mitglied("Tel. 0251/28503-0. Fax 0251/28503-23.", plz={"48143"})
    b = mitglied("Tel. 0251/285030. Fax 0251/2850323.", plz={"48143"})
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("namensfalle", "kontaktfragment")


def test_gattungsname_ueber_mehreren_regionen():
    """`Forstunternehmen` stand auf 35315/36396/56348/72297 — vier Regionen, vier Firmen."""
    a = mitglied("Forstunternehmen", plz={"56348"})
    b = mitglied("Forstunternehmen", plz={"35315", "36396", "72297"})
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("namensfalle", "gattungsname")


def test_kuerzel_ohne_gemeinsame_plz():
    """Bei einem Kuerzel entscheidet ein Zeichen — ohne Ortszeugen wird nicht verschmolzen."""
    a = mitglied("S.T.E.R.N. GmbH", ort={"berlin"})
    b = mitglied("Stern GmbH", ort={"deggendorf"})
    urteil, code, _ = urteile(a, b)
    assert urteil == "namensfalle" and code == "kuerzel"


# ── Widersprueche ────────────────────────────────────────────────────────────────────

def test_zwei_registereintraege_sind_ein_widerspruch():
    """`Joba GmbH` Toenisvorst (HRA8450) gegen `JO BA GmbH` Bremen (HRB18516)."""
    a = mitglied("Joba GmbH", plz={"47918"}, identity_id="solo:hr:D2404V_HRA8450")
    b = mitglied("Joba GmbH", plz={"28309"}, identity_id="solo:hr:H1101_HRB18516")
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("widerspruch", "register")


def test_getrennte_plz_ist_ein_widerspruch():
    a = mitglied("Protectis GmbH", plz={"22113"}, ort={"hamburg"})
    b = mitglied("protectis GmbH", plz={"28217"}, ort={"bremen"})
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("widerspruch", "plz")


def test_zwei_ustidnr_sind_ein_widerspruch():
    a = mitglied("R.O.M. Bauunternehmung GmbH", plz={"14473"}, nid={"DE235890016"})
    b = mitglied("R.O.M. Bauunternehmung GmbH", plz={"14473"}, nid={"DE354736183"})
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("widerspruch", "ustidnr")


# ── Belege ───────────────────────────────────────────────────────────────────────────

def test_gemeinsame_plz_belegt():
    a = mitglied("WesterWald Elektrotechnik Hummrich GmbH & Co. KG", plz={"57627"})
    b = mitglied("WesterwaldElektrotechnik Hummrich GmbH + Co. KG", plz={"57627"})
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("belegt", "plz")


def test_gemeinsamer_ort_belegt_wenn_keine_plz_dasteht():
    a = mitglied("Mickan General-Bau-Gesellschaft Amberg mbH & Co. KG", ort={"amberg"})
    b = mitglied("Mickan General-Bau-Gesellschaft Amberg mbH & Co. KG", ort={"amberg"})
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("belegt", "ort")


def test_ohne_jeden_zeugen_bleibt_es_unbelegt():
    a = mitglied("Librapharm Handelsgesellschaft GmbH")
    b = mitglied("Libra-Pharm Handelsgesellschaft GmbH")
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("unbelegt", "kein_zeuge")


# ── Die Reihenfolge der Beweislast ───────────────────────────────────────────────────

def test_widerspruch_schlaegt_beleg():
    """Ein Paar kann gleichzeitig einen Ortsbeleg und einen Registerwiderspruch haben.

    Dann gewinnt der Widerspruch — sonst waere die Reihenfolge Dekoration. Gemessen an
    `ZwickRoell` (beide Ulm 89079, HRB4401 gegen HRA1980).
    """
    a = mitglied("Zwick Roell GmbH & Co. KG", plz={"89079"}, ort={"ulm"},
                 identity_id="solo:hr:B8537_HRB4401")
    b = mitglied("ZwickRoell GmbH & Co. KG", plz={"89079"}, ort={"ulm"},
                 identity_id="solo:hr:B8537_HRA1980")
    urteil, _, _ = urteile(a, b)
    assert urteil == "widerspruch"


def test_namensfalle_schlaegt_widerspruch():
    """Erst die Frage, ob ueberhaupt ein Firmenname vorliegt — dann alles andere."""
    a = mitglied("Tel. 030 123456.", plz={"10115"})
    b = mitglied("Tel. 030 12 34 56.", plz={"80331"})
    urteil, code, _ = urteile(a, b)
    assert (urteil, code) == ("namensfalle", "kontaktfragment")


# ── Ein Merge ist transitiv ──────────────────────────────────────────────────────────

def test_zwei_paare_ergeben_drei_verschmolzene():
    """A~B und B~C heisst A~C — auch wenn A und C nie verglichen wurden.

    Genau das misst der Waechter am Ende: die Paarzahl sagt NICHT, wie gross die
    Zusammenfuehrung wird. Im DE-Bestand entsteht aus 7.339 belegten Paaren ein Klumpen
    von 1.679 Identitaeten.
    """
    klumpen, _ = ped.transitive_huelle([("A", "B"), ("B", "C")])
    assert [sorted(k) for k in klumpen] == [["A", "B", "C"]]


def test_getrennte_paare_bleiben_getrennt():
    """Die Gegenrichtung — sonst wuerde der Test auch bei „alles ist eins" bestehen."""
    klumpen, _ = ped.transitive_huelle([("A", "B"), ("C", "D")])
    assert sorted(sorted(k) for k in klumpen) == [["A", "B"], ["C", "D"]]


def test_die_nabe_wird_beim_namen_genannt():
    """Im Bestand sind es ausnahmslos Muellkennungen: `solo:id:keineAngabe` mit 508 Kanten."""
    paare = [("nabe", f"firma{i}") for i in range(5)] + [("x", "y")]
    _, naben = ped.transitive_huelle(paare)
    assert naben[0] == ("nabe", 5)


def test_ein_einzelnes_paar_ist_schon_ein_klumpen():
    klumpen, _ = ped.transitive_huelle([("A", "B")])
    assert [sorted(k) for k in klumpen] == [["A", "B"]]


def test_ohne_paare_kein_klumpen():
    assert ped.transitive_huelle([]) == ([], [])


# ── Der Waechter schreibt nichts ─────────────────────────────────────────────────────

def test_kein_schreibpfad_im_skript():
    """Ein Waechter, der schreiben kann, ist keiner mehr.

    Geprueft wird der SYNTAXBAUM, nicht der Text — sonst findet der Test seinen eigenen
    Erklaertext im Modulkopf (Fallenkatalog F13, dreimal an einem Tag passiert).
    """
    import ast
    baum = ast.parse((ROOT / "scripts" / "pruefe_entity_dubletten.py").read_text())
    verboten = {"to_parquet", "write_parquet", "mkdir", "rename", "unlink", "write_text",
                "write_bytes"}
    gefunden = {n.func.attr for n in ast.walk(baum)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in verboten}
    assert not gefunden, f"Schreibaufruf im Waechter: {sorted(gefunden)}"
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == "open" for n in ast.walk(baum))


def test_schranken_sind_begruendet():
    """Jede Schranke traegt im Modulkopf eine gemessene Begruendung.

    Ohne das wandert eine Zahl irgendwann nach oben, weil der Waechter laestig wurde.
    """
    kopf = ped.__doc__ or ""
    assert "2026-07-19" in kopf, "der verworfene Fuzzy-Versuch muss genannt bleiben"
    for stichwort in ("Grenzverschiebung", "Umlaut", "Platzhaltername"):
        assert stichwort in kopf


@pytest.mark.parametrize("land", ["DE", "AT", "CH", "LU"])
def test_laeuft_fuer_jedes_gebaute_land(land):
    """EU-weit: der Waechter darf nicht an einem Land haengenbleiben, das er nicht kennt.

    Geprueft wird nur die Namensmechanik — die Datenlage bleibt aussen vor, damit der
    Test nicht an einem Nachtlauf haengt.
    """
    assert ped.stamm("Beispiel GmbH", land)
    assert ped.streng("Beispiel GmbH") == "beispielgmbh"

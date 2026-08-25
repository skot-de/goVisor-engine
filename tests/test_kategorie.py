"""Kategorie-Ableitung für Ausschreibungen ohne CPV — Wasserfall + Lernschleife."""
from pathlib import Path


from govisor import kategorie as K

_QUELLE = (Path(__file__).resolve().parent.parent / "govisor" / "kategorie.py").read_text(
    encoding="utf-8")

_KAT = {"45": ("Bauarbeiten", None), "72": ("IT-Dienste", None)}


def _frag(K, faelle, antwort):
    """`frag_modell` mit gestubbter Gegenstelle — kein Netz, kein Geld."""
    import json

    import requests

    class _Antwort:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": json.dumps({"v": antwort})}}]}

    alt = requests.post
    requests.post = lambda *a, **kw: _Antwort()
    try:
        return K.frag_modell(faelle, _KAT, [], "testkey")
    finally:
        requests.post = alt


def test_wasserfall_reihenfolge_nach_belegkraft():
    """korrektur → zwilling → regelwerk → modell. Die Reihenfolge IST die Aussage.

    Ein veröffentlichter CPV des Zwillings ist ein Fakt, die Modell-Ableitung eine
    Schätzung mit gemessen ~82 %. Stünde das Modell weiter vorn, überschriebe eine
    Schätzung einen Beleg — und im Produkt sähe man den Unterschied nicht mehr.
    """
    b = _QUELLE.split("def bestimme")[1].split("\ndef ")[0]
    i = b.index('("korrektur"'), b.index('("zwilling"'), b.index('("regelwerk"')
    assert i[0] < i[1] < i[2], "Belegstufen nicht absteigend"
    assert b.index('("regelwerk"') < b.index("mit_modell and"), "Modell nicht zuletzt"


def test_lernschleife_speist_korrekturen_in_den_prompt():
    """Ohne diesen Rückfluss ist es keine Lernschleife, sondern nur eine Übersteuerung.

    Korrekturen wirken doppelt: sofort für ihre eigene Vergabe, und als Beispiele für
    alle weiteren. Fällt der zweite Teil weg, korrigiert der Nutzer dieselbe Sorte Fehler
    immer wieder.
    """
    p = _QUELLE.split("def _prompt")[1].split("\ndef ")[0]
    assert "beispiele" in p and "FRUEHERE KORREKTUREN" in p
    b = _QUELLE.split("def bestimme")[1].split("\ndef ")[0]
    assert "lade_korrekturen(country)[:LERN_BEISPIELE]" in b, "Beispiele erreichen den Prompt nicht"


def test_modell_darf_unbekannt_sagen():
    """Raten ist schädlicher als ein ehrliches Unbekannt.

    Ein falsch einsortierter Lead taucht in einer Fachsuche auf, in die er nicht gehört,
    und verdrängt dort einen echten. Ein unsortierter steht im Sammelbecken — sichtbar,
    aber unschädlich. Die Antwort `99` darf deshalb nie als Division durchgehen.
    """
    assert K.UNBEKANNT == "99"
    # ⚠ VERHALTEN PRUEFEN, NICHT DIE QUELLTEXTZEILE. Hier stand
    # `assert "if d in kat" in f` — der Test brach am 2026-08-25 an einer rein
    # gleichbedeutenden Umformulierung (`if d not in kat: continue`), waehrend er einen
    # echten Rueckschritt nicht bemerkt haette. Dieselbe Falle hat der Waechter der
    # Budgetbremse schon einmal gestellt (Commit 0271db6).
    erg = _frag(K, [("n1", "Rohbau"), ("n2", "Server")],
                [{"id": "n1", "div": "99"},        # UNBEKANNT
                 {"id": "n2", "div": "72"},        # gueltig
                 {"id": "n3", "div": "45"}])       # nie gesendet
    assert "n1" not in erg, "UNBEKANNT (99) darf keine Division werden"
    assert erg.get("n2") == "72", "eine gueltige Antwort muss durchkommen"


def test_modell_kennung_wird_gegen_die_anfrage_geprueft():
    """Ein Schluessel aus einer Modellantwort ist kein Schluessel, bis er belegt ist.

    Gemessen am 2026-08-25 im Bestand: 60 von 499 modellabgeleiteten NetServer-Zeilen in
    `lead_kategorie` trugen einen Doppelpunkt zu viel (`ns:he:6559bb29329c3878:`), weil
    die Prompt-Zeile `id={n}: "..."` lautete und NetServer-Kennungen selbst Doppelpunkte
    enthalten. Alle 60 waren Leads im Produkt — mit ermittelter Branche, die niemand sah,
    weil der Join ins Leere lief. Dazu zwei frei erfundene Kennungen.
    """
    erg = _frag(K, [("ns:he:6559bb29329c3878", "Netzwerk")],
                [{"id": "ns:he:6559bb29329c3878:", "div": "72"}])
    assert erg == {"ns:he:6559bb29329c3878": "72"}, "angehaengtes Trennzeichen nicht repariert"

    erg = _frag(K, [("ns:he:6559bb29329c3878", "Netzwerk")],
                [{"id": "ns:he:ausgedacht", "div": "72"}])
    assert erg == {}, "eine nie gesendete Kennung darf nicht nach Gold durchkommen"


def test_kein_erfundener_cpv_main():
    """Die Modellausgabe darf NICHT in den CPV-Raum.

    Ein geratener `cpv_main` verfälscht Branchenzählungen und lässt den Lead in
    Fachsuchen auftauchen, als wäre der Code veröffentlicht. Deshalb eine eigene Tabelle
    mit eigener Herkunftsspalte.
    """
    s = _QUELLE.split("def schreibe")[1].split("\ndef ")[0]
    assert "lead_kategorie.parquet" in s
    assert "cpv_main" not in s, "schreibt in den CPV-Raum"
    for spalte in ("quelle", "modell", "stand"):
        assert f'("{spalte}"' in s, f"Herkunftsspalte {spalte} fehlt"


def test_korrekturdatei_folgt_dem_kuratierungs_muster():
    """Gleiches Muster wie `DE_entity_aliases.csv` — menschlich gepflegt, versioniert."""
    p = K.korrektur_pfad("DE")
    assert p.parent.name == "curated"
    if p.exists():
        kopf = p.read_text(encoding="utf-8").splitlines()[0]
        for s in ("notice_id", "division", "titel", "grund", "stand"):
            assert s in kopf, f"Spalte {s} fehlt"


def test_zwilling_nimmt_nur_die_staerkste_belegstufe():
    """Ein Zwilling auf `nur_titel_kurz` ist bei generischen Titeln reines Rauschen."""
    z = _QUELLE.split("def aus_zwilling")[1].split("\ndef ")[0]
    assert "beleg = 'kaeufer_und_titel'" in z

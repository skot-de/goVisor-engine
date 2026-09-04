"""Der dritte Ableitungsweg: Verwaltungseinheit im Kaeufernamen.

⚠ Er ist der SCHWAECHSTE der drei — der Name einer Landesbehoerde sagt ihre Zustaendigkeit,
nicht zwingend den Ort der Leistung. Genau deshalb haengt er im Selbsttest und wird bei
Widerspruch verworfen. Die Faelle hier sind die vier, an denen eine naive Fassung scheitert.
"""
import importlib.util
import pathlib

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def ra():
    spec = importlib.util.spec_from_file_location(
        "ra_test", WURZEL / "scripts" / "region_ableiten.py")
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


@pytest.fixture(scope="module")
def einheiten(ra):
    d = ra._verwaltungseinheiten("DE")
    if not d:
        pytest.skip("kein dim_nuts/Ortsverzeichnis")
    return {" ".join(ra._worte(k)): v for k, v in d.items() if ra._worte(k)}


def test_klarer_fall(ra, einheiten):
    assert ra.einheit_im_namen(
        "Vermögens- und Hochbauverwaltung Baden-Württemberg", einheiten) == "DE1"
    assert ra.einheit_im_namen("Landeswohlfahrtsverband Hessen", einheiten) == "DE7"


def test_mehrdeutig_gibt_nichts(ra, einheiten):
    """⚠ „Deutsche Rentenversicherung Berlin-Brandenburg" nennt ZWEI Laender.

    Wer hier eines waehlt, raet — und nach diesem Wert wird gefiltert.
    """
    assert ra.einheit_im_namen(
        "Deutsche Rentenversicherung Berlin-Brandenburg", einheiten) is None


def test_teilzeichenkette_gibt_nichts(ra, einheiten):
    """⚠ „Sachsenforst" ist EIN Wort und kein Sachsen.

    Der Preis ist ehrlich: dieser Kaeufer faellt raus. Lieber 14 Leads weniger als ein
    Verfahren der Klasse „ahlen in Zahlenwerk" (s. `_worte`).
    """
    assert ra.einheit_im_namen(
        "Staatsbetrieb Sachsenforst - Forstbezirk Neudorf", einheiten) is None


def test_laengster_treffer_gewinnt(ra, einheiten):
    """⚠ „Sachsen-Anhalt" schlaegt „Sachsen" — sonst waeren es zwei Codes und das Ergebnis
    waere nichts."""
    assert ra.einheit_im_namen("Kulturstiftung Sachsen-Anhalt", einheiten) == "DEE"


def test_der_weg_haengt_im_selbsttest(ra):
    """⚠ Die eigentliche Zusicherung: er darf nicht an der Pruefung vorbei.

    Gemessen am 2026-09-04 an 19 pruefbaren Widerspruechen (Kaeufer-PLZ als Zeuge) lag in
    19 von 19 Faellen der VERWALTUNGSNAME richtig und der Ortsname falsch — „Landgesellschaft
    Sachsen-Anhalt" traf ueber das Wort „anhalt" einen bayerischen Ort. Die gestiegene
    Widerspruchsquote (5,6 % → 8,5 %) ist deshalb keine Verschlechterung, sondern die
    Sichtbarkeit vorhandener Fehlableitungen.
    """
    quelle = (WURZEL / "scripts" / "region_ableiten.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("signale = {"):quelle.index("aus.append({\"lead_id\"")]
    assert '"verwaltungsname": einheit_im_namen' in block
    assert "if len(werte) > 1:" in block, "der Widerspruchs-Riegel muss ALLE Signale sehen"
    assert "uneinig += 1" in block


def test_namensgleiche_orte_werden_berechnet_nicht_getippt():
    """⚠ DORF SCHLAEGT BUNDESLAND — zwei Namen, und sie kosteten 78 Leads.

    Im deutschen Ortsverzeichnis heisst „hessen" ein Ort im Landkreis Harz (DEE) und
    „sachsen" einer bei Ansbach (DE2). Der Ortsabgleich lieferte fuer
    „Landeswohlfahrtsverband Hessen" also DEE, der Verwaltungsname DE7 — Widerspruch, beide
    verworfen. In einem KAEUFERNAMEN ist die Landesbehoerde die weit wahrscheinlichere
    Lesart als das Dorf.

    Der Test haelt zweierlei fest: dass die Menge BERECHNET wird, und dass der Ortstreffer
    dabei WEGFAELLT statt zu gewinnen — eine Mehrheit von eins waere keine.
    """
    quelle = (WURZEL / "scripts" / "region_ableiten.py").read_text(encoding="utf-8")
    assert "namensgleich = {k for k, v in einheiten_gefaltet.items()" in quelle, (
        "die Menge muss aus den Daten kommen, nicht aus einer getippten Liste")
    block = quelle[quelle.index("namensgleich = {"):quelle.index('aus.append({"lead_id"')]
    assert 'signale["ortsname"] = None' in block, (
        "der Ortstreffer muss WEGFALLEN, nicht ueberstimmt werden")


def test_der_ortsabgleich_kennt_die_kollision_wirklich(ra):
    """Gegenprobe an den echten Daten: „hessen" und „sachsen" zeigen woanders hin."""
    orte = ra.ortsverzeichnis("DE")
    einheiten = ra._verwaltungseinheiten("DE")
    if not orte or not einheiten:
        pytest.skip("kein Ortsverzeichnis")
    gefaltet = {" ".join(ra._worte(k)): v for k, v in einheiten.items() if ra._worte(k)}
    kollision = {k for k, v in gefaltet.items() if orte.get(k) not in (None, v)}
    # Waeren es ploetzlich viele, haette sich am Ortsverzeichnis etwas Grundlegendes
    # geaendert — dann gehoert die Regel neu bewertet, nicht stillschweigend ausgeweitet.
    assert kollision <= {"hessen", "sachsen"}, f"neue Namensgleichheit: {kollision}"


def test_eindeutiges_praefix_schlaegt_das_kuerzere_wort(ra):
    """⚠ „Betriebshof Bad Homburg" lag im SAARLAND.

    Das Verzeichnis fuehrt „bad homburg vor der hoehe" (DE7, Hessen) und „homburg" (DEC,
    Saarland). Die Folge „bad homburg" ist kein Schluessel — also fiel der Abgleich auf das
    kuerzere Wort zurueck, ins falsche Bundesland. Amtliche Ortsnamen sind laenger als das,
    was ein Kaeufer schreibt; die Kurzform ist der Normalfall.

    Zwei Riegel halten es davon ab, Raten zu werden, und beide stehen hier:
      · mindestens ZWEI Woerter  — „Stadt Neustadt" bleibt ohne Ergebnis
      · GENAU EIN Eintrag        — „neustadt" ist Praefix von Dutzenden
    """
    orte = ra.ortsverzeichnis("DE")
    if not orte:
        pytest.skip("kein Ortsverzeichnis")
    srt = sorted(orte)
    assert ra.ort_im_namen("Betriebshof Bad Homburg", orte, srt) == "DE7"
    assert ra.ort_im_namen("Stadt Neustadt", orte, srt) is None
    # Der echte Saarlaender bleibt unberuehrt.
    assert ra.ort_im_namen("Amt Homburg", orte, srt) == "DEC"


def test_die_praefixsuche_laeuft_ueber_bisektion():
    """⚠ Ein Riegel darf nicht teurer sein als das, was er verhindert.

    Die erste Fassung tastete je Wortfolge alle 11.520 Eintraege ab und verlangsamte den
    DE-Lauf von 1,9 s auf 77 s — fuer 15 Namen. Jetzt Bisektion ueber `sortiert`.
    """
    quelle = (WURZEL / "scripts" / "region_ableiten.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("def ort_im_namen"):quelle.index("def einheit_im_namen")]
    assert "bisect.bisect_left(sortiert" in block
    assert "orte.items() if k.startswith" not in block, "keine Vollabtastung je Wortfolge"

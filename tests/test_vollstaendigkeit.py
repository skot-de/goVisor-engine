"""Haelt die Vollstaendigkeitsrechnung ehrlich (`scripts/pruefe_vollstaendigkeit.py`).

WARUM. Die Sonde macht genau EINE Zusage: jeder holbare Lead traegt genau einen Zustand,
und die Summe der Klassen ist die Gesamtzahl. Eine Rechnung, die still etwas fallen laesst,
ist schlimmer als keine — sie sieht aus wie eine Zusage und ist keine.

⚠ Die Akte `docs/dokumentdecke-de.md` haelt fest, dass bei genau dieser Frage schon DREI
Messfehler hintereinander als „Befund" gemeldet wurden (ueberzeichneter Rueckstand,
abgeschnittene URL, uebersehenes Praedikat). Ihre Lehre: „bei einer Zahl, die eine
Entscheidung traegt, gehoert eine Gegenprobe IN DEN CODE." Diese Datei ist diese Gegenprobe.
"""
import csv
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import pruefe_vollstaendigkeit as v                     # noqa: E402

LISTE = ROOT / "curated" / "portale_ohne_abrufer.csv"


def test_host_nimmt_den_query_nicht_mit():
    """Der Fehler, der die erste Fassung unbrauchbar machte.

    `vergabeplattform.charite.de?tid=…` erschien als 19 verschiedene Portale, weil eine URL
    OHNE Pfad ihren Query an den Rechnernamen haengt. Jede neue Sitzungskennung waere ein
    „neues Portal" gewesen und damit jede Nacht ein Befund.
    """
    a = v._host("https://vergabeplattform.charite.de?tid=f758f740b4291f9046cb")
    b = v._host("https://vergabeplattform.charite.de?tid=8bcf9b7b2c49d3431c75")
    assert a == b == "vergabeplattform.charite.de"


def test_host_ohne_port_und_klein():
    assert v._host("https://plattform.aumass.de:443/x") == "plattform.aumass.de"
    assert v._host("https://WWW.DTVP.DE/Satellite/notice/CX1") == "www.dtvp.de"


def test_host_bleibt_bei_muell_stumm():
    """Eine kaputte Adresse darf die Sonde nicht abbrechen."""
    assert v._host("") == "?"
    assert v._host("kein-schema") == "?"


def test_rib_steht_in_der_praedikatliste():
    """⚠ Der Fehler vom 2026-09-24: `rueckstau.abrufer()` kennt `docfetch_rib` NICHT.

    `is_rib` wird aus `docfetch._waehle_connector` heraus gerufen und schreibt ins
    cosinex-Manifest, taucht aber in keiner Abrufer-Registry auf. Wer die Registry fuer
    vollstaendig haelt, zaehlt die `meinauftrag.rib.de`-Leads als unabgedeckt — bei der
    ersten Messung waren das 652 Leads zu viel (4.363 statt 3.711).
    """
    namen = {kurz for kurz, _ in v.praedikate()}
    assert "rib" in namen, "is_rib fehlt — meinauftrag.rib.de zaehlt sonst als unabgedeckt"
    treffer = [kurz for kurz, f in v.praedikate()
               if v._trifft(f, "https://www.meinauftrag.rib.de/public/"
                               "DetailsByPlatformIdAndTenderId/platformId/1/tenderId/302443")]
    assert treffer, "eine echte meinauftrag-Adresse findet keinen Abrufer"


def test_jeder_abrufer_bringt_ein_praedikat_mit():
    """Ein Abrufer ohne Pruefer waere eine stumme Luecke: seine Leads gaelten als
    unabgedeckt, obwohl ein Modul fuer sie da ist."""
    from scripts.rueckstau import abrufer
    namen = {kurz for kurz, _ in v.praedikate()}
    fehlen = sorted(set(abrufer()) - namen)
    assert not fehlen, f"diese Abrufer tragen kein ist_/is_-Praedikat: {fehlen}"


def test_klassen_decken_jeden_bekannten_status():
    """Jeder Status, den `docfetch_queue` kennt, muss in einer Klasse landen.

    Sonst faellt ein Lead in „sperre", obwohl er dauerhaft erledigt ist — die Summe ginge
    weiter auf, die Aussage waere trotzdem falsch.
    """
    from govisor.docfetch_queue import BLOCKIERT, DAUERHAFT, KEIN_FEHLSCHLAG, WARTET
    for st in set(DAUERHAFT) | set(KEIN_FEHLSCHLAG) | set(BLOCKIERT) | set(WARTET):
        k = v._klasse(st)
        assert k, f"Status {st!r} landet in keiner Klasse"
    assert v._klasse("downloaded") == "geholt"
    assert v._klasse("weg") == "dauerhaft"
    assert v._klasse("gated").startswith("blockiert:")


def test_erklaerung_deckt_die_ausgabeordnung():
    """Jede Klasse der festen Ordnung braucht einen Klartext, sonst steht im Protokoll ein
    nackter Schluessel."""
    fehlen = [k for k in v.ORDNUNG if k not in v.ERKLAERUNG]
    assert not fehlen, f"ohne Erklaerungstext: {fehlen}"


def test_bekannte_luecke_ist_lesbar_und_vollstaendig():
    """Die kuratierte Liste traegt fuer jede Zeile einen Grund. Eine Zeile ohne Grund ist
    eine stillgelegte Warnung ohne Begruendung — genau das, was sie verhindern soll."""
    assert LISTE.exists(), f"{LISTE.name} fehlt"
    with LISTE.open(encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))
    assert zeilen, "die Liste ist leer"
    for z in zeilen:
        assert z["host"].strip(), f"Zeile ohne Host: {z}"
        assert z["grund"].strip(), f"{z['host']}: kein Grund angegeben"
        assert z["stand"].strip(), f"{z['host']}: kein Stand angegeben"


def test_bekannte_luecke_traegt_nur_blanke_hosts():
    """⚠ Sonst greift der Abgleich nicht. Steht dort eine ganze URL, findet
    `bekannte_luecke()` den Host nie wieder und die Sonde schlaegt jede Nacht an."""
    for h in v.bekannte_luecke():
        assert v._host(f"https://{h}/") == h, (
            f"{h!r} ist kein blanker Rechnername (Schema, Pfad oder Query drin?)")


@pytest.mark.parametrize("land", ["DE", "LU"])
def test_die_summe_geht_auf(land):
    """Die eigentliche Zusage, an den echten Daten.

    ⚠ Ueberspringt sich, wenn das Land keine Leaddatei hat — ein fehlender Bestand ist die
    Sache anderer Sonden, nicht dieser.
    """
    if not (ROOT / "data" / "gold" / land / "lead_export.parquet").exists():
        pytest.skip(f"kein lead_export fuer {land}")
    klassen, _, grund = v.rechne(land)
    if not grund:
        pytest.skip(f"{land} hat keine holbaren Leads")
    assert sum(klassen.values()) == grund, (
        f"{land}: Klassen summieren auf {sum(klassen.values()):,}, "
        f"holbar sind {grund:,} — es faellt etwas stumm heraus")


def test_open_house_bleibt_draussen():
    """⚠ Open House gehoert nicht in die Grundmenge (Begruendung in `rueckstau.rueckstand`).

    Zaehlt man es mit, sieht die Luecke doppelt so gross aus: in DE waren es am 2026-09-24
    2.067 Leads. Genau dieser Fehler hat an dem Tag zu einem Fehlbefund gefuehrt.
    """
    import duckdb
    p = ROOT / "data" / "gold" / "DE" / "lead_export.parquet"
    if not p.exists():
        pytest.skip("kein lead_export fuer DE")
    con = duckdb.connect()
    oh, alle = con.execute(f"""select
        count(*) filter (where coalesce(procedure_kind,'') = 'open_house'),
        count(*)
        from read_parquet('{p.as_posix()}')
        where phase='open' and documents_url is not null
          and deadline_date > current_date""").fetchone()
    con.close()
    if not oh:
        pytest.skip("keine Open-House-Leads im Bestand")
    _, _, grund = v.rechne("DE")
    assert grund == alle - oh, (
        f"Grundmenge {grund:,} != {alle:,} minus {oh:,} Open House")


def test_gesperrte_portale_werden_nicht_als_ungeprueft_gefuehrt():
    """⚠ „Kleinportal, ungeprueft" ist eine Absichtserklaerung, kein Befund. Bei zwei
    Hosts war sie am 2026-09-26 nachweislich falsch, und der Unterschied entscheidet
    darueber, ob jemand Arbeit in einen Abrufer steckt:

      * `xvergabe.de` verbietet in robots.txt den GANZEN Host (User-agent: * / Disallow: /)
      * `evoportal.vergabe.staatsanzeiger.de` antwortet auf JEDE Seite mit HTTP 401,
        auch auf robots.txt

    Beides ist keine Frage des Parsers. Wer das als „ungeprueft" fuehrt, laedt den
    naechsten ein, es noch einmal zu versuchen.
    """
    import csv

    with LISTE.open(encoding="utf-8") as f:
        nach_host = {z["host"]: z for z in csv.DictReader(f)}
    for host, wort in (("xvergabe.de", "robots.txt"),
                       ("evoportal.vergabe.staatsanzeiger.de", "401")):
        z = nach_host.get(host)
        if z is None:
            continue                       # der Host kann aus dem Bestand fallen
        assert wort in z["grund"], f"{host}: der gemessene Grund fehlt ({wort})"
        assert "ungeprueft" not in z["grund"], (
            f"{host}: steht wieder als ungeprueft da, obwohl die Sperre gemessen ist")

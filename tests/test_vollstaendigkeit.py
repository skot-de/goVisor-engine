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


def test_gesperrte_hosts_stehen_nicht_in_der_abrufer_luecke():
    """⚠ ZWEI LISTEN, ZWEI AUSSAGEN — und sie duerfen sich nicht ueberschneiden.
    `portale_ohne_abrufer.csv` sagt „hier fehlt ein Abrufer" und laedt ein, einen zu bauen.
    `hosts_gesperrt.csv` sagt das Gegenteil: es gibt einen, und er muss schweigen. Stuende
    ein gesperrter Host in der ersten Liste, baute irgendwann jemand einen Abrufer gegen
    eine robots.txt.
    """
    import csv

    from govisor import docfetch_queue as _queue

    with LISTE.open(encoding="utf-8") as f:
        ohne_abrufer = {z["host"].strip().lower() for z in csv.DictReader(f)}
    doppelt = ohne_abrufer & set(_queue.gesperrte_hosts())
    assert not doppelt, f"stehen in beiden Listen: {sorted(doppelt)}"


def test_querverweise_nennen_die_richtige_liste():
    """⚠ DIESEN FEHLER HABE ICH SELBST GEBAUT (2026-09-26). Die LMBV-Zeile endete mit
    „xvergabe.de steht in dieser Liste bereits" — und im selben Arbeitsgang habe ich
    xvergabe.de aus dieser Liste genommen, weil der Host seitdem gesperrt ist und in
    `hosts_gesperrt.csv` gehoert. Der Satz war damit falsch, und zwar auf die teuerste Art:
    er beantwortet genau die Frage, die der naechste Leser hat, und schickt ihn ins Leere.

    ⚠ DIE ERSTE FASSUNG DIESES TESTS HAETTE DEN FEHLER VERFEHLT. Sie fragte nur, ob der
    genannte Host in IRGENDEINER der beiden Listen steht — xvergabe.de stand ja in der
    Sperrliste, der falsche Satz waere gruen geblieben. Gefordert ist deshalb, dass der Text
    die Liste nennt, in der der Host WIRKLICH steht. Die Verwechslung der beiden Listen ist
    der ganze Punkt: „hier fehlt ein Abrufer" gegen „hier darf keiner fragen".
    """
    import csv
    import re

    # Dateinamen sehen wie Hostnamen aus. `robots.txt`, `hosts_gesperrt.csv` und
    # `docfetch_queue.py` sind genau die Woerter, die in diesen Begruendungen vorkommen.
    DATEI = re.compile(r"\.(csv|py|txt|json|md|sh|xml|zip|parquet)$")

    with LISTE.open(encoding="utf-8") as f:
        luecke = {z["host"].strip().lower(): (z.get("grund") or "") for z in csv.DictReader(f)}
    with (ROOT / "curated" / "hosts_gesperrt.csv").open(encoding="utf-8") as f:
        sperre = {z["host"].strip().lower() for z in csv.DictReader(f) if z.get("host")}

    geprueft = 0
    for host, text in luecke.items():
        erwaehnt = {m.lower() for m in re.findall(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", text)}
        for fremd in erwaehnt - {host}:
            if DATEI.search(fremd):
                continue
            geprueft += 1
            if fremd in sperre:
                assert "hosts_gesperrt" in text, (
                    f"{host}: nennt {fremd}, aber der Host ist GESPERRT und der Text verweist "
                    f"nicht auf curated/hosts_gesperrt.csv")
            elif fremd in luecke:
                assert "in dieser Liste" in text or "portale_ohne_abrufer" in text, (
                    f"{host}: nennt {fremd} ohne zu sagen, dass er in dieser Liste steht")
            else:
                raise AssertionError(
                    f"{host}: nennt {fremd} — der Host steht in keiner der beiden Listen, "
                    f"also gibt es zu ihm keine festgehaltene Haltung")
    assert geprueft, "kein einziger Querverweis geprueft — greift die Erkennung noch?"

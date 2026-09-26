"""Bei gesperrten Hosts wird gar nicht erst angeklopft — und nur beim Dokumentenholen.

⚠ DER BEFUND. Am 2026-09-26 standen **77 Saetze fuer `xvergabe.de`** im NetServer-Manifest.
Wir haben dort also geholt, obwohl die robots.txt des Hosts `User-agent: * / Disallow: /`
sagt. Aufgefallen ist es beim Nachsehen, ob sich ein Abrufer lohnt — nicht durch eine
Pruefung. Sven daraufhin: „lass den dokumenten sammler gar nicht erst bei den portalen
anfragen."

⚠ EIN LISTENEINTRAG WAERE DAS GEGENTEIL GEWESEN. `portale_ohne_abrufer.csv` sagt „hier
fehlt ein Abrufer" und laedt ein, einen zu bauen. Hier gibt es einen, und er muss
schweigen. Deshalb eine eigene Liste und eine Sperre, die VOR der Anfrage greift: wer erst
fragt und dann den 401 einsortiert, hat gefragt.

⚠ DIE SPERRE GILT NUR FUER DOKUMENTE, NICHT FUER AUSSCHREIBUNGEN. Sven hat genau danach
gefragt, und es ist der Punkt, an dem die Sache kippen koennte: die Bekanntmachungen kommen
aus TED/eForms und den Portal-Ingests, nicht aus dem Dokumentenabruf. Wuerde die Sperre
dort durchschlagen, verloeren wir 28 Ausschreibungen, um 77 unerlaubte Abrufe zu
vermeiden — ein schlechter Tausch und ein stiller dazu.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
from govisor import docfetch_queue as _queue  # noqa: E402
from govisor import docfetch_netserver as _ns  # noqa: E402

LISTE = WURZEL / "curated" / "hosts_gesperrt.csv"


def test_die_liste_nennt_je_host_einen_belegten_grund():
    import csv

    with LISTE.open(encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))
    assert zeilen, "die Sperrliste ist leer"
    for z in zeilen:
        assert z["host"].strip(), "Zeile ohne Host"
        assert z["grund"].strip() in ("robots", "anmeldung"), z["grund"]
        assert len(z["beleg"].strip()) > 40, f"{z['host']}: kein nachvollziehbarer Beleg"
        assert z["stand"].strip().count("-") == 2, f"{z['host']}: kein Stand"


def test_die_sperre_trifft_auch_www_und_unterdomaenen():
    assert _queue.ist_gesperrt("https://xvergabe.de/x") == "robots"
    assert _queue.ist_gesperrt("https://www.xvergabe.de/x") == "robots"
    assert _queue.ist_gesperrt("https://portal.xvergabe.de/x") == "robots"
    # ⚠ Die Grenze ist der Punkt, nicht die Zeichenfolge: `meinxvergabe.de` ist ein
    # anderer Host und darf nicht mitgesperrt werden.
    assert _queue.ist_gesperrt("https://meinxvergabe.de/x") is None
    assert _queue.ist_gesperrt("https://www.had.de/NetServer/x") is None


def test_der_dokumenten_abrufer_erkennt_den_host_nicht_mehr():
    """⚠ Die Erkennung war RICHTIG und das Ergebnis trotzdem falsch: `ist_netserver`
    trifft `xvergabe.de` ueber Pfad und Servlet-Namen, ganz ohne Hostliste."""
    gesperrt = "https://xvergabe.de/NetServer/TenderingProcedureDetails?function=_Details&TenderOID=1"
    erlaubt = "https://www.had.de/NetServer/TenderingProcedureDetails?function=_Details&TenderOID=1"
    assert not _ns.ist_netserver(gesperrt)
    assert _ns.ist_netserver(erlaubt), "die Sperre hat einen erlaubten Host miterwischt"
    # Und die Stelle, die wirklich abbricht, bevor etwas geladen wird:
    assert _ns.unterlagen_url(gesperrt) is None
    assert _ns.unterlagen_url(erlaubt) is not None


def test_die_auswahl_des_abrufers_laesst_gesperrte_gar_nicht_erst_zu():
    """⚠ ZWEITE FASSUNG DERSELBEN REGEL. Der Abrufer waehlt seine Arbeitsliste ueber
    eigenes SQL, nicht ueber `ist_netserver` — die Datei warnt selbst davor, dass zwei
    Fassungen auseinanderlaufen. Ohne diese Zeile stuenden gesperrte Vorgaenge weiter in
    der Liste und faenden erst eine Ebene spaeter ihr Ende."""
    quelle = (WURZEL / "govisor" / "docfetch_netserver.py").read_text(encoding="utf-8")
    i = quelle.index("wo = (\"documents_url LIKE")
    block = quelle[i:i + 1400]
    assert "gesperrte_hosts()" in block, "die Arbeitsliste kennt die Sperre nicht"
    assert "NOT LIKE" in block


def test_die_sperre_gilt_NICHT_fuer_den_ausschreibungs_ingest():
    """⚠ SVENS FRAGE, UND DIE WICHTIGSTE ZUSAGE HIER. Die Bekanntmachungen kommen aus
    TED/eForms und den Portal-Ingests. Griffe die Sperre dort, verloeren wir die
    Ausschreibungen selbst — 28 auf xvergabe.de, alle offen."""
    ingest = ("netserver", "cosinex", "dtvp", "healyhudson", "atverg", "simap", "doe",
              "schema", "normalize", "silver", "bulk")
    for name in ingest:
        p = WURZEL / "govisor" / f"{name}.py"
        if not p.exists():
            continue
        q = p.read_text(encoding="utf-8")
        assert "ist_gesperrt" not in q and "gesperrte_hosts" not in q, (
            f"govisor/{name}.py kennt die Dokumenten-Sperre — sie darf den Ingest der "
            "Ausschreibungen nicht beruehren")

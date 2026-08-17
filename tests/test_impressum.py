"""Impressum-Prüfer: Logik + Zwillingsabgleich Python↔TypeScript.

Der Prüfer existiert ZWEIMAL: `govisor/impressum.py` für den Stapelbetrieb und
`web/lib/impressum.ts` für den Request-Pfad (Python im Deploy wäre nicht serverless-
fähig). Die Doppelung ist bewusst, aber sie hat einen Preis: eine Regel kann in einer
Datei wandern und in der anderen stehenbleiben. Genau davor schützt der letzte Test.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from govisor import impressum as I

ROOT = Path(__file__).resolve().parent.parent
TS = ROOT / "web" / "lib" / "impressum.ts"


# ── Faltung ───────────────────────────────────────────────────────────────────────
def test_faltung_wirkt_auf_beiden_seiten():
    """Der Fehler, der beim Bauen wirklich passiert ist.

    Eine frühere Fassung faltete nur den Firmennamen: „Ed. Züblin AG" wurde zu
    ``zublin``, im Seitentext blieb „züblin" stehen und zerfiel zu „z blin". Das Urteil
    war WIDERLEGT für die eigene, korrekte Domain — ein Fehlurteil in genau die Richtung,
    die einen echten Kunden aussperrt.
    """
    assert I.kerne("Ed. Züblin AG") == {"zublin"}
    assert "zublin" in I.falte("Impressum der ZÜBLIN Direktion")
    # Beide Seiten treffen sich — das ist die Bedingung, die vorher verletzt war.
    assert next(iter(I.kerne("Ed. Züblin AG"))) in I.falte("ZÜBLIN AG, Stuttgart")


@pytest.mark.parametrize("roh,erwartet", [
    ("Straßenbau", "strassenbau".replace("ss", "s")),   # ß → s, wie in der Faltung
    ("Société Générale", "societe generale"),
    ("Kärcher", "karcher"),
])
def test_faltung_diakritika(roh, erwartet):
    assert I.falte(roh).strip() == erwartet


def test_kerne_wirft_rechtsform_weg():
    """„GmbH" steht in jedem zweiten Impressum Europas. Bliebe es ein Kernwort, würde
    jede beliebige Domain jede beliebige Firma bestätigen."""
    assert I.kerne("Klostermann Baugesellschaft mbH") == {"klostermann", "baugesellschaft"}
    assert I.kerne("Verwaltungs GmbH & Co. KG") == {"verwaltungs"}
    # Ein Name, der NUR aus Rechtsform besteht, ist nicht prüfbar — nicht „belegt".
    assert I.kerne("GmbH & Co. KG") == set()


def test_reiner_rechtsformname_ist_nicht_pruefbar():
    b = I.pruefe("example.com", "GmbH & Co. KG")
    assert b.urteil == I.NICHT_PRUEFBAR


# ── SSRF ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("host", ["localhost", "foo.local", "127.0.0.1", "10.0.0.5",
                                  "169.254.169.254", "[::1]", "boese.de/pfad"])
def test_ssrf_ziele_werden_nicht_abgerufen(host):
    """Die Domain kommt aus der Mailadresse, die der Nutzer eintippt. Ohne diese Sperre
    wäre der Endpunkt ein Portscanner für unser eigenes Netz."""
    b = I.pruefe(host, "Böse GmbH & Partner Bauunternehmung")
    assert b.urteil == I.NICHT_PRUEFBAR


# ── Die drei Urteile ──────────────────────────────────────────────────────────────
def _mit_seiten(monkeypatch, seiten: dict[str, str]):
    monkeypatch.setattr(I, "_oeffentlich", lambda h: True)
    monkeypatch.setattr(I, "_hole", lambda d, p: (p, seiten[p]) if p in seiten else None)


def test_belegt(monkeypatch):
    _mit_seiten(monkeypatch, {"/impressum":
                              "Impressum\nH. Klostermann Baugesellschaft mbH\nHamm\nHRB 1234"})
    b = I.pruefe("klostermann.de", "H. Klostermann Baugesellschaft mbH", ort="Hamm")
    assert b.urteil == I.BELEGT and b.quote == 1.0
    assert b.ort_belegt and b.register_belegt


def test_widerlegt_faengt_die_auftraggeber_domain(monkeypatch):
    """Der gemessene Kernfall: die einzige hinterlegte Mailadresse einer Firma ist die
    Portaladresse ihres AUFTRAGGEBERS (7,5 % der Gewinner-Mails). Der Mail-Hash allein
    hätte hier falsch bestätigt."""
    _mit_seiten(monkeypatch, {"/impressum": "Impressum\nDeutsche Bahn AG\nBerlin\nHRB 50000"})
    b = I.pruefe("deutschebahn.com", "LEONHARD WEISS GmbH & Co. KG")
    assert b.urteil == I.WIDERLEGT


def test_nicht_pruefbar_ist_kein_widerlegt(monkeypatch):
    """`hentschke-bau.de` und `cnhind.com` scheitern an kaputten Zertifikaten der
    GEGENSEITE (nachgemessen, auch mit curl). Wer das als „widerlegt" verbucht, sperrt
    eine echte Firma aus, weil ihr Hoster schlampt."""
    _mit_seiten(monkeypatch, {})
    b = I.pruefe("hentschke-bau.de", "Hentschke Bau GmbH")
    assert b.urteil == I.NICHT_PRUEFBAR


def test_startseite_ohne_kennung_zaehlt_nicht(monkeypatch):
    """Eine Startseite, die den Firmennamen trägt, ist KEIN Impressum — sonst genügte
    jede Seite, die den Namen irgendwo erwähnt (Presse, Referenzliste, Partnerlogo)."""
    _mit_seiten(monkeypatch, {"/": "Willkommen bei Hentschke Bau GmbH"})
    assert I.pruefe("fremd.de", "Hentschke Bau GmbH").urteil == I.NICHT_PRUEFBAR


# ── Zwillingsabgleich ─────────────────────────────────────────────────────────────
def test_zwillinge_kennen_dieselben_pfade():
    """Die Pfadliste trägt die EU-Weite (CLAUDE.md: jede Funktion gilt für ALLE Länder).
    Wächst sie nur in einer der beiden Dateien, prüft der Deploy weniger als der
    Stapelbetrieb — und niemand merkt es, weil beide für sich grün sind."""
    ts = TS.read_text(encoding="utf-8")
    block = re.search(r"const PFADE = \[(.*?)\];", ts, re.S)
    assert block, "PFADE in impressum.ts nicht gefunden"
    ts_pfade = set(re.findall(r'"([^"]+)"', block.group(1)))
    assert ts_pfade == set(I.PFADE), (
        f"Zwillinge driften auseinander:\n  nur Python: {set(I.PFADE) - ts_pfade}"
        f"\n  nur TS:     {ts_pfade - set(I.PFADE)}")


def test_zwillinge_teilen_die_schwelle():
    ts = TS.read_text(encoding="utf-8")
    m = re.search(r"schwelle = ([\d.]+)", ts)
    assert m and float(m.group(1)) == 0.5


def test_zwillinge_kennen_dieselben_urteile():
    ts = TS.read_text(encoding="utf-8")
    for wert in (I.BELEGT, I.WIDERLEGT, I.NICHT_PRUEFBAR):
        assert f'"{wert}"' in ts, f"Urteil {wert} fehlt in impressum.ts"

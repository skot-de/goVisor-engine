"""Der SSRF-Riegel der Dokument-Abrufer — ohne echtes Netz geprueft.

⚠ DER BEFUND (2026-09-28, Pentest). Die Abrufer (`docfetch`, `docfetch_rib`) holen
`documents_url` aus den Vergabedaten mit `allow_redirects=True`. Ein Portal, das auf
`http://169.254.169.254/…` oder `http://127.0.0.1/…` umleitet, liesse den Abruf ins eigene
Netz greifen — der Lauf sitzt auf dem Rechner, auf dem auch `.secrets/` liegt. `ssrf.hole`
verfolgt Umleitungen jetzt selbst und prueft JEDE Stufe.

Kein echtes DNS, kein echtes Netz: ein eingespeister Aufloeser bildet Namen auf Adressen ab,
eine Attrappen-Session liefert die Antworten. So ist auch die eigentliche Falle pruefbar —
dass ein interner Redirect gar nicht erst geholt wird.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
from govisor import ssrf  # noqa: E402


def _aufloeser(karte):
    """Fake-getaddrinfo: Name → Liste von IPs. Unbekannt → gaierror (wie echtes DNS)."""
    def f(host, port):
        if host not in karte:
            raise socket.gaierror(f"unbekannt: {host}")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in karte[host]]
    return f


class FakeResp:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {"location": location} if location else {}
        self.url = None


class FakeSession:
    """Beantwortet .get(url, ...) nach einem Plan {url: FakeResp} und merkt sich die Aufrufe."""
    def __init__(self, plan):
        self.plan = plan
        self.gerufen = []

    def get(self, url, timeout=None, allow_redirects=None, **kw):
        self.gerufen.append(url)
        r = self.plan[url]
        r.url = url
        return r


# ── host_ist_oeffentlich: IP-Literale ohne DNS ────────────────────────────────────────────

@pytest.mark.parametrize("ip,ok", [
    ("8.8.8.8", True), ("93.184.216.34", True),
    ("127.0.0.1", False), ("10.0.0.1", False), ("192.168.1.1", False),
    ("172.16.0.1", False), ("169.254.169.254", False),
    ("::1", False), ("::ffff:127.0.0.1", False), ("0.0.0.0", False),
])
def test_ip_literale(ip, ok):
    assert ssrf.host_ist_oeffentlich(ip) is ok


def test_dns_alle_adressen_muessen_oeffentlich_sein():
    auf = _aufloeser({"portal.example": ["93.184.216.34"],
                      "boese.example": ["93.184.216.34", "127.0.0.1"],  # eine interne genuegt
                      "leer.example": []})
    assert ssrf.host_ist_oeffentlich("portal.example", aufloeser=auf) is True
    assert ssrf.host_ist_oeffentlich("boese.example", aufloeser=auf) is False
    assert ssrf.host_ist_oeffentlich("unbekannt.example", aufloeser=auf) is False  # gaierror
    assert ssrf.host_ist_oeffentlich("leer.example", aufloeser=auf) is False        # 0 Adressen


# ── pruefe_url: Schema + Host ─────────────────────────────────────────────────────────────

def test_nur_http_und_https():
    with pytest.raises(ssrf.SsrfBlockiert):
        ssrf.pruefe_url("file:///etc/passwd")
    with pytest.raises(ssrf.SsrfBlockiert):
        ssrf.pruefe_url("gopher://x/")


def test_interner_host_wird_abgewiesen():
    auf = _aufloeser({"localhost": ["127.0.0.1"], "portal.example": ["93.184.216.34"]})
    with pytest.raises(ssrf.SsrfBlockiert):
        ssrf.pruefe_url("http://localhost/x", aufloeser=auf)
    ssrf.pruefe_url("https://portal.example/x", aufloeser=auf)  # wirft nicht


# ── hole: die eigentliche Falle, der interne Redirect ─────────────────────────────────────

def test_direkte_antwort_wird_durchgereicht():
    auf = _aufloeser({"portal.example": ["93.184.216.34"]})
    sess = FakeSession({"https://portal.example/z": FakeResp(200)})
    r = ssrf.hole(sess, "https://portal.example/z", timeout=5, aufloeser=auf)
    assert r.status_code == 200 and r.url == "https://portal.example/z"


def test_oeffentlicher_redirect_wird_verfolgt():
    auf = _aufloeser({"portal.example": ["93.184.216.34"], "cdn.example": ["93.184.216.35"]})
    sess = FakeSession({
        "https://portal.example/z": FakeResp(302, "https://cdn.example/datei.zip"),
        "https://cdn.example/datei.zip": FakeResp(200),
    })
    r = ssrf.hole(sess, "https://portal.example/z", timeout=5, aufloeser=auf)
    assert r.status_code == 200 and r.url == "https://cdn.example/datei.zip"


def test_interner_redirect_wird_geblockt_UND_nicht_geholt():
    """Der Kern: die Umleitung auf die interne Adresse darf nicht nur abgewiesen, sondern
    gar nicht erst angefragt werden — sonst ist der SSRF schon passiert."""
    auf = _aufloeser({"portal.example": ["93.184.216.34"], "intern.example": ["169.254.169.254"]})
    sess = FakeSession({
        "https://portal.example/z": FakeResp(302, "http://intern.example/latest/meta-data/"),
        "http://intern.example/latest/meta-data/": FakeResp(200),
    })
    with pytest.raises(ssrf.SsrfBlockiert):
        ssrf.hole(sess, "https://portal.example/z", timeout=5, aufloeser=auf)
    assert "http://intern.example/latest/meta-data/" not in sess.gerufen, \
        "die interne Adresse wurde geholt — der Riegel kam zu spaet"


def test_zu_viele_umleitungen():
    auf = _aufloeser({"a.example": ["93.184.216.34"]})
    # a → a (Endlosschleife); nach max_hops Schluss.
    sess = FakeSession({"https://a.example/": FakeResp(302, "https://a.example/")})
    with pytest.raises(ssrf.SsrfBlockiert):
        ssrf.hole(sess, "https://a.example/", timeout=5, max_hops=3, aufloeser=auf)

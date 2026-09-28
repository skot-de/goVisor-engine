"""SSRF-Riegel fuer die Dokument-Abrufer.

⚠ WARUM. Die Abrufer holen `documents_url` (aus den Vergabedaten) und folgen dabei
Umleitungen (`allow_redirects=True`). Zeigt eine solche URL — oder ihr Redirect-Ziel, oder
ein aus der Portalseite gelesener Datei-Link — auf eine INTERNE Adresse (127.0.0.1,
169.254.169.254, 10.0.0.0/8 …), holt der Abrufer Daten aus dem eigenen Netz statt vom
Portal. Der Abruf laeuft auf dem Nachtlauf-Rechner, also genau dort, wo `.secrets/` und
lokale Dienste liegen. Ein Portal, das eine 302 auf `http://169.254.169.254/…` setzt,
reicht.

Der Riegel loest den Host JEDER Stufe auf und weist ab, sobald EINE aufgeloeste Adresse
nicht oeffentlich ist. Fail-closed: was sich nicht aufloesen laesst, wird abgewiesen.

⚠ WAS ER NICHT LOEST: DNS-Rebinding. Zwischen unserer Aufloesung und dem Verbindungsaufbau
durch `requests` kann die DNS-Antwort wechseln. Dagegen hilft nur, die gepruefte IP
festzunageln und mit gesetztem Host-Header genau dorthin zu verbinden — ein eigener
`requests`-Adapter. Fuer einen Stapellauf gegen bekannte Portale ist die Hop-Pruefung die
verhaeltnismaessige Stufe; das Rebinding-Fenster ist als offener Punkt vermerkt.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit


class SsrfBlockiert(Exception):
    """Ziel zeigt auf eine nicht-oeffentliche Adresse (oder liess sich nicht aufloesen)."""


# 301/302/303/307/308 — alle Umleitungscodes. Auch die per Spezifikation methodenerhaltenden
# (307/308) verfolgen wir als GET: die Abrufer rufen ausschliesslich GET, und ein Wechsel
# der Methode kaeme hier ohnehin nicht vor.
_UMLEITUNG = {301, 302, 303, 307, 308}


def _ip_ist_oeffentlich(roh: str) -> bool:
    try:
        a = ipaddress.ip_address(roh)
    except ValueError:
        return False
    # IPv4-gemappte v6 (::ffff:127.0.0.1) auf die v4 herunterbrechen, sonst schluepft
    # Loopback als „global" durch.
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped is not None:
        a = a.ipv4_mapped
    return not (a.is_private or a.is_loopback or a.is_link_local
                or a.is_reserved or a.is_multicast or a.is_unspecified)


def host_ist_oeffentlich(host: str | None, *, aufloeser=socket.getaddrinfo) -> bool:
    """True nur, wenn der Host sich aufloest UND alle Adressen oeffentlich sind."""
    if not host:
        return False
    # IP-Literal ohne DNS pruefen.
    try:
        ipaddress.ip_address(host)
        return _ip_ist_oeffentlich(host)
    except ValueError:
        pass
    try:
        infos = aufloeser(host, None)
    except (socket.gaierror, OSError, UnicodeError):
        return False
    adressen = {eintrag[4][0] for eintrag in infos}
    # ⚠ ALLE muessen oeffentlich sein. Ein Host, der A→oeffentlich UND AAAA→::1 fuehrt,
    # ist ein Umgehungsversuch; es genuegt eine interne Adresse.
    return bool(adressen) and all(_ip_ist_oeffentlich(ip) for ip in adressen)


def pruefe_url(url: str, *, aufloeser=socket.getaddrinfo) -> None:
    """Wirft `SsrfBlockiert`, wenn `url` kein http(s) ist oder auf eine interne Adresse zeigt."""
    teile = urlsplit(url)
    if teile.scheme not in ("http", "https"):
        raise SsrfBlockiert(f"nur http/https zugelassen, nicht {teile.scheme!r}")
    if not host_ist_oeffentlich(teile.hostname, aufloeser=aufloeser):
        raise SsrfBlockiert(f"Host nicht oeffentlich: {teile.hostname!r}")


def hole(session, url: str, *, timeout, max_hops: int = 5,
         aufloeser=socket.getaddrinfo, **kw):
    """GET mit manueller, gepruefter Umleitungsverfolgung.

    Ersetzt `session.get(url, allow_redirects=True)`: jede Stufe — die Start-URL und jedes
    Redirect-Ziel — muss auf eine oeffentliche Adresse zeigen, sonst `SsrfBlockiert`. Die
    Antwort ist die letzte nicht-umleitende; ihr `.url` ist die zuletzt geholte Adresse
    (der Abrufer `docfetch_rib` verlaesst sich darauf).
    """
    kw.pop("allow_redirects", None)
    aktuell = url
    for _ in range(max_hops + 1):
        pruefe_url(aktuell, aufloeser=aufloeser)
        r = session.get(aktuell, timeout=timeout, allow_redirects=False, **kw)
        ort = r.headers.get("location")
        if r.status_code in _UMLEITUNG and ort:
            aktuell = urljoin(aktuell, ort)
            continue
        return r
    raise SsrfBlockiert(f"zu viele Umleitungen (>{max_hops})")

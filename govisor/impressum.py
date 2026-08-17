"""Gehört diese Domain dieser Firma? — Beleg über das Impressum.

**Warum das geht.** Wer eine geschäftsmäßige Website betreibt, muss eine Anbieterkennung
führen, und zwar mit Namen und Anschrift: § 5 DDG (Deutschland, vormals § 5 TMG), § 5 ECG
(Österreich), Art. 3 Abs. 1 lit. s UWG (Schweiz), Art. 5 der EU-Richtlinie 2000/31/EG als
gemeinsame Wurzel. Das ist der seltene Fall, in dem der Gesetzgeber uns die Datenquelle
garantiert, statt dass wir sie erraten müssen.

**Was hier NICHT passiert: die Domain suchen.** Das war die andere, viel schwerere Aufgabe
(gemessen 33–42 % Trefferquote über Namensmuster) und ist hier gegenstandslos: der Nutzer
tippt seine Mailadresse selbst ein, die Domain steht also fest. Zu klären ist allein, ob
sie ihm gehört.

**Warum es sich lohnt.** Gemessen am 2026-08-17 an 25 echten Firmen aus `notice_parties`:
Die stärkste Verunreinigung unserer Kontaktdaten sind Gewinner, deren einzige hinterlegte
Mailadresse die Portaladresse ihres *Auftraggebers* ist (7,5 % der Gewinner-Mails; 14 % der
Mail-Hashes hätten darüber falsch verifiziert). Der Impressum-Check hat alle acht solchen
Fälle abgelehnt (LEONHARD WEISS, STRABAG, Siemens Mobility … auf `deutschebahn.com`) und
die zwei echten Bahn-Töchter durchgelassen. Er trennt genau dort, wo der Mail-Hash blind war.

**Zeitbudget.** Median 3,25 s, p90 5,25 s, Maximum 5,81 s — die Kandidatenpfade laufen
gleichzeitig, die Gesamtzeit ist also die langsamste einzelne Anfrage, nicht ihre Summe.
Das passt in das Fenster zwischen „Registrieren" und dem Klick auf den Bestätigungslink.

**DREI Urteile, nicht zwei.** „Kein Beleg" und „widerlegt" sind verschiedene Dinge mit
verschiedenen Folgen, und die Messung hat gezeigt, warum: `hentschke-bau.de` und
`cnhind.com` scheitern an kaputten Zertifikaten der Gegenseite (auch mit ``curl``, also
nicht unser Fehler). Wer das als „widerlegt" verbucht, sperrt eine echte Firma aus, weil
ihr Hoster schlampt. Deshalb ``NICHT_PRUEFBAR`` als eigener Ausgang → zurück auf den
kalten Weg, nicht ablehnen.

Aufruf::

    from govisor.impressum import pruefe
    pruefe("klostermann.de", "H. Klostermann Baugesellschaft mbH", ort="Hamm")
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import urlsplit

import requests

BELEGT = "belegt"
WIDERLEGT = "widerlegt"
NICHT_PRUEFBAR = "nicht_pruefbar"

# goVisor ist EU-weit geplant (CLAUDE.md) — die Anbieterkennung heisst nicht ueberall
# „Impressum". Die Pflicht ist dieselbe (RL 2000/31/EG Art. 5), der Pfad nicht. Ohne
# diese Liste waere der Pruefer ein reines DE/AT/CH-Werkzeug.
PFADE = (
    "/impressum", "/impressum/", "/impressum.html", "/de/impressum",  # DE/AT/CH
    "/imprint", "/legal-notice", "/en/imprint",                        # englisch
    "/mentions-legales", "/fr/mentions-legales",                       # FR/BE/LU
    "/aviso-legal",                                                    # ES
    "/note-legali", "/it/note-legali",                                 # IT
    "/colofon", "/juridische-informatie",                              # NL/BE
    "/",                                                               # Startseite zuletzt
)

# Woran man eine Anbieterkennung erkennt, sprachunabhaengig.
_KENNUNG = re.compile(
    r"impressum|imprint|mentions\s+l[ée]gales|aviso\s+legal|note\s+legali|"
    r"colofon|legal\s+notice|anbieterkennzeichnung", re.I)

# Rechtsform-Woerter tragen NICHTS zur Zuordnung bei: „GmbH" steht in jedem zweiten
# Impressum Europas und wuerde jede beliebige Domain bestaetigen.
_RECHTSFORM = re.compile(
    r"\b(gmbh|ag|kg|ohg|mbh|se|ek|gbr|ug|co|kgaa|ggmbh|partg|mbb|bv|nv|sa|sas|sarl|srl|"
    r"spa|plc|ltd|inc|oy|ab|as|aps|gesellschaft|aktiengesellschaft|company|societe|"
    r"und|der|die|das|for|and)\b", re.I)

_REGISTER = re.compile(r"\b(hrb|hra|fn\s*\d|ch-\d|register|registre|registro)\s*[\d.]", re.I)

# Ein Link, dessen Ziel ODER dessen Beschriftung nach Anbieterkennung aussieht.
_LINK = re.compile(r'<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.{0,80}?)</a>', re.I | re.S)

KOPF = {"User-Agent": "goVisor/1.0 (+https://govisor.eu) Impressumspruefung",
        "Accept-Language": "de,en;q=0.8"}
FRIST = 5.0
MAX_BYTES = 400_000


_FALTUNG = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "s", "é": "e", "è": "e",
                          "ê": "e", "á": "a", "à": "a", "â": "a", "í": "i", "ó": "o",
                          "ô": "o", "ú": "u", "ç": "c", "ñ": "n", "å": "a", "ø": "o"})


def falte(s: str) -> str:
    """Text → kleingeschrieben, ohne Diakritika, Trennzeichen zu Leerraum.

    ⚠ Diese Funktion MUSS auf beide Seiten des Vergleichs angewandt werden, auf den
    Firmennamen UND auf den Seitentext. Eine frühere Fassung faltete nur den Namen:
    „Ed. Züblin AG" wurde zu ``zublin``, im Seitentext blieb „züblin" stehen und wurde
    beim Entfernen der Nicht-ASCII-Zeichen zu „z blin" zerrissen. Ergebnis war das
    Urteil WIDERLEGT für die eigene, korrekte Domain — ein Fehlurteil in genau die
    Richtung, die einen echten Kunden aussperrt.
    """
    return re.sub(r"[^a-z0-9]+", " ", s.lower().translate(_FALTUNG))


_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def umschrift(name: str) -> str:
    """„Bärmann" → „baermann".

    Deutsche Firmen schreiben ihren Namen im Web haeufig in Umschrift, weil Domains
    keine Umlaute vertragen: `baermann-partner.de`, `mueller.de`, `schroeder.com`. Die
    Faltung allein macht daraus `barmann` und trifft nie. Gemessen am 2026-08-17 war das
    einer von elf falsch Widerlegten — und es betrifft jede Firma mit Umlaut im Namen,
    also einen betraechtlichen Teil des deutschen Mittelstands.
    """
    return falte(name.lower().translate(_UMSCHRIFT))


# Organisationszusaetze. Was DAHINTER steht, benennt eine Untereinheit, keine Firma:
# „Ed. Züblin AG Bereich Bonn", „MAN Truck & Bus Deutschland GmbH - Verkauf Nutzfahrzeuge",
# „Matuczak Feuerschutz Inh. Florian Gripp". Gemessen am 2026-08-17 war das die Ursache
# fuer einen Teil der falsch Widerlegten: der Zusatz ist im Namensbestand SELTENER als der
# Markenname und wurde deshalb zum Traegerwort — auf der Firmenwebsite steht er aber nicht.
_ZUSATZ = re.compile(
    r"\b(bereich|direktion|niederlassung|zweigniederlassung|werk|filiale|standort|"
    r"geschaftsstelle|geschaeftsstelle|verkauf|vertrieb|region|abteilung|inh|inhaber|"
    r"betriebsstatte|betriebsstaette|division|branch|succursale)\b")


def stamm(name: str) -> str:
    """Firmenname ohne Organisationszusatz — alles ab dem Zusatzwort faellt weg."""
    f = falte(name)
    m = _ZUSATZ.search(f)
    gekuerzt = f[:m.start()].strip() if m else f
    return gekuerzt or f          # nie leer zurueckgeben


def kerne(name: str) -> set[str]:
    """Firmenname → bedeutungstragende Wortstämme (ohne Rechtsform, ohne Füllwörter).

    ⚠ Die Untergrenze liegt bei DREI Zeichen, nicht bei vier. Gemessen am 2026-08-17:
    bei vier fielen genau die Kürzel weg, die eine Firma ausmachen — „NEC Deutschland
    GmbH" behielt nur ``deutschland``, „BFT Planung GmbH" nur ``planung``. Beide wurden
    daraufhin auf einer wildfremden Domain zu 100 % „bestätigt". Die Regel warf also das
    Unterscheidende weg und behielt das Beliebige.
    """
    return {w for w in stamm(name).split()
            if len(w) >= 3 and not _RECHTSFORM.fullmatch(w) and not w.isdigit()}


# Wie oft kommt ein Wort in 317.146 Firmennamen vor? Gemessen, nicht geraten — eine
# handgeschriebene Stoppwortliste waere sofort veraltet und gaelte nur fuer Deutsch.
# Gespeichert sind nur Woerter ab 20 Vorkommen; alles Seltenere fehlt und gilt damit
# automatisch als unterscheidend. Aufgebaut aus `entities.parquet`.
_HAEUFIG: dict[str, int] | None = None
_TABELLE = Path(__file__).resolve().parent.parent / "data" / "reference" / "namenswoerter.json"


def haeufigkeit(wort: str) -> int:
    global _HAEUFIG
    if _HAEUFIG is None:
        try:
            _HAEUFIG = json.loads(_TABELLE.read_text(encoding="utf-8"))["zaehler"]
        except Exception:
            _HAEUFIG = {}
    return _HAEUFIG.get(wort, 0)


def traeger(k: set[str]) -> str | None:
    """Das Wort, das die Identität trägt: das seltenste im Firmennamen.

    **Warum das die entscheidende Regel ist.** Eine Quote von „die Hälfte der Wörter steht
    auf der Seite" ist wertlos, wenn die getroffene Hälfte aus Allerweltswörtern besteht.
    Gemessen an 200 verwürfelten Paaren (Firma A gegen die Domain von Firma B) kamen so
    5,5 % durch — jedes einzelne über Wörter wie ``planung``, ``deutschland``, ``technik``,
    ``systeme``, ``solution``. Sie stehen auf fast jeder deutschen Firmenseite.

    Das seltenste Wort ist dagegen genau das, was eine Firma von allen anderen trennt:
    ``klostermann`` (31 Namen), ``conet`` (21), ``fujitsu`` (51). Steht es nicht auf der
    Seite, ist es nicht ihre Seite — egal wie viel Beiwerk zufällig passt.
    """
    return min(k, key=lambda w: (haeufigkeit(w), -len(w))) if k else None


def _oeffentlich(host: str) -> bool:
    """Zeigt der Name auf eine öffentliche Adresse?

    Die Domain stammt aus der Mailadresse, die der Nutzer eintippt — also aus fremder
    Eingabe. Ein Server, der die ungeprüft abruft, ist ein SSRF-Loch: ``foo@localhost``
    oder eine Domain, die auf ``169.254.169.254`` zeigt, liesse ihn interne Dienste
    abfragen und das Ergebnis auch noch zurückmelden. Beim reinen Messen war das egal,
    beim Festeinbau nicht.
    """
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except Exception:
        return False
    if not infos:
        return False
    for inf in infos:
        ip = ipaddress.ip_address(inf[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def impressum_links(html: str) -> list[str]:
    """Alle Verweise auf der Seite, die zur Anbieterkennung fuehren.

    **Warum Raten nicht reicht.** Gemessen am 2026-08-17: `matuczak.de` fuehrt sein
    Impressum unter `/about/`, und keine noch so lange Pfadliste haette das getroffen.
    Ein Mensch braucht diese Liste auch nicht — er liest den Link im Fussbereich.
    """
    out = []
    for ziel, beschriftung in _LINK.findall(html):
        if _KENNUNG.search(ziel) or _KENNUNG.search(re.sub(r"<[^>]+>", " ", beschriftung)):
            if not ziel.lower().startswith(("mailto:", "tel:", "javascript:", "#")):
                out.append(ziel)
        if len(out) >= 4:
            break
    return out


def _hole(domain: str, pfad: str) -> tuple[str, str] | None:
    for schema in ("https://", "http://"):
        try:
            r = requests.get(schema + domain + pfad, headers=KOPF, timeout=FRIST,
                             allow_redirects=True, stream=True)
            # Umleitungen duerfen die Domain verlassen (viele Firmen liegen auf einer
            # Konzern-Domain), aber nicht ins private Netz zeigen.
            ziel = urlsplit(r.url).hostname or ""
            if ziel and not _oeffentlich(ziel):
                return None
            if r.status_code != 200:
                return None
            text = r.raw.read(MAX_BYTES, decode_content=True) or b""
            return pfad, text.decode(r.encoding or "utf-8", errors="replace")
        except requests.exceptions.SSLError:
            continue          # einmal ohne TLS nachfassen, dann aufgeben
        except Exception:
            return None
    return None


@dataclass
class Befund:
    urteil: str
    domain: str
    firma: str
    sekunden: float = 0.0
    pfad: str | None = None
    quote: float = 0.0
    ort_belegt: bool = False
    register_belegt: bool = False
    worte: list[str] = field(default_factory=list)
    grund: str = ""

    def dict(self) -> dict:
        return asdict(self)


def pruefe(domain: str, firma: str, ort: str | None = None,
           schwelle: float = 0.5) -> Befund:
    """Belegt das Impressum von ``domain``, dass sie zu ``firma`` gehört?"""
    t0 = time.time()
    domain = (domain or "").strip().lower().lstrip(".")
    if not domain or "." not in domain or "/" in domain:
        return Befund(NICHT_PRUEFBAR, domain, firma, grund="keine gültige Domain")
    if not _oeffentlich(domain):
        return Befund(NICHT_PRUEFBAR, domain, firma,
                      sekunden=round(time.time() - t0, 2),
                      grund="Domain löst nicht auf oder zeigt nicht ins öffentliche Netz")

    k = kerne(firma)
    if not k:
        return Befund(NICHT_PRUEFBAR, domain, firma,
                      grund="Firmenname trägt nur Rechtsform, nichts Unterscheidendes")

    kern_wort = traeger(k)
    # Zwei Lesarten des Namens: gefaltet („barmann") und in Umschrift („baermann").
    lesarten = [k, {w for w in stamm(umschrift(firma)).split()
                    if len(w) >= 3 and not _RECHTSFORM.fullmatch(w)}]
    traeger_worte = {t for t in (traeger(x) for x in lesarten) if t}

    bester: Befund | None = None
    kennung_gelesen = False          # ⚠ NUR echte Impressumsseiten, nicht die Startseite
    startseiten_links: list[str] = []

    def bewerte(pfad: str, text: str, ist_startseite: bool) -> None:
        nonlocal bester, kennung_gelesen
        # Die Startseite darf BESTAETIGEN, aber niemals WIDERLEGEN.
        #
        # Bestaetigen: nur wenn sie selbst eine Anbieterkennung traegt. Ein Firmenname auf
        # einer beliebigen Seite waere sonst schon ein Beleg — das kann auch eine Referenz-
        # oder Partnerliste sein. Gemessen an 200 verwuerfelten Paaren kam so KEIN einziges
        # durch, weil zusaetzlich das seltene Traegerwort passen muss.
        #
        # Widerlegen: nie. Wer „Impressum" im Menue sieht und daraus schliesst, die Firma
        # stehe nicht drin, urteilt ueber eine Seite, die er nie gelesen hat — gemessen die
        # Ursache mehrerer Fehlurteile gegen echte Firmen (matuczak.de fuehrt sein
        # Impressum unter `/about/`). Dafuer ist unten die Link-Verfolgung da.
        if ist_startseite and not _KENNUNG.search(text):
            return
        flach = falte(text)
        worte = set(flach.split())
        for lesart in lesarten:
            if not lesart:
                continue
            gefunden = {w for w in lesart if w in worte}
            quote = len(gefunden) / len(lesart)
            # Ohne ein Traegerwort zaehlt der Treffer NICHT, egal wie hoch die Quote ist.
            if not (gefunden & traeger_worte):
                continue
            if bester is None or quote > bester.quote:
                bester = Befund(BELEGT, domain, firma, pfad=pfad, quote=round(quote, 2),
                                ort_belegt=bool(ort) and falte(ort).strip() in flach,
                                register_belegt=bool(_REGISTER.search(text)),
                                worte=sorted(gefunden))
        # Eine Startseite ist KEIN Impressum, auch wenn „Impressum" im Menue steht. Wer sie
        # als gelesene Kennung wertet, urteilt WIDERLEGT, ohne je eine Anbieterkennung
        # gesehen zu haben — gemessen am 2026-08-17 die Ursache mehrerer Fehlurteile gegen
        # echte Firmen (matuczak.de fuehrt sein Impressum unter `/about/`).
        if not ist_startseite and _KENNUNG.search(text):
            kennung_gelesen = True

    with ThreadPoolExecutor(max_workers=len(PFADE)) as ex:
        for f in as_completed({ex.submit(_hole, domain, p) for p in PFADE}):
            r = f.result()
            if not r:
                continue
            pfad, text = r
            if pfad == "/":
                startseiten_links = impressum_links(text)
                bewerte(pfad, text, True)
            else:
                bewerte(pfad, text, False)

        # Dem Wegweiser folgen. Das ersetzt das Raten von Pfaden: kein Katalog haette
        # `/about/` erraten, ein Blick in den Fussbereich findet es sofort.
        if not kennung_gelesen and startseiten_links:
            for r in ex.map(lambda z: _hole(domain, z if z.startswith("/")
                                            else "/" + z.split("/", 3)[-1]),
                            startseiten_links[:3]):
                if r:
                    bewerte(r[0], r[1], False)

    dauer = round(time.time() - t0, 2)
    if bester and bester.quote >= schwelle:
        bester.sekunden = dauer
        bester.grund = f"Firmenname zu {bester.quote:.0%} im Impressum unter {bester.pfad}"
        return bester
    if kennung_gelesen:
        # Impressum da, nennt aber jemand anderen. DAS ist die Aussage, die Sicherheit
        # bringt — und der Fall, der die Portaladressen der Auftraggeber abfaengt.
        b = bester or Befund(WIDERLEGT, domain, firma)
        b.urteil = WIDERLEGT
        b.sekunden = dauer
        b.grund = "Impressum gefunden, nennt diese Firma aber nicht"
        return b
    return Befund(NICHT_PRUEFBAR, domain, firma, sekunden=dauer,
                  grund="kein Impressum erreichbar (Seite tot, Zertifikat kaputt "
                        "oder Kennung nur per JavaScript)")


if __name__ == "__main__":  # pragma: no cover
    import sys
    b = pruefe(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    print(f"{b.urteil:<14} {b.sekunden:>5.2f}s  {b.grund}")

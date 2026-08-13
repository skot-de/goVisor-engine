"""Vorprüfung: welche Vergabeportale geben die UNTERLAGEN ohne Anmeldung heraus?

**Warum es diese Fassung gibt — die erste war falsch.** Sie bewertete die Seite, die als
``documents_url`` gespeichert ist. Das ist die **Bekanntmachung**, nicht die Dokumentliste.
Auf der Bekanntmachung steht kein Passwortfeld, auf der Unterlagen-Seite schon. Die erste
Fassung meldete daraufhin „keine der 14 Plattformen stellt eine Anmelde-Wand vor die
Unterlagen — das Hindernis ist technisch, nicht rechtlich", und darauf wurde eine
Connector-Strategie gebaut. Gemessen am 2026-08-13 an der NetServer-Familie (1.408 Leads,
8+ Hosts): sowohl ``ParticipationControllerServlet?function=ParticipList`` als auch
``TenderingProcedureDetails?function=_Details`` liefern ein Passwortfeld und **null**
Datei-Links.

Der Fehler war, von der Zugänglichkeit EINER Schicht auf eine andere zu schliessen. Diese
Fassung geht deshalb den Weg, den ein Bieter geht: Bekanntmachung → Unterlagen-Link →
Beurteilung der Seite, auf der die Dateien liegen müssten.

**Positivkontrollen.** Der Lauf prüft cosinex und RIB mit, obwohl beide längst als Connector
gebaut sind. Sie kommen nachweislich ohne Anmeldung durch — stuft die Prüfung sie als „Wand"
ein, ist die Prüfung kaputt und nicht die Plattform. Genau das ist beim Bau passiert: ein
naheliegender Same-Host-Filter (gegen Treffer wie autobahn.de/downloads) liess RIB sofort
durchfallen, weil RIB ein Aggregator ist und seine Dateien auf FREMDEN Hosts liegen. Ohne
Kontrolle wäre der Filter drin geblieben und hätte 714 Leads als unerreichbar gemeldet.

**⚠ Was diese Prüfung NICHT kann, und das schränkt sie stark ein.** Sie unterscheidet eine
Vergabeunterlage nicht von einem beliebigen PDF. Die RIB-Kontrolle besteht mit „1 Datei auf
www.rib-software.com" — einem Hersteller-PDF, nicht der Unterlage; die echten RIB-Dateien
stehen in einem JS-Literal, das kein href-Ausdruck findet. Sie besteht also aus dem falschen
Grund. Daraus folgt:

* **„Anmelde-Wand" und „Bot-Sperre" sind belastbar** — ein Passwortfeld ohne jede Datei ist
  eindeutig, und daran ändert kein Nachladen etwas. Diese Prüfung taugt zum AUSSCHLIESSEN.
* **„offen?" ist ein Kandidaten-Merkmal, kein Urteil.** Der Host der gefundenen Dateien steht
  daneben, damit ein Mensch in einer Sekunde entscheidet. Wer aus „offen?" auf einen baubaren
  Connector schliesst, wiederholt den Fehler, den diese Datei zweimal dokumentiert.

**Was sie NICHT tut.** Sie meldet sich nirgends an, probiert keine Zugangsdaten, umgeht nichts.
Sie ruft öffentliche Seiten ab und liest, was dort steht. Ein Passwortfeld ist ein Befund,
kein Hindernis, das zu überwinden wäre.

Aufruf:  python3 scripts/probe_portals.py [--pro-host 2] [--top 14]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/126.0 Safari/537.36 goVisor-Marktanalyse (sven.kotzur@gmail.com)")
_PAUSE = 2.0
_TIMEOUT = 25

# Der Weg zur Dokumentliste. Die ersten beiden sind NetServer-spezifisch (1.408 Leads), der
# Rest deckt die üblichen Beschriftungen ab. Reihenfolge = Priorität.
_UNTERLAGEN_LINK = re.compile(
    r'href="([^"]*(?:ParticipList|TenderingProcedureDetails|function=_Details|'
    r'unterlagen|vergabeunterlagen|documents|dokumente|download)[^"]*)"', re.I)
_PASSWORT = re.compile(r'<input[^>]+type=[\'"]?password', re.I)
_DATEI_LINK = re.compile(
    r'(?:href|src)=[\'"]([^\'"]*\.(?:zip|pdf|docx?|xlsx?|x8[136]|d8[13]))\b', re.I)
_ROBOT = re.compile(r'captcha|cloudflare|Zugriff verweigert|Access denied', re.I)

# Plattformen, für die ein Connector existiert und nachweislich ohne Anmeldung laedt.
# Sie MUESSEN als "offen" herauskommen.
_KONTROLLE = {"cosinex/DTVP": r"/(V?MP)?Satellite/", "RIB/meinauftrag": r"meinauftrag\.rib\.de"}


def _hole(s, url: str):
    try:
        r = s.get(url, timeout=_TIMEOUT, allow_redirects=True)
    except Exception as e:
        return None, type(e).__name__
    return r, None


def _beurteile(html: str, basis_host: str = "") -> tuple[str, str]:
    """Eine Seite, auf der Dateien liegen müssten → Befund.

    ``basis_host`` filtert FREMDE Dateiverweise heraus. Ohne ihn genügte ein beliebiges PDF
    als Beleg — gemessen im ersten Lauf dieser Fassung: ``vergabe.autobahn.de`` galt als
    „offen", weil die Seite auf 24 Dateien unter ``autobahn.de/downloads`` verwies. Das ist
    die allgemeine Download-Seite des Unternehmens (Geschäftsberichte, Broschüren), nicht
    eine einzige Vergabeunterlage. Dieselbe Fehlerklasse wie in der ersten Fassung, nur eine
    Ebene später: etwas Dateiartiges gefunden und daraus auf Zugänglichkeit geschlossen.
    """
    if _ROBOT.search(html):
        return "Bot-Sperre", ""
    roh = set(_DATEI_LINK.findall(html))
    dateien = len(roh)
    if dateien:
        # Der Host der Dateien WIRD GEZEIGT, aber nicht gefiltert. Ein Same-Host-Filter lag
        # nahe (autobahn.de/downloads ist offensichtlich nicht die Vergabeunterlage) — und
        # liess prompt die Positivkontrolle RIB durchfallen: RIB ist ein Aggregator, seine
        # Dateien liegen auf my.vergabeplattform.berlin.de und anderen FREMDEN Hosts. Der
        # Filter haette also genau den funktionierenden Connector ausgeschlossen.
        #
        # Konsequenz, ehrlich: diese Pruefung kann eine Vergabeunterlage nicht von einem
        # beliebigen PDF unterscheiden. „offen" ist damit ein KANDIDATEN-Merkmal, kein
        # Urteil — der Host daneben laesst einen Menschen in einer Sekunde entscheiden.
        # „Anmelde-Wand" bleibt belastbar: ein Passwortfeld ohne jede Datei ist eindeutig.
        hosts = {re.sub(r'^https?://([^/]+).*', r'\1', x) for x in roh if x.startswith('http')}
        wo = ", ".join(sorted(hosts)[:2]) if hosts else "relativ"
        return "offen?", f"{dateien} Dateien auf {wo}"
    if _PASSWORT.search(html):
        return "Anmelde-Wand", "Passwortfeld, keine Dateien"
    return "unklar", "weder Dateien noch Passwortfeld (JS-Nachladen?)"


def pruefe(s, start_url: str) -> tuple[str, str]:
    """Bekanntmachung → Unterlagen-Link → Beurteilung. Der Weg eines Bieters."""
    r, fehler = _hole(s, start_url)
    if fehler:
        return "Fehler", fehler
    if r.status_code != 200:
        return f"HTTP {r.status_code}", ""
    ctype = r.headers.get("content-type", "").lower()
    if "html" not in ctype:
        return "Datei direkt", ctype.split(";")[0]

    # Liegen die Dateien schon hier? (cosinex/RIB — dann ist der Umweg unnötig.)
    host = re.sub(r'^https?://([^/]+).*', r'\\1', r.url)
    befund, notiz = _beurteile(r.text, host)
    if befund.startswith("offen") or befund == "Bot-Sperre":
        return befund, notiz + " (auf der Bekanntmachung)"

    kandidaten = list(dict.fromkeys(
        m.replace("&amp;", "&") for m in _UNTERLAGEN_LINK.findall(r.text)))[:3]
    if not kandidaten:
        return befund, notiz + " — kein Unterlagen-Link gefunden"
    for k in kandidaten:
        time.sleep(_PAUSE)
        r2, f2 = _hole(s, urljoin(r.url, k))
        if f2 or r2.status_code != 200:
            continue
        b2, n2 = _beurteile(r2.text, host)
        if b2.startswith("offen"):
            return b2, n2 + f" über {k.split('?')[0][:40]}"
        letzte = (b2, n2 + f" über {k.split('?')[0][:40]}")
    return letzte if kandidaten else (befund, notiz)


def ziele(pro_host: int, top: int):
    import duckdb

    con = duckdb.connect()
    src = ROOT / "data" / "gold" / "DE" / "lead_export.parquet"
    basis = f"""FROM read_parquet('{src.as_posix()}')
        WHERE phase='open' AND documents_url IS NOT NULL AND deadline_date >= current_date"""
    gross = con.execute(f"""SELECT regexp_extract(documents_url,'https?://([^/]+)',1) host,
        count(*) n {basis} GROUP BY 1 ORDER BY n DESC LIMIT {int(top)}""").fetchall()
    urls: dict[str, list[str]] = defaultdict(list)
    for host, _ in gross:
        for (u,) in con.execute(f"""SELECT documents_url {basis}
              AND documents_url LIKE '%{host}%' ORDER BY deadline_date DESC
              LIMIT {int(pro_host)}""").fetchall():
            urls[host].append(u)
    # Positivkontrollen dazu, auch wenn sie nicht unter den groessten sind.
    kontroll: dict[str, list[str]] = {}
    for name, muster in _KONTROLLE.items():
        r = con.execute(f"""SELECT documents_url {basis}
            AND regexp_matches(documents_url, '{muster}') ORDER BY deadline_date DESC
            LIMIT 1""").fetchall()
        if r:
            kontroll[name] = [r[0][0]]
    return dict(gross), urls, kontroll


def main(pro_host: int, top: int) -> int:
    import requests

    gewicht, urls, kontroll = ziele(pro_host, top)
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept-Language": "de-DE,de;q=0.9"})

    print("Positivkontrollen (muessen 'offen' ergeben — sonst ist die Pruefung kaputt):")
    kaputt = []
    for name, us in kontroll.items():
        b, n = pruefe(s, us[0])
        print(f"  {name:<20} {b:<14} {n[:60]}")
        if not b.startswith("offen"):
            kaputt.append(name)
        time.sleep(_PAUSE)
    if kaputt:
        print(f"\n⚠ Kontrolle fehlgeschlagen ({', '.join(kaputt)}). Die Befunde unten sind "
              f"NICHT verwertbar — erst die Pruefung reparieren.\n")

    print(f"\nUngedeckte Plattformen, je bis zu {pro_host} Vorgaenge, Weg ueber den "
          f"Unterlagen-Link:")
    for host, us in urls.items():
        befunde = [pruefe(s, u) for u in us]
        rang = {"Anmelde-Wand": 0, "Bot-Sperre": 1, "unklar": 2, "Fehler": 3,
                "offen?": 4, "Datei direkt": 5}
        haupt = min((b for b, _ in befunde), key=lambda b: rang.get(b, 2))
        notiz = next((n for b, n in befunde if b == haupt and n), "")
        print(f"  {gewicht.get(host,0):>5} Leads  {host:<34} {haupt:<14} {notiz[:56]}")
        time.sleep(_PAUSE)
    print("\n'offen' = die Unterlagen-Seite verweist ohne Anmeldung auf Dateien.")
    print("'Anmelde-Wand' = Passwortfeld UND keine Dateien — belastbar, kein Deutungsspielraum.")
    return 1 if kaputt else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pro-host", type=int, default=2)
    ap.add_argument("--top", type=int, default=14)
    a = ap.parse_args()
    sys.exit(main(a.pro_host, a.top))

"""Vorprüfung: welche Vergabeportale liefern Unterlagen OHNE Registrierung?

**Warum die Frage berechtigt ist.** § 41 VgV verpflichtet Auftraggeber, die Vergabeunterlagen
„unentgeltlich, uneingeschränkt, vollständig und direkt" zum Abruf bereitzustellen. Genau
deshalb kommt der cosinex-Fetcher ohne Login durch. Ob eine Plattform das auch technisch so
umsetzt, ist damit aber nicht gesagt — manche stellen eine Registrierung davor, was der
Vorschrift widerspricht, aber vorkommt.

**Was dieses Skript tut und was nicht.** Es ruft die Übersichtsseite ab, die in unseren Daten
als ``documents_url`` steht, und klassifiziert die ANTWORT. Es meldet sich nirgends an,
umgeht nichts und probiert keine Zugangsdaten. Ergebnis ist eine Einschätzung je Plattform,
kein Download. Höflich: ein Aufruf alle zwei Sekunden, ein Zeitlimit, echter User-Agent mit
Kontakt-Hinweis.

**Die Klassifikation ist eine Anzeige, kein Beweis.** „offen" heißt: die Seite liefert ohne
Anmeldung etwas, das nach Dokumentliste aussieht. Ob der Download dann wirklich durchgeht,
zeigt erst ein Connector-Versuch. Umgekehrt ist „Login" belastbarer — wo ein Passwortfeld
steht, steht eines.

Aufruf: python3 scripts/probe_portals.py [--pro-host 3]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/126.0 Safari/537.36 goVisor-Marktanalyse (sven.kotzur@gmail.com)")
_PAUSE = 2.0          # Sekunden zwischen zwei Aufrufen desselben Laufs
_TIMEOUT = 20

# Anzeichen im HTML — die Unterscheidung, auf die es ankommt:
#
# Ein `\bLogin\b` irgendwo im Text ist WERTLOS: praktisch jedes Portal hat einen Anmelde-Link
# in der Kopfzeile, auch auf vollständig offenen Seiten. Der erste Anlauf stufte deshalb fünf
# Plattformen als „Login + Doks" ein und sagte damit über keine von ihnen etwas aus.
#
# Belastbar ist nur dieses Paar:
#   OFFEN        = Verweise auf konkrete Dateien (href auf .zip/.pdf/.x83 …). Dann ist der
#                  Anmelde-Link daneben Zierde.
#   ANMELDE-WAND = echtes Passwort-Eingabefeld UND keine Datei-Verweise.
_PASSWORT = re.compile(r'<input[^>]+type=[\'"]?password', re.I)
_DATEI_LINK = re.compile(r'(?:href|src)=[\'"][^\'"]*\.(?:zip|pdf|docx?|xlsx?|x8[136]|d8[13])\b', re.I)
_DOWNLOAD_WORT = re.compile(r'Vergabeunterlagen|Leistungsbeschreibung|Unterlagen herunterladen', re.I)
_ROBOT = re.compile(r'captcha|cloudflare|Zugriff verweigert|Access denied', re.I)


def hosts(pro_host: int) -> dict[str, list[str]]:
    import duckdb

    con = duckdb.connect()
    src = ROOT / "data" / "gold" / "DE" / "lead_export.parquet"
    rows = con.execute(f"""
        SELECT regexp_extract(documents_url, 'https?://([^/]+)', 1) AS host, documents_url
        FROM read_parquet('{src.as_posix()}')
        WHERE phase='open' AND documents_url IS NOT NULL AND deadline_date >= current_date
          AND NOT regexp_matches(documents_url, '/(V?MP)?Satellite/')
        QUALIFY row_number() OVER (PARTITION BY host ORDER BY deadline_date DESC) <= {int(pro_host)}
    """).fetchall()
    aus: dict[str, list[str]] = defaultdict(list)
    for h, u in rows:
        aus[h].append(u)
    # Nur die Plattformen mit Gewicht — der lange Schwanz lohnt keinen Connector.
    gross = con.execute(f"""
        SELECT regexp_extract(documents_url, 'https?://([^/]+)', 1) AS host, count(*) n
        FROM read_parquet('{src.as_posix()}')
        WHERE phase='open' AND documents_url IS NOT NULL AND deadline_date >= current_date
          AND NOT regexp_matches(documents_url, '/(V?MP)?Satellite/')
        GROUP BY 1 ORDER BY n DESC LIMIT 14""").fetchall()
    return {h: aus[h] for h, _ in gross if aus.get(h)}, dict(gross)


def pruefe(url: str) -> tuple[str, str]:
    """→ (Befund, Notiz). Kein Login-Versuch, nur Klassifikation der Antwort.

    `requests` statt `urllib`: hier läuft ein TLS-abfangender Proxy, dessen CA `urllib`
    nicht kennt — der erste Anlauf meldete für ALLE 14 Plattformen denselben Fehler.
    14 von 14 identisch ist nie ein Befund über die Gegenseite, sondern immer einer
    über die eigene Messung. `docfetch` nutzt aus demselben Grund `requests`.
    """
    import requests

    try:
        r = requests.get(url, timeout=_TIMEOUT, allow_redirects=True,
                         headers={"User-Agent": _UA, "Accept-Language": "de-DE,de;q=0.9"})
    except Exception as e:
        return "Fehler", type(e).__name__
    ctype = r.headers.get("content-type", "")
    if r.status_code >= 400:
        return f"HTTP {r.status_code}", ""
    if "html" not in ctype.lower():
        return "Datei direkt", ctype.split(";")[0]
    html = r.text[:400_000]
    if _ROBOT.search(html):
        return "Bot-Sperre", ""
    dateien = len(set(_DATEI_LINK.findall(html)))
    if dateien:
        return "offen", f"{dateien} Datei-Verweise auf der Seite"
    if _PASSWORT.search(html):
        return "Anmelde-Wand", "Passwortfeld, keine Datei-Verweise"
    if _DOWNLOAD_WORT.search(html):
        return "unklar", "nennt Unterlagen, verlinkt aber keine Datei — vermutlich JS-Nachladen"
    return "unklar", "weder Datei-Verweise noch Passwortfeld"


def main(pro_host: int) -> int:
    ziele, gewicht = hosts(pro_host)
    print(f"Vorprüfung {len(ziele)} Plattformen, je bis zu {pro_host} Seiten. "
          f"Ein Aufruf alle {_PAUSE:.0f} s, kein Anmeldeversuch.\n")
    for host, urls in ziele.items():
        befunde = []
        for u in urls:
            befunde.append(pruefe(u))
            time.sleep(_PAUSE)
        # Strengster Befund gewinnt — eine offene Seite macht die Plattform nicht offen.
        rang = {"Anmelde-Wand": 0, "Bot-Sperre": 1, "unklar": 2,
                "Fehler": 3, "offen": 4, "Datei direkt": 5}
        haupt = min((b for b, _ in befunde), key=lambda b: rang.get(b, 3))
        notiz = next((n for b, n in befunde if b == haupt and n), "")
        alle = ", ".join(sorted({b for b, _ in befunde}))
        print(f"  {gewicht.get(host, 0):>5} Leads  {host:<38} {haupt:<13} "
              f"[{alle}]{' — ' + notiz if notiz else ''}")
    print("\n„offen" + "\" heißt: liefert ohne Anmeldung etwas Dokumentartiges — eine Anzeige, "
          "kein Beweis.\nOb der Download durchgeht, zeigt erst ein Connector-Versuch. "
          "„Login\" ist belastbarer.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pro-host", type=int, default=3)
    sys.exit(main(ap.parse_args().pro_host))

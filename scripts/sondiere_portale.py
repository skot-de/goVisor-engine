#!/usr/bin/env python3
"""Schritt 1+2 der Portal-Sondierung: Portallandschaft eines Landes aus TED ableiten.

⚠ KEIN PORTAL WIRD BERUEHRT. Diese Datei liest ausschliesslich TED-Monatspakete, die
ohnehin im Cache liegen. TED nennt in jeder Bekanntmachung das Portal — der Deeplink zu
den Unterlagen und den Kommunikationskanal. Damit entsteht die Landschaft, ohne dass ein
einziger fremder Server angefasst wird.

⚠ UND ES NIMMT KEIN LAND AUF. Ausgabe geht nach `data/sondierung/<land>/`, niemals nach
`data/gold` oder `data/silver`. Warum das eine eigene Wache hat, steht in
`scripts/pruefe_sondierung.py` — Stichwort Polen.

DIE ARBEITSEINHEIT IST DIE ENGINE, nicht die Domain. Fuer DE gemessen: 146 Domains laufen
auf ~8 Software-Engines, und der Zugang ist JE ENGINE gleich. Wer je Domain arbeitet,
macht dieselbe Arbeit hundertfach.

Aufruf:  python3 scripts/sondiere_portale.py --land FR [--monat 2026-06]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import tarfile
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import bulk, flatten                                    # noqa: E402

# ⚠ UEBER DEN PFAD, NICHT UEBER DAS ELEMENT. Die erste Fassung nahm jede `cbc:URI` und
# jede `cbc:EndpointID` — und zaehlte damit Dinge mit, die keine Portale sind. In Polen
# waren das 1.376 Treffer auf `uzp.gov.pl` (die Krajowa Izba Odwolawcza, also die
# NACHPRUEFUNGSSTELLE) und 809 auf `epuap.gov.pl` (das Einlegen der Beschwerde). Beide
# stehen als Pflichtangabe in jeder Bekanntmachung; als Portale gelesen ergaeben sie ein
# voellig falsches Bild. Dazu kaemen Gesetzeslinks und Organisations-Webseiten.
#
# Diese Pfade tragen wirklich das Portal (an 400 PL-Bekanntmachungen ausgezaehlt):
ZAEHLT = (
    # Der Unterlagen-Deeplink — das Feld, auf das es ankommt. Dieselbe Auswahl trifft
    # `gold.py` fuer `lead_export.documents_url`.
    "CallForTendersDocumentReference.Attachment.ExternalReference.URI",
    "TenderRecipientParty.EndpointID",      # wohin das Angebot geht
    "TenderingProcess.AccessToolsURI",      # der Kommunikationskanal
)
# ⚠ Und diese NICHT, obwohl sie URLs tragen:
IGNORIERT = (
    "Organizations.Organization",           # Kontaktdaten — hier steckt die Nachpruefungsstelle
    "LegislationDocumentReference",         # Gesetzestexte, keine Vergabeunterlagen
    "BuyerProfileURI",                      # Beschafferprofil, nicht das Verfahren
)
LAND = re.compile(rb'listName="country"[^>]*>([A-Z]{3})<')

# Engine am PFAD erkennen, nicht am Domainnamen — das ist sprachunabhaengig und gilt in
# Portugal wie in Estland. Die DACH-Muster sind gemessen; die uebrigen sind Kandidaten,
# die die Sondierung bestaetigen oder verwerfen muss.
ENGINES: tuple[tuple[str, re.Pattern], ...] = (
    ("cosinex",       re.compile(r"/Satellite/|/VMPSatellite/", re.I)),
    ("healy-netserver", re.compile(r"/NetServer/", re.I)),
    ("ai-evergabe",   re.compile(r"evergabe\.de|/unterlagen/|evergabe\.bieter", re.I)),
    ("bund-evergabe", re.compile(r"evergabe-online\.de", re.I)),
    ("rib-meinauftrag", re.compile(r"meinauftrag\.rib\.de", re.I)),
    ("subreport",     re.compile(r"subreport\.de", re.I)),
    ("mercell",       re.compile(r"mercell\.com|tendsign|visma(commerce)?\.", re.I)),
    ("vortal",        re.compile(r"vortal\.biz|community\.vortal|acingov|saphety", re.I)),
    # ── FR, am 2026-09-02 an den URL-Pfaden des Juni-Pakets bestimmt ──────────────────
    # ⚠ Die Engine steht im PFAD, nicht im Domainnamen. `demat-ampa.fr`,
    # `marchespublics596280.fr`, `plateforme.alsacemarchespublics.eu`, `marches.maximilien.fr`
    # und `megalis.bretagne.bzh` sehen wie fuenf Portale aus und tragen alle denselben Pfad
    # `/entreprise/consultation/<id>?orgAcronyme=…` — es ist EINE Software (Atexo/MPE).
    # Genau das ist die Rechtfertigung des ganzen Plans: eine Pruefung statt fuenf.
    ("atexo-mpe",     re.compile(r"/entreprise/consultation/|orgAcronyme=", re.I)),
    ("boamp-place",   re.compile(r"boamp\.fr|marches-publics\.gouv\.fr|place\.", re.I)),
    # `fuseaction=dematEnt.login&type=DCE` — die URL nennt die Schranke selbst: das
    # Dossier de Consultation des Entreprises liegt hinter einer Anmeldung.
    ("aws-achat",     re.compile(r"/mpiaws/|marches-publics\.info", re.I)),
    ("achatpublic",   re.compile(r"achatpublic\.com|/sdm/ent/", re.I)),
    ("xmarches-php",  re.compile(r"detailConsultation\.php", re.I)),
    ("marches-securises", re.compile(r"marches-securises\.fr", re.I)),
    # ── PL, am 2026-09-02 an den URL-Pfaden des Juni-Pakets bestimmt ──────────────────
    # Wie in FR laufen viele Domains auf wenigen Systemen: `*.ezamawiajacy.pl` ist EIN
    # mandantenfaehiges Portal (Marketplanet) mit einer Subdomain je Vergabestelle, und
    # `platformazakupowa.plk-sa.pl` ist eine Weissmarke von `platformazakupowa.pl`.
    ("openNexus",     re.compile(r"platformazakupowa\.", re.I)),
    ("ezamowienia",   re.compile(r"ezamowienia\.gov\.pl|/mp-client/", re.I)),
    ("marketplanet",  re.compile(r"\.ezamawiajacy\.pl", re.I)),
    ("eb2b",          re.compile(r"\.eb2b\.com\.pl|open-preview-auction", re.I)),
    ("logintrade",    re.compile(r"\.logintrade\.net", re.I)),
    ("propublico",    re.compile(r"e-propublico\.pl", re.I)),
    ("smartpzp",      re.compile(r"smartpzp\.pl", re.I)),
    ("ted-esender",   re.compile(r"ted\.europa\.eu", re.I)),
)


def engine(url: str) -> str:
    for name, rx in ENGINES:
        if rx.search(url):
            return name
    return "unbekannt"


def sammle(land: str, monat: str) -> tuple[collections.Counter, collections.Counter, int, int]:
    """Domains und Engines eines Landes aus EINEM Monatspaket."""
    paket = ROOT / "data" / "cache" / f"ted_{monat}.tar.gz"
    if not paket.exists():
        raise SystemExit(f"  Paket fehlt: {paket}")
    a3 = {"FR": b"FRA", "ES": b"ESP", "IT": b"ITA", "NL": b"NLD", "PL": b"POL",
          "DE": b"DEU", "AT": b"AUT", "SE": b"SWE", "PT": b"PRT", "CZ": b"CZE",
          "BG": b"BGR", "LV": b"LVA", "BE": b"BEL", "DK": b"DNK", "FI": b"FIN",
          "RO": b"ROU", "HU": b"HUN", "GR": b"GRC", "EL": b"GRC", "IE": b"IRL"}.get(land.upper())
    domains: collections.Counter = collections.Counter()
    je_domain: dict = {}
    engines: collections.Counter = collections.Counter()
    gesamt = mit_url = 0
    with tarfile.open(paket) as t:
        for m in t:
            if not m.name.endswith(".tar.gz"):
                continue
            for _name, roh in bulk._walk(m.name, t.extractfile(m).read(), land):
                kopf = roh[:120000]
                if a3:
                    c = LAND.search(kopf)
                    if not c or c.group(1) != a3:
                        continue
                gesamt += 1
                gefunden = set()
                try:
                    paare = flatten.leaves(roh)
                except Exception:                              # noqa: BLE001
                    paare = []
                for pfad, wert in paare:
                    if not wert.startswith("http"):
                        continue
                    if any(x in pfad for x in IGNORIERT):
                        continue
                    if not any(x in pfad for x in ZAEHLT):
                        continue
                    host = urlsplit(wert).netloc.lower().removeprefix("www.")
                    if host:
                        gefunden.add((host, engine(wert)))
                if gefunden:
                    mit_url += 1
                for host, eng in gefunden:
                    domains[host] += 1
                    engines[eng] += 1
                    # ⚠ Die Engine je Domain MITFUEHREN. Sie aus dem blossen Hostnamen
                    # neu zu bestimmen geht nicht — sie steht im PFAD. Die erste Fassung
                    # tat genau das und zeigte `demat-ampa.fr` als „unbekannt", waehrend
                    # dieselbe Domain in der Engine-Zaehlung korrekt als Atexo stand.
                    # Zwei Zahlen aus derselben Messung, die sich widersprechen.
                    if eng != "unbekannt":
                        je_domain[host] = eng
    return domains, engines, gesamt, mit_url, je_domain


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--land", required=True)
    p.add_argument("--monat", default="2026-06")
    a = p.parse_args()

    domains, engines, gesamt, mit_url, je_domain = sammle(a.land, a.monat)
    ziel = ROOT / "data" / "sondierung" / a.land.upper()
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / f"portale_{a.monat}.json").write_text(json.dumps({
        "land": a.land.upper(), "monat": a.monat, "bekanntmachungen": gesamt,
        "mit_portal_url": mit_url,
        "domains": [(h, n, je_domain.get(h, "unbekannt")) for h, n in domains.most_common()],
        "engines": engines.most_common(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"── {a.land.upper()} · {a.monat} ──")
    print(f"  Bekanntmachungen           {gesamt:,}")
    if not gesamt:
        return 0
    print(f"  davon mit Portal-URL       {mit_url:,} ({mit_url/gesamt*100:.0f} %)")
    print(f"  verschiedene Domains       {len(domains):,}")
    print(f"\n  Groesste Portale:")
    for host, n in domains.most_common(12):
        print(f"    {host[:48]:<50} {n:>6,}  {je_domain.get(host, 'unbekannt')}")
    print(f"\n  Nach Engine:")
    for eng, n in engines.most_common():
        print(f"    {eng:<18} {n:>6,}  ({n/sum(engines.values())*100:.0f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

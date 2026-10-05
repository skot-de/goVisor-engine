"""Amtliche eForms-Codelisten von EU Vocabularies holen und als Referenz ablegen.

⚠ WARUM NICHT SELBST UEBERSETZEN. `direct-award-justification` traegt 43 Codes wie
`not-wss`, `resd`, `dir24-list`, `exc-circ-rail`. Deren Bedeutung aus dem Namen zu
erraten ist genau der Fehler, der in diesem Projekt schon einmal passiert ist: drei
Regeln nach Plausibilitaet gebaut, zwei von vier Normzweigen erfunden. Die Codes
benennen Ausnahmetatbestaende der Vergaberichtlinien — da entscheidet der Wortlaut,
nicht die Vermutung.

EU Vocabularies liefert je Begriff ein SKOS-Dokument mit `prefLabel` in allen
Amtssprachen. Ein Abruf je Begriff, einmalig; das Ergebnis liegt danach als JSON unter
`data/reference/eforms/` und wird nicht bei jedem Lauf neu geholt.

Aufruf:  python3 scripts/hole_eforms_codeliste.py [listenname ...]
"""
import json
import pathlib
import re
import ssl
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

BASIS = "http://publications.europa.eu/resource/authority"
ZIEL = pathlib.Path("data/reference/eforms")
UA = "goVisor/0.1 (procurement analytics; codelist sync)"
SPRACHEN = ("de", "en", "fr")
#: Standard, wenn nichts angegeben wird. Waechst mit dem, was wir anschliessen.
LISTEN = ("direct-award-justification", "non-award-justification")

CTX = ssl.create_default_context()
try:
    import certifi
    CTX.load_verify_locations(certifi.where())
except Exception:                                                    # noqa: BLE001
    CTX = ssl._create_unverified_context()

NS = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      "skos": "http://www.w3.org/2004/02/skos/core#"}


def hole(url: str) -> bytes:
    r = urllib.request.Request(url, headers={"User-Agent": UA,
                                             "Accept": "application/rdf+xml"})
    with urllib.request.urlopen(r, timeout=60, context=CTX) as x:
        return x.read()


def begriffe(liste: str) -> list[str]:
    """Die Codes einer Liste, aus `hasTopConcept`."""
    baum = ET.fromstring(hole(f"{BASIS}/{liste}"))
    aus = []
    for e in baum.iter(f"{{{NS['skos']}}}hasTopConcept"):
        u = e.get(f"{{{NS['rdf']}}}resource") or ""
        if u.startswith(f"{BASIS}/{liste}/"):
            aus.append(u.rsplit("/", 1)[-1])
    return sorted(set(aus))


def beschriftung(liste: str, code: str) -> dict[str, str]:
    """`prefLabel` je Sprache. Fehlt eine, fehlt sie — nichts wird ersetzt."""
    baum = ET.fromstring(hole(f"{BASIS}/{liste}/{urllib.parse.quote(code)}"))
    aus = {}
    for e in baum.iter(f"{{{NS['skos']}}}prefLabel"):
        lg = e.get("{http://www.w3.org/XML/1998/namespace}lang")
        if lg in SPRACHEN and e.text and lg not in aus:
            aus[lg] = re.sub(r"\s+", " ", e.text).strip()
    return aus


def main() -> int:
    import urllib.parse  # noqa: F401  (in beschriftung benutzt)
    ZIEL.mkdir(parents=True, exist_ok=True)
    listen = sys.argv[1:] or list(LISTEN)
    for liste in listen:
        try:
            codes = begriffe(liste)
        except Exception as e:                                       # noqa: BLE001
            print(f"  ⚠ {liste}: {type(e).__name__} — uebersprungen")
            continue
        print(f"── {liste}: {len(codes)} Begriffe ──")
        aus, fehlend = {}, 0
        for i, code in enumerate(codes, 1):
            try:
                aus[code] = beschriftung(liste, code)
            except Exception as e:                                   # noqa: BLE001
                print(f"   ⚠ {code}: {type(e).__name__}")
                fehlend += 1
                continue
            if not aus[code].get("de"):
                fehlend += 1
            if i % 15 == 0:
                print(f"   {i}/{len(codes)} …")
            time.sleep(0.15)
        p = ZIEL / f"{liste}.json"
        p.write_text(json.dumps(aus, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                     encoding="utf-8")
        mit_de = sum(1 for v in aus.values() if v.get("de"))
        print(f"   {mit_de}/{len(codes)} mit deutschem Wortlaut → {p}")
        if fehlend:
            print(f"   ⚠ {fehlend} ohne — die bleiben im Produkt als Code stehen, "
                  f"nicht als geratene Uebersetzung")
    return 0


if __name__ == "__main__":
    import urllib.parse
    raise SystemExit(main())

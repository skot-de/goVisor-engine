#!/usr/bin/env python3
"""Stadt→Zentroid-Index für die Umkreissuche per Stadtnamen.

Hintergrund: `web/data/plz-geo.json` schlägt nur ZAHLEN-PLZ nach. Wer „München" tippt,
bekam bisher keinen Ort-/Umkreis-Vorschlag (nur Auftraggeber-Treffer). Dieser Index
liefert Stadt-/Kreisname → [lat, lon, Anzeigename], damit die Suche „<Stadt> · Umkreis"
als echten Koordinaten-Token anbieten kann.

Quelle: `data/reference/geonames/DE.txt` (GeoNames-PLZ-Tabelle, tab-getrennt).
  Spalten (0-basiert): 0=Land 1=PLZ 2=Ort 3=admin1 4=admin1_code 5=admin2 6=admin2_code
                       7=admin3(Kreis) 8=admin3_code 9=lat 10=lon 11=accuracy
Spalte 2 (Ort) ist in dieser Datei teils mit Firmennamen verunreinigt (》GmbH《, 》AG《…) —
solche Zeilen werden verworfen. Spalte 7 (Kreis) ist sauber und wird als Alias ergänzt.

Der Index wird als Top-Level-Key `_cities` in die bestehende plz-geo.json gemerged (nicht
neu gebaut) — kein Gold-Rebuild nötig. Aufruf: `python3 scripts/build_city_index.py`.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "reference" / "geonames" / "DE.txt"
GEO = ROOT / "web" / "data" / "plz-geo.json"

# Firmen- und Behördenzeilen (verunreinigte Ort-Spalte) verwerfen.
#
# Der Ursprung der Verunreinigung sind **Großempfänger-Postleitzahlen**: wer viel Post
# bekommt, hat eine eigene PLZ, und GeoNames trägt dort den Organisationsnamen in die
# Ort-Spalte. Erkennbar sind diese Zeilen daran, dass ihre `accuracy` (Spalte 11) leer
# bleibt — gemessen 8.247 von 23.297 Zeilen; echte Städte tragen durchgängig 4 oder 6.
#
# **Warum trotzdem nicht einfach nach `accuracy` gefiltert wird:** unter diesen 8.247
# stecken auch echte kleine Orte und Stadtteile (Kummersdorf-Alexanderdorf, Uetz,
# Travenbrück, Stuttgart-Ost). Ein harter Schnitt verlöre rund 1.350 davon. Die
# Fehlerkosten sind unsymmetrisch: nach „HUK-Coburg" sucht in einer Umkreissuche
# niemand, ein fehlendes Dorf ist ein echter Funktionsverlust.
#
# Die Liste unten ist deshalb **aus den Daten abgeleitet**, nicht geraten: Wörter, die in
# den Großempfänger-Zeilen häufig und in Zeilen mit gesetzter `accuracy` praktisch nie
# vorkommen. Städtenamen wie „Stuttgart" oder „Köln" stehen bewusst NICHT drin, obwohl sie
# in der Häufigkeitsliste auftauchen — sie stammen aus Namen wie „Stadtverwaltung
# Stuttgart" und würden echte Orte mitreißen.
#
# Gemessen gegen alle 15.050 Zeilen mit gesetzter `accuracy`: **0 echte Orte verworfen**.
# Trefferquote bei den Großempfängern 45,2 % → 64,5 %.
_JUNK = re.compile(
    r"\b(?:GmbH|mbH|gGmbH|AG|KG|OHG|UG|SE|eG|e\.?\s?V\.?|a\.?\s?G\.?|Co\.?|"
    r"Verlag|Stiftung|Bank|Bankhaus|Sparkasse|Volksbank|Postbank|Commerzbank|"
    r"Versicherung\w*|Bausparkasse|Krankenkasse|Gesundheitskasse|BKK|IKK|AOK|"
    # „Brand" stand hier fuer „Daimler Brand und IP Management GmbH" — und warf dabei
    # zwei echte Orte weg: Brand (Oberpfalz) und Neunkirchen am Brand. Die Firma faengt
    # ohnehin das GmbH; der Marker ist ersatzlos raus.
    r"Holding|Group|Germany|Deutschland|Deutsche|International|Vertrieb|Management|"
    r"Marketing|Service|Services|Center|Classic|Direkt|"
    r"Agentur|Finanzamt|Amtsgericht|Landgericht|Staatsanwaltschaft|Arbeitsgericht|"
    r"Stadtverwaltung|Landratsamt|Landesamt|Bundesamt|Kreisverwaltung|Kreisverwaltungsreferat|"
    r"Universit\w+|Hochschule|Berufsakademie|Klinikum|Krankenhaus|Zentrum|"
    r"Niederlassung|Zustellst\w+|Postfach|Brief\w*|Telekom|Siemens|Amazon|"
    r"Rentenversicherung|Sozialversicherung|Berufsgenossenschaft|Gesellschaft)\b"
    # Als ENDUNG, nicht nur als eigenes Wort: die Marker stecken oft im Kompositum
    # („Landesbausparkasse", „Betriebskrankenkasse", „Kreissparkasse", „Werbeagentur").
    # Kein echter Ortsname endet auf diese Silben — gegen alle 15.050 Zeilen mit
    # gesetzter `accuracy` geprüft, 0 Fehlalarme.
    r"|\w*(?:sparkasse|krankenkasse|bausparkasse|versicherung|agentur|"
    r"genossenschaft|beh\u00f6rde|verwaltung|direktion)\b"
    r"|&|\d",
    re.IGNORECASE,
)
_KREIS_PREFIX = re.compile(r"^(?:Kreisfreie Stadt|Landkreis|Stadtkreis|Kreis)\s+", re.IGNORECASE)


def _clean_kreis(name: str) -> str:
    # "Kreisfreie Stadt München" → "München"; "Berlin, Stadt" → "Berlin".
    name = name.split(",")[0].strip()
    return _KREIS_PREFIX.sub("", name).strip()


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC}", file=sys.stderr)
        return 1

    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0])  # key → [sum_lat, sum_lon, n]
    disp: dict[str, str] = {}

    def add(name: str, lat: float, lon: float) -> None:
        # .lower() (NICHT .casefold()) — deckungsgleich mit JS `toLowerCase()` im Frontend;
        # casefold würde ß→ss wandeln und Städte wie „Gießen" unauffindbar machen.
        key = name.lower()
        if len(key) < 2:
            return
        a = acc[key]
        a[0] += lat
        a[1] += lon
        a[2] += 1
        disp.setdefault(key, name)

    for line in SRC.read_text(encoding="utf-8").splitlines():
        c = line.split("\t")
        if len(c) < 11:
            continue
        try:
            lat, lon = float(c[9]), float(c[10])
        except ValueError:
            continue
        ort, kreis = c[2].strip(), c[7].strip()
        if ort and not _JUNK.search(ort):
            add(ort, lat, lon)          # Ortsname (fein), sofern nicht verunreinigt
        if kreis:
            add(_clean_kreis(kreis), lat, lon)   # Kreis-Alias (immer sauber)

    cities = {
        key: [round(a[0] / a[2], 4), round(a[1] / a[2], 4), disp[key]]
        for key, a in acc.items()
        if a[2] > 0
    }

    geo = json.loads(GEO.read_text(encoding="utf-8"))
    geo["_cities"] = {"DE": cities}
    GEO.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Stichprobe
    for probe in ("münchen", "stuttgart", "köln", "berlin", "fürstenfeldbruck"):
        print(f"  {probe:18} → {cities.get(probe)}")
    print(f"Stadt-Index: {len(cities)} Namen → _cities in plz-geo.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Käufer-Anreicherung aus **Wikidata** (frei, kein Auth) für den Vergabestelle-Tab.

Nur saubere Kommunal-Käufer (Stadt/Landkreis/Gemeinde …). Gegen Ortsnamen-Ambiguität
(„Wörth" gibt es zig-mal) wird **geografisch disambiguiert**: unter allen Wikidata-
Kandidaten gewinnt der, dessen Koordinate unserer Käufer-Koordinate (aus ``lead_geo``)
am nächsten liegt — und nur wenn < MAX_KM. Zieht Website, Einwohnerzahl, Koordinate, Typ.

Schreibt ``data/reference/buyer_external.parquet`` (Cache). ``build_buyer_profile`` joint es
optional (kein Netz im Gold-Lauf). Erneut laufen aktualisiert den Cache.

Aufruf:  python scripts/enrich_wikidata.py
"""
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import duckdb  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

BATCH = 40
MAX_KM = 25.0          # Treffer weiter weg = anderer Ort → verworfen
UA = "goVisor/1.0 (procurement analytics; sven.kotzur@gmail.com)"
OUT = ROOT / "data" / "reference" / "buyer_external.parquet"
# Kommunal-Präfix + Kernname (Mehrwort/Bindestrich ok, keine Kommas/Ziffern).
_CLEAN = re.compile(r"^(Stadt|Landkreis|Landeshauptstadt|Gemeinde|Kreis|Hansestadt|Markt) "
                    r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß .-]+)$")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def search_label(name: str) -> str | None:
    m = _CLEAN.match(name.strip())
    if not m:
        return None
    prefix, core = m.group(1), m.group(2).strip()
    if prefix in ("Kreis", "Landkreis"):
        return f"Landkreis {core}"
    return core          # Städte/Gemeinden: blanker Kernname = Wikidata-Label


def haversine(a_lat, a_lon, b_lat, b_lon):
    R = 6371.0
    dlat = math.radians(b_lat - a_lat); dlon = math.radians(b_lon - a_lon)
    x = (math.sin(dlat/2)**2 + math.cos(math.radians(a_lat))
         * math.cos(math.radians(b_lat)) * math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(x))


def query_wikidata(labels: list[str]) -> list[dict]:
    """Kandidaten je Suchlabel — **mit Stichtag zur Einwohnerzahl**.

    `wdt:P1082` liefert JEDES Einwohner-Statement, sobald kein Rang als „preferred"
    gesetzt ist — bei deutschen Gemeinden sind das typisch 20–30 Volkszaehlungen zurueck
    bis 1871. Neusaess hat 30 Statements, das erste ist **139 aus dem Jahr 1875**. Die
    erste Fassung nahm die erste Zeile und schrieb damit Zensuswerte des 19. Jahrhunderts
    in `buyer_profile.population` — 48 % der angereicherten Kaeufer landeten unter 5.000
    Einwohnern.

    Deshalb ueber `p:/ps:` das volle Statement abfragen und den Stichtag `pq:P585`
    mitnehmen; die Auswahl des juengsten Werts passiert in `main()`.
    """
    values = " ".join(f'"{l}"@de' for l in labels)
    q = f"""SELECT ?label ?item ?website ?pop ?popdate ?coord WHERE {{
      VALUES ?label {{ {values} }}
      ?item rdfs:label ?label . ?item wdt:P17 wd:Q183 .
      ?item wdt:P31/wdt:P279* wd:Q56061 .
      ?item wdt:P625 ?coord .
      OPTIONAL {{ ?item wdt:P856 ?website }}
      OPTIONAL {{ ?item p:P1082 ?popst .
                  ?popst ps:P1082 ?pop .
                  OPTIONAL {{ ?popst pq:P585 ?popdate }} }}
    }}"""
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})
    r = subprocess.run(["curl", "-sS", "--max-time", "60", "-H", f"User-Agent: {UA}", url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl {r.returncode}: {r.stderr[:200]}")
    return json.loads(r.stdout)["results"]["bindings"]


def main() -> int:
    con = duckdb.connect()
    rows = con.execute("""
        SELECT l.buyer_entity, any_value(l.buyer_name) nm,
               median(g.lat) lat, median(g.lon) lon
        FROM read_parquet('data/gold/DE/leads.parquet') l
        JOIN read_parquet('data/gold/DE/lead_geo.parquet') g ON g.lead_id=l.lead_id
        WHERE l.buyer_entity IS NOT NULL AND g.lat IS NOT NULL
        GROUP BY l.buyer_entity""").fetchall()
    targets = []
    for be, nm, lat, lon in rows:
        lbl = search_label(nm or "")
        if lbl and lat is not None:
            targets.append((be, nm, lbl, float(lat), float(lon)))
    log(f"{len(targets)} saubere Kommunal-Käufer mit Koordinate (von {len(rows)} gesamt)")

    # nach Suchlabel gruppieren (mehrere Käufer können dasselbe Label tragen)
    by_label: dict[str, list] = {}
    for t in targets:
        by_label.setdefault(t[2], []).append(t)
    labels = list(by_label)

    results = []
    for i in range(0, len(labels), BATCH):
        chunk = labels[i:i+BATCH]
        try:
            binds = query_wikidata(chunk)
        except Exception as exc:
            log(f"  Batch {i//BATCH+1}: FEHLER {exc}")
            time.sleep(3); continue
        # Kandidaten je Label sammeln
        cand: dict[str, list] = {}
        for x in binds:
            lbl = x["label"]["value"]
            m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", x["coord"]["value"])
            if not m:
                continue
            cand.setdefault(lbl, []).append({
                "item": x["item"]["value"].rsplit("/", 1)[-1],
                "lon": float(m.group(1)), "lat": float(m.group(2)),
                "website": x.get("website", {}).get("value"),
                "pop": int(float(x["pop"]["value"])) if "pop" in x else None,
                "popdate": x.get("popdate", {}).get("value")})
        # Je Wikidata-Item die JUENGSTE Einwohnerzahl behalten. Ohne diesen Schritt
        # gewinnt eine beliebige der 20–30 historischen Zaehlungen.
        for lbl, cs in cand.items():
            best_pop: dict[str, tuple] = {}
            for c in cs:
                if c["pop"] is None:
                    continue
                key = c["popdate"] or ""     # ohne Stichtag: schwaechster Rang
                prev = best_pop.get(c["item"])
                if prev is None or key > prev[0]:
                    best_pop[c["item"]] = (key, c["pop"])
            seen: dict[str, dict] = {}
            for c in cs:
                if c["item"] in seen:
                    continue
                c["pop"] = best_pop.get(c["item"], (None, None))[1]
                c["popdate"] = best_pop.get(c["item"], (None, None))[0] or None
                seen[c["item"]] = c
            cand[lbl] = list(seen.values())
        # je Käufer den nächstgelegenen Kandidaten wählen
        for lbl in chunk:
            for be, nm, _, blat, blon in by_label[lbl]:
                # AKTUALITAET VOR ENTFERNUNG. Zu „Neusaess" liefert Wikidata zwei Items
                # am selben Ort: Q503208 „Stadt in Deutschland" (Stand 2024-12-31) und
                # Q135669081 „Ortsteil" (Stand 1987). Die Entfernung kann sie nicht
                # trennen — beide sind derselbe Punkt. Die erste Fassung nahm den
                # Ortsteil und schrieb 139 Einwohner (Zensus 1875) ins Profil.
                # Eine Gemeinde, die Wikidata pflegt, hat frische Zahlen; ein
                # Ortsteil-Stub hat nur die alte Zaehlung. Deshalb sortiert der
                # Stichtag zuerst, die Entfernung entscheidet nur bei Gleichstand.
                besten = []
                for c in cand.get(lbl, []):
                    km = haversine(blat, blon, c["lat"], c["lon"])
                    if km <= MAX_KM:
                        besten.append(((c.get("popdate") or ""), -km, c, km))
                besten.sort(key=lambda t: (t[0], t[1]), reverse=True)
                best, bestkm = (besten[0][2], besten[0][3]) if besten else (None, 1e9)
                if best:
                    results.append({
                        "buyer_entity": be, "wikidata_id": best["item"],
                        "website": best["website"], "population": best["pop"],
                        "population_date": (best.get("popdate") or "")[:10] or None,
                        "wd_lat": best["lat"], "wd_lon": best["lon"],
                        "match_km": round(bestkm, 1)})
        log(f"  Batch {i//BATCH+1}/{-(-len(labels)//BATCH)}: {len(results)} Treffer kumuliert")
        time.sleep(1.0)      # höflich

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if results:
        cols = ["buyer_entity", "wikidata_id", "website", "population", "population_date",
                "wd_lat", "wd_lon", "match_km"]
        pq.write_table(pa.table({c: [r[c] for r in results] for c in cols}), OUT)
    log(f"FERTIG: {len(results)} Käufer angereichert → {OUT}")
    with_web = sum(1 for r in results if r["website"])
    with_pop = sum(1 for r in results if r["population"])
    log(f"  davon mit Website: {with_web} | mit Einwohnerzahl: {with_pop}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

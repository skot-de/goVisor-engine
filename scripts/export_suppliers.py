"""Lieferanten-Index für das Onboarding-Matching → web/data/suppliers.json

Wer sich anmeldet, ist mit hoher Wahrscheinlichkeit schon als Bieter in den Daten.
Statt ein leeres Profil abzufragen, matchen wir den Firmennamen gegen die echten
Gewinner und leiten das Profil aus dem Zuschlags-Verlauf ab (§4.2: „gemessen").

Gruppiert über `entity_identity` (grp:*), damit die Varianten einer Firma (z. B. die
24 CANCOM-Entities) zu EINEM Profil verschmelzen. Nur belegt aufgelöste Identitäten.
"""
import duckdb, json, pathlib

OUT = pathlib.Path("web/data"); OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(); con.execute("SET threads=4")
G = "data/gold/DE"
PE = f"read_parquet('{G}/party_entity.parquet')"
EI = f"read_parquet('{G}/entity_identity.parquet')"
EN = f"read_parquet('{G}/entities.parquet')"
CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
N = "read_parquet('data/silver/DE/notices/*/*.parquet', hive_partitioning=1)"
E = f"read_parquet('{G}/lead_export.parquet')"

TOP_N = 6000   # Top-Lieferanten nach Zuschlägen — deckt die realistischen Nutzer ab

# Generik-/Käufer-Stämme (Ticket #7 v2, Leitplanke 2): keine privaten Bieter, raus.
BLOCK = ['stadt', 'gemeinde', 'landkreis', 'kreis ', 'bezirk', 'vergabekammer', 'arge',
         'bietergemeinschaft', 'ministerium', 'behörde', 'körperschaft', 'anstalt des',
         'zweckverband', 'eigenbetrieb', 'kommunal', 'land ', 'freistaat', 'bundesamt',
         'bundesministerium', 'universität', 'hochschule', 'klinikum der']
BLOCK_SQL = ' AND '.join(f"lower(name) NOT LIKE '%{b}%'" for b in BLOCK)

# Gewinner-Zuschläge mit Identity, CPV4 und Leistungsort-NUTS1. Nur Identitäten, die
# mindestens eine belegt aufgelöste Entity (HR/national-id) enthalten — sonst Namens-Rauschen.
con.execute(f"""CREATE OR REPLACE TEMP TABLE belegt AS
  SELECT DISTINCT ei.identity_id
  FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id
  WHERE e.method IN ('handelsregister_exakt','ted_nationalid')""")

con.execute(f"""CREATE OR REPLACE TEMP TABLE w AS
  SELECT ei.identity_id, ei.canonical_name, p.entity_id, p.notice_id,
         substr(n.cpv_main, 1, 4) AS cpv4,
         substr(n.performance_nuts, 1, 3) AS nuts1,
         year(n.publication_date) AS jahr
  FROM {PE} p
  JOIN {EI} ei ON ei.entity_id = p.entity_id
  JOIN {N} n ON n.notice_id = p.notice_id
  WHERE p.role = 'winner' AND ei.identity_id IN (SELECT identity_id FROM belegt)""")

# Top-Identitäten nach Zuschlägen
con.execute(f"""CREATE OR REPLACE TEMP TABLE tops AS
  SELECT identity_id, count(DISTINCT notice_id) AS wins
  FROM w GROUP BY 1 ORDER BY 2 DESC LIMIT {TOP_N}""")

# Repräsentativer Name = häufigster canonical_name der Gruppe; Aliase = die übrigen
con.execute("""CREATE OR REPLACE TEMP TABLE namen AS
  WITH cnt AS (SELECT identity_id, canonical_name, count(*) c FROM w
               WHERE canonical_name IS NOT NULL GROUP BY 1,2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY c DESC, length(canonical_name)) rn FROM cnt)
  SELECT identity_id,
         max(canonical_name) FILTER (WHERE rn = 1) AS name,
         list(DISTINCT canonical_name) AS aliase
  FROM rk WHERE identity_id IN (SELECT identity_id FROM tops) GROUP BY 1""")

# Top-CPV-Felder je Identität (Schwerpunkte)
con.execute(f"""CREATE OR REPLACE TEMP TABLE felder AS
  WITH c AS (SELECT identity_id, cpv4, count(*) n FROM w
             WHERE cpv4 IS NOT NULL AND cpv4 <> '' AND identity_id IN (SELECT identity_id FROM tops)
             GROUP BY 1,2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC) rn FROM c)
  SELECT r.identity_id,
         list({{'cpv4': r.cpv4, 'label': cl.label, 'wins': r.n}} ORDER BY r.n DESC) AS fields
  FROM rk r LEFT JOIN {CL} cl ON cl.cpv_code = r.cpv4 || '0000'
  WHERE r.rn <= 6 GROUP BY 1""")

# Top-Regionen (Leistungsort-NUTS1) je Identität
con.execute("""CREATE OR REPLACE TEMP TABLE regionen AS
  WITH c AS (SELECT identity_id, nuts1, count(*) n FROM w
             WHERE nuts1 IS NOT NULL AND nuts1 <> '' AND identity_id IN (SELECT identity_id FROM tops)
             GROUP BY 1,2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC) rn FROM c)
  SELECT identity_id, list(nuts1 ORDER BY n DESC) AS regions
  FROM rk WHERE rn <= 4 GROUP BY 1""")

# Typisches Volumen: Median der belegten Auftragswerte über die Leads dieser Identität
con.execute(f"""CREATE OR REPLACE TEMP TABLE volumen AS
  SELECT w.identity_id, median(e.value_eur) AS vol_median
  FROM w JOIN {E} e ON e.lead_id = w.notice_id
  WHERE e.value_source = 'actual' AND w.identity_id IN (SELECT identity_id FROM tops)
  GROUP BY 1""")

# Stat-Karte: distinkte Auftraggeber + „aktiv seit" (frühestes Zuschlagsjahr)
con.execute(f"""CREATE OR REPLACE TEMP TABLE stats AS
  SELECT w.identity_id, count(DISTINCT pb.entity_id) AS buyers, min(w.jahr) AS seit
  FROM w LEFT JOIN {PE} pb ON pb.notice_id = w.notice_id AND pb.role = 'buyer'
  WHERE w.identity_id IN (SELECT identity_id FROM tops)
  GROUP BY 1""")

# Gruppen-Mitglieder (Schwester-Entities): je Entität eigener Name, Methode, Konfidenz, Wins.
con.execute(f"""CREATE OR REPLACE TEMP TABLE members AS
  WITH ew AS (
    SELECT ei.identity_id, p.entity_id, count(DISTINCT p.notice_id) AS wins
    FROM {PE} p JOIN {EI} ei ON ei.entity_id = p.entity_id
    WHERE p.role = 'winner' AND ei.identity_id IN (SELECT identity_id FROM tops)
    GROUP BY 1, 2)
  SELECT ew.identity_id,
         list({{'name': e.canonical_name, 'method': e.method, 'conf': e.confidence, 'wins': ew.wins}}
              ORDER BY ew.wins DESC) AS members
  FROM ew JOIN {EN} e ON e.entity_id = ew.entity_id
  GROUP BY 1""")

rows = con.execute(f"""
  SELECT t.identity_id, n.name, n.aliase, t.wins, f.fields, r.regions, v.vol_median,
         s.buyers, s.seit, m.members
  FROM tops t
  LEFT JOIN namen n ON n.identity_id = t.identity_id
  LEFT JOIN felder f ON f.identity_id = t.identity_id
  LEFT JOIN regionen r ON r.identity_id = t.identity_id
  LEFT JOIN volumen v ON v.identity_id = t.identity_id
  LEFT JOIN stats s ON s.identity_id = t.identity_id
  LEFT JOIN members m ON m.identity_id = t.identity_id
  WHERE n.name IS NOT NULL AND {BLOCK_SQL}
  ORDER BY t.wins DESC""").fetchall()

# NUTS1 = 'DE' + genau ein Zeichen (DE1..DEG). Bare 'DE' (nur Land) = bundesweit-Signal, raus.
def clean_nuts(regs):
    return [r for r in (regs or []) if len(r) == 3 and r.startswith('DE')]

def method_conf(m):
    """Methode → belegt/unsicher + Klartext (Ticket #7 Confidence-Marke)."""
    belegt = m in ("handelsregister_exakt", "ted_nationalid")
    text = {"handelsregister_exakt": "über Handelsregister-Nummer belegt",
            "ted_nationalid": "über nationale Kennung belegt",
            "nur_name": "nur über den Firmennamen erkannt"}.get(m, m)
    return ("belegt" if belegt else "unsicher"), text


out = []
for (iid, name, aliase, wins, fields, regions, vol, buyers, seit, members) in rows:
    ms = []
    for mem in (members or []):
        conf, text = method_conf(mem["method"])
        ms.append({"name": mem["name"], "conf": conf, "method": text, "wins": int(mem["wins"])})
    out.append({
        "id": iid,
        "name": name,
        # Aliase nur, soweit sie sich vom Namen unterscheiden (für die Suche)
        "aliases": [a for a in (aliase or []) if a and a != name][:6],
        "wins": int(wins),
        "buyers": int(buyers) if buyers else None,
        "seit": int(seit) if seit else None,
        "fields": [dict(f) for f in (fields or [])],
        "regions": clean_nuts(regions),
        "volMedian": float(vol) if vol else None,
        "members": ms,
    })

(OUT / "suppliers.json").write_text(json.dumps(out, ensure_ascii=False))
print(f"{len(out)} Lieferanten → {OUT}/suppliers.json")
cancom = next((s for s in out if "cancom" in s["name"].lower()), None)
if cancom:
    print(f"\nBeispiel CANCOM: {cancom['name']} · {cancom['wins']} Zuschläge")
    print("  Felder:", ", ".join(f"{f['cpv4']} {f['label'][:24] if f['label'] else ''}" for f in cancom["fields"][:4]))
    print("  Regionen:", cancom["regions"], "· Volumen-Median:", cancom["volMedian"])

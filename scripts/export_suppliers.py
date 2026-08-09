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

MIN_WINS = 3      # Firmen ab 3 Zuschlägen auffindbar (Mittelstand); darunter ist das CPV-Profil zu dünn
MAX_ROWS = 40000  # Sicherheits-Deckel gegen Ausreißer

# Generik-/Käufer-Stämme (Ticket #7 v2, Leitplanke 2): keine öffentlichen Käufer, raus.
# WORTANFANG-Match (am Namensanfang ODER nach einem Leerzeichen) — NICHT beliebiger Substring.
# Sonst blockt 'land ' auch „…Deutschland GmbH" (211 echte Firmen: MAN, Rosenbauer, Telekom …)
# und 'stadt' auch „Filderstadt". Wortanfang fängt „Stadtwerke"/„Land Berlin"/„Landkreis Cham",
# lässt aber „Deutschland/Filderstadt/Kommunaltechnik" durch.
BLOCK_WORD = ['stadt', 'gemeinde', 'landkreis', 'kreis', 'bezirk', 'vergabekammer', 'arge',
              'bietergemeinschaft', 'ministerium', 'behörde', 'körperschaft', 'zweckverband',
              'eigenbetrieb', 'kommunal', 'land', 'freistaat', 'bundesamt', 'bundesministerium',
              'universität', 'hochschule']
BLOCK_SUB = ['anstalt des', 'klinikum der']   # spezifische Phrasen: überall im Namen ok
def _block_sql(col):
    cl = []
    for b in BLOCK_WORD:
        cl.append(f"lower({col}) NOT LIKE '{b}%'")     # Namensanfang
        cl.append(f"lower({col}) NOT LIKE '% {b}%'")   # nach Leerzeichen (Wortanfang)
    for b in BLOCK_SUB:
        cl.append(f"lower({col}) NOT LIKE '%{b}%'")
    return ' AND '.join(cl)
BLOCK_SQL = _block_sql('name')

# Gewinner-Zuschläge mit Identity, CPV4 und Leistungsort-NUTS1. Nur Identitäten, die
# mindestens eine belegt aufgelöste Entity (HR/national-id) enthalten — sonst Namens-Rauschen.
con.execute(f"""CREATE OR REPLACE TEMP TABLE belegt AS
  SELECT DISTINCT ei.identity_id
  FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id
  WHERE e.method IN ('handelsregister_exakt','ted_nationalid')""")

con.execute(f"""CREATE OR REPLACE TEMP TABLE w AS
  SELECT ei.identity_id, ei.canonical_name, p.entity_id, p.notice_id,
         substr(n.cpv_main, 1, 4) AS cpv4,
         substr(n.cpv_main, 1, 6) AS cpv6,
         substr(n.performance_nuts, 1, 3) AS nuts1,
         year(n.publication_date) AS jahr
  FROM {PE} p
  JOIN {EI} ei ON ei.entity_id = p.entity_id
  JOIN {N} n ON n.notice_id = p.notice_id
  WHERE p.role = 'winner' AND ei.identity_id IN (SELECT identity_id FROM belegt)""")

# Identitäten ab MIN_WINS Zuschlägen
con.execute(f"""CREATE OR REPLACE TEMP TABLE tops AS
  SELECT identity_id, count(DISTINCT notice_id) AS wins
  FROM w GROUP BY 1 HAVING count(DISTINCT notice_id) >= {MIN_WINS}
  ORDER BY 2 DESC LIMIT {MAX_ROWS}""")

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

# Top-CPV-6-Felder je Identität (gewerkscharf) — ohne Divisions-Sammelcodes (XX0000).
# CPV-6 trennt die Gewerke, die CPV-4 zusammenwirft (Aufzug 453131 ≠ Elektro 453112). Speist
# den Relevanz-Volltreffer; CPV-4 (fields) bleibt als Nachbarfeld.
con.execute(f"""CREATE OR REPLACE TEMP TABLE felder6 AS
  WITH c AS (SELECT identity_id, cpv6, count(*) n FROM w
             WHERE cpv6 IS NOT NULL AND length(cpv6) = 6 AND substr(cpv6, 3, 4) <> '0000'
               AND identity_id IN (SELECT identity_id FROM tops)
             GROUP BY 1,2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC) rn FROM c)
  SELECT r.identity_id,
         list({{'cpv6': r.cpv6, 'wins': r.n}} ORDER BY r.n DESC) AS fields6
  FROM rk r
  WHERE r.rn <= 12 GROUP BY 1""")   # ohne Label: nur der Code zählt fürs Matching (spart ~3 MB)

# Regionaler Fußabdruck (Leistungsort-NUTS1) je Identität — AUS DER HISTORIE ABGELEITET.
# Statt stumpf „Top 4" die KLEINSTE Regionsmenge, die 80 % der Zuschläge abdeckt:
#   1-2 Regionen  → regional      (45 % + 22 % aller Firmen, gemessen)
#   3-5 Regionen  → teilregional  (28 %)
#   ab 6          → bundesweit    (5 %) → leere Liste = kein Regionsfilter, sonst würde man
#                                   auf 6 von 16 Bundesländern „filtern", was nichts aussagt.
# Das macht den Filter selbstjustierend: ein Hammer Elektriker bekommt NRW, Cancom nichts.
con.execute("""CREATE OR REPLACE TEMP TABLE regionen AS
  WITH c AS (SELECT identity_id, nuts1, count(*) n FROM w
             WHERE nuts1 IS NOT NULL AND nuts1 <> '' AND identity_id IN (SELECT identity_id FROM tops)
             GROUP BY 1,2),
  t AS (SELECT identity_id, sum(n) tot FROM c GROUP BY 1),
  r AS (SELECT c.*, t.tot,
               row_number() OVER (PARTITION BY c.identity_id ORDER BY c.n DESC) rn,
               sum(c.n) OVER (PARTITION BY c.identity_id ORDER BY c.n DESC ROWS UNBOUNDED PRECEDING) kum
        FROM c JOIN t ON t.identity_id = c.identity_id),
  n80 AS (SELECT identity_id, min(rn) FILTER (WHERE kum >= 0.8 * tot) AS noetig
          FROM r GROUP BY 1)
  SELECT r.identity_id,
         CASE WHEN n80.noetig >= 6 THEN []::VARCHAR[]          -- bundesweit → kein Filter
              ELSE list(r.nuts1 ORDER BY r.n DESC) END AS regions,
         min(n80.noetig) AS regionen_fuer_80
  FROM r JOIN n80 ON n80.identity_id = r.identity_id
  WHERE r.rn <= coalesce(n80.noetig, 4)
  GROUP BY r.identity_id, n80.noetig""")

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
  SELECT t.identity_id, n.name, n.aliase, t.wins, f.fields, f6.fields6, r.regions, r.regionen_fuer_80, v.vol_median,
         s.buyers, s.seit, m.members
  FROM tops t
  LEFT JOIN namen n ON n.identity_id = t.identity_id
  LEFT JOIN felder f ON f.identity_id = t.identity_id
  LEFT JOIN felder6 f6 ON f6.identity_id = t.identity_id
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
for (iid, name, aliase, wins, fields, fields6, regions, reg80, vol, buyers, seit, members) in rows:
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
        "fields6": [dict(f) for f in (fields6 or [])],
        "regions": clean_nuts(regions),
        # aus der Historie abgeleitet: wie viele Regionen für 80 % der Aufträge nötig sind
        # (1-2 = regional, 3-5 = teilregional, ≥6 = bundesweit → regions ist dann leer)
        "regionTyp": ("regional" if (reg80 or 9) <= 2 else "teilregional" if (reg80 or 9) <= 5 else "bundesweit"),
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

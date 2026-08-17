"""Lieferanten-Index für das Onboarding-Matching → web/data/suppliers.json

Wer sich anmeldet, ist mit hoher Wahrscheinlichkeit schon als Bieter in den Daten.
Statt ein leeres Profil abzufragen, matchen wir den Firmennamen gegen die echten
Gewinner und leiten das Profil aus dem Zuschlags-Verlauf ab (§4.2: „gemessen").

Gruppiert über `entity_identity` (grp:*), damit die Varianten einer Firma (z. B. die
24 CANCOM-Entities) zu EINEM Profil verschmelzen. Nur belegt aufgelöste Identitäten.
"""
import duckdb, json, os, pathlib, requests

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
  ORDER BY 2 DESC, identity_id LIMIT {MAX_ROWS}""")

# Repräsentativer Name = häufigster canonical_name der Gruppe; Aliase = die übrigen
con.execute("""CREATE OR REPLACE TEMP TABLE namen AS
  WITH cnt AS (SELECT identity_id, canonical_name, count(*) c FROM w
               WHERE canonical_name IS NOT NULL GROUP BY 1,2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY c DESC, length(canonical_name), canonical_name) rn FROM cnt)
  SELECT identity_id,
         max(canonical_name) FILTER (WHERE rn = 1) AS name,
         list(DISTINCT canonical_name ORDER BY canonical_name) AS aliase
  FROM rk WHERE identity_id IN (SELECT identity_id FROM tops) GROUP BY 1""")

# Top-CPV-Felder je Identität (Schwerpunkte)
con.execute(f"""CREATE OR REPLACE TEMP TABLE felder AS
  WITH c AS (SELECT identity_id, cpv4, count(*) n FROM w
             WHERE cpv4 IS NOT NULL AND cpv4 <> '' AND identity_id IN (SELECT identity_id FROM tops)
             GROUP BY 1,2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC, cpv4) rn FROM c)
  SELECT r.identity_id,
         list({{'cpv4': r.cpv4, 'label': cl.label, 'wins': r.n}} ORDER BY r.n DESC, r.cpv4) AS fields
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
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC, cpv6) rn FROM c)
  SELECT r.identity_id,
         list({{'cpv6': r.cpv6, 'wins': r.n}} ORDER BY r.n DESC, r.cpv6) AS fields6
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
               row_number() OVER (PARTITION BY c.identity_id ORDER BY c.n DESC, c.nuts1) rn,
               sum(c.n) OVER (PARTITION BY c.identity_id ORDER BY c.n DESC, c.nuts1 ROWS UNBOUNDED PRECEDING) kum
        FROM c JOIN t ON t.identity_id = c.identity_id),
  n80 AS (SELECT identity_id, min(rn) FILTER (WHERE kum >= 0.8 * tot) AS noetig
          FROM r GROUP BY 1)
  SELECT r.identity_id,
         CASE WHEN n80.noetig >= 6 THEN []::VARCHAR[]          -- bundesweit → kein Filter
              ELSE list(r.nuts1 ORDER BY r.n DESC, r.nuts1) END AS regions,
         min(n80.noetig) AS regionen_fuer_80
  FROM r JOIN n80 ON n80.identity_id = r.identity_id
  WHERE r.rn <= coalesce(n80.noetig, 4)
  GROUP BY r.identity_id, n80.noetig""")

# Typisches Volumen: Median der belegten Auftragswerte über die Leads dieser Identität
con.execute(f"""CREATE OR REPLACE TEMP TABLE volumen AS
  WITH v AS (SELECT w.identity_id, e.value_eur
             FROM w JOIN {E} e ON e.lead_id = w.notice_id
             WHERE e.value_source = 'actual' AND w.identity_id IN (SELECT identity_id FROM tops)),
  haeufigster AS (SELECT identity_id, value_eur, count(*) c,
                         row_number() OVER (PARTITION BY identity_id ORDER BY count(*) DESC, value_eur) rn
                  FROM v GROUP BY 1, 2)
  SELECT v.identity_id, median(v.value_eur) AS vol_median,
         count(*) AS wert_belege,                      -- wie viele Zuschläge überhaupt einen Wert tragen
         max(h.c) * 1.0 / count(*) AS wert_klumpen     -- Anteil des häufigsten Einzelwerts
  FROM v LEFT JOIN haeufigster h ON h.identity_id = v.identity_id AND h.rn = 1
  GROUP BY 1""")

# Stat-Karte: distinkte Auftraggeber + „aktiv seit" (frühestes Zuschlagsjahr)
con.execute(f"""CREATE OR REPLACE TEMP TABLE stats AS
  SELECT w.identity_id, count(DISTINCT pb.entity_id) AS buyers, min(w.jahr) AS seit
  FROM w LEFT JOIN {PE} pb ON pb.notice_id = w.notice_id AND pb.role = 'buyer'
  WHERE w.identity_id IN (SELECT identity_id FROM tops)
  GROUP BY 1""")

# Top-Auftraggeber je Identität, namentlich, mit Zeitraum. Plus der Anteil des größten
# am Gesamtvolumen — eine hohe Konzentration ist eine echte Erkenntnis für den Kunden
# (Jäger: 1.148 von 1.830 Zuschlägen bei EINEM Auftraggeber), keine Randnotiz.
con.execute(f"""CREATE OR REPLACE TEMP TABLE kunden AS
  WITH kb AS (
    SELECT w.identity_id, eb.canonical_name AS buyer, count(DISTINCT w.notice_id) AS n,
           min(w.jahr) AS seit, max(w.jahr) AS bis
    FROM w JOIN {PE} pb ON pb.notice_id = w.notice_id AND pb.role = 'buyer'
           JOIN {EN} eb ON eb.entity_id = pb.entity_id
    WHERE w.identity_id IN (SELECT identity_id FROM tops) AND eb.canonical_name IS NOT NULL
    GROUP BY 1, 2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC, buyer) rn,
                sum(n) OVER (PARTITION BY identity_id) tot FROM kb)
  SELECT identity_id,
         list({{'name': buyer, 'wins': n, 'seit': seit, 'bis': bis}} ORDER BY n DESC, buyer)
           FILTER (WHERE rn <= 3) AS top_kunden,
         max(CASE WHEN rn = 1 THEN n * 1.0 / nullif(tot, 0) END) AS top_anteil
  FROM rk GROUP BY 1""")

# Bekannte Firmen-Domain aus den Gewinner-Kontaktadressen der Vergabedaten.
# Gemessen: 52,8 % der Identitäten haben eine — damit lässt sich der Identitäts-Anspruch
# beim Onboarding ohne Rückfrage belegen, wenn die Registrierungs-Adresse dazu passt.
# ACHTUNG: Das Feld ist SERVERSEITIG. Es darf nie im Suchergebnis ans Frontend gehen —
# sonst wären die Kontaktdomains aller Firmen über die Suche abgreifbar.
con.execute(f"""CREATE OR REPLACE TEMP TABLE domains AS
  WITH kauf AS (   -- Domain des AUFTRAGGEBERS je Bekanntmachung
    SELECT lead_id, lower(split_part(email, '@', 2)) AS dom
    FROM read_parquet('{G}/lead_party.parquet')
    WHERE party_role = 'buyer' AND email LIKE '%@%'),
  m AS (
    SELECT w.identity_id, lower(split_part(lp.email, '@', 2)) AS dom
    FROM w JOIN read_parquet('{G}/lead_party.parquet') lp ON lp.lead_id = w.notice_id
           LEFT JOIN kauf k ON k.lead_id = w.notice_id
    WHERE lower(lp.party_role) LIKE '%win%' AND lp.email LIKE '%@%'
      AND w.identity_id IN (SELECT identity_id FROM tops)
      -- Das Gewinner-Mailfeld trägt in 14 % der Fälle die Adresse des Auftraggebers
      -- (gemessen). Ungefiltert bekäme LEONHARD WEISS die Domain deutschebahn.com —
      -- und jeder mit DB-Adresse könnte fremde Firmen beanspruchen.
      AND (k.dom IS NULL OR lower(split_part(lp.email, '@', 2)) <> k.dom)
      -- Platzhalter aus dem TED-Schema, keine echten Adressen
      AND lower(split_part(lp.email, '@', 2)) NOT IN ('emailaddress.given', 'example.com', 'nicht.angegeben')),
  c AS (SELECT identity_id, dom, count(*) n FROM m WHERE dom <> '' GROUP BY 1, 2),
  r AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC, dom) rn FROM c)
  SELECT identity_id, dom AS domain, n AS domain_belege FROM r WHERE rn = 1""")

# Konkrete Kontaktadressen der Gewinner — als HASH, nie im Klartext.
#
# Der Domain-Abgleich hilft nur Firmen mit eigener Domain. Genau die Gruppe, die ihn
# nicht hat (2.522 Firmen mit überwiegend privater Adresse, davon 1.239 t-online), ist
# aber fast vollständig über die konkrete Adresse belegbar: 2.518 von ihnen haben eine
# in den Vergabedaten. Wer sich mit genau dieser Adresse registriert, IST der Kontakt,
# der die Zuschläge entgegengenommen hat — ein stärkerer Beleg als jede Domain.
#
# Gespeichert wird sha256(normalisierte Adresse), auf 16 Hex-Zeichen gekürzt. Die Datei
# liegt ohnehin nur serverseitig; der Hash verhindert zusätzlich, dass sich aus ihr eine
# Adressliste ERNTEN lässt. Gegen das Nachprüfen einer bereits erratenen Adresse schützt
# er nicht — das kann er ohne geheimen Schlüssel auch nicht, und dafür ist er nicht da.
con.execute(f"""CREATE OR REPLACE TEMP TABLE mailhashes AS
  WITH kauf AS (
    SELECT lead_id, lower(split_part(email, '@', 2)) AS dom FROM read_parquet('{G}/lead_party.parquet')
    WHERE party_role = 'buyer' AND email LIKE '%@%'),
  m AS (
    SELECT DISTINCT w.identity_id, lower(trim(lp.email)) AS mail
    FROM w JOIN read_parquet('{G}/lead_party.parquet') lp ON lp.lead_id = w.notice_id
           LEFT JOIN kauf k ON k.lead_id = w.notice_id
    WHERE lower(lp.party_role) LIKE '%win%' AND lp.email LIKE '%@%'
      AND w.identity_id IN (SELECT identity_id FROM tops)
      -- ⚠ AUF DIE DOMAIN vergleichen, nicht auf die Adresse. Der Abgleich stand bis
      -- 2026-08-17 auf der exakten Adresse und ging deshalb an genau den Faellen vorbei,
      -- die zaehlen: die Vergabestelle traegt EINE Adresse als eigenen Kontakt ein und
      -- eine ANDERE ihrer Domain in die Gewinner-Zeile. Beide sind nicht identisch, also
      -- griff der Filter nicht.
      --
      -- Konkret: H. Klostermann Baugesellschaft trug als einzige „eigene" Adresse
      -- `bieterportal-alt@deutschebahn.com`. Wer bei der Bahn diese Adresse hat, waere
      -- als belegter Klostermann durch die Identitaetspruefung gekommen.
      -- Gemessen betrifft das 12.246 von 87.310 Gewinner-Adressen (14,0 %).
      AND (k.dom IS NULL OR lower(split_part(lp.email, '@', 2)) <> k.dom)
      AND lower(split_part(lp.email, '@', 2)) NOT IN ('emailaddress.given', 'example.com'))
  -- ORDER BY ist Pflicht: ohne ihn liefert die Aggregation die Hashes in wechselnder
  -- Reihenfolge, und die Datei aendert sich bei jedem Lauf ohne Datenaenderung.
  SELECT identity_id, list(substr(sha256(mail), 1, 16) ORDER BY substr(sha256(mail), 1, 16))
         AS mail_hashes
  FROM m GROUP BY 1""")

# Gruppen-Mitglieder (Schwester-Entities): je Entität eigener Name, Methode, Konfidenz, Wins.
con.execute(f"""CREATE OR REPLACE TEMP TABLE members AS
  WITH ew AS (
    SELECT ei.identity_id, p.entity_id, count(DISTINCT p.notice_id) AS wins
    FROM {PE} p JOIN {EI} ei ON ei.entity_id = p.entity_id
    WHERE p.role = 'winner' AND ei.identity_id IN (SELECT identity_id FROM tops)
    GROUP BY 1, 2)
  SELECT ew.identity_id,
         list({{'name': e.canonical_name, 'method': e.method, 'conf': e.confidence, 'wins': ew.wins}}
              ORDER BY ew.wins DESC, e.canonical_name) AS members
  FROM ew JOIN {EN} e ON e.entity_id = ew.entity_id
  GROUP BY 1""")

rows = con.execute(f"""
  SELECT t.identity_id, n.name, n.aliase, t.wins, f.fields, f6.fields6, r.regions, r.regionen_fuer_80,
         v.vol_median, v.wert_belege, v.wert_klumpen, s.buyers, s.seit, m.members, k.top_kunden, k.top_anteil,
         d.domain, d.domain_belege, mh.mail_hashes
  FROM tops t
  LEFT JOIN namen n ON n.identity_id = t.identity_id
  LEFT JOIN felder f ON f.identity_id = t.identity_id
  LEFT JOIN felder6 f6 ON f6.identity_id = t.identity_id
  LEFT JOIN regionen r ON r.identity_id = t.identity_id
  LEFT JOIN volumen v ON v.identity_id = t.identity_id
  LEFT JOIN stats s ON s.identity_id = t.identity_id
  LEFT JOIN members m ON m.identity_id = t.identity_id
  LEFT JOIN kunden k ON k.identity_id = t.identity_id
  LEFT JOIN domains d ON d.identity_id = t.identity_id
  LEFT JOIN mailhashes mh ON mh.identity_id = t.identity_id
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



def belegte_domains() -> dict[str, dict]:
    """Per Impressum bestaetigte Domains aus `domain_proof` zurueck in den Firmenbestand.

    **Warum das der Muehe wert ist.** Zu 47 % unserer Firmen kennen wir keine Domain, und
    die uebrigen kommen aus Kontaktmails der Vergabeunterlagen — einer Quelle, die gemessen
    zu 7,5 % die Adresse des AUFTRAGGEBERS traegt statt die des Gewinners. Der Impressum-
    Pruefer verifiziert genau diese Zuordnung, an 200 verwuerfelten Paaren mit 0,0 %
    Fehlbestaetigungen. Ohne diesen Rueckfluss haetten wir dieses Wissen einmal erzeugt und
    danach jedes Mal weggeworfen.

    **Nur `belegt`.** `widerlegt` sagt „diese Domain gehoert der Firma nicht" und ist als
    Negativwissen wertvoll, aber es benennt keine Domain. `nicht_pruefbar` sagt ueberhaupt
    nichts ausser „gerade nicht erreichbar".

    Faellt der Abruf aus, kommt eine leere Abbildung zurueck und der Export laeuft mit den
    abgeleiteten Domains weiter. Ein fehlender Rueckfluss ist ein verpasster Gewinn, kein
    Schaden — und darf den Tageslauf nicht anhalten.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and key):
        pfad = pathlib.Path(".secrets/supabase.txt")
        if pfad.exists():
            zeilen = [z.strip() for z in pfad.read_text().splitlines() if z.strip()]
            if len(zeilen) >= 2:
                url, key = zeilen[0], zeilen[1]
    if not (url and key):
        print("  ⚠ keine Supabase-Zugangsdaten — Impressum-Rueckfluss uebersprungen")
        return {}
    ziel = (f"{url.rstrip('/')}/rest/v1/domain_proof"
            "?select=domain,identity_id,geprueft_am&urteil=eq.belegt")
    # `requests` statt `urllib`: urllib nutzt den System-Zertifikatsspeicher, und der ist
    # auf dieser Maschine leer (CERTIFICATE_VERIFY_FAILED). requests bringt certifi mit.
    try:
        antwort = requests.get(ziel, timeout=30, headers={
            "apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
        antwort.raise_for_status()
        rows = antwort.json()
    except Exception as e:
        print(f"  ⚠ domain_proof nicht lesbar ({type(e).__name__}) — Rueckfluss uebersprungen")
        return {}
    # Mehrere Belege je Firma sind moeglich (Konzern mit zwei Domains). Der juengste
    # gewinnt — er beschreibt den heutigen Auftritt, nicht den von vor zwei Jahren.
    out: dict[str, dict] = {}
    for z in rows:
        iid, am = z.get("identity_id"), z.get("geprueft_am") or ""
        if not iid:
            continue
        if iid not in out or am > out[iid]["am"]:
            out[iid] = {"domain": z.get("domain"), "am": am}
    print(f"  ✓ {len(out):,} per Impressum bestaetigte Domains aus domain_proof")
    return out


belegte = belegte_domains()

out = []
for (iid, name, aliase, wins, fields, fields6, regions, reg80, vol, wert_belege, wert_klumpen,
     buyers, seit, members, top_kunden, top_anteil, domain, domain_belege, mail_hashes) in rows:
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
        # Ein „typischer Auftragswert" braucht zwei Belege, sonst ist er geraten:
        #  · genug Datenpunkte — 11.421 von 16.794 Firmen mit Wert haben GENAU EINEN;
        #    daraus einen Median zu bilden ist Zahlenkosmetik. Schwelle: 5.
        #  · kein dominierender Einzelbetrag — bei Jäger Spezialtiefbau sind 1.306 von
        #    1.344 Werten identisch (61,9 Mio €): die auf jeden Abruf wiederholte
        #    Rahmenvertragssumme. Betrifft 66 der 1.155 Firmen mit ≥5 Werten.
        # Ergebnis: ~1.089 Firmen bekommen einen belastbaren Wert, der Rest keinen.
        "volMedian": float(vol) if (vol and (wert_belege or 0) >= 5 and (wert_klumpen or 0) <= 0.4) else None,
        # Namentliche Auftraggeber — der Wiedererkennungs-Moment im Onboarding.
        "topBuyers": [{"name": k["name"], "wins": int(k["wins"]),
                       "seit": int(k["seit"]), "bis": int(k["bis"])} for k in (top_kunden or [])],
        # Anteil des größten Auftraggebers: ab ~40 % ist das ein Klumpenrisiko, das der
        # Kunde kennen sollte — und zugleich unser stärkstes Argument fürs Diversifizieren.
        "topShare": round(float(top_anteil), 3) if top_anteil else None,
        # Nur serverseitig ausgewertet (siehe /api/entity-verify) — nie ins Suchergebnis.
        # Ein per Impressum BESTAETIGTER Eintrag ueberschreibt hier die aus Mailadressen
        # abgeleitete Domain, statt sie nur zu ergaenzen. Grund ist ein Qualitaetsunterschied,
        # kein Geschmack: die Ableitung aus Kontaktmails traegt gemessen 7,5 % Auftraggeber-
        # Adressen, der Impressum-Beleg an 200 verwuerfelten Paaren 0,0 % Fehlbestaetigungen.
        # Wer die schwaechere Quelle gewinnen liesse, machte die Pruefung wertlos.
        "domain": (belegte.get(iid) or {}).get("domain") or domain or None,
        "domainBelege": int(domain_belege) if domain_belege else 0,
        # Woher die Domain stammt. Die Leiter in /api/entity-verify soll unterscheiden
        # koennen: „passt zu einer Adresse aus den Vergabeunterlagen" ist ein Indiz,
        # „steht im Impressum dieser Domain" ist ein Beleg.
        "domainQuelle": "impressum" if iid in belegte else ("kontakt" if domain else None),
        "domainGeprueft": (belegte.get(iid) or {}).get("am"),
        "mailHashes": list(mail_hashes or []),
        "members": ms,
    })

# Reihenfolge festnageln: die Zeilen kommen aus einer Abfrage ohne eindeutigen
# Endschluessel, und ohne diese Sortierung aendert sich die Datei bei jedem Lauf.
out.sort(key=lambda x: (-int(x.get("wins") or 0), str(x.get("id") or "")))
(OUT / "suppliers.json").write_text(json.dumps(out, ensure_ascii=False, sort_keys=True))
print(f"{len(out)} Lieferanten → {OUT}/suppliers.json")
cancom = next((s for s in out if "cancom" in s["name"].lower()), None)
if cancom:
    print(f"\nBeispiel CANCOM: {cancom['name']} · {cancom['wins']} Zuschläge")
    print("  Felder:", ", ".join(f"{f['cpv4']} {f['label'][:24] if f['label'] else ''}" for f in cancom["fields"][:4]))
    print("  Regionen:", cancom["regions"], "· Volumen-Median:", cancom["volMedian"])

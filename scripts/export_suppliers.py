"""Lieferanten-Index für das Onboarding-Matching → web/data/suppliers.json

Wer sich anmeldet, ist mit hoher Wahrscheinlichkeit schon als Bieter in den Daten.
Statt ein leeres Profil abzufragen, matchen wir den Firmennamen gegen die echten
Gewinner und leiten das Profil aus dem Zuschlags-Verlauf ab (§4.2: „gemessen").

Gruppiert über `entity_identity` (grp:*), damit die Varianten einer Firma (z. B. die
24 CANCOM-Entities) zu EINEM Profil verschmelzen. Nur belegt aufgelöste Identitäten.
"""
import duckdb, hashlib, json, os, pathlib, requests

OUT = pathlib.Path("web/data"); OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(); con.execute("SET threads=4")
G = "data/gold/DE"


def _union(tabelle: str) -> str:
    """Gold-Tabelle ueber ALLE Laender, DE zuerst (Basis-Schema).

    ⚠ Bis 2026-08-23 las dieses Skript ausschliesslich `data/gold/DE`. Der Firmenindex
    fuers Onboarding enthielt damit 31.459 Firmen und KEINE rein oesterreichische oder
    schweizerische — obwohl 34.340 AT- und 15.494 CH-Auftragnehmer in `contractor_stats`
    liegen. Gemessen: PORR war auffindbar, weil es auch in Deutschland gewinnt; Implenia
    Schweiz nicht. Eine Schweizer Firma fiel bei der Anmeldung auf den manuellen Pfad.
    """
    weitere = sorted(str(x) for x in pathlib.Path("data/gold").glob(f"*/{tabelle}.parquet")
                     if x.parent.name != "DE")
    dateien = [f"{G}/{tabelle}.parquet"] + weitere
    lst = ", ".join(f"'{d}'" for d in dateien)
    return f"read_parquet([{lst}], union_by_name=true)"


def _silber_union(tabelle: str) -> str:
    """Silber-Tabelle ueber alle Laender, die sie fuehren.

    Getrennt von `_union`: Gold hat EINE Datei je Land, Silber einen Baum aus
    Jahrespartitionen. Ein Glob ins Leere ist in DuckDB ein Laufzeitfehler.
    """
    muster = [f"data/silver/{x.parent.name}/{tabelle}/*/*.parquet"
              for x in sorted(pathlib.Path("data/silver").glob(f"*/{tabelle}"))
              if list(x.glob("*/*.parquet"))]
    lst = ", ".join(f"'{m}'" for m in muster)
    return f"read_parquet([{lst}], hive_partitioning=1, union_by_name=true)"


PE = _union("party_entity")
EI = _union("entity_identity")
EN = _union("entities")
CL = f"read_parquet('{G}/dim_cpv_label.parquet')"   # EU-Vokabular, eine Kopie genuegt
LP = _union("lead_party")
N = _silber_union("notices")
E = _union("lead_export")

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
# ⚠ ENTARTETE KENNUNGEN AUSSCHLIESSEN. Seit dieses Skript ueber alle Laender liest, ist
# das keine Feinheit mehr, sondern Pflicht: 1.722 `identity_id` kommen in mehr als einem
# Land vor, und 29 davon sind Platzhalter — `solo:id:.`, `solo:id:00000`, `solo:id:N/A`,
# `solo:id:00000000`. Unter ihnen faellt zusammen, was nichts miteinander zu tun hat
# (gemessen: „Fa. Scharr Tec GmbH & Co.KG" und „Bieter"). Die uebrigen 1.693 sind ECHTE
# grenzueberschreitende Firmen (Kaercher, Schindler Aufzuege, Amberg Engineering) und
# sollen genau deshalb zu EINEM Eintrag verschmelzen.
_KERN = "regexp_replace(split_part(identity_id, ':', -1), '[.0[:space:]-]', '', 'g')"
GUELTIG = (f"length({_KERN}) >= 3 AND lower({_KERN}) "
           f"NOT IN ('na', 'n/a', 'keine', 'unbekannt', 'bieter', 'unknown')")

con.execute(f"""CREATE OR REPLACE TEMP TABLE belegt AS
  SELECT DISTINCT ei.identity_id
  FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id
  WHERE e.method IN ('handelsregister_exakt','ted_nationalid')
    AND {GUELTIG.replace('identity_id', 'ei.identity_id')}""")

con.execute(f"""CREATE OR REPLACE TEMP TABLE w AS
  SELECT ei.identity_id, ei.canonical_name, p.entity_id, p.notice_id,
         substr(n.cpv_main, 1, 4) AS cpv4,
         substr(n.cpv_main, 1, 6) AS cpv6,
         -- REGIONS-EBENE JE LAND (s. govisor.gold._REGION_STELLEN). Ein fester Schnitt
         -- auf 3 Zeichen ist eine deutsche Annahme; AT1 hiesse „Ostoesterreich", CH0 die
         -- ganze Schweiz. Beim kritischen Durchgang am 2026-08-23 gefunden: die FIRMEN
         -- waren da schon laenderweit, ihre REGIONEN noch nicht.
         substr(n.performance_nuts, 1,
                CASE substr(n.performance_nuts, 1, 2)
                     WHEN 'AT' THEN 4 WHEN 'CH' THEN 5 ELSE 3 END) AS nuts1,
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

# ── WIE DIE GRUPPE HEISST ───────────────────────────────────────────────────────────
# ⚠ Bis zum 2026-08-21 galt „häufigster canonical_name der Gruppe". Sven beim Testlauf mit
# einer @netgo.de-Adresse: „ich glaube die netgo ost ist nicht die zentrale netgo einheit
# oder?" Genau so war es. Die Gruppe `grp:netgo` ist inhaltlich richtig (14 Mitglieder,
# 98 Zuschläge), sie hiess nur nach der falschen Tochter: „netgo Ost GmbH" klebt an SECHS
# Entitäten (dieselbe Firma, sechsmal verschieden geschrieben — HRB84278, HRB84278B,
# „HRB84278B,", HRB84278BerlinCh, zwei Umsatzsteuer-IDs), „NETGO GmbH" nur an einer, dafür
# mit Handelsregister-Beleg und den meisten Zuschlägen (40 gegen 20).
#
# Häufigkeit misst also, wie zerfranst die Schreibweise einer Tochter ist, nicht wer die
# Mutter ist. Der Name geht deshalb jetzt an den STAMM: an das Mitglied, dessen Name in den
# Namen der anderen steckt („netgo" in „netgo Ost", „netgo Süd", „netgo Nürnberg" …). Nur
# wenn es keinen solchen Stamm gibt, entscheidet wie bisher die Häufigkeit.
# Als Konstante, damit die Regel ohne den ganzen Export prüfbar ist
# (tests/test_entities.py::test_gruppenname_geht_an_den_stamm).
NAMEN_SQL = """CREATE OR REPLACE TEMP TABLE namen AS
  WITH cnt AS (SELECT identity_id, canonical_name, count(*) c FROM w
               WHERE canonical_name IS NOT NULL GROUP BY 1,2),
  -- Rechtsform und Zeichensetzung weg, damit „NETGO GmbH" und „netgo Ost GmbH"
  -- vergleichbar werden.
  norm AS (SELECT *, trim(regexp_replace(lower(canonical_name),
             '(gmbh|ag|se|kg|mbh|co\\.?|&|,|\\.)', ' ', 'g')) AS kern FROM cnt),
  -- Wie viele ANDERE Mitglieder fangen mit diesem Kern an? Das ist die Stammeigenschaft.
  stamm AS (SELECT a.identity_id, a.canonical_name, a.c, a.kern,
                   (SELECT count(*) FROM norm b
                     WHERE b.identity_id = a.identity_id AND b.kern <> a.kern
                       AND b.kern LIKE a.kern || '%') AS kinder
            FROM norm a),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id
                     ORDER BY (kinder >= 2) DESC, kinder DESC, c DESC,
                              length(canonical_name), canonical_name) rn
         FROM stamm)
  SELECT identity_id,
         max(canonical_name) FILTER (WHERE rn = 1) AS name,
         list(DISTINCT canonical_name ORDER BY canonical_name) AS aliase
  FROM rk WHERE identity_id IN (SELECT identity_id FROM tops) GROUP BY 1"""
con.execute(NAMEN_SQL)

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
con.execute("""CREATE OR REPLACE TEMP TABLE felder6 AS
  WITH c AS (SELECT identity_id, cpv6, count(*) n FROM w
             WHERE cpv6 IS NOT NULL AND length(cpv6) = 6 AND substr(cpv6, 3, 4) <> '0000'
               AND identity_id IN (SELECT identity_id FROM tops)
             GROUP BY 1,2),
  rk AS (SELECT *, row_number() OVER (PARTITION BY identity_id ORDER BY n DESC, cpv6) rn FROM c)
  SELECT r.identity_id,
         list({'cpv6': r.cpv6, 'wins': r.n} ORDER BY r.n DESC, r.cpv6) AS fields6
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
    FROM {LP}
    WHERE party_role = 'buyer' AND email LIKE '%@%'),
  m AS (
    SELECT w.identity_id, lower(split_part(lp.email, '@', 2)) AS dom
    FROM w JOIN {LP} lp ON lp.lead_id = w.notice_id
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
    SELECT lead_id, lower(split_part(email, '@', 2)) AS dom FROM {LP}
    WHERE party_role = 'buyer' AND email LIKE '%@%'),
  m AS (
    SELECT DISTINCT w.identity_id, lower(trim(lp.email)) AS mail
    FROM w JOIN {LP} lp ON lp.lead_id = w.notice_id
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

# Regionskennung = Landeskuerzel PLUS mindestens eine Stelle. Ein blosses „DE"/„AT"/„CH"
# ist das Bundesweit-Signal und keine Region — das faellt raus.
#
# ⚠ Die Laenge ist je Land verschieden (DE 3, AT 4, CH 5). Der fruehere Test
# `len(r) == 3 and r.startswith('DE')` verwarf deshalb JEDE oesterreichische und
# schweizerische Region — die Firmen waren nach der Umstellung auffindbar und standen
# ohne Einsatzgebiet da.
_STELLEN = {"DE": 3, "AT": 4, "CH": 5}


def clean_nuts(regs):
    aus = []
    for r in (regs or []):
        if not r or len(r) < 3:
            continue
        soll = _STELLEN.get(r[:2])
        if soll and len(r) == soll:
            aus.append(r)
    return aus

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

# ── GRENZGAENGER ZU EINEM EINTRAG ───────────────────────────────────────────────────
# Seit dieses Skript alle Laender liest, traegt dieselbe Firma mehrere Identitaeten:
# ACP IT Solutions kam mit VIER Eintraegen (`solo:id:032844a`, zwei GLN und
# `solo:id:FN32844a` — die letzten beiden sind dieselbe Firmenbuchnummer in zwei
# Schreibweisen). Gemessen stieg die Zahl mehrfach vorkommender Namen von 134 auf 868.
#
# Das ist kein Schoenheitsfehler: wer im Onboarding seinen Firmennamen tippt, bekaeme
# vierzehn Treffer und muesste raten, welcher SEIN Zuschlags-Verlauf ist.
#
# ⚠ Zusammengelegt wird nur bei ZWEI Belegen: gleicher Name UND mindestens ein
# gemeinsames CPV-4-Feld. Der Namensvergleich allein waere die Falle aus
# `docs/laender/08-entitaeten-und-locale.md` — 22 Kaeufernamen kommen in mehr als einem
# Land vor. Gemessen an allen 868 Faellen: JEDER hatte ueberlappende Felder, kein
# einziger sah nach fremden Firmen aus. Bleibt die Ueberlappung eines Tages aus, bleiben
# die Eintraege getrennt — die Bedingung steht deshalb im Code und nicht im Kommentar.
def _zusammenlegen(eintraege: list[dict]) -> list[dict]:
    from collections import defaultdict
    nach_name: dict[str, list[dict]] = defaultdict(list)
    for e in eintraege:
        nach_name[(e.get("name") or "").strip().lower()].append(e)

    def felder4(e):
        return {str(f.get("cpv") or f.get("code") or "")[:4]
                for f in (e.get("fields") or []) if f}

    aus, verschmolzen = [], 0
    for gruppe in nach_name.values():
        if len(gruppe) == 1:
            aus.append(gruppe[0])
            continue
        # Reichster Eintrag fuehrt (meiste Zuschlaege) — er traegt den vollstaendigsten
        # Verlauf, und die uebrigen steuern nur bei, was ihm fehlt.
        gruppe.sort(key=lambda e: -(e.get("wins") or 0))
        kopf, rest = gruppe[0], []
        for e in gruppe[1:]:
            if felder4(kopf) & felder4(e):
                rest.append(e)
            else:
                aus.append(e)          # kein gemeinsames Feld → getrennt lassen
        if not rest:
            aus.append(kopf)
            continue
        verschmolzen += len(rest)
        z = dict(kopf)
        z["wins"] = sum((e.get("wins") or 0) for e in gruppe[:1] + rest)
        z["buyers"] = sum((e.get("buyers") or 0) for e in gruppe[:1] + rest) or None
        seit = [e.get("seit") for e in gruppe[:1] + rest if e.get("seit")]
        z["seit"] = min(seit) if seit else None
        # Kennungen der Geschwister als Alias behalten: die Suche findet die Firma dann
        # auch ueber eine Schreibweise, die nur eine der Quellen fuehrt.
        z["aliases"] = list(dict.fromkeys(
            (kopf.get("aliases") or []) + [a for e in rest for a in (e.get("aliases") or [])]
        ))[:8]
        for feld in ("fields", "fields6", "topBuyers", "members", "mailHashes"):
            gesehen, zus = set(), []
            for e in gruppe[:1] + rest:
                for x in (e.get(feld) or []):
                    k = json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x)
                    if k not in gesehen:
                        gesehen.add(k); zus.append(x)
            z[feld] = zus[:12] if feld.startswith("fields") else zus
        # Eine belegte Domain schlaegt eine fehlende, egal aus welchem Geschwister.
        if not z.get("domain"):
            for e in rest:
                if e.get("domain"):
                    z["domain"] = e["domain"]; z["domainQuelle"] = e.get("domainQuelle"); break
        aus.append(z)
    print(f"  Grenzgaenger zusammengelegt: {verschmolzen:,} Eintraege in {len(eintraege):,} → {len(aus):,}")
    return aus


out = _zusammenlegen(out)

(OUT / "suppliers.json").write_text(json.dumps(out, ensure_ascii=False, sort_keys=True))
print(f"{len(out)} Lieferanten → {OUT}/suppliers.json")

# ── AUFGETEILT: was die Suche braucht, und was nur eine einzelne Firma braucht ────────────
#
# Gemessen am 2026-08-25 an 37.901 Firmen: fuenf Felder tragen 91 % der Bytes —
# `fields` 25 %, `members` 20 %, `topBuyers` 17 %, `fields6` 16 %, `mailHashes` 14 %.
# KEINE Route braucht mehr als eines davon, und vier Routen brauchen ueberhaupt nur EINE
# Firma (`.find(x => x.id === id)`). `entity-search` sucht ueber Name und Aliasse und
# reichert danach nur die SECHS besten Treffer an.
#
# Deshalb zweierlei: eine schlanke Datei fuer die Suche und den Domain-Index, und eine
# Datei je Firma fuer alles Uebrige.
JE_FIRMA = OUT / "suppliers"
JE_FIRMA.mkdir(parents=True, exist_ok=True)


def suppliers_dateiname(schluessel: str) -> str:
    """Firmen-ID → Dateiname. IDENTISCH zu `export_firma_profiles.dateiname` und
    `web/lib/suppliers.ts::supplierDateiname`. Hash, weil die uebliche Saeuberung
    `[^A-Za-z0-9_-]` → "" bei diesen Kennungen kollidiert (dort gemessen: drei Paare)."""
    return hashlib.sha1(schluessel.encode("utf-8")).hexdigest()


# Was die Suche und der Domain-Index brauchen — und sonst nichts. `wins` ist dabei, weil
# die Trefferliste danach sortiert; `domain`/`domainBelege`, weil `domainEigentuemer` den
# Rueckwaerts-Index ueber ALLE Firmen bildet.
_BASIS = ("id", "name", "aliases", "wins", "domain", "domainBelege")

_vorher = {q.name for q in JE_FIRMA.glob("*.json")}
_neu = _gleich = 0
for _s in out:
    _name = suppliers_dateiname(str(_s.get("id")))
    _ziel = JE_FIRMA / f"{_name}.json"
    _text = json.dumps(_s, ensure_ascii=False, sort_keys=True)
    if _ziel.exists() and _ziel.read_text(encoding="utf-8") == _text:
        _gleich += 1
    else:
        _ziel.write_text(_text, encoding="utf-8")
        _neu += 1
    _vorher.discard(f"{_name}.json")
for _tot in _vorher:
    (JE_FIRMA / _tot).unlink(missing_ok=True)

_basis = [{k: _s[k] for k in _BASIS if k in _s} for _s in out]
(OUT / "suppliers-basis.json").write_text(
    json.dumps(_basis, ensure_ascii=False, separators=(",", ":")))
print(f"  je Firma: {_neu:,} geschrieben, {_gleich:,} unveraendert, {len(_vorher):,} entfernt "
      f"→ web/data/suppliers/ · Basis "
      f"{(OUT / 'suppliers-basis.json').stat().st_size / 1048576:.1f} MB "
      f"statt {(OUT / 'suppliers.json').stat().st_size / 1048576:.0f} MB")
cancom = next((s for s in out if "cancom" in s["name"].lower()), None)
if cancom:
    print(f"\nBeispiel CANCOM: {cancom['name']} · {cancom['wins']} Zuschläge")
    print("  Felder:", ", ".join(f"{f['cpv4']} {f['label'][:24] if f['label'] else ''}" for f in cancom["fields"][:4]))
    print("  Regionen:", cancom["regions"], "· Volumen-Median:", cancom["volMedian"])

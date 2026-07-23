"""Kritischer DB-Härtungs-Audit: sucht Lücken/Schwächen, misst statt annimmt."""
import duckdb
c=duckdb.connect()
S="data/silver/DE"; G="data/gold/DE"
def sg(t): return f"'{S}/{t}/*/*.parquet'"
def gg(t): return f"'{G}/{t}.parquet'"
N,NP,L,A,RQ_="".join,"","","",""
N=sg("notices"); NP=sg("notice_parties"); L=sg("lots"); A=sg("awards")
NC=sg("notice_cpv"); LC=sg("lot_cpv"); AC=sg("award_criteria"); REQ=sg("requirements"); ATT=sg("attributes")
PE=gg("party_entity"); EN=gg("entities"); Q=gg("quality"); LD=gg("leads"); DD=gg("dim_deflator")
def one(q):
    return c.execute(q).fetchone()
def rows(q):
    return c.execute(q).fetchall()
def sec(t): print("\n"+"="*72+"\n"+t+"\n"+"="*72)

sec("1) TABELLEN-GRÖSSEN")
for t in ["notices","notice_parties","lots","awards","notice_cpv","lot_cpv","award_criteria","requirements","attributes"]:
    print(f"  silver.{t:<16}: {one(f'SELECT count(*) FROM {sg(t)}')[0]:,}")
for t in ["procedures","entities","party_entity","quality","review_queue","contract_chains","leads","dim_cpv","dim_deflator"]:
    try: print(f"  gold.{t:<18}: {one(f'SELECT count(*) FROM {gg(t)}')[0]:,}")
    except Exception as e: print(f"  gold.{t}: FEHLT ({e})")

sec("2) REFERENZINTEGRITÄT (Waisen)")
print("  party_entity.entity_id ohne entities-Zeile:",
      one(f"SELECT count(*) FROM {PE} pe LEFT JOIN {EN} e USING(entity_id) WHERE e.entity_id IS NULL")[0])
print("  awards.notice_id ohne notices-Zeile:",
      one(f"SELECT count(*) FROM {A} a LEFT JOIN {N} n USING(notice_id) WHERE n.notice_id IS NULL")[0])
print("  notice_parties.notice_id ohne notices-Zeile:",
      one(f"SELECT count(*) FROM {NP} p LEFT JOIN {N} n USING(notice_id) WHERE n.notice_id IS NULL")[0])
print("  leads.lead_id ohne quality-Zeile:",
      one(f"SELECT count(*) FROM {LD} l LEFT JOIN {Q} q ON q.notice_id=l.lead_id WHERE q.notice_id IS NULL")[0])
print("  CANs ohne irgendeinen winner in notice_parties:",
      one(f"SELECT count(*) FROM {N} n WHERE notice_kind='can' AND NOT EXISTS (SELECT 1 FROM {NP} p WHERE p.notice_id=n.notice_id AND p.role='winner')")[0])

sec("3) WÄHRUNG (EUR-Annahme prüfen!)")
for cur,n2,s in rows(f"SELECT coalesce(value_currency,'(null)'), count(*), round(sum(final_value)) FROM {N} WHERE final_value IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10"):
    print(f"  {cur:<8}: {n2:>7,} Vergaben")
print("  → Nicht-EUR in leads.value_clean (Bänder/Median verfälscht?):",
      one(f"SELECT count(*) FROM {LD} l JOIN {N} n ON n.notice_id=l.lead_id WHERE l.value_clean IS NOT NULL AND n.value_currency<>'EUR'")[0])

sec("4) WERT-PLAUSIBILITÄT")
print("  final_value < 0:", one(f"SELECT count(*) FROM {N} WHERE final_value<0")[0])
print("  final_value == 0:", one(f"SELECT count(*) FROM {N} WHERE final_value=0")[0])
print("  final_value 100..1000 (evtl. Cent/Platzhalter):", one(f"SELECT count(*) FROM {N} WHERE final_value BETWEEN 100 AND 1000")[0])
print("  final_value > 1e9 (über quality-Cap, absurd):", one(f"SELECT count(*) FROM {N} WHERE final_value>1e9")[0])
print("  estimated_value < 0:", one(f"SELECT count(*) FROM {N} WHERE estimated_value<0")[0])

sec("5) DATUMS-PLAUSIBILITÄT")
print("  award_date < publication_date:", one(f"SELECT count(*) FROM {N} WHERE award_date IS NOT NULL AND publication_date IS NOT NULL AND award_date<publication_date")[0])
print("  award_date in Zukunft (>heute):", one(f"SELECT count(*) FROM {N} WHERE award_date>DATE '2026-07-18'")[0])
print("  publication_date < 2004 oder > heute:", one(f"SELECT count(*) FROM {N} WHERE publication_date<DATE '2004-01-01' OR publication_date>DATE '2026-07-18'")[0])
print("  lots.duration_months <= 0:", one(f"SELECT count(*) FROM {L} WHERE duration_months IS NOT NULL AND duration_months<=0")[0])
print("  submission_deadline nach award_date:", one(f"SELECT count(*) FROM {N} WHERE submission_deadline IS NOT NULL AND award_date IS NOT NULL AND submission_deadline>award_date")[0])
print("  start_date nach end_date:", one(f"SELECT count(*) FROM {N} WHERE start_date IS NOT NULL AND end_date IS NOT NULL AND start_date>end_date")[0])

sec("6) CPV-VALIDITÄT")
print("  notices.cpv_main null:", one(f"SELECT count(*) FROM {N} WHERE cpv_main IS NULL")[0])
print("  cpv_main nicht 8-stellig-numerisch:", one(f"SELECT count(*) FROM {N} WHERE cpv_main IS NOT NULL AND NOT regexp_matches(cpv_main,'^[0-9]{{8}}$')")[0])
print("  Division ohne dim_cpv-Eintrag (branche NULL in leads):", one(f"SELECT count(*) FROM {LD} WHERE branche IS NULL")[0])

sec("7) BIETER-PLAUSIBILITÄT")
print("  num_tenders < 0:", one(f"SELECT count(*) FROM {A} WHERE num_tenders<0")[0])
print("  num_tenders > 500 (absurd):", one(f"SELECT count(*) FROM {A} WHERE num_tenders>500")[0])
print("  num_tenders_sme > num_tenders:", one(f"SELECT count(*) FROM {A} WHERE num_tenders_sme>num_tenders")[0])

sec("8) ENTITY-RESOLUTION-QUALITÄT")
for m,n2,frac in rows(f"SELECT method, count(*), round(100.0*count(*)/sum(count(*)) OVER(),1) FROM {EN} GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  {m:<26}: {n2:>7,}  ({frac}%)")
print("  Ø confidence (Verknüpfungen, gewichtet):",
      one(f"SELECT round(avg(e.confidence),3) FROM {PE} pe JOIN {EN} e USING(entity_id)")[0])
print("  --- größte Entitäten nach #Verknüpfungen (Über-Merging?) ---")
for eid,nm,cnt,meth in rows(f"SELECT pe.entity_id, e.canonical_name, count(*) n, e.method FROM {PE} pe JOIN {EN} e USING(entity_id) GROUP BY 1,2,4 ORDER BY n DESC LIMIT 8"):
    print(f"    {cnt:>6}  {str(nm)[:34]:<35} [{meth}]")

sec("9) DUPLIKATE")
print("  doppelte notice_id in notices:", one(f"SELECT count(*)-count(DISTINCT notice_id) FROM {N}")[0])
print("  doppelte (notice_id,lot_id) in awards:", one(f"SELECT count(*)-count(DISTINCT (notice_id||'|'||coalesce(lot_id,''))) FROM {A}")[0])
print("  leads: gleiche (buyer,incumbent,contract_end,cpv_class) mehrfach:",
      one(f"SELECT count(*)-count(DISTINCT (buyer_entity||'|'||coalesce(incumbent_entity,'')||'|'||contract_end||'|'||coalesce(cpv_class,''))) FROM {LD}")[0])

sec("10) ABDECKUNG JE JAHR (Wert / national_id / Beschreibung)")
print("  Jahr | CANs | Wert% | Beschr% ")
for y,cans,vpct,dpct in rows(f"""
  SELECT year, count(*) FILTER (WHERE notice_kind='can') cans,
    round(100.0*count(*) FILTER (WHERE notice_kind='can' AND final_value IS NOT NULL)/nullif(count(*) FILTER (WHERE notice_kind='can'),0)) vpct,
    round(100.0*count(*) FILTER (WHERE description IS NOT NULL AND description<>'')/count(*)) dpct
  FROM {N} GROUP BY 1 ORDER BY 1"""):
    print(f"  {y} | {cans:>7,} | {vpct}% | {dpct}%")

sec("11) DEFLATOR-ABDECKUNG")
print("  leads mit Wert aber value_real_2020 NULL (Jahr außerhalb Deflator):",
      one(f"SELECT count(*) FROM {LD} WHERE value_clean IS NOT NULL AND value_real_2020 IS NULL")[0])
print("  Deflator-Jahre:", one(f"SELECT min(year), max(year) FROM {DD}"))

sec("12) VERLUSTFREIHEIT (attributes-Invariante)")
print("  attributes-Zeilen:", one(f"SELECT count(*) FROM {ATT}")[0], "| distinct notices darin:", one(f"SELECT count(DISTINCT notice_id) FROM {ATT}")[0])
print("  notices ohne attributes-Zeile:", one(f"SELECT count(*) FROM {N} n WHERE NOT EXISTS(SELECT 1 FROM {ATT} a WHERE a.notice_id=n.notice_id)")[0])

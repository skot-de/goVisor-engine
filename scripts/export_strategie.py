"""Strategie-Aggregate (Ticket #10) → web/data/strategie.json

Baut die vorberechneten Aggregate für den Strategie-Bereich. Bewusst getrennt vom
Lead-Export: die Lead-Liste ist auf 18 Monate gedeckelt (Handlungsrelevanz), die
Pipeline braucht 36 Monate (unternehmerische Planung).

Provenance-Regeln (Ticket §3):
- Volumen wird NIE zu einer Gesamtsumme addiert — drei getrennte Klassen
  (echt / geschätzt / unbekannt-Anzahl), gestapelt dargestellt.
- Quartale ohne Datenlage bleiben leer, werden nicht interpoliert.
- Fallzahl-Schwellen (§3.1) gelten für jeden Quoten-KPI.
"""
import duckdb, json, pathlib

OUT = pathlib.Path("web/data"); OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(); con.execute("SET threads=4")

# ── TEMP-TABELLEN JE LAND ────────────────────────────────────────────────────────────
# Die Auswertungen stehen auf ~20 TEMP-Tabellen, die frueher beim Import EINMAL gebaut
# wurden — fest gegen DE. Sie muessen je Land neu entstehen, stehen aber im Quelltext
# verstreut zwischen den Funktionen, zu denen sie gehoeren. Statt die Datei umzubauen,
# sammelt `VORLAUF` sie in Reihenfolge ein; der f-String im Lambda wird erst beim Aufruf
# ausgewertet und sieht dann die Quellen des aktuellen Landes.
VORLAUF: list = []
# ── QUELLEN JE LAND ──────────────────────────────────────────────────────────────────
#
# Bis 2026-08-23 stand hier fest `data/gold/DE`, und zwar an SECHZEHN Stellen. Die
# Strategie-Ansicht war damit vollstaendig deutsch: ein oesterreichischer Bieter sah
# deutsche Vergabestellen, deutsche Wettbewerbsdichte, deutsche Felder — ausgegeben als
# seine. Nichts daran war als Landesangabe erkennbar.
#
# WARUM NICHT EINFACH ALLES ZUSAMMEN. Ein `union_by_name` ueber DE+AT+CH waere schneller
# gebaut und falsch: „Wer vergibt in meinem Feld?" und „wie dicht ist der Wettbewerb?"
# sind Fragen an EINEN Markt. Eine DACH-Summe beantwortet keine davon und verdeckt beide.
# Deshalb wird je Land ein eigener Satz Aggregate gerechnet; die Datei ist nach Land
# verschluesselt und `/api/strategie?land=…` reicht genau einen davon heraus — die Form,
# die das Frontend kennt, bleibt unveraendert.
#
# Die Quellen sind bewusst MODULWEIT und werden je Land neu gesetzt: die Auswertungs-
# funktionen bauen ihr SQL aus diesen Namen, und sie alle auf einen Parameter umzustellen
# waere ein Umbau von 700 Zeilen fuer denselben Effekt.
# ⚠ LU steht hier, obwohl es noch kein Gold hat: die Ausgabe ueberspringt Laender ohne
# Tabellen von selbst, und ein fehlender Eintrag waere spaeter die stillere Luecke.
LAENDER = ["DE", "AT", "CH", "LU"]


def quellen_setzen(land: str) -> None:
    """Alle Tabellen-Ausdruecke auf ein Land umstellen."""
    global G, E, DC, ATTR, PE, EN, N, AW, AC, CS, CA, CL, LL, BN, LR
    G = f"data/gold/{land}"
    S = f"data/silver/{land}"
    E = f"read_parquet('{G}/lead_export.parquet')"
    DC = f"read_parquet('{G}/dim_cpv.parquet')"
    ATTR = _glob_oder_leer(f"{S}/attributes", "notice_id VARCHAR, path VARCHAR, value VARCHAR")
    PE = f"read_parquet('{G}/party_entity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    N = _glob_oder_leer(f"{S}/notices", "notice_id VARCHAR, title VARCHAR")
    AW = _glob_oder_leer(f"{S}/awards", "notice_id VARCHAR")
    AC = _glob_oder_leer(f"{S}/award_criteria", "notice_id VARCHAR")
    CS = f"read_parquet('{G}/contract_succession.parquet')"
    CA = f"read_parquet('{G}/cpv_adjacency.parquet')"
    CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
    LL = f"read_parquet('{G}/lead_lot.parquet')"
    BN = f"read_parquet('{G}/buyer_stats.parquet')"
    LR = f"read_parquet('{G}/lead_requirement.parquet')"


def _glob_oder_leer(verzeichnis: str, spalten: str) -> str:
    """Silber-Glob, oder eine leere Tabelle mit denselben Spalten.

    Noetig, weil die Silber-Ebene nicht in jedem Land jede Tabelle fuehrt: CH hat keine
    `award_criteria` aus simap. Ein Glob ins Leere ist in DuckDB ein LAUFZEITFEHLER, kein
    leeres Ergebnis — die ganze Sektion waere ausgefallen statt leer zu bleiben.
    """
    if list(pathlib.Path(verzeichnis).glob("*/*.parquet")):
        return f"read_parquet('{verzeichnis}/*/*.parquet', hive_partitioning=1)"
    return f"(SELECT {', '.join('NULL::' + t.split(' ', 1)[1] + ' AS ' + t.split(' ', 1)[0] for t in spalten.split(', '))} WHERE false)"


G = E = DC = ATTR = PE = EN = N = AW = AC = CS = CA = CL = LL = BN = LR = ""

BRANCHE = """CASE b.branche
  WHEN 'IT' THEN 'it' WHEN 'Elektro' THEN 'it' WHEN 'Messtechnik' THEN 'it'
  WHEN 'Bau' THEN 'bau' WHEN 'Installation' THEN 'bau' WHEN 'Immobilien' THEN 'bau'
    WHEN 'Ingenieur/Architektur' THEN 'bau' WHEN 'Wartung' THEN 'bau'
  WHEN 'Medizin' THEN 'medizin' WHEN 'Gesundheit' THEN 'medizin'
  WHEN 'Sicherheit' THEN 'sicherheit'
  WHEN 'Energie' THEN 'energie' WHEN 'Versorgung' THEN 'energie' WHEN 'Wasser' THEN 'energie'
    WHEN 'Umwelt/Reinigung' THEN 'energie' WHEN 'Chemie' THEN 'energie' WHEN 'Rohstoffe' THEN 'energie'
  ELSE 'beratung' END"""

BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie"]

# Rahmenvereinbarungen OHNE erneuten Wettbewerb — Volumen, das zwar ausläuft,
# aber nur für Gelistete abrufbar ist (Ticket §5.1, letzte Kennzahl).
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE fa_wo_rc AS
      SELECT DISTINCT notice_id FROM {ATTR}
      WHERE path ILIKE '%ContractingSystemTypeCode' AND lower(value) = 'fa-wo-rc'""")
))

VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE basis AS
      SELECT e.lead_id, e.title, e.buyer_name, e.contract_end, e.value_eur,
             e.value_source, e.timing_source, e.buyer_nuts, e.market_nuts3,
             {BRANCHE} AS branche,
             (f.notice_id IS NOT NULL) AS rahmen_ohne_wb
      FROM {E} e
      LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
      LEFT JOIN fa_wo_rc f ON f.notice_id = e.lead_id
      WHERE e.phase = 'expiring' AND e.contract_end IS NOT NULL
        AND e.contract_end BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL 36 MONTH""")
))


def eur(v):
    if v is None:
        return None
    v = float(v)
    if v >= 1e9:
        return f"{v/1e9:.2f}".replace(".", ",") + " Mrd €"
    if v >= 1e6:
        return f"{v/1e6:.1f}".replace(".", ",") + " Mio €"
    return f"{int(round(v)):,}".replace(",", ".") + " €"


def pipeline(key):
    """Quartals-Aggregat mit striktem Herkunfts-Split — keine Gesamtsumme."""
    rows = con.execute(f"""
        SELECT strftime(date_trunc('quarter', contract_end), '%Y-%m-%d') AS q,
               count(*)                                               AS n_gesamt,
               sum(CASE WHEN value_source = 'actual'  THEN value_eur END) AS vol_echt,
               count(*) FILTER (WHERE value_source = 'actual')            AS n_echt,
               sum(CASE WHEN value_source = 'estimated' THEN value_eur END) AS vol_schaetz,
               count(*) FILTER (WHERE value_source = 'estimated')         AS n_schaetz,
               count(*) FILTER (WHERE value_eur IS NULL)                  AS n_unbekannt,
               count(*) FILTER (WHERE rahmen_ohne_wb)                     AS n_rahmen_ohne_wb,
               count(*) FILTER (WHERE timing_source <> 'actual')          AS n_ende_geschaetzt
        FROM basis WHERE branche = '{key}'
        GROUP BY 1 ORDER BY 1""").fetchall()
    return [{
        "q": q, "nGesamt": int(n), "volEcht": float(ve or 0), "nEcht": int(ne or 0),
        "volSchaetz": float(vs or 0), "nSchaetz": int(ns or 0), "nUnbekannt": int(nu or 0),
        "nRahmenOhneWb": int(nr or 0), "nEndeGeschaetzt": int(neg or 0),
    } for (q, n, ve, ne, vs, ns, nu, nr, neg) in rows]


def top_posten(key, limit=12):
    """Größte Einzelposten — Sprung in den Lead Explorer."""
    rows = con.execute(f"""
        SELECT lead_id, title, buyer_name, value_eur, value_source,
               strftime(contract_end, '%d.%m.%Y') AS ende, timing_source, rahmen_ohne_wb
        FROM basis WHERE branche = '{key}' AND value_eur IS NOT NULL
        ORDER BY value_eur DESC, lead_id LIMIT {limit}""").fetchall()
    return [{
        "id": lid, "titel": (t[:80] + "…") if t and len(t) > 80 else (t or ""),
        "buyer": bn or "", "wert": eur(v), "wertSrc": "echt" if vs == "actual" else "schaetz",
        "ende": ende, "endeSrc": "echt" if ts == "actual" else "schaetz", "rahmen": bool(rw),
    } for (lid, t, bn, v, vs, ende, ts, rw) in rows]


# ───────────────────────── Vergabestellen (Ticket §5.3 / §4.1) ─────────────────────────
# Jede Quote trägt ihre Fallzahl mit — die Schwellenregel (§3.1) entscheidet erst im UI
# über die Darstellung. So bleibt "gemessen aus 3 Fällen" von "aus 300" unterscheidbar.
# (Quelle wird in `quellen_setzen()` je Land gesetzt.)

print("\nBaue Vergabestellen-Aggregat …")

# Zuschläge mit BELEGTER Gewinner-Identität (Akzeptanzkriterium #8: confidence=none raus)
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE zusch AS
      SELECT n.notice_id, n.publication_date, substr(n.cpv_main,1,2) AS div,
             pb.entity_id AS buyer, pw.entity_id AS winner, ew.canonical_name AS winner_name
      FROM {N} n
      JOIN {PE} pb ON pb.notice_id = n.notice_id AND pb.role = 'buyer'
      JOIN {PE} pw ON pw.notice_id = n.notice_id AND pw.role = 'winner'
      JOIN {EN} ew ON ew.entity_id = pw.entity_id
      WHERE ew.method IN ('handelsregister_exakt','ted_nationalid')
        AND n.publication_date IS NOT NULL""")
))

VORLAUF.append(lambda: (
    con.execute("""CREATE OR REPLACE TEMP TABLE z36 AS
      SELECT * FROM zusch WHERE publication_date >= CURRENT_DATE - INTERVAL 36 MONTH""")
))

# Notice-Ebene, dedupliziert. OHNE das fächern Lose und Mehrfachgewinner jede Fallzahl
# auf (gemessen: DB Netz 44 Vergaben → n=13.295). Jede Quote zählt Vergaben, nicht Zeilen.
VORLAUF.append(lambda: (
    con.execute("""CREATE OR REPLACE TEMP TABLE v36 AS
      SELECT DISTINCT notice_id, buyer, div FROM z36""")
))

# Neuzugänge: Anbieter mit ERSTEM Zuschlag bei dieser Stelle im 36-Mon-Fenster.
# Braucht keine Nachfolge-Verkettung → belastbarster KPI (gemessen: 11.632 Stellen).
VORLAUF.append(lambda: (
    con.execute("""CREATE OR REPLACE TEMP TABLE neu AS
      WITH erst AS (SELECT buyer, winner, min(publication_date) ersten FROM zusch GROUP BY 1,2),
      hist AS (SELECT buyer, min(publication_date) AS erste_vergabe FROM zusch GROUP BY 1)
      SELECT e.buyer,
             count(*) FILTER (WHERE e.ersten >= CURRENT_DATE - INTERVAL 36 MONTH) AS neue_36m,
             count(*) AS anbieter_gesamt,
             -- Guard: taucht die STELLE selbst erst im Fenster auf, sind zwangsläufig alle
             -- Anbieter „neu" (gemessen: mehrere Stellen mit 100 %). Dann ist die Offenheit
             -- nicht messbar — lieber nichts zeigen als einen Artefakt-Wert.
             (h.erste_vergabe < CURRENT_DATE - INTERVAL 36 MONTH) AS hat_vorgeschichte
      FROM erst e JOIN hist h ON h.buyer = e.buyer
      GROUP BY 1, 4""")
))

# Wechselquote aus verifizierten Nachfolgen (schwächer, s. Spike) — mit Fallzahl
# Nur Paare, bei denen BEIDE Seiten genau EINEN belegten Gewinner haben. Bei Konsortien /
# Mehrfachgewinnern ist „gewechselt" nicht bestimmbar — die bleiben draußen statt geraten
# zu werden (dokumentierte Linie: ARGE-Fluktuation ehrlich „unbestimmbar").
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE wechsel AS
      WITH einzeln AS (
        SELECT notice_id, any_value(buyer) buyer, any_value(winner) winner
        FROM zusch GROUP BY notice_id HAVING count(DISTINCT winner) = 1)
      SELECT p.buyer,
             count(*) AS wechsel_n,
             count(*) FILTER (WHERE p.winner IS DISTINCT FROM s.winner) AS gewechselt
      FROM {CS} cs
      JOIN einzeln p ON p.notice_id = cs.predecessor
      JOIN einzeln s ON s.notice_id = cs.successor
      GROUP BY 1""")
))

# Bieterzahl + KMU-Anteil + Preisentscheidungen je Stelle
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE kpi AS
      WITH je_notice AS (
        SELECT notice_id, median(num_tenders) AS bieter
        FROM {AW} WHERE num_tenders > 0 GROUP BY 1)
      SELECT v.buyer, median(j.bieter) AS bieter_median, count(*) AS bieter_n
      FROM v36 v JOIN je_notice j ON j.notice_id = v.notice_id GROUP BY 1""")
))

VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE kmu AS
      WITH je_notice AS (
        SELECT notice_id,
               max(CASE WHEN lower(value) IN ('micro','small','medium','sme') THEN 1 ELSE 0 END) AS ist_kmu
        FROM {ATTR}
        WHERE path ILIKE '%CompanySizeCode' AND path NOT ILIKE '%listName' GROUP BY 1)
      SELECT v.buyer, sum(j.ist_kmu) AS kmu_treffer, count(*) AS kmu_n
      FROM v36 v JOIN je_notice j ON j.notice_id = v.notice_id GROUP BY 1""")
))

# „Preisentscheidung" = Vergabe, deren Zuschlagskriterien NUR Preis enthalten
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE preis AS
      WITH je_notice AS (
        SELECT notice_id, count(*) FILTER (WHERE kind <> 'price') AS nicht_preis
        FROM {AC} GROUP BY 1)
      SELECT v.buyer,
             count(*) FILTER (WHERE j.nicht_preis = 0) AS nur_preis,
             count(*) AS preis_n
      FROM v36 v JOIN je_notice j ON j.notice_id = v.notice_id GROUP BY 1""")
))

VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE vol AS
      SELECT pb.entity_id AS buyer,
             sum(e.value_eur) FILTER (WHERE e.value_source = 'actual') AS vol_echt_24m,
             count(*) FILTER (WHERE e.value_source = 'actual')         AS vol_n,
             count(*)                                                  AS vergaben_24m
      FROM {E} e JOIN {PE} pb ON pb.notice_id = e.lead_id AND pb.role = 'buyer'
      GROUP BY 1""")
))

# Konzentration + Top-Anbieter je Stelle
VORLAUF.append(lambda: (
    con.execute("""CREATE OR REPLACE TEMP TABLE topsupp AS
      WITH s AS (SELECT buyer, winner, any_value(winner_name) nm, count(*) n FROM z36 GROUP BY 1,2),
      r AS (SELECT *, row_number() OVER (PARTITION BY buyer ORDER BY n DESC, winner) rk,
                   sum(n) OVER (PARTITION BY buyer) ges FROM s)
      SELECT buyer, max(CASE WHEN rk=1 THEN n END)::DOUBLE / max(ges) AS top1_anteil,
             list({'n': nm, 'wins': n, 'pct': round(100.0*n/ges)} ORDER BY n DESC, nm)
               FILTER (WHERE rk <= 5) AS top
      FROM r GROUP BY 1""")
))


def _modalband(baender):
    """Häufigstes Wertband, bei Gleichstand das alphabetisch erste.

    `mode()` in SQL entscheidet Gleichstände beliebig — gemessen sprang das angezeigte
    Vergleichsband zwischen zwei Läufen derselben Daten von „250-500k" auf „500k-1,3M".
    Für eine Plausibilitätsangabe, die der Nutzer gegen den eigenen Wert hält, ist das
    nicht hinnehmbar: dieselbe Datenlage muss dieselbe Aussage ergeben.
    """
    from collections import Counter
    c = Counter(b for b in (baender or []) if b)
    if not c:
        return None
    hoechste = max(c.values())
    return sorted(b for b, n in c.items() if n == hoechste)[0]


def vergabestellen(key, limit=60):
    """Vergabestellen des Grundraums, nach Volumen. Jede Quote mit Fallzahl."""
    rows = con.execute(f"""
        WITH stellen AS (
          SELECT v.buyer,
                 count(*)                                            AS vergaben_36m,
                 count(*) FILTER (WHERE {BRANCHE} = '{key}')         AS vergaben_feld
          FROM v36 v
          LEFT JOIN {DC} b ON b.division = v.div
          GROUP BY 1
          HAVING count(*) FILTER (WHERE {BRANCHE} = '{key}') > 0)
        SELECT s.buyer, bs.buyer_name, s.vergaben_36m, s.vergaben_feld,
               v.vol_echt_24m, v.vol_n,
               k.bieter_median, k.bieter_n,
               m.kmu_treffer, m.kmu_n,
               p.nur_preis, p.preis_n,
               w.gewechselt, w.wechsel_n,
               nz.neue_36m, nz.anbieter_gesamt, nz.hat_vorgeschichte,
               t.top1_anteil, t.top
        FROM stellen s
        LEFT JOIN {BN} bs ON bs.buyer_entity_id = s.buyer
        LEFT JOIN vol v ON v.buyer = s.buyer
        LEFT JOIN kpi k ON k.buyer = s.buyer
        LEFT JOIN kmu m ON m.buyer = s.buyer
        LEFT JOIN preis p ON p.buyer = s.buyer
        LEFT JOIN wechsel w ON w.buyer = s.buyer
        LEFT JOIN neu nz ON nz.buyer = s.buyer
        LEFT JOIN topsupp t ON t.buyer = s.buyer
        WHERE bs.buyer_name IS NOT NULL
        -- nach Relevanz FÜR DAS FELD sortiert, nicht nach Gesamtgröße der Stelle
        ORDER BY s.vergaben_feld DESC, coalesce(v.vol_echt_24m, 0) DESC, s.buyer
        LIMIT {limit}""").fetchall()

    def quote(treffer, n):
        """Rohwerte + Fallzahl — die Schwellenregel (§3.1) wendet das UI an."""
        if not n:
            return None
        return {"pct": round(100.0 * (treffer or 0) / n), "n": int(n), "treffer": int(treffer or 0)}

    out = []
    for (buyer, name, verg36, vergfeld, vol, voln, bmed, bn, kmt, kmn, npr, prn,
         gew, wn, neue, anbg, hatvor, top1, top) in rows:
        out.append({
            "id": buyer, "name": name,
            "vergaben36": int(verg36 or 0),
            "vergabenFeld": int(vergfeld or 0),
            "vergabenJahr": round((verg36 or 0) / 3, 1),
            "volEcht": float(vol) if vol else None,
            "volN": int(voln or 0),
            "bieterMedian": round(float(bmed), 1) if bmed else None,
            "bieterN": int(bn or 0),
            "kmu": quote(kmt, kmn),
            "preis": quote(npr, prn),
            "wechsel": quote(gew, wn),
            "neuzugangJahr": round((neue or 0) / 3, 1) if (anbg and hatvor) else None,
            "neueAnbieter": int(neue or 0),
            "anbieterGesamt": int(anbg or 0),
            # Offenheit als ANTEIL — die absolute Zahl misst vor allem die Größe der Stelle
            # und ist zwischen Stellen nicht vergleichbar.
            "neuAnteil": quote(neue, anbg) if hatvor else None,
            "top1": round(100 * float(top1)) if top1 else None,
            "top": [dict(x) for x in (top or [])],
            "vorschau": [],   # C.4 — bald auslaufende eigene Verträge (unten befüllt)
        })

    # C.4 Vergabe-Vorschau: bald auslaufende eigene Verträge je Stelle (0–24 Mon.), aus lead_export.
    namen = [o["name"] for o in out if o.get("name")]
    if namen:
        con.execute("CREATE OR REPLACE TEMP TABLE _vn(n VARCHAR)")
        con.executemany("INSERT INTO _vn VALUES (?)", [(n,) for n in namen])
        vrows = con.execute(f"""
            SELECT buyer_name, title, months_to_expiry, contract_end FROM (
              SELECT buyer_name, title, months_to_expiry, contract_end,
                     -- `contract_end` als letzter Entscheider, sonst ist die Reihenfolge
                     -- bei gleichem Titel UND gleicher Restlaufzeit dem Zufall ueberlassen:
                     -- zwei aufeinanderfolgende Laeufe lieferten gemessen zwei vertauschte
                     -- Zeilen. Das ist inhaltlich egal und macht trotzdem jeden Vergleich
                     -- zweier Ausgaben unbrauchbar — und genau so ein Vergleich ist das
                     -- einzige Mittel, um bei einem Umbau zu belegen, dass sich nichts
                     -- verschoben hat.
                     row_number() OVER (PARTITION BY buyer_name
                                        ORDER BY months_to_expiry, title, contract_end) rn
              FROM {E}
              WHERE phase='expiring' AND buyer_name IN (SELECT n FROM _vn)
                AND months_to_expiry IS NOT NULL AND months_to_expiry BETWEEN 0 AND 24)
            WHERE rn <= 6
            ORDER BY buyer_name, months_to_expiry, title, contract_end""").fetchall()
        vmap = {}
        for bn, title, mte, cend in vrows:
            vmap.setdefault(bn, []).append({
                "titel": title, "monate": round(float(mte), 1) if mte is not None else None,
                "ende": str(cend) if cend else None})
        for o in out:
            o["vorschau"] = vmap.get(o["name"], [])
    return out


# ───────────────────────── Bindung (Ticket §5.7) ─────────────────────────
# „Gesperrt" darf NUR behauptet werden, wo die Gelisteten-Liste vorliegt. Sonst ist nur
# bekannt, dass es ein Rahmen ohne Wettbewerb ist — das wird als unbekannt ausgewiesen,
# nicht als gesperrt angenommen. (Gemessen: 82 % der laufenden Rahmen haben Gelistete.)
print("\nBaue Bindungs-Aggregat …")

VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE gelistet AS
      SELECT p.notice_id, list(DISTINCT en.canonical_name ORDER BY en.canonical_name) AS namen
      FROM {PE} p JOIN {EN} en USING(entity_id)
      WHERE p.role = 'winner' AND en.method IN ('handelsregister_exakt','ted_nationalid')
      GROUP BY 1""")
))

VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE bindung AS
      SELECT e.lead_id, e.title, e.buyer_name, e.contract_end, e.value_eur, e.value_source,
             e.timing_source, {BRANCHE} AS branche,
             g.namen AS gelistete,
             date_diff('day', CURRENT_DATE, e.contract_end) AS tage_bis_ende
      FROM {E} e
      JOIN fa_wo_rc f ON f.notice_id = e.lead_id
      LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
      LEFT JOIN gelistet g ON g.notice_id = e.lead_id
      WHERE e.contract_end >= CURRENT_DATE""")
))

# Vorlauf bis zum Einstiegsfenster: Median Bekanntmachung→Zuschlag ~87 Tage
# plus Positionierungsvorlauf. Vor diesem Datum muss man sich bewegt haben.
VORLAUF_TAGE = 87 + 90


def bindung_daten(key):
    r = con.execute(f"""
        SELECT count(*)                                                      AS rahmen,
               count(*) FILTER (WHERE gelistete IS NOT NULL)                 AS belegt_gesperrt,
               count(*) FILTER (WHERE gelistete IS NULL)                     AS gelistete_unbekannt,
               sum(value_eur) FILTER (WHERE value_source = 'actual'
                                        AND gelistete IS NOT NULL)           AS vol_gesperrt_echt,
               count(*) FILTER (WHERE value_source = 'actual'
                                  AND gelistete IS NOT NULL)                 AS vol_n
        FROM bindung WHERE branche = '{key}'""").fetchone()

    # Einstiegsfenster: wann muss man sich bewegen, damit man beim Auslaufen dabei ist?
    fenster = con.execute(f"""
        SELECT lead_id, title, buyer_name,
               strftime(contract_end, '%d.%m.%Y')                         AS ende,
               strftime(contract_end - INTERVAL {VORLAUF_TAGE} DAY, '%m/%Y') AS fenster,
               tage_bis_ende, value_eur, value_source, timing_source,
               len(gelistete)                                             AS n_gelistet,
               gelistete[1:3]                                             AS namen
        FROM bindung
        WHERE branche = '{key}' AND gelistete IS NOT NULL
          AND tage_bis_ende BETWEEN 0 AND 1095
        ORDER BY coalesce(value_eur, 0) DESC, tage_bis_ende ASC, lead_id
        LIMIT 15""").fetchall()

    return {
        "rahmen": int(r[0] or 0),
        "belegtGesperrt": int(r[1] or 0),
        "gelisteteUnbekannt": int(r[2] or 0),
        "volGesperrt": float(r[3]) if r[3] else None,
        "volN": int(r[4] or 0),
        "fenster": [{
            "id": lid, "titel": (t[:70] + "…") if t and len(t) > 70 else (t or ""),
            "buyer": bn or "", "ende": ende, "fenster": fen,
            "tage": int(tage or 0),
            "wert": eur(v) if v else None,
            "wertSrc": "echt" if vs == "actual" else "schaetz",
            "endeSrc": "echt" if ts == "actual" else "schaetz",
            "nGelistet": int(ng or 0), "gelistete": list(nm or []),
        } for (lid, t, bn, ende, fen, tage, v, vs, ts, ng, nm) in fenster],
    }


# ───────────────────────── Felder (Ticket §5.2) ─────────────────────────
# CPV-Bündel als Fachgebiete: wo ist Platz, wo ist es eng? Kaum entity-abhängig,
# deshalb laut Spike vor „Wettbewerb" gebaut.
print("\nBaue Felder-Aggregat …")
# (Quelle wird in `quellen_setzen()` je Land gesetzt.)

VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE feld_basis AS
      SELECT substr(n.cpv_main,1,4) AS cpv4, n.notice_id, n.publication_date,
             date_part('year', n.publication_date) AS jahr, {BRANCHE} AS branche
      FROM {N} n LEFT JOIN {DC} b ON b.division = substr(n.cpv_main,1,2)
      WHERE n.publication_date >= CURRENT_DATE - INTERVAL 36 MONTH
        AND n.cpv_main IS NOT NULL""")
))

# Kleinstes Los je Ausschreibung = Einstiegshürde (§5.2)
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE kleinstes_los AS
      SELECT lead_id, min(lot_value_eur) AS min_los
      FROM {LL} WHERE lot_value_eur > 0 GROUP BY 1""")
))

# Bürgschaftsquote je Feld = Kapitalhürde
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE buergschaft AS
      SELECT notice_id,
             max(CASE WHEN lower(value) NOT IN ('false','none') THEN 1 ELSE 0 END) AS hat_buerg
      FROM {ATTR}
      WHERE path ILIKE '%RequiredFinancialGuarantee.GuaranteeTypeCode' AND path NOT ILIKE '%listName'
      GROUP BY 1""")
))


def felder(key, limit=20):
    rows = con.execute(f"""
        WITH bieter AS (
          SELECT notice_id, median(num_tenders) b FROM {AW} WHERE num_tenders > 0 GROUP BY 1)
        SELECT f.cpv4, any_value(cl.label) AS label,
               count(*)                                                   AS vergaben_36m,
               -- ROLLIERENDE 12-Monats-Fenster, keine Kalenderjahre: das laufende Jahr ist
               -- ein Rumpfjahr und das älteste ebenso (Fenster beginnt mitten im Jahr) —
               -- ein Kalendervergleich zeigte dadurch überall künstliche −40 %.
               count(*) FILTER (WHERE f.publication_date >= CURRENT_DATE - INTERVAL 12 MONTH) AS j0,
               count(*) FILTER (WHERE f.publication_date >= CURRENT_DATE - INTERVAL 24 MONTH
                                  AND f.publication_date <  CURRENT_DATE - INTERVAL 12 MONTH) AS j1,
               count(*) FILTER (WHERE f.publication_date <  CURRENT_DATE - INTERVAL 24 MONTH) AS j2,
               median(bi.b)                                               AS bieter_median,
               count(bi.b)                                                AS bieter_n,
               median(kl.min_los)                                         AS kleinstes_los,
               count(kl.min_los)                                          AS los_n,
               sum(bg.hat_buerg)                                          AS buerg_treffer,
               count(bg.hat_buerg)                                        AS buerg_n,
               sum(e.value_eur) FILTER (WHERE e.value_source = 'actual')  AS vol_echt,
               count(*) FILTER (WHERE e.value_source = 'actual')          AS vol_n,
               -- #20 Wertplausibilität: Modalband der Vergleichsverfahren (nur echte Werte —
               -- „lieber Band als falscher Punkt", Schätzwerte fließen nicht ein).
               (list(e.value_band ORDER BY e.value_band)
                  FILTER (WHERE e.value_source = 'actual'))               AS _baender
        FROM feld_basis f
        LEFT JOIN bieter bi ON bi.notice_id = f.notice_id
        LEFT JOIN kleinstes_los kl ON kl.lead_id = f.notice_id
        LEFT JOIN buergschaft bg ON bg.notice_id = f.notice_id
        LEFT JOIN {E} e ON e.lead_id = f.notice_id
        LEFT JOIN {CL} cl ON cl.cpv_code = f.cpv4 || '0000'
        WHERE f.branche = '{key}'
        GROUP BY 1 ORDER BY 3 DESC, 1 LIMIT {limit}""").fetchall()

    def quote(t, n):
        return {"pct": round(100.0 * (t or 0) / n), "n": int(n), "treffer": int(t or 0)} if n else None

    out = []
    for (cpv4, label, verg, j0, j1, j2, bmed, bn, klos, losn, bgt, bgn, vol, voln, _baender) in rows:
        wband = _modalband(_baender)
        # Trend nur bei durchgehender Datenlage über alle drei Fenster (§5.2-Regel).
        # Vergleich: letzte 12 Mon gegen die 12 Mon davor.
        trend = round(100.0 * (j0 - j1) / j1) if (j0 and j1 and j2) else None
        out.append({
            "cpv4": cpv4, "label": label or cpv4,
            "vergaben36": int(verg), "vergabenJahr": round(verg / 3, 1),
            "trend": trend, "j0": int(j0), "j1": int(j1), "j2": int(j2),
            "bieterMedian": round(float(bmed), 1) if bmed else None, "bieterN": int(bn or 0),
            "kleinstesLos": float(klos) if klos else None, "losN": int(losn or 0),
            "buergschaft": quote(bgt, bgn),
            "volEcht": float(vol) if vol else None, "volN": int(voln or 0),
            "wertband": wband, "wertN": int(voln or 0),   # #20 (voln = Zahl echter Werte)
        })
    return out


# Fallzahl-Schwelle für die Nachbarfelder (§3.1 gilt für JEDEN Quoten-KPI — hier war sie
# vergessen). Ohne sie gewinnt die Reihung nach `cond_prob` das seltenste Paar: für Bau stand
# „Fernsprech- und Datenübertragungsdienste" mit **19 Firmen** ganz oben, für Energie
# „Straßenausrüstung" mit 16. Eine Quote auf so kleiner Basis ist keine Nähe, sondern Rauschen.
# Gemessen am 2026-08-22 über alle sechs Branchen: bei 25 bleibt jede Liste voll (8 Einträge),
# und oben stehen Felder mit 38 bis 232 geteilten Firmen. Bei 50 schrumpfen Medizin auf 5 und
# Sicherheit auf 3 — deshalb 25 und nicht mehr.
NACHBAR_MIN_FIRMEN = 25


def nachbarfelder(key, limit=8):
    """Felder, die dieselben Anbieter zusätzlich bedienen (§5.2, aus `Chancen` übernommen)."""
    rows = con.execute(f"""
        WITH meine AS (SELECT DISTINCT cpv4 FROM feld_basis WHERE branche = '{key}')
        SELECT a.cpv_b, any_value(cl.label) AS label,
               max(a.cond_prob) AS naehe, max(a.shared_firms) AS firmen
        FROM {CA} a
        JOIN meine m ON m.cpv4 = a.cpv_a
        LEFT JOIN {CL} cl ON cl.cpv_code = a.cpv_b || '0000'
        WHERE a.cpv_b NOT IN (SELECT cpv4 FROM meine)
        GROUP BY 1
        HAVING max(a.shared_firms) >= {NACHBAR_MIN_FIRMEN}
        ORDER BY 3 DESC, 1 LIMIT {limit}""").fetchall()
    return [{"cpv4": c, "label": l or c, "naehe": round(float(p) * 100),
             "firmen": int(f)} for (c, l, p, f) in rows]


def einstiegsfreundlich(key, limit=10):
    """Offene Ausschreibungen mit kleinem Volumen und historisch wenig Bietern (§5.2).

    Gemessen: offene Ausschreibungen veröffentlichen KEINE Los-Werte (0 von 12.123) —
    die stehen erst im Zuschlag. Also der Auftragswert der Ausschreibung selbst, und die
    Bieterzahl als historischer Median des Fachgebiets (bei laufenden Verfahren hat noch
    niemand geboten — dieser Hinweis gehört ins UI)."""
    rows = con.execute(f"""
        WITH feld_bieter AS (
          SELECT f.cpv4, median(bi.b) AS bieter
          FROM feld_basis f
          JOIN (SELECT notice_id, median(num_tenders) b FROM {AW} WHERE num_tenders > 0 GROUP BY 1) bi
            ON bi.notice_id = f.notice_id
          GROUP BY 1)
        SELECT e.lead_id, e.title, e.buyer_name, e.value_eur, e.value_source,
               strftime(e.deadline_date, '%d.%m.%Y') AS frist, fb.bieter
        FROM {E} e
        LEFT JOIN {DC} b ON b.division = substr(e.cpv_code,1,2)
        LEFT JOIN feld_bieter fb ON fb.cpv4 = substr(e.cpv_code,1,4)
        WHERE {BRANCHE} = '{key}' AND e.phase = 'open'
          AND e.value_eur > 0 AND e.days_to_deadline >= 0
        ORDER BY e.value_eur ASC, e.lead_id LIMIT {limit}""").fetchall()
    return [{"id": i, "titel": (t[:64] + "…") if t and len(t) > 64 else (t or ""),
             "buyer": bn or "", "wert": eur(v), "wertSrc": "echt" if vs == "actual" else "schaetz",
             "frist": fr, "bieterFeld": round(float(bi), 1) if bi else None}
            for (i, t, bn, v, vs, fr, bi) in rows]


# ───────────────────────── Wettbewerb (Ticket §5.4) ─────────────────────────
# Zwei Sichten auf dieselbe Kante (agg_buyer_supplier). Am stärksten entity-abhängig,
# deshalb laut Spike zuletzt gebaut — die Basis (65 % belegte Zuschläge) wird ausgewiesen.
print("\nBaue Wettbewerbs-Aggregat …")

# Die bipartite Kante Käufer×Anbieter, 36 Mon, auf belegten Zuschlägen (Notice-Ebene)
VORLAUF.append(lambda: (
    con.execute(f"""CREATE OR REPLACE TEMP TABLE bs AS
      WITH kante AS (SELECT DISTINCT notice_id, buyer, winner, div FROM z36)
      SELECT k.buyer, k.winner, k.div,
             count(DISTINCT k.notice_id)                                   AS wins,
             sum(e.value_eur) FILTER (WHERE e.value_source = 'actual')     AS vol
      FROM kante k LEFT JOIN {E} e ON e.lead_id = k.notice_id
      GROUP BY 1, 2, 3""")
))

# Käufer-Summen für Zuschlagsanteil vs. Marktdurchschnitt
VORLAUF.append(lambda: (
    con.execute("""CREATE OR REPLACE TEMP TABLE bt AS
      SELECT buyer, sum(wins) AS total, count(DISTINCT winner) AS n_supplier FROM bs GROUP BY 1""")
))

# Anbieter-Trend: letzte 12 Mon gegen die 12 davor (rollierend, wie bei Feldern)
VORLAUF.append(lambda: (
    con.execute("""CREATE OR REPLACE TEMP TABLE supp_trend AS
      WITH k AS (SELECT DISTINCT notice_id, winner, publication_date FROM z36)
      SELECT winner,
             count(*) FILTER (WHERE publication_date >= CURRENT_DATE - INTERVAL 12 MONTH) AS w0,
             count(*) FILTER (WHERE publication_date >= CURRENT_DATE - INTERVAL 24 MONTH
                                AND publication_date <  CURRENT_DATE - INTERVAL 12 MONTH) AS w1
      FROM k GROUP BY 1""")
))

# (`BN` wird in `quellen_setzen()` je Land gesetzt.)

# Namens-Lookup je Anbieter — EINE Zeile pro winner. Ihn per JOIN aus z36 zu ziehen
# hätte jede Aggregation über die Zuschlags-Zeilen des Anbieters aufgefächert.
VORLAUF.append(lambda: (
    con.execute("""CREATE OR REPLACE TEMP TABLE supp_name AS
      SELECT winner, any_value(winner_name) AS name FROM z36 GROUP BY 1""")
))


def wettbewerb(key):
    # Ebene 1 — Anbieter-Übersicht im Feld
    anbieter = con.execute(f"""
        SELECT bs.winner, sn.name,
               sum(bs.wins)                          AS wins,
               count(DISTINCT bs.buyer)              AS stellen,
               sum(bs.vol)                           AS vol,
               max(t.w0) AS w0, max(t.w1) AS w1
        FROM bs
        LEFT JOIN supp_name sn ON sn.winner = bs.winner
        LEFT JOIN {DC} b ON b.division = bs.div
        LEFT JOIN supp_trend t ON t.winner = bs.winner
        WHERE {BRANCHE} = '{key}'
        GROUP BY 1, 2 ORDER BY 3 DESC, 1, 2 LIMIT 40""").fetchall()

    supp = []
    for (wid, name, wins, stellen, vol, w0, w1) in anbieter:
        trend = round(100.0 * (w0 - w1) / w1) if (w0 and w1) else None
        supp.append({
            "id": wid, "name": name or wid, "wins": int(wins), "stellen": int(stellen or 0),
            "vol": float(vol) if vol else None, "trend": trend,
        })

    # Ebene 2 — je Anbieter die Top-Stellen mit Zuschlagsanteil vs. Marktdurchschnitt
    top_ids = [s["id"] for s in supp[:25]]
    profile = {}
    if top_ids:
        ph = ", ".join(f"'{i}'" for i in top_ids)
        rows = con.execute(f"""
            SELECT bs.winner, bn.buyer_name, bs.wins, bt.total, bt.n_supplier
            FROM bs
            JOIN bt ON bt.buyer = bs.buyer
            LEFT JOIN {BN} bn ON bn.buyer_entity_id = bs.buyer
            WHERE bs.winner IN ({ph}) AND bn.buyer_name IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY bs.winner ORDER BY bs.wins DESC, bs.buyer) <= 8
        """).fetchall()
        for (wid, bname, wins, total, nsupp) in rows:
            anteil = round(100.0 * wins / total) if total else 0
            markt = round(100.0 / nsupp) if nsupp else 0
            profile.setdefault(wid, []).append({
                "buyer": bname, "wins": int(wins), "anteil": anteil, "markt": markt,
                "ueber": anteil - markt,
            })
        for wid in profile:
            profile[wid].sort(key=lambda x: -x["ueber"])

    # Matrix — Top-12 Stellen (nach Feld-Vergaben) × Top-8 Anbieter, Zelle = Zuschlagsanteil
    stellen_ids = con.execute(f"""
        SELECT bs.buyer, any_value(bn.buyer_name) AS name, sum(bs.wins) AS w
        FROM bs LEFT JOIN {DC} b ON b.division = bs.div
        LEFT JOIN {BN} bn ON bn.buyer_entity_id = bs.buyer
        WHERE {BRANCHE} = '{key}' AND bn.buyer_name IS NOT NULL
        GROUP BY 1 ORDER BY 3 DESC, 1 LIMIT 12""").fetchall()
    m_supp = supp[:8]
    matrix = []
    if stellen_ids and m_supp:
        bset = {b[0]: b[1] for b in stellen_ids}
        sset = {s["id"]: s["name"] for s in m_supp}
        bph = ", ".join(f"'{i}'" for i in bset)
        sph = ", ".join(f"'{i}'" for i in sset)
        cells = con.execute(f"""
            SELECT bs.buyer, bs.winner, sum(bs.wins) w, max(bt.total) tot
            FROM bs JOIN bt ON bt.buyer = bs.buyer
            WHERE bs.buyer IN ({bph}) AND bs.winner IN ({sph})
            GROUP BY 1, 2""").fetchall()
        cmap = {(b, w): (round(100.0 * wn / tot) if tot else 0) for (b, w, wn, tot) in cells}
        matrix = {
            "buyers": [{"id": b[0], "name": b[1]} for b in stellen_ids],
            "supplier": [{"id": s["id"], "name": s["name"]} for s in m_supp],
            "cells": [[cmap.get((b[0], s["id"]), 0) for s in m_supp] for b in stellen_ids],
        }

    return {"anbieter": supp, "profile": profile, "matrix": matrix}


# ───────────────────────── Fähigkeiten (Ticket §5.6) ─────────────────────────
# Was blockiert uns? Eignungsanforderungen liegen überwiegend im Freitext (~37 % Abdeckung),
# deshalb ist JEDE Aussage eine Untergrenze: „Mindestens €X fordern Y", nie „€X fordern Y".
# (`LR` wird in `quellen_setzen()` je Land gesetzt.)

REGIME_LABEL = {
    "vgv": "VgV — Liefer-/Dienstleistung", "vob": "VOB/A — Bauleistung",
    "uvgo": "UVgO — unterschwellig", "sektvo": "SektVO — Sektoren (Verkehr/Wasser/Energie)",
    "konzvgv": "KonzVgV — Konzessionen", "vsvgv": "VSVgV — Verteidigung/Sicherheit",
    "eu_classic": "EU-Verfahren (klassisch)",
}


def faehigkeiten(key):
    n = con.execute(f"""
        SELECT count(*) FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code,1,2)
        WHERE {BRANCHE} = '{key}' AND e.phase IN ('expiring','open')""").fetchone()[0]

    regime = con.execute(f"""
        SELECT e.regulatory_regime, count(*) n,
               sum(e.value_eur) FILTER (WHERE e.value_source = 'actual') AS vol
        FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code,1,2)
        WHERE {BRANCHE} = '{key}' AND e.phase IN ('expiring','open')
          AND e.regulatory_regime IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 6""").fetchall()

    # Kapitalhürde: Bürgschaft (belastbar aus dem Attribut) — als Untergrenze
    buerg = con.execute(f"""
        SELECT count(*) FILTER (WHERE bg.hat_buerg = 1) AS treffer,
               sum(e.value_eur) FILTER (WHERE bg.hat_buerg = 1 AND e.value_source = 'actual') AS vol,
               count(bg.hat_buerg) AS n
        FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code,1,2)
        JOIN buergschaft bg ON bg.notice_id = e.lead_id
        WHERE {BRANCHE} = '{key}' AND e.phase IN ('expiring','open')""").fetchone()

    # Geforderte Nachweise (typisiert) — dünn, deshalb ausdrücklich als Untergrenze
    nachweise = con.execute(f"""
        SELECT r.requirement_code, count(DISTINCT r.lead_id) n
        FROM {LR} r JOIN {E} e ON e.lead_id = r.lead_id
        LEFT JOIN {DC} b ON b.division = substr(e.cpv_code,1,2)
        WHERE {BRANCHE} = '{key}'
          AND r.requirement_kind IN ('suitability','economic','technical')
        GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 8""").fetchall()

    return {
        "nLeads": int(n),
        "regime": [{"code": rc, "label": REGIME_LABEL.get(rc, rc), "n": int(cnt),
                    "vol": float(v) if v else None} for (rc, cnt, v) in regime],
        "buergschaft": {"treffer": int(buerg[0] or 0), "vol": float(buerg[1]) if buerg[1] else None,
                        "n": int(buerg[2] or 0)},
        "nachweise": [{"code": rc, "n": int(cnt)} for (rc, cnt) in nachweise],
    }


def branche_bauen(key):
    q = pipeline(key)
    ergebnis = {
        "quartale": q,
        "top": top_posten(key),
        "stellen": vergabestellen(key),
        "bindung": bindung_daten(key),
        "felder": felder(key),
        "nachbarn": nachbarfelder(key),
        "einstieg": einstiegsfreundlich(key),
        "wettbewerb": wettbewerb(key),
        "faehigkeiten": faehigkeiten(key),
        "summe": {
            "nGesamt": sum(x["nGesamt"] for x in q),
            "volEcht": sum(x["volEcht"] for x in q),
            "volSchaetz": sum(x["volSchaetz"] for x in q),
            "nUnbekannt": sum(x["nUnbekannt"] for x in q),
            "nRahmenOhneWb": sum(x["nRahmenOhneWb"] for x in q),
        },
    }
    z = ergebnis["summe"]
    print(f"  {key:11} {z['nGesamt']:>6} Verträge · echt {eur(z['volEcht']):>12} · "
          f"geschätzt {eur(z['volSchaetz']):>12} · ohne Wert {z['nUnbekannt']:>5} · "
          f"Rahmen o. Wettb. {z['nRahmenOhneWb']:>5}")
    return ergebnis


# ── EIN SATZ AGGREGATE JE LAND ───────────────────────────────────────────────────────
# Die Datei ist nach Land verschluesselt, `/api/strategie?land=…` reicht genau einen Satz
# heraus. Damit bleibt die Form, die das Frontend liest, exakt wie vorher — und die
# Nutzlast beim Client waechst nicht, obwohl die Datei es tut.
out: dict[str, dict] = {}
for land in LAENDER:
    if not pathlib.Path(f"data/gold/{land}/lead_export.parquet").exists():
        print(f"\n{land}: keine Gold-Ebene — uebersprungen.")
        continue
    print(f"\n══ {land} ══")
    quellen_setzen(land)
    for schritt in VORLAUF:
        schritt()
    out[land] = {}
    for key in BRANCHEN:
        try:
            out[land][key] = branche_bauen(key)
        except Exception as e:
            # EINE Branche darf den Lauf nicht kippen. Faellt sie aus, fehlt eine Sektion;
            # bricht das Skript ab, steht die GANZE Strategie-Ansicht auf altem Stand —
            # und zwar unbemerkt, weil eine alte Datei wie eine frische aussieht.
            print(f"  ⚠ {land}/{key} fehlgeschlagen: {str(e)[:110]}")

(OUT / "strategie.json").write_text(json.dumps(out, ensure_ascii=False, sort_keys=True))
groesse = (OUT / "strategie.json").stat().st_size
print(f"\n→ {OUT}/strategie.json ({groesse/1024:.0f} KB, Länder: {', '.join(sorted(out))})")

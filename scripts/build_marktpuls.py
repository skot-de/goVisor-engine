"""Marktpuls — Saisonalität + aktuelle Marktlage als vorberechnetes JSON.

Ein in sich geschlossenes Anzeige-Element (Briefing `INPUT/v1 Features/add/
govisor-briefing-marktpuls.md`). Zwei Teile, beide ausschliesslich aus dem
vorhandenen Silber-/Gold-Bestand (keine neue Quelle):

1. **Saisonalität** — Ø neu veröffentlichte Ausschreibungen je Kalendermonat über die
   letzten 5 *vollen* Jahre, plus Abweichung vom Jahresmittel.
2. **Aktuelle Lage** — laufende Verfahren (Frist in der Zukunft), Zuschläge und
   Aufhebungen der letzten 30 Tage, aufgeschlüsselt nach Branche.

Ausgabe: ``web/data/marktpuls.json`` (aggregiert, keine Einzelverfahren, < 50 KB).

--------------------------------------------------------------------------------
Die vier Entscheidungen, die hier drinstecken — alle an echten Daten gemessen:

**(1) Zähleinheit ist das Verfahren, nicht die Bekanntmachung.**
Im Bestand bildet sich ein Verfahren auf drei verschiedene Arten ab, je nach
Schema-Generation:
  * `legacy` (TED_EXPORT, bis 2023): Korrekturen sind ein eigener Notice-Typ
    (`notice_kind='corrigendum'`, F20_2014) — fallen also schon durch den Typfilter.
    Die Klammer über CN/CAN/Korrektur ist der Rückverweis `ref_publication_number`.
  * `eforms` (ab 2023): **eine Korrektur ist erneut ein `ContractNotice`** und trägt
    `notice_kind='cn'`. Gemessen DE 2025: 17.552 von 87.862 eForms-CN (20 %) sind
    Änderungsbekanntmachungen. Wer sie mitzählt, überzeichnet den Markt um ein Fünftel.
    Erkennungsmerkmal ist das Attribut `…EformsExtension.Changes.ChangedNoticeIdentifier`
    (bzw. `…Change.ChangedNoticeIdentifier`). `ref_publication_number` ist hier praktisch
    leer (DE 2025: 0 Zeilen) — die Rückverweis-Klammer trägt ab eForms also NICHT mehr.
    Dafür trägt `ContractFolderID` (BT-04 Verfahrenskennung) zu 100 % der eForms-CN.
  * nationale Quellen (`doe`, `simap`, `atverg`): weder Rückverweis noch verlässliche
    Verfahrenskennung (DÖE: `ContractFolderID` nur zu 9 %) — dort ist die Notice das
    Verfahren.
Daraus der Verfahrensschlüssel als Wasserfall: ContractFolderID → Wurzel der
Rückverweis-Kette → publication_number. Gruppiert wird über ihn, gezählt wird die
*früheste* qualifizierende Veröffentlichung der Gruppe.

**(2) Quellen-Onset ist ein Ingest-Artefakt, kein Marktsignal** (Briefing §6 sinngemäss).
Gemessen: DÖE liefert erst ab 2023 (+125k Notices/Jahr in DE), simap.ch erst ab 2024
(+14k/Jahr in CH). Eine 5-Jahres-Kurve über alle Quellen zeigte einen Sprung, der die
Aufnahme einer Quelle abbildet, nicht den Markt. Für die **Zeitreihe** wird deshalb je
Land nur die Quellenfamilie verwendet, die über das *ganze* Fenster durchgehend liefert
(faktisch überall TED). Welche Quellen ausgeschlossen wurden, steht im JSON
(`coverage.<land>.quellen_ausgeschlossen`) und gehört in die Anzeige.
Für den **Stichtags**-Teil (aktuelle Lage) gilt das nicht — dort zählt alles, was da ist,
mit Quellen-Dedup (AT: `atverg_dedup`, CH: `ted_dedup`).

**(3) Länder-parametrisiert, nicht DE-verdrahtet.** `--laender DE,AT,CH` (Default: was
unter `data/silver/` liegt). Je Land wird die Abdeckung ausgewiesen; wo das Fenster nicht
vollständig belegt ist oder die Fallzahl unter `MIN_FAELLE` liegt, steht das als
`belastbar: false` im JSON, statt still mitgemittelt zu werden.

**(4) Herkunft ausweisen.** Die laufenden Verfahren stützen sich auf die **echte**
`submission_deadline` aus der Bekanntmachung (`frist_basis: "echt"`). Verfahren ohne
veröffentlichte Frist werden separat als `ohne_frist` gezählt, nie stillschweigend
über eine geschätzte Frist in die Kennzahl gerechnet (die Schätzung aus
`gold/*/lead_deadline.parquet` existiert nur für DE vollständig — sie hier zu benutzen
hiesse, DE und CH/AT mit verschiedenen Massstäben zu messen).

--------------------------------------------------------------------------------
Aufruf::

    python3 scripts/build_marktpuls.py [--laender DE,AT,CH] [--jahre 5]
                                       [--out web/data/marktpuls.json] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
SILVER = ROOT / "data" / "silver"
GOLD = ROOT / "data" / "gold"

# --- Fachliche Konstanten -------------------------------------------------------
FENSTER_JAHRE = 5           # Briefing §3.1: letzte 5 vollständige Jahre
MIN_FAELLE = 200            # Briefing §3.4: Mindestfallzahl je Land×Branche-Kombination
LAGE_TAGE = 30              # Briefing §4.1: Zuschläge/Aufhebungen der letzten 30 Tage
AUSREISSER_PCT = 25.0       # Briefing §7: ab welcher Abweichung ein Befund benannt wird
GESAMT = "gesamt"           # Schlüssel des Länder-Aggregats
ALLE = "alle"               # Schlüssel des Branchen-Aggregats

# Die Bekanntmachungsarten, die ein *bietbares* Verfahren eröffnen. `pin` nur mit Frist
# (Briefing §2.1: „Vorinformationen ohne Frist zählen nicht als Ausschreibung").
TENDER_KINDS = ("cn", "pin")

# Quellenfamilie je schema_gen. Alle TED-Schema-Generationen sind EINE Quelle (der
# Formatwechsel legacy→eforms ist kein Quellenwechsel); die nationalen Portale sind eigene.
QUELLE = {
    "legacy": "ted", "eforms": "ted", "text": "ted", "ojs": "ted",
    "doe": "doe", "simap": "simap", "atverg": "atverg",
}

# Branche identisch zu scripts/export_web_leads.py (dim_cpv.branche → ui_branche) —
# Briefing §9-4: die Zahlen müssen zur Lead-Liste passen.
BRANCHE_SQL = """CASE b.branche
  WHEN 'IT' THEN 'it' WHEN 'Elektro' THEN 'it' WHEN 'Messtechnik' THEN 'it'
  WHEN 'Bau' THEN 'bau' WHEN 'Installation' THEN 'bau' WHEN 'Immobilien' THEN 'bau'
    WHEN 'Ingenieur/Architektur' THEN 'bau' WHEN 'Wartung' THEN 'bau'
  WHEN 'Medizin' THEN 'medizin' WHEN 'Gesundheit' THEN 'medizin'
  WHEN 'Sicherheit' THEN 'sicherheit'
  WHEN 'Energie' THEN 'energie' WHEN 'Versorgung' THEN 'energie' WHEN 'Wasser' THEN 'energie'
    WHEN 'Umwelt/Reinigung' THEN 'energie' WHEN 'Chemie' THEN 'energie' WHEN 'Rohstoffe' THEN 'energie'
  ELSE 'beratung' END"""
BRANCHEN = ("bau", "it", "beratung", "medizin", "sicherheit", "energie")


# --- Hilfsfunktionen ------------------------------------------------------------
def _glob(country: str, table: str) -> str:
    return str(SILVER / country / table / "**" / "*.parquet")


def _hat_tabelle(country: str, table: str) -> bool:
    d = SILVER / country / table
    return d.is_dir() and any(d.rglob("*.parquet"))


def verfuegbare_laender() -> list[str]:
    if not SILVER.is_dir():
        return []
    return sorted(p.name for p in SILVER.iterdir()
                  if p.is_dir() and _hat_tabelle(p.name, "notices"))


def _wurzeln(con: duckdb.DuckDBPyConnection, country: str) -> list[tuple[str, str]]:
    """Rückverweis-Kette bis zur Wurzel auflösen (wie ``gold.build_procedures``).

    Hier bewusst nachgebaut statt ``data/gold/DE/procedures.parquet`` gelesen: die
    Tabelle existiert nur für DE, und der Marktpuls soll für jedes Land gleich rechnen.
    """
    rows = con.execute(f"""
        SELECT publication_number, ref_publication_number
        FROM '{_glob(country, "notices")}'
        WHERE publication_number IS NOT NULL AND ref_publication_number IS NOT NULL
    """).fetchall()
    if not rows:
        return []
    ref = dict(rows)

    def root(pn: str) -> str:
        seen: set[str] = set()
        while True:
            parent = ref.get(pn)
            if not parent or parent in seen:
                return pn
            seen.add(pn)
            pn = parent

    return [(pn, root(pn)) for pn in ref]


def _dedup_ids(country: str) -> list[str]:
    """notice_ids, die als Quellen-Dublette fallen (AT: atverg-Zwilling, CH: simap-Zwilling)."""
    con = duckdb.connect()
    out: list[str] = []
    at = GOLD / country / "atverg_dedup.parquet"
    if at.exists():
        out += [r[0] for r in con.execute(
            f"SELECT av_id FROM '{at}' WHERE ted_id IS NOT NULL").fetchall()]
    ch = GOLD / country / "ted_dedup.parquet"
    if ch.exists():
        out += [r[0] for r in con.execute(
            f"SELECT simap_id FROM '{ch}' WHERE status='dublette' AND simap_id IS NOT NULL"
        ).fetchall()]
    con.close()
    return out


def _in_list(col: str, werte: list[str]) -> str:
    """SQL-Bedingung ohne Parameterbindung — Werte sind ausschliesslich Notice-IDs aus
    unserem eigenen Bestand, trotzdem wird jedes Hochkomma verdoppelt."""
    if not werte:
        return "FALSE"
    lit = ",".join("'" + w.replace("'", "''") + "'" for w in werte)
    return f"{col} IN ({lit})"


# --- Kern: Verfahrenstabelle je Land --------------------------------------------
def verfahren_tabelle(con: duckdb.DuckDBPyConnection, country: str, ab_jahr: int) -> None:
    """Legt TEMP TABLE ``v_<country>`` an: ein Verfahren = eine Zeile.

    Spalten: land, jahr, monat, branche, quelle, verfahren_key, frist, hat_frist.
    Enthält nur *eröffnende* Bekanntmachungen (cn / pin-mit-Frist), ohne Korrekturen.
    """
    n = _glob(country, "notices")
    a = _glob(country, "attributes")
    dim_cpv = GOLD / "DE" / "dim_cpv.parquet"      # reine Dimensionstabelle (CPV-Division)

    # Änderungsbekanntmachungen (eForms) — als eigene Temp-Tabelle, weil der
    # Attribut-Scan sonst je Abfrage neu läuft.
    con.execute("CREATE OR REPLACE TEMP TABLE _chg (notice_id VARCHAR)")
    if _hat_tabelle(country, "attributes"):
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE _chg AS
            SELECT DISTINCT notice_id FROM '{a}'
            WHERE year >= {ab_jahr} AND path LIKE '%ChangedNoticeIdentifier'
        """)
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE _folder AS
            SELECT notice_id, min(value) AS folder FROM '{a}'
            WHERE year >= {ab_jahr} AND path LIKE '%.ContractFolderID' AND value IS NOT NULL
            GROUP BY 1
        """)
    else:
        con.execute("CREATE OR REPLACE TEMP TABLE _folder (notice_id VARCHAR, folder VARCHAR)")

    # Rückverweis-Wurzeln (legacy)
    con.execute("CREATE OR REPLACE TEMP TABLE _root (publication_number VARCHAR, root VARCHAR)")
    paare = _wurzeln(con, country)
    if paare:
        con.executemany("INSERT INTO _root VALUES (?, ?)", paare)

    dedup = _dedup_ids(country)
    quelle_case = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in QUELLE.items())

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE _notices AS
        SELECT n.notice_id, n.publication_date, n.year AS jahr, n.month AS monat,
               n.submission_deadline AS frist,
               (c.notice_id IS NOT NULL) AS ist_aenderung,
               CASE n.schema_gen {quelle_case} ELSE 'sonstige' END AS quelle,
               coalesce({BRANCHE_SQL}, 'beratung') AS branche,
               coalesce(f.folder, r.root, n.publication_number, n.notice_id) AS verfahren_key
        FROM '{n}' n
        LEFT JOIN _folder f ON f.notice_id = n.notice_id
        LEFT JOIN _root r ON r.publication_number = n.publication_number
        LEFT JOIN _chg c ON c.notice_id = n.notice_id
        LEFT JOIN '{dim_cpv}' b ON b.division = substr(n.cpv_main, 1, 2)
        WHERE n.year >= {ab_jahr}
          AND n.notice_kind IN {TENDER_KINDS}
          AND (n.notice_kind <> 'pin' OR n.submission_deadline IS NOT NULL)
          AND n.publication_date IS NOT NULL
          AND n.publication_date <= current_date          -- Datums-Ausreisser (bis 2033) raus
          AND NOT ({_in_list("n.notice_id", dedup)})
    """)

    # Ein Verfahren = eine Zeile.
    # Zeitpunkt/Branche/Quelle: aus der frühesten **eröffnenden** Bekanntmachung (Änderungen
    # eröffnen nichts). Frist: das **Maximum über alle** Zeilen der Gruppe — genau dafür
    # bleiben die Änderungsbekanntmachungen in der Gruppe, denn eine Fristverlängerung steht
    # ausschliesslich in ihnen. Wer sie vorher wegwirft, zeigt abgelaufene Verfahren als offen.
    # Gruppen ohne eröffnende Zeile (Änderung, deren Original vor `ab_jahr` liegt) fallen raus.
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE v_{country} AS
        SELECT * FROM (
            SELECT '{country}' AS land, verfahren_key,
                   min_by(jahr, publication_date) FILTER (WHERE NOT ist_aenderung) AS jahr,
                   min_by(monat, publication_date) FILTER (WHERE NOT ist_aenderung) AS monat,
                   min(publication_date) FILTER (WHERE NOT ist_aenderung) AS pub,
                   min_by(branche, publication_date) FILTER (WHERE NOT ist_aenderung) AS branche,
                   min_by(quelle, publication_date) FILTER (WHERE NOT ist_aenderung) AS quelle,
                   max(frist) AS frist,
                   count(*) FILTER (WHERE ist_aenderung) AS n_aenderungen,
                   count(*) AS n_notices
            FROM _notices GROUP BY verfahren_key
        ) WHERE pub IS NOT NULL
    """)


# --- Teil 1: Saisonalität -------------------------------------------------------
def quellen_im_fenster(con, country: str, jahre: list[int]) -> tuple[list[str], list[dict]]:
    """Quellenfamilien, die über das GANZE Fenster liefern — der Rest fliegt aus der Zeitreihe."""
    rows = con.execute(f"""
        SELECT quelle, count(DISTINCT jahr) AS j, count(*) AS n, min(jahr) AS von, max(jahr) AS bis
        FROM v_{country} WHERE jahr BETWEEN {jahre[0]} AND {jahre[-1]}
        GROUP BY 1 ORDER BY 3 DESC
    """).fetchall()
    drin, raus = [], []
    for q, j, n, von, bis in rows:
        if j == len(jahre):
            drin.append(q)
        else:
            raus.append({"quelle": q, "verfahren": n, "von": von, "bis": bis,
                         "grund": "liefert erst ab %d — Quellen-Onset, kein Marktsignal" % von})
    return drin, raus


def saison_block(con, wo: str, jahre: list[int]) -> dict:
    """Monatswerte + Befund für eine Land×Branche-Kombination.

    ``avg`` = Ø absolute Verfahren je Kalendermonat (Briefing §3.1).
    ``pct`` = Abweichung vom Jahresmittel. Berechnet als **Saisonindex**: erst je Jahr
    normiert (Monat / Monatsmittel des Jahres), dann über die Jahre gemittelt. Der
    naive Weg (Ø-Zahl / Ø-Jahresmittel) gewichtet grosse Jahre stärker und reagiert auf
    Niveauverschiebungen im Fenster; der Index tut das nicht. Beide Werte liegen im JSON
    (`pct` = Index, `pct_naiv`), damit die Differenz prüfbar bleibt.
    """
    rows = con.execute(f"""
        WITH je_jahr_monat AS (
            SELECT jahr, monat, count(*) AS n FROM _saison WHERE {wo} GROUP BY 1, 2
        ), voll AS (
            SELECT j.jahr, m.monat, coalesce(x.n, 0) AS n
            FROM (SELECT unnest({jahre}) AS jahr) j
            CROSS JOIN (SELECT unnest([1,2,3,4,5,6,7,8,9,10,11,12]) AS monat) m
            LEFT JOIN je_jahr_monat x ON x.jahr = j.jahr AND x.monat = m.monat
        ), jm AS (
            SELECT jahr, avg(n) AS mittel FROM voll GROUP BY 1
        )
        SELECT v.monat, avg(v.n) AS avg_n,
               avg(CASE WHEN jm.mittel > 0 THEN v.n / jm.mittel END) AS index_
        FROM voll v JOIN jm ON jm.jahr = v.jahr
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    monate = [{"m": int(m), "avg": round(a, 1)} for m, a, _ in rows]
    total = sum(r[1] for r in rows) * len(jahre)
    jahresmittel = sum(r[1] for r in rows) / 12 if rows else 0.0
    for eintrag, (_, a, idx) in zip(monate, rows):
        eintrag["pct"] = round(((idx or 1.0) - 1.0) * 100, 1)
        eintrag["pct_naiv"] = round((a / jahresmittel - 1) * 100, 1) if jahresmittel else 0.0
    return {
        "monate": monate,
        "jahresmittel": round(jahresmittel, 1),
        "verfahren_gesamt": int(round(total)),
        "jahre": jahre,
        "befund": befund(monate),
        "genug": int(round(total)) >= MIN_FAELLE,
    }


def befund(monate: list[dict]) -> dict:
    """Der Ein-Satz-Befund aus den Werten — Briefing §7. Kein vorformulierter Text:
    hier entstehen nur CODE + Zahlen, formuliert wird im Frontend (i18n)."""
    if not monate:
        return {"typ": "keine_daten"}
    hoch = max(monate, key=lambda x: x["pct"])
    tief = min(monate, key=lambda x: x["pct"])
    if hoch["pct"] >= AUSREISSER_PCT:
        return {"typ": "spitze", "monat": hoch["m"], "pct": hoch["pct"], "avg": hoch["avg"]}
    if tief["pct"] <= -AUSREISSER_PCT:
        return {"typ": "tief", "monat": tief["m"], "pct": tief["pct"], "avg": tief["avg"]}
    return {"typ": "flach", "monat": hoch["m"], "pct": hoch["pct"], "avg": hoch["avg"],
            "monat_tief": tief["m"], "pct_tief": tief["pct"]}


# --- Teil 2: Aktuelle Lage ------------------------------------------------------
def lage_block(con, laender: list[str], heute: dt.date) -> dict:
    """Stichtags-Kennzahlen. Anders als die Zeitreihe zählt hier JEDE Quelle mit —
    ein Stichtag kennt keinen Onset-Sprung."""
    union = " UNION ALL ".join(f"SELECT * FROM v_{c}" for c in laender)
    con.execute(f"CREATE OR REPLACE TEMP TABLE _lage AS {union}")

    def zaehl(wo: str) -> int:
        return con.execute(f"SELECT count(*) FROM _lage WHERE {wo}").fetchone()[0]

    je_land, je_branche = {}, {}
    for c in laender + [GESAMT]:
        wo_land = "TRUE" if c == GESAMT else f"land = '{c}'"
        frisch = zaehl(f"{wo_land} AND pub >= current_date - 90")
        mit_frist = zaehl(f"{wo_land} AND pub >= current_date - 90 AND frist IS NOT NULL")
        je_land[c] = {
            "laufend": zaehl(f"{wo_land} AND frist >= current_date"),
            "ohne_frist": frisch - mit_frist,
            # Herkunfts-Kennzeichnung (Projekt-Konvention): die Kennzahl steht ausschliesslich
            # auf der echten `submission_deadline`. `frist_abdeckung` sagt, für welchen Anteil
            # der frischen Verfahren überhaupt eine Frist veröffentlicht ist — sinkt sie (AT:
            # atverg meldet oft keine), ist `laufend` eine Untergrenze, keine Vollzählung.
            "frist_basis": "echt",
            "frist_abdeckung": round(100.0 * mit_frist / frisch, 1) if frisch else 0.0,
        }
        je_branche[c] = [{"key": b, "n": zaehl(f"{wo_land} AND branche = '{b}' AND frist >= current_date")}
                         for b in BRANCHEN]
        je_branche[c].sort(key=lambda x: -x["n"])

    # Zuschläge / Aufhebungen der letzten 30 Tage — je Land aus Silber, ohne Verfahrens-
    # Klammer (ein CAN IST der Abschluss; die Klammer würde Mehrlos-Zuschläge verschlucken).
    zuschlag, aufhebung = {}, {}
    for c in laender:
        n, aw = _glob(c, "notices"), _glob(c, "awards")
        hat_aw = _hat_tabelle(c, "awards")
        gewinner = (f"(SELECT DISTINCT notice_id FROM '{aw}' WHERE winner_name IS NOT NULL)"
                    if hat_aw else "(SELECT NULL::VARCHAR AS notice_id WHERE FALSE)")
        z, a = con.execute(f"""
            SELECT count(*) FILTER (WHERE g.notice_id IS NOT NULL),
                   count(*) FILTER (WHERE g.notice_id IS NULL)
            FROM '{n}' x LEFT JOIN {gewinner} g ON g.notice_id = x.notice_id
            WHERE x.notice_kind = 'can'
              AND x.publication_date BETWEEN current_date - {LAGE_TAGE} AND current_date
        """).fetchone()
        zuschlag[c], aufhebung[c] = z, a
    zuschlag[GESAMT] = sum(zuschlag.values())
    aufhebung[GESAMT] = sum(aufhebung.values())

    return {
        "stand": heute.isoformat(),
        "fenster_tage": LAGE_TAGE,
        "je_land": {c: {**je_land[c], "zuschlag_30d": zuschlag[c], "aufhebung_30d": aufhebung[c]}
                    for c in je_land},
        "je_branche": je_branche,
    }


# --- Orchestrierung -------------------------------------------------------------
def bauen(laender: list[str], n_jahre: int, heute: dt.date) -> dict:
    letztes_volles = heute.year - 1
    jahre = list(range(letztes_volles - n_jahre + 1, letztes_volles + 1))
    con = duckdb.connect()
    con.execute("SET threads=4")

    coverage: dict[str, dict] = {}
    saison_quellen: dict[str, list[str]] = {}
    for c in laender:
        verfahren_tabelle(con, c, jahre[0])
        drin, raus = quellen_im_fenster(con, c, jahre)
        saison_quellen[c] = drin
        gesamt, im_fenster = con.execute(f"""
            SELECT count(*), count(*) FILTER (WHERE jahr BETWEEN {jahre[0]} AND {jahre[-1]}
                   AND quelle IN ({",".join("'" + q + "'" for q in drin) or "''"}))
            FROM v_{c}
        """).fetchone()
        max_pub = con.execute(f"SELECT max(pub) FROM v_{c}").fetchone()[0]
        coverage[c] = {
            "verfahren_gesamt": gesamt,
            "verfahren_im_fenster": im_fenster,
            "quellen_zeitreihe": drin,
            "quellen_ausgeschlossen": raus,
            "letzte_veroeffentlichung": max_pub.isoformat() if max_pub else None,
            "belastbar": im_fenster >= MIN_FAELLE and bool(drin),
        }

    # Länder OHNE einen einzigen Fall im Fenster fliegen ganz raus — nicht als „nicht
    # belastbar" markiert, sondern gar nicht erst ausgewiesen. Gemessen stand „EU: 0
    # Verfahren  ⚠ nicht belastbar" in der Ausgabe; eine Kategorie mit null Fällen ist keine
    # Aussage über einen dünnen Markt, sondern eine leere Zeile.
    #
    # Sie war zudem die Ursache des zweiten Fehlers: der EU-Topf brachte „ted" als
    # AUSGESCHLOSSENE Quelle ins Aggregat ein, während TED für DE/AT/CH die tragende Quelle
    # ist. In der Gesamtzeile stand deshalb „Quellen atverg+ted, ausgeschlossen: … ted" —
    # dieselbe Quelle gleichzeitig drin und draußen.
    leer = [c for c in laender if coverage[c]["verfahren_im_fenster"] == 0]
    for c in leer:
        print(f"  {c}: 0 Verfahren im Fenster — nicht ausgewiesen (leere Kategorie, "
              f"keine Aussage über den Markt)")
        laender.remove(c)
        coverage.pop(c, None)
        saison_quellen.pop(c, None)

    # Aggregat-Zeile: dieselbe Struktur wie ein Land, damit die Anzeige nicht zwei Fälle
    # kennen muss. Ein dünnes Land wird MITGEZÄHLT (kein Datenverlust), aber namentlich in
    # `nicht_belastbar` ausgewiesen — genau die Forderung „nicht still mitgemittelt".
    drin_agg = sorted({q for c in coverage.values() for q in c["quellen_zeitreihe"]})
    # Ausgeschlossen zählt am Aggregat nur, was NIRGENDS in die Zeitreihe eingeht. Sonst
    # stünde „TED erst ab 2023" da, nur weil der dünne EU-Topf erst 2023 anfängt — obwohl
    # TED die tragende Quelle von DE/AT/CH über das ganze Fenster ist.
    raus_agg: dict[str, dict] = {}
    for c in coverage.values():
        for q in c["quellen_ausgeschlossen"]:
            if q["quelle"] in drin_agg:
                continue
            vorher = raus_agg.get(q["quelle"])
            if vorher is None or q["von"] < vorher["von"]:
                raus_agg[q["quelle"]] = dict(q)
            elif vorher:
                vorher["verfahren"] += q["verfahren"]
    coverage[GESAMT] = {
        "verfahren_gesamt": sum(c["verfahren_gesamt"] for c in coverage.values()),
        "verfahren_im_fenster": sum(c["verfahren_im_fenster"] for c in coverage.values()),
        "quellen_zeitreihe": drin_agg,
        "quellen_ausgeschlossen": sorted(raus_agg.values(), key=lambda q: -q["verfahren"]),
        "letzte_veroeffentlichung": max(
            (c["letzte_veroeffentlichung"] for c in coverage.values() if c["letzte_veroeffentlichung"]),
            default=None),
        "belastbar": sum(c["verfahren_im_fenster"] for c in coverage.values()) >= MIN_FAELLE,
        "nicht_belastbar": [c for c in laender if not coverage[c]["belastbar"]],
        "mitglieder": laender,
    }

    # Saison-Grundmenge: nur durchgehende Quellen, nur volle Jahre.
    teile = [f"SELECT * FROM v_{c} WHERE quelle IN ({','.join(chr(39)+q+chr(39) for q in saison_quellen[c])})"
             for c in laender if saison_quellen[c]]
    con.execute(f"CREATE OR REPLACE TEMP TABLE _saison AS {' UNION ALL '.join(teile)}"
                if teile else "CREATE OR REPLACE TEMP TABLE _saison AS SELECT * FROM v_%s WHERE FALSE" % laender[0])

    saison: dict[str, dict] = {}
    for land in [GESAMT] + laender:
        wo_land = "TRUE" if land == GESAMT else f"land = '{land}'"
        for br in [ALLE] + list(BRANCHEN):
            wo = wo_land if br == ALLE else f"{wo_land} AND branche = '{br}'"
            saison[f"{land}|{br}"] = saison_block(con, wo, jahre)

    lage = lage_block(con, laender, heute)
    con.close()

    return {
        "schema": 1,
        "erzeugt": dt.datetime.now().isoformat(timespec="seconds"),
        "stand": heute.isoformat(),
        "laender": laender,
        "gesamt_key": GESAMT,
        "branchen": list(BRANCHEN),
        "fenster": {"von": jahre[0], "bis": jahre[-1], "jahre": len(jahre)},
        "min_faelle": MIN_FAELLE,
        "coverage": coverage,
        "saison": saison,
        "lage": lage,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--laender", default=None,
                   help="Komma-Liste, z. B. DE,AT,CH (Default: alles unter data/silver/)")
    p.add_argument("--jahre", type=int, default=FENSTER_JAHRE)
    p.add_argument("--out", default=str(ROOT / "web" / "data" / "marktpuls.json"))
    p.add_argument("--stichtag", default=None, help="ISO-Datum (Test/Reproduktion)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    laender = ([x.strip().upper() for x in args.laender.split(",") if x.strip()]
               if args.laender else verfuegbare_laender())
    laender = [c for c in laender if _hat_tabelle(c, "notices")]
    if not laender:
        print("Keine Länder mit Silber-notices gefunden.", file=sys.stderr)
        return 1
    heute = dt.date.fromisoformat(args.stichtag) if args.stichtag else dt.date.today()

    daten = bauen(laender, args.jahre, heute)
    text = json.dumps(daten, ensure_ascii=False, separators=(",", ":"))

    print(f"Länder: {', '.join(laender)} | Fenster {daten['fenster']['von']}–{daten['fenster']['bis']}")
    for c, cov in daten["coverage"].items():
        raus = ", ".join(q["quelle"] for q in cov["quellen_ausgeschlossen"]) or "–"
        print(f"  {c}: {cov['verfahren_im_fenster']:>8,} Verfahren im Fenster "
              f"(Quellen {'+'.join(cov['quellen_zeitreihe'])}, ausgeschlossen: {raus})"
              f"{'' if cov['belastbar'] else '  ⚠ nicht belastbar'}")
    g = daten["saison"][f"{GESAMT}|{ALLE}"]
    print(f"  Jahresmittel {g['jahresmittel']:,.0f}/Monat, Befund {g['befund']}")
    print("  " + "  ".join(f"{m['m']:>2}:{m['pct']:+.0f}%" for m in g["monate"]))
    print(f"  Lage: {daten['lage']['je_land'][GESAMT]}")
    print(f"  JSON {len(text)/1024:.1f} KB")

    if args.dry_run:
        return 0
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

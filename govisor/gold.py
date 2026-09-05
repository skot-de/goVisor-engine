"""Gold: die Ebenen, auf denen das Produkt arbeitet.

Silber ist notice-genau — quelltreu, aber nicht die Granularität des Produkts.
Zwei Ebenen liegen darüber, und beide entstehen hier:

* **Vergabeverfahren** (``procedures``): eine Bekanntmachung und alle Notices,
  die auf sie verweisen — ihre Vergabe, ihre Korrekturen, ihre Änderungen.
  Silber hat den Rückverweis (``ref_publication_number``); Gold zieht daraus
  die Gruppierung.

* **Entitäten** (``buyers``, ``suppliers``): dieselbe Organisation über viele
  Schreibweisen und Jahre hinweg als ein Datensatz — mit einer **Konfidenz**,
  nicht als sauberer Fremdschlüssel. Das ist der Kern: Die Auflösung liegt bei
  ~63 %, und ein JOIN, der Unsicherheit als Wahrheit tarnt, ist genau der
  Fehlertyp, den wir sonst jagen. Jeder Schlüssel trägt, wie sicher er ist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import locales
from . import db as _db
from .config import Config
from .testvergaben import sql_bedingung as _testvergabe_sql

# eForms-ORG-Referenz (UUID) — pro Dokument vergeben, taugt nicht als Entity-Schlüssel.
_RE_UUID_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-")

# Leitweg-ID — die bundesweit eindeutige Kennung ÖFFENTLICHER Stellen (E-Rechnungs-Pflicht seit
# 2020). Format <Grobadressierung>-<Feinadressierung>-<Prüfziffer>, optional mit Schema-Präfix
# „NNNN:". Autoritativer Schlüssel genau für Vergabestellen (im Handelsregister gibt es sie nicht).
# In eForms zu ~13 % vorhanden. Roh landete sie mit Präfix/Leerzeichen als GESPALTENER Schlüssel.
# Grobadressierung = 2–12 Stellen (Kfz-Kürzel bis voller Regionalschlüssel/AGS). Zu eng (2–3) ließ
# ~64k Käufer-Instanzen mit vollem AGS liegen (09162000=München, 05111=Düsseldorf, 08421000=LK).
_RE_LEITWEG = re.compile(r"^(?:\d{3,4}:)?(\d{2,12}-[0-9A-Za-z]+-\d{2})$")
_RE_VAT_DE = re.compile(r"^DE\s?(\d{9})$", re.I)                 # USt-IdNr
# Erkennbarer Müll: TED-interne „t:"-IDs, reine Bindestriche, 1-4-stellige Zahlen (Notiz-intern).
_RE_ID_JUNK = re.compile(r"^(?:t:.*|-+|\d{1,4})$", re.I)


def normalize_national_id(national_id: str | None) -> str | None:
    """Roh-``national_id`` → stabiler Entity-Schlüssel oder None (dann Name-Fallback).

    Vereinheitlicht die **Leitweg-ID** (Schema-Präfix + Leerzeichen weg → derselbe öffentliche
    Auftraggeber unter EINEM Schlüssel), normalisiert USt-IdNr, und verwirft erkennbaren Müll
    (UUID/TED-intern/Kurzzahlen), der sonst pro Notice eine neue Garbage-Entität erzeugt.
    """
    nid = re.sub(r"\s+", "", national_id or "")
    if not nid:
        return None
    m = _RE_LEITWEG.match(nid)
    if m:
        return "leitweg:" + m.group(1)
    m = _RE_VAT_DE.match(nid)
    if m:
        return "vat:DE" + m.group(1)
    if _RE_UUID_ID.match(nid) or _RE_ID_JUNK.match(nid):
        return None
    return nid                                                   # sonstige Register-ID unverändert

# Freemail-/Provider-Domains sind KEIN Firmengruppen-Signal (Einzelunternehmer mit
# gmail gehören zu keiner Gruppe). Die Second-Level-Domain einer Firmen-Domain
# dagegen bündelt Töchter/Marken zuverlässig: alles @*.cancom.* → Gruppe CANCOM.
# Freemail-Liste, öffentl.-rechtl. Sammeldomains und der Behörden-Namensfilter sind
# sprach-/institutionsspezifisch und liegen im aktiven Länder-Profil (locales.active()).
_DOMAIN_TLD2 = {"uk", "au", "br", "nz", "za", "jp"}      # zweistufige Länder-Suffixe
_DOMAIN_SLD2 = {"co", "gov", "com", "org", "ac", "net"}  # davor: co.uk, gov.uk …


def looks_public(name: str) -> bool:
    """Öffentlich-rechtliche Körperschaft? Dann keine kommerzielle Auto-Gruppe."""
    from . import entities as ent
    return bool(locales.active().re_public_name.search(ent.strip_accents((name or "").lower())))


def domain_group_label(domain: str | None, name_norm: str | None = None) -> str:
    """Second-Level-Domain einer FIRMEN-Domain → Gruppenlabel ('cancom.de' → 'CANCOM').

    Leerer String, wenn: Freemail/Provider, öffentlich-rechtliche Sammeldomain,
    oder — wenn ``name_norm`` gegeben — der Domain-Kern NICHT im Namen vorkommt.
    Letzteres killt die Portal-Kontamination (Lieferant mit @deutschebahn.com-
    Kontakt), weil dann Domain und Name widersprechen.
    """
    if not domain:
        return ""
    # `lstrip("www.")` wäre hier falsch: lstrip entfernt keinen Präfix, sondern jedes
    # führende Zeichen aus der Menge {w, .}. „wienerlinien.at" wurde damit zu
    # „ienerlinien.at" → Gruppe IENERLINIEN. Gemessen: 2.986 DE-Domains / 52.748 Kontakte
    # falsch gruppiert, darunter Totalverluste (wbm.de → „bm" → zu kurz → gar keine Gruppe).
    d = domain.lower().strip()
    if d.startswith("www."):
        d = d[4:]
    parts = [p for p in d.split(".") if p]
    if len(parts) < 2:
        return ""
    if parts[-1] in _DOMAIN_TLD2 and len(parts) >= 3 and parts[-2] in _DOMAIN_SLD2:
        sld = parts[-3]
    else:
        sld = parts[-2]
    loc = locales.active()
    if (sld in loc.freemail or sld in loc.public_domain_slds or len(sld) < 3
            or sld.endswith("-stadt") or sld.endswith("-kreis")):
        return ""
    if name_norm is not None:
        toks = name_norm.split()
        if not (sld in toks or any((len(t) >= 4 and (sld in t or t in sld)) for t in toks)):
            return ""            # Domain und Name widersprechen → nicht gruppieren
    return sld.upper()


def _notices_glob(cfg: Config, country: str) -> str:
    return cfg.silver_table_glob("notices", country)


def build_procedures(cfg: Config, country: str = "DE"):
    """Gruppiere Notices zu Vergabeverfahren über den Rückverweis-Graphen.

    Eine Notice verweist per ``ref_publication_number`` auf eine frühere (die
    Vergabe auf ihre Bekanntmachung, die Korrektur auf das Original). Wir
    folgen der Kette bis zur Wurzel — der frühesten Notice ohne eigenen
    Verweis. Diese Wurzel ist die ``procedure_id``.

    Wichtig: Das ist die Klammer um *ein* Verfahren (CN + CAN + Korrekturen),
    NICHT die Kette über Verfahren hinweg (Ausschreibung 2019 → Nachfolger
    2023). Letztere existiert in den Daten nicht und muss erschlossen werden —
    siehe docs/concept-v3.md, Abschnitt 8.
    """

    con = _db.connect()
    src = _notices_glob(cfg, country)
    rows = con.execute(f"""
        SELECT publication_number, ref_publication_number
        FROM '{src}'
        WHERE publication_number IS NOT NULL
    """).fetchall()

    ref = {pn: rp for pn, rp in rows}

    def root(pn: str) -> str:
        seen = set()
        while True:
            parent = ref.get(pn)
            # Stop at a notice with no ref, a ref outside our data, or a cycle.
            if not parent or parent not in ref or parent in seen:
                return pn
            seen.add(pn)
            pn = parent

    mapping = [(pn, root(pn)) for pn in ref]

    out = cfg.gold_dir / country / "procedures.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con.execute("CREATE TABLE m (publication_number VARCHAR, procedure_id VARCHAR)")
    con.executemany("INSERT INTO m VALUES (?, ?)", mapping)
    con.execute(f"COPY (SELECT * FROM m) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    return len(mapping)


def seed_groups(cfg: Config, country: str = "DE", reseed: bool = False) -> tuple[int, int]:
    """Editierbare Gruppen-Zuordnung bootstrappen — REDAKTIONELL, nicht Fakt.

    Eine goVisor-eigene Gruppe wie 'CANCOM', unter der alle Einheiten hängen —
    unabhängig von der echten Konzernmutter (die oft gar nicht sauber auflösbar
    ist). Wie die Branche über CPV: deine Setzung, versioniert, kuratierbar.

    Der Seed schreibt eine CSV (``data/curated/DE_company_groups.csv``) und schlägt
    eine Gruppe NUR vor, wenn die Firmen-**E-Mail-Domain** sie bestätigt (SLD deckt
    sich mit dem Namen: @cancom.de + „CANCOM …" → CANCOM). Der bloße Namensstamm
    taugt NICHT — gemessen mergt er unabhängige Firmen (144 „Müller", 1224
    „Ingenieurbüro") und öffentliche Stellen. Firmen ohne bestätigende Domain
    bleiben ungruppiert (Label leer) und werden bei Bedarf von Hand kuratiert.
    **Er überschreibt nie bestehende Zeilen** — Handkorrekturen überleben den Rebuild.

    Spalten: entity_id, canonical_name, national_id, group_label, source
    (``auto_domain`` = per Domain bestätigt, ``seed`` = ungruppiert/bootstrap,
    ``manual`` = von dir gesetzt). Zum Editieren: ``group_label`` ändern, ``source``
    auf ``manual`` setzen.
    """
    import csv
    from . import entities as ent

    path = cfg.group_csv(country)
    existing: dict[str, dict] = {}
    if path.exists() and not reseed:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                existing[row["entity_id"]] = row

    con = _db.connect()
    rows = con.execute(f"""
        SELECT entity_id, canonical_name, national_id
        FROM '{cfg.gold_dir / country / 'entities.parquet'}'
        WHERE canonical_name IS NOT NULL
    """).fetchall()
    # Dominante E-Mail-Domain je Entität (aus notice_parties über party_entity).
    # Stärkstes Gruppen-Signal, WO die Mail die Eigendomain der Firma ist —
    # korroboriert gegen den Namen, weil sie oft ein geteilter Vergabe-Kontakt ist.
    # Fehlen die Quellen (z. B. im Test), bleibt die Map leer → Namensstamm greift.
    PE = cfg.gold_dir / country / "party_entity.parquet"
    NP_glob = cfg.silver_table_glob("notice_parties", country)
    import glob as _glob
    domain_map: dict[str, str] = {}
    if PE.exists() and _glob.glob(NP_glob):
        domain_map = dict(con.execute(f"""
            WITH em AS (
              SELECT pe.entity_id,
                     lower(split_part(np.email, '@', 2)) AS domain
              FROM '{PE.as_posix()}' pe
              JOIN '{NP_glob}' np ON np.notice_id=pe.notice_id
                   AND np.role=pe.role AND np.seq=pe.seq
              WHERE np.email LIKE '%@%.%'
            ),
            cnt AS (SELECT entity_id, domain, count(*) n FROM em GROUP BY 1,2)
            SELECT entity_id, arg_max(domain, n) FROM cnt GROUP BY 1
        """).fetchall())
    # Dominante PLZ je Entität — für die kommunale Gruppierung (Gemeinde-Disambiguierung).
    # try/except: fehlt die postal_code-Spalte (z. B. Test-Fixtures), bleibt die Map leer.
    plz_map: dict[str, str] = {}
    if PE.exists() and _glob.glob(NP_glob):
        try:
            plz_map = dict(con.execute(f"""
                WITH pl AS (
                  SELECT pe.entity_id, regexp_extract(np.postal_code, '([0-9]{{5}})', 1) AS plz
                  FROM '{PE.as_posix()}' pe
                  JOIN '{NP_glob}' np ON np.notice_id=pe.notice_id AND np.role=pe.role AND np.seq=pe.seq
                  WHERE np.postal_code IS NOT NULL),
                cnt AS (SELECT entity_id, plz, count(*) n FROM pl WHERE plz<>'' GROUP BY 1,2)
                SELECT entity_id, arg_max(plz, n) FROM cnt GROUP BY 1
            """).fetchall())
        except Exception:
            plz_map = {}
    con.close()

    # Kommunale Gruppen: Referate/Ämter derselben Gemeinde (je EIGENE Leitweg-ID, daher NICHT
    # gemergt) unter EIN Gruppen-Label bringen — „Landeshauptstadt München", „…, Baureferat",
    # „…, Direktorium" → Gruppe „München". Label = kürzester Name der Gruppe (Basis-Gemeinde).
    plz_kreis = _load_plz_kreis(cfg) if country == "DE" else {}
    from collections import defaultdict as _dd
    _muni_members: dict[str, list] = _dd(list)
    for entity_id, name, national_id in rows:
        plz = plz_map.get(entity_id)
        k = _muni_key(name, {plz} if plz else set(), plz_kreis)
        if k:
            _muni_members[k].append((entity_id, name))
    muni_group: dict[str, str] = {}          # entity_id → Gemeinde-Label (nur Gruppen mit ≥2 Stellen)
    for k, members in _muni_members.items():
        if len({eid for eid, _ in members}) < 2:
            continue
        label = min((nm for _, nm in members), key=len)     # kürzester = Basis-Gemeinde
        for eid, _ in members:
            muni_group[eid] = label

    added = 0
    for entity_id, name, national_id in rows:
        if entity_id in existing:
            continue                       # Handkorrektur nie anfassen.
        kind = ent.classify(name).kind
        # Auto-Gruppe NUR wenn die Firmen-Domain sie bestätigt — gemessen ist der
        # bloße Namensstamm zu rauschig (generische Wörter, Nachnamen, Behörden:
        # 144 unabhängige „Müller", 1224 „Ingenieurbüro"). Firmen ohne bestätigende
        # Domain bleiben ungruppiert und werden bei Bedarf von Hand kuratiert.
        label, source = "", "seed"
        if kind is ent.Kind.COMPANY and not looks_public(name):
            dom_label = domain_group_label(domain_map.get(entity_id),
                                           name_norm=ent.normalize_company(name))
            if dom_label:
                label, source = dom_label, "auto_domain"
        elif entity_id in muni_group:
            # Kommunale Stelle → unter ihre Gemeinde gruppieren (Referate bleiben eigene Entities).
            label, source = muni_group[entity_id], "auto_muni"
        existing[entity_id] = {"entity_id": entity_id, "canonical_name": name,
                               "national_id": national_id or "", "group_label": label,
                               "source": source}
        added += 1

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["entity_id", "canonical_name", "national_id",
                                           "group_label", "source"])
        w.writeheader()
        for row in existing.values():
            w.writerow(row)
    return len(existing), added


def build_entity_groups(cfg: Config, country: str = "DE") -> tuple[int, int]:
    """Kuratierte Gruppen-CSV → abfragbare Tabellen (dim_company_group, entity_group).

    Liest die von Hand pflegbare CSV und materialisiert sie für Joins. Drill-down
    (Gruppe → Einheiten) und Roll-up (Einheit → Gruppe) laufen über ``group_id``.
    """
    import csv

    # KEIN früher Rücksprung ohne Datei. Die Gruppen-CSV wird von Hand gepflegt und existiert
    # nur für DE; für AT/CH gibt es keine — ein zulässiger Zustand, kein Fehler. Der Bauer
    # schrieb dann aber GAR NICHTS, und jeder Nachfolger brach mit „No files found" ab
    # (gemessen 2026-08-13: build_succession_kpis, build_entity_identity, in der Folge
    # lead_detail und lead_export — die ganze AT/CH-Kette hing an dieser einen Zeile).
    # Eine leere Tabelle mit korrektem Schema ist eine Aussage („keine Gruppen"), eine
    # fehlende Datei ist keine. Dieselbe Konvention wie „markieren statt filtern",
    # nur auf Dateiebene.
    path = cfg.group_csv(country)
    groups: dict[str, str] = {}
    links = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                label = (row.get("group_label") or "").strip()
                if not label:
                    continue
                gid = "grp:" + label.lower().replace(" ", "_")
                groups[gid] = label
                links.append((row["entity_id"], gid))

    con = _db.connect()
    _write(con, cfg.gold_dir / country / "dim_company_group.parquet",
           [(gid, label) for gid, label in groups.items()],
           "group_id VARCHAR, label VARCHAR")
    _write(con, cfg.gold_dir / country / "entity_group.parquet", links,
           "entity_id VARCHAR, group_id VARCHAR")
    con.close()
    return len(groups), len(links)


def build_dim_cpv(cfg: Config, country: str = "DE"):
    """Dimensionstabelle CPV-Division → Bezeichnung, Sektor, Branche.

    Redaktionell und versioniert — die Branchen-Zuordnung ist deine Setzung,
    kein Fakt. Silber bleibt unberührt (Rohcodes in notice_cpv/lot_cpv); die
    Sektor-Sicht ist ein Join hierauf. 'Was zählt als IT' zu ändern heißt: eine
    Zeile in govisor/cpv.py ändern und diese Tabelle neu schreiben — kein
    Silber-Rebuild.
    """
    from . import cpv

    rows = [(div, label, sector, branche, cpv.DIM_CPV_VERSION)
            for div, (label, sector, branche) in cpv.DIVISIONS.items()]
    out = cfg.gold_dir / country / "dim_cpv.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con = _db.connect()
    con.execute("CREATE TABLE d (division VARCHAR, label VARCHAR, sector VARCHAR, "
                "branche VARCHAR, version INTEGER)")
    con.executemany("INSERT INTO d VALUES (?, ?, ?, ?, ?)", rows)
    con.execute(f"COPY (SELECT * FROM d) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    return len(rows)


# Verbraucherpreisindex (2020 = 100), Jahresdurchschnitt — länderspezifisch und
# daher im aktiven Profil (locales.active().cpi). Als Dimension: der reale Wert ist
# ein Join, keine eingebrannte Spalte — Faktoren korrigierbar, ohne Silber-Rebuild.


def build_dim_deflator(cfg: Config, country: str = "DE"):
    """Jahr → Faktor auf Preise 2020. final_value * factor = realer Wert.

    Ohne das vergleicht 'typische Dealgröße' 2016 mit 2024 unbereinigt — bei
    26% Preisanstieg dazwischen ein systematischer Fehler.

    ``locales.active()`` ist ein GLOBALER Zustand — die Funktion nahm ``country`` entgegen und
    benutzte es nur für den Ausgabepfad. Gemessen am 2026-08-13: ``gold/AT/dim_deflator.parquet``
    enthielt Zeichen für Zeichen die deutsche Reihe. Das fiel nie auf, weil AT/CH-Gold bis dahin
    keine Werte real rechnete.

    Jetzt wird die Reihe des LANDES genommen. AT und CH sind in ``locales`` zwar angelegt, tragen
    aber **null CPI-Jahre** — die Daten gibt es im Projekt nicht. Statt daraus eine leere Tabelle
    zu bauen (die jede Realwert-Rechnung stumm auf NULL setzte) fällt der Bauer auf DE zurück und
    **kennzeichnet das in der Tabelle** (Spalte ``cpi_source``). Für Österreich ist das als
    Eurozonen-Näherung vertretbar; **für die Schweiz nicht** — eigene Währung, eigener
    Inflationspfad. Wer CH-Werte real vergleicht, muss vorher echte BFS-Daten einspielen.
    """
    eigen = locales.get(country)
    cpi = getattr(eigen, "cpi", None) or {}
    quelle = country
    if not cpi:
        cpi = locales.active().cpi
        quelle = f"{getattr(locales.active(), 'code', 'DE')}-Naeherung"
        print(f"  ⚠ dim_deflator {country}: keine eigene CPI-Reihe — {quelle} verwendet "
              f"(als cpi_source gekennzeichnet).")
    rows = [(y, v, round(100.0 / v, 4), quelle) for y, v in cpi.items()]
    con = _db.connect()
    _write(con, cfg.gold_dir / country / "dim_deflator.parquet", rows,
           "year SMALLINT, cpi DOUBLE, factor_to_2020 DOUBLE, cpi_source VARCHAR")
    con.close()
    return len(rows)


def build_quality(cfg: Config, country: str = "DE"):
    """Plausibilitäts-Schicht — macht Datenmüll sichtbar, ohne ihn zu löschen.

    Jede Notice bekommt Qualitätsmarken (wie die Parser-Flags) und einen
    *bereinigten* Wert: ``final_value_clean`` ist der Wert, wenn er plausibel
    ist, sonst NULL. Aggregate über die clean-Spalte sind damit von Haus aus
    sauber; der Rohwert bleibt in Silber erhalten.

    Belegt an DE: 82.002 Vergaben (~29% der bewerteten CANs) tragen einen
    Platzhalter unter 100 € — echte öffentliche Aufträge beginnen ~1.000 €.
    Ohne Bereinigung ist der Median-Deal um 45% zu niedrig.
    """
    con = _db.connect()
    N = cfg.silver_table_glob("notices", country)
    L = cfg.silver_table_glob("lots", country)
    A = cfg.silver_table_glob("awards", country)
    PE = str(cfg.gold_dir / country / "party_entity.parquet")
    out = cfg.gold_dir / country / "quality.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Jeder ERKENNBARE Defekt wird geflaggt (nicht weggeworfen). final_value_clean
    # ist nur dann gesetzt, wenn plausibel UND in EUR. Harte Fehler laufen von hier
    # in die Review-Queue. Zusätzlich `verfahren_status` (kein Defekt, sondern
    # Signal): CANs ohne Gewinner UND ohne Award-Daten = erfolglos/aufgehoben —
    # wertvoller Lead-Hinweis (weniger Konkurrenz beim Re-Tender), kein Fehler.
    # ⚠ Aber nur, wenn die QUELLE ueberhaupt Zuschlagsdaten liefert — sonst
    # `ohne_zuschlagsdaten`. Warum das zaehlt, steht unten am Status selbst.
    con.execute(f"""
        COPY (
          WITH dur AS (SELECT notice_id, max(duration_months) dm
                       FROM '{L}' WHERE duration_months>0 GROUP BY 1),
          bid AS (SELECT notice_id, bool_or(
                    num_tenders < 0 OR num_tenders > 500
                    OR (num_tenders_sme IS NOT NULL AND num_tenders > 0
                        AND num_tenders_sme > num_tenders)) AS bad
                  FROM '{A}' GROUP BY 1),
          win AS (SELECT DISTINCT notice_id FROM '{PE}' WHERE role='winner'),
          awp AS (SELECT DISTINCT notice_id FROM '{A}'),
          -- ⚠ WELCHE QUELLE LIEFERT UEBERHAUPT ZUSCHLAGSDATEN? Abgeleitet, nicht getippt:
          -- eine Quelle, deren Zuschlags-Bekanntmachungen zu unter 1 % eine Zeile in
          -- `awards` haben, liefert strukturell keine. Sobald sie es tut, faellt die
          -- Ausnahme von selbst weg — eine getippte Liste wuerde das nicht mitbekommen.
          quelle AS (
            SELECT n.schema_gen,
                   count(*) FILTER (WHERE a.notice_id IS NOT NULL)*1.0/count(*) AS anteil
            FROM '{N}' n LEFT JOIN awp a ON a.notice_id=n.notice_id
            WHERE n.notice_kind='can' GROUP BY 1),
          q AS (
            SELECT n.notice_id, n.final_value, n.estimated_value, n.value_currency,
                   n.notice_kind, n.award_date, n.end_date, n.start_date, n.title,
                   n.publication_date, n.submission_deadline,
                   COALESCE(n.end_date,
                     n.award_date + (CAST(dur.dm AS VARCHAR) || ' months')::INTERVAL) AS eff_end,
                   coalesce(bid.bad, false) AS bad_bid,
                   (win.notice_id IS NOT NULL) AS has_winner,
                   (awp.notice_id IS NOT NULL) AS has_award,
                   coalesce(quelle.anteil, 1.0) < 0.01 AS quelle_ohne_zuschlagsdaten
            FROM '{N}' n
            LEFT JOIN dur ON dur.notice_id=n.notice_id
            LEFT JOIN bid ON bid.notice_id=n.notice_id
            LEFT JOIN win ON win.notice_id=n.notice_id
            LEFT JOIN awp ON awp.notice_id=n.notice_id
            LEFT JOIN quelle ON quelle.schema_gen=n.schema_gen
          )
          SELECT notice_id,
            list_filter([
              CASE WHEN final_value IS NOT NULL AND final_value < 100
                   THEN 'wert_unplausibel_niedrig' END,
              CASE WHEN final_value <= 1 THEN 'wert_sentinel' END,
              -- Übungsvorgänge der Portale („Testvergabe für Bieter zur Übung der
              -- Angebotsabgabe") und Behörden-Selbsttests („TESTDL2025", 524 Mio €).
              -- Markiert, nicht gelöscht: sie sind Teil dessen, was die Quelle liefert.
              -- Das Muster ist bewusst eng, s. govisor/testvergaben.py.
              -- ⚠ BARE SPALTE, kein `n.`: die aeussere Auswahl steht ueber der CTE `q`,
              -- dort gibt es kein `n` mehr (die Nachbarzeilen sagen `final_value`, nicht
              -- `n.final_value`). Mit `n.title` bindet DuckDB nicht — und der Fehler
              -- erscheint erst beim Lauf, nicht beim Schreiben.
              CASE WHEN {_testvergabe_sql('title')} THEN 'testvergabe' END,
              CASE WHEN final_value >= 100 AND final_value < 1000
                   THEN 'wert_verdaechtig_niedrig' END,
              CASE WHEN final_value > 1e9 THEN 'wert_absurd_hoch' END,
              CASE WHEN final_value IS NOT NULL AND value_currency IS NOT NULL
                        AND value_currency <> 'EUR' THEN 'waehrung_fremd' END,
              CASE WHEN final_value IS NOT NULL AND value_currency IS NULL
                   THEN 'waehrung_angenommen' END,
              CASE WHEN estimated_value < 0 THEN 'schaetzwert_negativ' END,
              CASE WHEN end_date IS NOT NULL AND award_date IS NOT NULL
                        AND end_date < award_date THEN 'ende_vor_vergabe' END,
              CASE WHEN start_date IS NOT NULL AND end_date IS NOT NULL
                        AND start_date > end_date THEN 'datum_start_nach_ende' END,
              CASE WHEN submission_deadline IS NOT NULL AND publication_date IS NOT NULL
                        AND submission_deadline < publication_date THEN 'frist_vor_pub' END,
              -- ⚠ `publication_date` GEHOERT DAZU. Bis zum 2026-08-25 prueffte diese Regel
              -- nur award/end/start — ein Erscheinungsdatum in der Zukunft lief unmarkiert
              -- durch. Gemessen: 32 DE-Bekanntmachungen mit `publication_date` in 2033,
              -- alle vom Typ `can` und alle mit `_2023` in der Kennung, also um ein
              -- Jahrzehnt verrutscht. Einer davon steht als Lead im Frontend
              -- (773387_2023, „Juristische Datenbank", leads-it.json).
              -- Dass das Problem bekannt war, steht in `scripts/firma_profil.py:76`:
              -- dort wird auf „<= heute" geklemmt, mit dem Verweis auf genau diese Marke —
              -- ein Verbraucher raeumte auf, waehrend die Marke selbst nicht griff.
              -- Markieren, nicht wegwerfen: `datum_absurd` speist allein die Review-Queue.
              CASE WHEN award_date > current_date OR award_date < DATE '1990-01-01'
                        OR end_date > DATE '2100-01-01' OR start_date < DATE '1990-01-01'
                        OR publication_date > current_date
                        OR publication_date < DATE '1990-01-01'
                   THEN 'datum_absurd' END,
              CASE WHEN eff_end IS NOT NULL AND award_date IS NOT NULL
                        AND eff_end > award_date + INTERVAL 25 YEAR
                   THEN 'laufzeit_unplausibel' END,
              CASE WHEN bad_bid THEN 'bieterzahl_unplausibel' END,
              CASE WHEN notice_kind='corrigendum' THEN 'korrektur_nicht_zaehlen' END
            ], x -> x IS NOT NULL) AS quality_flags,
            CASE WHEN final_value >= 100 AND final_value <= 1e9
                      AND (value_currency = 'EUR' OR value_currency IS NULL)
                 THEN final_value END AS final_value_clean,
            CASE WHEN notice_kind='can' AND has_winner THEN 'vergeben'
                 -- Open-House-Rabattverträge (§130a SGB V): strukturell ohne Gewinner
                 -- (offener Beitritt), KEIN erfolgloses Verfahren → eigener Status, fällt
                 -- aus dem Chancen-Radar/der Chronik.
                 WHEN notice_kind='can' AND NOT has_winner
                      AND {_open_house_sql()} THEN 'open_house'
                 -- ⚠ „WIR WISSEN ES NICHT" IST NICHT „GESCHEITERT". Bis zum 2026-08-25
                 -- galt jede Zuschlags-Bekanntmachung ohne Zuschlagsdaten als erfolglos.
                 -- DOeE und NetServer schreiben aber ueberhaupt keine `awards`-Zeilen —
                 -- 79.302 bzw. 2.253 CANs, davon 0 mit Zeile. Ergebnis: **54 % aller
                 -- 150.168 „erfolglos" waren Artefakt**, und vierzehn Vergabestellen
                 -- standen mit einer Abbruchquote von exakt 100,0 % da (an der Spitze
                 -- die Vermoegens- und Hochbauverwaltung Baden-Wuerttemberg mit 5.189
                 -- Verfahren). Auffaellige Aggregatzahlen sind Warnsignale.
                 --
                 -- Das schlaegt weiter: `retender_signal` — laut CLAUDE.md „der
                 -- staerkste Kauf-/Chancen-Hinweis" — war zu 46 % allein auf diesen
                 -- Quellen gebaut, und dieselbe Groesse speist die Schwaeche-Achse von
                 -- `market_opportunity`. Ein Bieter waere zu Stellen geschickt worden,
                 -- die voellig normal vergeben, nur eben unterschwellig, wo niemand
                 -- einen Zuschlag veroeffentlicht.
                 --
                 -- Der eigene Status haelt beides auseinander, statt das Unbekannte als
                 -- Befund auszugeben. Wer „erfolglos" auswertet, bekommt ab hier nur
                 -- noch Faelle, bei denen die Quelle einen Zuschlag haette melden koennen.
                 WHEN notice_kind='can' AND quelle_ohne_zuschlagsdaten
                      THEN 'ohne_zuschlagsdaten'
                 WHEN notice_kind='can' AND NOT has_award THEN 'erfolglos'
                 WHEN notice_kind='can' THEN 'unbekannt'
                 -- NEU: auch die AUSSCHREIBUNGSSEITE markieren. Bisher lief der Status nur
                 -- auf Zuschlägen, weshalb 1.816 offene Open-House-Verfahren unerkannt in
                 -- der Akquise standen.
                 WHEN notice_kind IN ('cn','pin') AND {_open_house_sql()} THEN 'open_house'
                 END AS verfahren_status
          FROM q
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM '{out}' WHERE len(quality_flags)>0").fetchone()[0]
    con.close()
    return n


def _open_house_sql(title_col: str = "title", deadline_col: str | None = None) -> str:
    """Erkennt Open-House-Verfahren (§130a/§130c SGB V) am Titel.

    Open House ist kein Wettbewerb: jeder Anbieter kann jederzeit beitreten, es gibt keinen
    Gewinner und keine echte Angebotsfrist. Die „Frist" steht deshalb oft Jahre in der
    Zukunft — gemessen bei den offenen Medizin-Leads Median 273 Tage, Maximum 1.278.
    Ungetrennt schwemmen 1.816 solcher Dauerverfahren die Akquise eines Medizin-Kunden zu
    und verdrängen die ~200 echten Ausschreibungen pro Monat.

    Das Muster steht hier EINMAL, weil es an zwei Stellen gebraucht wird: in `quality`
    (Zuschlagsseite, `verfahren_status`) und in `lead_export` (Ausschreibungsseite). Zwei
    Kopien würden auseinanderlaufen.

    **Zweites, STRUKTURELLES Merkmal (2026-08-13):** eine Frist, die absurd weit in der Zukunft
    liegt. Die Titel-Regel oben ist an deutschem Recht gebaut (§130a SGB V) und greift außerhalb
    Deutschlands nicht. Gemessen in Österreich: von 684 offenen atverg-Verfahren tragen **357
    eine Frist über fünf Jahre hinaus, davon 258 den 1. Januar 2100** — ein Platzhalter der
    Quelle für „kein Ende gesetzt". Die Titel lauten „Achszählsysteme", „Gleis- und
    Weichenschwellen", „Druckdienste": laufende Rahmenvereinbarungen der ÖBB, keine Verfahren,
    auf die man morgen bieten kann. Kein einziges davon enthält ein deutsches Rechtswort.

    Das strukturelle Merkmal ist sprachunabhängig und gilt damit für jedes Land — der Grund,
    warum es hier steht und nicht als AT-Sonderfall irgendwo. Zum Vergleich: in Deutschland
    trifft es 45 von 11.194 offenen (0,4 %), in Österreich 357 von 684 (52 %).

    ``deadline_col`` ist optional, weil nicht jede Aufrufstelle eine Frist-Spalte zur Hand hat.
    Ohne sie bleibt es bei der Titel-Regel — dasselbe Verhalten wie vorher.
    """
    t = f"lower({title_col})"
    titel = (f"({t} LIKE '%rabatt%' OR {t} LIKE '%130a%' OR {t} LIKE '%130c%' "
             f"OR {t} LIKE '%open%house%')")
    if not deadline_col:
        return titel
    # Fünf Jahre ist dieselbe Schwelle wie der A6-Guard in `build_prospective_leads` — sie
    # steht bewusst an beiden Stellen gleich, sonst fällt ein Verfahren zwischen die Regeln.
    return (f"({titel} OR {deadline_col}::DATE > current_date + INTERVAL 5 YEAR)")


def build_review_queue(cfg: Config, country: str = "DE"):
    """Datenqualitäts-Worklist: jede Notice mit Quality-Flag, mit Beleg-Kontext.

    Der Fehler bleibt in der DB (Silber unverändert, Notice zählt normal), wird
    aber sichtbar zum Abarbeiten abgelegt statt weggeworfen — mit den auffälligen
    Rohwerten (Enddatum, Laufzeit, Wert) und dem TED-Link zum Nachsehen. Wer einen
    Fall geprüft/korrigiert hat, kann ihn in einer kuratierten Spalte abhaken
    (später) — die Queue ist die Grundlage, kein Löschknopf.
    """
    con = _db.connect()
    N = cfg.silver_table_glob("notices", country)
    L = cfg.silver_table_glob("lots", country)
    Q = str(cfg.gold_dir / country / "quality.parquet")
    out = cfg.gold_dir / country / "review_queue.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
          WITH dur AS (SELECT notice_id, max(duration_months) dm
                       FROM '{L}' WHERE duration_months>0 GROUP BY 1)
          SELECT n.notice_id, q.quality_flags, n.title AS titel,
                 n.award_date, n.end_date, dur.dm AS duration_months,
                 n.final_value, n.value_currency, n.ted_url
          FROM '{Q}' q
          JOIN '{N}' n ON n.notice_id=q.notice_id
          LEFT JOIN dur ON dur.notice_id=n.notice_id
          -- Nur HARTE, korrigierbare Fehler in die Worklist. Info-/systemische
          -- Flags (korrektur_nicht_zaehlen, Platzhalter-/Verdachts-Werte,
          -- waehrung_fremd) bleiben in quality sichtbar, verstopfen aber nicht
          -- die Abarbeitung.
          WHERE list_has_any(q.quality_flags,
                ['laufzeit_unplausibel','ende_vor_vergabe','datum_start_nach_ende',
                 'wert_absurd_hoch','schaetzwert_negativ','bieterzahl_unplausibel',
                 'frist_vor_pub','datum_absurd'])
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
    by = con.execute(f"""SELECT flag, count(*) FROM (
            SELECT unnest(quality_flags) flag FROM '{out}') GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    con.close()
    return n, dict(by)


def build_contract_chains(cfg: Config, country: str = "DE"):
    """Verketten: ein auslaufender Vertrag → sein Nachfolger (Schwäche 4).

    Über aufgelösten Käufer + CPV-Division + Zeitfenster. NICHT in den Daten
    vorhanden — erschlossen, mit ``match_confidence``. Das ist die Grundlage für
    'in den letzten N Ausschreibungen', und die Konfidenz läuft mit, damit eine
    schwache Vermutung nie als sichere Kette ausgegeben wird.
    """
    con = _db.connect()
    N = cfg.silver_table_glob("notices", country)
    PE = str(cfg.gold_dir / country / "party_entity.parquet")
    # Verträge (CAN) mit Käufer-Entität, CPV-Division, Enddatum.
    # Ein Vertrag je (Käufer, CPV-Klasse, Enddatum): der Gewinner als Amtsinhaber.
    # Feinere CPV (4-stellig statt 2) und genau EIN Nachfolger je Vertrag —
    # sonst explodiert das kartesische Produkt (ein Großkäufer im Bausektor über
    # 10 Jahre ergab 15 Mio Pseudo-Ketten).
    con.execute(f"""
        CREATE TABLE contracts AS
        SELECT n.notice_id, n.award_date, n.end_date,
               substr(n.cpv_main,1,4) AS cpv_class,
               pe.entity_id AS buyer_entity,
               w.entity_id  AS winner_entity
        FROM '{N}' n
        JOIN '{PE}' pe ON pe.notice_id=n.notice_id AND pe.role='buyer'
        LEFT JOIN (SELECT notice_id, min(entity_id) entity_id FROM '{PE}'
                   WHERE role='winner' GROUP BY 1) w ON w.notice_id=n.notice_id
        WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL
          AND n.end_date IS NOT NULL AND pe.entity_id IS NOT NULL
    """)
    # Nächster Nachfolger je Vorgänger: der zeitlich am dichtesten am Enddatum.
    con.execute("""
        CREATE TABLE chains AS
        WITH pairs AS (
          SELECT c1.notice_id AS predecessor, c2.notice_id AS successor,
                 c1.buyer_entity, c1.cpv_class,
                 c1.winner_entity AS incumbent, c2.winner_entity AS new_winner,
                 date_diff('day', c1.end_date, c2.award_date) AS gap_days,
                 row_number() OVER (PARTITION BY c1.notice_id
                                    ORDER BY abs(date_diff('day', c1.end_date, c2.award_date))) AS rn
          FROM contracts c1 JOIN contracts c2
            ON c1.buyer_entity=c2.buyer_entity AND c1.cpv_class=c2.cpv_class
           AND c1.notice_id != c2.notice_id
           AND c2.award_date BETWEEN c1.end_date - INTERVAL 3 MONTH
                                 AND c1.end_date + INTERVAL 18 MONTH
        )
        SELECT predecessor, successor, buyer_entity, cpv_class,
               incumbent, new_winner,
               CASE WHEN incumbent IS NOT NULL AND new_winner IS NOT NULL
                    THEN incumbent = new_winner END AS incumbent_retained,
               gap_days, 0.6 AS match_confidence
        FROM pairs WHERE rn = 1
    """)
    out = cfg.gold_dir / country / "contract_chains.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY (SELECT * FROM chains) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    n = con.execute("SELECT count(*) FROM chains").fetchone()[0]
    con.close()
    return n


# Vertragsart-Klassifikation für die Ketten-Bildung. Einmal-Werke (Hausbau) sind
# keine Kette; Rahmenverträge/Dienstleistungen wiederholen sich und SIND die Kette.
# Stichworte UND die Titel-Stoppwortliste (Ähnlichkeits-Blockung) sind sprach-
# spezifisch und kommen aus dem aktiven Länder-Profil (locales.active()).


def classify_contract(title: str, cpv_main: str, has_renewal: bool):
    """(kind, recurring, chain_worthy) — ist das ein wiederkehrender Vertrag?"""
    from . import entities as ent
    loc = locales.active()
    t = ent.strip_accents((title or "").lower())
    is_works = (cpv_main or "").startswith("45")
    framework = bool(re.search(loc.kind_framework_kw, t))
    recurring_kw = bool(re.search(loc.kind_recurring_kw, t))
    oneoff_kw = bool(re.search(loc.kind_oneoff_kw, t))
    if framework:
        kind = "rahmenvertrag"
    elif recurring_kw:
        kind = "wiederkehrend"
    elif is_works and oneoff_kw:
        kind = "einmal_werk"
    elif is_works:
        kind = "werk_sonstig"
    else:
        kind = "sonstiges"
    recurring = kind in ("rahmenvertrag", "wiederkehrend") or bool(has_renewal)
    # Einmal-Bauwerke ohne jedes Wiederkehr-Signal sind KEINE Kette (User-Vorgabe).
    chain_worthy = not (is_works and not framework and not recurring_kw and not has_renewal)
    return kind, recurring, chain_worthy


def _kind_sql(title_col: str, cpv_col: str) -> str:
    """SQL-Ausdruck für contract_kind — IDENTISCH für Leads und Score-Training,
    damit ein Lead genauso klassifiziert wird wie die gelernten Nachfolgen.
    Stichworte kommen aus dem aktiven Länder-Profil (locales.active())."""
    loc = locales.active()
    return f"""CASE
      WHEN regexp_matches(lower({title_col}), '{loc.kind_framework_kw}') THEN 'rahmenvertrag'
      WHEN regexp_matches(lower({title_col}), '{loc.kind_recurring_kw}') THEN 'wiederkehrend'
      WHEN {cpv_col} LIKE '45%' AND regexp_matches(lower({title_col}),
           '{loc.kind_oneoff_kw}') THEN 'einmal_werk'
      WHEN {cpv_col} LIKE '45%' THEN 'werk_sonstig'
      ELSE 'sonstiges' END"""


def build_contract_successions(cfg: Config, country: str = "DE", min_sim: float = 0.7,
                               min_gap_days: int = 300, max_block: int = 120):
    """Echte Vertrag→Neuvergabe-Ketten über Titel-/Scope-Ähnlichkeit (Schwäche 4, jetzt richtig).

    Die alten ``contract_chains`` (Käufer×CPV) waren ein Katalog dessen, was ein
    Käufer in einer Kategorie vergab — keine echte Nachfolge. Hier: gleicher Käufer,
    ähnlicher Titel (Käufername entfernt), >~1 Jahr Abstand → dieselbe wiederkehrende
    Vergabe. Einmal-Werke (Hausbau) sind ausgeschlossen (``chain_worthy``).

    Blockung nach (Käufer, 4-stellig CPV) hält das paarweise Matching bezahlbar;
    Blöcke über ``max_block`` Verträgen werden übersprungen (gezählt zurückgegeben).
    """
    from . import entities as ent

    con = _db.connect()
    S = cfg.silver_table_glob
    g = cfg.gold_dir / country
    PE = str(g / "party_entity.parquet")
    rows = con.execute(f"""
        WITH bw AS (SELECT notice_id, min(seq) seq FROM '{PE}' WHERE role='buyer'  GROUP BY 1),
             ww AS (SELECT notice_id, min(seq) seq FROM '{PE}' WHERE role='winner' GROUP BY 1),
             ren AS (SELECT notice_id, bool_or(has_renewal) hr FROM '{S("lots", country)}' GROUP BY 1)
        SELECT n.notice_id, bpe.entity_id buyer_id, be.canonical_name buyer_name,
               substr(n.cpv_main,1,4) cpv4, n.cpv_main, n.title, n.award_date,
               wpe.entity_id win_id, we.canonical_name win_name, coalesce(ren.hr,false) hr
        FROM '{S("notices", country)}' n
        JOIN bw ON bw.notice_id=n.notice_id JOIN ww ON ww.notice_id=n.notice_id
        JOIN '{PE}' bpe ON bpe.notice_id=n.notice_id AND bpe.role='buyer'  AND bpe.seq=bw.seq
        JOIN '{PE}' wpe ON wpe.notice_id=n.notice_id AND wpe.role='winner' AND wpe.seq=ww.seq
        JOIN '{g / "entities.parquet"}' be ON be.entity_id=bpe.entity_id
        JOIN '{g / "entities.parquet"}' we ON we.entity_id=wpe.entity_id
        LEFT JOIN ren ON ren.notice_id=n.notice_id
        WHERE n.notice_kind='can' AND n.title IS NOT NULL AND n.award_date IS NOT NULL
          AND n.cpv_main IS NOT NULL AND we.confidence>=0.75
    """).fetchall()

    import re as _re
    from collections import defaultdict
    succ_stop = locales.active().succ_stopwords
    blocks = defaultdict(list)
    for r in rows:
        nid, bid, bname, cpv4, cpvm, title, ad, wid, wname, hr = r
        kind, recurring, worthy = classify_contract(title, cpvm, hr)
        if not worthy:
            continue                                   # Einmal-Werk → keine Kette
        bstop = {w for w in _re.sub(r"[^a-zäöüß ]", " ", ent.strip_accents(str(bname).lower())).split()
                 if len(w) > 3}
        toks = {w for w in _re.sub(r"[^a-zäöüß0-9 ]", " ", ent.strip_accents(title.lower())).split()
                if len(w) > 3 and w not in succ_stop and w not in bstop}
        if len(toks) >= 2:
            blocks[(bid, cpv4)].append((ad, nid, wid, wname, title, kind, recurring, toks))

    edges, skipped = [], 0
    for (bid, cpv4), items in blocks.items():
        if len(items) > max_block:
            skipped += 1
            continue
        items.sort()                                   # nach award_date
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if (b[0] - a[0]).days < min_gap_days:
                    continue
                sim = len(a[7] & b[7]) / len(a[7] | b[7])
                if sim < min_sim:
                    continue
                edges.append((a[1], b[1], bid, cpv4, b[5], b[6],
                              a[2], b[2], (a[2] == b[2]),
                              (b[0] - a[0]).days, round(sim, 3),
                              a[3], b[3], b[4], a[0], b[0]))

    out = g / "contract_successions.parquet"
    _write(con, out, edges,
           "predecessor VARCHAR, successor VARCHAR, buyer_id VARCHAR, cpv_class VARCHAR, "
           "contract_kind VARCHAR, recurring BOOLEAN, incumbent_id VARCHAR, successor_win_id VARCHAR, "
           "incumbent_retained BOOLEAN, gap_days INTEGER, similarity DOUBLE, "
           "incumbent_name VARCHAR, successor_name VARCHAR, successor_title VARCHAR, "
           "predecessor_award DATE, successor_award DATE")
    con.close()
    return len(edges), skipped


def build_leads(cfg: Config, country: str = "DE", reference_date: str | None = None):
    """Auslauf-Radar (#1): kommende Re-Vergaben aus auslaufenden Verträgen.

    Der verkaufbare Liefergegenstand — der Blick nach vorn. Jeder abgeschlossene
    Auftrag (CAN) mit bekanntem Vertragsende erzeugt eine künftige
    Neuausschreibung. Wir listen sie *vor* der Re-Vergabe, mit Amtsinhaber (=
    Gewinner dieses Vertrags), Käuferkontakt, Wert-Band und Angreifbarkeit.

    Anders als ``contract_chains`` wird hier NICHTS gepaart: der Amtsinhaber ist
    der Gewinner genau dieses Vertrags, das Ende sein eigenes ``end_date`` (oder
    ``award_date`` + größte Los-Laufzeit). Deshalb hängt der Radar nicht an der
    erschlossenen Ketten-Logik.

    ``reference_date`` (ISO ``YYYY-MM-DD``) ist der Stichtag „heute"; Leads sind
    Verträge, die an oder nach ihm auslaufen. Als Parameter, nicht ``now()`` im
    Buildcode — reproduzierbar.
    """
    from datetime import date

    ref = reference_date or date.today().isoformat()
    con = _db.connect()
    N = cfg.silver_table_glob("notices", country)
    L = cfg.silver_table_glob("lots", country)
    A = cfg.silver_table_glob("awards", country)
    NP = cfg.silver_table_glob("notice_parties", country)
    g = cfg.gold_dir / country
    PE, EN, Q, DC, DD = (str(g / t) for t in
                         ("party_entity.parquet", "entities.parquet", "quality.parquet",
                          "dim_cpv.parquet", "dim_deflator.parquet"))

    # führende Partei je Rolle (min seq), mit Entität + Kontakt
    con.execute(f"""
        CREATE TABLE buyer AS
        SELECT pe.notice_id, pe.entity_id, e.canonical_name AS buyer_name, e.confidence AS buyer_conf,
               np.town AS buyer_town, np.nuts AS buyer_nuts, np.email AS buyer_email, np.url AS buyer_url
        FROM (SELECT notice_id, min(seq) seq FROM '{PE}' WHERE role='buyer' GROUP BY 1) b
        JOIN '{PE}' pe ON pe.notice_id=b.notice_id AND pe.role='buyer' AND pe.seq=b.seq
        JOIN '{EN}' e ON e.entity_id=pe.entity_id
        LEFT JOIN '{NP}' np ON np.notice_id=pe.notice_id AND np.role='buyer' AND np.seq=pe.seq
    """)
    con.execute(f"""
        CREATE TABLE winner AS
        SELECT pe.notice_id, pe.entity_id AS incumbent_entity, e.canonical_name AS incumbent_name,
               e.confidence AS incumbent_conf, coalesce(np.in_consortium,false) AS in_consortium
        FROM (SELECT notice_id, min(seq) seq FROM '{PE}' WHERE role='winner' GROUP BY 1) w
        JOIN '{PE}' pe ON pe.notice_id=w.notice_id AND pe.role='winner' AND pe.seq=w.seq
        JOIN '{EN}' e ON e.entity_id=pe.entity_id
        LEFT JOIN '{NP}' np ON np.notice_id=pe.notice_id AND np.role='winner' AND np.seq=pe.seq
    """)
    con.execute(f"CREATE TABLE dur AS SELECT notice_id, max(duration_months) dm "
                f"FROM '{L}' WHERE duration_months>0 GROUP BY 1")
    con.execute(f"CREATE TABLE ren AS SELECT notice_id, bool_or(has_renewal) hr, "
                f"max(max_renewals) mr FROM '{L}' GROUP BY 1")
    con.execute(f"CREATE TABLE tnd AS SELECT notice_id, max(num_tenders) nt "
                f"FROM '{A}' WHERE num_tenders>0 GROUP BY 1")

    out = g / "leads.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Vertragsende: eigenes end_date, sonst award_date + größte Los-Laufzeit.
    END = "COALESCE(n.end_date, n.award_date + (CAST(dur.dm AS VARCHAR) || ' months')::INTERVAL)"
    # Wert: Endwert (hart), sonst der Schätzwert der Ausschreibung als Fallback —
    # nur EUR/plausibel, klar als 'geschaetzt' markiert. Strukturschätzung wäre
    # falsche Präzision (gemessen ~70% Fehler), estimated_value dagegen ~12% Fehler.
    # Dritte Stufe seit 2026-08-14: der Schaetzwert aus dem Zwillingssatz. Nationale Portale
    # fuehren ihn deutlich besser als TED (atverg 69,8 % gegen 11,0 %). Gemessen schliesst
    # das 402 oesterreichische Auslauf-Leads, die sonst „unbekannt" blieben — klein, aber der
    # Wert traegt das Gebuehrenband, und „unbekannt" ist dort die teuerste Antwort.
    # Waehrungssperre wie oben: der uebernommene Wert bringt seine Waehrung mit.
    VU = ("COALESCE(q.final_value_clean, "
          "CASE WHEN n.estimated_value BETWEEN 1000 AND 1e9 "
          "     AND (n.value_currency='EUR' OR n.value_currency IS NULL) "
          "     THEN n.estimated_value END, "
          "CASE WHEN try_cast(wrtq.w AS DOUBLE) BETWEEN 1000 AND 1e9 "
          "     AND (wrtq.waehrung='EUR' OR wrtq.waehrung IS NULL) "
          "     THEN try_cast(wrtq.w AS DOUBLE) END)")
    VUR = f"({VU} * dd.factor_to_2020)"
    con.execute(f"""
        CREATE TABLE leads AS
        SELECT
          n.notice_id AS lead_id,
          'auslauf' AS source,
          b.entity_id AS buyer_entity, b.buyer_name, b.buyer_town, b.buyer_nuts,
          b.buyer_email, b.buyer_url, n.ted_url,
          w.incumbent_entity, w.incumbent_name, round(w.incumbent_conf,2) AS incumbent_conf,
          w.in_consortium,
          n.title AS titel, n.description AS beschreibung,
          n.cpv_main, substr(n.cpv_main,1,4) AS cpv_class, dc.branche, dc.sector,
          n.award_date AS vergabe_datum,
          {END}::DATE AS contract_end,
          date_diff('month', DATE '{ref}', {END}) AS months_to_expiry,
          CASE WHEN n.end_date IS NOT NULL THEN 'Vertragsende'
               WHEN dur.dm IS NOT NULL THEN 'aus Laufzeit geschätzt' END AS faellig_basis,
          -- ⚠ VIER FLAGS, NICHT EINS. Bis zum 2026-09-05 stand hier nur
          -- `laufzeit_unplausibel`. `ende_vor_vergabe` (Vertragsende VOR der Vergabe),
          -- `datum_absurd` und `datum_start_nach_ende` sagen dasselbe ueber dieselbe
          -- Zahl — sie machten die Zeitangabe aber nicht unsicher. Gemessen: 2 Leads
          -- gingen deshalb mit `timing_source='actual'` hinaus, also unmarkiert.
          coalesce(NOT list_has_any(q.quality_flags,
                   ['laufzeit_unplausibel','ende_vor_vergabe','datum_absurd',
                    'datum_start_nach_ende']), true) AS termin_plausibel,
          {_kind_sql('n.title', 'n.cpv_main')} AS contract_kind,
          q.final_value_clean AS value_clean,
          {VU} AS value_used,
          CASE WHEN q.final_value_clean IS NOT NULL THEN 'final'
               WHEN {VU} IS NOT NULL THEN 'geschaetzt' ELSE 'unbekannt' END AS value_source,
          round({VUR}) AS value_real_2020,
          CASE
            WHEN {VU} IS NULL THEN 'unbekannt'
            WHEN {VUR} < 50000 THEN '<50k'
            WHEN {VUR} < 200000 THEN '50-200k'
            WHEN {VUR} < 1000000 THEN '200k-1M'
            WHEN {VUR} < 5000000 THEN '1-5M'
            ELSE '>5M' END AS value_band,
          tnd.nt AS num_tenders, (tnd.nt = 1) AS single_bidder,
          coalesce(ren.hr,false) AS has_renewal, ren.mr AS max_renewals,
          (b.buyer_email IS NOT NULL OR b.buyer_url IS NOT NULL) AS reachable,
          round(LEAST(coalesce(w.incumbent_conf,0), coalesce(b.buyer_conf,0)),2) AS source_confidence
        FROM '{N}' n
        JOIN buyer b ON b.notice_id=n.notice_id
        JOIN winner w ON w.notice_id=n.notice_id
        LEFT JOIN dur ON dur.notice_id=n.notice_id
        LEFT JOIN tnd ON tnd.notice_id=n.notice_id
        LEFT JOIN ren ON ren.notice_id=n.notice_id
        LEFT JOIN '{Q}' q ON q.notice_id=n.notice_id
         {_frist_joins_sql(cfg, country)}
        LEFT JOIN '{DD}' dd ON dd.year=n.year
        LEFT JOIN '{DC}' dc ON dc.division=substr(n.cpv_main,1,2)
        WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL
          AND {END} IS NOT NULL AND {END} >= DATE '{ref}'
    """)
    # Lead-Dedup (kein Verlust): Mehrfach-Lose desselben Projekts teilen Käufer +
    # Amtsinhaber + Vertragsende + CPV-Klasse. Alle Zeilen bleiben; das wertvollste
    # Los je Cluster wird als Hauptlos markiert (ist_hauptlos), plus Los-Zahl — der
    # Radar zeigt per Default nur Hauptlose, die anderen sind über ein Flag da.
    key = "buyer_entity, incumbent_entity, contract_end, cpv_class"
    con.execute(f"""
        CREATE TABLE leads_dd AS
        SELECT *,
          count(*) OVER (PARTITION BY {key}) AS lose_im_cluster,
          row_number() OVER (PARTITION BY {key}
                             ORDER BY value_clean DESC NULLS LAST, lead_id) AS _rang
        FROM leads
    """)
    con.execute(f"""
        COPY (SELECT * EXCLUDE (_rang), (_rang = 1) AS ist_hauptlos FROM leads_dd)
        TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute("SELECT count(*) FROM leads").fetchone()[0]
    con.close()
    return n


def build_displaceability(cfg: Config, country: str = "DE", min_support: int = 20):
    """Verdrängbarkeits-Score (#2), auf ECHTEN Nachfolge-Labels basiert.

    Nicht mehr auf der erschlossenen (Käufer×CPV)-Paarung (Rauschen), sondern auf
    ``contract_successions`` — echten Vertrag→Neuvergabe-Ketten über Titel-Scope.
    Achsen: **Vertragsart × Branche × Bieterzahl** (die Vertragsart ist der stärkste
    Treiber — Rahmenverträge ~10% Amtstreue, Dienstleistungen 30–36%). Verdrängbarkeit
    = 1 − Amtstreue. Relatives, aber kreuzvalidiert kalibriertes Ranking.

    Backoff: (Art×Branche×Bieter) → (Art×Branche) → (Art) → global. Schreibt
    ``dim_displaceability`` (kuratierbar) + Score-Spalten auf ``leads``.
    """
    con = _db.connect()
    N = cfg.silver_table_glob("notices", country)
    A = cfg.silver_table_glob("awards", country)
    g = cfg.gold_dir / country
    DC = str(g / "dim_cpv.parquet")
    CS = str(g / "contract_successions.parquet")
    LD = str(g / "leads.parquet")
    BUCKET = ("CASE WHEN num_tenders=1 THEN 'einzel' WHEN num_tenders BETWEEN 2 AND 3 THEN 'wenig' "
              "WHEN num_tenders>=4 THEN 'viel' ELSE 'unbekannt' END")

    # Trainingsdaten: echte Nachfolgen, Merkmale des VORGÄNGERS (was man beim
    # Prognostizieren weiß) — Vertragsart identisch zu den Leads klassifiziert.
    con.execute(f"""
        CREATE TABLE train AS
        WITH tnd AS (SELECT notice_id, max(num_tenders) num_tenders FROM '{A}' WHERE num_tenders>0 GROUP BY 1),
        base AS (
          SELECT {_kind_sql('p.title', 'p.cpv_main')} AS contract_kind,
                 coalesce(dc.branche,'?') AS branche, tnd.num_tenders,
                 (NOT cs.incumbent_retained)::INT AS displaced
          FROM '{CS}' cs
          JOIN '{N}' p ON p.notice_id=cs.predecessor
          LEFT JOIN '{DC}' dc ON dc.division=substr(p.cpv_main,1,2)
          LEFT JOIN tnd ON tnd.notice_id=cs.predecessor
          WHERE cs.incumbent_retained IS NOT NULL
        )
        SELECT contract_kind, branche, {BUCKET} AS bucket, displaced FROM base
    """)
    con.execute("""
        CREATE TABLE model AS
        SELECT 'art_branche_bieter' lvl, contract_kind, branche, bucket, count(*) n, round(avg(displaced),3) displ
          FROM train GROUP BY 1,2,3,4
        UNION ALL SELECT 'art_branche', contract_kind, branche, NULL, count(*), round(avg(displaced),3) FROM train GROUP BY 1,2,3
        UNION ALL SELECT 'art', contract_kind, NULL, NULL, count(*), round(avg(displaced),3) FROM train GROUP BY 1,2
        UNION ALL SELECT 'global', NULL, NULL, NULL, count(*), round(avg(displaced),3) FROM train
    """)
    con.execute(f"COPY (SELECT * FROM model ORDER BY lvl,n DESC) TO '{g / 'dim_displaceability.parquet'}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    con.execute("CREATE TABLE mkbb AS SELECT contract_kind,branche,bucket,n,displ FROM model WHERE lvl='art_branche_bieter'")
    con.execute("CREATE TABLE mkb  AS SELECT contract_kind,branche,n,displ FROM model WHERE lvl='art_branche'")
    con.execute("CREATE TABLE mk   AS SELECT contract_kind,n,displ FROM model WHERE lvl='art'")
    gdispl, gn = con.execute("SELECT displ,n FROM model WHERE lvl='global'").fetchone()
    con.execute(f"""
        CREATE TABLE scored AS
        WITH l AS (SELECT *, {BUCKET} AS bucket, coalesce(branche,'?') AS branche_j FROM '{LD}')
        SELECT l.* EXCLUDE (bucket, branche_j),
          -- Einmal-Werke sind keine wiederkehrenden Verträge → kein Verdrängungs-
          -- signal (und kein Training). Ehrlich NICHT bewerten statt Rauschen ausgeben.
          CASE WHEN l.contract_kind IN ('einmal_werk','werk_sonstig') THEN NULL
               WHEN kbb.n>={min_support} THEN kbb.displ
               WHEN kb.n>={min_support} THEN kb.displ
               WHEN mk.n>={min_support} THEN mk.displ ELSE {gdispl} END AS displaceability,
          CASE WHEN l.contract_kind IN ('einmal_werk','werk_sonstig') THEN 'nicht_kettenrelevant'
               WHEN kbb.n>={min_support} THEN 'art_branche_bieter'
               WHEN kb.n>={min_support} THEN 'art_branche'
               WHEN mk.n>={min_support} THEN 'art' ELSE 'global' END AS score_basis,
          CASE WHEN l.contract_kind IN ('einmal_werk','werk_sonstig') THEN 0
               WHEN kbb.n>={min_support} THEN kbb.n
               WHEN kb.n>={min_support} THEN kb.n
               WHEN mk.n>={min_support} THEN mk.n ELSE {gn} END AS score_support,
          l.bucket AS bidder_bucket
        FROM l
        LEFT JOIN mkbb kbb ON kbb.contract_kind=l.contract_kind AND kbb.branche=l.branche_j AND kbb.bucket=l.bucket
        LEFT JOIN mkb  kb  ON kb.contract_kind=l.contract_kind AND kb.branche=l.branche_j
        LEFT JOIN mk   mk  ON mk.contract_kind=l.contract_kind
    """)
    con.execute("""
        CREATE TABLE leads2 AS
        SELECT * EXCLUDE (displaceability),
          round(displaceability,3) AS displaceability,
          CASE WHEN displaceability IS NULL THEN 'n/a (Einmal-Werk)'
               WHEN displaceability>=0.80 THEN 'hoch'
               WHEN displaceability>=0.60 THEN 'mittel' ELSE 'niedrig' END AS displ_band,
          CASE WHEN contract_kind IN ('einmal_werk','werk_sonstig')
                    THEN 'Einmal-Werk (kein Wechsel-Signal)'
          ELSE concat(
            CASE contract_kind WHEN 'rahmenvertrag' THEN 'Rahmenvertrag'
                 WHEN 'wiederkehrend' THEN 'wiederkehrend' ELSE 'sonstiges' END,
            ' · ',
            CASE bidder_bucket WHEN 'einzel' THEN 'Einzelbieter' WHEN 'wenig' THEN 'wenig Bieter'
                 WHEN 'viel' THEN 'viele Bieter' ELSE 'Bieter unbekannt' END,
            ' · ', coalesce(branche,'?')) END AS score_driver
        FROM scored
    """)
    con.execute(f"COPY (SELECT * FROM leads2) TO '{LD}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    n_model = con.execute("SELECT count(*) FROM model").fetchone()[0]
    n_leads = con.execute("SELECT count(*) FROM leads2").fetchone()[0]
    con.close()
    return n_model, n_leads


# --- Entitäten mit Konfidenz -------------------------------------------------

class Method:
    """Wie eine Entität aufgelöst wurde — Teil des Schlüssels, nicht Metadaten."""

    HR_EXACT = "handelsregister_exakt"       # normalisierter Name deckungsgleich
    HR_FUZZY_PLZ = "handelsregister_fuzzy_plz"   # ähnlich + PLZ bestätigt
    TED_NATIONAL_ID = "ted_nationalid"       # NATIONALID/CompanyID direkt aus TED
    NAME_ONLY = "nur_name"                    # kein Register-Treffer, Name als Schlüssel
    UNRESOLVED = "nicht_aufgeloest"           # Person, Bietergemeinschaft, ausländisch


# Konfidenz je Methode. Bewusst konservativ — eine 90%-Aussage darf nicht auf
# einem 0.7-Match stehen, ohne dass die 0.7 sichtbar mitläuft.
CONFIDENCE = {
    Method.TED_NATIONAL_ID: 1.0,
    Method.HR_EXACT: 0.9,
    Method.HR_FUZZY_PLZ: 0.75,
    Method.NAME_ONLY: 0.4,
    Method.UNRESOLVED: 0.0,
}

# Stufe-2-Schwelle: token-Jaccard-Ähnlichkeit zweier kanonisierter Namen, ab der
# ein PLZ-belegter Fuzzy-Match akzeptiert wird. Konservativ (0.7): bei gleicher
# PLZ genügt hohe Namensnähe, generische Ein-Wort-Namen fallen unter die Schwelle.
HR_FUZZY_MIN_SIM = 0.7


def _hr_token_sim(a: str, b: str) -> float:
    """Jaccard über signifikante Tokens (>2 Zeichen) zweier kanonisierter Namen.

    Token-Menge statt Reihenfolge: 'muller bau' und 'bau muller' sind identisch.
    Ein-Token-Namen (nur ein signifikantes Wort) geben nie 1.0 gegen einen
    längeren Namen — so rutscht 'stadt' nicht auf 'stadtwerke ... gmbh'.
    """
    ta = {t for t in a.split() if len(t) > 2}
    tb = {t for t in b.split() if len(t) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class _HRLookup(dict):
    """Exakt-Match; bei Fehltreffer PLZ-belegter Fuzzy-Match (Stufe 2).

    Der Fuzzy-Zweig ist bewusst eng: Kandidaten sind NUR HR-Einträge mit
    derselben PLZ (kleiner Block, starker Beleg), und der Name muss token-
    ähnlich genug sein (``HR_FUZZY_MIN_SIM``). Ohne PLZ kein Fuzzy — dann wäre es
    ein Ratespiel. Gleiche PLZ + token-gleicher Name = praktisch dieselbe Firma.

    Modul-Ebene (nicht Closure), damit Tests sie mit einem Mini-Index bauen und
    die Schwelle ohne die 5,5-Mio-Datei prüfen können.
    """

    _by_plz: dict[str, list[str]]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._by_plz = {}

    def get(self, norm, plz=None):
        hit = dict.get(self, norm)
        if hit is not None:
            return hit, False                       # exakter Namensmatch
        if not plz or not norm:
            return None, False                      # ohne PLZ kein sicherer Fuzzy
        best_rec, best_sim = None, 0.0
        for cnorm in self._by_plz.get(plz, ()):
            s = _hr_token_sim(norm, cnorm)
            if s > best_sim:
                best_rec, best_sim = dict.get(self, cnorm), s
        if best_rec is not None and best_sim >= HR_FUZZY_MIN_SIM:
            return best_rec, True                   # PLZ-belegter Fuzzy-Treffer
        return None, False


@dataclass
class ResolvedEntity:
    """Ein aufgelöster Käufer oder Lieferant — mit Beweislast.

    ``entity_id`` ist der kanonische Schlüssel. ``confidence`` und ``method``
    reisen mit: Wer auf dieser Entität aggregiert, sieht, wie belastbar die
    Zusammenfassung ist. Ein Fremdschlüssel ohne Konfidenz wäre eine Lüge über
    Daten, die zu 37 % nicht sauber auflösen.
    """

    entity_id: str
    canonical_name: str
    method: str
    confidence: float
    national_id: str | None = None
    source_names: tuple[str, ...] = ()
    norm: str = ""                    # kanonisierter Name — Brücke für die Konsolidierung

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.75


def build_hr_index(path: str | None = None, fuzzy: bool = False) -> dict:
    """Firmenregister-Extrakt → {normalisierter Name: (Reg-Nr, offizieller Name, PLZ)}.

    Für die Namens-Auflösung der Lieferanten ohne national_id. Ein 5,3-Mio-
    Zeilen-Scan (~60s), einmal je Lauf. Rückgabe passt zur hr_lookup-Signatur
    (normalized, plz) -> (record|None, is_fuzzy).

    ``path`` default = Register des aktiven Länder-Profils. Hat das Profil keins
    (register_path=None, z. B. FR-Stub), gibt es einen leeren Index — die Auflösung
    fällt sauber auf reine Namens-Konfidenz zurück, ohne Fehler.

    ``fuzzy`` schaltet den PLZ-belegten Fuzzy-Zweig frei — **Default aus**. Der
    Trockenlauf (2026-07-19) hat gemessen: bei Schwelle 0.7 ~24 % Fehl-Merges
    (Behörde vs. ihre GmbH, Konzern vs. Tochter, Akronym-Kollision) bei winzigem
    Ertrag (1.428 Entitäten). Das verletzt „0 Fehl-Merges", darum bleibt der Zweig
    aus, bis die Präzision (engere Schwelle / mehr Belege) belastbar ist. Ohne
    ``fuzzy`` bleibt ``_by_plz`` leer → ``_HRLookup.get`` findet nie einen Fuzzy-
    Kandidaten und liefert exakt das bisherige Exakt-Match-Verhalten.
    """
    import bz2, json, os, re
    from . import entities as ent
    if path is None:
        path = locales.active().register_path
    if not path:
        return {}   # kein Register → leerer Index; build_entities fällt auf Namens-Konfidenz zurück

    # Cache: die Register-Datei ist statisch, der geparste Index bei jedem Lauf identisch.
    # normalize_company über 5,5M Zeilen kostet ~2 Min — einmal parsen, dann aus Parquet
    # laden (mtime-invalidiert). Nur ohne fuzzy, weil der Fuzzy-Zweig ``by_plz`` braucht.
    cache = os.path.join("data", "cache", "hr_index.parquet")
    if not fuzzy and os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
        lk = _HRLookup()
        for norm, nr, name, plz in _db.connect().execute(
                f"SELECT norm, nr, name, plz FROM read_parquet('{cache}')").fetchall():
            lk[norm] = {"nr": nr, "name": name, "plz": plz}
        lk._by_plz = {}
        return lk

    index: dict[str, dict] = {}
    by_plz: dict[str, list[str]] = {}          # PLZ → normalisierte Namen (Stufe-2-Blocking)
    with bz2.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            name = d.get("name")
            if not name:
                continue
            m = re.search(r"\b(\d{5})\b", d.get("registered_address") or "")
            record = {"nr": d.get("company_number"), "name": name,
                      "plz": m.group(1) if m else None}
            # Aktuellen UND frühere Namen indizieren: eine umbenannte Firma
            # bleibt so über die Umbenennung hinweg auf dieselbe HRB auflösbar.
            candidates = [name]
            for prev in (d.get("previous_names") or []):
                candidates.append(prev.get("company_name") if isinstance(prev, dict) else prev)
            for cand in candidates:
                norm = ent.normalize_company(cand) if cand else None
                if norm and norm not in index:
                    index[norm] = record
                    if fuzzy and record["plz"]:      # Blocking nur bauen, wenn Fuzzy aktiv
                        by_plz.setdefault(record["plz"], []).append(norm)

    lk = _HRLookup(); lk.update(index); lk._by_plz = by_plz
    if not fuzzy:      # Cache für den nächsten Lauf schreiben (nur der reine Index)
        import pandas as pd
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        df = pd.DataFrame(((k, v["nr"], v["name"], v["plz"]) for k, v in index.items()),
                          columns=["norm", "nr", "name", "plz"])
        con = _db.connect(); con.register("df", df)
        con.execute(f"COPY df TO '{cache}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return lk


def build_entities(cfg: Config, country: str = "DE", hr_index: dict | None = None):
    """Materialisiere Käufer und Lieferanten als aufgelöste Entitäten.

    Zwei Ebenen der Verlässlichkeit, ohne dass eine geratene sich als sichere
    tarnt: die ``national_id`` (VAT/HRB, in eForms zu 85% vorhanden) ist der
    stabile Schlüssel; wo sie fehlt, greift die Namens-Auflösung mit Konfidenz.

    Schreibt:
      * ``entities``     — entity_id, canonical_name, national_id, method, confidence
      * ``party_entity`` — (notice_id, role, seq) → entity_id, damit notice_parties
                            joinbar wird
    """

    con = _db.connect()
    parties = con.execute(f"""
        SELECT notice_id, role, seq, name, national_id, postal_code, nuts, town
        FROM '{cfg.silver_table_glob("notice_parties", country)}'
        WHERE name IS NOT NULL
    """).fetchall()

    entity_of: dict[str, ResolvedEntity] = {}
    plz_of: dict[str, set[str]] = {}
    leitweg_of: dict[str, set[str]] = {}     # entity_id → Leitweg-ID(s), für den Vergabestellen-Anker
    vat_of: dict[str, set[str]] = {}         # entity_id → USt-IdNr(n), zweiter Vergabestellen-Anker
    # NUTS3 als ZWEITBESTER Ortsbeleg. Die PLZ ist der scharfe Beleg, aber sie fehlt bei
    # vielen oeffentlichen Stellen; NUTS3 (Kreisebene) traegt dieselbe Aussage groeber und
    # rettet genau die Faelle, in denen sonst gar kein Beleg vorliegt. Nie GEGEN eine PLZ.
    nuts_of: dict[str, set[str]] = {}
    # Ortsname als DRITTER, schwaechster Beleg — nur wo PLZ und NUTS beide fehlen.
    ort_of: dict[str, set[str]] = {}
    links = []
    # In-Run-Memoisierung: resolve_supplier ist rein in (name, national_id, plz, hr_index),
    # und 84 % der 3,7M Parteien sind Wiederholungen (nur 592k distinkte Tupel). Reihenfolge
    # und setdefault-First bleiben unverändert → bit-identisch. (Kein Cross-Lauf-Cache — der
    # brachte nichts, s. Historie: der Flaschenhals war _write, nicht die Auflösung.)
    memo: dict[tuple, ResolvedEntity] = {}
    from . import entities as _entities
    for notice_id, role, seq, name, national_id, plz, nuts, town in parties:
        key = (name, national_id, plz)
        resolved = memo.get(key)
        if resolved is None:
            resolved = resolve_supplier(name, national_id=national_id, postal_code=plz,
                                        hr_lookup=hr_index.get if hr_index else None)
            memo[key] = resolved
        entity_of.setdefault(resolved.entity_id, resolved)
        if plz and plz.strip():
            plz_of.setdefault(resolved.entity_id, set()).add(plz.strip())
        if nuts and nuts.strip():
            nuts_of.setdefault(resolved.entity_id, set()).add(nuts.strip()[:5])   # NUTS3
        if town and town.strip():
            # Gefaltet wie die Namen (ae/oe/ue), sonst spaltet „Muenchen"/„München" den Beleg.
            o = re.sub(r"[^a-z]", "", _entities.strip_accents(town.lower()))
            if o:
                ort_of.setdefault(resolved.entity_id, set()).add(o)
        # Käufer-IDs festhalten (resolve_supplier verwirft sie für PUBLIC) — Anker s. u.
        if role == "buyer" and national_id:
            nk = normalize_national_id(national_id)
            if nk and nk.startswith("leitweg:"):
                leitweg_of.setdefault(resolved.entity_id, set()).add(nk)
            elif nk and nk.startswith("vat:"):
                vat_of.setdefault(resolved.entity_id, set()).add(nk)
        links.append((notice_id, role, seq, resolved.entity_id))

    # Konsolidierung: eine nur-Name-Entität und eine Register-/ID-Entität mit
    # DEMSELBEN kanonisierten Namen sind oft dieselbe Firma über die Schema-
    # Generationsgrenze (2018 ohne, 2024 mit national_id). Verschmelzen — aber
    # NUR mit Beleg: identische PLZ. Ohne PLZ-Beleg wäre es ein Ratespiel (zwei
    # Firmen können Namen teilen), darum landet Unbelegtes als Kandidat in der
    # Review-Datei statt im Bestand. Konservativ: 0 Fehl-Merges, Rest sichtbar.
    merge_map, flagged = _consolidate_by_national_id(entity_of, plz_of)

    # ── GEPRUEFTE ZUSAMMENFUEHRUNGEN AUS DER SCHIEDSKARTE ────────────────────────────────
    #
    # Die Handregeln oben entscheiden nur, wo der Beleg eindeutig ist; alles andere landet in
    # `entity_merge_candidates`. Am 2026-08-18 waren das 6.971 Paare, die seit Monaten lagen.
    # Sie sind seitdem durch vier Instanzen gegangen — zwei Sprachmodelle, die uebereinstimmen
    # mussten, eine Datengegenprobe und das Impressum als quellenfremder Beleg — und was
    # dabei uebrig blieb, steht in `entity_merge_map.parquet` (10.018 Entitaeten, 3.967 Ziele).
    #
    # ⚠ DIE DATEI IST OPTIONAL UND HAT VORRANG. Optional, damit ein frisches Gold ohne sie
    # baut wie bisher. Vorrang, weil sie mehr weiss als die Regel: die Regel hat diese Faelle
    # ausdruecklich NICHT entschieden. Wer die Zusammenfuehrung rueckgaengig machen will,
    # loescht die Datei und laesst Gold neu laufen — deshalb wird hier nichts ueberschrieben,
    # was die Regel selbst entschieden hat.
    _karte = cfg.gold_dir / country / "entity_merge_map.parquet"
    if _karte.exists():
        import duckdb as _dd
        _uebernommen = 0
        for _alt, _neu in _dd.connect().execute(
                f"SELECT entity_id, ziel_entity_id FROM '{_karte.as_posix()}'").fetchall():
            # Nur was es hier auch gibt, und nur was die Regel offengelassen hat.
            if _alt in entity_of and _neu in entity_of and _alt not in merge_map:
                merge_map[_alt] = _neu
                _uebernommen += 1
        print(f"gold {country}: {_uebernommen:,} Zusammenfuehrungen aus entity_merge_map "
              f"uebernommen (geprueft, s. scripts/entity_adjudicate.py)")
    # Leitweg-Anker: öffentliche Vergabestellen über die bundesweit eindeutige Leitweg-ID
    # verschmelzen — der autoritative Schlüssel, den resolve_supplier für PUBLIC verwirft.
    # Fängt gerade die NICHT-kommunalen Stellen (Land/Bund/Zweckverbände) + Namens-Fragmente
    # ohne Gemeinde-Token, die der Municipality-Merge unten nicht sieht.
    leitweg_merges, leitweg_dropped = _consolidate_by_leitweg(entity_of, leitweg_of, set(merge_map))
    merge_map.update(leitweg_merges)
    if leitweg_dropped:
        top = ", ".join(f"{lw.split(':',1)[1]}({n})" for lw, n in leitweg_dropped[:3])
        print(f"  leitweg     : {len(leitweg_merges)} Fragmente über Leitweg-ID gemerged; "
              f"{len(leitweg_dropped)} generische Platzhalter ausgeschlossen ({top})")
    # USt-IdNr-Anker: zweiter autoritativer Vergabestellen-Schlüssel (dieselbe Kurzschluss-Lücke wie
    # Leitweg). Token-Guard gegen geteilte Verwaltungsgemeinschafts-VATs (fremde Gemeinden, eine VAT).
    vat_merges, vat_skipped = _consolidate_by_vat(entity_of, vat_of, set(merge_map))
    merge_map.update(vat_merges)
    if vat_merges or vat_skipped:
        print(f"  vat         : {len(vat_merges)} Fragmente über USt-IdNr gemerged; "
              f"{vat_skipped} geteilte VATs (kein gemeinsamer Namens-Token) übersprungen")
    # Kuratierte Aliase (belegte Umbenennungen/Fragmente, z. B. DB Netz→DB InfraGO).
    # Identitäts-Merge, KEIN Namensstamm-Raten — nur was in der CSV steht (human-verifiziert).
    merge_map.update(_load_entity_aliases(cfg, country, entity_of))
    # Clean-Name-Merge (PLZ-gegated): nur-Name-Fragmente öffentlicher Stellen ohne Register-Anker
    # (Casing-/Vertretungs-Dubletten) zusammenführen. Gemessen ~8 % weniger Vergabestellen-Entities.
    merge_map.update(_consolidate_by_shared_name_geo(entity_of, plz_of, nuts_of, ort_of, set(merge_map)))
    # Municipality-Merge (AGS-artig): kommunale Vergabestellen über kanonischen Gemeinde-Schlüssel
    # (Behörden-Typ + Gemeinde + geonames-Kreis) — merged „Stadt X"=„Landeshauptstadt X"=„STADT X,
    # Amt Y". Adressiert die Behörden-Fragmentierung, die Register nicht auflöst (~21 % der Buyer).
    if country == "DE":
        merge_map.update(_consolidate_by_municipality(
            entity_of, plz_of, _load_plz_kreis(cfg), set(merge_map)))
    # Merge-Ketten path-komprimieren: ein Ziel eines Passes kann Quelle eines späteren sein
    # (z. B. Leitweg-Ziel → Municipality-Rep). Ohne Kompression zeigt der Link auf ein entferntes
    # Zwischenziel → Waise. Jeder Quell-Key wird auf sein ENDgültiges Ziel gezogen (Zyklen-sicher).
    merge_map = _compress_merge_map(merge_map)
    for old_id, new_id in merge_map.items():
        src = entity_of.pop(old_id, None)
        tgt = entity_of.get(new_id)
        if src is not None and tgt is not None:
            tgt.source_names = tuple(sorted(set(tgt.source_names) | set(src.source_names)))
    links = [(nid, role, seq, merge_map.get(eid, eid)) for (nid, role, seq, eid) in links]

    # Anzeige-Namen bereinigen (NACH aller Resolution/Merging → Matching unberührt): generische
    # Hoheits-Präfixe auf die vertretene Stelle auflösen (bundesweit ~15k „Bundesrepublik
    # Deutschland, vertreten durch …"), KOMPLETT-GROSS auf Titel-Schreibung (30 % der Namen).
    from . import names
    ent_rows = [(e.entity_id, names.clean_display_name(e.canonical_name), e.national_id,
                 e.method, e.confidence)
                for e in entity_of.values()]
    _write(con, cfg.gold_dir / country / "entities.parquet", ent_rows,
           "entity_id VARCHAR, canonical_name VARCHAR, national_id VARCHAR, "
           "method VARCHAR, confidence DOUBLE")
    _write(con, cfg.gold_dir / country / "party_entity.parquet", links,
           "notice_id VARCHAR, role VARCHAR, seq SMALLINT, entity_id VARCHAR")
    _write(con, cfg.gold_dir / country / "entity_merge_candidates.parquet", flagged,
           "norm VARCHAR, name_only_entity VARCHAR, candidate_entity VARCHAR, reason VARCHAR")
    con.close()
    return len(entity_of), len(links)


def _load_entity_aliases(cfg: Config, country: str, entity_of: dict) -> dict:
    """Kuratierte Identitäts-Aliase aus ``curated/<country>_entity_aliases.csv``.

    CSV: ``alias_name, canonical_name`` (+ freie ``grund``-Spalte). Beide Namen werden
    über ``normalize_company`` auf ihre Entität aufgelöst; der Alias wird in die
    kanonische (bevorzugt register-/id-getragene) Entität gemerged. Nur belegte
    Einzelfälle (Umbenennung, Fragment) — kein Namensstamm-Automatismus.
    Gibt ``{alias_entity_id: canonical_entity_id}`` zurück.
    """
    # Repo-Pfad zuerst: `data/` ist ein Symlink auf die externe Platte und damit NICHT
    # versioniert. Diese Datei traegt recherchierte Handarbeit (die DB-Netz/InfraGO-Zeile
    # kostete eine HRB-Recherche) und gehoert deshalb ins Repo. Der alte Pfad bleibt als
    # Rueckfallebene, damit bestehende Installationen weiterlaufen.
    import csv
    from . import entities as ent

    path = cfg.data_dir / "curated" / f"{country}_entity_aliases.csv"
    if not path.exists():
        return {}
    from collections import defaultdict
    id_methods = {Method.HR_EXACT, Method.HR_FUZZY_PLZ, Method.TED_NATIONAL_ID}
    ids_by_norm: dict[str, list] = defaultdict(list)   # ALLE Entitäten je Norm (Varianten)
    canon_by_norm: dict[str, str] = {}                 # kanonisches Ziel je Norm (id-getragen bevorzugt)
    for e in entity_of.values():
        n = ent.normalize_company(e.canonical_name or "")
        if not n:
            continue
        ids_by_norm[n].append(e.entity_id)
        if n not in canon_by_norm or e.method in id_methods:
            canon_by_norm[n] = e.entity_id
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            target = canon_by_norm.get(ent.normalize_company(row.get("canonical_name", "")))
            if not target:
                continue
            for aid in ids_by_norm.get(ent.normalize_company(row.get("alias_name", "")), []):
                if aid != target:
                    out[aid] = target          # jede Alias-Variante → kanonische Entität
    return out


def _compress_merge_map(merge_map: dict) -> dict:
    """Merge-Ketten auflösen: jeder Quell-Key → ENDgültiges Ziel (kein Key mehr).

    Mehrere Konsolidierungs-Pässe können verketten (A→B in Pass 1, B→C in Pass 2). Ein einstufiges
    ``get`` würde Links auf das entfernte Zwischenziel B zeigen lassen → Waisen. Path-Kompression
    macht daraus A→C, B→C. Zyklen-sicher (``seen`` bricht ab; ein Zyklus wäre ein Logikfehler,
    darf aber nicht aufhängen)."""
    def final(eid):
        seen = set()
        while eid in merge_map and eid not in seen:
            seen.add(eid)
            eid = merge_map[eid]
        return eid
    return {old: final(old) for old in merge_map}


def _consolidate_by_national_id(entity_of: dict, plz_of: dict):
    """Nur-Name-Entitäten in ihre belegte Register-/ID-Entität verschmelzen.

    Gruppiert nach kanonisiertem Namen (``norm``). In einer Gruppe mit **genau
    einer** eindeutigen ID-tragenden Entität verschmilzt eine nur-Name-Entität
    nur, wenn sie mit dieser eine PLZ teilt (Beleg). Mehrdeutige (>1 ID) oder
    unbelegte Fälle werden geflaggt, nicht verschmolzen.

    Gibt ``(merge_map, flagged)`` zurück: ``merge_map`` alt→neu für die sicheren
    Merges, ``flagged`` die Kandidaten für die Review-Datei.
    """
    from collections import defaultdict

    id_methods = {Method.HR_EXACT, Method.HR_FUZZY_PLZ, Method.TED_NATIONAL_ID}
    by_norm: dict[str, list] = defaultdict(list)
    for e in entity_of.values():
        if e.norm:
            by_norm[e.norm].append(e)

    merge_map: dict[str, str] = {}
    flagged: list[tuple] = []
    for norm, group in by_norm.items():
        id_entities = [e for e in group if e.method in id_methods]
        name_only = [e for e in group if e.method == Method.NAME_ONLY]
        if not name_only or not id_entities:
            continue
        id_keys = {e.entity_id for e in id_entities}
        if len(id_keys) > 1:
            cand = ";".join(sorted(id_keys))
            for e in name_only:
                flagged.append((norm, e.entity_id, cand, "mehrdeutige_id"))
            continue
        target = id_entities[0]
        tplz = plz_of.get(target.entity_id, set())
        for e in name_only:
            if tplz and (plz_of.get(e.entity_id, set()) & tplz):
                merge_map[e.entity_id] = target.entity_id      # PLZ-Beleg → sicher mergen
            else:
                flagged.append((norm, e.entity_id, target.entity_id, "kein_plz_beleg"))
    return merge_map, flagged


# Oberhalb dieser Namensvielfalt ist eine Leitweg-ID ein generischer Platzhalter, kein Anker:
# „0204:991-1405-10" trägt 1.789 völlig verschiedene Käufer (Nationalpark, Bundeswehr, Städte …) —
# ein Portal-Default. Danach ein klarer Abgrund (nächstgrößter legitimer Cluster ~38 Namen).
_LEITWEG_GENERIC_MAX_NAMES = 80


def _consolidate_by_leitweg(entity_of: dict, leitweg_of: dict, already: set):
    """Öffentliche Vergabestellen über die bundesweit eindeutige **Leitweg-ID** zusammenführen.

    Die Leitweg-ID ist der autoritative Schlüssel für öffentliche Stellen (im Handelsregister
    stehen sie nicht). ``resolve_supplier`` verwirft sie aber für PUBLIC/Person/Konsortium, weil
    diese vor dem ``national_id``-Zweig zurückkehren — genau die Stellen, die eine Leitweg-ID
    tragen. Dieser Pass holt sie als ANKER zurück: Entitäten mit derselben (nicht-generischen)
    Leitweg-ID sind dieselbe Vergabestelle und werden verschmolzen.

    Rein **additiv**: der Name bleibt Fallback für Notices ohne Leitweg (Alt-Jahre vor eForms),
    daher kein Zeitachsen-Split. Guards gegen Fehl-Merges:
      1. **generische Platzhalter** (>``_LEITWEG_GENERIC_MAX_NAMES`` distinkte Namen) raus;
      2. **mehrdeutige** Entitäten (mehr als eine echte Leitweg-ID) übersprungen.
    Eine register-getragene Entität im Cluster wird bevorzugtes Ziel (behält ihre ``national_id``).

    Gibt ``(merge_map, dropped_generic)`` zurück — Letzteres für die Protokollierung (kein
    stiller Verwurf).
    """
    from collections import defaultdict

    id_methods = {Method.HR_EXACT, Method.HR_FUZZY_PLZ, Method.TED_NATIONAL_ID}

    # 1. Namensvielfalt je Leitweg über ALLE Entitäten → generische Platzhalter erkennen.
    norms_per_lw: dict[str, set] = defaultdict(set)
    for eid, keys in leitweg_of.items():
        e = entity_of.get(eid)
        if e is None or not e.norm:
            continue
        for lw in keys:
            norms_per_lw[lw].add(e.norm)
    generic = {lw for lw, ns in norms_per_lw.items() if len(ns) > _LEITWEG_GENERIC_MAX_NAMES}

    # 2. Entität → GENAU EINE nicht-generische Leitweg-ID (sonst mehrdeutig → überspringen).
    by_leitweg: dict[str, list] = defaultdict(list)
    for eid, keys in leitweg_of.items():
        if eid in already:
            continue
        real = [lw for lw in keys if lw not in generic]
        if len(real) != 1:
            continue
        e = entity_of.get(eid)
        if e is not None:
            by_leitweg[real[0]].append(e)

    # 3. Je Leitweg-Cluster mit ≥2 Entitäten verschmelzen; register-getragenes Ziel bevorzugt.
    merge_map: dict[str, str] = {}
    for lw, members in by_leitweg.items():
        if len(members) < 2:
            continue
        id_members = [e for e in members if e.method in id_methods]
        target = min(id_members or members, key=lambda e: e.entity_id)
        for e in members:
            if e.entity_id != target.entity_id:
                merge_map[e.entity_id] = target.entity_id
    dropped_generic = sorted(((lw, len(norms_per_lw[lw])) for lw in generic), key=lambda x: -x[1])
    return merge_map, dropped_generic


# Namens-Stopwörter für den USt-IdNr-Token-Guard: zu generisch, um zwei Vergabestellen als „dieselbe"
# zu belegen. Ohne Guard verschmölze eine geteilte Verwaltungsgemeinschafts-VAT fremde Gemeinden
# (DE309506861 = Bous/Eurasburg/Langerringen). Der geteilte SIGNIFIKANTE Token trägt den Beleg.
_VAT_STOP = frozenset({
    "stadt", "gemeinde", "markt", "landkreis", "kreis", "der", "die", "das", "und", "fuer",
    "gmbh", "amt", "bundesrepublik", "deutschland", "landeshauptstadt", "vertreten", "durch",
    "eigenbetrieb", "stadtverwaltung", "verbandsgemeinde", "samtgemeinde", "anstalt", "koerperschaft",
})


def _vat_tokens(norm: str) -> set:
    """Signifikante Namens-Token (≥4 Zeichen, ohne Stopwörter) aus dem kanonisierten Namen."""
    return {t for t in re.findall(r"[a-z0-9]{4,}", (norm or "")) if t not in _VAT_STOP}


def _consolidate_by_vat(entity_of: dict, vat_of: dict, already: set):
    """Öffentliche Vergabestellen über die **USt-IdNr** ankern — dieselbe Kurzschluss-Lücke wie
    bei der Leitweg-ID (``resolve_supplier`` verwirft die VAT für PUBLIC/Person/Konsortium).

    **Token-Guard statt Generik-Schwelle:** Eine USt-IdNr ist nicht immer eindeutig einer Stelle
    zugeordnet — Verwaltungsgemeinschaften teilen sich eine (``DE309506861`` = Bous/Eurasburg/
    Langerringen). Deshalb wird ein VAT-Cluster nur verschmolzen, wenn **alle** Mitglieder einen
    gemeinsamen signifikanten Namens-Token teilen (Heidelberg-Varianten ja, fremde Gemeinden nein).
    Wieder rein additiv; mehrdeutige Entitäten (>1 VAT) übersprungen; register-Ziel bevorzugt.

    Gibt ``(merge_map, skipped_shared)`` zurück — Letzteres = wegen fehlendem Token nicht gemergte
    (geteilte) VATs, für die Protokollierung.
    """
    from collections import defaultdict

    id_methods = {Method.HR_EXACT, Method.HR_FUZZY_PLZ, Method.TED_NATIONAL_ID}
    by_vat: dict[str, list] = defaultdict(list)
    for eid, keys in vat_of.items():
        if eid in already or len(keys) != 1:
            continue
        e = entity_of.get(eid)
        if e is not None:
            by_vat[next(iter(keys))].append(e)

    merge_map: dict[str, str] = {}
    skipped_shared = 0
    for vat, members in by_vat.items():
        if len(members) < 2:
            continue
        common = None
        for e in members:
            common = _vat_tokens(e.norm) if common is None else (common & _vat_tokens(e.norm))
            if not common:
                break
        if not common:
            skipped_shared += 1          # geteilte VG-VAT → kein Beleg, nicht mergen
            continue
        id_members = [e for e in members if e.method in id_methods]
        target = min(id_members or members, key=lambda e: e.entity_id)
        # Anzeige-Label: die knappste Basis-Behördenbezeichnung im Cluster (wenigste signifikante
        # Token) — damit ein register-getragener VERWALTER (Treuhänder wie DSK, der die VAT der
        # Kommune administriert) nicht zum Namen der Behörde wird („Stadt Heidelberg" statt „DSK…").
        # entity_id/national_id des Ziels bleiben unangetastet (die VAT ist ohnehin cluster-spezifisch).
        base = min(members, key=lambda e: (len(_vat_tokens(e.norm)), len(e.canonical_name or "")))
        if base.canonical_name and base.entity_id != target.entity_id:
            target.canonical_name = base.canonical_name
        for e in members:
            if e.entity_id != target.entity_id:
                merge_map[e.entity_id] = target.entity_id
    return merge_map, skipped_shared


# Kommunale Vergabestelle: Behörden-Typ + Gemeinde/Kreis-Name aus dem Käufer-Namen.
_RE_MUNI = re.compile(
    r"^(?P<typ>landeshauptstadt|kreisstadt|hansestadt|stadt|gemeinde|markt|stadtgemeinde"
    r"|landkreis|kreis|landratsamt|bezirk|zweckverband|amt|samtgemeinde|verbandsgemeinde)\s+"
    r"(?P<name>[A-Za-zÄÖÜäöüß.\- ]+?)"
    r"(?:\s*[,(/–-].*)?$", re.I)
_TYP_KLASSE = {  # Typ → grobe Klasse (Stadt vs. Kreis-Ebene bleiben getrennt)
    "landeshauptstadt": "gem", "kreisstadt": "gem", "hansestadt": "gem", "stadt": "gem",
    "gemeinde": "gem", "markt": "gem", "stadtgemeinde": "gem", "samtgemeinde": "gem",
    "verbandsgemeinde": "gem", "amt": "gem",
    "landkreis": "kreis", "kreis": "kreis", "landratsamt": "kreis", "bezirk": "bezirk",
    "zweckverband": "zv",
}


def _load_plz_kreis(cfg: Config) -> dict:
    """geonames DE (PLZ → Kreis + Bundesland) für die Gemeinde-Disambiguierung."""
    f = (cfg.data_dir / "reference" / "geonames" / "DE.txt")
    if not f.exists():
        return {}
    cols = {f"c{i:02d}": "VARCHAR" for i in range(1, 13)}
    try:
        rows = _db.connect().execute(
            f"SELECT c02, c04, c08 FROM read_csv('{f.as_posix()}', delim='\t', header=false, "
            f"columns={cols}, ignore_errors=true)").fetchall()
    except Exception:
        return {}
    return {plz: (bl or "", kreis or "") for plz, bl, kreis in rows if plz}


def _muni_key(name: str, plz_set: set, plz_kreis: dict) -> str | None:
    """Kanonischer Gemeinde-Schlüssel aus Behörden-Name + PLZ→Kreis. None, wenn kein Behörden-Muster."""
    from .entities import strip_accents
    m = _RE_MUNI.match((name or "").strip())
    if not m:
        return None
    klasse = _TYP_KLASSE.get(m.group("typ").lower())
    if not klasse:
        return None
    gem = re.sub(r"[^a-zäöüß]", "", strip_accents(m.group("name").lower()))
    if len(gem) < 3:
        return None
    # Disambiguierung über den Kreis der (ersten belegten) PLZ; ohne PLZ → Bundesland-los, riskanter.
    kreis = ""
    for plz in sorted(plz_set or ()):
        if plz in plz_kreis:
            kreis = re.sub(r"[^a-zäöüß]", "", strip_accents(plz_kreis[plz][1].lower()))
            break
    if not kreis:
        return None                       # ohne Kreis-Beleg nicht mergen (zu viele Gemeinde-Dubletten)
    return f"muni:{klasse}:{gem}:{kreis}"


def _consolidate_by_municipality(entity_of: dict, plz_of: dict, plz_kreis: dict, already: set):
    """Kommunale Vergabestellen-Fragmente über den kanonischen Gemeinde-Schlüssel verschmelzen
    (AGS-artig via geonames-Kreis). Merged „Stadt München" = „Landeshauptstadt München" =
    „STADT MÜNCHEN, Baureferat" (alle → gem:muenchen:kreisfreiestadtmuenchen), hält aber
    „Landkreis München" (kreis:…) und zwei „Neustadt" in verschiedenen Kreisen getrennt.
    Nur nicht-register-belegte Entities (Register-ID sticht)."""
    from collections import defaultdict

    id_methods = {Method.HR_EXACT, Method.HR_FUZZY_PLZ, Method.TED_NATIONAL_ID}
    groups: dict[str, list] = defaultdict(list)
    for e in entity_of.values():
        if e.entity_id in already or e.method in id_methods:
            continue
        k = _muni_key(e.canonical_name, plz_of.get(e.entity_id, set()), plz_kreis)
        if k:
            groups[k].append(e)
    merge_map: dict[str, str] = {}
    for k, group in groups.items():
        if len(group) < 2:
            continue
        rep = min(group, key=lambda e: e.entity_id)
        for e in group:
            if e.entity_id != rep.entity_id:
                merge_map[e.entity_id] = rep.entity_id
    return merge_map


def build_buyer_traeger(cfg: Config, country: str = "DE") -> tuple[int, int]:
    """Zweite Ebene ueber den Vergabestellen: TRAEGER (die Behoerde) + EINHEIT (die einkaufende Stelle).

    WARUM EINE EBENE UND KEIN MERGE. Gemessen am DE-Bestand 2026-08-30 liessen sich rund 20.700
    Kaeufer-Entitaeten (28,6 %) zusammenziehen, wenn man den Abteilungs-Zusatz wegwirft:
    „Landeshauptstadt Dresden, Geschaeftsbereich Finanzen" und „…, Geschaeftsbereich
    Stadtentwicklung" waeren dann eine Zeile. Das ist aber keine Datenbereinigung, sondern eine
    Produktentscheidung mit zwei richtigen Antworten:

      „Wie viele Vergabestellen gibt es?"      → die Behoerde (Traeger)
      „Wer schreibt diesen Auftrag aus?"       → die einkaufende Einheit

    Ein Merge beantwortet die erste Frage und macht die zweite unbeantwortbar. Diese Tabelle
    beantwortet beide, weil sie NICHTS wegnimmt: ``entity_id`` bleibt die Einheit und damit die
    Koernung des ganzen Bestands, ``traeger_id`` kommt daneben. Wer zaehlen will, gruppiert;
    wer anschreiben will, nimmt die Einheit.

    ⚠ DER TRAEGER IST NICHT DER NAMENSSTAMM ALLEIN. „Stadtwerke" gibt es hundertfach; ohne
    Ortsbeleg waeren das alles Geschwister. Es gilt dieselbe Kaskade wie beim Verschmelzen
    (``_ortsbeleg_passt``, PLZ → NUTS3 → Ortsname) und ausdruecklich dieselbe FUNKTION, damit
    Traeger-Ebene und Bestand nicht auseinanderdriften.

    JEDE Kaeufer-Entitaet bekommt eine Zeile, auch wenn ihr Traeger nur aus ihr selbst besteht.
    Sonst muesste jeder Verbraucher einen Aussenjoin schreiben und der erste, der es vergisst,
    verliert still die Haelfte der Vergabestellen.

    Rueckgabe: (Traeger, zugeordnete Einheiten).
    """
    import re as _re
    from collections import defaultdict, Counter
    from . import entities as _ents
    from . import names as _names

    con = _db.connect()
    gd = cfg.gold_dir / country
    pe, ent = f"'{gd}/party_entity.parquet'", f"'{gd}/entities.parquet'"
    reihen = con.execute(f"""
        SELECT DISTINCT e.entity_id, e.canonical_name
        FROM {pe} pe JOIN {ent} e USING(entity_id)
        WHERE pe.role = 'buyer'
    """).fetchall()
    geo = con.execute(f"""
        SELECT pe.entity_id,
               list(DISTINCT np.postal_code)          FILTER (WHERE np.postal_code IS NOT NULL AND np.postal_code <> ''),
               list(DISTINCT substr(np.nuts, 1, 5))   FILTER (WHERE np.nuts IS NOT NULL AND np.nuts <> ''),
               list(DISTINCT np.town)                 FILTER (WHERE np.town IS NOT NULL AND np.town <> '')
        FROM {pe} pe
        JOIN '{cfg.silver_table_glob("notice_parties", country)}' np
          ON np.notice_id = pe.notice_id AND np.role = pe.role AND np.seq = pe.seq
        WHERE pe.role = 'buyer'
        GROUP BY 1
    """).fetchall()

    def _ort(t):
        return _re.sub(r"[^a-z]", "", _ents.strip_accents((t or "").lower()))

    plz_of = {e: set(p or []) for e, p, _, _ in geo}
    nuts_of = {e: set(n or []) for e, _, n, _ in geo}
    ort_of = {e: {o for o in (_ort(t) for t in (x or [])) if o} for e, _, _, x in geo}

    # Der Bindestrich trennt eine Einheit genauso wie das Komma („Stadt Koeln - Amt fuer
    # Schulentwicklung"), aber `classify` schneidet nur am Komma. Ohne diese Angleichung waere
    # die Ebene in sich widerspruechlich: dieselbe Behoerde faltet mit Komma und faellt mit
    # Bindestrich auseinander. Angeglichen wird NUR hier, `classify` selbst bleibt unberuehrt —
    # es hat andere Nutzer, die auf seinem heutigen Verhalten stehen.
    _TRENNER = _re.compile(r"\s+[-–—]\s*|\s*,\s*")

    sauber_of, einheit_of, stamm_of = {}, {}, {}
    cluster: dict[str, list[str]] = defaultdict(list)
    for eid, name in reihen:
        sauber = _names.clean_display_name(name) or name or ""
        sauber_of[eid] = sauber
        teile = _TRENNER.split(sauber, 1)
        stamm_of[eid] = teile[0].strip()
        einheit_of[eid] = (teile[1].strip() if len(teile) > 1 else "") or None
        # Schluessel aus dem STAMM, nicht aus dem vollen Namen — sonst haengt die Zuordnung
        # daran, ob die Quelle Komma oder Bindestrich geschrieben hat.
        schluessel = _ents.classify(stamm_of[eid]).normalized if stamm_of[eid] else None
        if schluessel:
            cluster[schluessel].append(eid)
        else:
            cluster[f"__allein:{eid}"].append(eid)

    # Innerhalb eines Namens-Clusters entscheidet der Ortsbeleg, WELCHE Einheiten wirklich
    # denselben Traeger haben. Kleinste entity_id ist der Vertreter — dieselbe stabile Wahl
    # wie beim Verschmelzen, damit die IDs zwischen zwei Laeufen nicht wandern.
    zuordnung: dict[str, str] = {}
    for _, gruppe in cluster.items():
        gruppe.sort()
        for i, vertreter in enumerate(gruppe):
            if vertreter in zuordnung:
                continue
            zuordnung[vertreter] = vertreter
            for anderer in gruppe[i + 1:]:
                if anderer in zuordnung:
                    continue
                if _ortsbeleg_passt(vertreter, anderer, plz_of, nuts_of, ort_of):
                    zuordnung[anderer] = vertreter

    # Anzeigename des Traegers: bevorzugt ein Mitglied OHNE Einheit (das ist der reine
    # Behoerdenname), sonst der kuerzeste Namensstamm. Ohne diese Wahl hiesse der Traeger nach
    # der zufaellig kleinsten entity_id, also z. B. „…, Referat U 2.1" — formal richtig,
    # als Ueberschrift einer Behoerde aber irrefuehrend.
    mitglieder: dict[str, list[str]] = defaultdict(list)
    for eid, vertreter in zuordnung.items():
        mitglieder[vertreter].append(eid)
    name_of: dict[str, str] = {}
    for vertreter, gruppe in mitglieder.items():
        ohne = [g for g in gruppe if not einheit_of[g]]
        kandidaten = [g for g in (ohne or gruppe) if stamm_of[g]]
        if not kandidaten:
            name_of[vertreter] = sauber_of[vertreter]
            continue
        # HAEUFIGSTE Schreibweise, nicht die kuerzeste. Der kuerzeste Name gewinnt sonst mit
        # jeder verstuemmelten Variante: „DB Netz" schlaegt „DB Netz AG", obwohl fast alle
        # Quellen die lange Form schreiben. Gleichstand → der kuerzere, damit es stabil bleibt.
        haeufig = Counter(stamm_of[g] for g in kandidaten)
        name_of[vertreter] = min(haeufig, key=lambda n: (-haeufig[n], len(n), n))

    zeilen = [(eid, f"traeger:{vertreter}", name_of[vertreter], einheit_of[eid])
              for eid, vertreter in sorted(zuordnung.items())]
    _write(con, gd / "buyer_traeger.parquet", zeilen,
           "entity_id VARCHAR, traeger_id VARCHAR, traeger_name VARCHAR, einheit VARCHAR")
    con.close()
    return len(mitglieder), len(zeilen)


def _ortsbeleg_passt(a: str, b: str, plz_of: dict, nuts_of: dict, ort_of: dict) -> bool:
    """Ortsbeleg als KASKADE: der schaerfste vorhandene Beleg entscheidet allein.

    Der schwaechere darf den schaerferen nie ueberstimmen — sonst zoege ein geteilter Ortsname
    zwei Stellen mit widersprechender PLZ zusammen. Pro Paar wird die hoechste Stufe genommen,
    auf der BEIDE Seiten etwas vorweisen, und nur die zaehlt.

    ⚠ BEWUSST EINE MODULFUNKTION, nicht zweimal geschrieben. Sie entscheidet sowohl, was
    ``_consolidate_by_shared_name_geo`` verschmilzt, als auch, was ``build_buyer_traeger``
    unter einen Traeger stellt. Zwei Kopien wuerden auseinanderdriften, und dann widerspraeche
    die Traeger-Ebene dem Bestand, auf dem sie sitzt — ohne dass es jemandem auffiele.
    """
    pa, pb = plz_of.get(a, set()), plz_of.get(b, set())
    if pa and pb:
        return bool(pa & pb)                            # 1. PLZ: der scharfe Beleg
    na, nb = nuts_of.get(a, set()), nuts_of.get(b, set())
    if na and nb:
        return bool(na & nb)                            # 2. NUTS3: Kreisebene
    oa, ob = ort_of.get(a, set()), ort_of.get(b, set())
    return bool(oa and ob and (oa & ob))                 # 3. Ortsname: letzter Beleg


def _consolidate_by_shared_name_geo(entity_of: dict, plz_of: dict, nuts_of: dict,
                                    ort_of: dict, already: set):
    """Fragmente mit demselben GEREINIGTEN Namen und geteiltem Ortsbeleg verschmelzen.

    Der Vorgaenger (``_consolidate_by_shared_name_plz``) war an drei Stellen zu eng, und alle
    drei trafen ausgerechnet die Vergabestellen — also genau die Gruppe, fuer die er gedacht war.
    Gemessen am DE-Bestand 2026-08-30 (72.607 Kaeufer-Entitaeten aus 123.428 Rohnamen):

    1. FILTER AUF ``NAME_ONLY``. ``resolve_supplier`` kehrt fuer alles, was nicht
       ``Kind.COMPANY`` ist, frueh als ``unresolved:<name>`` zurueck — der Kommentar dort nennt
       Personen und Bietergemeinschaften, aber ``Kind.PUBLIC`` faellt in denselben Zweig.
       Ergebnis: **27.348 Kaeufer-Entitaeten (37,7 %) tragen ``nicht_aufgeloest``** und kamen in
       diesem Pass nie vor. Jetzt sind sie drin, aber nur wenn sie oeffentlich sind: Personen und
       Bietergemeinschaften bleiben ausgeschlossen, fuer die waere ein Namensmerge ein Ratespiel.

    2. SCHLUESSEL WAR ``e.norm``, ALSO DER ROHE NAME. ``clean_display_name`` loest
       „X vertreten durch Y" zu „X" auf — aber erst NACH der Aufloesung, auf dem Anzeigenamen.
       Der Merge-Schluessel trug den Zusatz weiter. Folge: **„DB Netz AG" existiert 98-mal**, als
       ``name:db netz vertreten durch db projektbau niederlassung suedost b so tp5`` und 97
       Geschwister, die einander nie begegnen. Jetzt clustert der Pass ueber den gereinigten
       Namen, mit demselben ``classify``-Normalisierer wie der Rest des Hauses.

    3. OHNE PLZ KEIN MERGE. Die PLZ ist der scharfe Beleg, fehlt aber bei oeffentlichen Stellen
       oft. NUTS3 (Kreisebene) und der ORTSNAME tragen dieselbe Aussage groeber und lagen beide
       ungenutzt daneben. Gemessen: **248.611 Kaeufer-Instanzen (11,2 %) tragen NUR einen
       Ortsnamen** und sonst keinen Ortsbeleg. Genau daran scheiterte der Pass bisher: von den
       1.889 blockierten Fragmenten scheiterten nur 68 an WIDERSPRECHENDEN Adressen, aber 1.821
       an gar keiner. Das Vergabestellen-Problem ist kein Zuordnungs-, sondern ein Adressproblem.

    ⚠ DIE BELEGREGEL IST BEWUSST ASYMMETRISCH: Haben BEIDE Seiten eine PLZ, MUSS sie sich
    ueberschneiden — zwei „Stadtwerke" verschiedener Orte bleiben getrennt, und NUTS3 darf das
    nicht ueberstimmen. Erst wenn der PLZ-Beleg auf mindestens einer Seite fehlt, entscheidet
    NUTS3. So bleibt die „0 Fehl-Merges"-Regel erhalten, statt sie gegen Ausbeute zu tauschen.

    Gemessen auf dem aktuellen Bestand: 1.471 Namensgruppen teilen einen Ortsbeleg
    (**2.369 ueberzaehlige Entitaeten**); 121 Gruppen (304 Entitaeten) haben WIDERSPRECHENDE
    Belege und werden bewusst nicht angefasst; 1.594 Gruppen (2.066) haben gar keinen Beleg und
    bleiben ebenfalls liegen. Nicht adressiert ist die Abteilungsebene („Stadt X, Bauamt" gegen
    „Stadt X, Schulamt", rund 28 % des Bestands) — das ist eine Produktfrage, kein Datenfehler,
    und gehoert nicht heimlich in einen Merge-Pass.

    ``already`` = Entities, die schon (per National-ID/Alias/Leitweg/VAT) verschmelzen.
    Konservativ: mergt je Cluster in die kleinste entity_id.
    """
    from collections import defaultdict
    import re as _re
    from . import entities as _ents
    from . import names as _names

    KANDIDAT = (Method.NAME_ONLY, Method.UNRESOLVED)
    OEFFENTLICH = (_ents.Kind.PUBLIC, _ents.Kind.ASSOCIATION)

    def _sauber(e):
        return _names.clean_display_name(e.canonical_name) or e.canonical_name or ""

    def _schluessel(e):
        """Cluster-Schluessel aus dem GEREINIGTEN Namen — kein eigener Normalisierer."""
        sauber = _sauber(e)
        return _ents.classify(sauber).normalized if sauber else None

    def _einheit(e):
        """Die Organisationseinheit hinter dem ersten Komma, normalisiert.

        ⚠ SIE ENTSCHEIDET UEBER DIE KOERNUNG DES BESTANDS, und deshalb steht sie hier.
        ``classify().normalized`` schneidet am Komma ab: „Landeshauptstadt Dresden,
        Geschaeftsbereich Stadtentwicklung" und „…, Geschaeftsbereich Allgemeine Verwaltung"
        ergeben denselben Schluessel. Ohne diesen Riegel wuerde der Pass also nebenbei die
        ABTEILUNGSEBENE einschmelzen — gemessen 1.772 statt 1.017 Merges.

        Das waere keine Datenbereinigung, sondern eine Produktentscheidung: „Wer ist die
        Vergabestelle, die Behoerde oder die einkaufende Einheit?" Sie ist frueher bewusst
        zugunsten der Einheit gefallen (Muenchen 5, BImA 4). Ein Merge-Pass ist nicht der Ort,
        an dem so etwas still umgedreht wird.

        Darum: verschmolzen wird nur, wenn die Einheiten GLEICH sind oder eine Seite gar keine
        nennt. „Stadt Muenster, der Oberbuergermeister" und „Stadt Muenster" gehoeren zusammen
        (Vertretung, keine Einheit); die zwei Dresdner Geschaeftsbereiche nicht.
        """
        sauber = _sauber(e)
        rest = sauber.split(",", 1)[1] if "," in sauber else ""
        return _re.sub(r"[^a-z0-9]", "", _ents.strip_accents(rest.lower()))

    by_key: dict[str, list] = defaultdict(list)
    for e in entity_of.values():
        if e.entity_id in already or e.method not in KANDIDAT:
            continue
        if e.method == Method.UNRESOLVED and _ents.classify(e.canonical_name).kind not in OEFFENTLICH:
            continue                                    # Person/Bietergemeinschaft: nicht raten
        k = _schluessel(e)
        if k:
            by_key[k].append(e)

    def _beleg_passt(a: str, b: str) -> bool:
        return _ortsbeleg_passt(a, b, plz_of, nuts_of, ort_of)

    merge_map: dict[str, str] = {}
    for _, group in by_key.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda e: e.entity_id)           # kleinste ID = Repraesentant, stabil
        for i, rep in enumerate(group):
            if rep.entity_id in merge_map:
                continue                                # schon einem frueheren Repraesentanten zu
            for other in group[i + 1:]:
                if other.entity_id in merge_map:
                    continue
                ea, eb = _einheit(rep), _einheit(other)
                if ea and eb and ea != eb:
                    continue                            # zwei verschiedene Einheiten: nicht unsere Entscheidung
                if _beleg_passt(rep.entity_id, other.entity_id):
                    merge_map[other.entity_id] = rep.entity_id
    return merge_map


def _write(con, path, rows, columns):
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"CREATE OR REPLACE TABLE _t ({columns})")
    # Vektorisiert über Arrow statt row-by-row executemany: bei party_entity (3,7M
    # Zeilen) war executemany der Flaschenhals (~336 s → ~3 s). Arrow bewahrt None→NULL
    # exakt (kein pandas-NaN); die typisierte Tabelle castet die Spalten.
    if rows:
        import pyarrow as pa
        names = [c.strip().split()[0] for c in columns.split(",")]
        cols = list(zip(*rows))
        tbl = pa.table({names[i]: pa.array(cols[i]) for i in range(len(names))})
        con.register("_arrow", tbl)
        con.execute("INSERT INTO _t SELECT * FROM _arrow")
        con.unregister("_arrow")
    con.execute(f"COPY (SELECT * FROM _t) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute("DROP TABLE _t")


def resolve_supplier(
    name: str,
    national_id: str | None = None,
    postal_code: str | None = None,
    hr_lookup=None,
) -> ResolvedEntity:
    """Löse einen Lieferanten auf und sage, wie sicher.

    ``hr_lookup`` ist eine Funktion ``(normalized_name, plz) -> record | None``
    über das Handelsregister — injiziert, damit die Logik ohne die 5-Millionen-
    Zeilen-Datei testbar bleibt. Fehlt sie, endet die Kette bei Name-oder-ID.

    Reihenfolge — STABILITÄT über die Generationsgrenze zuerst:
      1. Person / Bietergemeinschaft → gar nicht auflösbar
      2. Handelsregister-Namensmatch → HRB-Schlüssel. STABIL: derselbe Name gibt
         2020 (kein national_id) und 2024 (mit national_id) dieselbe HRB.
      3. national_id (nur wenn kein HR-Treffer) → national_id-Schlüssel. Belastbar
         pro Notice (1.0), aber existiert erst ab eForms — kann die Zeitachse
         nicht tragen, daher nachrangig.
      4. sonst: Name als Schlüssel → 0.4

    Warum HRB VOR national_id: Der Incumbent-Test 'gleicher Gewinner über die
    Zeit?' braucht einen Schlüssel, der 2020 und 2024 identisch ist. national_id
    (VAT) gibt es erst ab 2024 — als Primärschlüssel spaltet er dieselbe Firma
    in zwei IDs und drückt die Incumbent-Rate auf unmögliche 7%.
    """
    from . import entities

    classified = entities.classify(name)
    norm = classified.normalized

    if classified.kind is not entities.Kind.COMPANY:
        # Persons and consortia are not in any company register — saying
        # "unresolved" is the honest answer, not a bad fuzzy guess.
        return ResolvedEntity(
            entity_id=f"unresolved:{norm or name}",
            canonical_name=name,
            method=Method.UNRESOLVED,
            confidence=CONFIDENCE[Method.UNRESOLVED],
            source_names=(name,),
            norm=norm,
        )

    if hr_lookup is not None:
        hit, fuzzy = hr_lookup(norm, postal_code)
        if hit:
            method = Method.HR_FUZZY_PLZ if fuzzy else Method.HR_EXACT
            return ResolvedEntity(
                entity_id=f"hr:{hit['nr']}",
                canonical_name=hit.get("name", name),
                method=method,
                confidence=CONFIDENCE[method],
                national_id=hit["nr"],
                source_names=(name,),
                norm=norm,
            )

    # national_id normalisieren: Leitweg-ID/VAT vereinheitlichen, Müll (UUID/TED-intern/Kurzzahl)
    # verwerfen. Roh spaltete „0204:991-…" und „991-…" dieselbe öffentliche Stelle in zwei Entitäten.
    nid = normalize_national_id(national_id)
    if nid:
        return ResolvedEntity(
            entity_id=f"id:{nid}",
            canonical_name=name,
            method=Method.TED_NATIONAL_ID,
            confidence=CONFIDENCE[Method.TED_NATIONAL_ID],
            national_id=nid,
            source_names=(name,),
            norm=norm,
        )

    return ResolvedEntity(
        entity_id=f"name:{norm}",
        canonical_name=name,
        method=Method.NAME_ONLY,
        confidence=CONFIDENCE[Method.NAME_ONLY],
        source_names=(name,),
        norm=norm,
    )


# --- 🟢 Markt-Intelligenz-Views (Ticket #3, ohne Nachfolge-Modell) --------------

MARKET_WINDOW_YEARS = 5           # gleitendes Fenster für Behörden-/Markt-Statistik


def build_market_intelligence(cfg: Config, country: str = "DE", as_of_year: int | None = None):
    """Vier materialisierte Aggregat-Views über die CAN-Award-Historie.

    NUR nachfolge-freie KPIs (🟢) — Zählungen, Top-N, Rang/Anteil nach Win-Zahl,
    Trend. Volumen trägt ``*_coverage`` (55 % der Werte fehlen), Laufzeit ebenso.
    Verdrängungs-/Verlust-KPIs (loss_rate, head_to_head, switch_rate) fehlen hier
    bewusst — die brauchen das Nachfolge-Modell und kommen konfidenz-gegatet dazu.

    Schreibt: ``buyer_stats``, ``contractor_stats``, ``market_stats``,
    ``buyer_contractor_history`` (je Parquet). Gibt Zeilenzahlen zurück.
    """
    from datetime import date

    as_of = as_of_year or date.today().year
    win = as_of - MARKET_WINDOW_YEARS
    g = cfg.gold_dir / country
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    EN = f"'{(g / 'entities.parquet').as_posix()}'"
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    LOTS = f"'{cfg.silver_table_glob('lots', country)}'"

    con = _db.connect()
    con.execute("SET threads=3")

    def copy_to(sql, name):
        out = (g / name).as_posix()
        con.execute(f"COPY ({sql}) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        return con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]

    # Award-Basis (CAN, Fenster), Buyer-/Gewinner-Entity aufgelöst
    con.execute(f"""
    CREATE TEMP TABLE aw AS
    SELECT n.notice_id, bpe.entity_id AS buyer, be.canonical_name AS buyer_name,
           wpe.entity_id AS winner, we.canonical_name AS winner_name,
           substr(n.cpv_main,1,4) AS cpv_class,
           CAST(coalesce(year(n.award_date), n.year) AS INT) AS yr,
           coalesce(upper(substr(n.performance_nuts,1,3)), 'DE') AS nuts1,
           n.final_value AS value
    FROM read_parquet({N}, hive_partitioning=1) n
    JOIN read_parquet({PE}) bpe ON bpe.notice_id=n.notice_id AND bpe.role='buyer'
    LEFT JOIN read_parquet({EN}) be ON be.entity_id=bpe.entity_id
    LEFT JOIN read_parquet({PE}) wpe ON wpe.notice_id=n.notice_id AND wpe.role='winner'
    LEFT JOIN read_parquet({EN}) we ON we.entity_id=wpe.entity_id
    WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND bpe.entity_id IS NOT NULL
      AND CAST(coalesce(year(n.award_date), n.year) AS INT) >= {win}
    """)

    # Vergabedauer (cn→can via ref_publication_number, ~42 % verlinkbar) je Behörde
    con.execute(f"""CREATE TEMP TABLE _dds AS
      WITH dd AS (
        SELECT a.buyer, datediff('day', cn.publication_date, can.award_date) AS d
        FROM aw a
        JOIN read_parquet({N}, hive_partitioning=1) can ON can.notice_id=a.notice_id
        LEFT JOIN read_parquet({N}, hive_partitioning=1) cn
          ON cn.publication_number=can.ref_publication_number AND cn.notice_kind='cn'
        WHERE can.award_date IS NOT NULL)
      SELECT buyer,
             CASE WHEN count(*) FILTER (WHERE d BETWEEN 0 AND 730) >= 3
                  THEN round(avg(d) FILTER (WHERE d BETWEEN 0 AND 730)) END AS avg_decision_days,
             round(count(*) FILTER (WHERE d BETWEEN 0 AND 730)*1.0/count(*), 3) AS decision_days_coverage
      FROM dd GROUP BY buyer""")

    # 1) buyer_stats
    con.execute("""CREATE TEMP TABLE _bt AS
      SELECT buyer, list(struct_pack(entity_id:=winner, name:=winner_name, wins:=wins)
                         ORDER BY wins DESC) FILTER (WHERE rn<=3) AS top_contractors
      FROM (SELECT buyer, winner, any_value(winner_name) winner_name, count(*) wins,
                   row_number() OVER (PARTITION BY buyer ORDER BY count(*) DESC) rn
            FROM aw WHERE winner IS NOT NULL GROUP BY buyer, winner)
      GROUP BY buyer""")
    con.execute("""CREATE TEMP TABLE _bc AS
      SELECT buyer, list(cpv_class ORDER BY c DESC) FILTER (WHERE rn<=3) AS top_cpvs
      FROM (SELECT buyer, cpv_class, count(*) c,
                   row_number() OVER (PARTITION BY buyer ORDER BY count(*) DESC) rn
            FROM aw GROUP BY buyer, cpv_class)
      GROUP BY buyer""")
    n_buyer = copy_to(f"""
      SELECT a.buyer AS buyer_entity_id, any_value(a.buyer_name) AS buyer_name,
             count(DISTINCT a.notice_id) AS total_awards,
             count(DISTINCT a.winner) AS distinct_contractors,
             bc.top_cpvs, bt.top_contractors,
             dds.avg_decision_days, dds.decision_days_coverage,
             {as_of} AS window_end, {MARKET_WINDOW_YEARS} AS window_years
      FROM aw a LEFT JOIN _bt bt ON bt.buyer=a.buyer LEFT JOIN _bc bc ON bc.buyer=a.buyer
                LEFT JOIN _dds dds ON dds.buyer=a.buyer
      GROUP BY a.buyer, bc.top_cpvs, bt.top_contractors, dds.avg_decision_days, dds.decision_days_coverage""",
      "buyer_stats.parquet")

    # 2) contractor_stats (entity × cpv_class)
    n_contr = copy_to(f"""
      WITH base AS (
        SELECT winner AS entity_id, cpv_class, count(*) AS total_wins,
               count(value) AS wins_with_value,
               sum(value) FILTER (WHERE value IS NOT NULL) AS total_volume_known,
               count(*) FILTER (WHERE yr={as_of}) AS wly, count(*) FILTER (WHERE yr={as_of}-1) AS wpy
        FROM aw WHERE winner IS NOT NULL GROUP BY winner, cpv_class)
      SELECT entity_id, cpv_class, total_wins, total_volume_known,
             round(wins_with_value*1.0/total_wins,2) AS volume_coverage,
             rank() OVER (PARTITION BY cpv_class ORDER BY total_wins DESC) AS market_rank,
             round(total_wins*1.0/sum(total_wins) OVER (PARTITION BY cpv_class),4) AS market_share_by_wins,
             CASE WHEN wpy>0 THEN round((wly-wpy)*1.0/wpy,2) END AS trend_yoy
      FROM base""", "contractor_stats.parquet")

    # 3) market_stats (cpv_class × nuts1) inkl. Ø-Laufzeit aus lots
    con.execute(f"""CREATE TEMP TABLE _dur AS
      SELECT a.cpv_class, a.nuts1, avg(l.duration_months) avg_dur,
             count(l.duration_months) n_dur, count(*) n_tot
      FROM aw a LEFT JOIN read_parquet({LOTS}) l ON l.notice_id=a.notice_id
      GROUP BY a.cpv_class, a.nuts1""")
    n_market = copy_to("""
      SELECT a.cpv_class, a.nuts1, count(DISTINCT a.winner) AS active_contractors,
             count(DISTINCT a.notice_id) AS total_awards,
             round(d.avg_dur) AS avg_contract_duration_months,
             round(d.n_dur*1.0/d.n_tot,2) AS duration_coverage
      FROM aw a LEFT JOIN _dur d ON d.cpv_class=a.cpv_class AND d.nuts1=a.nuts1
      GROUP BY a.cpv_class, a.nuts1, d.avg_dur, d.n_dur, d.n_tot""", "market_stats.parquet")

    # 4) buyer_contractor_history inkl. Verlängerungen aus lots
    con.execute(f"""CREATE TEMP TABLE _ren AS
      SELECT a.buyer, a.winner, a.notice_id,
             max(CASE WHEN l.has_renewal THEN 1 ELSE 0 END) AS renewed
      FROM aw a LEFT JOIN read_parquet({LOTS}) l ON l.notice_id=a.notice_id
      WHERE a.winner IS NOT NULL GROUP BY a.buyer, a.winner, a.notice_id""")
    n_bch = copy_to("""
      SELECT a.buyer AS buyer_entity_id, a.winner AS contractor_entity_id,
             any_value(a.winner_name) AS contractor_name,
             count(DISTINCT a.notice_id) AS total_wins, max(a.yr) AS last_win_year,
             coalesce(sum(r.renewed),0) AS total_renewals
      FROM aw a LEFT JOIN _ren r ON r.buyer=a.buyer AND r.winner=a.winner AND r.notice_id=a.notice_id
      WHERE a.winner IS NOT NULL GROUP BY a.buyer, a.winner""", "buyer_contractor_history.parquet")

    con.close()
    return {"buyer_stats": n_buyer, "contractor_stats": n_contr,
            "market_stats": n_market, "buyer_contractor_history": n_bch}


# --- Nachfolge-Modell: inhaltsbasiert, konfidenz-tragend ------------------------

_SUCC_STOP = set("""rahmenvertrag rahmenvereinbarung rahmen vereinbarung vertrag vertraege vergabe
ausschreibung bekanntmachung vergabebekanntmachung aufhebung berichtigung eu euweit weit weite
offenes offene verfahren oeffentliche lieferung lieferungen liefern leistung leistungen erbringung
beschaffung bereitstellung durchfuehrung wartung ueber von und der die das fuer zur zum los teillos
gemaess im in den des dem einer eines eine sowie bzw div diverse verschiedene""".split())


def _succ_tokens(t: str) -> set:
    t = (t or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return {w for w in re.sub(r"[^a-z0-9]+", " ", t).split() if len(w) > 3 and w not in _SUCC_STOP}


def build_content_successions(cfg: Config, country: str = "DE",
                              conf_threshold: float = 0.45, amb_threshold: float = 0.30):
    """Inhaltsbasiertes Nachfolge-Modell — ersetzt die proximity-Ketten für KPIs.

    Trichter:
      A) Kandidaten = gleiche Behörde + CPV-Klasse, 1..10 J früher, NUR ketten-würdige
         Verträge (nicht-Rahmen-Bauprojekte raus — sonst Bau-Gewerke als Fehl-Nachfolge).
      B) Unmittelbarer Vorgänger = jüngster Kandidat mit Inhalts-Score >= Schwelle.
         Score = Titel-Token-Jaccard (+ CPV-8-Bonus + Laufzeit-Timing); Same-Verfahren
         (gleiche oj_ref) ausgeschlossen.
      C) mehrdeutige (Top-2 im selben Jahr dicht) → LLM-Queue (separates Parquet).

    Schreibt ``contract_succession`` (konfidente Kanten, als Fakt) + ``…_llm_queue``.
    Gibt ``(n_edges, n_llm, n_none)`` zurück.
    """
    from collections import defaultdict

    g = cfg.gold_dir / country
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    LOTS = f"'{cfg.silver_table_glob('lots', country)}'"
    kind_sql = _kind_sql("n.title", "n.cpv_main")

    con = _db.connect(); con.execute("SET threads=3")
    rows = con.execute(f"""
        SELECT n.notice_id, bpe.entity_id, n.cpv_main, substr(n.cpv_main,1,4),
               CAST(coalesce(year(n.award_date), n.year) AS INT), n.title, n.oj_ref,
               (SELECT max(l.duration_months) FROM read_parquet({LOTS}) l WHERE l.notice_id=n.notice_id)
        FROM read_parquet({N}, hive_partitioning=1) n
        JOIN read_parquet({PE}) bpe ON bpe.notice_id=n.notice_id AND bpe.role='buyer'
        WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND bpe.entity_id IS NOT NULL
          AND n.title IS NOT NULL AND ({kind_sql}) NOT IN ('einmal_werk','werk_sonstig')
    """).fetchall()

    groups: dict = defaultdict(list)
    tok, meta = {}, {}
    for nid, buyer, cpv, cpv4, yr, title, ojref, dur in rows:
        groups[(buyer, cpv4)].append(nid)
        tok[nid] = _succ_tokens(title)
        meta[nid] = (buyer, cpv, cpv4, yr, ojref, dur)

    edges, llm_queue = [], []
    n_none = 0
    for ids in groups.values():
        ids.sort(key=lambda i: meta[i][3])
        for anchor in ids:
            a_buyer, a_cpv, a_cpv4, ay, a_ojref, adur = meta[anchor]
            scored = []
            for cand in ids:
                cy = meta[cand][3]
                if not (ay - 10 <= cy < ay):
                    continue
                if a_ojref and meta[cand][4] == a_ojref:          # R1: Same-Verfahren
                    continue
                s = (len(tok[anchor] & tok[cand]) / len(tok[anchor] | tok[cand])
                     if tok[anchor] and tok[cand] else 0.0)
                if meta[cand][1] == a_cpv:
                    s += 0.30
                if adur:                                          # R2: Laufzeit-Timing
                    exp = max(1, round(adur / 12))
                    s += 0.10 * max(0, 1 - abs((ay - cy) - exp) / 5)
                scored.append((min(s, 1.0), cy, cand))
            if not scored:
                n_none += 1; continue
            above = sorted((x for x in scored if x[0] >= conf_threshold),
                           key=lambda x: (x[1], x[0]), reverse=True)
            if above:
                best = above[0]
                rivals = [x for x in above if x[1] == best[1] and x[2] != best[2] and abs(x[0] - best[0]) < 0.12]
                if rivals:
                    llm_queue.append((anchor, best[2], rivals[0][2], round(best[0], 3), round(rivals[0][0], 3)))
                    continue
                conf = round(0.55 + 0.4 * min(1.0, (best[0] - conf_threshold) / (1 - conf_threshold)), 2)
                edges.append((anchor, best[2], a_buyer, a_cpv4, ay - best[1], round(best[0], 3), conf, "content_unique"))
            else:
                top = max(scored)
                if top[0] >= amb_threshold:
                    llm_queue.append((anchor, top[2], None, round(top[0], 3), None))
                else:
                    n_none += 1

    con.execute("CREATE TEMP TABLE e(successor VARCHAR, predecessor VARCHAR, buyer_entity VARCHAR, "
                "cpv_class VARCHAR, gap_years INT, content_score DOUBLE, confidence DOUBLE, method VARCHAR)")
    if edges:
        con.executemany("INSERT INTO e VALUES (?,?,?,?,?,?,?,?)", edges)
    con.execute(f"COPY (SELECT * FROM e) TO '{(g / 'contract_succession.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute("CREATE TEMP TABLE q(successor VARCHAR, cand1 VARCHAR, cand2 VARCHAR, score1 DOUBLE, score2 DOUBLE)")
    if llm_queue:
        con.executemany("INSERT INTO q VALUES (?,?,?,?,?)", llm_queue)
    con.execute(f"COPY (SELECT * FROM q) TO '{(g / 'contract_succession_llm_queue.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    return len(edges), len(llm_queue), n_none


# --- 🔴 Nachfolge-KPIs: Verdrängung/Retention auf dem konfidenten Kern ----------

def build_succession_kpis(cfg: Config, country: str = "DE"):
    """Wettbewerbs-KPIs aus ``contract_succession`` — konfidenz-getragen.

    Gewinner-Matching bewusst sorgfältig (beim Messen als entscheidend erkannt):
      * **gruppen-bewusst** (entity_group) — sonst zählt Siemens AG ↔ Siemens Mobility als Verdrängung;
      * **Multi-Gewinner-Set-Schnitt** — Open-house/Los-Verträge haben viele Gewinner; Retention =
        Vorgänger-Gewinner IST unter den Nachfolger-Gewinnern (nicht „gleicher Primärgewinner");
      * **Konsortien geflaggt** — ARGE haben projektspezifische Namen, Retention unbestimmbar → aus
        den Raten ausgeschlossen, nicht als Verdrängung fehlgezählt.

    Schreibt ``succession_events`` (+ ``head_to_head``, ``market_switch_rate``,
    ``buyer_loyalty``, ``contractor_loss``). Gibt Zeilenzahlen + Retention zurück.
    """

    g = cfg.gold_dir / country
    S = f"'{(g / 'contract_succession.parquet').as_posix()}'"
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    EG = f"'{(g / 'entity_group.parquet').as_posix()}'"

    con = _db.connect(); con.execute("SET threads=3")

    def copy_to(sql, name):
        out = (g / name).as_posix()
        con.execute(f"COPY ({sql}) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        return con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]

    # Gewinner-Gruppen-Set je Notice (+ Konsortium-Flag)
    con.execute(f"""
    CREATE TEMP TABLE wg AS
    SELECT pe.notice_id,
           list(DISTINCT coalesce(g.group_id, pe.entity_id)) AS grp,
           bool_or(pe.entity_id LIKE 'unresolved:%') AS consortium
    FROM read_parquet({PE}) pe LEFT JOIN read_parquet({EG}) g ON g.entity_id=pe.entity_id
    WHERE pe.role='winner' GROUP BY pe.notice_id
    """)
    # Nachfolge-Ereignisse
    con.execute(f"""
    CREATE TEMP TABLE ev AS
    SELECT s.successor, s.predecessor, s.buyer_entity, s.cpv_class, s.gap_years, s.confidence,
           pw.grp AS pred_winners, sw.grp AS succ_winners,
           (pw.consortium OR sw.consortium) AS consortium,
           len(list_intersect(pw.grp, sw.grp)) > 0 AS retained
    FROM read_parquet({S}) s
    JOIN wg pw ON pw.notice_id=s.predecessor JOIN wg sw ON sw.notice_id=s.successor
    """)
    rr = con.execute("SELECT count(*) FILTER (WHERE retained), count(*) FROM ev WHERE NOT consortium").fetchone()
    retention = round(rr[0] / rr[1], 3) if rr[1] else None

    n_events = copy_to("""
      SELECT successor, predecessor, buyer_entity, cpv_class, gap_years, confidence,
             consortium, retained, NOT retained AS displaced,
             len(pred_winners) AS n_pred_winners, len(succ_winners) AS n_succ_winners
      FROM ev""", "succession_events.parquet")

    # market_switch_rate (cpv_class), buyer_loyalty (Behörde) — Konsortien raus, n mitgeben
    copy_to("""
      SELECT cpv_class, count(*) AS n_successions,
             round(count(*) FILTER (WHERE NOT retained)*1.0/count(*),3) AS switch_rate
      FROM ev WHERE NOT consortium GROUP BY cpv_class""", "market_switch_rate.parquet")
    copy_to("""
      SELECT buyer_entity, count(*) AS n_successions,
             round(count(*) FILTER (WHERE retained)*1.0/count(*),3) AS incumbent_loyalty
      FROM ev WHERE NOT consortium GROUP BY buyer_entity""", "buyer_loyalty.parquet")

    # contractor_loss: je Vorgänger-Gewinner-Gruppe verteidigt/verloren (Multi-Gewinner: unnest)
    n_loss = copy_to("""
      WITH d AS (
        SELECT unnest(pred_winners) AS entity, succ_winners, retained
        FROM ev WHERE NOT consortium)
      SELECT entity AS entity_id, count(*) AS n_defended,
             count(*) FILTER (WHERE NOT list_contains(succ_winners, entity)) AS n_lost,
             round(count(*) FILTER (WHERE NOT list_contains(succ_winners, entity))*1.0/count(*),3) AS loss_rate
      FROM d GROUP BY entity""", "contractor_loss.parquet")

    # head_to_head: saubere 1v1-Verdrängungen (beide Seiten genau ein Gewinner, kein Konsortium)
    n_h2h = copy_to("""
      SELECT succ_winners[1] AS winner_entity, pred_winners[1] AS loser_entity,
             count(*) AS displacements, round(avg(confidence),2) AS avg_conf
      FROM ev
      WHERE NOT consortium AND NOT retained AND len(pred_winners)=1 AND len(succ_winners)=1
      GROUP BY succ_winners[1], pred_winners[1]""", "head_to_head.parquet")

    con.close()
    return {"succession_events": n_events, "head_to_head": n_h2h,
            "contractor_loss": n_loss, "incumbent_retention": retention}


def merge_llm_successions(cfg: Config, country: str = "DE", llm_confidence: float = 0.7):
    """LLM-adjudizierte Kanten (``succession_llm_edges.parquet``) in ``contract_succession``
    einmischen — angereichert (buyer/cpv_class/gap) + ``method='llm_adjudicated'``.

    Dedup: hat ein Nachfolger schon eine ``content_unique``-Kante, gewinnt die (höhere
    Konfidenz). Idempotent: ein Gold-Rebuild schreibt erst die Content-Kanten, dann mischt
    dieser Schritt die (persistente) LLM-Datei wieder ein. Gibt die Gesamt-Kantenzahl zurück.
    """

    g = cfg.gold_dir / country
    llm = g / "succession_llm_edges.parquet"
    S = f"'{(g / 'contract_succession.parquet').as_posix()}'"
    if not llm.exists():
        return _db.connect().execute(f"SELECT count(*) FROM read_parquet({S})").fetchone()[0]

    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    con = _db.connect(); con.execute("SET threads=3")
    out = (g / "contract_succession.parquet").as_posix()
    con.execute(f"""
    COPY (
      SELECT * FROM read_parquet({S})
      UNION ALL
      SELECT e.successor, e.predecessor, bpe.entity_id AS buyer_entity,
             substr(ns.cpv_main,1,4) AS cpv_class,
             CAST(coalesce(year(ns.award_date),ns.year) AS INT)
               - CAST(coalesce(year(np.award_date),np.year) AS INT) AS gap_years,
             NULL::DOUBLE AS content_score, {llm_confidence} AS confidence, 'llm_adjudicated' AS method
      FROM read_parquet('{llm.as_posix()}') e
      JOIN read_parquet({N}, hive_partitioning=1) ns ON ns.notice_id=e.successor
      JOIN read_parquet({N}, hive_partitioning=1) np ON np.notice_id=e.predecessor
      LEFT JOIN read_parquet({PE}) bpe ON bpe.notice_id=e.successor AND bpe.role='buyer'
      WHERE e.successor NOT IN (SELECT successor FROM read_parquet({S}))
    ) TO '{out}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    import os
    os.replace(f"{out}.tmp", out)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_incumbent_tenure(cfg: Config, country: str = "DE"):
    """Wie lange hält der Incumbent diesen Vertrag schon? — aus den Nachfolge-Ketten.

    Läuft ``succession_events`` rückwärts, solange der Incumbent GEHALTEN hat (``retained``),
    und misst seit wann + über wie viele Zyklen. Basis für „Incumbent seit 20XX" (#3/#4 D4).
    Schreibt ``incumbent_tenure`` (notice_id, incumbent_since_year, tenure_years, chain_depth).
    """

    g = cfg.gold_dir / country
    con = _db.connect(); con.execute("SET threads=3")
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    ev = con.execute(f"SELECT successor, predecessor, retained "
                     f"FROM read_parquet('{(g / 'succession_events.parquet').as_posix()}')").fetchall()
    year = dict(con.execute(f"SELECT notice_id, CAST(coalesce(year(award_date), year) AS INT) "
                            f"FROM read_parquet({N}, hive_partitioning=1) WHERE notice_kind='can'").fetchall())
    pred = {s: p for s, p, ret in ev if ret}      # nur gehaltene Kanten
    rows = []
    for s in {x[0] for x in ev}:
        cur, since, depth, seen = s, year.get(s), 0, {s}
        while cur in pred and pred[cur] not in seen:
            cur = pred[cur]; seen.add(cur); depth += 1
            if year.get(cur) is not None:
                since = year[cur]
        if depth > 0:
            rows.append((s, since, (year.get(s) or since or 0) - (since or year.get(s) or 0), depth))
    con.execute("CREATE TEMP TABLE t(notice_id VARCHAR, incumbent_since_year INT, tenure_years INT, chain_depth INT)")
    if rows:
        con.executemany("INSERT INTO t VALUES (?,?,?,?)", rows)
    out = (g / "incumbent_tenure.parquet").as_posix()
    con.execute(f"COPY (SELECT * FROM t) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    return len(rows)


def build_award_tender_link(cfg: Config, country: str = "DE"):
    """Verknüpft jeden Zuschlag (can) mit seiner Ausschreibung über ``ref_publication_number``.

    Fundament für **Attribution** (#6: geklickte Ausschreibung → deren Zuschlag) und
    **Award-Alerts** (#9: Zuschlag zu beobachtetem Lead). Gemessen: ~51 % der Vergaben
    tragen einen Verweis, davon ~99,9 % in der DB auflösbar. Schreibt ``award_tender_link``
    (award_notice_id, tender_notice_id, tender_publication_number, gap_days, method).
    """

    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    out = (g / "award_tender_link.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH aw AS (
            SELECT notice_id, ref_publication_number, publication_date
            FROM read_parquet({N}, hive_partitioning=1)
            WHERE notice_kind='can' AND ref_publication_number IS NOT NULL),
          tn AS (
            SELECT publication_number, notice_id, publication_date
            FROM read_parquet({N}, hive_partitioning=1)
            WHERE publication_number IS NOT NULL)
          SELECT aw.notice_id AS award_notice_id,
                 tn.notice_id AS tender_notice_id,
                 aw.ref_publication_number AS tender_publication_number,
                 datediff('day', tn.publication_date, aw.publication_date) AS gap_days,
                 'ref_publication' AS method
          FROM aw JOIN tn ON tn.publication_number = aw.ref_publication_number
          QUALIFY row_number() OVER (PARTITION BY aw.notice_id ORDER BY tn.publication_date DESC) = 1
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_value_anchor(cfg: Config, country: str = "DE"):
    """Wert-Anker je Zuschlag — Schätzer für den Auftragswert, wo keiner veröffentlicht ist.

    ⚠ ZWECK ENTFALLEN. Gebaut wurde das als **Lowball-Wächter** fürs Erfolgsgebühren-Billing
    (#6): ein Plausibilitäts-Anker gegen die Kunden-Selbstauskunft (~68 % ±1 Band). Die
    Erfolgsprämie ist am 2026-08-21 gestrichen, und ``value_anchor.parquet`` liest seitdem
    **niemand** (nur `cli.py` baut es, `verify.py` prüft die Integrität). Der Schätzer selbst
    bleibt brauchbar, wo ein Auftragswert fehlt — er wartet aber auf einen Abnehmer.
    Kein Orakel: die Schätzung trifft nur ~42 % exakt. **Waterfall** (bester
    verfügbarer Schätzer): Ausschreibungssumme (via ``award_tender_link``) → Vorgänger-
    Vertrag (``contract_succession``) → Buyer×CPV-Median → Buyer-Median → CPV-Median.
    Werte sind **nominal** (der Kunde bestätigt den echten Auftragswert, nicht deflationiert).
    Schreibt ``value_anchor`` (notice_id, anchor_value, anchor_band, anchor_source,
    has_real_value).
    """

    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    CS = f"'{(g / 'contract_succession.parquet').as_posix()}'"
    ATL = f"'{(g / 'award_tender_link.parquet').as_posix()}'"
    out = (g / "value_anchor.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH win AS (SELECT notice_id, any_value(entity_id) eid FROM read_parquet({PE})
                       WHERE role='winner' AND entity_id IS NOT NULL GROUP BY notice_id),
          buy AS (SELECT notice_id, any_value(entity_id) eid FROM read_parquet({PE})
                  WHERE role='buyer' AND entity_id IS NOT NULL GROUP BY notice_id),
          can AS (
            SELECT n.notice_id, substr(n.cpv_main,1,4) cpv4, n.final_value fv, b.eid buy_eid
            FROM read_parquet({N}, hive_partitioning=1) n
            LEFT JOIN buy b ON b.notice_id=n.notice_id
            WHERE n.notice_kind='can'),
          tender AS (
            SELECT l.award_notice_id, t.estimated_value tev
            FROM read_parquet({ATL}) l
            JOIN read_parquet({N}, hive_partitioning=1) t ON t.notice_id=l.tender_notice_id
            WHERE t.estimated_value > 0),
          pred AS (
            SELECT cs.successor succ, median(coalesce(p.final_value, p.estimated_value)) pv
            FROM read_parquet({CS}) cs
            JOIN read_parquet({N}, hive_partitioning=1) p ON p.notice_id=cs.predecessor
            WHERE coalesce(p.final_value, p.estimated_value) > 0 GROUP BY cs.successor),
          -- Mediane aus Zuschlägen MIT echtem Wert (fv>0). Der Anker wird per Billing-
          -- Regel nur bei Zuschlägen OHNE echten Wert genutzt (has_real_value=false) —
          -- die tragen kein fv, sind also nicht in diesen Medianen: **Leave-one-out
          -- per Konstruktion** für den Wächter-Anwendungsfall (kein Self-Inclusion).
          bc_med AS (SELECT buy_eid, cpv4, median(fv) m FROM can WHERE fv>0
                     GROUP BY 1,2 HAVING count(*)>=6),
          b_med AS (SELECT buy_eid, median(fv) m FROM can WHERE fv>0
                    GROUP BY 1 HAVING count(*)>=6),
          c_med AS (SELECT cpv4, median(fv) m FROM can WHERE fv>0
                    GROUP BY 1 HAVING count(*)>=10)
          SELECT can.notice_id,
            coalesce(t.tev, pr.pv, bc.m, b.m, c.m) AS anchor_value,
            {_band_sql('coalesce(t.tev, pr.pv, bc.m, b.m, c.m)')} AS anchor_band,
            CASE WHEN t.tev IS NOT NULL THEN 'tender'
                 WHEN pr.pv IS NOT NULL THEN 'predecessor'
                 WHEN bc.m IS NOT NULL THEN 'buyer_cpv'
                 WHEN b.m IS NOT NULL THEN 'buyer'
                 WHEN c.m IS NOT NULL THEN 'cpv' ELSE 'none' END AS anchor_source,
            (can.fv IS NOT NULL AND can.fv > 0) AS has_real_value
          FROM can
          LEFT JOIN tender t ON t.award_notice_id=can.notice_id
          LEFT JOIN pred pr ON pr.succ=can.notice_id
          LEFT JOIN bc_med bc ON bc.buy_eid=can.buy_eid AND bc.cpv4=can.cpv4
          LEFT JOIN b_med b ON b.buy_eid=can.buy_eid
          LEFT JOIN c_med c ON c.cpv4=can.cpv4
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


# Leads ohne CPV bekommen eine EIGENE Kategorie statt hinauszufallen. Die CPV-Pflicht fiel
# am 2026-08-14 aus `build_prospective_leads` — 645 laufende Ausschreibungen (DE: 239 DOeE,
# 68 NetServer; AT/CH: 0) waren dadurch unsichtbar, obwohl Titel, Kaeufer und Frist da sind.
#
# Einen CPV zu ERFINDEN waere der falsche Weg: eine geratene Division verfaelschte die
# Branchenzaehlung und liesse den Lead in einer Fachsuche auftauchen, in die er nicht
# gehoert. Die eigene Kategorie ist ehrlich — der Nutzer sieht, dass die Einordnung fehlt,
# und findet den Lead trotzdem. Das Label fuehrt auch das Frontend (`explorerCore.js`).
OHNE_KATEGORIE = "Ohne Kategorie"


def _ANR_SQL(cfg: Config, country: str) -> str:
    """SQL-Quelle fuer ``notice_enrichment`` — die Ausgabe der Dubletten-Firewall.

    Die Anreicherung ist fuer JEDEN Verbraucher **optional**. Fehlt die Datei (frischer
    Klon, neues Land, Firewall im Tageslauf fehlgeschlagen), liefert diese Quelle eine
    leere Menge und der jeweilige Wasserfall verhaelt sich exakt wie vorher. Kein Bauer
    bekommt eine harte Abhaengigkeit von einem Schritt, der schiefgehen darf.

    Als Helfer herausgezogen, weil es inzwischen zwei Verbraucher gibt
    (``build_lead_deadline`` fuer Fristen, ``build_lead_geo`` fuer den Leistungsort) und
    die Fehlt-Datei-Behandlung an beiden Stellen dieselbe sein muss. Zwei Kopien waeren
    genau die Art Verzweigung, die spaeter nur an einer Stelle nachgezogen wird.
    """
    p = cfg.gold_dir / country / "notice_enrichment.parquet"
    if p.exists():
        return f"read_parquet('{p.as_posix()}')"
    # ⚠ Die leere Ersatzmenge muss JEDE Spalte fuehren, die ein Verbraucher anfasst — sonst
    # ist die „optionale" Anreicherung genau dann ein harter Fehler, wenn sie fehlt.
    # Gemessen: `_frist_joins_sql` joint auf `quelle_notice_id`; ohne die Spalte bricht
    # `build_leads` und `build_prospective_leads` mit „Referenced table \"c\" not found".
    # Die Tests dazu waren Quelltext-Zusicherungen und konnten das nicht sehen.
    return ("(SELECT NULL::VARCHAR AS notice_id, NULL::VARCHAR AS feld,"
            " NULL::VARCHAR AS wert, NULL::VARCHAR AS quelle_notice_id,"
            " NULL::VARCHAR AS quelle_gen WHERE false)")


def build_lead_deadline(cfg: Config, country: str = "DE"):
    """Angebotsfrist je offener Ausschreibung — der **primäre Timing-Alert** (#9, Flip).

    „Angebotsfrist naht" schlägt „Vertrag läuft aus" (nur 18 % `end_date`): `cn`-Notices
    tragen zu ~63 % ein echtes `submission_deadline`. Wo es fehlt, ist die Schätzung
    **belastbar**, weil Angebotsfristen gesetzlich mindestgeregelt sind (Bid-Fenster
    Median ~31 T, stddev 12 T). Waterfall: echt → CPV-Median-Fenster → globaler Median.
    Schreibt ``lead_deadline`` (notice_id, deadline_date, deadline_source, days_from_pub).
    """

    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    out = (g / "lead_deadline.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    ANRQ = _ANR_SQL(cfg, country)
    con.execute(f"""
        COPY (
          WITH win AS (
            SELECT substr(cpv_main,1,4) cpv4,
                   median(datediff('day', publication_date, submission_deadline)) m
            FROM read_parquet({N}, hive_partitioning=1)
            WHERE submission_deadline IS NOT NULL AND publication_date IS NOT NULL
              AND datediff('day', publication_date, submission_deadline) BETWEEN 0 AND 365
            GROUP BY 1 HAVING count(*) >= 10),
          gm AS (
            SELECT median(datediff('day', publication_date, submission_deadline)) m
            FROM read_parquet({N}, hive_partitioning=1)
            WHERE submission_deadline IS NOT NULL AND publication_date IS NOT NULL
              AND datediff('day', publication_date, submission_deadline) BETWEEN 0 AND 365)
          SELECT n.notice_id,
            -- WASSERFALL: eigene Frist → uebernommene aus einer Dublette → geschaetzt.
            -- Die mittlere Stufe ist neu (2026-08-13). `notice_enrichment` traegt Fristen,
            -- die ein anderer Satz DESSELBEN Verfahrens hat und dieser nicht — belegt ueber
            -- identische Vergabestelle UND Titel-Enthaltung >=0,8 (Stufe `kaeufer_und_titel`,
            -- die einzige, aus der angereichert wird). Ohne sie waeren diese Fristen bekannt
            -- und wuerden trotzdem geschaetzt.
            -- VOR der eigenen Frist steht die Verlaengerung: sie korrigiert einen
            -- vorhandenen, aber ueberholten Wert. Das ist der einzige Fall, in dem eine
            -- Dublette einen belegten Wert schlaegt — und er ist auf eindeutige 1:1-Paare
            -- begrenzt (Herleitung im Docstring von `dedupe.anreichern`).
            CASE WHEN vrl.wert IS NOT NULL THEN try_cast(vrl.wert AS DATE)
                 WHEN n.submission_deadline IS NOT NULL THEN n.submission_deadline::DATE
                 WHEN anr.wert IS NOT NULL THEN try_cast(anr.wert AS DATE)
                 ELSE (n.publication_date + (CAST(coalesce(win.m, gm.m) AS INT) * INTERVAL 1 DAY))::DATE
            END AS deadline_date,
            -- Eigene Herkunftsstufe, nicht als 'echt' getarnt: die Frist ist belegt, stammt
            -- aber aus einem anderen Satz. Wer sie benutzt, soll das sehen koennen.
            CASE WHEN vrl.wert IS NOT NULL THEN 'echt_verlaengert'
                 WHEN n.submission_deadline IS NOT NULL THEN 'echt'
                 WHEN anr.wert IS NOT NULL THEN 'echt_aus_dublette'
                 WHEN win.m IS NOT NULL THEN 'geschaetzt_cpv'
                 ELSE 'geschaetzt_global' END AS deadline_source,
            CAST(coalesce(win.m, gm.m) AS INT) AS est_window_days
          FROM read_parquet({N}, hive_partitioning=1) n
          LEFT JOIN win ON win.cpv4 = substr(n.cpv_main,1,4)
          LEFT JOIN (SELECT notice_id, min(wert) AS wert FROM {ANRQ}
                     WHERE feld='submission_deadline' GROUP BY 1) anr USING (notice_id)
          -- max(): bei mehreren belegten Verlaengerungen gilt die spaeteste. Die
          -- Eindeutigkeitspruefung sitzt in `dedupe`, das hier ist nur der Gleichstand.
          LEFT JOIN (SELECT notice_id, max(wert) AS wert FROM {ANRQ}
                     WHERE feld='submission_deadline_verlaengert' GROUP BY 1) vrl
                 USING (notice_id)
          CROSS JOIN gm
          -- Echte Frist braucht KEIN publication_date; nur die Schätzung tut es.
          -- (Bug-Fix: sonst fielen 4.360 offene cn mit echtem Datum ohne pub raus.)
          WHERE n.notice_kind IN ('cn','pin')
            AND (n.submission_deadline IS NOT NULL OR n.publication_date IS NOT NULL)
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_duration_calibration(cfg: Config, country: str = "DE"):
    """Selbstlernende Korrektur des prognostizierten Vertragsendes.

    Wir sagen „dieser Vertrag endet am X, dann kommt die Nachausschreibung". Ob das
    stimmt, wussten wir bisher nicht — es wurde nirgends gemessen. Diese Tabelle misst es
    an der eigenen Historie: für jede belegte Nachfolge-Kante (`contract_succession`) den
    Abstand zwischen dem prognostizierten Ende des Vorgängers und dem Tag, an dem der
    Nachfolger tatsächlich veröffentlicht wurde.

    Der Versatz ist NICHT global — er hängt stark vom Gewerk ab (gemessen, Median in Tagen):
        CPV 71 Ingenieurleistungen  −592     CPV 34 Fahrzeuge      0
        CPV 72 IT-Dienste           −577     CPV 30 Büro         +31
        CPV 90 Entsorgung           −458     CPV 38 Labor       +303
    Eine einheitliche Korrektur wäre für die Hälfte der Divisionen falsch. Deshalb je
    (Herkunft des Enddatums × CPV-Division), mit globalem Rückfall, wo die Belege dünn sind.

    „Selbstlernend" heißt hier: die Tabelle wird bei JEDEM Gold-Lauf neu aus den dann
    vorhandenen Ketten gerechnet. Je mehr Nachfolgen belegt sind, desto belastbarer die
    Korrektur — ohne Modell, ohne Training, nur gemessen.

    Ausreißer-Schutz: Paare mit über 4 Jahren Abstand sind keine Nachfolge-Beziehung mehr,
    sondern Zufall — sie fliegen raus, sonst zieht ein einzelner Fall den Median.
    """

    G = cfg.gold_dir / country
    N = cfg.silver_table_glob("notices", country)
    con = _db.connect(); con.execute("SET threads=4")
    SUC, DUR = G / "contract_succession.parquet", G / "lead_duration.parquet"
    out = G / "duration_calibration.parquet"
    if not SUC.exists() or not DUR.exists():
        con.close()
        return 0

    MIN_BELEGE = 100          # darunter ist ein Median Rauschen, nicht Signal
    MAX_ABSTAND = 1460        # 4 Jahre — darüber keine plausible Nachfolge mehr

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE paare AS
        WITH p AS (
          SELECT notice_id, max(publication_date) AS pub, substr(max(cpv_main), 1, 2) AS div
          FROM '{N}' GROUP BY 1)
        SELECT d.duration_source, pv.div,
               date_diff('day', d.contract_end, ps.pub) AS versatz
        FROM '{SUC}' s
        JOIN '{DUR}' d  ON d.notice_id = s.predecessor
        JOIN p pv ON pv.notice_id = s.predecessor
        JOIN p ps ON ps.notice_id = s.successor
        WHERE d.contract_end IS NOT NULL AND ps.pub IS NOT NULL
          AND abs(date_diff('day', d.contract_end, ps.pub)) <= {MAX_ABSTAND}
    """)
    con.execute(f"""
        COPY (
          WITH je_div AS (
            SELECT duration_source, div, count(*) AS belege,
                   round(median(versatz)) AS versatz_tage,
                   round(quantile_cont(versatz, 0.25)) AS p25,
                   round(quantile_cont(versatz, 0.75)) AS p75
            FROM paare GROUP BY 1, 2 HAVING count(*) >= {MIN_BELEGE}),
          global AS (
            SELECT duration_source, NULL AS div, count(*) AS belege,
                   round(median(versatz)) AS versatz_tage,
                   round(quantile_cont(versatz, 0.25)) AS p25,
                   round(quantile_cont(versatz, 0.75)) AS p75
            FROM paare GROUP BY 1)
          SELECT *, (p75 - p25) AS spanne_tage FROM je_div
          UNION ALL BY NAME
          SELECT *, (p75 - p25) AS spanne_tage FROM global
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
    con.close()
    return n


def build_lead_duration(cfg: Config, country: str = "DE"):
    """Vertragslaufzeit/-ende je Lead — für „bis Auslauf" (#3 Lead-Detail) + sekundären
    Auslauf-Alert (#9).

    `end_date` fehlt oft (17,7 % bei Vergaben) → **CPV-Median-Laufzeit** als Schätzung,
    ehrlich geflaggt (nie ein datierter Countdown auf geratenem Ende). Waterfall:
    echtes `end_date` → `start_date` + CPV-Median-Laufzeit → unbekannt.

    **Kalibrierung (`duration_calibration`).** Das rohe Ende sagt, wann der Vertrag endet —
    nicht, wann die Nachausschreibung kommt. Gemessen an 84.890 belegten Nachfolge-Kanten
    erscheint sie im Median deutlich VORHER, und wie viel früher hängt stark vom Gewerk ab
    (CPV 71: −592 Tage, CPV 34: 0, CPV 38: +303). `contract_end_kal` trägt diese Korrektur;
    `contract_end` bleibt unangetastet, damit das gemessene Rohdatum nachvollziehbar ist —
    und damit der nächste Kalibrier-Lauf nicht auf einer bereits korrigierten Zahl misst.

    Schreibt ``lead_duration`` (notice_id, contract_end, contract_end_kal, kal_versatz_tage,
    kal_spanne_tage, duration_days, duration_source).
    """

    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    out = (g / "lead_duration.parquet").as_posix()
    tmp = (g / "_lead_duration_roh.parquet").as_posix()
    KAL = g / "duration_calibration.parquet"
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH dur AS (   -- Vertragsdauer (start→end) je CPV
            SELECT substr(cpv_main,1,4) cpv4,
                   median(datediff('day', start_date, end_date)) m
            FROM read_parquet({N}, hive_partitioning=1)
            WHERE start_date IS NOT NULL AND end_date IS NOT NULL
              AND datediff('day', start_date, end_date) BETWEEN 1 AND 3650
            GROUP BY 1 HAVING count(*) >= 10),
          durA AS (   -- award→Ende-Spanne je CPV (enthält den award→start-Versatz)
            SELECT substr(cpv_main,1,4) cpv4,
                   median(datediff('day', award_date, end_date)) m
            FROM read_parquet({N}, hive_partitioning=1)
            WHERE award_date IS NOT NULL AND end_date IS NOT NULL
              AND datediff('day', award_date, end_date) BETWEEN 1 AND 3650
            GROUP BY 1 HAVING count(*) >= 10)
          SELECT n.notice_id,
            CASE WHEN n.end_date IS NOT NULL THEN n.end_date::DATE
                 WHEN n.start_date IS NOT NULL AND dur.m IS NOT NULL
                   THEN (n.start_date + (CAST(dur.m AS INT) * INTERVAL 1 DAY))::DATE
                 WHEN n.award_date IS NOT NULL AND coalesce(durA.m, dur.m) IS NOT NULL
                   THEN (n.award_date + (CAST(coalesce(durA.m, dur.m) AS INT) * INTERVAL 1 DAY))::DATE
                 ELSE NULL END AS contract_end,
            CASE WHEN n.end_date IS NOT NULL THEN datediff('day', n.start_date, n.end_date)
                 WHEN dur.m IS NOT NULL THEN CAST(dur.m AS INT)
                 WHEN durA.m IS NOT NULL THEN CAST(durA.m AS INT) ELSE NULL END AS duration_days,
            CASE WHEN n.end_date IS NOT NULL THEN 'echt'
                 WHEN n.start_date IS NOT NULL AND dur.m IS NOT NULL THEN 'geschaetzt_start'
                 WHEN n.award_date IS NOT NULL AND coalesce(durA.m, dur.m) IS NOT NULL THEN 'geschaetzt_award'
                 ELSE 'unbekannt' END AS duration_source
          , substr(n.cpv_main,1,2) AS _div
          FROM read_parquet({N}, hive_partitioning=1) n
          LEFT JOIN dur ON dur.cpv4 = substr(n.cpv_main,1,4)
          LEFT JOIN durA ON durA.cpv4 = substr(n.cpv_main,1,4)
          WHERE n.notice_kind IN ('can','cn')
        ) TO '{tmp}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    # Kalibrierung anhängen: je (Herkunft × CPV-Division), mit globalem Rückfall dort, wo
    # die Division zu wenige Belege hat. Fehlt die Tabelle (erster Lauf), bleibt kal = roh.
    if KAL.exists():
        con.execute(f"""
            COPY (
              SELECT d.* EXCLUDE (_div),
                coalesce(kd.versatz_tage, kg.versatz_tage, 0)::INT AS kal_versatz_tage,
                coalesce(kd.spanne_tage, kg.spanne_tage)::INT      AS kal_spanne_tage,
                CASE WHEN d.contract_end IS NULL THEN NULL
                     ELSE (d.contract_end
                           + (coalesce(kd.versatz_tage, kg.versatz_tage, 0)::INT * INTERVAL 1 DAY))::DATE
                END AS contract_end_kal
              FROM read_parquet('{tmp}') d
              LEFT JOIN read_parquet('{KAL}') kd
                     ON kd.duration_source = d.duration_source AND kd.div = d._div
              LEFT JOIN read_parquet('{KAL}') kg
                     ON kg.duration_source = d.duration_source AND kg.div IS NULL
            ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
    else:
        con.execute(f"""COPY (SELECT * EXCLUDE (_div), 0 AS kal_versatz_tage,
            NULL::INT AS kal_spanne_tage, contract_end AS contract_end_kal
            FROM read_parquet('{tmp}')) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    Path(tmp).unlink(missing_ok=True)
    return n


def build_entity_identity(cfg: Config, country: str = "DE"):
    """„Gruppe = Identität"-Auflösung (P0-3) — jede Entity → stabile `identity_id`.

    Fundament für **Winner-Matching** (#6/#9: Zuschlag-Gewinner → alle Schwester-
    Entities der Gruppe) und **Onboarding** (#7: „Das bin ich" bestätigt eine Gruppe).
    `identity_id` = Gruppen-ID, wo die Entity in einer ``entity_group`` steckt, sonst
    ``solo:<entity_id>`` (Einzel-Firma). So spannt jede Identität genau die zusammen-
    gehörigen Entities. Matching-Regel: Gewinner und bestätigte User-Identität teilen
    dieselbe `identity_id`. Schreibt ``entity_identity`` (entity_id, identity_id,
    in_group, group_size, canonical_name).
    """

    g = cfg.gold_dir / country
    def q(name): return f"'{(g / name).as_posix()}'"
    out = (g / "entity_identity.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH ident AS (
            SELECT e.entity_id, e.canonical_name,
                   coalesce(eg.group_id, 'solo:' || e.entity_id) AS identity_id,
                   (eg.group_id IS NOT NULL) AS in_group
            FROM read_parquet({q('entities.parquet')}) e
            LEFT JOIN read_parquet({q('entity_group.parquet')}) eg ON eg.entity_id = e.entity_id)
          SELECT entity_id, identity_id, in_group, canonical_name,
                 count(*) OVER (PARTITION BY identity_id) AS group_size
          FROM ident
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_detail(cfg: Config, country: str = "DE"):
    """UI-Sicht je Lead — führt ``leads`` mit den **ehrlichen Flags** zusammen (P0-6).

    Das Frontend (Lead-Detail #3) bekommt so alle Herkunfts-Kennzeichnungen an einer
    Stelle: Pricing-Band + `band_source`, verbessertes Vertragsende + `duration_source`,
    Angebotsfrist + `deadline_source`, Incumbent-Tenure. 1:1 zu ``leads`` (lead_id).
    Leitregel: was geschätzt ist, trägt seine Quelle — nie als Fakt getarnt.
    Schreibt ``lead_detail``.
    """

    g = cfg.gold_dir / country
    def q(name): return f"'{(g / name).as_posix()}'"
    out = (g / "lead_detail.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          SELECT l.*,
            vbe.band_effektiv, vbe.band_source, vbe.value_effektiv,
            ld.contract_end   AS contract_end_eff,
            -- Kalibriertes Ende NEBEN dem rohen: das rohe bleibt nachvollziehbar, das
            -- kalibrierte sagt, wann die Nachausschreibung erfahrungsgemäß erscheint.
            ld.contract_end_kal AS contract_end_cal,
            ld.kal_versatz_tage AS cal_offset_days,
            ld.kal_spanne_tage  AS cal_spread_days,
            ld.duration_days  AS duration_days_eff,
            ld.duration_source,
            dl.deadline_date, dl.deadline_source,
            it.incumbent_since_year, it.tenure_years
          FROM read_parquet({q('leads.parquet')}) l
          LEFT JOIN read_parquet({q('value_band_effektiv.parquet')}) vbe ON vbe.lead_id = l.lead_id
          LEFT JOIN read_parquet({q('lead_duration.parquet')}) ld ON ld.notice_id = l.lead_id
          LEFT JOIN read_parquet({q('lead_deadline.parquet')}) dl ON dl.notice_id = l.lead_id
          LEFT JOIN read_parquet({q('incumbent_tenure.parquet')}) it ON it.notice_id = l.lead_id
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def _kategorie_join_sql(cfg: Config, country: str, auf: str = "n.notice_id") -> str:
    """LEFT JOIN auf die abgeleitete Kategorie (`govisor.kategorie`), als ``katq``.

    OPTIONAL wie die Anreicherung: fehlt die Datei, liefert die Quelle eine leere Menge und
    der Lead bleibt „Ohne Kategorie". Die leere Ersatzmenge fuehrt ALLE Spalten, die ein
    Verbraucher anfasst — genau daran ist `_ANR_SQL` am 2026-08-14 mit einem harten
    BinderException gescheitert, weil eine Spalte fehlte.
    """
    p = cfg.gold_dir / country / "lead_kategorie.parquet"
    quelle = (f"read_parquet('{p.as_posix()}')" if p.exists()
              else "(SELECT NULL::VARCHAR AS notice_id, NULL::VARCHAR AS division,"
                   " NULL::VARCHAR AS branche, NULL::VARCHAR AS quelle,"
                   " NULL::VARCHAR AS modell, NULL::VARCHAR AS stand WHERE false)")
    return f"\n          LEFT JOIN {quelle} katq ON katq.notice_id = {auf}"


def _frist_joins_sql(cfg: Config, country: str, auf: str = "n.notice_id") -> str:
    """LEFT JOINs für die angereicherten Felder: Fristen (``anrq``/``vrlq``) und Wert
    samt Währung (``wrtq``). Wert und Währung kommen aus DEMSELBEN Quellsatz, sonst
    liesse sich die Währungssperre nicht anwenden."""
    ANR = _ANR_SQL(cfg, country)
    return f"""
          -- `arg_min(x, k)` = x aus der Zeile mit kleinstem k. Zwei Fehler auf einmal:
          --
          -- (1) `min(wert)` war ein LEXIKOGRAPHISCHES Minimum ueber Zahl-als-Text. Gemessen
          --     an AT: 1.312 Bekanntmachungen mit widerspruechlichen Werten, bei 650 war die
          --     Wahl nicht das numerische Minimum, bei 29 fiel sie aus dem Plausibilitaets-
          --     band und der Wert wurde still „unbekannt". Beispiel 179464_2026: aus
          --     460k…77,5M wurde 10.172.841,38 gewaehlt, weil „1" zuerst sortiert.
          -- (2) Wert und Waehrung kamen aus ZWEI unabhaengigen Aggregaten, konnten also aus
          --     verschiedenen Quellsaetzen stammen — die dokumentierte Kopplung galt nicht.
          --     Heute latent (0 widerspruechliche Waehrungen), scharf bei jeder Waehrung,
          --     die hinter 'EUR' sortiert (GBP/HUF/USD). Fuer eine EU-weite Engine zaehlt das.
          --
          -- Beide `arg_min` benutzen DENSELBEN Schluessel, also dieselbe Zeile. Das Minimum
          -- ist die konservative Wahl: es untertreibt das Gebuehrenband, statt zu ueberziehen.
          LEFT JOIN (SELECT w.notice_id,
                            arg_min(w.wert, try_cast(w.wert AS DOUBLE)) AS w,
                            arg_min(c.wert, try_cast(w.wert AS DOUBLE)) AS waehrung
                     FROM {ANR} w
                     LEFT JOIN {ANR} c ON c.notice_id = w.notice_id
                                      AND c.quelle_notice_id = w.quelle_notice_id
                                      AND c.feld = 'estimated_value_waehrung'
                     WHERE w.feld = 'estimated_value'
                       AND try_cast(w.wert AS DOUBLE) IS NOT NULL
                     GROUP BY 1) wrtq
                 ON wrtq.notice_id = {auf}
          LEFT JOIN (SELECT notice_id, min(wert) w FROM {ANR}
                     WHERE feld='submission_deadline' GROUP BY 1) anrq ON anrq.notice_id = {auf}
          LEFT JOIN (SELECT notice_id, max(wert) w FROM {ANR}
                     WHERE feld='submission_deadline_verlaengert' GROUP BY 1) vrlq
                 ON vrlq.notice_id = {auf}"""


# Die effektive Angebotsfrist. EINE Definition fuer alle Verbraucher.
#
# Sie stand vorher zweimal im Code und lief auseinander: `build_lead_deadline` rechnete den
# vollen Wasserfall, `build_prospective_leads` entschied die Lead-ZUGEHOERIGKEIT an der rohen
# Silber-Frist. Folge, gemessen 2026-08-13: von 40 Bekanntmachungen mit korrigierter
# (verlaengerter) Frist standen **0** in `leads.parquet`. Die Korrektur landete in einer
# Tabelle, die ueber die Zugehoerigkeit nicht entscheidet — der Lead blieb draussen, nur sein
# Datum stimmte. Dieselbe Divergenz haette den Zweitquellen-Ausschluss 180 gueltige Leads
# kosten lassen (AT 156, CH 18, DE 6): deren Master traegt seine Frist NUR aus der
# Anreicherung, war damit selbst nicht lead-faehig — und die Dublette waere trotzdem geflogen.
#
# Reihenfolge wie im Wasserfall von `build_lead_deadline`: Verlaengerung schlaegt eigene
# Frist (sie korrigiert einen ueberholten Wert), eigene Frist schlaegt uebernommene.
_FRIST_EFF = ("coalesce(try_cast(vrlq.w AS DATE), n.submission_deadline::DATE,"
              " try_cast(anrq.w AS DATE))")


def _redundante_zweitquelle_sql(cfg: Config, country: str, spalte: str = "n.notice_id",
                                stichtag: str | None = None) -> str:
    """SQL-Bedingung: schliesst Saetze aus, die eine Zweitquelle DOPPELT liefert.

    Die einzige Stelle, an der die Dubletten-Firewall wirklich etwas ENTFERNT. Ueberall
    sonst markiert und ergaenzt sie nur. Entsprechend eng ist die Bedingung — sie gilt
    ausschliesslich fuer Saetze, die

      1. mit dem staerksten Beleg als Dublette erkannt sind (`kaeufer_und_titel`,
         also identische Vergabestelle UND Titel-Enthaltung >= 0,8 nach Zahlen- und
         Geschwister-Sperre), UND
      2. deren MASTER heute noch ein brauchbarer Lead ist.

    Bedingung 2 ist der Kern. Ohne sie waere das genau der Ausschluss, der beim ersten
    Entwurf gemessen und verworfen wurde: 64 gueltige Leads gegen 6 echte Dubletten, weil
    der Master abgelaufen war und nur die Dublette lief. Fuer DTVP nachgemessen 2026-08-13:
    von 45 belegten Dubletten haetten 11 (24 %) genau dieses Problem. Sie bleiben stehen.

    Die Frist des Masters wird dabei so gelesen, wie das Produkt sie spaeter zeigt —
    inklusive der aus dem Zwilling uebernommenen und der VERLAENGERTEN. Sonst wuerde die
    Firewall eine Zeile wegwerfen, deren Information sie selbst gerade uebertragen hat.
    `lead_deadline` wird hier bewusst NICHT gelesen: die Tabelle entsteht erst spaeter im
    Lauf, eine Abhaengigkeit darauf waere eine Reihenfolgen-Falle.

    Fehlt `notice_duplicates.parquet`, liefert die Funktion einen leeren String — der
    Bauer verhaelt sich dann wie vor der Firewall.
    """
    dup = cfg.gold_dir / country / "notice_duplicates.parquet"
    if not dup.exists():
        return ""
    NS = f"'{cfg.silver_table_glob('notices', country)}'"
    ANR = _ANR_SQL(cfg, country)
    # DERSELBE Stichtag wie die Lead-Zugehoerigkeit, nicht `current_date`. Sonst laufen
    # Ausschluss und Zugehoerigkeit bei einem `--as-of` auseinander: in der Zukunft flöge die
    # Dublette raus, waehrend der Master noch nicht lead-faehig ist — die Vergabe verschwaende
    # ganz, also genau der 64-Leads-Verlust, den diese Bedingung verhindern soll. In der
    # Vergangenheit liefe der Ausschluss leer und die Dubletten blieben stehen.
    _ST = f"DATE '{stichtag}'" if stichtag else "current_date"
    return f"""
            AND {spalte} NOT IN (
              SELECT d.duplicate_id
              FROM read_parquet('{dup.as_posix()}') d
              JOIN read_parquet({NS}, hive_partitioning=1) m ON m.notice_id = d.master_id
              LEFT JOIN (SELECT notice_id, min(wert) w FROM {ANR}
                         WHERE feld='submission_deadline' GROUP BY 1) a
                     ON a.notice_id = d.master_id
              LEFT JOIN (SELECT notice_id, max(wert) w FROM {ANR}
                         WHERE feld='submission_deadline_verlaengert' GROUP BY 1) v
                     ON v.notice_id = d.master_id
              WHERE d.beleg = 'kaeufer_und_titel'
                -- ⚠ EIN EINZIGES NULL WUERDE DIESE BEDINGUNG TOETEN — und zwar in die
                -- teure Richtung. `x NOT IN (…, NULL)` ist fuer JEDES x niemals wahr
                -- (x <> NULL ergibt UNKNOWN), also faellt nicht die Dublette raus,
                -- sondern der GESAMTE Bestand: `build_leads` liefe auf eine leere
                -- Leadtabelle. Nachgestellt am 2026-08-25 an einer Nachbildung —
                -- 3 Saetze, 1 Treffer: ohne NULL bleiben 2 uebrig, mit NULL null.
                -- Gemessen tragen `duplicate_id` in DE/AT/CH heute 0 NULL; die Bedingung
                -- soll aber nicht davon abhaengen, dass das so bleibt.
                AND d.duplicate_id IS NOT NULL
                AND coalesce(try_cast(v.w AS DATE),
                             CAST(m.submission_deadline AS DATE),
                             try_cast(a.w AS DATE)) >= {_ST})"""


def build_prospective_leads(cfg: Config, country: str = "DE", reference_date: str | None = None):
    """F01/F02 (pin/cn) als Lead-Zeilen — der Blick nach vorn VOR der Vergabe (#1).

    Der Auslauf-Radar (``build_leads``) speist nur ``can``. Diese Funktion hängt
    **zusätzliche Zeilen** ans bestehende ``leads``-Parquet: laufende Ausschreibungen
    (``cn``, ``source='f02'``) und Vorinformationen (``pin``, ``source='f01'``) mit
    zukünftiger Angebotsfrist. Gleiches Schema; awarded-only-Felder (Incumbent,
    Wechsel-Score, num_tenders, Vertragsende) bleiben **NULL** (noch nicht vergeben) —
    ``UNION ALL BY NAME`` füllt sie automatisch. Muss NACH ``build_displaceability``
    laufen (dann trägt ``leads`` die Score-Spalten, die hier NULL werden).

    Gibt die Zahl der angehängten prospektiven Leads zurück.
    """
    from datetime import date

    ref = reference_date or date.today().isoformat()
    g = cfg.gold_dir / country
    N = cfg.silver_table_glob("notices", country)
    NP = cfg.silver_table_glob("notice_parties", country)
    PE, EN, Q, DC, DD, LD = (str(g / t) for t in
                             ("party_entity.parquet", "entities.parquet", "quality.parquet",
                              "dim_cpv.parquet", "dim_deflator.parquet", "leads.parquet"))
    con = _db.connect(); con.execute("SET threads=3")
    con.execute(f"""
        CREATE TABLE buyer AS
        SELECT pe.notice_id, pe.entity_id, e.canonical_name AS buyer_name, e.confidence AS buyer_conf,
               np.town AS buyer_town, np.nuts AS buyer_nuts, np.email AS buyer_email, np.url AS buyer_url
        FROM (SELECT notice_id, min(seq) seq FROM '{PE}' WHERE role='buyer' GROUP BY 1) b
        JOIN '{PE}' pe ON pe.notice_id=b.notice_id AND pe.role='buyer' AND pe.seq=b.seq
        JOIN '{EN}' e ON e.entity_id=pe.entity_id
        LEFT JOIN '{NP}' np ON np.notice_id=pe.notice_id AND np.role='buyer' AND np.seq=pe.seq
    """)
    # Wert: eigener Schaetzwert, sonst der aus dem Zwilling. Die zweite Stufe kam mit der
    # Dubletten-Firewall (2026-08-14) und ersetzt, was vorher im geloeschten
    # `dedupe_at_sources.py` stand — dort ging sie beim Umzug zunaechst verloren.
    #
    # Warum sie zaehlt: `atverg` fuehrt den Schaetzwert zu 69,8 %, TED-AT nur zu 11,0 %.
    # Gemessen 2026-08-14: 3.922 oesterreichische Leads ohne Wert bekommen dadurch einen,
    # und der Wert traegt das Gebuehrenband.
    #
    # DIE WAEHRUNGSSPERRE GILT FUER BEIDE STUFEN. Ein uebernommener Wert ohne seine
    # Waehrung waere keine Information, sondern eine Falle — deshalb reicht `anreichern()`
    # die Waehrung als eigene Zeile aus DEMSELBEN Quellsatz mit, und sie wird hier genauso
    # geprueft wie die eigene. Der Kommentar des abgeloesten Skripts sagte es richtig:
    # „damit keine Fremdwaehrung stillschweigend als Euro gilt".
    _plaus = "BETWEEN 1000 AND 1e9"
    VU = (f"coalesce("
          f"CASE WHEN n.estimated_value {_plaus} "
          f"     AND (n.value_currency='EUR' OR n.value_currency IS NULL) "
          f"     THEN n.estimated_value END, "
          f"CASE WHEN try_cast(wrtq.w AS DOUBLE) {_plaus} "
          f"     AND (wrtq.waehrung='EUR' OR wrtq.waehrung IS NULL) "
          f"     THEN try_cast(wrtq.w AS DOUBLE) END)")
    VUR = f"({VU} * dd.factor_to_2020)"
    out = g / "leads.parquet"
    con.execute(f"""
        COPY (
          SELECT * FROM '{LD}'
          UNION ALL BY NAME
          SELECT
            n.notice_id AS lead_id,
            CASE n.notice_kind WHEN 'cn' THEN 'f02' ELSE 'f01' END AS source,
            b.entity_id AS buyer_entity, b.buyer_name, b.buyer_town, b.buyer_nuts,
            b.buyer_email, b.buyer_url, n.ted_url,
            n.title AS titel, n.description AS beschreibung,
            n.cpv_main, substr(n.cpv_main,1,4) AS cpv_class,
            -- WASSERFALL: veroeffentlichter CPV → abgeleitete Kategorie → „Ohne Kategorie".
            -- `branche_source` traegt die Herkunft mit, damit im Produkt sichtbar bleibt,
            -- wie sicher die Einordnung ist (dieselbe Konvention wie `deadline_source`).
            coalesce(dc.branche, katq.branche, '{OHNE_KATEGORIE}') AS branche,
            coalesce(dc.sector,  katq.branche, '{OHNE_KATEGORIE}') AS sector,
            CASE WHEN dc.branche  IS NOT NULL THEN 'cpv'
                 WHEN katq.quelle IS NOT NULL THEN katq.quelle
                 ELSE 'ohne' END AS branche_source,
            {_FRIST_EFF} AS contract_end,
            date_diff('month', DATE '{ref}', {_FRIST_EFF}) AS months_to_expiry,
            CASE n.notice_kind WHEN 'cn' THEN 'Angebotsfrist' ELSE 'Vorinformation' END AS faellig_basis,
            -- ⚠ HIER STAND `true` — UND DAMIT GALT JEDE OFFENE AUSSCHREIBUNG ALS PLAUSIBEL.
            --
            -- Der Auslauf-Zweig oben liest dieselbe Aussage aus den Qualitaetsflags
            -- (`laufzeit_unplausibel`); dieser Zweig behauptete sie. Folge, gemessen am
            -- 2026-09-05: 73 ausgelieferte f02-Leads trugen eine Vertragslaufzeit von 26 bis
            -- 169 Jahren (Median 48) — und `timing_source` stand auf 'actual', der Wert ging
            -- also UNMARKIERT hinaus. Die Qualitaetspruefung hatte sie laengst erkannt und
            -- in `review_queue` gelegt, wo sie niemand liest.
            --
            -- Das ist der Markenkern, an genau der Stelle, an der er gilt: „Gemessenes ist
            -- gemessen, Geschaetztes ist markiert." Eine Laufzeit von 169 Jahren ist kein
            -- gemessener Wert, sondern ein erkannter Datenfehler.
            coalesce(NOT list_has_any(q.quality_flags,
                   ['laufzeit_unplausibel','ende_vor_vergabe','datum_absurd',
                    'datum_start_nach_ende']), true)
                                                      AS termin_plausibel,
            {_kind_sql('n.title', 'n.cpv_main')} AS contract_kind,
            {VU} AS value_used,
            CASE WHEN {VU} IS NOT NULL THEN 'geschaetzt' ELSE 'unbekannt' END AS value_source,
            round({VUR}) AS value_real_2020,
            CASE WHEN {VU} IS NULL THEN 'unbekannt' WHEN {VUR} < 50000 THEN '<50k'
                 WHEN {VUR} < 200000 THEN '50-200k' WHEN {VUR} < 1000000 THEN '200k-1M'
                 WHEN {VUR} < 5000000 THEN '1-5M' ELSE '>5M' END AS value_band,
            (b.buyer_email IS NOT NULL OR b.buyer_url IS NOT NULL) AS reachable,
            round(coalesce(b.buyer_conf,0),2) AS source_confidence,
            true AS ist_hauptlos, 1 AS lose_im_cluster
          FROM '{N}' n
          JOIN buyer b ON b.notice_id=n.notice_id
          -- Zeilentreu: `quality.parquet` traegt genau eine Zeile je `notice_id` (geprueft
          -- am 2026-09-05: 2.275.460 Zeilen, ebenso viele verschiedene Kennungen), und
          -- `build_quality` laeuft im Lauf des Landes VOR diesem Schritt.
          LEFT JOIN '{Q}' q ON q.notice_id=n.notice_id
          LEFT JOIN '{DD}' dd ON dd.year=n.year
          LEFT JOIN '{DC}' dc ON dc.division=substr(n.cpv_main,1,2)
          {_frist_joins_sql(cfg, country)}{_kategorie_join_sql(cfg, country)}
          -- KEINE CPV-Pflicht mehr. Sie stand hier bis 2026-08-14 und warf gemessen **307
          -- laufende Ausschreibungen mit Vergabestelle** weg (DÖE 239, NetServer 68) —
          -- lautlos, ohne Fehlermeldung, ohne Review-Eintrag.
          --
          -- Der CPV fehlt nicht der VERGABE, sondern der Quelle: dieselben UVgO-Vergaben
          -- tragen bei DÖE zu 100 % einen echten CPV, nur die NetServer-Trefferliste führt
          -- gar keinen. Ein Lead ohne Branche ist unvollständig, aber ein FEHLENDER Lead
          -- ist im Vergleich zweier Werkzeuge eine sichtbare Lücke — und die Projektregel
          -- lautet „nichts nach eigener Relevanz filtern, Unbekanntes markieren".
          --
          -- ⚠ FOLGE, die mitgetragen werden muss: `dc.branche` bleibt bei diesen Leads
          -- NULL. `scripts/export_web_leads.py` faengt das heute mit `ELSE 'beratung'` ab —
          -- fuer „15 Notebooks" oder „Milch und Molkereiprodukte" ist das schlicht falsch.
          -- Die ehrliche Loesung ist ein eigener Grundraum „Sonstiges" im Frontend; bis
          -- dahin ist die Fehlsortierung der Preis dafuer, die Vergabe ueberhaupt zu haben.
          WHERE n.notice_kind IN ('cn','pin')
            AND {_FRIST_EFF} IS NOT NULL AND {_FRIST_EFF} >= DATE '{ref}'
            -- A6 war ein HARTER Schnitt bei 5 Jahren. Gemessen 2026-08-13: er warf in
            -- Oesterreich 357 von 684 offenen atverg-Verfahren weg (52 %), davon 258 mit dem
            -- Platzhalter-Datum 2100-01-01 — laufende Rahmenvereinbarungen der OeBB und
            -- aehnlicher Grosskaeufer. In DE trifft er nur 45 von 11.194 (0,4 %), deshalb fiel
            -- es dort nie auf. Sie sind kein Muell, sondern eine eigene Kategorie: dauerhaft
            -- beitretbar, keine echte Frist — genau das, was `procedure_kind='open_house'`
            -- beschreibt. Konvention "markieren statt filtern": die Obergrenze bleibt nur als
            -- Absurditaets-Sperre gegen Parse-Muell, die Einordnung macht `_open_house_sql`.
            AND {_FRIST_EFF} <= DATE '2200-01-01'
            {_redundante_zweitquelle_sql(cfg, country, stichtag=ref)}
        ) TO '{out}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    import os
    os.replace(f"{out}.tmp", str(out))
    n = con.execute(f"SELECT count(*) FROM '{out}' WHERE source<>'auslauf'").fetchone()[0]
    con.close()
    return n


# --- Permanente Kurz-Slugs für Shareable-Links (govi.link/<slug>) ------------------
# Deterministisch aus lead_id (nicht sequenziell → nicht durchzählbar/abgrasbar), mit
# Quellen-Prefix (t=TED, d=DÖE). Basis-Länge 4 base62 (+1 Prefix = 5 Zeichen); bei
# Kollision deterministisch auf 5+ verlängert → **wächst automatisch mit dem Bestand**
# (je mehr Leads, desto mehr Kollisionen rutschen auf 6). Append-only Map in data/state/
# macht die Slugs PERMANENT (einmal vergeben, nie geändert) und überlebt Gold-Rebuilds.
# Trade-off: Länge 4 = 0,5 % ID-Raum-Belegung bei 74k Leads → nur per Rate-Limit-teurem
# Brute-Force abgrasbar. Kürzer (3) wäre trivial durchzählbar. Bei Bedarf _SLUG_LEN erhöhen.
_B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_SLUG_LEN = 4


def _b62(n: int, width: int) -> str:
    s = ""
    while n:
        n, r = divmod(n, 62)
        s = _B62[r] + s
    return s.rjust(width, "0")


def _mint_slug(lead_id: str, prefix: str, taken: set, length: int = _SLUG_LEN) -> str:
    import hashlib
    h = int.from_bytes(hashlib.sha256(lead_id.encode()).digest(), "big")
    L = length
    while True:
        cand = prefix + _b62(h % (62 ** L), L)
        if cand not in taken:
            return cand
        L += 1          # deterministische Verlängerung bei (seltener) Kollision


def _assign_slugs(cfg: Config, country: str, lead_ids: list[str],
                  doe_ids: set | None = None) -> str:
    """Append-only Slug-Map (lead_id→slug) in ``data/state/`` — permanent, überlebt Rebuilds.

    Neue lead_ids bekommen einen Slug in **sortierter** Reihenfolge (deterministisch),
    bestehende behalten ihren. Quellen-Prefix: ``d`` für DÖE-Leads (in ``doe_ids``),
    sonst ``t`` (TED). Gibt den Parquet-Pfad zurück (für den Join im Export).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    doe_ids = doe_ids or set()
    state = cfg.data_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    path = state / f"slug_map_{country}.parquet"
    mapping: dict[str, str] = {}
    if path.exists():
        con = _db.connect()
        for lid, slug in con.execute(
                f"SELECT lead_id, slug FROM read_parquet('{path.as_posix()}')").fetchall():
            mapping[lid] = slug
        con.close()
    taken = set(mapping.values())
    new = sorted(set(lead_ids) - mapping.keys())
    for lid in new:
        slug = _mint_slug(lid, "d" if lid in doe_ids else "t", taken)
        taken.add(slug)
        mapping[lid] = slug
    if new or not path.exists():                # nur schreiben, wenn sich was geändert hat
        items = sorted(mapping.items())         # stabile Sortierung → reproduzierbares File
        pq.write_table(pa.table({"lead_id": [k for k, _ in items],
                                 "slug": [v for _, v in items]}), path)
    return path.as_posix()



def _lead_context_sql(cfg: Config, country: str) -> str:
    """Vier Kontext-Felder je Notice, direkt aus der Auffang-Tabelle `attributes`.

    **Warum aus `attributes` und nicht aus `notices`:** die Felder sind bisher in keiner
    typisierten Silber-Spalte. Sie dorthin zu ziehen braeuchte einen Voll-Reparse ueber
    1,83 Mio. Notices (~2,5 h). `attributes` ist als verlustfreie Auffang-Tabelle genau
    fuer diesen Zugriff gebaut (s. `model.ATTRIBUTES`) — der Umweg kostet einen Scan und
    keinen Reparse. Wenn die Felder spaeter in den Parser wandern, ersetzt ein JOIN auf
    `notices` diesen Block.

    Vokabular durchgehend ENGLISCH wie der uebrige Export. eForms liefert Codes
    (`la`, `gen-pub`), Legacy englische Klartexte (`Regional or local authority`) — beide
    werden auf dieselben Werte abgebildet. Legacy kann `local` und `regional` nicht
    trennen, deshalb gibt es dafuer den eigenen Wert `regional_or_local`; ihn mit
    `local_authority` zu verschmelzen waere geraten.
    """
    A = cfg.silver_table_glob("attributes", country)
    # ⚠ EIN LAND OHNE `attributes` DARF DEN BAU NICHT ABBRECHEN. DuckDB wirft bei einem
    # Glob ohne Treffer einen IO-Fehler — und seit der AT-Pfad diesen Block benutzt
    # (2026-08-22) hiesse das: eine frische Installation oder ein Land, das noch keine
    # Attribute geerntet hat, bricht mitten im Gold-Bau ab. Stattdessen eine leere Tabelle
    # mit denselben Spalten; der LEFT JOIN liefert dann sauber NULL.
    import glob as _glob
    if not _glob.glob(A):
        return ("SELECT NULL::VARCHAR AS notice_id, NULL::VARCHAR AS legal_basis, "
                "NULL::VARCHAR AS documents_url, FALSE AS is_nationwide, "
                "NULL::INTEGER AS guarantee_required, NULL::INTEGER AS variants_allowed, "
                "NULL::INTEGER AS validity_days, NULL::DATE AS validity_until, "
                "NULL::INTEGER AS consortium_allowed, NULL::INTEGER AS subcontracting_allowed, "
                "NULL::VARCHAR AS award_types, NULL::VARCHAR AS award_criteria, "
                "NULL::VARCHAR AS selection_types, "
                "NULL::VARCHAR AS deadline_time, NULL::VARCHAR AS question_deadline "
                "WHERE false")
    return f"""
      SELECT notice_id,
        -- 1.1 Vergaberegime. Die deutsche Vorschrift ist spezifischer als die
        -- EU-Richtlinie, deshalb hat sie Vorrang: 32014L0024 allein sagt nur
        -- „klassische Richtlinie", vgv/vob-a-eu sagen, welches Regelwerk wirklich gilt.
        coalesce(
          max(CASE WHEN path ILIKE '%ProcurementLegislationDocumentReference.ID' THEN
            CASE lower(value) WHEN 'vgv' THEN 'vgv'
                 WHEN 'vob-a-eu' THEN 'vob' WHEN 'vob-a' THEN 'vob'
                 WHEN 'sektvo' THEN 'sektvo' WHEN 'vsvgv' THEN 'vsvgv'
                 WHEN 'konzvgv' THEN 'konzvgv' END END),
          max(CASE WHEN path ILIKE '%RegulatoryDomain' THEN
            CASE lower(value) WHEN 'de-vob' THEN 'vob'
                 WHEN 'de-uvgo' THEN 'uvgo' WHEN 'de-vol' THEN 'uvgo'
                 WHEN '32014l0025' THEN 'sektvo' WHEN '32009l0081' THEN 'vsvgv'
                 WHEN '32014l0023' THEN 'konzvgv' WHEN '32014l0024' THEN 'eu_classic' END END)
        )                                                    AS regulatory_regime,
        -- 1.3a Art der Vergabestelle
        max(CASE WHEN path ILIKE '%ContractingPartyType.PartyTypeCode' THEN
          CASE lower(value) WHEN 'la' THEN 'local_authority' WHEN 'ra' THEN 'regional_authority'
               WHEN 'cga' THEN 'central_government'
               WHEN 'body-pl-la' THEN 'body_public_law' WHEN 'body-pl-ra' THEN 'body_public_law'
               WHEN 'body-pl-cga' THEN 'body_public_law' WHEN 'body-pl' THEN 'body_public_law'
               WHEN 'pub-undert' THEN 'public_undertaking'
               WHEN 'pub-undert-ra' THEN 'public_undertaking'
               WHEN 'pub-undert-la' THEN 'public_undertaking'
               WHEN 'pub-undert-cga' THEN 'public_undertaking'
               WHEN 'cont-ent' THEN 'utility' WHEN 'org-sub' THEN 'subsidised_entity'
               WHEN 'org-sub-la' THEN 'subsidised_entity'
               WHEN 'org-sub-ra' THEN 'subsidised_entity'
               WHEN 'org-sub-cga' THEN 'subsidised_entity'
               WHEN 'eu-ins-bod-ag' THEN 'eu_institution'
               WHEN 'int-org' THEN 'international_org' ELSE 'other' END
          WHEN path ILIKE '%CODIF_DATA.AA_AUTHORITY_TYPE' THEN
          CASE value WHEN 'Regional or local authority' THEN 'regional_or_local'
               WHEN 'Regional or local Agency/Office' THEN 'regional_or_local'
               WHEN 'Body governed by public law' THEN 'body_public_law'
               WHEN 'Utilities entity' THEN 'utility'
               WHEN 'Ministry or any other national or federal authority' THEN 'central_government'
               WHEN 'National or federal Agency/Office' THEN 'central_government'
               WHEN 'European Institution/Agency' THEN 'eu_institution' ELSE 'other' END END)
                                                             AS buyer_type,
        -- 1.3b Taetigkeitsfeld der Behoerde
        max(CASE WHEN path ILIKE '%ContractingActivity.ActivityTypeCode' THEN
          CASE lower(value) WHEN 'gen-pub' THEN 'general_public'
               WHEN 'health' THEN 'health' WHEN 'hc-am' THEN 'health'
               WHEN 'education' THEN 'education' WHEN 'econ-aff' THEN 'economic_affairs'
               WHEN 'soc-pro' THEN 'social_protection' WHEN 'env-pro' THEN 'environment'
               WHEN 'defence' THEN 'defence' WHEN 'pub-os' THEN 'public_order'
               WHEN 'rcr' THEN 'recreation_culture' WHEN 'housing' THEN 'housing'
               WHEN 'rail' THEN 'transport' WHEN 'urttb' THEN 'transport'
               WHEN 'airport' THEN 'transport' WHEN 'port' THEN 'transport'
               WHEN 'post' THEN 'transport'
               WHEN 'water' THEN 'utilities' WHEN 'electricity' THEN 'utilities'
               WHEN 'gas-heat' THEN 'utilities' WHEN 'gas-oil' THEN 'utilities'
               WHEN 'solid-fuel' THEN 'utilities' ELSE 'other' END
          WHEN path ILIKE '%CODIF_DATA.MA_MAIN_ACTIVITIES' THEN
          CASE value WHEN 'General public services' THEN 'general_public'
               WHEN 'Health' THEN 'health' WHEN 'Education' THEN 'education'
               WHEN 'Economic and financial affairs' THEN 'economic_affairs'
               WHEN 'Social protection' THEN 'social_protection'
               WHEN 'Environment' THEN 'environment' WHEN 'Defence' THEN 'defence'
               WHEN 'Public order and safety' THEN 'public_order'
               WHEN 'Recreation, culture and religion' THEN 'recreation_culture'
               WHEN 'Housing and community amenities' THEN 'housing'
               WHEN 'Railway services' THEN 'transport'
               WHEN 'Airport-related activities' THEN 'transport'
               WHEN 'Port-related activities' THEN 'transport'
               WHEN 'Urban railway, tramway, trolleybus or bus services' THEN 'transport'
               WHEN 'Postal services' THEN 'transport'
               WHEN 'Water' THEN 'utilities' WHEN 'Electricity' THEN 'utilities'
               WHEN 'Production, transport and distribution of gas and heat' THEN 'utilities'
               ELSE 'other' END END)                         AS buyer_activity,
        -- 1.4 Direktlink zu den Vergabeunterlagen. Der Los-Link ist der spezifischere,
        -- deshalb `max()` ueber beide Ebenen — irgendein gueltiger http-Link genuegt.
        max(CASE WHEN path ILIKE '%CallForTendersDocumentReference%'
                  AND value LIKE 'http%' THEN value END)     AS documents_url,
        -- 1.2 Bundesweit erbringbar. `anyw-cou` = irgendwo im Land, `anyw` = irgendwo,
        -- `anyw-eea` = im EWR. Alle drei heissen: an keinen Ort gebunden.
        (max(CASE WHEN path ILIKE '%RealizedLocation.Address.Region'
                   AND lower(value) LIKE 'anyw%' THEN 1 ELSE 0 END) = 1) AS is_nationwide,
        -- #15 Weg A — strukturierte Anforderungen aus eForms (los-übergreifend je Notice
        -- aggregiert; `AND NOT ILIKE '%@%'` schliesst die @listName/@unitCode-Attribute aus,
        -- damit nur der Blattwert zaehlt). Nichts erfunden: fehlt der Beleg → NULL.
        max(CASE WHEN path ILIKE '%RequiredFinancialGuarantee.GuaranteeTypeCode' AND path NOT ILIKE '%@%'
                 THEN CASE lower(value) WHEN 'true' THEN 1 WHEN 'false' THEN 0 END END) AS guarantee_required,
        max(CASE WHEN path ILIKE '%VariantConstraintCode' AND path NOT ILIKE '%@%'
                 THEN CASE lower(value) WHEN 'allowed' THEN 1 WHEN 'not-allowed' THEN 0 END END) AS variants_allowed,
        CASE WHEN max(CASE WHEN path ILIKE '%TenderValidityPeriod.DurationMeasure@unitCode'
                           THEN upper(value) END) = 'MONTH'
             THEN max(CASE WHEN path ILIKE '%TenderValidityPeriod.DurationMeasure' AND path NOT ILIKE '%@%'
                           THEN try_cast(value AS integer) END) * 30
             ELSE max(CASE WHEN path ILIKE '%TenderValidityPeriod.DurationMeasure' AND path NOT ILIKE '%@%'
                           THEN try_cast(value AS integer) END) END                      AS validity_days,
        -- simap nennt kein Dauermass, sondern ein DATUM („Angebot gueltig bis 2026-12-31",
        -- 32 % der simap-Vorgaenge). In Tage umrechnen kann erst der Aufrufer, weil die
        -- Angebotsfrist in `notices` steht und nicht in `attributes`.
        max(CASE WHEN path = 'simap/offerValidityDeadline'
                 THEN try_cast(substr(value, 1, 10) AS date) END)                AS validity_until,
        -- ⚠ NUR SIMAP, UND DAS IST KEIN VERSEHEN. Gesucht wurde eine eForms-Entsprechung:
        -- `NoticeResult.LotTender.SubcontractingTerm` gibt es reichlich (DE 216.443), meint
        -- aber die ZUSCHLAGS-Seite — hat der Gewinner untervergeben. Das ist eine andere
        -- Frage als „darf ein Bieter untervergeben". Bieterseitig traegt eForms nur
        -- `TenderSubcontractingRequirementsCode`, DE 2.523 und AT 16 — zu duenn zum Anzeigen.
        -- simap sagt es direkt: `subContractorAllowed` 78 %, `consortiumAllowed` 55 %.
        -- Ein Feld, das nur ein Land fuellt, ist erlaubt — solange NULL „unbekannt" heisst
        -- und nicht „nicht erlaubt". Genau das steht in docs/land-onboarding.md.
        -- ── ZUSCHLAGSKRITERIEN ────────────────────────────────────────────────────────
        -- Bis zum 2026-08-23 trug der Export NUR die Gewichte (`price_weight_pct` &c.).
        -- Gemessen: AT veroeffentlicht die Kriterien zu 54 %, aber die GEWICHTE zu 0 % —
        -- also stand dort nichts. Die Kriterien selbst liegen in allen drei Laendern:
        -- Typ-Code DE 350.861 / AT 23.558 / CH 32.113 Vorgaenge.
        --
        -- ⚠ ZWEI SPALTEN, NICHT EINE. Die Attribut-Pfade tragen KEINEN Index
        -- (`AwardingCriterion.Description` steht ohne Nummer), Typ und Beschreibung lassen
        -- sich also nicht paaren. Beides getrennt zu fuehren ist ehrlich; sie zu paaren
        -- waere geraten — und ein falsch zugeordnetes Kriterium ist schlimmer als keins.
        string_agg(DISTINCT CASE WHEN path ILIKE '%AwardingCriterion.AwardingCriterionTypeCode'
                             AND path NOT ILIKE '%@%' AND value IN ('price','quality','cost')
                            THEN value END, ',')                                 AS award_types,
        -- ⚠ VERWEISE RAUS. „Bitte konsultieren Sie die Auftragsunterlagen" ist kein
        -- Kriterium, sondern ein Zeiger auf Dokumente, an die wir oft nicht kommen.
        -- Gemessen: DE 10 %, AT 24 %, CH unter 1 % solcher Verweise. Der Filter greift
        -- deutsch, franzoesisch und italienisch — CH ist zu 35 % nicht deutsch.
        list_aggregate(list_slice(list_distinct(list(CASE
            WHEN (path ILIKE '%AwardingCriterion.Description'
                  OR path ILIKE '%SubordinateAwardingCriterion.Name')
             AND path NOT ILIKE '%@%' AND length(trim(value)) BETWEEN 4 AND 80
             AND NOT regexp_matches(lower(value),
                   'unterlag|ausschreib|dokument|document|dossier|konsultier|consulter|'
                   || 'cit(e|é)s? dans|siehe|voir |vedi |see the|as (stated|specified)')
            THEN trim(value) END)), 1, 6), 'string_agg', ' · ')                  AS award_criteria,
        max(CASE WHEN path = 'simap/consortiumAllowed'
                 THEN CASE lower(value) WHEN 'yes' THEN 1 WHEN 'no' THEN 0 END END)
                                                                             AS consortium_allowed,
        max(CASE WHEN path = 'simap/subContractorAllowed'
                 THEN CASE lower(value) WHEN 'yes' THEN 1 WHEN 'no' THEN 0 END END)
                                                                             AS subcontracting_allowed,
        string_agg(DISTINCT CASE WHEN path ILIKE '%SelectionCriteria.CriterionTypeCode' AND path NOT ILIKE '%@%'
                            AND value IN ('tp-abil','sui-act','ef-stand') THEN value END, ',') AS selection_types,
        -- #16 Verfahrenskalender-Rest: Angebotsfrist-Uhrzeit (HH:MM) + Bieterfragen-Frist.
        max(CASE WHEN path ILIKE '%TenderSubmissionDeadlinePeriod.EndTime' AND path NOT ILIKE '%@%'
                 THEN substr(value, 1, 5) END)                                   AS deadline_time,
        -- ⚠ ZWEI VOKABULARE, EIN FELD. Die Schweiz hat zwei Quellen: 875 offene Vergaben
        -- kommen als eForms ueber TED, 813 direkt von simap.ch mit EIGENEN Feldnamen.
        -- Gemessen am 2026-08-22: die eForms-Haelfte war zu 98-100 % gefuellt, die
        -- simap-Haelfte zu NULL — nicht weil simap nichts liefert, sondern weil hier nur
        -- eForms-Pfade standen. simap traegt `questionDeadline` bei 93 % seiner Vorgaenge.
        -- Das ist genau der Fall aus `docs/land-onboarding.md`: uebertragbar ist die
        -- Funktion, NICHT das Vokabular.
        coalesce(
          max(CASE WHEN path ILIKE '%AdditionalInformationRequestPeriod.EndDate' AND path NOT ILIKE '%@%'
                   THEN substr(value, 1, 10) END),
          max(CASE WHEN path = 'simap/questionDeadline'
                   THEN substr(value, 1, 10) END))                               AS question_deadline,
        -- CH/simap: Unterlagen-Herkunft. Die Felder liegen seit dem ersten simap-Ingest in
        -- Bronze und seit 2026-08-13 in Silber; ohne diese vier Zeilen bleiben sie dort
        -- liegen. Gemessen ueber 11.460 Publikationen: 4.452 mit `documents_source_simap`
        -- (simap haelt die Unterlagen selbst), 238 externer Link, 225 nur auf Anfrage.
        -- `documents_source` beantwortet damit im Produkt die Frage, die vor jedem
        -- Dokument-Connector steht: kommt man ueberhaupt heran, und wie?
        max(CASE WHEN path = 'simap/documentsSourceType' THEN
          CASE value WHEN 'documents_source_simap'   THEN 'platform'
                     WHEN 'documents_source_url'     THEN 'external_url'
                     WHEN 'documents_source_email'   THEN 'on_request'
                     WHEN 'documents_source_address' THEN 'postal' ELSE 'other' END END)
                                                                        AS documents_source,
        (max(CASE WHEN path = 'simap/hasProjectDocuments' THEN 1 ELSE 0 END) = 1)
                                                                        AS has_documents,
        (max(CASE WHEN path = 'simap/documentsWithCosts'
             AND lower(value) = 'yes' THEN 1 ELSE 0 END) = 1)           AS documents_paid,
        string_agg(DISTINCT CASE WHEN path = 'simap/documentsLanguage'
             THEN lower(value) END, ',')                                AS documents_languages
      FROM read_parquet('{A}', hive_partitioning=1)
      -- ⚠ Diese WHERE-Liste ist eine POSITIVLISTE. Wer oben eine Spalte ergaenzt, muss den
      -- Pfad hier eintragen — sonst liest das CTE ihn gar nicht erst und die Spalte kommt
      -- ueberall als NULL heraus, ohne Fehler und ohne roten Test. Genau das passierte am
      -- 2026-08-13 mit den vier simap-Unterlagen-Feldern: Spalten im Parquet vorhanden,
      -- Werte durchgehend leer.
      WHERE path LIKE 'simap/documents%'
         OR path ILIKE '%AwardingCriterion%'
         -- ⚠ POSITIVLISTE, also auch die simap-EIGENEN Felder eintragen. Ohne diese zwei
         -- Zeilen bleibt der `coalesce` oben wirkungslos: die Zeilen kommen gar nicht erst
         -- durch. Gemessen am 2026-08-22: der Kontext lieferte 4 statt 765 Bieterfragen-
         -- Fristen, und der Fehler sah aus wie ein leeres Feld in der Quelle.
         OR path = 'simap/questionDeadline'
         OR path = 'simap/offerValidityDeadline'
         OR path = 'simap/consortiumAllowed'
         OR path = 'simap/subContractorAllowed'
         OR path = 'simap/hasProjectDocuments'
         OR path ILIKE '%RegulatoryDomain'
         OR path ILIKE '%ProcurementLegislationDocumentReference.ID'
         OR path ILIKE '%ContractingPartyType.PartyTypeCode'
         OR path ILIKE '%CODIF_DATA.AA_AUTHORITY_TYPE'
         OR path ILIKE '%ContractingActivity.ActivityTypeCode'
         OR path ILIKE '%CODIF_DATA.MA_MAIN_ACTIVITIES'
         OR path ILIKE '%CallForTendersDocumentReference%'
         OR path ILIKE '%RealizedLocation.Address.Region'
         OR path ILIKE '%RequiredFinancialGuarantee.GuaranteeTypeCode'
         OR path ILIKE '%VariantConstraintCode'
         OR path ILIKE '%TenderValidityPeriod.DurationMeasure%'
         OR path ILIKE '%SelectionCriteria.CriterionTypeCode'
         OR path ILIKE '%TenderSubmissionDeadlinePeriod.EndTime'
         OR path ILIKE '%AdditionalInformationRequestPeriod.EndDate'
      GROUP BY notice_id
    """


# Auf wie vielen Stellen der NUTS-Kennung sitzt die Verwaltungseinheit, nach der ein
# Bieter filtert? Das ist je Land verschieden und keine Geschmacksfrage:
#     DE  3  NUTS-1 = Bundesland          (DE2 = Bayern)
#     AT  4  NUTS-2 = Bundesland          (AT13 = Wien; AT1 waere „Ostoesterreich")
#     CH  5  NUTS-3 = Kanton              (CH021 = Bern; CH0 waere die ganze Schweiz)
# Unbekannte Laender bekommen 3 — dieselbe Annahme wie bisher, aber jetzt sichtbar.
# ⚠ LU IST EINE EINZIGE REGION. Der NUTS-Katalog fuehrt fuer Luxemburg genau VIER Codes —
# LU, LU0, LU00, LU000 — und alle vier heissen „Luxembourg" (geprueft an
# data/reference/nuts/NUTS_AT_2024.csv). Es gibt dort also keine Regionsebene, auf der man
# filtern koennte; drei Stellen ergeben einen einzigen Eimer „LU0", und das ist die richtige
# Antwort, nicht ein Defekt. Wer hier 5 einsetzt, um „genauer" zu sein, bekommt dasselbe
# Ergebnis mit laengerem Schluessel.
_REGION_STELLEN = {"DE": 3, "AT": 4, "CH": 5, "LU": 3}


def build_lead_export(cfg: Config, country: str = "DE"):
    """`lead_detail` → **Frontend-Vertrag** (flach, Supabase-ready) — durchgehend ENGLISCH.

    Spalten UND Werte sind englisch/sprachneutral, damit der Vertrag für weitere Länder
    trägt; die Übersetzung gehört ins Frontend. Herkunfts-Flags bleiben das Kernprinzip:
    ``*_source`` sagt immer, ob ein Wert belegt (``actual``) oder abgeleitet
    (``estimated``/``uncertain``/``unknown``) ist.

    Markt-Region = **Leistungsort**, nicht Käufersitz (``market_region_known`` als Gate).
    ``slug`` = permanenter Kurz-Link. Schreibt ``lead_export`` (1 Zeile je Lead).
    """

    g = cfg.gold_dir / country
    def q(n): return f"'{(g / n).as_posix()}'"
    nglob = cfg.silver_table_glob("notices", country)
    out = (g / "lead_export.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    lead_ids = [r[0] for r in con.execute(
        f"SELECT lead_id FROM read_parquet({q('lead_detail.parquet')})").fetchall()]
    doe_ids = {r[0] for r in con.execute(
        f"SELECT notice_id FROM read_parquet('{nglob}') WHERE schema_gen='doe'").fetchall()}
    slug_path = _assign_slugs(cfg, country, lead_ids, doe_ids)
    con.execute(f"""
        COPY (
          SELECT
            d.lead_id, sl.slug,
            -- Das Vergabe-LAND, ausdrücklich. Bis 2026-08-13 trug nur die alte AT/CH-Brücke
            -- diese Spalte, der DE-Bauer nicht — der Web-Export unterschied die Länder daran
            -- (`coalesce(country,'DE') <> 'DE'`). Als AT/CH auf denselben Bauer umgestellt
            -- wurden, verschwand sie dort und der Export brach ab: „Referenced column
            -- country not found". Ein Lead-Export ohne sein Land ist von der Konstruktion her
            -- mehrdeutig — deshalb schreibt ihn jetzt JEDES Land, auch DE.
            '{country}'                               AS country,
            d.titel                                   AS title,
            -- Freitext. GEMESSEN (2026-07-23, 437.401 offene Ausschreibungen ab 2024):
            -- die Notice-Beschreibung allein ist zu 61 % ein Zweizeiler (<200 Zeichen),
            -- Median 129. Zwei Drittel des Textes liegen auf der **Los**-Ebene
            -- (`lead_lot`) — mit ihr steigt der Median auf 432 und der Anteil mit
            -- >=1.000 Zeichen von 14,6 % auf 32,9 %. Das Flag rechnet deshalb ueber
            -- BEIDE Ebenen, sonst versteckte das UI bei jedem 5. Lead vorhandenen Inhalt.
            d.beschreibung                            AS description,
            length(d.beschreibung)                    AS description_length,
            coalesce(length(d.beschreibung),0) + coalesce(lt.lot_chars,0)
                                                      AS total_description_length,
            (coalesce(length(d.beschreibung),0) + coalesce(lt.lot_chars,0) >= 1000)
                                                      AS has_detailed_description,
            coalesce(lt.n_lots, 0)                    AS n_lots,
            d.buyer_name, d.buyer_town,
            -- REGIONS-EBENE JE LAND. Der feste Schnitt auf 3 Zeichen (NUTS-1) war eine
            -- deutsche Annahme: in DE ist NUTS-1 das Bundesland, in AT die Drittel-
            -- Einteilung (AT1 „Ostoesterreich" umfasst Burgenland, Niederoesterreich UND
            -- Wien) und in CH das GANZE LAND (CH0). Gemessen 2026-08-23 trugen deshalb
            -- alle 3.856 Schweizer Leads mit Region dieselbe Angabe „Schweiz/Suisse/
            -- Svizzera" und alle oesterreichischen eine von drei — als Filter wertlos,
            -- obwohl die Leads NUTS-3-genau vorliegen (AT130 = Wien, CH021 = Bern).
            -- Die passende Ebene ist die, auf der das Land seine Verwaltungseinheit
            -- fuehrt: DE NUTS-1, AT NUTS-2 (Bundesland), CH NUTS-3 (Kanton).
            d.buyer_nuts, substr(d.buyer_nuts,1,{_REGION_STELLEN.get(country, 3)}) AS buyer_nuts1,
            dn.name                                   AS buyer_region_name,
            -- Markt = LEISTUNGSORT. Nur zeigen, wenn NUTS-3-genau bekannt.
            CASE WHEN length(lg.perf_nuts) >= 5 THEN substr(lg.perf_nuts,1,5) END AS market_nuts3,
            mkt.name                                  AS market_region_name,
            (length(lg.perf_nuts) >= 5)               AS market_region_known,
            d.cpv_main                                AS cpv_code,
            -- Herkunft der Kategorie — dieselbe Konvention wie `deadline_source`/`band_source`:
            -- das Produkt behauptet die Einordnung nicht, es sagt, woher sie kommt.
            --   cpv        veroeffentlichter Code
            --   zwilling   Code der Dublette (veroeffentlicht, nur woanders)
            --   regelwerk  VOB/A ⇒ Bauleistung
            --   modell     aus dem Titel abgeleitet, gemessen ~82 %
            --   ohne       ehrlich unbekannt
            d.branche_source                          AS category_source,
            CASE d.contract_kind
                 WHEN 'rahmenvertrag' THEN 'framework' WHEN 'einmal_werk' THEN 'one_off_works'
                 WHEN 'wiederkehrend' THEN 'recurring' WHEN 'werk_sonstig' THEN 'works_other'
                 ELSE 'other' END                     AS contract_kind,
            CASE d.source WHEN 'auslauf' THEN 'expiring' WHEN 'f02' THEN 'open'
                 WHEN 'f01' THEN 'planned' END        AS phase,
            (d.source IN ('f01','f02'))               AS is_new_tender,
            -- Leistungsart: echte TED-Vertragsnatur (BT-23), sonst CPV-Heuristik
            CASE WHEN nt.contract_nature='works' THEN 'works'
                 WHEN nt.contract_nature='supplies' THEN 'supplies'
                 WHEN nt.contract_nature='services' THEN 'services'
                 WHEN substr(d.cpv_main,1,2)='45' THEN 'works'
                 WHEN substr(d.cpv_main,1,2) BETWEEN '03' AND '44' THEN 'supplies'
                 ELSE 'services' END                  AS contract_nature,
            CASE WHEN nt.contract_nature IN ('works','supplies','services')
                 THEN 'actual' ELSE 'estimated' END   AS contract_nature_source,
            -- Wert: 'default'-Band ist zu unsicher → NULL, Frontend zeigt '—'
            CASE WHEN d.band_source='default' THEN NULL ELSE d.value_effektiv END AS value_eur,
            d.band_effektiv                           AS value_band,
            CASE d.band_source WHEN 'echt' THEN 'actual'
                 WHEN 'geschaetzt' THEN 'estimated' WHEN 'imputiert' THEN 'estimated'
                 ELSE 'unknown' END                   AS value_source,
            -- Timing: Frist-DATUM + Tage (der eigentliche Alert) und Auslauf in Monaten
            d.deadline_date,
            datediff('day', current_date, d.deadline_date) AS days_to_deadline,
            date_diff('month', current_date,
                      coalesce(d.contract_end_cal, d.contract_end_eff)) AS months_to_expiry,
            d.contract_end_eff                        AS contract_end,
            -- Zeitrechnung auf dem KALIBRIERTEN Datum: der Nutzer will wissen, wann die
            -- Nachausschreibung kommt, nicht wann der Vertrag formal endet. Das rohe Ende
            -- bleibt als `contract_end` daneben stehen.
            d.contract_end_cal                        AS contract_end_expected,
            d.cal_offset_days, d.cal_spread_days,
            datediff('day', current_date,
                     coalesce(d.contract_end_cal, d.contract_end_eff)) AS days_to_expiry,
            -- Verfahrensart: Open House ist kein Wettbewerb (jederzeit beitretbar, kein
            -- Gewinner, keine echte Frist). Hier aus dem Titel bestimmt — dasselbe Muster
            -- wie in `quality.verfahren_status`, aber auch für offene Ausschreibungen, wo
            -- der Status bisher gar nicht gesetzt wurde.
            CASE WHEN {_open_house_sql('d.titel', 'd.deadline_date')} THEN 'open_house' ELSE 'wettbewerb' END
                                                      AS procedure_kind,
            d.faellig_basis                           AS due_basis,
            (NOT coalesce(d.termin_plausibel, true))  AS timing_implausible,
            CASE WHEN NOT coalesce(d.termin_plausibel, true) THEN 'uncertain'
                 WHEN d.source IN ('f01','f02') THEN
                      -- `starts_with('echt')` statt Gleichheit: die Dubletten-Firewall hat
                      -- zwei weitere echte Stufen erzeugt (`echt_aus_dublette`,
                      -- `echt_verlaengert`). Beide sind VEROEFFENTLICHTE Daten, nur aus dem
                      -- Zwillingssatz derselben Vergabe — sie als 'estimated' zu melden,
                      -- waere eine Untertreibung. Nur die `geschaetzt_*`-Stufen sind Modell.
                      CASE WHEN starts_with(d.deadline_source, 'echt') THEN 'actual'
                           ELSE 'estimated' END
                 ELSE CASE d.duration_source WHEN 'echt' THEN 'actual'
                          WHEN 'unbekannt' THEN 'unknown' ELSE 'estimated' END END AS timing_source,
            -- Amtsinhaber inkl. Konzern-Gruppe (entity_identity)
            d.incumbent_name,
            d.incumbent_since_year, d.incumbent_conf  AS incumbent_confidence,
            CASE WHEN d.incumbent_name IS NULL THEN NULL
                 WHEN d.incumbent_conf >= 0.75 THEN 'actual' ELSE 'uncertain' END AS incumbent_source,
            ei.identity_id                            AS incumbent_group_id,
            ei.group_size                             AS incumbent_group_size,
            CASE WHEN d.displ_band IS NULL OR d.displ_band LIKE 'n/a%' THEN 'na'
                 WHEN d.displ_band='hoch' THEN 'high' WHEN d.displ_band='mittel' THEN 'medium'
                 WHEN d.displ_band='niedrig' THEN 'low' ELSE 'na' END AS switch_chance,
            d.num_tenders                             AS n_bidders,
            d.single_bidder,
            CASE d.bidder_bucket WHEN 'einzel' THEN 'low' WHEN 'wenig' THEN 'medium'
                 WHEN 'viel' THEN 'high' ELSE 'na' END AS competition_level,
            CASE WHEN d.source IN ('f01','f02') THEN 'na'
                 WHEN d.num_tenders IS NOT NULL THEN 'actual' ELSE 'unknown' END AS competition_source,
            -- Zuschlagskriterien: „gewinne ich ueber den Preis oder ueber das Konzept?"
            -- Gewichte sind JE LOS normiert; bei Mehrlos-Ausschreibungen steht hier der
            -- Median ueber die Lose, und `criteria_uniform` sagt, ob die Lose ueberhaupt
            -- dasselbe wollen. Ohne diese Unterscheidung waere „Preis 40 %" bei einer
            -- 20-Los-Ausschreibung eine erfundene Zahl.
            cr.price_weight_pct, cr.quality_weight_pct, cr.cost_weight_pct,
            cr.n_criteria, cr.criteria_uniform,
            CASE WHEN cr.n_criteria IS NULL THEN 'unknown'
                 WHEN cr.price_weight_pct IS NOT NULL THEN 'actual'
                 WHEN cr.n_rank > 0 THEN 'ranked_only'   -- ord-imp: Reihenfolge, kein Gewicht
                 ELSE 'unweighted' END                AS criteria_source,
            -- 1.1 Vergaberegime: der Ein-Klick-Filter (VOB / UVgO / VgV / SektVO)
            ctx.regulatory_regime,
            -- 1.3 Kaeufer-Segmentierung — beide Achsen ueber die gesamte Historie
            ctx.buyer_type, ctx.buyer_activity,
            -- 1.4 Direktlink zu den Vergabeunterlagen. `source_url` zeigt auf TED,
            -- `portal_url` (in lead_detail) ist zu 44,5 % / bei DÖE zu 0 % gefuellt —
            -- dieses Feld deckt 96,8 % der OFFENEN Leads.
            -- ⚠ RÜCKFALL AUF DIE PORTALSEITE. `ctx.documents_url` kommt aus
            -- `CallForTendersDocumentReference` — ein eForms-Feld. Nationale Quellen haben
            -- es nicht: von 508 offenen AT-Vergaben aus offenevergaben.at trug KEINE eine
            -- documents_url, und das Frontend zeigte dort ueberhaupt keinen Weg zur Quelle.
            -- Jeder dieser 238.347 Vorgaenge traegt aber `portal_url` in Silber
            -- (`https://offenevergaben.at/auftrag/31290`). Dokumente gibt es dort nicht,
            -- die Bekanntmachung schon — und ein Link dorthin ist mehr als kein Link.
            coalesce(ctx.documents_url, nq.portal_url)  AS documents_url,
            -- CH/simap: WIE kommt man an die Unterlagen? `documents_url` sagt nur, DASS es
            -- einen Link gibt. Diese vier beantworten die Frage davor — gemessen ueber 11.460
            -- simap-Publikationen: 4.452 `platform` (simap haelt sie selbst), 238
            -- `external_url`, 225 `on_request` (nur per E-Mail), 5 `postal`.
            -- Ausserhalb der Schweiz NULL bzw. false: die Felder stammen aus simap-Attributen,
            -- TED und DOeE kennen sie nicht. Das ist kein Mangel, sondern die ehrliche Aussage
            -- „unbekannt" — nicht „keine Unterlagen".
            ctx.documents_source,
            coalesce(ctx.has_documents, false)         AS has_documents,
            coalesce(ctx.documents_paid, false)        AS documents_paid,
            ctx.documents_languages,
            -- 1.2 bundesweit erbringbar → darf in der Umkreissuche nie herausfallen
            coalesce(ctx.is_nationwide, false)         AS is_nationwide,
            -- #15 Weg A — strukturierte Anforderungen (Anforderungs-Check)
            ctx.guarantee_required, ctx.variants_allowed,
            -- Bindefrist: eForms nennt eine Dauer, simap ein Enddatum. Hier wird beides
            -- auf TAGE gebracht — gegen die Angebotsfrist, denn ab da laeuft die Bindung.
            coalesce(ctx.validity_days,
                     date_diff('day', d.deadline_date, ctx.validity_until)) AS validity_days,
            ctx.consortium_allowed, ctx.subcontracting_allowed,
            ctx.award_types, ctx.award_criteria,
            ctx.selection_types,
            ctx.deadline_time, ctx.question_deadline,
            d.ted_url                                 AS source_url,
            (d.incumbent_name IS NOT NULL AND d.incumbent_conf >= 0.75) AS has_comparables,
            (coalesce(d.tenure_years, 0) > 0)         AS has_contract_history
          FROM read_parquet({q('lead_detail.parquet')}) d
          -- Nur fuer `portal_url` — die Spalte steht in `notices` und in keiner Gold-Tabelle.
          -- ⚠ NUR MIT SCHEMA. Ein Eintrag lautet `www.bahn-bkk.de/leistungserbringer` —
          -- ohne `https://` ist das kein anklickbarer Link, und `test_lead_export_documents_
          -- url_is_a_link` besteht zu Recht darauf. Ein Schema davorzusetzen waere geraten:
          -- wir wissen nicht, ob der Host http oder https spricht.
          LEFT JOIN (SELECT notice_id, any_value(portal_url) AS portal_url
                     FROM read_parquet('{cfg.silver_table_glob("notices", country)}',
                                       hive_partitioning=1)
                     WHERE portal_url LIKE 'http%' GROUP BY 1) nq ON nq.notice_id = d.lead_id
          LEFT JOIN read_parquet('{slug_path}') sl ON sl.lead_id = d.lead_id
          LEFT JOIN read_parquet({q('lead_geo.parquet')}) lg ON lg.lead_id = d.lead_id
          -- Derselbe Schnitt wie bei `buyer_nuts1` oben — sonst traegt der Lead die
          -- richtige Kennung und daneben den Namen der falschen Ebene.
          LEFT JOIN read_parquet({q('dim_nuts.parquet')}) dn
                 ON dn.nuts_code = substr(d.buyer_nuts, 1, {_REGION_STELLEN.get(country, 3)})
          LEFT JOIN read_parquet({q('dim_nuts.parquet')}) mkt ON mkt.nuts_code = substr(lg.perf_nuts,1,5)
          LEFT JOIN read_parquet({q('entity_identity.parquet')}) ei ON ei.entity_id = d.incumbent_entity
          LEFT JOIN (
            SELECT notice_id, any_value(contract_nature) AS contract_nature
            FROM read_parquet('{nglob}') WHERE contract_nature IS NOT NULL GROUP BY notice_id
          ) nt ON nt.notice_id = d.lead_id
          LEFT JOIN (
            SELECT notice_id, count(*) AS n_lots,
                   sum(coalesce(length(description),0)) AS lot_chars
            FROM read_parquet('{cfg.silver_table_glob("lots", country)}', hive_partitioning=1)
            GROUP BY notice_id
          ) lt ON lt.notice_id = d.lead_id
          LEFT JOIN ({_lead_context_sql(cfg, country)}) ctx ON ctx.notice_id = d.lead_id
          LEFT JOIN (
            -- Erst JE LOS die Gewichte je Art buendeln, DANN ueber die Lose mitteln.
            -- Andersherum (alles in einen Topf) addierten sich die Lose zu >100 %.
            WITH per_lot AS (
              SELECT notice_id, lot_id,
                     sum(CASE WHEN kind='price'   THEN w END) AS p,
                     sum(CASE WHEN kind='quality' THEN w END) AS q,
                     sum(CASE WHEN kind='cost'    THEN w END) AS k,
                     count(*)                                 AS nc,
                     count(*) FILTER (WHERE weight_kind='ord-imp') AS nr
              FROM (
                SELECT notice_id, lot_id, kind, weight_kind,
                       CASE WHEN weight_kind='ord-imp' THEN NULL
                            WHEN s > 0 THEN 100.0 * v / s END AS w
                FROM (
                  SELECT notice_id, lot_id, kind, weight_kind,
                         try_cast(replace(replace(replace(weight,'%',''),',','.'),' ','')
                                  AS DOUBLE) AS v,
                         sum(CASE WHEN weight_kind IS NULL OR weight_kind LIKE 'per%'
                                    OR weight_kind LIKE 'poi%' OR weight_kind LIKE 'dec%'
                                  THEN try_cast(replace(replace(replace(weight,'%',''),
                                       ',','.'),' ','') AS DOUBLE) END)
                           OVER (PARTITION BY notice_id, lot_id) AS s
                  -- union_by_name: der Kriterien-Reparse lief nur ab 2024, aeltere
                  -- Monate kennen die Spalte `weight_kind` noch nicht.
                  FROM read_parquet('{cfg.silver_table_glob("award_criteria", country)}',
                                    hive_partitioning=1, union_by_name=1)
                )
              ) GROUP BY notice_id, lot_id
            )
            SELECT notice_id,
                   round(median(p),1) AS price_weight_pct,
                   round(median(q),1) AS quality_weight_pct,
                   round(median(k),1) AS cost_weight_pct,
                   sum(nc)            AS n_criteria,
                   sum(nr)            AS n_rank,
                   -- Lose einig? (gerundet, damit 69,9 vs 70,0 nicht als Konflikt zaehlt)
                   (count(DISTINCT round(coalesce(p,-1))) = 1) AS criteria_uniform
              FROM per_lot GROUP BY notice_id
          ) cr ON cr.notice_id = d.lead_id
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_cpv(cfg: Config, country: str = "DE"):
    """**Alle** CPV je Lead (n:m) — 41 % der Notices tragen mehr als einen.

    `lead_export.cpv_code` führt nur den Haupt-CPV; diese Tabelle macht die übrigen
    zugänglich (Silber `notice_cpv`). Schreibt ``lead_cpv`` (lead_id, cpv_code, is_main).
    """

    g = cfg.gold_dir / country
    out = (g / "lead_cpv.parquet").as_posix()
    NC = cfg.silver_table_glob("notice_cpv", country)
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          SELECT DISTINCT c.notice_id AS lead_id, c.cpv_code, c.is_main
          FROM read_parquet('{NC}', hive_partitioning=1) c
          JOIN read_parquet('{(g / "lead_export.parquet").as_posix()}') l ON l.lead_id = c.notice_id
          WHERE c.cpv_code IS NOT NULL
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_lot(cfg: Config, country: str = "DE"):
    """**Lose je Lead** (n:m) — der eigentliche Inhalts-Layer fuers Frontend.

    Warum eigene Tabelle: die Notice-Beschreibung ist bei **61 % ein Zweizeiler**
    (<200 Zeichen, gemessen 2026-07-23 an 437.401 offenen Ausschreibungen ab 2024).
    Der Inhalt steckt zu zwei Dritteln auf der **Los**-Ebene (s. `docs/data-sources.md`,
    Abschnitt „Der Freitext ist los-basiert"). Rechnet man die Lose dazu, steigt der
    Median von **129 auf 432 Zeichen** und der Anteil mit >=1.000 Zeichen von
    **14,6 % auf 32,9 %** — genau das, was man beim Durchklicken auf TED sieht.

    Das Los ist ausserdem die **Entscheidungs-Einheit**: eine Firma bietet auf ein Los,
    nicht auf die Bekanntmachung. Deshalb kommen Wert, Laufzeit, Leistungsort und
    Optionen/Verlaengerung je Los mit — auf Lead-Ebene sind sie zusammengemittelt.

    Schreibt ``lead_lot`` (englischer Vertrag, 1:n zu `lead_export.lead_id`).
    """

    g = cfg.gold_dir / country
    out = (g / "lead_lot.parquet").as_posix()
    L = cfg.silver_table_glob("lots", country)
    LC = cfg.silver_table_glob("lot_cpv", country)
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH lot_cpv_main AS (
            -- Los-CPV (ProcurementProjectLot.MainCommodityClassification, ~72 % DÖE):
            -- das eigene Fachgebiet je Los. Fundament fuer per-Los-Relevanz (#12).
            SELECT notice_id, lot_id,
                   coalesce(any_value(cpv_code) FILTER (WHERE is_main),
                            any_value(cpv_code)) AS lot_cpv_code
            FROM read_parquet('{LC}', hive_partitioning=1)
            GROUP BY notice_id, lot_id
          )
          SELECT
            lo.notice_id                              AS lead_id,
            lc.lot_cpv_code                           AS lot_cpv_code,
            -- 450 Lose tragen keine LotID im Quell-XML. Der Supabase-PK ist
            -- (lead_id, lot_id) → NULL waere dort nicht erlaubt und das Upsert fiele
            -- auf die Nase. Ordinal-Fallback statt Zeile wegwerfen.
            coalesce(lo.lot_id, 'n' || row_number() OVER (
                PARTITION BY lo.notice_id ORDER BY lo.title NULLS LAST)::VARCHAR) AS lot_id,
            (lo.lot_id IS NULL)                       AS lot_id_synthetic,
            lo.title                                  AS lot_title,
            lo.description                            AS lot_description,
            length(lo.description)                    AS lot_description_length,
            -- Wert nur, wenn er auch eine Waehrung traegt; Fremdwaehrung ehrlich benannt
            CASE WHEN lo.value_currency='EUR' THEN lo.value_amount END AS lot_value_eur,
            lo.value_currency                         AS lot_value_currency,
            lo.start_date, lo.end_date, lo.duration_months,
            CASE WHEN length(lo.performance_nuts) >= 5
                 THEN substr(lo.performance_nuts,1,5) END AS lot_market_nuts3,
            coalesce(lo.has_options, false)           AS has_options,
            lo.options_description,
            coalesce(lo.has_renewal, false)           AS has_renewal,
            lo.renewal_description, lo.max_renewals
          FROM read_parquet('{L}', hive_partitioning=1) lo
          JOIN read_parquet('{(g / "lead_export.parquet").as_posix()}') l
            ON l.lead_id = lo.notice_id
          LEFT JOIN lot_cpv_main lc
            ON lc.notice_id = lo.notice_id AND lc.lot_id = lo.lot_id
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_text(cfg: Config, country: str = "DE"):
    """**Sprachfassungen je Lead** — damit die App eine Dokumentsprache anbieten kann.

    `lead_export` fuehrt genau EINEN Titel und EINE Beschreibung. Solange das so bleibt,
    kann die Oberflaeche keine Sprachwahl anbieten, auch wenn die Fassungen im Silber
    liegen (`notice_text`, 35,3 Mio. Zeilen ueber 24 Sprachen). Diese Tabelle reicht sie
    bis auf die Lead-Ebene durch.

    Gefiltert auf das, was das Frontend wirklich braucht: nur Leads, die es auch in
    `lead_export` gibt. `notice_text` deckt den ganzen Bestand ab (auch Zuschlaege von
    2011), das Frontend zeigt aber nur die Lead-Auswahl — ungefiltert waere die Tabelle
    zwanzigmal so gross wie noetig.

    Schreibt `lead_text` (lead_id, lot_id, field, language, value), 1:n zu
    `lead_export.lead_id`. Sprachcodes sind ISO-639-1 klein (s. `govisor/languages.py`).
    """

    g = cfg.gold_dir / country
    out = (g / "lead_text.parquet").as_posix()
    T = cfg.silver_table_glob("notice_text", country)
    E = (g / "lead_export.parquet").as_posix()
    if not list((cfg.silver_dir / country / "notice_text").glob("*/*.parquet")):
        # Ohne Silber-Tabelle eine LEERE Datei schreiben, nicht gar keine: der Exporter
        # joint sie, und eine fehlende Datei waere ein Laufzeitfehler statt „keine
        # Sprachfassungen bekannt".
        con = _db.connect()
        con.execute(f"""COPY (SELECT NULL::VARCHAR lead_id, NULL::VARCHAR lot_id,
            NULL::VARCHAR field, NULL::VARCHAR language, NULL::VARCHAR value WHERE false)
            TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
        con.close()
        return 0

    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          SELECT t.notice_id AS lead_id, t.lot_id, t.field, t.language, t.value
          FROM read_parquet('{T}', hive_partitioning=1) t
          JOIN (SELECT DISTINCT lead_id FROM read_parquet('{E}')) e
            ON e.lead_id = t.notice_id
          WHERE t.value IS NOT NULL AND t.language IS NOT NULL
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_doe_buyer_profile(cfg: Config, country: str = "DE"):
    """Käufer-Profil für den **Unterschwellenmarkt** (DÖE) — die neue Analyse-Ebene.

    Je Käufer-Entität: Zahl der Unterschwellen-Ausschreibungen (cn) + Awards (can),
    Kategorie-Breite + Haupt-CPV-Division (Label), Haupt-Leistungsregion, letzte Aktivität
    und — der Alleinstellungs-Fund — ob der Käufer **auch oberschwellig (TED)** ausschreibt
    (Cross-Threshold, 47 % Overlap). KEINE €/Gewinner-KPIs (DÖE trägt beides nicht).
    Schreibt ``doe_buyer_profile``.
    """

    g = cfg.gold_dir / country
    def q(n): return f"'{(g / n).as_posix()}'"
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    out = (g / "doe_buyer_profile.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH doe AS (
            SELECT notice_id, cpv_main, notice_kind, performance_nuts,
                   printf('%04d-%02d', year, month) AS ym
            FROM read_parquet({N}, hive_partitioning=1) WHERE schema_gen='doe'),
          buyer AS (
            SELECT pe.notice_id, pe.entity_id
            FROM (SELECT notice_id, min(seq) s FROM read_parquet({q('party_entity.parquet')})
                  WHERE role='buyer' GROUP BY 1) b
            JOIN read_parquet({q('party_entity.parquet')}) pe
              ON pe.notice_id=b.notice_id AND pe.role='buyer' AND pe.seq=b.s),
          ted_b AS (
            SELECT DISTINCT pe.entity_id FROM read_parquet({q('party_entity.parquet')}) pe
            JOIN read_parquet({N}, hive_partitioning=1) n ON n.notice_id=pe.notice_id
            WHERE pe.role='buyer' AND n.schema_gen<>'doe'),
          j AS (SELECT b.entity_id, d.* FROM doe d JOIN buyer b ON b.notice_id=d.notice_id),
          topdiv AS (
            SELECT t.entity_id, t.top_div, cl.label AS top_label FROM (
              SELECT entity_id, arg_max(div, c) AS top_div FROM (
                SELECT entity_id, substr(cpv_main,1,2) div, count(*) c FROM j
                WHERE cpv_main IS NOT NULL GROUP BY 1,2) GROUP BY 1) t
            LEFT JOIN read_parquet({q('dim_cpv_label.parquet')}) cl
              ON cl.cpv_code = rpad(t.top_div, 8, '0'))
          SELECT j.entity_id AS buyer_entity, e.canonical_name AS buyer_name,
            count(DISTINCT j.notice_id) FILTER (WHERE notice_kind='cn')  AS n_tenders,
            count(DISTINCT j.notice_id) FILTER (WHERE notice_kind='can') AS n_awarded,
            count(DISTINCT substr(j.cpv_main,1,2))                        AS n_cpv_divisions,
            any_value(td.top_div)                                        AS top_division,
            any_value(td.top_label)                                      AS top_division_label,
            mode(substr(j.performance_nuts,1,5))                         AS main_nuts3,
            max(j.ym)                                                     AS last_activity,
            (j.entity_id IN (SELECT entity_id FROM ted_b))               AS also_on_ted
          FROM j
          JOIN read_parquet({q('entities.parquet')}) e ON e.entity_id=j.entity_id
          LEFT JOIN topdiv td ON td.entity_id=j.entity_id
          GROUP BY j.entity_id, e.canonical_name, also_on_ted
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_criteria(cfg: Config, country: str = "DE"):
    """**Zuschlagskriterien je Lead** — „gewinne ich hier ueber den Preis oder ueber das Konzept?"

    Die praktischste Einzelinformation fuer die Angebotsstrategie: „Preis 100 %" heisst
    reiner Preiswettbewerb, „Qualitaet 70 % / Preis 30 %" heisst, dass ein durchdachtes
    Konzept den hoeheren Preis schlagen kann.

    **Normiert wird je LOS, nicht je Notice.** Gemessen (2026-07-23): je Notice summierten
    36.824 Notices auf ueber 105 % — davon 95,5 % mehrlosig bei Ø 4,97 Losen, weil sich
    dort die Gewichte aller Lose addieren. Je Los treffen **97,5 %** exakt 100.

    Nur ``weight_kind`` aus ``number-weight`` zaehlt (s. `schema.Criterion`):
    ``per-*`` ist bereits Prozent, ``poi-*``/``dec-*`` sind Punkte — beide werden auf die
    Los-Summe normiert, was beide Faelle korrekt behandelt. ``ord-imp`` ist ein **Rang**
    und wird bewusst NICHT in ein Gewicht umgedeutet.

    Schreibt ``lead_criteria`` (eine Zeile je Kriterium, fuer die Detailansicht).
    """

    g = cfg.gold_dir / country
    out = (g / "lead_criteria.parquet").as_posix()
    AC = cfg.silver_table_glob("award_criteria", country)
    con = _db.connect(); con.execute("SET threads=4")
    # Rohtext -> Zahl: deutsches Dezimalkomma, Prozentzeichen, Leerzeichen.
    num = "try_cast(replace(replace(replace(c.weight,'%',''),',','.'),' ','') AS DOUBLE)"
    con.execute(f"""
        COPY (
          WITH c AS (
            SELECT c.notice_id AS lead_id, c.lot_id, c.kind, c.name,
                   c.weight_kind, {num} AS w
              -- union_by_name: der Reparse lief nur ab 2024, aeltere Monate haben
              -- die Spalte `weight_kind` noch nicht. Ohne das Flag bricht der Read.
              FROM read_parquet('{AC}', hive_partitioning=1, union_by_name=1) c
              JOIN read_parquet('{(g / "lead_export.parquet").as_posix()}') l
                ON l.lead_id = c.notice_id
          ), norm AS (
            SELECT *,
                   -- Summe der ECHTEN Gewichte im selben Los (ord-imp bleibt draussen)
                   sum(CASE WHEN weight_kind IS NULL
                             OR weight_kind LIKE 'per%' OR weight_kind LIKE 'poi%'
                             OR weight_kind LIKE 'dec%' THEN w END)
                     OVER (PARTITION BY lead_id, lot_id) AS lot_sum
              FROM c
          )
          SELECT lead_id,
                 -- lot_id darf im Supabase-PK nicht NULL sein (Kriterien ohne Los-Bezug
                 -- kommen in schlanken Dialekten vor); `criterion_no` macht den
                 -- Schluessel eindeutig, denn ein Los kann zwei gleichnamige Kriterien
                 -- tragen.
                 coalesce(lot_id, '-')                AS lot_id,
                 row_number() OVER (PARTITION BY lead_id, coalesce(lot_id,'-')
                                    ORDER BY kind, name NULLS LAST) AS criterion_no,
                 kind AS criterion_kind, name AS criterion_name, weight_kind,
                 CASE WHEN weight_kind = 'ord-imp' THEN NULL
                      WHEN lot_sum > 0 THEN round(100.0 * w / lot_sum, 1) END AS weight_pct,
                 w AS weight_raw,
                 (weight_kind = 'ord-imp')            AS is_rank,
                 (lot_sum > 0)                        AS weight_usable
            FROM norm
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_requirement(cfg: Config, country: str = "DE"):
    """**Eignungsanforderungen je Lead** — „darf ich hier ueberhaupt mitbieten?"

    Die Bekanntmachung beschreibt selten, *was* gekauft wird (61 % der Beschreibungen
    sind Zweizeiler), aber fast immer, *wer* bieten darf. Gemessen 2026-07-23 ab 2024:
    3,19 Mio. Zeilen, davon **75,2 % mit echtem Text** (>=60 Zeichen) ueber **92 % aller
    Notices** — „drei Referenzen der letzten fuenf Jahre", „Umsatz > 350 TEUR",
    „ISO 9001". Damit kann ein Nutzer einen Lead **aussortieren, bevor** er die
    Vergabeunterlagen laedt.

    Gefiltert wird nur, was nachweislich nichts traegt: reine Ja/Nein-Marker und Zeilen,
    die statt der Anforderung nur einen Portal-Link enthalten (1,2 %) — der Link steht
    ohnehin schon als `portal_url` am Lead. Alles andere bleibt, auch kurze Texte:
    „Berufshaftpflicht" ist kurz und trotzdem eine Anforderung.

    Schreibt ``lead_requirement``.
    """

    g = cfg.gold_dir / country
    out = (g / "lead_requirement.parquet").as_posix()
    RQ = cfg.silver_table_glob("requirements", country)
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          SELECT r.notice_id AS lead_id,
                 coalesce(r.lot_id, '-')              AS lot_id,
                 row_number() OVER (PARTITION BY r.notice_id, coalesce(r.lot_id,'-')
                                    ORDER BY r.kind, r.text) AS requirement_no,
                 r.kind        AS requirement_kind,
                 r.type_code   AS requirement_code,
                 r.text        AS requirement_text,
                 length(r.text) AS requirement_length
            FROM read_parquet('{RQ}', hive_partitioning=1) r
            JOIN read_parquet('{(g / "lead_export.parquet").as_posix()}') l
              ON l.lead_id = r.notice_id
           WHERE r.text IS NOT NULL
             AND lower(trim(r.text)) NOT IN ('ja','nein','yes','no','true','false')
             AND r.text NOT LIKE 'http%'
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_party(cfg: Config, country: str = "DE"):
    """**Beteiligte je Lead** — vor allem die Kontaktdaten der Vergabestelle.

    Gemessen ab 2024 (678.497 buyer-Zeilen): **E-Mail 62 % · Telefon 62 % · Web 46 %**.
    Das ist der Unterschied zwischen „hier ist ein Lead" und „hier ist ein Lead und die
    Person, die man anruft" — und es kommt aus der Bekanntmachung selbst, ohne Zukauf.

    Rollen: `buyer` (Vergabestelle), `winner` (Zuschlagsempfaenger), `review`
    (Nachpruefungsstelle), `mediation`. Die Review-Zeile ist nebenbei die Adresse, an die
    eine Ruege ginge — im Produkt bewusst nicht als Handlungsaufforderung darstellen.

    Schreibt ``lead_party``.
    """

    g = cfg.gold_dir / country
    out = (g / "lead_party.parquet").as_posix()
    PT = cfg.silver_table_glob("notice_parties", country)
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          SELECT p.notice_id AS lead_id,
                 p.role      AS party_role,
                 p.seq       AS party_no,
                 p.name      AS party_name,
                 p.national_id, p.town, p.postal_code, p.country, p.nuts,
                 p.email, p.phone, p.contact_person, p.url,
                 p.is_sme, p.in_consortium
            FROM read_parquet('{PT}', hive_partitioning=1) p
            JOIN read_parquet('{(g / "lead_export.parquet").as_posix()}') l
              ON l.lead_id = p.notice_id
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def _measure_field_usage(con, cfg: Config, country: str, since_year: int,
                         sample: int = 4000) -> None:
    """Legt die Temp-Tabelle ``usage`` an: Rohpfad → Silber-Spalte, **gemessen**.

    Statt die Zuordnung aus dem Parser-Code abzulesen (fehleranfaellig und veraltet,
    sobald jemand etwas umbaut), wird sie an den Daten nachgewiesen: fuer eine
    Stichprobe Notices jeden Silber-Spaltenwert gegen jeden Rohwert **derselben Notice**
    joinen. Trifft ein Wert, ist der Pfad die Quelle.

    Kurze Werte (<3 Zeichen) bleiben draussen — „DE" oder „01" treffen sonst zufaellig
    ein Dutzend Pfade und machten jede Zuordnung wertlos. Bei Mehrfachtreffern gewinnt
    der Pfad mit den meisten Notices.
    """
    A = cfg.silver_table_glob("attributes", country)
    N = cfg.silver_table_glob("notices", country)
    tables = {t: cfg.silver_table_glob(t, country) for t in
              ("notices", "lots", "awards", "notice_parties", "award_criteria",
               "requirements")}
    # Stichprobe **je Generation aus ihrer eigenen Zeit**, nicht ab einem festen Jahr.
    # Mit `year >= 2024` bestand die Legacy-Stichprobe aus 1.602 von 1,15 Mio. Notices
    # (0,14 %) und `text`/`ojs` fehlten ganz — die Pfadliste war damit wertlos.
    # Gestreut ueber die Jahre, damit Formularaenderungen innerhalb einer Generation
    # nicht durchrutschen.
    con.execute(f"""CREATE OR REPLACE TEMP TABLE _samp AS
        SELECT notice_id, schema_gen, year FROM read_parquet('{N}', hive_partitioning=1)
         QUALIFY row_number() OVER (PARTITION BY schema_gen, year ORDER BY notice_id)
                 <= {max(sample // 8, 200)}""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE _raw AS
        SELECT a.notice_id, s.schema_gen, a.path, a.value
          FROM read_parquet('{A}', hive_partitioning=1) a
          JOIN _samp s ON s.notice_id = a.notice_id AND s.year = a.year
         WHERE a.value IS NOT NULL AND length(a.value) >= 3""")
    parts = []
    for tname, glob in tables.items():
        cols = [c[0] for c in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{glob}', hive_partitioning=1)").fetchall()]
        for c in cols:
            if c in ("notice_id", "year", "month"):
                continue
            # KEIN Jahresfilter: die Stichprobe umfasst alle Generationen ueber ihre
            # ganze Laufzeit. Mit `year >= 2024` konnte fuer `text` (2004–2010), `ojs`
            # (2008) und den Grossteil von `legacy` nie etwas matchen — die zeigten
            # daraufhin faelschlich „0 genutzt".
            parts.append(
                f"SELECT t.notice_id, '{tname}.{c}' AS col, CAST(t.{c} AS VARCHAR) AS value "
                f"FROM read_parquet('{glob}', hive_partitioning=1) t "
                f"JOIN _samp s USING (notice_id) "
                f"WHERE t.{c} IS NOT NULL")
    con.execute("CREATE OR REPLACE TEMP TABLE _silver AS " + " UNION ALL ".join(parts))
    con.execute("""CREATE OR REPLACE TEMP TABLE usage AS
        SELECT schema_gen, path, col AS derived_column FROM (
          SELECT r.schema_gen, r.path, s.col, count(DISTINCT r.notice_id) AS n,
                 row_number() OVER (PARTITION BY r.schema_gen, r.path
                                    ORDER BY count(DISTINCT r.notice_id) DESC) AS rk
            FROM _raw r JOIN _silver s
              ON s.notice_id = r.notice_id AND s.value = r.value
           GROUP BY 1, 2, 3
        ) WHERE rk = 1""")


def build_bronze_inventory(cfg: Config, country: str = "DE", since_year: int = 2024):
    """**Feld-Inventar der Rohdaten** — „welche Spalten haben wir eigentlich in Bronze?"

    Bronze hat **keine Spalten**: es sind 270 tar.gz mit Original-TED-XML. Die ehrliche
    Entsprechung ist die Auffang-Tabelle `attributes`, die jeden Blattwert unter seinem
    XML-Pfad festhaelt (Verlust-Garantie, s. `model.ATTRIBUTES`). Dieser Builder
    aggregiert sie zu einer lesbaren Feldliste: Pfad, Abdeckung, Beispielwert.

    Gemessen 2026-07-23 fuer 2024+: **143,2 Mio. Blattwerte über 3.339 Pfade** in 678.988
    Notices — davon nur **34 mit >=50 % Abdeckung**, 405 zwischen 5 und 50 % und 2.900
    unter 5 %. Der lange Schwanz ist der Grund, warum ein Parser nie „fertig" ist: die
    seltenen Pfade sind teils Formular-Exoten, teils genau die Felder, die einem Nutzer
    im Einzelfall die Entscheidung abnehmen.

    Nach `schema_gen` getrennt, weil sich die Pfade zwischen den Generationen vollstaendig
    unterscheiden (`ContractNotice.…` vs. `TED_EXPORT.FORM_SECTION.…`) — eine gemeinsame
    Liste waere die Summe zweier disjunkter Vokabulare und damit irrefuehrend.

    **Die wichtigste Spalte ist ``derived_column``** — sie sagt, in welche Silber-Spalte
    ein Pfad fliesst, und ``is_used = false`` markiert damit, was wir heute *nicht*
    nutzen. Diese Zuordnung wird **gemessen, nicht aus dem Code gelesen**: fuer eine
    Stichprobe Notices wird jeder Silber-Wert gegen jeden Rohwert derselben Notice
    gejoint. Trifft ein Wert, ist der Pfad die Quelle. Das findet auch Faelle, in denen
    der Parser ein Feld zu lesen *scheint*, aber nichts davon ankommt.

    Gemessen 2026-07-23 (eForms): **496 von 1.585 Pfaden genutzt, 1.089 nicht** — darunter
    Felder mit >50 % Abdeckung und echtem Produktwert, z. B. ``VariantConstraintCode``
    (Nebenangebote erlaubt? 8 % ja), ``MultipleTendersCode`` (mehrere Lose? 32 % ja),
    ``FundingProgramCode`` (EU-Foerderung? 4 %), ``ContractingPartyType.PartyTypeCode``
    (Art der Vergabestelle) und ``ContractingActivity.ActivityTypeCode`` (Taetigkeitsfeld).

    Schreibt ``bronze_inventory``. Klein genug (~wenige tausend Zeilen), um sie ins
    Frontend zu exportieren.
    """

    g = cfg.gold_dir / country
    out = (g / "bronze_inventory.parquet").as_posix()
    A = cfg.silver_table_glob("attributes", country)
    N = cfg.silver_table_glob("notices", country)
    con = _db.connect(); con.execute("SET threads=4")
    _measure_field_usage(con, cfg, country, since_year)
    con.execute(f"""
        COPY (
          WITH n AS (
            -- Stichprobe je Generation UND Jahr: `text` lief 2004–2010, `legacy` bis
            -- 2024, `eforms` ab 2023. Ein fester Startjahr-Filter haette drei von fuenf
            -- Generationen fast vollstaendig ausgeblendet.
            SELECT notice_id, schema_gen, year FROM read_parquet('{N}', hive_partitioning=1)
             QUALIFY row_number() OVER (PARTITION BY schema_gen, year ORDER BY notice_id)
                     <= 1500
          ), tot AS (
            SELECT schema_gen, count(*) AS n_notices FROM n GROUP BY 1
          ), agg AS (
            SELECT n.schema_gen, a.path,
                   count(*)                    AS n_values,
                   count(DISTINCT a.notice_id) AS n_notices,
                   max(length(a.value))        AS max_length,
                   any_value(a.value)          AS example_value
              FROM read_parquet('{A}', hive_partitioning=1) a
              JOIN n ON n.notice_id = a.notice_id AND n.year = a.year
             GROUP BY 1, 2
          )
          SELECT agg.schema_gen, agg.path,
                 agg.n_values, agg.n_notices,
                 round(100.0 * agg.n_notices / tot.n_notices, 2) AS coverage_pct,
                 agg.max_length, agg.example_value,
                 -- Attribut (@…) vs. Element: Attribute tragen Codelisten-Namen und
                 -- Sprachkennungen, keine Sachdaten — im UI trennbar halten.
                 (agg.path LIKE '%@%')                           AS is_attribute,
                 u.derived_column,
                 (u.derived_column IS NOT NULL)                  AS is_used
            FROM agg JOIN tot USING (schema_gen)
            LEFT JOIN usage u ON u.path = agg.path AND u.schema_gen = agg.schema_gen
           ORDER BY agg.schema_gen, coverage_pct DESC
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_buyer_profile(cfg: Config, country: str = "DE"):
    """**Vergabestelle-Analyse** je Käufer — der konsolidierte Buyer-Intelligence-KPI.

    Führt zusammen: Aktivität (Aufträge, Ø/Jahr), Volumen (€ real-2020 + `value_coverage`
    als Ehrlichkeits-Flag, da Werte nur ~30 % gedeckt → Floor), Themen (Top-CPV-Division),
    Lieferanten-Konzentration (Top-3-Anteil → captured/offen), Wettbewerb (Single-Bieter,
    Ø Bieter), Incumbent-Retention, Entscheidungsdauer, Cross-Threshold (auch DÖE aktiv).
    Basis: ``leads`` (source='auslauf' = vergeben) + buyer_stats/history/succession/DÖE.
    Schreibt ``buyer_profile`` (eine Zeile je Käufer-Entität).
    """

    g = cfg.gold_dir / country
    def q(n): return f"'{(g / n).as_posix()}'"
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    out = (g / "buyer_profile.parquet").as_posix()
    # Optionale externe Anreicherung (Wikidata, via scripts/enrich_wikidata.py). Fehlt der
    # Cache, bleiben die Spalten NULL — Gold-Lauf braucht kein Netz.
    ext = cfg.data_dir / "reference" / "buyer_external.parquet"
    if ext.exists():
        ext_cols = ("ext.website, ext.population, ext.wikidata_id, "
                    "(ext.buyer_entity IS NOT NULL) AS is_enriched")
        ext_join = f"LEFT JOIN read_parquet('{ext.as_posix()}') ext ON ext.buyer_entity=b.buyer_entity"
    else:
        ext_cols = ("NULL::VARCHAR AS website, NULL::BIGINT AS population, "
                    "NULL::VARCHAR AS wikidata_id, false AS is_enriched")
        ext_join = ""
    # Optionaler Regions-KONTEXT (Destatis, via scripts/fetch_destatis.py): Investitions-
    # budget des Kreises. Deckt ALLE Kommunen des Kreises ab → Kontext, NICHT das Budget
    # dieser einen Vergabestelle (daraus keine Käufer-Quote bilden).
    kfin = cfg.data_dir / "reference" / "kreis_finanzen.parquet"
    if kfin.exists():
        kf_cols = "kf.investitionen_eur AS kreis_investitionen_eur, kf.fin_year AS kreis_finanzen_jahr"
        kf_join = (f"LEFT JOIN (SELECT nuts_code, any_value(investitionen_eur) investitionen_eur, "
                   f"any_value(\"year\") AS fin_year FROM read_parquet('{kfin.as_posix()}') "
                   f"WHERE nuts_code IS NOT NULL GROUP BY 1) kf ON kf.nuts_code = b.main_nuts3")
    else:
        kf_cols = ("NULL::BIGINT AS kreis_investitionen_eur, NULL::INT AS kreis_finanzen_jahr")
        kf_join = ""
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH aw AS (
            SELECT * FROM read_parquet({q('leads.parquet')})
            WHERE source='auslauf' AND buyer_entity IS NOT NULL),
          base AS (
            SELECT buyer_entity, any_value(buyer_name) AS buyer_name,
              count(*) AS total_awards,
              count(DISTINCT year(vergabe_datum)) AS active_years,
              min(year(vergabe_datum)) AS first_year, max(year(vergabe_datum)) AS last_year,
              round(count(*) FILTER (WHERE vergabe_datum >= (current_date - INTERVAL 2 YEAR))
                    / 2.0, 1) AS awards_per_year_recent,
              round(sum(value_real_2020)) AS volume_known_eur,
              round(median(value_real_2020)) AS median_award_eur,
              round(100.0*count(value_real_2020)/count(*)) AS value_coverage,
              count(DISTINCT cpv_class) AS n_categories,
              count(DISTINCT incumbent_entity) AS n_distinct_winners,
              round(100.0*avg(single_bidder::int)) AS single_bidder_rate,
              round(avg(num_tenders), 1) AS avg_bidders,
              mode(substr(buyer_nuts, 1, 3)) AS main_nuts,
              mode(substr(buyer_nuts, 1, 5)) AS main_nuts3
            FROM aw GROUP BY buyer_entity),
          topdiv AS (
            SELECT t.buyer_entity, cl.label AS top_division_label FROM (
              SELECT buyer_entity, arg_max(substr(cpv_main,1,2), c) AS d FROM (
                SELECT buyer_entity, cpv_main, count(*) c FROM aw
                WHERE cpv_main IS NOT NULL GROUP BY 1,2) GROUP BY 1) t
            LEFT JOIN read_parquet({q('dim_cpv_label.parquet')}) cl
              ON cl.cpv_code = rpad(t.d, 8, '0')),
          conc AS (
            SELECT buyer_entity_id,
              -- WICHTIG: Gewinner-Zahlen stammen aus buyer_contractor_history (ALLE Vergaben),
              -- NICHT aus `leads` (Auslauf-Radar = gefilterte Teilmenge). `wins_total` macht die
              -- Basis explizit, damit im UI nicht faelschlich durch total_awards geteilt wird.
              sum(total_wins) AS wins_total,
              count(*) AS n_contractors,
              round(100.0 * sum(total_wins) FILTER (WHERE rk <= 3) / sum(total_wins)) AS top3_share,
              string_agg(contractor_name, ', ' ORDER BY total_wins DESC)
                FILTER (WHERE rk <= 3) AS top_winners
            FROM (SELECT *, row_number() OVER (PARTITION BY buyer_entity_id ORDER BY total_wins DESC) rk
                  FROM read_parquet({q('buyer_contractor_history.parquet')})) GROUP BY 1),
          ret AS (
            SELECT buyer_entity, round(100.0*avg(retained::int)) AS retention_rate
            FROM read_parquet({q('succession_events.parquet')})
            WHERE retained OR displaced GROUP BY 1),
          doe AS (
            SELECT pe.entity_id, count(DISTINCT n.notice_id) AS n_below_threshold
            FROM read_parquet({N}, hive_partitioning=1) n
            JOIN read_parquet({q('party_entity.parquet')}) pe
              ON pe.notice_id=n.notice_id AND pe.role='buyer'
            WHERE n.schema_gen='doe' AND n.notice_kind='cn' GROUP BY 1),
          bs AS (SELECT buyer_entity_id, avg_decision_days
                 FROM read_parquet({q('buyer_stats.parquet')}))
          SELECT b.*,
            -- Wettbewerbs-Ampel (single_bidder_rate): EU-Red-Flag-Zone. Schwellen an der
            -- Verteilung aktiver Käufer geeicht (Median 15, Q3 26, P90 43).
            CASE WHEN b.single_bidder_rate IS NULL THEN NULL
                 WHEN b.single_bidder_rate >= 35 THEN 'rot'
                 WHEN b.single_bidder_rate >= 15 THEN 'gelb' ELSE 'gruen' END AS competition_flag,
            td.top_division_label,
            c.wins_total, c.n_contractors, c.top3_share,
            CASE WHEN c.top3_share >= 70 THEN 'oligopol'
                 WHEN c.top3_share >= 40 THEN 'moderat' ELSE 'fragmentiert' END AS concentration,
            c.top_winners,
            r.retention_rate,
            bs.avg_decision_days,
            coalesce(d.n_below_threshold, 0) AS n_below_threshold,
            (d.n_below_threshold IS NOT NULL) AS also_below_threshold,
            {kf_cols},
            {ext_cols}
          FROM base b
          LEFT JOIN topdiv td ON td.buyer_entity=b.buyer_entity
          LEFT JOIN conc c    ON c.buyer_entity_id=b.buyer_entity
          LEFT JOIN ret r     ON r.buyer_entity=b.buyer_entity
          LEFT JOIN doe d     ON d.entity_id=b.buyer_entity
          LEFT JOIN bs        ON bs.buyer_entity_id=b.buyer_entity
          {ext_join}
          {kf_join}
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_buyer_recent_awards(cfg: Config, country: str = "DE"):
    """„Wer gewann zuletzt" — die letzten 20 Zuschläge je Käufer als Feed fürs Dossier.

    Titel, Gewinner, Wert (real-2020 + `value_known`-Flag), Thema, Datum, Wettbewerb.
    Schreibt ``buyer_recent_awards``.
    """

    g = cfg.gold_dir / country
    def q(n): return f"'{(g / n).as_posix()}'"
    out = (g / "buyer_recent_awards.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          SELECT l.buyer_entity, l.buyer_name, l.lead_id, l.titel,
            l.incumbent_name AS winner, l.value_real_2020 AS value_eur,
            (l.value_real_2020 IS NOT NULL) AS value_known,
            l.cpv_class, cl.label AS cpv_class_label,
            l.vergabe_datum, l.single_bidder, l.num_tenders
          FROM read_parquet({q('leads.parquet')}) l
          LEFT JOIN read_parquet({q('dim_cpv_label.parquet')}) cl
            ON cl.cpv_code = rpad(l.cpv_class, 8, '0')
          WHERE l.source='auslauf' AND l.buyer_entity IS NOT NULL AND l.vergabe_datum IS NOT NULL
          QUALIFY row_number() OVER (PARTITION BY l.buyer_entity ORDER BY l.vergabe_datum DESC) <= 20
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_region_kpi(cfg: Config, country: str = "DE"):
    """**Regions-KPI je NUTS-3**: unsere Nachfrage × Destatis-Regionalkontext.

    ⚠ AT/CH: nur die NACHFRAGE-Seite traegt Inhalt. Der Kontext kommt aus Destatis und
    endet an der deutschen Grenze — gemessen 2026-08-23 stehen 39 von 40 AT-Regionen und
    23 von 23 CH-Regionen ohne Investitionen, Baubetriebe, Bevoelkerung da. (Die eine
    gefuellte AT-Zeile ist KEIN Fehljoin, sondern eine oesterreichische Vergabe mit
    Leistungsort Heidelberg.) Die Spalten bleiben NULL statt 0 — dieselbe Regel wie bei
    den 86 deutschen Regionen ohne Destatis-Zuordnung weiter unten. Wer AT/CH-Kontext
    will, braucht Statistik Austria bzw. das BFS als eigene Quelle.

    Führt erstmals Angebot und Nachfrage zusammen. Nachfrage aus ``leads`` (vergeben +
    offen), Kontext aus ``kreis_finanzen`` (Investitionen) und ``kreis_kontext``
    (A Baubetriebe/Umsatz, B Baugenehmigungen, C Schulden, D Bevölkerung/Beschäftigte).

    Abgeleitet:
      * ``intensitaet_pct`` — sichtbares Auftragsvolumen ÷ Investitionsbudget. **Untergrenze**,
        weil unsere Werte nur ~30 % gedeckt sind (``volumen_coverage`` mitliefern!).
      * ``auftraege_je_betrieb`` — Nachfrage je Baubetrieb der Region. **Deskriptiv, nicht
        erklärend**: gemessen erklärt die Dichte die Single-Bieter-Quote NICHT (je Quartil
        21/21/19/22 %, corr 0,099, n=322). Baufirmen sind mobil — der relevante Anbieterpool
        ist gewerkescharf (CPV), nicht kreisscharf. Nicht als Chancen-Signal verkaufen.
      * ``genehmigungen_gesamt`` — Vorlaufindikator (Baugenehmigungen laufen Ausschreibungen voraus).
      * Pro-Kopf-Größen für faire Regionsvergleiche.
    Fehlt ein Destatis-Cache, bleiben die betroffenen Spalten NULL (Gold-Lauf braucht kein Netz).
    Schreibt ``region_kpi``.
    """

    g = cfg.gold_dir / country
    def q(n): return f"'{(g / n).as_posix()}'"
    out = (g / "region_kpi.parquet").as_posix()
    kfin = cfg.data_dir / "reference" / "kreis_finanzen.parquet"
    kctx = cfg.data_dir / "reference" / "kreis_kontext.parquet"
    con = _db.connect(); con.execute("SET threads=4")

    # Kontext-Blöcke breit ziehen (nur wenn Cache da ist).
    if kctx.exists():
        con.execute(f"""CREATE TEMP TABLE ctx AS
            SELECT nuts_code,
              max(CASE WHEN kennzahl_code='BETR01' THEN wert END)  AS baubetriebe,
              max(CASE WHEN kennzahl_code='ERW012' THEN wert END)  AS bau_beschaeftigte,
              max(CASE WHEN kennzahl_code='UMS041' THEN wert END)  AS bau_umsatz_eur,
              max(CASE WHEN kennzahl_code='BAU017' THEN wert END)  AS genehm_wohngeb,
              max(CASE WHEN kennzahl_code='BAU018' THEN wert END)  AS genehm_nichtwohngeb,
              max(CASE WHEN kennzahl_code='SDKHGV1' THEN wert END) AS schulden_kernhaushalt_eur,
              max(CASE WHEN kennzahl_code='BEVSTD' THEN wert END)  AS bevoelkerung,
              max(CASE WHEN kennzahl_code='ERW032' THEN wert END)  AS sv_beschaeftigte
            FROM read_parquet('{kctx.as_posix()}') WHERE nuts_code IS NOT NULL GROUP BY 1""")
    else:
        con.execute("""CREATE TEMP TABLE ctx (nuts_code VARCHAR, baubetriebe DOUBLE,
            bau_beschaeftigte DOUBLE, bau_umsatz_eur DOUBLE, genehm_wohngeb DOUBLE,
            genehm_nichtwohngeb DOUBLE, schulden_kernhaushalt_eur DOUBLE, bevoelkerung DOUBLE,
            sv_beschaeftigte DOUBLE)""")
    if kfin.exists():
        con.execute(f"""CREATE TEMP TABLE fin AS
            SELECT nuts_code, any_value(investitionen_eur) AS investitionen_eur
            FROM read_parquet('{kfin.as_posix()}') WHERE nuts_code IS NOT NULL GROUP BY 1""")
    else:
        con.execute("CREATE TEMP TABLE fin (nuts_code VARCHAR, investitionen_eur BIGINT)")

    con.execute(f"""
        COPY (
          WITH nachfrage AS (
            -- Aggregation über den LEISTUNGSORT: der Käufersitz führt bei bundesweiten
            -- Käufern (DB Netz: 17 Bundesländer) in die falsche Region. Nebeneffekt: DÖE-Leads
            -- kommen so überhaupt erst rein (dort ist buyer_nuts zu 0 % gefüllt, perf_nuts zu 77 %).
            SELECT substr(g.perf_nuts, 1, 5) AS nuts_code,
              count(*) FILTER (WHERE l.source='auslauf') AS n_vergeben,
              count(*) FILTER (WHERE l.source IN ('f02','f01')) AS n_offen,
              round(sum(l.value_real_2020) FILTER (WHERE l.source='auslauf')) AS volumen_eur,
              round(sum(l.value_real_2020) FILTER (WHERE l.source='auslauf'
                    AND year(l.vergabe_datum)=2023)) AS volumen_2023_eur,
              round(100.0*count(l.value_real_2020) FILTER (WHERE l.source='auslauf')
                    / nullif(count(*) FILTER (WHERE l.source='auslauf'), 0)) AS volumen_coverage,
              round(100.0*avg(l.single_bidder::int) FILTER (WHERE l.source='auslauf')) AS single_bidder_rate,
              count(DISTINCT l.buyer_entity) AS n_vergabestellen
            FROM read_parquet({q('leads.parquet')}) l
            JOIN read_parquet({q('lead_geo.parquet')}) g ON g.lead_id = l.lead_id
            WHERE g.perf_nuts IS NOT NULL AND length(g.perf_nuts) >= 5 GROUP BY 1)
          SELECT n.nuts_code, dn.name AS region_name,
            n.n_vergeben, n.n_offen, n.n_vergabestellen,
            n.volumen_eur, n.volumen_coverage, n.single_bidder_rate,
            f.investitionen_eur,
            -- Regions-Intensität: sichtbares Volumen ÷ Investitionsbudget (UNTERGRENZE!)
            n.volumen_2023_eur,
            -- Zeitlich ausgerichtet: Vergaben 2023 ÷ Investitionsbudget 2023.
            -- >100 % heisst NICHT 'ueberinvestiert', sondern: in dieser Region dominieren
            -- Bundes-/Konzern-Kaeufer (BImA, DB, Autobahn), deren Auftraege nicht aus dem
            -- Kommunalhaushalt stammen. Genau deshalb als SIGNAL lesen, nicht als Quote.
            round(100.0 * n.volumen_2023_eur / nullif(f.investitionen_eur, 0), 1) AS intensitaet_pct,
            c.baubetriebe, c.bau_beschaeftigte, c.bau_umsatz_eur,
            -- Wettbewerbsdichte: wie viele Aufträge kommen auf einen Baubetrieb
            round(n.n_vergeben::DOUBLE / nullif(c.baubetriebe, 0), 2) AS auftraege_je_betrieb,
            -- NULL bleibt NULL. `coalesce(a,0)+coalesce(b,0)` machte aus „kein
            -- Destatis-Treffer" eine gemessene Null: 86 der 408 deutschen Regionen standen
            -- mit „0 Baugenehmigungen" da — für einen Landkreis wie den Rems-Murr-Kreis
            -- offensichtlich falsch, aber nirgends als Lücke erkennbar. Es sind exakt die
            -- Regionen ohne Destatis-Zuordnung (gleichnamige Kreise, s. docs/kpi-region-
            -- und-kontext.md): dieselben 86, die auch keine Einwohnerzahl haben.
            CASE WHEN c.genehm_wohngeb IS NULL AND c.genehm_nichtwohngeb IS NULL THEN NULL
                 ELSE coalesce(c.genehm_wohngeb, 0) + coalesce(c.genehm_nichtwohngeb, 0)
            END AS genehmigungen_gesamt,
            c.schulden_kernhaushalt_eur, c.bevoelkerung, c.sv_beschaeftigte,
            round(f.investitionen_eur / nullif(c.bevoelkerung, 0)) AS investition_je_kopf_eur,
            round(c.schulden_kernhaushalt_eur / nullif(c.bevoelkerung, 0)) AS schulden_je_kopf_eur,
            round(1000.0 * n.n_vergeben / nullif(c.bevoelkerung, 0), 2) AS auftraege_je_1000_ew
          FROM nachfrage n
          LEFT JOIN read_parquet({q('dim_nuts.parquet')}) dn ON dn.nuts_code = n.nuts_code
          LEFT JOIN fin f ON f.nuts_code = n.nuts_code
          LEFT JOIN ctx c ON c.nuts_code = n.nuts_code
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_doe_demand(cfg: Config, country: str = "DE"):
    """Unterschwellen-**Nachfrage-Dichte**: CPV-Division × NUTS-3 × Jahr → Tender-Zahl (cn).

    Wo tut sich im Unterschwellenmarkt was — die Karte, die TED nicht liefert. Region aus
    ``performance_nuts`` (Käufer-NUTS ist unterschwellig 0 %). Nur Zählungen (kein €).
    Schreibt ``doe_demand`` (cpv_div, cpv_div_label, nuts3, year, n_tenders).
    """

    g = cfg.gold_dir / country
    def q(n): return f"'{(g / n).as_posix()}'"
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    out = (g / "doe_demand.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          SELECT substr(n.cpv_main,1,2) AS cpv_div, cl.label AS cpv_div_label,
                 substr(n.performance_nuts,1,5) AS nuts3, n.year,
                 count(DISTINCT n.notice_id) AS n_tenders
          FROM read_parquet({N}, hive_partitioning=1) n
          LEFT JOIN read_parquet({q('dim_cpv_label.parquet')}) cl
            ON cl.cpv_code = rpad(substr(n.cpv_main,1,2), 8, '0')
          WHERE n.schema_gen='doe' AND n.notice_kind='cn'
            AND n.cpv_main IS NOT NULL AND n.performance_nuts IS NOT NULL
          GROUP BY 1,2,3,4
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_dim_plz(cfg: Config, country: str = "DE"):
    """PLZ → Geo-Zentroid (lat/lon) für die **Radius-Suche**.

    Quelle: GeoNames-PLZ-Datensätze ``data/reference/geonames/{DE,CH}.txt`` (CC-BY,
    download.geonames.org/export/zip/<CC>.zip). Eine PLZ hat mehrere Zeilen (Orte/
    Groß­kunden teilen sie) → Mittel der Koordinaten je PLZ = Zentroid. Dient doppelt:
    Lead-Geokoder (Buyer-PLZ → Koordinate) **und** City-Such-Geokoder („München" →
    Koordinate, per Ort-Aggregat). Schreibt ``dim_plz`` (plz, lat, lon, ort, bundesland).

    **DACH — nach (Land, PLZ) verschlüsselt:** AT und CH sind BEIDE 4-stellig und kollidieren
    (1010 = Wien AT *und* Lausanne CH). Deshalb trägt ``dim_plz`` eine ``country``-Spalte, und
    alle Geo-Joins (``build_lead_geo`` je Quelle) filtern auf das Land des Leads. Für CH/AT steht
    im ``bundesland``-Feld der Kanton/das Bundesland. Es werden alle vorhandenen ``{CC}.txt`` gelesen.
    """

    g = cfg.gold_dir / country
    gn = cfg.data_dir / "reference" / "geonames"
    # ⚠ DER SATZ IM DOCSTRING WAR UNWAHR. Hier stand ("DE", "CH", "AT") fest verdrahtet,
    # waehrend darueber steht „Es werden alle vorhandenen {CC}.txt gelesen". Am 2026-09-03 lag
    # LU.txt im Verzeichnis und wurde stillschweigend uebergangen — kein Fehler, keine leere
    # Tabelle, nur ein Land ohne Umkreissuche.
    # ⚠ NUR die PLZ-Dateien, und die heissen genau „<CC>.txt" mit ZWEI Buchstaben. Im selben
    # Verzeichnis liegen `DE_gazetteer.txt` (19 Spalten, ein voellig anderer GeoNames-Satz)
    # und `readme.txt`. Ein blosses *.txt las sie mit und liess den Aufbau abstuerzen —
    # die alte feste Liste hatte also einen Grund, nur den falschen Mechanismus.
    files = sorted(x.as_posix() for x in gn.glob("??.txt"))
    src = "[" + ", ".join(f"'{f}'" for f in files) + "]"
    out = (g / "dim_plz.parquet").as_posix()
    con = _db.connect()
    con.execute(f"""
        COPY (
          SELECT country,
                 -- LUXEMBURG SCHREIBT SEINE PLZ AUF ZWEI ARTEN. GeoNames fuehrt durchgehend
                 -- „L-4968", TED gemischt: in lead_party stehen „L-2950" UND „1000"/„8070"
                 -- nebeneinander (gemessen 2026-09-03). Ein Join auf die rohe PLZ traefe die
                 -- Haelfte. Kanonisch sind die vier Ziffern — das tippt der Nutzer, und das
                 -- erwartet plzLookup im Frontend.
                 regexp_replace(plz, '^[A-Z][A-Z]?-', '') AS plz,
                 round(avg(lat), 5) AS lat,
                 round(avg(lon), 5) AS lon,
                 any_value(ort) AS ort,
                 any_value(bundesland) AS bundesland
          FROM read_csv({src}, delim='\t', header=false, columns={{
                 'country':'VARCHAR','plz':'VARCHAR','ort':'VARCHAR','bundesland':'VARCHAR',
                 'a1':'VARCHAR','rb':'VARCHAR','a2':'VARCHAR','kreis':'VARCHAR','a3':'VARCHAR',
                 'lat':'DOUBLE','lon':'DOUBLE','acc':'VARCHAR'}})
          WHERE lat IS NOT NULL AND lon IS NOT NULL
          GROUP BY country, regexp_replace(plz, '^[A-Z][A-Z]?-', '')
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_lead_geo(cfg: Config, country: str = "DE"):
    """Geo-Koordinate je Lead — Fundament der **Radius-Suche** (#Radius).

    Waterfall: Buyer-PLZ (aus ``notice_parties``, 85 %) → ``dim_plz``-Zentroid; sonst
    ``buyer_town`` → Ort-Zentroid (aus denselben Geo-Daten); sonst keine Koordinate.
    ``geo_source`` flaggt die Herkunft ehrlich (`plz`/`ort`/`none`). Damit wird die
    Haversine-Distanz-Query je Lead möglich. Schreibt ``lead_geo`` (lead_id, lat, lon,
    plz, ort, geo_source).
    """

    g = cfg.gold_dir / country
    NP = f"'{cfg.silver_table_glob('notice_parties', country)}'"
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    L = f"'{(g / 'leads.parquet').as_posix()}'"
    DP = f"'{(g / 'dim_plz.parquet').as_posix()}'"
    out = (g / "lead_geo.parquet").as_posix()
    # PLZ-Stellenzahl je Land: DE 5-stellig, CH/AT 4-stellig (disjunkt → dieselbe dim_plz).
    # ⚠ STELLENZAHL DER PLZ, und sie scheitert LAUTLOS, wenn ein Land fehlt: der Ausdruck
    # `[0-9]{5}` trifft eine vierstellige PLZ nicht, der Lead faellt auf den Ortsnamen
    # zurueck, und die Abdeckung sieht weiter gut aus — nur die Genauigkeit ist weg.
    # Gemessen am 2026-09-03: LU stand nicht drin, also 0 von 279 Leads ueber die PLZ,
    # alle 275 ueber den Ort. Kein Fehler im Log, keine leere Tabelle.
    # Wer ein Land aufnimmt, traegt es HIER ein — die Vorgabe 5 ist eine Annahme, kein Wissen.
    _PLZ_STELLEN = {"DE": 5, "AT": 4, "CH": 4, "LU": 4}
    _pd = _PLZ_STELLEN.get(country, 5)
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH bplz AS (
            -- Buyer-PLZ auf saubere Ziffern normalisieren („D-80805" / „80805 " → „80805"),
            -- sonst scheitert der Join auf dim_plz und der Lead fällt unnötig auf den Ort-Fallback.
            SELECT notice_id, any_value(regexp_extract(postal_code, '([0-9]{{{_pd}}})', 1)) plz
            FROM read_parquet({NP}, hive_partitioning=1)
            WHERE role='buyer' AND regexp_extract(postal_code, '([0-9]{{{_pd}}})', 1) <> '' GROUP BY notice_id),
          ort_geo AS (   -- Ort-Zentroid als Fallback (normalisiert klein), nur eigenes Land
            SELECT lower(ort) ortk, avg(lat) lat, avg(lon) lon FROM read_parquet({DP})
            WHERE ort IS NOT NULL AND country = '{country}' GROUP BY 1),
          perf AS (   -- Leistungsort-NUTS je Notice (zweite Achse)
            -- Leistungsort aus dem eigenen Satz ODER aus dem Zwilling. Die zweite Quelle
            -- ist die Dubletten-Firewall: veroeffentlicht die nationale Quelle eine Region
            -- und TED nicht (oder umgekehrt), stand der Lead bisher ohne Leistungsort da
            -- und war ueber die Achse `performance` nicht auffindbar. Gemessen 2026-08-13:
            -- +229 AT, +4 CH, 0 DE. Keiner davon ist ganz ortlos — die Kaeufer-Achse trug
            -- sie schon; es kommt die ZWEITE Achse dazu, und die ist bei zentral
            -- beschaffenden Stellen die genauere von beiden.
            -- `coalesce` und nicht `union`: der eigene Satz hat Vorrang, angereichert wird
            -- nur die Luecke. Die Quelle bleibt ueber `notice_enrichment` nachvollziehbar.
            SELECT notice_id, any_value(performance_nuts) pn FROM read_parquet({N}, hive_partitioning=1)
            WHERE performance_nuts IS NOT NULL GROUP BY notice_id),
          perf_anr AS (
            SELECT notice_id, min(wert) pn FROM {_ANR_SQL(cfg, country)}
            WHERE feld='performance_nuts' GROUP BY notice_id),
          base AS (   -- Buyer-Achse zuerst (feine PLZ-Koordinate)
            SELECT l.lead_id,
              coalesce(p.lat, o.lat) AS lat, coalesce(p.lon, o.lon) AS lon,
              bplz.plz, l.buyer_town AS ort,
              CASE WHEN p.lat IS NOT NULL THEN 'plz'
                   WHEN o.lat IS NOT NULL THEN 'ort' ELSE 'none' END AS geo_source,
              -- Buyer-NUTS zuerst; wo er fehlt (DÖE-Unterschwellig = 0 %) Leistungsort-NUTS,
              -- damit der Regions-Filter auch DÖE-Leads trifft.
              coalesce(l.buyer_nuts, pf.pn, pa.pn) AS nuts,
              coalesce(pf.pn, pa.pn)               AS perf_nuts
            FROM read_parquet({L}) l
            LEFT JOIN bplz ON bplz.notice_id = l.lead_id
            LEFT JOIN read_parquet({DP}) p ON p.plz = bplz.plz AND p.country = '{country}'
            LEFT JOIN ort_geo o ON o.ortk = lower(l.buyer_town)
            LEFT JOIN perf pf ON pf.notice_id = l.lead_id
            LEFT JOIN perf_anr pa ON pa.notice_id = l.lead_id),
          centroid AS (   -- NUTS-3-Zentroid = Mittel der Buyer-Koordinaten je Region (selbst-abgeleitet)
            SELECT nuts, avg(lat) clat, avg(lon) clon FROM base WHERE lat IS NOT NULL GROUP BY nuts)
          SELECT base.lead_id, base.lat, base.lon, base.plz, base.ort, base.geo_source,
                 base.nuts, base.perf_nuts,
                 c.clat AS perf_lat, c.clon AS perf_lon   -- Leistungsort-Koordinate (NUTS-3-grob)
          FROM base LEFT JOIN centroid c ON c.nuts = base.perf_nuts
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_at_gold(cfg: Config, country: str = "AT"):
    """AT (TED, oberschwellig) → schlanke ``gold/AT/{lead_export,lead_geo,lead_deadline}`` für den
    Web-Explorer — analog ``simap.build_ch_gold``, aber aus **TED-Silber** (dieselbe Pipeline wie DE,
    nur ``--country AT``). Reicher als CH: **echter Schätzwert** (``estimated_value``) + **echte Frist**.

    Leads = offene Ausschreibungen (``notice_kind='cn'``, Frist in Zukunft). Geo über ``dim_plz``
    mit **``country='AT'``-Filter** (AT-PLZ 4-stellig kollidiert mit CH!). Award-Verknüpfung wie CH
    (Vor-Zuschlag desselben Käufers + volle CPV + Titel-Token → Amtsinhaber unsicher + Bieterzahl).
    Bewusst KEINE volle DE-Gold-Pipeline (die käme später separat, wenn AT-Volumen es rechtfertigt).
    """

    g = cfg.gold_dir / country
    g.mkdir(parents=True, exist_ok=True)
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    P = f"'{cfg.silver_table_glob('notice_parties', country)}'"
    A = f"'{cfg.silver_table_glob('awards', country)}'"
    DP = f"'{(cfg.gold_dir / 'DE' / 'dim_plz.parquet').as_posix()}'"

    # OSB-Dedup: atverg (AT-unterschwellig-Quelle) liefert AUCH oberschwellige Bekanntmachungen
    # (~36 %, geflaggt via attributes 'atverg/schwelle'='OSB'). Die deckt TED-AT bereits ab → sonst
    # Doppel-Leads. Regel: TED = oberschwellige Autorität, atverg trägt nur unterschwellig bei.
    # Da TED per Definition NUR oberschwellig führt und atverg-USB NUR unterschwellig, sind beide
    # nach dieser Filterung disjunkt (kein Content-Matching nötig). No-op, solange keine
    # atverg-attributes existieren (z. B. reiner TED-AT-Bestand).
    _attr = cfg.silver_table_glob("attributes", country)
    _has_attr = bool(list((cfg.silver_dir / country / "attributes").glob("*/*.parquet")))
    OSB_EXCLUDE = (
        f" AND n.notice_id NOT IN (SELECT notice_id FROM read_parquet('{_attr}', hive_partitioning=1)"
        f" WHERE path='atverg/schwelle' AND value='OSB')"
    ) if _has_attr else ""

    # Der OSB-Filter allein reicht NICHT — die Disjunktheits-Annahme darüber ist gemessen
    # falsch. Von 7.870 atverg-Notices, die 2025 nachweislich eine TED-Entsprechung haben,
    # tragen nur 42,8 % das OSB-Flag; 53,8 % tragen gar keinen Schwellenwert (81.626 der
    # 236.118 atverg-Notices haben kein `atverg/schwelle`-Attribut), 3,4 % sind als
    # unterschwellig geflaggt. Damit überlebten 57,2 % der echten Dubletten den Flag-Filter.
    # Die zentrale Firewall `govisor/dedupe.py` matcht sie inhaltlich; hier fliegen sie raus.
    _dedup = g / "notice_duplicates.parquet"
    # Die Master-Bedingung gilt AUCH hier. Ohne sie faellt die Dublette, obwohl ihr Master
    # laengst abgelaufen ist — die Vergabe verschwaende dann ganz. Diese Bruecke ist zwar
    # nicht mehr im Tageslauf (build_dach_gold hat sie abgeloest), aber ueber
    # `cli gold --country AT --bridge` erreichbar, und ein erreichbarer Pfad mit der
    # gefaehrlichen Haelfte einer Regel ist schlimmer als gar keiner.
    DEDUP_EXCLUDE = _redundante_zweitquelle_sql(cfg, country) if _dedup.exists() else ""
    LEAD = ("n.notice_kind='cn' AND n.submission_deadline >= current_date"
            + OSB_EXCLUDE + DEDUP_EXCLUDE)

    # WERTETRANSFER ENTFALLEN (2026-08-13, mit der Ablösung von `dedupe_at_sources.py`).
    #
    # Das alte Skript reichte den atverg-Schätzwert an die TED-Zeile weiter — begründet mit
    # 69,8 % gegen 11,0 % Abdeckung. Nachgemessen ist diese Zahl über alle Bekanntmachungs-
    # arten gerechnet und wird von den ZUSCHLÄGEN getragen: atverg führt bei `can` 98,4 %
    # Werte, bei `cn` **0,0 %**. Für Leads (= offene `cn`) kann atverg also gar nichts
    # beisteuern; die 949 Werte, die es doch tat, kamen aus stufen-gemischten Paaren
    # (atverg-`can` gegen TED-`cn`), die die neue Stufen-Sperre zu Recht nicht mehr bildet.
    #
    # Bleibt dieser Bauer ohnehin nur eine Alt-Brücke: die volle Pipeline läuft seit
    # 2026-08-13 über `scripts/build_dach_gold.py`, im Tageslauf steht build_at_gold nicht.
    AV_WERT = ""
    WERT_SQL = "n.estimated_value"
    _tok = ("list_filter(string_split(regexp_replace(lower({c}), '[^a-zäöü0-9 ]', ' ', 'g'), ' '),"
            " w -> length(w) >= 5)")
    con = _db.connect()

    con.execute(f"""COPY (
      WITH buyer AS (
        SELECT notice_id, any_value(name) buyer_name,
               any_value(regexp_extract(postal_code, '([0-9]{{4}})', 1)) plz,
               any_value(nuts) canton, any_value(town) town
        FROM read_parquet({P}, hive_partitioning=1) WHERE role='buyer' GROUP BY notice_id),
      awn AS (
        SELECT a.notice_id, bu.buyer_name, an.cpv_main, an.title AS atitle,
               a.winner_name, a.num_tenders, year(an.publication_date) AS ayear
        FROM read_parquet({A}, hive_partitioning=1) a
        JOIN read_parquet({N}, hive_partitioning=1) an ON an.notice_id = a.notice_id
        JOIN buyer bu ON bu.notice_id = a.notice_id
        WHERE an.notice_kind = 'can' AND a.winner_name IS NOT NULL),
      matched AS (
        SELECT n.notice_id AS lead_id, awn.winner_name, awn.num_tenders, awn.ayear,
               row_number() OVER (PARTITION BY n.notice_id ORDER BY awn.ayear DESC NULLS LAST) rn
        FROM read_parquet({N}, hive_partitioning=1) n
        JOIN buyer b ON b.notice_id = n.notice_id
        JOIN awn ON awn.buyer_name = b.buyer_name AND awn.cpv_main = n.cpv_main
        WHERE {LEAD}
          AND list_has_any({_tok.format(c='n.title')}, {_tok.format(c='awn.atitle')}))
      SELECT n.notice_id AS lead_id, n.title, n.description,
             length(coalesce(n.description, '')) >= 1000 AS has_detailed_description,
             b.buyer_name, n.performance_nuts AS buyer_nuts, b.town AS buyer_region_name,
             n.cpv_main AS cpv_code, n.contract_nature,
             'open' AS phase,
             (m.winner_name IS NULL) AS is_new_tender,
             n.submission_deadline AS deadline_date,
             date_diff('day', current_date, n.submission_deadline) AS days_to_deadline,
             {WERT_SQL} AS value_eur,       -- TED-Schätzwert, ersatzweise der von atverg
             -- Beide sind Schätzwerte, also bleibt das Vokabular 'estimated' korrekt
             -- (die Allow-Liste in tests/test_plumbing.py::_EXPORT_VOCAB ist fest).
             CASE WHEN {WERT_SQL} IS NOT NULL THEN 'estimated' ELSE 'unknown' END AS value_source,
             -- ⚠ `ted_url` IST FUER DIE NATIONALE AT-QUELLE IMMER LEER. Gemessen am
             -- 2026-08-22: von 10.877 `atv-`-Vorgaengen in `lead_detail` hatten NULL eine
             -- ted_url und NULL eine buyer_url — das Frontend zeigte bei 508 heute offenen
             -- AT-Vergaben ueberhaupt keinen Weg zur Quelle. Dabei traegt jeder einzelne
             -- der 238.347 atv-Vorgaenge in Silber eine eigene Seite:
             -- `https://offenevergaben.at/auftrag/31290`. Dokumente gibt es dort nicht,
             -- aber die Bekanntmachung — und ein Link dorthin ist mehr als kein Link.
             coalesce(n.ted_url, n.portal_url) AS source_url,
             coalesce(n.ted_url, n.portal_url) AS documents_url,
             FALSE AS is_nationwide, 'AT' AS country,
             m.winner_name AS incumbent_name, m.ayear AS incumbent_since_year,
             CASE WHEN m.winner_name IS NOT NULL THEN 'uncertain' END AS incumbent_source,
             CASE WHEN m.winner_name IS NOT NULL THEN 0.55 END AS incumbent_confidence,
             m.num_tenders AS n_bidders,
             CASE WHEN m.num_tenders IS NOT NULL THEN 'actual' END AS competition_source,
             CASE WHEN m.num_tenders IS NULL THEN NULL
                  WHEN m.num_tenders <= 2 THEN 'low'
                  WHEN m.num_tenders <= 5 THEN 'medium' ELSE 'high' END AS competition_level,
             -- ── ANFORDERUNGS-SIGNALE (#15 Weg A) ───────────────────────────────────────
             -- ⚠ Bis zum 2026-08-22 endete der AT-Export hier, und zwar bewusst („Bewusst
             -- KEINE volle DE-Gold-Pipeline (die käme später separat, wenn AT-Volumen es
             -- rechtfertigt)"). Der Preis dafuer war messbar: 435 offene AT-Vergaben trugen
             -- `anf.quelle = "eforms"` und darunter NICHTS — keine Bindefrist, keine
             -- Buergschaft, keine Zuschlagskriterien, keine Lose. Die Schweiz kam auf 51 %,
             -- Deutschland auf 39 bis 79 %. Es lag also nie an eForms.
             --
             -- Die Quelle trug es die ganze Zeit: Angebotsfrist 88 %, Bindefrist 71 %,
             -- Zuschlagskriterien 54 %, Nebenangebote 34 %, Buergschaft 20 %, Lose 88 %.
             --
             -- Kein zweiter Parser: `_lead_context_sql` nimmt das Land als Parameter und
             -- laeuft fuer DE und CH seit jeher. Er wird hier nur angeschlossen.
             ctx.guarantee_required, ctx.variants_allowed, ctx.validity_days,
             ctx.selection_types, ctx.deadline_time, ctx.question_deadline
      FROM read_parquet({N}, hive_partitioning=1) n
      LEFT JOIN buyer b ON b.notice_id = n.notice_id
      LEFT JOIN matched m ON m.lead_id = n.notice_id AND m.rn = 1
      LEFT JOIN ({_lead_context_sql(cfg, country)}) ctx ON ctx.notice_id = n.notice_id
      {AV_WERT}
      WHERE {LEAD}
    ) TO '{(g / 'lead_export.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    con.execute(f"""COPY (
      WITH buyer AS (
        SELECT notice_id, any_value(regexp_extract(postal_code, '([0-9]{{4}})', 1)) plz,
               any_value(town) town
        FROM read_parquet({P}, hive_partitioning=1) WHERE role='buyer' GROUP BY notice_id)
      SELECT n.notice_id AS lead_id, dp.lat, dp.lon, b.plz, b.town AS ort,
             CASE WHEN dp.lat IS NOT NULL THEN 'plz' ELSE 'none' END AS geo_source
      FROM read_parquet({N}, hive_partitioning=1) n
      LEFT JOIN buyer b ON b.notice_id = n.notice_id
      LEFT JOIN read_parquet({DP}) dp ON dp.plz = b.plz AND dp.country = 'AT'
      WHERE {LEAD}
    ) TO '{(g / 'lead_geo.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    con.execute(f"""COPY (
      SELECT n.notice_id, n.submission_deadline AS deadline_date, 'echt' AS deadline_source
      FROM read_parquet({N}, hive_partitioning=1) n WHERE {LEAD}
    ) TO '{(g / 'lead_deadline.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    n = con.execute(f"SELECT count(*) FROM read_parquet('{(g / 'lead_export.parquet').as_posix()}')").fetchone()[0]
    con.close()
    # Die Funktion dient als generische TED-Silber-Brücke und wird auch mit country='CH'
    # aufgerufen — ein festes "AT" im Log führt dann in die Irre (hat es auch: ein CH-Bau
    # meldete "AT Gold").
    print(f"{country} Gold: {n} offene Ausschreibungen → lead_export/lead_geo/lead_deadline")
    return n


def build_lead_predecessor(cfg: Config, country: str = "DE"):
    """Offene Leads (``source`` f01/f02, ohne eigenen Zuschlag) mit ihrem **Vorgänger-Zuschlag**
    verknüpfen → Incumbent, Bieterzahl, Wettbewerb + Nachfolge-**Kette**.

    Das Problem (gemessen 2026-07-29): die 12k offenen DE-Leads hatten Incumbent/Konkurrenz/Wechsel
    zu 0 %, weil eine offene Ausschreibung noch keinen Zuschlag hat. Der Amtsinhaber ist aber
    bekannt: wer den **auslaufenden Vorgänger-Vertrag** hält. Diese Brücke matcht den offenen Lead
    auf den jüngsten passenden Zuschlag desselben Käufers (Entity + CPV + Titel-Token-Überlappung)
    und erbt von dort Gewinner + Bieterzahl. Über ``incumbent_tenure`` (keyed auf die Zuschlag-
    ``notice_id``) kommt die **Kettentiefe** (bis 10 Zyklen) und „Incumbent seit" gratis dazu.

    Schreibt ``lead_predecessor.parquet`` (lead_id → incumbent_*, n_bidders, competition_level,
    chain_depth, incumbent_since_year, confidence); der Web-Export joint es für offene Leads.
    Konservativ: nur bei Entity+CPV-Gleichheit UND Titel-Token-Überlappung (sonst kein Link).
    """

    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    A = f"'{cfg.silver_table_glob('awards', country)}'"
    L = f"'{(g / 'leads.parquet').as_posix()}'"
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    IT = f"'{(g / 'incumbent_tenure.parquet').as_posix()}'"
    _tok = ("list_filter(string_split(regexp_replace(lower({c}), '[^a-zäöü0-9 ]', ' ', 'g'), ' '),"
            " w -> length(w) >= 5)")
    con = _db.connect()
    out = (g / "lead_predecessor.parquet").as_posix()
    con.execute(f"""COPY (
      WITH award_ctx AS (   -- Zuschläge mit Käufer-Entity, Gewinner, Bieterzahl, Datum, CPV, Titel
        SELECT an.notice_id, pe.entity_id AS buyer_entity, aw.winner_name, aw.num_tenders,
               an.award_date, an.cpv_main, an.title
        FROM read_parquet({N}, hive_partitioning=1) an
        JOIN read_parquet({A}, hive_partitioning=1) aw ON aw.notice_id = an.notice_id
        JOIN read_parquet({PE}) pe ON pe.notice_id = an.notice_id AND pe.role='buyer'
        WHERE an.notice_kind='can' AND aw.winner_name IS NOT NULL AND an.award_date IS NOT NULL),
      open_lead AS (
        SELECT lead_id, buyer_entity, cpv_main, titel
        FROM read_parquet({L})
        WHERE source IN ('f01','f02') AND buyer_entity IS NOT NULL AND cpv_main IS NOT NULL),
      matched AS (
        SELECT ol.lead_id, ac.notice_id AS pred_notice, ac.winner_name, ac.num_tenders,
               ac.award_date,
               row_number() OVER (PARTITION BY ol.lead_id ORDER BY ac.award_date DESC) AS rn
        FROM open_lead ol
        JOIN award_ctx ac ON ac.buyer_entity = ol.buyer_entity AND ac.cpv_main = ol.cpv_main
          AND list_has_any({_tok.format(c='ol.titel')}, {_tok.format(c='ac.title')}))
      SELECT m.lead_id, m.pred_notice, m.winner_name AS incumbent_name, m.num_tenders AS n_bidders,
             m.award_date AS pred_award_date,
             CASE WHEN m.num_tenders IS NULL THEN NULL
                  WHEN m.num_tenders <= 2 THEN 'low'
                  WHEN m.num_tenders <= 5 THEN 'medium' ELSE 'high' END AS competition_level,
             it.incumbent_since_year, it.tenure_years,
             coalesce(it.chain_depth, 1) AS chain_depth,
             'content' AS incumbent_source, 0.6 AS incumbent_confidence
      FROM matched m
      LEFT JOIN read_parquet({IT}) it ON it.notice_id = m.pred_notice
      WHERE m.rn = 1
    ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    deep = con.execute(f"SELECT count(*) FROM read_parquet('{out}') WHERE chain_depth >= 3").fetchone()[0]
    con.close()
    print(f"lead_predecessor {country}: {n:,} offene Leads verknüpft "
          f"(davon {deep:,} mit Kette ≥3 Verträge)")
    return n


def build_dim_nuts(cfg: Config, country: str = "DE"):
    """NUTS-Code → Name/Ebene/Parent für **Regions-Autocomplete** (Radius-Kombination).

    Quelle: EU-GISCO NUTS-Attributtabellen (autoritativ), ``data/reference/nuts/
    NUTS_AT_{2021,2024}.csv`` (download.gisco-services.ec.europa.eu). Union beider
    Versionen (2024-Name bevorzugt), damit Codes aus verschiedenen NUTS-Ständen über
    die Jahre abgedeckt sind. Ebene = Code-Länge − 2 (DE=0, DE2=1, DE21=2, DE212=3).
    Schreibt ``dim_nuts`` (nuts_code, name, level, parent, version).
    """

    g = cfg.gold_dir / country
    ref = cfg.data_dir / "reference" / "nuts"
    c21 = (ref / "NUTS_AT_2021.csv").as_posix()
    c24 = (ref / "NUTS_AT_2024.csv").as_posix()
    out = (g / "dim_nuts.parquet").as_posix()
    con = _db.connect()
    con.execute(f"""
        COPY (
          WITH u AS (
            SELECT NUTS_ID, NUTS_NAME, 2024 AS v FROM read_csv('{c24}', header=true)
              WHERE CNTR_CODE='{country}'
            UNION ALL
            SELECT NUTS_ID, NUTS_NAME, 2021 AS v FROM read_csv('{c21}', header=true)
              WHERE CNTR_CODE='{country}'),
          best AS (SELECT NUTS_ID, arg_max(NUTS_NAME, v) AS name, max(v) AS ver FROM u GROUP BY 1)
          SELECT NUTS_ID AS nuts_code, name,
                 length(NUTS_ID) - 2 AS level,
                 CASE WHEN length(NUTS_ID) > 2 THEN left(NUTS_ID, length(NUTS_ID) - 1) END AS parent,
                 ver AS version
          FROM best
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_dim_cpv_label(cfg: Config, country: str = "DE"):
    """CPV-Code → deutsche Bezeichnung (volles Vokabular, ~9.454 Codes).

    Quelle: offizielle EU-CPV-2008-Codeliste (``data/reference/cpv_2008.xml``,
    Download: https://ted.europa.eu/documents/d/ted/cpv_2008_xml). ``dim_cpv``
    (45 Divisionen + Branche) bleibt; dies ist die feine Code→Label-Ebene für die
    Anzeige. Coverage nutzungsgewichtet 97 % (100 % ab 2016; Rest = Legacy-CPV-2003
    in Alt-Jahren). Schreibt ``dim_cpv_label`` (cpv_code 8-stellig, label, label_en, label_fr).

    Die englischen und franzoesischen Bezeichnungen kommen aus derselben amtlichen Liste —
    kein Uebersetzen noetig und auch nicht erlaubt: die CPV-Begriffe sind Rechtsvokabular.
    """
    import xml.etree.ElementTree as ET

    src = cfg.data_dir / "reference" / "cpv_2008.xml"
    if not src.exists():
        return 0
    rows = []
    for cpv in ET.parse(src).getroot().findall("CPV"):
        code = (cpv.get("CODE") or "").split("-")[0]
        txt = {t.get("LANG"): t.text for t in cpv.findall("TEXT")}
        de = txt.get("DE")
        if code and de:
            # Die EU liefert dieselbe Codeliste in 23 Sprachen. Diese Bezeichnungen sind
            # amtlich — sie selbst zu uebersetzen waere schlechter UND falsch: „Bauarbeiten"
            # heisst im Vergaberecht „Construction work", nicht „Building work". Also die
            # Originale mitnehmen statt raten.
            rows.append((code, de, txt.get("EN"), txt.get("FR")))
    con = _db.connect()
    con.execute("CREATE TABLE t(cpv_code VARCHAR, label VARCHAR, label_en VARCHAR, label_fr VARCHAR)")
    if rows:
        con.executemany("INSERT INTO t VALUES (?,?,?,?)", rows)
    con.execute(f"COPY (SELECT * FROM t) TO "
                f"'{(cfg.gold_dir / country / 'dim_cpv_label.parquet').as_posix()}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    return len(rows)


def build_market_opportunity(cfg: Config, country: str = "DE", as_of_year: int | None = None,
                             years: int = 3, min_awards: int = 30):
    """⭐ Marktchancen-Landkarte (White-Space Explorer) — je CPV-Segment.

    Segment-intrinsische Attraktivität (user-agnostisch; die „Nähe"-Achse kommt pro Nutzer
    zur Laufzeit dazu): Nachfrage × Schwäche × Wert, plus **Struktur** (top3_share →
    fragmentiert/oligopol) und die **Top-Dominatoren = Buy-/Partner-Kandidaten**.

    Schwäche = `verfahren_status='erfolglos'`-Rate + Single-Bidder + Ø-Bieter (der A2-Kern).

    ``years`` = **3** (Default, bewusst kurz): eine 2010 erfolglose Ausschreibung sagt nichts
    über heute — Chance ist ein GEGENWARTS-Signal. Fenster + ``last_award_year`` stehen
    transparent in der Ausgabe. Score als relatives Perzentil-Ranking (0–100).
    """
    from datetime import date

    as_of = as_of_year or date.today().year
    win = as_of - years
    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    A = f"'{cfg.silver_table_glob('awards', country)}'"
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    EN = f"'{(g / 'entities.parquet').as_posix()}'"
    Q = f"'{(g / 'quality.parquet').as_posix()}'"
    DL = f"'{(g / 'dim_cpv_label.parquet').as_posix()}'"
    RS = g / "retender_signal.parquet"

    con = _db.connect(); con.execute("SET threads=4")
    if RS.exists():
        con.execute(f"CREATE TEMP TABLE chr AS SELECT cpv_class cpv4, "
                    f"count(*) FILTER (WHERE still_open) chronic_needs, max(fail_years) max_fail_years "
                    f"FROM read_parquet('{RS.as_posix()}') GROUP BY cpv_class")
    else:
        con.execute("CREATE TEMP TABLE chr(cpv4 VARCHAR, chronic_needs INT, max_fail_years INT)")
    con.execute(f"""
    CREATE TEMP TABLE base AS
    SELECT n.notice_id, substr(n.cpv_main,1,4) AS cpv4, q.final_value_clean AS val,
           q.verfahren_status, a.nt AS num_tenders, w.winner, we.canonical_name AS winner_name,
           CAST(coalesce(year(n.award_date), n.year) AS INT) AS yr
    FROM read_parquet({N}, hive_partitioning=1) n
    LEFT JOIN read_parquet({Q}) q ON q.notice_id=n.notice_id
    LEFT JOIN (SELECT notice_id, max(num_tenders) nt FROM read_parquet({A}) WHERE num_tenders>0 GROUP BY 1) a
      ON a.notice_id=n.notice_id
    LEFT JOIN (SELECT notice_id, arg_min(entity_id,seq) winner FROM read_parquet({PE})
               WHERE role='winner' GROUP BY 1) w ON w.notice_id=n.notice_id
    LEFT JOIN read_parquet({EN}) we ON we.entity_id=w.winner
    WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND CAST(n.year AS INT) >= {win}
    """)
    # Gewinner-Anteile → HHI + Top-Dominatoren
    con.execute("""CREATE TEMP TABLE ws AS
      SELECT cpv4, winner, any_value(winner_name) nm, count(*) wins,
             count(*)*1.0/sum(count(*)) OVER (PARTITION BY cpv4) sh
      FROM base WHERE winner IS NOT NULL GROUP BY cpv4, winner""")
    con.execute("""CREATE TEMP TABLE hhi AS
      SELECT cpv4, round(sum(sh*sh),3) hhi,
             round(sum(sh) FILTER (WHERE rn<=3),3) top3_share
      FROM (SELECT *, row_number() OVER (PARTITION BY cpv4 ORDER BY sh DESC) rn FROM ws)
      GROUP BY cpv4""")
    con.execute("""CREATE TEMP TABLE dom AS
      SELECT cpv4, list(struct_pack(entity_id:=winner, name:=nm, wins:=wins, share:=round(sh,3))
                        ORDER BY wins DESC) FILTER (WHERE rn<=5) AS top_dominators
      FROM (SELECT *, row_number() OVER (PARTITION BY cpv4 ORDER BY wins DESC) rn FROM ws) GROUP BY cpv4""")
    # Segment-Aggregate
    con.execute(f"""CREATE TEMP TABLE seg AS
      SELECT b.cpv4,
        count(*) AS n_awards,
        count(*) FILTER (WHERE verfahren_status='erfolglos') AS n_erfolglos,
        round(100.0*count(*) FILTER (WHERE verfahren_status='erfolglos')/count(*),1) AS erfolglos_pct,
        round(100.0*count(*) FILTER (WHERE num_tenders=1)/nullif(count(num_tenders),0),1) AS single_bidder_pct,
        round(avg(num_tenders),1) AS avg_bidders,
        round(median(val)) AS median_value,
        sum(val) AS total_value_known,
        count(DISTINCT winner) AS n_contractors,
        max(yr) AS last_award_year
      FROM base b GROUP BY b.cpv4 HAVING count(*) >= {min_awards}""")
    # Score: relatives Perzentil-Ranking über Wert / Schwäche / Nachfrage
    out = (g / "market_opportunity.parquet").as_posix()
    con.execute(f"""
    COPY (
      WITH s AS (
        SELECT seg.*, hhi.hhi, hhi.top3_share, dom.top_dominators, dl.label AS segment_label,
          coalesce(chr.chronic_needs,0) AS chronic_needs, chr.max_fail_years,
          coalesce(erfolglos_pct,0)+coalesce(single_bidder_pct,0) AS weakness_raw
        FROM seg LEFT JOIN hhi ON hhi.cpv4=seg.cpv4 LEFT JOIN dom ON dom.cpv4=seg.cpv4
        LEFT JOIN chr ON chr.cpv4=seg.cpv4
        LEFT JOIN read_parquet({DL}) dl ON dl.cpv_code=seg.cpv4||'0000'),
      r AS (
        SELECT *,
          percent_rank() OVER (ORDER BY coalesce(median_value,0)) AS value_pr,
          percent_rank() OVER (ORDER BY weakness_raw) AS weakness_pr,
          percent_rank() OVER (ORDER BY n_awards) AS demand_pr
        FROM s)
      SELECT cpv4, segment_label, n_awards, n_erfolglos, erfolglos_pct, single_bidder_pct,
             avg_bidders, median_value, total_value_known, n_contractors, hhi, top3_share,
             CASE WHEN top3_share>=0.6 THEN 'oligopol'
                  WHEN top3_share<0.25 THEN 'fragmentiert' ELSE 'moderat' END AS struktur,
             round(100*(0.35*value_pr + 0.35*weakness_pr + 0.30*demand_pr)) AS opportunity_score,
             chronic_needs, max_fail_years,
             top_dominators, last_award_year, {win} AS window_start, {as_of} AS window_end
      FROM r
    ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


def build_retender_signal(cfg: Config, country: str = "DE", as_of_year: int | None = None,
                          min_fail_years: int = 2):
    """⭐ Chronische Fehl-Ausschreibungen — „seit X Jahren Y-mal erfolglos gesucht".

    Der stärkste Kauf-/Chancen-Hinweis: ein Bedarf, den eine Behörde wiederholt erfolglos
    ausschreibt = verzweifelter Käufer, kaum Wettbewerb. Naiv (Behörde+CPV) überzählt bei
    Mega-Käufern/Framework-Losen — darum **inhaltsgeclustert** (Titel-Token-Ähnlichkeit, wie
    das Nachfolge-Modell): ein Bedarf = titelähnliche erfolglose Tender derselben Behörde+CPV.

    Zählt DISTINKTE Fehl-JAHRE (Anläufe), nicht Lose. Schreibt ``retender_signal``
    (buyer_entity, cpv_class, need_title, fail_attempts, first_fail_year, last_fail_year,
    span_years, still_open). Gibt die Zahl chronischer Bedarfe zurück.
    """
    from datetime import date
    from collections import defaultdict

    as_of = as_of_year or date.today().year
    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    Q = f"'{(g / 'quality.parquet').as_posix()}'"
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"

    con = _db.connect(); con.execute("SET threads=4")
    rows = con.execute(f"""
        SELECT bpe.buyer, substr(n.cpv_main,1,4) cpv4,
               CAST(coalesce(year(n.award_date), n.year) AS INT) yr, n.title
        FROM read_parquet({N}, hive_partitioning=1) n
        JOIN (SELECT notice_id, arg_min(entity_id,seq) buyer FROM read_parquet({PE})
              WHERE role='buyer' GROUP BY 1) bpe ON bpe.notice_id=n.notice_id
        JOIN read_parquet({Q}) q ON q.notice_id=n.notice_id
        WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND n.title IS NOT NULL
          AND q.verfahren_status='erfolglos'
    """).fetchall()

    groups: dict = defaultdict(list)
    for buyer, cpv4, yr, title in rows:
        groups[(buyer, cpv4)].append((yr, title, _succ_tokens(title)))

    out_rows = []
    for (buyer, cpv4), items in groups.items():
        used = [False] * len(items)
        for i in range(len(items)):
            if used[i]:
                continue
            cl = [i]; used[i] = True
            for j in range(i + 1, len(items)):
                if used[j]:
                    continue
                a, b = items[i][2], items[j][2]
                if a and b and len(a & b) / len(a | b) >= 0.55:
                    cl.append(j); used[j] = True
            yrs = {items[k][0] for k in cl}
            if len(yrs) >= min_fail_years:
                # still_open = letzter Fehlversuch aktuell genug, um noch relevant zu sein (3-J-Fenster)
                out_rows.append((buyer, cpv4, items[i][1], len(cl), len(yrs),
                                 min(yrs), max(yrs), max(yrs) - min(yrs), max(yrs) >= as_of - 3))

    con.execute("CREATE TEMP TABLE t(buyer_entity VARCHAR, cpv_class VARCHAR, need_title VARCHAR, "
                "fail_attempts INT, fail_years INT, first_fail_year INT, last_fail_year INT, "
                "span_years INT, still_open BOOLEAN)")
    if out_rows:
        con.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?)", out_rows)
    con.execute(f"COPY (SELECT * FROM t) TO '{(g / 'retender_signal.parquet').as_posix()}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    return len(out_rows)


def build_cpv_adjacency(cfg: Config, country: str = "DE", since_year: int = 2016,
                        min_shared: int = 3):
    """CPV-Segment-Nähe über Firmen-Co-Occurrence — die „Skill-Adjacency".

    Zwei CPV-Klassen sind nah, wenn Firmen, die das eine gewinnen, oft auch das andere
    gewinnen. Das ist die persönliche Achse des Marktchancen-Radars: „diese offenen
    Märkte liegen nah an dem, was DU schon kannst". User-agnostische Referenz — die
    „Nähe" eines Kandidaten zum Nutzer-Footprint entsteht zur Laufzeit.

    ``cond_prob`` = P(Firma bedient cpv_b | bedient cpv_a) — gerichtet a→b. Schreibt
    ``cpv_adjacency`` (cpv_a, cpv_b, shared_firms, jaccard, cond_prob).
    """

    g = cfg.gold_dir / country
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    PE = f"'{(g / 'party_entity.parquet').as_posix()}'"
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        CREATE TEMP TABLE fc AS
        SELECT DISTINCT w.entity_id AS firm, substr(n.cpv_main,1,4) AS cpv4
        FROM read_parquet({N}, hive_partitioning=1) n
        JOIN (SELECT notice_id, entity_id FROM read_parquet({PE}) WHERE role='winner') w
          ON w.notice_id=n.notice_id
        WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL
          AND CAST(n.year AS INT) >= {since_year} AND w.entity_id NOT LIKE 'unresolved:%'
    """)
    con.execute("CREATE TEMP TABLE cnt AS SELECT cpv4, count(DISTINCT firm) n FROM fc GROUP BY cpv4")
    out = (g / "cpv_adjacency.parquet").as_posix()
    con.execute(f"""
        COPY (
          WITH co AS (
            SELECT a.cpv4 ca, b.cpv4 cb, count(*) shared
            FROM fc a JOIN fc b ON a.firm=b.firm AND a.cpv4<>b.cpv4
            GROUP BY 1,2 HAVING count(*) >= {min_shared})
          SELECT co.ca AS cpv_a, co.cb AS cpv_b, co.shared AS shared_firms,
                 round(co.shared*1.0/(na.n + nb.n - co.shared), 3) AS jaccard,
                 round(co.shared*1.0/na.n, 3) AS cond_prob
          FROM co JOIN cnt na ON na.cpv4=co.ca JOIN cnt nb ON nb.cpv4=co.cb
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n


# Bandgrenzen (real 2020) — identisch zu build_leads.value_band, als SQL-Ausdruck.
def _band_sql(col: str) -> str:
    # 7-Stufen-Pricing-Schema, Grenzen an den echten Wert-Perzentilen (p20/p40/p60/p80
    # ~ 100k/250k/500k/1,3M) + Rahmen-Splits bei 5M/25M. NUR fuer die Gebuehren-Basis
    # value_band_effektiv — bewusst getrennt vom KPI-value_band (5 Baender).
    #
    # ⚠ DIESE FUNKTION IST DIE QUELLE DER LABELS. Hier stand „Labels = exakt die Keys in
    # pricing.SCHEDULE" — `govisor/pricing.py` ist aber am 2026-08-17 mit der Erfolgs-
    # gebuehr geloescht worden (Commit dd1f290). Der Verweis zeigte also acht Tage lang auf
    # eine Datei, die es nicht gibt. Wer die Bandgrenzen aendert, aendert sie HIER und
    # zieht `tests/test_plumbing.py::PRICING_BANDS` nach; eine dritte Stelle gibt es nicht
    # mehr.
    return (f"CASE WHEN {col} IS NULL THEN 'unbekannt' "
            f"WHEN {col}<100000 THEN '<100k' WHEN {col}<250000 THEN '100-250k' "
            f"WHEN {col}<500000 THEN '250-500k' WHEN {col}<1300000 THEN '500k-1,3M' "
            f"WHEN {col}<5000000 THEN '1,3-5M' WHEN {col}<25000000 THEN '5-25M' "
            f"ELSE '>25M' END")


def build_value_band_effektiv(cfg: Config, country: str = "DE", min_samples: int = 10,
                              default_band: str = "250-500k"):
    """Gebühren-Basis je Lead: ein Band, das NIE „unbekannt" ist (für ein Erfolgs-
    gebühren-Preismodell).

    Echter Wert (57 %) → Band (`band_source='echt'`/`'geschaetzt'`). Sonst
    **CPV-Klassen-Median** (≥``min_samples`` bewertete Leads) → imputiertes Band
    (`'imputiert'`). Sonst Default-Band (`'default'`, der Median-Bereich, wo die
    Masse liegt). Basis = ``value_real_2020`` (deflationiert, jahresvergleichbar),
    konsistent zu ``value_band``. Schreibt ``value_band_effektiv``
    (lead_id, value_effektiv, band_effektiv, band_source).
    """

    g = cfg.gold_dir / country
    L = f"'{(g / 'leads.parquet').as_posix()}'"
    out = (g / "value_band_effektiv.parquet").as_posix()
    con = _db.connect(); con.execute("SET threads=4")
    con.execute(f"""
        COPY (
          WITH med AS (
            SELECT cpv_class, median(value_real_2020) m
            FROM read_parquet({L}) WHERE value_source <> 'unbekannt' AND value_real_2020 IS NOT NULL
            GROUP BY cpv_class HAVING count(*) >= {min_samples})
          SELECT l.lead_id, l.cpv_class,
            CASE WHEN l.value_source <> 'unbekannt' THEN l.value_real_2020 ELSE med.m END AS value_effektiv,
            CASE WHEN l.value_source <> 'unbekannt' THEN {_band_sql('l.value_real_2020')}
                 WHEN med.m IS NOT NULL THEN {_band_sql('med.m')}
                 ELSE '{default_band}' END AS band_effektiv,
            CASE WHEN l.value_source = 'final' THEN 'echt'
                 WHEN l.value_source = 'geschaetzt' THEN 'geschaetzt'
                 WHEN med.m IS NOT NULL THEN 'imputiert'
                 ELSE 'default' END AS band_source
          FROM read_parquet({L}) l LEFT JOIN med ON med.cpv_class = l.cpv_class
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    return n

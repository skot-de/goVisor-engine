"""Vollständigkeitsprüfung gegen eine unabhängige Referenz.

Monate untereinander zu vergleichen findet nur Ausreißer. Fehlen in *jedem*
Monat 10.000 Notices, ist die Kurve glatt und plausibel — und falsch. Deshalb
prüfen wir gegen die TED Search API, die unabhängig zählt, wie viele Notices
ein Monat hat.

Kalibriert an DE 2023-06: die API meldet 69.655 Notices für alle Länder, das
Paket enthält exakt 69.655. Für DE meldet sie 13.720, unser Bronze hält 13.716
— die Differenz von 4 stammt aus Notices, deren Länderzuordnung wir anders
lesen (die API nutzt `buyer-country`, wir das `ISO_COUNTRY` der Notice).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import requests

from . import bulk
from .config import Config

# Tabellen, die eine Fremdschluessel-Spalte tragen und trotzdem NICHT geprueft werden.
# Als Daten und nicht als Kommentar, damit `test_jede_gold_tabelle_mit_fk_wird_geprueft`
# sie kennt: eine Ausnahme, die nur in Prosa steht, kann eine Pruefung nicht von einer
# Nachlaessigkeit unterscheiden.
FK_AUSNAHMEN: dict[str, str] = {
    "entity_merge_map.parquet":
        "100 % Waisen, und das ist der Zweck: die Spalte nennt die QUELL-Entitaet einer "
        "Verschmelzung, die es danach nicht mehr gibt (gemessen 2026-08-31: 10.018).",
    "entity_group.parquet":
        "12.861 nicht aufloesbar, davon 4.916 verschmolzen und 7.945 Mitglieder aus dem "
        "kuratierten Gruppen-Katalog, die in DE nie als Partei auftraten. Eine "
        "Gruppendefinition darf Mitglieder nennen, die man noch nicht gesehen hat.",
}


def gold_integrity(cfg: Config, country: str = "DE") -> list[tuple[str, int]]:
    """Referenz-Integrität der Gold-Tabellen — jeder FK muss auflösen.

    Der Fall, der das nötig macht: ``build_entities`` schreibt ``entities`` und
    ``party_entity`` nacheinander. Stirbt der Prozess dazwischen (z. B. RAM),
    zeigt ``party_entity`` auf entity_ids, die es in ``entities`` nicht mehr gibt
    — Waisen, die Leads still verschwinden lassen. Jeder Rebuild muss hier 0
    liefern. Gibt (Beschreibung, Anzahl) je Verstoß zurück (leer = sauber).
    """
    import duckdb

    g = cfg.gold_dir / country
    def q(path):
        return f"'{(g / path).as_posix()}'"
    # (Beschreibung, Kind-Tabelle, Kind-Spalte, Eltern-Tabelle, Eltern-Spalte)
    checks = [
        ("party_entity → entities", "party_entity.parquet", "entity_id", "entities.parquet", "entity_id"),
        ("leads.buyer_entity → entities", "leads.parquet", "buyer_entity", "entities.parquet", "entity_id"),
        ("leads.incumbent_entity → entities", "leads.parquet", "incumbent_entity", "entities.parquet", "entity_id"),
        ("leads.lead_id → quality", "leads.parquet", "lead_id", "quality.parquet", "notice_id"),
        ("contract_chains.incumbent → entities", "contract_chains.parquet", "incumbent", "entities.parquet", "entity_id"),
        ("buyer_stats.buyer → entities", "buyer_stats.parquet", "buyer_entity_id", "entities.parquet", "entity_id"),
        ("contractor_stats.entity → entities", "contractor_stats.parquet", "entity_id", "entities.parquet", "entity_id"),
        ("buyer_contractor_history.contractor → entities", "buyer_contractor_history.parquet", "contractor_entity_id", "entities.parquet", "entity_id"),
        ("contract_succession.successor → quality", "contract_succession.parquet", "successor", "quality.parquet", "notice_id"),
        ("contract_succession.predecessor → quality", "contract_succession.parquet", "predecessor", "quality.parquet", "notice_id"),
        ("award_tender_link.award → quality", "award_tender_link.parquet", "award_notice_id", "quality.parquet", "notice_id"),
        ("award_tender_link.tender → quality", "award_tender_link.parquet", "tender_notice_id", "quality.parquet", "notice_id"),
        ("value_anchor.notice → quality", "value_anchor.parquet", "notice_id", "quality.parquet", "notice_id"),
        ("lead_deadline.notice → quality", "lead_deadline.parquet", "notice_id", "quality.parquet", "notice_id"),
        ("lead_duration.notice → quality", "lead_duration.parquet", "notice_id", "quality.parquet", "notice_id"),
        ("lead_detail.lead_id → leads", "lead_detail.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("entity_identity.entity_id → entities", "entity_identity.parquet", "entity_id", "entities.parquet", "entity_id"),
        ("lead_geo.lead_id → leads", "lead_geo.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("lead_export.lead_id → leads", "lead_export.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("doe_buyer_profile.buyer_entity → entities", "doe_buyer_profile.parquet", "buyer_entity",
         "entities.parquet", "entity_id"),
        ("buyer_profile.buyer_entity → entities", "buyer_profile.parquet", "buyer_entity",
         "entities.parquet", "entity_id"),
        ("buyer_recent_awards.lead_id → leads", "buyer_recent_awards.parquet", "lead_id",
         "leads.parquet", "lead_id"),
        # ── Nachtrag 2026-08-25 ──────────────────────────────────────────────────────
        # Diese Liste war auf 22 Pruefungen stehengeblieben, waehrend `data/gold/<L>`
        # auf 64 Tabellen gewachsen ist — 44 davon kamen hier nicht vor, darunter die
        # gesamte Los-, CPV-, Text- und Kriterien-Ebene. CLAUDE.md behauptete derweil
        # „Alle neuen Tabellen in verify.gold_integrity (FK sauber)". Dieselbe Krankheit
        # wie beim Altersbericht, der `lead_lot` nie gemeldet hat: eine handgepflegte
        # Liste, die aufgehoert hat zu wachsen.
        #
        # Alle folgenden wurden am 2026-08-25 gegen den Bestand gemessen und lagen bei
        # 0 Waisen. Sie stehen hier, damit sie es bleiben.
        ("lead_lot.lead_id → leads", "lead_lot.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("lead_cpv.lead_id → leads", "lead_cpv.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("lead_party.lead_id → leads", "lead_party.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("lead_text.lead_id → leads", "lead_text.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("lead_criteria.lead_id → leads", "lead_criteria.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("lead_requirement.lead_id → leads", "lead_requirement.parquet", "lead_id",
         "leads.parquet", "lead_id"),
        ("lead_predecessor.lead_id → leads", "lead_predecessor.parquet", "lead_id",
         "leads.parquet", "lead_id"),
        ("lead_region_fill.lead_id → leads", "lead_region_fill.parquet", "lead_id",
         "leads.parquet", "lead_id"),
        # ⚠ Nicht nur die Zeile pruefen, sondern den WERT. Bis zum 2026-09-02 reichte die
        # Ableitung durch, was im Bestand stand, ohne es gegen die Regionsliste zu halten:
        # 199 oesterreichische Leads erbten `ATZZ` (Extra-Regio), 2 Schweizer `BS`
        # (Kantonskuerzel) — und 4 deutsche `BE3`, also Bruessel. Kein Fremdschluessel
        # hat widersprochen, weil keiner auf diese Spalte zeigte.
        ("lead_region_fill.region → dim_nuts", "lead_region_fill.parquet",
         "buyer_nuts1_abgeleitet", "dim_nuts.parquet", "nuts_code"),
        ("value_band_effektiv.lead_id → leads", "value_band_effektiv.parquet", "lead_id",
         "leads.parquet", "lead_id"),
        ("review_queue.notice → quality", "review_queue.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        # ── Nachtrag 2026-08-31 ──────────────────────────────────────────────────────
        # Gefunden nicht durch Nachdenken, sondern durch die Meta-Pruefung unten: drei
        # Tabellen trugen eine Fremdschluessel-Spalte und kamen hier nicht vor. Alle drei
        # am 2026-08-31 gegen den Bestand gemessen, alle 0 Waisen.
        ("buyer_loyalty.buyer → entities", "buyer_loyalty.parquet", "buyer_entity",
         "entities.parquet", "entity_id"),
        ("retender_signal.buyer → entities", "retender_signal.parquet", "buyer_entity",
         "entities.parquet", "entity_id"),
        ("buyer_traeger.entity → entities", "buyer_traeger.parquet", "entity_id",
         "entities.parquet", "entity_id"),
        # ── Nachtrag 2026-09-01: die LLM-Auswertung als Tabelle ──────────────────────
        # Eltern ist `quality`, NICHT `leads`: ausgewertet wird jeder Vorgang mit
        # Unterlagen, und 42,8 % davon sind keine offenen Leads (Zuschlaege, abgelaufene).
        # Gegen `leads` gepruegt gaebe es 151.427 „Waisen", die alle richtig sind —
        # ein Fehlalarm, der die Pruefung wertlos machen wuerde. Gegen `quality`
        # gemessen 2026-09-01: 0 Waisen bei 7.188 bzw. 396.284 Zeilen.
        ("doc_analysis.notice → quality", "doc_analysis.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        # ⚠ Vorgaenge: beide Tabellen haengen an `notice_id`. `vorgang_notice` ist die
        # Mitgliedschaft (welche Bekanntmachung gehoert in welche Akte) — eine Waise dort
        # laesst eine Bekanntmachung lautlos aus ihrem Vorgang fallen.
        ("vorgang_notice.notice → quality", "vorgang_notice.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        # ⚠ Eine Waise hier heisst: ein Kettenglied zeigt auf einen Vorgang, den es nicht
        # gibt — die Kette bricht in der Mitte, ohne dass es jemand sieht.
        ("vorgang_kette.vorgang → vorgaenge", "vorgang_kette.parquet", "vorgang_id",
         "vorgaenge.parquet", "vorgang_id"),
        ("vorgang_kette.kette → vorgaenge", "vorgang_kette.parquet", "kette_id",
         "vorgaenge.parquet", "vorgang_id"),
        ("doc_checklist.notice → quality", "doc_checklist.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        ("doc_verworfen.notice → quality", "doc_verworfen.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        # Dieselbe Herkunft wie die drei darueber: `doc_qa_stand` zaehlt Fragenkataloge
        # aus `doc_text`, also aus derselben Grundgesamtheit. Gegen `leads` gepruegt
        # waere es derselbe Fehlalarm.
        ("doc_qa_stand.notice → quality", "doc_qa_stand.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        ("incumbent_tenure.notice → quality", "incumbent_tenure.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        ("notice_enrichment.notice → quality", "notice_enrichment.parquet", "notice_id",
         "quality.parquet", "notice_id"),
        ("succession_events.successor → quality", "succession_events.parquet", "successor",
         "quality.parquet", "notice_id"),
        ("notice_duplicates.master → quality", "notice_duplicates.parquet", "master_id",
         "quality.parquet", "notice_id"),
        ("notice_duplicates.duplicate → quality", "notice_duplicates.parquet", "duplicate_id",
         "quality.parquet", "notice_id"),
        ("document_duplicates.master → quality", "document_duplicates.parquet", "master_id",
         "quality.parquet", "notice_id"),
        # ⚠ `lead_kategorie` steht bewusst DAHINTER (s. unten bei den Ausnahmen): am
        # 2026-08-25 lagen dort 62 Waisen, und die Ursache sass nicht in der Verdrahtung,
        # sondern im Modellschritt von `govisor/kategorie.py`.
        ("lead_kategorie.notice → quality", "lead_kategorie.parquet", "notice_id",
         "quality.parquet", "notice_id"),
    ]

    # ── NUR IN DE PRUEFBAR, mit Messung statt Vermutung ─────────────────────────────
    #
    # `build_at_gold`/`simap.build_ch_gold` bauen `leads` bewusst SCHMALER als DE: nur
    # offene Ausschreibungen mit Frist in der Zukunft (steht so im Docstring von
    # `build_at_gold`). `lead_lot` und `lead_cpv` entstehen dagegen ueber den ganzen
    # Bestand. Ein Los zu einem abgelaufenen Vorgang ist dort also KEIN Fehler.
    #
    # Gemessen 2026-08-25: AT 36, CH 40 solcher Vorgaenge — keiner als Dublette markiert,
    # alle in Silber vorhanden, 31 von 36 vom Typ `cn`. DE: 0, weil `build_leads` dort
    # auch auslaufende und prospektive Vergaben aufnimmt.
    #
    # ⚠ Wer AT/CH auf die volle Gold-Kette hebt, streicht diese Zeile — dann muss die
    # Pruefung dort genauso greifen.
    nur_de = {"lead_lot.parquet", "lead_cpv.parquet"}

    # ── Schluessel, die ENTITAET ODER GRUPPE sein duerfen ────────────────────────────
    #
    # `build_succession_kpis` baut seine Gewinnerlisten als `coalesce(group_id, entity_id)`
    # — bewusst gruppen-bewusst, damit Siemens AG und Siemens Mobility nicht als Wechsel
    # zaehlen. Diese Spalten gegen `entities` allein zu pruefen ergibt Fehlalarm: beim
    # ersten Anlauf am 2026-08-25 meldeten sie 18.236 bzw. 10.678 „Waisen", und alle
    # waren Gruppenkennungen. Gegen die Vereinigung gemessen: 0.
    gruppen_checks = [
        ("head_to_head.winner → entity|group", "head_to_head.parquet", "winner_entity"),
        ("head_to_head.loser → entity|group", "head_to_head.parquet", "loser_entity"),
        ("contractor_loss.entity → entity|group", "contractor_loss.parquet", "entity_id"),
    ]

    # ── BEWUSST NICHT GEPRUEFT, mit Grund ───────────────────────────────────────────
    #
    # `entity_merge_map.entity_id`  → 100 % „Waisen", und das ist der Zweck: die Spalte
    #   nennt die QUELL-Entitaet einer Verschmelzung, die es danach nicht mehr gibt.
    #   Geprueft wird stattdessen `ziel_entity_id` (unten in `checks` nicht noetig — sie
    #   loest zu 100 % auf, gemessen 2026-08-25).
    # `entity_group.entity_id`      → 12.861 nicht aufloesbar, davon 4.916 verschmolzen
    #   und 7.945 Mitglieder aus dem kuratierten Gruppen-Katalog, die in DE nie als
    #   Partei aufgetreten sind (in `party_entity`: 0). Eine Gruppendefinition darf
    #   Mitglieder nennen, die man noch nicht gesehen hat.
    con = duckdb.connect()
    out: list[tuple[str, int]] = []
    for label, child, ckey, parent, pkey in checks:
        if not (g / child).exists() or not (g / parent).exists():
            continue
        if child in nur_de and country != "DE":
            continue
        n = con.execute(
            f"SELECT count(*) FROM {q(child)} c "
            f"LEFT JOIN {q(parent)} p ON p.{pkey}=c.{ckey} "
            f"WHERE c.{ckey} IS NOT NULL AND p.{pkey} IS NULL"
        ).fetchone()[0]
        if n:
            out.append((label, n))

    # ── ABDECKUNG statt Fremdschluessel: die andere Richtung ────────────────────────
    #
    # Ein FK-Check fragt „zeigt jede Zeile auf etwas Gueltiges". Die Zusage der Traeger-Ebene
    # ist die UMGEKEHRTE: „bekommt jede Vergabestelle eine Zeile". Sie kann tadellos
    # fremdschluessel-sauber sein und trotzdem die Haelfte der Kaeufer nicht enthalten —
    # und genau dann verliert der erste Verbraucher, der den Aussenjoin vergisst, still die
    # Haelfte der Vergabestellen. Darum hier eigens geprueft.
    bt, pe_p = g / "buyer_traeger.parquet", g / "party_entity.parquet"
    if bt.exists() and pe_p.exists():
        n = con.execute(
            f"SELECT count(*) FROM (SELECT DISTINCT entity_id FROM {q('party_entity.parquet')} "
            f"WHERE role='buyer' EXCEPT SELECT entity_id FROM {q('buyer_traeger.parquet')})"
        ).fetchone()[0]
        if n:
            out.append(("Kaeufer ohne Traeger-Zeile", n))

    eg = g / "entity_group.parquet"
    if (g / "entities.parquet").exists():
        raum = (f"SELECT entity_id AS k FROM {q('entities.parquet')}"
                + (f" UNION SELECT group_id FROM {q('entity_group.parquet')}" if eg.exists() else ""))
        for label, child, ckey in gruppen_checks:
            if not (g / child).exists():
                continue
            n = con.execute(
                f"SELECT count(*) FROM {q(child)} c "
                f"LEFT JOIN ({raum}) p ON p.k=c.{ckey} "
                f"WHERE c.{ckey} IS NOT NULL AND p.k IS NULL"
            ).fetchone()[0]
            if n:
                out.append((label, n))
    con.close()
    return out


API_URL = "https://api.ted.europa.eu/v3/notices/search"
# Die Search API indiziert erst ab 2016, und 2016 nur teilweise.
API_COVERAGE_START = (2016, 1)

_MONTH_END = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
              7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


@dataclass
class MonthCheck:
    key: str
    bronze_notices: int | None = None     # tatsächlich gelesen, nicht aus dem Log
    bronze_readable: bool | None = None
    api_country: int | None = None
    api_total: int | None = None
    error: str | None = None

    @property
    def delta(self) -> int | None:
        if self.bronze_notices is None or self.api_country is None:
            return None
        return self.bronze_notices - self.api_country

    @property
    def delta_pct(self) -> float | None:
        if self.delta is None or not self.api_country:
            return None
        return 100.0 * self.delta / self.api_country


def api_count(year: int, month: int, country: str | None = None,
              attempts: int = 3) -> int | None:
    """Wie viele Notices hat TED für diesen Monat? None, wenn nicht abfragbar."""
    end = _MONTH_END[month]
    query = f"publication-date>={year}{month:02d}01 AND publication-date<={year}{month:02d}{end}"
    if country:
        query += f" AND buyer-country={country}"
    for attempt in range(attempts):
        try:
            response = requests.post(
                API_URL,
                json={"query": query, "fields": ["publication-number"], "limit": 1},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=90,
            )
            if response.status_code == 200:
                return response.json().get("totalNoticeCount")
        except requests.RequestException:
            pass
        time.sleep(3 * (attempt + 1))
    return None


def count_bronze(path: Path) -> tuple[int | None, bool, str | None]:
    """Notices im Archiv zählen, indem es komplett gelesen wird.

    Kein Blick auf die Dateigröße: ein abgeschnittenes Archiv hat eine
    plausible Größe. Nur der vollständige Durchlauf beweist Lesbarkeit.
    """
    if not path.exists():
        return None, False, "fehlt"
    try:
        return sum(1 for _ in bulk.iter_notices(path)), True, None
    except Exception as exc:
        return None, False, f"{type(exc).__name__}: {exc}"


def check_month(cfg: Config, country: str, key: str, with_api: bool = True) -> MonthCheck:
    year, month = (int(p) for p in key.split("-"))
    check = MonthCheck(key=key)
    check.bronze_notices, check.bronze_readable, check.error = count_bronze(
        cfg.raw_path(country, key)
    )
    if with_api and (year, month) >= API_COVERAGE_START:
        alpha3 = _alpha3(country)
        check.api_country = api_count(year, month, alpha3)
        check.api_total = api_count(year, month)
    return check


def _alpha3(country: str) -> str:
    from . import countries
    return countries.resolve(country).alpha3

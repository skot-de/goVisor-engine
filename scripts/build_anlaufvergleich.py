#!/usr/bin/env python3
"""Zweiter Anlauf gegen ersten: was die Vergabestelle geaendert hat.

    data/gold/<L>/anlauf_vergleich.parquet   eine Zeile je Kettenpaar

DIE FRAGE. Eine Ausschreibung findet keinen Bieter und wird neu eingestellt. Was hat die
Vergabestelle dabei fallen gelassen? Wert erhoeht, Frist verlaengert, Lose geteilt, Verfahrensart
gewechselt — jede dieser Aenderungen ist ein Zugestaendnis, und sie verraet, woran der erste
Anlauf gescheitert ist. Fuer einen Bieter ist das die Antwort auf „ist diese Anforderung
verhandelbar?", und sie steht in keiner Bekanntmachung, sondern nur im Vergleich zweier.

⚠ DIE DOKUMENTENSPALTEN SIND HEUTE LEER, UND DAS IST KEIN FEHLER. Der eigentliche Vergleich
waere der der Vergabeunterlagen: welche Anforderung ist im zweiten Anlauf verschwunden. Am
2026-09-15 gemessen hat KEIN einziges der 101.270 Kettenpaare Unterlagen auf beiden Seiten —
wir holen Unterlagen erst seit wenigen Wochen und nur bei laufender Frist, ein Vorgaenger liegt
aber Jahre zurueck. Die Spalten stehen trotzdem im Schema und werden in DERSELBEN Abfrage
befuellt, sobald beide Seiten Anforderungen tragen. Wer den Erbauer erneut laufen laesst,
bekommt sie ohne Codeaenderung.

  Rechnung dazu: 8,3 % aller Verfahren scheitern, 4.719 offene Verfahren sind dokumentiert,
  Wiederholungen kommen zu 11.861 Faellen noch im selben Jahr. Die ersten Paare entstehen also
  von selbst, geschaetzt rund 400 binnen zwoelf Monaten.

⚠ NICHT JEDES PAAR IST EIN GESCHEITERTER ANLAUF. Eine Kette verbindet auch den planmaessigen
Neuabschluss eines auslaufenden Rahmenvertrags. `vorher_erfolglos` trennt beides: nur dort ist
die Aenderung ein Zugestaendnis, sonst ist sie normale Fortschreibung. Beide Faelle bleiben in
der Tabelle, weil beide interessant sind — aber wer sie verwechselt, liest Absicht in Routine.

⚠ DIE KETTE IST NICHT UEBERALL GLEICH SICHER. `konfidenz` und `methode` wandern mit. Ein
maschinell entschiedenes Paar (`llm_adjudicated`) darf nicht aussehen wie ein inhaltlich
eindeutiges. Wer den Vergleich anzeigt, zeigt die Guete daneben.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor.laender import AKTIV  # noqa: E402

# Die Leitbekanntmachung eines Vorgangs: die frueheste Ausschreibung. Sie traegt Frist,
# Verfahrensart und Losstruktur; der Zuschlag traegt sie nicht, und eine Korrektur nur teilweise.
LEIT_ARTEN = ("cn", "pin")


def _laender() -> list[str]:
    return [l for l in AKTIV if (ROOT / "data" / "gold" / l / "vorgang_kette.parquet").exists()]


def _hat(land: str, *teile: str) -> bool:
    return (ROOT.joinpath("data", *teile[:-1], teile[-1])).exists() if teile else False


def baue(con: duckdb.DuckDBPyConnection, land: str) -> tuple[int, int, int]:
    g = f"data/gold/{land}"
    kette = f"read_parquet('{g}/vorgang_kette.parquet')"
    vn = f"read_parquet('{g}/vorgang_notice.parquet')"
    vg = f"read_parquet('{g}/vorgaenge.parquet')"
    silber = f"read_parquet('data/silver/{land}/notices/**/*.parquet')"

    # Optional: erst seit es sie gibt. Fehlen sie, bleiben die Spalten leer statt zu krachen.
    q_pfad = ROOT / "data" / "gold" / land / "quality.parquet"
    c_pfad = ROOT / "data" / "docs" / land / "doc_checklist.parquet"
    if not c_pfad.exists():
        c_pfad = ROOT / "data" / "gold" / land / "doc_checklist.parquet"
    status_sql = (f"(select notice_id, verfahren_status from read_parquet('{q_pfad.as_posix()}'))"
                  if q_pfad.exists() else "(select null::varchar notice_id, null::varchar verfahren_status)")
    anf_sql = (f"(select notice_id, req_type, cast(value as varchar) wert "
               f"from read_parquet('{c_pfad.as_posix()}'))"
               if c_pfad.exists() else
               "(select null::varchar notice_id, null::varchar req_type, null::varchar wert)")

    con.execute(f"""
    create or replace temp view leit as
      select vn.vorgang_id, vn.notice_id, s.publication_date, s.submission_deadline,
             s.procedure_type, s.lot_count, s.cpv_main,
             coalesce(s.final_value, s.estimated_value) wert,
             row_number() over (partition by vn.vorgang_id
                                order by s.publication_date nulls last, vn.notice_id) rn
      from {vn} vn join {silber} s using (notice_id)
      where vn.notice_kind in {LEIT_ARTEN} and coalesce(vn.dublette, false) = false
    """)
    con.execute("create or replace temp view leit1 as select * from leit where rn = 1")
    # ⚠ `verfahren_status='erfolglos'` haengt zu 100 % am ZUSCHLAG (`can`), nie an der
    # Ausschreibung — am 2026-09-15 gemessen: 68.663 von 68.663. Wer auf die Leitbekanntmachung
    # verbindet, findet null Treffer und haelt das fuer „keine gescheiterten Anlaeufe".
    # Der Status gehoert dem ganzen Vorgang, also ueber alle seine Bekanntmachungen suchen.
    con.execute(f"create or replace temp view stat_n as select * from {status_sql}")
    con.execute(f"""
    create or replace temp view stat as
      select vn.vorgang_id,
             bool_or(q.verfahren_status = 'erfolglos') erfolglos,
             bool_or(q.verfahren_status = 'vergeben') vergeben
      from {vn} vn join stat_n q using (notice_id) group by 1
    """)
    con.execute(f"create or replace temp view anf as select * from {anf_sql}")

    con.execute(f"""
    create or replace temp view paare as
      select k.land, k.kette_id, k.vorgaenger vorher_vorgang, k.vorgang_id nachher_vorgang,
             k.konfidenz_zum_vorgaenger konfidenz, k.methode, k.n_glieder
      from {kette} k where k.vorgaenger is not null
    """)

    sql = f"""
    with a as (select * from leit1), b as (select * from leit1),
    -- Anforderungen je Vorgang, nur wo es welche gibt
    anf_v as (
      select vn.vorgang_id, count(*) n, list(distinct req_type || '␟' || coalesce(wert,'')) schl
      from {vn} vn join anf using (notice_id) group by 1),
    z as (
      select p.*,
             a.notice_id vorher_notice, b.notice_id nachher_notice,
             a.publication_date vorher_pub, b.publication_date nachher_pub,
             date_diff('day', a.publication_date, a.submission_deadline) vorher_frist_tage,
             date_diff('day', b.publication_date, b.submission_deadline) nachher_frist_tage,
             a.procedure_type vorher_verfahren, b.procedure_type nachher_verfahren,
             a.lot_count vorher_lose, b.lot_count nachher_lose,
             a.cpv_main vorher_cpv, b.cpv_main nachher_cpv,
             a.wert vorher_wert, b.wert nachher_wert,
             coalesce(sa.erfolglos, false) vorher_erfolglos_roh,
             coalesce(sa.vergeben, false) vorher_vergeben,
             va.n vorher_n_anforderungen, vb.n nachher_n_anforderungen,
             va.schl vorher_schl, vb.schl nachher_schl,
             coalesce(gv.hat_unterlagen, false) vorher_unterlagen,
             coalesce(gn.hat_unterlagen, false) nachher_unterlagen
      from paare p
      left join a on a.vorgang_id = p.vorher_vorgang
      left join b on b.vorgang_id = p.nachher_vorgang
      left join stat sa on sa.vorgang_id = p.vorher_vorgang
      left join anf_v va on va.vorgang_id = p.vorher_vorgang
      left join anf_v vb on vb.vorgang_id = p.nachher_vorgang
      left join {vg} gv on gv.vorgang_id = p.vorher_vorgang
      left join {vg} gn on gn.vorgang_id = p.nachher_vorgang)
    select
      land, kette_id, vorher_vorgang, nachher_vorgang, konfidenz, methode, n_glieder,
      vorher_notice, nachher_notice, vorher_pub, nachher_pub,
      date_diff('day', vorher_pub, nachher_pub) abstand_tage,
      vorher_erfolglos_roh vorher_erfolglos, vorher_vergeben,
      -- Bekanntmachungsebene: heute schon da
      vorher_wert, nachher_wert,
      case when vorher_wert > 0 and nachher_wert is not null
           then round(nachher_wert / vorher_wert, 3) end wert_faktor,
      vorher_frist_tage, nachher_frist_tage,
      nachher_frist_tage - vorher_frist_tage frist_delta_tage,
      vorher_verfahren, nachher_verfahren,
      vorher_verfahren is distinct from nachher_verfahren verfahren_gewechselt,
      vorher_lose, nachher_lose, nachher_lose - vorher_lose lose_delta,
      vorher_cpv, nachher_cpv, vorher_cpv is distinct from nachher_cpv cpv_gewechselt,
      -- Dokumentenebene: leer, bis beide Seiten Anforderungen tragen (s. Modulkopf)
      vorher_unterlagen, nachher_unterlagen,
      (vorher_schl is not null and nachher_schl is not null) unterlagen_beide,
      vorher_n_anforderungen, nachher_n_anforderungen,
      case when vorher_schl is not null and nachher_schl is not null
           then len(list_filter(vorher_schl, x -> not list_contains(nachher_schl, x))) end anf_entfallen,
      case when vorher_schl is not null and nachher_schl is not null
           then len(list_filter(nachher_schl, x -> not list_contains(vorher_schl, x))) end anf_neu
    from z
    """
    ziel = ROOT / "data" / "gold" / land / "anlauf_vergleich.parquet"
    con.execute(f"create or replace temp view ergebnis as {sql}")
    n, erfolglos, mit_dok = con.execute(
        "select count(*), count(*) filter (where vorher_erfolglos),"
        " count(*) filter (where unterlagen_beide) from ergebnis").fetchone()
    return n, erfolglos or 0, mit_dok or 0


def schreibe(con: duckdb.DuckDBPyConnection, land: str) -> Path:
    ziel = ROOT / "data" / "gold" / land / "anlauf_vergleich.parquet"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"copy ergebnis to '{ziel.as_posix()}' (format parquet)")
    return ziel


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--land", default=None)
    p.add_argument("--probe", action="store_true",
                   help="nur rechnen und berichten, nichts nach data/ schreiben")
    a = p.parse_args()
    con = duckdb.connect()
    con.execute(f"set home_directory='{ROOT.as_posix()}'")
    for land in ([a.land] if a.land else _laender()):
        if not (ROOT / "data" / "gold" / land / "vorgang_kette.parquet").exists():
            print(f"  {land}: keine Ketten, uebersprungen")
            continue
        n, erfolglos, mit_dok = baue(con, land)
        wohin = "(Probe, nicht geschrieben)" if a.probe else str(schreibe(con, land).relative_to(ROOT))
        print(f"  {land}: {n:,} Paare · {erfolglos:,} nach erfolglosem Anlauf · "
              f"{mit_dok:,} mit Unterlagen auf beiden Seiten  {wohin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

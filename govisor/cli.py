"""Command line entry point: ``python -m govisor.cli ingest --from 2023-06``."""

from __future__ import annotations

import argparse
import collections
import sys
from datetime import date

from . import bulk, locales, review, silver, simap, verify
from .config import Config
from .ingest import ingest_month, is_done


def _month(value: str) -> tuple[int, int]:
    try:
        year, month = value.split("-")
        parsed = (int(year), int(month))
    except ValueError:
        raise argparse.ArgumentTypeError(f"Erwartet YYYY-MM, bekam {value!r}")
    if not 1 <= parsed[1] <= 12 or parsed < bulk.ARCHIVE_START:
        raise argparse.ArgumentTypeError(
            f"{value} liegt außerhalb des Archivs (ab {bulk.ARCHIVE_START[0]}-01)"
        )
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="govisor")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Monatspakete laden und filtern")
    ingest.add_argument("--from", dest="start", type=_month, required=True, metavar="YYYY-MM")
    ingest.add_argument("--to", dest="end", type=_month, metavar="YYYY-MM")
    ingest.add_argument("--country", nargs="+", default=["DE"], metavar="CODE")
    ingest.add_argument("--data-dir", default="data")
    ingest.add_argument("--force", action="store_true", help="Cache ignorieren")
    ingest.add_argument(
        "--evict", action="store_true",
        help="Paket nach der Verarbeitung löschen (spart ~25 GB bei einem Vollimport)",
    )
    ingest.add_argument(
        "--resume", action="store_true",
        help="Monate überspringen, für die schon Bronze existiert",
    )

    silver_cmd = sub.add_parser("silver", help="Bronze → Parquet (verlustfrei)")
    silver_cmd.add_argument("--country", nargs="+", default=["DE"], metavar="CODE")
    silver_cmd.add_argument("--data-dir", default="data")
    silver_cmd.add_argument("--force", action="store_true", help="vorhandene Parquet überschreiben")

    doe = sub.add_parser("ingest-doe", help="DÖE-eForms (unterschwellig) → Silber")
    doe.add_argument("--country", default="DE")
    doe.add_argument("--data-dir", default="data")
    doe.add_argument("--start", help="ab Monat YYYY-MM (Default: alle vorhandenen)")
    doe.add_argument("--force", action="store_true", help="vorhandene -doe-Parquet überschreiben")
    doe.add_argument("--fetch", action="store_true",
                     help="frische Monatspakete VORHER laden (laufender Monat wächst täglich)")
    doe.add_argument("--fetch-back", dest="fetch_back", type=int, default=1,
                     help="wie viele Vormonate mitladen (Default 1 = laufend + Vormonat)")

    sm = sub.add_parser("ingest-simap", help="simap.ch (CH, offene JSON-API) → Bronze")
    sm.add_argument("--country", default="CH")
    sm.add_argument("--data-dir", default="data")
    sm.add_argument("--max-pages", dest="max_pages", type=int, default=None,
                    help="Seiten begrenzen (je 20, neueste zuerst; Default: ganze Historie)")
    sm.add_argument("--delay", type=float, default=0.15, help="Pause je Request in s (höflich)")
    sm.add_argument("--force", action="store_true", help="Monatsfiles überschreiben statt mergen")
    sm.add_argument("--silver", action="store_true",
                    help="nach dem Download Bronze→Silber bauen (--max-pages 0 = nur Silber)")
    sm.add_argument("--gold", action="store_true",
                    help="Silber + schlanke CH-Gold-Brücke bauen (lead_export/geo/deadline)")

    av = sub.add_parser("ingest-atverg", help="OffeneVergaben.at (AT unterschwellig, CSV-Bulk) → Bronze")
    av.add_argument("--country", default="AT")
    av.add_argument("--data-dir", default="data")
    av.add_argument("--stamp", default=None, help="Datei-Stempel überschreiben (Default: heute)")
    av.add_argument("--silver", action="store_true",
                    help="nach dem Download Bronze→Silber bauen (--skip-download = nur Silber)")
    av.add_argument("--skip-download", dest="skip_download", action="store_true",
                    help="kein Download, nur aus vorhandener Bronze-ZIP Silber bauen")
    av.add_argument("--force", action="store_true", help="vorhandene Silber-Parquet überschreiben")

    rev = sub.add_parser("review", help="Zweifelsfälle zur Nachbearbeitung anzeigen")
    rev.add_argument("--data-dir", default="data")
    rev.add_argument("--csv", help="Queue als CSV exportieren")
    rev.add_argument("--limit", type=int, default=20)

    goldp = sub.add_parser("gold", help="Verfahren aus Silber ableiten")
    goldp.add_argument("--country", default="DE")
    goldp.add_argument("--data-dir", default="data")
    goldp.add_argument("--bridge", action="store_true",
                       help="schlanke Quell-Gold-Brücke statt voller Pipeline (z.B. AT: build_at_gold)")
    goldp.add_argument("--as-of", dest="as_of", default=None,
                       help="Stichtag YYYY-MM-DD für den Auslauf-Radar (Default: heute)")

    fd = sub.add_parser("fetch-docs", help="Vergabeunterlagen holen (cosinex/DTVP, login-frei)")
    fd.add_argument("--country", default="DE")
    fd.add_argument("--data-dir", default="data")
    fd.add_argument("--limit", type=int, default=None, help="nur die ersten N Vorgänge")
    fd.add_argument("--delay", type=float, default=1.5, help="Pause je Download in s (höflich)")

    ix = sub.add_parser("index-docs", help="Vergabeunterlagen-ZIPs → Volltext-Index (doc_text.parquet)")
    ix.add_argument("--country", default="DE")
    ix.add_argument("--data-dir", default="data")
    # Der Docstring von `build_index` verlangt einen Neuaufbau nach JEDER Parser-Aenderung
    # („sonst traegt der Index halb altes, halb neues Verhalten — und das faellt niemandem
    # auf"). Die Funktion konnte das immer; die CLI bot es nicht an, man musste also Python
    # schreiben. Eine Pflicht, die nur ueber einen Umweg erfuellbar ist, wird nicht erfuellt.
    ix.add_argument("--neu-aufbauen", action="store_true",
                    help="alles neu entpacken (PFLICHT nach Parser-Aenderungen)")

    sg = sub.add_parser("signals-docs", help="Volltext → strukturierte Lead-Signale (doc_signals.parquet)")
    sg.add_argument("--country", default="DE")
    sg.add_argument("--data-dir", default="data")
    # Der Schritt rechnet nur noch Neues/Geaendertes. Eine Regelaenderung erzwingt den
    # Voll-Lauf von selbst (Fingerabdruck der Regeln); dieser Schalter ist fuer den Fall,
    # dass man dem Bestand aus einem anderen Grund nicht traut.
    sg.add_argument("--neu-aufbauen", action="store_true",
                    help="alle Vorgaenge neu rechnen statt nur die geaenderten")

    srcp = sub.add_parser("sources", help="Quellen-Registry anzeigen (Connector × Land × Tier)")
    srcp.add_argument("--country", default=None, metavar="CC", help="nur Quellen dieses Landes")
    srcp.add_argument("--status", default=None, choices=("live", "prepared", "candidate", "research"),
                      help="nur Quellen dieses Status")

    check = sub.add_parser("verify", help="Vollständigkeit gegen die TED-API prüfen")
    check.add_argument("--from", dest="start", type=_month, default=(2016, 1), metavar="YYYY-MM")
    check.add_argument("--to", dest="end", type=_month, metavar="YYYY-MM")
    check.add_argument("--country", default="DE")
    check.add_argument("--data-dir", default="data")
    check.add_argument("--no-api", action="store_true", help="nur lokal lesen, nicht gegen TED prüfen")
    check.add_argument("--csv", help="Bericht als CSV schreiben")
    return parser


def cmd_ingest_doe(args) -> int:
    cfg = Config(countries=(args.country,), data_dir=args.data_dir)
    if args.country in locales.LOCALES:
        locales.use(args.country)
    # Download vor dem Parsen: der laufende Monat wächst täglich (pubMonth). Ohne diesen Schritt
    # parst der Ingest nur alte ZIPs → keine frischen Leads. `--fetch-back N` = N Vormonate dazu.
    if getattr(args, "fetch", False):
        from datetime import date
        from . import doe
        back = max(0, int(getattr(args, "fetch_back", 1) or 0))
        y, m = date.today().year, date.today().month
        for _ in range(back + 1):
            key = f"{y:04d}-{m:02d}"
            try:
                sz = doe.fetch_month(cfg, key, country=args.country, force=True)
                print(f"  ⭳ {key}: {sz/1e6:.1f} MB geladen" if sz else f"  ⭳ {key}: leer/nicht verfügbar")
            except Exception as e:  # noqa: BLE001
                print(f"  ⚠ {key}: Download fehlgeschlagen ({str(e)[:100]})")
            m -= 1
            if m == 0:
                m = 12; y -= 1
    months = silver.available_months_doe(cfg, args.country)
    if args.start:
        months = [m for m in months if m >= args.start]
    print(f"{args.country}: {len(months)} DÖE-Monate (unterschwellig)")
    total = skipped = 0
    for i, key in enumerate(months, 1):
        n = silver.build_month_doe(cfg, key, force=args.force, country=args.country)
        if n == -1:
            skipped += 1
            continue
        total += max(n, 0)
        print(f"  [{i:>3}/{len(months)}] {key}: {n:>6,} Notices", flush=True)
    dedup = silver.consolidate_doe(cfg, args.country)
    print(f"  → {total:,} Notices ins Staging, konsolidiert auf {dedup:,} (Cross-Monat-Dedup). "
          f"Jetzt `gold` rebuilden, damit die Leads einfließen.")
    return 0


def cmd_ingest_simap(args) -> int:
    cfg = Config(countries=(args.country,), data_dir=args.data_dir)
    n = simap.download(cfg, country=args.country, max_pages=args.max_pages,
                       delay=args.delay, force=args.force)
    print(f"  → {n:,} Publikationen in Bronze (raw_simap/{args.country}/).")
    if args.silver or args.gold:
        m = simap.build_silver(cfg, country=args.country, force=args.force)
        print(f"  → {m:,} Notices in Silber (schema_gen=simap).")
    if args.gold:
        k = simap.build_ch_gold(cfg, country=args.country)
        print(f"  → {k:,} CH-Leads in Gold. `scripts/export_web_leads.py` laufen lassen, "
              f"damit sie im Explorer erscheinen.")
    return 0


def cmd_ingest_atverg(args) -> int:
    from . import atverg
    cfg = Config(countries=(args.country,), data_dir=args.data_dir)
    if not args.skip_download:
        p = atverg.download(cfg, country=args.country, stamp=args.stamp)
        print(f"  → Bronze: {p}")
    if args.silver or args.skip_download:
        m = atverg.build_silver(cfg, country=args.country, force=args.force)
        print(f"  → {m:,} Notices in Silber (schema_gen=atverg). Danach `gold --country AT` "
              f"(build_at_gold zieht die atverg-cn-Leads automatisch mit).")
    return 0


def cmd_silver(args) -> int:
    cfg = Config(countries=tuple(args.country), data_dir=args.data_dir)
    for country in cfg.countries:
        if country in locales.LOCALES:
            locales.use(country)         # länderspezifisches Parsen aktivieren
        months = silver.available_months(cfg, country)
        print(f"{country}: {len(months)} Monate in Bronze")
        total = skipped = 0
        for i, key in enumerate(months, 1):
            n = silver.build_month(cfg, country, key, force=args.force)
            if n == -1:
                skipped += 1
                continue
            total += n
            print(f"  [{i:>3}/{len(months)}] {key}: {n:>6,} Notices", flush=True)
        print(f"  → {total:,} Notices geschrieben, {skipped} übersprungen")
    return 0


def cmd_review(args) -> int:
    """Alles, was nicht sauber durchlief — verworfen wie behalten.

    Zwei Quellen: verworfene Notices stehen in data/review (nur dort, denn sie
    sind in keinem Bronze-Archiv), behaltene tragen ihre Marken in Silber.
    """
    cfg = Config(data_dir=args.data_dir)
    rows = []
    for path in sorted(cfg.review_dir.glob("*.jsonl.gz")):
        month = path.name.replace(".jsonl.gz", "")
        for item in review.load(path):
            rows.append((month, item))

    kept_flagged = 0
    try:
        import duckdb
        glob = cfg.silver_table_glob("notices", "DE")
        # ⚠ `coalesce`, weil drei Connectoren `flags` als NULL schreiben statt als leere
        # Liste (atverg, simap, healyhudson — zusammen 272.501 Zeilen, gemessen
        # 2026-08-25). `len(NULL) > 0` ergibt NULL, nicht FALSE: die Zeilen fielen aus
        # der Zaehlung, und „0 Marken" las sich wie „nichts zu beanstanden" statt wie
        # „dieser Connector setzt gar keine Marken". Die Erzeuger sind mitgezogen, aber
        # der Bestand traegt die NULL bis zum naechsten Silber-Neubau.
        kept_flagged = duckdb.sql(
            f"SELECT count(*) FROM '{glob}' WHERE len(coalesce(flags, [])) > 0"
        ).fetchone()[0]
    except Exception:
        pass

    if not rows and not kept_flagged:
        print("Queue ist leer.")
        return 0
    if kept_flagged:
        print(f"{kept_flagged:,} behaltene Notices tragen Marken (in Silber, Spalte `flags`)\n")
    if not rows:
        return 0

    by_reason = collections.Counter(item.reason for _, item in rows)
    print(f"{len(rows)} Fälle zur Nachbearbeitung\n")
    for reason, count in by_reason.most_common():
        print(f"   {count:>4}  {reason}")
    codes = collections.Counter(
        c for _, item in rows for c in item.raw_country_codes
        if c not in ("DEU", "DE")
    )
    print("\nHäufigste fremde Ländercodes in diesen Dokumenten:")
    for code, count in codes.most_common(8):
        print(f"   {count:>4}  {code}")

    print(f"\nErste {min(args.limit, len(rows))} Fälle:")
    for month, item in rows[: args.limit]:
        print(f"\n  {month}  {item.notice_id}  [{item.reason}]")
        print(f"     Codes im Dokument : {item.raw_country_codes}")
        print(f"     {(item.title or '—')[:66]}")
        print(f"     {item.ted_url or '—'}")

    if args.csv:
        import csv as _csv
        with open(args.csv, "w", newline="") as fh:
            w = _csv.writer(fh)
            w.writerow(["monat", "notice_id", "publikationsnummer", "grund",
                        "laendercodes_im_dokument", "formulartyp", "titel", "ted_url"])
            for month, item in rows:
                w.writerow([month, item.notice_id, item.publication_number, item.reason,
                            " ".join(item.raw_country_codes), item.form_type,
                            item.title, item.ted_url])
        print(f"\nCSV: {args.csv}")
    return 0


def cmd_sources(args) -> int:
    """Quellen-Registry (govisor/sources.py) auflisten — Connector × Land × Tier + Kennzahlen."""
    from . import sources
    if args.country or args.status:
        rows = sources.REGISTRY
        if args.country:
            rows = [s for s in rows if s.country == args.country.upper()]
        if args.status:
            rows = [s for s in rows if s.status == args.status]
        print(f"{'Quelle':<40}{'Connector':<12}{'Land':<5}{'Tier':<15}Status")
        print("-" * 80)
        for s in rows:
            print(f"{s.name:<40}{s.connector:<12}{s.country:<5}{s.tier:<15}{s.status}")
        print(f"\n{len(rows)} Quelle(n).")
    else:
        print(sources.format_overview())
    return 0


def cmd_verify(args) -> int:
    """Jeden Monat einzeln gegen TED prüfen — Archiv lesen, Zahlen vergleichen."""
    cfg = Config(countries=(args.country,), data_dir=args.data_dir)
    country = cfg.countries[0]
    if country in locales.LOCALES:
        locales.use(country)
    today = date.today()
    end = args.end or (today.year, today.month)
    packages = list(bulk.months(args.start, end))

    print(f"{'Monat':<9} {'Bronze':>9} {'TED-API':>9} {'Delta':>8} {'':>7}  Prüfung")
    print("-" * 78)
    checks = []
    for package in packages:
        c = verify.check_month(cfg, country, package.key, with_api=not args.no_api)
        checks.append(c)
        bronze = f"{c.bronze_notices:,}" if c.bronze_notices is not None else "—"
        api = f"{c.api_country:,}" if c.api_country is not None else "—"
        delta = f"{c.delta:+,}" if c.delta is not None else "—"
        pct = f"{c.delta_pct:+.2f}%" if c.delta_pct is not None else ""
        if c.error:
            status = f"FEHLT ({c.error})" if c.error == "fehlt" else f"DEFEKT ({c.error[:30]})"
        elif c.delta is None:
            status = "gelesen, keine API-Referenz"
        elif abs(c.delta_pct or 0) < 0.5:
            status = "vollständig gelesen + gegen TED geprüft"
        else:
            status = "ABWEICHUNG — prüfen"
        print(f"{c.key:<9} {bronze:>9} {api:>9} {delta:>8} {pct:>7}  {status}", flush=True)

    have = [c for c in checks if c.bronze_notices]
    missing = [c for c in checks if not c.bronze_notices]
    bad = [c for c in have if c.delta_pct is not None and abs(c.delta_pct) >= 0.5]
    print("-" * 78)
    print(f"Monate geprüft        : {len(checks)}")
    print(f"  vollständig         : {len(have) - len(bad)}")
    print(f"  mit Abweichung      : {len(bad)}")
    print(f"  fehlend/defekt      : {len(missing)}")
    print(f"Notices Bronze        : {sum(c.bronze_notices or 0 for c in checks):,}")
    print(f"Notices laut TED-API  : {sum(c.api_country or 0 for c in checks):,}")
    if missing:
        print(f"\nFehlend: {', '.join(c.key for c in missing)}")

    # Gold-Integrität: FK-Waisen (unabhängig von der API — läuft immer).
    orphans = verify.gold_integrity(cfg, country)
    print("\nGold-Integrität (FK-Waisen, muss 0 sein):")
    if orphans:
        for label, n in orphans:
            print(f"  ✗ {label}: {n:,} Waisen")
    else:
        print("  ✓ alle Referenzen auflösbar")

    if args.csv:
        import csv as _csv
        with open(args.csv, "w", newline="") as fh:
            w = _csv.writer(fh)
            w.writerow(["monat", "bronze_notices", "ted_api_notices", "delta",
                        "delta_pct", "archiv_lesbar", "geprueft"])
            for c in checks:
                w.writerow([c.key, c.bronze_notices, c.api_country, c.delta,
                            f"{c.delta_pct:.3f}" if c.delta_pct is not None else "",
                            c.bronze_readable,
                            "Archiv komplett gelesen + TED-API" if c.delta is not None
                            else ("Archiv komplett gelesen" if c.bronze_readable else "nicht vorhanden")])
        print(f"\nCSV: {args.csv}")
    return 1 if (missing or bad or orphans) else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "silver":
        return cmd_silver(args)
    if args.command == "ingest-doe":
        return cmd_ingest_doe(args)
    if args.command == "ingest-simap":
        return cmd_ingest_simap(args)
    if args.command == "ingest-atverg":
        return cmd_ingest_atverg(args)
    if args.command == "fetch-docs":
        from . import docfetch
        cfg = Config(countries=(args.country,), data_dir=args.data_dir)
        docfetch.fetch_batch(cfg, country=args.country, limit=args.limit, delay=args.delay)
        return 0
    if args.command == "index-docs":
        from . import docpipe
        cfg = Config(countries=(args.country,), data_dir=args.data_dir)
        docpipe.build_index(cfg, country=args.country, neu_aufbauen=args.neu_aufbauen)
        return 0
    if args.command == "signals-docs":
        from . import docsignals
        cfg = Config(countries=(args.country,), data_dir=args.data_dir)
        docsignals.build_signals(cfg, country=args.country, neu_aufbauen=args.neu_aufbauen)
        return 0
    if args.command == "sources":
        return cmd_sources(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "review":
        return cmd_review(args)
    if args.command == "gold":
        from . import gold
        cfg = Config(countries=(args.country,), data_dir=args.data_dir)
        c = args.country
        if args.bridge:
            # Schlanke Brücke (nur lead_export/geo/deadline) — für Quellen, die keine volle
            # DE-getunte Pipeline rechtfertigen. AT = TED-Silber → build_at_gold.
            n = gold.build_at_gold(cfg, c)
            print(f"  → {n:,} {c}-Leads in Gold. `scripts/export_web_leads.py` laufen lassen.")
            return 0
        if c in locales.LOCALES:
            locales.use(c)               # Klassifikation/Deflator/Register aus dem Länder-Profil
        print("procedures  :", f"{gold.build_procedures(cfg, c):,}")
        print("dim_cpv     :", gold.build_dim_cpv(cfg, c))
        print("dim_cpv_label:", f"{gold.build_dim_cpv_label(cfg, c):,} CPV-Bezeichnungen")
        print("dim_deflator:", gold.build_dim_deflator(cfg, c))
        print("HR-Index laden ...", flush=True)
        hr = gold.build_hr_index()
        print(f"  {len(hr):,} Firmen")
        e, l = gold.build_entities(cfg, c, hr_index=hr)
        print(f"entities    : {e:,} Entitäten, {l:,} Verknüpfungen")
        del hr  # HR-Index (5,5 Mio) freigeben, bevor die Downstream-Builds laufen
        # Fail-Fast: entities + party_entity müssen konsistent sein. Ein Absturz
        # zwischen den beiden Schreibvorgängen (RAM) hinterlässt sonst Waisen, die
        # Leads still verlieren. Lieber hier laut abbrechen als still falsch bauen.
        pe_orphans = [n for lbl, n in verify.gold_integrity(cfg, c) if lbl.startswith("party_entity")]
        if pe_orphans:
            raise RuntimeError(f"party_entity → entities: {pe_orphans[0]:,} Waisen — "
                               "Entity-Rebuild unvollständig (build_entities erneut laufen lassen).")
        total, added = gold.seed_groups(cfg, c)
        print(f"gruppen-seed: {total:,} Firmen in CSV ({added:,} neu geseedet)")
        g, gl = gold.build_entity_groups(cfg, c)
        print(f"gruppen     : {g:,} Gruppen, {gl:,} Zuordnungen")
        print("quality     :", f"{gold.build_quality(cfg, c):,} Notices markiert")
        nq, byflag = gold.build_review_queue(cfg, c)
        print(f"review-queue: {nq:,} Notices ({byflag})")
        print("chains      :", f"{gold.build_contract_chains(cfg, c):,}")
        ns, sk = gold.build_contract_successions(cfg, c)
        print(f"successions : {ns:,} echte Ketten ({sk} Blöcke übersprungen)")
        print("leads       :", f"{gold.build_leads(cfg, c, reference_date=args.as_of):,}")
        nm, nl = gold.build_displaceability(cfg, c)
        print(f"displaceab. : Modell {nm} Zeilen, {nl:,} leads gescort")
        print("prospective :", f"{gold.build_prospective_leads(cfg, c, reference_date=args.as_of):,} F01/F02-Leads")
        print("wert-band-eff:", f"{gold.build_value_band_effektiv(cfg, c):,} Leads (Gebühren-Basis)")
        mi = gold.build_market_intelligence(cfg, c)
        print(f"markt-intel : buyer_stats {mi['buyer_stats']:,} · contractor_stats "
              f"{mi['contractor_stats']:,} · market_stats {mi['market_stats']:,} · "
              f"buyer_contractor_history {mi['buyer_contractor_history']:,}")
        print("retender-sig:", f"{gold.build_retender_signal(cfg, c):,} chronische Fehl-Bedarfe")
        print("markt-chancen:", f"{gold.build_market_opportunity(cfg, c):,} Segmente gescort")
        print("cpv-nähe    :", f"{gold.build_cpv_adjacency(cfg, c):,} Adjacency-Kanten")
        ne, nq, nn = gold.build_content_successions(cfg, c)
        print(f"nachfolge   : {ne:,} konfidente Kanten · {nq:,} LLM-Queue · {nn:,} kein Vorgänger")
        nm = gold.merge_llm_successions(cfg, c)
        print(f"nachf.-llm  : {nm:,} Kanten gesamt (inkl. LLM-adjudiziert)")
        sk = gold.build_succession_kpis(cfg, c)
        print(f"nachf.-kpis : {sk['succession_events']:,} Ereignisse · Incumbent-Retention "
              f"{100*sk['incumbent_retention']:.1f}% · head_to_head {sk['head_to_head']:,} · "
              f"contractor_loss {sk['contractor_loss']:,}")
        print("tenure      :", f"{gold.build_incumbent_tenure(cfg, c):,} Incumbents mit Historie")
        print("award-link  :", f"{gold.build_award_tender_link(cfg, c):,} Zuschlag↔Ausschreibung (Attribution)")
        print("vorgänger   :", f"{gold.build_lead_predecessor(cfg, c):,} offene Leads → Vorgänger-Zuschlag (Incumbent+Kette)")
        print("wert-anker  :", f"{gold.build_value_anchor(cfg, c):,} Zuschläge (Wert-Schätzer)")
        print("frist       :", f"{gold.build_lead_deadline(cfg, c):,} offene Ausschr. (Angebotsfrist)")
        print("laufzeit    :", f"{gold.build_lead_duration(cfg, c):,} Leads (Vertragsende, echt+geschätzt)")
        print("kalibrierung:", f"{gold.build_duration_calibration(cfg, c):,} Zeilen (Prognose-Versatz aus echten Ketten)")
        # Zweiter Laufzeit-Durchgang: der erste rechnete noch mit der Kalibrierung des
        # VORIGEN Laufs. Die Kalibrierung misst auf `contract_end` (roh, unkorrigiert),
        # also gibt es keine Rückkopplung — aber ohne diesen Durchgang trüge lead_detail
        # eine Korrektur, die einen Lauf alt ist. Kostet Sekunden, spart Erklärungen.
        print("laufzeit ²  :", f"{gold.build_lead_duration(cfg, c):,} Leads (mit frischer Kalibrierung)")
        print("lead-detail :", f"{gold.build_lead_detail(cfg, c):,} Leads (UI-View mit ehrlichen Flags)")
        print("identity    :", f"{gold.build_entity_identity(cfg, c):,} Entities (Gruppe=Identität, Winner-Match)")
        print("dim-plz     :", f"{gold.build_dim_plz(cfg, c):,} PLZ-Zentroide (Radius-Suche)")
        print("dim-nuts    :", f"{gold.build_dim_nuts(cfg, c):,} NUTS-Codes (Regions-Autocomplete)")
        print("lead-geo    :", f"{gold.build_lead_geo(cfg, c):,} Leads geokodiert (Radius-Suche)")
        print("lead-export :", f"{gold.build_lead_export(cfg, c):,} Leads (Frontend-Vertrag, Supabase-ready)")
        # Die beiden n:m-Begleittabellen zum Export — hingen bisher NICHT im Lauf und
        # wurden von Hand gebaut; damit lief das Frontend Gefahr, auf veralteten
        # Nebentabellen zu sitzen. Reihenfolge zaehlt: beide joinen auf lead_export.
        print("lead-cpv    :", f"{gold.build_lead_cpv(cfg, c):,} CPV-Zeilen (alle CPV je Lead)")
        print("lead-lot    :", f"{gold.build_lead_lot(cfg, c):,} Lose (Inhalts-Layer: 2/3 des Freitexts)")
        print("lead-text   :", f"{gold.build_lead_text(cfg, c):,} Sprachfassungen (Dokumentsprache je Lead)")
        print("lead-krit.  :", f"{gold.build_lead_criteria(cfg, c):,} Zuschlagskriterien (Preis vs. Konzept)")
        print("lead-anford.:", f"{gold.build_lead_requirement(cfg, c):,} Eignungsanforderungen (darf ich bieten?)")
        print("lead-partei :", f"{gold.build_lead_party(cfg, c):,} Beteiligte (Kontakt der Vergabestelle)")
        print("bronze-inv. :", f"{gold.build_bronze_inventory(cfg, c):,} Roh-Feldpfade (Was steckt im XML?)")
        print("doe-buyer   :", f"{gold.build_doe_buyer_profile(cfg, c):,} Käufer-Profile (Unterschwellenmarkt)")
        print("doe-demand  :", f"{gold.build_doe_demand(cfg, c):,} Nachfrage-Zellen (CPV-Div × NUTS-3 × Jahr)")
        print("buyer-profile:", f"{gold.build_buyer_profile(cfg, c):,} Vergabestellen-Profile")
        print("buyer-awards:", f"{gold.build_buyer_recent_awards(cfg, c):,} Award-Feed-Zeilen (letzte 20/Käufer)")
        print("region-kpi  :", f"{gold.build_region_kpi(cfg, c):,} Regionen (Nachfrage × Destatis-Kontext)")
        return 0
    today = date.today()
    end = args.end or min(args.start, (today.year, today.month))

    cfg = Config(countries=tuple(args.country), data_dir=args.data_dir)
    packages = list(bulk.months(args.start, end))
    print(f"Länder: {', '.join(cfg.countries)} | Pakete: {len(packages)}")

    for i, package in enumerate(packages, 1):
        if args.resume and is_done(cfg, package):
            print(f"  [{i:>3}/{len(packages)}] {package.key}: vorhanden, übersprungen", flush=True)
            continue
        try:
            stats = ingest_month(cfg, package, force=args.force, evict=args.evict)
        except Exception as exc:
            print(f"  [{i:>3}/{len(packages)}] {package.key}: FEHLER {exc}", flush=True)
            continue
        for country, s in sorted(stats.items()):
            print(
                f"  [{i:>3}/{len(packages)}] {package.key} {country}:"
                f" {s.kept:>6,}/{s.scanned:>6,} behalten | {s.lots:>6,} Lose"
                f" | Freitext {s.description_rate:5.1f}% | {s.text_chars/1e6:5.2f}M Zeichen"
                + (f" | {s.queued} zur Prüfung" if s.queued else ""),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())

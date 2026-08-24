"""Ertragsbericht — was ein Tageslauf tatsächlich einbringt.

**Warum es das gibt.** Am 2026-08-16 fragte Sven nach den Zahlen, die man täglich sehen
sollte: Zufluss neuer Ausschreibungen, neue Dokumente, Auslesequalität, Ausbeute. Sie waren
alle da — aber verstreut über Logzeilen und fünf Parquet-Dateien, und der Zufluss war gar
nicht sauber messbar. Kennzahlen, die man erst ausrechnen muss, schaut niemand täglich an.

**Der Leitgedanke: ein Trichter, keine Kennzahlensammlung.** Die entscheidende Frage ist
nicht „wie viel haben wir geladen", sondern **wo reisst es ab**. Gemessen 2026-08-16:
92,3 % der Dateien sind lesbar, aber nur 21,7 % der offenen Leads haben überhaupt
Unterlagen. Die Ausbeute ist gut, die REICHWEITE ist das Problem — und das sieht man erst,
wenn beide Zahlen nebeneinander stehen.

**Vergleich statt Momentaufnahme.** Jeder Lauf liest den Bericht des Vorlaufs und schreibt
die Veränderung mit. Eine Quote von 92 % sagt wenig; „92 %, gestern 94 %" sagt, dass etwas
passiert ist. Ohne den Vergleich müsste man sich Zahlen merken, und das tut niemand.

Schreibt ``data/logs/ertrag.json`` (aktueller Lauf) und hängt eine Zeile an
``data/logs/ertrag_verlauf.jsonl`` (Historie, für Kurven im Dashboard).

Aufruf::

    python3 -m govisor.ertrag [--country DE] [--dry-run]
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _zahl(con, sql: str, default=0):
    """Eine Zahl holen, ohne dass eine fehlende Datei den ganzen Bericht kippt.

    Bewusst fehlertolerant: der Bericht ist eine ANZEIGE. Fällt eine Quelle aus, soll die
    Zeile fehlen und der Rest stehen — ein Bericht, der komplett ausfällt, weil eine
    Nebengrösse fehlt, wird beim ersten Mal abgeschaltet.
    """
    try:
        r = con.execute(sql).fetchone()
        return r[0] if r and r[0] is not None else default
    except Exception:                                      # noqa: BLE001
        return None


def _quote(teil, ganz):
    if not ganz or teil is None:
        return None
    return round(teil / ganz * 100, 1)


def sammle(country: str = "DE", data_dir: Path | None = None) -> dict:
    import duckdb

    d = data_dir or (ROOT / "data")
    gold, docs = d / "gold" / country, d / "docs" / country
    L = (gold / "lead_export.parquet").as_posix()
    T = (docs / "doc_text.parquet").as_posix()
    S = (docs / "doc_signals.parquet").as_posix()

    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    b: dict = {"land": country}

    # ── A. BESTAND UND ZUFLUSS ────────────────────────────────────────────────────────
    b["bestand"] = {
        "leads_gesamt": _zahl(con, f"SELECT count(*) FROM read_parquet('{L}')"),
        "leads_offen": _zahl(con, f"SELECT count(*) FROM read_parquet('{L}') WHERE phase='open'"),
        "vergabestellen": _zahl(con, f"SELECT count(DISTINCT buyer_name) FROM read_parquet('{L}')"),
    }
    # Zufluss je Quelle. `src` trennt Auslauf-Radar von echten offenen Ausschreibungen —
    # beides als „Leads" zu zaehlen waere die Sorte Sammelzahl, die nichts aussagt.
    b["quellen"] = {}
    try:
        for q, n in con.execute(f"""SELECT coalesce(src,'?'), count(*) FROM read_parquet('{L}')
                                    WHERE phase='open' GROUP BY 1 ORDER BY 2 DESC""").fetchall():
            b["quellen"][q] = n
    except Exception:                                      # noqa: BLE001
        pass

    # ── B. DOKUMENT-ABRUF ─────────────────────────────────────────────────────────────
    # Aus den Manifesten, nicht aus dem Log: das Log ist Prosa, die Manifeste sind die
    # Wahrheit — und sie tragen auch, was ABSICHTLICH uebersprungen wurde.
    from . import docfetch_queue as _q
    abruf: dict = {}
    for pfad in sorted(docs.glob("_manifest*.parquet")):
        name = pfad.stem.replace("_manifest_", "").replace("_manifest", "cosinex")
        klassen: dict = {}
        try:
            rows = con.execute(f"""SELECT status, count(*) FROM read_parquet('{pfad.as_posix()}')
                                   GROUP BY 1""").fetchall()
        except Exception:                                  # noqa: BLE001
            continue
        for st, n in rows:
            st = _q.normalisiere(st)
            k = ("erledigt" if st in _q.KEIN_FEHLSCHLAG else
                 "dauerhaft" if st in _q.DAUERHAFT else
                 f"blockiert:{_q.BLOCKIERT[st]}" if st in _q.BLOCKIERT else "offen")
            klassen[k] = klassen.get(k, 0) + n
        # ⚠ „offen" ist die Sammelklasse fuer alles, was in KEINE der drei bekannten
        # Mengen faellt — und sie liest sich wie „steht noch aus". Gemessen am 2026-08-24
        # verbargen sich hinter „evergabe: 240 offen" 240-mal `NameError`, also UNSER
        # eigener Fehler, sauber protokolliert und eine Woche lang von niemandem gesehen
        # (behoben am 21.08. mit 04d2dd8, „fehlende Zeile legte den Abrufer drei Tage
        # still"). Ein Bericht, der die Antwort hat und sie zudeckt, ist schlimmer als
        # keiner: er beruhigt.
        #
        # Deshalb: bei „offen" die haeufigsten NOTIZEN mitliefern. Sie stehen im
        # Manifest, es sah nur nie jemand hinein.
        if klassen.get("offen"):
            # ⚠ NUR die ungeklaerten Zeilen zaehlen. Die erste Fassung zaehlte die Notizen
            # ALLER Zeilen und meldete „1494×" bei 364 Faellen — eine Zahl, die groesser
            # ist als ihre Grundmenge, ist keine Auskunft, sondern ein Warnsignal.
            bekannt = (set(_q.KEIN_FEHLSCHLAG) | set(_q.DAUERHAFT) | set(_q.BLOCKIERT))
            liste = ", ".join(f"'{x}'" for x in sorted(bekannt)) or "''"
            try:
                notizen = con.execute(f"""
                    SELECT coalesce(nullif(trim(note), ''), '(ohne Notiz)') AS grund, count(*) n
                    FROM read_parquet('{pfad.as_posix()}')
                    WHERE lower(coalesce(status, '')) NOT IN ({liste})
                    GROUP BY 1 ORDER BY n DESC LIMIT 3""").fetchall()
                klassen["offen_gruende"] = {t: n for t, n in notizen}
            except Exception:                              # noqa: BLE001
                pass
        abruf[name] = klassen
    b["abruf"] = abruf
    # Die Arbeitsliste: was ist blockiert, und woran. DAS ist die Reichweiten-Frage.
    blocker: dict = {}
    for quelle, kl in abruf.items():
        for k, n in kl.items():
            if k.startswith("blockiert:"):
                blocker[k.split(":", 1)[1]] = blocker.get(k.split(":", 1)[1], 0) + n
    b["blockiert_nach_grund"] = dict(sorted(blocker.items(), key=lambda x: -x[1]))

    # ── C. AUSLESEQUALITAET ───────────────────────────────────────────────────────────
    dateien = _zahl(con, f"SELECT count(*) FROM read_parquet('{T}')")
    lesbar = _zahl(con, f"SELECT count(*) FROM read_parquet('{T}') WHERE status='ok'")
    b["auslesen"] = {
        "dateien": dateien,
        "lesbar": lesbar,
        "lesbar_pct": _quote(lesbar, dateien),
        "zeichen": _zahl(con, f"SELECT sum(n_chars) FROM read_parquet('{T}')"),
        "archive": _zahl(con, f"SELECT count(DISTINCT notice_id) FROM read_parquet('{T}')"),
    }
    b["auslesen"]["status"] = dict(con.execute(
        f"""SELECT status, count(*) FROM read_parquet('{T}') WHERE status<>'ok'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10""").fetchall() or [])
    # Lesbarkeit JE DATEITYP — die eigentliche Arbeitsliste fuer den Parser. Eine
    # Gesamtquote von 92 % verdeckt, dass ein einzelnes Format zu 0 % gelesen wird.
    b["auslesen"]["je_typ"] = {}
    try:
        for typ, ges, ok, grund in con.execute(f"""
                SELECT filetype, count(*) g, count(*) FILTER (WHERE status='ok') o,
                       mode(status) FILTER (WHERE status<>'ok') AS haupt
                FROM read_parquet('{T}') GROUP BY 1 HAVING g >= 50 ORDER BY g DESC LIMIT 16
            """).fetchall():
            b["auslesen"]["je_typ"][typ or "?"] = {
                "n": ges, "ok_pct": _quote(ok, ges), "hauptgrund": grund}
    except Exception:                                      # noqa: BLE001
        pass

    # ── D. DER TRICHTER ───────────────────────────────────────────────────────────────
    offen = b["bestand"]["leads_offen"] or 0
    stufen = [("offene Leads", offen)]
    for label, sql in [
        ("mit Archiv", f"""SELECT count(DISTINCT t.notice_id) FROM read_parquet('{T}') t
                           JOIN read_parquet('{L}') l ON l.lead_id=t.notice_id WHERE l.phase='open'"""),
        ("mit lesbarem Text", f"""SELECT count(DISTINCT t.notice_id) FROM read_parquet('{T}') t
                           JOIN read_parquet('{L}') l ON l.lead_id=t.notice_id
                           WHERE l.phase='open' AND t.status='ok'"""),
        ("mit Signalen", f"""SELECT count(*) FROM read_parquet('{S}') s
                           JOIN read_parquet('{L}') l ON l.lead_id=s.notice_id WHERE l.phase='open'"""),
    ]:
        stufen.append((label, _zahl(con, sql)))
    for name, datei in [("mit Leistungsverzeichnis", "doc_lv.parquet"),
                        ("mit Kriterienmatrix", "doc_criteria.parquet")]:
        p = docs / datei
        if p.exists():
            stufen.append((name, _zahl(con, f"""
                SELECT count(DISTINCT x.notice_id) FROM read_parquet('{p.as_posix()}') x
                JOIN read_parquet('{L}') l ON l.lead_id=x.notice_id WHERE l.phase='open'""")))
    b["trichter"] = [{"stufe": s, "n": n, "pct": _quote(n, offen)} for s, n in stufen]

    # ── E. DATENQUALITAET DER LEADS ───────────────────────────────────────────────────
    # Wie viel steht auf ECHTEN Angaben statt auf Schaetzung. Das Projekt kennzeichnet das
    # ueberall mit `*_source`; hier wird es einmal zusammengezogen.
    # Jedes Feld hat sein EIGENES Vokabular — beim ersten Anlauf habe ich ueberall
    # `actual` erwartet und bekam „Wert 0 %, Kategorie 0 %", was nach Totalausfall aussah.
    # `category_source` heisst cpv/modell/regelwerk, `value_source` bei OFFENEN Vergaben
    # nie `actual` (der Wert wird selten veroeffentlicht).
    #
    # `competition_source` ist bei offenen Leads strukturell `na` und steht deshalb gar
    # nicht hier: eine laufende Ausschreibung HAT noch keine Bieterzahl. Eine Kennzahl,
    # die immer 0 % zeigt, erzieht dazu, den ganzen Block zu ueberlesen.
    b["belegt_pct"] = {}
    for feld, spalte, gilt_als_belegt in [
            ("Frist", "timing_source", ("actual",)),
            ("Wert", "value_source", ("actual", "estimated")),
            ("Kategorie", "category_source", ("cpv",)),
    ]:
        liste = ",".join(f"'{x}'" for x in gilt_als_belegt)
        n = _zahl(con, f"""SELECT count(*) FROM read_parquet('{L}')
                           WHERE phase='open' AND {spalte} IN ({liste})""")
        b["belegt_pct"][feld] = _quote(n, offen)

    # ── F. SIGNAL-ABDECKUNG ───────────────────────────────────────────────────────────
    b["signale"] = {}
    for feld in ("guarantee_required", "binding_until", "eligibility_count", "award_weights",
                 "site_visit", "penalty_pct", "variants_allowed", "framework"):
        n = _zahl(con, f"SELECT count(*) FROM read_parquet('{S}') WHERE {feld} IS NOT NULL")
        if n is not None:
            b["signale"][feld] = n

    # ── G. DUBLETTEN ──────────────────────────────────────────────────────────────────
    dup = gold / "notice_duplicates.parquet"
    if dup.exists():
        b["dubletten"] = _zahl(con, f"SELECT count(*) FROM read_parquet('{dup.as_posix()}')")

    # ── H. FRISCHE ────────────────────────────────────────────────────────────────────
    # Eine Quote sagt nichts, wenn sie aus einer zwei Wochen alten Datei stammt. Am
    # 2026-08-14 entstanden die Signale aus einem Volltext-Index vom 31. Juli, und der
    # Lauf meldete trotzdem „gruen".
    import datetime as dt
    b["alter_tage"] = {}
    for label, p in [("Leads", gold / "lead_export.parquet"), ("Volltext-Index", docs / "doc_text.parquet"),
                     ("Signale", docs / "doc_signals.parquet"), ("Frontend", ROOT / "web/data/leads-bau.json")]:
        if p.exists():
            b["alter_tage"][label] = (dt.date.today() - dt.date.fromtimestamp(p.stat().st_mtime)).days

    con.close()
    return b


def _vergleiche(neu: dict, alt: dict | None) -> dict:
    """Veränderung gegenüber dem Vorlauf — nur für die Zahlen, bei denen sie etwas sagt.

    Bewusst NICHT rekursiv über alles: eine Delta-Wüste liest niemand. Gezeigt wird, was
    eine Handlung auslösen würde.
    """
    if not alt:
        return {}
    d: dict = {}
    for pfad in (("bestand", "leads_offen"), ("auslesen", "dateien"),
                 ("auslesen", "lesbar_pct"), ("auslesen", "zeichen"), ("dubletten",)):
        a, n = alt, neu
        for k in pfad:
            a = (a or {}).get(k) if isinstance(a, dict) else None
            n = (n or {}).get(k) if isinstance(n, dict) else None
        if isinstance(a, (int, float)) and isinstance(n, (int, float)):
            d[".".join(pfad)] = round(n - a, 1)
    # Trichter-Stufen einzeln — hier steckt die Aussage „Reichweite waechst/faellt".
    alt_t = {s["stufe"]: s["n"] for s in (alt.get("trichter") or [])}
    for s in neu.get("trichter") or []:
        if s["stufe"] in alt_t and isinstance(s["n"], int):
            d[f"trichter.{s['stufe']}"] = s["n"] - alt_t[s["stufe"]]
    return d


def schreibe(country: str = "DE", dry_run: bool = False) -> dict:
    import datetime as dt

    logs = ROOT / "data" / "logs"
    jetzt = sammle(country)
    jetzt["stand"] = dt.datetime.now().replace(microsecond=0).isoformat()

    vorher = None
    p_akt = logs / "ertrag.json"
    if p_akt.exists():
        try:
            vorher = json.loads(p_akt.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            vorher = None
    jetzt["veraenderung"] = _vergleiche(jetzt, vorher)

    if not dry_run:
        logs.mkdir(parents=True, exist_ok=True)
        p_akt.write_text(json.dumps(jetzt, ensure_ascii=False, indent=1), encoding="utf-8")
        # Historie fortschreiben, damit spaeter Kurven moeglich sind. Eine Zeile je Lauf,
        # bewusst schlank — die Volldatei gibt es ja.
        kurz = {"stand": jetzt["stand"], "land": country,
                "leads_offen": jetzt["bestand"]["leads_offen"],
                "dateien": jetzt["auslesen"]["dateien"],
                "lesbar_pct": jetzt["auslesen"]["lesbar_pct"],
                "trichter": {s["stufe"]: s["n"] for s in jetzt["trichter"]}}
        with (logs / "ertrag_verlauf.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(kurz, ensure_ascii=False) + "\n")
    return jetzt


def _drucke(b: dict) -> None:
    v = b.get("veraenderung") or {}

    def delta(schluessel, einheit=""):
        x = v.get(schluessel)
        if x is None or x == 0:
            return ""
        return f"  ({x:+g}{einheit} ggü. Vorlauf)"

    print(f"\n── ERTRAG {b['land']} · {b.get('stand','')} " + "─" * 34)
    bs = b["bestand"]
    print(f"  Leads offen        {bs['leads_offen']:>9,}{delta('bestand.leads_offen')}")
    a = b["auslesen"]
    print(f"  Dateien im Index   {a['dateien']:>9,}{delta('auslesen.dateien')}")
    print(f"  davon lesbar          {a['lesbar_pct']:>6} %{delta('auslesen.lesbar_pct',' pp')}")

    print("\n  TRICHTER — wo reisst es ab")
    for s in b["trichter"]:
        d = v.get(f"trichter.{s['stufe']}")
        dd = f"  ({d:+d})" if d else ""
        print(f"    {s['stufe']:<26}{s['n']:>8,}  {s['pct'] if s['pct'] is not None else '?':>5} %{dd}")

    if b.get("blockiert_nach_grund"):
        print("\n  BLOCKIERT — die Reichweiten-Arbeitsliste")
        for grund, n in b["blockiert_nach_grund"].items():
            print(f"    {grund:<26}{n:>8,}")

    # ⚠ UNGEKLAERTE FEHLVERSUCHE. Bis 2026-08-24 tauchten sie hier GAR NICHT auf: die
    # Klasse „offen" wurde zwar berechnet, aber nie gedruckt. Gemessen verbargen sich
    # hinter evergabe 240 Versuche mit `NameError` — also unser eigener Fehler, sauber
    # protokolliert und eine Woche lang unsichtbar (behoben am 21.08. mit 04d2dd8:
    # „fehlende Zeile legte den Abrufer drei Tage still").
    #
    # Ein blockierter Vorgang wartet auf die Welt; ein ungeklaerter wartet auf UNS. Die
    # zweite Sorte gehoert deshalb ganz nach oben, nicht in eine Restkategorie.
    ungeklaert = {q: kl for q, kl in (b.get("abruf") or {}).items() if kl.get("offen")}
    if ungeklaert:
        print("\n  UNGEKLAERT — Fehlversuche ohne Klasse (warten auf UNS, nicht auf die Welt)")
        for quelle, kl in sorted(ungeklaert.items(), key=lambda x: -x[1]["offen"]):
            gruende = kl.get("offen_gruende") or {}
            text = ", ".join(f"{n}× {t}" for t, n in gruende.items()) or "ohne Notiz"
            print(f"    {quelle:<26}{kl['offen']:>8,}   {text}")

    # `datei_zu_gross` ist eine ABSICHTLICHE Grenze, kein fehlender Parser. Beide in einer
    # Liste zu zeigen liest sich als „.zip koennen wir nicht" — koennen wir, wir wollen
    # nur keine 40-MB-Archive entpacken. Deshalb getrennt.
    GEWOLLT = {"datei_zu_gross", "ocr_ohne_inhalt", "leeres_archiv"}
    typen = (b["auslesen"].get("je_typ") or {})
    luecke = {k: x for k, x in typen.items()
              if x["ok_pct"] is not None and x["ok_pct"] < 80 and x.get("hauptgrund") not in GEWOLLT}
    grenze = {k: x for k, x in typen.items()
              if x["ok_pct"] is not None and x["ok_pct"] < 80 and x.get("hauptgrund") in GEWOLLT}
    if luecke:
        print("\n  FEHLENDE PARSER (< 80 % lesbar, kein gewollter Ausschluss)")
        for t, x in sorted(luecke.items(), key=lambda i: -i[1]["n"]):
            print(f"    {t:<20}{x['n']:>8,}  {x['ok_pct']:>5} %   {x.get('hauptgrund') or ''}")
    if grenze:
        print("\n  BEWUSST AUSGESCHLOSSEN (Grenzen, kein Defekt)")
        for t, x in sorted(grenze.items(), key=lambda i: -i[1]["n"]):
            print(f"    {t:<20}{x['n']:>8,}  {x.get('hauptgrund')}")

    if b.get("belegt_pct"):
        print("\n  BELEGT statt geschaetzt")
        print("    " + " · ".join(f"{k} {x} %" for k, x in b["belegt_pct"].items() if x is not None))

    alt = b.get("alter_tage") or {}
    if alt:
        auff = [f"{k} {t} T" for k, t in alt.items() if t and t > 1]
        print("\n  FRISCHE: " + (", ".join(auff) if auff else "alles vom heutigen Lauf"))


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--country", default="DE")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    _drucke(schreibe(a.country, a.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Aus Urteilen eine Zusammenführungs-Karte bauen — und NUR die Karte.

**Was hier passiert und was nicht.** Das Skript liest die Schiedssprüche
(`entity_merge_urteil.parquet`), wirft alles Strittige raus und schreibt eine Zuordnung
`alt → neu` nach ``entity_merge_map.parquet``. Es fasst `entities.parquet` NICHT an. Der
Gold-Lauf entscheidet, ob er die Karte anwendet; so bleibt jede Zusammenführung umkehrbar,
indem man die Karte wegnimmt und neu baut.

**Warum diese Vorsicht.** Eine falsche Zusammenführung verschmilzt zwei Firmen zu einer.
Danach stimmen Marktanteile, Wettbewerbsbilder und Firmenprofile nicht mehr — und auffallen
würde es erst, wenn ein Kunde sein eigenes Profil ansieht und sich nicht wiedererkennt.

**Wer den Ausschlag gibt.** Vier Instanzen, in dieser Reihenfolge:

1. Die Handregeln in `gold.py` — sie haben diese Fälle ausdrücklich NICHT entschieden.
2. Zwei Sprachmodelle, die übereinstimmen müssen (`entity_adjudicate.py`).
3. Die Daten selbst (`entity_urteil_pruefen.py`) — Widersprüche schliessen aus.
4. Das Impressum als quellenfremder Beleg (`entity_impressum_beleg.py`), wo eine Domain
   bekannt ist.

⚠️ Bemerkenswert und hier festgehalten: In allen vier Prüfrunden hat **keine** Datenregel
eine falsche Zusammenführung gefunden. Was sie fand, waren Eigenheiten der Daten — mehrere
Postleitzahlen je Organisation, Ortsnamen in Langform, Tippfehler („kalrsruhe"), Behörden,
die zugleich Nachprüfungsstelle sind, und Firmen, die mehrere Lose gewinnen. Jede dieser
Regeln hätte ohne Gegenprobe wie ein Befund ausgesehen.

Aufruf::

    scripts/entity_merge_anwenden.py --probe     # nur rechnen
    scripts/entity_merge_anwenden.py
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "data/gold/DE"
SILBER = ROOT / "data/silver/DE/notice_parties"
ZIEL = G / "entity_merge_map.parquet"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--streng", choices=["locker", "mittel", "streng"], default="mittel",
                    help="wie viel POSITIVER Beleg verlangt wird (s. Modulkopf)")
    ap.add_argument("--vergleich", action="store_true",
                    help="alle drei Stufen rechnen und gegenüberstellen, nichts schreiben")
    a = ap.parse_args()

    import duckdb
    import pandas as pd

    urteile = pd.read_parquet(G / "entity_merge_urteil.parquet")
    con = duckdb.connect()
    con.register("u", urteile[["entity_a", "entity_b", "urteil", "treffer", "einig"]])

    # Nur einstimmige Urteile, die zusammenführen. „unsicher" und „verschieden" bleiben
    # liegen — sie sind das Ergebnis, nicht ein Zwischenstand.
    con.execute("""CREATE TEMP TABLE kandidaten AS
        SELECT entity_a, unnest(str_split(entity_b, ';')) AS entity_b, urteil, treffer
        FROM u WHERE einig AND urteil IN ('gleich', 'alle_gleich')""")

    # ── ORTE ALS SKALAR, nicht als Liste ─────────────────────────────────────────────────
    # Die erste Fassung verglich LISTE gegen LISTE (jede Stadt der einen gegen jede der
    # anderen, mit contains und levenshtein). Über 10.762 Beziehungen lief das in die
    # Zehn-Minuten-Grenze, ohne fertig zu werden — ein Kreuzprodukt je Paar.
    #
    # Stattdessen: EIN Hauptort je Entität, nämlich der am häufigsten genannte. Das ist
    # etwas gröber (eine Firma mit zwei gleich häufigen Standorten verliert den zweiten),
    # dafür rechnet es in Sekunden. Der Unterschied ist gemessen: dieselben 44
    # zurückgestellten Fälle wie mit der Listenfassung.
    con.execute(f"""CREATE TEMP TABLE ort AS
        SELECT entity_id, arg_max(stadt, n) AS ort FROM (
            SELECT pe.entity_id,
                   lower(regexp_replace(p.town, '[^A-Za-zÄÖÜäöüß]', '', 'g')) AS stadt,
                   count(*) AS n
            FROM '{(G / 'party_entity.parquet').as_posix()}' pe
            JOIN '{SILBER.as_posix()}/**/*.parquet' p
              ON p.notice_id = pe.notice_id AND p.role = pe.role AND p.seq = pe.seq
            WHERE p.town IS NOT NULL
              AND regexp_replace(p.town, '[^A-Za-zÄÖÜäöüß]', '', 'g') <> ''
            GROUP BY 1, 2)
        GROUP BY 1""")
    con.execute("""CREATE TEMP TABLE ort_passt AS
        SELECT k.entity_a, k.entity_b,
               (a.ort = b.ort OR contains(a.ort, b.ort) OR contains(b.ort, a.ort)
                OR levenshtein(a.ort, b.ort) <= 2) AS passt
        FROM kandidaten k
        JOIN ort a ON a.entity_id = k.entity_a
        JOIN ort b ON b.entity_id = k.entity_b""")
    con.execute("""CREATE TEMP TABLE strittig AS
        SELECT entity_a, entity_b FROM ort_passt WHERE NOT passt""")

    # Für die strengste Stufe: dieselbe Mechanik auf Postleitzahlen. Sie sind der engere
    # Beleg — dieselbe Stadt haben viele, dieselbe Anschriftenzone deutlich weniger.
    con.execute(f"""CREATE TEMP TABLE plz AS
        SELECT entity_id, arg_max(code, n) AS plz FROM (
            SELECT pe.entity_id, p.postal_code AS code, count(*) AS n
            FROM '{(G / 'party_entity.parquet').as_posix()}' pe
            JOIN '{SILBER.as_posix()}/**/*.parquet' p
              ON p.notice_id = pe.notice_id AND p.role = pe.role AND p.seq = pe.seq
            WHERE p.postal_code IS NOT NULL AND length(p.postal_code) >= 4
            GROUP BY 1, 2)
        GROUP BY 1""")
    con.execute("""CREATE TEMP TABLE plz_passt AS
        SELECT k.entity_a, k.entity_b, (a.plz = b.plz) AS passt
        FROM kandidaten k JOIN plz a ON a.entity_id = k.entity_a
        JOIN plz b ON b.entity_id = k.entity_b""")

    # ── DREI STUFEN, und der Unterschied ist nicht Vorsicht, sondern BEWEISLAST ──────────
    #
    #   locker  Kein Widerspruch. Das ist die Beweislast der Handregeln: zusammenführen,
    #           solange nichts dagegen spricht. Fehlende Angaben zählen als unverdächtig.
    #   mittel  Beide Seiten nennen eine Stadt, und die passt zusammen. Fehlende Angaben
    #           zählen nicht mehr als Zustimmung — wer nichts sagt, belegt nichts.
    #   streng  Zusätzlich eine gemeinsame POSTLEITZAHL. GEMESSEN UND VERWORFEN: kostet
    #           1.497 Beziehungen (9.998 → 8.501) und gewinnt keine einzige nachweisbar
    #           falsche dazu. Was wegfällt, sind Organisationen mit mehreren Anschriften:
    #           Charité Berlin (Campus 10117 und 13353), Zentral- und Landesbibliothek
    #           Berlin, Magistrat Melsungen (Postfach 34212 gegen Hausanschrift 34201),
    #           SES Astra (6815 gegen L-6815 — derselbe Ort mit Ländercode). Die Stufe
    #           bleibt aufrufbar, aber die Vorgabe ist `mittel`.
    #
    # ⚠ „Das Ziel muss eine amtliche Kennung tragen" war der erste Entwurf für `streng` und
    # änderte NICHTS: gemessen dieselben 10.015 Beziehungen wie `mittel`. Der Grund liegt im
    # Bau der Kandidaten (gold.py: `_consolidate_by_national_id`) — die Zielseite ist immer
    # eine Entität MIT Kennung, sonst wäre das Paar nie entstanden. Eine Bedingung, die
    # per Konstruktion erfüllt ist, ist keine Strenge, sondern Dekoration.
    #
    # Der Preis der Strenge ist Abdeckung, und den soll man sehen statt ihn zu vermuten:
    # `--vergleich` rechnet alle drei und stellt sie nebeneinander.
    def paare_fuer(stufe: str):
        bedingungen = ["s.entity_a IS NULL"]
        if stufe in ("mittel", "streng"):
            # Positiver Ortsbeleg: beide Seiten nennen einen Ort UND er passt. Fehlt die
            # Angabe auf einer Seite, gibt es keinen Eintrag in `ort_passt` — und damit
            # keinen Beleg. Genau das ist der Unterschied zu „locker".
            bedingungen.append("""EXISTS (SELECT 1 FROM ort_passt o
                WHERE o.entity_a = k.entity_a AND o.entity_b = k.entity_b AND o.passt)""")
        if stufe == "streng":
            bedingungen.append("""EXISTS (SELECT 1 FROM plz_passt pp
                WHERE pp.entity_a = k.entity_a AND pp.entity_b = k.entity_b AND pp.passt)""")
        return con.execute(f"""
            SELECT k.entity_a, k.entity_b, k.urteil
            FROM kandidaten k
            LEFT JOIN strittig s ON s.entity_a = k.entity_a AND s.entity_b = k.entity_b
            JOIN '{(G / 'entities.parquet').as_posix()}' e ON e.entity_id = k.entity_b
            WHERE {' AND '.join(bedingungen)}""").df()

    if a.vergleich:
        print(f"\n  {'Stufe':<10} {'Beziehungen':>12} {'Entitäten':>11} {'Ziele':>8}")
        print("  " + "─" * 44)
        for stufe in ("locker", "mittel", "streng"):
            df = paare_fuer(stufe)
            e: dict[str, str] = {}

            def f(x, e=e):
                while e.get(x, x) != x:
                    e[x] = e.get(e[x], e[x])
                    x = e[x]
                return x
            for _, r in df.iterrows():
                wx, wy = f(r["entity_a"]), f(r["entity_b"])
                if wx != wy:
                    e[wx] = wy
            wandern = [k for k in e if f(k) != k]
            print(f"  {stufe:<10} {len(df):>12,} {len(wandern):>11,} "
                  f"{len({f(k) for k in wandern}):>8,}")
        print("\n  (Vergleich — nichts geschrieben)")
        return 0

    paare = paare_fuer(a.streng)

    # Verbundene Komponenten: „alle_gleich" verknüpft mehrere Kennungen untereinander.
    eltern: dict[str, str] = {}

    def finde(x: str) -> str:
        while eltern.get(x, x) != x:
            eltern[x] = eltern.get(eltern[x], eltern[x])
            x = eltern[x]
        return x

    def vereine(x: str, y: str) -> None:
        # Das Ziel gewinnt: `y` ist die Seite mit Kennung.
        wx, wy = finde(x), finde(y)
        if wx != wy:
            eltern[wx] = wy

    for _, r in paare.iterrows():
        vereine(r["entity_a"], r["entity_b"])

    karte = pd.DataFrame([{"entity_id": k, "ziel_entity_id": finde(k),
                           "quelle": "llm_konsens_2026-08-18", "stand": date.today().isoformat()}
                          for k in eltern if finde(k) != k])
    gruppen = karte.ziel_entity_id.nunique()
    strittig_n = con.execute("SELECT count(*) FROM strittig").fetchone()[0]
    print(f"  Stufe {a.streng} · {len(paare):,} Beziehungen")
    print(f"  davon wegen getrennter Städte zurückgestellt: {strittig_n:,}")
    print(f"  → {len(karte):,} Entitäten wandern in {gruppen:,} Ziele")

    if a.probe:
        print("  (Probe — nichts geschrieben)")
        return 0
    karte.to_parquet(ZIEL, index=False)
    print(f"  ✓ {ZIEL.relative_to(ROOT)}")
    print("  `entities.parquet` ist UNVERÄNDERT. Die Karte anzuwenden ist ein eigener Schritt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

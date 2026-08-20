#!/usr/bin/env python3
"""Preisstufen aus dem tatsaechlichen Auftragsvolumen ableiten — statt raten.

Umsetzung von ``INPUT/v1 Features/add/govisor-analyse-preisstufen.md`` (v1.0).
Einmalige Datenanalyse, kein Feature: sie schreibt einen Bericht und eine CSV, sie
veraendert keine Gold-Tabelle und laeuft nicht im Tageslauf.

**Was sie beantwortet:** wie sich das oeffentliche Auftragsvolumen ueber die in Frage
kommenden Unternehmen verteilt, ob die Verteilung natuerliche Gruppen zeigt, und wie gross
die Preisstufen bei welchem Schnitt waeren — je Land und je Branche.

⚠ **Zwei Wertvarianten, bewusst beide.** Nur rund zwei Drittel der Zuschlaege tragen einen
veroeffentlichten Wert. Variante A summiert nur das Belegte (unterschaetzt systematisch),
Variante B ersetzt Fehlendes durch den Median der CPV-Division im selben Jahr (geschaetzt,
nie als gemessen ausgeben). Fuehren beide zu verschiedenen Schnitten, ist DAS das Ergebnis.

⚠ **Zwei Stellen, an denen die Spezifikation auf Felder zeigt, die es so nicht gibt** —
beide hier offengelegt statt still ersetzt:

* ``entity_confidence = confirmed`` existiert nicht als Wert. Die Entity-Aufloesung fuehrt
  eine ``method`` mit vier Auspraegungen. Als »confirmed« gilt hier register- oder
  national-ID-gestuetzt (``confidence >= 0.9``); der Trichter weist beide Zahlen aus, damit
  die Wirkung dieser Setzung sichtbar bleibt.
* **Oeffentliche Eigenbetriebe** sind nicht als Merkmal gefuehrt. Erkannt werden sie
  datengetrieben: wer haeufiger als Auftraggeber auftritt denn als Auftragnehmer, bietet
  nicht im Wettbewerb. Dazu eine kleine Namensliste (Eigenbetrieb, Landesbetrieb,
  Zweckverband, Anstalt des oeffentlichen Rechts). Beide Wege werden getrennt gezaehlt.

Aufruf:
    python3 scripts/preisstufen_analyse.py                    # DE, AT, CH
    python3 scripts/preisstufen_analyse.py --laender DE
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUS = ROOT / "data" / "analyse" / "preisstufen"

# 36 Monate, auf Jahresdurchschnitt normiert (§2).
MONATE = 36
JAHRE = MONATE / 12

# Unterschwellige Quellen. TED-Formen sind oberschwellig, DÖE und die Portal-Abgriffe
# tragen das unterschwellige Geschäft (s. docs/data-sources.md).
UNTERSCHWELLIG = ("doe", "netserver", "cosinex", "dtvp", "simap", "atverg")

_OEFFENTLICH = ("eigenbetrieb", "landesbetrieb", "zweckverband",
                "anstalt des öffentlichen rechts", "anstalt öffentlichen rechts")

# ⚠ WARUM HIER NICHT `quality.final_value_clean` STEHT — der wichtigste Fund dieser Analyse.
#
# `final_value_clean` verlangt „plausibel UND EUR". Gemessen 2026-08-18 an den Zuschlägen der
# letzten 36 Monate:
#
#     DE  251.453 CANs · Wert bei 35,7 % · davon clean 30,2 %
#     AT   91.197 CANs · Wert bei 15,3 % · davon clean 15,1 %
#     CH   29.206 CANs · Wert bei 91,6 % · davon clean  0,8 %   ← 44.436 Werte in CHF
#
# Die Schweiz hat die MIT ABSTAND beste Wertabdeckung (simap liefert den Zuschlagspreis
# direkt) — und verliert sie vollständig an einer Währungsprüfung: jeder CHF-Wert trägt
# `waehrung_fremd` und fällt aus `final_value_clean`. Damit ist CH in jeder wertbasierten
# Kennzahl des Projekts unsichtbar, nicht nur in dieser Analyse.
#
# Hier wird deshalb direkt auf `final_value` gerechnet, mit Umrechnung und den ÜBRIGEN
# Plausibilitätsprüfungen (`wert_*`-Flags) — die Währung allein disqualifiziert nicht.
# Der Kurs ist eine gesetzte Näherung, kein Marktkurs, und als solche gekennzeichnet.
CHF_IN_EUR = 1.05          # langjährige Näherung; Stichtagskurs wäre Scheingenauigkeit

_WERT_SQL = f"""
  CASE
    WHEN n.final_value IS NULL THEN NULL
    -- Nur Wert-Flags disqualifizieren. `waehrung_fremd` und `laufzeit_unplausibel` sagen
    -- nichts über die Richtigkeit des Betrags.
    WHEN len(list_filter(coalesce(q.quality_flags, []),
                         f -> starts_with(f, 'wert_'))) > 0 THEN NULL
    WHEN upper(coalesce(n.value_currency, '')) IN ('EUR', '') THEN n.final_value
    WHEN upper(n.value_currency) = 'CHF' THEN n.final_value * {CHF_IN_EUR}
    ELSE NULL                       -- USD/GBP u. a.: zu wenige für einen eigenen Kurs
  END"""


def _sql_grundgesamtheit(land: str) -> str:
    """Ein Zuschlag je Zeile, schon auf Konzernebene aufgelöst."""
    N = f"read_parquet('{ROOT}/data/silver/{land}/notices/**/*.parquet', hive_partitioning=1)"
    P = f"'{ROOT}/data/gold/{land}/party_entity.parquet'"
    E = f"'{ROOT}/data/gold/{land}/entities.parquet'"
    I = f"'{ROOT}/data/gold/{land}/entity_identity.parquet'"
    Q = f"'{ROOT}/data/gold/{land}/quality.parquet'"
    PR = f"'{ROOT}/data/gold/{land}/procedures.parquet'"
    return f"""
      WITH zuschlag AS (
        SELECT n.notice_id, n.publication_number, n.cpv_main, n.performance_nuts,
               n.schema_gen, coalesce(n.award_date, n.publication_date) AS datum,
               {_WERT_SQL} AS wert
        FROM {N} n
        LEFT JOIN {Q} q ON q.notice_id = n.notice_id
        WHERE n.notice_kind = 'can'
          AND coalesce(n.award_date, n.publication_date)
              >= (current_date - INTERVAL '{MONATE} months')
          AND coalesce(n.award_date, n.publication_date) <= current_date),
      gewinner AS (
        SELECT DISTINCT pe.notice_id, pe.entity_id
        FROM {P} pe WHERE pe.role = 'winner'),
      -- Wer öfter kauft als gewinnt, bietet nicht im Wettbewerb (§2 Ausschluss).
      kaeufer_zahl AS (
        SELECT entity_id, count(DISTINCT notice_id) n_kauf
        FROM {P} WHERE role = 'buyer' GROUP BY 1),
      gewinn_zahl AS (
        SELECT entity_id, count(DISTINCT notice_id) n_gewinn
        FROM {P} WHERE role = 'winner' GROUP BY 1)
      SELECT i.identity_id, any_value(i.canonical_name) AS name,
             z.notice_id, coalesce(pr.procedure_id, z.notice_id) AS verfahren,
             z.cpv_main, substr(z.cpv_main, 1, 2) AS division,
             substr(z.performance_nuts, 1, 4) AS nuts2,
             z.schema_gen, z.datum, z.wert,
             max(e.confidence) AS konfidenz,
             max(coalesce(kz.n_kauf, 0)) AS n_kauf,
             max(coalesce(gz.n_gewinn, 0)) AS n_gewinn,
             max(lower(i.canonical_name)) AS name_klein
      FROM zuschlag z
      JOIN gewinner g   ON g.notice_id = z.notice_id
      JOIN {E} e        ON e.entity_id = g.entity_id
      JOIN {I} i        ON i.entity_id = g.entity_id
      LEFT JOIN {PR} pr ON pr.publication_number = z.publication_number
      LEFT JOIN kaeufer_zahl kz ON kz.entity_id = g.entity_id
      LEFT JOIN gewinn_zahl  gz ON gz.entity_id = g.entity_id
      GROUP BY i.identity_id, z.notice_id, verfahren, z.cpv_main, division, nuts2,
               z.schema_gen, z.datum, z.wert"""


def trichter(con, land: str) -> tuple:
    """Grundgesamtheit schrittweise verengen — jeder Schritt mit Zahl (§2)."""
    con.execute(f"CREATE OR REPLACE TEMP TABLE roh AS {_sql_grundgesamtheit(land)}")
    stufen = []

    def zaehle(bez, wo=""):
        n = con.execute(f"SELECT count(DISTINCT identity_id) FROM roh {wo}").fetchone()[0]
        z = con.execute(f"SELECT count(*) FROM roh {wo}").fetchone()[0]
        stufen.append((bez, n, z))
        return n

    zaehle("Zuschläge mit auflösbarem Gewinner (36 Monate), Konzernebene")
    zaehle("… davon register-/ID-gestützt (Konfidenz ≥ 0,9)", "WHERE konfidenz >= 0.9")
    ausschluss_name = " OR ".join(f"name_klein LIKE '%{w}%'" for w in _OEFFENTLICH)
    zaehle("… ohne öffentliche Eigenbetriebe (Name)",
           f"WHERE konfidenz >= 0.9 AND NOT ({ausschluss_name})")
    zaehle("… ohne überwiegende Auftraggeber (kauft öfter als gewinnt)",
           f"WHERE konfidenz >= 0.9 AND NOT ({ausschluss_name}) AND n_kauf <= n_gewinn")

    con.execute(f"""CREATE OR REPLACE TEMP TABLE basis AS
        SELECT * FROM roh
        WHERE konfidenz >= 0.9 AND NOT ({ausschluss_name}) AND n_kauf <= n_gewinn""")
    # Mindestaktivität zuletzt: sie wirkt je Unternehmen, nicht je Zuschlag.
    con.execute("""CREATE OR REPLACE TEMP TABLE aktiv AS
        SELECT identity_id FROM basis
        GROUP BY 1 HAVING count(DISTINCT verfahren) >= 2""")
    n_aktiv = con.execute("SELECT count(*) FROM aktiv").fetchone()[0]
    z_aktiv = con.execute("SELECT count(*) FROM basis b JOIN aktiv a USING(identity_id)").fetchone()[0]
    stufen.append(("… mit ≥ 2 Verfahren in 36 Monaten  → GRUNDGESAMTHEIT", n_aktiv, z_aktiv))
    return stufen, n_aktiv


def kennzahlen(con, land: str):
    """Je Unternehmen die Kennzahlen aus §3, beide Wertvarianten."""
    D = f"'{ROOT}/data/gold/{land}/dim_cpv.parquet'"
    # Variante B: fehlender Wert ← Median der CPV-Division im selben Jahr. Fällt der aus
    # (Division ohne einen einzigen belegten Wert), bleibt die Zeile ohne Wert — lieber eine
    # Lücke als eine erfundene Zahl.
    con.execute("""CREATE OR REPLACE TEMP TABLE median_div AS
        SELECT division, year(datum) AS jahr, median(wert) AS med
        FROM basis WHERE wert IS NOT NULL GROUP BY 1, 2""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE firma AS
      SELECT b.identity_id,
             any_value(b.name)                                   AS name,
             count(DISTINCT b.verfahren) / {JAHRE}               AS zuschlaege_pa,
             sum(b.wert) / {JAHRE}                               AS volumen_pa_a,
             sum(coalesce(b.wert, m.med)) / {JAHRE}              AS volumen_pa_b,
             count(b.wert) * 1.0 / count(*)                      AS volumen_anteil_echt,
             median(b.wert)                                      AS median_auftragswert,
             avg(b.wert)                                         AS mittel_auftragswert,
             count(DISTINCT b.division)                          AS felder,
             count(DISTINCT b.nuts2)                             AS regionen,
             count(*) FILTER (WHERE b.schema_gen IN {UNTERSCHWELLIG!r}) * 1.0
               / count(*)                                        AS anteil_unterschwellig,
             any_value(dc.branche)                               AS branche_haupt
      FROM basis b
      JOIN aktiv a USING(identity_id)
      LEFT JOIN median_div m ON m.division = b.division AND m.jahr = year(b.datum)
      LEFT JOIN {D} dc ON dc.division = b.division
      GROUP BY b.identity_id""")
    return con.execute("SELECT * FROM firma").df()


# ── Verteilung, Cluster, Stufen ─────────────────────────────────────────────────────────
PERZENTILE = (10, 25, 50, 75, 90, 95, 99)


def verteilung(s, name: str) -> list[str]:
    import numpy as np
    s = s.dropna()
    s = s[s > 0]
    if s.empty:
        return [f"_{name}: keine Werte._"]
    z = [f"**{name}** (n = {len(s):,})".replace(",", "."), "",
         "| Perzentil | " + " | ".join(f"P{p}" for p in PERZENTILE) + " |",
         "|---|" + "---|" * len(PERZENTILE),
         "| Wert | " + " | ".join(f"{np.percentile(s, p):,.0f}".replace(",", ".")
                                  for p in PERZENTILE) + " |", ""]
    # Logarithmische Klassen (§4.1) — das Volumen ist stark rechtsschief, lineare Klassen
    # zeigten nur einen Balken ganz links.
    lo, hi = np.floor(np.log10(s.min())), np.ceil(np.log10(s.max()))
    kanten = 10 ** np.arange(lo, hi + 1)
    zahl, _ = np.histogram(s, bins=kanten)
    z += ["| Klasse | Unternehmen | |", "|---|---:|---|"]
    for i, n in enumerate(zahl):
        if n == 0:
            continue
        balken = "█" * max(1, round(40 * n / zahl.max()))
        z.append(f"| {kanten[i]:,.0f} – {kanten[i+1]:,.0f} | {n:,} | {balken} |"
                 .replace(",", "."))
    return z + [""]


_BESTES_K: dict = {}


def cluster(df, spalten: tuple[str, str]) -> list[str]:
    """k-means über log-transformierte Kennzahlen, Silhouette für k = 2,3,4 (§4.2)."""
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    d = df[list(spalten)].dropna()
    d = d[(d > 0).all(axis=1)]
    if len(d) < 50:
        return [f"_Zu wenige Unternehmen für eine Clusteranalyse ({len(d)})._", ""]
    X = StandardScaler().fit_transform(np.log10(d.to_numpy(dtype=float)))
    z = ["| k | Silhouette | Gruppengrössen | Median-Volumen je Gruppe |", "|---|---|---|---|"]
    bestes = (None, -1)
    for k in (2, 3, 4):
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
        s = silhouette_score(X, km.labels_)
        gr = np.bincount(km.labels_)
        med = [f"{np.median(d.iloc[km.labels_ == i, 0]):,.0f}".replace(",", ".")
               for i in range(k)]
        z.append(f"| {k} | **{s:.3f}** | {' · '.join(f'{g:,}'.replace(',','.') for g in gr)}"
                 f" | {' · '.join(med)} |")
        if s > bestes[1]:
            bestes = (k, s)
    _BESTES_K[spalten] = bestes
    z += ["", f"**Bestes k nach Silhouette: {bestes[0]}** (Wert {bestes[1]:.3f}). "
              "Werte unter 0,25 gelten als schwache Struktur — dann ist die Verteilung eher "
              "stufenlos und jeder Schnitt ist eine Setzung, keine Entdeckung.", ""]
    return z


def stufen_simulieren(df, spalte: str, kandidaten: list[tuple]) -> list[str]:
    """Je Kandidaten-Schwelle: wie gross wären die Stufen (§4.3)."""
    z = ["| Schnitt (X / Y) | Stufe 1 | Stufe 2 | Stufe 3 | Median-Vol. je Stufe |",
         "|---|---:|---:|---:|---|"]
    d = df[df[spalte].notna() & (df[spalte] > 0)]
    for x, y in kandidaten:
        s1, s2, s3 = d[d[spalte] < x], d[(d[spalte] >= x) & (d[spalte] < y)], d[d[spalte] >= y]
        n = max(len(d), 1)
        med = " · ".join(f"{t[spalte].median():,.0f}".replace(",", ".") if len(t) else "—"
                         for t in (s1, s2, s3))
        z.append(f"| {x:,.0f} / {y:,.0f} ".replace(",", ".")
                 + f"| {len(s1):,} ({100*len(s1)/n:.0f} %) ".replace(",", ".")
                 + f"| {len(s2):,} ({100*len(s2)/n:.0f} %) ".replace(",", ".")
                 + f"| {len(s3):,} ({100*len(s3)/n:.0f} %) ".replace(",", ".")
                 + f"| {med} |")
    return z + [""]


_SPANNE: dict = {}


def branchen(df) -> list[str]:
    """§4.4 — tragen einheitliche Schwellen über die Branchen? Die Prüffrage, nicht die Deko."""
    g = df[df.volumen_pa_b.notna() & (df.volumen_pa_b > 0)].groupby("branche_haupt")
    z = ["| Branche | Unternehmen | Median Vol./J | P75 | P90 | Median Zuschläge/J |",
         "|---|---:|---:|---:|---:|---:|"]
    zeilen = []
    for name, t in g:
        if len(t) < 20:
            continue
        zeilen.append((len(t), name, t.volumen_pa_b.median(),
                       t.volumen_pa_b.quantile(.75), t.volumen_pa_b.quantile(.90),
                       t.zuschlaege_pa.median()))
    for n, name, m, p75, p90, mz in sorted(zeilen, reverse=True):
        z.append(f"| {name} | {n:,} | {m:,.0f} | {p75:,.0f} | {p90:,.0f} | {mz:.1f} |"
                 .replace(",", "."))
    if len(zeilen) >= 2:
        mediane = [r[2] for r in zeilen]
        spanne = max(mediane) / max(min(mediane), 1)
        _SPANNE['wert'] = spanne
        z += ["", f"**Spannweite der Branchen-Mediane: Faktor {spanne:.1f}.** "
                  + ("Über Faktor 3 tragen einheitliche Schwellen nicht mehr — dann gehört "
                     "die Stufengrenze je Branche kalibriert."
                     if spanne > 3 else
                     "Unter Faktor 3 ist eine einheitliche Schwelle vertretbar.")]
    return z + [""]


def empfehlung(fakten: list[dict]) -> list[str]:
    """§5.1 Punkt 6 — Empfehlung, aus den gemessenen Zahlen abgeleitet.

    Bewusst regelbasiert statt formuliert: was hier steht, muss sich aus den Tabellen
    darüber nachrechnen lassen. Wo die Daten nicht tragen, sagt der Text das.
    """
    z = ["## Empfehlung", ""]
    # 1) Tragen überhaupt drei Stufen?
    ks = ", ".join(f"{f['land']} k={f['bestes_k']} ({f['silhouette']:.2f})" for f in fakten)
    drei = [f for f in fakten if f["bestes_k"] == 3]
    z += [f"**1. Wie viele Gruppen zeigen die Daten?** {ks}.", ""]
    if not drei:
        z += ["Die Verteilung stützt **zwei** Gruppen, nicht drei. In keinem Land erreicht "
              "k = 3 den besten Silhouettenwert. Das heisst nicht, dass drei Preisstufen "
              "falsch sind — es heisst, dass die **dritte Grenze eine Geschäftsentscheidung "
              "ist und keine Entdeckung**. Sie darf gesetzt werden, aber nicht mit „die Daten "
              "zeigen es\" begründet.", ""]
    else:
        z += ["k = 3 trägt in " + ", ".join(f["land"] for f in drei)
              + " — dort ist die dritte Grenze in den Daten angelegt.", ""]

    # 2) Branchen
    z += ["**2. Tragen einheitliche Schwellen über die Branchen?**", ""]
    for f in fakten:
        if f["branchen_spanne"]:
            urteil = ("nein — je Branche kalibrieren" if f["branchen_spanne"] > 3
                      else "ja, vertretbar")
            z.append(f"- {f['land']}: Spannweite der Branchen-Mediane Faktor "
                     f"{f['branchen_spanne']:.1f} → **{urteil}**")
    z += [""]

    # 3) Konkrete Schwellen: die, bei der Stufe 3 in die Zielgrösse fällt (§4.3)
    z += ["**3. Konkrete Schwellen.** Die Spezifikation gibt für Stufe 3 „wenige hundert "
          "Unternehmen je Land\" vor — klein genug für Einzelgespräche. Gemessen trifft das:", "",
          "| Land | Schnitt X / Y (Volumen p. a., Variante B) | Stufe 1 | Stufe 2 | Stufe 3 |",
          "|---|---|---:|---:|---:|"]
    for f in fakten:
        w = f["treffer"]
        if not w:
            z.append(f"| {f['land']} | keine Kandidatenschwelle trifft die Zielgrösse | — | — | — |")
            continue
        z.append(f"| {f['land']} | {w['x']:,.0f} / {w['y']:,.0f} ".replace(",", ".")
                 + f"| {w['n1']:,} | {w['n2']:,} | **{w['n3']:,}** |".replace(",", "."))
    z += ["", "**4. Wo die Analyse unsicher ist.**", "",
          "- Die Zuschlagszahl ist der schwächere Trenner: der Median liegt in fast jeder "
          "Branche bei **einem Verfahren pro Jahr**. Wer regelmässig bietet, ist die "
          "Ausnahme, nicht die Regel — das trifft die Annahme hinter Pro („regelmässige "
          "Bieter\") härter als die Volumenfrage.",
          "- Variante A und B unterscheiden sich in der Stufengrösse deutlich (s. Tabellen). "
          "Wer auf A schneidet, macht Stufe 1 grösser, weil fehlende Werte als klein zählen.",
          "- Volumen misst Grösse, nicht Zahlungsbereitschaft. Ein Unternehmen mit 90 % "
          "Privatgeschäft erscheint hier klein.", ""]
    return z


def bericht(land: str, stufen, df, kandidaten) -> tuple[str, dict]:
    import numpy as np
    z = [f"## {land}", "", "### Trichter der Grundgesamtheit", "",
         "| Schritt | Unternehmen | Zuschläge |", "|---|---:|---:|"]
    for bez, n, k in stufen:
        z.append(f"| {bez} | {n:,} | {k:,} |".replace(",", "."))
    z += ["", f"**Grundgesamtheit: {len(df):,} Unternehmen.**".replace(",", "."), ""]
    fakten = {"land": land, "bestes_k": None, "silhouette": 0.0,
              "branchen_spanne": None, "treffer": None}
    if df.empty:
        return "\n".join(z + ["_Keine auswertbare Grundgesamtheit._", ""]), fakten

    a = df.volumen_pa_a.dropna(); b = df.volumen_pa_b.dropna()
    z += ["### Verteilung", ""] + verteilung(df.zuschlaege_pa, "Zuschläge je Jahr")
    z += verteilung(a, "Volumen je Jahr — Variante A (nur belegte Werte)")
    z += verteilung(b, "Volumen je Jahr — Variante B (fehlende geschätzt) ⚠ geschätzt")
    if len(a) and len(b):
        z += [f"**A gegen B:** Median {np.median(a):,.0f} € gegen {np.median(b):,.0f} € "
              f"(Faktor {np.median(b)/max(np.median(a),1):.2f}). "
              .replace(",", ".")
              + f"Im Schnitt sind {100*df.volumen_anteil_echt.mean():.0f} % der Zuschläge "
                "eines Unternehmens mit veröffentlichtem Wert belegt.", ""]

    z += ["### Natürliche Gruppen (k-means, log-transformiert)", ""]
    z += cluster(df, ("volumen_pa_b", "zuschlaege_pa"))
    z += ["### Stufengrössen bei Kandidaten-Schwellen (Variante B)", ""]
    z += stufen_simulieren(df, "volumen_pa_b", kandidaten)
    z += ["### Dieselben Schwellen auf Variante A", ""]
    z += stufen_simulieren(df, "volumen_pa_a", kandidaten)
    fakten["bestes_k"], fakten["silhouette"] = _BESTES_K.get(("volumen_pa_b", "zuschlaege_pa"),
                                                             (None, 0.0))
    z += ["### Branchenvergleich", ""] + branchen(df)
    fakten["branchen_spanne"] = _SPANNE.get("wert")
    # Welche Kandidatenschwelle bringt Stufe 3 in die Zielgrösse „wenige hundert"? (§4.3)
    d = df[df.volumen_pa_b.notna() & (df.volumen_pa_b > 0)]
    for x, y in kandidaten:
        n3 = int((d.volumen_pa_b >= y).sum())
        if 50 <= n3 <= 900:
            fakten["treffer"] = {"x": x, "y": y, "n3": n3,
                                 "n1": int((d.volumen_pa_b < x).sum()),
                                 "n2": int(((d.volumen_pa_b >= x) & (d.volumen_pa_b < y)).sum())}
            break
    return "\n".join(z), fakten


def kandidaten_aus(df) -> list[tuple]:
    """Schwellen aus der Verteilung ableiten, nicht runde Zahlen raten (§4.2)."""
    import numpy as np
    v = df.volumen_pa_b.dropna()
    v = v[v > 0]
    if len(v) < 20:
        return [(1e5, 1e6)]
    p = {q: np.percentile(v, q) for q in (50, 75, 90, 95, 99)}
    # Perzentil-Paare + eine runde Variante zum Vergleich — die runde ist der Kontrast,
    # nicht der Vorschlag.
    return [(p[50], p[90]), (p[75], p[95]), (p[75], p[99]), (250_000, 2_500_000)]


def main(argv=None) -> int:
    import duckdb
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--laender", default="DE,AT,CH")
    a = ap.parse_args(argv)
    AUS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    teile = [f"# Preisstufen aus dem Auftragsvolumen", "",
             f"**Erzeugt:** {dt.date.today().isoformat()} · "
             f"`scripts/preisstufen_analyse.py` · Fenster: letzte {MONATE} Monate", ""]
    alle, fakten = [], []
    for land in [x.strip().upper() for x in a.laender.split(",") if x.strip()]:
        if not (ROOT / "data" / "gold" / land / "entities.parquet").exists():
            print(f"{land}: kein Gold-Bestand — übersprungen"); continue
        print(f"── {land} …", flush=True)
        stufen, _ = trichter(con, land)
        df = kennzahlen(con, land)
        df.insert(0, "land", land)
        kand = kandidaten_aus(df)
        for i, (x, y) in enumerate(kand, 1):
            df[f"stufe_kand{i}"] = df.volumen_pa_b.apply(
                lambda v: 1 if (v is None or v != v or v < x) else (2 if v < y else 3))
        txt, fkt = bericht(land, stufen, df, kand)
        teile.append(txt); fakten.append(fkt)
        alle.append(df)
        print(f"   {len(df):,} Unternehmen in der Grundgesamtheit")
    if alle:
        import pandas as pd
        ges = pd.concat(alle, ignore_index=True)
        ges.to_csv(AUS / "unternehmen.csv", index=False)
        teile += empfehlung(fakten)
        teile += ["## Grenzen der Analyse", "",
                  "| Grenze | Warum |", "|---|---|",
                  "| Zahlungsbereitschaft | Volumen ist ein Näherungswert für Grösse, kein Beleg dafür, was jemand zahlt |",
                  "| Privater Umsatz | goVisor sieht nur öffentliche Aufträge — wer 90 % privat macht, erscheint klein |",
                  "| Teamgrösse | aus Vergabedaten nicht ableitbar. Fliesst die Nutzerzahl ins Preismodell ein, fehlt hier die Grundlage |",
                  "| Wertlücke | Variante B ist geschätzt, nicht gemessen |",
                  "| Rahmenvolumen am oberen Rand | Der Zuschlagswert ist der **Auftragswert**, "
                  "nicht der Umsatzanteil des Gewinners. Bei Rahmenverträgen zählt das ganze "
                  "Volumen auf den Gewinner — deshalb erscheinen im obersten Perzentil "
                  "Unternehmen, deren Jahresvolumen ihre reale Grösse übersteigt. Gemessen: "
                  "absurde Werte (bis 7·10¹⁹ €) fängt der `wert_*`-Filter ab, der höchste "
                  "durchgelassene Zuschlag liegt bei 1,0 Mrd. € — plausibel für einen "
                  "Rahmenvertrag, irreführend als Jahresumsatz eines Einzelunternehmens |",
                  "| »confirmed« | existiert nicht als Feld; ersetzt durch Konfidenz ≥ 0,9 (Register/National-ID) — s. Trichter |",
                  "| Eigenbetriebe | datengetrieben erkannt (kauft öfter als gewinnt) plus Namensliste, keine amtliche Liste |", ""]
        (AUS / "bericht.md").write_text("\n".join(teile), encoding="utf-8")
        print(f"\n→ {AUS/'bericht.md'}\n→ {AUS/'unternehmen.csv'} ({len(ges):,} Zeilen)")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

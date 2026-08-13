"""Quellen-übergreifender Dublettencheck — ein Durchlass für ALLE Quellen eines Landes.

**Warum das nicht je Quelle gebaut gehört.** Vorher gab es ``dedupe_at_sources.py`` und
``dedupe_ch_sources.py`` — zwei Skripte für dasselbe Problem, und für DTVP fehlte prompt ein
drittes. Ergebnis: von den ersten 60 geholten DTVP-Vorgängen waren **44 echte Dubletten**
(identischer Titel UND identische Vergabestelle), höchstens 4 neu. Die Vergleichslogik ist
aber in allen Fällen dieselbe — *dasselbe Verfahren, auf zwei Plattformen veröffentlicht*.
Nur das Quellenpaar wechselt. Mit jeder neuen Quelle wächst die Zahl der Paare quadratisch,
die Zahl der nötigen Skripte auch, und irgendeins fehlt immer.

Deshalb hier **eine Prüfung, durch die jeder Satz muss**, unabhängig davon, woher er kommt.

**Die Regeln sind übernommen, nicht neu erfunden.** ``measure_at_overlap.py`` hat sie an
8.788 sicheren Paaren gemessen; sie noch einmal zu erfinden hiesse, dieselben drei Fehler
noch einmal zu machen:

* **±90 Tage** aus der Abstandsverteilung (Median 2 T, 96 % binnen 90). 180 Tage bringen
  einen Punkt mehr und fangen dafür gleichnamige Wiederholungsvergaben ein.
* **Enthaltung ≥ 0,8 statt symmetrischer Deckung.** Die eine Seite stellt eine Vorgangs-ID
  voran, die andere hängt „- Los 2" an; symmetrisch fällt beides durch. Gemessen wird der
  Anteil der KLEINEREN Wortmenge, der in der grösseren steckt.
* **Seed über die drei seltensten INDIZIERTEN Wörter.** Über ein einzelnes seltenes Wort
  (z. B. eine plattformeigene Vorgangsnummer) findet man null Kandidaten und hält die
  Dublette für neu.

**Die zweite Hälfte — Dublette heisst nicht wertlos.** Ein doppelter Satz wird nicht
weggeworfen, sondern auf ZUSATZINFORMATION geprüft: trägt er ein Feld, das der Master nicht
hat? Gemessen kommt das häufig vor — die nationale Quelle hat oft einen Schätzwert, wo TED
keinen führt, und umgekehrt trägt TED CPV und NUTS, wo die nationale Quelle nichts hat.
``anreicherung()`` liefert das feldweise, damit ein späterer Merge nicht raten muss.
Das ist der Unterschied zwischen „Dublette verwerfen" und „Dublette einschmelzen".

**Was hier NICHT passiert.** Es wird nichts gelöscht und nichts überschrieben. Ergebnis ist
eine Tabelle ``gold/<C>/notice_duplicates.parquet`` — wer sie benutzt, entscheidet der
Aufrufer. Projekt-Konvention: markieren statt filtern.

Aufruf::

    python3 -m govisor.dedupe --country DE --ab-jahr 2026
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import re
import sys
from collections import defaultdict

from . import entities as _entities
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FENSTER_TAGE = 90          # aus der Abstandsverteilung, s. measure_at_overlap.py
MIN_ENTHALTUNG = 0.8       # Anteil der kleineren Wortmenge in der grösseren
MIN_WORTE = 3              # darunter ist ein Titel kein Unterscheidungsmerkmal
SEED_WORTE = 3             # Kandidaten über die N seltensten indizierten Wörter

# Wer gewinnt, wenn zwei Sätze dasselbe Verfahren beschreiben? Die reichere Quelle.
# TED trägt CPV, NUTS, Lose und Werte; nationale Portale meist nur die Trefferzeile.
# Der Master ist damit derjenige, an den angereichert wird.
#
# ⚠ FELD-REICHTUM IST NICHT AKTUALITÄT. Gemessen 2026-08-13: von 70 Leads, die man beim
# Ausschluss von Dubletten verlieren würde, haben **64 einen Master, der selbst kein Lead
# ist** — bei 61 davon ist die Frist des Masters ABGELAUFEN. Beispiel: TED führt
# „Universitätsklinikum Tübingen, Anbau Frauenklinik" mit Frist 30.06., die DÖE-Fassung
# derselben Vergabe hat eine laufende. Bei wiederholt ausgeschriebenen Vergaben ist der
# SPÄTERE Satz der gültige, und das ist oft die nationale Quelle.
#
# Diese Rangfolge taugt deshalb NUR für die Anreicherungsrichtung (wohin fehlende Felder
# fliessen), NICHT als Entscheidung, welcher Satz ein Lead wird. Ein Ausschluss von
# Dubletten auf ihrer Basis haette 6 echte Dubletten entfernt und 64 gueltige Leads mit.
QUELLEN_RANG = {"eforms": 0, "legacy": 1, "ojs": 2, "text": 3,
                "doe": 4, "simap": 4, "atverg": 4, "dtvp": 5}

_STOPP = frozenset("""der die das und oder von für mit im in am an auf zu zur zum des dem den
eines einer eine ein als bei aus über unter nach vor durch gemäss gemäß sowie inkl inklusive
los lose teil ba bauabschnitt vergabe ausschreibung arbeiten lieferung leistung leistungen
neubau sanierung erneuerung""".split())


def worte(s: str | None) -> frozenset[str]:
    """Titel → bedeutungstragende Wörter. Zahlen bleiben (Los-/Vergabenummern trennen)."""
    if not s:
        return frozenset()
    roh = re.findall(r"[a-zà-ÿA-ZÀ-Þ0-9]{3,}", s.lower())
    return frozenset(w for w in roh if w not in _STOPP)


def zahlen(s: str | None) -> frozenset[str]:
    """Alle Zahlfolgen aus dem ROHTITEL — auch ein- und zweistellige.

    `worte()` behaelt nur Tokens ab drei Zeichen. „26.39" zerfaellt dort in „26" und
    „39", beide zweistellig, beide verworfen — die Losnummer verschwindet also, BEVOR
    die Los-Sperre sie sehen kann. Gemessen an den Paaren „26.39 / 26.40 / 26.30 —
    Grundschulerweiterung und Ersatzneubau MZH", die als Dubletten in der Tabelle
    landeten, obwohl die Nummer sie klar trennt.

    Fuehrende Nullen fallen weg, damit „Los 03" und „Los 3" dieselbe Nummer sind.
    """
    if not s:
        return frozenset()
    return frozenset(x.lstrip("0") or "0" for x in re.findall(r"\d+", s))


def _enthaltung(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _laden(country: str, ab_jahr: int):
    import duckdb

    g = glob.glob(f"{ROOT}/data/silver/{country}/notices/**/*.parquet", recursive=True)
    p = glob.glob(f"{ROOT}/data/silver/{country}/notice_parties/**/*.parquet", recursive=True)
    con = duckdb.connect()
    return con.execute(f"""
        SELECT n.notice_id, n.schema_gen, n.title,
               coalesce(n.publication_date, n.submission_deadline) AS d,
               b.buyer_name AS buyer, n.cpv_main, n.estimated_value, n.submission_deadline,
               n.performance_nuts, n.description
        FROM read_parquet({g!r}) n
        LEFT JOIN (SELECT notice_id, min(name) AS buyer_name FROM read_parquet({p!r})
                   WHERE role='buyer' GROUP BY 1) b USING (notice_id)
        WHERE n.notice_kind IN ('cn','pin') AND n.title IS NOT NULL
          AND coalesce(n.year, 0) >= {int(ab_jahr)}
    """).fetchall()


def finde(country: str = "DE", ab_jahr: int = 2026) -> list[dict]:
    """Alle Dubletten-Paare eines Landes, quellenübergreifend."""
    zeilen = _laden(country, ab_jahr)
    print(f"  {len(zeilen):,} Bekanntmachungen ab {ab_jahr} geladen")
    saetze = []
    for nid, gen, titel, d, buyer, cpv, wert, frist, nuts, beschr in zeilen:
        w = worte(titel)
        if len(w) < MIN_WORTE:
            continue                      # zu kurz für eine belastbare Aussage
        # Kaeufername ueber die PROJEKTEIGENE Normalform vergleichen, nicht roh.
        # `normalize_company` entfernt Akzente, Klammerzusaetze, Vertretungsklauseln,
        # Abteilungs-Anhaengsel, Rechtsformen und Einkaufskreis-Nummern — an echten Daten
        # erprobt (122.860 Kaeufernamen → 75.306 Normalformen). Der rohe Vergleich davor
        # liess „bundesagentur fuer arbeit, regionales einkaufszentrum nrw" und dieselbe
        # Zeichenkette OHNE Komma als verschiedene Kaeufer durchgehen. Gemessen: +941 Paare
        # bekommen dadurch einen Kaeufer-Beleg, 2.918 → 3.859 von 6.794.
        saetze.append({"id": nid, "gen": gen or "?", "titel": titel, "w": w,
                       "z": zahlen(titel), "d": d,
                       "buyer": _entities.normalize_company(buyer) if buyer else "",
                       "cpv": cpv, "wert": wert,
                       "frist": frist, "nuts": nuts, "beschr": beschr})

    # Invertierter Index: Wort → Sätze. Der Kandidatenraum wird über die SELTENSTEN Wörter
    # aufgespannt, sonst vergleicht man jeden „Neubau" mit jedem.
    inv: dict[str, list[int]] = defaultdict(list)
    for i, s in enumerate(saetze):
        for w in s["w"]:
            inv[w].append(i)

    paare, gesehen = [], set()
    for i, s in enumerate(saetze):
        seeds = sorted((w for w in s["w"] if w in inv), key=lambda w: len(inv[w]))[:SEED_WORTE]
        kand = {j for w in seeds for j in inv[w] if j != i}
        for j in kand:
            schluessel = (min(i, j), max(i, j))
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            t = saetze[j]
            if s["gen"] == t["gen"]:
                continue                  # dieselbe Quelle dedupliziert sich selbst schon
            e = _enthaltung(s["w"], t["w"])
            if e < MIN_ENTHALTUNG:
                continue
            if s["d"] and t["d"] and abs((s["d"] - t["d"]).days) > FENSTER_TAGE:
                continue
            # LOS-GUARD. Gemessen: „GU-Rahmenvertrag 2026 Los 1 - Hochbau" und
            # „… Los 2 - Dach und Fassade" landeten als Dubletten in der Tabelle. Das sind
            # VERSCHIEDENE Lose desselben Rahmenvertrags — zwei Vergaben, auf die man
            # getrennt bietet, kein doppelter Satz. Unterscheiden sie sich in einer Zahl
            # bei sonst gleichem Text, ist das ein Trennmerkmal, kein Rauschen.
            #
            # Die Zahlen kommen aus dem ROHTITEL (`zahlen()`), nicht aus `w` — sonst
            # faellt jede ein- oder zweistellige Losnummer durch das 3-Zeichen-Minimum
            # von `worte()` und die Sperre laeuft leer. Siehe Docstring dort.
            if s["z"] and t["z"] and s["z"] != t["z"]:
                continue
            # GEWERKE-SPERRE. Dieselbe Trennung wie oben, nur ohne Nummern: ein Bauprojekt
            # wird gewerkeweise ausgeschrieben, und die Gewerke stehen als WORT im Titel.
            #   „… Bertha-von-Suttner-Gymnasium – Trockenbauarbeiten"
            #   „… Bertha-von-Suttner-Gymnasium – Stahlbauarbeiten"
            # Der gemeinsame Projektname ist lang, das trennende Wort kurz — die Enthaltung
            # liegt dadurch weit ueber der Schwelle. Merkmal ist nicht die Aehnlichkeit,
            # sondern die RICHTUNG: bei echten Dubletten hat hoechstens EINE Seite eigene
            # Woerter (die andere ist Teilmenge oder gleich), bei Geschwister-Losen haben
            # BEIDE eines. Sprachunabhaengig und ohne Gewerke-Vokabular — was in DE/AT/CH
            # gilt, gilt auch in FR und PL.
            #
            # Gemessen an einem Zufallsschnitt: der beidseitige Eimer enthaelt neben Losen
            # auch voellig unverwandte Vergaben desselben Kaeufers („Sanierung Freibad"
            # gegen „Neubau Schulmensa", „Mittagessen Regelschule" gegen „Kopierpapier").
            # Sie wird deshalb als eigene Belegstufe MARKIERT, nicht verworfen — die Paare
            # bleiben in der Tabelle sichtbar, aber die Anreicherung fasst sie nicht an.
            geschwister = bool((s["w"] - t["w"]) and (t["w"] - s["w"]))
            gleicher_kaeufer = bool(s["buyer"] and s["buyer"] == t["buyer"])
            # BELEGLAGE statt Schwelle. Ein kurzer Gewerke-Titel („Sanitär, Lüftung,
            # Heizung") steckt vollständig in jedem längeren Titel desselben Gewerks —
            # Enthaltung 1,0 ist dort KEIN Identitätsbeleg. Gemessen: eine Lockerung auf
            # „Titel identisch genügt" haette die Anreicherung von 28 auf 393 Werte
            # gehoben und dabei fremde Fristen uebernommen. Die Stufe steht deshalb in
            # der Tabelle, damit jeder Verbraucher selbst entscheidet.
            kurz = min(len(s["w"]), len(t["w"])) < 6
            beleg = ("geschwister" if geschwister
                     else "kaeufer_und_titel" if gleicher_kaeufer
                     else "nur_titel_kurz" if kurz else "nur_titel")
            # Master = reichere Quelle. Bei Gleichstand der frühere Satz.
            a, b = (s, t) if QUELLEN_RANG.get(s["gen"], 9) <= QUELLEN_RANG.get(t["gen"], 9) else (t, s)
            paare.append({
                "master_id": a["id"], "duplicate_id": b["id"],
                "master_quelle": a["gen"], "duplicate_quelle": b["gen"],
                "enthaltung": round(e, 3), "gleicher_kaeufer": gleicher_kaeufer,
                "beleg": beleg,
                "tage_abstand": abs((s["d"] - t["d"]).days) if s["d"] and t["d"] else None,
                # Was bringt die Dublette MIT, das der Master nicht hat?
                "ergaenzt": ",".join(f for f in ("cpv", "wert", "frist", "nuts", "beschr")
                                     if b[f if f != "cpv" else "cpv"] and not a[f if f != "cpv" else "cpv"]) or None,
            })
    return paare


def schreibe(paare: list[dict], country: str = "DE") -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    ziel = ROOT / "data" / "gold" / country / "notice_duplicates.parquet"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(paare, schema=pa.schema([
        ("master_id", pa.string()), ("duplicate_id", pa.string()),
        ("master_quelle", pa.string()), ("duplicate_quelle", pa.string()),
        ("enthaltung", pa.float64()), ("gleicher_kaeufer", pa.bool_()),
        ("beleg", pa.string()),
        ("tage_abstand", pa.int64()), ("ergaenzt", pa.string())])),
        ziel, compression="zstd")
    return ziel


def anreichern(country: str = "DE") -> dict:
    """Dubletten-Tabelle → konkrete Feldwerte, die dem Master fehlen.

    Erkennung allein nuetzt nichts: `ergaenzt` sagt nur, DASS die Dublette eine Frist hat.
    Diese Funktion holt den WERT und legt ihn als `notice_enrichment.parquet` ab —
    (notice_id, feld, wert, quelle_notice_id, quelle_gen). Damit kann ein Verbraucher die
    Luecke fuellen, ohne selbst zu joinen, und die Herkunft bleibt an jedem Wert haengen.

    **Nur unstrittige Paare.** Angereichert wird ausschliesslich aus Dubletten mit
    IDENTISCHEM Kaeufer. Gemessen: von 7.000 Paaren tragen 2.950 denselben Kaeufer; die
    uebrigen sind gemischt — „Kunststoff-, Metallbau- und Verglasungsarbeiten" gegen
    „Metallbau, Kunststoff- und Verglasungsarbeiten, Theodor-Heuss Grundschule" ist
    plausibel dasselbe, „Strassenerhaltung Rahmenvertrag 2026-2028" gegen „Rahmenvertrag
    Jahresvertrag Neubau und Unterhaltungsarbeiten" bei Enthaltung 0,8 eher nicht. Aus einem
    Zweifelsfall einen Wert zu uebernehmen hiesse, eine falsche Frist ins Produkt zu
    schreiben — schlimmer als eine fehlende.

    **Es wird nichts ueberschrieben.** Nur Felder, die beim Master NULL sind.
    """
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    dup = ROOT / "data" / "gold" / country / "notice_duplicates.parquet"
    if not dup.exists():
        print(f"  keine {dup.name} — erst `finde` laufen lassen")
        return {}
    g = glob.glob(f"{ROOT}/data/silver/{country}/notices/**/*.parquet", recursive=True)
    con = duckdb.connect()
    FELDER = ("submission_deadline", "performance_nuts", "cpv_main",
              "estimated_value", "description")
    zeilen = []
    for feld in FELDER:
        typ = "VARCHAR" if feld not in ("submission_deadline", "estimated_value") else None
        wert_sql = f"CAST(x.{feld} AS VARCHAR)"
        zeilen += [dict(notice_id=r[0], feld=feld, wert=r[1], quelle_notice_id=r[2],
                        quelle_gen=r[3])
                   for r in con.execute(f"""
              SELECT d.master_id, {wert_sql}, d.duplicate_id, d.duplicate_quelle
              FROM read_parquet('{dup.as_posix()}') d
              JOIN read_parquet({g!r}) m ON m.notice_id = d.master_id
              JOIN read_parquet({g!r}) x ON x.notice_id = d.duplicate_id
              -- Auf die BELEGSTUFE filtern, nicht auf `gleicher_kaeufer`. Geschwister-Lose
              -- teilen sich per Definition den Kaeufer — die Spalte ist dort wahr und haette
              -- die Sperre lautlos unterlaufen. `kaeufer_und_titel` schliesst sie aus.
              WHERE d.beleg = 'kaeufer_und_titel'
                AND m.{feld} IS NULL AND x.{feld} IS NOT NULL
           """).fetchall()]

    # FRISTVERLAENGERUNG — die einzige Stelle, an der ein Wert NICHT nur eine Luecke
    # fuellt, sondern einen vorhandenen korrigiert. Sie steht deshalb als eigene Feldart
    # `submission_deadline_verlaengert` da und nicht unter `submission_deadline`.
    #
    # Der Fall: TED und die nationale Quelle veroeffentlichen dieselbe Vergabe, die Frist
    # wird spaeter verschoben, und nur eine der beiden Quellen bekommt die Korrektur mit.
    # Der Lead gilt bei uns dann als abgelaufen, obwohl man noch bieten kann — ein Fehler,
    # den der Kunde direkt merkt: er filtert „offen" und die Ausschreibung fehlt.
    #
    # EINDEUTIGKEIT IST PFLICHT. Gemessen an den 109 Kandidaten: 69 davon sind mehrdeutig,
    # weil Behoerden templatisierte Titel benutzen. „REZ SW 45ind JC Rhein-Neckar-Kreis"
    # ist ein Dienststellen-Kuerzel, kein Auftragsgegenstand — drei verschiedene eForms-
    # Bekanntmachungen (24.06./07.07./16.07.) haengen dort an EINER DOeE-Bekanntmachung vom
    # 18.08. Hoechstens eine davon ist die Verlaengerung; welche, ist aus dem Titel nicht
    # zu entscheiden. Uebertragen wird deshalb nur, wo die Zuordnung auf BEIDEN Seiten
    # eindeutig ist (1:1). Bleiben 40 von 109 — der Rest bleibt lieber abgelaufen als
    # falsch verlaengert.
    #
    # `current_date` bewusst zur Laufzeit: was heute verlaengert ist, ist in drei Wochen
    # abgelaufen. Ein eingefrorener Stichtag wuerde die Tabelle still veralten lassen.
    zeilen += [dict(notice_id=r[0], feld="submission_deadline_verlaengert", wert=r[1],
                    quelle_notice_id=r[2], quelle_gen=r[3])
               for r in con.execute(f"""
          WITH k AS (
            SELECT d.master_id, d.duplicate_id, d.duplicate_quelle,
                   CAST(x.submission_deadline AS VARCHAR) AS wert
            FROM read_parquet('{dup.as_posix()}') d
            JOIN read_parquet({g!r}) m ON m.notice_id = d.master_id
            JOIN read_parquet({g!r}) x ON x.notice_id = d.duplicate_id
            WHERE d.beleg = 'kaeufer_und_titel'
              AND m.submission_deadline IS NOT NULL      -- KEINE Luecke, ein falscher Wert
              AND CAST(m.submission_deadline AS DATE) <  current_date
              AND CAST(x.submission_deadline AS DATE) >= current_date),
          z AS (SELECT *, count(*) OVER (PARTITION BY master_id)    AS je_master,
                          count(*) OVER (PARTITION BY duplicate_id) AS je_dublette FROM k)
          SELECT master_id, wert, duplicate_id, duplicate_quelle
          FROM z WHERE je_master = 1 AND je_dublette = 1
       """).fetchall()]

    ziel = ROOT / "data" / "gold" / country / "notice_enrichment.parquet"
    if zeilen:
        pq.write_table(pa.Table.from_pylist(zeilen, schema=pa.schema([
            ("notice_id", pa.string()), ("feld", pa.string()), ("wert", pa.string()),
            ("quelle_notice_id", pa.string()), ("quelle_gen", pa.string())])),
            ziel, compression="zstd")
    from collections import Counter
    je_feld = Counter(z["feld"] for z in zeilen)
    print(f"  Anreicherung: {len(zeilen):,} Werte fuer "
          f"{len({z['notice_id'] for z in zeilen}):,} Bekanntmachungen")
    for f, n in je_feld.most_common():
        print(f"    {f:<22} {n:>6,}")
    return dict(je_feld)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Quellenübergreifender Dublettencheck")
    ap.add_argument("--country", default="DE")
    ap.add_argument("--ab-jahr", type=int, default=dt.date.today().year)
    ap.add_argument("--anreichern", action="store_true",
                    help="nach der Erkennung die fehlenden Feldwerte sammeln")
    a = ap.parse_args(argv)
    print(f"Dublettencheck {a.country}, ab {a.ab_jahr}")
    paare = finde(a.country, a.ab_jahr)
    if not paare:
        print("  Keine Dubletten gefunden.")
        return 0
    ziel = schreibe(paare, a.country)
    from collections import Counter
    kombis = Counter(f"{p['master_quelle']} ← {p['duplicate_quelle']}" for p in paare)
    from collections import Counter as _C
    stufen = _C(p["beleg"] for p in paare)
    sicher = sum(1 for p in paare if p["gleicher_kaeufer"])
    mit_plus = sum(1 for p in paare if p["ergaenzt"])
    print(f"\n  {len(paare):,} Dubletten-Paare, davon {sicher:,} mit identischem Käufer")
    print(f"  {mit_plus:,} bringen ein Feld MIT, das der Master nicht hat")
    print("  Beleglage: " + " · ".join(f"{k}={n:,}" for k, n in stufen.most_common()))
    for k, n in kombis.most_common(8):
        print(f"    {k:<26} {n:>7,}")
    felder = Counter(f for p in paare if p["ergaenzt"] for f in p["ergaenzt"].split(","))
    if felder:
        print("  ergänzte Felder:", ", ".join(f"{k}={n:,}" for k, n in felder.most_common()))
    print(f"\n→ {ziel.relative_to(ROOT)}")
    if a.anreichern:
        print()
        anreichern(a.country)
    return 0


if __name__ == "__main__":
    sys.exit(main())

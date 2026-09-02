#!/usr/bin/env python3
"""Vorgaenge und ihre Ketten: Ausschreibung + Dokumente + Zuschlag unter EINER Kennung.

    data/gold/<L>/vorgaenge.parquet        eine Zeile je Vorgang
    data/gold/<L>/vorgang_notice.parquet   welche Bekanntmachung gehoert dazu
    data/gold/<L>/vorgang_kette.parquet    welcher Vorgang folgt auf welchen

DIE FRAGE. Wer eine Kennung sucht, will die Akte sehen: die Ausschreibung, die Unterlagen, die
Berichtigungen und am Ende den Zuschlag. Heute ist jeder dieser Teile fuer sich adressierbar und
nichts davon zusammen.

⚠ DER SCHLUESSEL IST EIN WASSERFALL, UND SEINE STUFEN SIND VERSCHIEDEN GUT. Deshalb steht in
jeder Zeile, WOHER er kommt (`schluessel_quelle`) — eine zusammengesetzte Akte darf nicht
aussehen wie eine amtlich verknuepfte:

  `folder`   `ContractFolderID` (BT-04, Verfahrenskennung des Auftraggebers). Liegt in 100 %
             der eForms-Bekanntmachungen und gruppiert enger als der alte Weg (1,57 gegen 1,46
             Bekanntmachungen je Verfahren). Das ist die Stufe, die die Jahre ab 2024 traegt.
  `rueckref` Wurzel der `ref_publication_number`-Kette (legacy TED, bis 2023). ⚠ Ab eForms ist
             das Feld praktisch leer — genau daran bricht `award_tender_link` (2023: 44.470
             verknuepfte Zuschlaege, 2024: 507, danach null) und ebenso `procedures.parquet`.
  `allein`   keine der beiden Stufen greift: die Bekanntmachung IST der Vorgang. Normalfall bei
             nationalen Quellen (DOeE traegt `ContractFolderID` nur zu 9 %).

⚠ GROSSE VORGAENGE WERDEN GEZAEHLT, NICHT GEKAPPT. 304 Kennungen tragen ueber 20
Bekanntmachungen, die groesste 344. Das ist ENTWEDER ein Rahmenvertrag mit vielen Abrufen — „DBS
ueber den Bezug von Schulungsleistungen": 1 Ausschreibung, 789 Zuschlaege, 0 Korrekturen — ODER
eine nachlaessig vergebene Kennung. Der Unterschied steht in den Zaehlspalten. Wer kappt, wirft
den Fall weg, wegen dem man das Ganze baut.

⚠ WAS AN UNTERLAGEN DRANHAENGT, STEHT MIT DABEI. `hat_unterlagen` und `n_dokumente` sagen, ob
die Akte ihre dritte Schicht hat. Heute hat sie kein abgeschlossener Vorgang: Unterlagen gibt es
nur waehrend laufender Frist, und der Dokumentbestand ist zwei Wochen alt. Zwischen Ausschreibung
und Zuschlag liegen im Median 114 Tage — die ersten vollstaendigen Akten entstehen um Januar
2027, von selbst, sofern niemand `web/data/doc-analysis/` aufraeumt.

DIE KETTEN. Ein Rahmenvertrag laeuft aus und wird neu ausgeschrieben — dieselbe Stelle, derselbe
Bedarf, neue Anforderungen. `contract_succession` kennt diese Nachfolge auf Ebene der
BEKANNTMACHUNG; hier wird sie auf die Ebene des VORGANGS gehoben.

⚠ DABEI FALLEN 10.935 KANTEN WEG, UND ZWAR ZU RECHT: sie verbinden zwei Bekanntmachungen
DESSELBEN Vorgangs — die Abrufe unter einem Rahmenvertrag. Auf Vorgangsebene ist das keine
Nachfolge, sondern Innenleben. Von 114.402 Kanten bleiben 103.467.

⚠ JE VORGANG GEWINNT DER BESTE VORGAENGER, und das ist eine Korrektur fuer 1 % der Faelle:
100.742 von 101.780 Vorgaengen haben ohnehin genau einen. Nachfolger verzweigen dagegen oft
(13.260 mit zwei bis drei) — ein alter Auftrag wird in mehrere neue zerlegt. Die Kette folgt
deshalb der Vorgaenger-Richtung.

⚠ UND SIE TRAEGT IHRE KONFIDENZ MIT. `contract_succession` ist keine amtliche Verknuepfung,
sondern Inhaltsvergleich (0,76) und LLM-Adjudikation (0,70). Eine Kette ist so belastbar wie ihr
schwaechstes Glied — `min_konfidenz` steht deshalb an jeder.

Aufruf: python3 scripts/build_vorgaenge.py [--land DE]
"""
from __future__ import annotations

import argparse
import collections
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

RANG = {"folder": 0, "rueckref": 1, "allein": 2}
DAUERANGEBOT_TAKT = 4.0   # Glieder je Jahr; darueber ist es kein Neuausschreibungs-Rhythmus

SPALTEN_V = ("land VARCHAR, vorgang_id VARCHAR, schluessel_quelle VARCHAR, "
             "n_bekanntmachungen BIGINT, n_ausschreibung BIGINT, n_zuschlag BIGINT, "
             "n_korrektur BIGINT, n_vorinfo BIGINT, "
             "erste_veroeffentlichung DATE, letzte_veroeffentlichung DATE, "
             "titel VARCHAR, cpv VARCHAR, vollstaendig BOOLEAN, "
             "hat_unterlagen BOOLEAN, n_dokumente BIGINT, n_anforderungen BIGINT")
SPALTEN_N = ("land VARCHAR, vorgang_id VARCHAR, notice_id VARCHAR, notice_kind VARCHAR, "
             "jahr BIGINT, veroeffentlicht DATE, hat_unterlagen BOOLEAN")
SPALTEN_K = ("land VARCHAR, kette_id VARCHAR, vorgang_id VARCHAR, position BIGINT, "
             "n_glieder BIGINT, jahr BIGINT, konfidenz_zum_vorgaenger DOUBLE, "
             "min_konfidenz DOUBLE, methode VARCHAR, n_titel BIGINT, "
             "glieder_pro_jahr DOUBLE, dauerangebot BOOLEAN, vorgaenger VARCHAR")


def _laender() -> list[str]:
    """Aus dem Bestand, nicht aus einer Liste im Code."""
    s = ROOT / "data" / "silver"
    return sorted(p.name for p in s.iterdir()
                  if p.is_dir() and (p / "notices").is_dir()) if s.exists() else []


def _wurzel(ref: dict[str, str], pn: str) -> str:
    """Wurzel der Rueckverweis-Kette. ⚠ Mit Zyklusschutz — eine Korrektur, die auf sich selbst
    zeigt, haengt sonst den ganzen Lauf auf (beim Bauen genau einmal passiert)."""
    gesehen: set[str] = set()
    while True:
        eltern = ref.get(pn)
        if not eltern or eltern in gesehen:
            return pn
        gesehen.add(pn)
        pn = eltern


def _schreibe(con, pfad: pathlib.Path, zeilen: list, spalten: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"CREATE OR REPLACE TABLE _t ({spalten})")
    if zeilen:
        import pyarrow as pa
        namen = [s.strip().split()[0] for s in spalten.split(",")]
        tabelle = pa.table({n: [z[i] for z in zeilen] for i, n in enumerate(namen)})
        con.register("_arrow", tabelle)
        con.execute("INSERT INTO _t SELECT * FROM _arrow")
        con.unregister("_arrow")
    con.execute(f"COPY _t TO '{pfad.as_posix()}' (FORMAT PARQUET)")


def baue(con, land: str) -> tuple[int, int]:
    N = f"read_parquet('{(ROOT / 'data' / 'silver' / land / 'notices').as_posix()}/**/*.parquet')"
    apfad = ROOT / "data" / "silver" / land / "attributes"
    gold = ROOT / "data" / "gold" / land

    folder: dict[str, str] = {}
    if apfad.is_dir():
        A = f"read_parquet('{apfad.as_posix()}/**/*.parquet')"
        for nid, wert in con.execute(
                f"select distinct notice_id, value from {A} "
                "where path like '%.ContractFolderID' and value is not null "
                "and trim(value) <> ''").fetchall():
            folder.setdefault(str(nid), str(wert).strip())

    ref = {str(a): str(b) for a, b in con.execute(
        f"select publication_number, ref_publication_number from {N} "
        "where publication_number is not null and ref_publication_number is not null").fetchall()}

    mit_docs: dict[str, tuple[int, int]] = {}
    dpfad, tpfad = gold / "doc_checklist.parquet", ROOT / "data" / "docs" / land / "doc_text.parquet"
    if dpfad.exists():
        for nid, n in con.execute(
                f"select notice_id, count(*) from read_parquet('{dpfad.as_posix()}') group by 1").fetchall():
            mit_docs[str(nid)] = (0, int(n))
    if tpfad.exists():
        for nid, n in con.execute(
                f"select notice_id, count(*) from read_parquet('{tpfad.as_posix()}') "
                "where status = 'ok' group by 1").fetchall():
            mit_docs[str(nid)] = (int(n), mit_docs.get(str(nid), (0, 0))[1])

    zeilen_n: list = []
    gruppen: dict[str, list] = collections.defaultdict(list)
    for nid, pn, kind, jahr, datum, titel, cpv in con.execute(
            f"select notice_id, publication_number, notice_kind, year, publication_date, "
            f"title, cpv_main from {N}").fetchall():
        s_nid, s_pn = str(nid), (str(pn) if pn else "")
        if s_nid in folder:
            vid, quelle = f"folder:{folder[s_nid]}", "folder"
        elif s_pn and s_pn in ref:
            vid, quelle = f"pub:{_wurzel(ref, s_pn)}", "rueckref"
        else:
            vid, quelle = f"pub:{s_pn or s_nid}", "allein"
        dok = mit_docs.get(s_nid)
        zeilen_n.append((land, vid, s_nid, str(kind or ""), int(jahr or 0), datum, bool(dok)))
        gruppen[vid].append((quelle, str(kind or ""), datum, titel, cpv, dok))

    zeilen_v: list = []
    for vid, teile in gruppen.items():
        arten = collections.Counter(t[1] for t in teile)
        daten = sorted(t[2] for t in teile if t[2])
        # ⚠ Titel und CPV kommen aus der AUSSCHREIBUNG, nicht aus dem Zuschlag: der Zuschlag
        # traegt oft nur „Vergabe von …" oder den Losnamen.
        aus = [t for t in teile if t[1] == "cn"] or teile
        # ⚠ DIE STAERKSTE REGEL DER GRUPPE GEWINNT, nicht die erste Bekanntmachung. Bei einer
        # Rueckverweis-Kette traegt nur das KIND einen Verweis; die Wurzel faellt fuer sich auf
        # `allein` und gruppiert trotzdem richtig. Wer das Erstbeste nimmt, meldet je nach
        # Lesereihenfolge mal `rueckref`, mal `allein` — die Zahl schwankte um das Fuenfzigfache.
        beste = min((t[0] for t in teile), key=lambda q: RANG[q])
        dokumente = sum(t[5][0] for t in teile if t[5])
        anforderungen = sum(t[5][1] for t in teile if t[5])
        zeilen_v.append((
            land, vid, beste, len(teile),
            arten.get("cn", 0), arten.get("can", 0), arten.get("corrigendum", 0), arten.get("pin", 0),
            daten[0] if daten else None, daten[-1] if daten else None,
            (aus[0][3] or None), (aus[0][4] or None),
            arten.get("cn", 0) > 0 and arten.get("can", 0) > 0,
            dokumente > 0, dokumente, anforderungen))

    _schreibe(con, gold / "vorgaenge.parquet", zeilen_v, SPALTEN_V)
    _schreibe(con, gold / "vorgang_notice.parquet", zeilen_n, SPALTEN_N)
    return len(zeilen_v), len(zeilen_n)


def baue_ketten(con, land: str) -> tuple[int, int]:
    """Nachfolge auf Vorgangsebene, als Ketten ausgeschrieben."""
    gold = ROOT / "data" / "gold" / land
    S, VN, V = (gold / "contract_succession.parquet", gold / "vorgang_notice.parquet",
                gold / "vorgaenge.parquet")
    if not (S.exists() and VN.exists() and V.exists()):
        _schreibe(con, gold / "vorgang_kette.parquet", [], SPALTEN_K)
        return 0, 0
    kanten = con.execute(f"""
        select distinct a.vorgang_id nach, b.vorgang_id vor, s.confidence, s.method, s.gap_years
        from read_parquet('{S.as_posix()}') s
        join read_parquet('{VN.as_posix()}') a on a.notice_id = s.successor
        join read_parquet('{VN.as_posix()}') b on b.notice_id = s.predecessor
        where a.vorgang_id <> b.vorgang_id""").fetchall()
    bester: dict[str, tuple] = {}
    for nach, vor, konf, methode, jahre in kanten:
        rang = (float(konf or 0), -float(jahre if jahre is not None else 99))
        if nach not in bester or rang > bester[nach][0]:
            bester[nach] = (rang, vor, float(konf or 0), str(methode or ""))
    kopf = {str(a): (int(b) if b else 0, str(c or "")) for a, b, c in con.execute(
        f"select vorgang_id, year(erste_veroeffentlichung), titel "
        f"from read_parquet('{V.as_posix()}')").fetchall()}

    def wurzel(v: str) -> str:
        """⚠ Zyklusschutz: eine Nachfolge-SCHAETZUNG kann im Kreis zeigen."""
        gesehen: set[str] = set()
        while v in bester and v not in gesehen:
            gesehen.add(v)
            v = bester[v][1]
        return v

    glieder: dict[str, list[str]] = collections.defaultdict(list)
    for v in set(list(bester) + [b[1] for b in bester.values()]):
        glieder[wurzel(v)].append(v)

    zeilen: list = []
    for kette_id, mitglieder in glieder.items():
        if len(mitglieder) < 2:
            continue
        geordnet = sorted(mitglieder, key=lambda v: (kopf.get(v, (0, ""))[0], v))
        konfs = [bester[v][2] for v in geordnet if v in bester]
        mini = min(konfs) if konfs else None
        # ⚠ DER TAKT TRENNT NEUAUSSCHREIBUNG VON DAUERANGEBOT, nicht der Titel. Die erste
        # Fassung markierte Ketten mit nur EINEM Titel — und traf daneben: die laengste Kette
        # (435 Glieder, „Abschluss einer nicht-exklusiven Rabattvereinbarung") traegt mehrere
        # Titelvarianten und waere durchgerutscht. Ein Rahmenvertrag wird alle zwei bis vier
        # Jahre neu vergeben; ein Open-House-Vertrag nach §130a SGB V nimmt laufend Beitritte
        # auf. Gemessen: 398 Ketten liegen ueber vier Gliedern je Jahr und halten 8.927 Glieder
        # bei einem Schnitt von 22,4 — der ganze Klumpen.
        # ⚠ CLAUDE.md nennt den Fall („DAK-Arzneimittel 440× war Open-House"), aber
        # `verfahren_status` traegt im heutigen Bestand kein `open_house`. Markiert, nicht
        # entfernt: wer Arzneimittel beobachtet, will diese Ketten sehen.
        jahre = [kopf.get(v, (0, ""))[0] for v in geordnet if kopf.get(v, (0, ""))[0]]
        spanne = max((max(jahre) - min(jahre) + 1) if jahre else 1, 1)
        takt = len(geordnet) / spanne
        titel = {" ".join(kopf.get(v, (0, ""))[1].lower().split())[:60] for v in geordnet}
        titel.discard("")
        # ⚠ `position` IST EIN ZEITRANG, KEIN KETTENRANG. Sortiert wird nach Jahr, weil eine
        # Ansicht einen Zeitstrahl will. Der Vorgaenger einer Vergabe ist deshalb NICHT
        # zwangslaeufig die Zeile darueber: in 3.189 Faellen sitzt die Wurzel (die ohne
        # Vorgaenger) mitten in der Kette, weil die erschlossene Nachfolge rueckwaerts in
        # der Zeit zeigt. Ohne die Spalte `vorgaenger` kann eine Anzeige die Konfidenz
        # keinem sichtbaren Uebergang zuordnen und behauptet stillschweigend den falschen.
        for i, v in enumerate(geordnet, 1):
            e = bester.get(v)
            zeilen.append((land, kette_id, v, i, len(geordnet), kopf.get(v, (0, ""))[0],
                           e[2] if e else None, mini, e[3] if e else "",
                           len(titel), round(takt, 2), takt > DAUERANGEBOT_TAKT,
                           e[1] if e else None))
    _schreibe(con, gold / "vorgang_kette.parquet", zeilen, SPALTEN_K)
    return len({z[1] for z in zeilen}), len(zeilen)


def main() -> int:
    import duckdb
    p = argparse.ArgumentParser()
    p.add_argument("--land", default=None)
    a = p.parse_args()
    con = duckdb.connect()
    for land in ([a.land] if a.land else _laender()):
        n_v, n_n = baue(con, land)
        V = f"read_parquet('{(ROOT / 'data' / 'gold' / land / 'vorgaenge.parquet').as_posix()}')"
        z = con.execute(f"""select count(*) filter (where vollstaendig) voll,
              count(*) filter (where hat_unterlagen) mit_dok,
              count(*) filter (where schluessel_quelle = 'folder') via_folder,
              count(*) filter (where schluessel_quelle = 'rueckref') via_ref,
              count(*) filter (where schluessel_quelle = 'allein') allein from {V}""").fetchone()
        print(f"  {land}: {n_v:,} Vorgaenge aus {n_n:,} Bekanntmachungen · "
              f"{z[0]:,} vollstaendig (Ausschreibung UND Zuschlag) · {z[1]:,} mit Unterlagen")
        print(f"      Schluessel: folder {z[2]:,} · rueckref {z[3]:,} · allein {z[4]:,}")
        n_k, n_g = baue_ketten(con, land)
        if n_k:
            K = f"read_parquet('{(ROOT / 'data' / 'gold' / land / 'vorgang_kette.parquet').as_posix()}')"
            d = con.execute(f"""select max(n_glieder),
                  count(distinct kette_id) filter (where dauerangebot) from {K}""").fetchone()
            print(f"      Ketten: {n_k:,} mit {n_g:,} Gliedern · laengste {d[0]} · "
                  f"{d[1]:,} als Dauerangebot markiert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

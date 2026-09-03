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

# Vierte Stufe: wie weit ein heimatloser Zuschlag zurueckgreifen darf, um seine Ausschreibung
# zu finden. Gemessen bei 12 und 24 Monaten: das laengere Fenster ordnet WENIGER zu (56.529
# statt 57.260), weil mehr Ausschreibungen passen und der Fall damit mehrdeutig wird.
ANDOCK_TAGE = 372

SPALTEN_V = ("land VARCHAR, vorgang_id VARCHAR, schluessel_quelle VARCHAR, "
             "n_bekanntmachungen BIGINT, n_ausschreibung BIGINT, n_zuschlag BIGINT, "
             "n_korrektur BIGINT, n_vorinfo BIGINT, "
             "erste_veroeffentlichung DATE, letzte_veroeffentlichung DATE, "
             "titel VARCHAR, cpv VARCHAR, vollstaendig BOOLEAN, "
             "hat_unterlagen BOOLEAN, n_dokumente BIGINT, n_anforderungen BIGINT, "
             "n_angedockt BIGINT, n_dubletten BIGINT, n_verschmolzen BIGINT")
# Nur dieser Beleg wird geglaubt. `nur_titel`, `nur_titel_kurz` und `geschwister` sind
# schwaechere Indizien; `export_web_leads.py` traut aus demselben Grund ebenfalls nur diesem.
DUBLETTEN_BELEG = "kaeufer_und_titel"

# Wie weit die ERSTVEROEFFENTLICHUNGEN zweier Vorgaenge auseinanderliegen duerfen, damit
# sie als dieselbe Vergabe gelten.
#
# ⚠ NICHT GETUNT, SONDERN UEBERNOMMEN: `govisor/dedupe.py` kappt seine Paare bei 90 Tagen.
# Auf Bekanntmachungsebene gilt das schon; beim Heben auf die Vorgangsebene geht die Naehe
# aber verloren, denn ein Vorgang kann sich ueber Jahre erstrecken. Ohne diese Grenze
# entstand eine Akte von 2011 bis 2023 mit 150 Zuschlaegen — ein Jahrzehnt, keine Vergabe.
VORGANG_DUBLETTE_TAGE = 90

SPALTEN_N = ("land VARCHAR, vorgang_id VARCHAR, notice_id VARCHAR, notice_kind VARCHAR, "
             "jahr BIGINT, veroeffentlicht DATE, hat_unterlagen BOOLEAN, dublette BOOLEAN")
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


def _anwenden(karte: dict[str, str], zeilen_n: list, gruppen: dict,
              zaehle_teile: bool = False) -> tuple[list, dict, dict]:
    """Eine Zuordnung „alte Nummer → Zielnummer" auf Bekanntmachungen und Gruppen anwenden.

    Vierte und fuenfte Stufe unterscheiden sich darin, WAS sie zuordnen, nicht darin, wie
    das Ergebnis eingearbeitet wird. `zaehle_teile` trennt die beiden Zaehlweisen: die
    vierte Stufe zaehlt aufgenommene BEKANNTMACHUNGEN, die fuenfte aufgenommene VORGAENGE.
    """
    zaehler: dict[str, int] = collections.Counter()
    if not karte:
        return zeilen_n, gruppen, zaehler
    zeilen_n = [(l, karte.get(v, v), *rest) for l, v, *rest in zeilen_n]
    neue: dict[str, list] = collections.defaultdict(list)
    for vid, teile in gruppen.items():
        ziel = karte.get(vid, vid)
        if ziel != vid:
            zaehler[ziel] += len(teile) if zaehle_teile else 1
        neue[ziel].extend(teile)
    return zeilen_n, neue, zaehler


def _vorgangsdubletten(con, land: str, gruppen: dict, zeilen_n: list) -> dict[str, str]:
    """Fuenfte Stufe: dieselbe Vergabe, die als ZWEI Vorgaenge existiert.

    **Das Problem.** Melden zwei Portale dieselbe Vergabe und bekommen die beiden Meldungen
    verschiedene Schluessel, entstehen zwei Akten fuer einen Vorgang. Die Firewall weiss
    laengst, dass es dieselbe ist; die Vorgangsebene zog daraus bisher keine Folgerung.

    **Die Regel, in derselben Form wie `_andocken`.** Eine Zweitmeldung haengt sich an ihren
    Master; Master haengen sich NIE aneinander. Vetos:
      * der Kandidat ist selbst Master eines anderen Paares,
      * er bezieht seinen Schluessel aus einer amtlichen `ContractFolderID`,
      * die Erstveroeffentlichungen liegen weiter als `VORGANG_DUBLETTE_TAGE` auseinander,
      * es passt mehr als ein Master.

    ⚠ OHNE DIE ZEITGRENZE WAERE ES FALSCH, und zwar spektakulaer. Der Beleg der Firewall
    gilt fuer zwei BEKANNTMACHUNGEN binnen 90 Tagen. Ein VORGANG kann aber Jahre umspannen;
    hebt man das Paar ungeprueft hoch, verschmilzt eine Akte von 2011 mit einer von 2023.
    Genau so entstand im Versuch eine Akte mit 150 Zuschlaegen ueber zwoelf Jahre.

    ⚠ UND OHNE DIE NICHT-TRANSITIVITAET EBENSO. Eine freie Verschmelzung ueber denselben
    Belegen erzeugte Gruppen von 148 Vorgaengen: A gleicht B, B gleicht C, C gleicht D, und
    ueber ein gleitendes 90-Tage-Fenster laeuft man durch ein Jahr.

    Was danach noch zusammenliegt, ist ein Rahmenvertrag mit vielen Abrufen — und der DARF
    eine grosse Akte sein (s. Kopf dieser Datei). Groesstes Ziel nach allen Sperren: +34.
    """
    d = ROOT / "data" / "gold" / land / "notice_duplicates.parquet"
    if not d.exists():
        return {}
    vorgang_von = {nid: vid for _l, vid, nid, *_r in zeilen_n}
    erste, quelle_von = {}, {}
    for vid, teile in gruppen.items():
        daten = sorted(t[2] for t in teile if t[2])
        if daten:
            erste[vid] = daten[0]
        quelle_von[vid] = min((t[0] for t in teile), key=lambda q: RANG[q])

    paare = con.execute(
        f"select distinct master_id, duplicate_id from read_parquet('{d.as_posix()}') "
        f"where beleg = '{DUBLETTEN_BELEG}'").fetchall()
    roh: list[tuple[str, str]] = []
    for m, x in paare:
        vm, vx = vorgang_von.get(str(m)), vorgang_von.get(str(x))
        if vm and vx and vm != vx:
            roh.append((vm, vx))
    master = {vm for vm, _vx in roh}

    kandidaten: dict[str, set[str]] = collections.defaultdict(set)
    veto = 0
    for vm, vx in roh:
        if vx in master or quelle_von.get(vx) == "folder":
            veto += 1
            continue
        a, b = erste.get(vm), erste.get(vx)
        if a is None or b is None or abs((a - b).days) > VORGANG_DUBLETTE_TAGE:
            veto += 1
            continue
        kandidaten[vx].add(vm)
    karte = {vx: next(iter(ms)) for vx, ms in kandidaten.items() if len(ms) == 1}
    mehrdeutig = sum(1 for ms in kandidaten.values() if len(ms) > 1)
    print(f"      Vorgangsdubletten: {len(karte):,} doppelte Vorgaenge zusammengefuehrt · "
          f"{veto:,} durch Veto oder Zeitgrenze gehalten · {mehrdeutig:,} mehrdeutig")
    return karte


def _dubletten(con, land: str, zeilen_n: list) -> set[str]:
    """Welche Bekanntmachungen sind eine Zweitmeldung IM SELBEN VORGANG?

    **Warum ueberhaupt.** `govisor/dedupe.py` erkennt seit langem, wenn zwei Quellen
    dieselbe Vergabe melden, und schreibt das nach `notice_duplicates.parquet`. Die
    Vorgangsebene hat diese Tabelle NIE gelesen. Folge: liegen Master und Zweitmeldung in
    derselben Akte, zaehlt sie beide — im Zuercher Beispiel sieben Zuschlaege fuer sechs
    Lose, eine falsche Zahl an prominenter Stelle.

    ⚠ NUR WENN DER MASTER IN DERSELBEN AKTE LIEGT. Gemessen am 2026-09-02 trifft das auf
    einen kleinen Teil zu: DE 1.545 von 20.786 belegten Dubletten (7 %), AT 404 (1 %),
    CH 5.930 (55 %). Bei allen uebrigen steht der Master in einem ANDEREN Vorgang — dort
    ist die Zweitmeldung das einzige, was diese Vergabe in dieser Akte belegt. Sie zu
    entwerten hiesse, eine Bekanntmachung verschwinden zu lassen, die kein anderer Eintrag
    ersetzt. Dass dieselbe Vergabe dann zweimal als Vorgang existiert, ist ein anderes
    Problem und wird hier NICHT geloest.

    ⚠ WER SELBST MASTER IST, WIRD NICHT ENTWERTET. 456 Bekanntmachungen in DE stehen in der
    einen Zeile als Duplikat und in der naechsten als Master. Ohne diese Sperre koennte eine
    Akte beide Seiten eines Paares verlieren.

    Markiert, nicht geloescht — dieselbe Regel wie in der Firewall selbst: die Bekanntmachung
    bleibt in der Akte und im Verlauf sichtbar, sie zaehlt nur nicht ein zweites Mal.
    """
    d = ROOT / "data" / "gold" / land / "notice_duplicates.parquet"
    if not d.exists():
        return set()
    vorgang_von = {nid: vid for _l, vid, nid, *_r in zeilen_n}
    paare = con.execute(
        f"select distinct master_id, duplicate_id from read_parquet('{d.as_posix()}') "
        f"where beleg = '{DUBLETTEN_BELEG}'").fetchall()
    master = {str(m) for m, _x in paare}
    markiert: set[str] = set()
    for m, x in paare:
        m, x = str(m), str(x)
        if x in master:
            continue
        if vorgang_von.get(x) and vorgang_von.get(x) == vorgang_von.get(m):
            markiert.add(x)
    print(f"      Dubletten: {len(markiert):,} Zweitmeldungen im selben Vorgang markiert "
          f"(von {len({str(x) for _m, x in paare}):,} belegten)")
    return markiert


def _andocken(con, land: str, gruppen: dict, zeilen_n: list) -> dict[str, str]:
    """Vierte Stufe des Wasserfalls: heimatlose Zuschlaege an ihre Ausschreibung.

    **Das Problem.** Ein Zuschlag ohne `ContractFolderID` und ohne Rueckverweis wird zu
    einem eigenen Vorgang. Er sieht dann aus wie eine zweite Vergabe und landet als solche
    in der Kette — gemessen am 2026-09-02: 17 % der Ketten enthielten zwei Glieder mit
    identischem Titel weniger als zwoelf Monate auseinander, also eine Vergabe in Stuecken.

    **Die Regel, und warum sie so eng ist.** Ein Kandidat dockt an, wenn er
      * genau EINE Bekanntmachung hat und KEINE eigene Ausschreibung (`cn`),
      * seinen Schluessel NICHT aus einer amtlichen `ContractFolderID` bezieht,
      * und genau EINE gleichnamige Ausschreibung desselben Kaeufers innerhalb von
        `ANDOCK_TAGE` vor sich findet.
    Passen mehrere, passiert nichts. Ein falsches Zusammenlegen behauptet eine Einheit, die
    es nicht gibt, und ist teurer als ein verpasstes: 47.546 Kandidaten bleiben deshalb
    bewusst liegen.

    ⚠ WARUM NICHT EINFACH „gleicher Kaeufer + gleicher Titel + Zeitfenster". Weil so ein
    Zusammenlegen TRANSITIV wird: A passt zu B, B zu C, C zu D. Ueber ein gleitendes
    Halbjahresfenster entstanden dabei Gruppen von 630, 533 und 462 Vorgaengen — ein
    ganzes Jahrzehnt „d-muenchen: gebaeudereinigung" in einer Akte. Hier gibt es keine
    Transitivitaet: Kandidaten haengen sich an Ziele, Ziele nie aneinander.

    ⚠ EINE EIGENE `ContractFolderID` IST EIN VETO. Traegt der Kandidat eine, hat der
    Auftraggeber selbst gesagt, dass es ein anderes Verfahren ist. 20.380 Kandidaten sind
    dadurch geschuetzt; sie zu ueberstimmen hiesse, eine Schaetzung ueber eine Angabe zu
    stellen.

    ⚠ BRAUCHT `party_entity`. PL und EU fuehren keine — dort greift die Stufe nicht, und
    das ist eine Luecke, keine Eigenschaft (s. `docs/laender/`).
    """
    pe = ROOT / "data" / "gold" / land / "party_entity.parquet"
    if not pe.exists():
        print(f"      Andocken uebersprungen: {land} hat keine party_entity")
        return {}

    fakten: dict[str, tuple] = {}
    for vid, teile in gruppen.items():
        daten = sorted(t[2] for t in teile if t[2])
        aus = [t for t in teile if t[1] == "cn"] or teile
        titel = " ".join(str(aus[0][3] or "").lower().split())
        if not titel or not daten:
            continue
        beste = min((t[0] for t in teile), key=lambda q: RANG[q])
        fakten[vid] = (titel, daten[0], sum(1 for t in teile if t[1] == "cn"),
                       len(teile), beste)

    # ⚠ DIE ZUORDNUNG MUSS AUS DEM LAUFENDEN DURCHGANG KOMMEN. Der erste Entwurf las den
    # Kaeufer ueber `vorgang_notice.parquet` — also ueber die AUSGABE des vorherigen Laufs.
    # Deren Vorgangsnummern sind nicht die, die gerade entstehen; nach jeder Aenderung am
    # Schluessel haette die Stufe stumm ins Leere gegriffen.
    je_notice = {str(a): str(b) for a, b in con.execute(
        f"select notice_id, min(entity_id) from read_parquet('{pe.as_posix()}') "
        "where role = 'buyer' group by 1").fetchall()}
    kaeufer: dict[str, str] = {}
    for _land, vid, nid, *_rest in zeilen_n:
        k = je_notice.get(nid)
        if k and (vid not in kaeufer or k < kaeufer[vid]):
            kaeufer[vid] = k
    if not kaeufer:
        print(f"      Andocken uebersprungen: {land} ohne Kaeuferzuordnung")
        return {}

    nach: dict[tuple, list] = collections.defaultdict(list)
    for vid, (titel, datum, cn, n, beste) in fakten.items():
        k = kaeufer.get(vid)
        if k:
            nach[(k, titel)].append((vid, datum, cn, n, beste))

    karte: dict[str, str] = {}
    mehrdeutig = veto = 0
    for _, liste in nach.items():
        ziele = [x for x in liste if x[2] > 0]
        if not ziele:
            continue
        for vid, datum, cn, n, beste in liste:
            if cn > 0 or n != 1:
                continue
            if beste == "folder":
                veto += 1
                continue
            passend = [z for z in ziele
                       if z[1] <= datum and (datum - z[1]).days <= ANDOCK_TAGE]
            if len(passend) == 1:
                karte[vid] = passend[0][0]
            elif len(passend) > 1:
                mehrdeutig += 1
    print(f"      Andocken: {len(karte):,} heimatlose Zuschlaege zugeordnet · "
          f"{veto:,} durch eigene FolderID geschuetzt · {mehrdeutig:,} mehrdeutig gelassen")
    return karte


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
        gruppen[vid].append((quelle, str(kind or ""), datum, titel, cpv, dok, s_nid))

    # Vierte Stufe: heimatlose Zuschlaege an ihre Ausschreibung. Laeuft NACH der Gruppierung,
    # weil sie Gruppen-Eigenschaften braucht (hat der Vorgang eine eigene Ausschreibung?).
    zeilen_n, gruppen, angedockt = _anwenden(
        _andocken(con, land, gruppen, zeilen_n), zeilen_n, gruppen, zaehle_teile=True)

    # ⚠ FUENFTE STUFE ZWISCHEN VIERTER UND DUBLETTENMARKIERUNG, und die Reihenfolge ist der
    # halbe Nutzen. Erst NACH dem Andocken stehen die endgueltigen Nummern fest; und erst
    # NACHDEM hier zwei doppelte Vorgaenge zusammengefuehrt sind, liegen Master und
    # Zweitmeldung in derselben Akte — wo `_dubletten` sie dann von der Zaehlung ausnimmt.
    # Umgekehrt sortiert waere jede Stufe fuer sich richtig und das Ergebnis trotzdem falsch.
    zeilen_n, gruppen, verschmolzen = _anwenden(
        _vorgangsdubletten(con, land, gruppen, zeilen_n), zeilen_n, gruppen)

    # Zweitmeldungen derselben Vergabe im selben Vorgang. MUSS nach dem Andocken laufen:
    # erst dort landen Master und Zweitmeldung ueberhaupt in einer Akte.
    dubl = _dubletten(con, land, zeilen_n)
    zeilen_n = [(*z, z[2] in dubl) for z in zeilen_n]

    zeilen_v: list = []
    for vid, alle_teile in gruppen.items():
        # ⚠ MARKIERT, NICHT GELOESCHT. Die Zweitmeldung bleibt in `vorgang_notice` und damit
        # im Verlauf der Akte sichtbar — sie zaehlt nur nicht ein zweites Mal. Wer sie
        # wegwirft, verliert die Spur zur zweiten Quelle, und genau die ist der Beleg dafuer,
        # dass wir beide Portale gelesen haben.
        n_dubl = sum(1 for t in alle_teile if t[6] in dubl)
        teile = [t for t in alle_teile if t[6] not in dubl] or alle_teile
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
            dokumente > 0, dokumente, anforderungen, angedockt.get(vid, 0), n_dubl,
            verschmolzen.get(vid, 0)))

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

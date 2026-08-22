"""Dokument-Dubletten: dasselbe Formular wird einmal ausgewertet, nicht hundertmal.

**Warum.** Gemessen am 2026-08-22: von 141.337 Dokumenten im Bestand gibt es nur 86.368
verschiedene Texte. Bei den priorisierten Typen sind **6.773 von 42.407 Dokumenten mehrfach
vorhanden** — zusammen **21.191 sparbare Auswertungen**. Die Wiederholungstäter sind die
Standardformulare: `VHB_124_Eigenerklaerung_zur_Eignung.pdf` liegt in 432 Vergaben,
`VHB_221_Zuschlagskalkulation.pdf` in 267.

**Warum PAARE und nicht Ergebnisse.** Der erste Entwurf war ein Ergebnisspeicher — eine
zweite Kopie der Eintraege neben `doc-analysis.json`, mit eigener Verfallslogik, die
auseinanderlaufen kann. Sven am 22.08.: „kann man die gleiche mechanik nicht wieder
nutzen?". Die Firewall fuer Vergabe-Dubletten (`govisor/dedupe.py`) macht es richtig: sie
schreibt PAARE (`master_id`/`duplicate_id`/`beleg`), markiert statt zu loeschen und laesst
die Quelldaten unberuehrt. Ein Paar bleibt gueltig, egal wie oft sich der Prompt aendert;
eine gespeicherte Extraktion nicht.

⚠ **Der unscharfe Apparat aus `dedupe.py` passt hier NICHT.** Wortmengen, Enthaltungsmass
und Zeitscheiben beantworten „sind zwei VERSCHIEDENE Texte dieselbe Vergabe?". Dokument-
Dubletten sind byteweise identisch — eine Pruefsumme antwortet exakt, wo der unscharfe
Abgleich nur wahrscheinlich antwortet. Uebernommen ist das Muster, nicht der Code.

⚠ **Nur Einzeldokument-Auswertungen taugen als Master.** Die Extraktion laeuft ueber einen
zusammengefuegten Blob je Doktyp, und die Eintraege tragen als `source_file` die ERSTE
Datei des Typs — bei mehreren Dokumenten ist die Zuordnung geraten. Nur wo der Blob aus
genau EINEM Dokument bestand (33 % der Faelle), stammt jeder Eintrag nachweislich daher.
Rueckwirkend erntbar sind so 789 Master, die 6.300 der 21.191 Wiederholungen decken (30 %)
— ohne einen einzigen Modellaufruf.
"""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BELEG = "text_identisch"


def pruefsumme(text: str) -> str:
    return hashlib.md5((text or "").encode()).hexdigest()


def _ziel(country: str) -> Path:
    return ROOT / "data" / "gold" / country / "document_duplicates.parquet"


def finde(country: str = "DE") -> list[dict]:
    """Paare bilden. Master ist, wessen Eintraege eindeutig zuzuordnen sind.

    Gibt Saetze mit derselben Form wie `notice_duplicates.parquet`, ergaenzt um Datei und
    Doktyp — ohne die waere ein Paar nicht aufloesbar.
    """
    import duckdb

    from . import doctypes, docpipe

    src = ROOT / "data" / "docs" / country / "doc_text.parquet"
    analyse = ROOT / "web" / "data" / "doc-analysis.json"
    if not src.exists():
        return []
    fertig = json.loads(analyse.read_text(encoding="utf-8")) if analyse.exists() else {}

    rows = duckdb.sql(f"""select notice_id, file, text from '{src.as_posix()}'
                          where {docpipe.SQL_BRAUCHBAR} and length(text) > 120""").fetchall()
    je: dict[str, list] = collections.defaultdict(list)
    for n, f, t in rows:
        je[n].append((f, t))

    gruppen: dict[tuple, list] = collections.defaultdict(list)
    allein: dict[tuple, tuple] = {}
    for nid, dat in je.items():
        raus = docpipe.ueberholte(f for f, _ in dat)
        pro: dict[str, list] = collections.defaultdict(list)
        for f, t in dat:
            if f in raus:
                continue
            dt = doctypes.classify(f, t)
            if doctypes.is_priority(dt):
                pro[dt].append((f, t))
        for dt, liste in pro.items():
            for f, t in liste:
                gruppen[(dt, pruefsumme(t))].append((nid, f))
            # Master-tauglich: ein Dokument, der Vorgang ist ausgewertet — UND seine
            # Eintraege sind wirklich dieser Datei zugeordnet.
            #
            # ⚠ Die letzte Bedingung ist keine Formsache. Der Doktyp wird HIER mit dem
            # heutigen Klassifikator bestimmt, die Auswertung lief mit dem von gestern;
            # aenderte sich die Einteilung, zeigt `source_file` auf eine andere Datei.
            # Gemessen 2026-08-22: von 789 vermeintlichen Mastern hielten nur **363**
            # (46 %) dem Abgleich stand. Ein Paar ohne belegbaren Master waere ein
            # Versprechen, das beim Auswerten still ins Leere laeuft.
            if len(liste) == 1 and isinstance(fertig.get(nid), dict):
                f, t = liste[0]
                belegt = any(i.get("source_file") == f and not i.get("parser")
                             for i in fertig[nid].get("checklist", []))
                if belegt:
                    allein.setdefault((dt, pruefsumme(t)), (nid, f))

    paare = []
    for (dt, h), vorkommen in gruppen.items():
        if len(vorkommen) < 2:
            continue
        master = allein.get((dt, h))
        if master is None:
            continue                       # kein zuordenbarer Master → kein Paar
        for nid, f in vorkommen:
            if (nid, f) == master:
                continue
            paare.append({"master_id": master[0], "master_file": master[1],
                          "duplicate_id": nid, "duplicate_file": f,
                          "doctype": dt, "pruefsumme": h, "beleg": BELEG})
    return paare


def schreibe(paare: list[dict], country: str = "DE") -> Path:
    """Atomar neben die Golddaten — dieselbe Stelle wie `notice_duplicates.parquet`."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    ziel = _ziel(country)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    felder = ["master_id", "master_file", "duplicate_id", "duplicate_file",
              "doctype", "pruefsumme", "beleg"]
    tab = pa.table({k: pa.array([p.get(k) for p in paare], pa.string()) for k in felder})
    tmp = ziel.with_suffix(".teil")
    pq.write_table(tab, tmp, compression="zstd")
    tmp.replace(ziel)
    return ziel


def karte(country: str = "DE") -> dict[tuple, tuple]:
    """(doctype, pruefsumme) → (master_id, master_file). Leer, wenn es die Datei nicht gibt."""
    ziel = _ziel(country)
    if not ziel.exists():
        return {}
    try:
        import pyarrow.parquet as pq

        t = pq.read_table(ziel)
    except Exception:                                         # noqa: BLE001
        return {}
    aus = {}
    for dt, h, mid, mf in zip(t.column("doctype").to_pylist(),
                              t.column("pruefsumme").to_pylist(),
                              t.column("master_id").to_pylist(),
                              t.column("master_file").to_pylist()):
        aus[(dt, h)] = (mid, mf)
    return aus


MASTER_ITEMS = "document_master_items.parquet"


def _master_datei(country: str) -> Path:
    return ROOT / "data" / "gold" / country / MASTER_ITEMS


def prompt_version() -> str:
    """Fingerabdruck der Extraktionsaufgabe — nur fuer den VORLAUF-Speicher noetig.

    Die Paare selbst brauchen ihn nicht: „diese beiden Texte sind identisch" bleibt wahr,
    egal wie der Prompt aussieht. Wo aber EINTRAEGE liegen, muessen sie verfallen, wenn
    sich die Aufgabe aendert — sonst mischt sich altes Verhalten unbemerkt unter neues.
    """
    from . import docextract

    roh = json.dumps(docextract._TASKS, sort_keys=True, ensure_ascii=False, default=str)
    quelle = Path(docextract.__file__).read_text(encoding="utf-8")
    a, b = quelle.find("def build_messages"), quelle.find("def extract")
    return hashlib.md5((roh + quelle[a:b]).encode()).hexdigest()[:12]


def master_items(country: str = "DE") -> dict[tuple, list]:
    """(doctype, pruefsumme) → Eintraege aus dem Vorlauf. Veraltete Prompt-Version faellt raus."""
    d = _master_datei(country)
    if not d.exists():
        return {}
    try:
        import pyarrow.parquet as pq

        t = pq.read_table(d)
    except Exception:                                         # noqa: BLE001
        return {}
    gueltig = prompt_version()
    return {(dt, h): json.loads(it)
            for dt, h, pv, it in zip(t.column("doctype").to_pylist(),
                                     t.column("pruefsumme").to_pylist(),
                                     t.column("prompt_version").to_pylist(),
                                     t.column("items").to_pylist())
            if pv == gueltig}


def schreibe_master_items(eintraege: dict[tuple, list], country: str = "DE") -> Path:
    """Vorlauf-Ergebnisse ablegen. Bestehende gueltige Eintraege bleiben erhalten."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    alle = {**master_items(country), **eintraege}
    pv = prompt_version()
    ziel = _master_datei(country)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tab = pa.table({
        "doctype": pa.array([k[0] for k in alle], pa.string()),
        "pruefsumme": pa.array([k[1] for k in alle], pa.string()),
        "prompt_version": pa.array([pv] * len(alle), pa.string()),
        "items": pa.array([json.dumps(v, ensure_ascii=False) for v in alle.values()], pa.string()),
    })
    tmp = ziel.with_suffix(".teil")
    pq.write_table(tab, tmp, compression="zstd")
    tmp.replace(ziel)
    return ziel


def items_fuer(doctype: str, text: str, source_file: str, fertig: dict,
               karte_: dict, vorlauf: dict) -> list | None:
    """Die eine Anlaufstelle: erst der Vorlauf, dann der Master aus einer echten Auswertung.

    ⚠ Der Vorlauf zuerst, weil er das Dokument ALLEIN ausgewertet hat — dort ist die
    Zuordnung nicht nur belegt, sondern konstruktionsbedingt eindeutig.
    """
    h = pruefsumme(text)
    treffer = vorlauf.get((doctype, h))
    if treffer:
        return [{**i, "source_file": source_file, "aus_dublette": True} for i in treffer]
    m = karte_.get((doctype, h))
    return items_vom_master(fertig, m[0], m[1], source_file) if m else None


def items_vom_master(fertig: dict, master_id: str, master_file: str,
                     source_file: str) -> list | None:
    """Die Eintraege des Masters, umgeschrieben auf die Datei DIESES Vorgangs.

    ⚠ `source_file` wird ersetzt: der Eintrag muss auf die Datei zeigen, die der Nutzer vor
    sich hat, nicht auf die, bei der er zuerst gefunden wurde. Das Zitat bleibt gueltig —
    der Text ist byteweise identisch, die Belegpflicht (§6a.2) also nicht verletzt.
    """
    v = fertig.get(master_id)
    if not isinstance(v, dict):
        return None
    treffer = [i for i in v.get("checklist", [])
               if i.get("source_file") == master_file and not i.get("parser")]
    if not treffer:
        return None
    return [{**i, "source_file": source_file, "aus_dublette": True} for i in treffer]

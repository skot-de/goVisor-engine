"""Kategorie für Ausschreibungen, deren QUELLE keinen CPV-Code führt.

**Das Problem.** Seit die CPV-Pflicht aus dem Lead-Bau raus ist, stehen Ausschreibungen im
Bestand, die keine Branche tragen — gemessen 2026-08-14 in DE 645 laufende (DÖE 247,
NetServer 398; AT und CH null). Der CPV fehlt nicht der VERGABE, sondern der Quelle:
dieselben Verfahren tragen bei DÖE einen echten Code, die NetServer-Trefferliste führt gar
keinen. Ohne Kategorie landen sie im Sammelbecken „Ohne Kategorie" und werden von jedem
Fachfilter nicht gefunden.

**Der Wasserfall, absteigend nach Belegkraft.** Jede Stufe trägt ihre Herkunft mit, damit
im Produkt sichtbar bleibt, wie sicher die Einordnung ist:

===================  ==========================================  ===========
``quelle``           Woher                                       Belegkraft
===================  ==========================================  ===========
``korrektur``        ein Mensch hat sie korrigiert               höchste
``zwilling``         CPV des Dubletten-Zwillings (veröffentlicht) exakt
``regelwerk``        VOB/A ⇒ Bauleistung (rechtlich definiert)    exakt
``modell``           aus dem Titel abgeleitet, ~82 %              abgeleitet
(keine Zeile)        bleibt „Ohne Kategorie"                      —
===================  ==========================================  ===========

**Warum kein erfundener ``cpv_main``.** Die Modellausgabe landet in einer EIGENEN Tabelle,
nicht im CPV-Raum. Ein geratener CPV würde Branchenzählungen verfälschen und den Lead in
Fachsuchen auftauchen lassen, als wäre er veröffentlicht — genau die falsche Präzision, die
die Projektregel „Erschlossenes trägt Konfidenz" verhindern soll.

**Gemessene Genauigkeit.** 120 Ausschreibungen derselben Quellen, deren CPV wir kennen, dem
Modell ohne den Code vorgelegt: **81 % exakte Division, 82 % richtige Branche**, 1-mal
ehrlich „unbekannt". Die Prüfmenge kommt bewusst aus ``doe``/``netserver`` und nicht aus
TED — sonst misst man den Textstil von TED statt den der Quelle, um die es geht.

Ein Teil der verbleibenden Abweichung ist Rauschen im REFERENZ-CPV, nicht Fehler des
Modells: bei „Reinigungsleistungen Oberschule Jöhstadt" führt der veröffentlichte Code
„Reparatur und Wartung", das Modell sagt „Abwasser, Abfall, Reinigung, Umwelt" — und hat
recht. Die 82 % sind deshalb eine Untergrenze.

**Die Lernschleife.** Korrekturen aus dem Produkt landen in
``curated/<C>_kategorie_korrektur.csv`` — **im Repo**, nicht unter ``data/``. Das ist kein
Detail: ``data/`` ist ein Symlink auf die externe Platte, und dort ist keine einzige Datei
versioniert, auch nicht ``DE_entity_aliases.csv`` mit der von Hand recherchierten
DB-Netz/InfraGO-Aufloesung. Sie wirken doppelt:

1. **Sofort** — die korrigierte Zeile schlägt jede andere Stufe, für genau diese Vergabe.
2. **Auf alles Weitere** — die letzten ``LERN_BEISPIELE`` Korrekturen gehen als Beispiele in
   den Prompt. Das Modell sieht damit, wie DIESES Haus einordnet, nicht nur, was der Katalog
   sagt. Wer „Veranstaltungstechnik" konsequent unter Kultur statt Unternehmensdienste
   führt, bekommt das nach ein paar Korrekturen automatisch.

Die Schleife ist bewusst so gebaut, dass sie NICHTS überschreibt: eine Korrektur ändert die
Ableitung, nicht die Quelldaten, und ist jederzeit rücknehmbar, indem man die Zeile aus der
CSV entfernt.

Aufruf::

    python3 -m govisor.kategorie --country DE            # nur messen, nichts schreiben
    python3 -m govisor.kategorie --country DE --schreiben
"""
from __future__ import annotations
from . import db as _db

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MODELL = "google/gemini-2.5-flash-lite"
URL = "https://openrouter.ai/api/v1/chat/completions"
BATCH = 30
LERN_BEISPIELE = 40        # so viele Korrekturen gehen als Beispiele in den Prompt
TITEL_MAX = 160

# Das Modell DARF „unbekannt" sagen. Ohne diese Möglichkeit raet es bei jedem unklaren Titel
# irgendetwas, und ein falsch einsortierter Lead ist schlimmer als ein unsortierter: er
# taucht in einer Fachsuche auf, in die er nicht gehoert, und verdraengt dort einen echten.
UNBEKANNT = "99"


def _key() -> str | None:
    p = os.environ.get("OPENROUTER_KEY_FILE", str(ROOT / ".secrets" / "openrouter.key"))
    try:
        return Path(p).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def korrektur_pfad(country: str) -> Path:
    """Korrekturen liegen IM REPO, nicht unter ``data/``.

    ``data/`` ist ein Symlink auf die externe Platte — git fasst nichts darunter an.
    Gemessen 2026-08-14: **keine einzige** Datei in ``data/curated/`` ist versioniert,
    auch nicht ``DE_entity_aliases.csv`` mit der von Hand recherchierten
    DB-Netz/InfraGO-Aufloesung. Stirbt die Platte, ist die gesamte menschliche
    Kuratierung weg.

    Fuer die Lernschleife waere das besonders bitter: die Korrekturen SIND der
    aufgebaute Wert — sie steuern nicht nur einzelne Vergaben, sondern ueber den Prompt
    jede kuenftige Ableitung. Sie gehoeren deshalb versioniert.

    Der alte Pfad wird weiter gelesen, falls dort schon etwas liegt; geschrieben wird
    ins Repo. (Dass die uebrigen kuratierten Dateien denselben Umzug brauchen, ist ein
    eigener offener Punkt — hier nur benannt, nicht nebenbei erledigt.)
    """
    repo = ROOT / "curated" / f"{country}_kategorie_korrektur.csv"
    alt = ROOT / "data" / "curated" / f"{country}_kategorie_korrektur.csv"
    return repo if repo.exists() or not alt.exists() else alt


def lade_korrekturen(country: str) -> list[dict]:
    """Menschliche Korrekturen, neueste zuerst.

    Spalten: ``notice_id,division,titel,grund,stand``. ``titel`` und ``grund`` sind für die
    Lernschleife da — das Modell lernt aus dem Titel, der Mensch begründet für den Menschen.
    """
    p = korrektur_pfad(country)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        zeilen = [r for r in csv.DictReader(f) if r.get("notice_id") and r.get("division")]
    zeilen.sort(key=lambda r: r.get("stand") or "", reverse=True)
    return zeilen


def _divisionen(country: str) -> dict[str, tuple[str, str]]:
    p = ROOT / "data" / "gold" / country / "dim_cpv.parquet"
    if not p.exists():                       # dim_cpv ist DE-gepflegt, andere Laender erben sie
        p = ROOT / "data" / "gold" / "DE" / "dim_cpv.parquet"
    rows = _db.connect().execute(
        f"SELECT division, label, branche FROM read_parquet('{p.as_posix()}')").fetchall()
    return {d: (l, b) for d, l, b in rows}


def offene_ohne_kategorie(country: str) -> list[tuple[str, str]]:
    """(notice_id, titel) aller laufenden Ausschreibungen ohne CPV."""
    g = glob.glob(f"{ROOT}/data/silver/{country}/notices/**/*.parquet", recursive=True)
    if not g:
        return []
    return _db.connect().execute(f"""
        SELECT notice_id, title FROM read_parquet({g!r})
        WHERE notice_kind IN ('cn','pin') AND cpv_main IS NULL AND title IS NOT NULL
          AND CAST(submission_deadline AS DATE) >= current_date
    """).fetchall()


def aus_zwilling(country: str) -> dict[str, str]:
    """CPV-Division aus dem Dubletten-Zwilling — veroeffentlicht, also exakt.

    Nur die staerkste Belegstufe. Ein Zwilling auf `nur_titel_kurz` waere bei generischen
    Titeln („Installation von elektrischen Leitungen") reines Rauschen.
    """
    dup = ROOT / "data" / "gold" / country / "notice_duplicates.parquet"
    g = glob.glob(f"{ROOT}/data/silver/{country}/notices/**/*.parquet", recursive=True)
    if not dup.exists() or not g:
        return {}
    rows = _db.connect().execute(f"""
        WITH d AS (SELECT master_id, duplicate_id FROM read_parquet('{dup.as_posix()}')
                   WHERE beleg = 'kaeufer_und_titel'),
             n AS (SELECT notice_id, cpv_main FROM read_parquet({g!r}))
        SELECT ziel, min(substr(cpv, 1, 2)) FROM (
            SELECT d.master_id AS ziel, nq.cpv_main AS cpv
            FROM d JOIN n nz ON nz.notice_id = d.master_id
                   JOIN n nq ON nq.notice_id = d.duplicate_id
            WHERE nz.cpv_main IS NULL AND nq.cpv_main IS NOT NULL
            UNION ALL
            SELECT d.duplicate_id, nq.cpv_main
            FROM d JOIN n nz ON nz.notice_id = d.duplicate_id
                   JOIN n nq ON nq.notice_id = d.master_id
            WHERE nz.cpv_main IS NULL AND nq.cpv_main IS NOT NULL)
        GROUP BY ziel
    """).fetchall()
    return {r[0]: r[1] for r in rows}


def aus_regelwerk(country: str) -> dict[str, str]:
    """VOB/A ⇒ Bauleistung. Keine Schaetzung, sondern die Definition der Vergabeordnung.

    Dieselbe Ableitung benutzen die DTVP- und NetServer-Connectoren bereits fuer `cpv_main`;
    hier greift sie fuer die Saetze, bei denen der Connector sie nicht ziehen konnte.
    """
    a = glob.glob(f"{ROOT}/data/silver/{country}/attributes/**/*.parquet", recursive=True)
    g = glob.glob(f"{ROOT}/data/silver/{country}/notices/**/*.parquet", recursive=True)
    if not a or not g:
        return {}
    rows = _db.connect().execute(f"""
        WITH k AS (SELECT notice_id FROM read_parquet({g!r})
                   WHERE notice_kind IN ('cn','pin') AND cpv_main IS NULL
                     AND CAST(submission_deadline AS DATE) >= current_date)
        SELECT DISTINCT k.notice_id FROM k
        JOIN read_parquet({a!r}) x ON x.notice_id = k.notice_id
        WHERE regexp_matches(lower(x.value), '(^|[^a-z])vob([^a-z]|$)')
    """).fetchall()
    return {r[0]: "45" for r in rows}


def _prompt(kat: dict, beispiele: list[dict]) -> str:
    liste = "\n".join(f"{d} = {l}" for d, (l, _) in sorted(kat.items()))
    txt = ("Du ordnest oeffentliche Ausschreibungen (DE) einer CPV-Division zu. Waehle GENAU "
           "EINE zweistellige Division aus der Liste. Wenn der Titel keine belastbare "
           f"Zuordnung erlaubt, gib \"{UNBEKANNT}\" zurueck — raten ist schaedlicher als ein "
           "ehrliches Unbekannt, weil ein falsch einsortierter Lead in einer Fachsuche "
           "auftaucht, in die er nicht gehoert.\n\n"
           f"DIVISIONEN:\n{liste}\n")
    if beispiele:
        # DIE LERNSCHLEIFE. Korrigierte Faelle als Beispiele — das Modell sieht damit, wie
        # DIESES Haus einordnet, nicht nur, was der Katalog hergibt.
        zeilen = "\n".join(f'"{(b.get("titel") or "")[:TITEL_MAX]}" -> {b["division"]}'
                           for b in beispiele if b.get("titel"))
        if zeilen:
            txt += ("\nFRUEHERE KORREKTUREN durch Fachleute dieses Hauses. Sie gehen im "
                    "Zweifel VOR deiner eigenen Einschaetzung:\n" + zeilen + "\n")
    txt += '\nNur JSON: {"v":[{"id":"..","div":".."}]}'
    return txt


def frag_modell(faelle: list[tuple[str, str]], kat: dict, beispiele: list[dict],
                key: str) -> dict[str, str]:
    """Titel → Division. Fehlschlaege sind LEER, nicht geraten."""
    import requests

    sys_prompt = _prompt(kat, beispiele)
    out: dict[str, str] = {}
    for i in range(0, len(faelle), BATCH):
        teil = faelle[i:i + BATCH]
        body = {"model": MODELL, "temperature": 0,
                "messages": [{"role": "system", "content": sys_prompt},
                             {"role": "user", "content": "\n".join(
                                 f'id={n}: "{(t or "")[:TITEL_MAX]}"' for n, t in teil)}]}
        for versuch in range(3):
            try:
                r = requests.post(URL, headers={"Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json"}, json=body, timeout=120)
                if r.status_code == 200:
                    txt = r.json()["choices"][0]["message"]["content"]
                    txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.M).strip()
                    for v in json.loads(txt).get("v", []):
                        d = str(v.get("div", "")).zfill(2)
                        if d in kat:                     # UNBEKANNT und Muell fallen hier raus
                            out[str(v.get("id"))] = d
                    break
            except Exception as e:
                if versuch == 2:
                    print(f"  Batch-Fehler: {type(e).__name__}: {str(e)[:70]}", flush=True)
        print(f"  {min(i + BATCH, len(faelle))}/{len(faelle)}", flush=True)
    return out


def bestimme(country: str = "DE", mit_modell: bool = True) -> list[dict]:
    """Der Wasserfall. Liefert je Notice hoechstens EINE Zeile, mit ihrer Herkunft."""
    kat = _divisionen(country)
    offen = offene_ohne_kategorie(country)
    if not offen:
        return []
    print(f"  {len(offen):,} laufende Ausschreibungen ohne CPV")

    korr = {k["notice_id"]: k["division"] for k in lade_korrekturen(country)}
    zwi = aus_zwilling(country)
    reg = aus_regelwerk(country)

    stand = dt.date.today().isoformat()
    zeilen: list[dict] = []
    offen_fuers_modell: list[tuple[str, str]] = []
    for nid, titel in offen:
        for quelle, tabelle in (("korrektur", korr), ("zwilling", zwi), ("regelwerk", reg)):
            if nid in tabelle and tabelle[nid] in kat:
                zeilen.append(dict(notice_id=nid, division=tabelle[nid],
                                   branche=kat[tabelle[nid]][1], quelle=quelle,
                                   modell=None, stand=stand))
                break
        else:
            offen_fuers_modell.append((nid, titel))

    print("  " + " · ".join(
        f"{q} {sum(1 for z in zeilen if z['quelle'] == q):,}"
        for q in ("korrektur", "zwilling", "regelwerk")))

    if mit_modell and offen_fuers_modell:
        key = _key()
        if not key:
            print("  ⚠ kein OpenRouter-Schluessel — Modellstufe uebersprungen.")
        else:
            beispiele = lade_korrekturen(country)[:LERN_BEISPIELE]
            if beispiele:
                print(f"  Lernschleife: {len(beispiele)} Korrekturen im Prompt")
            for nid, d in frag_modell(offen_fuers_modell, kat, beispiele, key).items():
                zeilen.append(dict(notice_id=nid, division=d, branche=kat[d][1],
                                   quelle="modell", modell=MODELL, stand=stand))
    rest = len(offen) - len(zeilen)
    print(f"  modell {sum(1 for z in zeilen if z['quelle'] == 'modell'):,}"
          f" · bleibt Ohne Kategorie {rest:,}")
    return zeilen


def schreibe(zeilen: list[dict], country: str = "DE") -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    ziel = ROOT / "data" / "gold" / country / "lead_kategorie.parquet"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema([("notice_id", pa.string()), ("division", pa.string()),
                        ("branche", pa.string()), ("quelle", pa.string()),
                        ("modell", pa.string()), ("stand", pa.string())])
    pq.write_table(pa.Table.from_pylist(zeilen, schema=schema), ziel, compression="zstd")
    return ziel


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Kategorie fuer Ausschreibungen ohne CPV")
    ap.add_argument("--country", default="DE")
    ap.add_argument("--schreiben", action="store_true", help="Ergebnis nach Gold schreiben")
    ap.add_argument("--ohne-modell", action="store_true",
                    help="nur die belegten Stufen, keine Modell-Ableitung")
    a = ap.parse_args(argv)
    print(f"Kategorie-Ableitung {a.country}")
    zeilen = bestimme(a.country, mit_modell=not a.ohne_modell)
    if not zeilen:
        print("  nichts abzuleiten.")
        return 0
    if a.schreiben:
        print(f"→ {schreibe(zeilen, a.country)}")
    else:
        print("  (Probelauf — mit --schreiben wird gespeichert)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
BATCH = 30
LERN_BEISPIELE = 40        # so viele Korrekturen gehen als Beispiele in den Prompt
TITEL_MAX = 160

# Das Modell DARF „unbekannt" sagen. Ohne diese Möglichkeit raet es bei jedem unklaren Titel
# irgendetwas, und ein falsch einsortierter Lead ist schlimmer als ein unsortierter: er
# taucht in einer Fachsuche auf, in die er nicht gehoert, und verdraengt dort einen echten.
UNBEKANNT = "99"


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
    txt += ('\nJede Eingabezeile lautet `id=<kennung> | "<titel>"`. Gib die Kennung '
            'unveraendert zurueck; sie kann selbst Doppelpunkte enthalten.'
            '\nNur JSON: {"v":[{"id":"..","div":".."}]}')
    return txt


def frag_modell(faelle: list[tuple[str, str]], kat: dict,
                beispiele: list[dict]) -> dict[str, str]:
    """Titel → Division. Fehlschlaege sind LEER, nicht geraten.

    ⚠ **UEBER `llm.chat`, NICHT MIT EIGENEM `requests.post`.** Bis zum 2026-09-04 stand hier
    ein eigener Aufruf gegen `openrouter.ai/api/v1/chat/completions`, mit eigenem
    Schluessel-Leser und eigener Wiederholschleife. Das lief damit an drei Einrichtungen
    vorbei, die es fuer genau diesen Zweck gibt:

      · der **Geldwache** — der Tagesdeckel und die Reserve in `llm._geldwache()` galten
        fuer diesen Weg nicht. Er konnte das Guthaben leerlaufen lassen, waehrend die
        gebremsten Wege sich fuer geschuetzt hielten.
      · dem **Kostenbuch** — die Buchungen fehlten. Die naechtliche Modellmarkt-Rechnung
        („Mischung 3.0:1 Eingabe/Ausgabe, gemessen an 24.455 Buchungen") stand damit auf
        unvollstaendigen Zahlen, und `kostenbericht.py` unterschaetzte die Ausgaben.
      · dem **Bodenpreis** — `llm.mit_boden()` waehlt denselben Modellnamen beim guenstigeren
        Anbieter (gemessen: halber Preis). Dieser Weg zahlte Listenpreis.

    Gemessen im Lauf vom 2026-09-04: 1.179 Titel, 40 Stapel, jede Nacht. Kein grosser Betrag,
    aber unsichtbar — und eine Bremse, an der ein Weg vorbeifuehrt, ist keine Bremse.

    Der frühere Parameter `key` ist weg: `llm` liest seine Schlüssel selbst und kann
    rotieren. Ihn tot mitzuschleppen hätte den nächsten Leser glauben lassen, hier werde
    noch ein eigener Schlüssel gebraucht.
    """
    from . import llm

    sys_prompt = _prompt(kat, beispiele)
    out: dict[str, str] = {}
    verworfen: list[str] = []      # Kennungen, die so nicht gesendet wurden
    for i in range(0, len(faelle), BATCH):
        teil = faelle[i:i + BATCH]
        # ⚠ TRENNZEICHEN, DAS IN KEINER KENNUNG VORKOMMT. Hier stand `id={n}: "..."` —
        # und NetServer-Kennungen tragen selbst Doppelpunkte (`ns:he:6559bb29329c3878`).
        # Die Zeile lautete damit `id=ns:he:6559bb29329c3878: "Titel"`, und das Modell
        # musste raten, wo die Kennung endet. Gemessen am 2026-08-25 im Bestand: von 499
        # modellabgeleiteten NetServer-Zeilen trugen **60** einen Doppelpunkt zu viel
        # (12 %). Kennungen ohne Doppelpunkt (TED, DOeE) waren zu 0 von 1.199 betroffen.
        erlaubt = {n for n, _ in teil}
        nachricht = [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": "\n".join(
                         f'id={n} | "{(t or "")[:TITEL_MAX]}"' for n, t in teil)}]
        try:
            with llm.kontext(zweck="kategorie"):
                txt = llm.chat(nachricht, model=MODELL, temperature=0,
                               timeout=120, max_retries=3)
        except llm.BudgetErschoepft as e:
            # ⚠ NICHT WEITERSTAPELN. Die Wache ist klebrig: einmal gefallen, wirft jeder
            # weitere Aufruf sofort. Vierzig Stapel durchzulaufen, die alle scheitern,
            # erzeugt vierzig gleiche Zeilen und verdeckt den einen Grund.
            print(f"  Budget erschoepft, Ableitung abgebrochen: {e}", flush=True)
            break
        except Exception as e:                                  # noqa: BLE001
            print(f"  Batch-Fehler: {type(e).__name__}: {str(e)[:70]}", flush=True)
            # ⚠ NICHT JEDER FEHLSCHLAG IST VORUEBERGEHEND — aber auch nicht jeder ist
            # endgueltig. `AllKeysExhausted` faellt schon bei einem haengenden Endpunkt,
            # das waere ein schlechter Grund, vierzig Stapel abzublasen. Endgueltig ist
            # es erst, wenn KEIN Schluessel mehr kann; ein 402 mustert ihn prozessweit aus.
            # Also das echte Signal fragen statt die Ausnahme zu deuten.
            if not llm.available_keys():
                print("  kein nutzbarer Schluessel mehr — Ableitung abgebrochen.", flush=True)
                break
            print(f"  {min(i + BATCH, len(faelle))}/{len(faelle)}", flush=True)
            continue
        try:
            txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.M).strip()
            for v in json.loads(txt).get("v", []):
                d = str(v.get("div", "")).zfill(2)
                if d not in kat:                 # UNBEKANNT und Muell fallen hier raus
                    continue
                # ⚠ DIE KENNUNG AUS DER ANTWORT IST NICHT VERTRAUENSWUERDIG. Sie
                # wurde bisher ungeprueft uebernommen und landete so in einer
                # Gold-Tabelle, in der sie auf NICHTS zeigte — 60 Leads mit
                # ermittelter Branche, die im Produkt „Ohne Kategorie" blieben,
                # weil der Join ins Leere lief. Ein Schluessel, den ein Modell
                # zurueckgibt, gehoert gegen die gesendete Menge geprueft.
                roh = str(v.get("id", ""))
                nid = roh if roh in erlaubt else roh.strip().rstrip(":")
                if nid in erlaubt:
                    out[nid] = d
                else:
                    verworfen.append(roh)
        except Exception as e:                                  # noqa: BLE001
            # Eine unlesbare Antwort ist ein leerer Stapel, kein Abbruch — dieselbe Regel
            # wie oben im Kopf: „Fehlschlaege sind LEER, nicht geraten."
            print(f"  Antwort unlesbar: {type(e).__name__}: {str(e)[:70]}", flush=True)
        print(f"  {min(i + BATCH, len(faelle))}/{len(faelle)}", flush=True)
    if verworfen:
        # Laut sagen, nicht stillschweigend schlucken: wer das Trennzeichen oder den
        # Prompt aendert, soll es hier sehen und nicht erst Wochen spaeter an einer
        # Gold-Tabelle, die auf nichts zeigt.
        print(f"  ⚠ {len(verworfen)} Antwort-Kennungen gehoerten nicht zur Anfrage und "
              f"wurden verworfen (z. B. {verworfen[0]!r})", flush=True)
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
        # ⚠ ÜBER `llm`, NICHT ÜBER EINE EIGENE SCHLÜSSELDATEI. Der frühere `_key()` las nur
        # `.secrets/openrouter.key` — den EINEN Schlüssel. `llm` kennt zusätzlich die
        # Mehrfachdatei und mustert leergelaufene aus; wer selbst liest, meldet „kein
        # Schlüssel", während `llm` noch zwei hätte, oder umgekehrt.
        from . import llm as _llm
        if not _llm.available_keys():
            print("  ⚠ kein OpenRouter-Schluessel — Modellstufe uebersprungen.")
        else:
            beispiele = lade_korrekturen(country)[:LERN_BEISPIELE]
            if beispiele:
                print(f"  Lernschleife: {len(beispiele)} Korrekturen im Prompt")
            for nid, d in frag_modell(offen_fuers_modell, kat, beispiele).items():
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

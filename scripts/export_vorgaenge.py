#!/usr/bin/env python3
"""Vorgangsakten → web/data/vorgang/<sha1>.json (+ Bestand, + Nachschlagewerk)

**Warum.** `data/gold/<L>/vorgaenge.parquet` führt seit dem 2026-09-01 1,47 Mio. Vorgänge:
Ausschreibung, Korrekturen, Zuschlag und die zugehörigen Unterlagen unter EINER Nummer.
Gelesen hat sie bis heute niemand — es gab keinen Weg ins Produkt. Dieses Skript legt ihn.

⚠ NICHT ALLE 1,47 MIO. Die Akten zusammen sind rund 6 MB je 36.000 Stück; die volle Menge
wären ~250 MB in 1,5 Mio. Dateien. Exportiert wird deshalb die **Produktmenge**: jeder
Vorgang, der eine heute ausgeschriebene Vergabe enthält, plus alle Glieder der Ketten, in
denen diese Vorgänge stehen. Die Vorgeschichte eines offenen Rahmenvertrags gehört dazu —
sie ist der eigentliche Grund für die Ansicht. Der Rest bleibt in Gold und wartet auf eine
Abfrageschicht (Supabase oder eine Route mit DuckDB), die es heute nicht gibt.

⚠ WAS DIE AKTE NICHT KANN, MUSS SIE SAGEN. Gemessen am 2026-09-02 über alle 1,47 Mio.:

    mit Zuschlag                    730.755   (49,6 %)
    mehr als eine Bekanntmachung    492.020   (33,4 %)
    mit Korrektur                    60.156   ( 4,1 %)
    mit Unterlagen                    8.868   ( 0,6 %)   ← der Dokumentenschenkel

Der Dokumentenschenkel ist dünn und wird nur nach vorn dichter: Unterlagen holen wir erst
seit August 2026 ein, rückwirkend gibt sie kein Portal heraus. Eine Akte von 2015 hat
deshalb Bekanntmachungen und Zuschlag, aber fast nie Dateien. Jede Anzeige muss das
unterscheiden können — dafür steht `unterlagen` an jedem Verlaufseintrag und nicht nur
eine Gesamtzahl oben.

Aufruf: python3 scripts/export_vorgaenge.py [--land DE]
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "web" / "data"
JE_VORGANG = OUT / "vorgang"
LISTINGS = OUT / "doc-listing"

# Mehr Dateinamen als das trägt keine Ansicht sinnvoll; die längste Liste hat 486.
# Die Gesamtzahl steht daneben, es geht also nichts verloren ausser der Auflistung.
MAX_DATEIEN = 60

# ⚠ DAS SIND DIE ECHTEN WERTE AUS `vorgang_notice.notice_kind`, nicht die Spaltennamen aus
# `vorgaenge`. Der erste Lauf am 2026-09-02 setzte hier "ausschreibung"/"zuschlag" — also die
# Namen der ZAEHLSPALTEN — und die Ansicht haette „cn" und „can" angezeigt. Zwei Vokabulare
# fuer dieselbe Sache, eines davon geraten.
ARTEN = {"cn": "Ausschreibung", "can": "Zuschlag", "corrigendum": "Korrektur",
         "pin": "Vorinformation", "other": "Weitere Bekanntmachung"}

# Wie viele Kettenglieder eine Akte mitfuehrt (um die eigene Position herum).
#
# ⚠ WARUM UEBERHAUPT EINE GRENZE. Ohne sie traegt jede Akte jedes Glied ihrer Kette. Die
# laengste Kette hat 435 Glieder, p99 sind 223 — das schreibt 435 Titel in 435 Dateien,
# 189.225 Kopien fuer EINE Kette. Der erste Lauf kam so auf 153 MB. Es ist ausserdem keine
# Anzeige: 435 Vorlaeufer liest niemand. Die Gesamtzahl steht daneben, es fehlt also nichts
# ausser der Auflistung.
KETTE_FENSTER = 12

# Wie viele Zeichen des Aktenhashes den Buendelnamen bilden: 2 → 256 Buendel.
# MUSS mit `web/lib/vorgangsakte.ts` uebereinstimmen.
BUENDEL_STELLEN = 2

# Wie belastbar eine Kette ist, in drei Baendern: (Untergrenze, Name).
#
# ⚠ DIE BAENDER STEHEN IN DEN DATEN, NICHT IM RENDERER. Sonst kennt die Anzeige eine
# Schwelle, die der Export nicht kennt, und beide laufen beim naechsten Anfassen
# auseinander — dieselbe Regel wie bei `export_schwellen.py`.
#
# ⚠ UND SIE SIND GEMESSEN, NICHT GERATEN. Die Verteilung der 189.000 Kanten hat drei klare
# Spitzen: 28.538 bei genau 0,70 (das ist `llm_adjudicated`, pauschal), 8.096 bei 0,80 und
# 28.520 bei 0,95 (beides `content_unique`), darunter eine diffuse Masse von 0,55 bis 0,69.
# Zwei Baender waeren zu grob, vier haetten keine Entsprechung in den Daten.
KETTE_GUETE = ((0.80, "belastbar"), (0.70, "plausibel"), (0.0, "schwach"))

# Unterhalb dieser Grenze wird ein einzelnes Glied als duenn gekennzeichnet.
GLIED_DUENN = 0.70

# Ab wann wir Vergabeunterlagen ueberhaupt abrufen. Vorher gibt es keine, und kein Portal
# gibt sie rueckwirkend heraus.
#
# ⚠ DIESES DATUM ENTSCHEIDET, WELCHE ERKLAERUNG STIMMT. Der erste Entwurf schob eine
# fehlende Dateiliste IMMER aufs Alter — und behauptete das am 2026-09-02 auch bei 7.453
# Akten, die von August 2026 oder spaeter sind. Einer Vergabe vom 26.08.2026 zu sagen,
# aeltere Vorgaenge haetten deshalb selten Dateien, ist schlicht falsch.
ABRUF_START = "2026-08-01"


def dateiname(land: str, vorgang_id: str) -> str:
    """Land + Vorgangsnummer → Dateiname. Muss in `web/lib/vorgangsakte.ts` identisch sein.

    Hash aus demselben Grund wie bei `export_firma_profiles.dateiname`: die Nummern sehen
    `folder:BA090-26` und `pub:123456-2015` aus. Die sonst übliche Säuberung
    `[^A-Za-z0-9_-]` → "" macht aus `folder:ab-1` und `folder:ab1` denselben Dateinamen,
    und die eine Akte überschreibt die andere lautlos.

    ⚠ WARUM DAS LAND MIT IN DEN SCHLUESSEL MUSS. Die Nummer allein ist NICHT weltweit
    eindeutig. Gemessen am 2026-09-02 über alle fünf Länder mit Vorgängen: 48 Nummern
    kommen in mehr als einem Land vor (AT∩DE 31, CH∩DE 9, DE∩PL 4, dazu drei einzelne).
    Ohne das Land im Hash überschreibt die österreichische Akte die deutsche, und zwar
    lautlos — dieselbe Kollision, gegen die der Hash überhaupt eingeführt wurde, nur eine
    Ebene höher.
    """
    return hashlib.sha1(f"{land}:{vorgang_id}".encode("utf-8")).hexdigest()


def _temp(con: duckdb.DuckDBPyConnection, name: str, spalte: str, werte) -> None:
    """Menge → temporäre Tabelle.

    ⚠ `executemany` wirft bei einer LEEREN Liste, statt nichts zu tun. Beide Aufrufstellen
    hatten den Fall, und beide sahen harmlos aus: ein Land ohne sichtbare Leads (PL) und
    ein Land ohne passende Vorgaenge. Der Lauf starb an Land fuenf und liess die Akten der
    Laender eins bis vier ungeschrieben — nachdem er sie bereits berechnet hatte.
    """
    con.execute(f"create or replace temp table {name} ({spalte} varchar)")
    liste = sorted(werte)
    if liste:
        con.executemany(f"insert into {name} values (?)", [(w,) for w in liste])


def _sichtbare_leads() -> set[str]:
    """Die Vergaben, die der Explorer wirklich zeigt.

    ⚠ NICHT `lead_export.parquet`. Das fuehrt 90.272 Leads, `web/data/leads-*.json` nur
    42.678 — der Web-Export filtert danach noch einmal auf das, was heute offen ist. Der
    erste Lauf nahm die Parquet-Menge und baute damit Akten fuer 48.000 Vergaben, die im
    Produkt niemand aufrufen kann.

    Die Kopplung an die Ausgabedatei ist Absicht: sie ist die einzige Stelle, an der die
    Sichtbarkeitsregel wirklich steht. Sie hier zu wiederholen hiesse, sie zweimal zu
    pflegen. Im Tageslauf laeuft `export_web_leads.py` davor.
    """
    ids: set[str] = set()
    for p in sorted((OUT).glob("leads-*.json")):
        try:
            roh = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for l in (roh if isinstance(roh, list) else roh.get("leads", [])):
            if isinstance(l, dict) and l.get("id"):
                ids.add(str(l["id"]))
    return ids


def _menge(con: duckdb.DuckDBPyConnection, land: str, sichtbar: set[str]) -> set[str]:
    """Die Produktmenge eines Landes: Vorgänge sichtbarer Vergaben + ihre Ketten."""
    g = f"data/gold/{land}"
    if not sichtbar:
        return set()
    _temp(con, "_l", "lead_id", sichtbar)
    menge = {r[0] for r in con.execute(f"""
        select distinct vn.vorgang_id
        from read_parquet('{g}/vorgang_notice.parquet') vn
        join _l l on l.lead_id = vn.notice_id
    """).fetchall()}
    vorher = len(menge)
    # Ein Land ohne Treffer ist der Normalfall, kein Fehler: PL hat Vorgaenge in Gold, aber
    # keinen einzigen sichtbaren Lead.
    if not menge:
        print(f"  {land}: {len(sichtbar):,} sichtbare Leads → kein Vorgang, uebersprungen")
        return menge
    _temp(con, "_v0", "vorgang_id", menge)
    menge |= {r[0] for r in con.execute(f"""
        select distinct k2.vorgang_id
        from read_parquet('{g}/vorgang_kette.parquet') k1
        join read_parquet('{g}/vorgang_kette.parquet') k2 on k2.kette_id = k1.kette_id
        join _v0 v on v.vorgang_id = k1.vorgang_id
    """).fetchall()}
    print(f"  {land}: {len(sichtbar):,} sichtbare Leads → {vorher:,} Vorgaenge, "
          f"+{len(menge) - vorher:,} aus deren Ketten → {len(menge):,}")
    return menge


def _listing(notice_id: str) -> dict | None:
    """Die Dateiliste einer Bekanntmachung, falls ein Portal sie hergegeben hat."""
    p = LISTINGS / f"{notice_id}.json"
    if not p.exists():
        return None
    try:
        roh = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    dateien = roh.get("dateien") or []
    return {
        "notice": notice_id,
        "quelle": roh.get("quelle"),
        "url": roh.get("url"),
        "gelesen": bool(roh.get("gelesen")),
        "n": roh.get("n") or len(dateien),
        "dateien": dateien[:MAX_DATEIEN],
        "gekuerzt": max(0, len(dateien) - MAX_DATEIEN),
    }


def _unterlagen_grund(akte: dict) -> str | None:
    """Warum zu diesem Vorgang keine Dateiliste vorliegt. `None`, wenn eine vorliegt.

    Drei verschiedene Gruende, die alle „keine Unterlagen" heissen und in der Anzeige
    verschiedene Saetze verdienen:

      angekuendigt    Die Vergabe weist Unterlagen aus, wir haben die Liste nicht geholt.
      vor_abrufstart  Der Vorgang liegt vor `ABRUF_START` — es gibt schlicht keine.
      kein_abruf      Der Vorgang ist neu genug, aber kein Portal hat eine Liste hergegeben.

    ⚠ DIE DRITTE ZEILE IST DER GRUND FUER DIESE FUNKTION. Ohne sie bekamen 7.453 aktuelle
    Vorgaenge die Alters-Erklaerung, die auf sie nicht zutrifft.
    """
    if akte["dokumente"]:
        return None
    if any(e["unterlagen"] for e in akte["verlauf"]):
        return "angekuendigt"
    return "vor_abrufstart" if (akte["bis"] or "") < ABRUF_START else "kein_abruf"


def _verlauf(teile: list[dict]) -> list[dict]:
    """Bekanntmachungen → Verlauf, gleiche Art am gleichen Tag zu EINEM Eintrag.

    ⚠ WARUM ZUSAMMENFASSEN. Korrekturen kommen in Schüben: eine Vergabe mit 14 Korrekturen
    hat sie typischerweise an drei Tagen veröffentlicht, weil jede geänderte Frist eine
    eigene Bekanntmachung erzeugt. Ungruppiert liest sich der Verlauf wie 14 Ereignisse und
    die eine Ausschreibung darunter verschwindet. Gruppiert sind es drei Änderungen — was
    tatsächlich passiert ist.
    """
    nach_tag: dict[tuple, list[dict]] = defaultdict(list)
    for t in teile:
        nach_tag[(t["veroeffentlicht"], t["notice_kind"])].append(t)
    verlauf = []
    for (datum, art), gruppe in sorted(nach_tag.items(),
                                       key=lambda kv: (kv[0][0] or "", kv[0][1])):
        verlauf.append({
            "datum": _tag(datum),
            "art": art,
            "label": ARTEN.get(art, art),
            "n": len(gruppe),
            "ids": sorted(t["notice_id"] for t in gruppe),
            "unterlagen": any(t["hat_unterlagen"] for t in gruppe),
        })
    return verlauf


def _guete(min_konfidenz: float | None) -> str | None:
    """Konfidenz des schwaechsten Glieds → Band. `None`, wenn es keine Zahl gibt.

    Eine Kette ist so belastbar wie ihr schwaechstes Glied; deshalb entscheidet das Minimum
    und nicht der Durchschnitt. Ein Durchschnitt verwischt genau den Fall, um den es geht:
    vier gute Verknuepfungen und eine geratene sehen darin aus wie fuenf mittelmaessige.
    """
    if min_konfidenz is None:
        return None
    for grenze, name in KETTE_GUETE:
        if min_konfidenz >= grenze:
            return name
    return KETTE_GUETE[-1][1]


def _fenster(glieder: list[dict], position: int) -> list[dict]:
    """Die KETTE_FENSTER Glieder um die eigene Position herum, Reihenfolge erhalten.

    Am Rand wandert das Fenster nach innen, statt zu schrumpfen: wer an Position 1 einer
    langen Kette steht, will die Nachfolger sehen, nicht sechs leere Plaetze davor.
    """
    if len(glieder) <= KETTE_FENSTER:
        return [dict(g) for g in glieder]
    mitte = next((i for i, g in enumerate(glieder) if g["position"] == position), 0)
    start = max(0, min(mitte - KETTE_FENSTER // 2, len(glieder) - KETTE_FENSTER))
    return [dict(g) for g in glieder[start:start + KETTE_FENSTER]]


def _tag(wert) -> str | None:
    """Datum als `YYYY-MM-DD`.

    ⚠ `str(wert)` allein reicht nicht: dieselbe Spalte kommt ueber `.df()` als Timestamp
    (`2025-08-08 00:00:00`) und ueber `fetchall()` als `date` (`2025-08-08`) zurueck. Der
    erste Lauf hatte beide Formen in EINER Akte — oben am Zeitraum die lange, unten im
    Verlauf die kurze.
    """
    if wert is None:
        return None
    return str(wert)[:10] or None


def _akten(con: duckdb.DuckDBPyConnection, land: str,
           menge: set[str]) -> dict[tuple[str, str], dict]:
    g = f"data/gold/{land}"
    _temp(con, "_m", "vorgang_id", menge)

    # ⚠ KEIN `.df()` HIER. Ueber pandas wird aus jedem fehlenden Wert ein `float('nan')`,
    # und `json.dumps` schreibt dafuer das nackte `NaN` in die Datei — Python erlaubt das,
    # JSON nicht. Ergebnis am 2026-09-02: 256 gueltig aussehende Buendel, von denen der
    # Browser jedes zweite nicht lesen konnte (`"cpv": NaN`). Der Export meldete Erfolg,
    # die Tests waren gruen; gefunden hat es erst ein Blick auf die Seite.
    ergebnis = con.execute(f"""
        select v.* from read_parquet('{g}/vorgaenge.parquet') v
        join _m m on m.vorgang_id = v.vorgang_id
    """)
    spalten = [b[0] for b in ergebnis.description]
    kopf = [dict(zip(spalten, zeile)) for zeile in ergebnis.fetchall()]

    teile = defaultdict(list)
    for r in con.execute(f"""
        select vn.vorgang_id, vn.notice_id, vn.notice_kind, vn.jahr,
               vn.veroeffentlicht, vn.hat_unterlagen
        from read_parquet('{g}/vorgang_notice.parquet') vn
        join _m m on m.vorgang_id = vn.vorgang_id
    """).fetchall():
        teile[r[0]].append({"notice_id": r[1], "notice_kind": r[2], "jahr": r[3],
                            "veroeffentlicht": r[4], "hat_unterlagen": r[5]})

    ketten: dict[str, dict] = {}
    kette_glieder = defaultdict(list)
    for r in con.execute(f"""
        select k.kette_id, k.vorgang_id, k.position, k.n_glieder, k.jahr,
               k.konfidenz_zum_vorgaenger, k.min_konfidenz, k.methode, k.dauerangebot,
               k.vorgaenger
        from read_parquet('{g}/vorgang_kette.parquet') k
        join _m m on m.vorgang_id = k.vorgang_id
    """).fetchall():
        ketten[r[1]] = {"kette": r[0], "position": r[2], "n_glieder": r[3],
                        "min_konfidenz": r[6], "methode": r[7], "dauerangebot": bool(r[8])}
        kette_glieder[r[0]].append({"vorgang": r[1], "position": r[2], "jahr": r[4],
                                    "konfidenz": r[5], "vorgaenger": r[9]})

    titel = {k["vorgang_id"]: k.get("titel") for k in kopf}
    akten = {}
    for k in kopf:
        vid = k["vorgang_id"]
        meine = teile.get(vid, [])
        akte = {
            "id": vid,
            "land": land,
            "titel": k.get("titel"),
            "cpv": k.get("cpv"),
            "schluessel": k.get("schluessel_quelle"),
            "vollstaendig": bool(k.get("vollstaendig")),
            "von": _tag(k.get("erste_veroeffentlichung")),
            "bis": _tag(k.get("letzte_veroeffentlichung")),
            "zahlen": {a: int(k.get(f"n_{a}") or 0)
                       for a in ("bekanntmachungen", "ausschreibung", "zuschlag",
                                 "korrektur", "vorinfo", "dokumente", "anforderungen",
                                 # ⚠ MUSS SICHTBAR SEIN. Zuschlaege, die ueber Kaeufer und
                                 # Titel zugeordnet wurden, sind erschlossen und nicht
                                 # amtlich verknuepft — wie bei der Kette gehoert das an die
                                 # Oberflaeche und nicht nur in die Tabelle.
                                 "angedockt")},
            "verlauf": _verlauf(meine),
            "dokumente": [d for d in (_listing(t["notice_id"]) for t in meine) if d],
        }
        akte["unterlagen_grund"] = _unterlagen_grund(akte)
        if vid in ketten:
            kk = dict(ketten[vid])
            alle = sorted(kette_glieder[kk["kette"]], key=lambda x: x["position"])
            fenster = _fenster(alle, kk["position"])
            for gl in fenster:
                gl["titel"] = titel.get(gl["vorgang"])
            # ⚠ DIE ZEILE DARUEBER IST NICHT ZWANGSLAEUFIG DER VORGAENGER. Sortiert wird
            # nach Jahr; in 3.189 Faellen zeigt die erschlossene Nachfolge rueckwaerts in
            # der Zeit. Ohne diese Pruefung setzt die Anzeige ihr „hier duenn" an einen
            # Uebergang, den es so nicht gibt — sie sagt dann etwas Falsches, nicht nur
            # etwas Ungenaues.
            jahr_von = {g["vorgang"]: g["jahr"] for g in alle}
            for i, gl in enumerate(fenster):
                # Am einzelnen Glied, nicht nur oben: die Kette kann an genau EINER Stelle
                # duenn sein, und dann will man wissen, an welcher.
                gl["duenn"] = (gl["konfidenz"] is not None
                               and gl["konfidenz"] < GLIED_DUENN)
                gl["wurzel"] = gl["vorgaenger"] is None
                davor = fenster[i - 1]["vorgang"] if i > 0 else None
                gl["anschluss_direkt"] = gl["vorgaenger"] is not None and gl["vorgaenger"] == davor
                gl["vorgaenger_jahr"] = jahr_von.get(gl["vorgaenger"])
            kk["glieder"] = fenster
            kk["gekuerzt"] = len(alle) - len(fenster)
            kk["guete"] = _guete(kk["min_konfidenz"])
            # ⚠ Das schwaechste Glied kann AUSSERHALB des Fensters liegen. Dann traegt die
            # Kette zu Recht ein schwaches Band, ohne dass ein sichtbares Glied markiert
            # ist — die Anzeige muss das sagen koennen, statt widerspruechlich auszusehen.
            kk["duennes_glied_sichtbar"] = any(g["duenn"] for g in fenster)
            akte["kette"] = kk
        akten[(land, vid)] = akte
    return akten


def schreibe(akten: dict[tuple[str, str], dict], nachschlag: dict[str, str]) -> None:
    """Die Akten in 256 Buendel, nicht in 53.872 Einzeldateien.

    ⚠ WARUM NICHT EINE DATEI JE AKTE, wie bei `firma/` und `doc-analysis/`. Dort sind es
    38.307 bzw. 8.106 Stueck; zusammen mit den 53.872 Akten stuenden rund 156.000 Dateien
    unter `web/data`, und `next build` starb daran reproduzierbar im Node-Heap (SIGABRT,
    Stapel in `node::fs::AfterStat`) — Next geht beim Bauen den Projektbaum ab. Mit
    `--max-old-space-size=8192` lief er wieder, aber ein hochgedrehter Heap verschiebt die
    Grenze nur; die Zahl der Akten waechst mit jedem Land und jedem Jahr weiter.

    ⚠ UND WARUM NICHT EINE EINZIGE SAMMELDATEI. Genau daran ist `firma-profiles.json`
    gescheitert: 67 MB laden, um 1,6 KB zu liefern. Ein Buendel ist im Median 150 KB gross
    und damit die richtige Ladeeinheit zwischen beiden Fehlern.

    Der Buendelname sind die ersten zwei Zeichen des Aktenhashes — dieselbe Funktion, die
    `web/lib/vorgangsakte.ts` benutzt, also kann nichts auseinanderlaufen.
    """
    JE_VORGANG.mkdir(parents=True, exist_ok=True)
    vorher = {p.name for p in JE_VORGANG.glob("*.json")}
    buendel: dict[str, dict[str, dict]] = defaultdict(dict)
    for (land, vid), akte in akten.items():
        h = dateiname(land, vid)
        buendel[h[:BUENDEL_STELLEN]][h] = akte

    neu = gleich = 0
    for name, inhalt in sorted(buendel.items()):
        datei = f"{name}.json"
        ziel = JE_VORGANG / datei
        # ⚠ `allow_nan=False` IST DER RIEGEL, NICHT DIE FEINHEIT. Ohne ihn schreibt
        # `json.dumps` fuer `float('nan')` das nackte `NaN` — gueltiges Python, ungueltiges
        # JSON — und der Fehler taucht erst beim Lesen im Browser auf, weit weg von hier.
        # Mit ihm bricht der Export an der Stelle ab, an der der Wert entsteht.
        text = json.dumps(inhalt, ensure_ascii=False, default=str, sort_keys=True,
                          allow_nan=False)
        # Nur Geaendertes schreiben — sonst laedt der naechtliche Abgleich alles erneut hoch.
        if ziel.exists() and ziel.read_text(encoding="utf-8") == text:
            gleich += 1
        else:
            ziel.write_text(text, encoding="utf-8")
            neu += 1
        vorher.discard(datei)
    for tot in vorher:
        (JE_VORGANG / tot).unlink(missing_ok=True)

    # ⚠ SERVERSEITIG, NICHT IM BROWSER. Bekanntmachung → Vorgang, damit die Detailansicht
    # einer Vergabe ihre Akte verlinken kann. Die Datei ist ~3 MB; sie liegt im Cache der
    # Route und geht NIE an den Browser. Ins Lead-Json gehoert sie nicht: dann traegt jeder
    # der 42.678 Leads ein weiteres Feld, das 41.999 Nutzer nie anfassen.
    (OUT / "vorgang-lead.json").write_text(
        json.dumps(nachschlag, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    # Trennt „diesen Vorgang gibt es nicht" (404) von „die Akten fehlen" (503) — dieselbe
    # Unterscheidung, die `firma-stand.json` nach einem echten Vorfall bekommen hat.
    (OUT / "vorgang-stand.json").write_text(
        json.dumps({"n": len(akten), "n_lead": len(nachschlag)}), encoding="utf-8")
    print(f"  Buendel: {neu:,} geschrieben, {gleich:,} unveraendert, "
          f"{len(vorher):,} entfernt → web/data/vorgang/")


def _laender(gewuenscht: str | None) -> list[str]:
    """Welche Länder haben Vorgänge?

    ⚠ NICHT NUR DE. Der erste Entwurf hatte `--land DE` als Vorgabe und der Tageslauf rief
    ihn ohne Argument — vier Länder mit zusammen 585.925 Vorgängen wären nie exportiert
    worden, ohne dass irgendetwas rot geworden wäre. Deutschland ist der Testfall, nicht
    der Geltungsbereich.
    """
    if gewuenscht:
        return [gewuenscht]
    gold = ROOT / "data" / "gold"
    return sorted(d.name for d in gold.iterdir()
                  if d.is_dir() and (d / "vorgaenge.parquet").exists()
                  and (d / "vorgang_notice.parquet").exists())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--land", default=None, help="nur dieses Land (sonst alle mit Vorgaengen)")
    a = ap.parse_args()
    con = duckdb.connect()

    sichtbar = _sichtbare_leads()
    if not sichtbar:
        raise SystemExit("web/data/leads-*.json fehlt oder ist leer — "
                         "erst export_web_leads.py laufen lassen.")

    # ⚠ ALLE LAENDER SAMMELN, DANN EINMAL SCHREIBEN. `schreibe` raeumt weg, was nicht in der
    # uebergebenen Menge steht. Je Land zu schreiben hiesse, dass das zweite Land die Akten
    # des ersten wieder loescht — und der Lauf saehe dabei erfolgreich aus.
    akten: dict[tuple[str, str], dict] = {}
    nachschlag: dict[str, str] = {}
    for land in _laender(a.land):
        menge = _menge(con, land, sichtbar)
        if not menge:
            continue
        teil = _akten(con, land, menge)
        akten.update(teil)
        for (l, vid), akte in teil.items():
            for e in akte["verlauf"]:
                for nid in e["ids"]:
                    nachschlag[nid] = f"{l}:{vid}"

    mit_dok = sum(1 for x in akten.values() if x["dokumente"])
    mit_kette = sum(1 for x in akten.values() if x.get("kette"))
    mit_zuschlag = sum(1 for x in akten.values() if x["zahlen"]["zuschlag"] > 0)
    print(f"  {len(akten):,} Akten · {mit_zuschlag:,} mit Zuschlag · "
          f"{mit_kette:,} in einer Kette · {mit_dok:,} mit Dateiliste")
    schreibe(akten, nachschlag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

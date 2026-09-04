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
import re
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "web" / "data"
JE_VORGANG = OUT / "vorgang"
# ⚠ ZWEI NAMENSRAEUME, WEIL ES ZWEI ZUGRIFFSMUSTER GIBT. `vorgang/` haelt die Akten der
# heute sichtbaren Vergaben — der heisse Pfad, aus jedem Lead verlinkt, im Median 21 KB je
# Buendel. `vorgang-archiv/` haelt alles Uebrige (1,88 Mio.), das seltener und einzeln
# nachgeschlagen wird; dort sind die Buendel rund 350 KB gross.
#
# Alles in EINEN Namensraum zu werfen waere die schlechtere Wahl: 1,47 GB auf 4.096 Buendel
# ergaeben 360 KB — auch fuer den Klick aus der Trefferliste, der heute 21 KB kostet. Und
# feiner zu buendeln geht nicht: die Buendelzahl IST die Dateizahl, und daran ist
# `next build` bei rund 156.000 gestorben.
ARCHIV = OUT / "vorgang-archiv"
# Kennung → Vorgang, gebuendelt wie die Akten selbst.
#
# ⚠ NICHT ALS EINE DATEI. Als `vorgang-lead.json` war sie 3,6 MB, solange sie nur die
# Produktmenge fuehrte. Mit allen 3,15 Mio. Bekanntmachungen wurde sie 132 MB — und die
# Route laedt sie komplett in den Speicher, um EINE Zeile zu beantworten. Das ist derselbe
# Fehler, an dem `firma-profiles.json` gescheitert ist, nur eine Tabelle weiter.
KENNUNG = OUT / "vorgang-kennung"
# Kuerzere Suchformen werden nicht aufgenommen — sie treffen alles und nichts.
KENNUNG_MIND = 4
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

# Wie viele Zeichen des Aktenhashes den Buendelnamen bilden: 3 → 4.096 Buendel.
# MUSS mit `web/lib/vorgangsakte.ts` uebereinstimmen.
#
# ⚠ WARUM NICHT 256, WIE ZUERST GEBAUT. Ein Buendel wird als GANZES neu geschrieben, sobald
# EINE Akte darin sich aendert — und weil der Hash streut, treffen schon 0,5 % geaenderte
# Akten praktisch jedes Buendel. Bei 256 Buendeln (median 347 KB) laed der Nachtlauf dafuer
# 87 MB hoch; bei 4.096 (median 21 KB) ist es ein Bruchteil davon, und jeder Aufruf einer
# Akte holt ebenfalls 21 statt 347 KB.
#
# ⚠ UND WARUM NICHT NOCH FEINER. Die Zahl der Buendel ist zugleich die Zahl der Dateien
# unter `web/data`, und daran ist `next build` schon einmal gestorben: bei rund 156.000
# Dateien im Node-Heap (SIGABRT). Mit 4.096 sind es 107.529 — geprueft, Build gruen in 35 s.
# Die Menge waechst kuenftig in die Buendel hinein, nicht in ihre Anzahl.
BUENDEL_STELLEN = 3

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


def kenn_norm(s: str) -> str:
    """Kennung → Suchform. MUSS mit `web/lib/explorerCore.js` (`_kennNorm`) uebereinstimmen.

    Wer eine Nummer abtippt, tippt sie anders: `BA090-26`, `ba090/26`, `BA 090 26`. Ohne
    Vereinheitlichung findet die Suche nur den Glueckstreffer.
    """
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def kenn_datei(schluessel: str) -> str:
    """Kennung → Buendelname. MUSS mit `web/lib/vorgangsakte.ts` uebereinstimmen."""
    return hashlib.sha1(schluessel.encode("utf-8")).hexdigest()[:BUENDEL_STELLEN]


def _produktlaender() -> set[str]:
    """Welche Laender das Produkt ueberhaupt zeigt — aus derselben Quelle wie die Leads.

    ⚠ WARUM DAS ARCHIV EINE GRENZE BRAUCHT. `build_vorgaenge` nimmt seine Laender aus
    SILBER und baut fuer alles, was dort liegt. Gemessen am 2026-09-04 waren das sechs
    Laender, das Produkt zeigt aber vier: PL (144.590 Vorgaenge) und EU stehen in keiner
    Trefferliste. Ohne Grenze lieferte das Archiv fuer sie Akten aus, die aussehen wie eine
    deutsche — nur ohne Kette, ohne Dublettenpruefung und ohne die vierte und fuenfte
    Schluesselstufe, weil dort die Gold-Kette fehlt (PL hat 3 Tabellen, DE hat 72).

    ⚠ NICHT „sondiert gegen aufgenommen". Das waere die falsche Grenze: PL IST auf
    Bekanntmachungsebene aufgenommen, `pruefe_sondierung.py` sagt das ausdruecklich. Die
    Frage ist nicht, ob wir das Land kennen, sondern ob ein Nutzer dort etwas findet.
    """
    laender: set[str] = set()
    for p in sorted(OUT.glob("leads-*.json")):
        try:
            roh = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for l in (roh if isinstance(roh, list) else roh.get("leads", [])):
            if isinstance(l, dict) and l.get("land"):
                laender.add(str(l["land"]).upper())
    return laender


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


def _zaehle(con: duckdb.DuckDBPyConnection, land: str) -> int:
    return con.execute(
        f"select count(*) from read_parquet('data/gold/{land}/vorgaenge.parquet')").fetchone()[0]


def _alle_vorgaenge(con: duckdb.DuckDBPyConnection, land: str) -> set[str]:
    """Jeder Vorgang des Landes — die Grundlage des Archivs.

    ⚠ WARUM UEBERHAUPT ALLE. Aufbereitet waren bis zum 2026-09-03 nur die 53.867 Vorgaenge
    heute sichtbarer Vergaben, also 2,8 % von 1.932.060. Eine Vergabe von 2015 war damit
    nicht auffindbar — und genau danach war die erste Frage gestellt worden. 695.399
    Vorgaenge stammen aus 2020 oder frueher.
    """
    g = f"data/gold/{land}"
    return {r[0] for r in con.execute(
        f"select vorgang_id from read_parquet('{g}/vorgaenge.parquet')").fetchall()}


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
            # ⚠ `n` ZAEHLT OHNE ZWEITMELDUNGEN. Sie bleiben in `ids` sichtbar — die Spur zur
            # zweiten Quelle ist der Beleg dafuer, dass wir beide Portale gelesen haben —
            # aber sie sind nicht noch ein Ereignis. Genau daran hingen im Zuercher Beispiel
            # sieben Zuschlaege fuer sechs Lose.
            # `.get`, nicht `[...]`: fehlt das Kennzeichen, ist es keine Zweitmeldung.
            # Ein fehlendes Feld darf den Export nicht anhalten.
            "n": sum(1 for t in gruppe if not t.get("dublette")) or len(gruppe),
            "dubletten": sum(1 for t in gruppe if t.get("dublette")),
            # ⚠ EIN EINTRAG KANN NUR AUS ZWEITMELDUNGEN BESTEHEN. Die Zweitmeldung eines
            # anderen Portals traegt oft ein anderes Datum als das Original und bekommt
            # damit eine eigene Zeile im Verlauf. Ohne diese Unterscheidung stand dort
            # „Ausschreibung · dazu eine Zweitmeldung" — bei einer Zeile, die SELBST die
            # Zweitmeldung ist und keine hat.
            "nur_zweitmeldung": all(t.get("dublette") for t in gruppe),
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
               vn.veroeffentlicht, vn.hat_unterlagen, vn.dublette
        from read_parquet('{g}/vorgang_notice.parquet') vn
        join _m m on m.vorgang_id = vn.vorgang_id
    """).fetchall():
        teile[r[0]].append({"notice_id": r[1], "notice_kind": r[2], "jahr": r[3],
                            "veroeffentlicht": r[4], "hat_unterlagen": r[5],
                            "dublette": bool(r[6])})

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
            # ⚠ WORAUF DIE VOLLSTAENDIGKEIT RUHT. 62.795 Akten (9,7 % aller vollstaendigen)
            # sind es NUR, weil `_andocken` ihren Zuschlag ueber Kaeufer und Titel zugeordnet
            # hat. Eine gruene Plakette „Ausschreibung und Zuschlag vorhanden" behauptet dort
            # eine Tatsache, wo eine Schaetzung steht — derselbe Fehler, den die Kette und die
            # Unterlagen schon hinter sich haben, eine Ebene hoeher.
            "vollstaendig_beleg": (
                None if not k.get("vollstaendig")
                else "erschlossen"
                if (k.get("n_angedockt") or 0) > 0
                and (k.get("n_zuschlag") or 0) == (k.get("n_angedockt") or 0)
                else "amtlich"),
            "von": _tag(k.get("erste_veroeffentlichung")),
            "bis": _tag(k.get("letzte_veroeffentlichung")),
            "zahlen": {a: int(k.get(f"n_{a}") or 0)
                       for a in ("bekanntmachungen", "ausschreibung", "zuschlag",
                                 "korrektur", "vorinfo", "dokumente", "anforderungen",
                                 "dubletten", "verschmolzen",
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


def _buendeln(akten: dict[tuple[str, str], dict], ziel: Path, was: str,
              raeumen: bool = True) -> None:
    """Akten in Buendel schreiben; nur Geaendertes anfassen, Verwaistes entfernen.

    ⚠ `raeumen=False` BEI EINEM TEILLAUF. Das Wegraeumen setzt voraus, dass die uebergebene
    Menge VOLLSTAENDIG ist. Mit `--land CH` ist sie es nicht — und der erste Versuch loeschte
    prompt 1.785 Buendel der anderen Laender, waehrend der Lauf „erfolgreich" meldete. Ein
    Teillauf darf ergaenzen, nie aufraeumen.
    """
    ziel.mkdir(parents=True, exist_ok=True)
    vorher = {p.name for p in ziel.glob("*.json")}
    buendel: dict[str, dict[str, dict]] = defaultdict(dict)
    for (land, vid), akte in akten.items():
        h = dateiname(land, vid)
        buendel[h[:BUENDEL_STELLEN]][h] = akte
    neu = gleich = 0
    for name, inhalt in sorted(buendel.items()):
        datei = f"{name}.json"
        pfad = ziel / datei
        text = json.dumps(inhalt, ensure_ascii=False, default=str, sort_keys=True,
                          allow_nan=False)
        if pfad.exists() and pfad.read_text(encoding="utf-8") == text:
            gleich += 1
        else:
            pfad.write_text(text, encoding="utf-8")
            neu += 1
        vorher.discard(datei)
    if raeumen:
        for tot in vorher:
            (ziel / tot).unlink(missing_ok=True)
    print(f"  {was}: {len(akten):,} Akten in {len(buendel):,} Buendeln · {neu:,} geschrieben, "
          f"{gleich:,} unveraendert, "
          f"{len(vorher):,} " + ("entfernt" if raeumen else "fremde behalten (Teillauf)")
          + f" → {ziel.name}/")


def _kennungen(nachschlag: dict[str, str], akten: set[tuple[str, str]]) -> None:
    """Der Suchindex: jede Kennung, unter der ein Vorgang auffindbar sein soll.

    Aufgenommen wird beides, und zwar bewusst doppelt:
      * die Kennung, WIE SIE DASTEHT (`525589_2025`, `folder:4679…`) — daran haengt der
        Verweis aus der Detailansicht, der die exakte Bekanntmachungs-ID kennt;
      * ihre Suchform (`kenn_norm`) — daran haengt das Suchfeld, denn wer eine Nummer
        abtippt, tippt sie anders.

    ⚠ ERST DIE EXAKTE, DANN DIE SUCHFORM. Zwei verschiedene Kennungen koennen dieselbe
    Suchform haben; wer die exakte ueberschreibt, verliert den sicheren Treffer zugunsten
    eines geratenen. Die exakte gewinnt deshalb immer.

    ⚠ ZU KURZES WIRD NICHT AUFGENOMMEN. `kenn_norm("1")` ist `"1"` — eine solche Kennung
    trifft alles und nichts. Dieselbe Grenze wie in der Trefferlisten-Suche.
    """
    KENNUNG.mkdir(parents=True, exist_ok=True)
    eimer: dict[str, dict[str, str]] = defaultdict(dict)
    n_exakt = n_such = 0
    for kennung, ziel in nachschlag.items():
        eimer[kenn_datei(kennung)][kennung] = ziel
        n_exakt += 1
    for land, vid in akten:
        eimer[kenn_datei(vid)].setdefault(vid, f"{land}:{vid}")
        n_exakt += 1
    # Suchformen zuletzt und nur, wo noch nichts steht — die exakte Kennung gewinnt.
    for kennung, ziel in list(nachschlag.items()):
        k = kenn_norm(kennung)
        if len(k) >= KENNUNG_MIND and k != kennung:
            if eimer[kenn_datei(k)].setdefault(k, ziel) is ziel:
                n_such += 1
    for land, vid in akten:
        k = kenn_norm(vid)
        if len(k) >= KENNUNG_MIND and k != vid:
            if eimer[kenn_datei(k)].setdefault(k, f"{land}:{vid}") == f"{land}:{vid}":
                n_such += 1

    vorher = {p.name for p in KENNUNG.glob("*.json")}
    neu = gleich = 0
    for name, inhalt in sorted(eimer.items()):
        datei = f"{name}.json"
        ziel_p = KENNUNG / datei
        text = json.dumps(inhalt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if ziel_p.exists() and ziel_p.read_text(encoding="utf-8") == text:
            gleich += 1
        else:
            ziel_p.write_text(text, encoding="utf-8")
            neu += 1
        vorher.discard(datei)
    for tot in vorher:
        (KENNUNG / tot).unlink(missing_ok=True)
    # Die alte Sammeldatei aktiv entfernen: 132 MB, die niemand mehr liest, saehen sonst
    # aus wie ein aktueller Stand und gingen beim naechsten Upload wieder mit.
    (OUT / "vorgang-lead.json").unlink(missing_ok=True)
    print(f"  Kennungen: {n_exakt:,} exakt + {n_such:,} Suchformen in {len(eimer):,} "
          f"Buendeln · {neu:,} geschrieben, {gleich:,} unveraendert → {KENNUNG.name}/")


def schreibe(produkt: dict[tuple[str, str], dict],
             archiv: dict[tuple[str, str], dict],
             nachschlag: dict[str, str], voll: bool = True) -> None:
    """Zwei Buendelmengen, ein Nachschlagewerk.

    ⚠ WARUM GEBUENDELT UND NICHT EINE DATEI JE AKTE. Zusammen mit `firma/` und
    `doc-analysis/` stuenden sonst rund 156.000 Dateien unter `web/data`, und `next build`
    starb daran reproduzierbar im Node-Heap (SIGABRT, Stapel in `node::fs::AfterStat`).

    ⚠ UND WARUM NICHT EINE SAMMELDATEI. Daran ist `firma-profiles.json` gescheitert:
    67 MB laden, um 1,6 KB zu liefern.

    ⚠ UND WARUM ZWEI MENGEN. Die 1,93 Mio. Akten sind zusammen 1,47 GB; auf 4.096 Buendel
    waeren das 360 KB je Abruf — auch fuer den Klick aus der Trefferliste, der im heissen
    Pfad 21 KB kostet. Getrennt bleibt der haeufige Weg billig und das seltene Nachschlagen
    im Archiv bezahlbar.
    """
    _buendeln(produkt, JE_VORGANG, "Produktmenge", raeumen=voll)
    _buendeln(archiv, ARCHIV, "Archiv", raeumen=voll)

    # ⚠ SERVERSEITIG, NICHT IM BROWSER. Bekanntmachung → Vorgang, damit die Detailansicht
    # einer Vergabe ihre Akte verlinken kann. Die Datei liegt im Cache der Route und geht NIE
    # an den Browser. Ins Lead-Json gehoert sie auch nicht: dann traegt jeder Lead ein
    # weiteres Feld, das fast niemand anfasst — und `export_web_leads.py` haette eine zweite
    # Quelle fuer dieselbe Zuordnung.
    if voll:
        _kennungen(nachschlag, set(produkt) | set(archiv))
    else:
        print("  Kennungsindex NICHT geschrieben (Teillauf) — er braucht alle Laender.")
    # Trennt „diesen Vorgang gibt es nicht" (404) von „die Akten fehlen" (503) — dieselbe
    # Unterscheidung, die `firma-stand.json` nach einem echten Vorfall bekommen hat.
    if voll:
        (OUT / "vorgang-stand.json").write_text(
            json.dumps({"n": len(produkt), "n_archiv": len(archiv),
                        "n_lead": len(nachschlag)}), encoding="utf-8")


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
    ap.add_argument("--ohne-archiv", action="store_true",
                    help="nur die Produktmenge bauen (schnell; das Archiv bleibt stehen)")
    a = ap.parse_args()
    con = duckdb.connect()

    sichtbar = _sichtbare_leads()
    if not sichtbar:
        raise SystemExit("web/data/leads-*.json fehlt oder ist leer — "
                         "erst export_web_leads.py laufen lassen.")

    # ⚠ ALLE LAENDER SAMMELN, DANN EINMAL SCHREIBEN. `_buendeln` raeumt weg, was nicht in der
    # uebergebenen Menge steht. Je Land zu schreiben hiesse, dass das zweite Land die Akten
    # des ersten wieder loescht — und der Lauf saehe dabei erfolgreich aus.
    produkt: dict[tuple[str, str], dict] = {}
    archiv: dict[tuple[str, str], dict] = {}
    nachschlag: dict[str, str] = {}
    produktlaender = _produktlaender()
    if not produktlaender:
        raise SystemExit("keine Laender in web/data/leads-*.json — erst export_web_leads.py")
    for land in _laender(a.land):
        menge = _menge(con, land, sichtbar)
        # ⚠ DAS ARCHIV FOLGT DEM PRODUKT, DIE PRODUKTMENGE DEM LEAD. Ein Vorgang, den ein
        # sichtbarer Lead erreicht, bleibt IMMER — auch wenn sein Land sonst nicht gezeigt
        # wird (es gibt zwei solche auf EU-Ebene). Nur das Archiv hoert an der Landesgrenze
        # des Produkts auf.
        if land not in produktlaender and not menge:
            print(f"  {land}: kein Produktland und kein sichtbarer Lead — uebersprungen "
                  f"({_zaehle(con, land):,} Vorgaenge bleiben in Gold)")
            continue
        alle = (_alle_vorgaenge(con, land)
                if (not a.ohne_archiv and land in produktlaender) else menge)
        if not alle:
            continue
        teil = _akten(con, land, alle)
        for (l, vid), akte in teil.items():
            (produkt if vid in menge else archiv)[(l, vid)] = akte
            for e in akte["verlauf"]:
                for nid in e["ids"]:
                    nachschlag[nid] = f"{l}:{vid}"
        print(f"      {land}: {sum(1 for k in teil if k[1] in menge):,} Produktakten, "
              f"{sum(1 for k in teil if k[1] not in menge):,} Archivakten")

    mit_dok = sum(1 for x in produkt.values() if x["dokumente"])
    mit_kette = sum(1 for x in {**produkt, **archiv}.values() if x.get("kette"))
    mit_zuschlag = sum(1 for x in produkt.values() if x["zahlen"]["zuschlag"] > 0)
    print(f"  {len(produkt):,} Produktakten ({mit_zuschlag:,} mit Zuschlag, "
          f"{mit_dok:,} mit Dateiliste) · {len(archiv):,} Archivakten · "
          f"{mit_kette:,} in einer Kette")
    # ⚠ Ein Teillauf (`--land`, `--ohne-archiv`) darf weder aufraeumen noch das
    # Nachschlagewerk ueberschreiben: beide setzen Vollstaendigkeit voraus.
    voll = a.land is None and not a.ohne_archiv
    schreibe(produkt, archiv, nachschlag, voll=voll)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

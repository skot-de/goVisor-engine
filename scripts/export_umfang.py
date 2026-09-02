#!/usr/bin/env python3
"""Umfang der Angebotsarbeit → web/data/umfang.json (Kennzahlen 4 und 5).

Zwei Zahlen, eine Frage: wie viel Arbeit ist dieses Angebot, bevor man die Unterlagen öffnet?

  Kennzahl 4  das grösste einzelne FORMULAR      Felder zum Ausfüllen
  Kennzahl 5  das grösste LEISTUNGSVERZEICHNIS   Positionen zum Bepreisen

⚠ SIE MESSEN NICHT DASSELBE, obwohl die Vermutung naheliegt: ein VHB 223 („Aufgliederung der
Einheitspreise") hat ein Feld je LV-Position. Nachgemessen ist die Korrelation **-0,02**, und
von 803 Vorgängen mit grossem LV haben nur 79 auch ein grosses Formular (10 %). Das LV erreicht
724 Vorgänge, die das Formular nicht sieht. Sie stehen deshalb im selben Block, aber als zwei
Zeilen.

KENNZAHL 4 — DAS GRÖSSTE FORMULAR. Steckt in diesen Unterlagen ein Formular, das nicht in
einer Stunde ausgefüllt ist? Ein Preisblatt mit 3.456 Feldern verschiebt die Angebotsplanung um
Tage, und es steht nirgends in der Bekanntmachung.

    VHB 223 Aufgliederung der Einheitspreise      3.456 Felder
    223.pdf                                       5.120 Felder
    Abgabe.zip::Angebotsdatei A                   2.688 Felder

⚠ SIE ZÄHLT NUR EIN FORMULAR, NICHT DEN VORGANG — und das ist der ganze Punkt. Die Übergabe
verspricht „Formularaufwand, Median 22 Pflichtfelder"; beides hält nicht:

  1. „Pflicht" ist ein Kennzeichen im PDF, das fast niemand setzt. 93 % aller Formulare tragen
     null Pflichtfelder, auch 92 % derjenigen mit mindestens 50 Feldern. Ein
     95-Felder-Vergabeformular ohne ein einziges Pflichtfeld gibt es nicht. Die Zahl misst die
     Formularsoftware, nicht die Vergabe.
  2. Die „22" ist der Median je FORMULAR (gemessen 23), nicht je Vorgang.
  3. ⚠ Summen je Vorgang messen UNS. Formulare je Vorgang wachsen mit der Zahl gelesener
     Dateien: 2 → 7 → 16 bei 1-5 / 6-15 / 16-40 gelesenen Dateien, Felder 60 → 327 → 606. Ein
     Plateau gibt es bei keiner Lesetiefe, und auch nicht in den 165 Vorgängen, deren
     Unterlagen vollständig aus EINEM ZIP kamen. Wer diese Summe anzeigt, zeigt unsere
     Abrufquote als Eigenschaft der Ausschreibung.

Was übrig bleibt, ist die eine Aussage, die von der Lesetiefe unabhängig ist: **Anwesenheit.**
Ein Formular, das wir gesehen haben, ist da. Nur seine Abwesenheit dürfen wir nicht behaupten,
deshalb sagt diese Kennzahl nie „wenig Aufwand" und hat auch keinen Marktvergleich: gegen
einen marktweiten Median verglichen, der aus derselben Untererfassung stammt, sähe jeder tief
gelesene Vorgang extremer aus als er ist.

Basis 5.469 Vorgänge mit Formularen: 47 % haben eines mit mindestens 100 Feldern, 19 % mit
200, 12 % mit 400. Von den 636 über 400 Feldern sind 472 VHB-Formblätter, also Preisblätter.

KENNZAHL 5 — DAS LEISTUNGSVERZEICHNIS. Wie viele Positionen sind zu bepreisen?

⚠ DIESE KENNZAHL LIEFERT DIE ZAHL NICHT — nur den Vergleich. Der Block „Leistungsumfang" im
Frontend zeigt `nPositionen` seit jeher an; ihm fehlte bloss, wogegen der Nutzer sie halten
soll. Eine zweite Kachel mit derselben Zahl daneben waere Doppelung gewesen. Wer eine neue
Kennzahl baut, sucht deshalb zuerst, ob ihre Zahl schon irgendwo steht.

⚠ UND SIE LIEST DIESELBE QUELLE WIE DER BLOCK (`data/docs/<L>/doc_positions.parquet`). Der
erste Versuch nahm die `leistung_menge`-Zeilen aus `doc_checklist` — eine zweite Ableitung
derselben Sache, und die schlechtere:

    aus doc_positions   3.770 Vorgaenge · Median  96 · max   9.411
    aus doc_checklist   2.812 Vorgaenge · Median  83 · max 200.010

Die 200.010 sind ein LASTGANG: Viertelstundenwerte eines Jahres in einer Tabelle, keine zu
kalkulierenden Positionen. „200.010 Positionen zu bepreisen" waere bei jeder Stromausschreibung
falsch gewesen. Die Uebergabe verspricht ausserdem „495.891 LV-Positionen" — diese Zahl liegt
nirgends, sie wurde beim Parsen gezaehlt und nie gespeichert.

⚠ VERGLICHEN WIRD JE GEWERK (CPV 4-stellig), NICHT GLOBAL. Innerhalb von CPV 45 spreizen die
Mediane 5,4-fach: Installationsarbeiten (4533) 292 Positionen, Anstricharbeiten (4544) 54. Ein
Median ueber alle Bauarbeiten markierte jedes normale Installations-LV als gross und jedes
grosse Maler-LV als normal. Derselbe Fehler wie ein Fristenmedian ueber VgV und UVgO hinweg
(Kennzahl 1). Unter 40 Vorgaengen im Gewerk steht die Zahl ohne Vergleich.

⚠ WARUM SIE EINEN VERGLEICH TRAGEN DARF UND KENNZAHL 4 NICHT. Das groesste LV je Vorgang ist
ueber die Lesetiefe STABIL (69 → 96 → 78 bei 1-5 / 6-15 / 16+ gelesenen Dateien), und je Vorgang
gibt es genau ein LV. Die Formularsummen wachsen dagegen monoton mit. Wer eine neue
Dokument-Kennzahl baut, misst das zuerst — siehe `docs/laender/10-abnahme-und-messung.md`,
Abschnitt „Misst die Zahl den Vorgang oder misst sie uns?".

Basis: 1.621 Vorgaenge bekommen einen Vergleich, verteilt auf 13 Gewerke.

Aufruf: python3 scripts/export_umfang.py
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "umfang.json"

ZEIGEN = 100     # Formular: darunter ist es ein normaler Vordruck und keine Nachricht wert
HINWEIS = 400    # Formular: ab hier ist es Arbeit von Tagen (oberste 12 %)

MIND_GEWERK = 40 # weniger tragen keinen Median; darunter steht die Zahl ohne Vergleich
BELEG_MAX = 6    # so viele Feldnamen als Zitat; mehr belegt nichts zusaetzlich

# ⚠ Ein Drittel der Formulare beginnt mit durchnummerierten Platzhaltern („Field0, TEXTFELD_1"),
# die sprechenden Namen stehen dahinter. Wer die ersten sechs nimmt, zeigt bei jedem dritten
# Vorgang ein Zitat, das nichts belegt. Diese kommen deshalb zuletzt, nicht weg: bei 3 % der
# Formulare sind sie alles, was es gibt.
_STUMM = re.compile(r"^(field|text|textfeld|kontrollk|checkbox|undefined)[\d_. ]*$", re.I)


def _kurz(pfad: str) -> str:
    """Dateiname ohne Verzeichnis. ⚠ Kommt aus fremden Unterlagen, also nie ungeprueft ins DOM."""
    name = str(pfad or "").replace("\\", "/").split("/")[-1].split("::")[-1].strip()
    return name[:80] or "Formular"


def _laender() -> list[str]:
    """Aus dem Bestand, nicht aus einer Liste im Code — sonst faellt ein neues Land stumm raus."""
    gold = ROOT / "data" / "gold"
    return sorted(p.name for p in gold.iterdir()
                  if p.is_dir() and (p / "doc_checklist.parquet").exists()) if gold.exists() else []


def _formulare(con, C: str, raus: dict) -> tuple[int, int]:
    """Kennzahl 4 — das groesste einzelne Formular. `r = 1` holt genau eins."""
    treffer = con.execute(f"""
        with f as (select notice_id, wert_num, source_file, beleg,
                          row_number() over (partition by notice_id order by wert_num desc) r
                   from read_parquet('{C}')
                   where unit = 'Felder' and wert_num >= {ZEIGEN})
        select notice_id, wert_num, source_file, beleg from f where r = 1""").fetchall()
    for nid, felder, datei, beleg in treffer:
        zitat = ""
        if beleg and ":" in str(beleg):
            namen = [t.strip() for t in str(beleg).split(":", 1)[1].split(",") if t.strip()]
            namen.sort(key=lambda n: bool(_STUMM.match(n)))   # stabil: sprechende zuerst
            zitat = ", ".join(namen[:BELEG_MAX])
        raus.setdefault(str(nid), {})["formular"] = {
            "felder": int(felder), "datei": _kurz(datei),
            "hinweis": int(felder) >= HINWEIS, **({"beleg": zitat[:160]} if zitat else {})}
    return len(treffer), sum(1 for t in treffer if t[1] >= HINWEIS)


def _verzeichnisse(con, land: str, L: str, raus: dict) -> tuple[int, int]:
    """Kennzahl 5 — der GEWERKSVERGLEICH zum Leistungsverzeichnis.

    ⚠ SIE LIEFERT DIE ZAHL NICHT MIT, und das ist der Punkt. Der Block „Leistungsumfang" zeigt
    seit jeher `nPositionen` aus `doc-struktur.json`; eine zweite Kachel mit derselben Zahl
    daneben waere die Sorte Doppelung, die eine Oberflaeche unlesbar macht. Hier entsteht nur,
    was dort fehlt: wogegen der Nutzer die Zahl halten soll.

    ⚠ UND SIE LIEST DIESELBE QUELLE WIE DER BLOCK (`doc_positions.parquet`), nicht die
    `leistung_menge`-Zeilen aus `doc_checklist`. Der erste Versuch nahm die: er sah 2.812
    Vorgaenge statt 3.770, und seine Spitze waren LASTGAENGE — Viertelstundenwerte eines Jahres
    (max 200.010), die als „Positionen zu bepreisen" gezaehlt worden waeren. Zwei Quellen fuer
    dieselbe Zahl sind immer die schlechtere Loesung, hier war die zweite zusaetzlich falsch.

    ⚠ VERGLICHEN WIRD JE GEWERK (CPV 4-stellig). Innerhalb von CPV 45 spreizen die Mediane
    5,4-fach: Installationsarbeiten 292 Positionen, Anstrichsarbeiten 54. Ein Median ueber alle
    Bauarbeiten markierte jedes normale Installations-LV als gross — derselbe Fehler wie ein
    Fristenmedian ueber VgV und UVgO hinweg (Kennzahl 1).

    ⚠ UND EIN VERKUERZTER CPV IST KEIN GEWERK. 239 Vorgaenge tragen nur „45" (Bauarbeiten,
    ohne Gewerk). `substr(...,1,4)` machte daraus klaglos eine Gruppe „45", und die Anzeige
    haette gesagt „neun von zehn Verzeichnissen DIESES GEWERKS sind kleiner" — ueber einen
    Topf, in dem jedes Gewerk liegt. Sie bekommen lieber keinen Vergleich."""
    P = ROOT / "data" / "docs" / land / "doc_positions.parquet"
    if not P.exists() or not Path(L).exists():
        return 0, 0
    zeilen = con.execute(f"""
        select p.notice_id, p.n, substr(l.cpv_code, 1, 4) gewerk
        from (select notice_id, count(*) n from read_parquet('{P.as_posix()}') group by 1) p
        join read_parquet('{L}') l on l.lead_id = p.notice_id
        where length(l.cpv_code) >= 4""").fetchall()
    je: dict[str, list[float]] = {}
    for _, n, g in zeilen:
        je.setdefault(g, []).append(float(n))
    lage = {g: (statistics.median(v), statistics.quantiles(v, n=10)[8])
            for g, v in je.items() if len(v) >= MIND_GEWERK}
    for nid, _, g in zeilen:
        if g not in lage:
            continue
        raus.setdefault(str(nid), {})["lv"] = {
            "gewerk": g, "median": round(lage[g][0]), "hoch": round(lage[g][1])}
    return sum(1 for _, _, g in zeilen if g in lage), len(lage)


def main() -> int:
    con = duckdb.connect()
    raus: dict[str, dict] = {}
    for land in _laender():
        C = (ROOT / "data" / "gold" / land / "doc_checklist.parquet").as_posix()
        L = (ROOT / "data" / "gold" / land / "lead_export.parquet").as_posix()
        n, warn = _formulare(con, C, raus)
        print(f"  {land}: Formulare  {n:,} ab {ZEIGEN} Feldern · davon {warn:,} ab {HINWEIS}")
        n2, gruppen = _verzeichnisse(con, land, L, raus)
        print(f"  {land}: LV         {n2:,} Vorgaenge bekommen einen Gewerksvergleich"
              f" · {gruppen} Gewerke ab {MIND_GEWERK} Vorgaengen")

    if not raus:
        print("FEHLT: keine Datengrundlage — erst `doc_checklist` bauen lassen.")
        return 1
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    beide = sum(1 for v in raus.values() if len(v) == 2)
    print(f"Umfang → {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB) · {len(raus):,} Vorgaenge, "
          f"{beide:,} mit beiden Zeilen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

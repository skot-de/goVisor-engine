#!/usr/bin/env python3
"""Bezifferte Schwellen im Vergleich → web/data/schwellen.json (Kennzahl 6).

DIE FRAGE. „Berufshaftpflicht 5 Mio. EUR für Personenschäden" steht in der Checkliste. Ist das
üblich oder ist das die Hürde, an der man sich das Angebot spart? Die Zahl steht seit jeher da,
der Vergleich fehlte.

⚠ DIE ÜBERGABE VERSPRICHT „198.584 Zahlen, einordenbar gegen Median und Quartil". Zahlen gibt
es sogar mehr (223.570), einordenbar sind davon rund ein Prozent. Drei Filter liegen dazwischen,
und jeder hat einen eigenen Grund.

FILTER 1 — OHNE EINHEIT KEIN VERGLEICH. Die grössten Posten tragen gar keine: bei
`technische_mindestanforderung` fehlt sie in 66 % der Fälle, bei `vertragsstrafe` in 81 %, bei
`zertifikat` in 97 %. „Median 20" ist 20 mm oder 20 Jahre, das weiss niemand mehr. Nach
Normalisierung auf fünf Dimensionen bleiben 22.229 Zahlen (10 %).

⚠ Und die Einheit kann einen FAKTOR tragen: „1,5 Mio. EUR" gegen „1.500.000 EUR" verglichen
wäre ein Fehler um das Millionenfache. Solche Schreibweisen werden verworfen, nicht geraten.

FILTER 2 — DIE GRUPPE MUSS EINE EINZIGE GRÖSSE BENENNEN. Das ist ein Urteil, kein Rechenschritt,
deshalb steht es als Liste mit Begründung in `VERGLEICHBAR`. Verworfen sind unter anderem:

    technische_mindestanforderung   „mindestens 20 %" — wovon? Steigung, Recyclinganteil, Rabatt
    frist                           Bindefrist und Ausführungsfrist im selben Topf
    leistung_menge                  „3 Stück" mischt Türen und Schrauben (und ist Kennzahl 5)
    einzureichendes_dokument        Formularfelder, das ist Kennzahl 4

⚠ Bei den beiden Versicherungsarten reicht der `req_type` nicht: die Deckungssummen sind nach
SCHADENSART gestaffelt und spreizen dabei um das Sechsfache (allgemein 500.000, Umweltschäden
3.000.000). Ein gemeinsamer Median wäre für jede einzelne Art falsch.

FILTER 3 — MISST DIE ZAHL DEN VORGANG ODER MISST SIE UNS? Diese Prüfung rechnet das Skript bei
jedem Lauf selbst, statt ein Urteil von heute einzufrieren: der Median der flach gelesenen
Vorgänge (1 bis 7 Dateien) gegen den der tief gelesenen (ab 8). Läuft er um mehr als
`MAX_DRIFT` auseinander, fliegt die Gruppe raus. Gemessen am 2026-09-02 fielen dabei:

    mindestumsatz / EUR            400.000 → 1.000.000   2,5×
    referenz_mindestwert / EUR     500.000 →   300.000   1,7×
    eignung_personal / Stück             3 →         9   3,0×
    vertragsstrafe / EUR             1.250 →        75  16,7×   (gemischte Skala)

⚠ Beim Mindestumsatz war die naheliegende Erklärung falsch. „Tief gelesene Vorgänge sind grosse
Vergaben, die verlangen eben mehr" — nachgemessen korreliert die Schwelle NICHT mit dem
Auftragswert (0,24; bei der Berufshaftpflicht sogar -0,09), und der Anstieg bleibt innerhalb
jedes Regelwerks bestehen (VgV 480.000 → 1.500.000). Es ist unsere Lesetiefe.

⚠ DIE REGELN WERDEN MITGELIEFERT, NICHT IM FRONTEND WIEDERHOLT. Der Renderer bildet denselben
Gruppenschlüssel aus derselben Einheitenliste. Zwei gepflegte Listen wären zwei Listen, die
auseinanderlaufen — dieselbe Fehlerform wie die handgetippte Spaltenliste bei den Doc-Signalen.

Aufruf: python3 scripts/export_schwellen.py
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "schwellen.json"

MIND_GRUPPE = 60    # darunter tragen Median und Quartil nichts
MIND_BAND = 20      # so viele je Lesetiefe-Band, sonst ist die Driftpruefung selbst Rauschen
FLACH, TIEF = 7, 8  # Grenze zwischen „flach" und „tief" gelesen (Dateien)
MAX_DRIFT = 1.5     # laufen die beiden Mediane weiter auseinander, misst die Gruppe uns

# Einheiten je Dimension. ⚠ BEWUSST OHNE FAKTOR-SCHREIBWEISEN („Mio. EUR", „TEUR"): sie tragen
# einen Multiplikator im Text, und wer sie hier aufnimmt, vergleicht 1,5 gegen 1.500.000.
EINHEITEN: dict[str, list[str]] = {
    "geld": ["eur", "euro", "€", "eur netto", "€ netto", "eur brutto", "€ brutto"],
    "prozent": ["%", "prozent", "v.h.", "vh"],
    "jahre": ["jahr", "jahre", "kalenderjahr", "kalenderjahre"],
    "stueck": ["stück", "stk", "st", "stueck", "anzahl", "referenz", "referenzen",
               "referenznachweis", "referenznachweise", "person", "personen",
               "mitarbeiter", "mitarbeitende"],
}

# ── AUSPRAEGUNGEN: wenn der `req_type` allein die Groesse noch nicht festlegt ────────────
#
# Zwei Anforderungsarten zerfallen in Unterarten, die man nicht gegeneinander halten darf, und
# beide Male steht die Unterscheidung IM BELEG, nicht in einem eigenen Feld:
#
#   berufshaftpflicht/haftung   Deckungssummen sind nach Schadensart gestaffelt und spreizen
#                               dabei sechsfach (allgemein 500.000, Umweltschaeden 3 Mio.).
#   vertragsstrafe              Tagessatz und Obergrenze sind zwei verschiedene Zahlen im
#                               Verhaeltnis 1:25 (0,20 % je Werktag gegen 5 % insgesamt).
#                               „Fast alle bei 5 %" aus der Uebergabe meint die Obergrenze.
#
# ⚠ DER BELEG DARF DIE FEHLENDE EINHEIT ERSETZEN, ABER NUR MIT BAND. Bei der Vertragsstrafe
# fehlt die Einheit in 81 % der Faelle; ohne sie waeren 216 statt 4.796 Werte vergleichbar. Wer
# „je Werktag 0,2" sagt, meint Prozent — das ist Beleg, keine Vermutung. Was ausserhalb des
# angegebenen Bandes liegt, wird VERWORFEN und nicht umgerechnet: unter den Vertragsstrafen
# stecken auch Eurobetraege, und die duerfen nie als Prozent gelesen werden.
#
# ⚠ EINE FORM FUER BEIDE FAELLE, und sie wird mitgeliefert. Zwei Klassifikatoren (hier und im
# Frontend) waeren zwei Klassifikatoren, die auseinanderlaufen.
_TAG = r"(je|pro)\s*(werk|kalender|arbeits)?tag|täglich|werktag|kalendertag"
_MAX = r"insgesamt|höchstens|maximal|obergrenze|begrenzt|überschreiten|gesamtsumme|gesamten auftrag"
_AUFZ = r"(personen|sach|vermögens|umwelt)\s*-\s*[,/]|(personen|sach|vermögens|umwelt)-\s*(und|bzw|sowie|oder)"

# ⚠ DAS EINHEITENFELD IST HIER FLIESSTEXT, kein Symbol: „der Auftragssumme je angefangenen
# Werktag", „€ je Vorfall", „pro Woche", „maximal". 2.123 der Vertragsstrafen tragen so etwas,
# und die erste Fassung verwarf sie alle, weil `_dimension()` nichts erkannte. Der Text ist
# aber der beste Beleg, den es gibt — er sagt Geld oder Prozent UND die Ausprägung.
#
# ⚠ UND „PRO WOCHE" IST KEIN TAGESSATZ. 134 Zeilen sagen „pro Woche", 44 „pro
# Überschreitungsfall": eigene Bezugsgroessen, die kein Muster trifft und die deshalb
# herausfallen. Ein Wochensatz von 0,5 % neben Tagessaetzen von 0,2 % waere ein Fehlalarm.
_GELD_BELEG = r"€|\beur\b|\beuro\b"
_PROZENT_BELEG = r"%|prozent|auftrags(summe|wert)|abrechnungssumme|vertragssumme|nettoauftrag"

AUSPRAEGUNGEN: dict[str, dict] = {
    "vertragsstrafe": {
        "dimension": "prozent", "einheitOptional": True, "sonst": None,
        "dimensionMuster": {"geld": _GELD_BELEG, "prozent": _PROZENT_BELEG},
        "regeln": [
            {"name": "Tagessatz", "muster": _TAG, "sperre": _MAX, "band": [0.01, 3.0]},
            {"name": "Obergrenze", "muster": _MAX, "sperre": _TAG, "band": [0.5, 30.0]},
        ],
    },
}
for _versicherung in ("berufshaftpflicht", "haftung"):
    AUSPRAEGUNGEN[_versicherung] = {
        "dimension": "geld", "einheitOptional": False, "sonst": "allgemein",
        "dimensionMuster": None,
        # ⚠ „kombiniert" ZUERST: 28 % der Belege lauten „3 Mio. EUR fuer Personen-, Sach- und
        # Vermoegensschaeden" — EINE Summe fuer alles. Die abgekuerzten Glieder tragen das Wort
        # „schaeden" nicht, deshalb traf die Schlagwortsuche nur das letzte und buchte eine
        # kombinierte Deckung als Vermoegensschaeden-Summe.
        "regeln": [{"name": "kombiniert", "muster": _AUFZ, "sperre": None, "band": None}]
                  + [{"name": n, "muster": m, "sperre": None, "band": None} for m, n in (
                      ("personenschäden", "Personenschäden"), ("sachschäden", "Sachschäden"),
                      ("umwelt", "Umweltschäden"), ("vermögensschäden", "Vermögensschäden"))],
    }

# ⚠ FILTER 2, das Urteil. Jeder Eintrag muss EINE Groesse benennen, sonst vergleicht die Anzeige
# Aepfel mit Birnen und sieht dabei serioes aus.
VERGLEICHBAR: dict[str, tuple[str, ...]] = {
    "berufshaftpflicht": ("geld",),      # Deckungssumme, je Schadensart getrennt
    "haftung": ("geld",),                # dito, aus dem Vertrag statt aus der Eignung
    # ⚠ NUR Prozent: in EUR mischt die Vertragsstrafe zwei Skalen (Drift 16,7×). Getrennt nach
    # Tagessatz und Obergrenze, s. AUSPRAEGUNGEN — 0,20 % je Werktag gegen 5 % insgesamt.
    "vertragsstrafe": ("prozent",),
    "referenz_anzahl": ("stueck",),      # „mindestens 3 Referenzen"
    "eignung_personal": ("jahre",),      # „mindestens 3 Jahre Berufserfahrung". NICHT Stueck
    "laufzeit": ("jahre",),              # Vertragslaufzeit
}

_LABEL = {
    "berufshaftpflicht": "Berufshaftpflicht", "haftung": "Haftungssumme",
    "vertragsstrafe": "Vertragsstrafe", "referenz_anzahl": "Referenzen",
    "eignung_personal": "Berufserfahrung", "laufzeit": "Laufzeit",
}


def _dimension(einheit: str | None) -> str | None:
    u = (einheit or "").strip().lower()
    return next((d for d, liste in EINHEITEN.items() if u in liste), None) if u else None


_REGELN = {rt: [(r["name"], re.compile(r["muster"], re.I),
                 re.compile(r["sperre"], re.I) if r["sperre"] else None, r["band"])
                for r in cfg["regeln"]]
           for rt, cfg in AUSPRAEGUNGEN.items()}


def _belegtext(einheit: str | None, zitat: str | None) -> str:
    """⚠ BEIDE FELDER SIND BELEG. Das Einheitenfeld traegt bei der Vertragsstrafe den halben
    Satz („der Auftragssumme je angefangenen Werktag"), das Zitat den anderen."""
    return f"{einheit or ''} {zitat or ''}".lower()


def _dimension_aus_beleg(cfg: dict | None, text: str) -> str | None:
    """Die Dimension aus dem Belegtext, wenn das Einheitenfeld keine bekannte Einheit ist."""
    muster = (cfg or {}).get("dimensionMuster")
    if not muster:
        return None
    for dim, p in muster.items():
        if re.search(p, text, re.I):
            return dim
    return None


def _regel_treffer(req_type: str, text: str, wert: float) -> str | None:
    """Die Unterart aus EINEM Text. `None` heisst: ausserhalb des Bandes, also nicht vergleichbar.

    ⚠ DIE SPERRE IST NICHT SCHMUCK. „0,2 % je Werktag, insgesamt höchstens 5 %" nennt BEIDE
    Zahlen in einem Satz; ohne Sperre landete der Tagessatz in der Obergrenzen-Gruppe und
    zerlegte deren Median. Solche Belege fallen lieber ganz raus (329 Stück)."""
    cfg = AUSPRAEGUNGEN.get(req_type)
    if not cfg:
        return ""
    for name, muster, sperre, band in _REGELN[req_type]:
        if not muster.search(text) or (sperre and sperre.search(text)):
            continue
        if band and not (band[0] <= wert <= band[1]):
            return None
        return name
    return cfg["sonst"]


def _auspraegung(req_type: str, einheit: str | None, zitat: str | None,
                 wert: float) -> str | None:
    """Die Unterart, EINHEITENFELD ZUERST.

    ⚠ GESCHWISTERZEILEN TEILEN SICH DAS ZITAT. Ein Vorgang mit „0,1 % der Auftragssumme je
    angefangenen Werktag" und „10 % der Auftragssumme" hat fuer BEIDE denselben Belegsatz; nur
    das Einheitenfeld ist zeilengenau. Wer den gemeinsamen Text zuerst liest, bekommt bei
    Vorgaengen, die beide Zahlen nennen, gar keine Zuordnung — und das sind genau die
    interessanten. Gemessen entscheidet das Einheitenfeld in 442 Faellen, das Zitat in 5.799;
    beide zusammen sind mehr als jedes allein.
    """
    ein = (einheit or "").lower()
    if ein.strip():
        treffer = _regel_treffer(req_type, ein, wert)
        if treffer not in (None, "", AUSPRAEGUNGEN.get(req_type, {}).get("sonst")):
            return treffer
    return _regel_treffer(req_type, f"{ein} {zitat or ''}", wert)


def _laender() -> list[str]:
    """Aus dem Bestand, nicht aus einer Liste im Code — sonst faellt ein neues Land stumm raus."""
    gold = ROOT / "data" / "gold"
    return sorted(p.name for p in gold.iterdir()
                  if p.is_dir() and (p / "doc_checklist.parquet").exists()) if gold.exists() else []


def main() -> int:
    con = duckdb.connect()
    gruppen: dict[str, dict] = {}
    verworfen: list[str] = []
    for land in _laender():
        C = (ROOT / "data" / "gold" / land / "doc_checklist.parquet").as_posix()
        A = ROOT / "data" / "gold" / land / "doc_analysis.parquet"
        tiefe = dict(con.execute(
            f"select notice_id, n_parsed_files from read_parquet('{A.as_posix()}')").fetchall()) if A.exists() else {}
        arten = ", ".join(f"'{r}'" for r in VERGLEICHBAR)
        roh = con.execute(f"""select notice_id, req_type, unit, wert_num, quote from read_parquet('{C}')
                              where wert_num is not null and req_type in ({arten})""").fetchall()
        sammel: dict[str, list[tuple[float, int]]] = {}
        for nid, rt, einheit, wert, zitat in roh:
            dim = _dimension(einheit)
            cfg = AUSPRAEGUNGEN.get(rt)
            text = _belegtext(einheit, zitat)
            # ⚠ Ist das Einheitenfeld keine bekannte Einheit, darf der Beleg einspringen — und
            # nur wo es erlaubt ist. Er entscheidet dann AUCH ueber Geld gegen Prozent: „€ je
            # Vorfall" faellt so heraus, statt als Prozentsatz gelesen zu werden.
            if dim is None and cfg and cfg["einheitOptional"]:
                dim = _dimension_aus_beleg(cfg, text) or (
                    cfg["dimension"] if not (einheit or "").strip() else None)
            if dim not in VERGLEICHBAR[rt]:
                continue
            art = _auspraegung(rt, einheit, zitat, float(wert))
            if art is None:
                continue
            sammel.setdefault(f"{land}|{rt}|{dim}|{art}", []).append(
                (float(wert), int(tiefe.get(nid) or 0)))

        for schluessel, werte in sorted(sammel.items(), key=lambda kv: -len(kv[1])):
            if len(werte) < MIND_GRUPPE:
                verworfen.append(f"{schluessel}: nur {len(werte)} Zahlen")
                continue
            flach = [w for w, t in werte if 1 <= t <= FLACH]
            tief = [w for w, t in werte if t >= TIEF]
            if len(flach) < MIND_BAND or len(tief) < MIND_BAND:
                verworfen.append(f"{schluessel}: Driftpruefung zu duenn "
                                 f"({len(flach)} flach / {len(tief)} tief)")
                continue
            a, b = statistics.median(flach), statistics.median(tief)
            drift = max(a, b) / max(min(a, b), 1e-9)
            if drift > MAX_DRIFT:
                verworfen.append(f"{schluessel}: Drift {drift:.1f}× "
                                 f"({a:,.0f} flach → {b:,.0f} tief) — misst die Lesetiefe")
                continue
            alle = sorted(w for w, _ in werte)
            gruppen[schluessel] = {
                "n": len(alle), "median": round(statistics.median(alle), 2),
                "hoch": round(statistics.quantiles(alle, n=4)[2], 2),
                "label": _LABEL.get(schluessel.split("|")[1], schluessel.split("|")[1]),
            }
        print(f"  {land}: {sum(1 for k in gruppen if k.startswith(land)):,} Gruppen tragen · "
              f"{len(verworfen):,} verworfen")

    # ⚠ LAUT MELDEN, WAS RAUSFLIEGT. Eine stille Auswahl liest sich spaeter wie „es gab nicht
    # mehr", und die naechste Sitzung sucht die fehlenden Vergleiche im Renderer.
    for zeile in verworfen:
        print(f"     verworfen  {zeile}")
    if not gruppen:
        print("FEHLT: keine Gruppe hat die Pruefung bestanden.")
        return 1
    OUT.write_text(json.dumps(
        {"gruppen": gruppen, "einheiten": EINHEITEN, "auspraegungen": AUSPRAEGUNGEN},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    zahlen = sum(g["n"] for g in gruppen.values())
    print(f"Schwellen → {OUT.name} ({OUT.stat().st_size / 1024:.1f} kB) · "
          f"{len(gruppen)} Gruppen über {zahlen:,} Zahlen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

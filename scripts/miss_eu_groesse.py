#!/usr/bin/env python3
"""Wie gross ist jedes TED-Land, und wie viele Firmen gewinnen dort?

    --umfang   Bekanntmachungen je Land (eine Abfrage je Land, exakt)
    --firmen   verschiedene Gewinnerfirmen je Land (blaettert durch die Zuschlaege)

DIE FRAGE. Fuer eine Aussage ueber den europaeischen Markt brauchen wir zwei Zahlen je Land:
wie viel dort ausgeschrieben wird, und wie viele Unternehmen dort nachweislich gewinnen. Die
zweite ist die ansprechbare Kundenbasis, und sie ist belegt statt geschaetzt.

⚠ DAS IST EINE MESSUNG, KEIN ONBOARDING. Kein Silber, kein Gold, kein Connector, kein
Abrufer. Es entsteht eine Datei mit Zahlen, sonst nichts. Wer daraus ein Land aufnehmen will,
liest `docs/land-onboarding.md`.

⚠ NUR OBERSCHWELLIG. TED kennt die nationale Ebene nicht. In den zwei Laendern, wo wir sie
gemessen haben, traegt sie 41 % (DE) bzw. 74 % (AT) des Aufkommens — die echte Marktgroesse
liegt also deutlich ueber dem, was hier steht. Diese Spanne gehoert an jede Zahl daneben.

## Die Sperre

⛔ `--aufgeloest` VERWEIGERT DEN DIENST. Die Entdopplung ueber `winner-identifier` laeuft,
liefert aber eine Zahl, die nachweislich falsch ist — und zwar ohne dass man es der Ausgabe
ansieht. Genau deshalb ist sie gesperrt: eine stille Falschzahl ist schlimmer als keine.

    Deutschland, August 2025:
      ueber Namen                          4.600 Firmen
      erster Versuch (Kennung ODER Name)   4.675   ← dieselbe Firma zweimal gezaehlt
      zweiter Versuch (gepaart)            5.144   ← immer noch zu hoch

Vier Fallen sind bisher aufgedeckt, jede beim Reparieren der vorigen:

  1. Die TED-Blaetterung deckelt bei 15.000 Treffern, ohne es zu melden. Behoben durch
     monatsweises Zerlegen (`_monate`).
  2. `winner-identifier` ist bei 100 % der benannten Gewinner gefuellt, enthaelt aber neben
     Registernummern auch reine Vorgangs-UUIDs. Behoben durch `kennung_taugt`.
  3. Wer je Zuschlag ENTWEDER Kennung ODER Name zaehlt, zaehlt dieselbe Firma doppelt, sobald
     sie einmal mit und einmal ohne Kennung auftaucht. Behoben durch Paarung.
  4. ⚠ OFFEN: bei rund 15 % der Zuschlaege sind Namens- und Kennungsliste nicht gleich lang
     (gemessen: 51 von 60 gleich, 3 ungleich, 6 halb leer). Dort werden weiterhin beide Seiten
     gezaehlt.

⛔ DIE GEGENPROBE IST GELAUFEN (2026-09-16) UND HAT DAS VERFAHREN WIDERLEGT. Dieselbe
Periode, dasselbe Land, nur TED-Zuschlaege, gegen `party_entity` (entitaetsaufgeloest):

    Wahrheit                  35.428 Firmen
    rein namensbasiert        37.587   +6,1 %
    dieses Kennungsverfahren  38.612   +9,0 %   ← SCHLECHTER als der Name

Die Kennung TRENNT, was zusammengehoert: verschiedene Steuer- und Registernummern derselben
Gruppe, oder dieselbe Firma mit wechselnder Kennungsart. In unseren eigenen Daten stehen
46.546 verschiedene `national_id` gegen 37.587 Namen — die Kennung ist FEINER als die Firma.

WAS FEHLT, und es steht in `gold._consolidate_by_national_id`: dort wird die Registernummer
**nur bei geteilter Postleitzahl** zum Zusammenfuehren benutzt (0 Fehlverschmelzungen
gemessen), dazu kuratierte Aliase. Ohne diese Absicherung ist die Kennung kein Fortschritt.
Ein EU-Verfahren braucht dasselbe: Kennung PLUS Ortsabgleich PLUS Aliasliste je Land.

NUETZLICH IST DIE GEGENPROBE TROTZDEM: Sie eicht die namensbasierte Zahl. In Deutschland
liegt sie 6,1 % ueber der Wahrheit. Ob das Verhaeltnis in anderen Laendern haelt, ist
ungeprueft — aber es ist die erste belegte Aussage darueber, WIE FALSCH die 228.405 sind.

Zum Weiterentwickeln: `--aufgeloest --unvalidiert-ok`.

⚠ `winner-name` kommt sprachgeschluesselt als {sprache: [namen]}. Ein Zuschlag traegt
mehrere Gewinner (Rahmenvertraege, Lose), und derselbe Name steht in mehreren Sprachen.
Deshalb wird ueber alle Sprachen vereinigt und dann normalisiert gezaehlt.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH = "https://api.ted.europa.eu/v3/notices/search"
SEITE = 250
TAKT = 0.4          # hoeflicher Abstand; TED antwortet unter Last mit HTML statt JSON

# ISO alpha-2 → alpha-3, wie TED sie in `buyer-country` erwartet.
LAENDER: dict[str, str] = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "HR": "HRV", "CY": "CYP", "CZ": "CZE",
    "DK": "DNK", "EE": "EST", "FI": "FIN", "FR": "FRA", "DE": "DEU", "GR": "GRC",
    "HU": "HUN", "IE": "IRL", "IT": "ITA", "LV": "LVA", "LT": "LTU", "LU": "LUX",
    "MT": "MLT", "NL": "NLD", "PL": "POL", "PT": "PRT", "RO": "ROU", "SK": "SVK",
    "SI": "SVN", "ES": "ESP", "SE": "SWE",
    # EWR und Schweiz veroeffentlichen ebenfalls in TED
    "NO": "NOR", "IS": "ISL", "LI": "LIE", "CH": "CHE",
}


def _frage(nutzlast: dict, versuche: int = 5) -> dict:
    for versuch in range(versuche):
        out = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", "90", "-X", "POST",
             "-H", "Content-Type: application/json", "-d", json.dumps(nutzlast), SEARCH],
            capture_output=True)
        try:
            return json.loads(out.stdout.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            time.sleep(2.0 * (2 ** versuch))   # 429 kommt als HTML, nicht als Fehlercode
    raise RuntimeError("Search-API liefert dauerhaft kein JSON")


def _zeitraum(seit: str, bis: str) -> str:
    return (f"publication-date>={seit.replace('-', '')} "
            f"AND publication-date<={bis.replace('-', '')}")


def umfang(seit: str, bis: str) -> dict[str, dict]:
    """Eine Abfrage je Land: Bekanntmachungen gesamt und davon Zuschlaege."""
    erg: dict[str, dict] = {}
    for a2, a3 in LAENDER.items():
        z = _zeitraum(seit, bis)
        alle = _frage({"query": f"buyer-country={a3} AND {z}",
                       "fields": ["publication-number"], "limit": 1, "page": 1})
        time.sleep(TAKT)
        zusch = _frage({"query": f"buyer-country={a3} AND {z} AND notice-type=can-standard",
                        "fields": ["publication-number"], "limit": 1, "page": 1})
        time.sleep(TAKT)
        erg[a2] = {"bekanntmachungen": alle.get("totalNoticeCount") or 0,
                   "zuschlaege": zusch.get("totalNoticeCount") or 0}
        print(f"  {a2}  {erg[a2]['bekanntmachungen']:>9,} Bekanntmachungen · "
              f"{erg[a2]['zuschlaege']:>8,} Zuschlaege", flush=True)
    return erg


# ⚠ WAS EINE KENNUNG WERT IST, STEHT NICHT IM FELD. `winner-identifier` ist bei 100 % der
# benannten Gewinner gefuellt (gemessen 2026-09-16, fuenf Laender) — aber der Inhalt ist ein
# Gemischtwarenladen: echte Registernummern (`DE310303402`, SIRET `54205494500416`) neben
# reinen Vorgangs-UUIDs (`8fb4b194-6b79-4319-b113-9fac454095f7`), die ausserhalb des einen
# Dokuments nichts identifizieren. Wer auf einer UUID entdoppelt, ERHOEHT die Firmenzahl.
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def kennung_taugt(wert: object) -> bool:
    """Traegt der Wert eine Registernummer, oder ist er nur dokumentlokal?"""
    s = " ".join(str(wert or "").split()).replace(" ", "")
    if not s or _UUID.match(s):
        return False
    ziffern = sum(c.isdigit() for c in s)
    # Registernummern sind ueberwiegend Ziffern, mit optionalem Laenderpraefix.
    return len(s) >= 6 and ziffern >= max(5, len(s) // 2)


def _normal(wert: object) -> str:
    return " ".join(str(wert or "").upper().split()).replace(" ", "").replace("-", "")


def _namen(knoten: object) -> list[str]:
    """`winner-name` kommt als {sprache: [namen]} — ueber alle Sprachen vereinigen."""
    if isinstance(knoten, dict):
        raus: list[str] = []
        for wert in knoten.values():
            raus += _namen(wert)
        return raus
    if isinstance(knoten, list):
        raus = []
        for wert in knoten:
            raus += _namen(wert)
        return raus
    return [str(knoten)] if knoten else []


# ⚠ DIE SCHNITTSTELLE DECKELT DIE BLAETTERUNG BEI 15.000 TREFFERN. Gemessen am 2026-09-16:
# Bulgarien hat 16.747 Zuschlaege, geliefert wurden 15.000, und die Abfrage meldete keinen
# Fehler. Ohne Gegenmassnahme waeren genau die grossen Laender untermessen gewesen — DE
# 58.406, PL 45.345, FR 32.591, ES 26.661, CZ 26.006, RO 24.182 — also die, auf die es
# ankommt. Deshalb wird der Zeitraum in MONATE zerlegt; kein Monat erreicht den Deckel.
API_DECKEL = 15_000


def _monate(seit: str, bis: str) -> list[tuple[str, str]]:
    """Den Zeitraum in Kalendermonate zerlegen, damit keine Abfrage den Deckel reisst."""
    import calendar
    import datetime as dt
    a = dt.date.fromisoformat(seit)
    e = dt.date.fromisoformat(bis)
    raus, jahr, monat = [], a.year, a.month
    while (jahr, monat) <= (e.year, e.month):
        erster = dt.date(jahr, monat, 1)
        letzter = dt.date(jahr, monat, calendar.monthrange(jahr, monat)[1])
        raus.append((max(erster, a).isoformat(), min(letzter, e).isoformat()))
        jahr, monat = (jahr + 1, 1) if monat == 12 else (jahr, monat + 1)
    return raus


def firmen(a2: str, seit: str, bis: str, deckel: int | None,
           mit_kennung: bool = False) -> tuple[int, int, bool] | tuple[int, int, bool, dict]:
    """Verschiedene Gewinnerfirmen des Landes. Gibt (firmen, gelesene Zuschlaege, vollstaendig).

    Monatsweise, weil die Schnittstelle bei 15.000 abschneidet. Die Firmenmenge wird ueber
    alle Monate vereinigt — eine Firma, die in drei Monaten gewinnt, zaehlt einmal.
    """
    a3 = LAENDER[a2]
    gesehen: set[str] = set()     # Namen, nur wo keine brauchbare Kennung vorlag
    kennungen: set[str] = set()   # Registernummern, der bessere Schluessel
    name_zu_kennung: dict[str, str] = {}   # Name → Kennung, aus paarbaren Zuschlaegen
    gelesen, erwartet, voll = 0, 0, True
    for m_seit, m_bis in _monate(seit, bis):
        q = (f"buyer-country={a3} AND {_zeitraum(m_seit, m_bis)} "
             f"AND notice-type=can-standard")
        seite, im_monat, gesamt = 1, 0, None
        while True:
            felder = ["publication-number", "winner-name"]
            if mit_kennung:
                felder.append("winner-identifier")
            d = _frage({"query": q, "fields": felder, "limit": SEITE, "page": seite})
            gesamt = gesamt if gesamt is not None else (d.get("totalNoticeCount") or 0)
            stapel = d.get("notices") or []
            for n in stapel:
                namen = [" ".join(x.lower().split()) for x in _namen(n.get("winner-name"))
                         if len(" ".join(x.lower().split())) > 2]
                if not mit_kennung:
                    gesehen.update(namen)
                    continue
                # ⚠ ERST PAAREN, DANN ZAEHLEN. Der erste Entwurf zaehlte je Zuschlag
                # ENTWEDER Kennungen ODER Namen — und damit dieselbe Firma zweimal, wenn sie
                # einmal mit und einmal ohne Kennung auftauchte. Gemessen am 2026-09-16 wurde
                # die Zahl dadurch GROESSER (4.675 statt 4.600) statt kleiner. Deshalb werden
                # Paare gesammelt und erst am Schluss aufgeloest.
                roh = n.get("winner-identifier") or []
                # Eine Sprachfassung reicht; die Reihenfolge entspricht der Kennungsliste
                # (gemessen: 51 von 60 Zuschlaegen gleich lang, 3 ungleich, 6 halb leer).
                nm = n.get("winner-name")
                eine_sprache = (list(nm.values())[0] if isinstance(nm, dict) and nm else nm) or []
                eine_sprache = [" ".join(str(x).lower().split()) for x in eine_sprache]
                if len(eine_sprache) == len(roh) and roh:
                    for name, kennung in zip(eine_sprache, roh):
                        if kennung_taugt(kennung):
                            k = _normal(kennung)
                            kennungen.add(k)
                            if len(name) > 2:
                                name_zu_kennung.setdefault(name, k)
                        elif len(name) > 2:
                            gesehen.add(name)
                else:
                    # Nicht paarbar: beide Seiten getrennt merken, Aufloesung am Schluss.
                    for kennung in roh:
                        if kennung_taugt(kennung):
                            kennungen.add(_normal(kennung))
                    gesehen.update(namen)
            im_monat += len(stapel)
            if not stapel or im_monat >= gesamt or im_monat >= API_DECKEL:
                if im_monat >= API_DECKEL and gesamt > API_DECKEL:
                    voll = False   # selbst ein Monat reisst den Deckel: ehrlich melden
                break
            if deckel and gelesen + im_monat >= deckel:
                voll = False
                break
            seite += 1
            time.sleep(TAKT)
        gelesen += im_monat
        erwartet += gesamt or 0
        time.sleep(TAKT)
    voll_ok = voll and gelesen >= erwartet
    if mit_kennung:
        # Namen, die anderswo unter einer Kennung auftauchten, sind KEINE eigene Firma.
        rest = {n for n in gesehen if n not in name_zu_kennung}
        return len(kennungen) + len(rest), gelesen, voll_ok, {
            "ueber_kennung": len(kennungen), "ueber_name": len(rest),
            "namen_zugeordnet": len(gesehen) - len(rest)}
    return len(gesehen), gelesen, voll_ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seit", default="2024-09-01")
    p.add_argument("--bis", default="2025-08-31")
    p.add_argument("--umfang", action="store_true")
    p.add_argument("--firmen", action="store_true")
    p.add_argument("--aufgeloest", action="store_true",
                   help="⚠ UNVALIDIERT, s. Modulkopf — verweigert ohne --unvalidiert-ok")
    p.add_argument("--unvalidiert-ok", action="store_true",
                   help="die Sperre loesen; nur zum Weiterentwickeln, nie fuer eine Aussage")
    p.add_argument("--land", default=None, help="nur dieses Land (fuer --firmen)")
    p.add_argument("--deckel", type=int, default=None, help="hoechstens N Zuschlaege je Land lesen")
    p.add_argument("--aus", default="data/analyse/eu_groesse.json")
    a = p.parse_args()

    ziel = Path(a.aus)
    bestand = json.loads(ziel.read_text(encoding="utf-8")) if ziel.exists() else {}
    bestand.setdefault("zeitraum", {"seit": a.seit, "bis": a.bis})

    if a.umfang:
        print(f"── Umfang je Land, {a.seit} bis {a.bis} ──")
        bestand["umfang"] = umfang(a.seit, a.bis)
    if a.aufgeloest and not getattr(a, "unvalidiert_ok", False):
        print(__doc__.split("## Die Sperre")[-1].strip(), file=sys.stderr)
        return 2
    if a.firmen:
        print(f"── Firmen je Land, {a.seit} bis {a.bis} ──")
        bestand.setdefault("firmen", {})
        schluessel = "firmen_aufgeloest" if a.aufgeloest else "firmen"
        bestand.setdefault(schluessel, {})
        for a2 in ([a.land] if a.land else list(LAENDER)):
            erg = firmen(a2, a.seit, a.bis, a.deckel, mit_kennung=a.aufgeloest)
            if a.aufgeloest:
                n, gelesen, voll, teile = erg
                bestand[schluessel][a2] = {"firmen": n, "zuschlaege_gelesen": gelesen,
                                           "vollstaendig": voll, **teile}
                print(f"  {a2}  {n:>8,} Firmen  ({teile['ueber_kennung']:,} über Kennung, "
                      f"{teile['ueber_name']:,} nur Name, {teile['namen_zugeordnet']:,} zugeordnet)"
                      f"{'' if voll else '  ⚠ unvollstaendig'}", flush=True)
            else:
                n, gelesen, voll = erg
                bestand[schluessel][a2] = {"firmen": n, "zuschlaege_gelesen": gelesen,
                                           "vollstaendig": voll}
                print(f"  {a2}  {n:>8,} Firmen aus {gelesen:,} Zuschlaegen{'' if voll else '  ⚠ unvollstaendig'}", flush=True)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(bestand, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")
    print(f"\n  → {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Quellen-übergreifender Dublettencheck — ein Durchlass für ALLE Quellen eines Landes.

**Warum das nicht je Quelle gebaut gehört.** Vorher gab es ``dedupe_at_sources.py`` und
``dedupe_ch_sources.py`` — zwei Skripte für dasselbe Problem, und für DTVP fehlte prompt ein
drittes. Ergebnis: von den ersten 60 geholten DTVP-Vorgängen waren **44 echte Dubletten**
(identischer Titel UND identische Vergabestelle), höchstens 4 neu. Die Vergleichslogik ist
aber in allen Fällen dieselbe — *dasselbe Verfahren, auf zwei Plattformen veröffentlicht*.
Nur das Quellenpaar wechselt. Mit jeder neuen Quelle wächst die Zahl der Paare quadratisch,
die Zahl der nötigen Skripte auch, und irgendeins fehlt immer.

Deshalb hier **eine Prüfung, durch die jeder Satz muss**, unabhängig davon, woher er kommt.

**Die Regeln sind übernommen, nicht neu erfunden.** ``measure_at_overlap.py`` hat sie an
8.788 sicheren Paaren gemessen; sie noch einmal zu erfinden hiesse, dieselben drei Fehler
noch einmal zu machen:

* **±90 Tage** aus der Abstandsverteilung (Median 2 T, 96 % binnen 90). 180 Tage bringen
  einen Punkt mehr und fangen dafür gleichnamige Wiederholungsvergaben ein.
* **Enthaltung ≥ 0,8 statt symmetrischer Deckung.** Die eine Seite stellt eine Vorgangs-ID
  voran, die andere hängt „- Los 2" an; symmetrisch fällt beides durch. Gemessen wird der
  Anteil der KLEINEREN Wortmenge, der in der grösseren steckt.
* **Seed über die drei seltensten INDIZIERTEN Wörter.** Über ein einzelnes seltenes Wort
  (z. B. eine plattformeigene Vorgangsnummer) findet man null Kandidaten und hält die
  Dublette für neu.

**Die zweite Hälfte — Dublette heisst nicht wertlos.** Ein doppelter Satz wird nicht
weggeworfen, sondern auf ZUSATZINFORMATION geprüft: trägt er ein Feld, das der Master nicht
hat? Gemessen kommt das häufig vor — die nationale Quelle hat oft einen Schätzwert, wo TED
keinen führt, und umgekehrt trägt TED CPV und NUTS, wo die nationale Quelle nichts hat.
``anreicherung()`` liefert das feldweise, damit ein späterer Merge nicht raten muss.
Das ist der Unterschied zwischen „Dublette verwerfen" und „Dublette einschmelzen".

**Warum das eine Python-Schleife bleibt.** Der Abgleich wurde 2026-08-14 vollstaendig als
DuckDB-Abfrage nachgebaut (Kandidaten als Join, Enthaltung als Listenarithmetik) — und war
gemessen **zwei- bis dreimal langsamer**: CH ab 2024 5 s gegen 9 s, AT ab 2024 111 s gegen
44 s. Beide Fassungen lieferten dieselben Paare, die SQL-Variante ist also korrekt, nur
teurer: DuckDB zahlt pro Zeile mehr fuer ``list_intersect``, als Pythons ``frozenset``-
Schnitt kostet, und die Kandidatenmenge ist gross.

**Inkrementell: das rollende Fenster (2026-08-17).** Der Schritt war mit gemessenen
188 min der teuerste des Tageslaufs — er verglich jede Nacht die volle Historie ab 2004,
um Paare unter rund 700 neuen Bekanntmachungen zu finden. ``--fenster-tage 190`` laedt
stattdessen nur die letzten N Tage plus alle Saetze OHNE Datum.

Das ist verlustfrei, aber nur unter zwei Bedingungen, und beide muessen zusammen gelten:

1. **N deutlich groesser als 2 x FENSTER_TAGE.** Ein Paar liegt binnen 90 Tagen; ein
   Fenster von 190 kann also nur Paare verpassen, deren BEIDE Seiten aelter sind — und
   die hat ein frueherer Lauf gefunden.
2. **Das Ergebnis wird VEREINIGT, nicht geschrieben** (``schreibe(..., vereinigen=True)``,
   automatisch bei gesetztem Fenster). Ohne das waere der erste Nachtlauf ein stiller
   Totalverlust der Historie.

Gemessen (Paarung, ``--alle-arten``, ab 2004), Fenster gegen Vollauf:

    CH    120.641 Saetze   7,5 s  ->   18.228 im Fenster   0,9 s    8x
    AT    414.172 Saetze  39,4 s  ->   26.882 im Fenster   2,0 s   20x
    DE  2.221.669 Saetze          ->  163.049 im Fenster  41,5 s

In allen drei Faellen fand das Fenster **kein Paar, das der Vollauf nicht auch fand**.

**⚠ WAS DAS FENSTER NICHT ERKLAERT.** Die Versuchung war, die 188 min dem Vollabgleich
zuzuschreiben. Nachgemessen stimmt das nicht:

    DE Paarung voll   13,1 min      AT 0,7 min      CH 0,1 min
    Anreicherung DE    0,0 min      (sechs Joins, aber gegen eine winzige Dublettentabelle)

Zusammen rund 14 min gegen 188 im Nachtlauf. Die fehlenden 174 min erklaert der Algorithmus
NICHT. Was sie erklaert, ist die Nachbarschaft: unmittelbar davor liefen fuenf Stunden
Dokumentendownload (aumass 52, Staatsanzeiger 133, vergabeportal.at 108 min) und haben den
Dateicache mit Gigabyte an ZIPs geflutet. Die Messungen hier sind Warm-Cache-Werte, der
Nachtlauf las kalt — fuenfmal ueber 2,2 Mio Zeilen.

Das ist eine begruendete Vermutung, kein Beweis. Zwei Dinge folgen daraus:

* Das Fenster hilft genau hier am meisten: es liest 7,3 % der Daten, und Kaltlesen ist
  das, was ein kleiner Ausschnitt am staerksten spart.
* Der eigentliche Fix war der UMBAU DER REIHENFOLGE (2026-08-17, `daily_leads.sh`): die
  Firewall laeuft jetzt VOR den Abrufern, auf einem Cache, den niemand zugemuellt hat.
  Das war beim Bauen nicht der Grund, ist aber vermutlich der groessere Effekt.

Belegen wird es der naechste Nachtlauf. Wer die Zahl nachtraegt, schreibt sie hierher.

**Warum trotzdem sonntags voll.** Nicht aus Misstrauen gegen die Rechnung, sondern gegen
ihre Annahmen: ruecklaufende Korrekturen an alten Saetzen, ein geaenderter Schwellwert,
eine neue Quelle, die Altbestand mitbringt. Der Wochenlauf faengt das ein.

Die Beschleunigung kam am Ende von woanders — aus dem **Seed-Deckel** (s. ``finde``), der
das Problem an der Wurzel packt statt an der Ausfuehrungsschicht. Er wirkt auf jede
Implementierung. Die SQL-Fassung wurde deshalb wieder entfernt; wer sie erneut versucht,
sollte zuerst die Kandidatenzahl messen, nicht die Engine wechseln.

**Was hier NICHT passiert.** Es wird nichts gelöscht und nichts überschrieben. Ergebnis ist
eine Tabelle ``gold/<C>/notice_duplicates.parquet`` — wer sie benutzt, entscheidet der
Aufrufer. Projekt-Konvention: markieren statt filtern.

Aufruf::

    python3 -m govisor.dedupe --country DE --ab-jahr 2026
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import re
import sys
from collections import Counter, defaultdict

from . import entities as _entities
from . import db as _db
from . import locales as _locales
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FENSTER_TAGE = 90          # aus der Abstandsverteilung, s. measure_at_overlap.py
MIN_ENTHALTUNG = 0.8       # Anteil der kleineren Wortmenge in der grösseren
MIN_WORTE = 3              # darunter ist ein Titel kein Unterscheidungsmerkmal
SEED_WORTE = 3             # Kandidaten über die N seltensten indizierten Wörter
SEED_DECKEL = 5000         # zu häufige Wörter taugen nicht als Einstieg (gemessen, s. finde)

# Wer gewinnt, wenn zwei Sätze dasselbe Verfahren beschreiben? Die reichere Quelle.
# TED trägt CPV, NUTS, Lose und Werte; nationale Portale meist nur die Trefferzeile.
# Der Master ist damit derjenige, an den angereichert wird.
#
# ⚠ FELD-REICHTUM IST NICHT AKTUALITÄT. Gemessen 2026-08-13: von 70 Leads, die man beim
# Ausschluss von Dubletten verlieren würde, haben **64 einen Master, der selbst kein Lead
# ist** — bei 61 davon ist die Frist des Masters ABGELAUFEN. Beispiel: TED führt
# „Universitätsklinikum Tübingen, Anbau Frauenklinik" mit Frist 30.06., die DÖE-Fassung
# derselben Vergabe hat eine laufende. Bei wiederholt ausgeschriebenen Vergaben ist der
# SPÄTERE Satz der gültige, und das ist oft die nationale Quelle.
#
# Diese Rangfolge taugt deshalb NUR für die Anreicherungsrichtung (wohin fehlende Felder
# fliessen), NICHT als Entscheidung, welcher Satz ein Lead wird. Ein Ausschluss von
# Dubletten auf ihrer Basis haette 6 echte Dubletten entfernt und 64 gueltige Leads mit.
# `netserver` steht hinter dtvp, weil eine NetServer-Trefferzeile das ärmste Satzbild im
# Bestand hat: kein CPV (ausser der Ableitung aus VOB/A), kein Wert, keine Beschreibung,
# bei Bremen nicht einmal die Vergabestelle. Als Anreicherungs-ZIEL ist er damit richtig —
# als Quelle fehlender Felder taugt er kaum.
# `healyhudson` steht ganz hinten und aus demselben Grund wie netserver: die Trefferliste
# gibt Titel, Vergabestelle, Verordnung und zwei Daten her — keinen CPV, keinen Wert, keine
# Beschreibung, nicht einmal einen Link zum Vorgang. Als Anreicherungs-ZIEL richtig, als
# Feldquelle wertlos. Ausdruecklich eingetragen statt auf den `.get(..., 9)`-Vorgabewert zu
# vertrauen: der wuerde dasselbe tun, aber niemand koennte lesen, dass es Absicht war.
QUELLEN_RANG = {"eforms": 0, "legacy": 1, "ojs": 2, "text": 3,
                "doe": 4, "simap": 4, "atverg": 4, "dtvp": 5, "netserver": 6,
                "healyhudson": 7}

_STOPP = frozenset("""der die das und oder von für mit im in am an auf zu zur zum des dem den
eines einer eine ein als bei aus über unter nach vor durch gemäss gemäß sowie inkl inklusive
los lose teil ba bauabschnitt vergabe ausschreibung arbeiten lieferung leistung leistungen
neubau sanierung erneuerung""".split())


def worte(s: str | None) -> frozenset[str]:
    """Titel → bedeutungstragende Wörter. Zahlen bleiben (Los-/Vergabenummern trennen)."""
    if not s:
        return frozenset()
    roh = re.findall(r"[a-zà-ÿA-ZÀ-Þ0-9]{3,}", s.lower())
    return frozenset(w for w in roh if w not in _STOPP)


def zahlen(s: str | None) -> frozenset[str]:
    """Alle Zahlfolgen aus dem ROHTITEL — auch ein- und zweistellige.

    `worte()` behaelt nur Tokens ab drei Zeichen. „26.39" zerfaellt dort in „26" und
    „39", beide zweistellig, beide verworfen — die Losnummer verschwindet also, BEVOR
    die Los-Sperre sie sehen kann. Gemessen an den Paaren „26.39 / 26.40 / 26.30 —
    Grundschulerweiterung und Ersatzneubau MZH", die als Dubletten in der Tabelle
    landeten, obwohl die Nummer sie klar trennt.

    Fuehrende Nullen fallen weg, damit „Los 03" und „Los 3" dieselbe Nummer sind.
    """
    if not s:
        return frozenset()
    return frozenset(x.lstrip("0") or "0" for x in re.findall(r"\d+", s))


def _enthaltung(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _laden(country: str, ab_jahr: int, alle_arten: bool = False,
           fenster_tage: int = 0):

    g = glob.glob(f"{ROOT}/data/silver/{country}/notices/**/*.parquet", recursive=True)
    p = glob.glob(f"{ROOT}/data/silver/{country}/notice_parties/**/*.parquet", recursive=True)
    con = _db.connect()
    return con.execute(f"""
        SELECT n.notice_id, n.schema_gen, n.title, n.notice_kind,
               coalesce(n.publication_date, n.submission_deadline) AS d,
               b.buyer_name AS buyer, b.buyer_id AS buyer_id,
               n.cpv_main, n.estimated_value, n.submission_deadline,
               n.performance_nuts, n.description
        FROM read_parquet({g!r}) n
        LEFT JOIN (SELECT notice_id, min(name) AS buyer_name,
                          min(national_id) AS buyer_id FROM read_parquet({p!r})
                   WHERE role='buyer' GROUP BY 1) b USING (notice_id)
        WHERE n.title IS NOT NULL
          -- ARTEN. Standard sind Ausschreibungen (`cn`/`pin`) — das ist die Lead-Sicht und
          -- der taegliche Lauf. `alle_arten` nimmt auch Zuschlaege (`can`), Aufhebungen,
          -- Direktvergaben usw. dazu; das ist die VEROEFFENTLICHUNGS-Sicht, die Marktpuls
          -- braucht, weil er Publikationen je Jahr zaehlt und sonst AT/CH doppelt zaehlt.
          -- Gemessen 2026-08-13 gegen die abgeloesten Quellskripte: von 4.345 AT-Treffern,
          -- die nur SIE fanden, waren 3.403 Zuschlaege; in CH 2.385 von 2.695.
          {{ARTEN}}
          -- Jahr ODER laufende Frist. `ab_jahr` allein war der falsche Schnitt: eine 2024
          -- veroeffentlichte Rahmenvereinbarung mit Frist in 2027 ist HEUTE ein offener
          -- Lead, faellt aber aus jedem Jahresfenster. Gemessen 2026-08-13: 1.940 offene
          -- Bekanntmachungen blieben so unsichtbar (DE 1.516, AT 422, CH 2) — bei atverg
          -- 367 von 1.044, also gut ein Drittel, weil OeBB & Co. mit langen Laufzeiten
          -- ausschreiben. Genau dort sitzen die Dubletten, die uns interessieren.
          AND (coalesce(n.year, 0) >= {int(ab_jahr)}
               OR CAST(n.submission_deadline AS DATE) >= current_date)
          {{FENSTER}}
    """.replace("{ARTEN}", "" if alle_arten else
                 "AND n.notice_kind IN ('cn','pin')")
       .replace("{FENSTER}", "" if not fenster_tage else f"""
          -- ROLLENDES FENSTER (inkrementeller Nachtlauf).
          --
          -- Ein Paar muss binnen FENSTER_TAGE (90) liegen. Wer nur die letzten N Tage
          -- laedt, kann deshalb hoechstens Paare verlieren, deren BEIDE Seiten aelter
          -- sind als N — und die hat ein frueherer Lauf schon gefunden und geschrieben.
          -- Verlustfrei ist das aber NUR unter zwei Bedingungen, beide hart:
          --   1. N deutlich groesser als 2 x FENSTER_TAGE (Standard 190 gegen 180),
          --   2. das Ergebnis wird mit dem Bestand VEREINIGT statt darueber geschrieben
          --      (`schreibe(..., vereinigen=True)`).
          --
          -- Saetze OHNE Datum bleiben immer dabei: sie paaren mit allem und laufen
          -- deshalb in jeder Zeitscheibe mit. In DE sind das 16.694, in AT und CH null.
          AND (coalesce(n.publication_date, n.submission_deadline) IS NULL
               OR coalesce(n.publication_date, n.submission_deadline)
                  >= current_date - {int(fenster_tage)})""")).fetchall()


def finde(country: str = "DE", ab_jahr: int = 2026,
          alle_arten: bool = False, fenster_tage: int = 0) -> list[dict]:
    """Alle Dubletten-Paare eines Landes, quellenübergreifend.

    ``alle_arten=False`` (Standard) prüft nur Ausschreibungen — die Lead-Sicht, täglicher
    Lauf. ``True`` nimmt Zuschläge und alle übrigen Arten dazu: die Veröffentlichungs-Sicht
    für Marktpuls. Beides ist DIESELBE Prüfung, nur ein anderer Ausschnitt; zwei Skripte
    daraus zu machen wäre der Rückfall in genau das, was dieses Modul abgelöst hat.
    """
    # LOCALE JE LAND. Ohne das lief der Wall fuer AT und CH mit dem DE-Profil, weil
    # `locales.active()` auf DE vorbelegt ist und NIEMAND es umgestellt hat. Folge:
    # `normalize_company` kannte oesterreichische Rechtsformen nicht, „KRAGES … GesmbH"
    # und „Krages …" galten als verschiedene Kaeufer. Gemessen 2026-08-23 an AT: allein
    # das Umstellen macht 31 Paare kaeuferbelegt, die vorher nur einen Titelbeleg hatten.
    # Der Aufruf gehoert hierher und nicht in die CLI, weil `finde()` auch aus Skripten
    # kommt (build_dach_gold) — dort haette die CLI-Variante lautlos gefehlt.
    _locales.use(country)
    zeilen = _laden(country, ab_jahr, alle_arten, fenster_tage)
    wie = f"ab {ab_jahr}" if not fenster_tage else f"aus den letzten {fenster_tage} Tagen (+ ohne Datum)"
    print(f"  {len(zeilen):,} Bekanntmachungen {wie} geladen")
    saetze = _saetze(zeilen)
    return _in_zeitscheiben(saetze)


# Kennungen, die KEINE sind. Gemessen an AT: „0" steht bei 510 verschiedenen Kaeufern,
# „1" bei 178, „AT" bei 133. Wer sie als Gleichheitsbeleg nimmt, verschmilzt fremde Haeuser.
_KENNUNG_MUELL = {"0", "1", "at", "de", "ch", "n a", "na", "keine", "999999"}


def _kennung(v: str | None) -> str:
    """Vergleichsform einer Kaeufer-Kennung, oder "" wenn sie nichts beweist."""
    k = re.sub(r"[^a-z0-9]", "", (v or "").lower())
    return "" if len(k) < 6 or k in _KENNUNG_MUELL else k


def _kaeufer_gleich(s: dict, t: dict) -> bool:
    """Sind das zwei Namen DESSELBEN Kaeufers?

    Zwei Wege. Der erste ist die Normalform des Namens — sie traegt die Hauptlast.
    Der zweite ist die amtliche Kennung, und der ist noetig, weil AT und CH dieselbe
    Stelle je nach Quelle voellig anders schreiben: TED meldet „ASFINAG Autobahnen- und
    Schnellstrassen-Finanzierungs-AG", offenevergaben.at den ausgeschriebenen Namen ohne
    das Kuerzel. Keine Normalisierung der Welt fuehrt diese beiden zusammen.

    Die Kennung allein reicht aber NICHT, und das ist der teuer gemessene Teil: die
    oesterreichischen GLN sind Dachkennungen. `9110027589349` traegt die OeGK-Landesstellen
    Wien, Steiermark UND Kaernten, `FN92191a` deckt 60 verschiedene ASFINAG-Namen ab. Wer
    auf Kennungsgleichheit allein merged, wirft die Landesstelle Wien mit der steirischen
    zusammen — bei kurzen Gewerketiteln passiert das sofort.
    Deshalb muss die Kennung stimmen UND die Namen duerfen sich nicht WIDERSPRECHEN: einer
    ist Teilmenge des anderen (Kuerzel-Praefix, Dachname vs. Dienststelle) oder beide sind
    gleich. Traegt jede Seite ein eigenes Wort („Wien" gegen „Steiermark"), gilt der Beleg
    nicht. Gemessen 2026-08-23 an AT: +147 Paare belegt, 1.055 widerspruechliche bleiben
    bewusst aussen vor.
    """
    if s["buyer"] and s["buyer"] == t["buyer"]:
        return True
    if not (s["bid"] and s["bid"] == t["bid"]):
        return False
    a, b = set(s["buyer"].split()), set(t["buyer"].split())
    return bool(a and b and (a <= b or b <= a))


def _saetze(zeilen) -> list[dict]:
    """Rohzeilen → vergleichsfertige Sätze (Wortmenge, Zahlen, Käufer-Normalform)."""
    saetze = []
    for nid, gen, titel, art, d, buyer, buyer_id, cpv, wert, frist, nuts, beschr in zeilen:
        w = worte(titel)
        if len(w) < MIN_WORTE:
            continue                      # zu kurz für eine belastbare Aussage
        # Kaeufername ueber die PROJEKTEIGENE Normalform vergleichen, nicht roh.
        # `normalize_company` entfernt Akzente, Klammerzusaetze, Vertretungsklauseln,
        # Abteilungs-Anhaengsel, Rechtsformen und Einkaufskreis-Nummern — an echten Daten
        # erprobt (122.860 Kaeufernamen → 75.306 Normalformen). Der rohe Vergleich davor
        # liess „bundesagentur fuer arbeit, regionales einkaufszentrum nrw" und dieselbe
        # Zeichenkette OHNE Komma als verschiedene Kaeufer durchgehen. Gemessen: +941 Paare
        # bekommen dadurch einen Kaeufer-Beleg, 2.918 → 3.859 von 6.794.
        saetze.append({"id": nid, "gen": gen or "?", "titel": titel, "w": w,
                       "z": zahlen(titel), "art": art, "d": d,
                       "buyer": _entities.normalize_company(buyer) if buyer else "",
                       "bid": _kennung(buyer_id),
                       "cpv": cpv, "wert": wert,
                       "frist": frist, "nuts": nuts, "beschr": beschr})

    return saetze


def _in_zeitscheiben(saetze: list[dict]) -> list[dict]:
    """Abgleich JAHRESWEISE statt über den ganzen Bestand — verlustfrei und der Hebel.

    Ein Paar muss binnen ``FENSTER_TAGE`` liegen; das war bisher ein Filter NACH der
    Kandidatenbildung. Gepaart wurde quer über 22 Jahrgänge und anschliessend fast alles
    verworfen — der Aufwand wächst dabei quadratisch mit dem Bestand, obwohl zwei Sätze aus
    2008 und 2019 sich per Definition nie treffen können.

    Hier wird dieselbe Bedingung VOR die Kandidatenbildung gezogen: je Jahrgang bekommt der
    Abgleich nur die Sätze dieses Jahres plus ``FENSTER_TAGE`` Rand nach beiden Seiten. Der
    Rand ist Pflicht, sonst zerschneidet der Jahreswechsel echte Paare (TED im Dezember,
    nationale Quelle im Januar). Sätze ohne jedes Datum können mit allem paaren und laufen
    deshalb in JEDER Scheibe mit — in AT und CH gibt es davon 0, in DE 16.020 (0,7 %).

    Paare aus überlappenden Rändern werden über (master_id, duplicate_id) entdoppelt.
    """
    import datetime as _dt
    from collections import defaultdict as _dd

    ohne_datum = [s for s in saetze if not s["d"]]
    nach_jahr: dict[int, list[dict]] = _dd(list)
    for s in saetze:
        if s["d"]:
            nach_jahr[s["d"].year].append(s)
    if len(nach_jahr) <= 1:
        return _paare_finden(saetze)

    # Worthaeufigkeit EINMAL ueber den ganzen Bestand, nicht je Scheibe. Sonst waehlt jede
    # Scheibe andere Seeds (in einem kleineren Ausschnitt ist ein Wort seltener), und das
    # Ergebnis haengt am Zuschnitt statt an den Daten. Gemessen, als sie noch scheibenlokal
    # war: CH ab 2024 fand 18.144 statt 18.146 Paaren — klein, aber ein Zuschnitt-Artefakt.
    haeufigkeit: dict[str, int] = _dd(int)
    for s in saetze:
        for w in s["w"]:
            haeufigkeit[w] += 1

    rand = _dt.timedelta(days=FENSTER_TAGE)
    zusammen: dict[tuple, dict] = {}
    for jahr in sorted(nach_jahr):
        von = _dt.date(jahr, 1, 1) - rand
        bis = _dt.date(jahr, 12, 31) + rand
        scheibe = [s for s in saetze if s["d"] and von <= s["d"] <= bis] + ohne_datum
        for p in _paare_finden(scheibe, haeufigkeit):
            zusammen.setdefault((p["master_id"], p["duplicate_id"]), p)
    return list(zusammen.values())


def _paare_finden(saetze: list[dict], haeufigkeit: dict | None = None) -> list[dict]:
    """Der eigentliche Abgleich über eine (Teil-)Menge von Sätzen.

    ``haeufigkeit`` ist die GLOBALE Wortstatistik; sie steuert die Seed-Auswahl, damit
    diese vom Scheiben-Zuschnitt unabhaengig bleibt. Ohne sie (Einzellauf) wird sie aus
    der uebergebenen Menge bestimmt.
    """
    # Invertierter Index: Wort → Sätze. Der Kandidatenraum wird über die SELTENSTEN Wörter
    # aufgespannt, sonst vergleicht man jeden „Neubau" mit jedem.
    inv: dict[str, list[int]] = defaultdict(list)
    for i, s in enumerate(saetze):
        for w in s["w"]:
            inv[w].append(i)

    _df = (lambda w: haeufigkeit.get(w, 0)) if haeufigkeit else (lambda w: len(inv[w]))

    paare, gesehen = [], set()
    for i, s in enumerate(saetze):
        # SEED-DECKEL. Ein Wort, das in mehr als SEED_DECKEL Saetzen vorkommt, taugt nicht
        # als Einstieg: es liefert Zehntausende Kandidaten, von denen so gut wie keiner die
        # Enthaltungsschwelle nimmt. Gemessen an AT ab 2024: DREI Woerter erzeugten 40 % aller
        # 61,4 Mio Kandidatenpaare, 44 Woerter zwei Drittel.
        #
        # Verlustfrei, weil ein echtes Paar per Konstruktion mindestens
        # ceil(MIN_ENTHALTUNG * MIN_WORTE) = 3 Woerter teilt und darunter praktisch immer ein
        # selteneres ist. Gemessen gegen den ungedeckelten Lauf: Deckel 5.000 verliert 0 von
        # 66.024 Paaren (AT) bzw. 0 von 18.146 (CH) und halbiert die Kandidaten.
        # Schaerfer waere billiger, aber nicht mehr umsonst: Deckel 1.000 kostet 3 Paare,
        # Deckel 300 kostet 16 (AT) und 170 (CH). Deshalb 5.000.
        #
        # RUECKFALLEBENE ist Pflicht: ein Satz, dessen Woerter ALLE ueber dem Deckel liegen
        # („Neubau Volksschule Wien"), haette sonst gar keinen Seed und faende nie einen
        # Partner. Fuer ihn bleibt das seltenste Wort Seed, auch ueber dem Deckel.
        # Sortierschluessel ist (Haeufigkeit, Wort) — nicht nur die Haeufigkeit. Bei
        # Gleichstand entschied vorher die Iterationsreihenfolge des `frozenset`, also der
        # Zufall: zwei Laeufe ueber denselben Bestand lieferten 18.144 bzw. 18.146 CH-Paare.
        # Ein Abgleich, dessen Ergebnis zwischen zwei Laeufen schwankt, laesst sich weder
        # pruefen noch reproduzieren.
        _sortiert = sorted((w for w in s["w"] if w in inv),
                           key=lambda w: (_df(w), w))
        seeds = [w for w in _sortiert[:SEED_WORTE]
                 if _df(w) <= SEED_DECKEL] or _sortiert[:1]
        kand = {j for w in seeds for j in inv[w] if j != i}
        for j in kand:
            schluessel = (min(i, j), max(i, j))
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            t = saetze[j]
            if s["gen"] == t["gen"]:
                continue                  # dieselbe Quelle dedupliziert sich selbst schon
            # STUFEN-SPERRE. Eine Vorinformation und die Bekanntmachung derselben Vergabe
            # tragen denselben Titel und denselben Kaeufer — sie sind aber zwei SCHRITTE
            # eines Verfahrens, keine Dublette. Gemessen 2026-08-13 vor dieser Sperre:
            # 189 stufen-gemischte Paare (DE 33, AT 156). Mit geladenen Zuschlaegen
            # (`alle_arten`) waere der Fehler gross geworden — ein `can` haette dann gegen
            # das `cn` derselben Vergabe gepaart und beide als Dublette markiert.
            if s["art"] != t["art"]:
                continue
            e = _enthaltung(s["w"], t["w"])
            if e < MIN_ENTHALTUNG:
                continue
            if s["d"] and t["d"] and abs((s["d"] - t["d"]).days) > FENSTER_TAGE:
                continue
            # LOS-GUARD. Gemessen: „GU-Rahmenvertrag 2026 Los 1 - Hochbau" und
            # „… Los 2 - Dach und Fassade" landeten als Dubletten in der Tabelle. Das sind
            # VERSCHIEDENE Lose desselben Rahmenvertrags — zwei Vergaben, auf die man
            # getrennt bietet, kein doppelter Satz. Unterscheiden sie sich in einer Zahl
            # bei sonst gleichem Text, ist das ein Trennmerkmal, kein Rauschen.
            #
            # Die Zahlen kommen aus dem ROHTITEL (`zahlen()`), nicht aus `w` — sonst
            # faellt jede ein- oder zweistellige Losnummer durch das 3-Zeichen-Minimum
            # von `worte()` und die Sperre laeuft leer. Siehe Docstring dort.
            if s["z"] and t["z"] and s["z"] != t["z"]:
                continue
            # GEWERKE-SPERRE. Dieselbe Trennung wie oben, nur ohne Nummern: ein Bauprojekt
            # wird gewerkeweise ausgeschrieben, und die Gewerke stehen als WORT im Titel.
            #   „… Bertha-von-Suttner-Gymnasium – Trockenbauarbeiten"
            #   „… Bertha-von-Suttner-Gymnasium – Stahlbauarbeiten"
            # Der gemeinsame Projektname ist lang, das trennende Wort kurz — die Enthaltung
            # liegt dadurch weit ueber der Schwelle. Merkmal ist nicht die Aehnlichkeit,
            # sondern die RICHTUNG: bei echten Dubletten hat hoechstens EINE Seite eigene
            # Woerter (die andere ist Teilmenge oder gleich), bei Geschwister-Losen haben
            # BEIDE eines. Sprachunabhaengig und ohne Gewerke-Vokabular — was in DE/AT/CH
            # gilt, gilt auch in FR und PL.
            #
            # Gemessen an einem Zufallsschnitt: der beidseitige Eimer enthaelt neben Losen
            # auch voellig unverwandte Vergaben desselben Kaeufers („Sanierung Freibad"
            # gegen „Neubau Schulmensa", „Mittagessen Regelschule" gegen „Kopierpapier").
            # Sie wird deshalb als eigene Belegstufe MARKIERT, nicht verworfen — die Paare
            # bleiben in der Tabelle sichtbar, aber die Anreicherung fasst sie nicht an.
            geschwister = bool((s["w"] - t["w"]) and (t["w"] - s["w"]))
            gleicher_kaeufer = _kaeufer_gleich(s, t)
            # BELEGLAGE statt Schwelle. Ein kurzer Gewerke-Titel („Sanitär, Lüftung,
            # Heizung") steckt vollständig in jedem längeren Titel desselben Gewerks —
            # Enthaltung 1,0 ist dort KEIN Identitätsbeleg. Gemessen: eine Lockerung auf
            # „Titel identisch genügt" haette die Anreicherung von 28 auf 393 Werte
            # gehoben und dabei fremde Fristen uebernommen. Die Stufe steht deshalb in
            # der Tabelle, damit jeder Verbraucher selbst entscheidet.
            kurz = min(len(s["w"]), len(t["w"])) < 6
            beleg = ("geschwister" if geschwister
                     else "kaeufer_und_titel" if gleicher_kaeufer
                     else "nur_titel_kurz" if kurz else "nur_titel")
            # Master = reichere Quelle. Bei Gleichstand der frühere Satz.
            a, b = (s, t) if QUELLEN_RANG.get(s["gen"], 9) <= QUELLEN_RANG.get(t["gen"], 9) else (t, s)
            paare.append({
                "master_id": a["id"], "duplicate_id": b["id"],
                "master_quelle": a["gen"], "duplicate_quelle": b["gen"],
                "enthaltung": round(e, 3), "gleicher_kaeufer": gleicher_kaeufer,
                "beleg": beleg,
                "tage_abstand": abs((s["d"] - t["d"]).days) if s["d"] and t["d"] else None,
                # Was bringt die Dublette MIT, das der Master nicht hat?
                "ergaenzt": ",".join(f for f in ("cpv", "wert", "frist", "nuts", "beschr")
                                     if b[f if f != "cpv" else "cpv"] and not a[f if f != "cpv" else "cpv"]) or None,
            })
    return paare



def schreibe(paare: list[dict], country: str = "DE", vereinigen: bool = False) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    ziel = ROOT / "data" / "gold" / country / "notice_duplicates.parquet"
    ziel.parent.mkdir(parents=True, exist_ok=True)

    # VEREINIGEN statt ersetzen — die Bedingung, ohne die das rollende Fenster Datenverlust
    # waere. Ein Fensterlauf sieht nur die letzten Monate; wuerde er die Datei ueberschreiben,
    # verschwaenden alle Paare aus 2004 bis vorletztes Jahr beim ersten Nachtlauf.
    #
    # Neue Zeile gewinnt bei gleichem Schluessel (master_id, duplicate_id): der frische Lauf
    # hat die aktuellere Anreicherung gesehen. Reihenfolge zaehlt also, `alt` zuerst.
    if vereinigen and ziel.exists():
        try:
            vorher = pq.read_table(ziel).to_pylist()
        except Exception as e:                       # beschaedigte Datei darf den Lauf nicht
            print(f"  ⚠ Bestand nicht lesbar ({e}) — es wird neu geschrieben.")
            vorher = []
        nach_schluessel = {(z["master_id"], z["duplicate_id"]): z for z in vorher}
        vor_n = len(nach_schluessel)
        nach_schluessel.update({(z["master_id"], z["duplicate_id"]): z for z in paare})
        paare = list(nach_schluessel.values())
        print(f"  vereinigt: {vor_n:,} im Bestand + {len(paare) - vor_n:,} neu = {len(paare):,}")

    pq.write_table(pa.Table.from_pylist(paare, schema=pa.schema([
        ("master_id", pa.string()), ("duplicate_id", pa.string()),
        ("master_quelle", pa.string()), ("duplicate_quelle", pa.string()),
        ("enthaltung", pa.float64()), ("gleicher_kaeufer", pa.bool_()),
        ("beleg", pa.string()),
        ("tage_abstand", pa.int64()), ("ergaenzt", pa.string())])),
        ziel, compression="zstd")
    return ziel


def anreichern(country: str = "DE") -> dict:
    """Dubletten-Tabelle → konkrete Feldwerte, die dem Master fehlen.

    Erkennung allein nuetzt nichts: `ergaenzt` sagt nur, DASS die Dublette eine Frist hat.
    Diese Funktion holt den WERT und legt ihn als `notice_enrichment.parquet` ab —
    (notice_id, feld, wert, quelle_notice_id, quelle_gen). Damit kann ein Verbraucher die
    Luecke fuellen, ohne selbst zu joinen, und die Herkunft bleibt an jedem Wert haengen.

    **Nur unstrittige Paare.** Angereichert wird ausschliesslich aus Dubletten mit
    IDENTISCHEM Kaeufer. Gemessen: von 7.000 Paaren tragen 2.950 denselben Kaeufer; die
    uebrigen sind gemischt — „Kunststoff-, Metallbau- und Verglasungsarbeiten" gegen
    „Metallbau, Kunststoff- und Verglasungsarbeiten, Theodor-Heuss Grundschule" ist
    plausibel dasselbe, „Strassenerhaltung Rahmenvertrag 2026-2028" gegen „Rahmenvertrag
    Jahresvertrag Neubau und Unterhaltungsarbeiten" bei Enthaltung 0,8 eher nicht. Aus einem
    Zweifelsfall einen Wert zu uebernehmen hiesse, eine falsche Frist ins Produkt zu
    schreiben — schlimmer als eine fehlende.

    **Es wird nichts ueberschrieben.** Nur Felder, die beim Master NULL sind.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    dup = ROOT / "data" / "gold" / country / "notice_duplicates.parquet"
    if not dup.exists():
        print(f"  keine {dup.name} — erst `finde` laufen lassen")
        return {}
    g = glob.glob(f"{ROOT}/data/silver/{country}/notices/**/*.parquet", recursive=True)
    con = _db.connect()
    FELDER = ("submission_deadline", "performance_nuts", "cpv_main",
              "estimated_value", "description")
    zeilen = []
    for feld in FELDER:
        # Alles als Text: die Zeile traegt `wert` als String, unabhaengig vom Quelltyp.
        # (Hier stand ein `typ`-Ternaer, der nie benutzt wurde und den Eindruck erweckte,
        # es gaebe zwei Umwandlungen. Es gibt nur diese eine.)
        wert_sql = f"CAST(x.{feld} AS VARCHAR)"
        zeilen += [dict(notice_id=r[0], feld=feld, wert=r[1], quelle_notice_id=r[2],
                        quelle_gen=r[3])
                   for r in con.execute(f"""
              SELECT d.master_id, {wert_sql}, d.duplicate_id, d.duplicate_quelle
              FROM read_parquet('{dup.as_posix()}') d
              JOIN read_parquet({g!r}) m ON m.notice_id = d.master_id
              JOIN read_parquet({g!r}) x ON x.notice_id = d.duplicate_id
              -- Auf die BELEGSTUFE filtern, nicht auf `gleicher_kaeufer`. Geschwister-Lose
              -- teilen sich per Definition den Kaeufer — die Spalte ist dort wahr und haette
              -- die Sperre lautlos unterlaufen. `kaeufer_und_titel` schliesst sie aus.
              WHERE d.beleg = 'kaeufer_und_titel'
                AND m.{feld} IS NULL AND x.{feld} IS NOT NULL
           """).fetchall()]

    # WERT MIT SEINER WAEHRUNG. Ein Schaetzwert ohne Waehrung ist keine Information, sondern
    # eine Falle: das abgeloeste `dedupe_at_sources.py` uebertrug bewusst nur EUR, „damit
    # keine Fremdwaehrung stillschweigend als Euro gilt". Diese Sperre darf beim Umzug in die
    # zentrale Firewall nicht verlorengehen — deshalb wandert die Waehrung als EIGENE Zeile
    # aus DEMSELBEN Quellsatz mit, und der Verbraucher entscheidet.
    #
    # Warum das zaehlt: `atverg` fuehrt den Wert zu 69,8 %, TED-AT nur zu 11,0 %. Gemessen
    # 2026-08-14 wuerden 3.922 oesterreichische Leads ohne Wert dadurch einen bekommen —
    # und der Wert traegt das Gebuehrenband.
    zeilen += [dict(notice_id=r[0], feld="estimated_value_waehrung", wert=r[1],
                    quelle_notice_id=r[2], quelle_gen=r[3])
               for r in con.execute(f"""
          SELECT d.master_id, x.value_currency, d.duplicate_id, d.duplicate_quelle
          FROM read_parquet('{dup.as_posix()}') d
          JOIN read_parquet({g!r}) m ON m.notice_id = d.master_id
          JOIN read_parquet({g!r}) x ON x.notice_id = d.duplicate_id
          WHERE d.beleg = 'kaeufer_und_titel'
            AND m.estimated_value IS NULL AND x.estimated_value IS NOT NULL
       """).fetchall()]

    # FRISTVERLAENGERUNG — die einzige Stelle, an der ein Wert NICHT nur eine Luecke
    # fuellt, sondern einen vorhandenen korrigiert. Sie steht deshalb als eigene Feldart
    # `submission_deadline_verlaengert` da und nicht unter `submission_deadline`.
    #
    # Der Fall: TED und die nationale Quelle veroeffentlichen dieselbe Vergabe, die Frist
    # wird spaeter verschoben, und nur eine der beiden Quellen bekommt die Korrektur mit.
    # Der Lead gilt bei uns dann als abgelaufen, obwohl man noch bieten kann — ein Fehler,
    # den der Kunde direkt merkt: er filtert „offen" und die Ausschreibung fehlt.
    #
    # EINDEUTIGKEIT IST PFLICHT. Gemessen an den 109 Kandidaten: 69 davon sind mehrdeutig,
    # weil Behoerden templatisierte Titel benutzen. „REZ SW 45ind JC Rhein-Neckar-Kreis"
    # ist ein Dienststellen-Kuerzel, kein Auftragsgegenstand — drei verschiedene eForms-
    # Bekanntmachungen (24.06./07.07./16.07.) haengen dort an EINER DOeE-Bekanntmachung vom
    # 18.08. Hoechstens eine davon ist die Verlaengerung; welche, ist aus dem Titel nicht
    # zu entscheiden. Uebertragen wird deshalb nur, wo die Zuordnung auf BEIDEN Seiten
    # eindeutig ist (1:1). Bleiben 40 von 109 — der Rest bleibt lieber abgelaufen als
    # falsch verlaengert.
    #
    # `current_date` bewusst zur Laufzeit: was heute verlaengert ist, ist in drei Wochen
    # abgelaufen. Ein eingefrorener Stichtag wuerde die Tabelle still veralten lassen.
    zeilen += [dict(notice_id=r[0], feld="submission_deadline_verlaengert", wert=r[1],
                    quelle_notice_id=r[2], quelle_gen=r[3])
               for r in con.execute(f"""
          WITH k AS (
            SELECT d.master_id, d.duplicate_id, d.duplicate_quelle,
                   CAST(x.submission_deadline AS VARCHAR) AS wert
            FROM read_parquet('{dup.as_posix()}') d
            JOIN read_parquet({g!r}) m ON m.notice_id = d.master_id
            JOIN read_parquet({g!r}) x ON x.notice_id = d.duplicate_id
            WHERE d.beleg = 'kaeufer_und_titel'
              AND m.submission_deadline IS NOT NULL      -- KEINE Luecke, ein falscher Wert
              AND CAST(m.submission_deadline AS DATE) <  current_date
              AND CAST(x.submission_deadline AS DATE) >= current_date),
          z AS (SELECT *, count(*) OVER (PARTITION BY master_id)    AS je_master,
                          count(*) OVER (PARTITION BY duplicate_id) AS je_dublette FROM k)
          SELECT master_id, wert, duplicate_id, duplicate_quelle
          FROM z WHERE je_master = 1 AND je_dublette = 1
       """).fetchall()]

    ziel = ROOT / "data" / "gold" / country / "notice_enrichment.parquet"
    if zeilen:
        pq.write_table(pa.Table.from_pylist(zeilen, schema=pa.schema([
            ("notice_id", pa.string()), ("feld", pa.string()), ("wert", pa.string()),
            ("quelle_notice_id", pa.string()), ("quelle_gen", pa.string())])),
            ziel, compression="zstd")
    from collections import Counter
    je_feld = Counter(z["feld"] for z in zeilen)
    print(f"  Anreicherung: {len(zeilen):,} Werte fuer "
          f"{len({z['notice_id'] for z in zeilen}):,} Bekanntmachungen")
    for f, n in je_feld.most_common():
        print(f"    {f:<22} {n:>6,}")
    return dict(je_feld)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Quellenübergreifender Dublettencheck")
    ap.add_argument("--country", default="DE")
    ap.add_argument("--ab-jahr", type=int, default=dt.date.today().year)
    ap.add_argument("--anreichern", action="store_true",
                    help="nach der Erkennung die fehlenden Feldwerte sammeln")
    ap.add_argument("--fenster-tage", type=int, default=0, metavar="N",
                    help="Nur Bekanntmachungen der letzten N Tage (plus die ohne Datum) "
                         "abgleichen und das Ergebnis mit dem Bestand VEREINIGEN. Der "
                         "inkrementelle Nachtlauf. 0 = volle Historie (Standard).")
    ap.add_argument("--alle-arten", action="store_true",
                    help="auch Zuschläge/Aufhebungen prüfen (Veröffentlichungs-Sicht "
                         "für Marktpuls) statt nur Ausschreibungen")
    a = ap.parse_args(argv)
    print(f"Dublettencheck {a.country}, ab {a.ab_jahr}"
          + (" (alle Bekanntmachungsarten)" if a.alle_arten else ""))
    paare = finde(a.country, a.ab_jahr, a.alle_arten, a.fenster_tage)
    if not paare:
        print("  Keine Dubletten gefunden.")
        return 0
    ziel = schreibe(paare, a.country, vereinigen=bool(a.fenster_tage))
    kombis = Counter(f"{p['master_quelle']} ← {p['duplicate_quelle']}" for p in paare)
    stufen = Counter(p["beleg"] for p in paare)
    sicher = sum(1 for p in paare if p["gleicher_kaeufer"])
    mit_plus = sum(1 for p in paare if p["ergaenzt"])
    print(f"\n  {len(paare):,} Dubletten-Paare, davon {sicher:,} mit identischem Käufer")
    print(f"  {mit_plus:,} bringen ein Feld MIT, das der Master nicht hat")
    print("  Beleglage: " + " · ".join(f"{k}={n:,}" for k, n in stufen.most_common()))
    for k, n in kombis.most_common(8):
        print(f"    {k:<26} {n:>7,}")
    felder = Counter(f for p in paare if p["ergaenzt"] for f in p["ergaenzt"].split(","))
    if felder:
        print("  ergänzte Felder:", ", ".join(f"{k}={n:,}" for k, n in felder.most_common()))
    print(f"\n→ {ziel.relative_to(ROOT)}")
    if a.anreichern:
        print()
        anreichern(a.country)
    return 0


if __name__ == "__main__":
    sys.exit(main())

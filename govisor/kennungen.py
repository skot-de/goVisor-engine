"""Welche ``national_id`` ist eine Kennung — und welche ist nur ein ausgefülltes Feld?

⚠ WARUM ES DIESES MODUL GIBT. Am 2026-10-06 zeigte die Nachfragekarte eine Zeile
„Amt Siek Der Amtsvorsteher · Aachen · 33 km von Warstein". Amt Siek liegt in
Schleswig-Holstein. Die Entität hiess ``id:keineAngabe`` und trug — gemessen im DE-Silber —
**2.198 verschiedene kanonisierte Namen in 1.128 Orten**: Universitätsklinikum Aachen,
Bremer Bäder, Deutscher Bundestag, München Klinik, Handelskammer Hamburg. Ein Platzhalter
im Feld ``national_id`` hatte sie zu EINEM Auftraggeber verschmolzen.

**Eine Liste verbotener Zeichenketten reicht nicht.** Gemessen im DE-Silber tragen
``'8477'`` und ``'00002636'`` dieselbe Form wie eine echte Registernummer — die eine ist
Müll, die andere gehört wirklich einer Stelle (92 Namen, 2 Orte, 99 % teilen einen Namens-
Token). Umgekehrt stehen NUTS-Codes (``DE212``, ``DED21``, ``DEA2D``) und eForms-interne
Organisations-Referenzen (``ORG-0001``) im Feld, die wie Kennungen aussehen und keine sind.
Eine gepflegte Liste altert; die Eigenschaft nicht:

    Eine Kennung, die von zu vielen verschiedenen Namen geteilt wird und für die kein
    gemeinsamer Namens-Beleg vorliegt, ist keine Kennung.

**ZWEI BEINE, und das zweite ist das wichtigere.** Die Streuung allein trifft auch echte
Dach-Kennungen: ``DE129515865`` ist die USt-IdNr der Fraunhofer-Gesellschaft und trägt 70
kanonisierte Namen ("… Einkauf B12", "… Institut für Angewandte Sicherheit AISEC"),
``9110015233841`` die der österreichischen Bundesimmobiliengesellschaft mit 12.736 Zeilen.
Wer die nach Namenszahl verwirft, zerschlägt echte Auftraggeber. Deshalb muss eine Kennung
über der Streuungsgrenze einen **Beleg** bringen: einen signifikanten Namens-Token, den
ein nennenswerter Teil ihrer Namen teilt.

**Der Beleg wird nach Namen UND nach Zeilen gezählt, und das Maximum gilt.** Nur nach Namen
gezählt fiel ``9110002556748`` (Land Niederösterreich mit seinen Strassenbauabteilungen,
7.189 Zeilen) auf 48 % — die 108 seltenen Schreibvarianten wiegen dort so viel wie die
dominanten. Nach Zeilen gezählt trägt derselbe Schlüssel ~100 %. Umgekehrt rettet die
Namenszählung Fälle, in denen eine einzelne Stelle viele Zeilen und einen Schwanz fremder
Namen hat. Beide Zählungen zu fordern wäre scharf, aber falsch scharf; das Maximum lässt
einen Zweifelsfall stehen, statt ihn zu entscheiden.

**KONSERVATIV MIT ABSICHT.** ``BELEG_MINDEST`` liegt bei 30 % und damit UNTERHALB des
gemessenen Tals der Verteilung (DE: Dezil 40–49 % ist mit 26 Kennungen die Senke zwischen
54 und 54). Das ist kein Versehen: oberhalb der Senke liegen die echten Dach-Kennungen,
unterhalb die Platzhalter, und die umstrittene Mitte soll NICHT automatisch entschieden
werden. Sie landet als ``verdacht`` in ``entity_kennung_verdacht.parquet`` und kann in
``curated/<L>_kennung_entscheidung.csv`` von Hand entschieden werden — dieselbe Form, in der
die 6.971 Merge-Kandidaten entschieden wurden. ``scripts/pruefe_kennungen.py`` meldet, wenn
die Senke wegwandert, also wenn die Begründung für die 30 % wegfällt.

**Kein Datenverlust.** Eine verworfene Kennung löscht keine Zeile. Der Satz fällt auf die
Namens-Auflösung zurück (``name:<norm>``), wo er vor eForms ohnehin lag; die Leitweg- und
USt-IdNr-Anker in ``gold.build_entities`` können ihn danach mit ihrem eigenen Token-Guard
wieder zusammenführen. ``party_entity`` behält genau so viele Zeilen wie vorher.

**Sprachgrenze, offen benannt.** Die Stoppwörter für signifikante Token
(``entities.STOPP_TOKEN``) sind deutsch. Für LU (französisch) zählen „ministere",
„administration", „communale" deshalb als signifikant und heben den Beleg-Anteil
künstlich. Gemessene Folge: LU verwirft 3 Kennungen (27 Zeilen) — die Regel ist dort
zurückhaltender als in DE, nicht falscher. Ein Stoppwort-Satz je Länderprofil
(``locales.py``) ist der offene Punkt dazu.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import entities as _entities

# ── Schwellen ────────────────────────────────────────────────────────────────────────────
#
# ⚠ DIE STREUUNGS-SCHWELLE WIRD NICHT GETIPPT, SIE WIRD GEMESSEN. `streuung()` nimmt das
# 99. Perzentil der gemessenen Namen-je-Kennung-Verteilung der Quelle selbst. Gemessen am
# 2026-10-06: DE 5, AT 6, CH 4, LU 5 — bei einem Median von 1 und p90 von 2 in allen vier
# Ländern. Eine getippte 20 hätte in CH nichts gefunden und in DE die Hälfte durchgelassen.
#
# MINDEST_SCHWELLE ist keine zweite Schwelle, sondern ein Entartungsschutz: bei einer sehr
# kleinen Quelle (ein neues Land mit 40 Kennungen) kann p99 auf 1 fallen, und dann hiesse
# die Regel „zwei Schreibweisen eines Namens sind ein Platzhalter". Gemessen ist p90 = 2 in
# JEDEM der vier Länder; unter 3 Namen lässt sich „von zu vielen Namen geteilt" nicht
# behaupten. Greift der Schutz, steht es in `Streuung.schwelle_gegriffen`.
MINDEST_SCHWELLE = 3

# ── DREI URTEILE, NICHT ZWEI ─────────────────────────────────────────────────────────────
#
# Der erste Entwurf kannte nur „fällt" und „fällt nicht". Der Wächter meldete daraufhin 66
# Kennungen zur Entscheidung — und das waren fast alle die ECHTEN: ÖBB (Beleg 100 %),
# Fraunhofer (100 %), Bundesimmobiliengesellschaft (97 %), Autobahn GmbH (99 %). Sie waren
# „nicht entschieden", weil die Regel nur das Verwerfen entschied. Eine Sonde, die das
# Richtige als Arbeitsvorrat meldet, wird abgeschaltet.
#
# Die beiden Grenzen fassen das gemessene Tal der zweigipfeligen Beleg-Verteilung ein:
#
#   Beleg  <  BELEG_MINDEST  → platzhalter   die Regel entscheidet: identifiziert nicht
#   dazwischen               → verdacht      umstritten, gehört in die Hand
#   Beleg  >= BELEG_SICHER   → traegt        die Regel entscheidet: identifiziert
#
# Gemessen am 2026-10-06 über alle Länder: oberhalb von 70 % war JEDER von Hand geprüfte
# Fall echt (ÖBB 100 %, Fraunhofer 100 %, BIG 97 %, Land Niederösterreich 96 %, Bundesamt
# für Bauten und Logistik 81 %, Hessen Mobil 72 %); die Senke liegt bei 40–50 %. Unterhalb
# von 30 % war keiner echt. In der Mitte liegen beide Sorten — BMLV 45 % (echt) neben
# LU99999999 46 % (Müll) —, und genau deshalb entscheidet die Regel dort nicht.
#
# ⚠ BEIDE ZAHLEN SIND GEGENPRÜFBAR, und `scripts/pruefe_kennungen.py` prüft sie: die
# gemessene Senke MUSS zwischen ihnen liegen. Wandert sie heraus, fassen die Grenzen nicht
# mehr das Tal ein und die Begründung ist weg (s. Auto-Memory
# `schwelle-aus-der-quelle-ableiten`).
BELEG_MINDEST = 0.30
BELEG_SICHER = 0.70

# Perzentil für die Schwellen-Ableitung. 0.99 und nicht 0.999, weil die Verteilung bei
# p99.9 schon in den Platzhaltern liegt (DE p99.9 = 24 Namen) — die Schwelle würde dann
# von dem Befund gesetzt, den sie finden soll.
SCHWELLEN_PERZENTIL = 0.99


@dataclass(frozen=True)
class Befund:
    """Eine Kennung mit ihrer gemessenen Streuung und dem Urteil darüber."""

    kennung: str          # normalisierter Schlüssel (wie `gold.normalize_national_id` liefert)
    roh: str              # ein Rohwert, wie er in der Quelle stand — für die Lesbarkeit
    namen: int            # Zahl der distinkten kanonisierten Namen
    zeilen: int           # Zahl der Partei-Zeilen
    anteil_namen: float   # Anteil der NAMEN mit dem häufigsten signifikanten Token
    anteil_zeilen: float  # Anteil der ZEILEN mit dem häufigsten signifikanten Token
    token: str            # dieser Token (leer, wenn keiner signifikant ist)
    urteil: str           # "platzhalter" | "verdacht" | "traegt" — s. die Grenzen oben

    @property
    def beleg(self) -> float:
        return max(self.anteil_namen, self.anteil_zeilen)


@dataclass
class Streuung:
    """Das Ergebnis einer Messung über eine ganze Quelle."""

    schwelle: int                      # angewandte Streuungs-Grenze
    rohe_schwelle: int                 # das gemessene Perzentil VOR dem Entartungsschutz
    schwelle_gegriffen: bool           # True, wenn MINDEST_SCHWELLE gebunden hat
    kennungen: int                     # Kennungen insgesamt
    zeilen: int                        # Partei-Zeilen insgesamt
    befunde: list[Befund] = field(default_factory=list)   # nur oberhalb der Schwelle
    perzentil: float = SCHWELLEN_PERZENTIL
    beleg_mindest: float = BELEG_MINDEST
    beleg_sicher: float = BELEG_SICHER

    @property
    def platzhalter(self) -> frozenset[str]:
        """Kennungen, die NICHT identifizieren — die Regel hat entschieden."""
        return frozenset(b.kennung for b in self.befunde if b.urteil == "platzhalter")

    @property
    def verdacht(self) -> frozenset[str]:
        """Im umstrittenen Band zwischen den Grenzen — bewusst NICHT entschieden."""
        return frozenset(b.kennung for b in self.befunde if b.urteil == "verdacht")

    @property
    def traegt(self) -> frozenset[str]:
        """Streuend, aber mit starkem Beleg — die Regel entscheidet: echte Dach-Kennung."""
        return frozenset(b.kennung for b in self.befunde if b.urteil == "traegt")

    def zeilen_von(self, urteil: str) -> int:
        return sum(b.zeilen for b in self.befunde if b.urteil == urteil)


def perzentil(werte: list[int], p: float) -> int:
    """Nächster Rang, ohne Interpolation — damit zwei Läufe über dieselben Daten dieselbe
    Schwelle ergeben und die Zahl in der Datei nachrechenbar ist."""
    if not werte:
        return 0
    g = sorted(werte)
    return g[min(len(g) - 1, int(p * len(g)))]


def streuung(saetze, *, schluessel, beleg_mindest: float = BELEG_MINDEST,
             beleg_sicher: float = BELEG_SICHER,
             perzentil_p: float = SCHWELLEN_PERZENTIL) -> Streuung:
    """Messe je Kennung, wie viele verschiedene Namen sie trägt, und urteile.

    ``saetze``    — iterierbar über ``(national_id, name, zeilen)``. ``zeilen`` ist die
                    Zahl der Partei-Zeilen mit genau diesem (id, name)-Paar; wer je Zeile
                    iteriert, gibt 1.
    ``schluessel`` — die Normalisierung von ``national_id`` auf den Entity-Schlüssel
                    (``gold.normalize_national_id``). Injiziert, damit dieses Modul nicht
                    gegen ``gold`` zirkulär importiert und testbar bleibt. Gibt sie
                    ``None``, ist der Rohwert schon als Müll erkannt und zählt nicht mit.

    Die Reihenfolge der Sätze ist für das Ergebnis unerheblich (nur Mengen und Summen).
    """
    norms: dict[str, set[str]] = defaultdict(set)
    tok_namen: dict[str, Counter] = defaultdict(Counter)
    tok_zeilen: dict[str, Counter] = defaultdict(Counter)
    zeilen: dict[str, int] = defaultdict(int)
    roh: dict[str, str] = {}

    for national_id, name, n in saetze:
        k = schluessel(national_id)
        if k is None:
            continue
        zeilen[k] += n
        roh.setdefault(k, national_id)
        norm = _entities.normalize_company(name)
        if not norm:
            continue
        neu = norm not in norms[k]
        norms[k].add(norm)
        for t in _entities.signifikante_token(norm):
            tok_zeilen[k][t] += n
            if neu:                         # Namen zählen jeden Namen EINMAL
                tok_namen[k][t] += 1

    rohe = perzentil([len(v) for v in norms.values()], perzentil_p)
    grenze = max(rohe, MINDEST_SCHWELLE)

    befunde: list[Befund] = []
    for k, ns in norms.items():
        if len(ns) <= grenze:
            continue
        an = (tok_namen[k].most_common(1)[0][1] / len(ns)) if tok_namen[k] else 0.0
        az = (tok_zeilen[k].most_common(1)[0][1] / zeilen[k]) if tok_zeilen[k] and zeilen[k] else 0.0
        top = tok_namen[k].most_common(1)[0][0] if tok_namen[k] else ""
        beleg = max(an, az)
        befunde.append(Befund(
            kennung=k, roh=roh.get(k, k), namen=len(ns), zeilen=zeilen[k],
            anteil_namen=an, anteil_zeilen=az, token=top,
            urteil=("platzhalter" if beleg < beleg_mindest
                    else "traegt" if beleg >= beleg_sicher
                    else "verdacht")))
    befunde.sort(key=lambda b: (-b.namen, b.kennung))

    return Streuung(schwelle=grenze, rohe_schwelle=rohe,
                    schwelle_gegriffen=grenze > rohe,
                    kennungen=len(norms), zeilen=sum(zeilen.values()),
                    befunde=befunde, perzentil=perzentil_p,
                    beleg_mindest=beleg_mindest, beleg_sicher=beleg_sicher)


def senke(streu: Streuung, dezile: int = 10) -> float:
    """Wo liegt das Tal der Beleg-Verteilung oberhalb der Schwelle?

    Die Begründung für ``BELEG_MINDEST`` ist, dass die Verteilung zweigipfelig ist und 30 %
    unterhalb des Tals liegen. Diese Funktion rechnet das Tal aus den aktuellen Daten
    zurück, damit der Wächter merkt, wenn die Begründung wegfällt — statt dass die Zahl
    stehen bleibt und niemand sie mehr prüfen kann.

    Gibt die Mitte des dünnsten Dezils zwischen dem ersten und dem letzten besetzten
    zurück, oder ``-1.0``, wenn zu wenige Befunde für eine Aussage vorliegen.
    """
    if len(streu.befunde) < 3 * dezile:          # unter 30 Befunden ist ein „Tal" Rauschen
        return -1.0
    h = Counter(min(dezile - 1, int(b.beleg * dezile)) for b in streu.befunde)
    besetzt = sorted(d for d in h)
    if len(besetzt) < 3:
        return -1.0
    innen = besetzt[1:-1]                        # Ränder sind die Gipfel, nicht das Tal
    tiefstes = min(innen, key=lambda d: h[d])
    return (tiefstes + 0.5) / dezile


def entscheidungen_lesen(pfade, schluessel=None) -> dict[str, str]:
    """Kuratierte Urteile aus ``<L>_kennung_entscheidung.csv`` — Kennung → Urteil.

    Spalten: ``kennung``, ``urteil`` (``platzhalter`` | ``traegt`` | ``offen``), ``grund``.
    ``offen`` heisst „gesehen, noch nicht entschieden" und zählt als Entscheidung im Sinne
    des Wächters (er meldet NEUE Fälle, keine bekannten).

    ⚠ ROHWERT ODER SCHLÜSSEL — BEIDES WIRD ANGENOMMEN. Der erste Entwurf nahm nur den
    normalisierten Schlüssel, der Wächter druckte aber den Rohwert („Kennung 'DE 126118252'").
    Von Hand eingetragen traf kein einziges der sechs Urteile, und die Sonde meldete beides
    zugleich: „nicht entschieden" UND „Handurteil ohne Gegenstück". Deshalb wird jede Zeile
    auch durch ``schluessel`` geschickt und unter beiden Formen eingetragen — wer aus der
    Sondenausgabe kopiert, trifft.

    ⚠ ZWEI PFADE, EINER GEWINNT. ``curated/`` liegt im Repo und ist versioniert,
    ``data/curated/`` auf der externen Platte und ist es nicht. Diese Datei trägt
    Handarbeit und gehört ins Repo, deshalb steht der Repo-Pfad zuerst — gelesen werden
    beide, der erste Treffer je Kennung gewinnt. (``gold._load_entity_aliases``
    beschreibt in seinem Docstring dieselbe Reihenfolge, liest aber nur
    ``data/curated/``; das ist ein eigener Befund, hier nicht stillschweigend mitgeändert.)
    """
    import csv

    out: dict[str, str] = {}
    for p in pfade:
        if not p or not p.exists():
            continue
        with p.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("kennung") or "").strip()
                u = (row.get("urteil") or "").strip().lower()
                if not k or not u:
                    continue
                formen = [k]
                if schluessel is not None:
                    norm = schluessel(k)
                    if norm:
                        formen.append(norm)
                for f in formen:
                    if f not in out:
                        out[f] = u
    return out
